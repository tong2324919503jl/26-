"""Fair development-only comparison through one evaluator-owned simulator.

Extract the pinned ZIP to a fresh temporary directory. Original package names
live only in separate child processes. Cases and source truth stay here;
workers receive only public action responses, with no case id or seed.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter
import hashlib
import json
import math
from pathlib import Path,PurePosixPath
import queue
import statistics
import subprocess
import subprocess
import sys
import tempfile
import threading
import time
import zipfile

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from problem3.scenarios import generate_suite
from problem3.simulator import LocalSimulator,ObservationClient
from problem4.coverage import directional_cover_certificate,segment_cover_radius

ZIP_NAME='B题第三四问_第三轮演练包.zip'
ZIP_SHA='bce6c749b633275e01c20913d1b9980b4f810cf6fad57f9de58732edbe5b4332'
ZIP_COMMIT='8aefbd7'


def archived_teammate_package(destination):
    """Recover the removed historical delivery from Git only for its replay."""
    original = ROOT / ZIP_NAME
    if original.is_file():
        return original
    result = subprocess.run(['git', 'show', f'{ZIP_COMMIT}:{ZIP_NAME}'], cwd=ROOT,
                            capture_output=True)
    if result.returncode:
        raise FileNotFoundError(
            f'Historical package requires Git commit {ZIP_COMMIT}; '
            'use a full-history checkout to replay the v3 comparison.')
    if hashlib.sha256(result.stdout).hexdigest() != ZIP_SHA:
        raise ValueError('Historical archive fingerprint mismatch')
    archive = destination / 'historical_p34_round3.zip'
    archive.write_bytes(result.stdout)
    return archive


def inspect_extract(archive,destination):
    raw=archive.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ZIP_SHA:raise ValueError('Archive fingerprint changed: review required')
    rows=[];roots=set();total=0
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            name=item.filename
            if '\\' in name or ':' in name or '\x00' in name:raise ValueError('Unsafe archive member')
            parts=PurePosixPath(name).parts
            if not parts or PurePosixPath(name).is_absolute() or '..' in parts:raise ValueError('Unsafe archive path')
            if (item.external_attr>>16)&0o170000==0o120000:raise ValueError('Archive symlink refused')
            roots.add(parts[0]);total+=item.file_size
            if total>32_000_000:raise ValueError('Archive size limit')
            if len(parts)<2 or item.is_dir():continue
            relative=Path(*parts[1:]);target=(destination/relative).resolve()
            if not target.is_relative_to(destination.resolve()):raise ValueError('Archive path escaped')
            data=z.read(item)
            if relative.suffix in ('.py','.json'):
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            if relative.suffix=='.py':
                tree=ast.parse(data.decode('utf-8-sig'))
                imports=sorted({ast.unparse(n) for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))})
                rows.append({'path':relative.as_posix(),'sha256':hashlib.sha256(data).hexdigest(),'imports':imports})
    if len(roots)!=1:raise ValueError('Expected one archive root')
    return {'zip_sha256':ZIP_SHA,'uncompressed_bytes':total,'python_modules':rows,
            'execution_review':'Reviewed imports, protocol, simulation, run entries and factory chain. No launcher/main/evaluate or teammate LocalWorld is executed. HTTP/process/write attempts are blocked in the worker.'}


class Worker:
    def __init__(self,implementation,root,problem,target=None):
        command=[sys.executable,'-I','-B','-u',str(ROOT/'scripts/compare_teammate_p34_worker.py'),implementation,str(root),str(problem)]
        if target:command.append(target)
        self.process=subprocess.Popen(command,cwd=root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                      text=True,encoding='utf-8',bufsize=1,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.events=queue.Queue();self.errors=[]
        def stdout():
            for line in self.process.stdout:self.events.put(line)
            self.events.put(None)
        def stderr():
            for line in self.process.stderr:self.errors.append(line.rstrip())
        threading.Thread(target=stdout,daemon=True).start();threading.Thread(target=stderr,daemon=True).start()
        self.ready=self.read()
        if self.ready.get('type')!='ready':raise RuntimeError('Worker failed to initialize')
    def read(self):
        line=self.events.get(timeout=1200)
        if line is None:raise RuntimeError('Worker exited: '+' | '.join(self.errors[-8:]))
        return json.loads(line)
    def write(self,data):
        self.process.stdin.write(json.dumps(data,allow_nan=False)+'\n');self.process.stdin.flush()
    def close(self):
        if self.process.poll() is None:
            self.write({'type':'stop'})
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()


def public_completion(problem,measured,positive,cleared,cache):
    if len(cleared)==16:return {'certified':True,'reason':'sixteen_public_clear_successes'}
    if positive-cleared:return {'certified':False,'reason':'known_channel_not_cleared'}
    unknown=sorted(set(range(1,21))-positive-cleared);checks=[]
    for channel in unknown:
        points=tuple(sorted(set(measured[channel])))
        key=(problem,points)
        if key not in cache:
            if not points:
                cache[key]={'certified':False,'reason':'no_observations_for_unknown_channel','max_radius_bound_m':None}
            elif problem==3:
                bound=segment_cover_radius(points,(1.,0.),-1801.)['radius_bound_m']
                cache[key]={'certified':bool(points) and bound<999.999,'max_radius_bound_m':bound}
            else:
                report=directional_cover_certificate(points,early_exit=False)
                cache[key]={k:v for k,v in report.items() if k not in ('program_runtime_s',)}
        checks.append({'channel':channel,'observed_station_count':len(points),'certificate':cache[key]})
    return {'certified':bool(checks) and all(r['certificate']['certified'] for r in checks),
            'reason':'independent_public_per_channel_coverage','unknown_channels':unknown,'checks':checks}


def episode(worker,case,problem,cache):
    sim=LocalSimulator(case);client=ObservationClient(sim);measured={c:[] for c in range(1,21)}
    positive=set();cleared=set();protocol_error=None;actions=Counter();exit_time=None
    worker.write({'type':'run'})
    while True:
        message=worker.read()
        if message['type']=='result':break
        if message['type']!='action':raise RuntimeError('Unexpected worker event')
        path=message['path'];payload=message['payload'];actions[path]+=1
        try:
            if path=='/enter':response=sim.enter()
            elif path=='/exit':response=sim.exit();exit_time=sim.virtual_time_s
            elif path in ('/measure','/clear'):
                position=(payload['position']['x'],payload['position']['y']);channel=payload['channel']
                response=client.measure(position,channel) if path=='/measure' else client.clear(position,channel)
                if path=='/measure':
                    measured[channel].append(tuple(position))
                    if response['measure_result'] in ('direction','near'):positive.add(channel)
                elif response['clear_result']=='success':cleared.add(channel)
            else:raise ValueError('Unexpected endpoint')
            worker.write({'response':response,'public_state':{'position':client.position,'current_channel':client.current_channel,
                          'virtual_time_s':client.virtual_time_s}})
        except Exception as exc:
            protocol_error=f'{type(exc).__name__}: {exc}';worker.write({'error':protocol_error})
    if sim.active:sim.exit()
    stats=sim.statistics();proof=public_completion(problem,measured,positive,cleared,cache)
    policy=message['policy'];claimed=bool(policy.get('complete_certificate',policy.get('completion_certified',False)))
    all_cleared=stats['cleared_count']==stats['source_count']
    certified=claimed and proof['certified'] and all_cleared and bool(message['normal_exit']) and not message['error'] and not protocol_error
    physical=stats['movement_m']/5+stats['measure']*5+stats['switch']+stats['failed_clear']*3+(stats['clear']-stats['failed_clear'])*5
    if abs(physical-stats['virtual_time_s'])>1e-5:raise AssertionError('Physical accounting mismatch')
    if stats['cleared_count']!=len(cleared):raise AssertionError('Public/truth clearance mismatch')
    return {'case_id':case.get('case_id',case.get('name')),'case_sha256':hashlib.sha256(json.dumps(case,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            **stats,'source_truth_all_cleared':all_cleared,'policy_claimed_complete':claimed,'independent_public_completion':proof,
            'certified_full_clear':certified,'actual_exit_time_s':exit_time,'normal_exit':message['normal_exit'],
            'error':message['error'] or protocol_error,'policy_cpu_s':message['policy_cpu_s'],'policy_wall_s':message['policy_wall_s'],
            'endpoint_counts':dict(actions),'policy':policy}


def summarize(rows,threshold):
    complete=[r for r in rows if r['certified_full_clear']]
    values=[r['average_clear_time_s'] for r in complete];cpu=[r['policy_cpu_s'] for r in rows]
    return {'cases':len(rows),'all_cleared':sum(r['source_truth_all_cleared'] for r in rows),'certified_complete':len(complete),
            'complete_fraction':len(complete)/len(rows),'mean_seconds_per_source':statistics.mean(values) if len(complete)==len(rows) else None,
            'completed_case_mean_seconds_per_source':statistics.mean(values) if values else None,
            'p90_seconds_per_source':sorted(values)[math.ceil(.9*len(values))-1] if len(complete)==len(rows) else None,
            'weighted_seconds_per_source':sum(r['virtual_time_s'] for r in complete)/sum(r['cleared_count'] for r in complete) if complete else None,
            'threshold_s':threshold,'threshold_passes':sum(v<=threshold for v in values),'threshold_pass_rate':sum(v<=threshold for v in values)/len(rows),
            'cpu_total_s':sum(cpu),'cpu_mean_s':statistics.mean(cpu),'cpu_p90_s':sorted(cpu)[math.ceil(.9*len(cpu))-1],
            'cpu_max_s':max(cpu),'wall_total_s':sum(r['policy_wall_s'] for r in rows),
            'failure_case_ids':[r['case_id'] for r in rows if not r['certified_full_clear']]}


def run(count=48,problems=(3,4),split='development_v3',targets=None,output_path=None):
    if split not in ('development_v2','development_v3','holdout_v3','stress_v3'):raise ValueError('Unsupported split')
    if count<1:raise ValueError('Positive case count required')
    if targets and len(problems)!=1:raise ValueError('--targets requires one --problem')
    suffix=f'_p{problems[0]}' if len(problems)==1 else ''
    if targets:suffix+='_'+hashlib.sha256('|'.join(targets).encode()).hexdigest()[:8]
    output=Path(output_path) if output_path else ROOT/f'validation/compare_teammate_p34_{split}_{count}{suffix}.json'
    if not output.is_absolute():output=ROOT/output
    output=output.resolve()
    if not any(output.is_relative_to(ROOT/folder) for folder in ('validation','tmp')):raise ValueError('Comparison output must stay under validation/ or tmp/')
    if output.exists():raise FileExistsError('Comparison result already exists; keep the previous snapshot')
    temp=tempfile.TemporaryDirectory(prefix='compare-teammate-p34-');extracted=Path(temp.name).resolve()
    def owned_temp():
        if extracted.parent!=Path(tempfile.gettempdir()).resolve() or not extracted.name.startswith('compare-teammate-p34-'):
            raise RuntimeError('Refuse cleanup outside the owned temporary directory')
    owned_temp();body={'split':split,'cases_per_problem':count,'zip':ZIP_NAME,'zip_sha256':ZIP_SHA,'results':{},
           'scope':'Same evaluator-owned LocalSimulator and ObservationClient. No source truth, seed, family or case_id is sent to either worker. Primary metric is per-case mean of actual exit virtual time / cleared count.',
           'cpu_scope':'Worker process CPU, including policy construction and first-case cache initialization; wall time additionally includes pipe waits. No platform calls.'}
    body['evaluator_sha256']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
        ('scripts/compare_teammate_p34.py','scripts/compare_teammate_p34_worker.py','problem3/simulator.py','problem3/scenarios.py','problem4/coverage.py')}
    try:
        body['archive_review']=inspect_extract(archived_teammate_package(extracted),extracted)
        for problem in problems:
            cases=generate_suite(problem,split,count)
            body['results'][str(problem)]={}
            variants=[(target,ROOT,target) for target in targets] if targets else [('ours',ROOT,None)]
            variants.append(('teammate',extracted,None))
            for name,folder,target in variants:
                implementation='teammate' if name=='teammate' else 'ours'
                worker=Worker(implementation,folder,problem,target);rows=[];cache={}
                try:
                    for index,case in enumerate(cases):
                        rows.append(episode(worker,case,problem,cache))
                        if (index+1)%8==0:
                            averages=[r['average_clear_time_s'] for r in rows if r['average_clear_time_s'] is not None]
                            print(problem,name,index+1,round(statistics.mean(averages),3) if averages else None,flush=True)
                finally:worker.close()
                summary=summarize(rows,220 if problem==3 else 400)
                body['results'][str(problem)][name]={'worker_metadata':worker.ready,'summary':summary,'episodes':rows,'stderr':worker.errors}
                output.parent.mkdir(parents=True,exist_ok=True)
                output.write_text(json.dumps(body,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
                print('SUMMARY',problem,name,summary,flush=True)
        report=['# 队友第三轮 ZIP：同一模拟器配对比较','',f'每问均使用显式指定的 `{split}` 前 {count} 例。原 ZIP SHA256：`{ZIP_SHA}`。没有连接平台。','',
                '两方均在独立进程中运行，只接收同一 LocalSimulator 的公开接口响应；算法进程不接收案例编号、种子或源真值。队友使用压缩包原配置和原 factory，未执行其模拟器或启动器。原包运行时解压到临时目录，用后清理。','',
                '| 问题 | 分支 | 平均秒/源 | p90 | 达标率 | 证书及全清 | 平均CPU秒/例 |','|---|---|---:|---:|---:|---:|---:|']
        for problem,runs in body['results'].items():
            for name,data in runs.items():
                s=data['summary'];report.append(f"| {problem} | {name} | {s['mean_seconds_per_source']} | {s['p90_seconds_per_source']} | {s['threshold_passes']}/{count} | {s['certified_complete']}/{count} | {s['cpu_mean_s']:.4f} |")
        report += ['', '第三问统一按220秒、第四问按400秒，均包含失败clear、切频道、移动及最后清除后为证明完整性所需的搜索；平均值先逐例计算再平均。p90使用升序第 ceil(0.9n) 项。JSON另列总时间/总清除数的加权汇总，不作为目标判定。',
                   '', '每例同时记录算法自报证书、按公开动作逐频道独立验证的覆盖证书、实际源真值全清核验及实际exit时间；错误退出不会被补发exit改判成功。CPU为进程CPU时间，包含策略构造和首次证书缓存建立；管道等待仅计入另列的wall时间。',
                   '', '这是显式指定的自建集合配对比较，不是官方成绩；程序不读取其它集合。留出/压力选项只应在候选冻结后使用。逐例结果、导入路径、原配置、ZIP静态审阅和成本核验见同名JSON。']
        output.with_suffix('.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    finally:
        owned_temp();temp.cleanup()
    return body


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--count',type=int,default=48)
    parser.add_argument('--problem',type=int,choices=(3,4));parser.add_argument('--split',choices=('development_v2','development_v3','holdout_v3','stress_v3'),default='development_v3')
    parser.add_argument('--targets',nargs='+',help='One or more module:class targets for the selected problem; teammate is always included')
    parser.add_argument('--output',help='New JSON output under validation/ or tmp/; existing files are preserved')
    args=parser.parse_args();run(args.count,(args.problem,) if args.problem else (3,4),args.split,args.targets,args.output)

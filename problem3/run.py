"""Shared local/online command line; local is the safe reproducible default."""
from __future__ import annotations

import argparse
import html
import json
import math
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def draw_route(case, events, destination):
    points = [tuple(e['position']) for e in events]
    points = [(0, 0)]+[p for i,p in enumerate(points) if i == 0 or p != points[i-1]]
    limit = max([2300]+[max(abs(x),abs(y))+150 for x,y in points])
    def xy(p):
        return (410+350*p[0]/limit, 400-350*p[1]/limit)
    def circ(p, r, color, extra=''):
        x,y=xy(p)
        return f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" fill="{color}" {extra}/>'
    coords = ' '.join(f'{x:.2f},{y:.2f}' for x,y in map(xy,points))
    lines = ['<svg xmlns="http://www.w3.org/2000/svg" width="820" height="840" viewBox="0 0 820 840">',
             '<rect width="820" height="840" fill="#fafafa"/>',
             f'<text x="28" y="32" font-family="sans-serif" font-size="20">{html.escape(case["case_id"])}</text>',
             '<text x="28" y="58" font-family="sans-serif" font-size="13">Synthetic local case; blue: path, red: sources, arrows: emission orientation</text>',
             circ((0,0),1800*350/limit,'none','stroke="#aaa" stroke-dasharray="5 4"'),
             f'<polyline points="{coords}" fill="none" stroke="#3977bc" stroke-width="1.3" opacity=".65"/>']
    for s in case['sources']:
        p=(s['x'],s['y']); x,y=xy(p)
        lines.append(circ(p,4,'#c64343'))
        lines.append(f'<text x="{x+6:.2f}" y="{y-6:.2f}" font-family="sans-serif" font-size="11">{s["channel"]}</text>')
        if s['orientation_deg'] is not None:
            a=math.radians(s['orientation_deg'])
            dx,dy=20*math.cos(a),-20*math.sin(a)
            lines.append(f'<path d="M{x:.2f},{y:.2f} l{dx:.2f},{dy:.2f}" stroke="#c64343" stroke-width="2"/>')
    lines += [circ((0,0),5,'#111'), '<text x="28" y="815" font-family="sans-serif" font-size="13">Black: start (0,0). Dashed circle: 1800 m target boundary. Truth is shown only after simulation.</text>', '</svg>']
    destination.write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main(problem):
    parser=argparse.ArgumentParser(description=f'问题{problem}：默认运行本地自建样本；--online连接已就绪的平台')
    parser.add_argument('--online',action='store_true')
    parser.add_argument('--robot-id')
    parser.add_argument('--base-url',default='http://127.0.0.1:2026')
    strategies = ('adaptive','v4','previous','legacy','baseline','optical') if problem == 4 else ('adaptive','v4','previous','baseline','optical')
    parser.add_argument('--strategy',choices=strategies,default='adaptive')
    parser.add_argument('--version',action='store_true',help='Print the selected algorithm version and exit')
    parser.add_argument('--case',type=Path,help='Local case JSON; relative to this problem directory')
    parser.add_argument('--index',type=int,default=3,help='Built-in development case index')
    parser.add_argument('--config',type=Path,help='Fixed policy config JSON; relative to this problem directory')
    parser.add_argument('--output-dir',type=Path,help='Output directory; relative to this problem directory')
    args=parser.parse_args()
    from scripts.benchmark_search import get_algorithm_version
    version=get_algorithm_version(problem,args.strategy)
    print(f'问题{problem} strategy={args.strategy} algorithm_version={version}',flush=True)
    if args.version:
        return 0
    here=ROOT/f'problem{problem}'
    def resolve(p):
        return p if p.is_absolute() else here/p
    config=json.loads(resolve(args.config).read_text(encoding='utf-8')) if args.config else None
    output=resolve(args.output_dir) if args.output_dir else here/'results'
    output.mkdir(parents=True,exist_ok=True)
    if not args.online:
        if args.robot_id:
            parser.error('--robot-id only applies with --online')
        from problem3.scenarios import generate_case
        from scripts.benchmark_search import run_case
        case=json.loads(resolve(args.case).read_text(encoding='utf-8')) if args.case else generate_case(problem,args.index)
        if case.get('problem') != problem:
            parser.error('The selected case belongs to a different problem')
        if not args.case:
            examples=here/'examples'; examples.mkdir(parents=True,exist_ok=True)
            (examples/'demo_case.json').write_text(json.dumps(case,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        row,events=run_case(case,args.strategy,config,record=True)
        row['algorithm_version']=version
        row.setdefault('policy',{})['algorithm_version']=version
        (output/'demo_result.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (output/'demo_trace.jsonl').write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in events),encoding='utf-8')
        draw_route(case,events,output/'demo_route.svg')
        average = ('无定义' if row['average_clear_time_s'] is None else
                   f"{row['average_clear_time_s']:.1f} 秒/源")
        print(f"本地自建案例 {case['case_id']}：清除 {row['cleared_count']}/{row['source_count']}，"
              f"总虚拟耗时 {row['virtual_time_s']:.1f} 秒，平均 {average}，"
              f"完成确认={row['completion_certified']}。")
        print(f"结果：{output/'demo_result.json'}")
        if row['error']:
            print(row['error'],file=sys.stderr)
        return 0 if row['certified_full_clear'] else 1
    if not args.robot_id:
        parser.error('--online requires --robot-id with the logged-in team ID')
    if args.case:
        parser.error('--case cannot be combined with --online')
    from problem3.client import HttpClient, BudgetExceeded
    from scripts.benchmark_search import get_policy
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]
    live=output/'online'; live.mkdir(parents=True,exist_ok=True)
    client=HttpClient(args.base_url,args.robot_id,live/f'{stamp}_client_trace.jsonl')
    policy=get_policy(problem,args.strategy,config)
    started=time.perf_counter()
    result={}
    failure=None
    exited=False
    entered=False
    try:
        response=client.enter()
        if response.get('accepted') is not True:
            raise RuntimeError('平台拒绝进入：检查所选模块、接口就绪状态和参赛队号')
        entered=True
        print(f"已进入，实际剩余运行时间 {response['remaining_real_duration_s']} 秒。",flush=True)
        result=policy.run(client)
        response=client.exit()
        exited=response.get('accepted') is True
        if not exited:
            raise RuntimeError('平台未接受退出请求')
    except BudgetExceeded as exc:
        failure=str(exc)
        if client.can_exit:
            try:
                exited=client.exit().get('accepted') is True
            except Exception as exit_error:
                failure+=f'; exit: {exit_error}'
    except (Exception, KeyboardInterrupt) as exc:
        # Unknown request outcomes must not trigger a different action.
        failure=f'{type(exc).__name__}: {exc}'
    count=len(policy.cleared)
    pending = client.pending_request
    # Without a confirmed /exit, later accepted-but-unobserved actions or an
    # automatic timeout may make the platform's final totals differ from these.
    statistics_final = exited and pending is None
    observed_average = client.virtual_time_s/count if count else None
    result['algorithm_version']=version
    summary=dict(problem=problem,strategy=args.strategy,provenance='official_platform_client_observations',
                 algorithm_version=version,
                 platform_case_code=None,test_module='fill_from_platform_ui',source_count=None,
                 cleared_count=count,cleared_fraction=None,virtual_time_s=client.virtual_time_s,
                 average_clear_time_s=observed_average if statistics_final else None,
                 observed_average_clear_time_s=observed_average,
                 statistics_final=statistics_final,statistics_scope='accepted_responses_only',
                 pending_request_id=pending.get('request_id') if pending else None,
                 local_program_runtime_s=time.perf_counter()-started,
                 platform_program_runtime_s=None,entered=entered,exit_accepted=exited,
                 policy=result,error=failure,
                 note='平台案例编码/正式运行时间从界面填写；演练源总数仅在结束后可见；正式测试不公开总数。未确认退出时，虚拟时间与清除数仅是已确认观测，不能当作平台最终成绩。')
    dest=live/f'{stamp}_summary.json'
    dest.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'记录已保存：{dest}')
    print('请在平台确认结束状态，并导出平台加密日志；本地记录不能替代官方日志。')
    if failure:
        print(failure,file=sys.stderr)
    return 0 if not failure and exited and result.get('completion_certified',result.get('coverage_complete')) else 1

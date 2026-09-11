"""Read-only paired development-episode audit of existing legal branches.

The post-hoc oracle is a performance ceiling for this branch collection,
not an executable strategy. It never uses official logs or held-out files.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
FOLDER=ROOT/'problem4/results/iterations_v3'


def containers(value,path=()):
    if isinstance(value,dict):
        for key in ('episodes','rows'):
            if isinstance(value.get(key),list) and value[key] and isinstance(value[key][0],dict):
                if any('case_id' in r for r in value[key]):yield path+(key,),value[key]
        for key,child in value.items():
            if key not in ('episodes','rows') and isinstance(child,(dict,list)):yield from containers(child,path+(key,))
    elif isinstance(value,list):
        for i,child in enumerate(value):
            if isinstance(child,dict):yield from containers(child,path+(str(i),))


def normalize(row):
    case_id=row.get('case_id','')
    if not case_id.startswith('local_p4_development_v2_'):return None,'not_development_v2_case'
    sim=row.get('sim',row);policy=row.get('policy',{})
    if row.get('error') or sim.get('error'):return None,'error'
    source_count=sim.get('source_count');cleared=sim.get('cleared_count')
    if not source_count or cleared!=source_count:return None,'not_full_clear'
    if not policy.get('completion_certified',False):return None,'no_completion_certificate'
    if len(policy.get('cleared_channels',[]))!=cleared:return None,'clear_metadata_mismatch'
    time=sim.get('virtual_time_s');average=sim.get('average_clear_time_s')
    if not isinstance(time,(int,float)) or not math.isfinite(time) or time<=0:return None,'invalid_time'
    if average is None or abs(average-time/cleared)>1e-5:return None,'average_is_not_completion_time_per_source'
    expected=sim.get('movement_m',math.nan)/5+sim.get('measure',math.nan)*5+sim.get('switch',math.nan)
    expected+=sim.get('failed_clear',math.nan)*3+(sim.get('clear',math.nan)-sim.get('failed_clear',math.nan))*5
    if not math.isfinite(expected) or abs(expected-time)>1e-4:return None,'physical_cost_mismatch'
    return {'case_id':case_id,'source_count':source_count,'time_s':time,'average_s':time/source_count,
            'movement_m':sim['movement_m'],'actions':sim.get('actions'),'termination':policy.get('termination_reason'),
            'algorithm_version':policy.get('algorithm_version'),'coverage_points':policy.get('effective_settings',{}).get('coverage_points')},None


def collect():
    branches=[];excluded=[];files=[]
    for path in sorted(FOLDER.rglob('*.json')):
        name=path.name.lower()
        if 'development_v2' not in name or any(word in name for word in ('holdout','stress','oracle')):continue
        raw_bytes=path.read_bytes();data=json.loads(raw_bytes);found=False
        for location,raw in containers(data):
            found=True;rows=[];errors=Counter()
            for item in raw:
                row,error=normalize(item)
                if error:errors[error]+=1
                else:rows.append(row)
            name=path.name+'#'+'/'.join(location[:-1])
            if errors or len({row['case_id'] for row in rows})!=len(rows):
                excluded.append({'branch':name,'raw_cases':len(raw),'errors':dict(errors),'duplicate_case_ids':len({r['case_id'] for r in rows})!=len(rows)})
                continue
            rows.sort(key=lambda r:r['case_id'])
            branches.append({'name':name,'rows':rows,'cases':len(rows),'mean_s':statistics.mean(r['average_s'] for r in rows),
                             'weighted_s':sum(r['time_s'] for r in rows)/sum(r['source_count'] for r in rows)})
        if found:files.append({'name':path.name,'sha256':hashlib.sha256(raw_bytes).hexdigest()})
    # Case identity and denominator must agree across every retained run.
    counts={}
    for branch in branches:
        for row in branch['rows']:
            old=counts.setdefault(row['case_id'],row['source_count'])
            if old!=row['source_count']:raise AssertionError('Same case_id has different source count')
    return branches,excluded,files


def audit_scope(branches,count):
    ids=[f'local_p4_development_v2_{i:04d}' for i in range(count)]
    choices=[];aliases={};signatures={}
    for branch in branches:
        rows={row['case_id']:row for row in branch['rows']}
        if not all(key in rows for key in ids):continue
        selected=[rows[key] for key in ids]
        signature=tuple(round(row['time_s'],6) for row in selected)
        if signature in signatures:
            aliases[signatures[signature]].append(branch['name']);continue
        signatures[signature]=branch['name'];aliases[branch['name']]=[branch['name']]
        choices.append({'name':branch['name'],'rows':selected,'mean_s':statistics.mean(r['average_s'] for r in selected),
                        'weighted_s':sum(r['time_s'] for r in selected)/sum(r['source_count'] for r in selected),
                        'original_cases':branch['cases']})
    choices.sort(key=lambda b:b['mean_s'])
    winners=Counter();oracle=[]
    for i,key in enumerate(ids):
        costs=[choice['rows'][i]['average_s'] for choice in choices];best=min(costs)
        tied=[j for j,cost in enumerate(costs) if abs(cost-best)<1e-6]
        for j in tied:winners[choices[j]['name']]+=1/len(tied)
        row=choices[tied[0]]['rows'][i]
        oracle.append({'case_id':key,'source_count':row['source_count'],'average_s':best,'time_s':row['time_s'],
                       'winner_names':[choices[j]['name'] for j in tied],
                       'improvement_over_best_fixed_s':choices[0]['rows'][i]['average_s']-best})
    # A greedy portfolio quantifies whether gains depend on dozens of branches.
    incumbent=[row['average_s'] for row in choices[0]['rows']];portfolio=[choices[0]['name']];curve=[]
    for size in range(min(12,len(choices))):
        if size:
            candidate=min((c for c in choices if c['name'] not in portfolio),
                          key=lambda c:sum(min(a,b['average_s']) for a,b in zip(incumbent,c['rows'])))
            proposed=[min(a,b['average_s']) for a,b in zip(incumbent,candidate['rows'])]
            if sum(incumbent)-sum(proposed)<1e-7:break
            incumbent=proposed;portfolio.append(candidate['name'])
        curve.append({'branches':portfolio.copy(),'mean_s':statistics.mean(incumbent)})
    result={'cases':count,'eligible_run_records':sum(len(v) for v in aliases.values()),'unique_time_vectors':len(choices),
            'best_fixed_branch':choices[0]['name'],'best_fixed_mean_s':choices[0]['mean_s'],'best_fixed_weighted_s':choices[0]['weighted_s'],
            'oracle_mean_s':statistics.mean(r['average_s'] for r in oracle),
            'oracle_weighted_s':sum(r['time_s'] for r in oracle)/sum(r['source_count'] for r in oracle),
            'oracle_pass400':sum(r['average_s']<=400 for r in oracle),'oracle_pass390':sum(r['average_s']<=390 for r in oracle),
            'winners_fractional_ties':winners.most_common(),'greedy_portfolio':curve,'oracle_rows':oracle,
            'branch_rankings':[{k:v for k,v in c.items() if k!='rows'}|{'aliases':aliases[c['name']]} for c in choices]}
    return result


def run():
    branches,excluded,files=collect()
    results={str(count):audit_scope(branches,count) for count in (48,96,384)}
    body={'metric':'Mean across cases of completion virtual_time_s / cleared_count. Weighted alternative is diagnostic only.',
          'scope':'Existing legal fully-cleared development_v2 records only; no official logs, holdout, stress, or new policy runs.',
          'origin_feature_audit':{'consistent_origin_observation_fields_available':False,
              'observed_origin_related_keys':['shared_initial_only','shared_initial_pure'],
              'note':'Only configuration names were found; final totals cannot recover the initial scan. No source_count, family, seed, case_id, true position, or final detected_channels are used as gating features.',
              'public_features_if_future_logging_is_needed':['number of positive channels at the origin','number of near readings at the origin','bearing angular spread or largest angular gap'],
              'selector_trained':False},
          'files':files,'excluded_branches':excluded,'retained_branch_records':len(branches),
          'complete_384_or_more':[{'name':b['name'],'cases':b['cases'],'mean_s':b['mean_s'],'weighted_s':b['weighted_s']} for b in branches if b['cases']>=384],
          'complete_96_or_more':[{'name':b['name'],'cases':b['cases'],'mean_s':b['mean_s'],'weighted_s':b['weighted_s']} for b in branches if b['cases']>=96],
          'scopes':results}
    output=FOLDER/'branch_oracle_audit.json';output.write_text(json.dumps(body,indent=2)+'\n',encoding='utf-8')
    text=['# 第四问现有分支的事后 Oracle 审计','',
          '结论：现有分支池即使事后知道每例的最快分支，也未达到平均 400 秒/源，因此不值得为当前分支池训练选择器。没有修改策略或运行新场景。','',
          f"只读取 `problem4/results/iterations_v3` 中带 `development_v2` 的已有结果，按 `case_id` 配对；要求所有已记录案例全部清除、完成证书为真、清除数一致，并验证虚拟总时间等于移动与实际动作成本之和。几何报告、少于所需例数的分支不进入相应比较。{len(branches)} 条结果记录通过检查；其中 {results['48']['eligible_run_records']} 条覆盖前 48 例、{results['96']['eligible_run_records']} 条覆盖前 96 例、{results['384']['eligible_run_records']} 条覆盖全部 384 例。同一批案例上相同时间向量只计一次，完整路径和文件指纹保存在 JSON。",'',
          '| 前缀样本数 | 原始记录/不同时间向量 | 最佳固定分支均值 | Oracle 每案例均值 | Oracle 加权汇总 | Oracle ≤400 |',
          '|---:|---:|---:|---:|---:|---:|']
    for count,result in results.items():
        text.append(f"| {count} | {result['eligible_run_records']}/{result['unique_time_vectors']} | {result['best_fixed_mean_s']:.3f} | {result['oracle_mean_s']:.3f} | {result['oracle_weighted_s']:.3f} | {result['oracle_pass400']}/{count} |")
    text += ['',
          '目标仍是每案例均值 `mean(T_i / N_i)`；加权汇总是 `sum(T_i) / sum(N_i)`，相当于对源数较多的案例赋予较大权重，不能将其较小数值视为原目标达标。这里 T 是完成覆盖确认后的总虚拟时间，不是最后一次清除时间。Oracle 只能说明这个已测分支池的互补上限，不是所有合法算法的性能下界。','',
          '前 48 例从最佳固定分支 436.290 降到 Oracle 420.904，最多节省 15.386 秒/源。贪心选 2、4、8 个分支的事后组合分别为 431.799、426.275、422.866；即使用很多分支也不能跨过 400。前 96、384 例的互补空间各约 8 秒/源。','',
          '48 例的赢家很分散：SharedLibraryCoverage 赢 5 例，clear_region 与 discovery_nolatency 各 4 例，skeleton_outer_unbounded、skeleton_outer 和 21 点覆盖原分支各 3 例。96 例主要赢家为 clear_region（24 例）、incremental_q30（15 例）、incremental_dynamic（13 例）。384 例中“21点＋仅新发现源共享基线”占 168.5 例，所有已知源共享基线占 47.5 例，其余分散；并列按比例分摊，避免重复结果制造赢家。','',
          '## 全部 384 例均有结果的分支','',
          '| 分支记录 | 每案例均值 | 加权汇总 |','|---|---:|---:|']
    for branch in sorted(body['complete_384_or_more'],key=lambda b:b['mean_s']):
        name=branch['name'].replace('coverage_ring_development_v2_384.json#','').replace('routing_development_v2_384_','').replace('.json#results/',' → ').replace('_development_v2_384.json#','')
        text.append(f"| {name} | {branch['mean_s']:.3f} | {branch['weighted_s']:.3f} |")
    text += ['',
          f"全部 96 例完整记录（含以上 384 例分支）的 {results['96']['eligible_run_records']} 条清单、去重后的 {results['96']['unique_time_vectors']} 条排名，分别见 JSON 的 `complete_96_or_more` 与 `scopes.96.branch_rankings`；48 例大集合的 {results['48']['unique_time_vectors']} 条排名见 `scopes.48.branch_rankings`。每个分支均保留原文件和键路径。",'',
          '## 公共初始观测与证据边界','',
          '这些旧结果只保存最终累计观测，没有一致保存原点首次扫频的正信号数或方位分布；出现的 initial 字段只是配置。因此不能从最终 detected_channels、动作次数或源数反推原点特征，也没有给出虚假的可预测性结论。未来若出现显著更强的新分支，可记录原点正信号频道数、near 数量、方位角最大空隙等公开特征；当前 Oracle 本身仍高于目标，没有训练门控器，也不进行新的开发集评估。','',
          '以上只使用自建开发结果，不读取留出集、压力集或官方日志。代码为 `problem4/experiments_v3/branch_oracle_audit.py`，逐例结果为 `branch_oracle_audit.json`。']
    (FOLDER/'branch_oracle_audit.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    for count,result in results.items():print(count,{k:v for k,v in result.items() if k not in ('oracle_rows','branch_rankings','winners_fractional_ties','greedy_portfolio')},flush=True)
    print('Retained',len(branches),'excluded',excluded,flush=True)
    return body


if __name__=='__main__':run()

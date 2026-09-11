"""Compare observation-only policies on matched synthetic cases.

Development cases are for selection. Holdout/stress results must never be used
to silently retune a selected policy. Reports retain every failure and seed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from problem3.scenarios import SPLITS, FAMILIES, generate_suite
from problem3.simulator import LocalSimulator, ObservationClient

THRESHOLDS = {3: 220.0, 4: 400.0}


def _policy_entry(problem, strategy):
    if problem not in (3, 4):
        raise ValueError('problem must be 3 or 4')
    if strategy == 'legacy':
        if problem != 4:
            raise ValueError('legacy is the original problem4 v1 adaptive policy')
        from problem4.legacy_policy import SearchPolicy
        return SearchPolicy, 'adaptive', 'problem4_v1'
    if strategy == 'adaptive':
        if problem == 3:
            from problem3.speed_policy import SearchPolicy
        else:
            from problem4.speed_policy import SearchPolicy
        return SearchPolicy, strategy, SearchPolicy.algorithm_version
    if strategy not in ('previous', 'baseline', 'optical'):
        raise ValueError(f'Unknown strategy: {strategy}')
    if problem == 3:
        from problem3.policy import SearchPolicy
        version = 'problem3_v1'
    else:
        from problem4.policy import SearchPolicy
        version = 'problem4_v2'
    return SearchPolicy, 'adaptive' if strategy == 'previous' else strategy, version


def get_algorithm_version(problem, strategy='adaptive'):
    """Resolve version without entering an arena or executing a policy."""
    return _policy_entry(problem, strategy)[2]


def get_policy(problem, strategy, config=None):
    policy_class, selected_strategy, version = _policy_entry(problem, strategy)
    policy = policy_class(problem=problem, strategy=selected_strategy, config=config)
    policy.algorithm_version = version
    return policy


def run_case(case, strategy='adaptive', config=None, record=False):
    version = get_algorithm_version(case['problem'], strategy)
    sim = LocalSimulator(case, record=record)
    sim.enter()
    start = time.perf_counter()
    result, error = {}, None
    try:
        result = get_policy(case['problem'], strategy, config).run(ObservationClient(sim))
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
    result['algorithm_version'] = version
    elapsed = time.perf_counter()-start
    if sim.active:
        sim.exit()
    stats = sim.statistics()
    complete = bool(result.get('completion_certified', result.get('coverage_complete')))
    full = stats['cleared_count'] == stats['source_count']
    certified = full and complete and not error
    threshold = THRESHOLDS[case['problem']]*stats['source_count']
    passed = certified and stats['virtual_time_s'] <= threshold
    # A miss/uncertified exit can never be rewarded for being fast.
    reward = (-1000000*(stats['source_count']-stats['cleared_count'])-1000000
              if not certified else
              1000*int(passed) + max(-1000, 100*(1-stats['virtual_time_s']/threshold)))
    row = dict(case_id=case['case_id'], seed=case['seed'], split=case['split'],
               family=case['family'], noise=case['noise'], strategy=strategy,
               algorithm_version=version,
               **stats, coverage_complete=bool(result.get('coverage_complete')),
               completion_certified=complete, certified_full_clear=certified,
               threshold_total_s=threshold, threshold_passed=passed, reward=reward,
               program_runtime_s=elapsed, error=error, policy=result)
    return row, sim.events


def quantile(values, q):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q*len(ordered))-1)] if ordered else None


def aggregate(rows):
    times = [r['virtual_time_s'] for r in rows]
    averages = [r['average_clear_time_s'] for r in rows if r['average_clear_time_s'] is not None]
    return dict(cases=len(rows), all_clear_cases=sum(r['certified_full_clear'] for r in rows),
                missed_sources=sum(r['source_count']-r['cleared_count'] for r in rows),
                threshold_pass_rate=statistics.mean(r['threshold_passed'] for r in rows),
                mean_virtual_time_s=statistics.mean(times), p95_virtual_time_s=quantile(times,.95),
                worst_virtual_time_s=max(times),
                mean_average_clear_time_s=statistics.mean(averages) if averages else None,
                mean_actions=statistics.mean(r['actions'] for r in rows),
                mean_failed_clear=statistics.mean(r['failed_clear'] for r in rows),
                mean_movement_m=statistics.mean(r['movement_m'] for r in rows),
                mean_reward=statistics.mean(r['reward'] for r in rows),
                total_program_runtime_s=sum(r['program_runtime_s'] for r in rows),
                max_program_runtime_s=max(r['program_runtime_s'] for r in rows),
                failures=[r['case_id'] for r in rows if not r['certified_full_clear']],
                threshold_curve={str(t): statistics.mean(r['certified_full_clear'] and
                                    r['average_clear_time_s'] <= t for r in rows)
                                 for t in (100,150,200,220,250,300,400,500,700,1000)})


def source_fingerprint():
    # Production dependencies live directly in these packages. Include every
    # module so a newly added mixin cannot silently escape the freeze check.
    paths = [path for problem in (3, 4)
             for path in sorted((ROOT/f'problem{problem}').glob('*.py'))]
    paths += [Path(__file__).resolve()]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths if p.exists()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--problem', type=int, choices=(3,4), required=True)
    parser.add_argument('--split', choices=tuple(SPLITS), default='development')
    parser.add_argument('--count', type=int, help='Default: full predeclared split')
    parser.add_argument('--strategies', nargs='+', default=['baseline','adaptive'])
    parser.add_argument('--config', type=Path, help='Optional fixed policy configuration JSON')
    parser.add_argument('--tag', default='', help='Distinct result suffix for development experiments')
    parser.add_argument('--save-cases', action='store_true')
    args = parser.parse_args()
    if args.count is not None and args.count <= 0:
        parser.error('--count must be positive')
    if args.tag and not all(c.isalnum() or c=='_' for c in args.tag):
        parser.error('--tag may only contain letters, digits and underscores')
    cases = generate_suite(args.problem, args.split, args.count)
    config = json.loads(args.config.read_text(encoding='utf-8')) if args.config else None
    rows = []
    fingerprints = source_fingerprint()
    versions = {strategy: get_algorithm_version(args.problem, strategy)
                for strategy in args.strategies}
    for strategy in args.strategies:
        print(f"p{args.problem} strategy={strategy} algorithm_version={versions[strategy]}", flush=True)
        for i, case in enumerate(cases):
            row, _ = run_case(case, strategy, config)
            rows.append(row)
            if (i+1)%24 == 0 or row['error'] or i+1 == len(cases):
                print(f"p{args.problem} {strategy} {args.split} {i+1}/{len(cases)} "
                      f"cleared={row['cleared_count']}/{row['source_count']} "
                      f"T={row['virtual_time_s']:.1f}s error={row['error']}", flush=True)
    if fingerprints != source_fingerprint():
        raise RuntimeError('Algorithm changed during benchmark; rerun after freezing code')
    summary = {s: aggregate([r for r in rows if r['strategy']==s]) for s in args.strategies}
    by_family = {s: {f: aggregate([r for r in rows if r['strategy']==s and r['family']==f])
                     for f in FAMILIES if any(r['family']==f for r in rows)} for s in args.strategies}
    body = dict(provenance='Local synthetic results, NOT official practice/formal results',
                problem=args.problem, split=args.split, case_count=len(cases),
                cases_sha256=hashlib.sha256(json.dumps(cases, sort_keys=True, separators=(',', ':'),
                                                     ensure_ascii=False).encode('utf-8')).hexdigest(),
                threshold_seconds_per_source=THRESHOLDS[args.problem],
                threshold_definition='Full clearance AND completion certificate; total virtual time <= threshold * N',
                algorithm_versions=versions, config=config, source_sha256=fingerprints,
                summary=summary, by_family=by_family, episodes=rows)
    folder = ROOT/f'problem{args.problem}/results'
    folder.mkdir(parents=True,exist_ok=True)
    stem = f"benchmark_{args.split}" + ('_'+args.tag if args.tag else '')
    (folder/f'{stem}.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines = [f'# 问题{args.problem}自建样本比较：{args.split}', '',
             f'每分支 {len(cases)} 例；所有分支逐例使用相同样本和固定地点误差。不是官方演练或正式成绩。', '',
             '算法版本：'+'；'.join(f'{name}={version}' for name,version in versions.items())+'。', '',
             f'自定阈值：确保全清后，总虚拟时间 ≤ {THRESHOLDS[args.problem]:g} × 实际源数（秒）。源数只供事后评分，算法不可读取。', '',
             '| 分支 | 全清且完成确认 | 阈值通过率 | 平均总耗时/秒 | P95/秒 | 最差/秒 | 平均每源/秒 | 平均动作数 |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for s,a in summary.items():
        average = '无定义' if a['mean_average_clear_time_s'] is None else f"{a['mean_average_clear_time_s']:.1f}"
        lines.append(f"| {s} | {a['all_clear_cases']}/{a['cases']} | {a['threshold_pass_rate']:.1%} | "
                     f"{a['mean_virtual_time_s']:.1f} | {a['p95_virtual_time_s']:.1f} | {a['worst_virtual_time_s']:.1f} | "
                     f"{average} | {a['mean_actions']:.1f} |")
    lines += ['', '奖励：未全清或未完成确认给至少一百万负分；全清且过阈值加1000分，再按节省的时间加分。此奖励只用于本地比较，题目没有给官方奖励函数。', '',
              '总耗时包括发现最后一个源后的排除/覆盖确认，不只统计最后一次清除时刻。P95为最近秩分位数；本地程序运行耗时不含HTTP和平台延迟。', '',
              '下表使用相同结果扫描更严格/宽松阈值，没有重新训练或调参。', '',
              '| 分支 | 150秒/源 | 200秒/源 | 250秒/源 | 300秒/源 | 400秒/源 | 500秒/源 |',
              '| --- | --- | --- | --- | --- | --- | --- |']
    for s,a in summary.items():
        lines.append('| '+s+' | '+' | '.join(f"{a['threshold_curve'][str(t)]:.1%}" for t in (150,200,250,300,400,500))+' |')
    lines += ['', f'逐例数据、分场景汇总、失败记录及代码指纹见 [{stem}.json]({stem}.json)。', '']
    (folder/f'{stem}.md').write_text('\n'.join(lines),encoding='utf-8')
    if args.save_cases:
        ex = ROOT/f'problem{args.problem}/examples'; ex.mkdir(parents=True,exist_ok=True)
        (ex/f'{args.split}_cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0 if all(r['certified_full_clear'] for r in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())

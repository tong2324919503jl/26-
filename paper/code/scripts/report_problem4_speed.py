"""Summarize frozen, paired Q4 speed experiments; standard library only."""
from __future__ import annotations

import json
import random
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'problem4/results'
SPLITS = ('development_v2', 'holdout_v2', 'stress_v2')


def paired(rows):
    old = {r['case_id']: r for r in rows if r['strategy'] == 'legacy'}
    new = {r['case_id']: r for r in rows if r['strategy'] == 'adaptive'}
    if old.keys() != new.keys() or not old:
        raise ValueError('The two branches must use exactly the same nonempty cases')
    pairs = [(old[k], new[k]) for k in sorted(old)]
    if any(a['source_count'] != b['source_count'] for a, b in pairs):
        raise ValueError('Mismatched source counts')
    delta = [a['average_clear_time_s'] - b['average_clear_time_s'] for a, b in pairs]
    before = statistics.mean(a['average_clear_time_s'] for a, _ in pairs)
    after = statistics.mean(b['average_clear_time_s'] for _, b in pairs)
    rng = random.Random(260911)
    bootstrap = sorted(statistics.mean(rng.choices(delta, k=len(delta))) for _ in range(4000))
    return dict(cases=len(pairs), old_seconds_per_source=before, new_seconds_per_source=after,
                reduction_fraction=1-after/before,
                mean_saved_seconds_per_source=statistics.mean(delta),
                bootstrap_95_mean_saved_seconds_per_source=[bootstrap[99], bootstrap[3899]],
                faster_cases=sum(d > .000001 for d in delta),
                slower_cases=sum(d < -.000001 for d in delta),
                tied_cases=sum(abs(d) <= .000001 for d in delta),
                gained_threshold_cases=sum(not a['threshold_passed'] and b['threshold_passed'] for a,b in pairs),
                lost_threshold_cases=sum(a['threshold_passed'] and not b['threshold_passed'] for a,b in pairs),
                old_threshold_pass_rate=statistics.mean(a['threshold_passed'] for a,_ in pairs),
                new_threshold_pass_rate=statistics.mean(b['threshold_passed'] for _,b in pairs))


def main():
    reports = {s: json.loads((RESULTS/f'benchmark_{s}.json').read_text(encoding='utf-8')) for s in SPLITS}
    fingerprints = [r['source_sha256'] for r in reports.values()]
    if any(f != fingerprints[0] for f in fingerprints[1:]):
        raise ValueError('Benchmarks were not generated with the same frozen sources')
    frozen = json.loads((ROOT/'validation/problem4_freeze_v2.json').read_text(encoding='utf-8'))
    if frozen['source_sha256'] != fingerprints[0]:
        raise ValueError('Evaluation differs from the recorded pre-holdout freeze')
    seeds = [set(r['seed'] for r in report['episodes']) for report in reports.values()]
    if any(seeds[i] & seeds[j] for i in range(len(seeds)) for j in range(i)):
        raise ValueError('Split seed overlap')
    comparison = {split: paired(report['episodes']) for split,report in reports.items()}
    stratified = {split: {str(n): paired([r for r in report['episodes'] if r['source_count']==n])
                         for n in range(10,17) if any(r['source_count']==n for r in report['episodes'])}
                  for split,report in reports.items()}
    body = dict(provenance='Synthetic local evaluation, not official platform results',
                source_sha256=fingerprints[0], paired=comparison, by_source_count=stratified,
                uncertainty_note='Paired bootstrap conditional on these synthetic distributions; not official performance bounds')
    (RESULTS/'speed_comparison_v2.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines = ['# 第四问第二轮速度改进', '',
             '对手是上一版已交付的 `adaptive`（本轮名为 `legacy`），不是更弱的基础分支。两版逐例使用相同输入、固定地点误差和计时。以下均为自建模拟，未连接官方平台。', '',
             '阈值保持 **500秒/源**：全清且取得完成确认后，总虚拟时间不超过500×实际源数。总时间包含最后一次清除后的覆盖确认；算法不能读取实际源数。', '',
             '| 集合 | 案例数 | 旧版→新版 秒/源 | 耗时减少 | 旧版→新版 阈值通过率 | 新版全清且确认 |',
             '| --- | ---: | ---: | ---: | ---: | ---: |']
    labels = {'development_v2':'开发','holdout_v2':'新留出','stress_v2':'新压力'}
    for split,p in comparison.items():
        a = reports[split]['summary']['adaptive']
        lines.append(f"| {labels[split]} | {p['cases']} | {p['old_seconds_per_source']:.2f} → {p['new_seconds_per_source']:.2f} | {p['reduction_fraction']:.1%} | {p['old_threshold_pass_rate']:.1%} → {p['new_threshold_pass_rate']:.1%} | {a['all_clear_cases']}/{a['cases']} |")
    lines += ['', '## 成本与逐例变化', '',
              '| 集合 | 移动距离 米/局（旧→新） | 动作数/局（旧→新） | 总时间P95 秒（旧→新） | 新版更快/更慢 | 新增/失去阈值通过 |',
              '| --- | ---: | ---: | ---: | ---: | ---: |']
    for split,p in comparison.items():
        a,b = (reports[split]['summary'][s] for s in ('legacy','adaptive'))
        lines.append(f"| {labels[split]} | {a['mean_movement_m']:.0f} → {b['mean_movement_m']:.0f} | {a['mean_actions']:.1f} → {b['mean_actions']:.1f} | {a['p95_virtual_time_s']:.0f} → {b['p95_virtual_time_s']:.0f} | {p['faster_cases']}/{p['slower_cases']} | {p['gained_threshold_cases']}/{p['lost_threshold_cases']} |")
    lines += ['', '提速不是逐例保证；更慢及失去阈值的案例没有删除。JSON保留按源数分层与配对自助法区间；该区间只描述本地生成分布，不表示官方成绩区间。', '',
              '## 少源场景是否仍慢', '',
              '| 集合 | 实际源数 | 案例数 | 旧版→新版 秒/源 | 旧版→新版 阈值通过率 |',
              '| --- | ---: | ---: | ---: | ---: |']
    for split in ('holdout_v2','stress_v2'):
        for n,p in stratified[split].items():
            lines.append(f"| {labels[split]} | {n} | {p['cases']} | {p['old_seconds_per_source']:.1f} → {p['new_seconds_per_source']:.1f} | {p['old_threshold_pass_rate']:.1%} → {p['new_threshold_pass_rate']:.1%} |")
    lines += ['', '源数分组只用于事后分析。发现16个频道可停止寻找新频道，但必须实际清除16个才结束；少于16个时仍要完成覆盖。', '',
              '## 复现', '', '```powershell',
              *[f'python scripts/benchmark_search.py --problem 4 --split {s} --strategies legacy adaptive --save-cases' for s in SPLITS],
              'python scripts/report_problem4_speed.py', '```', '',
              '新版集合与第一轮集合种子互不重叠。开发384例用于选型；代码冻结后再运行新留出512例、新压力256例。全部1280个输入保存在 `problem4/examples/`，不按结果删样本。', '',
              '每组完整明细：'+ '、'.join(f'[{labels[s]}](benchmark_{s}.md)' for s in SPLITS)+'；[配对统计JSON](speed_comparison_v2.json)。', '']
    (RESULTS/'speed_comparison_v2.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(comparison,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()

"""Summarize frozen paired P3/P4 evaluations, including dispersion and failures."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ('development_v3', 'holdout_v3', 'stress_v3')


def describe(rows, threshold):
    values = [r['average_clear_time_s'] for r in rows]
    full = all(r['certified_full_clear'] for r in rows)
    if any(v is None for v in values):
        return {'cases': len(rows), 'complete': sum(r['certified_full_clear'] for r in rows),
                'mean': None, 'std': None, 'p90': None, 'maximum': None}
    ordered = sorted(values)
    return dict(cases=len(rows), complete=sum(r['certified_full_clear'] for r in rows),
                mean=statistics.mean(values) if full else None, std=statistics.pstdev(values),
                p90=ordered[math.ceil(.9*len(rows))-1], maximum=max(values),
                threshold_passes=sum(r['certified_full_clear'] and v <= threshold
                                     for r, v in zip(rows, values)),
                mean_movement_m=statistics.mean(r['movement_m'] for r in rows),
                mean_actions=statistics.mean(r['actions'] for r in rows))


def paired(reference, selected):
    assert len(reference) == len(selected)
    changes = []
    for a, b in zip(reference, selected):
        assert a['case_id'] == b['case_id'] and a['case_sha256'] == b['case_sha256']
        if not a['certified_full_clear'] or not b['certified_full_clear']:
            return {'all_pairs_complete': False}
        changes.append(b['average_clear_time_s']-a['average_clear_time_s'])
    delta = statistics.mean(changes)
    se = statistics.stdev(changes)/math.sqrt(len(changes))
    return dict(all_pairs_complete=True, mean_change_s=delta,
                decrease_fraction=-delta/statistics.mean(r['average_clear_time_s'] for r in reference),
                faster=sum(d < -1e-6 for d in changes), slower=sum(d > 1e-6 for d in changes),
                equal=sum(abs(d) <= 1e-6 for d in changes),
                approximate_95_percent_interval=[delta-1.96*se, delta+1.96*se],
                worst_regression_s=max(changes), largest_improvement_s=-min(changes))


def main():
    freeze = json.loads((ROOT/'validation/speed_v4_freeze.json').read_text(encoding='utf-8'))
    for problem in (3, 4):
        entry = freeze[f'problem{problem}']
        normalized = 'source_lf_sha256' in entry
        for name, digest in entry.get('source_lf_sha256', entry['source_sha256']).items():
            content = (ROOT/name).read_bytes()
            if normalized:
                content = content.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
            if hashlib.sha256(content).hexdigest() != digest:
                raise RuntimeError(f'Frozen algorithm changed: {name}')
    body = {'scope': 'Local synthetic paired evaluation; no official simulator runs.',
            'frozen_selection': 'Development only; holdout and stress are never used to retune.',
            'statistics': 'Per-case exit virtual time / cleared count, then unweighted case mean. Population standard deviation; nearest-rank p90. Approximate paired-mean interval is descriptive, not a guarantee.',
            'results': {}}
    lines = ['# 第四轮：队友方案融合与独立检验', '',
             '默认入口已更新为 `problem3_v4`、`problem4_v4`，启动时会打印版本。加 `--strategy previous` 可回放本轮之前的平台默认算法。', '',
             '**本地自建结果，不是官方成绩。第三问220、第四问400秒/源的均值目标仍未达到。**', '',
             '每问开发384例、冻结后留出512例、压力256例；两问共2304个不同案例。所有比较分支逐例使用相同数据、计费与固定地点误差，包含最后清除后的覆盖确认。算法进程只接收公开动作响应，不接收源真值、案例类别或种子。', '',
             '## 同批比较', '',
             '| 问题/集合 | 分支 | 均值秒/源 | 标准差 | P90 | 过220/400 | 全清且独立确认 |',
             '|---|---|---:|---:|---:|---:|---:|']
    names = {'teammate': '队友原包'}
    for problem in (3, 4):
        names[f'problem{problem}.policy:SearchPolicy'] = '此前默认'
        names[f'problem{problem}.speed_policy:SearchPolicy'] = '本轮默认'
    names['problem4.experiments_v3.posterior:Shared21Policy'] = '上一轮最好实验'
    for problem in (3, 4):
        for split in SPLITS:
            path = ROOT/f'validation/speed_v4/p{problem}_{split}.json'
            raw = json.loads(path.read_text(encoding='utf-8'))
            runs = raw['results'][str(problem)]
            expected = {f'problem{problem}.policy:SearchPolicy',
                        f'problem{problem}.speed_policy:SearchPolicy', 'teammate'}
            if problem == 4:
                expected.add('problem4.experiments_v3.posterior:Shared21Policy')
            if set(runs) != expected:
                raise RuntimeError(f'Comparison has not finished every branch: {path}')
            selected = runs[f'problem{problem}.speed_policy:SearchPolicy']['episodes']
            entry = {'source': str(path.relative_to(ROOT)).replace('\\', '/'),
                     'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'branches': {}}
            for target, run in runs.items():
                rows = run['episodes']; desc = describe(rows, {3: 220, 4: 400}[problem])
                if len(rows) != dict(zip(SPLITS, (384, 512, 256)))[split]:
                    raise RuntimeError(f'Wrong predeclared case count: {path} {target}')
                if any(not r['normal_exit'] or r['actual_exit_time_s'] != r['virtual_time_s'] for r in rows):
                    raise RuntimeError(f'Exit totals are not final: {path} {target}')
                entry['branches'][target] = {'summary': desc, 'selected_vs_this_branch': paired(rows, selected)}
                if desc['mean'] is None:
                    raise RuntimeError(f'Incomplete run; inspect raw report before reporting speed: {path} {target}')
                lines.append(f"| {problem}/{split.replace('_v3','')} | {names[target]} | {desc['mean']:.2f} | {desc['std']:.2f} | {desc['p90']:.2f} | {desc['threshold_passes']}/{desc['cases']} | {desc['complete']}/{desc['cases']} |")
            body['results'][f'p{problem}_{split}'] = entry
    held = body['results']['p4_holdout_v3']['branches']
    old_best = held['problem4.experiments_v3.posterior:Shared21Policy']
    current = held['problem4.speed_policy:SearchPolicy']['summary']
    comparison = old_best['selected_vs_this_branch']
    lines += ['',
              f"第四问留出集相对上轮最好实验：{comparison['faster']}例更快、{comparison['slower']}例更慢，均值降低{-comparison['mean_change_s']:.2f}秒/源（{comparison['decrease_fraction']:.2%}）。标准差{old_best['summary']['std']:.2f}→{current['std']:.2f}，P90则{old_best['summary']['p90']:.2f}→{current['p90']:.2f}。因此本轮有均值提速，但不能声称方差已经减小。", '',
              '## 采用与舍弃', '',
              '- 第三问：保留上一轮最好算法——全局重排、原点无信号时的9点外环、保守阴性约束、前瞻检测和窄条带清除；本轮将它迁入实际默认入口。队友的途中截获与补测筛选没有带来增益，不强行加入。',
              '- 第四问：保留我方历史观测定位和50米共享基线，加入队友启发的补测收益筛选、失败清除盘扣除后的碎片并集重排，以及经独立认证的22点布局。',
              '- 开发384例中，第四问上一轮最好444.38→补测筛选442.07→再加光学修复440.76→22点最终440.16。布局单项收益较小，不将总提升都归因于减少站点。',
              '- 光学面积只是动作排序估计。每源最多额外尝试16次，仍以实际成功清除和原有有限覆盖兜底为准。', '',
              '## 证据与局限', '',
              '三个集合均保留每例的实际退出时间、失败动作、全清核对与逐未知频道的独立覆盖证书。未全清或证书不足不能获得速度奖励。标准差和P90用于展示波动；不存在逐例提速或保证全部过阈值的承诺。', '',
              '原ZIP保留，SHA256为 `bce6c749b633275e01c20913d1b9980b4f810cf6fad57f9de58732edbe5b4332`。生产运行不读取ZIP、临时解压目录或实验脚本。', '',
              '数值、配对快慢例数和均值差区间见 [JSON汇总](speed_v4_summary.json)；冻结指纹见 [冻结记录](speed_v4_freeze.json)；[光学消融](../problem4/results/iterations_v4/unionmass_review.md)、[布局消融](../problem4/results/iterations_v4/teammate_cover_report.md)。', '',
              '复现第四问：`python scripts/compare_teammate_p34.py --problem 4 --split holdout_v3 --count 512 --targets problem4.policy:SearchPolicy problem4.experiments_v3.posterior:Shared21Policy problem4.speed_policy:SearchPolicy --output validation/recheck_p4.json`。第三问使用 `--problem 3 --targets problem3.policy:SearchPolicy problem3.speed_policy:SearchPolicy`，输出另取新名称。开发/压力分别改集合名和384/256；避免覆盖冻结记录。', '',
              '重建本汇总：`python scripts/report_search_v4.py`。平台测试步骤见 [简明说明](../simulation_guide.md)。', '']
    (ROOT/'validation/speed_v4_summary.json').write_text(json.dumps(body, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (ROOT/'validation/speed_v4_summary.md').write_text('\n'.join(lines), encoding='utf-8')
    print('Wrote validation/speed_v4_summary.json and .md')


if __name__ == '__main__':
    main()

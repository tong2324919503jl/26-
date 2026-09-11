"""Post-hoc paired audit of existing P3 development_v2 strategy results.

No strategy is run. No held-out, stress, official or counterexample file is
opened. The oracle is a bound for this finite branch pool, not a deployable
selector or a bound for all possible policies.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
RESULTS = ROOT / 'problem3' / 'results'
OUTPUT = RESULTS / 'iterations_v3'
PREFIX = 'local_p3_development_v2_'


def containers(value, path=()):
    if isinstance(value, dict):
        for key in ('rows', 'episodes'):
            rows = value.get(key)
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                if any('case_id' in row or 'id' in row for row in rows):
                    yield path + (key,), rows
        for key, child in value.items():
            if key not in ('rows', 'episodes') and isinstance(child, (dict, list)):
                yield from containers(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, dict):
                yield from containers(child, path + (str(index),))


def normalize(row):
    case_id = row.get('case_id', row.get('id', ''))
    if not case_id.startswith(PREFIX):
        return None, 'not_development_v2_case'
    sim, policy = row.get('sim', row), row.get('policy', {})
    if row.get('error') or sim.get('error'):
        return None, 'error'
    if policy.get('problem') != 3:
        return None, 'not_p3_policy'
    count, cleared = sim.get('source_count'), sim.get('cleared_count')
    if count not in range(10, 17) or count != cleared:
        return None, 'not_full_clear'
    if not policy.get('completion_certified'):
        return None, 'no_completion_certificate'
    if len(set(policy.get('cleared_channels', []))) != cleared:
        return None, 'clear_metadata_mismatch'
    elapsed, average = sim.get('virtual_time_s'), sim.get('average_clear_time_s')
    if not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed <= 0:
        return None, 'invalid_time'
    if average is None or abs(average - elapsed / count) > 1e-5:
        return None, 'invalid_completion_average'
    cost = sim.get('movement_m', math.nan) / 5 + sim.get('measure', math.nan) * 5
    cost += sim.get('switch', math.nan) + sim.get('failed_clear', math.nan) * 3
    cost += (sim.get('clear', math.nan) - sim.get('failed_clear', math.nan)) * 5
    if not math.isfinite(cost) or abs(elapsed - cost) > 1e-4:
        return None, 'physical_cost_mismatch'
    return dict(case_id=case_id, seed=row.get('seed'), source_count=count,
                time_s=elapsed, average_s=elapsed / count,
                movement_m=sim['movement_m'], actions=sim.get('actions'),
                origin_empty=policy.get('zero_origin_geometry', {}).get('triggered')), None


def collect():
    branches, excluded, files = [], [], []
    # Explicit non-recursive roots avoid the online folder entirely.
    paths = list(RESULTS.glob('p3_*.json')) + list(OUTPUT.glob('*development_v2*.json'))
    for path in sorted(paths):
        if any(word in path.name.lower() for word in
               ('holdout', 'stress', 'counterexample', 'oracle', 'superseded')):
            continue
        raw = path.read_bytes()
        data = json.loads(raw)
        found = False
        for location, source_rows in containers(data):
            found = True
            name = str(path.relative_to(RESULTS)).replace('\\', '/') + '#' + '/'.join(location[:-1])
            rows, errors = [], Counter()
            for source_row in source_rows:
                row, error = normalize(source_row)
                if error:
                    errors[error] += 1
                else:
                    rows.append(row)
            if len({row['case_id'] for row in rows}) != len(rows):
                errors['duplicate_case_id'] += 1
            if errors:
                excluded.append(dict(branch=name, cases=len(source_rows), errors=dict(errors)))
                continue
            branches.append(dict(name=name, cases=len(rows), rows=rows))
        if found:
            files.append(dict(path=str(path.relative_to(RESULTS)).replace('\\', '/'),
                              sha256=hashlib.sha256(raw).hexdigest()))
    identity, seeds, empty_origin = {}, {}, {}
    for branch in branches:
        for row in branch['rows']:
            key = row['case_id']
            value = row['source_count']
            if identity.setdefault(key, value) != value:
                raise AssertionError('Case identity/denominator mismatch: ' + key)
            if row['seed'] is not None and seeds.setdefault(key, row['seed']) != row['seed']:
                raise AssertionError('Case seed mismatch: ' + key)
            if row['origin_empty'] is not None:
                if empty_origin.setdefault(key, row['origin_empty']) != row['origin_empty']:
                    raise AssertionError('Conflicting public origin-empty metadata: ' + key)
    return branches, excluded, files, empty_origin


def scope(branches, count, empty_origin):
    ids = [f'{PREFIX}{i:04d}' for i in range(count)]
    choices, signatures, aliases = [], {}, {}
    for branch in branches:
        lookup = {row['case_id']: row for row in branch['rows']}
        if any(key not in lookup for key in ids):
            continue
        rows = [lookup[key] for key in ids]
        signature = tuple(round(row['time_s'], 6) for row in rows)
        if signature in signatures:
            aliases[signatures[signature]].append(branch['name'])
            continue
        signatures[signature] = branch['name']
        aliases[branch['name']] = [branch['name']]
        choices.append(dict(name=branch['name'], rows=rows, original_cases=branch['cases'],
                            mean_s=statistics.mean(row['average_s'] for row in rows),
                            pass220=sum(row['average_s'] <= 220 for row in rows),
                            weighted_s=sum(row['time_s'] for row in rows) / sum(row['source_count'] for row in rows)))
    choices.sort(key=lambda choice: (choice['mean_s'], choice['name']))
    if not choices:
        raise ValueError('No eligible paired choices')
    oracle, wins = [], Counter()
    for index, key in enumerate(ids):
        best = min(choice['rows'][index]['average_s'] for choice in choices)
        tied = [choice for choice in choices if abs(choice['rows'][index]['average_s'] - best) < 1e-6]
        for choice in tied:
            wins[choice['name']] += 1 / len(tied)
        original = tied[0]['rows'][index]
        oracle.append(dict(case_id=key, source_count=original['source_count'], average_s=best,
                           time_s=original['time_s'], winners=[choice['name'] for choice in tied],
                           gain_over_best_fixed_s=choices[0]['rows'][index]['average_s'] - best))
    current = [row['average_s'] for row in choices[0]['rows']]
    portfolio, curve = [choices[0]['name']], []
    for size in range(min(16, len(choices))):
        if size:
            candidate = min((choice for choice in choices if choice['name'] not in portfolio),
                            key=lambda choice: sum(min(a, row['average_s']) for a, row in zip(current, choice['rows'])))
            proposed = [min(a, row['average_s']) for a, row in zip(current, candidate['rows'])]
            if sum(current) - sum(proposed) < 1e-7:
                break
            current = proposed
            portfolio.append(candidate['name'])
        curve.append(dict(branches=portfolio.copy(), mean_s=statistics.mean(current),
                          pass220=sum(value <= 220 for value in current)))
    # The only consistent recorded initial public feature is zero signals at
    # the origin, from geometry-family result metadata. Selecting the best
    # fixed branch in each group is itself optimistically fitted on this set.
    origin_groups, origin_gate = {}, None
    if all(key in empty_origin for key in ids):
        gate_cost = [None] * count
        for value in (False, True):
            indices = [i for i, key in enumerate(ids) if empty_origin[key] == value]
            if not indices:
                continue
            ranked = sorted(choices, key=lambda choice: statistics.mean(choice['rows'][i]['average_s'] for i in indices))
            winner = ranked[0]
            for i in indices:
                gate_cost[i] = winner['rows'][i]['average_s']
            origin_groups[str(value).lower()] = dict(cases=len(indices), best_fixed_branch=winner['name'],
                mean_s=statistics.mean(winner['rows'][i]['average_s'] for i in indices),
                oracle_mean_s=statistics.mean(oracle[i]['average_s'] for i in indices),
                top_branches=[dict(name=choice['name'], mean_s=statistics.mean(choice['rows'][i]['average_s'] for i in indices)) for choice in ranked[:8]])
        origin_gate = dict(mean_s=statistics.mean(gate_cost), pass220=sum(cost <= 220 for cost in gate_cost),
                           groups=origin_groups, fitted_and_scored_on_same_data=True)
    return dict(cases=count, eligible_run_records=sum(len(value) for value in aliases.values()),
        unique_time_vectors=len(choices), best_fixed_branch=choices[0]['name'],
        best_fixed_mean_s=choices[0]['mean_s'], best_fixed_pass220=choices[0]['pass220'],
        oracle_mean_s=statistics.mean(row['average_s'] for row in oracle),
        oracle_weighted_s=sum(row['time_s'] for row in oracle) / sum(row['source_count'] for row in oracle),
        oracle_pass220=sum(row['average_s'] <= 220 for row in oracle),
        oracle_pass210=sum(row['average_s'] <= 210 for row in oracle),
        winners_fractional_ties=wins.most_common(), greedy_portfolio=curve,
        public_origin_empty_gate=origin_gate, oracle_rows=oracle,
        branch_rankings=[{key: value for key, value in choice.items() if key != 'rows'} |
                         dict(aliases=aliases[choice['name']]) for choice in choices])


def run():
    branches, excluded, files, origin = collect()
    scopes = {str(count): scope(branches, count, origin) for count in (96, 384)}
    body = dict(scope='Existing fully cleared P3 development_v2 records only. Post-hoc finite branch-pool oracle; not deployable.',
                metric='mean_i(completion virtual_time_s_i / source_count_i); no threshold or family weighting',
                validation='Every recorded case full clear, certificate true, P3 policy, unique IDs, consistent seed/source count, physical cost conservation.',
                exclusions='No online/official, holdout, stress, development_v3, counterexample, superseded radius-overwrite, or geometric lower-bound records.',
                legal_review='Root and P3 author reported no other known illegal-information or unsafe-geometry branch in this retained pool. This is an existing-record audit, not a fresh full proof of every branch.',
                retained_branch_records=len(branches), source_files=files, excluded_branches=excluded,
                public_features='Only origin-empty boolean is consistently recorded by geometry-family variants. No final counts, source count, seed, family, or true position used for gating.',
                scopes=scopes)
    (OUTPUT / 'branch_oracle_audit.json').write_text(json.dumps(body, indent=2) + '\n', encoding='utf-8')
    lines = ['# 第三问现有分支的事后 Oracle 审计', '',
             f"结论：现有分支池即使逐例事后选择最快策略，前 96 例仍为 {scopes['96']['oracle_mean_s']:.3f}、全部 384 例为 {scopes['384']['oracle_mean_s']:.3f} 秒/源，均未达到 220。当前没有证据支持为这些分支训练选择器。", '',
             '只读取已有自建 `development_v2` 结果，不运行新策略，不读取留出、压力、平台或反例数据。每条分支要求其记录的全部案例均成功清除、完成证书为真、P3 策略元数据一致、物理动作成本守恒，再按案例编号和种子配对。去除时间向量相同的重复分支。', '',
             '| 案例数 | 完整记录/不同分支时间向量 | 最佳固定分支 | Oracle | Oracle ≤220 |',
             '|---:|---:|---:|---:|---:|']
    for count, result in scopes.items():
        lines.append(f"| {count} | {result['eligible_run_records']}/{result['unique_time_vectors']} | {result['best_fixed_mean_s']:.3f} | {result['oracle_mean_s']:.3f} | {result['oracle_pass220']}/{count} |")
    lines += ['', 'Oracle 逐例选择事后最快的已测分支。它描述这个有限分支池的互补潜力，不是可执行策略，也不是所有算法的最优下界。目标仍为每案例均值 `mean(T_i/N_i)`，其中 T 是完整结束时间；JSON 同时保留按源数加权的 `sum(T_i)/sum(N_i)`，不能用后者替换目标。', '',
              '## 少量分支的互补空间', '']
    for count, result in scopes.items():
        lines.append(f"{count} 例最佳固定分支：`{result['best_fixed_branch']}`。")
        lines.append('')
        for step in result['greedy_portfolio']:
            if len(step['branches']) in (1, 2, 3, 4, 8, 12, 16):
                lines.append(f"- {len(step['branches'])} 个分支的贪心事后组合：{step['mean_s']:.3f} 秒/源，{step['pass220']}/{count} 例 ≤220。")
        lines.append('')
    lines += ['## 公开特征能否区分赢家', '',
              '旧日志中可一致核对的初始公开特征只有“原点首次扫频是否零信号”，由覆盖几何实验显式记录。下面分别为零信号/非零信号组挑选最好的固定分支，再在同一批数据评分；这仍是乐观拟合，不是验证集结果。未使用最终清除数、真实源数、family、seed、真实位置或最终检测频道作选择特征。', '']
    for count, result in scopes.items():
        gate = result['public_origin_empty_gate']
        if gate:
            lines.append(f"{count} 例按原点零信号二分：{gate['mean_s']:.3f} 秒/源，{gate['pass220']}/{count} 例 ≤220。")
            lines.append('')
            for key, group in gate['groups'].items():
                label = '原点零信号' if key == 'true' else '原点有信号'
                lines.append(f"- {label} {group['cases']} 例：固定最佳 {group['mean_s']:.3f}，该组 Oracle {group['oracle_mean_s']:.3f}；`{group['best_fixed_branch']}`。")
            lines.append('')
    lines += ['仅凭 Oracle 低于阈值不能宣称策略达标。是否继续训练选择器取决于公开观测能否在独立案例预测这些赢家；当前没有训练选择器。若只掌握原点零信号而无法达到 220，应继续改善动作策略或先补充公开观测日志，不能用案例家族标签充当可部署规则。', '',
              '完整分支别名、逐例赢家、源文件 SHA-256、排除原因及贪心组合顺序见 `branch_oracle_audit.json`。源数和案例编号始终核对，保存了种子的记录另核对种子；精确 TSP 结果未保存逐例种子，沿用其明确的案例编号。此前被覆盖半径重置的 superseded 结果被排除；两个 ring7 旧分支因全部 64 例报错被剔除。其余保留分支经作者确认未有已知非法信息或硬几何错误。本审计核对现有行为记录，不替代每个实验策略的完整数学证明。']
    (OUTPUT / 'branch_oracle_audit.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    for key, result in scopes.items():
        print(key, {field: result[field] for field in ('eligible_run_records', 'unique_time_vectors', 'best_fixed_mean_s', 'oracle_mean_s', 'oracle_pass220')}, flush=True)
        gate = result['public_origin_empty_gate']
        print('origin_gate', None if gate is None else {field: gate[field] for field in ('mean_s', 'pass220')}, flush=True)
    print('excluded', excluded, flush=True)
    return body


if __name__ == '__main__':
    run()

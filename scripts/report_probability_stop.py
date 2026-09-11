"""Verify and summarize the frozen local probabilistic-stop experiment.

No scenarios, policies, probability particles or platform requests are run here.
Relative paths are anchored at this script's repository root. Source or trace
hash/metric mismatches abort before replacing the existing Markdown report.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parents[1]
SPLITS = {'development': 256, 'calibration': 512, 'holdout': 2048, 'stress': 512}
SPLIT_NAMES = {'development': '开发', 'calibration': '校准', 'holdout': '留出', 'stress': '压力'}
MODES = ('nominal', 'robust', 'guarded')
THRESHOLDS = (.8, .9, .95, .975, .99, .995, .999, .9999)
BRANCHES = ('safe_v4',) + tuple(f'{mode}_{threshold:g}' for mode in MODES for threshold in THRESHOLDS)
PRIMARY = ('safe_v4', 'nominal_0.99', 'guarded_0.99')


class VerificationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def root_path(relative):
    path = (ROOT / relative).resolve()
    require(path.is_relative_to(ROOT), f'路径越出仓库：{relative}')
    return path


def digest(path, *, normalize_lf=False):
    if normalize_lf:
        data = path.read_bytes().replace(b'\r\n', b'\n').replace(b'\r', b'\n')
        return hashlib.sha256(data).hexdigest()
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def verify_sources(expected, label, *, normalize_lf=True):
    require(isinstance(expected, dict) and expected, f'{label} 缺源码指纹')
    for relative, checksum in expected.items():
        path = root_path(relative)
        require(path.is_file(), f'{label} 源文件不存在：{relative}')
        require(digest(path, normalize_lf=normalize_lf) == checksum,
                f'{label} 当前源码与记录不一致：{relative}')


def verify_auxiliary_sources(audit):
    """Prefer canonical fingerprints; retain compatibility with legacy raw SHA.

    A legacy fingerprint must match either the exact current bytes or the same
    text with uniformly LF/CRLF line endings. No other difference is tolerated.
    Core files are also independently checked against freeze's canonical hash.
    """
    if audit.get('source_lf_sha256'):
        verify_sources(audit['source_lf_sha256'], 'independent_audit（LF）')
        return
    require(audit.get('source_sha256'), 'independent_audit 缺源码指纹')
    for relative, recorded in audit['source_sha256'].items():
        data = root_path(relative).read_bytes()
        canonical = data.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
        equivalent = (data, canonical, canonical.replace(b'\n', b'\r\n'))
        require(recorded in {hashlib.sha256(candidate).hexdigest() for candidate in equivalent},
                f'independent_audit 历史指纹不匹配，且不只是换行差异：{relative}')


def binomial_upper(failures, count, alpha=.05):
    """One-sided exact binomial inversion, used only as an iid reference."""
    if count == 0 or failures == count:
        return 1.
    if failures == 0:
        return -math.expm1(math.log(alpha) / count)
    coefficients = [math.lgamma(count + 1) - math.lgamma(j + 1)
                    - math.lgamma(count - j + 1) for j in range(failures + 1)]
    lower, upper = failures / count, 1.
    for _ in range(60):
        probability = (lower + upper) / 2
        terms = [coefficient + j * math.log(probability)
                 + (count - j) * math.log1p(-probability)
                 for j, coefficient in enumerate(coefficients)]
        maximum = max(terms)
        cdf = math.exp(maximum) * math.fsum(math.exp(term - maximum) for term in terms)
        if cdf > alpha:
            lower = probability
        else:
            upper = probability
    return (lower + upper) / 2


def recompute(rows, branch):
    paired = [(row, row['outcomes'][branch]) for row in rows]
    valid = [(row, outcome) for row, outcome in paired if not outcome.get('error')]
    times = sorted(outcome['average_clear_time_s'] for _, outcome in valid)
    full = [outcome['average_clear_time_s'] for _, outcome in valid if outcome['all_cleared']]
    early = [outcome for _, outcome in valid if outcome['probability_exit']]
    failures = sum(not outcome['all_cleared'] for _, outcome in paired)
    false_exits = sum(not outcome['all_cleared'] for outcome in early)
    savings = [row['baseline_statistics']['virtual_time_s'] - outcome['virtual_time_s']
               for row, outcome in valid]
    mean = lambda values: statistics.mean(values) if values else None
    return dict(
        episodes=len(rows), errors=len(rows) - len(valid),
        full_clear_episodes=len(rows) - failures, incomplete_episodes=failures,
        missed_sources=sum(outcome['remaining_count'] for _, outcome in paired),
        probability_exits=len(early), false_probability_exits=false_exits,
        certified_completions=sum(outcome['completion_certified'] for _, outcome in paired),
        nominal_iid_95_upper_incomplete_rate=binomial_upper(failures, len(rows)),
        nominal_iid_95_upper_false_exit_rate_given_exit=binomial_upper(false_exits, len(early)),
        mean_average_clear_time_s=mean(times), mean_full_clear_only_s=mean(full),
        std_average_clear_time_s=statistics.pstdev(times) if times else None,
        p90_average_clear_time_s=times[math.ceil(.9 * len(times)) - 1] if times else None,
        mean_saved_virtual_s=mean(savings) if savings else 0.,
        max_saved_virtual_s=max(savings, default=0.),
        mean_saved_s_per_original_source=mean([
            (row['baseline_statistics']['virtual_time_s'] - outcome['virtual_time_s'])
            / row['baseline_statistics']['source_count'] for row, outcome in valid]),
        full_clear_and_time_threshold=sum(outcome['all_cleared'] and not outcome.get('error')
            and outcome['average_clear_time_s'] <= (220 if row['problem'] == 3 else 400)
            for row, outcome in paired),
    )


def verify_metrics(expected, actual, label):
    require(set(expected) == set(actual), f'{label} 汇总字段不一致')
    for key, value in actual.items():
        recorded = expected[key]
        if isinstance(value, float):
            require(isinstance(recorded, (int, float)) and math.isfinite(recorded)
                    and math.isclose(value, recorded, rel_tol=1e-9, abs_tol=1e-8),
                    f'{label}.{key} 重算不一致：{recorded} / {value}')
        else:
            require(recorded == value, f'{label}.{key} 重算不一致：{recorded} / {value}')


def verify_episode(row, label):
    require(set(row['outcomes']) == set(BRANCHES), f'{label} 不是完整 24 阈值 + 安全基线')
    baseline = row['baseline_statistics']
    total = baseline['source_count']
    require(10 <= total <= 16, f'{label} 非法源数')
    require(math.isclose(baseline['virtual_time_s'], baseline['movement_m'] / 5
            + 5 * baseline['measure'] + baseline['switch']
            + 5 * (baseline['clear'] - baseline['failed_clear'])
            + 3 * baseline['failed_clear'], rel_tol=1e-10, abs_tol=1e-6),
            f'{label} 基线物理计时不守恒')
    for branch, outcome in row['outcomes'].items():
        cleared, remaining = outcome['cleared_count'], outcome['remaining_count']
        require(cleared + remaining == total and min(cleared, remaining) >= 0,
                f'{label}/{branch} 清除与剩余数不守恒')
        require(outcome['all_cleared'] == (remaining == 0), f'{label}/{branch} 全清标记错误')
        if not outcome.get('error'):
            require(cleared > 0 and math.isclose(outcome['average_clear_time_s'],
                    outcome['virtual_time_s'] / cleared, rel_tol=1e-10, abs_tol=1e-7),
                    f'{label}/{branch} T/k 不一致')
        require(outcome['virtual_time_s'] <= baseline['virtual_time_s'] + 1e-6,
                f'{label}/{branch} 停止时间超出完整轨迹')
        if outcome['probability_exit']:
            require(not outcome['completion_certified'], f'{label}/{branch} 概率退出冒充认证')
            require(10 <= cleared < 16, f'{label}/{branch} 概率退出的清除数非法')


def verify_trace(report):
    path = root_path(report['trace_file'])
    require(path.is_file(), f'轨迹不存在：{path}')
    require(digest(path) == report['trace_sha256'], f'轨迹 SHA256 不一致：{path.name}')
    expected = {row['case_id']: row for row in report['episodes']}
    seen = set()
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            trace = json.loads(line)
            case_id = trace['case_id']
            require(case_id in expected and case_id not in seen, f'轨迹案例重复或未知：{case_id}')
            seen.add(case_id)
            row = expected[case_id]
            require(trace['outcomes'] == row['outcomes'], f'{case_id} 轨迹与逐局 outcomes 不一致')
            require(trace['baseline_statistics'] == row['baseline_statistics'], f'{case_id} 基线统计不一致')
            require(trace['case_sha256'] == row['case_sha256'], f'{case_id} 案例指纹不一致')
            checkpoints = trace['checkpoints']
            for branch in BRANCHES[1:]:
                mode, threshold_text = branch.split('_')
                threshold = float(threshold_text)
                first = next((index for index, checkpoint in enumerate(checkpoints)
                    if not checkpoint['public']['final_safe']
                    and checkpoint['estimate']['eligible']
                    and checkpoint['estimate'][mode] >= threshold), None)
                outcome = row['outcomes'][branch]
                require(outcome['probability_exit'] == (first is not None),
                        f'{case_id}/{branch} 提前退出与首次跨越不符')
                if first is not None:
                    checkpoint = checkpoints[first]
                    public, truth = checkpoint['public'], checkpoint['truth']
                    require(outcome['checkpoint_index'] == first,
                            f'{case_id}/{branch} 并非首次跨越')
                    require(outcome['virtual_time_s'] == public['time_s'],
                            f'{case_id}/{branch} 退出时间不是该公开前缀的时刻')
                    require(set(public['detected_channels']) <= set(public['cleared_channels']),
                            f'{case_id}/{branch} 仍有已发现源未清除')
                    require(outcome['cleared_count'] == len(public['cleared_channels'])
                            and outcome['remaining_count'] == truth['remaining_count']
                            and outcome['all_cleared'] == truth['all_cleared'],
                            f'{case_id}/{branch} 事后真值标注不一致')
                else:
                    require(outcome == row['outcomes']['safe_v4'],
                            f'{case_id}/{branch} 未跨越却不等于安全回退')
    require(seen == set(expected), f'{path.name} 轨迹案例不齐')


def load_verified(directory):
    freeze_path = directory / 'freeze.json'
    freeze = json.loads(freeze_path.read_text(encoding='utf-8')) if freeze_path.is_file() else None
    if freeze:
        verify_sources(freeze['source_lf_sha256'], 'freeze')
        require(tuple(freeze['thresholds']) == THRESHOLDS and tuple(freeze['modes']) == MODES,
                'freeze 预注册阈值或模式不一致')
        require(freeze['main_comparisons'] == list(PRIMARY[1:]), 'freeze 主比较并非预设 .99')
    reports, missing = {}, []
    for problem in (3, 4):
        for split in SPLITS:
            path = directory / f'p{problem}_{split}.json'
            if not path.is_file():
                missing.append(path.name)
                continue
            report = json.loads(path.read_text(encoding='utf-8'))
            label = path.name
            require(report['problem'] == problem and report['split'] == split, f'{label} 身份字段错误')
            verify_sources(report['source_lf_sha256'], label)
            if freeze:
                require(report['source_lf_sha256'] == freeze['source_lf_sha256'], f'{label} 源码与 freeze 不一致')
                require(report['particles'] == freeze['particles'], f'{label} 粒子数与 freeze 不一致')
            require(tuple(report['thresholds']) == THRESHOLDS, f'{label} 阈值不齐')
            rows = report['episodes']
            require(rows and len(rows) == report['count'], f'{label} 局数不一致或为空')
            require([row['index'] for row in rows] == list(range(len(rows))), f'{label} 编号重复或不连续')
            require(len({row['case_id'] for row in rows}) == len(rows), f'{label} case_id 重复')
            for row in rows:
                require(row['problem'] == problem and row['split'] == split, f'{label} 混入其他数据集')
                verify_episode(row, row['case_id'])
            require(set(report['summary']) == set(BRANCHES), f'{label} 分支汇总不齐')
            for branch in BRANCHES:
                verify_metrics(report['summary'][branch], recompute(rows, branch), f'{label}/{branch}')
            groups = {family: [row for row in rows if row['family'] == family]
                      for family in {row['family'] for row in rows}}
            require(set(groups) == set(report['by_family']), f'{label} 分族汇总不齐')
            for family, subset in groups.items():
                for branch in BRANCHES:
                    verify_metrics(report['by_family'][family][branch], recompute(subset, branch),
                                   f'{label}/{family}/{branch}')
            verify_trace(report)
            reports[problem, split] = report
    return freeze, reports, missing


def number(value, digits=2):
    return '—' if value is None else f'{value:.{digits}f}'


def table(lines, columns, rows):
    lines.extend(['', '| ' + ' | '.join(columns) + ' |',
                  '| ' + ' | '.join('---' for _ in columns) + ' |'])
    lines.extend('| ' + ' | '.join(map(str, row)) + ' |' for row in rows)
    lines.append('')


def summary_cells(summary):
    return [f"{summary['full_clear_episodes']}/{summary['episodes']}",
            f"{summary['incomplete_episodes']}/{summary['missed_sources']}",
            f"{summary['probability_exits']}/{summary['false_probability_exits']}",
            summary['certified_completions'], number(summary['mean_average_clear_time_s']),
            number(summary['mean_saved_s_per_original_source'])]


def render(directory, freeze, reports, missing):
    complete = bool(freeze and not missing and all(
        report['count'] == SPLITS[split] for (_, split), report in reports.items()))
    lines = ['# 概率提前停止：本地验证报告', '']
    if all(key in reports for key in ((3, 'holdout'), (4, 'holdout'), (4, 'stress'))):
        h4 = reports[4, 'holdout']['summary']['nominal_0.99']
        s4 = reports[4, 'stress']['summary']['nominal_0.99']
        h3 = reports[3, 'holdout']['summary']['nominal_0.99']
        lines.append('本轮不建议直接使用概率提前停止。P4 普通 99% 阈值在留出集平均只省 '
            f"{h4['mean_saved_s_per_original_source']:.2f} 秒/原始源，却漏清 {h4['incomplete_episodes']} 局；"
            f"压力集漏清 {s4['incomplete_episodes']} 局。P3 同阈值留出集提前退出 "
            f"{h3['probability_exits']} 次、平均节省 {h3['mean_saved_s_per_original_source']:.2f} 秒/源。"
            + ('guarded 99% 在两问全部数据集中均未触发，不能证明提前停止安全。'
               if all(report['summary']['guarded_0.99']['probability_exits'] == 0
                      for report in reports.values()) else 'guarded 99% 的触发与漏清次数见下表。'))
        lines.append('')
    lines.extend(['安全默认仍为 `problem3_v4 / problem4_v4`。以下均为自建环境结果，不是官方模拟器成绩。', ''])
    total = sum(report['count'] for report in reports.values())
    if complete:
        lines.append(f'四个数据集已齐：每问 3328 局，两问共 {total} 局；每局比较安全基线及 24 个预设概率分支。')
    else:
        lines.append(f'**临时报告：目前完成 {total} 局，计划每问 3328 局、两问共 6656 局。**')
        if missing:
            lines.append('待补齐：' + '、'.join(f'`{name}`' for name in missing) + '。')
        if not freeze:
            lines.append('尚无 `freeze.json`，不能认定已经完成冻结验证。')
        nondefault = [f'P{problem} {split}={report["count"]}/{SPLITS[split]}'
                      for (problem, split), report in reports.items() if report['count'] != SPLITS[split]]
        if nondefault:
            lines.append('当前数量与计划不同：' + '、'.join(nondefault) + '。')
    table(lines, ['问题', '开发', '校准', '留出', '压力', '合计'], [
        [f'P{problem}'] + [reports[problem, split]['count'] if (problem, split) in reports else '待补'
                           for split in SPLITS] + [sum(r['count'] for (p, _), r in reports.items() if p == problem)]
        for problem in (3, 4)])
    lines.extend([
        '`nominal` 使用均匀位置/半径/方向先验；`robust` 对五种先验取保守包络，并向较多源数倾斜；'
        '`guarded` 在此基础上给粒子积分加入同时数值上界。三者都依赖源分布假设；数值保护不等于控制真实场景漏清率。'
        '压力模型可能与已知源位置不相容，因此后两者只作先验敏感性分数；推导和限制见 [model.md](model.md)。', '',
        '每个阈值只取公开轨迹上第一次合格跨越。完整基线实际执行到退出；提前退出时间由该前缀回放，'
        '本地 exit 不增加虚拟时间，另有实际停止运行与回放等价检查。只有停止规则改变，定位和路线不变。', '',
        '表中“全清”由结束后的外部真值核对；“认证”由覆盖证明或成功清除 16 个源给出。'
        '概率提前退出一律不认证，即使该局实际全部清除。“漏局/源”分别统计漏清局数和遗漏源数；'
        '“早退/错退”分别统计概率退出及其中漏清次数。', '',
        '“T/k”是无运行错误局的退出总虚拟时间除以已清源数后的均值，包含漏清局，不能据此宣称达标；'
        '“省时/N”用原始源总数固定分母计算成对节省秒/源。全清子集均值存在选择偏差。'
        '统计单位是整局，24 个共享轨迹分支不是新增独立样本。', '',
        '## 预先固定的主对照', '',
        '主比较固定为 `nominal 0.99` 与 `guarded 0.99`。留出/压力结果不用于重新选参数。'])
    primary_rows = []
    for problem in (3, 4):
        for split in ('holdout', 'stress', 'calibration', 'development'):
            report = reports.get((problem, split))
            if report:
                for branch in PRIMARY:
                    primary_rows.append([f'P{problem}', SPLIT_NAMES[split], branch]
                                        + summary_cells(report['summary'][branch]))
    table(lines, ['问题', '数据集', '分支', '全清', '漏局/源', '早退/错退', '认证', 'T/k 秒', '省时/N 秒'], primary_rows)
    lines.extend(['**零次提前退出只说明分支回退到了安全策略，不能据此验证提前退出安全。**', '',
                  '## .95 与 .80 的风险对照'])
    risk_rows = []
    for (problem, split), report in reports.items():
        for branch in ('nominal_0.95', 'nominal_0.8'):
            summary = report['summary'][branch]
            risk_rows.append([f'P{problem}', SPLIT_NAMES[split], branch]
                             + summary_cells(summary)[:3]
                             + [number(summary['mean_average_clear_time_s']),
                                number(summary['mean_full_clear_only_s'])])
    table(lines, ['问题', '数据集', '分支', '全清', '漏局/源', '早退/错退', '全体 T/k', '仅全清 T/k'], risk_rows)
    lines.extend(['## 二项上界：仅作 iid 参照', '',
        '以下为单侧 95% 精确二项上界。它假设整局独立同分布；本套件按源族固定配额构造，'
        '且真实平台分布未知，因此这里只作 iid 参照，不能解释为平台风险保证。'
        '零失败时上界为 `1 - 0.05^(1/n)`；未发生提前退出时，没有“退出后的失败率”验证样本。'])
    bound_rows = []
    for (problem, split), report in reports.items():
        for branch in PRIMARY[1:]:
            summary = report['summary'][branch]
            conditional = (number(100 * summary['nominal_iid_95_upper_false_exit_rate_given_exit']) + '%'
                           if summary['probability_exits'] else '—（未触发）')
            bound_rows.append([f'P{problem}', SPLIT_NAMES[split], branch,
                f"{summary['incomplete_episodes']}/{summary['episodes']}",
                number(100 * summary['nominal_iid_95_upper_incomplete_rate']) + '%',
                f"{summary['false_probability_exits']}/{summary['probability_exits']}", conditional])
    table(lines, ['问题', '数据集', '分支', '漏局/全部局', 'iid 上界', '错退/早退', '退出条件 iid 上界'], bound_rows)
    lines.extend(['## 完整 24 阈值对照', '',
                  '逐问优先列留出和压力集，随后列校准和开发集；所有预设分支均保留。'
                  '“全清且达时限”要求实际全清、无运行错误，且 P3 ≤220、P4 ≤400 秒/源。'])
    for problem in (3, 4):
        for split in ('holdout', 'stress', 'calibration', 'development'):
            report = reports.get((problem, split))
            if not report:
                continue
            lines.extend(['', f'### P{problem} · {SPLIT_NAMES[split]}（{report["count"]} 局）'])
            rows = []
            for branch in BRANCHES[1:]:
                summary = report['summary'][branch]
                rows.append([branch] + summary_cells(summary)
                            + [summary['full_clear_and_time_threshold']])
            table(lines, ['分支', '全清', '漏局/源', '早退/错退', '认证', 'T/k 秒', '省时/N 秒', '全清且达时限'], rows)
    lines.extend(['## 核验与证据边界', '',
        f'已核对 {len(reports)} 份结果：当前源码与各结果记录的 LF 归一化 SHA256 一致，'
        + ('并与 [冻结清单](freeze.json) 一致；' if freeze else '冻结清单待补；')
        + '压缩轨迹 SHA256 正确；逐局清除数、剩余数、物理时间守恒、首次阈值跨越、'
        '全体与分族汇总均通过独立重算。'])
    errors = sum(report['summary']['safe_v4']['errors'] for report in reports.values())
    lines.append(f'安全基线运行错误共 {errors} 局。错误单独保留；不得将运行失败当作成功提前退出。')
    if (directory / 'independent_audit.json').is_file():
        audit = json.loads((directory / 'independent_audit.json').read_text(encoding='utf-8'))
        verify_auxiliary_sources(audit)
        lines.append('独立数值检查及反例见 [independent_audit.json](independent_audit.json)。'
                     '反例用于展示先验失配风险，不并入随机套件局数，也不参与留出阈值选择。')
        example = audit.get('current_default_counterexample', {})
        if example.get('identical_public_trace'):
            base = example['base_run']['statistics']
            hidden = example['counterexample_run']['statistics']
            lines.append(f"该反例中，{base['source_count']} 源和 {hidden['source_count']} 源的合法场景具有完全相同的"
                         f"公开行动轨迹，nominal 99% 都在 {base['virtual_time_s']:.2f} 秒退出；"
                         f"前者清除 {base['cleared_count']}/{base['source_count']}，"
                         f"后者仅清除 {hidden['cleared_count']}/{hidden['source_count']}。"
                         '新增源躲过了全部已扫位置；相同模型分数不能区分这两个真实状态。')
    else:
        lines.append('独立数值与反例审计尚未落盘，暂不宣称该项已完成。')
    replay_path = directory / 'replay_checks.json'
    if replay_path.is_file():
        replay = json.loads(replay_path.read_text(encoding='utf-8'))
        verify_sources(replay['source_lf_sha256'], 'replay_checks')
        if freeze:
            require(replay['source_lf_sha256'] == freeze['source_lf_sha256'], 'replay_checks 与 freeze 不一致')
        if isinstance(replay.get('verifier_lf_sha256'), dict):
            verify_sources(replay['verifier_lf_sha256'], 'replay verifier')
        lines.append(f"实际执行与回放检查：{replay['matching_policy_runs']}/{replay['checked_policy_runs']} 次一致，"
                     f"其中实际概率退出 {replay['actual_probability_exits']} 次、"
                     f"安全回退 {replay['actual_safe_fallbacks']} 次。"
                     '详情及各分支是否真正触发见 [replay_checks.json](replay_checks.json)；'
                     '旧开发案例按触发情况筛选，只用于流程核对，不能估计风险率，也不并入上述统计局数。')
        if not replay.get('required_branch_coverage_met', False):
            lines.append('该检查未达到全部分支的实际退出样本配额；未触发的分支不能视作已完成实测退出验证。'
                         '固定布局的可达分数界如有证明，应与实际执行样本分别解读。')
        envelopes = replay.get('frozen_score_envelopes', {})
        if envelopes:
            lines.extend(['', '冻结模型在尚未完成覆盖、已清 10–15 源时的最高可达分数如下。'
                          '证明枚举固定布局的缺站集合并使用质量单调性，覆盖其未完成子集；'
                          '**这是模型分数的界，不是真实全清概率或漏清率的界。**'])
            table(lines, ['问题', 'nominal 最高分', 'robust 最高分', 'guarded 最高分'], [
                [f'P{problem}'] + [number(envelopes[str(problem)]['maxima'][mode]['score'], 9)
                                  for mode in MODES] for problem in (3, 4)])
            if (envelopes['3']['maxima']['nominal']['score'] < .99
                    and envelopes['4']['maxima']['guarded']['score'] < .8):
                lines.append('因此，固定实现中的 P3 nominal 0.99、P4 guarded ≥0.80 '
                             '本就无法触发提前退出；这解释了零触发，不能转述为提前退出风险已被验证为零。')
    lines.extend(['完整逐局记录保留在本目录各 `p{问题}_{数据集}.json` 及对应 `.jsonl.gz`；'
                  '固定实验口径见 [protocol.md](protocol.md)。源码校验使用 LF 归一化口径，'
                  '独立审计的历史字节指纹保留；若只有旧字段，仅允许 LF/CRLF 等价差异。'
                  '压缩轨迹为二进制文件，始终使用原始字节 SHA256。', ''])
    return '\n'.join(lines), complete


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=ROOT / 'validation/probability_stop')
    parser.add_argument('--output', type=Path, default=ROOT / 'validation/probability_stop/report.md')
    parser.add_argument('--require-complete', action='store_true', help='八份结果和全部计划局数齐全才写报告')
    args = parser.parse_args(argv)
    directory = args.input_dir if args.input_dir.is_absolute() else ROOT / args.input_dir
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        freeze, reports, missing = load_verified(directory)
        require(reports, '尚无已完成的结果文件')
        content, complete = render(directory, freeze, reports, missing)
        require(not args.require_complete or complete, '结果尚未齐全；未覆盖现有报告')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding='utf-8')
    print(f'已核验 {len(reports)} 份结果，{sum(r["count"] for r in reports.values())} 局；'
          f'{"完整" if complete else "临时"}报告：{output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

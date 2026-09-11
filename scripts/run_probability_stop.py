"""Run one local synthetic probabilistic-stop experiment; no online support.

Example: python scripts/run_probability_stop.py --problem 4 --index 11
Relative --case and --output paths are resolved under the selected problem
directory, irrespective of the current working directory.  The safe solve.py
entry points are unchanged.  NumPy is required only for this optional model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_local(case: dict, *, threshold: float = .99, mode: str = 'guarded',
              particles: int | None = None) -> dict:
    """Run through the public facade; label truth only after the actual exit."""
    from problem3.probability_stop import DEFAULT_PARTICLES, make_policy
    from problem3.simulator import LocalSimulator, ObservationClient

    particles = DEFAULT_PARTICLES if particles is None else particles
    problem = case.get('problem')
    if type(problem) is not int or problem not in (3, 4):
        raise ValueError('Case problem must be 3 or 4')
    sources = case.get('sources', [])
    if (not isinstance(sources, list)
            or any(not isinstance(source, dict) for source in sources)
            or not 10 <= len(sources) <= 16):
        raise ValueError('A case must contain 10 to 16 sources')
    directional = sum(source.get('orientation_deg') is not None for source in sources)
    if (problem == 3 and directional) or (problem == 4 and not 0 < directional < len(sources)):
        raise ValueError('P3 requires all omni; P4 requires both omni and directional sources')
    simulator = LocalSimulator(case)
    policy = make_policy(problem, threshold=threshold, probability_mode=mode, particles=particles)
    result, error, exit_response = {}, None, None
    entered = False
    started = time.perf_counter()
    try:
        entered = simulator.enter().get('accepted') is True
        if not entered:
            raise RuntimeError('Local enter was rejected')
        result = policy.run(ObservationClient(simulator))
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
    finally:
        if entered and simulator.active:
            try:
                exit_response = simulator.exit()
                if exit_response.get('accepted') is not True:
                    raise RuntimeError('Local exit was rejected')
            except Exception as exc:
                detail = f'exit: {type(exc).__name__}: {exc}'
                error = f'{error}; {detail}' if error else detail
    exit_accepted = bool(exit_response and exit_response.get('accepted') is True)
    statistics = simulator.statistics()
    # Only this outer harness reads simulator truth.  Neither stopping nor
    # localization/routing receives the case, source count, seed or family.
    remaining = set(simulator.sources) - simulator.cleared
    all_cleared = not remaining
    probability_exit = result.get('termination_reason') == 'experimental_probability_threshold'
    certified = bool(result.get('completion_certified', False))
    if probability_exit:
        certified = False
    return dict(
        problem=problem, case_id=case.get('case_id', 'custom_local_case'),
        case_sha256=hashlib.sha256(json.dumps(case, sort_keys=True).encode()).hexdigest(),
        provenance='self_constructed_not_official',
        strategy='experimental_probability_stop',
        algorithm_version=result.get('algorithm_version'),
        base_algorithm_version=result.get('base_algorithm_version'),
        settings=dict(threshold=threshold, mode=mode, particles=particles),
        **statistics, remaining_count=len(remaining), all_cleared=all_cleared,
        completion_certified=certified,
        certified_full_clear=bool(certified and all_cleared and exit_accepted and not error),
        probability_exit=probability_exit,
        entered=entered, exit_accepted=exit_accepted, exit_response=exit_response,
        statistics_final=bool(exit_accepted and not simulator.active),
        statistics_scope='local_simulator_after_exit',
        local_program_runtime_s=time.perf_counter() - started,
        policy=result, error=error,
        note=('仅本地自建实验。all_cleared 来自运行结束后的外部真值核对；'
              'completion_certified 表示策略的完整性证明。概率提前退出时后者为 false，'
              '即使本例恰好全部清除，也不构成覆盖证明或平台成功率保证。'),
    )


def main(argv=None) -> int:
    from problem3.probability_scenarios import generate_case
    from problem3.probability_stop import DEFAULT_PARTICLES, MODES

    parser = argparse.ArgumentParser(description='概率提前停止的本地演练；不支持连接平台。')
    parser.add_argument('--problem', type=int, choices=(3, 4), required=True)
    parser.add_argument('--case', type=Path, help='自选本地 JSON；相对路径基于对应问题目录')
    parser.add_argument('--index', type=int, default=0, help='新 development 样本编号，默认 0')
    parser.add_argument('--threshold', type=float, default=.99)
    parser.add_argument('--mode', choices=MODES, default='guarded')
    parser.add_argument('--particles', type=int, default=DEFAULT_PARTICLES)
    parser.add_argument('--output', type=Path, help='结果 JSON；相对路径基于对应问题目录')
    parser.add_argument('--online', action='store_true', help='不支持；指定此项会直接报错')
    args = parser.parse_args(argv)
    if args.online:
        parser.error('--online 不受支持：此入口只运行本地实验，不能连接平台')
    if not math.isfinite(args.threshold) or not 0 < args.threshold < 1:
        parser.error('--threshold 必须严格位于 0 和 1 之间')
    if args.particles < 64:
        parser.error('--particles 必须至少为 64')
    here = ROOT / f'problem{args.problem}'

    def resolve(path):
        return path if path.is_absolute() else here / path

    output = resolve(args.output) if args.output else here / 'results/probability_stop_demo.json'
    try:
        if args.case:
            case_path = resolve(args.case)
            if output.resolve() == case_path.resolve():
                parser.error('--output 不能覆盖输入案例')
            case = json.loads(case_path.read_text(encoding='utf-8-sig'))
        else:
            case = generate_case(args.problem, args.index, split='development')
        if not isinstance(case, dict) or case.get('problem') != args.problem:
            parser.error('案例 problem 必须与 --problem 一致')
        row = run_local(case, threshold=args.threshold, mode=args.mode, particles=args.particles)
    except (OSError, ValueError, TypeError, KeyError, ImportError) as exc:
        parser.error(str(exc))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    average = row['average_clear_time_s']
    average_text = f'{average:.2f} 秒/源' if average is not None else '无定义'
    print(f"本地自建案例 {row['case_id']}：清除 {row['cleared_count']}/{row['source_count']}，"
          f"平均 {average_text}。")
    print(f"概率提前退出={row['probability_exit']}，实际全清={row['all_cleared']}，"
          f"完整性证明={row['completion_certified']}，已确认退出={row['exit_accepted']}。")
    print(f'结果：{output}')
    if row['error']:
        print(row['error'], file=sys.stderr)
    return 0 if row['all_cleared'] and row['exit_accepted'] and not row['error'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

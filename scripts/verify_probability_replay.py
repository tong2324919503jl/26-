"""Execute frozen probability policies and verify offline first-crossing replay.

Only the already opened development_v3 suite is used. The first 32 cases per
problem are checked unconditionally, followed by further old cases if needed
to exercise at least eight nominal exits (.95 for P3, .99 for P4). P3 cannot
reach .99 before completing its fixed layouts, as a separate score enumeration
checks. Selecting extra examples is for control-flow testing, never for
estimating failure rates or speed means.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from problem3.probability_stop import DEFAULT_PARTICLES, get_model, make_policy
from problem3.probability_numeric import supported_layouts
from problem3.probability_trace import capture_case
from problem3.scenarios import SPLITS, generate_case
from problem3.simulator import LocalSimulator, ObservationClient
from scripts.benchmark_probability_stop import evaluate_trace, source_fingerprint

SETTINGS = (('nominal', .8), ('nominal', .95), ('nominal', .99), ('guarded', .99))


def layout_score_envelope(problem, particles):
    """Frozen computed scores, NOT bounds on the true full-clear probability.

    Any unfinished scan subset is contained in a layout with one unvisited
    station omitted. Adding scan points cannot increase any unseen mass, so
    its score cannot exceed a one-omission score with the same cleared count.
    P3's origin is necessarily visited first; P4 is checked even if omitted.
    """
    model = get_model(problem, particles)
    modes = ('nominal', 'robust', 'guarded')
    maxima = {mode: {'score': -1.} for mode in modes}
    rows = []
    for layout_index, layout in enumerate(supported_layouts(problem)):
        for omitted, point in enumerate(layout):
            if problem == 3 and point == (0., 0.):
                continue
            points = layout[:omitted] + layout[omitted+1:]
            scores = {mode: {'score': -1.} for mode in modes}
            for cleared in range(10, 16):
                estimate = model.estimate(points, cleared)
                for mode in modes:
                    if estimate[mode] > scores[mode]['score']:
                        scores[mode] = {'score': estimate[mode], 'cleared_count': cleared}
                    if estimate[mode] > maxima[mode]['score']:
                        maxima[mode] = {'score': estimate[mode], 'cleared_count': cleared,
                                        'layout_index': layout_index, 'omitted_station': omitted}
            rows.append({'layout_index': layout_index, 'omitted_station': omitted,
                         'omitted_position': point, 'maxima_over_k_10_to_15': scores})
    origin_only = {str(k): {mode: model.estimate([(0., 0.)], k)[mode] for mode in modes}
                   for k in range(10, 16)}
    return {
        'meaning': 'Maximum frozen integration-model SCORE over unfinished supported scan subsets; not a true probability bound',
        'origin_preserved': problem == 3,
        'count_range': [10, 15], 'layouts': len(supported_layouts(problem)),
        'one_omission_count': len(rows), 'maxima': maxima,
        'origin_only_scores': origin_only, 'one_omission_rows': rows,
        'reason': 'Every unfinished subset is contained in a one-omission set; scores are monotone under adding full scan points. Sixteen clears use the deterministic safe return.',
    }


def execute_and_compare(case, evaluated, mode, threshold, particles):
    """Truth labels both completed runs externally; policies get only a client."""
    branch = f'{mode}_{threshold:g}'
    expected = evaluated['outcomes'][branch]
    simulator = LocalSimulator(case)
    simulator.enter()
    result = None
    error = None
    try:
        policy = make_policy(case['problem'], probability_mode=mode,
                             threshold=threshold, particles=particles)
        result = policy.run(ObservationClient(simulator))
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
    finally:
        simulator.exit()
    stats = simulator.statistics()
    actual = {
        'virtual_time_s': stats['virtual_time_s'],
        'average_clear_time_s': stats['average_clear_time_s'],
        'cleared_count': stats['cleared_count'],
        'remaining_count': stats['source_count'] - stats['cleared_count'],
        'all_cleared': stats['source_count'] == stats['cleared_count'],
        'completion_certified': bool(result and result['completion_certified']),
        'probability_exit': bool(result and result['termination_reason'] ==
                                 'experimental_probability_threshold'),
        'error': error,
    }
    mismatches = []
    for field in actual:
        if actual[field] != expected[field]:
            mismatches.append(field)
    if expected['probability_exit']:
        point = evaluated['checkpoints'][expected['checkpoint_index']]
        public = point['public']
        if list(simulator.position) != public['position']:
            mismatches.append('position')
        if simulator.current_channel != public['current_channel']:
            mismatches.append('current_channel')
        for name in ('measure', 'clear', 'failed_clear', 'switch', 'no_signal', 'actions'):
            if stats[name] != public['counts'][name]:
                mismatches.append('count_' + name)
        if not point['estimate']['eligible'] or point['estimate'][mode] < threshold:
            mismatches.append('crossing_not_eligible')
        if any(cp['estimate']['eligible'] and cp['estimate'][mode] >= threshold
               for cp in evaluated['checkpoints'][:expected['checkpoint_index']]
               if not cp['public']['final_safe']):
            mismatches.append('not_first_crossing')
    elif stats != evaluated['baseline_statistics']:
        mismatches.append('safe_fallback_statistics')
    return {'branch': branch, 'expected': expected, 'actual': actual,
            'checks_passed': not mismatches, 'mismatches': mismatches}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', type=int, default=32)
    parser.add_argument('--minimum-nominal-exits', type=int, default=8)
    parser.add_argument('--particles', type=int, default=DEFAULT_PARTICLES)
    parser.add_argument('--output', type=Path,
                        default=ROOT/'validation/probability_stop/replay_checks.json')
    args = parser.parse_args()
    if not 1 <= args.count <= SPLITS['development_v3'][1]:
        parser.error('count must be between 1 and 384 old development cases')
    if args.minimum_nominal_exits < 0:
        parser.error('minimum exits must be nonnegative')
    output = args.output if args.output.is_absolute() else ROOT/args.output
    if output.exists():
        parser.error('Refusing to overwrite an existing validation report')
    freeze_path = ROOT/'validation/probability_stop/freeze.json'
    freeze = json.loads(freeze_path.read_text(encoding='utf-8'))
    before = source_fingerprint()
    if before != freeze['source_lf_sha256']:
        raise RuntimeError('Source fingerprints differ from the frozen experiment')
    started = time.perf_counter()
    rows = []
    coverage = {}
    envelopes = {str(problem): layout_score_envelope(problem, args.particles) for problem in (3, 4)}
    for problem in (3, 4):
        exercise_threshold = .95 if problem == 3 else .99
        exercise_branch = f'nominal_{exercise_threshold:g}'
        nominal_exits = 0
        selected = []
        for index in range(SPLITS['development_v3'][1]):
            case = generate_case(problem, index, 'development_v3')
            trace = evaluate_trace(capture_case(case), particles=args.particles)
            if trace['error'] or not trace['outcomes']['safe_v4']['completion_certified']:
                raise RuntimeError(f'Safe baseline failed on {case["case_id"]}')
            crosses = trace['outcomes'][exercise_branch]['probability_exit']
            if index < args.count or (crosses and nominal_exits < args.minimum_nominal_exits):
                checks = [execute_and_compare(case, trace, mode, threshold, args.particles)
                          for mode, threshold in SETTINGS]
                rows.append({'problem': problem, 'case_id': case['case_id'],
                             'old_development_index': index, 'checks': checks})
                selected.append(index)
                nominal_exits += int(crosses)
                print(f'P{problem} old case {index}: '
                      f'{sum(c["checks_passed"] for c in checks)}/{len(checks)} match; '
                      f'{nominal_exits} nominal {exercise_threshold:g} exits', flush=True)
            if index >= args.count - 1 and nominal_exits >= args.minimum_nominal_exits:
                break
        coverage[str(problem)] = {
            'old_cases_scanned': index + 1, 'cases_executed': len(selected),
            'selected_indices': selected, 'exercised_branch': exercise_branch,
            'nominal_exits_executed': nominal_exits,
            'first_requested_cases_present': selected[:args.count] == list(range(args.count)),
            'minimum_exit_coverage_met': nominal_exits >= args.minimum_nominal_exits,
        }
    after = source_fingerprint()
    checks = [check for row in rows for check in row['checks']]
    passed = all(c['checks_passed'] for c in checks)
    required = all(c['first_requested_cases_present'] and c['minimum_exit_coverage_met']
                   for c in coverage.values())
    report = {
        'provenance': 'OLD self-built development_v3; control-flow verification, not performance estimation',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'particles': args.particles, 'settings': SETTINGS,
        'requested_first_cases_per_problem': args.count,
        'requested_nominal_exits_per_problem': args.minimum_nominal_exits,
        'checked_policy_runs': len(checks), 'matching_policy_runs': sum(c['checks_passed'] for c in checks),
        'actual_probability_exits': sum(c['actual']['probability_exit'] for c in checks),
        'actual_safe_fallbacks': sum(c['actual']['completion_certified'] for c in checks),
        'all_checks_passed': passed, 'required_branch_coverage_met': required,
        'frozen_sources_unchanged': before == after == freeze['source_lf_sha256'],
        'source_lf_sha256': after,
        'verifier_lf_sha256': hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
        'elapsed_wall_s': time.perf_counter() - started, 'coverage': coverage,
        'frozen_score_envelopes': envelopes, 'cases': rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(checks)} executions; all matched={passed}; branch coverage={required}; {output}', flush=True)
    if not (passed and required and report['frozen_sources_unchanged']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()

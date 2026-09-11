"""Local-only, first-crossing evaluation of experimental probability exits.

The safe v4 trajectory is collected in full.  Each threshold is evaluated at
its FIRST eligible crossing using only public history; source truth labels the
decision afterwards.  This is an exact counterfactual for a stop-only change,
and a separately executed stopping policy checks the replay equivalence.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from problem3.probability_stop import (DEFAULT_PARTICLES, MODEL_VERSION, MODES, THRESHOLDS,
                                      get_model)


def upper_failure_bound(failures, count, alpha=.05):
    """Exact one-sided binomial inversion; episodes, not correlated checkpoints.

    Valid for independent identically distributed episodes from the evaluated
    distribution. Fixed family strata and distribution shift limit application
    to a real platform. No extrapolation to adversarial configurations.
    """
    if count == 0 or failures == count:
        return 1.
    if failures == 0:
        return -math.expm1(math.log(alpha)/count)
    def cdf(p):
        terms = [math.lgamma(count+1)-math.lgamma(i+1)-math.lgamma(count-i+1)
                 +i*math.log(p)+(count-i)*math.log1p(-p)
                 for i in range(failures+1)]
        top = max(terms)
        return math.exp(top)*sum(math.exp(v-top) for v in terms)
    lo, hi = failures/count, 1.
    for _ in range(55):
        mid = (lo+hi)/2
        if cdf(mid) > alpha:
            lo = mid
        else:
            hi = mid
    return (lo+hi)/2


def summarize(rows, branch):
    items = [r['outcomes'][branch] for r in rows]
    valid = [x for x in items if not x.get('error')]
    failures = sum(not x['all_cleared'] for x in items)
    times = sorted(x['average_clear_time_s'] for x in valid)
    full = [x['average_clear_time_s'] for x in valid if x['all_cleared']]
    early = [x for x in valid if x['probability_exit']]
    false_exits = sum(not x['all_cleared'] for x in early)
    savings = [r['baseline_statistics']['virtual_time_s']-x['virtual_time_s']
               for r, x in zip(rows, items) if not x.get('error')]
    # T/N is shown solely as a diagnostic with a fixed denominator. A missed
    # source invalidates completion irrespective of a superficially low T/k.
    return dict(episodes=len(items), errors=len(items)-len(valid),
                full_clear_episodes=len(items)-failures, incomplete_episodes=failures,
                missed_sources=sum(x['remaining_count'] for x in items),
                probability_exits=len(early), false_probability_exits=false_exits,
                certified_completions=sum(x['completion_certified'] for x in items),
                nominal_iid_95_upper_incomplete_rate=upper_failure_bound(failures, len(items)),
                nominal_iid_95_upper_false_exit_rate_given_exit=upper_failure_bound(false_exits, len(early)),
                mean_average_clear_time_s=statistics.mean(times) if times else None,
                mean_full_clear_only_s=statistics.mean(full) if full else None,
                std_average_clear_time_s=statistics.pstdev(times) if times else None,
                p90_average_clear_time_s=times[math.ceil(.9*len(times))-1] if times else None,
                mean_saved_virtual_s=statistics.mean(savings) if savings else 0.,
                max_saved_virtual_s=max(savings, default=0.),
                mean_saved_s_per_original_source=statistics.mean(
                    (r['baseline_statistics']['virtual_time_s']-x['virtual_time_s']) /
                    r['baseline_statistics']['source_count']
                    for r, x in zip(rows, items) if not x.get('error')) if valid else None,
                full_clear_and_time_threshold=sum(x['all_cleared'] and not x.get('error') and
                    x['average_clear_time_s'] <= (220 if r['problem'] == 3 else 400)
                    for r, x in zip(rows, items)))


def evaluate_trace(trace, *, particles=DEFAULT_PARTICLES):
    model = get_model(trace['problem'], particles)
    stats = trace['baseline_statistics']
    points = trace['checkpoints']
    for point in points:
        if point['public']['final_safe']:
            continue
        public = point['public']
        point['estimate'] = model.estimate(public['coverage_visited'], len(public['cleared_channels']),
            known_pending=bool(set(public['detected_channels'])-set(public['cleared_channels'])))
    baseline = dict(virtual_time_s=stats['virtual_time_s'],
                    average_clear_time_s=stats['average_clear_time_s'],
                    cleared_count=stats['cleared_count'],
                    remaining_count=stats['source_count']-stats['cleared_count'],
                    all_cleared=stats['source_count']==stats['cleared_count'],
                    completion_certified=(trace['baseline_result'] or {}).get('completion_certified', False),
                    probability_exit=False, error=trace.get('error'))
    outcomes = {'safe_v4': baseline}
    for mode in MODES:
        for threshold in THRESHOLDS:
            crossing = next((cp for cp in points if not cp['public']['final_safe'] and
                cp['estimate']['eligible'] and cp['estimate'][mode] >= threshold), None)
            name = f'{mode}_{threshold:g}'
            if crossing is None:
                outcomes[name] = dict(baseline)
                continue
            public, truth = crossing['public'], crossing['truth']
            k = len(public['cleared_channels'])
            outcomes[name] = dict(virtual_time_s=public['time_s'],
                average_clear_time_s=public['time_s']/k, cleared_count=k,
                remaining_count=truth['remaining_count'], all_cleared=truth['all_cleared'],
                completion_certified=False, probability_exit=True, error=None,
                probability=crossing['estimate'][mode], scan_count=len(public['coverage_visited']),
                checkpoint_index=points.index(crossing))
    trace['outcomes'] = outcomes
    return trace


def worker(task):
    from problem3.probability_scenarios import generate_case
    from problem3.probability_trace import capture_case
    problem, split, index, particles = task
    case = generate_case(problem, index, split)
    trace = capture_case(case)
    trace['case_sha256'] = hashlib.sha256(json.dumps(case, sort_keys=True).encode()).hexdigest()
    trace['family'], trace['split'], trace['index'] = case['family'], split, index
    return evaluate_trace(trace, particles=particles)


def source_fingerprint():
    paths = [ROOT/'scripts/benchmark_probability_stop.py']
    paths += sorted((ROOT/'problem3').glob('*.py')) + sorted((ROOT/'problem4').glob('*.py'))
    return {str(p.relative_to(ROOT)).replace('\\', '/'):
            hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n').replace(b'\r', b'\n')).hexdigest()
            for p in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--problem', type=int, choices=(3, 4), required=True)
    parser.add_argument('--split', choices=('development', 'calibration', 'holdout', 'stress'), required=True)
    parser.add_argument('--count', type=int)
    parser.add_argument('--workers', type=int, default=12)
    parser.add_argument('--particles', type=int, default=DEFAULT_PARTICLES)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    from problem3.probability_scenarios import SPLITS
    count = args.count or SPLITS[args.split][1]
    output = args.output or ROOT/'validation/probability_stop'/f'p{args.problem}_{args.split}.json'
    if not output.is_absolute():
        output = ROOT/output
    traces = output.with_suffix('.jsonl.gz')
    if output.exists() or traces.exists():
        parser.error('Refusing to overwrite existing experiment results')
    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    rows = []
    print(f'Collecting P{args.problem} {args.split}: {count} fresh cases', flush=True)
    with gzip.open(traces, 'wt', encoding='utf-8') as stream:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(worker, (args.problem, args.split, index, args.particles))
                       for index in range(count)]
            for future in as_completed(futures):
                row = future.result()
                stream.write(json.dumps(row, ensure_ascii=False, separators=(',', ':'))+'\n')
                # Full public traces are persisted separately; keep summary rows compact.
                row.pop('checkpoints')
                row.pop('no_signal_events', None)
                rows.append(row)
                if len(rows)%32 == 0 or len(rows) == count:
                    print(f'{len(rows)}/{count}; wall {time.perf_counter()-started:.1f}s', flush=True)
    rows.sort(key=lambda r:r['index'])
    branches = list(rows[0]['outcomes'])
    report = dict(provenance='self-built local cases; NOT official simulator results',
                  model_version=MODEL_VERSION, problem=args.problem, split=args.split,
                  count=count, particles=args.particles, thresholds=THRESHOLDS,
                  created_utc=datetime.now(timezone.utc).isoformat(),
                  elapsed_wall_s=time.perf_counter()-started,
                  source_lf_sha256=source_fingerprint(),
                  trace_file=str(traces.relative_to(ROOT)).replace('\\', '/'),
                  trace_sha256=hashlib.sha256(traces.read_bytes()).hexdigest(),
                  summary={b:summarize(rows, b) for b in branches},
                  by_family={family:{b:summarize([r for r in rows if r['family']==family], b)
                                     for b in branches}
                             for family in sorted(set(r['family'] for r in rows))},
                  episodes=rows)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report['summary'], ensure_ascii=False, indent=2), flush=True)
    print(f'Saved {output}', flush=True)


if __name__ == '__main__':
    main()

"""Checkpoint the current solve default on equal-sized local source-count groups.

No platform client or historical/teammate strategy is run. An evaluator-owned
simulator remains outside the isolated policy process. Stored episode metrics
include failures; average clear time is undefined exactly when Nc is zero.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import statistics
import subprocess
import sys
import threading
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.compare_teammate_p34 import Worker, episode
from problem3.balanced_datasets import SOURCE_COUNTS

PROVENANCE = 'self_constructed_not_official'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def source_fingerprint():
    """Freeze production packages and both ends of the public-reply evaluator."""
    paths = [p for problem in (3, 4)
             for p in (ROOT / f'problem{problem}').rglob('*.py')
             if not any(part in ('tests', 'examples', 'results', '__pycache__')
                        for part in p.relative_to(ROOT / f'problem{problem}').parts)]
    paths += [ROOT / 'scripts' / name for name in (
        'benchmark_search.py', 'compare_teammate_p34.py',
        'compare_teammate_p34_worker.py', 'balanced_search_worker.py',
        'benchmark_balanced_search.py')]
    return {p.relative_to(ROOT).as_posix(): sha256(p) for p in sorted(set(paths))}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def append_episode(path, row):
    content = json.dumps(row, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n'
    with Path(path).open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return content.encode('utf-8')


def read_episodes(path, *, recover_tail=False):
    """Only resume may remove a torn final JSONL write, never an interior line."""
    path = Path(path)
    if not path.exists():
        return []
    lines = path.read_bytes().splitlines(keepends=True)
    rows, valid_bytes = [], 0
    for index, line in enumerate(lines):
        try:
            row = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            if recover_tail and index == len(lines) - 1 and not line.endswith(b'\n'):
                with path.open('r+b') as stream:
                    stream.truncate(valid_bytes)
                break
            raise ValueError(f'Invalid episode JSON on line {index + 1}')
        if not isinstance(row, dict):
            raise ValueError(f'Invalid episode object on line {index + 1}')
        rows.append(row)
        valid_bytes += len(line)
    if recover_tail and rows and not lines[len(rows) - 1].endswith(b'\n') and path.stat().st_size == valid_bytes:
        with path.open('ab') as stream:
            stream.write(b'\n')
    return rows


def verify_checkpoint_prefix(run, path):
    """A crash may append new rows, but it cannot rewrite committed records."""
    lines = Path(path).read_bytes().splitlines(keepends=True)
    count = run['processed_cases']
    if type(count) is not int or count < 0 or count > len(lines):
        raise ValueError('Checkpoint episode count is invalid')
    digest = hashlib.sha256(b''.join(lines[:count])).hexdigest()
    if digest != run.get('episodes_sha256'):
        raise ValueError('Checkpoint episode fingerprint mismatch; committed rows changed')


class CurrentWorker(Worker):
    """Reuse Worker transport and evaluator episode; record public actions."""
    def __init__(self, problem):
        command = [sys.executable, '-I', '-B', '-u',
                   str(ROOT / 'scripts/balanced_search_worker.py'), str(ROOT), str(problem)]
        self.process = subprocess.Popen(
            command, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding='utf-8', bufsize=1,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.events, self.errors = queue.Queue(), []
        self.trace, self.pending_action = [], None

        def stdout():
            for line in self.process.stdout:
                self.events.put(line)
            self.events.put(None)

        def stderr():
            for line in self.process.stderr:
                self.errors.append(line.rstrip())

        threading.Thread(target=stdout, daemon=True).start()
        threading.Thread(target=stderr, daemon=True).start()
        try:
            self.ready = self.read()
            if self.ready.get('type') != 'ready':
                raise RuntimeError('Current solve worker failed to initialize')
        except BaseException:
            self.close()
            raise

    def read(self):
        message = super().read()
        if message.get('type') == 'action':
            self.pending_action = message
        return message

    def write(self, data):
        if data == {'type': 'run'}:
            self.trace, self.pending_action = [], None
        if 'response' in data and self.pending_action:
            action = self.pending_action
            if action['path'] in ('/measure', '/clear'):
                payload = action['payload']
                self.trace.append({'action': action['path'].lstrip('/'),
                                   'position': [payload['position']['x'], payload['position']['y']],
                                   'channel': payload['channel'], 'response': data['response']})
            self.pending_action = None
        super().write(data)

    def close(self):
        if self.process.poll() is None:
            try:
                super().close()
            except (BrokenPipeError, OSError):
                self.process.kill()
                self.process.wait()
        for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
            if pipe:
                pipe.close()


def select_cases(cases, limit_per_count=None):
    if limit_per_count is not None and limit_per_count < 1:
        raise ValueError('--limit-per-count must be positive')
    available = Counter(case['source_count'] for case in cases)
    if set(available) != set(SOURCE_COUNTS) or len(set(available.values())) != 1:
        raise ValueError('Dataset must have equal numbers of cases at every source count 10..16')
    if limit_per_count is not None and limit_per_count > min(available.values()):
        raise ValueError('--limit-per-count exceeds the dataset')
    seen, selected = Counter(), []
    for case in cases:
        count = case['source_count']
        if limit_per_count is None or seen[count] < limit_per_count:
            selected.append(case)
            seen[count] += 1
    return selected


def summarize_group(rows):
    averages = [r['average_clear_time_s'] for r in rows
                if r['average_clear_time_s'] is not None]
    values = sorted(averages)
    count = len(rows)
    return {
        'case_count': count,
        'mean_cleared_fraction': statistics.mean(r['cleared_fraction'] for r in rows) if rows else None,
        'mean_average_clear_time_s': statistics.mean(averages) if averages else None,
        'median_average_clear_time_s': statistics.median(averages) if averages else None,
        'p90_average_clear_time_s': values[math.ceil(.9 * len(values)) - 1] if values else None,
        'defined_average_clear_time_cases': len(averages),
        'undefined_average_clear_time_cases': count - len(averages),
        'all_cleared_cases': sum(bool(r['source_truth_all_cleared']) for r in rows),
        'certified_complete_cases': sum(bool(r['certified_full_clear']) for r in rows),
        'error_cases': sum(bool(r['error']) for r in rows),
        'zero_clear_cases': sum(r['cleared_count'] == 0 for r in rows),
        'total_sources': sum(r['source_count'] for r in rows),
        'total_cleared': sum(r['cleared_count'] for r in rows),
        'failure_case_ids': [r['case_id'] for r in rows if not r['certified_full_clear']],
        'mean_virtual_time_s': statistics.mean(r['virtual_time_s'] for r in rows) if rows else None,
        'policy_cpu_total_s': sum(r['policy_cpu_s'] for r in rows),
    }


def build_summary(run, rows):
    return {
        'schema_version': 1, 'problem': run['problem'], 'run_id': run['run_id'],
        'algorithm_version': run['algorithm_version'], 'provenance': PROVENANCE,
        'dataset_sha256': run['dataset_sha256'], 'complete': run['complete'],
        'is_subset': run['is_subset'], 'expected_cases': run['expected_cases'],
        'processed_cases': len(rows),
        'metric_definitions': {
            'cleared_fraction': 'Nc/N',
            'average_clear_time_s': 'actual total local virtual time/Nc; null if Nc=0',
            'aggregation': 'arithmetic mean of per-case metrics; undefined time cases explicitly counted',
            'time_includes': 'movement, measure, channel switching, all clears and completion search',
        },
        'overall': summarize_group(rows),
        'by_source_count': {str(n): summarize_group([r for r in rows if r['source_count'] == n])
                            for n in SOURCE_COUNTS},
    }


def checkpoint(directory, run, rows, *, update_summary=True):
    run['processed_cases'] = len(rows)
    run['updated_utc'] = utc_now()
    if 'episodes_sha256' not in run:
        run['episodes_sha256'] = sha256(directory / 'episodes.jsonl')
    write_json(directory / 'run.json', run)
    if not update_summary:
        return
    summary = build_summary(run, rows)
    write_json(directory / 'summary.json', summary)
    def value(number, digits=3):
        return '无定义' if number is None else f'{number:.{digits}f}'
    lines = [f"# 问题{run['problem']}：当前 solve 本地均衡样例结果", '',
             f"版本：`{run['algorithm_version']}`；已记录 {len(rows)}/{run['expected_cases']} 例。",
             '本地自建结果，不是正式测试成绩。所有异常、未全清及零清除样例均保留。', '',
             '| 源数 | 样例数 | 平均清除比例 | 平均定位清除时间（秒/源） | 时间无定义 | 全清且证书通过 | 异常 |',
             '|---:|---:|---:|---:|---:|---:|---:|']
    for n, group in summary['by_source_count'].items():
        fraction = group['mean_cleared_fraction']
        lines.append(f"| {n} | {group['case_count']} | {value(None if fraction is None else fraction*100)}% | "
                     f"{value(group['mean_average_clear_time_s'])} | {group['undefined_average_clear_time_cases']} | "
                     f"{group['certified_complete_cases']} | {group['error_cases']} |")
    lines += ['', '先按每例计算清除比例 Nc/N 与总虚拟耗时/Nc，再在同一源数内等权平均。',
              'Nc=0 时平均定位清除时间记 null；有定义的失败样例仍参与时间统计，并单列异常与全清情况。',
              '全清核验同时检查公开动作覆盖证书、策略声明、正常退出和事后源真值。',
              '恢复同一批次要求数据与代码指纹一致；代码修改后必须使用新的运行编号。']
    (directory / 'summary.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def validate_rows(run, rows, selected_cases):
    expected = {case['case_id']: case for case in selected_cases}
    seen = set()
    for row in rows:
        case_id = row.get('case_id')
        if case_id in seen or case_id not in expected:
            raise ValueError(f'Duplicate or unselected case: {case_id}')
        seen.add(case_id)
        case = expected[case_id]
        expected_hash = hashlib.sha256(json.dumps(case, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if row.get('case_sha256') != expected_hash:
            raise ValueError(f'Case fingerprint mismatch: {case_id}')
        if row.get('problem') != run['problem'] or row.get('source_count') != case['source_count']:
            raise ValueError(f'Problem/source count mismatch: {case_id}')
        if row.get('algorithm_version') != run['algorithm_version']:
            raise ValueError(f'Mixed algorithm versions: {case_id}')
        n, cleared = row['source_count'], row['cleared_count']
        if type(cleared) is not int or not 0 <= cleared <= n:
            raise ValueError(f'Invalid clearance count: {case_id}')
        elapsed = row['virtual_time_s']
        if not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError(f'Invalid virtual time: {case_id}')
        average = row['average_clear_time_s']
        if ((cleared == 0 and average is not None) or
                (cleared > 0 and (average is None or not math.isclose(average, elapsed / cleared, abs_tol=1e-7)))):
            raise ValueError(f'Invalid average clear time: {case_id}')
        if not math.isclose(row['cleared_fraction'], cleared / n, abs_tol=1e-12):
            raise ValueError(f'Invalid cleared fraction: {case_id}')
    return seen


def _dataset(problem, directory=None):
    from problem3.balanced_datasets import dataset_directory, load_cases
    # Persisted legacy run paths are absolute. Explicit relative runner paths
    # retain their repository-relative meaning; the default comes from gateway.
    if directory is None:
        directory = dataset_directory(problem)
    else:
        directory = Path(directory)
        if not directory.is_absolute():
            directory = ROOT / directory
        directory = dataset_directory(problem, directory)
    cases = load_cases(problem, directory)
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    return directory, manifest, cases


def load_run(directory, *, allow_partial=False):
    """Validate a stored run for plotting; current code may differ from old runs."""
    directory = Path(directory)
    if not directory.is_absolute():
        directory = ROOT / directory
    run = json.loads((directory / 'run.json').read_text(encoding='utf-8'))
    dataset_dir, manifest, cases = _dataset(run['problem'], run['dataset_path'])
    if (manifest['cases_sha256'] != run['dataset_sha256'] or
            sha256(dataset_dir / 'manifest.json') != run['dataset_manifest_sha256']):
        raise ValueError('Dataset fingerprint differs from the stored run')
    if run['dataset_version'] != manifest['dataset']:
        raise ValueError('Dataset version differs from the stored run')
    if not run.get('source_sha256') or run.get('strategy') != 'adaptive':
        raise ValueError('Missing frozen source fingerprint or unexpected strategy')
    rows = read_episodes(directory / 'episodes.jsonl')
    selected = select_cases(cases, run['limit_per_count'])
    validate_rows(run, rows, selected)
    if len(selected) != run['expected_cases'] or len(rows) != run['processed_cases']:
        raise ValueError('Run case counts disagree with stored episodes')
    counts = {str(n): sum(c['source_count'] == n for c in selected) for n in SOURCE_COUNTS}
    if counts != run['counts_by_source_count'] or run['is_subset'] != (len(selected) != len(cases)):
        raise ValueError('Run balance/subset metadata disagrees with the selected dataset')
    if run['complete'] and (run['status'] != 'complete' or len(rows) != len(selected)):
        raise ValueError('Run completion flag disagrees with episode coverage')
    if rows and sha256(directory / 'episodes.jsonl') != run.get('episodes_sha256'):
        raise ValueError('Episode file fingerprint differs from the checkpoint')
    if not allow_partial and (not run['complete'] or run['status'] != 'complete' or len(rows) != len(selected)):
        raise ValueError('Incomplete run; explicitly allow partial previews or finish the batch first')
    summary = build_summary(run, rows)
    saved_summary = json.loads((directory / 'summary.json').read_text(encoding='utf-8'))
    if saved_summary != summary:
        raise ValueError('Summary differs from the stored episode records')
    return run, rows, summary


def run_problem(problem, *, run_id, limit_per_count=None, resume=False,
                dataset_dir=None, output_root=None, worker_factory=CurrentWorker,
                evaluate=episode, fingerprint=source_fingerprint):
    """Execute sequentially, persisting each complete evaluator episode immediately."""
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}', run_id):
        raise ValueError('run-id must use 1..96 letters, digits, underscore, dot or hyphen')
    dataset_dir, manifest, cases = _dataset(problem, dataset_dir)
    selected = select_cases(cases, limit_per_count)
    output_root = Path(output_root) if output_root else ROOT / f'problem{problem}/results/balanced'
    if not output_root.is_absolute():
        output_root = ROOT / output_root
    directory = output_root / run_id
    if directory.exists() and not resume:
        raise FileExistsError('Run already exists; use --resume or choose a new run-id')
    if resume and not (directory / 'run.json').exists():
        raise FileNotFoundError('Cannot resume: run.json is missing')
    from scripts.benchmark_search import get_algorithm_version
    version = get_algorithm_version(problem, 'adaptive')
    sources = fingerprint()
    identity = {'problem': problem, 'dataset_version': manifest['dataset'],
                'dataset_sha256': manifest['cases_sha256'],
                'dataset_manifest_sha256': sha256(dataset_dir / 'manifest.json'),
                'algorithm_version': version, 'source_sha256': sources,
                'limit_per_count': limit_per_count, 'expected_cases': len(selected)}
    if resume:
        run = json.loads((directory / 'run.json').read_text(encoding='utf-8'))
        for key, value in identity.items():
            if run.get(key) != value:
                raise ValueError(f'Cannot resume: {key} mismatch; use a new run-id')
        verify_checkpoint_prefix(run, directory / 'episodes.jsonl')
        rows = read_episodes(directory / 'episodes.jsonl', recover_tail=True)
        seen = validate_rows(run, rows, selected)
        if run['complete'] and len(rows) == len(selected):
            load_run(directory)
            return directory
    else:
        directory.mkdir(parents=True, exist_ok=False)
        (directory / 'episodes.jsonl').touch()
        run = {'schema_version': 1, 'run_id': run_id, **identity,
               'dataset_path': str(dataset_dir),
               'strategy': 'adaptive', 'provenance': PROVENANCE,
               'is_subset': len(selected) != len(cases), 'dataset_total_cases': len(cases),
               'counts_by_source_count': {str(n): sum(c['source_count'] == n for c in selected) for n in SOURCE_COUNTS},
               'created_utc': utc_now(), 'processed_cases': 0,
               'status': 'running', 'complete': False}
        rows, seen = [], set()
    run.update(status='running', complete=False)
    run.pop('error', None)
    episodes_digest = hashlib.sha256((directory / 'episodes.jsonl').read_bytes())
    run['episodes_sha256'] = episodes_digest.hexdigest()
    checkpoint(directory, run, rows)
    case_file = dataset_dir / manifest.get('cases_file', 'cases.jsonl')
    baseline_stats = (case_file.stat().st_mtime_ns, case_file.stat().st_size,
                      (dataset_dir / 'manifest.json').stat().st_mtime_ns)

    def unchanged():
        if fingerprint() != sources:
            run['status'] = 'source_changed'
            raise RuntimeError('Source code changed during this batch; use a new run-id')
        current_stats = (case_file.stat().st_mtime_ns, case_file.stat().st_size,
                         (dataset_dir / 'manifest.json').stat().st_mtime_ns)
        if current_stats != baseline_stats and (sha256(case_file) != run['dataset_sha256'] or
                sha256(dataset_dir / 'manifest.json') != run['dataset_manifest_sha256']):
            run['status'] = 'dataset_changed'
            raise RuntimeError('Dataset changed during this batch; use a new run-id')

    worker, cache = None, {}
    first_ids = {n: next(c['case_id'] for c in selected if c['source_count'] == n) for n in SOURCE_COUNTS}
    try:
        unchanged()
        worker = worker_factory(problem)
        if worker.ready['algorithm_version'] != version:
            raise RuntimeError('Worker version differs from the frozen solve default')
        run['worker_metadata'] = worker.ready
        unchanged()
        for case in selected:
            if case['case_id'] in seen:
                continue
            unchanged()
            run['active_case_id'] = case['case_id']
            row = evaluate(worker, case, problem, cache)
            unchanged()
            row.update(problem=problem, algorithm_version=version, provenance=PROVENANCE)
            validate_rows(run, [row], [case])
            if case['case_id'] == first_ids[case['source_count']]:
                trace_dir = directory / 'trace_samples' / f"n{case['source_count']}"
                write_json(trace_dir / 'case.json', case)
                write_json(trace_dir / 'result.json', row)
                with (trace_dir / 'events.jsonl').open('w', encoding='utf-8', newline='\n') as stream:
                    for event in worker.trace:
                        stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + '\n')
            episodes_digest.update(append_episode(directory / 'episodes.jsonl', row))
            run['episodes_sha256'] = episodes_digest.hexdigest()
            rows.append(row)
            seen.add(case['case_id'])
            run.pop('active_case_id', None)
            checkpoint(directory, run, rows, update_summary=len(rows) % 25 == 0)
            print(f"问题{problem} {len(rows)}/{len(selected)} 源数={case['source_count']} "
                  f"清除={row['cleared_count']}/{row['source_count']}", flush=True)
        unchanged()
        run.update(status='complete', complete=True)
    except KeyboardInterrupt:
        run.update(status='interrupted', error='KeyboardInterrupt')
        raise
    except BaseException as exc:
        if run['status'] == 'running':
            run['status'] = 'error'
        run['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        if worker:
            if worker.errors:
                (directory / 'worker_stderr.log').write_text('\n'.join(worker.errors) + '\n', encoding='utf-8')
            worker.close()
        checkpoint(directory, run, rows)
    return directory


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--problem', choices=('3', '4', 'all'), default='all')
    parser.add_argument('--run-id', help='New output name; defaults to a unique UTC timestamp')
    parser.add_argument('--limit-per-count', type=int, help='Balanced smoke subset; e.g. 2 means 14 cases per problem')
    parser.add_argument('--resume', action='store_true', help='Continue the same run only when code and dataset match')
    args = parser.parse_args()
    if args.resume and not args.run_id:
        parser.error('--resume requires --run-id')
    run_id = args.run_id or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8]
    problems = (3, 4) if args.problem == 'all' else (int(args.problem),)
    for problem in problems:
        directory = run_problem(problem, run_id=run_id, limit_per_count=args.limit_per_count, resume=args.resume)
        print(directory, flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Persistence and failure accounting for the future current-solve batch."""
from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from problem3 import balanced_scenarios as legacy_scenarios
from problem3.balanced_datasets import DATASET, prepare_dataset
from scripts import benchmark_balanced_search as runner
from scripts.benchmark_search import get_algorithm_version


class FakeWorker:
    def __init__(self, problem):
        self.ready = {'type': 'ready', 'algorithm_version': get_algorithm_version(problem, 'adaptive')}
        self.trace, self.errors = [], []

    def close(self):
        pass


def result_for_case(worker, case, problem, cache):
    n = case['source_count']
    cleared = 0 if n == 10 else n - 1 if n == 11 else n
    elapsed = 12.0 * n
    return {'case_id': case['case_id'],
            'case_sha256': hashlib.sha256(json.dumps(case, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
            'source_count': n, 'cleared_count': cleared,
            'cleared_fraction': cleared / n, 'virtual_time_s': elapsed,
            'average_clear_time_s': elapsed / cleared if cleared else None,
            'source_truth_all_cleared': cleared == n,
            'certified_full_clear': cleared == n,
            'error': 'synthetic test policy error' if n == 10 else None,
            'policy_cpu_s': .01}


class BalancedRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.dataset = self.base / 'dataset'
        prepare_dataset(3, 1, self.dataset)
        self.options = dict(run_id='test', dataset_dir=self.dataset,
                            output_root=self.base / 'output', worker_factory=FakeWorker,
                            evaluate=result_for_case,
                            fingerprint=lambda: {'production.py': 'frozen-test-code'})

    def tearDown(self):
        self.temporary.cleanup()

    def run_batch(self, **overrides):
        options = dict(self.options, **overrides)
        with redirect_stdout(io.StringIO()):
            return runner.run_problem(3, **options)

    def interrupted_batch(self):
        calls = []

        def interrupt(worker, case, problem, cache):
            calls.append(case['case_id'])
            if len(calls) == 3:
                raise KeyboardInterrupt()
            return result_for_case(worker, case, problem, cache)

        with self.assertRaises(KeyboardInterrupt):
            self.run_batch(evaluate=interrupt)
        return self.base / 'output/test', calls[:2]

    def test_failures_and_undefined_metrics_are_preserved(self):
        directory = self.run_batch()
        run, rows, summary = runner.load_run(directory)
        self.assertTrue(run['complete'])
        self.assertEqual(run['dataset_version'], DATASET)
        self.assertEqual(len(rows), 7)
        self.assertEqual(summary['overall']['case_count'], 7)
        self.assertEqual(summary['overall']['certified_complete_cases'], 5)
        self.assertEqual(summary['overall']['error_cases'], 1)
        self.assertEqual(summary['overall']['undefined_average_clear_time_cases'], 1)
        self.assertIsNone(summary['by_source_count']['10']['mean_average_clear_time_s'])
        self.assertAlmostEqual(summary['by_source_count']['11']['mean_average_clear_time_s'], 13.2)
        self.assertTrue((directory / 'trace_samples/n16/case.json').exists())
        with self.assertRaises(FileExistsError):
            self.run_batch()

    def test_resume_skips_completed_rows_and_rejects_changed_code(self):
        directory, completed = self.interrupted_batch()
        run, rows, summary = runner.load_run(directory, allow_partial=True)
        self.assertEqual(run['status'], 'interrupted')
        self.assertEqual(len(rows), 2)
        with self.assertRaisesRegex(ValueError, 'source_sha256 mismatch'):
            self.run_batch(resume=True, fingerprint=lambda: {'production.py': 'different-code'})
        resumed = []

        def evaluate(worker, case, problem, cache):
            resumed.append(case['case_id'])
            return result_for_case(worker, case, problem, cache)

        self.run_batch(resume=True, evaluate=evaluate)
        self.assertEqual(len(resumed), 5)
        self.assertTrue(set(completed).isdisjoint(resumed))
        self.assertEqual(len(runner.load_run(directory)[1]), 7)

    def test_resume_rejects_changed_committed_metrics(self):
        directory, _ = self.interrupted_batch()
        path = directory / 'episodes.jsonl'
        rows = runner.read_episodes(path)
        rows[1]['virtual_time_s'] *= 2
        rows[1]['average_clear_time_s'] *= 2
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'fingerprint mismatch'):
            self.run_batch(resume=True)

    def test_resume_removes_only_a_torn_uncommitted_final_line(self):
        directory, _ = self.interrupted_batch()
        path = directory / 'episodes.jsonl'
        with path.open('ab') as stream:
            stream.write(b'{"case_id":"unfinished')
        self.run_batch(resume=True)
        self.assertEqual(len(runner.load_run(directory)[1]), 7)

    def test_code_change_during_episode_is_not_mixed_into_run(self):
        changed = [False]

        def evaluate(worker, case, problem, cache):
            changed[0] = True
            return result_for_case(worker, case, problem, cache)

        with self.assertRaisesRegex(RuntimeError, 'Source code changed'):
            self.run_batch(evaluate=evaluate,
                           fingerprint=lambda: {'production.py': 'new' if changed[0] else 'old'})
        directory = self.base / 'output/test'
        run = json.loads((directory / 'run.json').read_text(encoding='utf-8'))
        self.assertEqual(run['status'], 'source_changed')
        self.assertEqual(runner.read_episodes(directory / 'episodes.jsonl'), [])

    def test_selection_rejects_unbalanced_groups(self):
        cases = [{'source_count': n} for n in range(10, 17)]
        self.assertEqual(len(runner.select_cases(cases, 1)), 7)
        with self.assertRaisesRegex(ValueError, 'equal numbers'):
            runner.select_cases(cases + [{'source_count': 10}])
        with self.assertRaises(ValueError):
            runner.select_cases(cases, 2)

    def test_explicit_legacy_dataset_remains_readable_without_installed_v1(self):
        legacy = self.base / 'legacy'
        legacy_scenarios.prepare_dataset(3, 1, legacy)
        directory = self.run_batch(dataset_dir=legacy)
        run, rows, _ = runner.load_run(directory)
        self.assertEqual(run['dataset_version'], legacy_scenarios.DATASET)
        self.assertEqual(len(rows), 7)
        self.assertNotIn('construction_difficulty', json.loads(
            (directory / 'trace_samples/n10/case.json').read_text(encoding='utf-8')))

    def test_current_policy_receives_only_public_responses_for_new_case(self):
        _, _, cases = runner._dataset(3, self.dataset)
        case = cases[0]
        self.assertIn('construction_difficulty', case)

        class AuditedWorker(runner.CurrentWorker):
            def __init__(self, problem):
                self.sent = []
                super().__init__(problem)

            def write(self, data):
                self.sent.append(data)
                super().write(data)

        worker = AuditedWorker(3)
        try:
            result = runner.episode(worker, case, 3, {})
            self.assertEqual(result['case_id'], case['case_id'])
            self.assertEqual(result['source_count'], case['source_count'])
            self.assertEqual(worker.ready['algorithm_version'], get_algorithm_version(3, 'adaptive'))
            self.assertEqual(worker.sent[0], {'type': 'run'})
            for message in worker.sent[1:]:
                self.assertEqual(set(message), {'response', 'public_state'})
            wire = json.dumps(worker.sent)
            for private_name in ('case_id', 'seed', 'source_count', 'sources', 'construction_difficulty'):
                self.assertNotIn(f'"{private_name}"', wire)
        finally:
            worker.close()


if __name__ == '__main__':
    unittest.main()

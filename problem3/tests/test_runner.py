"""Local/online runner integration and failure-reporting boundaries."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from problem3 import run
from problem3.client import BudgetExceeded, TransportError
from problem3.scenarios import generate_case
from problem3.simulator import LocalSimulator
from scripts import benchmark_search


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.destination = Path(self.directory.name)

    def online(self, *, failure=None, enter_accepted=True, exit_accepted=True,
               pending=None, can_exit=True):
        client = Mock()
        client.virtual_time_s = 0.0
        client.pending_request = None
        client.can_exit = can_exit
        client.enter.return_value = dict(accepted=enter_accepted, remaining_real_duration_s=37)
        client.exit.return_value = dict(accepted=exit_accepted, exit_reason='user_exit')
        policy = Mock()
        policy.cleared = set()

        def policy_run(observations):
            self.assertIs(observations, client)
            client.virtual_time_s = 46.25
            client.pending_request = pending
            policy.cleared.add(7)
            if failure:
                raise failure
            return dict(completion_certified=True, coverage_complete=True)

        policy.run.side_effect = policy_run
        args = ['solve.py', '--online', '--robot-id', 'test-team', '--output-dir', str(self.destination)]
        with patch.object(sys, 'argv', args), patch('problem3.client.HttpClient', return_value=client), \
                patch.object(benchmark_search, 'get_policy', return_value=policy), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = run.main(3)
        files = list((self.destination/'online').glob('*_summary.json'))
        self.assertEqual(len(files), 1)
        return code, json.loads(files[0].read_text(encoding='utf-8')), client, policy

    def test_success_keeps_platform_truth_and_runtime_unknown(self):
        code, result, client, _ = self.online()
        self.assertEqual(code, 0)
        self.assertTrue(result['statistics_final'])
        self.assertEqual(result['cleared_count'], 1)
        self.assertEqual(result['average_clear_time_s'], 46.25)
        self.assertIsNone(result['source_count'])
        self.assertIsNone(result['cleared_fraction'])
        self.assertIsNone(result['platform_program_runtime_s'])
        self.assertIsNone(result['platform_case_code'])
        self.assertEqual(result['algorithm_version'], 'problem3_v5_continuous')
        self.assertEqual(result['policy']['algorithm_version'], 'problem3_v5_continuous')
        client.exit.assert_called_once()

    def test_unknown_outcome_does_not_exit_or_publish_final_average(self):
        code, result, client, _ = self.online(failure=TransportError('lost response'),
                                             pending={'request_id': 'measure-uncertain'}, can_exit=False)
        self.assertEqual(code, 1)
        client.exit.assert_not_called()
        self.assertFalse(result['statistics_final'])
        self.assertIsNone(result['average_clear_time_s'])
        self.assertEqual(result['observed_average_clear_time_s'], 46.25)
        self.assertEqual(result['pending_request_id'], 'measure-uncertain')
        self.assertEqual(result['algorithm_version'], 'problem3_v5_continuous')
        self.assertEqual(result['policy']['algorithm_version'], 'problem3_v5_continuous')

    def test_budget_uses_exit_reserve_when_exit_is_safe(self):
        code, result, client, _ = self.online(failure=BudgetExceeded('reserve reached'))
        self.assertEqual(code, 1)
        client.exit.assert_called_once()
        self.assertTrue(result['statistics_final'])
        self.assertTrue(result['exit_accepted'])
        self.assertIn('reserve reached', result['error'])

    def test_rejected_enter_does_not_run_policy_or_probe_exit(self):
        code, result, client, policy = self.online(enter_accepted=False)
        self.assertEqual(code, 1)
        self.assertFalse(result['entered'])
        self.assertEqual(result['cleared_count'], 0)
        policy.run.assert_not_called()
        client.exit.assert_not_called()

    def test_rejected_exit_is_not_reissued_as_a_new_request(self):
        code, result, client, _ = self.online(exit_accepted=False)
        self.assertEqual(code, 1)
        self.assertFalse(result['statistics_final'])
        self.assertIsNone(result['average_clear_time_s'])
        client.exit.assert_called_once()

    def test_relative_local_paths_are_based_on_problem_directory_from_outside(self):
        root = self.destination/'repository'
        problem = root/'problem3'
        examples = problem/'examples'
        examples.mkdir(parents=True)
        case = generate_case(3)
        (examples/'case.json').write_text(json.dumps(case), encoding='utf-8')
        row = dict(cleared_count=0, source_count=10, virtual_time_s=10.0,
                   average_clear_time_s=None, completion_certified=False,
                   certified_full_clear=False, error='injected failure')
        output = io.StringIO()
        original = Path.cwd()
        try:
            os.chdir(self.destination)
            with patch.object(sys, 'argv', ['solve.py', '--case', 'examples/case.json',
                                           '--output-dir', 'results/check']), \
                    patch.object(run, 'ROOT', root), \
                    patch.object(benchmark_search, 'run_case', return_value=(row, [])) as local_run, \
                    patch('problem3.client.HttpClient', side_effect=AssertionError('Local mode contacted network')), \
                    contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(run.main(3), 1)
        finally:
            os.chdir(original)
        self.assertEqual(local_run.call_args.args[0]['case_id'], case['case_id'])
        self.assertTrue((problem/'results/check/demo_result.json').exists())
        saved = json.loads((problem/'results/check/demo_result.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['algorithm_version'], 'problem3_v5_continuous')
        self.assertEqual(saved['policy']['algorithm_version'], 'problem3_v5_continuous')
        self.assertTrue((problem/'results/check/demo_route.svg').exists())
        self.assertFalse((self.destination/'results').exists())
        self.assertIn('无定义', output.getvalue())
        self.assertIn('algorithm_version=problem3_v5_continuous', output.getvalue())

    def test_version_display_is_read_only_and_never_enters_arena(self):
        for problem, strategy, version in ((3, 'adaptive', 'problem3_v5_continuous'),
                                           (3, 'previous', 'problem3_v1'),
                                           (4, 'adaptive', 'problem4_v5_visibility_discovery'),
                                           (4, 'previous', 'problem4_v2'),
                                           (4, 'legacy', 'problem4_v1')):
            destination = self.destination/f'p{problem}_{strategy}'
            output = io.StringIO()
            with self.subTest(problem=problem, strategy=strategy), \
                    patch.object(sys, 'argv', ['solve.py', '--version', '--online',
                                              '--strategy', strategy, '--output-dir', str(destination)]), \
                    patch('problem3.client.HttpClient', side_effect=AssertionError('Version display contacted network')), \
                    patch.object(benchmark_search, 'run_case', side_effect=AssertionError('Version display ran a case')), \
                    contextlib.redirect_stdout(output):
                self.assertEqual(run.main(problem), 0)
            self.assertIn('algorithm_version='+version, output.getvalue())
            self.assertFalse(destination.exists())

    def test_previous_alias_replays_original_policies(self):
        from problem3.policy import SearchPolicy as Previous3
        from problem3.simulator import ObservationClient
        from problem4.policy import SearchPolicy as Previous4
        for problem, policy_class, version in ((3, Previous3, 'problem3_v1'),
                                               (4, Previous4, 'problem4_v2')):
            case = generate_case(problem, 2, 'development_v3')
            row, events = benchmark_search.run_case(case, 'previous', record=True)
            sim = LocalSimulator(case, record=True)
            sim.enter()
            policy_class(problem=problem, strategy='adaptive').run(ObservationClient(sim))
            sim.exit()

            def physical_trace(trace):
                return [(event['action'], event['position'], event['channel'],
                         {k: v for k, v in event['response'].items() if k != 'real_timestamp_ms'})
                        for event in trace]

            with self.subTest(problem=problem):
                self.assertIsNone(row['error'])
                self.assertEqual(row['algorithm_version'], version)
                self.assertEqual(row['policy']['algorithm_version'], version)
                self.assertEqual(physical_trace(events), physical_trace(sim.events))

    def test_fingerprint_covers_production_modules_and_thresholds(self):
        fingerprints = benchmark_search.source_fingerprint()
        for problem in (3, 4):
            for path in (benchmark_search.ROOT/f'problem{problem}').glob('*.py'):
                self.assertIn(path.relative_to(benchmark_search.ROOT).as_posix(), fingerprints)
        self.assertFalse(any('/experiments' in name for name in fingerprints))
        self.assertEqual(benchmark_search.THRESHOLDS, {3: 220.0, 4: 400.0})

    def test_solver_wrappers_import_from_outside_repository(self):
        for problem in (3, 4):
            process = subprocess.run([sys.executable, str(run.ROOT/f'problem{problem}/solve.py'), '--help'],
                                     cwd=self.destination, capture_output=True, timeout=15)
            self.assertEqual(process.returncode, 0, process.stderr.decode('utf-8', errors='replace'))
            self.assertIn(b'--online', process.stdout)

    def test_total_failure_is_retained_in_aggregate(self):
        case = generate_case(3)
        with patch.object(benchmark_search, 'get_policy', side_effect=RuntimeError('injected failure')):
            row, _ = benchmark_search.run_case(case)
        summary = benchmark_search.aggregate([row])
        self.assertEqual(summary['all_clear_cases'], 0)
        self.assertEqual(summary['missed_sources'], len(case['sources']))
        self.assertIsNone(summary['mean_average_clear_time_s'])
        self.assertEqual(summary['failures'], [case['case_id']])
        self.assertEqual(summary['threshold_pass_rate'], 0)
        self.assertLess(summary['mean_reward'], -1000000)

    def test_nonfinite_orientation_is_rejected_as_bad_case(self):
        for invalid in (float('nan'), float('inf'), True, 'east'):
            case = generate_case(4)
            case['sources'][0]['orientation_deg'] = invalid
            with self.assertRaises(ValueError):
                LocalSimulator(case)


if __name__ == '__main__':
    unittest.main()

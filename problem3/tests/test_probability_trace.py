"""Collector boundaries, temporal information and unchanged physical actions."""
import json
import unittest
from importlib.util import find_spec

from problem3.probability_trace import TracedProblem3Policy, TracedProblem4Policy, capture_case
from problem3.scenarios import generate_case
from problem3.simulator import LocalSimulator, ObservationClient
from problem3.speed_policy import SearchPolicy as P3
from problem4.speed_policy import SearchPolicy as P4


def origin_case(problem, count=10):
    return {'problem': problem, 'case_id': f'trace_origin_{problem}_{count}',
            'seed': 914, 'sources': [dict(channel=ch, x=0., y=0., radius=1000.,
                                         orientation_deg=180. if problem == 4 else None)
                                    for ch in range(1, count + 1)]}


class ProbabilityTraceTests(unittest.TestCase):
    def test_physical_trajectories_unchanged_in_both_production_mros(self):
        for problem, base, traced in ((3, P3, TracedProblem3Policy),
                                      (4, P4, TracedProblem4Policy)):
            case = generate_case(problem, 0, 'development_v3')
            outcomes = []
            for cls in (base, traced):
                simulator = LocalSimulator(case, record=True)
                simulator.enter()
                policy = cls()
                result = policy.run(ObservationClient(simulator))
                simulator.exit()
                # Wall timestamps naturally differ; accepted physical actions,
                # readouts and all virtual timings must be exactly identical.
                for event in simulator.events:
                    event['response'].pop('real_timestamp_ms')
                outcomes.append((result, simulator.statistics(), simulator.events))
            self.assertEqual(outcomes[0], outcomes[1], problem)

    def test_tenth_near_clear_is_not_a_mid_scan_checkpoint(self):
        for problem in (3, 4):
            captured = capture_case(origin_case(problem))
            self.assertIsNone(captured['error'])
            first = captured['checkpoints'][0]['public']
            # All ten sources are cleared by t=109, but channels 11..20 still
            # have to be measured before the first legal scan boundary t=169.
            self.assertEqual(first['time_s'], 169.)
            self.assertEqual(first['counts']['measure'], 20)
            self.assertEqual(first['scans'][0]['unknown_channels'], list(range(1, 21)))
            self.assertEqual(first['scans'][0]['measured_channels'], list(range(1, 21)))
            self.assertEqual(first['coverage_visited'], [[0., 0.]])
            self.assertEqual(set(first['no_signal_by_channel']), {str(ch) for ch in range(11, 21)})

    def test_snapshots_are_prefixes_and_final_upper_count_return_is_captured(self):
        captured = capture_case(origin_case(4))
        previous = -1.
        for checkpoint in captured['checkpoints']:
            public = checkpoint['public']
            self.assertGreaterEqual(public['time_s'], previous)
            previous = public['time_s']
            self.assertTrue(public['eligibility'])
            self.assertEqual(public['detected_channels'], public['cleared_channels'])
            expected = {}
            for event in captured['no_signal_events']:
                if event['time_s'] <= public['time_s']:
                    expected.setdefault(str(event['channel']), []).append(event['position'])
            self.assertEqual(public['no_signal_by_channel'], expected)
            self.assertEqual(len(public['coverage_visited']), len(public['scans']))
        self.assertEqual(len(captured['checkpoints'][0]['public']['no_signal_by_channel']['11']), 1)
        self.assertGreater(len(captured['checkpoints'][-1]['public']['no_signal_by_channel']['11']), 1)
        self.assertEqual(captured, json.loads(json.dumps(captured)))
        for name in ('measure', 'clear', 'failed_clear', 'switch', 'no_signal', 'actions'):
            self.assertEqual(captured['checkpoints'][-1]['public']['counts'][name],
                             captured['baseline_statistics'][name])
        sixteen = capture_case(origin_case(3, 16))
        final = sixteen['checkpoints'][-1]
        self.assertTrue(final['public']['final_safe'])
        self.assertEqual(final['public']['boundary'], 'final')
        self.assertTrue(final['truth']['all_cleared'])
        self.assertFalse(final['public']['coverage_complete'])
        self.assertEqual(final['public']['time_s'], sixteen['baseline_statistics']['virtual_time_s'])

    def test_budget_failure_does_not_invent_a_safe_final_checkpoint(self):
        captured = capture_case(origin_case(3), action_limit=21)
        self.assertIsNotNone(captured['error'])
        self.assertIsNone(captured['final_safe_index'])
        self.assertEqual(captured['checkpoints'], [])

    def test_identical_public_prefix_can_have_different_external_truth(self):
        ten = origin_case(3)
        eleven = origin_case(3)
        eleven['sources'].append(dict(channel=11, x=1700., y=0., radius=1000.,
                                      orientation_deg=None))
        a = capture_case(ten)['checkpoints'][0]
        b = capture_case(eleven)['checkpoints'][0]
        self.assertEqual(a['public'], b['public'])
        self.assertTrue(a['truth']['all_cleared'])
        self.assertFalse(b['truth']['all_cleared'])
        self.assertEqual(b['truth']['remaining_count'], 1)


@unittest.skipUnless(find_spec('numpy'), 'Optional probability experiment requires NumPy')
class ProbabilityReplayTests(unittest.TestCase):
    """A stop-only counterfactual must equal the actual physical action prefix."""

    particles = 8192

    def assert_replay(self, case, evaluated, mode, threshold, expected_exit):
        from problem3.probability_stop import make_policy

        expected = evaluated['outcomes'][f'{mode}_{threshold:g}']
        self.assertEqual(expected['probability_exit'], expected_exit)
        simulator = LocalSimulator(case)
        simulator.enter()
        policy = make_policy(case['problem'], probability_mode=mode,
                             threshold=threshold, particles=self.particles)
        result = policy.run(ObservationClient(simulator))
        simulator.exit()
        actual = simulator.statistics()
        self.assertAlmostEqual(actual['virtual_time_s'], expected['virtual_time_s'], places=9)
        self.assertAlmostEqual(actual['average_clear_time_s'],
                               expected['average_clear_time_s'], places=9)
        self.assertEqual(actual['cleared_count'], expected['cleared_count'])
        self.assertEqual(actual['source_count'] - actual['cleared_count'],
                         expected['remaining_count'])
        self.assertEqual(result['completion_certified'], expected['completion_certified'])
        self.assertEqual(result['termination_reason'] == 'experimental_probability_threshold',
                         expected_exit)
        if expected_exit:
            chosen = evaluated['checkpoints'][expected['checkpoint_index']]
            public = chosen['public']
            self.assertEqual(list(simulator.position), public['position'])
            self.assertEqual(simulator.current_channel, public['current_channel'])
            for name in ('measure', 'clear', 'failed_clear', 'switch', 'no_signal', 'actions'):
                self.assertEqual(actual[name], public['counts'][name])
            self.assertFalse(public['final_safe'])
            self.assertTrue(public['eligibility'])
            self.assertEqual(public['detected_channels'], public['cleared_channels'])
            self.assertGreaterEqual(chosen['estimate'][mode], threshold)
            for earlier in evaluated['checkpoints'][:expected['checkpoint_index']]:
                if not earlier['public']['final_safe'] and earlier['estimate']['eligible']:
                    self.assertLess(earlier['estimate'][mode], threshold)
            self.assertLess(actual['virtual_time_s'],
                            evaluated['baseline_statistics']['virtual_time_s'])
        else:
            self.assertEqual(actual, evaluated['baseline_statistics'])
            self.assertTrue(result['completion_certified'])

    def test_first_crossing_and_safe_fallback_match_actual_runs(self):
        from scripts.benchmark_probability_stop import evaluate_trace

        # These are fixed OLD development examples, never new calibration or
        # holdout cases. P3 deliberately contains a false probability exit:
        # identical stopping decisions must retain the external missed-source
        # label rather than allowing truth to alter either execution path.
        fixtures = ((3, 2, (True, False, False)),
                    (4, 1, (True, True, False)))
        settings = (('nominal', .80), ('nominal', .99), ('robust', .95))
        for problem, index, exits in fixtures:
            case = generate_case(problem, index, 'development_v3')
            evaluated = evaluate_trace(capture_case(case), particles=self.particles)
            self.assertIsNone(evaluated['error'])
            for (mode, threshold), expected_exit in zip(settings, exits):
                with self.subTest(problem=problem, mode=mode, threshold=threshold):
                    self.assert_replay(case, evaluated, mode, threshold, expected_exit)
            if problem == 3:
                self.assertEqual(evaluated['outcomes']['nominal_0.8']['remaining_count'], 1)
                self.assertFalse(evaluated['outcomes']['nominal_0.8']['all_cleared'])

    def test_sixteen_source_safe_return_has_no_probability_interception(self):
        from scripts.benchmark_probability_stop import evaluate_trace

        for problem in (3, 4):
            case = origin_case(problem, 16)
            evaluated = evaluate_trace(capture_case(case), particles=self.particles)
            with self.subTest(problem=problem):
                self.assert_replay(case, evaluated, 'nominal', .80, False)
                self.assertEqual(len(evaluated['checkpoints']), 1)
                self.assertTrue(evaluated['checkpoints'][0]['public']['final_safe'])


if __name__ == '__main__':
    unittest.main()

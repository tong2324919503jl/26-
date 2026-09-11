"""Generator validation only: reserved evaluation trajectories are not opened."""
import math
import random
import unittest
from collections import defaultdict
from unittest.mock import patch

from problem3 import probability_scenarios as scenarios
from problem3.scenarios import SPLITS as OLD_SPLITS
from problem3.simulator import LocalSimulator, ObservationClient


class ProbabilityScenariosTests(unittest.TestCase):
    def assert_legal(self, case, problem):
        self.assertEqual(case['problem'], problem)
        self.assertEqual(case['provenance'], 'self_constructed_not_official')
        sources = case['sources']
        self.assertTrue(10 <= len(sources) <= 16)
        channels = [source['channel'] for source in sources]
        self.assertEqual(len(channels), len(set(channels)))
        for source in sources:
            self.assertTrue(1 <= source['channel'] <= 20)
            self.assertTrue(math.isfinite(source['x']) and math.isfinite(source['y']))
            self.assertLessEqual(math.hypot(source['x'], source['y']), 1800 + 1e-9)
            self.assertTrue(1000 <= source['radius'] <= 1500)
            if source['orientation_deg'] is not None:
                self.assertTrue(0 <= source['orientation_deg'] < 360)
        directional = sum(source['orientation_deg'] is not None for source in sources)
        if problem == 3:
            self.assertEqual(directional, 0)
        else:
            self.assertTrue(1 <= directional < len(sources))
        LocalSimulator(case)

    def test_development_legality_diversity_and_reproducibility(self):
        for problem in (3, 4):
            counts, noises = defaultdict(set), defaultdict(set)
            for index in range(256):
                case = scenarios.generate_case(problem, index)
                self.assert_legal(case, problem)
                self.assertEqual(case, scenarios.generate_case(problem, index))
                counts[case['family']].add(len(case['sources']))
                noises[case['family']].add(case['noise'])
                if case['family'] in scenarios.HARD_FAMILIES:
                    self.assertTrue(all(s['radius'] == 1000 for s in case['sources']))
            self.assertEqual(set(counts), set(scenarios.FAMILIES))
            for family in scenarios.FAMILIES:
                self.assertEqual(counts[family], set(range(10, 17)))
                self.assertEqual(noises[family], set(scenarios.NOISE_MODES))

    def test_stress_construction_with_non_reserved_unit_seeds(self):
        # Exercise the stress branch without evaluating calibration/holdout/stress
        # realizations that the early-stop experiment will later consume.
        for problem in (3, 4):
            for index in range(112):
                case = scenarios._construct_case(
                    problem, index, 900_000_000 + problem * 1000 + index,
                    'unit_test', stress=True)
                self.assert_legal(case, problem)
                self.assertIn(case['noise'], ('extreme', 'bias'))
                self.assertTrue(all(s['radius'] == 1000 for s in case['sources']))
                if problem == 4:
                    self.assertEqual(sum(s['orientation_deg'] is None
                                         for s in case['sources']), 1)

    def test_full_seed_reservations_are_disjoint_from_each_other_and_old_suites(self):
        intervals = []
        for problem in (3, 4):
            for split in scenarios.SPLITS:
                first = scenarios.case_seed(problem, 0, split)
                last = scenarios.case_seed(problem, scenarios.SEED_CAPACITY - 1, split)
                self.assertEqual(last - first + 1, scenarios.SEED_CAPACITY)
                intervals.append((first, last))
                for old_base, old_count in OLD_SPLITS.values():
                    old_first = old_base + problem * 1_000_000
                    old_last = old_first + old_count - 1
                    self.assertTrue(last < old_first or first > old_last)
        intervals.sort()
        for left, right in zip(intervals, intervals[1:]):
            self.assertLess(left[1], right[0])

    def test_default_sizes_without_generating_reserved_cases(self):
        self.assertEqual({k: v[1] for k, v in scenarios.SPLITS.items()},
                         dict(development=256, calibration=512, holdout=2048, stress=512))
        with patch.object(scenarios, 'generate_case', return_value=None) as generate:
            for split, (_, expected) in scenarios.SPLITS.items():
                generate.reset_mock()
                self.assertEqual(len(scenarios.generate_suite(4, split)), expected)
                self.assertEqual(generate.call_count, expected)
                generate.assert_called_with(4, expected - 1, split)

    def test_prefix_empty_independence_and_invalid_inputs(self):
        state = random.getstate()
        small = scenarios.generate_suite(4, count=3)
        self.assertEqual(small, scenarios.generate_suite(4, count=7)[:3])
        self.assertEqual(state, random.getstate())
        self.assertEqual(scenarios.generate_suite(3, count=0), [])
        small[0]['sources'][0]['x'] = 99999
        self.assertNotEqual(small[0], scenarios.generate_case(4))
        for problem in (True, 3.0, 2, 5, '3'):
            with self.assertRaises(ValueError):
                scenarios.generate_case(problem)
        for index in (True, -1, .5, scenarios.SEED_CAPACITY):
            with self.assertRaises(ValueError):
                scenarios.generate_case(3, index)
        for split in ('holdout_v3', 'unknown', None, []):
            with self.assertRaises(ValueError):
                scenarios.generate_case(3, split=split)
        for count in (True, -1, .5, scenarios.SEED_CAPACITY + 1):
            with self.assertRaises(ValueError):
                scenarios.generate_suite(3, count=count)

    def test_hidden_families_have_actual_origin_blind_sources(self):
        expected_hidden = {'one_hidden_outward': 1, 'two_hidden_opposite': 2,
                           'remote_hidden_cluster': 3}
        for problem in (3, 4):
            for family, hidden_count in expected_hidden.items():
                for block in range(7):
                    index = scenarios.FAMILIES.index(family) + block * len(scenarios.FAMILIES)
                    case = scenarios.generate_case(problem, index)
                    simulator = LocalSimulator(case)
                    simulator.enter()
                    hidden = []
                    for source in case['sources']:
                        result = simulator.measure((0, 0), source['channel'])
                        if result['measure_result'] == 'no_signal':
                            hidden.append(source)
                    self.assertEqual(len(hidden), hidden_count)
                    if problem == 4:
                        self.assertTrue(all(s['orientation_deg'] is not None for s in hidden))
                    self.assertTrue(all(math.hypot(s['x'], s['y']) > 1000 for s in hidden))

    def test_fixed_bounded_errors_and_public_facade(self):
        for noise_index in range(4):
            case = scenarios.generate_case(4, noise_index * len(scenarios.FAMILIES))
            self.assertEqual(case['noise'], scenarios.NOISE_MODES[noise_index])
            simulator = LocalSimulator(case)
            simulator.enter()
            facade = ObservationClient(simulator)
            for name in ('sources', 'case', 'seed', 'family', 'split'):
                self.assertFalse(hasattr(facade, name))
            source = case['sources'][0]
            angle = math.radians(source['orientation_deg'] or 0)
            point = (source['x'] + 30 * math.cos(angle),
                     source['y'] + 30 * math.sin(angle))
            first = facade.measure(point, source['channel'])
            again = facade.measure(point, source['channel'])
            self.assertEqual(first['measure_result'], 'direction')
            self.assertEqual(first['svd_deg'], again['svd_deg'])
            truth = math.degrees(math.atan2(source['y'] - point[1], source['x'] - point[0]))
            error = abs((first['svd_deg'] - truth + 180) % 360 - 180)
            self.assertLessEqual(error, 1.0050001)


if __name__ == '__main__':
    unittest.main()

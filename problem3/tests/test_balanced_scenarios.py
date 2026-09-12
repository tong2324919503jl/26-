"""Balanced dataset reproducibility, integrity and constraint checks (no solver)."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
import tempfile
import unittest

from problem3 import balanced_scenarios as scenarios
from problem3.probability_scenarios import (
    PROBLEM_SEED_STRIDE as OLD_PROBABILITY_STRIDE,
    SEED_CAPACITY as OLD_PROBABILITY_CAPACITY,
    SPLITS as OLD_PROBABILITY_SPLITS,
)
from problem3.scenarios import SPLITS as OLD_SPLITS
from problem3.simulator import LocalSimulator


class BalancedScenariosTests(unittest.TestCase):
    def test_full_default_balance_legality_and_uniqueness(self):
        seeds, contents = set(), set()
        for problem in (3, 4):
            counts = Counter()
            for case in scenarios.iter_cases(problem):
                counts[case['source_count']] += 1
                self.assertEqual(case['provenance'], 'self_constructed_not_official')
                self.assertTrue({'split', 'family', 'difficulty'}.isdisjoint(case))
                self.assertNotIn(case['seed'], seeds)
                seeds.add(case['seed'])
                digest = hashlib.sha256(json.dumps(case['sources'], sort_keys=True).encode()).digest()
                self.assertNotIn(digest, contents)
                contents.add(digest)
                simulator = LocalSimulator(case)
                self.assertEqual(len(simulator.sources), case['source_count'])
                directional = sum(s['orientation_deg'] is not None for s in case['sources'])
                self.assertTrue(directional == 0 if problem == 3 else
                                1 <= directional < case['source_count'])
                self.assertTrue(all(math.hypot(s['x'], s['y']) <= 1800 + 1e-9
                                    for s in case['sources']))
            self.assertEqual(counts, dict.fromkeys(range(10, 17), 714))
        self.assertEqual(len(seeds), 9996)

    def test_reproducibility_prefix_and_independent_random_state(self):
        state = random.getstate()
        first = list(scenarios.iter_cases(4, 2))
        second = list(scenarios.iter_cases(4, 3))
        self.assertEqual(first, second[:14])
        self.assertEqual([c['source_count'] for c in first], list(range(10, 17)) * 2)
        self.assertEqual(state, random.getstate())
        self.assertEqual(scenarios.generate_case(3, 12, 7), scenarios.generate_case(3, 12, 7))

    def test_seed_reservations_are_disjoint_from_prior_suites(self):
        intervals = []
        old_intervals = []
        for problem in (3, 4):
            for n in range(10, 17):
                intervals.append((scenarios.case_seed(problem, n),
                                  scenarios.case_seed(problem, n, scenarios.SEED_CAPACITY - 1)))
            for base, count in OLD_SPLITS.values():
                old_intervals.append((base + problem * 1_000_000,
                                      base + problem * 1_000_000 + count - 1))
            for base, _ in OLD_PROBABILITY_SPLITS.values():
                old_intervals.append((base + problem * OLD_PROBABILITY_STRIDE,
                                      base + problem * OLD_PROBABILITY_STRIDE
                                      + OLD_PROBABILITY_CAPACITY - 1))
        intervals.sort()
        for previous, current in zip(intervals, intervals[1:]):
            self.assertLess(previous[1], current[0])
        for low, high in intervals:
            for old_low, old_high in old_intervals:
                self.assertTrue(high < old_low or low > old_high)

    def test_write_reload_and_idempotent_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            manifest = scenarios.prepare_dataset(3, 2, directory)
            self.assertEqual(manifest['total_cases'], 14)
            cases_path = directory / 'cases.jsonl'
            before = (cases_path.read_bytes(), cases_path.stat().st_mtime_ns)
            self.assertEqual(scenarios.prepare_dataset(3, 2, directory), manifest)
            self.assertEqual(before, (cases_path.read_bytes(), cases_path.stat().st_mtime_ns))
            self.assertEqual(scenarios.load_cases(3, cases_path), list(scenarios.iter_cases(3, 2)))
            with self.assertRaises(ValueError):
                scenarios.prepare_dataset(3, 3, directory)
            with self.assertRaises(ValueError):
                scenarios.load_cases(4, directory)

    def test_damaged_or_partial_files_are_rejected_and_preserved(self):
        for damage in ('cases', 'manifest', 'missing_manifest', 'fingerprint',
                       'rehashed_mutation', 'rehashed_numeric_type'):
            with self.subTest(damage=damage), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                scenarios.prepare_dataset(4, 1, directory)
                cases_path, manifest_path = directory / 'cases.jsonl', directory / 'manifest.json'
                if damage == 'cases':
                    cases_path.write_bytes(cases_path.read_bytes() + b'{}\n')
                elif damage == 'manifest':
                    manifest_path.write_text('{}', encoding='utf-8')
                elif damage == 'missing_manifest':
                    manifest_path.unlink()
                else:
                    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
                    if damage == 'fingerprint':
                        manifest['generator_sha256'] = '0' * 64
                    elif damage == 'rehashed_mutation':
                        cases_bytes = cases_path.read_bytes().replace(b'"radius":', b'"radius":0.0,"old_radius":', 1)
                        cases_path.write_bytes(cases_bytes)
                        manifest['cases_sha256'] = hashlib.sha256(cases_bytes).hexdigest()
                    else:
                        cases_bytes = cases_path.read_bytes().replace(b'"problem":4,', b'"problem":4.0,', 1)
                        cases_path.write_bytes(cases_bytes)
                        manifest['cases_sha256'] = hashlib.sha256(cases_bytes).hexdigest()
                    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
                before = cases_path.read_bytes()
                with self.assertRaises(ValueError):
                    scenarios.prepare_dataset(4, 1, directory)
                self.assertEqual(cases_path.read_bytes(), before)

    def test_invalid_inputs_and_path_resolution(self):
        for problem in (True, 3.0, 2, 5, '3'):
            with self.assertRaises(ValueError):
                scenarios.iter_cases(problem, 1)
        for count in (True, -1, 0, .5, scenarios.SEED_CAPACITY + 1):
            with self.assertRaises(ValueError):
                scenarios.iter_cases(3, count)
        for source_count in (True, 9, 17, 10.0, '10'):
            with self.assertRaises(ValueError):
                scenarios.generate_case(3, source_count)
        for index in (True, -1, 1.5, scenarios.SEED_CAPACITY):
            with self.assertRaises(ValueError):
                scenarios.generate_case(4, 10, index)
        self.assertEqual(scenarios.dataset_directory(4, 'examples/unit'),
                         scenarios.ROOT / 'problem4' / 'examples' / 'unit')


if __name__ == '__main__':
    unittest.main()

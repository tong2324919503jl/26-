"""Check the construction prior and physical constraints without solver outcomes."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import tempfile
import unittest

from problem3 import balanced_scenarios as old_balanced
from problem3 import normal_scenarios as scenarios
from problem3.probability_scenarios import (
    PROBLEM_SEED_STRIDE as PROBABILITY_STRIDE,
    SEED_CAPACITY as PROBABILITY_CAPACITY,
    SPLITS as PROBABILITY_SPLITS,
)
from problem3.scenarios import SPLITS as OLD_SPLITS
from problem3.simulator import LocalSimulator


class NormalScenariosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {problem: list(scenarios.iter_cases(problem)) for problem in (3, 4)}

    def test_full_counts_legality_unique_ids_seeds_and_source_configurations(self):
        ids, seeds, contents = set(), set(), set()
        for problem, cases in self.cases.items():
            self.assertEqual(len(cases), 7000)
            self.assertEqual(Counter(c['source_count'] for c in cases), dict.fromkeys(range(10, 17), 1000))
            self.assertEqual([c['source_count'] for c in cases[:14]], list(range(10, 17)) * 2)
            for case in cases:
                self.assertEqual(case['provenance'], 'self_constructed_not_official')
                self.assertTrue({'family', 'split', 'difficulty_level'}.isdisjoint(case))
                self.assertNotIn(case['case_id'], ids)
                self.assertNotIn(case['seed'], seeds)
                digest = hashlib.sha256(json.dumps(case['sources'], sort_keys=True).encode()).digest()
                self.assertNotIn(digest, contents)
                ids.add(case['case_id']); seeds.add(case['seed']); contents.add(digest)
                LocalSimulator(case)
                score = case['construction_difficulty']['score']
                for source in case['sources']:
                    self.assertLessEqual(math.hypot(source['x'], source['y']), 900 + 900 * score + 1e-8)
                    self.assertGreaterEqual(source['radius'], 1350 - 350 * score - 1e-8)
                    self.assertLessEqual(source['radius'], 1500 - 350 * score + 1e-8)
                directional = sum(s['orientation_deg'] is not None for s in case['sources'])
                self.assertTrue(directional == 0 if problem == 3 else 1 <= directional < case['source_count'])
        self.assertEqual(len(seeds), 14000)

    def test_exact_normal_quantiles_and_shuffled_score_order_for_every_source_count(self):
        expected = scenarios.difficulty_quantiles()
        self.assertAlmostEqual(statistics.mean(expected), 0., places=12)
        self.assertTrue(.98 < statistics.pstdev(expected) < 1.)
        for k, z in enumerate(expected):
            conditional_cdf = ((scenarios.NORMAL.cdf(z) - scenarios.LOWER_CDF)
                               / (scenarios.UPPER_CDF - scenarios.LOWER_CDF))
            self.assertAlmostEqual(conditional_cdf, (k + .5) / 1000, places=12)
        for cases in self.cases.values():
            for n in scenarios.SOURCE_COUNTS:
                group = [c for c in cases if c['source_count'] == n]
                zs = [c['construction_difficulty']['z'] for c in group]
                self.assertEqual(sorted(zs), list(expected))
                self.assertEqual(Counter(c['construction_difficulty']['quantile_index'] for c in group),
                                 dict.fromkeys(range(1000), 1))
                self.assertEqual([sum(z < -1 for z in zs), sum(-1 <= z <= 1 for z in zs), sum(z > 1 for z in zs)],
                                 [158, 684, 158])
                self.assertNotEqual(zs[:20], sorted(zs[:20]))
                self.assertLess(min(zs[:20]), 0)
                self.assertGreater(max(zs[:20]), 0)

    def test_physical_score_mapping_with_identical_latent_random_numbers(self):
        for problem in (3, 4):
            for n in (10, 13, 16):
                sequence = [scenarios._physical_sources(problem, n, 9_100_000_000 + n, d)
                            for d in (0., .25, .5, .75, 1.)]
                for j, (previous, current) in enumerate(zip(sequence, sequence[1:])):
                    scale = (900 + 900 * (j + 1) / 4) / (900 + 900 * j / 4)
                    for a, b in zip(previous, current):
                        self.assertEqual(a['channel'], b['channel'])
                        self.assertAlmostEqual(a['x'] * scale, b['x'], delta=2e-9)
                        self.assertAlmostEqual(a['y'] * scale, b['y'], delta=2e-9)
                        self.assertAlmostEqual(a['radius'] - b['radius'], 87.5, delta=2e-9)
                        if a['orientation_deg'] is not None:
                            self.assertIsNotNone(b['orientation_deg'])
                            radial = math.atan2(a['y'], a['x'])
                            a_outward = math.cos(math.radians(a['orientation_deg']) - radial)
                            b_outward = math.cos(math.radians(b['orientation_deg']) - radial)
                            self.assertGreaterEqual(b_outward + 1e-8, a_outward)
                if problem == 4:
                    self.assertEqual(sum(s['orientation_deg'] is not None for s in sequence[0]), 1)
                    self.assertEqual(sum(s['orientation_deg'] is not None for s in sequence[-1]), n - 1)

    def test_independent_geometry_formulas(self):
        def source(x, y, radius, orientation):
            return dict(x=x, y=y, radius=radius, orientation_deg=orientation)
        examples = [
            (source(100, 0, 50, None), 50),
            (source(100, 0, 150, None), 0),
            (source(100, 0, 50, 0), 100),
            (source(100, 0, 50, 180), 50),
            (source(100, 0, 50, 90), 50),
            (source(100, 80, 50, 0), math.sqrt(100**2 + 30**2)),
            (source(100, 80, 50, 180), math.hypot(100, 80) - 50),
        ]
        for item, expected in examples:
            self.assertAlmostEqual(scenarios.origin_receiving_distance(item), expected, places=9)
        self.assertAlmostEqual(scenarios.source_mst_length([dict(x=3, y=0), dict(x=0, y=4)]), 7)
        self.assertAlmostEqual(scenarios.source_mst_length([dict(x=3, y=0), dict(x=3, y=4)]), 7)

    def test_within_count_geometric_associations_and_ten_equal_frequency_bins(self):
        for problem, cases in self.cases.items():
            audit = scenarios._distribution(problem, cases)
            for group in audit['by_source_count'].values():
                self.assertEqual([b['case_count'] for b in group['equal_frequency_score_bins']], [100] * 10)
                correlations = group['score_correlations']
                self.assertLess(correlations['mean_receiving_radius_m']['pearson'], -.9)
                for metric in ('mean_source_distance_from_origin_m', 'mean_pairwise_source_distance_m',
                               'source_mst_m_per_source', 'mean_origin_to_receiving_region_m'):
                    self.assertGreater(correlations[metric]['pearson'], .2)
                    self.assertGreater(correlations[metric]['spearman'], .2)
                if problem == 4:
                    self.assertGreater(correlations['directional_fraction']['pearson'], .9)
                    self.assertGreater(correlations['directional_outward_fraction']['pearson'], .2)

    def test_reproducibility_global_random_state_and_seed_isolation(self):
        before = random.getstate()
        self.assertEqual(scenarios.generate_case(4, 12, 71), self.cases[4][71 * 7 + 2])
        self.assertEqual(before, random.getstate())
        intervals, old_intervals = [], []
        for problem in (3, 4):
            for n in scenarios.SOURCE_COUNTS:
                first = scenarios.case_seed(problem, n)
                intervals.append((first, first + scenarios.SEED_BLOCK - 1))
                old_intervals.append((old_balanced.case_seed(problem, n),
                                      old_balanced.case_seed(problem, n, old_balanced.SEED_CAPACITY - 1)))
            for base, count in OLD_SPLITS.values():
                old_intervals.append((base + problem * 1_000_000, base + problem * 1_000_000 + count - 1))
            for base, _ in PROBABILITY_SPLITS.values():
                old_intervals.append((base + problem * PROBABILITY_STRIDE,
                                      base + problem * PROBABILITY_STRIDE + PROBABILITY_CAPACITY - 1))
        intervals.sort()
        for left, right in zip(intervals, intervals[1:]):
            self.assertLess(left[1], right[0])
        for a, b in intervals:
            for c, d in old_intervals:
                self.assertTrue(b < c or a > d)

    def test_idempotent_write_reload_and_modified_or_partial_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            manifest = scenarios.prepare_dataset(4, 2, directory)
            before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in directory.iterdir()}
            self.assertEqual(scenarios.prepare_dataset(4, 2, directory), manifest)
            self.assertEqual(scenarios.load_cases(4, directory), list(scenarios.iter_cases(4, 2)))
            self.assertEqual(before, {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in directory.iterdir()})
            with self.assertRaises(ValueError):
                scenarios.prepare_dataset(4, 3, directory)
        for name in ('cases.jsonl', 'distribution.json', 'README.md', 'manifest.json'):
            with self.subTest(file=name), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                scenarios.prepare_dataset(3, 1, directory)
                path = directory / name
                path.write_bytes(path.read_bytes() + b'corrupted\n')
                changed = path.read_bytes()
                with self.assertRaises(ValueError):
                    scenarios.prepare_dataset(3, 1, directory)
                self.assertEqual(path.read_bytes(), changed)
                path.unlink()
                with self.assertRaises(ValueError):
                    scenarios.prepare_dataset(3, 1, directory)

    def test_invalid_requests_and_relative_paths(self):
        for problem in (True, 3.0, 2, 5, '3'):
            with self.assertRaises(ValueError):
                scenarios.iter_cases(problem, 1)
        for count in (True, -1, 0, .5, scenarios.SEED_CAPACITY + 1):
            with self.assertRaises(ValueError):
                scenarios.iter_cases(3, count)
        for n in (True, 9, 17, 10.0, '10'):
            with self.assertRaises(ValueError):
                scenarios.generate_case(3, n)
        for index in (True, -1, 1.5, 1000):
            with self.assertRaises(ValueError):
                scenarios.generate_case(3, 10, index)
        self.assertEqual(scenarios.dataset_directory(4, 'examples/custom'),
                         scenarios.ROOT / 'problem4/examples/custom')


if __name__ == '__main__':
    unittest.main()

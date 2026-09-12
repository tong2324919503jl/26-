"""Version routing without requiring historical datasets in a clean checkout."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest

from problem3 import balanced_datasets as datasets
from problem3 import balanced_scenarios as legacy
from problem3 import normal_scenarios as current


class BalancedDatasetGatewayTests(unittest.TestCase):
    def test_default_generates_seven_thousand_cases_per_problem(self):
        self.assertEqual(datasets.DEFAULT_PER_COUNT, 1000)
        self.assertEqual(datasets.DATASET, current.DATASET)
        with tempfile.TemporaryDirectory() as temporary:
            for problem in (3, 4):
                path = Path(temporary) / f'problem{problem}'
                manifest = datasets.prepare_dataset(problem, path=path)
                self.assertEqual(manifest['dataset'], current.DATASET)
                self.assertEqual(manifest['total_cases'], 7000)
                self.assertEqual(manifest['counts_by_source_count'], dict.fromkeys(map(str, range(10, 17)), 1000))
                cases = datasets.load_cases(problem, path)
                self.assertEqual(Counter(case['source_count'] for case in cases), dict.fromkeys(range(10, 17), 1000))
                self.assertTrue(all('construction_difficulty' in case for case in cases))
                self.assertEqual(datasets.dataset_directory(problem), current.dataset_directory(problem))

    def test_explicit_legacy_manifest_selects_legacy_validator(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            manifest = legacy.prepare_dataset(4, 2, path)
            self.assertEqual(datasets.validate_dataset(4, path), manifest)
            self.assertEqual(datasets.load_cases(4, path / 'cases.jsonl'), list(legacy.iter_cases(4, 2)))
            self.assertEqual(datasets.prepare_dataset(4, 2, path), manifest)
            self.assertEqual(manifest['dataset'], legacy.DATASET)

    def test_unknown_version_never_silently_falls_back(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            (path / 'manifest.json').write_text(json.dumps({'dataset': 'unsupported'}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Unsupported dataset version'):
                datasets.load_cases(3, path)
            with self.assertRaisesRegex(ValueError, 'Unsupported dataset version'):
                datasets.prepare_dataset(3, 1, path)


if __name__ == '__main__':
    unittest.main()

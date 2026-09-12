"""Production version selection and frozen practice-source integrity."""
import unittest

from scripts.benchmark_search import get_algorithm_version, get_policy
from scripts.verify_practice_v5 import verify_source


class CurrentPracticeTests(unittest.TestCase):
    def test_migrated_code_matches_the_original_practice_package(self):
        self.assertGreaterEqual(verify_source()['files_checked'], 30)

    def test_default_is_v5_and_v4_is_an_explicit_historical_selection(self):
        for problem, version in ((3, 'problem3_v5_continuous'),
                                 (4, 'problem4_v5_visibility_discovery')):
            with self.subTest(problem=problem):
                policy = get_policy(problem, 'adaptive')
                self.assertEqual(policy.__class__.__module__, f'problem{problem}.current_policy')
                self.assertEqual(get_algorithm_version(problem), version)
                self.assertEqual(get_algorithm_version(problem, 'v4'), f'problem{problem}_v4')
                self.assertEqual(get_policy(problem, 'v4').strategy, 'adaptive')


if __name__ == '__main__':
    unittest.main()

"""Risks and invariants of the optional probability experiment."""
import math
import unittest
from importlib.util import find_spec

from problem3.probability_stop import (ProbabilityModel, full_clear_probability,
                                      make_policy)


class PosteriorTests(unittest.TestCase):
    def test_unknown_source_minimum_and_maximum(self):
        self.assertEqual(full_clear_probability(9, 0), 0)
        self.assertEqual(full_clear_probability(16, 1), 1)
        self.assertEqual(full_clear_probability(10, 0), 1)

    def test_one_remaining_count_hypothesis(self):
        # For k=15 only N=15 and N=16 are possible.
        self.assertAlmostEqual(full_clear_probability(15, .02), 1/(1+16*.02))
        self.assertAlmostEqual(full_clear_probability(15, .02, 2), 1/(1+32*.02))

    def test_channel_assignment_likelihood_matches_formula(self):
        k, q = 11, .017
        weights = [math.comb(20-k, n-k)/math.comb(20, n)*q**(n-k)
                   for n in range(k, 17)]
        self.assertAlmostEqual(weights[0]/sum(weights), full_clear_probability(k, q))

    def test_invalid_inputs(self):
        for k, q in ((True, .1), (17, .1), (10, math.nan), (10, -.1)):
            with self.assertRaises(ValueError):
                full_clear_probability(k, q)
        with self.assertRaises(ValueError):
            make_policy(3, threshold=1.)


@unittest.skipUnless(find_spec('numpy'), 'Optional probability experiment requires NumPy')
class ConfigurationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = ProbabilityModel(4, 512)

    def test_repeated_no_signal_is_not_independent_evidence(self):
        once = self.model.estimate([(0., 0.)], 10)
        repeated = self.model.estimate([(0., 0.)]*20, 10)
        self.assertEqual(once, repeated)

    def test_more_scan_points_and_prior_sensitivity(self):
        first = self.model.estimate([(0., 0.)], 12)
        more = self.model.estimate([(0., 0.), (1800., 0.)], 12)
        for prior, mass in first['unseen_mass'].items():
            self.assertLessEqual(more['unseen_mass'][prior], mass)
        self.assertLessEqual(more['robust'], more['nominal'])
        self.assertLess(more['nominal'], 1.)
        self.assertFalse(more['completion_certified'])

    def test_positive_unresolved_source_blocks_exit(self):
        result = self.model.estimate([(0., 0.)], 12, known_pending=True)
        self.assertFalse(result['eligible'])
        self.assertEqual(result['nominal'], 0.)
        self.assertEqual(result['robust'], 0.)

    def test_source_minimum_blocks_exit(self):
        result = self.model.estimate([(0., 0.)], 9)
        self.assertFalse(result['eligible'])
        self.assertEqual(result['robust'], 0.)

    def test_zero_sampled_survivors_still_not_certainty(self):
        from problem4.search_layout import coverage_points
        result = self.model.estimate(coverage_points(), 15)
        self.assertTrue(all(v >= 1/512 for v in result['unseen_mass'].values()))
        self.assertLess(result['nominal'], 1.)


if __name__ == '__main__':
    unittest.main()

"""Finite-layout and numerical-error regressions, without held-out cases."""
import math
import unittest

from problem3.probability_numeric import (
    NUMERICAL_ALPHA, POINT_TOLERANCE_M, bernoulli_kl, hypothesis_count,
    simultaneous_mass_upper, supported_layouts, supports_points,
)


class ProbabilityNumericalTests(unittest.TestCase):
    def test_finite_union_counts_all_layout_subsets_and_five_priors(self):
        self.assertEqual(hypothesis_count(3), 5 * (24 * 2**7 + 16 * 2**10))
        self.assertEqual(hypothesis_count(4), 5 * 2**22)

    def test_all_declared_layouts_and_reordered_subsets_are_supported(self):
        for problem in (3, 4):
            for layout in supported_layouts(problem):
                self.assertTrue(supports_points(problem, layout))
                self.assertTrue(supports_points(problem, list(reversed(layout[::2]))))
                self.assertTrue(supports_points(problem, [layout[0], layout[0]]))
        self.assertTrue(supports_points(3, []))

    def test_points_from_incompatible_layouts_cannot_be_combined(self):
        layouts = supported_layouts(3)
        self.assertFalse(supports_points(3, [(0., 0.), layouts[0][1], layouts[1][1]]))
        self.assertFalse(supports_points(3, [(0., 0.), layouts[0][1], layouts[24][1]]))
        self.assertFalse(supports_points(4, [(0., 0.), (50., 0.)]))

    def test_matching_uses_euclidean_tolerance_and_rejects_bad_points(self):
        x, y = supported_layouts(4)[0][3]
        self.assertTrue(supports_points(4, [(x + .6e-6, y + .6e-6)]))
        self.assertFalse(supports_points(4, [(x + .8e-6, y + .8e-6)]))
        for points in ([(math.nan, 0.)], [(math.inf, 0.)], [(True, 0.)], [(0.,)], [None], None):
            self.assertFalse(supports_points(3, points))

    def test_tolerance_detection_sandwich_at_both_physical_boundaries(self):
        eps = POINT_TOLERANCE_M
        source = (0., 0.)
        canonical = (1000.-eps, 0.)
        actual = (canonical[0]+eps, canonical[1])
        self.assertLessEqual(math.dist(source, actual), 1000.)
        canonical_beam = (eps, 200.)
        actual_beam = (canonical_beam[0]-eps, canonical_beam[1])
        self.assertGreaterEqual(actual_beam[0], 0.)
        # Even an actual detection on the deep inset's boundaries remains a
        # canonical epsilon-inset detection after the largest permitted shift.
        actual = (1000.-.001, 0.)
        canonical = (actual[0]+eps, actual[1])
        self.assertLessEqual(math.dist(source, canonical), 1000.-eps)
        actual_beam = (.001, 200.)
        self.assertGreaterEqual(actual_beam[0]-eps, eps)

    def test_zero_survivors_have_strictly_positive_closed_form_upper_bound(self):
        for problem in (3, 4):
            exact = -math.expm1(-math.log(hypothesis_count(problem)/NUMERICAL_ALPHA)/131072)
            computed = simultaneous_mass_upper(0., 131072, problem)
            self.assertGreater(computed, 0.)
            self.assertGreaterEqual(computed, exact)
            self.assertAlmostEqual(computed, exact, places=15)
        self.assertEqual(simultaneous_mass_upper(1., 131072, 4), 1.)

    def test_inverted_bound_keeps_safe_bracket_and_is_monotone(self):
        for problem in (3, 4):
            for count in (64, 32768, 131072):
                target = math.log(hypothesis_count(problem)/NUMERICAL_ALPHA)/count
                values = [simultaneous_mass_upper(p, count, problem)
                          for p in sorted((0., 1/count, .01, .5, .99, 1.))]
                self.assertEqual(values, sorted(values))
                for p in (1/count, .01, .5, .99):
                    upper = simultaneous_mass_upper(p, count, problem)
                    self.assertGreaterEqual(bernoulli_kl(p, upper), target-1e-14)
                    if upper < 1.-1e-9:
                        self.assertAlmostEqual(bernoulli_kl(p, upper), target, places=12)
        self.assertGreater(simultaneous_mass_upper(.001, 32768, 4),
                           simultaneous_mass_upper(.001, 131072, 4))

    def test_invalid_numerical_inputs_are_rejected(self):
        for p in (-.01, 1.01, math.nan, math.inf, True):
            with self.assertRaises(ValueError): simultaneous_mass_upper(p, 32768, 4)
        for count in (0, -1, 64., True):
            with self.assertRaises(ValueError): simultaneous_mass_upper(.1, count, 4)
        with self.assertRaises(ValueError): simultaneous_mass_upper(.1, 32768, 2)


if __name__ == '__main__': unittest.main()

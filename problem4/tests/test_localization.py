"""Physical half-plane counterexamples and source-retention boundary checks."""
from __future__ import annotations

import math
import random
import unittest

from problem3.geometry import contains
from problem3.policy import SearchPolicy as BasePolicy
from problem4.localization import LocalizationMixin


class _Policy(LocalizationMixin, BasePolicy):
    pass


class _EmitterOracle:
    """Independent test emitter; the policy receives only public responses."""

    def __init__(self, source, radius=1000., heading=math.pi, error=0.):
        self.__source = source
        self.__radius = radius
        self.__normal = (math.cos(heading), math.sin(heading))
        self.__error = error
        self.position = (0., 0.)
        self.current_channel = 1
        self.virtual_time_s = 0.

    def check_budget(self):
        return None

    def measure(self, point, channel):
        self.position = point
        self.current_channel = channel
        dx, dy = point[0] - self.__source[0], point[1] - self.__source[1]
        visible = dx * self.__normal[0] + dy * self.__normal[1] >= -1e-9
        if math.hypot(dx, dy) > self.__radius + 1e-9 or not visible:
            return {"accepted": True, "measure_result": "no_signal"}
        angle = math.degrees(math.atan2(-dy, -dx))
        return {"accepted": True, "measure_result": "direction",
                "svd_deg": round((angle + self.__error) % 360, 2) % 360}


class HistoricalNegativeGeometryTests(unittest.TestCase):
    def test_in_range_backside_pair_removes_shadow_but_retains_source(self):
        source = (100., 0.)
        client, policy = _EmitterOracle(source), _Policy()
        for point in ((600., -40.), (600., 40.)):
            self.assertEqual(policy._measure(client, point, 1), "no_signal")
        self.assertEqual(policy._measure(client, (0., 0.), 1), "direction")
        self.assertTrue(contains(policy.regions[1], source))
        self.assertLess(max(p[0] for p in policy.regions[1]), 600.001)

    def test_out_of_range_negatives_must_not_remove_source_behind_pair(self):
        # Both negatives lie on the transmitting side. They are absent only
        # because of distance; deleting their shadow without a range proof
        # would incorrectly remove the true source at x=1400.
        source = (1400., 0.)
        client, policy = _EmitterOracle(source, radius=1500.), _Policy()
        for point in ((300., -1400.), (300., 1400.)):
            self.assertGreater(math.dist(point, source), 1500.)
            self.assertEqual(policy._measure(client, point, 1), "no_signal")
        self.assertEqual(policy._measure(client, (0., 0.), 1), "direction")
        self.assertTrue(contains(policy.regions[1], source))

    def test_positive_radius_lower_bound_cuts_beyond_1000m(self):
        source = (0., 0.)
        client, policy = _EmitterOracle(source, radius=1500.), _Policy()
        negatives = ((100., -1100.), (100., 1100.))
        for point in negatives:
            self.assertGreater(math.dist(point, source), 1000.)
            self.assertEqual(policy._measure(client, point, 1), "no_signal")
        self.assertEqual(policy._measure(client, (-1100., 0.), 1), "direction")
        self.assertTrue(contains(policy.regions[1], source))
        self.assertLess(max(p[0] for p in policy.regions[1]), 100.001)

    def test_two_negatives_may_require_different_positive_radius_witnesses(self):
        source = (0., 0.)
        client = _EmitterOracle(source, radius=1500.)
        lower, upper = (-1000., -1000.), (-1000., 1000.)
        q_upper, q_lower = (100., 1200.), (100., -1200.)
        for point in (lower, upper):
            self.assertEqual(client.measure(point, 1)["measure_result"], "direction")
        for point in (q_upper, q_lower):
            self.assertEqual(client.measure(point, 1)["measure_result"], "no_signal")
        cell = [(-10., -300.), (10., -300.), (10., 300.), (-10., 300.)]
        policy = _Policy()
        policy.observations[1] = [(lower, 45.)]
        self.assertFalse(policy._history_point_in_range(q_upper, cell, 1))
        self.assertTrue(policy._history_point_in_range(q_lower, cell, 1))
        policy.observations[1] = [(upper, 315.)]
        self.assertTrue(policy._history_point_in_range(q_upper, cell, 1))
        self.assertFalse(policy._history_point_in_range(q_lower, cell, 1))
        policy.observations[1] += [(lower, 45.)]
        self.assertTrue(all(policy._history_point_in_range(q, cell, 1)
                            for q in (q_upper, q_lower)))

    def test_rounded_fixed_error_boundary_is_retained_without_averaging(self):
        for sign in (-1., 1.):
            angle = sign * .00500001
            source = (500. * math.cos(math.radians(angle)),
                      500. * math.sin(math.radians(angle)))
            client, policy = _EmitterOracle(source, error=sign), _Policy()
            for point in ((700., -30.), (700., 30.)):
                self.assertEqual(policy._measure(client, point, 1), "no_signal")
            policy._measure(client, (0., 0.), 1)
            reading = policy.observations[1][-1][1]
            angular_error = abs((reading - angle + 180.) % 360. - 180.)
            self.assertGreater(angular_error, 1.00499)
            self.assertTrue(contains(policy.regions[1], source))
            policy._measure(client, (0., 0.), 1)
            self.assertEqual(policy.observations[1][-1][1], reading)
            self.assertTrue(contains(policy.regions[1], source))

    def test_collinear_negative_pair_cannot_claim_two_dimensional_cut(self):
        policy = _Policy()
        policy.regions[1] = [(50., 0.), (150., 0.)]
        policy.observations[1] = [((0., 0.), 0.)]
        policy._negative_history = {1: [(200., 0.), (400., 0.)]}
        policy._clip_history(1)
        self.assertEqual(policy.regions[1], [(50., 0.), (150., 0.)])

    def test_singleton_feasible_region_survives_history_refinement(self):
        policy = _Policy()
        policy.regions[1] = [(100., 0.)]
        policy.observations[1] = [((0., 0.), 0.)]
        policy._negative_history = {1: [(200., -20.), (200., 20.)]}
        policy._clip_history(1)
        self.assertEqual(policy.regions[1], [(100., 0.)])

    def test_random_physical_halfplanes_and_radius_causes_retain_true_source(self):
        # Independent geometric cases, not new holdout/stress benchmark data.
        rng = random.Random(972213)
        for index in range(128):
            source = (rng.uniform(-900., 900.), rng.uniform(-900., 900.))
            heading = rng.uniform(0., math.tau)
            radius = rng.uniform(1000., 1500.)
            client = _EmitterOracle(source, radius, heading, 1. if index % 2 else -1.)
            policy = _Policy()
            for j in range(5):
                angle = heading + math.pi + rng.uniform(-1.4, 1.4)
                r = rng.uniform(40., radius) if j % 2 else radius + rng.uniform(1., 700.)
                point = (source[0] + r * math.cos(angle), source[1] + r * math.sin(angle))
                self.assertEqual(policy._measure(client, point, 1), "no_signal")
            for j in range(3):
                angle = heading + rng.uniform(-1.55, 1.55)
                r = rng.uniform(30., radius)
                point = (source[0] + r * math.cos(angle), source[1] + r * math.sin(angle))
                self.assertEqual(policy._measure(client, point, 1), "direction")
                self.assertTrue(contains(policy.regions[1], source), (index, j))


if __name__ == "__main__":
    unittest.main()

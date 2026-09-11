"""Independent geometric and black-box clearance checks."""
import math
import random
import unittest

from problem3.geometry import (certified_covering_radius, contains, distance, enclosing_circle, initial_region,
                                intersect_bearing, optical_cover)
from problem3.policy import SearchPolicy


class GeometryTests(unittest.TestCase):
    def test_quantized_adversarial_bearings_retain_truth(self):
        rng = random.Random(49016)
        for _ in range(400):
            angle = rng.uniform(0, 2 * math.pi)
            radius = rng.uniform(0, 1800)
            truth = (radius * math.cos(angle), radius * math.sin(angle))
            polygon = initial_region()
            for _ in range(5):
                a = rng.uniform(0, 2 * math.pi)
                d = rng.uniform(5.001, 1500)
                receiver = (truth[0] - d * math.cos(a), truth[1] - d * math.sin(a))
                bearing = round((math.degrees(a) + rng.choice((-1.0, 1.0))) % 360, 2)
                polygon = intersect_bearing(polygon, receiver, bearing)
                self.assertTrue(contains(polygon, truth))
            center, bound = enclosing_circle(polygon)
            self.assertLessEqual(distance(center, truth), bound + 1e-5)

    def test_ring_coverage_certificate_and_dense_boundary(self):
        points = SearchPolicy().coverage_points()
        self.assertEqual(len(points), 7)
        for radial in range(0, 1801, 60):
            for step in range(720):
                angle = step * math.pi / 360
                source = radial * math.cos(angle), radial * math.sin(angle)
                self.assertLessEqual(min(distance(source, p) for p in points), 1000)

    def test_enclosing_circle_equilateral_not_half_diameter(self):
        vertices = [(0.0, 0.0), (40.0, 0.0), (20.0, 20 * math.sqrt(3))]
        _, radius = enclosing_circle(vertices)
        self.assertAlmostEqual(radius, 40 / math.sqrt(3), places=5)
        self.assertGreater(radius, 20)

    def test_voronoi_cover_certificate(self):
        ring = SearchPolicy().coverage_points()
        self.assertLess(certified_covering_radius(ring), 1000)
        self.assertGreater(certified_covering_radius([(0, 0)]), 1800)
        self.assertGreater(certified_covering_radius(ring[:-1]), 1000)

    def test_rotated_optical_cover_contains_every_sample(self):
        rng = random.Random(499)
        for bearing in (0, 0.005, 42.37, 90, 180, 359.995):
            polygon = intersect_bearing(initial_region(), (300, -100), bearing)
            cover = optical_cover(polygon)
            for _ in range(250):
                weights = [rng.expovariate(1) for _ in polygon]
                total = sum(weights)
                point = (sum(p[0] * w for p, w in zip(polygon, weights)) / total,
                         sum(p[1] * w for p, w in zip(polygon, weights)) / total)
                self.assertLessEqual(min(distance(point, p) for p in cover), 20)
            for point in polygon:
                self.assertLessEqual(min(distance(point, p) for p in cover), 20)


class ProtocolOnlyClient:
    """A one-source fake with no public true-position API."""
    def __init__(self, point, bearing_error=1.0, directional=False):
        self.__point = point
        self.__error = bearing_error
        self.__directional = directional
        self.__cleared = False
        self.position = (0., 0.)
        self.current_channel = 1
        self.virtual_time_s = 0.
        self.actions = 0

    def check_budget(self):
        if self.actions > 1500:
            raise RuntimeError("Unexpected policy loop")

    def measure(self, point, channel):
        self.virtual_time_s += distance(self.position, point) / 5 + 5 + (channel != self.current_channel)
        self.position, self.current_channel = point, channel
        self.actions += 1
        d = distance(point, self.__point)
        if self.__cleared or channel != 7 or d > 1000 or self.__directional and point[1] > self.__point[1]:
            return {"accepted": True, "measure_result": "no_signal"}
        if d <= 5:
            return {"accepted": True, "measure_result": "near"}
        angle = math.degrees(math.atan2(self.__point[1] - point[1], self.__point[0] - point[0]))
        return {"accepted": True, "measure_result": "direction", "svd_deg": round((angle + self.__error) % 360, 2)}

    def clear(self, point, channel):
        success = not self.__cleared and channel == 7 and distance(point, self.__point) <= 20
        self.virtual_time_s += distance(self.position, point) / 5 + (5 if success else 3)
        self.position = point
        self.actions += 1
        self.__cleared |= success
        return {"accepted": True, "clear_result": "success" if success else "no_target_in_range"}


class PolicyTests(unittest.TestCase):
    def test_end_to_end_adversarial_error_and_edge_positions(self):
        for strategy in ("baseline", "adaptive", "optical"):
            for point in ((0, 0), (1799, 0), (-900, 1558), (650, -500)):
                for error in (-1, 1):
                    result = SearchPolicy(strategy=strategy).run(ProtocolOnlyClient(point, error))
                    self.assertEqual(result["cleared_channels"], [7])
                    self.assertTrue(result["coverage_complete"])

    def test_directional_localization_remains_finite(self):
        client = ProtocolOnlyClient((650, 0), directional=True)
        policy = SearchPolicy()
        policy._measure(client, (0., 0.), 7)
        self.assertTrue(policy._localize(7, client))
        self.assertIn(7, policy.cleared)

    def test_near_clears_without_bearing(self):
        client = ProtocolOnlyClient((3, 0))
        policy = SearchPolicy()
        self.assertEqual(policy._measure(client, (0, 0), 7), "near")
        self.assertIn(7, policy.cleared)

    def test_directional_negative_does_not_discard_true_region(self):
        client = ProtocolOnlyClient((650, 0), directional=True)
        policy = SearchPolicy()
        policy._measure(client, (0, 0), 7)
        original = list(policy.regions[7])
        self.assertEqual(policy._measure(client, (600, 100), 7), "no_signal")
        self.assertEqual(policy.regions[7], original)

    def test_rejected_action_never_becomes_a_reading(self):
        class RejectedClient(ProtocolOnlyClient):
            def measure(self, point, channel):
                return {"accepted": False, "virtual_time_s": 0}
        with self.assertRaisesRegex(RuntimeError, "not accepted"):
            SearchPolicy().run(RejectedClient((0, 0)))

    def test_sixteen_clearances_certify_early_stop(self):
        class NearClient(ProtocolOnlyClient):
            def measure(self, point, channel):
                return {"accepted": True, "measure_result": "near" if channel <= 16 else "no_signal"}
            def clear(self, point, channel):
                return {"accepted": True, "clear_result": "success"}
        report = SearchPolicy().run(NearClient((0, 0)))
        self.assertEqual(len(report["cleared_channels"]), 16)
        self.assertTrue(report["completion_certified"])
        self.assertFalse(report["coverage_complete"])


if __name__ == "__main__":
    unittest.main()

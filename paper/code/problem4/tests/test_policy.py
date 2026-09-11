"""Coverage geometry and adversarial public-interface regression tests."""
from __future__ import annotations

import math
import random
import unittest

from problem4.policy import SearchPolicy, covering_triangles, directional_coverage_points, polar_covering_triangles, polar_coverage_points, triangle_contains


class _PublicOnlyClient:
    """Small independent oracle; production policy sees responses only."""

    def __init__(self, sources):
        self.__sources = {source[0]: source[1:] for source in sources}
        self.__cleared = set()
        self.position = (0.0, 0.0)
        self.current_channel = 1
        self.virtual_time_s = 0.0
        self.actions = 0
        self.negative_after_detection = 0
        self.__detected = set()

    def check_budget(self):
        if self.actions > 12000:
            raise RuntimeError("policy failed to terminate within the regression budget")
        return True

    def _move(self, point):
        self.check_budget()
        self.virtual_time_s += math.dist(point, self.position) / 5.0
        self.position = tuple(point)
        self.actions += 1

    def measure(self, point, channel):
        self._move(point)
        self.virtual_time_s += 5 + (self.current_channel != channel)
        self.current_channel = channel
        result = {"accepted": True, "measure_result": "no_signal"}
        if channel not in self.__cleared and channel in self.__sources:
            x, y, radius, direction, error_mode = self.__sources[channel]
            dx, dy = point[0] - x, point[1] - y
            distance = math.hypot(dx, dy)
            visible = direction is None or dx * math.cos(direction) + dy * math.sin(direction) >= -1e-9
            if distance <= radius + 1e-9 and visible:
                result["measure_result"] = "near" if distance <= 5 else "direction"
                if distance > 5:
                    # Fixed at each point, so repetition cannot reduce bias.
                    sign = 1.0 if error_mode == "positive" else -1.0
                    if error_mode == "spatial":
                        sign = math.sin(point[0] * .017 + point[1] * .011 + channel * .97)
                    result["svd_deg"] = round((math.degrees(math.atan2(-dy, -dx)) + sign) % 360, 2) % 360
                self.__detected.add(channel)
        if result["measure_result"] == "no_signal" and channel in self.__detected:
            self.negative_after_detection += 1
        result["virtual_time_s"] = self.virtual_time_s
        return result

    def clear(self, point, channel):
        self._move(point)
        success = channel not in self.__cleared and channel in self.__sources and math.dist(point, self.__sources[channel][:2]) <= 20 + 1e-9
        self.virtual_time_s += 5 if success else 3
        if success:
            self.__cleared.add(channel)
        return {"accepted": True, "clear_result": "success" if success else "no_target_in_range", "virtual_time_s": self.virtual_time_s}

    def cleared_count_for_test(self):
        return len(self.__cleared)


class DirectionalCoverageTests(unittest.TestCase):
    def test_triangles_have_strictly_subminimum_receive_diameter(self):
        triangles = covering_triangles()
        self.assertGreater(len(triangles), 0)
        for triangle in triangles:
            for i in range(3):
                self.assertAlmostEqual(math.dist(triangle[i], triangle[(i + 1) % 3]), 990, places=7)

    def test_boundary_and_interior_have_convex_hull_witnesses(self):
        # Numerical regression of the implementation, not the mathematical proof.
        triangles = polar_covering_triangles()
        rng = random.Random(80413)
        points = [(0.0, 0.0)]
        points += [(1800 * math.cos(i * math.tau / 360), 1800 * math.sin(i * math.tau / 360)) for i in range(360)]
        for _ in range(400):
            angle = rng.random() * math.tau
            radius = 1800 * math.sqrt(rng.random())
            points.append((radius * math.cos(angle), radius * math.sin(angle)))
        for point in points:
            witnesses = [triangle for triangle in triangles if triangle_contains(triangle, point)]
            self.assertTrue(witnesses, point)
            self.assertTrue(all(math.dist(point, vertex) < 1000 for vertex in witnesses[0]), point)

    def test_outward_boundary_sources_detectable(self):
        points = polar_coverage_points()
        self.assertTrue(any(math.hypot(*point) > 1800 for point in points))
        self.assertEqual(points[0], (0.0, 0.0))
        self.assertEqual(len(set(points)), len(points))
        for index in range(720):
            angle = index * math.tau / 720
            source = (1800 * math.cos(angle), 1800 * math.sin(angle))
            self.assertTrue(any(math.dist(source, point) < 1000 and (point[0] - source[0]) * math.cos(angle) + (point[1] - source[1]) * math.sin(angle) >= -1e-8 for point in points), index)

    def test_polar_cover_has_25_vertices_with_robust_margins(self):
        self.assertEqual(len(polar_coverage_points()), 25)
        self.assertGreater(1870 * math.cos(math.pi / 12), 1800)
        for triangle in polar_covering_triangles():
            self.assertLess(max(math.dist(a, b) for a in triangle for b in triangle), 984)

    def test_invalid_spacing_cannot_claim_coverage(self):
        for spacing in (0, -1, 1000, float("nan")):
            with self.assertRaises(ValueError):
                covering_triangles(spacing=spacing)


class MixedPolicyTests(unittest.TestCase):
    def test_paired_negative_probe_reduces_range_before_optical_clear(self):
        # The first bearing is received from the west. Both forward probes
        # overshoot a west-facing source: they are in range but on its back.
        client = _PublicOnlyClient([(1, 100.0, 0.0, 1000, math.pi, "positive")])
        policy = SearchPolicy()
        self.assertEqual(policy._measure(client, (0.0, 0.0), 1), "direction")
        self.assertTrue(policy._localize(1, client))
        self.assertGreater(policy.stats.get("paired_negative_clips", 0), 0)
        self.assertEqual(client.cleared_count_for_test(), 1)
        self.assertLess(client.actions, 20)

    def test_outward_boundary_minimum_radius_extreme_fixed_errors(self):
        sources = []
        for i in range(10):
            angle = (i + .37) * math.tau / 10
            sources.append((i * 2 + 1, 1800 * math.cos(angle), 1800 * math.sin(angle), 1000, angle, "positive" if i % 2 else "negative"))
        client = _PublicOnlyClient(sources)
        result = SearchPolicy().run(client)
        self.assertEqual(client.cleared_count_for_test(), 10)
        self.assertEqual(set(result["cleared_channels"]), {source[0] for source in sources})
        self.assertTrue(result["coverage_complete"])

    def test_mixed_clustered_and_tangent_directions(self):
        sources = []
        for i in range(16):
            angle = (i + .11) * math.tau / 16
            radius = 1740 if i % 3 else 25 + i * 5
            heading = None if i % 4 == 0 else angle + math.pi / 2 + (1e-7 if i % 2 else -1e-7)
            sources.append((i + 1, radius * math.cos(angle), radius * math.sin(angle), 1000 + (i % 4) * 160, heading, "spatial"))
        client = _PublicOnlyClient(sources)
        result = SearchPolicy().run(client)
        self.assertEqual(client.cleared_count_for_test(), 16)
        self.assertEqual(len(result["cleared_channels"]), 16)

    def test_wrong_problem_rejected(self):
        with self.assertRaises(ValueError):
            SearchPolicy(problem=3)


if __name__ == "__main__":
    unittest.main()

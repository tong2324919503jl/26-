"""Regression of the finite proof calculation, including geometric failures."""
from __future__ import annotations

import math
import unittest

from problem4.coverage import directional_cover_certificate, legacy_coverage_points, segment_cover_radius, static_coverage_points


class VoronoiSegmentTests(unittest.TestCase):
    def test_one_site_farthest_arc_is_enumerated(self):
        result = segment_cover_radius([(-500.0, 0.0)], (1.0, 0.0), 0)
        self.assertAlmostEqual(result["radius_bound_m"], 2300.0, places=5)

    def test_clipped_arc_endpoints_are_enumerated(self):
        result = segment_cover_radius([(500.0, 0.0)], (1.0, 0.0), 0)
        self.assertAlmostEqual(result["radius_bound_m"], math.hypot(1800, 500), places=5)

    def test_voronoi_bisector_and_circle_intersections(self):
        result = segment_cover_radius([(-500.0, 0.0), (500.0, 0.0)], (1.0, 0.0), -1801)
        self.assertAlmostEqual(result["radius_bound_m"], math.hypot(1800, 500), places=5)

    def test_narrow_circular_cap(self):
        result = segment_cover_radius([(1900.0, 0.0)], (1.0, 0.0), 1799)
        self.assertAlmostEqual(result["radius_bound_m"], math.sqrt(101 ** 2 + 1800 ** 2 - 1799 ** 2), places=5)


class DirectionalCertificateTests(unittest.TestCase):
    def test_frozen_23_point_layout_has_large_reception_margin(self):
        points = static_coverage_points()
        result = directional_cover_certificate(points)
        self.assertEqual(len(points), 23)
        self.assertTrue(result["certified"])
        self.assertEqual(result["pair_checks"], 494)
        self.assertLess(result["max_directional_radius_bound_m"], 985)
        self.assertGreater(result["hull_inradius_m"], 1800.9)

    def test_old_25_point_proof_is_reproduced(self):
        result = directional_cover_certificate(legacy_coverage_points())
        self.assertTrue(result["certified"])
        self.assertAlmostEqual(result["max_directional_radius_bound_m"], 983.598261, places=4)

    def test_no_single_frozen_point_can_be_silently_deleted(self):
        # Local irredundancy of this layout, not a lower bound on all layouts.
        points = static_coverage_points()
        for index in range(len(points)):
            with self.subTest(index=index):
                self.assertFalse(directional_cover_certificate(points[:index] + points[index + 1:])["certified"])

    def test_previously_failed_symmetric_23_points_are_rejected(self):
        n = 11
        points = [(0.0, 0.0)]
        points += [(1000 * math.cos((i + .5) * math.tau / n), 1000 * math.sin((i + .5) * math.tau / n)) for i in range(n)]
        points += [(1876 * math.cos(i * math.tau / n), 1876 * math.sin(i * math.tau / n)) for i in range(n)]
        self.assertFalse(directional_cover_certificate(points)["certified"])

    def test_rotation_and_order_do_not_change_the_proof(self):
        angle = .173
        c, s = math.cos(angle), math.sin(angle)
        points = [(x * c - y * s, x * s + y * c) for x, y in reversed(static_coverage_points())]
        result = directional_cover_certificate(points)
        self.assertTrue(result["certified"])
        self.assertAlmostEqual(result["max_directional_radius_bound_m"], 984.418184, places=3)

    def test_degenerate_hull_and_invalid_margin_are_rejected(self):
        self.assertFalse(directional_cover_certificate([(-2000, 0), (0, 0), (2000, 0)])["certified"])
        with self.assertRaises(ValueError):
            directional_cover_certificate(static_coverage_points(), margin_m=1e-8)


if __name__ == "__main__":
    unittest.main()

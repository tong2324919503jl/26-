from __future__ import annotations

from fractions import Fraction
import itertools
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from problem1.solve import (HalfPlane, Measurement, analyze_halfplanes, bearing_halfplanes,
                            direction, distance_squared, intersection_vertices,
                            load_measurements, localize, minimum_enclosing_circle)


class HalfPlaneGeometryTests(unittest.TestCase):
    def test_rectangle_exact_diameter_and_cover(self):
        result = analyze_halfplanes([HalfPlane(-1, 0, 0), HalfPlane(1, 0, 3),
                                     HalfPlane(0, -1, 0), HalfPlane(0, 1, 4)])
        self.assertEqual(result["status"], "polygon")
        self.assertEqual(result["diameter_m"], 5)
        self.assertEqual(result["minimum_enclosing_circle"]["center"], [1.5, 2.0])
        self.assertTrue(result["diameter_circle_covers"])

    def test_empty_parallel_constraints(self):
        result = analyze_halfplanes([HalfPlane(1, 0, 0), HalfPlane(-1, 0, -1)])
        self.assertEqual(result["status"], "empty")
        self.assertIsNone(result["diameter_m"])

    def test_nonempty_halfplane_without_vertices(self):
        result = analyze_halfplanes([HalfPlane(-1, 0, -3)])
        self.assertEqual(result["status"], "unbounded")
        self.assertEqual(result["vertices"], [])
        self.assertEqual(result["feasible_point"], [3.0, 0.0])

    def test_unbounded_strip_without_vertices(self):
        result = analyze_halfplanes([HalfPlane(-1, 0, -3), HalfPlane(1, 0, 4)])
        self.assertEqual(result["status"], "unbounded")
        self.assertTrue(result["diameter_is_infinite"])

    def test_unbounded_line_without_vertices(self):
        result = analyze_halfplanes([HalfPlane(-1, 0, -3), HalfPlane(1, 0, 3)])
        self.assertEqual(result["status"], "unbounded")
        self.assertEqual(result["feasible_point"], [3.0, 0.0])

    def test_unconstrained_plane(self):
        self.assertEqual(analyze_halfplanes([])["status"], "unbounded")

    def test_zero_normal_redundant_and_inconsistent(self):
        self.assertEqual(analyze_halfplanes([HalfPlane(0, 0, 1)])["status"], "unbounded")
        self.assertEqual(analyze_halfplanes([HalfPlane(0, 0, -1)])["status"], "empty")

    def test_bounded_single_point(self):
        result = analyze_halfplanes([HalfPlane(-1, 0, -2), HalfPlane(1, 0, 2),
                                     HalfPlane(0, -1, -3), HalfPlane(0, 1, 3)])
        self.assertEqual(result["status"], "point")
        self.assertEqual(result["vertices"], [[2, 3]])
        self.assertEqual(result["diameter_m"], 0)
        self.assertTrue(result["diameter_circle_covers"])

    def test_bounded_segment(self):
        result = analyze_halfplanes([HalfPlane(-1, 0, -2), HalfPlane(1, 0, 2),
                                     HalfPlane(0, -1, -3), HalfPlane(0, 1, 8)])
        self.assertEqual(result["status"], "segment")
        self.assertEqual(result["diameter_m"], 5)
        self.assertEqual(result["minimum_enclosing_circle"]["radius_m"], 2.5)

    def test_near_parallel_is_large_bounded_not_unbounded(self):
        epsilon = Fraction(1, 10**14)
        result = analyze_halfplanes([HalfPlane(0, -1, 0), HalfPlane(-epsilon, 1, 0),
                                     HalfPlane(epsilon, 1, 1)])
        self.assertEqual(result["status"], "polygon")
        self.assertEqual(result["diameter_m"], 1e14)
        self.assertEqual(len(result["vertices"]), 3)

    def test_acute_triangle_needs_more_than_half_diameter_radius(self):
        # Exact rational acute triangle (0,0), (4,0), (2,3).
        result = analyze_halfplanes([HalfPlane(0, -1, 0), HalfPlane(-3, 2, 0),
                                     HalfPlane(3, 2, 12)])
        self.assertEqual(result["diameter_m"], 4)
        self.assertFalse(result["diameter_circle_covers"])
        self.assertAlmostEqual(result["minimum_enclosing_circle"]["radius_m"], 13 / 6)

    def test_circle_contains_polygon_not_only_support_points(self):
        # An obtuse triangle has a two-point supported covering circle.
        vertices = [(Fraction(0), Fraction(0)), (Fraction(8), Fraction(0)),
                    (Fraction(2), Fraction(1))]
        circle = minimum_enclosing_circle(vertices)
        self.assertEqual(circle.radius_squared, 16)
        self.assertTrue(all(circle.contains(point) for point in vertices))

    def test_redundant_and_rescaled_constraints_leave_geometry_unchanged(self):
        base = [HalfPlane(-1, 0, 0), HalfPlane(1, 0, 3),
                HalfPlane(0, -1, 0), HalfPlane(0, 1, 4)]
        changed = [HalfPlane(p.a * 10**16, p.b * 10**16, p.c * 10**16) for p in base]
        changed.extend([HalfPlane(1, 1, 100), base[0]])
        self.assertEqual(analyze_halfplanes(base), analyze_halfplanes(changed))


class BearingModelTests(unittest.TestCase):
    def test_angles_wrap_consistently(self):
        self.assertEqual(direction(0), direction(360))
        self.assertEqual(direction(-1), direction(359))
        first = localize([Measurement(0, 100, 0), Measurement(100, 0, 90)])
        second = localize([Measurement(0, 100, 360), Measurement(100, 0, -270)])
        self.assertEqual(first, second)

    def test_north_and_east_follow_official_convention(self):
        planes = bearing_halfplanes([Measurement(0, 0, 90)])
        self.assertTrue(all(p.contains((Fraction(0), Fraction(10))) for p in planes))
        self.assertFalse(all(p.contains((Fraction(10), Fraction(0))) for p in planes))
        self.assertFalse(all(p.contains((Fraction(0), Fraction(-10))) for p in planes))

    def test_zero_error_is_ray_not_whole_line(self):
        result = localize([Measurement(0, 0, 0, 0), Measurement(-1, 0, 180, 0)])
        self.assertEqual(result["status"], "empty")
        segment = localize([Measurement(0, 0, 0, 0), Measurement(10, 0, 180, 0)])
        self.assertEqual(segment["status"], "segment")
        self.assertEqual(segment["diameter_m"], 10)

    def test_zero_error_perpendicular_rays_make_point(self):
        result = localize([Measurement(0, 1, 0, 0), Measurement(2, 0, 90, 0)])
        self.assertEqual(result["status"], "point")
        self.assertEqual(result["vertices"], [[2, 1]])

    def test_same_direction_sectors_are_unbounded(self):
        result = localize([Measurement(0, 0, 0), Measurement(0, 10, 0)])
        self.assertEqual(result["status"], "unbounded")

    def test_unbounded_does_not_become_finite_from_vertex_pairs(self):
        result = localize([Measurement(0, 0, 0)])
        self.assertEqual(result["vertices"], [[0, 0]])
        self.assertEqual(result["status"], "unbounded")
        self.assertIsNone(result["minimum_enclosing_circle"])

    def test_translation_preserves_size_even_at_large_coordinate_offset(self):
        original = localize([Measurement(0, 100, 0), Measurement(100, 0, 90)])
        moved = localize([Measurement(10**12, 10**12 + 100, 0),
                          Measurement(10**12 + 100, 10**12, 90)])
        self.assertEqual(original["diameter_m"], moved["diameter_m"])
        self.assertEqual(original["minimum_enclosing_circle"]["radius_m"],
                         moved["minimum_enclosing_circle"]["radius_m"])

    def test_positive_scale_preserves_relative_geometry(self):
        first = localize([Measurement(0, 100, 0), Measurement(100, 0, 90)])
        scaled = localize([Measurement(0, 700, 0), Measurement(700, 0, 90)])
        self.assertAlmostEqual(scaled["diameter_m"], first["diameter_m"] * 7)
        self.assertEqual(scaled["diameter_circle_covers"], first["diameter_circle_covers"])

    def test_adding_consistent_observation_cannot_increase_diameter(self):
        measurements = [Measurement(0, 100, 0), Measurement(100, 0, 90)]
        first = localize(measurements)
        extra = localize(measurements + [Measurement(200, 100, 180)])
        self.assertLessEqual(extra["diameter_m"], first["diameter_m"])

    def test_equilateral_counterexample_is_actual_bearing_intersection(self):
        document, measurements = load_measurements(ROOT / "problem1/examples/triangle_counterexample.json")
        result = localize(measurements)
        self.assertEqual(result["status"], "polygon")
        self.assertEqual(len(result["vertices"]), 3)
        self.assertAlmostEqual(result["diameter_m"], 20, places=9)
        self.assertAlmostEqual(result["minimum_enclosing_circle"]["radius_m"], 20 / math.sqrt(3), places=9)
        self.assertFalse(result["diameter_circle_covers"])
        source = tuple(Fraction(value) for value in document["reference_source"])
        self.assertTrue(all(p.contains(source) for p in bearing_halfplanes(measurements)))
        for measurement in measurements:
            distance = math.hypot(float(source[0]) - measurement.x, float(source[1]) - measurement.y)
            self.assertGreater(distance, 5)
            self.assertLess(distance, 1500)

    def test_random_consistent_sources_and_vertex_feasibility(self):
        rng = random.Random(20260910)
        for _ in range(12):
            source = (rng.uniform(-500, 500), rng.uniform(-500, 500))
            measurements = []
            for angle in (0, 90, 180):
                rad = math.radians(angle + rng.uniform(-10, 10))
                station = (source[0] - 300 * math.cos(rad), source[1] - 300 * math.sin(rad))
                bearing = math.degrees(math.atan2(source[1] - station[1], source[0] - station[0]))
                measurements.append(Measurement(*station, bearing + rng.uniform(-0.8, 0.8)))
            planes = bearing_halfplanes(measurements)
            exact_source = tuple(Fraction(value) for value in source)
            self.assertTrue(all(plane.contains(exact_source) for plane in planes))
            vertices = intersection_vertices(planes)
            self.assertTrue(vertices)
            self.assertTrue(all(plane.contains(v) for v in vertices for plane in planes))
            result = localize(measurements)
            self.assertEqual(result["status"], "polygon")
            circle = minimum_enclosing_circle(vertices)
            self.assertTrue(circle.contains(exact_source))
            # Any convex combination is a feasible interior point and its
            # distances cannot exceed the vertex diameter (independent check).
            midpoints = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                         for a, b in itertools.combinations(vertices, 2)]
            diameter_squared = max(distance_squared(a, b) for a in vertices for b in vertices)
            self.assertTrue(all(distance_squared(a, b) <= diameter_squared for a in midpoints for b in midpoints))

    def test_invalid_numbers_and_error_bounds_rejected(self):
        for bad in (float("nan"), float("inf"), True, "20"):
            with self.assertRaises(ValueError):
                Measurement(bad, 0, 0)
        for error in (-1, 90, 180):
            with self.assertRaises(ValueError):
                Measurement(0, 0, 0, error)

    def test_cli_runs_outside_repository_and_writes_valid_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "result.json"
            process = subprocess.run(
                [sys.executable, str(ROOT / "problem1/solve.py"),
                 "--input", "examples/two_station_crossing.json", "--output", str(destination)],
                cwd=temporary, capture_output=True, text=True, encoding="utf-8", check=False)
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "polygon")
            self.assertTrue(destination.with_suffix(".svg").is_file())


if __name__ == "__main__":
    unittest.main()

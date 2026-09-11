"""Mathematical regression tests for experimental 21-point coverage."""
import math
import unittest
from problem4.coverage import directional_cover_certificate
from problem4.experiments_v3.coverage_independent_check import check
from problem4.experiments_v3.coverage_ring_policy import ring_points


class Coverage21Tests(unittest.TestCase):
    def test_full_finite_certificate_and_independent_extrema(self):
        points=ring_points(12,8,997.32)
        self.assertEqual(len(points),21)
        result=check(points)
        self.assertTrue(result['certified'])
        self.assertEqual(len(result['pairs']),408)
        self.assertLess(result['independent_bound_m'],997.322)
        self.assertLess(result['maximum_difference_m'],1e-5)
        self.assertGreater(result['hull_inradius_m'],1801.99)

    def test_rotation_reflection_and_coordinate_rounding(self):
        points=ring_points(12,8,997.32)
        angle=.371
        transformed=[(round(math.cos(angle)*x+math.sin(angle)*y,6),
                      round(math.sin(angle)*x-math.cos(angle)*y,6)) for x,y in points]
        result=directional_cover_certificate(transformed,early_exit=False)
        self.assertTrue(result['certified'])
        self.assertLess(result['max_directional_radius_bound_m'],997.322)

    def test_no_unproved_single_deletion(self):
        points=ring_points(12,8,997.32)
        for index in range(len(points)):
            with self.subTest(index=index):
                self.assertFalse(directional_cover_certificate(points[:index]+points[index+1:])['certified'])

    def test_optical_hole_requires_an_actual_clear(self):
        points=ring_points(13,7,1009.35)
        self.assertFalse(directional_cover_certificate(points)['certified'])
        result=check(points,inner_radius=19.99)
        self.assertTrue(result['certified'])
        self.assertTrue(result['optical_clear_required'])
        self.assertLess(result['maximum_difference_m'],1e-5)


if __name__=='__main__':unittest.main()

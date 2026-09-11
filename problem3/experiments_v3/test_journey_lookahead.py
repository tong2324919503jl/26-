"""Independent geometry boundaries for development action planners."""
import math,unittest
from problem3.geometry import contains,distance,enclosing_circle,intersect_bearing
from problem3.experiments_v3.journey import safe_clear_points
from problem3.experiments_v3.lookahead import source_quadrature,negative_posterior


class TestSafeClearRegion(unittest.TestCase):
    def test_two_active_disks_give_closest_point(self):
        polygon=[(-5.,-5.),(5.,-5.),(5.,5.),(-5.,5.)]
        center,_=enclosing_circle(polygon);start=(-100.,0.)
        result=min(safe_clear_points(polygon,center,start),key=lambda p:distance(start,p))
        self.assertAlmostEqual(result[0],5.-math.sqrt(19.99**2-25.),places=7)
        self.assertAlmostEqual(result[1],0.,places=7)
        self.assertTrue(all(distance(result,p)<20. for p in polygon))

    def test_feasible_current_position_avoids_all_travel(self):
        polygon=[(-1.,-1.),(1.,-1.),(1.,1.),(-1.,1.)]
        center,_=enclosing_circle(polygon);start=(4.,7.)
        self.assertIn(start,safe_clear_points(polygon,center,start))

    def test_collinear_lens_boundary_is_not_radius_of_mec(self):
        polygon=[(-19.8,0.),(19.8,0.)]
        center,_=enclosing_circle(polygon);start=(-100.,0.)
        result=min(safe_clear_points(polygon,center,start),key=lambda p:distance(start,p))
        self.assertAlmostEqual(result[0],-.19,places=8)
        self.assertTrue(all(distance(result,p)<20. for p in polygon))


class TestRolloutGeometry(unittest.TestCase):
    def test_quadrature_nodes_inside_region_and_conditioned_radius(self):
        polygon=[(800.,-10.),(1200.,-10.),(1200.,10.),(800.,10.)]
        old=list(polygon);positive=[((0.,0.),0.)];negative=[((2400.,0.),)]
        nodes=source_quadrature(polygon,positive,[negative[0][0]],7)
        self.assertAlmostEqual(sum(n[0] for n in nodes),1.)
        for weight,p,lo,hi in nodes:
            self.assertTrue(contains(polygon,p));self.assertGreater(weight,0.)
            self.assertGreaterEqual(lo,max(1000.,distance(p,(0.,0.))))
            self.assertLessEqual(hi,min(1500.,distance(p,(2400.,0.))))
        self.assertEqual(old,polygon)

    def test_absence_keeps_real_source_at_range_boundary(self):
        polygon=[(-2000.,-2000.),(2000.,-2000.),(2000.,2000.),(-2000.,2000.)]
        source=(123.4,-78.9);p=(source[0]-1000.,source[1]);q=(source[0]+1000.0001,source[1])
        posterior=negative_posterior(polygon,q,[(p,0.)])
        self.assertTrue(contains(posterior,source))
        self.assertFalse(contains(posterior,(source[0]+1.,source[1])))

    def test_fixed_extreme_and_rounding_sources_are_retained(self):
        polygon=[(-2000.,-2000.),(2000.,-2000.),(2000.,2000.),(-2000.,2000.)]
        point=(100.,-75.)
        for angle in (0.0049,89.9951,179.9951,359.9951):
            source=(point[0]+1000*math.cos(math.radians(angle)),point[1]+1000*math.sin(math.radians(angle)))
            for noise in (-1.,0.,1.):
                reading=round((angle+noise)%360,2)
                self.assertTrue(contains(intersect_bearing(polygon,point,reading,1.005),source))


if __name__=='__main__':unittest.main()

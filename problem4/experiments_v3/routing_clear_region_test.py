"""Geometric checks for the optional nearest guaranteed clearance stop."""
import math,random,unittest
from problem3.geometry import distance
from problem4.experiments_v3.routing_clear_region import closest_guaranteed_clear

class ClearProjectionTests(unittest.TestCase):
    def test_singleton_and_feasible_origin(self):
        self.assertEqual(closest_guaranteed_clear([(0.,0.)],(3.,4.),20.),(3.,4.))
        self.assertEqual(closest_guaranteed_clear([(0.,0.)],(30.,0.),20.),(20.,0.))
    def test_two_active_disks(self):
        point=closest_guaranteed_clear([(-10.,0.),(10.,0.)],(0.,100.),20.)
        self.assertAlmostEqual(point[0],0.,places=8)
        self.assertAlmostEqual(point[1],math.sqrt(300),places=8)
    def test_empty_intersection(self):
        self.assertIsNone(closest_guaranteed_clear([(-21.,0.),(21.,0.)],(0.,100.),20.))
    def test_random_feasible_and_sampled_arc_optimality(self):
        rng=random.Random(520041)
        for _ in range(64):
            angles=sorted(rng.random()*math.tau for _ in range(6))
            poly=[(rng.uniform(2,12)*math.cos(a),rng.uniform(2,12)*math.sin(a)) for a in angles]
            origin=(rng.uniform(40,100),rng.uniform(-100,100))
            point=closest_guaranteed_clear(poly,origin,20.)
            self.assertIsNotNone(point)
            self.assertLessEqual(max(distance(point,v) for v in poly),20.+1e-7)
            value=distance(point,origin)
            for vertex in poly:
                for k in range(120):
                    theta=k*math.tau/120;q=(vertex[0]+20*math.cos(theta),vertex[1]+20*math.sin(theta))
                    if all(distance(q,v)<=20. for v in poly):
                        self.assertLessEqual(value,distance(q,origin)+1e-7)

if __name__=='__main__':unittest.main()

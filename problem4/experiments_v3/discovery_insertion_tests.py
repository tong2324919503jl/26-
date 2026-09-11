"""Checks for discovery precedence and the fixed-first route constructions."""
import math,random,unittest
from problem3.geometry import distance
from problem4.experiments_v3.discovery_insertion import fixed_first_route,insertion_terms,get_class

class DiscoveryInsertionTests(unittest.TestCase):
    def test_service_cannot_precede_first_detection(self):
        goals=[(0.,0.),(1000.,0.),(1000.,1000.)]
        matrix=[[distance(a,b) for b in goals] for a in goals]
        g=(500.,0.);distances=[distance(g,p) for p in goals]
        delayed,latency=insertion_terms((0,1,2),matrix,{0,1},[(distances,{1})])
        early,_=insertion_terms((0,1,2),matrix,{0,1},[(distances,{0})])
        self.assertAlmostEqual(delayed,500+math.sqrt(1250000)-1000-40)
        self.assertEqual(latency,2.)
        self.assertEqual(early,0.)

    def test_end_neighborhood_has_only_one_leg_allowance(self):
        extra,latency=insertion_terms((0,),[[0.]],{0},[([100.],{0})])
        self.assertEqual(extra,80.)
        self.assertEqual(latency,1.)

    def test_all_visits_and_first_goal_are_retained(self):
        rng=random.Random(660011)
        for n in (2,5,12,25):
            points=[(rng.uniform(-100,100),rng.uniform(-100,100)) for _ in range(n+1)]
            matrix=[[distance(a,b) for b in points] for a in points]
            for first in range(n):
                route=fixed_first_route(first,matrix)
                self.assertEqual(route[0],first)
                self.assertEqual(sorted(route),list(range(n)))

    def test_bounded_source_count_expectation(self):
        policy=get_class('discovery')()
        for known in range(17):
            for unseen in (1,len(policy.samples)//2,len(policy.samples)):
                expectation=policy._expected_unknown(known,unseen)
                self.assertGreaterEqual(expectation,max(0,10-known)-1e-9)
                self.assertLessEqual(expectation,16-known+1e-9)

if __name__=='__main__':unittest.main()

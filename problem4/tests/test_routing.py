"""Route transformations preserve all visits and improve real geometric cost."""
import math
import random
import unittest
from types import SimpleNamespace
from problem3.geometry import distance
from problem4.legacy_policy import SearchPolicy as LegacyPolicy
from problem4.routing import RoutingMixin,nearest_seed,two_opt,or_opt,route_length

class RoutingTests(unittest.TestCase):
    def test_oropt_escapes_a_two_opt_local_minimum(self):
        points=[(-814,603),(1186,-783),(408,-83),(-751,755),(1020,-1188),
                (-941,-456),(638,597),(15,1),(-322,-1328),(271,-718),
                (1489,668),(975,1237),(-1134,652)]
        matrix=[[distance(a,b) for b in points] for a in points]
        local=two_opt(nearest_seed(matrix),matrix)
        escaped=or_opt(local,matrix)
        self.assertEqual(sorted(local),sorted(escaped))
        self.assertGreater(route_length(local,matrix)-route_length(escaped,matrix),60)
        self.assertEqual(local,two_opt(local,matrix))

    def test_random_routes_preserve_visits_and_never_increase_length(self):
        rng=random.Random(261109)
        for count in (0,1,3,12,30):
            for _ in range(4):
                points=[(rng.uniform(-2000,2000),rng.uniform(-2000,2000)) for _ in range(count+1)]
                matrix=[[distance(a,b) for b in points] for a in points]
                seed=nearest_seed(matrix);first=two_opt(seed,matrix);last=or_opt(first,matrix)
                self.assertEqual(sorted(last),list(range(count)))
                self.assertLessEqual(route_length(last,matrix),route_length(first,matrix)+1e-7)
                self.assertLessEqual(route_length(first,matrix),route_length(seed,matrix)+1e-7)

    def test_sixteen_detected_stops_scanning_without_claiming_completion(self):
        class Policy(RoutingMixin,LegacyPolicy):pass
        policy=Policy()
        for channel in range(1,17):
            angle=channel*math.tau/16;x,y=800*math.cos(angle),800*math.sin(angle)
            policy.regions[channel]=[(x-1,y-1),(x+1,y-1),(x,y+1)]
        pending=[(1800.,0.),(0.,1800.),(-1800.,0.)]
        goal=policy._route_goal(SimpleNamespace(position=(0.,0.)),pending)
        self.assertEqual(goal[1],'clear')
        self.assertEqual(len(pending),3)
        self.assertFalse(policy._result('test',False)['completion_certified'])

if __name__=='__main__':unittest.main()

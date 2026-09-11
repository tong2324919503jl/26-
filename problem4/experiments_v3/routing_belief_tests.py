"""Independent checks for continuous belief sampling (no hidden test data)."""
from __future__ import annotations
import math,random,unittest
from problem3.geometry import distance
from problem4.experiments_v3.belief_sampling import (
    ConditionalRolloutPolicy,orientation_intervals,
)
from problem4.experiments_v3.rollout import received

def make_policy(polygon,positive,negative=(),failed=()):
    policy=ConditionalRolloutPolicy()
    policy.regions={1:polygon}
    policy.observations={1:[(p,math.degrees(math.atan2(-p[1],-p[0]))%360) for p in positive]}
    policy._negative_history={1:list(negative)}
    policy._belief_failed_clears={1:list(failed)}
    return policy

class OrientationIntervalTests(unittest.TestCase):
    def test_full_half_and_conflicting_intervals(self):
        self.assertAlmostEqual(sum(b-a for a,b in orientation_intervals((0,0),[],[])),math.tau)
        self.assertAlmostEqual(sum(b-a for a,b in orientation_intervals((0,0),[(1,0)],[])),math.pi)
        self.assertEqual(orientation_intervals((0,0),[(1,0)],[(1,0)]),[])
        self.assertEqual(orientation_intervals((0,0),[],[(0,0)]),[])

    def test_thin_wrapped_intervals(self):
        for degrees in (1.,.1,.01,.00001):
            angles=(-90+degrees/2,90-degrees/2)
            positive=[(100*math.cos(math.radians(a)),100*math.sin(math.radians(a))) for a in angles]
            arcs=orientation_intervals((0,0),positive,[(-100,0)])
            self.assertAlmostEqual(sum(b-a for a,b in arcs),math.radians(degrees),places=12)
            self.assertEqual(len(arcs),2)

    def test_random_direct_dot_products(self):
        rng=random.Random(790042)
        for _ in range(128):
            source=(rng.uniform(-100,100),rng.uniform(-100,100))
            points=[(rng.uniform(-200,200),rng.uniform(-200,200)) for _ in range(6)]
            positive,negative=points[:3],points[3:]
            arcs=orientation_intervals(source,positive,negative)
            for k in range(512):
                angle=(k+.347)*math.tau/512
                dots=[(p[0]-source[0])*math.cos(angle)+(p[1]-source[1])*math.sin(angle) for p in points]
                if min(abs(d) for d in dots)<1e-8:continue
                direct=all(v>0 for v in dots[:3]) and all(v<0 for v in dots[3:])
                interval=any(a<=angle<=b for a,b in arcs)
                self.assertEqual(interval,direct)

class ConditionalSamplingTests(unittest.TestCase):
    def test_radius_and_omnidirectional_mass(self):
        policy=make_policy([(0.,0.)],[(1200.,0.)])
        rng=random.Random(90171)
        samples=[policy._known_sample(1,rng) for _ in range(1600)]
        self.assertTrue(all(1200<=s['radius']<=1500 for s in samples))
        self.assertAlmostEqual(sum(s['radius'] for s in samples)/len(samples),1350,delta=7.)
        self.assertAlmostEqual(sum(s['orientation_deg'] is None for s in samples)/len(samples),2/3,delta=.04)

    def test_negative_radius_cut_and_failed_clear(self):
        policy=make_policy([(0.,0.)],[(1000.,0.)],[(1100.,0.)])
        rng=random.Random(91911)
        for _ in range(128):
            sample=policy._known_sample(1,rng)
            self.assertLess(sample['radius'],1100.)
            self.assertTrue(received(sample,(1000.,0.)))
            self.assertFalse(received(sample,(1100.,0.)))
        policy=make_policy([(0.,-.1),(100.,-.1),(100.,.1),(0.,.1)],[(-500.,0.)],failed=[(20.,0.)])
        for _ in range(128):
            sample=policy._known_sample(1,rng)
            self.assertGreater(distance((sample['x'],sample['y']),(20.,0.)),20.)

    def test_position_mass_is_not_renormalized_uniform(self):
        policy=make_policy([(1200.,-.001),(1490.,-.001),(1490.,.001),(1200.,.001)],[(0.,0.)])
        rng=random.Random(150003)
        positions=[policy._known_sample(1,rng)['x'] for _ in range(1800)]
        # For this thin rectangle the exact density is proportional to1500-x.
        # Its mean is1299.785... rather than the unweighted midpoint1345.
        a,b=1200.,1490.
        norm=1500*(b-a)-(b*b-a*a)/2
        expected=(750*(b*b-a*a)-(b**3-a**3)/3)/norm
        self.assertAlmostEqual(sum(positions)/len(positions),expected,delta=7.)

if __name__=='__main__':unittest.main()

"""Independent channel coverage and negative-shadow geometry checks."""
import math,random,unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from problem4.experiments_v3.routing_channel_audit import necessity_witnesses
from problem4.experiments_v3.routing_channel_split import count_posterior,get_class
from problem4.experiments_v3.routing_channel_reads import get_class as read_class

class ChannelTests(unittest.TestCase):
    def test_every_fixed_station_has_unique_receiver_witness(self):
        witnesses=necessity_witnesses();self.assertEqual(len(witnesses),21)
        self.assertTrue(all(r['receiving_stations']==[r['station_index']] for r in witnesses))

    def test_source_count_posterior_matches_equal_channel_formula(self):
        for known in range(10,16):
            for unseen in (.01,.2,.8):
                result=count_posterior(known,[unseen]*(20-known))
                weights={n:math.comb(n,known)*unseen**(n-known) for n in range(known,17)}
                total=sum(weights.values())
                for n,value in result.items():self.assertAlmostEqual(value,weights[n]/total,places=12)

    def test_one_channels_missing_station_prevents_certificate(self):
        policy=get_class('channel_split')()
        policy._channel_fixed=tuple(policy.coverage_points())
        policy._channel_points={ch:set(policy._channel_fixed) for ch in range(1,21)}
        self.assertTrue(policy._channel_certificate())
        policy._channel_points[20].remove(policy._channel_fixed[6])
        self.assertFalse(policy._channel_certificate())
        self.assertEqual(policy._missing_points(),[policy._channel_fixed[6]])

    def test_negative_shadow_agrees_with_continuous_direction_model(self):
        policy=read_class('channel_reads_shadow')()
        policy.regions={1:[(-10.,90.),(10.,90.),(10.,110.),(-10.,110.)]}
        policy.observations={1:[((-100.,0.),0.)]};policy._negative_history={1:[(100.,0.)]}
        proposed=(200.,0.)
        self.assertTrue(policy._provably_negative(1,proposed))
        self.assertFalse(policy._provably_negative(1,(0.,200.)))
        rng=random.Random(443172)
        for _ in range(200):
            source=(rng.uniform(-10,10),rng.uniform(90,110))
            for k in range(1024):
                angle=(k+.123)*math.tau/1024
                dot=lambda p:(p[0]-source[0])*math.cos(angle)+(p[1]-source[1])*math.sin(angle)
                if dot((-100.,0.))>=0 and dot((100.,0.))<0:self.assertLess(dot(proposed),0.)

if __name__=='__main__':unittest.main()

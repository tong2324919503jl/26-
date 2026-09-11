"""Independent geometric and controller-bound checks for unionmass repair."""
import math
import random
import unittest
from problem3.geometry import contains, distance
from problem4.optical_repair import subtract_failed_disk, fragment_centers, UnionmassMixin


class UnionGeometryTests(unittest.TestCase):
    def test_failed_disk_subtraction_retains_every_outside_point(self):
        # Dense rings straddle the physical boundary. Testing two overlapping
        # failed disks also exercises nested clipping and disconnected pieces.
        polygon=[(-60.,-25.),(60.,-25.),(60.,25.),(-60.,25.)]
        failures=[(-9.,0.),(9.,0.)];fragments=[polygon]
        for failed in failures:
            fragments=[p for f in fragments for p in subtract_failed_disk(f,failed)]
        points=[(x/4,y/4) for x in range(-240,241,3) for y in range(-100,101,3)]
        points.extend((q[0]+r*math.cos(k*math.tau/720),q[1]+r*math.sin(k*math.tau/720))
                      for q in failures for r in (19.999999,20.,20.000001) for k in range(720))
        checked=0
        for point in points:
            if contains(polygon,point) and all(distance(point,q)>20. for q in failures):
                checked+=1
                self.assertTrue(any(contains(f,point) for f in fragments),point)
        self.assertGreater(checked,5000)
        self.assertFalse(any(contains(f,(0.,0.)) for f in fragments))

    def test_fragment_cover_handles_thin_rotated_and_degenerate_shapes(self):
        random.seed(913)
        for _ in range(100):
            angle=random.uniform(0,math.tau);c,s=math.cos(angle),math.sin(angle)
            # The helper aligns the strip to its longest chord. A rectangle's
            # diagonal can nearly double its perpendicular strip width, hence
            # choose a thin enough rectangle to satisfy the helper's gate.
            length=random.uniform(40.,300.);width=random.uniform(0.,15.)
            rotate=lambda x,y:(1730.+x*c-y*s,-711.+x*s+y*c)
            poly=[rotate(-length/2,-width/2),rotate(length/2,-width/2),rotate(length/2,width/2),rotate(-length/2,width/2)]
            centers=[p for p,_ in fragment_centers(poly)]
            self.assertTrue(centers)
            for i in range(41):
                for j in range(9):
                    point=rotate(-length/2+length*i/40,-width/2+width*j/8)
                    self.assertLessEqual(min(distance(point,p) for p in centers),20.)
        for poly in ([(1.,2.)],[(-50.,0.),(50.,0.)]):
            centers=fragment_centers(poly)
            self.assertTrue(centers)

    def test_failed_optional_actions_are_bounded_and_never_claim_success(self):
        class Backend:
            def __init__(self):
                self.regions={1:[(-5.,-5.),(5.,-5.),(5.,5.),(-5.,5.)]};self.stats={};self.calls=0
            def _clear(self,client,point,ch):self.calls+=1;client.position=point;return False
        class Repair(UnionmassMixin,Backend):
            # Force an available proposal even after physical contradictions:
            # this verifies the action cap independently of geometry shrinking.
            def _union_point(self,ch,client):
                return (float(self.calls),0.) if self._union_counts.get(ch,0)<self.union_maximum else None
        client=type('PublicClient',(),{'position':(0.,0.)})();p=Repair()
        self.assertFalse(p._clear(client,(0.,0.),1))
        self.assertEqual(p.calls,17)
        self.assertEqual(p._union_counts[1],16)


if __name__=='__main__':unittest.main()


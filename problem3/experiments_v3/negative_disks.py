"""P3: negative readings exclude guaranteed reception disks, without a prior."""
import math
from problem3.geometry import clip_halfplane,distance
from problem4.localization import _convex_hull
from problem3.experiments_v3.candidate import SearchPolicy as Candidate
from problem3.experiments_v3.radial_adaptive import InnerAnnularPolicy


def outside_inner_disk(polygon,center,sides=48):
    inside=list(polygon);outside=[]
    # This inscribed polygon is strictly contained in the guaranteed disk;
    # retaining its complement cannot exclude any truly absent source.
    radius=999.999*math.cos(math.pi/sides)
    for i in range(sides):
        a,b=math.cos(math.tau*i/sides),math.sin(math.tau*i/sides)
        c=a*center[0]+b*center[1]+radius
        outside.extend(clip_halfplane(inside,-a,-b,-c))
        inside=clip_halfplane(inside,a,b,c)
        if not inside:break
    return _convex_hull(outside)


class NegativeDiskMixin:
    negative_disk_sides=48
    def _measure(self,client,point,ch):
        result=super()._measure(client,point,ch)
        if ch not in self.regions or ch in self.cleared:return result
        polygon=self.regions[ch]
        for q in getattr(self,'negative_history',{}).get(ch,[]):
            # Skip guaranteed distant polygons by a cheap enclosing rectangle.
            xmin=min(p[0] for p in polygon);xmax=max(p[0] for p in polygon)
            ymin=min(p[1] for p in polygon);ymax=max(p[1] for p in polygon)
            if distance(q,(max(xmin,min(xmax,q[0])),max(ymin,min(ymax,q[1]))))>=1000:continue
            polygon=outside_inner_disk(polygon,q,self.negative_disk_sides)
            if not polygon:raise RuntimeError('Negative guaranteed disk contradicts positive bearings')
        self.regions[ch]=polygon
        return result


class NegativeDiskPolicy(NegativeDiskMixin,Candidate):pass
class AnnularNegativePolicy(NegativeDiskMixin,InnerAnnularPolicy):pass

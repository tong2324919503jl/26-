"""Stop at the nearest position guaranteeing optical clearance of a region."""
from __future__ import annotations
import math
from problem3.geometry import distance,enclosing_circle
from problem4.experiments_v3.coverage_ring_policy import Ring12CoverPolicy
from problem4.experiments_v3.routing_shared import SharedBaselineMixin

def closest_guaranteed_clear(polygon,origin,radius=19.999):
    """Project onto the intersection of equal-radius disks around vertices.

    A closest feasible point is the input point, a radial projection onto one
    active circle, or the intersection of two active circles. Convexity then
    certifies every source in the polygon is within the optical radius.
    """
    def valid(q):return all(distance(q,v)<=radius+1e-8 for v in polygon)
    if valid(origin):return origin
    center,uncertainty=enclosing_circle(polygon)
    if uncertainty>radius:return None
    choices=[center]
    for v in polygon:
        d=distance(v,origin)
        if d:
            point=(v[0]+radius*(origin[0]-v[0])/d,v[1]+radius*(origin[1]-v[1])/d)
            if valid(point):choices.append(point)
    for i,a in enumerate(polygon):
        for b in polygon[:i]:
            d=distance(a,b)
            if not 1e-9<d<=2*radius:continue
            mid=((a[0]+b[0])/2,(a[1]+b[1])/2)
            height=math.sqrt(max(0.,radius*radius-d*d/4));ux,uy=-(b[1]-a[1])/d,(b[0]-a[0])/d
            for sign in (-1,1):
                point=(mid[0]+sign*height*ux,mid[1]+sign*height*uy)
                if valid(point):choices.append(point)
    return min(choices,key=lambda q:distance(origin,q))

class ClearanceRegionMixin:
    clear_region_radius=19.999
    def _clear(self,client,point,channel):
        if channel in self.regions and channel not in self.cleared:
            polygon=self.regions[channel]
            center,uncertainty=enclosing_circle(polygon)
            if uncertainty<=self.clear_region_radius:
                candidate=closest_guaranteed_clear(polygon,client.position,self.clear_region_radius)
                if candidate is not None and distance(client.position,candidate)<distance(client.position,point):
                    self.stats['clear_region_stops']=self.stats.get('clear_region_stops',0)+1
                    point=candidate
        return super()._clear(client,point,channel)

def get_class(name):
    return type(name,(SharedBaselineMixin,ClearanceRegionMixin,Ring12CoverPolicy),dict(shared_min_channels=1,shared_radius_m=50.,shared_fresh_only=True))

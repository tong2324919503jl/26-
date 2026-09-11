"""Soft online radial transfer using only successful clearance positions.

No candidate is removed and no completion decision uses this prior. The
existing bearing/radius constraints and optical fallback remain authoritative.
"""
from __future__ import annotations
import math,statistics
from problem3.geometry import distance,enclosing_circle,polygon_centroid
from problem4.routing import two_opt,or_opt,nearest_seed,insertion_seed,route_length
from problem3.experiments_v3.candidate import SearchPolicy as Candidate
from problem3.experiments_v3.negative_disks import AnnularNegativePolicy


class ShapePriorMixin:
    shape_min_count=4
    shape_max_spread=180.
    shape_min_band=60.
    shape_uniform_weight=.1
    shape_empty_center_only=False
    def _clear(self,client,point,channel):
        result=super()._clear(client,point,channel)
        if result:
            if not hasattr(self,'_shape_clears'):self._shape_clears={}
            self._shape_clears[channel]=client.position
        return result
    def _shape_parameters(self):
        positions=list(getattr(self,'_shape_clears',{}).values())
        if len(positions)<self.shape_min_count:return None
        if self.shape_empty_center_only and any(distance(p,(0.,0.))<1e-6 for observations in self.observations.values() for p,_ in observations):return None
        radii=[math.hypot(*p) for p in positions]
        if max(radii)-min(radii)>self.shape_max_spread:return None
        return statistics.median(radii),max(self.shape_min_band,statistics.pstdev(radii)+20.)
    def _shape_estimate(self,channel):
        polygon=self.regions[channel]
        prior=self._shape_parameters()
        if prior is None or enclosing_circle(polygon)[1]<100:return polygon_centroid(polygon)
        if not hasattr(self,'_shape_cache'):self._shape_cache={}
        key=(tuple(polygon),prior)
        if self._shape_cache.get(channel,(None,))[0]==key:return self._shape_cache[channel][1]
        triangles=[(polygon[0],polygon[i],polygon[i+1]) for i in range(1,len(polygon)-1)]
        for _ in range(2):
            refined=[]
            for a,b,c in triangles:
                ab=((a[0]+b[0])/2,(a[1]+b[1])/2);bc=((b[0]+c[0])/2,(b[1]+c[1])/2);ca=((c[0]+a[0])/2,(c[1]+a[1])/2)
                refined.extend(((a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)))
            triangles=refined
        mean,band=prior;sx=sy=total=0.
        for a,b,c in triangles:
            p=((a[0]+b[0]+c[0])/3,(a[1]+b[1]+c[1])/3)
            area=abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))
            w=area*(self.shape_uniform_weight+math.exp(-.5*((math.hypot(*p)-mean)/band)**2))
            sx+=w*p[0];sy+=w*p[1];total+=w
        estimate=(sx/total,sy/total) if total else polygon_centroid(polygon)
        self._shape_cache[channel]=(key,estimate)
        return estimate
    def _probe_point(self,channel,client,probe_index):
        if self._shape_parameters() is None:return super()._probe_point(channel,client,probe_index)
        polygon=self.regions[channel]
        if enclosing_circle(polygon)[1]<100:return super()._probe_point(channel,client,probe_index)
        point=self._shape_estimate(channel);anchor,angle=self.observations[channel][-1]
        theta=math.radians(angle);side=(-math.sin(theta),math.cos(theta))
        width=max(15.,min(100.,self.probe_fraction*distance(anchor,point)))
        candidates=[(point[0]+s*width*side[0],point[1]+s*width*side[1]) for s in (-1,1)]
        self.stats['shape_guided_probes']=self.stats.get('shape_guided_probes',0)+1
        return min(candidates,key=lambda p:distance(client.position,p))
    def _route_goal(self,client,pending):
        original=super()._route_goal(client,pending)
        if self._shape_parameters() is None:return original
        if len(set(self.regions)|self.cleared)==16:pending=[]
        goals=[(p,'scan',i) for i,p in enumerate(pending)]
        goals += [(self._shape_estimate(ch),'clear',ch) for ch in self.regions if ch not in self.cleared]
        points=[g[0] for g in goals]+[client.position];matrix=[[distance(a,b) for b in points] for a in points]
        routes=[two_opt(nearest_seed(matrix),matrix),two_opt(insertion_seed(matrix),matrix)]
        route=or_opt(min(routes,key=lambda r:route_length(r,matrix)),matrix)
        self._route_keys=[self._goal_key(goals[i]) for i in route]
        return goals[route[0]]


class ShapePolicy(ShapePriorMixin,Candidate):pass
class AnnularShapePolicy(ShapePriorMixin,AnnularNegativePolicy):pass

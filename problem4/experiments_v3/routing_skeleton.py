"""Stable discovery skeleton with service inserted at a cheap future edge.

Only candidate regions and public observations enter scheduling. The original
scan points are retained and all deferred sources use the complete localizer.
"""
from __future__ import annotations
import math
from problem3.geometry import distance,enclosing_circle,polygon_centroid
from problem4.routing import nearest_seed,insertion_seed,two_opt,or_opt,route_length
from problem4.experiments_v3.coverage_ring_policy import Ring12CoverPolicy
from problem4.experiments_v3.routing_shared import SharedBaselineMixin
from problem4.experiments_v3.routing import EnrouteMixin

class SkeletonRoutingMixin:
    skeleton_order='optimized'
    skeleton_detour_limit=300.
    skeleton_best_slack=50.
    skeleton_max_radius=math.inf
    skeleton_replan=False
    skeleton_clear_penalty=0.

    def _scan_order(self,pending,origin):
        n=len(pending)
        if self.skeleton_order in ('outer','inner'):
            rows=[]
            for p in pending:
                level=0 if math.hypot(*p)<10 else (1 if math.hypot(*p)>1500 else 2)
                if self.skeleton_order=='inner' and level:level=3-level
                rows.append((level,math.atan2(p[1],p[0]),p))
            rows.sort();ordered=[r[2] for r in rows]
            return ordered
        points=pending+[origin];matrix=[[distance(a,b) for b in points] for a in points]
        angular=sorted(range(n),key=lambda i:math.atan2(pending[i][1],pending[i][0]))
        seeds=[nearest_seed(matrix),insertion_seed(matrix),angular,list(reversed(angular))]
        route=min((or_opt(two_opt(seed,matrix),matrix) for seed in seeds),key=lambda r:route_length(r,matrix))
        return [pending[i] for i in route]

    def _route_goal(self,client,pending):
        if not pending or len(set(self.regions)|self.cleared)==16:
            return super()._route_goal(client,pending)
        if self.skeleton_replan or not hasattr(self,'_skeleton_points'):
            self._skeleton_points=self._scan_order(pending,client.position)
        remaining=set(pending);order=[p for p in self._skeleton_points if p in remaining]
        if not order:raise RuntimeError('Discovery skeleton lost a pending coverage point')
        goal=order[0];candidates=[]
        for ch,poly in self.regions.items():
            if ch in self.cleared:continue
            center,uncertainty=enclosing_circle(poly)
            if uncertainty>self.skeleton_max_radius:continue
            center=polygon_centroid(poly)
            detour=distance(client.position,center)+distance(center,goal)-distance(client.position,goal)
            if detour>self.skeleton_detour_limit:continue
            best=detour
            for a,b in zip(order,order[1:]):
                best=min(best,distance(a,center)+distance(center,b)-distance(a,b))
            best=min(best,distance(order[-1],center))
            if detour>best+self.skeleton_best_slack:continue
            score=detour+.05*distance(client.position,center)+self.skeleton_clear_penalty*uncertainty
            candidates.append((score,center,ch))
        if candidates:
            _,point,ch=min(candidates,key=lambda x:x[0]);return point,'clear',ch
        return goal,'scan',pending.index(goal)

def get_class(name):
    tokens=set(name.split('_'));attrs=dict(shared_min_channels=1,shared_radius_m=50.,shared_fresh_only=True)
    if 'outer' in tokens:attrs['skeleton_order']='outer'
    if 'inner' in tokens:attrs['skeleton_order']='inner'
    if 'narrow' in tokens:attrs['skeleton_max_radius']=80.
    if 'wide' in tokens:attrs['skeleton_detour_limit']=600.
    if 'unbounded' in tokens:attrs['skeleton_detour_limit']=math.inf
    if 'strict' in tokens:attrs['skeleton_detour_limit']=100.
    if 'greedy' in tokens:attrs['skeleton_best_slack']=math.inf
    if 'replan' in tokens:attrs['skeleton_replan']=True
    if 'enroute' in tokens:
        bases=(SharedBaselineMixin,SkeletonRoutingMixin,EnrouteMixin,Ring12CoverPolicy)
        attrs.update(enroute_min_radius=120.,enroute_min_gain=100.)
    else:bases=(SharedBaselineMixin,SkeletonRoutingMixin,Ring12CoverPolicy)
    return type(name,bases,attrs)

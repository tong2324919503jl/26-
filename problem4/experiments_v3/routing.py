"""V3 scheduling experiments: deferred service and bearings along paid travel.

Only public observations/candidate polygons are used. All termination rules and
optical fallbacks remain inherited; priors and scores only choose next actions.
"""
from __future__ import annotations
import math
from problem3.geometry import distance,enclosing_circle,polygon_centroid
from problem4.policy import SearchPolicy as ProductionPolicy
from problem4.routing import RoutingMixin


def line_point(a,b,t):return (a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1]))


def predicted_radius(polygon,anchor,point,error=1.005):
    center,radius=enclosing_circle(polygon)
    a=(anchor[0]-center[0],anchor[1]-center[1]);b=(point[0]-center[0],point[1]-center[1])
    da,db=math.hypot(*a),math.hypot(*b)
    sine=abs(a[0]*b[1]-a[1]*b[0])/(da*db) if da*db else 0.
    if sine<.03:return radius,0.
    estimate=min(radius,math.tan(math.radians(error))*(da+db)/sine)
    probability=max(0.,min(1.,(1500-db)/500))
    angle=math.acos(max(-1.,min(1.,(a[0]*b[0]+a[1]*b[1])/(da*db)))) if da*db else math.pi
    probability*=1-.5*angle/math.pi
    return estimate,probability


class EnrouteMixin:
    enroute_min_radius=60.
    enroute_min_distance=150.
    enroute_min_gain=50.
    enroute_max_probes=6
    enroute_compare_destination=False
    enroute_clear=False
    def _measure(self,client,point,channel):
        if not getattr(self,'_enroute_active',False):self._collect_enroute(client,point,channel)
        return super()._measure(client,point,channel)
    def _clear(self,client,point,channel):
        if not getattr(self,'_enroute_active',False):self._collect_enroute(client,point,channel)
        return super()._clear(client,point,channel)
    def _collect_enroute(self,client,destination,active_channel):
        start=client.position;length=distance(start,destination)
        if length<self.enroute_min_distance:return
        entries=[]
        if not hasattr(self,'_enroute_attempts'):self._enroute_attempts={}
        for channel,polygon in list(self.regions.items()):
            if channel in self.cleared or channel==active_channel:continue
            center,radius=enclosing_circle(polygon)
            if radius<self.enroute_min_radius:continue
            anchor,_=self.observations[channel][-1]
            attempts=self._enroute_attempts.setdefault(channel,[])
            endpoint_radius,endpoint_probability=predicted_radius(polygon,anchor,destination)
            best=None
            for t in (.15,.3,.45,.6,.75,.9):
                point=line_point(start,destination,t)
                if min(distance(point,p) for p,_ in self.observations[channel])<75:continue
                if attempts and min(distance(point,p) for p in attempts)<75:continue
                predicted,probability=predicted_radius(polygon,anchor,point)
                gain=(radius-predicted)*probability
                if self.enroute_compare_destination:gain-=(radius-endpoint_radius)*endpoint_probability*.8
                if gain<self.enroute_min_gain:continue
                score=gain/(1+distance(point,center)/1500)
                if best is None or score>best[0]:best=(score,t,point,channel)
            if best:entries.append(best)
        entries=sorted(sorted(entries,reverse=True)[:self.enroute_max_probes],key=lambda e:e[1])
        self._enroute_active=True
        try:
            for _,t,point,channel in entries:
                if channel in self.cleared or enclosing_circle(self.regions[channel])[1]<self.enroute_min_radius:continue
                self._enroute_attempts[channel].append(point)
                self._measure(client,point,channel)
                self.stats['enroute_probes']=self.stats.get('enroute_probes',0)+1
        finally:self._enroute_active=False


class DeferredMixin:
    deferred_mode='soft'
    deferred_radius=100.
    deferred_detour=600.
    deferred_prediction=60.
    def _route_goal(self,client,pending):
        if not pending or len(set(self.regions)|self.cleared)==16:return super()._route_goal(client,pending)
        saved={}
        for channel,polygon in list(self.regions.items()):
            if channel in self.cleared:continue
            center,radius=enclosing_circle(polygon)
            if radius<self.deferred_radius:continue
            anchor,_=self.observations[channel][-1]
            opportunities=[]
            for point in pending:
                estimate,probability=predicted_radius(polygon,anchor,point)
                detour=distance(client.position,point)+distance(point,center)-distance(client.position,center)
                if estimate<self.deferred_prediction and probability>.45:
                    opportunities.append((detour,point))
            delay=bool(opportunities) and (self.deferred_mode=='hard' or min(x[0] for x in opportunities)<self.deferred_detour)
            if delay:
                saved[channel]=self.regions.pop(channel)
        try:return super()._route_goal(client,pending)
        finally:self.regions.update(saved)


class ServiceLegMixin:
    """If a radio target is uncertain, use a useful point on a future scan leg."""
    service_detour=300.
    service_radius=100.
    def _route_goal(self,client,pending):
        goal=super()._route_goal(client,pending)
        if goal[1]!='clear' or not pending:return goal
        channel=goal[2];polygon=self.regions[channel];center,radius=enclosing_circle(polygon)
        if radius<self.service_radius:return goal
        anchor,_=self.observations[channel][-1]
        choices=[]
        for i,point in enumerate(pending):
            detour=distance(client.position,point)+distance(point,center)-distance(client.position,center)
            if detour>self.service_detour:continue
            estimated,probability=predicted_radius(polygon,anchor,point)
            score=detour-(radius-estimated)*probability
            if probability>.45 and estimated<radius*.4:choices.append((score,i,point))
        if choices:
            _,i,point=min(choices);self.stats['deferred_to_scan']=self.stats.get('deferred_to_scan',0)+1
            return point,'scan',i
        return goal


def get_class(name):
    if name.startswith('channel_split'):
        from problem4.experiments_v3.routing_channel_split import get_class as channel_split_class
        return channel_split_class(name)
    if name.startswith('channel_reads'):
        from problem4.experiments_v3.routing_channel_reads import get_class as channel_read_class
        return channel_read_class(name)
    if name.startswith('discovery'):
        from problem4.experiments_v3.discovery_insertion import get_class as discovery_class
        return discovery_class(name)
    if name.startswith('clear_region'):
        from problem4.experiments_v3.routing_clear_region import get_class as clear_region_class
        return clear_region_class(name)
    if name.startswith('skeleton'):
        from problem4.experiments_v3.routing_skeleton import get_class as skeleton_class
        return skeleton_class(name)
    if name.startswith('incremental'):
        from problem4.experiments_v3.routing_incremental import get_class as incremental_class
        return incremental_class(name)
    if name.startswith('departure'):
        from problem4.experiments_v3.routing_departure import get_class as departure_class
        return departure_class(name)
    if name.startswith('shared'):
        from problem4.experiments_v3.routing_shared import get_class as get_shared
        return get_shared(name)
    if name.startswith('tspn'):
        from problem4.experiments_v3.routing_tspn import get_class as get_tspn
        return get_tspn(name)
    if name.startswith('reuse'):
        attrs={'reuse_margin':5. if 'strict' in name else 18.,'reuse_max_radius':300. if 'narrow' in name else math.inf}
        bases=(ReuseClearMixin,EnrouteMixin,ProductionPolicy) if 'enroute' in name else (ReuseClearMixin,ProductionPolicy)
        return type(name,bases,attrs)
    if name=='v2':return ProductionPolicy
    if name.startswith('enroute'):
        attrs={}
        if 'selective' in name:attrs['enroute_compare_destination']=True
        if 'low' in name:attrs.update(enroute_min_radius=35.,enroute_min_gain=15.)
        if 'high' in name:attrs.update(enroute_min_radius=120.,enroute_min_gain=100.)
        return type(name,(EnrouteMixin,ProductionPolicy),attrs)
    if name.startswith('defer'):
        attrs={'deferred_mode':'hard' if 'hard' in name else 'soft'}
        if 'wide' in name:attrs['deferred_detour']=1200.
        if 'strict' in name:attrs.update(deferred_radius=60.,deferred_prediction=35.)
        mixins=(EnrouteMixin,DeferredMixin,ProductionPolicy) if 'enroute' in name else (DeferredMixin,ProductionPolicy)
        return type(name,mixins,attrs)
    if name.startswith('service'):
        attrs={'service_detour':600. if 'wide' in name else 300.}
        mixins=(EnrouteMixin,ServiceLegMixin,ProductionPolicy) if 'enroute' in name else (ServiceLegMixin,ProductionPolicy)
        return type(name,mixins,attrs)
    raise ValueError(name)


class ReuseClearMixin:
    reuse_margin=18.
    reuse_max_radius=math.inf
    def _clear(self,client,point,channel):
        result=super()._clear(client,point,channel)
        if not result or getattr(self,'_reuse_active',False):return result
        from problem3.geometry import contains
        if not hasattr(self,'_reuse_attempts'):self._reuse_attempts={}
        self._reuse_active=True
        try:
            for other,polygon in list(self.regions.items()):
                if other in self.cleared:continue
                if enclosing_circle(polygon)[1]>self.reuse_max_radius:continue
                attempts=self._reuse_attempts.setdefault(other,[])
                if any(distance(point,p)<5 for p in attempts):continue
                gap=0. if len(polygon)>=3 and contains(polygon,point) else math.inf
                for a,b in zip(polygon,polygon[1:]+polygon[:1]):
                    length=distance(a,b)**2
                    t=max(0.,min(1.,((point[0]-a[0])*(b[0]-a[0])+(point[1]-a[1])*(b[1]-a[1]))/length)) if length else 0.
                    gap=min(gap,distance(point,line_point(a,b,t)))
                if gap>self.reuse_margin:continue
                attempts.append(point)
                self.stats['reuse_clear_attempts']=self.stats.get('reuse_clear_attempts',0)+1
                if self._clear(client,point,other):self.stats['reuse_clear_successes']=self.stats.get('reuse_clear_successes',0)+1
        finally:self._reuse_active=False
        return result



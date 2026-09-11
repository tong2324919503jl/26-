"""Shortest safe clearing positions and shared measurements on planned legs."""
from __future__ import annotations
import math
from problem3.geometry import distance,enclosing_circle,polygon_centroid
from problem3.experiments_v3.candidate import SearchPolicy as CandidatePolicy


def circle_intersections(a,b,radius):
    d=distance(a,b)
    if d<1e-9 or d>2*radius:return []
    mid=((a[0]+b[0])/2,(a[1]+b[1])/2)
    h=math.sqrt(max(0.,radius*radius-d*d/4))
    x,y=-(b[1]-a[1])*h/d,(b[0]-a[0])*h/d
    return [(mid[0]+x,mid[1]+y),(mid[0]-x,mid[1]-y)]


def safe_clear_points(polygon,center,start,end=None,radius=19.99):
    points=[center]
    for target in [start]+([end] if end is not None else []):
        points.append(target)
        for vertex in polygon:
            d=distance(target,vertex)
            if d:
                points.append((vertex[0]+radius*(target[0]-vertex[0])/d,
                               vertex[1]+radius*(target[1]-vertex[1])/d))
    for i,a in enumerate(polygon):
        for b in polygon[i+1:]:points.extend(circle_intersections(a,b,radius))
    if end is not None:
        dx,dy=end[0]-start[0],end[1]-start[1];a=dx*dx+dy*dy;lo,hi=0.,1.
        if a:
            for vertex in polygon:
                sx,sy=start[0]-vertex[0],start[1]-vertex[1]
                b=2*(dx*sx+dy*sy);c=sx*sx+sy*sy-radius*radius
                disc=b*b-4*a*c
                if disc<0:lo,hi=1.,0.;break
                root=math.sqrt(disc);lo=max(lo,(-b-root)/(2*a));hi=min(hi,(-b+root)/(2*a))
            if lo<=hi:points.append((start[0]+lo*dx,start[1]+lo*dy))
    return [p for p in points if all(distance(p,v)<=radius+1e-7 for v in polygon)]


class ClearRegionMixin:
    clear_lookahead=False
    def _clear(self,client,point,channel):
        polygon=self.regions.get(channel)
        if polygon:
            center,radius=enclosing_circle(polygon)
            if radius<=self.config.clear_guarantee_radius_m:
                nxt=None
                if self.clear_lookahead and getattr(self,'_route_keys',None):
                    keys=self._route_keys
                    try:i=keys.index(('clear',channel))+1
                    except ValueError:i=len(keys)
                    if i<len(keys):
                        key=keys[i]
                        if key[0]=='scan':nxt=(key[1],key[2])
                        elif key[1] in self.regions and key[1] not in self.cleared:nxt=polygon_centroid(self.regions[key[1]])
                candidates=safe_clear_points(polygon,center,client.position,nxt,self.config.clear_guarantee_radius_m)
                if candidates:
                    point=min(candidates,key=lambda p:distance(client.position,p)+(distance(p,nxt) if nxt else 0))
                    self.stats['safe_clear_offsets']=self.stats.get('safe_clear_offsets',0)+1
        return super()._clear(client,point,channel)


def line_point(a,b,t):return (a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1]))


def predicted_radius(polygon,anchor,point):
    center,radius=enclosing_circle(polygon)
    a=(anchor[0]-center[0],anchor[1]-center[1]);b=(point[0]-center[0],point[1]-center[1])
    da,db=math.hypot(*a),math.hypot(*b)
    sine=abs(a[0]*b[1]-a[1]*b[0])/(da*db) if da*db else 0.
    if sine<.03:return radius,0.
    estimate=min(radius,math.tan(math.radians(1.005))*(da+db)/sine)
    return estimate,max(0.,min(1.,(1500-db)/500))


class EnrouteMixin:
    enroute_min_radius=120.
    enroute_min_distance=150.
    enroute_min_gain=100.
    enroute_compare_destination=True
    enroute_max_probes=6
    enroute_active_channel=False
    enroute_projection=True
    def _prediction(self,polygon,anchor,point):return predicted_radius(polygon,anchor,point)
    def _measure(self,client,point,channel):
        if not getattr(self,'_enroute_active',False):
            outcome=self._collect_enroute(client,point,channel,allow_active=self.enroute_active_channel and channel in self.regions)
            if outcome is not None:return outcome
        return super()._measure(client,point,channel)
    def _clear(self,client,point,channel):
        if not getattr(self,'_enroute_active',False):self._collect_enroute(client,point,channel)
        return super()._clear(client,point,channel)
    def _collect_enroute(self,client,destination,active_channel,allow_active=False):
        start=client.position
        if distance(start,destination)<self.enroute_min_distance:return None
        if not hasattr(self,'_enroute_attempts'):self._enroute_attempts={}
        entries=[]
        for channel,polygon in list(self.regions.items()):
            if channel in self.cleared or (channel==active_channel and not allow_active):continue
            center,radius=enclosing_circle(polygon)
            if radius<self.enroute_min_radius:continue
            anchor,_=self.observations[channel][-1]
            attempts=self._enroute_attempts.setdefault(channel,[])
            endpoint_radius,endpoint_probability=self._prediction(polygon,anchor,destination)
            best=None
            ts=[.15,.3,.45,.6,.75,.9]
            if self.enroute_projection:
                dx,dy=destination[0]-start[0],destination[1]-start[1]
                t=((center[0]-start[0])*dx+(center[1]-start[1])*dy)/(dx*dx+dy*dy)
                if .05<t<.95:ts.append(t)
            for t in ts:
                point=line_point(start,destination,t)
                if min(distance(point,p) for p,_ in self.observations[channel])<75:continue
                if attempts and min(distance(point,p) for p in attempts)<75:continue
                predicted,probability=self._prediction(polygon,anchor,point)
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
                result=self._measure(client,point,channel)
                self.stats['enroute_probes']=self.stats.get('enroute_probes',0)+1
                if channel not in self.cleared and max(distance(point,p) for p in self.regions[channel])<19.99:
                    self._clear(client,point,channel)
                if allow_active and channel==active_channel:return result
        finally:self._enroute_active=False
        return None


class ClearRegionPolicy(ClearRegionMixin,CandidatePolicy):pass
class EnroutePolicy(EnrouteMixin,CandidatePolicy):pass
class JourneyPolicy(ClearRegionMixin,EnrouteMixin,CandidatePolicy):pass


class FreshBaselineMixin:
    fresh_min_count=1
    fresh_step=50.
    fresh_triangular=False
    fresh_only=True
    def _scan(self,client,point):
        previous=set(self.regions)|self.cleared
        super()._scan(client,point)
        self._fresh_channels=[ch for ch in self.regions if ch not in previous and ch not in self.cleared]
    def _after_scan(self,client,pending):
        eligible=self._fresh_channels if self.fresh_only else [ch for ch in self.regions if ch not in self.cleared]
        channels=[ch for ch in eligible if enclosing_circle(self.regions[ch])[1]>100.]
        if len(channels)<self.fresh_min_count:return
        start=client.position;best=None
        for k in range(24):
            angle=k*math.tau/24
            point=(start[0]+self.fresh_step*math.cos(angle),start[1]+self.fresh_step*math.sin(angle));gain=0.
            for ch in channels:
                center,radius=enclosing_circle(self.regions[ch]);anchor=self.observations[ch][-1][0]
                estimate,probability=predicted_radius(self.regions[ch],anchor,point)
                gain+=(radius-estimate)*probability
            if best is None or (gain,angle)>best:best=(gain,angle)
        angle=best[1]
        point=(start[0]+self.fresh_step*math.cos(angle),start[1]+self.fresh_step*math.sin(angle))
        for ch in channels:self._measure(client,point,ch)
        if self.fresh_triangular:
            point=(start[0]-self.fresh_step*math.sin(angle),start[1]+self.fresh_step*math.cos(angle))
            for ch in channels:
                if ch not in self.cleared and enclosing_circle(self.regions[ch])[1]>100.:
                    self._measure(client,point,ch)


class FreshBaselinePolicy(FreshBaselineMixin,CandidatePolicy):pass

"""Observation-only global scheduling and conservative omnidirectional geometry.

Selected from the evaluated third-round methods. Production imports no
experiment modules; optional hypotheses rank motion but never certify clearance.
"""
from __future__ import annotations
import math
from problem3.policy import SearchPolicy as LegacyPolicy
from problem3.geometry import (clip_halfplane, distance, enclosing_circle,
    polygon_centroid, optical_cover, certified_covering_radius, contains)
from problem4.localization import _convex_hull
from problem4.routing import RoutingMixin, two_opt, nearest_seed, insertion_seed, route_length



class NegativeMixin:
    def _measure(self,client,point,channel):
        result=super()._measure(client,point,channel)
        if not hasattr(self,'negative_history'):self.negative_history={}
        if result=='no_signal':
            history=self.negative_history.setdefault(channel,[])
            if point not in history:history.append(point)
        if channel in self.regions and channel not in self.cleared:
            polygon=self.regions[channel]
            for p,_ in self.observations[channel]:
                for q in self.negative_history.get(channel,[]):
                    # P received, Q absent, omni source: |P-g|<=R<|Q-g|.
                    # Cancel |g|^2 for a necessary affine inequality.
                    a,b=2*(q[0]-p[0]),2*(q[1]-p[1])
                    c=q[0]*q[0]+q[1]*q[1]-p[0]*p[0]-p[1]*p[1]
                    polygon=clip_halfplane(polygon,a,b,c)
                    if not polygon:raise RuntimeError('Omnidirectional radius bounds contradict bearings')
            self.regions[channel]=polygon
        return result


class LocalizationMixin:
    probe_quantile=.5
    probe_fraction=.04
    probe_min=15.
    direct_radius=100.
    def _probe_point(self,channel,client,probe_index):
        polygon=self.regions[channel]
        center=polygon_centroid(polygon)
        anchor,bearing=self.observations[channel][-1]
        theta=math.radians(bearing);forward=(math.cos(theta),math.sin(theta));side=(-forward[1],forward[0])
        _,radius=enclosing_circle(polygon)
        if len(self.observations[channel])>1 and radius<self.direct_radius:return center
        projs=[(p[0]-anchor[0])*forward[0]+(p[1]-anchor[1])*forward[1] for p in polygon]
        step=min(projs)+self.probe_quantile*(max(projs)-min(projs))
        width=max(self.probe_min,min(140.,self.probe_fraction*step))
        midpoint=(anchor[0]+step*forward[0],anchor[1]+step*forward[1])
        candidates=[(midpoint[0]+s*width*side[0],midpoint[1]+s*width*side[1]) for s in (-1,1)]
        return min(candidates,key=lambda p:distance(client.position,p))


class GlobalMixin(RoutingMixin):
    samples=None
    mask_cache={}
    escape_info_weight=0.
    dynamic=False
    def run(self,client):
        pending=self.coverage_points()
        while pending or any(ch not in self.cleared for ch in self.regions):
            client.check_budget()
            _,kind,ident=self._route_goal(client,pending)
            if kind=='scan':
                self._scan(client,pending.pop(ident))
                if hasattr(self,'_after_scan'):self._after_scan(client,pending)
            else:
                self._localize(ident,client)
                if hasattr(self,'_coverage_after_clear'):self._coverage_after_clear(client,pending)
                if self.dynamic:
                    for index in sorted(range(len(pending)),key=lambda i:distance(client.position,pending[i])):
                        replacement=self.coverage_visited+pending[:index]+pending[index+1:]+[client.position]
                        if certified_covering_radius(replacement)<=999.999:
                            self._scan(client,client.position);pending.pop(index);break
            self._update_neighbors(client)
            if len(self.cleared)==16:return self._result('maximum_source_count_cleared',not pending)
        return self._result('certified_coverage_and_all_detected_cleared',True)


class CombinedPolicy(GlobalMixin,NegativeMixin,LocalizationMixin,LegacyPolicy):pass


class RotatingPolicy(CombinedPolicy):
    phase_count=24
    def _route_goal(self,client,pending):
        if len(pending)==6 and len(self.coverage_visited)==1 and distance(self.coverage_visited[0],(0.,0.))<1e-7:
            radius=self.config.ring_radius
            known=[polygon_centroid(p) for ch,p in self.regions.items() if ch not in self.cleared]
            best=None
            for phase in range(self.phase_count):
                angle=phase*math.tau/(6*self.phase_count)
                points=[(radius*math.cos(angle+k*math.tau/6),radius*math.sin(angle+k*math.tau/6)) for k in range(6)]
                allpoints=points+known+[client.position]
                matrix=[[distance(a,b) for b in allpoints] for a in allpoints]
                routes=[two_opt(nearest_seed(matrix),matrix),two_opt(insertion_seed(matrix),matrix)]
                value=min(route_length(route,matrix) for route in routes)
                if best is None or value<best[0]:best=(value,points)
            pending[:]=best[1]
        return super()._route_goal(client,pending)


class IncrementalMixin:
    def _localize(self,channel,client):
        if not hasattr(self,'_local_state'):self._local_state={}
        state=self._local_state.setdefault(channel,{'count':0,'clear':False,'points':set()})
        polygon=self.regions[channel];center,radius=enclosing_circle(polygon)
        if radius<=self.config.clear_guarantee_radius_m:
            if self._clear(client,center,channel):return True
        elif radius<=self.config.exploratory_clear_radius_m and not state['clear']:
            state['clear']=True
            if self._clear(client,polygon_centroid(polygon),channel):return True
        point=self._probe_point(channel,client,state['count']);key=tuple(round(v,6) for v in point)
        if state['count']<5 and key not in state['points']:
            state['points'].add(key);state['count']+=1
            result=self._measure(client,point,channel)
            if result=='no_signal':self.stats['negative_localization_reads']+=1
            return channel in self.cleared
        self.stats['optical_fallbacks']+=1
        points=optical_cover(self.regions[channel],self.config.optical_spacing_m)
        while points:
            i=min(range(len(points)),key=lambda i:distance(client.position,points[i]))
            if self._clear(client,points.pop(i),channel):return True
        raise RuntimeError('Optical cover failed')


class RotatingIncrementalPolicy(IncrementalMixin,RotatingPolicy):pass


def polygon_distance(point,polygon):
    if contains(polygon,point):return 0.
    best=math.inf
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy
        t=max(0.,min(1.,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/den)) if den else 0.
        best=min(best,math.hypot(point[0]-a[0]-t*dx,point[1]-a[1]-t*dy))
    return best


class AngularNeighborsMixin:
    neighbor_angle_span=10.
    def _update_neighbors(self,client):
        point=client.position
        for ch in list(self.regions):
            if ch in self.cleared:continue
            polygon=self.regions[ch]
            if max(distance(point,p) for p in polygon)<19.99:
                self._clear(client,point,ch);continue
            if enclosing_circle(polygon)[1]<30.:continue
            if any(distance(point,p)<1e-5 for p,_ in self.observations[ch]):continue
            if polygon_distance(point,polygon)>1500.:continue
            angles=sorted(math.atan2(p[1]-point[1],p[0]-point[0]) for p in polygon)
            gaps=[(angles[(i+1)%len(angles)]-angles[i])%math.tau for i in range(len(angles))]
            span=math.tau-max(gaps)
            if span>=math.radians(self.neighbor_angle_span):
                self._measure(client,point,ch)


class BatchBaselineMixin:
    batch_step=200.
    batch_each_scan=False
    batch_choice='nearest'
    def _after_scan(self,client,pending):
        if not self.batch_each_scan and len(self.coverage_visited)!=1:return
        channels=[ch for ch in self.regions if ch not in self.cleared and enclosing_circle(self.regions[ch])[1]>100.]
        if len(channels)<3:return
        start=client.position
        if self.batch_choice=='nearest':
            closest=min(channels,key=lambda ch:distance(start,polygon_centroid(self.regions[ch])))
            goal=polygon_centroid(self.regions[closest]);angle=math.atan2(goal[1]-start[1],goal[0]-start[0])
        else:
            best=None
            for k in range(24):
                angle=k*math.tau/24
                p=(start[0]+self.batch_step*math.cos(angle),start[1]+self.batch_step*math.sin(angle))
                gain=0.
                for ch in channels:
                    center,radius=enclosing_circle(self.regions[ch]);origin=self.observations[ch][-1][0]
                    a=(origin[0]-center[0],origin[1]-center[1]);b=(p[0]-center[0],p[1]-center[1])
                    den=math.hypot(*a)*math.hypot(*b)
                    sine=abs(a[0]*b[1]-a[1]*b[0])/den if den else 1.
                    gain+=min(radius,max(0.,radius-2*.01754*distance(p,center)/max(.01,sine)))
                goal=(gain,angle)
                if best is None or goal>best:best=goal
            angle=best[1]
        point=(start[0]+self.batch_step*math.cos(angle),start[1]+self.batch_step*math.sin(angle))
        for ch in channels:self._measure(client,point,ch)


class Candidate(AngularNeighborsMixin, BatchBaselineMixin, RotatingIncrementalPolicy):
    batch_step = 100.
    batch_choice = "information"
    neighbor_angle_span = 40.



class AnnularMixin:
    annular_count=7
    annular_radius=1790.
    annular_signal_count=0
    annular_phases=16
    def _route_goal(self,client,pending):
        if len(self.coverage_visited)==1 and distance(self.coverage_visited[0],(0.,0.))<1e-7:
            if not hasattr(self,'_annular_decision'):
                self._annular_decision=len(set(self.regions)|self.cleared)<=self.annular_signal_count
            if self._annular_decision:
                n=self.annular_count;r=self.annular_radius
                known=[polygon_centroid(poly) for ch,poly in self.regions.items() if ch not in self.cleared]
                best=None
                for phase in range(self.annular_phases):
                    a=math.tau*phase/(n*self.annular_phases)
                    ring=[(r*math.cos(a+k*math.tau/n),r*math.sin(a+k*math.tau/n)) for k in range(n)]
                    pts=ring+known+[client.position];matrix=[[distance(p,q) for q in pts] for p in pts]
                    value=min(route_length(two_opt(route,matrix),matrix) for route in (nearest_seed(matrix),insertion_seed(matrix)))
                    if best is None or value<best[0]:best=value,ring
                if certified_covering_radius(self.coverage_visited+best[1])<=999.999:
                    pending[:]=best[1];self.stats['annular_scan_count']=n
        return super()._route_goal(client,pending)


class AnnularPolicy(AnnularMixin,Candidate):pass


class InnerAnnularPolicy(AnnularPolicy):annular_radius=1650.


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


class AnnularNegativePolicy(NegativeDiskMixin,InnerAnnularPolicy):pass


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

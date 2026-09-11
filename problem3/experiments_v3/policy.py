"""P3-only development policies. Never infer truth from the local simulator."""
from __future__ import annotations
import math
from problem3.policy import SearchPolicy as LegacyPolicy
from problem3.geometry import clip_halfplane,distance,enclosing_circle,polygon_centroid,optical_cover,certified_covering_radius
from problem3.geometry import contains
from problem4.routing import RoutingMixin
from problem4.routing import two_opt,nearest_seed,insertion_seed,route_length,or_opt


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


class NegativePolicy(NegativeMixin,LegacyPolicy):pass
class LocalPolicy(LocalizationMixin,LegacyPolicy):pass
class NegativeLocalPolicy(NegativeMixin,LocalizationMixin,LegacyPolicy):pass
class GlobalPolicy(GlobalMixin,LegacyPolicy):pass
class GlobalNegativePolicy(GlobalMixin,NegativeMixin,LegacyPolicy):pass
class CombinedPolicy(GlobalMixin,NegativeMixin,LocalizationMixin,LegacyPolicy):pass
class DynamicPolicy(CombinedPolicy):dynamic=True


class OpportunisticPolicy(CombinedPolicy):
    scan_spacing=700.
    scan_max_offset=math.inf
    def _coverage_after_clear(self,client,pending):
        if not pending or len(set(self.regions)|self.cleared)>=16:return
        if self.coverage_visited and min(distance(client.position,p) for p in self.coverage_visited)<self.scan_spacing:return
        if min(distance(client.position,p) for p in pending)>self.scan_max_offset:return
        self._scan(client,client.position)
        for index in reversed(range(len(pending))):
            if certified_covering_radius(self.coverage_visited+pending[:index]+pending[index+1:])<=999.999:
                pending.pop(index)


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


class IncrementalPolicy(IncrementalMixin,CombinedPolicy):pass
class RotatingIncrementalPolicy(IncrementalMixin,RotatingPolicy):pass


class ScanFirstPolicy(CombinedPolicy):
    clear_distance=0.
    def _route_goal(self,client,pending):
        if pending and len(set(self.regions)|self.cleared)<16:
            candidates=[(distance(client.position,polygon_centroid(p)),ch) for ch,p in self.regions.items() if ch not in self.cleared]
            if candidates and min(candidates)[0]<self.clear_distance:
                ch=min(candidates)[1];return polygon_centroid(self.regions[ch]),'clear',ch
            i=min(range(len(pending)),key=lambda i:distance(client.position,pending[i]))
            return pending[i],'scan',i
        return super()._route_goal(client,pending)


def polygon_distance(point,polygon):
    if contains(polygon,point):return 0.
    best=math.inf
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy
        t=max(0.,min(1.,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/den)) if den else 0.
        best=min(best,math.hypot(point[0]-a[0]-t*dx,point[1]-a[1]-t*dy))
    return best


class OpportunisticClearMixin:
    opportunistic_clear=True
    richer_neighbors=False
    nearby_region_distance=40.
    def _update_neighbors(self,client):
        point=client.position
        for ch in list(self.regions):
            if ch in self.cleared:continue
            polygon=self.regions[ch]
            region_distance=polygon_distance(point,polygon)
            if self.opportunistic_clear and region_distance<=19.99:
                if self._clear(client,point,ch):continue
            if self.richer_neighbors and region_distance<=self.nearby_region_distance:
                if not any(distance(point,old)<1e-5 for old,_ in self.observations[ch]):
                    self._measure(client,point,ch)
        return super()._update_neighbors(client)


class OpportunisticClearPolicy(OpportunisticClearMixin,RotatingIncrementalPolicy):pass


class ProbeRouteMixin:
    def _route_goal(self,client,pending):
        if len(set(self.regions)|self.cleared)==16:pending=[]
        goals=[(p,'scan',i) for i,p in enumerate(pending)]
        for ch,polygon in self.regions.items():
            if ch in self.cleared:continue
            center,radius=enclosing_circle(polygon)
            if radius<=self.config.clear_guarantee_radius_m:point=center
            elif radius<=self.config.exploratory_clear_radius_m:point=polygon_centroid(polygon)
            else:point=self._probe_point(ch,client,0)
            goals.append((point,'clear',ch))
        points=[p for p,_,_ in goals]+[client.position]
        matrix=[[distance(a,b) for b in points] for a in points]
        routes=[two_opt(nearest_seed(matrix),matrix),two_opt(insertion_seed(matrix),matrix)]
        route=min(routes,key=lambda route:route_length(route,matrix));route=or_opt(route,matrix)
        return goals[route[0]]


class ProbeRoutePolicy(ProbeRouteMixin,IncrementalPolicy):pass


class RingCoverMixin:
    cover_count=7
    cover_radius=999.
    include_origin=False
    def coverage_points(self):
        points=[(self.cover_radius*math.cos(i*math.tau/self.cover_count),self.cover_radius*math.sin(i*math.tau/self.cover_count)) for i in range(self.cover_count)]
        # Voronoi-cell extrema certify both the central hole and boundary.
        if certified_covering_radius(points)>999.999:raise ValueError('Uncertified ring')
        return ([(0.,0.)] if self.include_origin else [])+points


class RingPolicy(RingCoverMixin,IncrementalPolicy):pass


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


class AngularNeighborsPolicy(AngularNeighborsMixin,RotatingIncrementalPolicy):pass


class PosteriorMixin:
    posterior_prior_max=1500.
    def _estimate(self,ch):
        polygon=self.regions[ch]
        if not hasattr(self,'_estimate_cache'):self._estimate_cache={}
        key=(tuple(polygon),len(self.observations[ch]),len(self.negative_history.get(ch,[])))
        if ch in self._estimate_cache and self._estimate_cache[ch][0]==key:return self._estimate_cache[ch][1]
        triangles=[(polygon[0],polygon[i],polygon[i+1]) for i in range(1,len(polygon)-1)]
        for _ in range(2):
            split=[]
            for a,b,c in triangles:
                ab=((a[0]+b[0])/2,(a[1]+b[1])/2);bc=((b[0]+c[0])/2,(b[1]+c[1])/2);ca=((c[0]+a[0])/2,(c[1]+a[1])/2)
                split.extend([(a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)])
            triangles=split
        sx=sy=total=0.
        for a,b,c in triangles:
            p=((a[0]+b[0]+c[0])/3,(a[1]+b[1]+c[1])/3)
            low=max([1000.]+[distance(p,q) for q,_ in self.observations[ch]])
            high=min([self.posterior_prior_max]+[distance(p,q) for q in self.negative_history.get(ch,[])])
            area=abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))
            w=area*max(0.,high-low);sx+=w*p[0];sy+=w*p[1];total+=w
        answer=(sx/total,sy/total) if total else polygon_centroid(polygon)
        self._estimate_cache[ch]=(key,answer)
        return answer
    def _probe_point(self,ch,client,probe_index):
        point=self._estimate(ch)
        if len(self.observations[ch])>1 and enclosing_circle(self.regions[ch])[1]<100:return point
        anchor,angle=self.observations[ch][-1];theta=math.radians(angle);side=(-math.sin(theta),math.cos(theta))
        width=max(15.,min(100.,distance(point,anchor)*self.probe_fraction))
        points=[(point[0]+s*width*side[0],point[1]+s*width*side[1]) for s in (-1,1)]
        return min(points,key=lambda p:distance(client.position,p))
    def _route_goal(self,client,pending):
        if len(set(self.regions)|self.cleared)==16:pending=[]
        goals=[(p,'scan',i) for i,p in enumerate(pending)]+[(self._estimate(ch),'clear',ch) for ch in self.regions if ch not in self.cleared]
        points=[p for p,_,_ in goals]+[client.position];matrix=[[distance(a,b) for b in points] for a in points]
        routes=[two_opt(nearest_seed(matrix),matrix),two_opt(insertion_seed(matrix),matrix)]
        route=min(routes,key=lambda route:route_length(route,matrix));route=or_opt(route,matrix)
        return goals[route[0]]


class PosteriorPolicy(PosteriorMixin,IncrementalPolicy):pass


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


class BatchBaselinePolicy(BatchBaselineMixin,IncrementalPolicy):pass

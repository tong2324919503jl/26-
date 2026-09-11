"""Use one nearby station to refine newly discovered sources together."""
import math
from problem3.geometry import distance, enclosing_circle


class SharedBaselineMixin:
    shared_initial_only=False
    shared_min_channels=3
    shared_radius_m=100.
    shared_min_uncertainty=100.
    shared_detour_weight=1.
    shared_fresh_only=True
    shared_min_gain=25.
    shared_radius_options=False
    shared_neighbor_first=False
    shared_outer_only=False
    shared_rounds=1
    shared_all_anchors=False
    def coverage_points(self):
        points=super().coverage_points();self._shared_pending=points;return points
    def _scan(self,client,point):
        old=set(self.regions);super()._scan(client,point)
        if self.shared_initial_only and len(self.coverage_visited)>1:return
        if len(self.cleared)==16:return
        if self.shared_neighbor_first:self._update_neighbors(client)
        if self.shared_outer_only and math.hypot(*client.position)<1800:return
        for _ in range(self.shared_rounds):
            if not self._shared_step(client,old):break
    def _shared_step(self,client,old):
        channels=[ch for ch in self.regions if ch not in self.cleared and enclosing_circle(self.regions[ch])[1]>self.shared_min_uncertainty and (not self.shared_fresh_only or ch not in old)]
        if len(channels)<self.shared_min_channels:return
        candidates=[];origin=client.position
        next_goal=super()._route_goal(client,self._shared_pending)[0] if self._shared_pending or any(ch not in self.cleared for ch in self.regions) else origin
        radii=(50.,100.,150.,200.) if self.shared_radius_options else (self.shared_radius_m,)
        for radius in radii:
            for index in range(24):
                angle=index*math.tau/24;q=(origin[0]+radius*math.cos(angle),origin[1]+radius*math.sin(angle));gains=[]
                for ch in channels:
                    center,uncertainty=enclosing_circle(self.regions[ch]);anchor,_=self.observations[ch][-1]
                    estimate=uncertainty
                    anchors=[a for a,b in self.observations[ch]] if self.shared_all_anchors else [anchor]
                    for a_point in anchors:
                        a=(a_point[0]-center[0],a_point[1]-center[1]);b=(q[0]-center[0],q[1]-center[1]);den=math.hypot(*a)*math.hypot(*b)
                        sine=abs(a[0]*b[1]-a[1]*b[0])/den if den else 0
                        estimate=min(estimate,2*.01754*distance(q,center)/max(.01,sine))
                    probability=max(0.,min(1.,(1500-distance(q,center))/500))
                    gain=min(uncertainty,max(0.,uncertainty-estimate))*probability
                    gains.append((gain,ch))
                eligible=[(gain,ch) for gain,ch in gains if gain>=self.shared_min_gain]
                detour=radius+distance(q,next_goal)-distance(origin,next_goal)
                score=sum(gain for gain,ch in eligible)-self.shared_detour_weight*detour
                if len(eligible)>=self.shared_min_channels:candidates.append((score,q,[ch for gain,ch in eligible]))
        if not candidates:return
        score,q,channels=max(candidates,key=lambda item:item[0])
        if score<=0:return
        if client.current_channel in channels:channels.remove(client.current_channel);channels.insert(0,client.current_channel)
        for ch in channels:
            if ch not in self.cleared:self._measure(client,q,ch)
        self.stats['shared_baselines']=self.stats.get('shared_baselines',0)+1
        self.stats['shared_baseline_reads']=self.stats.get('shared_baseline_reads',0)+len(channels)
        return True

"""Replan the mixed tour after each bounded radio localization stage."""
from __future__ import annotations
import math
from problem3.geometry import clip_halfplane,distance,enclosing_circle,polygon_centroid
from problem4.experiments_v3.coverage_ring_policy import Ring12CoverPolicy
from problem4.experiments_v3.routing_shared import SharedBaselineMixin

class IncrementalLocalizationMixin:
    incremental_quantile=.2
    incremental_max_rounds=5
    incremental_radius_clear=55.
    incremental_dynamic=False
    incremental_route_aware=False

    def _localize(self,channel,client):
        if not hasattr(self,'_incremental_rounds'):
            self._incremental_rounds={};self._incremental_measures={};self._incremental_clear=set()
        count=self._incremental_rounds.get(channel,0)
        if count>=self.incremental_max_rounds:
            return super()._localize(channel,client)
        self._incremental_rounds[channel]=count+1
        polygon=self.regions[channel];center,radius=enclosing_circle(polygon)
        if radius<=self.config.clear_guarantee_radius_m:
            if self._clear(client,center,channel):return True
        elif radius<=self.incremental_radius_clear and channel not in self._incremental_clear:
            self._incremental_clear.add(channel)
            if self._clear(client,polygon_centroid(polygon),channel):return True
        anchor,bearing=self.observations[channel][-1]
        theta=math.radians(bearing);forward=(math.cos(theta),math.sin(theta));sideways=(-forward[1],forward[0])
        longitudinal=[(p[0]-anchor[0])*forward[0]+(p[1]-anchor[1])*forward[1] for p in polygon]
        low,high=min(longitudinal),max(longitudinal)
        quantiles=(.1,.25,.5,.75,.9) if self.incremental_dynamic else (self.incremental_quantile,)
        choices=[]
        next_goal=center
        if self.incremental_route_aware and getattr(self,'_route_keys',None):
            key=('clear',channel)
            if key in self._route_keys:
                index=self._route_keys.index(key)
                if index+1<len(self._route_keys):
                    next_key=self._route_keys[index+1]
                    if next_key[0]=='scan':next_goal=(next_key[1],next_key[2])
                    elif next_key[1] not in self.cleared:next_goal=polygon_centroid(self.regions[next_key[1]])
        for quantile in quantiles:
            step=low+quantile*(high-low)
            width=max(self.localization_width_min,min(self.localization_width_max,self.localization_width_fraction*step))
            width=max(width,step*math.tan(math.radians(self.config.bearing_error_deg))+.01)
            for _ in range(24):
                midpoint=(anchor[0]+step*forward[0],anchor[1]+step*forward[1])
                pair=[(midpoint[0]+sign*width*sideways[0],midpoint[1]+sign*width*sideways[1]) for sign in (-1,1)]
                if max(distance(q,v) for q in pair for v in polygon)<999.99:break
                step=.5*step+.25*(low+high)
                width=max(width,step*math.tan(math.radians(self.config.bearing_error_deg))+.01)
            pair.sort(key=lambda p:distance(client.position,p))
            # Approximate two-step expense, with an uncertainty penalty for
            # overshooting the front portion of an unlocalized strip.
            risk=max(0.,quantile-.2)*(high-low)*.4
            score=distance(client.position,pair[0])+distance(pair[0],center)+risk
            if self.incremental_route_aware:
                score+=.2*distance(pair[0],next_goal)
            choices.append((score,step,pair))
        _,step,pair=min(choices,key=lambda x:x[0])
        attempted=self._incremental_measures.setdefault(channel,set());negative=0
        all_in_range=all(distance(q,v)<999.999 for q in pair for v in polygon)
        for point in pair:
            key=(round(point[0],7),round(point[1],7))
            if key in attempted:continue
            attempted.add(key);result=self._measure(client,point,channel)
            self.stats['paired_probe_actions']=self.stats.get('paired_probe_actions',0)+1
            if channel in self.cleared:return True
            if result=='direction':break
            negative+=1;self.stats['negative_localization_reads']+=1
        if negative==2 and all_in_range and step>0:
            constant=step+anchor[0]*forward[0]+anchor[1]*forward[1]
            updated=clip_halfplane(polygon,forward[0],forward[1],constant)
            if not updated:raise RuntimeError('Paired negatives contradict feasible region')
            self.regions[channel]=updated
            self.stats['paired_negative_clips']=self.stats.get('paired_negative_clips',0)+1
        self.stats['incremental_replans']=self.stats.get('incremental_replans',0)+1
        return False

def get_class(name):
    tokens=set(name.split('_'));attrs=dict(shared_min_channels=1,shared_radius_m=50.,shared_fresh_only=True)
    for token,value in [('q10',.1),('q30',.3),('q40',.4),('q50',.5),('q70',.7)]:
        if token in tokens:attrs['incremental_quantile']=value
    if 'dynamic' in tokens:attrs['incremental_dynamic']=True
    if 'route' in tokens:attrs.update(incremental_dynamic=True,incremental_route_aware=True)
    if 'clear80' in tokens:attrs['incremental_radius_clear']=80.
    if 'clear100' in tokens:attrs['incremental_radius_clear']=100.
    return type(name,(SharedBaselineMixin,IncrementalLocalizationMixin,Ring12CoverPolicy),attrs)

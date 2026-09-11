"""Reorder the next task by predicted information-dependent remaining tours.

All hypothetical observations are derived from the public feasible polygon.
Only the first action is executed. The real source regions, negative history,
coverage and termination checks remain those of the frozen parent policy.
"""
from __future__ import annotations
import math
from problem3.geometry import distance,polygon_centroid,enclosing_circle,intersect_bearing,clip_halfplane
from problem4.routing import route_length,nearest_seed,insertion_seed,two_opt
from problem3.experiments_v3.lookahead import LookaheadPolicy,negative_posterior
from problem3.experiments_v3.negative_disks import outside_inner_disk


def tour_cost(start,goals):
    if not goals:return 0.
    points=list(goals)+[start]
    matrix=[[distance(a,b) for b in points] for a in points]
    return min(route_length(two_opt(seed,matrix,30),matrix) for seed in (nearest_seed(matrix),insertion_seed(matrix)))


class GlobalLookaheadMixin:
    global_target_count=3
    global_future_uncertainty=True
    global_allow_scan_override=True
    global_noise=(-1.,0.,1.)

    def _probe_point(self,channel,client,probe_index):
        choice=getattr(self,'_global_probe',None)
        if choice and choice[0]==channel:
            self._global_probe=None
            if choice[2]==tuple(self.regions[channel]) and distance(client.position,choice[3])<1e-7:
                return choice[1]
        return super()._probe_point(channel,client,probe_index)

    def _uncertainty_cost(self,polygon,source):
        if not self.global_future_uncertainty:return 0.
        center,radius=enclosing_circle(polygon)
        estimate=center if radius<=19.99 else polygon_centroid(polygon)
        residual=max(0.,distance(estimate,source)-19.99)
        return residual+(40. if radius>55. or residual else 0.)

    def _future_cost(self,point,posterior,source,others,old_uncertainty):
        if not posterior:return tour_cost(point,others)+3000.-old_uncertainty
        center,radius=enclosing_circle(posterior)
        estimate=center if radius<=19.99 else polygon_centroid(posterior)
        return tour_cost(point,others+[estimate])+self._uncertainty_cost(posterior,source)-old_uncertainty

    def _global_candidates(self,channel,client):
        state=getattr(self,'_local_state',{}).get(channel,{})
        original=super()._probe_point(channel,client,state.get('count',0))
        polygon=self.regions[channel];anchor,bearing=self.observations[channel][-1]
        theta=math.radians(bearing);forward=(math.cos(theta),math.sin(theta));side=(-forward[1],forward[0])
        projections=[(p[0]-anchor[0])*forward[0]+(p[1]-anchor[1])*forward[1] for p in polygon]
        candidates=[original]
        for quantile in (.15,.75):
            step=min(projections)+quantile*(max(projections)-min(projections));width=max(25.,min(100.,.04*step))
            for sign in (-1.,1.):
                candidates.append((anchor[0]+step*forward[0]+sign*width*side[0],anchor[1]+step*forward[1]+sign*width*side[1]))
        history=[p for p,_ in self.observations[channel]]+getattr(self,'negative_history',{}).get(channel,[])
        unique=[]
        for p in candidates:
            if min(distance(p,q) for q in history)<2.:continue
            if all(distance(p,q)>1. for q in unique):unique.append(p)
        return unique

    def _route_goal(self,client,pending):
        self._global_probe=None
        original=super()._route_goal(client,pending)
        original_point,original_kind,original_id=original
        if original_kind=='scan' and not self.global_allow_scan_override:return original
        if original_kind=='clear' and enclosing_circle(self.regions[original_id])[1]<=60.:return original
        known=set(self.regions)|self.cleared
        scans=[] if len(known)==16 else [(p,'scan',i) for i,p in enumerate(pending)]
        clear_goals=[(polygon_centroid(p),'clear',ch) for ch,p in self.regions.items() if ch not in self.cleared]
        all_goals=scans+clear_goals
        centers={ch:p for p,_,ch in clear_goals}
        ordered=[key[1] for key in getattr(self,'_route_keys',[]) if key[0]=='clear' and key[1] in centers]
        eligible=[ch for ch in ordered if enclosing_circle(self.regions[ch])[1]>60. and getattr(self,'_local_state',{}).get(ch,{}).get('count',0)<5]
        if not eligible:return original
        selected=eligible[:self.global_target_count]
        nearest=min(eligible,key=lambda ch:distance(client.position,centers[ch]))
        if nearest not in selected:selected[-1]=nearest
        if original_kind=='clear' and original_id not in selected:
            selected[-1]=original_id
        best=None
        if original_kind=='scan':
            # Every candidate still owes this scan. Its common action cost can
            # be removed; no unobserved discovery is invented for the baseline.
            remaining=[p for p,kind,i in all_goals if not(kind=='scan' and i==original_id)]
            best=(distance(client.position,original_point)+tour_cost(original_point,remaining),original,None)
        for channel in selected:
            polygon=self.regions[channel];positives=self.observations[channel]
            negatives=getattr(self,'negative_history',{}).get(channel,[])
            nodes=self._rollout_nodes(polygon,positives,negatives)
            if not nodes:continue
            others=[p for p,kind,ident in all_goals if not(kind=='clear' and ident==channel)]
            old_uncertainty=sum(w*self._uncertainty_cost(polygon,s) for w,s,_,_ in nodes)
            for point in self._global_candidates(channel,client):
                cost=distance(client.position,point)+25.
                absent=None
                for weight,source,rlo,rhi in nodes:
                    d=distance(point,source)
                    probability=float(d<=rlo) if rhi-rlo<1e-6 else max(0.,min(1.,(rhi-d)/(rhi-rlo)))
                    positive_cost=0.
                    if probability:
                        if d<=5.:
                            # The automatic near response leads to a clear.
                            # Its fee replaces the source's common future fee.
                            positive_cost=tour_cost(point,others)-old_uncertainty
                        else:
                            bearing=math.degrees(math.atan2(source[1]-point[1],source[0]-point[0]))
                            for noise in self.global_noise:
                                posterior=intersect_bearing(polygon,point,round((bearing+noise)%360,2),self.config.bearing_error_deg)
                                for q in negatives:
                                    posterior=clip_halfplane(posterior,2*(q[0]-point[0]),2*(q[1]-point[1]),q[0]**2+q[1]**2-point[0]**2-point[1]**2)
                                positive_cost+=self._future_cost(point,posterior,source,others,old_uncertainty)/len(self.global_noise)
                    negative_cost=0.
                    if probability<1.:
                        if absent is None:absent=outside_inner_disk(negative_posterior(polygon,point,positives),point)
                        negative_cost=self._future_cost(point,absent,source,others,old_uncertainty)
                    cost+=weight*(probability*positive_cost+(1-probability)*negative_cost)
                if best is None or cost<best[0]:best=(cost,(centers[channel],'clear',channel),point)
        if best is None:return original
        _,goal,point=best
        self.stats['global_lookahead_choices']=self.stats.get('global_lookahead_choices',0)+1
        if goal[1:]!=original[1:]:self.stats['global_target_changes']=self.stats.get('global_target_changes',0)+1
        if original_kind=='scan' and goal[1]=='clear':self.stats['global_scan_deferrals']=self.stats.get('global_scan_deferrals',0)+1
        if point is not None:self._global_probe=(goal[2],point,tuple(self.regions[goal[2]]),client.position)
        return goal


class GlobalLookaheadPolicy(GlobalLookaheadMixin,LookaheadPolicy):pass
class GlobalRouteOnlyPolicy(GlobalLookaheadPolicy):global_future_uncertainty=False
class GlobalFixedScanPolicy(GlobalLookaheadPolicy):global_allow_scan_override=False
class GlobalSameTargetPolicy(GlobalFixedScanPolicy):global_target_count=1


if __name__=='__main__':
    from problem3.experiments_v3.benchmark import run,generate_suite,ROOT
    import sys,json
    n=int(sys.argv[1]) if len(sys.argv)>1 else 96
    cases=generate_suite(3,'development_v2',n);results={}
    branch_names=sys.argv[2:]
    branches=(LookaheadPolicy,GlobalLookaheadPolicy,GlobalRouteOnlyPolicy,GlobalFixedScanPolicy,GlobalSameTargetPolicy)
    if branch_names:branches=tuple(cls for cls in branches if cls.__name__ in branch_names)
    for cls in branches:
        r=run(cls,cases);results[cls.__name__]=r
        print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
        suffix=('_'+('_'.join(branch_names))) if branch_names else ''
        (ROOT/f'problem3/results/p3_global_lookahead_v3_development{n}{suffix}.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

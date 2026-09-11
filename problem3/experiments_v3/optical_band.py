"""Choose a finite optical sweep only when its estimated cost beats a radio read.

All clear centers cover an oriented bounding rectangle of the live polygon.
The score uses public candidate quadrature; actual stopping still needs a
successful /clear response. No simulator state is consulted.
"""
from __future__ import annotations
import math
from problem3.geometry import distance, enclosing_circle, intersect_bearing, clip_halfplane
from problem3.experiments_v3.lookahead import source_quadrature, negative_posterior
from problem3.experiments_v3.coverage_family_tuning import get_policy

BasePolicy = get_policy(9,1700)


def band_cover(polygon, radius=19.99, maximum=10):
    a,b=max(((a,b) for a in polygon for b in polygon),key=lambda pair:distance(*pair))
    d=distance(a,b)
    if d<1e-9:return [a]
    u=((b[0]-a[0])/d,(b[1]-a[1])/d);v=(-u[1],u[0])
    xs=[p[0]*u[0]+p[1]*u[1] for p in polygon]
    ys=[p[0]*v[0]+p[1]*v[1] for p in polygon]
    low,high=min(xs),max(xs);mid=(min(ys)+max(ys))/2
    width=(max(ys)-min(ys))/2
    if width>=radius:return []
    step=2*math.sqrt(radius*radius-width*width)
    count=max(1,math.ceil((high-low)/step))
    if count>maximum:return []
    # Every point lies in one longitudinal slab; its distance to that slab's
    # center is <= sqrt((length/(2*count))^2+width^2) <= radius.
    return [((low+(i+.5)*(high-low)/count)*u[0]+mid*v[0],
             (low+(i+.5)*(high-low)/count)*u[1]+mid*v[1]) for i in range(count)]


def sweep_score(start,plan,nodes):
    elapsed=0.;costs=[];point=start
    for goal in plan:
        elapsed+=distance(point,goal)+15.
        costs.append(elapsed+10.) # replace final 3s failure with 5s success
        point=goal
    total=0.
    for weight,source,_,_ in nodes:
        hit=next((i for i,p in enumerate(plan) if distance(p,source)<=19.99+1e-7),None)
        if hit is None:raise AssertionError('Quadrature escaped the certified optical band')
        total+=weight*costs[hit]
    return total


class OpticalBandPolicy(BasePolicy):
    band_margin=0.
    band_maximum=10
    def _radio_score(self,channel,client,point,nodes):
        polygon=self.regions[channel];positives=self.observations[channel]
        negatives=self.negative_history.get(channel,[])
        score=distance(client.position,point)+25.
        absent=negative_posterior(polygon,point,positives)
        for weight,source,rlo,rhi in nodes:
            d=distance(point,source)
            chance=float(d<=rlo) if rhi-rlo<1e-6 else max(0.,min(1.,(rhi-d)/(rhi-rlo)))
            future=0.
            if chance:
                if d<=5.:future=25.
                else:
                    angle=math.degrees(math.atan2(source[1]-point[1],source[0]-point[0]))
                    for noise in (-1.,0.,1.):
                        posterior=intersect_bearing(polygon,point,round((angle+noise)%360,2),self.config.bearing_error_deg)
                        for q in negatives:
                            posterior=clip_halfplane(posterior,2*(q[0]-point[0]),2*(q[1]-point[1]),q[0]**2+q[1]**2-point[0]**2-point[1]**2)
                        future+=self._rollout_finish(point,posterior,source)/3
            score+=weight*(chance*future+(1-chance)*self._rollout_finish(point,absent,source))
        return score

    def _localize(self,channel,client):
        polygon=self.regions[channel]
        radius=enclosing_circle(polygon)[1]
        if radius>self.config.exploratory_clear_radius_m:
            plan=band_cover(polygon,maximum=self.band_maximum)
            if len(plan)>1:
                nodes=source_quadrature(polygon,self.observations[channel],self.negative_history.get(channel,[]),12)
                if nodes:
                    options=[plan,list(reversed(plan))]
                    # Also test a central first attempt followed by a complete
                    # sweep. This retains the same deterministic cover proof.
                    for i in set((len(plan)//2,(len(plan)-1)//2)):
                        for order in (plan,list(reversed(plan))):
                            options.append([plan[i]]+[p for p in order if p!=plan[i]])
                    score,chosen=min((sweep_score(client.position,p,nodes),p) for p in options)
                    state=getattr(self,'_local_state',{}).get(channel,{})
                    point=self._probe_point(channel,client,state.get('count',0))
                    radio=self._radio_score(channel,client,point,nodes)
                    if score+self.band_margin<radio:
                        self.stats['band_sweeps']=self.stats.get('band_sweeps',0)+1
                        for goal in chosen:
                            self.stats['band_clear_attempts']=self.stats.get('band_clear_attempts',0)+1
                            if self._clear(client,goal,channel):return True
                        raise RuntimeError('Certified optical band exhausted without a clear')
        return super()._localize(channel,client)


class ConservativeBandPolicy(OpticalBandPolicy):band_margin=25.
class AggressiveBandPolicy(OpticalBandPolicy):band_margin=-25.

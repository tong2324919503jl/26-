"""Finite-horizon probe scoring and certified optical strip coverage."""
from __future__ import annotations
import math
from problem3.geometry import (distance, clip_halfplane, polygon_centroid,
    enclosing_circle, intersect_bearing)
from problem3.planning import ClearRegionMixin, AnnularNegativePolicy



def polygon_area(polygon):
    return abs(sum(p[0]*q[1]-p[1]*q[0] for p,q in zip(polygon,polygon[1:]+polygon[:1])))/2


def source_quadrature(polygon,positives,negatives,count=3):
    """Area-weighted centroids of thin longitudinal slices, each inside polygon."""
    a,b=max(((a,b) for a in polygon for b in polygon),key=lambda ab:distance(*ab))
    d=distance(a,b)
    if d<1e-6:return [(1.,polygon_centroid(polygon),1000.,1500.)]
    x,y=(b[0]-a[0])/d,(b[1]-a[1])/d
    projs=[x*p[0]+y*p[1] for p in polygon];lo,hi=min(projs),max(projs)
    nodes=[]
    for i in range(count):
        slab=clip_halfplane(polygon,-x,-y,-(lo+(hi-lo)*i/count))
        slab=clip_halfplane(slab,x,y,lo+(hi-lo)*(i+1)/count)
        if not slab:continue
        point=polygon_centroid(slab);weight=polygon_area(slab)
        rlo=max([1000.]+[distance(point,p) for p,_ in positives])
        rhi=min([1500.]+[distance(point,p) for p in negatives])
        # Hull relaxations can contain points violating nonlinear old evidence.
        if rlo<=rhi+1e-6 and weight>1e-8:nodes.append((weight,point,rlo,max(rlo,rhi)))
    total=sum(n[0] for n in nodes)
    return [(w/total,p,lo,hi) for w,p,lo,hi in nodes] if total else []


def negative_posterior(polygon,point,positives):
    polygon=list(polygon)
    for p,_ in positives:
        a,b=2*(point[0]-p[0]),2*(point[1]-p[1])
        c=point[0]**2+point[1]**2-p[0]**2-p[1]**2
        polygon=clip_halfplane(polygon,a,b,c)
    return polygon


class LookaheadMixin:
    rollout_node_count=3
    rollout_quantiles=(.15,.45,.75,1.)
    rollout_widths=(25.,100.)
    rollout_residual_weight=1.
    rollout_action_penalty=40.
    rollout_min_radius=60.

    def _rollout_nodes(self,polygon,positives,negatives):
        return source_quadrature(polygon,positives,negatives,self.rollout_node_count)

    def _rollout_finish(self,point,polygon,source):
        if not polygon:return 3000.
        center,radius=enclosing_circle(polygon)
        if radius<=19.99:
            d=distance(point,center);offset=min(d,max(0.,19.99-radius))
            estimate=(center[0]+(point[0]-center[0])*offset/d,center[1]+(point[1]-center[1])*offset/d) if d else center
        else:estimate=polygon_centroid(polygon)
        residual=max(0.,distance(estimate,source)-19.99)
        extra=self.rollout_action_penalty if radius>55. or residual else 0.
        return distance(point,estimate)+self.rollout_residual_weight*residual+25.+extra

    def _probe_point(self,channel,client,probe_index):
        original=super()._probe_point(channel,client,probe_index)
        polygon=self.regions[channel]
        center,radius=enclosing_circle(polygon)
        if radius<self.rollout_min_radius:return original
        positives=self.observations[channel]
        negatives=getattr(self,'negative_history',{}).get(channel,[])
        nodes=self._rollout_nodes(polygon,positives,negatives)
        if not nodes:return original
        anchor,bearing=positives[-1];theta=math.radians(bearing)
        forward=(math.cos(theta),math.sin(theta));side=(-forward[1],forward[0])
        projs=[(p[0]-anchor[0])*forward[0]+(p[1]-anchor[1])*forward[1] for p in polygon]
        candidates=[original,polygon_centroid(polygon)]
        for quantile in self.rollout_quantiles:
            step=min(projs)+quantile*(max(projs)-min(projs))
            for width in self.rollout_widths:
                for sign in (-1.,1.):
                    candidates.append((anchor[0]+step*forward[0]+sign*width*side[0],anchor[1]+step*forward[1]+sign*width*side[1]))
        best=None
        for point in candidates:
            if min(distance(point,p) for p,_ in positives)<2.:continue
            if negatives and min(distance(point,p) for p in negatives)<2.:continue
            score=distance(client.position,point)+25.
            absent=negative_posterior(polygon,point,positives)
            for weight,source,rlo,rhi in nodes:
                d=distance(point,source)
                probability=float(d<=rlo) if rhi-rlo<1e-6 else max(0.,min(1.,(rhi-d)/(rhi-rlo)))
                future=0.
                if probability:
                    if d<=5.:future=25.
                    else:
                        bearing=math.degrees(math.atan2(source[1]-point[1],source[0]-point[0]))
                        for noise in (-1.,0.,1.):
                            posterior=intersect_bearing(polygon,point,round((bearing+noise)%360,2),self.config.bearing_error_deg)
                            # A new positive also supplies another R lower bound.
                            for q in negatives:
                                posterior=clip_halfplane(posterior,2*(q[0]-point[0]),2*(q[1]-point[1]),q[0]**2+q[1]**2-point[0]**2-point[1]**2)
                            future+=self._rollout_finish(point,posterior,source)/3
                score+=weight*(probability*future+(1-probability)*self._rollout_finish(point,absent,source))
            if best is None or score<best[0]:best=(score,point)
        self.stats['lookahead_choices']=self.stats.get('lookahead_choices',0)+1
        return best[1] if best else original


class LookaheadPolicy(LookaheadMixin,ClearRegionMixin,AnnularNegativePolicy):pass


class GeometryLookaheadPolicy(LookaheadPolicy):
    annular_signal_count=0
    def _route_goal(self,client,pending):
        # The inherited RotatingPolicy rebuilds any six-point ring using this
        # configuration field. Synchronize it only after a truly empty origin,
        # otherwise six-point alternatives would silently revert to 1150m.
        if (self.annular_count==6 and len(self.coverage_visited)==1
            and math.hypot(*self.coverage_visited[0])<1e-7
            and not (set(self.regions)|self.cleared)):
            self.config.ring_radius=self.annular_radius
        return super()._route_goal(client,pending)

    def _scan(self,client,point):
        if len(self.coverage_visited)==1 and getattr(self,'_annular_decision',False):
            self.stats['actual_empty_ring_first_scan_radius_m']=math.hypot(*point)
        return super()._scan(client,point)

    def _result(self,reason,coverage_complete):
        result=super()._result(reason,coverage_complete)
        result['zero_origin_geometry']={'count':self.annular_count,'radius_m':self.annular_radius,
            'triggered':bool(getattr(self,'_annular_decision',False)),
            'phase_candidates':self.annular_phases}
        return result


class RingLookaheadPolicy(GeometryLookaheadPolicy):
    annular_count = 9
    annular_radius = 1700.



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


class OpticalBandPolicy(RingLookaheadPolicy):
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


class AggressiveBandPolicy(OpticalBandPolicy):band_margin=-25.

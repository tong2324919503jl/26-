"""One-observation rollout planning; all latent nodes come from public geometry.

The rollout is only a cost model. It never modifies the live feasible region.
An interval prior on unknown R is used for scoring reception failures, whereas
every real action retains the ordinary conservative geometric update/fallback.
"""
from __future__ import annotations
import math
from problem3.geometry import distance,clip_halfplane,polygon_centroid,enclosing_circle,intersect_bearing
from problem3.experiments_v3.journey import ClearRegionMixin
from problem3.experiments_v3.negative_disks import AnnularNegativePolicy


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


class SecondReadLookaheadMixin(LookaheadMixin):
    """Expand the fallback approach into a second radio read when affordable.

    The next observation is at the posterior centroid, independent of the
    latent source. Only a region of diameter below 1000 is expanded, making
    this second radio observation guaranteed even at the minimum unknown R.
    """
    def _rollout_finish(self,point,polygon,source):
        if not polygon:return 3000.
        center,radius=enclosing_circle(polygon)
        if radius<=55. or radius>=499.:return super()._rollout_finish(point,polygon,source)
        estimate=polygon_centroid(polygon)
        if max(distance(estimate,p) for p in polygon)>=999.999:
            return super()._rollout_finish(point,polygon,source)
        if distance(estimate,source)<=5.:return distance(point,estimate)+50.
        angle=math.degrees(math.atan2(source[1]-estimate[1],source[0]-estimate[0]))
        score=distance(point,estimate)+25.
        for noise in (-1.,0.,1.):
            posterior=intersect_bearing(polygon,estimate,round((angle+noise)%360,2),self.config.bearing_error_deg)
            score+=super()._rollout_finish(estimate,posterior,source)/3
        return score


class SecondReadLookaheadPolicy(SecondReadLookaheadMixin,ClearRegionMixin,AnnularNegativePolicy):pass


class TransverseQuadratureMixin(LookaheadMixin):
    """Integrate both longitudinal and transverse uncertainty of old bearings."""
    def _rollout_nodes(self,polygon,positives,negatives):
        a,b=max(((a,b) for a in polygon for b in polygon),key=lambda ab:distance(*ab))
        d=distance(a,b)
        if d<1e-6:return super()._rollout_nodes(polygon,positives,negatives)
        x,y=-(b[1]-a[1])/d,(b[0]-a[0])/d
        projs=[x*p[0]+y*p[1] for p in polygon];mid=(min(projs)+max(projs))/2
        halves=(clip_halfplane(polygon,x,y,mid),clip_halfplane(polygon,-x,-y,-mid))
        nodes=[]
        for half in halves:
            if not half:continue
            area=polygon_area(half)
            for w,p,lo,hi in source_quadrature(half,positives,negatives,self.rollout_node_count):
                nodes.append((w*area,p,lo,hi))
        total=sum(w for w,*_ in nodes)
        return [(w/total,p,lo,hi) for w,p,lo,hi in nodes] if total else []


class TransverseLookaheadPolicy(TransverseQuadratureMixin,ClearRegionMixin,AnnularNegativePolicy):pass

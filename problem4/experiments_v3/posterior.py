"""Observation-only range/orientation posterior used solely to propose travel."""
import math
from problem3.geometry import polygon_centroid,enclosing_circle,distance
from problem4.routing import RoutingMixin
from problem4.experiments_v3.routing_shared import SharedBaselineMixin
from problem4.experiments_v3.coverage_ring_policy import Ring12CoverPolicy


def hemisphere_mask(dx,dy,n=64):
    if dx*dx+dy*dy<1e-12:return (1<<n)-1
    angle=math.atan2(dy,dx)
    lo=math.ceil((angle-math.pi/2)*n/math.tau-.5)
    hi=math.floor((angle+math.pi/2)*n/math.tau-.5)
    k=hi-lo+1;raw=((1<<k)-1)<<(lo%n)
    return (raw|(raw>>n))&((1<<n)-1)


def quadrature(poly):
    triangles=[(poly[0],poly[i],poly[i+1]) for i in range(1,len(poly)-1)]
    for _ in range(2):
        new=[]
        for a,b,c in triangles:
            ab=((a[0]+b[0])/2,(a[1]+b[1])/2);ac=((a[0]+c[0])/2,(a[1]+c[1])/2);bc=((b[0]+c[0])/2,(b[1]+c[1])/2)
            new.extend(((a,ab,ac),(ab,b,bc),(ac,bc,c),(ab,bc,ac)))
        triangles=new
    return [(((a[0]+b[0]+c[0])/3,(a[1]+b[1]+c[1])/3),abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))) for a,b,c in triangles]


class PosteriorMixin:
    posterior_directional_weight=.5
    posterior_probe=False
    posterior_route=True
    posterior_min_radius=60.
    def _estimate(self,ch):
        poly=self.regions[ch];center,radius=enclosing_circle(poly)
        if radius<self.posterior_min_radius:return polygon_centroid(poly)
        if not hasattr(self,'_posterior_cache'):self._posterior_cache={}
        positive=[p for p,a in self.observations[ch]]
        negative=getattr(self,'_negative_history',{}).get(ch,[])
        key=(tuple(poly),tuple(negative),tuple(positive))
        if ch in self._posterior_cache and self._posterior_cache[ch][0]==key:return self._posterior_cache[ch][1]
        sx=sy=total=0.;full=(1<<64)-1
        for g,area in quadrature(poly):
            needed=max(1000.,max(distance(g,p) for p in positive))
            if needed>1500:continue
            possible=full
            for p in positive:possible&=hemisphere_mask(p[0]-g[0],p[1]-g[1])
            cuts=sorted((distance(g,q),hemisphere_mask(q[0]-g[0],q[1]-g[1])) for q in negative)
            limits=sorted({needed,1500.,*(min(1500.,max(needed,d)) for d,m in cuts)})
            weight=0.
            for a,b in zip(limits,limits[1:]):
                r=(a+b)/2;mask=possible;omni=True
                for d,m in cuts:
                    if d<=r:mask&=full^m;omni=False
                likelihood=(1-self.posterior_directional_weight)*omni+self.posterior_directional_weight*mask.bit_count()/64
                weight+=(b-a)*likelihood
            weight*=area;sx+=weight*g[0];sy+=weight*g[1];total+=weight
        estimate=(sx/total,sy/total) if total else polygon_centroid(poly)
        self._posterior_cache[ch]=(key,estimate)
        return estimate
    def _route_goal(self,client,pending):
        if not self.posterior_route:return super()._route_goal(client,pending)
        estimates={ch:[self._estimate(ch)] if ch not in self.cleared else poly for ch,poly in self.regions.items()}
        original=self.regions
        try:
            self.regions=estimates
            return RoutingMixin._route_goal(self,client,pending)
        finally:self.regions=original
    def _localize(self,ch,client):
        if not self.posterior_probe:return super()._localize(ch,client)
        estimate=self._estimate(ch);anchor,angle=self.observations[ch][-1];theta=math.radians(angle)
        dot=lambda p:(p[0]-anchor[0])*math.cos(theta)+(p[1]-anchor[1])*math.sin(theta)
        values=[dot(p) for p in self.regions[ch]];low,high=min(values),max(values)
        q=max(.05,min(.95,(dot(estimate)-low)/(high-low))) if high>low else .2
        original=self.localization_quantile
        try:
            self.localization_quantile=q
            return super()._localize(ch,client)
        finally:self.localization_quantile=original


class Shared21Policy(SharedBaselineMixin,Ring12CoverPolicy):
    shared_min_channels=1
    shared_radius_m=50.
    shared_fresh_only=True

class PosteriorPolicy(PosteriorMixin,Shared21Policy):pass
class PosteriorProbePolicy(PosteriorPolicy):posterior_probe=True
class PosteriorLocalPolicy(PosteriorProbePolicy):posterior_route=False

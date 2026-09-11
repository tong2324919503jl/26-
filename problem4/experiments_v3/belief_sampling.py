"""Continuous conditional radius/orientation sampler for hypothetical worlds."""
import math
from problem3.geometry import distance
from problem4.experiments_v3.rollout import sample_polygon,DiverseRolloutPolicy


def orientation_intervals(source,positive,negative):
    intervals=[(0.,math.tau)]
    for point,included in [(p,True) for p in positive]+[(q,False) for q in negative]:
        dx,dy=point[0]-source[0],point[1]-source[1]
        if dx*dx+dy*dy<1e-18:
            if not included:return []
            continue
        angle=math.atan2(dy,dx)+(0 if included else math.pi)
        low=(angle-math.pi/2)%math.tau;high=low+math.pi
        allowed=[(low,min(high,math.tau))]+([(0.,high-math.tau)] if high>math.tau else [])
        intervals=[(max(a,c),min(b,d)) for a,b in intervals for c,d in allowed if min(b,d)-max(a,c)>1e-12]
        if not intervals:return []
    return intervals


class ConditionalSamplingMixin:
    def _clear(self,client,point,ch):
        result=super()._clear(client,point,ch)
        if not hasattr(self,'_belief_failed_clears'):self._belief_failed_clears={}
        if not result:self._belief_failed_clears.setdefault(ch,[]).append(tuple(client.position))
        return result
    def _known_sample(self,ch,rng):
        positive=[p for p,a in self.observations[ch]]
        negative=getattr(self,'_negative_history',{}).get(ch,[])
        failed=getattr(self,'_belief_failed_clears',{}).get(ch,[])
        for _ in range(5000):
            g=sample_polygon(self.regions[ch],rng)
            if math.hypot(*g)>1800 or any(distance(g,p)<=5 for p in positive) or any(distance(g,q)<=20 for q in failed):continue
            low=max(1000.,max(distance(g,p) for p in positive))
            if low>=1500:continue
            cuts=sorted((distance(g,q),q) for q in negative)
            limits=sorted({low,1500.,*(max(low,min(1500.,d)) for d,q in cuts)})
            components=[]
            for a,b in zip(limits,limits[1:]):
                inside=[q for d,q in cuts if d<(a+b)/2]
                arcs=orientation_intervals(g,positive,inside)
                if not inside:components.append(((a,b,None),.5*(b-a)))
                for c,d in arcs:components.append(((a,b,(c,d)),.5*(b-a)*(d-c)/math.tau))
            total=sum(w for _,w in components)
            # Uniform position/radius and a half-omni prior conditioned on all
            # observations. Rejection by integrated feasible mass is essential:
            # choosing an always-feasible R/angle without this biases positions.
            if total<=0 or rng.random()*500>total:continue
            a,b,arc=rng.choices([v for v,w in components],weights=[w for v,w in components])[0]
            return dict(channel=ch,x=g[0],y=g[1],radius=rng.uniform(a,b),orientation_deg=None if arc is None else math.degrees(rng.uniform(*arc)))
        raise ValueError('No continuous conditional sample within computation limit')


class ConditionalRolloutPolicy(ConditionalSamplingMixin,DiverseRolloutPolicy):pass

class SpreadConditionalPolicy(ConditionalRolloutPolicy):
    def _choices(self,original,goals,client):
        scans=sorted((g for g in goals if g[1]=='scan'),key=lambda g:distance(client.position,g[0]))
        clears=sorted((g for g in goals if g[1]=='clear'),key=lambda g:distance(client.position,g[0]))
        choices=[original]
        if scans:
            if scans[0] not in choices:choices.append(scans[0])
            first=scans[0][0];a=math.atan2(first[1]-client.position[1],first[0]-client.position[0])
            def contrast(goal):
                p=goal[0];b=math.atan2(p[1]-client.position[1],p[0]-client.position[0])
                angle=abs((a-b+math.pi)%math.tau-math.pi)
                return angle/(1+distance(client.position,p)/1000)
            opposite=max(scans,key=contrast)
            if opposite not in choices:choices.append(opposite)
        if clears and clears[0] not in choices:choices.append(clears[0])
        return choices[:self.rollout_choices]

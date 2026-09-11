"""Finite weighted-particle approximation to the continuous belief sampler."""
import math
from problem3.geometry import distance
from problem4.experiments_v3.rollout import sample_polygon
from problem4.experiments_v3.belief_sampling import orientation_intervals,SpreadConditionalPolicy


class ImportanceSamplingMixin:
    importance_candidates=64
    def _known_sample(self,ch,rng):
        positive=[p for p,a in self.observations[ch]]
        negative=getattr(self,'_negative_history',{}).get(ch,[])
        failed=getattr(self,'_belief_failed_clears',{}).get(ch,[])
        candidates=[];weights=[]
        for _ in range(self.importance_candidates):
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
            total=sum(w for v,w in components)
            if total>0:candidates.append((g,components));weights.append(total)
        if not candidates:raise ValueError('Finite importance pool has no valid source')
        g,components=rng.choices(candidates,weights=weights)[0]
        a,b,arc=rng.choices([v for v,w in components],weights=[w for v,w in components])[0]
        return dict(channel=ch,x=g[0],y=g[1],radius=rng.uniform(a,b),orientation_deg=None if arc is None else math.degrees(rng.uniform(*arc)))


class ImportanceSpreadPolicy(ImportanceSamplingMixin,SpreadConditionalPolicy):pass

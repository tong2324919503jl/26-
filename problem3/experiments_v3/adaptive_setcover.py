"""Experimental adaptive station selection with exact geometric separation.

A binary covering model selects public candidate sites. Any uncovered Voronoi
vertex is added as a constraint, and a proposal is usable only after full
continuous-domain certification. SciPy is confined to this experiment.
"""
from __future__ import annotations
import math
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from problem3.geometry import distance, initial_region, clip_halfplane, polygon_centroid, certified_covering_radius
from problem4.routing import nearest_seed, insertion_seed, two_opt, route_length
from problem3.experiments_v3.coverage_pool import travel
from problem3.experiments_v3.coverage_family_tuning import get_policy

BasePolicy=get_policy(9,1700)


def uncovered_vertices(points):
    witnesses=[]
    for point in points:
        cell=initial_region()
        for other in points:
            if point==other:continue
            cell=clip_halfplane(cell,2*(other[0]-point[0]),2*(other[1]-point[1]),other[0]**2+other[1]**2-point[0]**2-point[1]**2)
            if not cell:break
        witnesses.extend(p for p in cell if min(distance(p,q) for q in points)>999.98)
    return witnesses


def select_cover(candidates,visited,weights,max_count):
    witnesses=initial_region()+[(r*math.cos(k*math.tau/32),r*math.sin(k*math.tau/32)) for r in (400,800,1200,1500) for k in range(32)]
    witnesses=[p for p in witnesses if min(distance(p,q) for q in visited)>999.98]
    n=len(candidates)
    for _ in range(12):
        matrix=np.array([[float(distance(p,q)<=999.97) for q in candidates] for p in witnesses])
        if any(sum(row)==0 for row in matrix):return None
        result=milp(np.asarray(weights),integrality=np.ones(n),bounds=Bounds(np.zeros(n),np.ones(n)),
                    constraints=[LinearConstraint(matrix,1,np.inf),LinearConstraint(np.ones((1,n)),0,max_count)],
                    options={'time_limit':.20,'mip_rel_gap':.015})
        if result.x is None:return None
        chosen=[p for p,x in zip(candidates,result.x) if x>.5]
        gaps=uncovered_vertices(visited+chosen)
        if not gaps:
            if certified_covering_radius(visited+chosen)<=999.99:return chosen
            return None
        witnesses.extend(gaps)
    return None


class AdaptiveSetCoverPolicy(BasePolicy):
    setcover_weights=(1.,)
    setcover_only_empty=True
    def _cover_worlds(self,known,centers):return [centers]
    def _route_goal(self,client,pending):
        original=super()._route_goal(client,pending)
        known=set(self.regions)|self.cleared
        if not pending or len(known)==16 or len(self.coverage_visited)<2:return original
        if self.setcover_only_empty and not getattr(self,'_annular_decision',False):return original
        stamp=(len(self.coverage_visited),len(self.cleared))
        # Replan after a new scan, not after every localization read.
        if getattr(self,'_setcover_stamp',None) is not None and self._setcover_stamp[0]==stamp[0]:return original
        self._setcover_stamp=stamp
        centers=[polygon_centroid(p) for ch,p in self.regions.items() if ch not in self.cleared]
        candidates=list(pending)+centers+[client.position]
        phase=math.atan2(client.position[1],client.position[0])
        candidates.extend((r*math.cos(phase+k*math.tau/32),r*math.sin(phase+k*math.tau/32)) for r in (1100.,1400.,1650.,1790.) for k in range(32))
        unique={tuple(round(v,5) for v in p):p for p in candidates}
        candidates=[p for p in unique.values() if min(distance(p,q) for q in self.coverage_visited)>10.]
        worlds=self._cover_worlds(known,centers)
        paths=[]
        for world in worlds:
            pts=world+[client.position];matrix=[[distance(a,b) for b in pts] for a in pts]
            routes=[two_opt(nearest_seed(matrix),matrix),two_opt(insertion_seed(matrix),matrix)]
            route=min(routes,key=lambda r:route_length(r,matrix))
            paths.append([client.position]+[world[i] for i in route])
        def insertion(p):
            return sum(min([distance(p,path[-1])]+[distance(a,p)+distance(p,b)-distance(a,b) for a,b in zip(path,path[1:])]) for path in paths)/len(paths)
        costs=[insertion(p) for p in candidates]
        price=30.*(20-len(known))
        before=sum(travel(list(pending)+world,client.position) for world in worlds)/len(worlds)+price*len(pending)
        best=before;proposal=None
        for weight in self.setcover_weights:
            sites=select_cover(candidates,self.coverage_visited,[c+weight*price for c in costs],len(pending)+1)
            if sites is None:continue
            value=sum(travel(sites+world,client.position) for world in worlds)/len(worlds)+price*len(sites)
            if value<best-25.:best=value;proposal=sites
        self.stats['setcover_attempts']=self.stats.get('setcover_attempts',0)+1
        if proposal is not None:
            self.stats['setcover_replans']=self.stats.get('setcover_replans',0)+1
            self.stats['setcover_predicted_gain_m']=self.stats.get('setcover_predicted_gain_m',0)+before-best
            pending[:]=proposal
            return super()._route_goal(client,pending)
        return original


class GlobalSetCoverPolicy(AdaptiveSetCoverPolicy):setcover_only_empty=False
class MultiSetCoverPolicy(AdaptiveSetCoverPolicy):setcover_weights=(.5,1.,2.)

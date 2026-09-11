"""Reconsider complete outer-ring layouts after public discoveries."""
import math
from problem3.geometry import distance, polygon_centroid, certified_covering_radius
from problem3.experiments_v3.coverage_pool import travel
from problem3.experiments_v3.coverage_family_tuning import get_policy

BasePolicy=get_policy(9,1700)


class AdaptiveRingPolicy(BasePolicy):
    ring_library_price=30.
    ring_library_counts=(7,8,9,10)
    ring_library_offsets=(0.,.5)
    def _route_goal(self,client,pending):
        original=super()._route_goal(client,pending)
        if not pending or len(set(self.regions)|self.cleared)==16:return original
        if not getattr(self,'_annular_decision',False) or len(self.coverage_visited)<2:return original
        if getattr(self,'_ring_stamp',0)==len(self.coverage_visited):return original
        self._ring_stamp=len(self.coverage_visited)
        centers=[polygon_centroid(p) for ch,p in self.regions.items() if ch not in self.cleared]
        price=self.ring_library_price*(20-len(set(self.regions)|self.cleared))
        before=travel(list(pending)+centers,client.position)+price*len(pending)
        best=before;chosen=None
        first=self.coverage_visited[1];phase=math.atan2(first[1],first[0])
        for n in self.ring_library_counts:
            for offset in self.ring_library_offsets:
                sites=[(1700.*math.cos(phase+(i+offset)*math.tau/n),1700.*math.sin(phase+(i+offset)*math.tau/n)) for i in range(n)]
                sites=[p for p in sites if min(distance(p,q) for q in self.coverage_visited)>1e-4]
                # Delete only stations whose omitted coverage has already been
                # supplied by the union of visited and remaining stations.
                for p in sorted(sites,key=lambda p:min(distance(p,q) for q in self.coverage_visited)):
                    remainder=[q for q in sites if q!=p]
                    if certified_covering_radius(self.coverage_visited+remainder)<=999.99:sites=remainder
                value=travel(sites+centers,client.position)+price*len(sites)
                if value<best-100.:
                    if certified_covering_radius(self.coverage_visited+sites)>999.99:raise AssertionError('Uncertified ring proposal')
                    best=value;chosen=sites
        if chosen is not None:
            self.stats['ring_library_changes']=self.stats.get('ring_library_changes',0)+1
            pending[:]=chosen
            return super()._route_goal(client,pending)
        return original


class RingTravelPolicy(AdaptiveRingPolicy):ring_library_price=0.
class RingLowPricePolicy(AdaptiveRingPolicy):ring_library_price=10.

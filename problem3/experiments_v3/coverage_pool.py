"""Joint future discovery/clearance sites, checked by a finite disk cover."""
import math
from problem3.geometry import certified_covering_radius,distance,enclosing_circle,polygon_centroid
from problem4.routing import nearest_seed,insertion_seed,two_opt,or_opt,route_length
from problem3.experiments_v3.candidate import SearchPolicy as Candidate


def travel(points,start):
    pts=points+[start];matrix=[[distance(a,b) for b in pts] for a in pts]
    routes=[two_opt(nearest_seed(matrix),matrix),two_opt(insertion_seed(matrix),matrix)]
    route=or_opt(min(routes,key=lambda r:route_length(r,matrix)),matrix,max_moves=8)
    return route_length(route,matrix)


class PoolMixin:
    pool_max_radius=150.
    pool_scan_price=30.
    pool_min_gain=5.
    def _route_goal(self,client,pending):
        original=super()._route_goal(client,pending)
        if not pending or len(set(self.regions)|self.cleared)==16:return original
        known=[(polygon_centroid(poly),enclosing_circle(poly)[1]) for ch,poly in self.regions.items() if ch not in self.cleared]
        centers=[p for p,r in known]
        additional=[p for p,r in known if r<=self.pool_max_radius and min(distance(p,q) for q in self.coverage_visited+pending)>200.]
        if not additional:return original
        scan_price=self.pool_scan_price*(20-len(set(self.regions)|self.cleared))
        before=travel(list(pending)+centers,client.position)+scan_price*len(pending)
        sites=list(pending)+additional
        anchors=centers+[client.position]
        def priority(p):
            # A site's geometric insertion estimate relative to necessary clear
            # stops. A newly proposed clear location has zero insertion cost.
            return min(distance(p,q) for q in anchors)+scan_price
        for point in sorted(sites,key=priority,reverse=True):
            proposal=list(sites);proposal.remove(point)
            if certified_covering_radius(self.coverage_visited+proposal)<=999.999:
                sites=proposal
        after=travel(sites+centers,client.position)+scan_price*len(sites)
        if sites and after<before-self.pool_min_gain:
            self.stats['pool_replans']=self.stats.get('pool_replans',0)+1
            self.stats['pool_removed_net']=self.stats.get('pool_removed_net',0)+len(pending)-len(sites)
            pending[:]=sites
            return super()._route_goal(client,pending)
        return original


class PoolPolicy(PoolMixin,Candidate):pass
class WidePoolPolicy(PoolPolicy):pool_max_radius=math.inf
class CheapPoolPolicy(PoolPolicy):pool_scan_price=15.

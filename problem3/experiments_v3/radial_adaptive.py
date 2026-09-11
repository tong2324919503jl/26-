"""Use an observed empty/sparse center to choose the certified search radius.

This only changes the visit geometry; observations, not scenario family names,
select the radius. Both alternative six-ring radii have analytic full coverage.
"""
import math
from problem3.geometry import distance
from problem3.geometry import certified_covering_radius,polygon_centroid
from problem4.routing import two_opt,nearest_seed,insertion_seed,route_length
from problem3.experiments_v3.candidate import SearchPolicy as Candidate


class RadialMixin:
    sparse_center_count=1
    sparse_ring_radius=1496.6629547095765
    def _scan(self,client,point):
        super()._scan(client,point)
        if len(self.coverage_visited)==1 and distance(point,(0.,0.))<1e-7:
            if len(set(self.regions)|self.cleared)<=self.sparse_center_count:
                r=self.sparse_ring_radius
                assert r/math.sqrt(3)<1000
                assert math.sqrt(1800**2+r*r-3600*r*math.cos(math.pi/6))<1000
                self.config.ring_radius=r
                self.stats['sparse_center_ring_radius']=r


class RadialPolicy(RadialMixin,Candidate):pass
class EmptyRadialPolicy(RadialPolicy):sparse_center_count=0
class ThreeRadialPolicy(RadialPolicy):sparse_center_count=3
class OuterRadialPolicy(RadialPolicy):sparse_ring_radius=1650.
class NearRadialPolicy(RadialPolicy):sparse_ring_radius=1350.


class AnnularMixin:
    annular_count=7
    annular_radius=1790.
    annular_signal_count=0
    annular_phases=16
    def _route_goal(self,client,pending):
        if len(self.coverage_visited)==1 and distance(self.coverage_visited[0],(0.,0.))<1e-7:
            if not hasattr(self,'_annular_decision'):
                self._annular_decision=len(set(self.regions)|self.cleared)<=self.annular_signal_count
            if self._annular_decision:
                n=self.annular_count;r=self.annular_radius
                known=[polygon_centroid(poly) for ch,poly in self.regions.items() if ch not in self.cleared]
                best=None
                for phase in range(self.annular_phases):
                    a=math.tau*phase/(n*self.annular_phases)
                    ring=[(r*math.cos(a+k*math.tau/n),r*math.sin(a+k*math.tau/n)) for k in range(n)]
                    pts=ring+known+[client.position];matrix=[[distance(p,q) for q in pts] for p in pts]
                    value=min(route_length(two_opt(route,matrix),matrix) for route in (nearest_seed(matrix),insertion_seed(matrix)))
                    if best is None or value<best[0]:best=value,ring
                if certified_covering_radius(self.coverage_visited+best[1])<=999.999:
                    pending[:]=best[1];self.stats['annular_scan_count']=n
        return super()._route_goal(client,pending)


class AnnularPolicy(AnnularMixin,Candidate):pass
class InnerAnnularPolicy(AnnularPolicy):annular_radius=1650.
class EightAnnularPolicy(AnnularPolicy):annular_count=8;annular_radius=1800.


from problem3.experiments_v3.journey import FreshBaselineMixin,ClearRegionMixin

class ConditionalBatchMixin(FreshBaselineMixin):
    fresh_only=False
    def _after_scan(self,client,pending):
        if getattr(self,'_annular_decision',False):
            return FreshBaselineMixin._after_scan(self,client,pending)
        return Candidate._after_scan(self,client,pending)

class ConditionalBatchPolicy(ConditionalBatchMixin,InnerAnnularPolicy):pass
class ConditionalHundredPolicy(ConditionalBatchPolicy):fresh_step=100.
class ConditionalFreshPolicy(ConditionalBatchPolicy):fresh_only=True
class ConditionalClearPolicy(ClearRegionMixin,ConditionalBatchPolicy):pass

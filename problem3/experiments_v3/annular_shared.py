"""Combine later annular discovery with the travel-aware shared baseline."""
from problem4.experiments_v3.routing_shared import SharedBaselineMixin
from problem3.experiments_v3.coverage_family_tuning import get_policy

BasePolicy=get_policy(9,1700)


class AnnularSharedPolicy(SharedBaselineMixin,BasePolicy):
    shared_min_channels=1
    shared_radius_m=50.
    shared_fresh_only=True
    def _shared_step(self,client,old):
        if len(self.coverage_visited)<2 or not getattr(self,'_annular_decision',False):return
        return super()._shared_step(client,old)


class AnnularHundredPolicy(AnnularSharedPolicy):shared_radius_m=100.

"""Development compositions after changing the scan geometry."""
from problem3.experiments_v3.negative_disks import AnnularNegativePolicy
from problem3.experiments_v3.coverage_pool import PoolMixin
from problem3.experiments_v3.cell_planner import CellPlanningMixin
from problem3.experiments_v3.journey import ClearRegionMixin


class AnnularPoolPolicy(PoolMixin,AnnularNegativePolicy):pass
class AnnularCellPolicy(CellPlanningMixin,AnnularNegativePolicy):
    joint_route=True

class AnnularCellInitializedPolicy(AnnularCellPolicy):
    def _route_goal(self,client,pending):
        AnnularNegativePolicy._route_goal(self,client,pending)
        return CellPlanningMixin._route_goal(self,client,pending)

class CellAfterOriginPolicy(AnnularCellPolicy):
    def _route_goal(self,client,pending):
        goal=AnnularNegativePolicy._route_goal(self,client,pending)
        if not self.coverage_visited:return goal
        return CellPlanningMixin._route_goal(self,client,pending)

class AnnularClearPolicy(ClearRegionMixin,AnnularNegativePolicy):pass
class AnnularClearLookaheadPolicy(AnnularClearPolicy):clear_lookahead=True

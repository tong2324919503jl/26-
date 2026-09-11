"""Matched development ablations combining independently proposed mechanisms."""
import json
from pathlib import Path
from problem4.legacy_policy import SearchPolicy as Legacy
from problem4.experiments.localization import OptimizedSearchPolicy,RadiusBoundSearchPolicy,PartitionedRadiusSearchPolicy
from problem4.experiments.routing import DetectedStopPolicy, InformationRoutingMixin

POINTS=tuple(tuple(p) for p in json.loads((Path(__file__).resolve().parents[1]/'examples/search_layout_v2.json').read_text(encoding='utf-8'))['points'])

class ReducedCover:
    def coverage_points(self):
        return list(POINTS)

class CoverOnly(ReducedCover,Legacy):
    pass

class CoverStop(ReducedCover,DetectedStopPolicy):
    pass

class CoverLocate(ReducedCover,OptimizedSearchPolicy):
    pass

class CoverLocateStop(ReducedCover,OptimizedSearchPolicy):
    def _route_goal(self,client,pending):
        if len(set(self.regions)|self.cleared)==16:
            pending=[]
        return super()._route_goal(client,pending)

class CoverLocateInfo(ReducedCover,InformationRoutingMixin,OptimizedSearchPolicy):
    pass

class CoverRadiusStop(ReducedCover,RadiusBoundSearchPolicy):
    def _route_goal(self,client,pending):
        if len(set(self.regions)|self.cleared)==16:
            pending=[]
        return super()._route_goal(client,pending)

class CoverRadiusInfo(ReducedCover,InformationRoutingMixin,RadiusBoundSearchPolicy):
    pass

class CoverPartitionInfo(ReducedCover,InformationRoutingMixin,PartitionedRadiusSearchPolicy):
    pass

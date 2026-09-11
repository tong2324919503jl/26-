"""Select a proved layout after the initial common measurement baseline.

Only the observation-derived source polygons are used. All library members
and their rigid rotations are already certified, and no non-origin scan is
performed before the choice becomes fixed.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from problem4.experiments_v3.coverage_future import FutureCoverPolicy
from problem4.experiments_v3.coverage_ring_policy import Ring12CoverPolicy,ring_points
from problem4.experiments_v3.routing_shared import SharedBaselineMixin


class LibraryMixin:
    future_scan_weight=1.
    _future_cost=FutureCoverPolicy._future_cost
    library_angles=24

    def _route_goal(self,client,pending):
        if (not getattr(self,'_library_chosen',False) and self.coverage_visited
            and all(math.hypot(*p)<1e-8 for p in self.coverage_visited)):
            self._library_chosen=True
            best=self._future_cost(client,pending);seen=set()
            selected=(12,8,997.32,0.);point_count=21
            for outer,inner,radius in ((12,8,997.32),(14,7,975.),(13,8,995.)):
                base=ring_points(outer,inner,radius)[1:]
                for index in range(self.library_angles):
                    angle=index*math.tau/self.library_angles;ca,sa=math.cos(angle),math.sin(angle)
                    proposal=[(ca*x-sa*y,sa*x+ca*y) for x,y in base]
                    key=tuple(sorted((round(x,5),round(y,5)) for x,y in proposal))
                    if key in seen:continue
                    seen.add(key)
                    score=self._future_cost(client,proposal)
                    if score<best-.01:
                        best=score;pending[:]=proposal;point_count=len(proposal)+1
                        selected=(outer,inner,radius,math.degrees(angle))
            self.stats['cover_library_choice']=selected
            self._library_point_count=point_count
        return super()._route_goal(client,pending)

    def _result(self,reason,coverage_complete):
        result=super()._result(reason,coverage_complete)
        result['effective_settings']['coverage_points']=getattr(self,'_library_point_count',21)
        result['algorithm_version']='problem4_experiment_v3_coverage_library'
        return result


class Shared21(SharedBaselineMixin,Ring12CoverPolicy):
    shared_min_channels=1
    shared_radius_m=50.
    shared_fresh_only=True


class SharedLibraryCoverage(LibraryMixin,Shared21):pass


if __name__=='__main__':
    import argparse
    from problem4.experiments.compare import evaluate
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--count',type=int,default=48)
    parser.add_argument('--split',choices=('development','development_v2'),default='development_v2');args=parser.parse_args()
    folder=ROOT/'problem4'/'results'/'iterations_v3';folder.mkdir(parents=True,exist_ok=True)
    output=folder/f'coverage_library_{args.split}_{args.count}.json';body={}
    for cls in (Shared21,SharedLibraryCoverage):
        summary,rows=evaluate(cls,args.split,args.count);body[cls.__name__]={'summary':summary,'episodes':rows}
        output.write_text(json.dumps(body,indent=2)+'\n',encoding='utf-8');print(cls.__name__,summary,flush=True)

"""Choose a rigidly rotated certified layout from first public observations.

Rotation/reflection about the target-circle centre preserves all distances,
half-plane visibility and the certificate. The layout is fixed before its
first non-origin scan. Candidate source centres influence route cost only.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from problem4.experiments_v3.coverage_future import FutureCoverPolicy
from problem4.policy import SearchPolicy


class RotatedCoverPolicy(SearchPolicy):
    angle_count = 24
    allow_reflection = True
    rotation_score_mode = 'travel'
    _future_cost = FutureCoverPolicy._future_cost
    future_scan_weight = 1.0

    def _route_goal(self, client, pending):
        if (not getattr(self, '_rotation_chosen', False) and self.coverage_visited
                and all(math.hypot(*point) < 1e-8 for point in self.coverage_visited)):
            self._rotation_chosen = True
            original = list(pending)
            best = self._future_cost(client, original)
            chosen = (0.0, 1)
            for reflection in ((1, -1) if self.allow_reflection else (1,)):
                for index in range(self.angle_count):
                    angle = index * math.tau / self.angle_count
                    ca, sa = math.cos(angle), math.sin(angle)
                    points = [(ca*x-sa*y*reflection, sa*x+ca*y*reflection) for x,y in original]
                    cost = self._future_cost(client, points)
                    if cost < best - .01:
                        pending[:] = points
                        best, chosen = cost, (math.degrees(angle), reflection)
            self.stats['cover_rotation_deg'] = chosen[0]
            self.stats['cover_reflection'] = chosen[1]
        return super()._route_goal(client, pending)


class DenseRotatedCoverPolicy(RotatedCoverPolicy):
    angle_count = 72


if __name__ == '__main__':
    import argparse
    from problem4.experiments.compare import evaluate
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count',type=int,default=48)
    parser.add_argument('--split',choices=('development','development_v2'),default='development_v2')
    args=parser.parse_args()
    folder=ROOT/'problem4'/'results'/'iterations_v3'
    folder.mkdir(parents=True,exist_ok=True)
    output=folder/f'coverage_rotate_{args.split}_{args.count}.json'
    body={}
    for cls in (SearchPolicy,RotatedCoverPolicy,DenseRotatedCoverPolicy):
        summary,rows=evaluate(cls,args.split,args.count)
        body[cls.__name__]={'summary':summary,'episodes':rows}
        output.write_text(json.dumps(body,indent=2)+'\n',encoding='utf-8')
        print(cls.__name__,json.dumps(summary),flush=True)

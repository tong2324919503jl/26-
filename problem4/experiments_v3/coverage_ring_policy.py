"""Certified 22-point ring alternatives, development comparison only."""
from __future__ import annotations
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from problem4.policy import SearchPolicy
from problem4.coverage import directional_cover_certificate


def ring_points(outer_count, inner_count, inner_radius):
    outer_radius=1802/math.cos(math.pi/outer_count)
    return [(0.0,0.0)]+[(outer_radius*math.cos(i*math.tau/outer_count),
                        outer_radius*math.sin(i*math.tau/outer_count))
                       for i in range(outer_count)]+[(inner_radius*math.cos(i*math.tau/inner_count),
                       inner_radius*math.sin(i*math.tau/inner_count)) for i in range(inner_count)]


class RingBasePolicy(SearchPolicy):
    ring_point_count=0
    def _result(self,reason,coverage_complete):
        result=super()._result(reason,coverage_complete)
        result['algorithm_version']=f'problem4_experiment_v3_ring{self.ring_point_count}'
        result['effective_settings']['coverage_points']=self.ring_point_count
        return result


class Ring14CoverPolicy(RingBasePolicy):
    ring_point_count=22
    def coverage_points(self):return ring_points(14,7,975.0)


class Ring13CoverPolicy(RingBasePolicy):
    ring_point_count=22
    def coverage_points(self):return ring_points(13,8,995.0)


class Ring12CoverPolicy(RingBasePolicy):
    ring_point_count=21
    def coverage_points(self):return ring_points(12,8,997.32)


if __name__=='__main__':
    import argparse
    from problem4.experiments.compare import evaluate
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count',type=int,default=48)
    parser.add_argument('--split',choices=('development','development_v2'),default='development_v2')
    args=parser.parse_args()
    folder=ROOT/'problem4'/'results'/'iterations_v3';folder.mkdir(parents=True,exist_ok=True)
    output=folder/f'coverage_ring_{args.split}_{args.count}.json';body={}
    for cls in (SearchPolicy,Ring14CoverPolicy,Ring13CoverPolicy,Ring12CoverPolicy):
        certificate=directional_cover_certificate(cls().coverage_points(),full_report=True,early_exit=False)
        if not certificate['certified']:raise RuntimeError('Layout did not certify')
        (folder/f'{cls.__name__}_certificate.json').write_text(json.dumps(certificate,indent=2)+'\n',encoding='utf-8')
        summary,rows=evaluate(cls,args.split,args.count)
        body[cls.__name__]={'summary':summary,'episodes':rows}
        output.write_text(json.dumps(body,indent=2)+'\n',encoding='utf-8')
        print(cls.__name__,json.dumps(summary),flush=True)

"""Test whether accumulated free-arrival scans can replace interior travel.

Extra scans are an explicit exploration investment. Coverage points are only
removed after a finite certificate over scans already completed plus every
remaining planned scan. The heuristic never weakens the completion condition.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from problem3.geometry import distance
from problem4.policy import SearchPolicy
from problem4.experiments_v3.coverage_future import FutureCoverPolicy


class InvestmentCoverPolicy(FutureCoverPolicy):
    investment_limit=8
    investment_distance=650.0
    investment_spacing=450.0

    def _route_goal(self,client,pending):
        self._investment_pending=pending
        return SearchPolicy._route_goal(self,client,pending)

    def _localize(self,channel,client):
        result=super()._localize(channel,client)
        pending=getattr(self,'_investment_pending',[])
        if (len(set(self.regions)|self.cleared)==16 or
            self.stats.get('investment_scans',0)>=self.investment_limit):
            return result
        inner=[p for p in pending if math.hypot(*p)<1800]
        point=tuple(client.position)
        if not inner or min(distance(point,p) for p in inner)>self.investment_distance:
            return result
        if min((distance(point,p) for p in self.coverage_visited),default=9999)<self.investment_spacing:
            return result
        self._scan(client,point)
        self.stats['investment_scans']=self.stats.get('investment_scans',0)+1
        for target in sorted(inner,key=lambda p:distance(point,p)):
            candidate=list(pending);candidate.remove(target)
            if self._certify_replacement(client,self.coverage_visited+candidate):
                pending[:]=candidate
                self.stats['investment_removed']=self.stats.get('investment_removed',0)+1
        return result


class NarrowInvestmentCoverPolicy(InvestmentCoverPolicy):
    investment_limit=6
    investment_distance=400.0


if __name__=='__main__':
    import argparse
    from problem4.experiments.compare import evaluate
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count',type=int,default=48)
    parser.add_argument('--split',choices=('development','development_v2'),default='development_v2')
    args=parser.parse_args()
    folder=ROOT/'problem4'/'results'/'iterations_v3';folder.mkdir(parents=True,exist_ok=True)
    output=folder/f'coverage_invest_{args.split}_{args.count}.json';body={}
    for cls in (SearchPolicy,InvestmentCoverPolicy,NarrowInvestmentCoverPolicy):
        summary,rows=evaluate(cls,args.split,args.count)
        body[cls.__name__]={'summary':summary,'episodes':rows}
        output.write_text(json.dumps(body,indent=2)+'\n',encoding='utf-8')
        print(cls.__name__,json.dumps(summary),flush=True)

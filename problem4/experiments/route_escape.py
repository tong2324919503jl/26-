"""Open-tour escape experiments: Or-opt, multiple starts, and route warm starts.

The strategy only receives observed candidate regions and public robot state.
Its geometric route score is a heuristic; completion still uses the existing
coverage proof or 16 successful clearances. No evaluation truth is consulted.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import random
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from problem3.geometry import distance,polygon_centroid
from problem4.experiments.routing import InformationRoutingMixin
from problem4.experiments.localization import RadiusBoundSearchPolicy
from problem4.experiments.combined import ReducedCover,CoverRadiusInfo,CoverRadiusStop


def route_length(route,matrix):
    return sum(matrix[len(matrix)-1 if i==0 else route[i-1]][j] for i,j in enumerate(route))


def two_opt(route,matrix,moves=80):
    route=list(route);start=len(matrix)-1
    for _ in range(moves):
        best=-.01;change=None
        for i in range(len(route)-1):
            a=start if i==0 else route[i-1];b=route[i]
            for j in range(i+1,len(route)):
                c=route[j];d=route[j+1] if j+1<len(route) else None
                delta=matrix[a][c]-matrix[a][b]
                if d is not None:delta+=matrix[b][d]-matrix[c][d]
                if delta<best:best=delta;change=(i,j)
        if change is None:break
        i,j=change;route[i:j+1]=reversed(route[i:j+1])
    return route


def or_opt(route,matrix,max_moves=16,max_chain=3):
    """Relocate contiguous chains, maintaining the fixed start and free end."""
    route=list(route);start=len(matrix)-1;n=len(route)
    for _ in range(max_moves):
        best=-.01;change=None
        for k in range(1,min(max_chain,n-1)+1):
            for i in range(n-k+1):
                chain=route[i:i+k];rest=route[:i]+route[i+k:]
                a=start if i==0 else route[i-1];b=route[i+k] if i+k<n else None
                removal=-matrix[a][chain[0]]
                if b is not None:removal+=matrix[a][b]-matrix[chain[-1]][b]
                for j in range(len(rest)+1):
                    if j==i:continue
                    c=start if j==0 else rest[j-1];d=rest[j] if j<len(rest) else None
                    for reverse in (False,True) if k>1 else (False,):
                        first,last=(chain[-1],chain[0]) if reverse else (chain[0],chain[-1])
                        delta=removal+matrix[c][first]
                        if d is not None:delta+=matrix[last][d]-matrix[c][d]
                        if delta<best:best=delta;change=(i,k,j,reverse)
        if change is None:break
        i,k,j,reverse=change;chain=route[i:i+k];rest=route[:i]+route[i+k:]
        if reverse:chain.reverse()
        route=rest[:j]+chain+rest[j:]
        route=two_opt(route,matrix,20)
    return route


def nearest_seed(matrix,first=None):
    n=len(matrix)-1;remaining=set(range(n));route=[];last=n
    if first is not None:route=[first];remaining.remove(first);last=first
    while remaining:
        nxt=min(remaining,key=lambda i:matrix[last][i]);route.append(nxt);remaining.remove(nxt);last=nxt
    return route


def insertion_seed(matrix):
    n=len(matrix)-1;start=n;remaining=set(range(n))
    if not remaining:return []
    first=max(remaining,key=lambda i:matrix[start][i]);route=[first];remaining.remove(first)
    while remaining:
        best=None
        for point in remaining:
            for index in range(len(route)+1):
                a=start if index==0 else route[index-1];b=route[index] if index<len(route) else None
                extra=matrix[a][point]+(matrix[point][b]-matrix[a][b] if b is not None else 0)
                candidate=(extra,point,index)
                if best is None or candidate<best:best=candidate
        _,point,index=best;route.insert(index,point);remaining.remove(point)
    return route


class RouteEscapeMixin:
    escape_oropt=True
    escape_chain=3
    escape_starts=1
    escape_warm=False
    escape_info_weight=0.
    escape_oropt_final_only=True

    @staticmethod
    def _goal_key(goal):
        p,kind,ident=goal
        return (kind,round(p[0],5),round(p[1],5)) if kind=='scan' else (kind,ident)

    def _route_goal(self,client,pending):
        known=set(self.regions)|self.cleared
        if len(known)==16:pending=[]
        goals=[(p,'scan',i) for i,p in enumerate(pending)]+[(polygon_centroid(p),'clear',ch) for ch,p in self.regions.items() if ch not in self.cleared]
        points=[g[0] for g in goals]+[client.position]
        matrix=[[distance(a,b) for b in points] for a in points]
        seeds=[nearest_seed(matrix)]
        if self.escape_starts>1:
            seeds.append(insertion_seed(matrix))
        if self.escape_starts>2:
            ordered=sorted(range(len(goals)),key=lambda i:math.atan2(goals[i][0][1],goals[i][0][0]))
            if ordered:
                cut=min(range(len(ordered)),key=lambda i:matrix[-1][ordered[i]])
                angular=ordered[cut:]+ordered[:cut]
                seeds.append(angular)
                if self.escape_starts>3:seeds.append([angular[0]]+list(reversed(angular[1:])))
        if self.escape_starts>4:
            nearest=sorted(range(len(goals)),key=lambda i:matrix[-1][i])
            seeds.extend(nearest_seed(matrix,i) for i in nearest[1:self.escape_starts-3])
        if self.escape_warm and hasattr(self,'_route_keys'):
            mapping={self._goal_key(g):i for i,g in enumerate(goals)}
            warm=[mapping[k] for k in self._route_keys if k in mapping]
            for point in range(len(goals)):
                if point in warm:continue
                best=min(range(len(warm)+1),key=lambda i:matrix[-1 if i==0 else warm[i-1]][point]+(matrix[point][warm[i]]-matrix[-1 if i==0 else warm[i-1]][warm[i]] if i<len(warm) else 0))
                warm.insert(best,point)
            seeds.append(warm)
        candidates=[]
        for seed in seeds:
            route=two_opt(seed,matrix)
            if self.escape_oropt and not self.escape_oropt_final_only:route=or_opt(route,matrix,max_chain=self.escape_chain)
            candidates.append(route)
        route=min(candidates,key=lambda r:route_length(r,matrix))
        if self.escape_oropt and self.escape_oropt_final_only:route=or_opt(route,matrix,max_chain=self.escape_chain)
        if self.escape_info_weight and pending and len(pending)>1:
            total=len(self.samples);unseen=total-self.scanned_mask.bit_count()
            if unseen:
                unknown=20-len(known);posterior=.65*unseen/(.35*total+.65*unseen)
                masks={i:self._mask(p) for i,p in enumerate(pending)}
                def score(r):
                    cost=route_length(r,matrix)/5;covered=self.scanned_mask
                    for index in r:
                        _,kind,ident=goals[index]
                        if kind=='scan':
                            cost+=self.escape_info_weight*6*unknown*((1-posterior)+posterior*(total-covered.bit_count())/unseen)
                            covered|=masks[ident]
                    return cost
                best=score(route)
                for _ in range(20):
                    changed=False
                    for i in range(len(route)-1):
                        for j in range(i+1,len(route)):
                            candidate=route[:i]+list(reversed(route[i:j+1]))+route[j+1:];cost=score(candidate)
                            if cost<best-.01:route=candidate;best=cost;changed=True;break
                        if changed:break
                    if not changed:break
        self._route_keys=[self._goal_key(goals[i]) for i in route]
        return goals[route[0]]


def get_class(name):
    if name=='stop23':return CoverRadiusStop
    if name=='info23':return CoverRadiusInfo
    if name=='info25':return type('Info25',(InformationRoutingMixin,RadiusBoundSearchPolicy),{})
    if name=='stop25':
        def choose(self,client,pending):
            return RadiusBoundSearchPolicy._route_goal(self,client,[] if len(set(self.regions)|self.cleared)==16 else pending)
        return type('Stop25',(RadiusBoundSearchPolicy,),{'_route_goal':choose})
    cover=() if name.endswith('25') else (ReducedCover,)
    base=name[:-2]
    attrs={'escape_oropt':base not in ('multi','warmmulti'),
           'escape_starts':4 if 'multi' in base or 'hybrid' in base else 1,
           'escape_warm':'warm' in base,
           'escape_info_weight':1. if 'info' in base else 0.,
           'escape_chain':1 if base=='relocate' else 3,
           'escape_oropt_final_only':'each' not in base}
    return type(name,(*cover,RouteEscapeMixin,InformationRoutingMixin,RadiusBoundSearchPolicy),attrs)


def self_test():
    rng=random.Random(261109)
    for count in (3,5,12,30):
        for _ in range(20):
            pts=[(rng.uniform(-2000,2000),rng.uniform(-2000,2000)) for _ in range(count+1)]
            matrix=[[distance(a,b) for b in pts] for a in pts];seed=nearest_seed(matrix)
            a=two_opt(seed,matrix);b=or_opt(a,matrix)
            assert sorted(a)==sorted(b)==list(range(count))
            assert route_length(b,matrix)<=route_length(a,matrix)+1e-6<=route_length(seed,matrix)+1e-6
    print('80 random geometric route checks passed',flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('names',nargs='*');parser.add_argument('--count',type=int,default=96);parser.add_argument('--split',choices=('development','development_v2'),default='development_v2');parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
    if args.self_test:self_test()
    if not args.names:return
    from problem3.scenarios import generate_suite
    from problem3.simulator import LocalSimulator,ObservationClient
    body={}
    for name in args.names:
        cls=get_class(name);rows=[];start=time.perf_counter()
        for case in generate_suite(4,args.split,args.count):
            sim=LocalSimulator(case);sim.enter();result={};error=None;runtime=time.perf_counter()
            try:result=cls().run(ObservationClient(sim))
            except Exception as exc:error=repr(exc)
            stats=sim.statistics();complete=not error and result.get('completion_certified') and stats['cleared_count']==stats['source_count']
            rows.append({'case_id':case['case_id'],'family':case['family'],'error':error,**stats,'policy':result,'certified_full_clear':bool(complete),'threshold_passed':bool(complete and stats['average_clear_time_s']<=500),'program_runtime_s':time.perf_counter()-runtime})
        summary={'cases':len(rows),'mean':statistics.mean(r['average_clear_time_s'] for r in rows),'pass':statistics.mean(r['threshold_passed'] for r in rows),'move':statistics.mean(r['movement_m'] for r in rows),'actions':statistics.mean(r['actions'] for r in rows),'full':sum(r['certified_full_clear'] for r in rows),'failures':[(r['case_id'],r['error']) for r in rows if not r['certified_full_clear']],'cpu':time.perf_counter()-start}
        print(name,json.dumps(summary),flush=True);body[name]={'summary':summary,'episodes':rows}
        out=(Path(__file__).resolve().parents[1]/'results'/'iterations_v2').joinpath(f'route_escape_{args.split}_{args.count}_{"_".join(args.names)}.json');out.write_text(json.dumps(body,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()



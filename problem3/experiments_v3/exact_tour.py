"""Development-only exact open tours using SciPy/HiGHS and subtour cuts.

Only geometric visit estimates enter the MILP. Source regions, observations,
coverage geometry and the initial origin scan retain their original behavior.
Every incomplete, timed-out or invalid solver outcome keeps a known full route.
"""
from __future__ import annotations
import argparse,json,math,random,statistics,sys,time,warnings
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
from scipy.optimize import Bounds,LinearConstraint,milp
from scipy.sparse import csc_matrix
from problem3.geometry import distance,polygon_centroid
from problem3.scenarios import generate_suite
from problem3.simulator import LocalSimulator,ObservationClient
from problem3.experiments_v3.coverage_family_tuning import get_policy,fingerprints
from problem4.routing import nearest_seed,two_opt,route_length


def connected_components(vertex_count,edges):
    adjacency=[[] for _ in range(vertex_count)]
    for a,b in edges:adjacency[a].append(b);adjacency[b].append(a)
    components=[];remaining=set(range(vertex_count))
    while remaining:
        component={remaining.pop()};stack=list(component)
        while stack:
            for nxt in adjacency[stack.pop()]:
                if nxt in remaining:remaining.remove(nxt);component.add(nxt);stack.append(nxt)
        components.append(component)
    return components,adjacency


def exact_open_tour(matrix,incumbent,time_limit=.25):
    """Fixed start is matrix[-1], and every other node is visited once.

    Add a zero-cost dummy, force dummy-start, and require degree2 everywhere.
    Every disconnected component adds sum(internal edges)<=size-1. A connected
    integral solution is a legal cycle; deleting the dummy produces the path.
    """
    started=time.perf_counter();n=len(matrix)-1;incumbent=list(incumbent)
    if sorted(incumbent)!=list(range(n)):raise ValueError('Incumbent is not a complete route')
    initial=route_length(incumbent,matrix)
    record=dict(goal_count=n,initial_length_m=initial,length_m=initial,lower_bound_m=None,
                optimal=False,status='time_limit_fallback',iterations=0,cuts=0,runtime_s=0.)
    if n<=2:
        alternatives=[incumbent,list(reversed(incumbent))]
        best=min(alternatives,key=lambda r:route_length(r,matrix));cost=route_length(best,matrix)
        record.update(length_m=cost,lower_bound_m=cost,optimal=True,status='enumerated',runtime_s=time.perf_counter()-started)
        return best,record
    start=n;dummy=n+1;vertex_count=n+2
    edge_list=[(a,b) for a in range(vertex_count) for b in range(a+1,vertex_count)]
    costs=np.array([0. if dummy in (a,b) else matrix[a][b] for a,b in edge_list])
    variables=len(edge_list);lo=np.zeros(variables);hi=np.ones(variables)
    lo[edge_list.index((start,dummy))]=1.
    rows=[];cols=[];values=[]
    for index,(a,b) in enumerate(edge_list):
        rows.extend((a,b));cols.extend((index,index));values.extend((1.,1.))
    # The known heuristic route is a valid upper bound even without warm starts.
    for index,cost in enumerate(costs):
        if cost:rows.append(vertex_count);cols.append(index);values.append(cost)
    lower=[2.]*vertex_count+[-np.inf];upper=[2.]*vertex_count+[initial+1e-5]
    seen_cuts=set();best_route=incumbent;best_cost=initial;lower_bound=-math.inf
    while time.perf_counter()-started<time_limit:
        remaining=time_limit-(time.perf_counter()-started)
        if remaining<.001:break
        constraints=LinearConstraint(csc_matrix((values,(rows,cols)),shape=(len(lower),variables)),np.array(lower),np.array(upper))
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore',message='Unrecognized options detected.*',category=RuntimeWarning)
                result=milp(costs,integrality=np.ones(variables),bounds=Bounds(lo,hi),constraints=constraints,
                            options={'time_limit':remaining,'mip_rel_gap':0.,'presolve':True,'threads':1})
        except Exception as error:
            record['status']='solver_error:'+repr(error);break
        record['iterations']+=1
        bound=getattr(result,'mip_dual_bound',None)
        if bound is not None and math.isfinite(bound):lower_bound=max(lower_bound,float(bound))
        vector=result.x
        if vector is None:
            record['status']='no_incumbent:'+str(result.status);break
        if max(abs(value-round(value)) for value in vector)>1e-5:
            record['status']='nonintegral_fallback';break
        selected=[edge for edge,value in zip(edge_list,vector) if value>.5]
        components,adjacency=connected_components(vertex_count,selected)
        if any(len(neighbors)!=2 for neighbors in adjacency) or start not in adjacency[dummy]:
            record['status']='invalid_degree_fallback';break
        if len(components)==1:
            previous=dummy;current=start;route=[]
            while True:
                nxt=next(v for v in adjacency[current] if v!=previous)
                if nxt==dummy:break
                route.append(nxt);previous,current=current,nxt
                if len(route)>n:break
            if sorted(route)!=list(range(n)):
                record['status']='invalid_path_fallback';break
            cost=route_length(route,matrix)
            if cost<best_cost:best_route=route;best_cost=cost
            record['optimal']=result.status==0
            record['status']='optimal' if result.status==0 else 'connected_incumbent'
            if result.status==0:lower_bound=cost
            break
        added=0
        for component in components:
            key=tuple(sorted(component))
            if key in seen_cuts:continue
            seen_cuts.add(key);row=len(lower)
            for index,(a,b) in enumerate(edge_list):
                if a in component and b in component:rows.append(row);cols.append(index);values.append(1.)
            lower.append(-np.inf);upper.append(len(component)-1);added+=1
        record['cuts']+=added
        if not added:record['status']='repeated_subtour_fallback';break
    record.update(length_m=best_cost,lower_bound_m=lower_bound if math.isfinite(lower_bound) else None,runtime_s=time.perf_counter()-started)
    return best_route,record


class ExactTourMixin:
    exact_apply=True
    exact_time_limit=.25
    exact_min_gain_m=.01
    def _route_goal(self,client,pending):
        original=super()._route_goal(client,pending)
        if not self.coverage_visited:return original
        active_pending=[] if len(set(self.regions)|self.cleared)==16 else pending
        goals=[(p,'scan',i) for i,p in enumerate(active_pending)]+[(polygon_centroid(poly),'clear',ch) for ch,poly in self.regions.items() if ch not in self.cleared]
        mapping={self._goal_key(g):i for i,g in enumerate(goals)}
        incumbent=[mapping[k] for k in self._route_keys if k in mapping]
        if len(incumbent)!=len(goals):return original
        points=[g[0] for g in goals]+[client.position]
        matrix=[[distance(a,b) for b in points] for a in points]
        route,record=exact_open_tour(matrix,incumbent,self.exact_time_limit)
        record['gain_m']=record['initial_length_m']-record['length_m']
        record['first_goal_changed']=bool(route and route[0]!=incumbent[0])
        if not hasattr(self,'_exact_records'):self._exact_records=[]
        self._exact_records.append(record)
        self.stats['exact_tour_calls']=self.stats.get('exact_tour_calls',0)+1
        self.stats['exact_tour_optimal']=self.stats.get('exact_tour_optimal',0)+int(record['optimal'])
        if not self.exact_apply or record['gain_m']<self.exact_min_gain_m:return original
        self.stats['exact_tour_improvements']=self.stats.get('exact_tour_improvements',0)+1
        self.stats['exact_tour_changed_goals']=self.stats.get('exact_tour_changed_goals',0)+int(record['first_goal_changed'])
        self._route_keys=[self._goal_key(goals[i]) for i in route]
        return goals[route[0]]


def exact_dp(matrix):
    n=len(matrix)-1
    if not n:return 0.
    values={(1<<j,j):matrix[-1][j] for j in range(n)}
    for mask in range(1,1<<n):
        for end in range(n):
            cost=values.get((mask,end))
            if cost is None:continue
            for j in range(n):
                if mask&(1<<j):continue
                key=(mask|(1<<j),j);values[key]=min(values.get(key,math.inf),cost+matrix[end][j])
    return min(values[((1<<n)-1,j)] for j in range(n))


def verify():
    rng=random.Random(59132);rows=[]
    for n in (1,2,3,5,8,10):
        for _ in range(3):
            points=[(rng.uniform(-1000,1000),rng.uniform(-1000,1000)) for _ in range(n+1)]
            matrix=[[distance(a,b) for b in points] for a in points]
            incumbent=two_opt(nearest_seed(matrix),matrix)
            route,record=exact_open_tour(matrix,incumbent,2.)
            optimum=exact_dp(matrix)
            if not record['optimal'] or abs(record['length_m']-optimum)>1e-5:raise AssertionError((record,optimum))
            if sorted(route)!=list(range(n)):raise AssertionError('Exact solver lost a visit')
            fallback,limited=exact_open_tour(matrix,incumbent,0.)
            if n>2 and fallback!=incumbent:raise AssertionError('Zero-budget solver changed the incumbent')
            rows.append({'goals':n,'optimum':optimum,'cuts':record['cuts']})
    return {'passed':True,'exact_dp_cases':len(rows),'cases_requiring_subtour_cuts':sum(row['cuts']>0 for row in rows)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count',type=int,default=8)
    parser.add_argument('--time-limit',type=float,default=.25)
    parser.add_argument('--modes',nargs='+',default=['baseline','audit','exact'],choices=['baseline','audit','exact'])
    args=parser.parse_args();validation=verify();before=fingerprints()
    base=get_policy(9,1700.);cases=generate_suite(3,'development_v2',args.count)
    folder=ROOT/'problem3/results/iterations_v3';folder.mkdir(parents=True,exist_ok=True)
    output=folder/f'exact_tour_development_v2_{args.count}.json'
    body={'provenance':'Synthetic development_v2 only; no hidden cases or official platform.','scipy':scipy.__version__,'time_limit_s_per_route':args.time_limit,'baseline':'Lookahead plus zero-origin nine-point radius1700 ring','dependencies':before,'verification':validation,'branches':{}}
    for mode in args.modes:
        cls=base if mode=='baseline' else type('ExactRing9'+mode,(ExactTourMixin,base),{'exact_apply':mode=='exact','exact_time_limit':args.time_limit})
        rows=[];started=time.perf_counter()
        for case in cases:
            if fingerprints()!=before:raise RuntimeError('Frozen reference changed during comparison')
            sim=LocalSimulator(case);sim.enter();policy=cls();error=None;cpu=time.perf_counter()
            try:result=policy.run(ObservationClient(sim))
            except Exception as exc:error=repr(exc);result={}
            stats=sim.statistics();full=not error and result.get('completion_certified') and stats['cleared_count']==stats['source_count']
            records=getattr(policy,'_exact_records',[])
            rows.append({'case_id':case['case_id'],'family':case['family'],**stats,'full':bool(full),'pass220':bool(full and stats['average_clear_time_s']<=220),'error':error,'policy':result,'exact_calls':records,'program_runtime_s':time.perf_counter()-cpu})
        records=[record for row in rows for record in row['exact_calls']]
        summary={'mean':statistics.mean(r['average_clear_time_s'] for r in rows),'full':sum(r['full'] for r in rows),'pass220':sum(r['pass220'] for r in rows),'mean_movement_m':statistics.mean(r['movement_m'] for r in rows),'mean_actions':statistics.mean(r['actions'] for r in rows),'runtime_s':time.perf_counter()-started,'max_case_runtime_s':max(r['program_runtime_s'] for r in rows),'solver_calls':len(records),'optimal_calls':sum(r['optimal'] for r in records),'improvable_calls':sum(r['gain_m']>.01 for r in records),'first_changes':sum(r['first_goal_changed'] and r['gain_m']>.01 for r in records),'sum_snapshot_gain_m':sum(r['gain_m'] for r in records),'max_solve_s':max((r['runtime_s'] for r in records),default=0.),'failed_cases':[(r['case_id'],r['error']) for r in rows if not r['full']]}
        if mode=='audit' and 'baseline' in body['branches']:
            fields=('virtual_time_s','movement_m','actions','measure','clear','switch')
            if not all(all(a[k]==b[k] for k in fields) for a,b in zip(rows,body['branches']['baseline']['episodes'])):raise AssertionError('Read-only audit changed physical behavior')
        body['branches'][mode]={'summary':summary,'episodes':rows}
        output.write_text(json.dumps(body,indent=2)+'\n',encoding='utf-8')
        print(mode,json.dumps(summary),flush=True)

if __name__=='__main__':main()

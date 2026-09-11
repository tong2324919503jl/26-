"""POST-HOC ONLY: lower/upper travel bounds for the fixed 23-scan architecture.

This evaluator reads synthetic source truth deliberately. It is not a policy,
not imported by production, and no truth-derived choice reaches robot code.
"""
from __future__ import annotations
import argparse,json,math,random,statistics,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from problem3.geometry import distance
from problem4.coverage import static_coverage_points
from problem4.routing import nearest_seed,insertion_seed,two_opt,or_opt,route_length
from problem3.scenarios import generate_suite


def mst(matrix,penalty):
    n=len(matrix);best=[math.inf]*n;best[0]=0.;parent=[-1]*n;used=[False]*n;degree=[0]*n;cost=0.
    for _ in range(n):
        i=min((j for j in range(n) if not used[j]),key=lambda j:best[j]);used[i]=True;cost+=best[i]
        if parent[i]>=0:degree[i]+=1;degree[parent[i]]+=1
        for j in range(n):
            if not used[j]:
                edge=matrix[i][j]+penalty[i]+penalty[j]
                if edge<best[j]:best[j]=edge;parent[j]=i
    return cost,degree


def held_karp_open_bound(matrix,upper,iterations=500):
    """Lagrangian 1-tree bound for a fixed-start/free-end Hamiltonian path.

    Add dummy D; force edge D-0, choose the other dummy edge D-j at zero base
    cost. A minimum spanning tree on real vertices plus those two edges is a
    relaxation of every feasible open path. Degree penalties therefore give
    LB = MST(d_ij+pi_i+pi_j) + pi_0 + min_{j!=0}pi_j - 2 sum_i pi_i.
    Pairwise minimum distances between clearance disks lower-bound physical
    transitions even though these relaxed weights need not obey triangle
    inequality. Thus the 1-tree bound remains a physical travel lower bound.
    """
    n=len(matrix);penalty=[0.]*n;best=-math.inf;scale=2.;stall=0;first=None
    for iteration in range(iterations):
        tree,degree=mst(matrix,penalty);end=min(range(1,n),key=lambda i:penalty[i]);degree[0]+=1;degree[end]+=1
        bound=tree+penalty[0]+penalty[end]-2*sum(penalty)
        if first is None:first=bound
        if bound>best+1e-8:best=bound;stall=0
        else:stall+=1
        gradient=[d-2 for d in degree];norm=sum(g*g for g in gradient)
        if not norm:break
        if stall>=25:scale*=.7;stall=0
        if scale<.001:break
        step=scale*max(0.,upper-bound)/norm
        penalty=[p+step*g for p,g in zip(penalty,gradient)]
    return best,first,iteration+1


def circle_service(center,radius,previous,nxt):
    if radius<=0:return center
    if nxt is None:
        d=distance(center,previous)
        return previous if d<=radius else (center[0]+radius*(previous[0]-center[0])/d,center[1]+radius*(previous[1]-center[1])/d)
    dx,dy=nxt[0]-previous[0],nxt[1]-previous[1];length=dx*dx+dy*dy
    t=max(0.,min(1.,((center[0]-previous[0])*dx+(center[1]-previous[1])*dy)/length)) if length else 0.
    foot=(previous[0]+t*dx,previous[1]+t*dy)
    if distance(foot,center)<=radius:return foot
    def point(theta):return(center[0]+radius*math.cos(theta),center[1]+radius*math.sin(theta))
    def cost(theta):p=point(theta);return distance(previous,p)+distance(p,nxt)
    step=math.tau/32;idx=min(range(32),key=lambda i:cost(i*step));lo,hi=(idx-1)*step,(idx+1)*step
    for _ in range(32):
        left,right=lo+(hi-lo)/3,hi-(hi-lo)/3
        if cost(left)<cost(right):hi=right
        else:lo=left
    return point((lo+hi)/2)


def feasible_geometry_route(vertices):
    """Explicit feasible visit locations, not a lower bound or exact optimum."""
    start=vertices[0][0];centers=[v[0] for v in vertices[1:]];radii=[max(0.,v[1]-.01) for v in vertices[1:]]
    matrix=[[distance(a,b) for b in centers+[start]] for a in centers+[start]]
    candidates=[two_opt(nearest_seed(matrix),matrix),two_opt(insertion_seed(matrix),matrix)]
    angular=sorted(range(len(centers)),key=lambda i:math.atan2(centers[i][1],centers[i][0]));candidates.extend([two_opt(angular,matrix),two_opt(list(reversed(angular)),matrix)])
    order=min(candidates,key=lambda r:route_length(r,matrix));order=or_opt(order,matrix)
    visits=list(centers)
    for _ in range(6):
        for i,j in enumerate(order):
            previous=start if i==0 else visits[order[i-1]];nxt=visits[order[i+1]] if i+1<len(order) else None
            visits[j]=circle_service(centers[j],radii[j],previous,nxt)
        matrix=[[distance(a,b) for b in visits+[start]] for a in visits+[start]];order=or_opt(two_opt(order,matrix),matrix,max_moves=8)
    assert all(distance(p,c)<=r+.011 for p,c,r in zip(visits,centers,radii))
    return route_length(order,matrix),[start]+[visits[i] for i in order]


def exact_open_path(matrix):
    n=len(matrix);dp={(1,0):0.}
    for mask in range(1,1<<n):
        for end in range(n):
            value=dp.get((mask,end))
            if value is None:continue
            for j in range(1,n):
                if not mask&(1<<j):
                    key=(mask|(1<<j),j);dp[key]=min(dp.get(key,math.inf),value+matrix[end][j])
    return min(dp[((1<<n)-1,j)] for j in range(1,n))


def verify_bound():
    rng=random.Random(410)
    for n in (3,5,8):
        for _ in range(8):
            points=[(rng.uniform(-100,100),rng.uniform(-100,100)) for _ in range(n)];radii=[0]+[rng.uniform(0,20) for _ in range(n-1)]
            matrix=[[max(0.,distance(a,b)-radii[i]-radii[j]) for j,b in enumerate(points)] for i,a in enumerate(points)]
            exact=exact_open_path(matrix);bound,_,_=held_karp_open_bound(matrix,exact,300)
            assert bound<=exact+1e-6,(bound,exact)
    return {'exact_dp_comparisons':24,'all_bounds_valid':True}


def scan_action_bound(case, fixed):
    """Exact minimum scan action cost with travel/clearance precedence relaxed.

    Only undetected source bits matter; visiting a point that adds no source
    can be postponed until after discovery (N<16) or skipped (N=16). For N<16
    every empty channel is still scanned at all fixed sites. At a station with
    k empty and u unknown real channels, time is at least 6*(k+u)-1 seconds.
    """
    from functools import lru_cache
    n=len(case['sources']);all_bits=(1<<n)-1;masks=[]
    for point in fixed:
        mask=0
        for i,source in enumerate(case['sources']):
            dx,dy=point[0]-source['x'],point[1]-source['y'];angle=source.get('orientation_deg')
            if math.hypot(dx,dy)<=source['radius']+1e-9 and (angle is None or dx*math.cos(math.radians(angle))+dy*math.sin(math.radians(angle))>=-1e-9):mask|=1<<i
        masks.append(mask)
    candidates=list(set(masks))
    # Dominated reception sets cannot lower this relaxed action-only objective.
    candidates=[a for a in candidates if not any(a!=b and a|b==b for b in candidates)]
    assert all_bits==__import__('functools').reduce(int.__or__,candidates,0)
    empty_cost=6*(20-n)-1
    @lru_cache(None)
    def solve(mask):
        if mask==all_bits:return 0.
        cost=6*(n-mask.bit_count())+(empty_cost if n==16 else 0)
        return min(cost+solve(mask|reception) for reception in candidates if mask|reception!=mask)
    source_measure_equivalent=n+(solve(masks[0])/6 if n<16 else 0)
    scan_cost=(len(fixed)*empty_cost+6*n+solve(masks[0]) if n<16 else empty_cost+6*n+solve(masks[0]))
    return {'minimum_scan_action_time_s':scan_cost,'minimum_scan_plus_clear_time_s':scan_cost+5*n,'minimum_unknown_source_read_count':source_measure_equivalent if n<16 else None,'action_dp_states':solve.cache_info().currsize}

def main():
    p=argparse.ArgumentParser();p.add_argument('--count',type=int,default=96);p.add_argument('--layout',choices=('23','21'),default='23');args=p.parse_args();verification=verify_bound();rows=[];start=time.perf_counter()
    if args.layout=='21':
        from problem4.experiments_v3.coverage_ring_policy import Ring12CoverPolicy
        fixed=Ring12CoverPolicy().coverage_points()
    else:fixed=static_coverage_points()
    for case in generate_suite(4,'development_v2',args.count):
        n=len(case['sources']);points=[(point,0.) for point in fixed]+[((s['x'],s['y']),20.) for s in case['sources']]
        upper,route=feasible_geometry_route(points);matrix=[[max(0.,distance(a,b)-ra-rb) for b,rb in points] for a,ra in points];bound,mst_bound,iters=held_karp_open_bound(matrix,upper)
        action_bound=scan_action_bound(case,fixed)
        if n==16:
            source_vertices=[((0.,0.),0.)]+[((source['x'],source['y']),20.) for source in case['sources']]
            source_upper,_=feasible_geometry_route(source_vertices)
            source_matrix=[[max(0.,distance(a,b)-ra-rb) for b,rb in source_vertices] for a,ra in source_vertices]
            universal_travel_bound,_,_=held_karp_open_bound(source_matrix,source_upper)
        else:universal_travel_bound=bound
        strengthened=(universal_travel_bound/5+action_bound['minimum_scan_plus_clear_time_s'])/n
        if n<16:
            empty=20-n;scan_min=len(fixed)*(5*empty+max(0,empty-1));action_min=scan_min+10*n;time_bound=bound/5+action_min
        else:scan_min=action_min=time_bound=None
        rows.append({'case_id':case['case_id'],'family':case['family'],'source_count':n,'fixed_scan_count':len(fixed),'mst_travel_lower_m':mst_bound,'held_karp_travel_lower_m':bound,'feasible_travel_upper_m':upper,'scan_empty_channels_time_lower_s':scan_min,'all_action_time_lower_s':action_min,'fixed_architecture_time_lower_s':time_bound,'fixed_architecture_seconds_per_source_lower':time_bound/n if time_bound is not None else None,'requires_all_fixed_scans':n<16,'held_karp_iterations':iters,'feasible_route':route,**action_bound,'source_latency_strengthened_seconds_per_source_lower':strengthened,'applicable_travel_lower_m':universal_travel_bound})
        if len(rows)%24==0:print(f'audit {len(rows)}/{args.count}',flush=True)
    applicable=[r for r in rows if r['requires_all_fixed_scans']]
    summary={'cases':len(rows),'fixed_architecture_applicable_cases':len(applicable),'mean_travel_lower_m':statistics.mean(r['held_karp_travel_lower_m'] for r in applicable),'mean_travel_upper_m':statistics.mean(r['feasible_travel_upper_m'] for r in applicable),'mean_fixed_architecture_seconds_per_source_lower':statistics.mean(r['fixed_architecture_seconds_per_source_lower'] for r in applicable),'proven_unable_to_hit_400_under_fixed_architecture':sum(r['fixed_architecture_seconds_per_source_lower']>400 for r in applicable),'runtime_s':time.perf_counter()-start,'mean_strengthened_lower_all_cases':statistics.mean(r['source_latency_strengthened_seconds_per_source_lower'] for r in rows),'mean_strengthened_lower_n_below_16':statistics.mean(r['source_latency_strengthened_seconds_per_source_lower'] for r in applicable),'cases_strengthened_lower_above_400':sum(r['source_latency_strengthened_seconds_per_source_lower']>400 for r in rows)}
    by_n={str(n):{'cases':len(rs),'mean_travel_lb_m':statistics.mean(r['held_karp_travel_lower_m'] for r in rs),'mean_travel_ub_m':statistics.mean(r['feasible_travel_upper_m'] for r in rs),'mean_seconds_per_source_lb':statistics.mean(r['fixed_architecture_seconds_per_source_lower'] for r in rs),'minimum_seconds_per_source_lb':min(r['fixed_architecture_seconds_per_source_lower'] for r in rs),'cases_proven_above_400':sum(r['fixed_architecture_seconds_per_source_lower']>400 for r in rs),'mean_strengthened_seconds_per_source_lb':statistics.mean(r['source_latency_strengthened_seconds_per_source_lower'] for r in rs),'mean_minimum_source_scan_reads':statistics.mean(r['minimum_unknown_source_read_count'] for r in rs)} for n in range(10,16) if (rs:=[r for r in applicable if r['source_count']==n])}
    output={'provenance':'POST-HOC synthetic development_v2 truth diagnostics only; never policy input; not official','bound_scope':f'All {len(fixed)} fixed scans plus all 20m clearance disks must be visited; applies only N<16 in the current batch scan architecture. Geometry upper bound is an explicit feasible route, not an optimum. Action bound is a lower bound, not an executable full-time upper bound.','bound_verification':verification,'summary':summary,'by_source_count':by_n,'episodes':rows}
    suffix='' if args.layout=='23' else '_21'
    (ROOT/'problem4/results/iterations_v3'/f'routing_fixed_architecture_audit{suffix}_{args.count}.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8');print(json.dumps(summary,indent=2));print(json.dumps(by_n,indent=2))
if __name__=='__main__':main()

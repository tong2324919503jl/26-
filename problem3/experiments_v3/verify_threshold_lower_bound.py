"""Independent integer-arithmetic lower bound; never runs or tunes a policy."""
from __future__ import annotations
import hashlib,json,math
from decimal import Decimal
from fractions import Fraction
from itertools import permutations
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CASE_PATH=ROOT/'problem3/examples/threshold_lower_bound_case.json'
RESULT_PATH=ROOT/'problem3/results/iterations_v3/threshold_lower_bound_dp.json'
MICRO=1_000_000


def make_case():
    sources=[]
    for i in range(10):
        theta=math.tau*i/10
        # Truncate both components toward zero so the serialized rational
        # coordinates lie inside, rather than outside, the legal target disk.
        x=math.trunc(1800*math.cos(theta)*MICRO)/MICRO
        y=math.trunc(1800*math.sin(theta)*MICRO)/MICRO
        sources.append(dict(channel=i+1,x=x,y=y,radius=1000.,orientation_deg=None))
    return dict(case_id='p3_threshold_lower_bound_regular_decagon',problem=3,
                provenance='self_constructed_physical_lower_bound_not_official',
                seed=2026091103,split='independent_physical_lower_bound',
                family='regular_decagon_outer_boundary',noise='hash_uniform',
                construction=dict(ideal_radius_m=1800,ideal_angles_deg=[36*i for i in range(10)],
                                  coordinate_rule='truncate each coordinate toward zero to 6 decimal places',
                                  purpose='physical lower bound only; excluded from tuning and benchmark suites'),
                sources=sources)


def integer_points(case):
    points=[]
    assert case['problem']==3 and len(case['sources'])==10
    assert [s['channel'] for s in case['sources']]==list(range(1,11))
    for source in case['sources']:
        x=Decimal(str(source['x']))*MICRO;y=Decimal(str(source['y']))*MICRO
        assert x==x.to_integral_value() and y==y.to_integral_value()
        x,y=int(x),int(y)
        assert x*x+y*y<=(1800*MICRO)**2
        assert source['radius']==1000 and source['orientation_deg'] is None
        points.append((x,y))
    return points


def exact_relaxed_open_tsp(points):
    """Held-Karp DP on integer lower bounds for visits to 20m neighborhoods.

    isqrt computes floor(distance in micrometers) exactly; every graph weight
    is therefore a certified lower bound. The DP itself has no float rounding.
    """
    n=len(points);full=(1<<n)-1
    start=[max(0,math.isqrt(x*x+y*y)-20*MICRO) for x,y in points]
    edges=[[max(0,math.isqrt((x-u)**2+(y-v)**2)-40*MICRO)
            if i!=j else 0 for j,(u,v) in enumerate(points)] for i,(x,y) in enumerate(points)]
    dp=[[None]*n for _ in range(1<<n)];previous=[[None]*n for _ in range(1<<n)]
    for i in range(n):dp[1<<i][i]=start[i]
    transitions=0
    for mask in range(1,full+1):
        for last in range(n):
            value=dp[mask][last]
            if value is None:continue
            for nxt in range(n):
                if mask&(1<<nxt):continue
                transitions+=1;newmask=mask|(1<<nxt);candidate=value+edges[last][nxt]
                if dp[newmask][nxt] is None or candidate<dp[newmask][nxt]:
                    dp[newmask][nxt]=candidate;previous[newmask][nxt]=last
    last=min(range(n),key=lambda i:dp[full][i]);optimum=dp[full][last]
    path=[];mask=full
    while last is not None:
        path.append(last);parent=previous[mask][last];mask^=1<<last;last=parent
    path.reverse()
    assert sorted(path)==list(range(n))
    assert start[path[0]]+sum(edges[a][b] for a,b in zip(path,path[1:]))==optimum
    states=sum(v is not None for row in dp for v in row)
    assert states==n*2**(n-1) and transitions==n*(n-1)*2**(n-2)
    return optimum,path,start,edges,states,transitions,dp[full]


def decimal_value(value):
    return str(Decimal(value.numerator)/Decimal(value.denominator))


def verify_and_save():
    case=make_case()
    CASE_PATH.parent.mkdir(parents=True,exist_ok=True)
    payload=(json.dumps(case,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if CASE_PATH.exists() and CASE_PATH.read_bytes()!=payload:
        raise ValueError('Existing independently named lower-bound case differs; refusing to overwrite')
    CASE_PATH.write_bytes(payload)
    # Re-read the persisted decimal coordinates rather than an idealized copy.
    case=json.loads(CASE_PATH.read_text(encoding='utf8'));points=integer_points(case)
    length,path,start,edges,states,transitions,end_costs=exact_relaxed_open_tsp(points)
    small,_,small_start,small_edges,*_=exact_relaxed_open_tsp(points[:7])
    exhaustive=min(small_start[order[0]]+sum(small_edges[a][b] for a,b in zip(order,order[1:]))
                   for order in permutations(range(7)))
    assert small==exhaustive
    n=len(points);total=Fraction(length,5*MICRO)+5*n;average=total/n
    easy_length=min(start)+(n-1)*min(edges[i][j] for i in range(n) for j in range(n) if i!=j)
    assert average>220 and Fraction(easy_length,5*MICRO*n)+5>220
    ideal_length=1800-20+9*(3600*math.sin(math.pi/10)-40)
    assert 0<=ideal_length-length/MICRO<.0001
    result=dict(
        evidence_type='independent_physical_lower_bound_not_policy_or_platform_score',
        claim_scope='Refutes every legal P3 case having total_time/source_count <= 220; does not refute a batch mean <=220',
        case_path=str(CASE_PATH.relative_to(ROOT)).replace('\\','/'),
        case_sha256=hashlib.sha256(payload).hexdigest(),
        source_count=n,legal_case_checks=dict(channels_1_through_10=True,all_omnidirectional=True,
            all_receive_radii_1000m=True,all_exact_serialized_points_inside_1800m=True),
        relaxations=['All source positions known before starting','No detection or switching time',
                     'No failed clears, no search or completion certification cost','No return to origin required'],
        units=dict(integer_distance='micrometer',virtual_time='second'),
        recurrence='D[{j},j]=start[j]; D[S,j]=min_i(D[S\\{j},i]+edge[i,j]); optimum=min_j D[all,j]',
        weight_formula='start=floor_um(norm(g))-20m; edge=max(0,floor_um(norm(g_i-g_j))-40m)',
        graph_start_costs_um=start,graph_edge_costs_um=edges,dp_state_count=states,
        dp_transition_count=transitions,dp_full_mask_end_costs_um=end_costs,
        independent_dp_check=dict(method='all 7! open paths on the first 7 serialized source points',
                                  enumerated_paths=math.factorial(7),exact_match=small==exhaustive),
        exact_relaxed_open_tsp_um=length,minimizing_channel_order=[i+1 for i in path],
        minimum_pairwise_proof_lower_bound_um=easy_length,
        movement_lower_bound_m=decimal_value(Fraction(length,MICRO)),
        total_time_lower_bound_s=decimal_value(total),
        per_source_lower_bound_s=decimal_value(average),
        threshold_s=220,strict_margin_above_threshold_s=decimal_value(average-220),
        exact_per_source_fraction=dict(numerator=average.numerator,denominator=average.denominator),
        ideal_regular_decagon=dict(chord_formula_m='900*(sqrt(5)-1)',
            movement_lower_bound_formula_m='8100*sqrt(5)-6680',
            per_source_lower_bound_formula_s='162*sqrt(5)-128.6',
            movement_lower_bound_m=ideal_length,per_source_lower_bound_s=ideal_length/50+5),
        important_limit='This DP is exact for a LOWER-BOUND graph, not the optimum continuous route through clearance disks.')
    RESULT_PATH.parent.mkdir(parents=True,exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return {k:result[k] for k in ('movement_lower_bound_m','total_time_lower_bound_s','per_source_lower_bound_s','strict_margin_above_threshold_s','dp_state_count','dp_transition_count')}


if __name__=='__main__':print(json.dumps(verify_and_save(),ensure_ascii=False,indent=2))

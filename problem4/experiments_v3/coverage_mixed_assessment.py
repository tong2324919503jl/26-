"""Finite blind-state packing and full-coverage cost bounds for mixed layouts.

Sampling only finds counterexamples. Every retained source/beam state is then
checked directly at R=1000, and every pair of source positions is >40m apart.
Thus each needs a different 20m optical station for this fixed RF layout.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from problem4.experiments_v3.coverage_replan import _beam_at_blind_source
from problem4.experiments_v3.coverage_independent_check import check


def mst_lower_bound(points,radii):
    """Any visit path must contain a tree; subtract endpoint placement radii."""
    pts=np.asarray(points);r=np.asarray(radii)
    d=np.maximum(0.,np.linalg.norm(pts[:,None,:]-pts[None,:,:],axis=2)-r[:,None]-r[None,:])
    used=np.zeros(len(points),dtype=bool);distance=np.full(len(points),np.inf);distance[0]=0.;total=0.
    for _ in points:
        index=int(np.argmin(np.where(used,np.inf,distance)));total+=distance[index];used[index]=True
        distance=np.minimum(distance,d[index])
    return float(total)


def assess(path):
    row=json.loads(Path(path).read_text());points=row['points'];certificate=row['certificate'];centers=[]
    for detail in certificate['pair_details']:
        if detail['radius_bound_m']>1000.01 and detail['witness'] is not None:centers.append(detail['witness'])
    probes=set()
    for center in centers:
        for dx in range(-100,101,20):
            for dy in range(-100,101,20):
                g=(center[0]+dx,center[1]+dy);norm=math.hypot(*g)
                if 20.01<norm<1800.:probes.add(g)
    valid=[]
    for g in sorted(probes):
        angle=_beam_at_blind_source(points,g,1000.)
        if angle is None:continue
        n=(math.cos(angle),math.sin(angle))
        margin=min(max(math.dist(p,g)-1000.,-((p[0]-g[0])*n[0]+(p[1]-g[1])*n[1])) for p in points)
        if margin>.02:valid.append({'source':g,'heading_rad':angle,'blindness_margin_m':margin})
    best=[]
    rng=np.random.default_rng(123456)
    for repeat in range(12):
        order=sorted(valid,key=lambda r:-r['blindness_margin_m']) if repeat==0 else [valid[i] for i in rng.permutation(len(valid))]
        packed=[]
        for candidate in order:
            if all(math.dist(candidate['source'],other['source'])>40.01 for other in packed):packed.append(candidate)
        if len(packed)>len(best):best=packed
    separation=min((math.dist(a['source'],b['source']) for i,a in enumerate(best) for b in best[i+1:]),default=None)
    # These are mandatory visits for complete geometric coverage, prior to any
    # legitimate max-count early stop. Movement is a whole-path lower bound,
    # not an amount to add to the RF route (which may overlap this tree).
    positions=[(0.,0.)]+points+[w['source'] for w in best]
    movement=mst_lower_bound(positions,[0.]*(len(points)+1)+[20.]*len(best))
    result={'rf_input_file':Path(path).name,'rf_count':len(points),'fixed_layout_patch_lower_bound':len(best),
            'required_initial_origin_optical_stations':1,'total_optical_station_lower_bound':1+len(best),
            'minimum_witness_separation_m':separation,'witnesses':best,'candidate_blind_states':len(valid),
            'witnesses_outside_100m':sum(math.hypot(*w['source'])>100. for w in best),
            'witnesses_outside_500m':sum(math.hypot(*w['source'])>500. for w in best),
            'witnesses_outside_1000m':sum(math.hypot(*w['source'])>1000. for w in best),
            'all20_channels_optical_failure_time_s':60*(1+len(best)),
            'four_empty_channels_failure_time_s':12*(1+len(best)),
            'complete_hybrid_route_lower_bound_m':movement,'complete_hybrid_movement_lower_bound_s':movement/5,
            'full20_static_actions_and_movement_lower_bound_s':movement/5+len(points)*119+60*(1+len(best)),
            'notes':'Costs require complete geometric coverage. Unknown-channel pruning and a legitimate 16-clear early stop can reduce executed actions; 60s per patch assumes all20 channels remain unknown.'}
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('files',nargs='+');parser.add_argument('--independent',action='store_true')
    args=parser.parse_args();rows=[]
    for filename in args.files:
        result=assess(filename)
        if args.independent:result['independent_annulus_certificate']=check(json.loads(Path(filename).read_text())['points'],19.99)
        rows.append(result);print({k:v for k,v in result.items() if k not in ('witnesses','independent_annulus_certificate')},flush=True)
    folder=ROOT/'problem4/results/iterations_v3'
    (folder/'coverage_mixed_optical_cost_bounds.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')

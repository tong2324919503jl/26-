"""Packing lower bound on optical patches for two failed 20-point RF layouts.

Each retained witness has a physically blind orientation at R=1000m, and
every pair of witness positions is farther than 40m apart. Consequently one
20m optical clearance station cannot cover two witnesses. This only bounds
patches for the given RF layouts, not all possible 20-point designs.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from problem4.experiments_v3.coverage_optical_hole import certificate
from problem4.experiments_v3.coverage_route_optimize import robust_counterexample


def assess(path):
    layout=json.loads(path.read_text())['points'];report=certificate(layout,full_report=True)
    candidates=[]
    for row in sorted(report['pair_details'],key=lambda r:-r['radius_bound_m']):
        if row['radius_bound_m']<=1000:continue
        state=robust_counterexample(layout,row)
        if state is None or math.hypot(state[0],state[1])<=20.01:continue
        x,y,angle=state;nx,ny=math.cos(angle),math.sin(angle)
        margin=min(max(math.dist(point,(x,y))-1000.,-((point[0]-x)*nx+(point[1]-y)*ny)) for point in layout)
        if margin>.01:candidates.append({'source':(x,y),'heading_rad':angle,'blindness_margin_m':margin})
    packed=[]
    for row in sorted(candidates,key=lambda r:-r['blindness_margin_m']):
        if all(math.dist(row['source'],other['source'])>40.01 for other in packed):packed.append(row)
    separation=min((math.dist(a['source'],b['source']) for i,a in enumerate(packed) for b in packed[i+1:]),default=None)
    return {'input':path.name,'minimum_optical_patch_stations_for_this_rf_layout':len(packed),
            'minimum_witness_separation_m':separation,'witnesses':packed}


if __name__=='__main__':
    folder=ROOT/'problem4'/'results'/'iterations_v3'
    results=[assess(folder/name) for name in ('coverage20_optimization_seed2.json','coverage20_optimization_seed2_optical.json')]
    (folder/'coverage20_optical_patch_lower_bound.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    print([{k:v for k,v in row.items() if k!='witnesses'} for row in results])

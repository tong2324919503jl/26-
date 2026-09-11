"""Geometry-only nonsymmetric search for a certified 20-point layout.

Unlike the earlier short-edge objective, optimize the actual finite
half-plane/Voronoi coverage bound. Failure is not a point-count lower bound.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from problem4.coverage import directional_cover_certificate
from problem4.experiments_v3.coverage_ring_policy import ring_points


def optimize(seed=0,max_iterations=60,optical=False):
    import numpy as np
    from scipy.optimize import minimize
    started=time.perf_counter();rng=np.random.default_rng(seed)
    fixed=ring_points(12,7,997.)[:13]
    initial=np.r_[np.full(7,997.),np.zeros(7)]
    if seed:initial[7:]=rng.uniform(-70,70,7)
    if optical:
        from problem4.experiments_v3.coverage_optical_hole import certificate as optical_certificate
        previous=ROOT/'problem4'/'results'/'iterations_v3'/f'coverage20_optimization_seed{seed}.json'
        if previous.exists():
            vertices=json.loads(previous.read_text())['points'][13:]
            initial=np.asarray([math.hypot(*p) for p in vertices]+[
                ((math.atan2(p[1],p[0])-i*math.tau/7+math.pi)%math.tau-math.pi)*1000
                for i,p in enumerate(vertices)])
    best={'bound':math.inf};history=[];evaluations=0
    def unpack(x):
        return fixed+[(float(x[i]*math.cos(i*math.tau/7+x[i+7]/1000)),
                       float(x[i]*math.sin(i*math.tau/7+x[i+7]/1000))) for i in range(7)]
    def objective(x):
        nonlocal evaluations
        points=unpack(x)
        report=optical_certificate(points) if optical else directional_cover_certificate(points,early_exit=False)
        value=report['max_directional_radius_bound_m'];evaluations+=1
        if value<best['bound']-.01:
            best.update(bound=value,points=points,certificate=report)
            history.append({'evaluation':evaluations,'bound_m':value,'elapsed_s':time.perf_counter()-started})
            if len(history)%10==0:print(seed,evaluations,round(value,5),flush=True)
        return value
    result=minimize(objective,initial,method='SLSQP',bounds=[(850.,1020. if optical else 999.)]*7+[(-200.,200.)]*7,
                    options={'maxiter':max_iterations,'ftol':.001,'eps':.02})
    best.update(seed=seed,optimizer_message=result.message,evaluations=evaluations,
                runtime_s=time.perf_counter()-started,history=history)
    folder=ROOT/'problem4'/'results'/'iterations_v3';folder.mkdir(parents=True,exist_ok=True)
    suffix='_optical' if optical else ''
    (folder/f'coverage20_optimization_seed{seed}{suffix}.json').write_text(json.dumps(best,indent=2)+'\n',encoding='utf-8')
    print({k:v for k,v in best.items() if k not in ('points','history','certificate')},flush=True)
    return best


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--seed',type=int,default=0)
    parser.add_argument('--iterations',type=int,default=60);parser.add_argument('--optical',action='store_true');args=parser.parse_args()
    optimize(args.seed,args.iterations,args.optical)

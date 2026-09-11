"""Twenty RF stations, none at the origin; geometry-only finite certification.

The robot still starts at (0,0), but no origin scan is implied or added.
Only a certified layout could proceed to a simulation, including first travel.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys
import time
import numpy as np
from scipy.optimize import differential_evolution,minimize
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from problem4.coverage import directional_cover_certificate
from problem4.experiments_v3.coverage_tangent20 import fast_bound
from problem4.experiments_v3.coverage_tangent20_epigraph import pair_bounds
from problem4.experiments_v3.coverage_independent_check import check


def rings(outer,inner_radius,phase,support=1801.):
    radius=support/math.cos(math.pi/outer);inner=20-outer
    return np.asarray([(radius*math.cos(i*math.tau/outer),radius*math.sin(i*math.tau/outer)) for i in range(outer)]+
                      [(inner_radius*math.cos(i*math.tau/inner+phase),inner_radius*math.sin(i*math.tau/inner+phase)) for i in range(inner)])


def three_rings(core_radius,middle_radius,core_phase,middle_phase,support=1801.):
    radius=support/math.cos(math.pi/12)
    return np.asarray([(radius*math.cos(i*math.tau/12),radius*math.sin(i*math.tau/12)) for i in range(12)]+
                      [(r*math.cos(i*math.tau/n+phase),r*math.sin(i*math.tau/n+phase))
                       for n,r,phase in ((3,core_radius,core_phase),(5,middle_radius,middle_phase)) for i in range(n)])


def screen(seed=0):
    rows=[];started=time.perf_counter();fast_bound(rings(12,997.32,0.))
    for outer in range(8,15):
        result=differential_evolution(lambda x:fast_bound(rings(outer,*x)),
                                      bounds=[(650.,1250.),(0.,math.tau/outer),(1801.,1900.)],
                                      seed=seed+outer,popsize=8,maxiter=100,tol=1e-6,polish=False)
        points=rings(outer,*result.x);certificate=directional_cover_certificate(points,early_exit=False,full_report=True)
        assert abs(result.fun-certificate['max_directional_radius_bound_m'])<1e-5
        row={'structure':[outer,20-outer],'parameters':result.x.tolist(),'points':points.tolist(),
             'bound_m':float(result.fun),'certificate':certificate,'evaluations':result.nfev,'seed':seed}
        rows.append(row);print(row['structure'],row['parameters'],row['bound_m'],flush=True)
    result=differential_evolution(lambda x:fast_bound(three_rings(*x)),
                                 bounds=[(100.,900.),(750.,1400.),(0.,math.pi/6),(0.,math.pi/6),(1801.,1900.)],
                                 seed=seed+123,popsize=8,maxiter=130,tol=1e-6,polish=False)
    points=three_rings(*result.x);certificate=directional_cover_certificate(points,early_exit=False,full_report=True)
    assert abs(result.fun-certificate['max_directional_radius_bound_m'])<1e-5
    row={'structure':[12,3,5],'parameters':result.x.tolist(),'points':points.tolist(),'bound_m':float(result.fun),
         'certificate':certificate,'evaluations':result.nfev,'seed':seed}
    rows.append(row);print(row['structure'],row['parameters'],row['bound_m'],flush=True)
    folder=ROOT/'problem4/results/iterations_v3';folder.mkdir(parents=True,exist_ok=True)
    (folder/f'coverage_noorigin20_screen_seed{seed}.json').write_text(json.dumps({'runtime_s':time.perf_counter()-started,'rows':rows},indent=2)+'\n',encoding='utf-8')
    return rows


def refine(row,seed=0,iterations=220):
    """Remove regularity after screening: outer support angles and inner x,y."""
    outer=row['structure'][0];inner=20-outer;points=np.asarray(row['points']);rng=np.random.default_rng(seed)
    z0=np.r_[np.asarray(row.get('normal_offsets_rad',np.zeros(outer-1))),points[outer:].ravel()/1000.,row['bound_m']/1000.]
    if seed:z0[:-1]+=np.r_[rng.normal(0,.02,outer-1),rng.normal(0,.04,inner*2)]
    def unpack(z):
        normals=np.arange(outer)*math.tau/outer-math.pi/outer
        normals[1:]+=z[:outer-1];answer=np.zeros((20,2))
        for i in range(outer):
            first=normals[i];second=normals[(i+1)%outer]+(math.tau if i==outer-1 else 0.)
            angle=(first+second)/2;radius=1801/math.cos((second-first)/2)
            answer[i]=[radius*math.cos(angle),radius*math.sin(angle)]
        answer[outer:]=1000*z[outer-1:-1].reshape(inner,2)
        return answer
    best={'bound_m':float(pair_bounds(unpack(z0)).max()),'z':z0.tolist()};history=[];evaluations=0;started=time.perf_counter()
    def constraints(z):
        nonlocal evaluations
        values=pair_bounds(unpack(z));bound=float(values.max());evaluations+=1
        if bound<best['bound_m']-1e-5:
            best.update(bound_m=bound,z=z.tolist());history.append([evaluations,bound,time.perf_counter()-started])
        return z[-1]-values/1000.
    result=minimize(lambda z:z[-1],z0,method='SLSQP',bounds=[(-.21,.21)]*(outer-1)+[(-1.45,1.45)]*(inner*2)+[(.9,1.8)],
                    constraints={'type':'ineq','fun':constraints},options={'maxiter':iterations,'ftol':1e-9,'eps':1e-6})
    points=unpack(np.asarray(best['z']));certificate=directional_cover_certificate(points,early_exit=False,full_report=True)
    assert abs(certificate['max_directional_radius_bound_m']-best['bound_m'])<1e-5
    best.update(points=points.tolist(),certificate=certificate,history=history,structure=row['structure'],seed=seed,
                evaluations=evaluations,runtime_s=time.perf_counter()-started,optimizer_message=str(result.message),
                origin_is_rf_station=False,minimum_rf_station_radius_m=float(np.min(np.linalg.norm(points,axis=1))))
    folder=ROOT/'problem4/results/iterations_v3';suffix='_'.join(map(str,row['structure']))
    (folder/f'coverage_noorigin20_refine_{suffix}_seed{seed}.json').write_text(json.dumps(best,indent=2)+'\n',encoding='utf-8')
    print(suffix,{k:v for k,v in best.items() if k not in ('z','points','certificate','history')},flush=True)
    return best


def verify_best():
    folder=ROOT/'problem4/results/iterations_v3'
    files=list(folder.glob('coverage_noorigin20_refine_*.json'))
    path=min(files,key=lambda p:json.loads(p.read_text())['bound_m'])
    candidate=json.loads(path.read_text());points=candidate['points'];result=check(points)
    for detail in sorted(candidate['certificate']['pair_details'],key=lambda d:-d['radius_bound_m']):
        if detail['witness'] is None or math.hypot(*detail['witness'])>=1700:continue
        normal=detail['left_normal'];source=[detail['witness'][k]+.1*normal[k] for k in range(2)]
        visible=[math.dist(p,source) for p in points if sum(normal[k]*(p[k]-source[k]) for k in range(2))>=0]
        if visible and min(visible)>1000.01:
            result['explicit_blind_witness']={'source':source,'beam_axis_degrees':math.degrees(math.atan2(normal[1],normal[0]))%360,
                 'nearest_in_closed_beam_m':min(visible),'source_radius_m':math.hypot(*source),'pair':detail['pair']}
            break
    result['input_file']=path.name
    result['minimum_rf_station_radius_m']=min(math.hypot(*p) for p in points)
    (folder/'coverage_noorigin20_independent_certificate.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print({k:v for k,v in result.items() if k!='pairs'},flush=True)
    return result


def warm_refine(seed=0):
    """Let the previously fixed origin move as one of eight free inner sites."""
    path=ROOT/'problem4/results/iterations_v3/coverage_tangent20_seed5_de120_epigraph.json'
    old=json.loads(path.read_text());theta=-math.pi/12
    rotation=np.array([[math.cos(theta),-math.sin(theta)],[math.sin(theta),math.cos(theta)]])
    points=np.asarray(old['points'][1:13]+[old['points'][0]]+old['points'][13:])@rotation.T
    row={'structure':[12,1,7],'points':points.tolist(),
         'normal_offsets_rad':(np.asarray(old['x'][:11])*math.pi/180).tolist(),'bound_m':old['bound_m']}
    return refine(row,seed,200)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--seed',type=int,default=0)
    parser.add_argument('--refine',action='store_true');parser.add_argument('--verify-best',action='store_true')
    parser.add_argument('--warm-start',action='store_true');args=parser.parse_args()
    if args.verify_best:verify_best()
    elif args.warm_start:warm_refine(args.seed)
    elif args.refine:
        data=json.loads((ROOT/'problem4/results/iterations_v3/coverage_noorigin20_screen_seed0.json').read_text())['rows']
        for row in sorted(data,key=lambda r:r['bound_m'])[:3]:refine(row,args.seed)
    else:screen(args.seed)

"""RF coverage outside an explicitly optically searched central disk.

Geometry experiments only. A 20m optical disk requires a real /clear action
for every unknown channel; neither /measure nor near certifies this disk.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys
import time
import numpy as np
from numba import njit
from scipy.optimize import minimize_scalar,minimize
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from problem4.experiments_v3.coverage_tangent20 import clip
from problem4.experiments_v3.coverage_optical_hole import certificate


@njit(cache=True)
def annular_max2(poly,count,sx,sy,inner=19.99):
    worst=0.;outer=1800.
    for i in range(count):
        ax,ay=poly[i];norm=math.hypot(ax,ay)
        if inner-1e-7<=norm<=outer+1e-7:worst=max(worst,(ax-sx)**2+(ay-sy)**2)
    for boundary in (outer,inner):
        for i in range(count):
            ax,ay=poly[i];bx,by=poly[(i+1)%count]
            dx=bx-ax;dy=by-ay;length2=dx*dx+dy*dy
            if length2<1e-16:continue
            middle=-(ax*dx+ay*dy)/length2
            fx=ax+middle*dx;fy=ay+middle*dy;radial2=boundary*boundary-fx*fx-fy*fy
            if radial2 < -1e-6:continue
            half=math.sqrt(max(0.,radial2)/length2)
            for t in (middle-half,middle+half):
                if -1e-9<=t<=1+1e-9:
                    px=ax+t*dx;py=ay+t*dy;worst=max(worst,(px-sx)**2+(py-sy)**2)
        norm=math.hypot(sx,sy)
        fx=-boundary*sx/norm if norm else boundary;fy=-boundary*sy/norm if norm else 0.
        inside=count>0
        for i in range(count):
            ax,ay=poly[i];bx,by=poly[(i+1)%count]
            if (bx-ax)*(fy-ay)-(by-ay)*(fx-ax)<-1e-6*max(1.,math.hypot(bx-ax,by-ay)):
                inside=False;break
        if inside:worst=max(worst,(fx-sx)**2+(fy-sy)**2)
    return worst


@njit(cache=True)
def pair_bounds(points,inner=19.99):
    size=len(points);answer=np.zeros(size*size)
    box=np.array([[-1800.,-1800.],[1800.,-1800.],[1800.,1800.],[-1800.,1800.]])
    ids=np.empty(size,dtype=np.int64)
    for i in range(size):
        for j in range(size):
            if i==j:continue
            ax,ay=points[i];bx,by=points[j];length=math.hypot(bx-ax,by-ay)
            if length==0:continue
            nx=-(by-ay)/length;ny=(bx-ax)/length;offset=nx*ax+ny*ay
            if offset>=1800.:continue
            n=0
            for k in range(size):
                if nx*points[k,0]+ny*points[k,1]>offset+1e-7:ids[n]=k;n+=1
            if n==0:answer[i*size+j]=1e9;continue
            segment,segsize=clip(box,4,-nx,-ny,-offset)
            worst=0.
            for k in range(n):
                sx,sy=points[ids[k]];poly=segment;count=segsize
                for m in range(n):
                    if m==k:continue
                    ox,oy=points[ids[m]];dx=ox-sx;dy=oy-sy
                    poly,count=clip(poly,count,dx,dy,(dx*(ox+sx)+dy*(oy+sy))/2)
                    if count==0:break
                worst=max(worst,annular_max2(poly,count,sx,sy,inner))
            answer[i*size+j]=math.sqrt(worst)
    return answer


def rings(total,outer,origin,radius,phase=0.):
    inner=total-outer-int(origin)
    outer_radius=1801/math.cos(math.pi/outer)
    points=[(0.,0.)] if origin else []
    points += [(outer_radius*math.cos(i*math.tau/outer),outer_radius*math.sin(i*math.tau/outer)) for i in range(outer)]
    points += [(radius*math.cos(i*math.tau/inner+phase),radius*math.sin(i*math.tau/inner+phase)) for i in range(inner)]
    return np.asarray(points)


def screen():
    rows=[];started=time.perf_counter()
    for total in range(15,20):
        for outer in range(8,14):
            for origin in (False,True):
                inner=total-outer-int(origin)
                if inner<3:continue
                best=None
                for phase in (0.,math.pi/outer):
                    result=minimize_scalar(lambda radius:float(pair_bounds(rings(total,outer,origin,radius,phase)).max()),
                                           bounds=(650.,1200.),method='bounded',options={'xatol':.025})
                    row={'total_rf':total,'outer':outer,'inner':inner,'rf_origin':origin,'inner_radius_m':float(result.x),
                         'phase_rad':phase,'bound_m':float(result.fun),'points':rings(total,outer,origin,float(result.x),phase).tolist()}
                    if best is None or row['bound_m']<best['bound_m']:best=row
                rows.append(best)
        selected=min((r for r in rows if r['total_rf']==total),key=lambda r:r['bound_m'])
        print({k:v for k,v in selected.items() if k!='points'},flush=True)
    rows.sort(key=lambda r:r['bound_m'])
    folder=ROOT/'problem4/results/iterations_v3';folder.mkdir(parents=True,exist_ok=True)
    (folder/'coverage_mixed_ring_screen.json').write_text(json.dumps({'runtime_s':time.perf_counter()-started,'rows':rows},indent=2)+'\n',encoding='utf-8')
    return rows


def verify():
    rows=[]
    for total,outer,origin,radius in ((19,12,False,999.),(19,12,True,1050.),(18,10,True,950.),(17,10,False,800.),(16,9,True,900.),(15,8,False,1100.)):
        points=rings(total,outer,origin,radius,.017)
        fast=float(pair_bounds(points).max());reference=certificate(points)['max_directional_radius_bound_m']
        if abs(fast-reference)>1e-5:raise AssertionError((fast,reference))
        rows.append({'count':total,'outer':outer,'rf_origin':origin,'fast_m':fast,'reference_m':reference,'difference_m':abs(fast-reference)})
    folder=ROOT/'problem4/results/iterations_v3';folder.mkdir(parents=True,exist_ok=True)
    (folder/'coverage_mixed_acceleration_check.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
    print('Verified',len(rows),'geometries; max difference',max(r['difference_m'] for r in rows),flush=True)


def refine(row,seed=0,iterations=220):
    """Open all inner coordinates and irregular circumscribed outer angles."""
    total=row['total_rf'];outer=row['outer'];origin=row['rf_origin'];inner=row['inner']
    points=np.asarray(row['points']);offset=int(origin);rng=np.random.default_rng(seed)
    x0=np.r_[np.zeros(outer-1),points[offset+outer:].ravel()/1000.]
    if seed:x0+=np.r_[rng.normal(0,.03,outer-1),rng.normal(0,.045,inner*2)]
    def unpack(z):
        normals=np.arange(outer)*math.tau/outer-math.pi/outer
        normals[1:]+=z[:outer-1]
        answer=np.zeros((total,2))
        for i in range(outer):
            first=normals[i];second=normals[(i+1)%outer]+(math.tau if i==outer-1 else 0.)
            angle=(first+second)/2;r=1801/math.cos((second-first)/2)
            answer[offset+i]=[r*math.cos(angle),r*math.sin(angle)]
        answer[offset+outer:]=1000*z[outer-1:-1].reshape(inner,2)
        return answer
    z0=np.r_[x0,1.1];v=float(pair_bounds(unpack(z0)).max());z0[-1]=v/1000
    best={'bound_m':v,'z':z0.tolist()};history=[];evaluations=0;started=time.perf_counter()
    def constraints(z):
        nonlocal evaluations
        values=pair_bounds(unpack(z));bound=float(values.max());evaluations+=1
        if bound<best['bound_m']-1e-5:
            best.update(bound_m=bound,z=z.tolist());history.append([evaluations,bound,time.perf_counter()-started])
        return z[-1]-values/1000.
    result=minimize(lambda z:z[-1],z0,method='SLSQP',bounds=[(-.24,.24)]*(outer-1)+[(-1.35,1.35)]*(inner*2)+[(.9,2.)],
                    constraints={'type':'ineq','fun':constraints},options={'maxiter':iterations,'ftol':1e-9,'eps':1e-6})
    points=unpack(np.asarray(best['z']));report=certificate(points,full_report=True)
    if abs(report['max_directional_radius_bound_m']-best['bound_m'])>1e-5:raise AssertionError('Final acceleration mismatch')
    best.update(total_rf=total,outer=outer,inner=inner,rf_origin=origin,seed=seed,points=points.tolist(),certificate=report,
                history=history,evaluations=evaluations,runtime_s=time.perf_counter()-started,optimizer_message=str(result.message))
    folder=ROOT/'problem4/results/iterations_v3';path=folder/f'coverage_mixed_{total}rf_outer{outer}_origin{int(origin)}_seed{seed}.json'
    path.write_text(json.dumps(best,indent=2)+'\n',encoding='utf-8')
    print(path.name,{k:v for k,v in best.items() if k not in ('points','z','certificate','history')},flush=True)
    return best


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verify',action='store_true')
    parser.add_argument('--refine',action='store_true');parser.add_argument('--seed',type=int,default=0);args=parser.parse_args()
    if args.verify:verify()
    elif args.refine:
        data=json.loads((ROOT/'problem4/results/iterations_v3/coverage_mixed_ring_screen.json').read_text())['rows']
        for count in (19,18,17):
            for row in sorted((r for r in data if r['total_rf']==count),key=lambda r:r['bound_m'])[:2]:refine(row,args.seed)
    else:screen()

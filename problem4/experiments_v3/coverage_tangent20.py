"""Geometry-only 20-site search with a variable circumscribed outer polygon.

No case data are read. Numba accelerates the same finite cell/arc enumeration;
the original standard-library certificate is the acceptance authority.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import numpy as np
from numba import njit
from scipy.optimize import differential_evolution, minimize

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from problem4.coverage import directional_cover_certificate


@njit(cache=True)
def clip(poly,count,nx,ny,offset):
    out=np.empty((64,2));size=0
    if count==0:return out,0
    norm=math.hypot(nx,ny)
    if norm==0:return poly,count
    nx/=norm;ny/=norm;offset=offset/norm+1e-8
    ax,ay=poly[count-1];fa=nx*ax+ny*ay-offset
    for i in range(count):
        bx,by=poly[i];fb=nx*bx+ny*by-offset
        if (fa<=0)!=(fb<=0):
            t=fa/(fa-fb);out[size,0]=ax+t*(bx-ax);out[size,1]=ay+t*(by-ay);size+=1
        if fb<=0:out[size,0]=bx;out[size,1]=by;size+=1
        ax=bx;ay=by;fa=fb
    return out,size


@njit(cache=True)
def cell_max2(poly,count,sx,sy):
    worst=0.;D=1800.
    for i in range(count):
        ax,ay=poly[i];bx,by=poly[(i+1)%count]
        if math.hypot(ax,ay)<=D+1e-7:worst=max(worst,(ax-sx)**2+(ay-sy)**2)
        dx=bx-ax;dy=by-ay;length2=dx*dx+dy*dy
        if length2<1e-16:continue
        middle=-(ax*dx+ay*dy)/length2
        fx=ax+middle*dx;fy=ay+middle*dy;radial2=D*D-fx*fx-fy*fy
        if radial2 < -1e-6:continue
        half=math.sqrt(max(0.,radial2)/length2)
        for t in (middle-half,middle+half):
            if -1e-9<=t<=1+1e-9:
                px=ax+t*dx;py=ay+t*dy;worst=max(worst,(px-sx)**2+(py-sy)**2)
    norm=math.hypot(sx,sy)
    fx=-D*sx/norm if norm else D;fy=-D*sy/norm if norm else 0.
    inside=count>0
    for i in range(count):
        ax,ay=poly[i];bx,by=poly[(i+1)%count]
        if (bx-ax)*(fy-ay)-(by-ay)*(fx-ax)<-1e-6*max(1.,math.hypot(bx-ax,by-ay)):
            inside=False;break
    if inside:worst=max(worst,(fx-sx)**2+(fy-sy)**2)
    return worst


@njit(cache=True)
def fast_bound(points):
    size=len(points);worst=0.;box=np.array([[-1800.,-1800.],[1800.,-1800.],[1800.,1800.],[-1800.,1800.]])
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
            if n==0:return math.inf
            segment,segsize=clip(box,4,-nx,-ny,-offset)
            for k in range(n):
                sx,sy=points[ids[k]];poly=segment;count=segsize
                for m in range(n):
                    if m==k:continue
                    ox,oy=points[ids[m]];dx=ox-sx;dy=oy-sy
                    poly,count=clip(poly,count,dx,dy,(dx*(ox+sx)+dy*(oy+sy))/2)
                    if count==0:break
                worst=max(worst,cell_max2(poly,count,sx,sy))
    return math.sqrt(worst)


def unpack(x,support=1801.):
    normals=np.arange(12)*math.tau/12
    normals[1:]+=x[:11]*math.pi/180
    points=np.zeros((20,2))
    for i in range(12):
        first=normals[i];second=normals[(i+1)%12]+(math.tau if i==11 else 0.)
        middle=(first+second)/2;r=support/math.cos((second-first)/2)
        points[i+1]=(r*math.cos(middle),r*math.sin(middle))
    points[13:]=x[11:].reshape(7,2)
    return points


def initial(seed):
    rng=np.random.default_rng(seed);x=np.zeros(25)
    angle=np.arange(7)*math.tau/7+math.pi/12
    x[11:]=np.column_stack((995*np.cos(angle),995*np.sin(angle))).ravel()
    if seed:
        x[:11]=rng.uniform(-6,6,11)
        x[11:]+=rng.normal(0,75,14)
    previous=ROOT/'problem4/results/iterations_v3'/f'coverage20_optimization_seed{seed%3}.json'
    if seed>=3 and previous.exists():
        points=np.asarray(json.loads(previous.read_text())['points'][13:])
        theta=math.pi/12+seed*.03
        rot=np.array([[math.cos(theta),-math.sin(theta)],[math.sin(theta),math.cos(theta)]])
        x[11:]=(points@rot.T).ravel()
    return x


def verify_acceleration(count=16):
    rows=[]
    for seed in range(count):
        points=unpack(initial(seed));actual=fast_bound(points)
        original=directional_cover_certificate(points,early_exit=False)
        delta=abs(actual-original['max_directional_radius_bound_m'])
        if delta>1e-5:raise AssertionError((seed,actual,original))
        rows.append({'seed':seed,'accelerated_m':actual,'original_m':original['max_directional_radius_bound_m'],'difference_m':delta})
    return rows


def optimize(seed=0,iterations=120,global_iterations=0):
    started=time.perf_counter();evaluations=0;history=[];best={'bound_m':math.inf}
    x0=initial(seed);fast_bound(unpack(x0))
    def objective(x):
        nonlocal evaluations
        value=fast_bound(unpack(x));evaluations+=1
        if value<best['bound_m']-.0001:
            best.update(bound_m=value,x=x.tolist())
            history.append({'evaluation':evaluations,'bound_m':value,'elapsed_s':time.perf_counter()-started})
        return value
    bounds=[(-14.5,14.5)]*11+[(-1350.,1350.)]*14
    objective(x0)
    if global_iterations:
        rng=np.random.default_rng(seed)
        population=np.tile(x0,(125,1))
        population[:,0:11]+=rng.normal(0,5,(125,11))
        population[:,11:]+=rng.normal(0,100,(125,14))
        population=np.clip(population,np.array(bounds)[:,0],np.array(bounds)[:,1]);population[0]=x0
        differential_evolution(objective,bounds,maxiter=global_iterations,popsize=5,polish=False,
                               init=population,seed=seed,tol=.0002,mutation=(.3,.8),recombination=.85)
    result=minimize(objective,np.asarray(best['x']),method='SLSQP',bounds=bounds,
                    options={'maxiter':iterations,'ftol':.00002,'eps':.015})
    points=unpack(np.asarray(best['x']));certificate=directional_cover_certificate(points,early_exit=False,full_report=True)
    if abs(best['bound_m']-certificate['max_directional_radius_bound_m'])>1e-5:raise AssertionError('Accelerated final differs')
    normals=np.arange(12)*30.;normals[1:]+=np.asarray(best['x'])[:11]
    gaps=np.diff(np.r_[normals,normals[0]+360.])
    best.update(seed=seed,points=points.tolist(),certificate=certificate,normal_gaps_deg=gaps.tolist(),
                evaluations=evaluations,runtime_s=time.perf_counter()-started,history=history,
                optimizer_message=str(result.message),global_iterations=global_iterations,
                experiment_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    folder=ROOT/'problem4/results/iterations_v3';folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'coverage_tangent20_seed{seed}_de{global_iterations}.json'
    path.write_text(json.dumps(best,indent=2)+'\n',encoding='utf-8')
    print({k:v for k,v in best.items() if k not in ('points','x','certificate','history')},flush=True)
    return best


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--seed',type=int,default=0)
    parser.add_argument('--iterations',type=int,default=120);parser.add_argument('--global-iterations',type=int,default=0)
    parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    if args.verify:
        rows=verify_acceleration();folder=ROOT/'problem4/results/iterations_v3';folder.mkdir(parents=True,exist_ok=True)
        (folder/'coverage_tangent20_acceleration_check.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
        print('Verified',len(rows),'geometries; maximum difference',max(r['difference_m'] for r in rows),flush=True)
    else:optimize(args.seed,args.iterations,args.global_iterations)

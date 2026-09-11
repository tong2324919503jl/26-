"""Epigraph refinement of the variable-tangent 20-point geometry experiment."""
from __future__ import annotations
import json
import math
from pathlib import Path
import sys
import time
import numpy as np
from numba import njit
from scipy.optimize import minimize
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from problem4.experiments_v3.coverage_tangent20 import clip,cell_max2,unpack,fast_bound
from problem4.coverage import directional_cover_certificate


@njit(cache=True)
def pair_bounds(points):
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
                worst=max(worst,cell_max2(poly,count,sx,sy))
            answer[i*size+j]=math.sqrt(worst)
    return answer


def refine(path,iterations=200):
    old=json.loads(Path(path).read_text());scale=np.r_[np.full(11,10.),np.full(14,1000.)]
    x0=np.asarray(old['x']);z=np.r_[x0/scale,old['bound_m']/1000]
    initial=pair_bounds(unpack(x0));assert abs(initial.max()-fast_bound(unpack(x0)))<1e-6
    best={'bound_m':float(initial.max()),'x':x0.tolist()};history=[];evaluations=0;started=time.perf_counter()
    def constraints(z):
        nonlocal evaluations
        x=z[:-1]*scale;values=pair_bounds(unpack(x));bound=float(values.max());evaluations+=1
        if bound<best['bound_m']-1e-5:
            best.update(bound_m=bound,x=x.tolist());history.append([evaluations,bound,time.perf_counter()-started])
        return z[-1]-values/1000.
    result=minimize(lambda z:z[-1],z,method='SLSQP',
                    bounds=[(-1.45,1.45)]*11+[(-1.35,1.35)]*14+[(.9,1.5)],
                    constraints={'type':'ineq','fun':constraints},
                    options={'maxiter':iterations,'ftol':1e-9,'eps':1e-6})
    points=unpack(np.asarray(best['x']));certificate=directional_cover_certificate(points,early_exit=False,full_report=True)
    assert abs(certificate['max_directional_radius_bound_m']-best['bound_m'])<1e-5
    best.update(points=points.tolist(),certificate=certificate,evaluations=evaluations,runtime_s=time.perf_counter()-started,
                history=history,source_file=str(Path(path).name),optimizer_message=str(result.message))
    output=Path(path).with_name(Path(path).stem+'_epigraph.json');output.write_text(json.dumps(best,indent=2)+'\n',encoding='utf-8')
    print(output.name,{k:v for k,v in best.items() if k not in ('points','x','certificate','history')},flush=True)
    return best


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('files',nargs='+');parser.add_argument('--iterations',type=int,default=200)
    args=parser.parse_args()
    for path in args.files:refine(path,args.iterations)

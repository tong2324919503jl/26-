"""Shorten the complete route by convex assigned-observation constraints.

Each sampled source/beam state is assigned to one current observation point.
That point must remain inside its reception disk and emitting half-plane.
The resulting coordinate problem is convex for a fixed visit order. Finite
analytic certificates alone accept new layouts; failed extrema add states.
Thus discrete optimization proposes routes but never proves their coverage.
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
from problem4.experiments_v3.coverage_replan import source_heading_grid,_beam_at_blind_source
from problem4.experiments_v3.coverage_ring_policy import ring_points
from problem4.experiments_v3.coverage_three_rings import shortest_route


def robust_counterexample(points,detail):
    a,b=(points[i] for i in detail['pair']);length=math.dist(a,b)
    normal=(-(b[1]-a[1])/length,(b[0]-a[0])/length)
    witness=detail['witness'];best=None
    for step in (.01,.1,1.,3.,10.,30.,75.,150.,300.):
        g=(witness[0]+step*normal[0],witness[1]+step*normal[1]);norm=math.hypot(*g)
        if norm>1800:g=(g[0]*(1800-1e-7)/norm,g[1]*(1800-1e-7)/norm)
        angle=_beam_at_blind_source(points,g,999.999)
        if angle is None:continue
        beam=(math.cos(angle),math.sin(angle))
        margin=min(max(math.dist(p,g)-999.999,-((p[0]-g[0])*beam[0]+(p[1]-g[1])*beam[1])) for p in points)
        if best is None or margin>best[0]:best=(margin,(g[0],g[1],angle))
    return best[1] if best else None


def optimize(extra_points=0,rounds=30,inner_extra=False,assignment='nearest'):
    import numpy as np
    from scipy.optimize import minimize
    from scipy.spatial import ConvexHull,QhullError
    started=time.perf_counter()
    p=ring_points(12,8,997.32)
    for _ in range(extra_points):
        _,route=shortest_route(p)
        edges=list(zip(route,route[1:]))
        if inner_extra:edges=[(a,b) for a,b in edges if max(math.hypot(*p[a]),math.hypot(*p[b]))<1500]
        a,b=max(edges,key=lambda ij:math.dist(p[ij[0]],p[ij[1]]))
        p.append(((p[a][0]+p[b][0])/2,(p[a][1]+p[b][1])/2))
    states=source_heading_grid();history=[];best_report=None
    initial_length,_=shortest_route(p)
    for iteration in range(rounds):
        length,route=shortest_route(p);n=len(p)
        source=np.asarray(states)[:,:2]
        normals=np.column_stack((np.cos(np.asarray(states)[:,2]),np.sin(np.asarray(states)[:,2])))
        delta=np.asarray(p)[None,:,:]-source[:,None,:]
        distance2=np.sum(delta**2,axis=2)
        feasible=(distance2<=999.0**2)&(np.sum(delta*normals[:,None,:],axis=2)>=-1e-8)
        if not np.all(np.any(feasible,axis=1)):raise RuntimeError('Certified incumbent lost a sampled state')
        if assignment=='slack':
            direction=np.zeros((n,2))
            for k,index in enumerate(route):
                for other in ([route[k-1]] if k else [0])+([route[k+1]] if k+1<len(route) else []):
                    difference=np.asarray(p[other])-p[index];norm=np.linalg.norm(difference)
                    if norm:direction[index]+=difference/norm
            direction[0]=0.;norms=np.linalg.norm(direction,axis=1)
            direction/=np.maximum(norms[:,None],1e-10)
            projection=np.sum(delta*direction[None,:,:],axis=2)
            slack=-projection+np.sqrt(np.maximum(0,projection**2+999.0**2-distance2))
            beam_motion=normals@direction.T;beam_level=np.sum(delta*normals[:,None,:],axis=2)
            slack=np.minimum(slack,np.where(beam_motion<0,-beam_level/np.minimum(beam_motion,-1e-15),np.inf))
            slack[:,norms<1e-10]=1e5
            assigned=np.argmax(np.where(feasible,slack,-np.inf),axis=1)
        else:
            assigned=np.argmin(np.where(feasible,distance2,np.inf),axis=1)
        disk_indices=[];disk_centers=[];line_indices=[];line_normals=[];line_constants=[]
        for i in range(1,n):
            ids=np.flatnonzero(assigned==i)
            if not len(ids):continue
            unique=np.unique(source[ids],axis=0)
            try:vertices=unique[ConvexHull(unique).vertices] if len(unique)>=3 else unique
            except QhullError:vertices=unique
            disk_indices.extend([i]*len(vertices));disk_centers.extend(vertices)
            strongest={}
            for state in ids:
                normal=tuple(normals[state]);offset=float(normals[state]@source[state])
                strongest[normal]=max(strongest.get(normal,-math.inf),offset)
            for normal,offset in strongest.items():
                line_indices.append(i);line_normals.append(normal);line_constants.append(offset)
        di=np.asarray(disk_indices);dc=np.asarray(disk_centers)
        li=np.asarray(line_indices);ln=np.asarray(line_normals);lc=np.asarray(line_constants)
        edges=np.asarray([(route[i-1] if i else 0,j) for i,j in enumerate(route) if (route[i-1] if i else 0)!=j])
        def objective(x):
            q=x.reshape((-1,2));return float(np.linalg.norm(q[edges[:,0]]-q[edges[:,1]],axis=1).sum())
        def gradient(x):
            q=x.reshape((-1,2));d=q[edges[:,0]]-q[edges[:,1]]
            d/=np.maximum(np.linalg.norm(d,axis=1)[:,None],1e-10)
            g=np.zeros_like(q);np.add.at(g,edges[:,0],d);np.add.at(g,edges[:,1],-d)
            return g.ravel()
        def constraints(x):
            q=x.reshape((-1,2))
            return np.r_[(999.0**2-np.sum((q[di]-dc)**2,axis=1))/1998.,np.sum(q[li]*ln,axis=1)-lc]
        def jacobian(x):
            q=x.reshape((-1,2));j=np.zeros((len(di)+len(li),n,2))
            j[np.arange(len(di)),di]=-(q[di]-dc)/999.
            j[len(di)+np.arange(len(li)),li]=ln
            return j.reshape((len(di)+len(li),n*2))
        bounds=[(0.,0.),(0.,0.)]+[(v-150.,v+150.) for point in p[1:] for v in point]
        result=minimize(objective,np.asarray(p).ravel(),jac=gradient,bounds=bounds,
                        constraints={'type':'ineq','fun':constraints,'jac':jacobian},
                        method='SLSQP',options={'maxiter':80,'ftol':.001})
        proposal=[tuple(map(float,row)) for row in result.x.reshape((-1,2))]
        report=directional_cover_certificate(proposal,full_report=True,early_exit=False)
        proposed_length,_=shortest_route(proposal)
        accepted=report['certified'] and proposed_length<length-.01
        if accepted:p=proposal;best_report=report
        new=[]
        if not report['certified']:
            if report.get('reason')=='target_disk_not_strictly_inside_hull':
                hull=ConvexHull(proposal)
                for a,b,c in hull.equations:
                    norm=math.hypot(a,b)
                    if -c/norm<1800.1:new.append((1800.1*a/norm,1800.1*b/norm,math.atan2(b,a)))
            else:
                for detail in report.get('pair_details',[]):
                    if detail['radius_bound_m']>=999.999:
                        state=robust_counterexample(proposal,detail)
                        if state is not None:new.append(state)
            states.extend(new)
        history.append({'iteration':iteration,'incumbent_route_m':length,'proposed_route_m':proposed_length,
                        'accepted':accepted,'new_witnesses':len(new),'certificate_bound_m':report.get('max_directional_radius_bound_m'),
                        'optimizer_success':bool(result.success)})
        print(extra_points,iteration,round(proposed_length,2),accepted,len(new),report.get('max_directional_radius_bound_m'),flush=True)
        if not accepted and not new:break
    final_length,route=shortest_route(p)
    report=directional_cover_certificate(p,full_report=True,early_exit=False)
    body={'initial_route_m':initial_length,'final_route_m':final_length,'route':route,'points':p,'certificate':report,
          'history':history,'runtime_s':time.perf_counter()-started}
    folder=ROOT/'problem4'/'results'/'iterations_v3';folder.mkdir(parents=True,exist_ok=True)
    suffix=('_inner' if inner_extra else '')+('_slack' if assignment=='slack' else '')
    (folder/f'coverage_route_optimized_{21+extra_points}{suffix}.json').write_text(json.dumps(body,indent=2)+'\n',encoding='utf-8')
    return body


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--extra',type=int,default=0)
    parser.add_argument('--rounds',type=int,default=30)
    parser.add_argument('--inner-extra',action='store_true')
    parser.add_argument('--assignment',choices=('nearest','slack'),default='nearest');args=parser.parse_args()
    optimize(args.extra,args.rounds,args.inner_extra,args.assignment)

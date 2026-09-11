"""Conditional RF cover outside an explicitly optically searched origin disk.

This certificate is valid only after /clear has actually been attempted for
every still-unknown channel at the origin. A measurement or a near response
is not a substitute. Unknown sources then lie outside the 20m optical disk;
the RF proof conservatively covers radii at least 19.99m.
"""
from __future__ import annotations
import itertools
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from problem4.coverage import convex_hull,_clip,_disk_intersection_extrema
from problem4.experiments_v3.coverage_ring_policy import ring_points


def annular_segment_radius(sites,normal,offset,inner=19.99,outer=1800.):
    if not sites:return math.inf,None
    segment=_clip([(-outer,-outer),(outer,-outer),(outer,outer),(-outer,outer)],
                  -normal[0],-normal[1],-offset)
    worst=0.;witness=None
    for site in sites:
        cell=segment
        for other in sites:
            if other==site:continue
            dx,dy=other[0]-site[0],other[1]-site[1]
            bound=(dx*(other[0]+site[0])+dy*(other[1]+site[1]))/2
            cell=_clip(cell,dx,dy,bound)
            if not cell:break
        candidates=[p for p in _disk_intersection_extrema(cell,site,outer)
                    if math.hypot(*p)>=inner-1e-7]
        candidates += [p for p in _disk_intersection_extrema(cell,site,inner)
                       if math.hypot(*p)>=inner-1e-7]
        for point in candidates:
            value=math.dist(point,site)
            if value>worst:worst,witness=value,point
    return worst,witness


def certificate(points,full_report=False):
    points=[tuple(map(float,point)) for point in points]
    hull=convex_hull(points)
    if len(hull)<3:return {'certified':False,'reason':'degenerate_hull'}
    inradius=min((a[0]*b[1]-a[1]*b[0])/math.dist(a,b) for a,b in zip(hull,hull[1:]+hull[:1]))
    if inradius<1800.001:return {'certified':False,'reason':'hull_not_strictly_containing_disk'}
    rows=[];worst=0.;witness=None
    for i,j in itertools.permutations(range(len(points)),2):
        a,b=points[i],points[j];length=math.dist(a,b)
        if not length:continue
        normal=(-(b[1]-a[1])/length,(b[0]-a[0])/length)
        offset=normal[0]*a[0]+normal[1]*a[1]
        if offset>=1800.:continue
        eligible=[p for p in points if normal[0]*p[0]+normal[1]*p[1]>offset+1e-7]
        value,point=annular_segment_radius(eligible,normal,offset)
        if value>worst:worst,witness=value,point
        if full_report:rows.append({'pair':[i,j],'radius_bound_m':value,'witness':point})
    result={'certified':worst<999.999,'max_directional_radius_bound_m':worst,'witness':witness,
            'hull_inradius_m':inradius,'optical_clear_required':True,'optical_radius_m':20.,
            'rf_annulus_inner_radius_m':19.99}
    if full_report:result.update(points=points,pair_details=rows)
    return result


if __name__=='__main__':
    from scipy.optimize import minimize_scalar
    rows=[]
    for outer,inner in ((12,7),(13,7),(14,6),(12,8),(13,6)):
        result=minimize_scalar(lambda r:certificate(ring_points(outer,inner,r))['max_directional_radius_bound_m'],
                              bounds=(940.,1025.),method='bounded',options={'xatol':.01})
        points=ring_points(outer,inner,float(result.x));report=certificate(points,True)
        row={'outer_count':outer,'inner_count':inner,'inner_radius':float(result.x),'certificate':report}
        rows.append(row);print(outer,inner,float(result.x),report['max_directional_radius_bound_m'],flush=True)
    folder=ROOT/'problem4'/'results'/'iterations_v3';folder.mkdir(parents=True,exist_ok=True)
    (folder/'coverage_optical_hole_rings.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')

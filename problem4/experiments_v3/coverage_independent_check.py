"""Independent finite verification using intersections, never polygon clipping.

For every pair-supported circular segment, enumerate each nearest site's
Voronoi-cell vertices from pairs of line equations, all line/circle crossings,
and the farthest circular point. This implementation does not import the
production clipper, circle intersection routine, or cell extrema routine.
"""
from __future__ import annotations
import itertools
import json
import math
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from problem4.coverage import directional_cover_certificate
from problem4.experiments_v3.coverage_ring_policy import ring_points


def cell_radius(site,sites,normal,offset,radius,inner_radius=0.):
    constraints=[(-normal[0],-normal[1],-offset)]
    for other in sites:
        dx,dy=other[0]-site[0],other[1]-site[1]
        length=math.hypot(dx,dy)
        if not length:continue
        nx,ny=dx/length,dy/length
        midpoint=((site[0]+other[0])/2,(site[1]+other[1])/2)
        constraints.append((nx,ny,nx*midpoint[0]+ny*midpoint[1]))
    def feasible(p):
        return (inner_radius-1e-7<=math.hypot(*p)<=radius+1e-7
                and all(a*p[0]+b*p[1]<=c+1e-7 for a,b,c in constraints))
    candidates=[]
    for a,b in itertools.combinations(constraints,2):
        determinant=a[0]*b[1]-a[1]*b[0]
        if abs(determinant)>1e-12:
            p=((a[2]*b[1]-a[1]*b[2])/determinant,
               (a[0]*b[2]-a[2]*b[0])/determinant)
            if feasible(p):candidates.append(p)
    for boundary in ((radius,inner_radius) if inner_radius else (radius,)):
        for nx,ny,constant in constraints:
            if abs(constant)>boundary+1e-7:continue
            half=math.sqrt(max(0,boundary**2-constant**2))
            for sign in (-1,1):
                p=(constant*nx-sign*half*ny,constant*ny+sign*half*nx)
                if feasible(p):candidates.append(p)
        norm=math.hypot(*site)
        far=(-boundary*site[0]/norm,-boundary*site[1]/norm) if norm else (boundary,0.)
        if feasible(far):candidates.append(far)
    return max((math.dist(p,site) for p in candidates),default=0.)


def check(points,inner_radius=0.):
    from scipy.spatial import ConvexHull
    started=time.perf_counter()
    if inner_radius:
        from problem4.experiments_v3.coverage_optical_hole import certificate
        if inner_radius!=19.99:raise ValueError('Experimental optical certificate fixes 19.99m')
        production=certificate(points,full_report=True)
    else:production=directional_cover_certificate(points,early_exit=False,full_report=True)
    production_pairs={tuple(row['pair']):row for row in production['pair_details']}
    hull=ConvexHull(points)
    hull_inradius=float(min(-c/math.hypot(a,b) for a,b,c in hull.equations))
    rows=[]
    for i,j in itertools.permutations(range(len(points)),2):
        # Recompute the equations and eligible set from the raw coordinates.
        a,b=points[i],points[j]
        length=math.dist(a,b)
        if not length:continue
        normal=(-(b[1]-a[1])/length,(b[0]-a[0])/length)
        offset=normal[0]*a[0]+normal[1]*a[1]
        if offset>=1800.:continue
        eligible=[p for p in points if normal[0]*p[0]+normal[1]*p[1]>offset+1e-7]
        bound=max((cell_radius(site,eligible,normal,offset,1800.,inner_radius) for site in eligible),default=math.inf)
        detail=production_pairs[(i,j)]
        rows.append({'pair':[i,j],'independent_bound_m':bound,
                     'production_bound_m':detail['radius_bound_m'],
                     'absolute_difference_m':abs(bound-detail['radius_bound_m'])})
    worst=max(r['independent_bound_m'] for r in rows)
    return {'certified':worst<999.99 and hull_inradius>1800.01,
            'hull_inradius_m':hull_inradius,'independent_bound_m':worst,
            'maximum_difference_m':max(r['absolute_difference_m'] for r in rows),
            'points_sha256':production.get('points_sha256'),'optical_clear_required':bool(inner_radius),'pairs':rows,
            'runtime_s':time.perf_counter()-started}


if __name__=='__main__':
    result=check(ring_points(12,8,997.32))
    folder=ROOT/'problem4'/'results'/'iterations_v3';folder.mkdir(parents=True,exist_ok=True)
    (folder/'coverage21_independent_certificate.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print({k:v for k,v in result.items() if k!='pairs'})

"""Geometry-only route-aware screen of three-ring coverage structures."""
from __future__ import annotations
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from problem4.coverage import directional_cover_certificate
from problem4.routing import nearest_seed,two_opt,or_opt,route_length


def points(outer_count,core_count,middle_count,core_radius,middle_radius,phase):
    outer_radius=1802/math.cos(math.pi/outer_count)
    rings=[(outer_count,outer_radius,0.),(core_count,core_radius,0.),(middle_count,middle_radius,phase)]
    return [(0.,0.)]+[(r*math.cos((i+p)*math.tau/n),r*math.sin((i+p)*math.tau/n))
                       for n,r,p in rings for i in range(n)]


def shortest_route(p):
    matrix=[[math.dist(a,b) for b in p+[(0.,0.)]] for a in p+[(0.,0.)]]
    routes=[or_opt(two_opt(nearest_seed(matrix,i),matrix),matrix) for i in range(len(p))]
    route=min(routes,key=lambda r:route_length(r,matrix))
    return route_length(route,matrix),route


def screen(structures):
    rows=[];best_certified=None
    for outer,core,middle in structures:
        best=None
        for core_radius in (600.,700.,800.,900.,990.):
            for middle_radius in (1100.,1200.,1300.,1400.,1500.,1600.):
                for phase in (0.,.25,.5):
                    p=points(outer,core,middle,core_radius,middle_radius,phase)
                    report=directional_cover_certificate(p,early_exit=False)
                    row={'structure':[outer,core,middle],'core_radius':core_radius,
                         'middle_radius':middle_radius,'phase':phase,'certificate':report}
                    if report['certified']:
                        row['route_length_m'],row['route']=shortest_route(p)
                        row['points']=p
                        if best_certified is None or row['route_length_m']<best_certified['route_length_m']:
                            best_certified=row
                    if best is None or report['max_directional_radius_bound_m']<best['certificate']['max_directional_radius_bound_m']:
                        best=row
                    rows.append(row)
        print('structure',outer,core,middle,'best bound',best['certificate']['max_directional_radius_bound_m'],
              'best route',best_certified['route_length_m'] if best_certified else None,flush=True)
    folder=ROOT/'problem4'/'results'/'iterations_v3';folder.mkdir(parents=True,exist_ok=True)
    suffix='_'.join(map(str,structures[0]))
    (folder/f'coverage_three_rings_{suffix}.json').write_text(json.dumps({'candidates':rows,'best_certified':best_certified},indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--group',type=int,default=0)
    args=parser.parse_args()
    groups=[[(12,3,5),(12,3,6),(12,4,5),(12,4,6)],
            [(13,3,5),(13,3,6),(14,3,4),(14,4,4)],
            [(10,4,7),(10,3,8),(11,3,7),(11,4,6)]]
    screen(groups[args.group])

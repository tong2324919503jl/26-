"""Independent finite-cell check of the experimental optical band cover."""
import json,math,random
from pathlib import Path
from problem3.geometry import distance,clip_halfplane
from problem4.localization import _convex_hull
from problem3.experiments_v3.optical_band import band_cover


def verify():
    rng=random.Random(861340);checks=accepted=0;worst=0.
    for _ in range(1200):
        center=(rng.uniform(-1800,1800),rng.uniform(-1800,1800))
        theta=rng.uniform(0,math.tau);u=(math.cos(theta),math.sin(theta));v=(-u[1],u[0])
        length=rng.uniform(.1,600.);width=rng.uniform(.001,45.)
        raw=[(rng.uniform(-length/2,length/2),rng.uniform(-width/2,width/2)) for _ in range(24)]
        polygon=_convex_hull((center[0]+x*u[0]+y*v[0],center[1]+x*u[1]+y*v[1]) for x,y in raw)
        plan=band_cover(polygon)
        if not plan:continue
        accepted+=1
        for p in plan:
            cell=list(polygon)
            for q in plan:
                if p==q:continue
                cell=clip_halfplane(cell,2*(q[0]-p[0]),2*(q[1]-p[1]),q[0]**2+q[1]**2-p[0]**2-p[1]**2)
            for vertex in cell:
                value=distance(vertex,p);checks+=1;worst=max(worst,value)
                assert value<=19.99002,(value,polygon,plan)
    return {'polygons':1200,'covered_polygons':accepted,'independent_voronoi_vertex_checks':checks,
            'maximum_distance_m':worst,'clear_radius_m':20.,'all_passed':True}


if __name__=='__main__':
    result=verify();print(json.dumps(result))
    path=Path(__file__).resolve().parents[1]/'results/iterations_v3/optical_band_geometry.json'
    path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')

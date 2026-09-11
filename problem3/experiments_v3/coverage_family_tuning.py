"""Compare regular-ring geometry only after a zero-signal origin scan.

All localization, neighbor updates and routing inherit the same LookaheadPolicy.
The count/radius choice is fixed per experimental class and never uses a case
family, seed, hidden source count, or simulator truth.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from problem3.experiments_v3.lookahead import LookaheadPolicy
from problem3.experiments_v3.benchmark import run
from problem3.geometry import certified_covering_radius
from problem3.scenarios import generate_suite

REPRESENTATIVES={6:(1250.,1400.,1550.,1700.),
                 7:(1350.,1450.,1550.,1650.,1750.),
                 8:(1250.,1350.,1450.,1550.,1700.),
                 9:(1250.,1400.,1550.,1700.)}
DEPENDENCIES=('problem3/experiments_v3/lookahead.py','problem3/experiments_v3/radial_adaptive.py',
              'problem3/experiments_v3/negative_disks.py','problem3/experiments_v3/journey.py',
              'problem3/experiments_v3/policy.py','problem3/experiments_v3/candidate.py',
              'problem3/geometry.py','problem3/simulator.py','problem3/scenarios.py')


def fingerprints():
    return {path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in DEPENDENCIES}


def ring_certificate(count,radius):
    """Exact-form regular-ring Voronoi bound, independently checked below.

Interior Voronoi vertices have radius r/(2*cos(pi/n)). The outer-circle
maximum is midway between adjacent ring bearings. No sample grid is used.
"""
    cosine=math.cos(math.pi/count);sine=math.sin(math.pi/count)
    root=math.sqrt(1000.**2-(1800.*sine)**2)
    low=1800.*cosine-root
    high=min(1800.*cosine+root,2000.*cosine)
    inner=radius/(2*cosine)
    boundary=math.sqrt(1800.**2+radius**2-3600.*radius*cosine)
    bound=max(inner,boundary)
    points=[(0.,0.)]+[(radius*math.cos(i*math.tau/count),radius*math.sin(i*math.tau/count)) for i in range(count)]
    independent=certified_covering_radius(points)
    if max(bound,independent)>=999.999:raise ValueError('Ring failed full target-disk coverage')
    # The existing checker covers an outer 96-gon, so its bound may exceed the
    # exact circular-domain value by at most the polygon's radial excess.
    polygon_excess=1800.*(1/math.cos(math.pi/96)-1)
    if independent+1e-4<bound or independent-bound>polygon_excess+1e-4:
        raise RuntimeError('Analytic and conservative Voronoi bounds disagree')
    return {'certified':True,'ring_count':count,'ring_radius_m':radius,
            'legal_radius_interval_m':[low,high],'interior_bound_m':inner,
            'boundary_bound_m':boundary,'maximum_covering_radius_m':bound,
            'independent_voronoi_bound_m':independent}


class GeometryLookaheadPolicy(LookaheadPolicy):
    annular_signal_count=0
    def _route_goal(self,client,pending):
        # The inherited RotatingPolicy rebuilds any six-point ring using this
        # configuration field. Synchronize it only after a truly empty origin,
        # otherwise six-point alternatives would silently revert to 1150m.
        if (self.annular_count==6 and len(self.coverage_visited)==1
            and math.hypot(*self.coverage_visited[0])<1e-7
            and not (set(self.regions)|self.cleared)):
            self.config.ring_radius=self.annular_radius
        return super()._route_goal(client,pending)

    def _scan(self,client,point):
        if len(self.coverage_visited)==1 and getattr(self,'_annular_decision',False):
            self.stats['actual_empty_ring_first_scan_radius_m']=math.hypot(*point)
        return super()._scan(client,point)

    def _result(self,reason,coverage_complete):
        result=super()._result(reason,coverage_complete)
        result['zero_origin_geometry']={'count':self.annular_count,'radius_m':self.annular_radius,
            'triggered':bool(getattr(self,'_annular_decision',False)),
            'phase_candidates':self.annular_phases}
        return result


def get_policy(count,radius):
    ring_certificate(count,radius)
    return type(f'OriginZeroRing{count}R{int(radius)}',(GeometryLookaheadPolicy,),
                {'annular_count':count,'annular_radius':float(radius)})


def validate_scope(reference,result):
    unchanged=triggered=radius_checks=0
    for original,row in zip(reference['rows'],result['rows']):
        metadata=row['policy']['zero_origin_geometry']
        if not metadata['triggered']:
            if row['sim']!=original['sim']:raise AssertionError('Non-triggered case changed physical behavior')
            unchanged+=1
        else:
            triggered+=1
            actual=row['policy'].get('actual_empty_ring_first_scan_radius_m')
            if actual is not None:
                if abs(actual-metadata['radius_m'])>1e-6:raise AssertionError('Requested ring radius was overwritten')
                radius_checks+=1
    return {'unchanged_non_trigger_cases':unchanged,'triggered_cases':triggered,
            'first_scan_radius_checked_cases':radius_checks}


def evaluate_family(counts,split,case_count,selected=None):
    before=fingerprints();cases=generate_suite(3,split,case_count)
    folder=ROOT/'problem3'/'results'/'iterations_v3';folder.mkdir(parents=True,exist_ok=True)
    suffix='_'.join(map(str,counts)) if selected is None else 'selected'
    output=folder/f'coverage_family_{split}_{case_count}_n{suffix}.json'
    body={'split':split,'case_count':case_count,'dependencies':before,'branches':{}}
    specs=selected or [(n,r) for n in counts for r in REPRESENTATIVES[n]]
    branches=[('lookahead_reference',LookaheadPolicy,None)]
    branches += [(f'ring{n}_r{int(r)}',get_policy(n,r),ring_certificate(n,r)) for n,r in specs]
    for name,cls,certificate in branches:
        if fingerprints()!=before:raise RuntimeError('Shared branch changed before a comparison')
        result=run(cls,cases)
        if fingerprints()!=before:raise RuntimeError('Shared branch changed during a comparison')
        body['branches'][name]={'geometry_certificate':certificate,'result':result}
        if certificate:
            body['branches'][name]['scope_validation']=validate_scope(body['branches']['lookahead_reference']['result'],result)
        output.write_text(json.dumps(body,indent=2)+'\n',encoding='utf-8')
        summary={k:v for k,v in result.items() if k!='rows'}
        if certificate:
            triggered=[row for row in result['rows'] if row['policy']['zero_origin_geometry']['triggered']]
            summary['triggered_cases']=len(triggered)
            summary['triggered_mean']=sum(row['average'] for row in triggered)/len(triggered) if triggered else None
        print(name,summary,flush=True)
    return body


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--counts',default='6,7,8,9')
    parser.add_argument('--count',type=int,default=96)
    parser.add_argument('--split',choices=('development','development_v2','development_v3'),default='development_v2')
    parser.add_argument('--selected',help='Comma-separated n:radius pairs for confirmation')
    args=parser.parse_args()
    counts=[int(value) for value in args.counts.split(',')]
    selected=[(int(a),float(b)) for a,b in (spec.split(':') for spec in args.selected.split(','))] if args.selected else None
    evaluate_family(counts,args.split,args.count,selected)

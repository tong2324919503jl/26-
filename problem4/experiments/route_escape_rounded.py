"""Candidate comparisons at the rounded production coverage coordinates."""
import argparse,hashlib,json,statistics,time
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from problem4.coverage import static_coverage_points
from problem4.localization import LocalizationMixin
from problem4.legacy_policy import SearchPolicy as LegacyPolicy
from problem4.experiments.routing import InformationRoutingMixin
from problem4.experiments.route_escape import RouteEscapeMixin
from problem3.scenarios import generate_suite
from problem3.simulator import LocalSimulator,ObservationClient
class RoundedCover:
 def coverage_points(self):return static_coverage_points()
def get_class(name):
 if name=='info':return type('RoundedInfo',(RoundedCover,InformationRoutingMixin,LocalizationMixin,LegacyPolicy),{})
 if name=='stop':
  def choose(self,client,pending):return LegacyPolicy._route_goal(self,client,[] if len(set(self.regions)|self.cleared)==16 else pending)
  return type('RoundedStop',(RoundedCover,LocalizationMixin,LegacyPolicy),{'_route_goal':choose})
 attrs={'escape_oropt':'multi' not in name or 'hybrid' in name,'escape_starts':4 if 'multi' in name or 'hybrid' in name else 1,'escape_warm':'warm' in name,'escape_info_weight':1. if 'info' in name else 0.,'escape_chain':1 if 'relocate' in name else 3,'escape_oropt_final_only':'each' not in name}
 return type(name,(RoundedCover,RouteEscapeMixin,InformationRoutingMixin,LocalizationMixin,LegacyPolicy),attrs)
def fingerprints():
 return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'problem4/coverage.py',ROOT/'problem4/localization.py',ROOT/'problem4/experiments/route_escape.py',ROOT/'problem4/experiments/routing.py')}
def main():
 p=argparse.ArgumentParser();p.add_argument('names',nargs='+');p.add_argument('--count',type=int,default=96);args=p.parse_args();body={};before=fingerprints()
 for name in args.names:
  cls=get_class(name);rows=[];start=time.perf_counter()
  for case in generate_suite(4,'development_v2',args.count):
   sim=LocalSimulator(case);sim.enter();result={};error=None;runtime=time.perf_counter()
   try:result=cls().run(ObservationClient(sim))
   except Exception as exc:error=repr(exc)
   stats=sim.statistics();done=not error and result.get('completion_certified') and stats['cleared_count']==stats['source_count']
   rows.append({'case_id':case['case_id'],'family':case['family'],'error':error,**stats,'policy':result,'certified_full_clear':bool(done),'threshold_passed':bool(done and stats['average_clear_time_s']<=500),'program_runtime_s':time.perf_counter()-runtime})
  summary={'cases':len(rows),'mean':statistics.mean(r['average_clear_time_s'] for r in rows),'pass':statistics.mean(r['threshold_passed'] for r in rows),'move':statistics.mean(r['movement_m'] for r in rows),'actions':statistics.mean(r['actions'] for r in rows),'full':sum(r['certified_full_clear'] for r in rows),'failures':[(r['case_id'],r['error']) for r in rows if not r['certified_full_clear']],'cpu':time.perf_counter()-start,'cpu_max':max(r['program_runtime_s'] for r in rows)}
  print(name,json.dumps(summary),flush=True);body[name]={'summary':summary,'episodes':rows}
  out=(Path(__file__).resolve().parents[1]/'results'/'iterations_v2').joinpath(f'route_escape_rounded_{args.count}_{"_".join(args.names)}.json');out.write_text(json.dumps({'provenance':'Only development_v2; rounded production coverage and localization; not official','source_sha256':before,'results':body},indent=2)+'\n',encoding='utf-8')
 if before!=fingerprints():raise RuntimeError('Relevant source changed during benchmark')
if __name__=='__main__':main()

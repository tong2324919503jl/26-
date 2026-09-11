"""Development-only scheduler comparison; never accepts holdout/stress input."""
import argparse,hashlib,json,statistics,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from problem4.experiments_v3.routing import get_class
from problem3.scenarios import generate_suite
from problem3.simulator import LocalSimulator,ObservationClient

def main():
 p=argparse.ArgumentParser();p.add_argument('names',nargs='+');p.add_argument('--count',type=int,default=48);a=p.parse_args();body={}
 for name in a.names:
  cls=get_class(name);rows=[];start=time.perf_counter()
  for case in generate_suite(4,'development_v2',a.count):
   sim=LocalSimulator(case);sim.enter();result={};error=None;cpu=time.perf_counter()
   try:result=cls().run(ObservationClient(sim))
   except Exception as e:error=repr(e)
   stats=sim.statistics();done=not error and result.get('completion_certified') and stats['source_count']==stats['cleared_count']
   rows.append({'case_id':case['case_id'],'family':case['family'],**stats,'error':error,'policy':result,'certified_full_clear':bool(done),'threshold_passed':bool(done and stats['average_clear_time_s']<=400),'program_runtime_s':time.perf_counter()-cpu})
  summary={'cases':len(rows),'mean':statistics.mean(r['average_clear_time_s'] for r in rows),'pass':statistics.mean(r['threshold_passed'] for r in rows),'move':statistics.mean(r['movement_m'] for r in rows),'actions':statistics.mean(r['actions'] for r in rows),'full':sum(r['certified_full_clear'] for r in rows),'failures':[(r['case_id'],r['error']) for r in rows if not r['certified_full_clear']],'cpu':time.perf_counter()-start,'cpu_max':max(r['program_runtime_s'] for r in rows)}
  print(name,json.dumps(summary),flush=True);body[name]={'summary':summary,'episodes':rows,'variant_settings':{key:getattr(cls,key) for key in dir(cls) if key.startswith(('shared_','enroute_','service_','deferred_','reuse_','departure_','incremental_','skeleton_','discovery_','read_','channel_')) and isinstance(getattr(cls,key),(bool,int,float,str,tuple))}}
  out=ROOT/'problem4/results/iterations_v3'/f'routing_development_v2_{a.count}_{"_".join(a.names)}.json';out.write_text(json.dumps({'provenance':'Self-constructed development_v2 only, not official','threshold_seconds_per_source':400,'results':body},indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()

import json,statistics,sys,time
from pathlib import Path
from problem4.experiments.routing import LegacyPolicy,InformationPolicy
from problem3.scenarios import generate_suite
from problem3.simulator import LocalSimulator,ObservationClient
count=int(sys.argv[1]);split=sys.argv[2] if len(sys.argv)>2 else 'development';body={}
for weight in (0.5,1,2,4):
 cls=type('InfoVariant',(InformationPolicy,),{'info_weight':weight});rows=[];start=time.perf_counter()
 for case in generate_suite(4,split,count):
  sim=LocalSimulator(case);sim.enter();error=None;result={}
  try:result=cls().run(ObservationClient(sim))
  except Exception as e:error=repr(e)
  rows.append({'id':case['case_id'],'error':error,**sim.statistics(),'policy':result})
 summary={'mean':statistics.mean(r['average_clear_time_s'] for r in rows),'pass':sum(r['average_clear_time_s']<=500 and not r['error'] for r in rows)/len(rows),'move':statistics.mean(r['movement_m'] for r in rows),'actions':statistics.mean(r['actions'] for r in rows),'full':sum(r['cleared_count']==r['source_count'] and not r['error'] for r in rows),'failures':[(r['id'],r['error']) for r in rows if r['error']],'cpu':time.perf_counter()-start}
 print(weight,summary,flush=True);body[str(weight)]={'summary':summary,'episodes':rows}
(Path(__file__).resolve().parents[1]/'results'/'iterations_v2').joinpath(f'info_{split}_{count}.json').write_text(json.dumps(body,indent=2)+'\n',encoding='utf-8')

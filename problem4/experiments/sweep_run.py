import json,statistics
from pathlib import Path
from problem4.experiments.routing import LegacyPolicy,SweepPolicy,DetectedStopPolicy
from problem3.scenarios import generate_suite
from problem3.simulator import LocalSimulator,ObservationClient
import sys
count=int(sys.argv[1]);split=sys.argv[2] if len(sys.argv)>2 else 'development'
body={}
classes=[('legacy',LegacyPolicy),('detectedstop',DetectedStopPolicy)]
for order in ('outer','inner'):
 for cost in (150,400,800):classes.append((order+str(cost),type('Variant',(SweepPolicy,),{'ordering':order,'insert_detour':cost})))
for name,cls in classes:
 rows=[]
 for case in generate_suite(4,split,count):
  sim=LocalSimulator(case);sim.enter();error=None;result={}
  try:result=cls().run(ObservationClient(sim))
  except Exception as e:error=repr(e)
  rows.append({'id':case['case_id'],'error':error,**sim.statistics(),'policy':result})
 summary={'mean':statistics.mean(r['average_clear_time_s'] for r in rows),'pass':sum(r['average_clear_time_s']<=500 and not r['error'] for r in rows)/len(rows),'move':statistics.mean(r['movement_m'] for r in rows),'actions':statistics.mean(r['actions'] for r in rows),'full':sum(r['cleared_count']==r['source_count'] and not r['error'] for r in rows),'failures':[(r['id'],r['error']) for r in rows if r['error']]}
 print(name,summary,flush=True);body[name]={'summary':summary,'episodes':rows}
Path(__file__).with_name(f'sweep_{split}_{count}.json').write_text(json.dumps(body,indent=2)+'\n',encoding='utf-8')

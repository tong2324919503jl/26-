import json,statistics,time
from pathlib import Path
from problem4.experiments.routing import InformationPolicy
from problem4.experiments.localization import LocalizationMixin
from problem3.scenarios import generate_suite
from problem3.simulator import LocalSimulator,ObservationClient
class OptimizedTourOnly(LocalizationMixin,InformationPolicy):
 localization_quantile=.2
 localization_width_fraction=.04
 localization_width_min=15.
 localization_enforce_range=True
 localization_history=True
 localization_history_slices=12
 info_weight=0.
rows=[];start=time.perf_counter()
for case in generate_suite(4,'development_v2',384):
 sim=LocalSimulator(case);sim.enter();error=None;result={}
 try:result=OptimizedTourOnly().run(ObservationClient(sim))
 except Exception as e:error=repr(e)
 rows.append({'id':case['case_id'],'error':error,**sim.statistics(),'policy':result})
summary={'mean':statistics.mean(r['average_clear_time_s'] for r in rows),'pass':sum(r['average_clear_time_s']<=500 and not r['error'] for r in rows)/len(rows),'move':statistics.mean(r['movement_m'] for r in rows),'actions':statistics.mean(r['actions'] for r in rows),'full':sum(r['cleared_count']==r['source_count'] and not r['error'] for r in rows),'failures':[(r['id'],r['error']) for r in rows if r['error']],'cpu':time.perf_counter()-start}
print(summary,flush=True);(Path(__file__).resolve().parents[1]/'results'/'iterations_v2').joinpath('info_ablation_development_v2_384.json').write_text(json.dumps({'summary':summary,'episodes':rows},indent=2)+'\n',encoding='utf-8')

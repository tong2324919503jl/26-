from benchmark import *
from problem3.experiments_v3.journey import *
cases=generate_suite(3,'development_v2',96);results={}
for step in (30,50,100):
    for triangular in (False,True):
        cls=type(f'all{step}_tri{triangular}',(FreshBaselinePolicy,),dict(fresh_step=step,fresh_triangular=triangular,fresh_only=False))
        r=run(cls,cases);results[cls.__name__]=r;print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
(ROOT/'problem3/results/p3_all_baseline_v3_screen96.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

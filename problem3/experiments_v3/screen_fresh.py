from benchmark import *
from problem3.experiments_v3.journey import *
cases=generate_suite(3,'development_v2',96);results={}
for step in (30,50,100):
    for minimum in (1,2):
        cls=type(f'fresh{step}min{minimum}',(FreshBaselinePolicy,),dict(fresh_step=step,fresh_min_count=minimum))
        r=run(cls,cases);results[cls.__name__]=r;print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
for step in (50,100):
    cls=type(f'triangle{step}',(FreshBaselinePolicy,),dict(fresh_step=step,fresh_triangular=True))
    r=run(cls,cases);results[cls.__name__]=r;print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
(ROOT/'problem3/results/p3_fresh_v3_screen96.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

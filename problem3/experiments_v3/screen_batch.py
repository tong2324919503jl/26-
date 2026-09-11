from benchmark import *
cases=generate_suite(3,'development_v2',64);results={}
for step in (100,200,350,500):
    for choice in ('nearest','information'):
        cls=type(f'batch{step}_{choice}',(BatchBaselinePolicy,),dict(batch_step=step,batch_choice=choice))
        r=run(cls,cases);results[cls.__name__]=r;print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
(ROOT/'problem3/results/p3_batch_v3_screen.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

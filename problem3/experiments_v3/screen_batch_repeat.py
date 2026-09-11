from benchmark import *
cases=generate_suite(3,'development_v2',64);results={}
for step in (50,100,200):
    for rotate in (False,True):
        base=type('RotatingBatch',(BatchBaselineMixin,RotatingIncrementalPolicy),{}) if rotate else BatchBaselinePolicy
        cls=type(f'repeat{step}_rotate{rotate}',(base,),dict(batch_step=step,batch_choice='information',batch_each_scan=True))
        r=run(cls,cases);results[cls.__name__]=r;print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
(ROOT/'problem3/results/p3_batch_repeat_v3_screen.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

from benchmark import *
cases=generate_suite(3,'development_v2',64);results={}
samples=[((x,y),r,None) for x in range(-1800,1801,300) for y in range(-1800,1801,300) if math.hypot(x,y)<=1800 for r in (1000,1250,1500)]
for weight in (.5,1,2,4,8,16):
    cls=type(f'info{weight}',(IncrementalPolicy,),dict(escape_info_weight=weight,samples=samples,mask_cache={}))
    r=run(cls,cases);results[cls.__name__]=r;print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
(ROOT/'problem3/results/p3_information_v3_screen.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

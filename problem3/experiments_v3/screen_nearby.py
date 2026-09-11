from benchmark import *
cases=generate_suite(3,'development_v2',64);results={}
for clear in (False,True):
    for nearby in (0,30,100,300):
        cls=type(f'clear{clear}_near{nearby}',(OpportunisticClearPolicy,),dict(opportunistic_clear=clear,richer_neighbors=nearby>0,nearby_region_distance=nearby))
        r=run(cls,cases);results[cls.__name__]=r;print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
(ROOT/'problem3/results/p3_nearby_v3_screen.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

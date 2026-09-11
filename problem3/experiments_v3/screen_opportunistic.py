from benchmark import *
cases=generate_suite(3,'development_v2',64);results={}
for spacing in (500,700,900,1100):
    for offset in (300,600,math.inf):
        cls=type(f'opportunistic_s{spacing}_o{offset}',(OpportunisticPolicy,),dict(scan_spacing=spacing,scan_max_offset=offset))
        r=run(cls,cases);results[cls.__name__]=r
        print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
(ROOT/'problem3/results/p3_opportunistic_v3_screen.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

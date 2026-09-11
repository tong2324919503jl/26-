from benchmark import *
cases=generate_suite(3,'development_v2',64);results={}
for q in (.2,.35,.5,.7):
    for width in (0,.04,.12):
        cls=type(f'q{q}w{width}',(ProbeRoutePolicy,),dict(probe_quantile=q,probe_fraction=width,probe_min=0. if width==0 else 15.))
        r=run(cls,cases);results[cls.__name__]=r;print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
(ROOT/'problem3/results/p3_probe_route_v3_screen.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

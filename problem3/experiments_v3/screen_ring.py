from benchmark import *
cases=generate_suite(3,'development_v2',64);results={}
for count in (7,8,9,10):
    angle=math.pi/count
    radius=1800*math.cos(angle)-math.sqrt(999.**2-1800.**2*math.sin(angle)**2)+2.
    for origin in (False,True):
        cls=type(f'ring{count}_origin{origin}',(RingPolicy,),dict(cover_count=count,cover_radius=radius,include_origin=origin))
        r=run(cls,cases);results[cls.__name__]=r;print(cls.__name__,radius,{k:v for k,v in r.items() if k!='rows'},flush=True)
(ROOT/'problem3/results/p3_ring_v3_screen.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

from benchmark import *
cases=generate_suite(3,'development_v2',64);results={}
for angle in (2,5,10,20,40):
    cls=type(f'angular{angle}',(AngularNeighborsPolicy,),dict(neighbor_angle_span=angle))
    r=run(cls,cases);results[cls.__name__]=r;print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
(ROOT/'problem3/results/p3_angular_v3_screen.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

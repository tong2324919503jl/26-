from benchmark import *
from problem3.experiments_v3.enroute_geometry import *
cases=generate_suite(3,'development_v2',96);results={}
for active in (False,True):
    for compare in (False,True):
        cls=type(f'geometry_active{active}_compare{compare}',(GeometryEnroutePolicy,),dict(enroute_active_channel=active,enroute_compare_destination=compare))
        r=run(cls,cases);results[cls.__name__]=r;print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
(ROOT/'problem3/results/p3_enroute_geometry_v3_screen96.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

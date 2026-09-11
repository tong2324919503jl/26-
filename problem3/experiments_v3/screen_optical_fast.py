from benchmark import *
from problem3.experiments_v3.optical_fast import *
cases=generate_suite(3,'development_v2',96);results={}
branches={'annular_negative':AnnularNegativePolicy,'clear_only':type('ClearOnly',(ClearRegionMixin,AnnularNegativePolicy),{})}
for r in (55,100,200,500):
    for offset in (10,50):branches[f'optical{r}_offset{offset}']=type('OpticalVariant',(OpticalFastPolicy,),dict(optical_first_radius=r,optical_first_offset=offset))
for name,cls in branches.items():
    r=run(cls,cases);results[name]=r;print(name,{k:v for k,v in r.items() if k!='rows'},flush=True)
(ROOT/'problem3/results/p3_optical_fast_v3_screen96.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

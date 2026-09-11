from benchmark import *
from problem3.experiments_v3.shape_prior import *
cases=generate_suite(3,'development_v2',96);results={}
branches={'candidate':Candidate,'annular_negative':AnnularNegativePolicy,'shape':ShapePolicy,'annular_shape':AnnularShapePolicy}
for weight in (.03,.3):branches[f'annular_shape_w{weight}']=type(f'Shape{weight}',(AnnularShapePolicy,),dict(shape_uniform_weight=weight))
branches['annular_shape_empty']=type('ShapeEmpty',(AnnularShapePolicy,),dict(shape_empty_center_only=True))
for name,cls in branches.items():
    r=run(cls,cases);results[name]=r;print(name,{k:v for k,v in r.items() if k!='rows'},flush=True)
(ROOT/'problem3/results/p3_shape_v3_screen96.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

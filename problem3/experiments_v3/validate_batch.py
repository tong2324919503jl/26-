from benchmark import *
cases=generate_suite(3,'development_v2',384);results={}
branches={
 'batch100':type('Batch100',(BatchBaselinePolicy,),dict(batch_step=100.,batch_choice='information')),
 'batch200':type('Batch200',(BatchBaselinePolicy,),dict(batch_step=200.,batch_choice='information')),
 'batch_rotate':type('BatchRotate',(BatchBaselineMixin,RotatingIncrementalPolicy),dict(batch_step=100.,batch_choice='information')),
 'batch_angular':type('BatchAngular',(AngularNeighborsMixin,BatchBaselinePolicy),dict(batch_step=100.,batch_choice='information',neighbor_angle_span=40.)),
}
for name,cls in branches.items():
    r=run(cls,cases);results[name]=r;print(name,{k:v for k,v in r.items() if k!='rows'},flush=True)
(ROOT/'problem3/results/p3_batch_v3_development.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

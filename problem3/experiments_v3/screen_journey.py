from benchmark import *
from problem3.experiments_v3.journey import *
cases=generate_suite(3,'development_v2',96);results={}
branches={'candidate':CandidatePolicy,'clear_nearest':ClearRegionPolicy,'clear_lookahead':type('Lookahead',(ClearRegionPolicy,),dict(clear_lookahead=True))}
for gain in (40,100,200):
    for batch in (False,True):
        attrs=dict(enroute_min_gain=gain)
        if not batch:attrs['_after_scan']=lambda self,client,pending:None
        branches[f'enroute{gain}_batch{batch}']=type(f'Enroute{gain}B{batch}',(EnroutePolicy,),attrs)
for name,cls in branches.items():
    r=run(cls,cases);results[name]=r;print(name,{k:v for k,v in r.items() if k!='rows'},flush=True)
(ROOT/'problem3/results/p3_journey_v3_screen96.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

from benchmark import *
from problem3.geometry import contains
cases=generate_suite(3,'development_v2',384);results={}
branches={'legacy':LegacyPolicy,'global_negative':GlobalNegativePolicy,'incremental':IncrementalPolicy,'rotation_incremental':RotatingIncrementalPolicy,'angular40':type('Angular40',(AngularNeighborsPolicy,),dict(neighbor_angle_span=40.))}
for name,cls in branches.items():
    r=run(cls,cases);results[name]=r;print(name,{k:v for k,v in r.items() if k!='rows'},flush=True)
checks=0;violations=[]
for case in cases:
    sim=LocalSimulator(case);sim.enter();policy=RotatingIncrementalPolicy()
    actual={source['channel']:(source['x'],source['y']) for source in case['sources']}
    original=policy._measure
    def checked(client,point,channel):
        global checks
        result=original(client,point,channel)
        if channel in policy.regions and channel not in policy.cleared:
            checks+=1
            if not contains(policy.regions[channel],actual[channel]):violations.append((case['case_id'],channel))
        return result
    policy._measure=checked
    policy.run(ObservationClient(sim))
results['retention_checks']=checks;results['retention_violations']=violations
print('retention',checks,violations,flush=True)
(ROOT/'problem3/results/p3_architecture_v3_development.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

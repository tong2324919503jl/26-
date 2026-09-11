from benchmark import *
from problem3.experiments_v3.candidate import SearchPolicy
from problem3.geometry import contains
results={}
for count in (64,384):
    result=run(SearchPolicy,generate_suite(3,'development_v2',count));results[str(count)]=result
    print(count,{k:v for k,v in result.items() if k!='rows'},flush=True)
checks=0;violations=[]
for case in generate_suite(3,'development_v2',384):
    sim=LocalSimulator(case);sim.enter();policy=SearchPolicy()
    actual={source['channel']:(source['x'],source['y']) for source in case['sources']}
    original=policy._measure
    def checked(client,point,channel):
        global checks
        result=original(client,point,channel)
        if channel in policy.regions and channel not in policy.cleared:
            checks+=1
            if not contains(policy.regions[channel],actual[channel]):violations.append((case['case_id'],channel))
        return result
    policy._measure=checked;policy.run(ObservationClient(sim))
results['retention_checks']=checks;results['retention_violations']=violations
print('retention',checks,violations,flush=True)
(ROOT/'problem3/results/p3_candidate_v3_development.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

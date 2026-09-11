"""Independent development evaluation of positive-reception radius bounds."""
from sweep_localization import *
from problem4.experiments.localization import OptimizedSearchPolicy,RadiusBoundSearchPolicy
from problem3.geometry import contains
cases=generate_suite(4,'development_v2')
output={}
for name, cls in [('history_localization',OptimizedSearchPolicy),('positive_radius',RadiusBoundSearchPolicy)]:
    begin=time.perf_counter()
    result=run(cls,cases)
    result['runtime_s']=time.perf_counter()-begin
    output[name]=result
    print(name,{k:v for k,v in result.items() if k!='rows'},flush=True)

checks=0
violations=[]
for c in cases:
    s=LocalSimulator(c);s.enter();p=RadiusBoundSearchPolicy()
    original=p._clip_history
    truth={source['channel']:(source['x'],source['y']) for source in c['sources']}
    def checked(channel):
        global checks
        original(channel)
        checks+=1
        if not contains(p.regions[channel],truth[channel]):
            violations.append((c['case_id'],channel))
    p._clip_history=checked
    p.run(ObservationClient(s))
output['retention_checks']=checks
output['retention_violations']=violations
print('retention_checks',checks,'violations',violations,flush=True)
out=ROOT/'problem4/results/localization_positive_radius_development_v2.json'
out.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf8')

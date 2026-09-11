from sweep_localization import *
from problem4.experiments.localization import PartitionedRadiusSearchPolicy
from problem3.geometry import contains
cases=generate_suite(4,'development_v2')
begin=time.perf_counter()
output=run(PartitionedRadiusSearchPolicy,cases)
output['runtime_s']=time.perf_counter()-begin
print({k:v for k,v in output.items() if k!='rows'},flush=True)
checks=0;violations=[]
for c in cases:
    s=LocalSimulator(c);s.enter();p=PartitionedRadiusSearchPolicy()
    original=p._clip_history
    truth={source['channel']:(source['x'],source['y']) for source in c['sources']}
    def checked(channel):
        global checks
        original(channel);checks+=1
        if not contains(p.regions[channel],truth[channel]):
            violations.append((c['case_id'],channel))
    p._clip_history=checked
    p.run(ObservationClient(s))
output['retention_checks']=checks
output['retention_violations']=violations
print('retention_checks',checks,'violations',violations,flush=True)
(ROOT/'problem4/results/localization_partitioned_radius_development_v2.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf8')

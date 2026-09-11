import json,time
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from problem4.experiments.route_escape_rounded import get_class,RoundedCover
from problem4.routing import RoutingMixin
from problem4.localization import LocalizationMixin
from problem4.legacy_policy import SearchPolicy as LegacyPolicy
from problem3.scenarios import generate_suite
from problem3.simulator import LocalSimulator,ObservationClient
class ProductionCandidate(RoundedCover,RoutingMixin,LocalizationMixin,LegacyPolicy):pass
reference=get_class('warmhybrid_info');checked=0;start=time.perf_counter()
for case in generate_suite(4,'development_v2',96):
 outputs=[]
 for cls in (reference,ProductionCandidate):
  sim=LocalSimulator(case,record=True);sim.enter();result=cls().run(ObservationClient(sim));outputs.append((sim.statistics(),[(e['action'],e['position'],e['channel'],e['response'].get('measure_result'),e['response'].get('clear_result')) for e in sim.events],result))
 assert outputs[0]==outputs[1],case['case_id']
 checked+=1
result={'development_cases':checked,'exact_action_and_result_match':True,'runtime_s':time.perf_counter()-start}
print(result);(ROOT/'problem4/results/iterations_v2/routing_production_equivalence.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')

from problem3.experiments_v3.benchmark import *
from problem3.experiments_v3.enroute_geometry import *
from problem3.experiments_v3.optical_fast import *

class SafeBaseline(ClearRegionMixin,AnnularNegativePolicy):pass
class OpticalSelected(OpticalFastPolicy):optical_first_offset=10.
class EnrouteSelected(GeometryEnroutePolicy):
    enroute_active_channel=True
    enroute_compare_destination=False
class CombinedSelected(OpticalFirstMixin,EnrouteSelected):optical_first_offset=10.

if __name__=='__main__':
    cases=generate_suite(3,'development_v2',384);results={}
    for cls in (AnnularNegativePolicy,SafeBaseline,OpticalSelected,EnrouteSelected,CombinedSelected):
        r=run(cls,cases);results[cls.__name__]=r;print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
    (ROOT/'problem3/results/p3_journey_v3_development384.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

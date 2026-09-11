from problem3.experiments_v3.benchmark import *
from problem3.experiments_v3.lookahead import *
from problem3.experiments_v3.validate_journey import EnrouteSelected,OpticalFirstMixin

class LookaheadEnroute(LookaheadMixin,EnrouteSelected):pass
class LookaheadOptical(OpticalFirstMixin,LookaheadPolicy):optical_first_offset=10.
class DenseQuadrature(LookaheadPolicy):rollout_node_count=7

if __name__=='__main__':
    n=int(sys.argv[1]) if len(sys.argv)>1 else 96
    cases=generate_suite(3,'development_v2',n);results={}
    branches=(LookaheadPolicy,LookaheadEnroute,LookaheadOptical,DenseQuadrature,SecondReadLookaheadPolicy)
    for cls in branches:
        r=run(cls,cases);results[cls.__name__]=r;print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
        (ROOT/f'problem3/results/p3_lookahead_variants_v3_development{n}.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

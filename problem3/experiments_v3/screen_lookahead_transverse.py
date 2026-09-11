from problem3.experiments_v3.benchmark import *
from problem3.experiments_v3.lookahead import *
from problem3.experiments_v3.optical_fast import OpticalFirstMixin

class TransverseOptical(OpticalFirstMixin,TransverseLookaheadPolicy):optical_first_offset=10.

if __name__=='__main__':
    n=int(sys.argv[1]) if len(sys.argv)>1 else 96
    cases=generate_suite(3,'development_v2',n);results={}
    for cls in (TransverseLookaheadPolicy,TransverseOptical):
        r=run(cls,cases);results[cls.__name__]=r;print(cls.__name__,{k:v for k,v in r.items() if k!='rows'},flush=True)
        (ROOT/f'problem3/results/p3_lookahead_transverse_v3_screen{n}.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

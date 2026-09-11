from problem3.experiments_v3.benchmark import *
from problem3.experiments_v3.lookahead import *

class SafeBaseline(ClearRegionMixin,AnnularNegativePolicy):pass

if __name__=='__main__':
    n=int(sys.argv[1]) if len(sys.argv)>1 else 96
    cases=generate_suite(3,'development_v2',n)
    branches={'safe_annular':SafeBaseline,'lookahead':LookaheadPolicy}
    results={}
    for name,cls in branches.items():
        r=run(cls,cases);results[name]=r
        print(name,{k:v for k,v in r.items() if k!='rows'},flush=True)
    (ROOT/f'problem3/results/p3_lookahead_v3_screen{n}.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

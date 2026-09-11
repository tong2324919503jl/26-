from __future__ import annotations
import sys,json,statistics,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from problem3.experiments_v3.policy import *
from problem3.scenarios import generate_suite
from problem3.simulator import LocalSimulator,ObservationClient

def run(cls,cases):
    rows=[];start=time.perf_counter()
    for c in cases:
        s=LocalSimulator(c);s.enter();p=cls();error=None
        try:r=p.run(ObservationClient(s))
        except Exception as e:error=str(e);r={}
        st=s.statistics();full=st['cleared_count']==st['source_count'] and r.get('completion_certified') and not error
        rows.append(dict(id=c['case_id'],seed=c['seed'],family=c['family'],time=st['virtual_time_s'],average=st['average_clear_time_s'],pass220=full and st['virtual_time_s']<=220*st['source_count'],full=bool(full),error=error,policy=r,sim=st))
    return dict(mean=statistics.mean(x['average'] or 1000000 for x in rows),passed=sum(x['pass220'] for x in rows),full=sum(x['full'] for x in rows),movement=statistics.mean(x['sim']['movement_m'] for x in rows),actions=statistics.mean(x['sim']['actions'] for x in rows),runtime=time.perf_counter()-start,rows=rows)

if __name__=='__main__':
    cases=generate_suite(3,'development_v2',int(sys.argv[1]) if len(sys.argv)>1 else 64)
    branches={'legacy':LegacyPolicy,'negative':NegativePolicy,'local':LocalPolicy,'negative_local':NegativeLocalPolicy,'global':GlobalPolicy,'global_negative':GlobalNegativePolicy,'combined':CombinedPolicy,'dynamic':DynamicPolicy}
    results={}
    for name,cls in branches.items():
        r=run(cls,cases);results[name]=r
        print(name,{k:v for k,v in r.items() if k!='rows'},flush=True)
    (ROOT/'problem3/results/p3_development_v3_screen.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

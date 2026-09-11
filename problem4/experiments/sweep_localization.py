from __future__ import annotations
import sys,json,statistics,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from problem4.legacy_policy import SearchPolicy as LegacyPolicy
from problem4.experiments.localization import SearchPolicy
from problem3.scenarios import generate_suite
from problem3.simulator import LocalSimulator,ObservationClient

def run(cls,cases):
    rows=[]
    for c in cases:
        s=LocalSimulator(c);s.enter();p=cls();error=None
        try:r=p.run(ObservationClient(s))
        except Exception as e:error=str(e);r={}
        st=s.statistics(); full=st['cleared_count']==st['source_count'] and r.get('completion_certified') and not error
        rows.append(dict(id=c['case_id'],time=st['virtual_time_s'],average=st['average_clear_time_s'],pass500=full and st['virtual_time_s']<=500*st['source_count'],full=bool(full),error=error,stats=r,sim=st))
    return dict(mean=statistics.mean(x['average'] or 1000000 for x in rows),passed=sum(x['pass500'] for x in rows),full=sum(x['full'] for x in rows),movement=statistics.mean(x['sim']['movement_m'] for x in rows),actions=statistics.mean(x['sim']['actions'] for x in rows),rows=rows)

if __name__=='__main__':
    cases=generate_suite(4,sys.argv[1] if len(sys.argv)>1 else 'development')
    results={}
    branches={'legacy':LegacyPolicy}
    for q in (.25,.35,.5,.65):
        for w in (.08,.12,.18,.3):
            name=f'q{q}w{w}'
            branches[name]=type(name,(SearchPolicy,),dict(localization_quantile=q,localization_width_fraction=w))
    for name,cls in branches.items():
        r=run(cls,cases);results[name]=r
        print(name,{k:v for k,v in r.items() if k!='rows'},flush=True)
    out=ROOT/'problem4/results/localization_development_sweep.json'
    out.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

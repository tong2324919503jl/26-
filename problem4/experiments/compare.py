"""Small development-only comparison runner for composable policy prototypes."""
from __future__ import annotations
import argparse
import importlib
import json
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from problem3.scenarios import generate_suite
from problem3.simulator import LocalSimulator,ObservationClient
from scripts.benchmark_search import aggregate


def evaluate(cls,split='development',count=96):
    rows=[]
    for case in generate_suite(4,split,count):
        sim=LocalSimulator(case); sim.enter(); start=time.perf_counter()
        policy=cls(); err=None; res={}
        try: res=policy.run(ObservationClient(sim))
        except Exception as exc: err=f'{type(exc).__name__}: {exc}'
        stats=sim.statistics(); done=stats['cleared_count']==stats['source_count'] and bool(res.get('completion_certified')) and not err
        rows.append(dict(case_id=case['case_id'],family=case['family'],error=err,**stats,
                    certified_full_clear=done,threshold_passed=done and stats['average_clear_time_s']<=500,
                    reward=-1000000 if not done else 1000*(stats['average_clear_time_s']<=500)+100*(1-stats['average_clear_time_s']/500),
                    program_runtime_s=time.perf_counter()-start,policy=res))
    return aggregate(rows),rows


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('target');p.add_argument('--split',choices=('development','development_v2'),default='development');p.add_argument('--count',type=int,default=96)
    a=p.parse_args(); module,name=a.target.split(':'); cls=getattr(importlib.import_module(module),name)
    s,rows=evaluate(cls,a.split,a.count)
    folder=ROOT/'problem4/results/iterations_v2';folder.mkdir(parents=True,exist_ok=True)
    (folder/f'{name.lower()}_{a.split}_{a.count}.json').write_text(json.dumps(dict(summary=s,episodes=rows),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(s,indent=2))

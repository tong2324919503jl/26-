"""Irregular 22-station layout with the frozen predicted-read/optical repair mixins."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from problem3.experiments_v4.bystander import PredictedGainMixin
from problem3.experiments_v4.unionmass import UnionmassMixin
from problem4.experiments_v4.teammate_cover import Shared22Policy,verify,fingerprints as base_fingerprints
from problem3.scenarios import generate_suite
from problem3.simulator import LocalSimulator,ObservationClient


class PredictedUnion22Policy(PredictedGainMixin,UnionmassMixin,Shared22Policy):
    pass


def fingerprints():
    values=base_fingerprints()
    for name in ('problem3/experiments_v4/bystander.py','problem3/experiments_v4/unionmass.py',
                 'problem4/experiments_v4/teammate_cover_combo.py'):
        values[name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    return values


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count',type=int,default=384)
    args=parser.parse_args();frozen=fingerprints();certificates=verify()
    rows=[];started=time.perf_counter()
    for case in generate_suite(4,'development_v3',args.count):
        if frozen!=fingerprints():raise RuntimeError('Frozen dependencies changed')
        sim=LocalSimulator(case);sim.enter();error=None;result={};cpu=time.perf_counter()
        try:result=PredictedUnion22Policy().run(ObservationClient(sim))
        except Exception as exc:error=repr(exc)
        stats=sim.statistics()
        full=bool(not error and result.get('completion_certified') and stats['source_count']==stats['cleared_count'])
        rows.append(dict(case_id=case['case_id'],seed=case['seed'],family=case['family'],**stats,
                         policy=result,error=error,full=full,
                         pass400=full and stats['average_clear_time_s']<=400,
                         program_runtime_s=time.perf_counter()-cpu))
        if len(rows)%48==0:print('done',len(rows),'mean',statistics.mean(r['average_clear_time_s'] for r in rows),'full',sum(r['full'] for r in rows),flush=True)
    if frozen!=fingerprints():raise RuntimeError('Frozen dependencies changed after evaluation')
    values=[row['average_clear_time_s'] for row in rows]
    summary=dict(mean=statistics.mean(values),p90=statistics.quantiles(values,n=10,method='inclusive')[8],
                 full=sum(row['full'] for row in rows),pass400=sum(row['pass400'] for row in rows),
                 movement_m=statistics.mean(row['movement_m'] for row in rows),
                 actions=statistics.mean(row['actions'] for row in rows),runtime_s=time.perf_counter()-started,
                 max_case_runtime_s=max(row['program_runtime_s'] for row in rows),
                 failures=[(row['case_id'],row['error']) for row in rows if not row['full']])
    folder=ROOT/'problem4/results/iterations_v4';folder.mkdir(exist_ok=True)
    output=folder/f'teammate_cover_combo_development_v3_{args.count}.json'
    output.write_text(json.dumps(dict(provenance='Self-built development_v3; no platform, holdout or stress.',
        dependencies=frozen,certificates=certificates,branches={'PredictedUnion22Policy':dict(summary=summary,episodes=rows)}),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()

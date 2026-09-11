"""Development-only paired runner for the 220/400 second targets."""
from __future__ import annotations
import argparse,importlib,json,statistics,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from problem3.scenarios import generate_suite
from problem3.simulator import LocalSimulator,ObservationClient

def evaluate(cls,problem,split='development_v2',count=96):
    threshold={3:220,4:400}[problem]
    rows=[]
    for case in generate_suite(problem,split,count):
        sim=LocalSimulator(case);sim.enter();start=time.perf_counter();error=None;result={}
        try: result=cls().run(ObservationClient(sim))
        except Exception as exc:error=f'{type(exc).__name__}: {exc}'
        elapsed=time.perf_counter()-start
        if sim.active:sim.exit()
        stats=sim.statistics()
        full=not error and bool(result.get('completion_certified')) and stats['cleared_count']==stats['source_count']
        passed=bool(full and stats['average_clear_time_s']<=threshold)
        rows.append(dict(case_id=case['case_id'],seed=case['seed'],family=case['family'],noise=case['noise'],
                    error=error,**stats,policy=result,certified_full_clear=bool(full),threshold_passed=passed,
                    reward=-1000000 if not full else 1000*passed+100*(1-stats['average_clear_time_s']/threshold),
                    program_runtime_s=elapsed))
    summary=dict(cases=len(rows),full=sum(r['certified_full_clear'] for r in rows),
                 mean=statistics.mean(r['average_clear_time_s'] for r in rows),
                 threshold=threshold,pass_rate=statistics.mean(r['threshold_passed'] for r in rows),
                 mean_movement=statistics.mean(r['movement_m'] for r in rows),
                 mean_actions=statistics.mean(r['actions'] for r in rows),
                 mean_reward=statistics.mean(r['reward'] for r in rows),
                 runtime=sum(r['program_runtime_s'] for r in rows),
                 failures=[(r['case_id'],r['error']) for r in rows if not r['certified_full_clear']])
    return summary,rows

def main():
    p=argparse.ArgumentParser();p.add_argument('targets',nargs='+');p.add_argument('--problem',type=int,choices=(3,4),required=True)
    p.add_argument('--split',choices=('development','development_v2','development_v3'),default='development_v2')
    p.add_argument('--count',type=int,default=96);args=p.parse_args()
    folder=ROOT/f'problem{args.problem}/results/iterations_v3';folder.mkdir(parents=True,exist_ok=True)
    for target in args.targets:
        module,name=target.split(':');cls=getattr(importlib.import_module(module),name)
        summary,rows=evaluate(cls,args.problem,args.split,args.count)
        stem=target.replace(':','_').replace('.','_').lower()
        dest=folder/f'{stem}_{args.split}_{args.count}.json'
        dest.write_text(json.dumps(dict(provenance='local development, not official',target=target,
                                       summary=summary,episodes=rows),indent=2)+'\n',encoding='utf-8')
        print(target,json.dumps(summary),flush=True)

if __name__=='__main__':main()

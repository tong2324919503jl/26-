"""Post-hoc channel action budget and explicit fixed-station necessity witnesses."""
from __future__ import annotations
import argparse,json,math,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from problem3.scenarios import generate_suite
from problem3.simulator import LocalSimulator,ObservationClient
from problem4.experiments_v3.posterior import Shared21Policy
from problem4.experiments_v3.rollout import received


def necessity_witnesses():
    points=Shared21Policy().coverage_points();rows=[]
    for index,point in enumerate(points):
        angle=math.atan2(point[1],point[0]) if index else 0.
        radius=1800. if 1<=index<=12 else 800. if index>12 else 100.
        source=dict(channel=1,x=radius*math.cos(angle),y=radius*math.sin(angle),radius=1000.,orientation_deg=math.degrees(angle)+(180 if index==0 else 0))
        visible=[j for j,q in enumerate(points) if received(source,q)]
        if visible!=[index]:raise AssertionError('Claimed necessary station has another receiver')
        rows.append({'station_index':index,'station':point,'source_witness':source,'receiving_stations':visible})
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--count',type=int,default=96);args=parser.parse_args()
    witnesses=necessity_witnesses();rows=[]
    for case in generate_suite(4,'development_v2',args.count):
        simulator=LocalSimulator(case,record=True);simulator.enter();result=Shared21Policy().run(ObservationClient(simulator))
        channels={s['channel'] for s in case['sources']};seen=set();empty=negative=discovery=0;empty_cost=negative_cost=0.;current=1
        for event in simulator.events:
            if event['action']!='measure':continue
            channel=event['channel'];cost=5+int(channel!=current);current=channel
            if channel not in channels:empty+=1;empty_cost+=cost
            elif channel not in seen:
                discovery+=1
                if event['response']['measure_result']=='no_signal':negative+=1;negative_cost+=cost
                else:seen.add(channel)
        n=len(channels)
        if n<16 and empty!=21*(20-n):raise AssertionError('Unexpected empty-channel scan count')
        rows.append({'case_id':case['case_id'],'family':case['family'],'source_count':n,
                     'empty_reads':empty,'source_discovery_reads':discovery,'source_negative_reads':negative,
                     'source_negative_time_per_source':negative_cost/n,'empty_time_per_source':empty_cost/n,
                     'oracle_saved_read_seconds_per_source':(negative_cost+(empty_cost if n==16 else 0))/n,
                     'baseline_seconds_per_source':simulator.statistics()['average_clear_time_s']})
    groups=[('all',rows),('n_below16',[r for r in rows if r['source_count']<16]),('n16',[r for r in rows if r['source_count']==16])]
    groups += [(family,[r for r in rows if r['family']==family]) for family in sorted({r['family'] for r in rows})]
    fields=('empty_reads','source_discovery_reads','source_negative_reads','source_negative_time_per_source','empty_time_per_source','oracle_saved_read_seconds_per_source','baseline_seconds_per_source')
    summary={name:{'cases':len(group),**{field:statistics.mean(row[field] for row in group) for field in fields}} for name,group in groups if group}
    output={'scope':'Post-hoc synthetic development_v2 only. Oracle removed-read budget holds the original movement trajectory fixed; not a universal algorithm lower bound.','station_necessity_witnesses':witnesses,'summary':summary,'episodes':rows}
    path=ROOT/'problem4/results/iterations_v3'/f'channel_action_audit_development_v2_{args.count}.json'
    path.write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()

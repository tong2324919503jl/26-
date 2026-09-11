"""Post-hoc development diagnosis. The audit oracle never chooses an action."""
from __future__ import annotations
import collections,json,math,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from problem4.experiments_v3.routing_departure import get_class
from problem3.geometry import distance
from problem3.simulator import LocalSimulator,ObservationClient
from problem3.scenarios import generate_suite

class TracedPolicy(get_class('departure_base')):
    def _scan(self,client,point):
        self._phase='scan';return super()._scan(client,point)
    def _localize(self,ch,client):
        self._phase='localize'
        start=client.position
        if not hasattr(self,'_visits'):self._visits=[]
        row={'channel':ch,'start':start,'movement':0.,'actions':0}
        self._localize_row=row
        result=super()._localize(ch,client)
        row['finish']=client.position;row['cleared']=ch in self.cleared
        self._visits.append(row);self._localize_row=None
        return result
    def _update_neighbors(self,client):
        self._phase='neighbors';return super()._update_neighbors(client)
    def _note(self,client,point):
        if not hasattr(self,'_phase_costs'):self._phase_costs=collections.defaultdict(lambda:[0.,0])
        movement=distance(client.position,point)
        self._phase_costs[self._phase][0]+=movement;self._phase_costs[self._phase][1]+=1
        if getattr(self,'_localize_row',None) is not None:
            self._localize_row['movement']+=movement;self._localize_row['actions']+=1
    def _measure(self,client,point,ch):
        self._note(client,point);return super()._measure(client,point,ch)
    def _clear(self,client,point,ch):
        self._note(client,point);return super()._clear(client,point,ch)

def main():
    rows=[]
    for case in generate_suite(4,'development_v2',96):
        sim=LocalSimulator(case);sim.enter();p=TracedPolicy();p.run(ObservationClient(sim))
        sources={s['channel']:s for s in case['sources']}
        for visit in p._visits:
            source=sources[visit['channel']]
            position=(source['x'],source['y'])
            visit['geometric_minimum']=max(0.,distance(visit['start'],position)-20)
            visit['extra_over_direct']=visit['movement']-visit['geometric_minimum']
        rows.append({'case_id':case['case_id'],'family':case['family'],'phase_costs':dict(p._phase_costs),'visits':p._visits})
    summary={}
    for family in ['all']+sorted(set(r['family'] for r in rows)):
        group=[r for r in rows if family=='all' or r['family']==family]
        summary[family]={'cases':len(group),'phases':{phase:[statistics.mean(r['phase_costs'].get(phase,[0,0])[i] for r in group) for i in range(2)] for phase in ['scan','localize','neighbors']},'mean_localization_extra_m':statistics.mean(sum(v['extra_over_direct'] for v in r['visits']) for r in group)}
    output=ROOT/'problem4/results/iterations_v3/routing_phase_audit96.json'
    output.write_text(json.dumps({'warning':'Post-hoc geometric diagnosis uses truth only after the policy has finished; not a deployed policy or universal lower bound.','summary':summary,'episodes':rows},indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()

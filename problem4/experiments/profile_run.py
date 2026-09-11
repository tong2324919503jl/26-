import json,statistics,math
from pathlib import Path
from problem4.experiments.routing import LegacyPolicy,nearest_route
from problem3.scenarios import generate_suite
from problem3.simulator import LocalSimulator,ObservationClient
class ProfileClient:
 def __init__(self,c):self.client=c;self.phase='other';self.cost={}
 def __getattr__(self,k):return getattr(self.client,k)
 def _call(self,kind,point,ch):
  before=self.client.virtual_time_s;move=math.dist(self.client.position,point)
  result=getattr(self.client,kind)(point,ch)
  bucket=self.cost.setdefault(self.phase,{'time':0,'move':0,'actions':0});bucket['time']+=self.client.virtual_time_s-before;bucket['move']+=move;bucket['actions']+=1
  return result
 def measure(self,point,ch):return self._call('measure',point,ch)
 def clear(self,point,ch):return self._call('clear',point,ch)
class ProfilePolicy(LegacyPolicy):
 def _scan(self,client,point):client.phase='discovery';super()._scan(client,point)
 def _localize(self,ch,client):client.phase='localize';return super()._localize(ch,client)
 def _update_neighbors(self,client):client.phase='neighbor';super()._update_neighbors(client)
rows=[]
for case in generate_suite(4,'development_v2',384):
 sim=LocalSimulator(case);sim.enter();client=ProfileClient(ObservationClient(sim));policy=ProfilePolicy();r=policy.run(client)
 # Evaluation-only hindsight route visits ALL fixed scan points + exact actual source positions.
 goals=[(p,'scan',i) for i,p in enumerate(policy.coverage_points()) if math.dist(p,(0,0))>.001]+[((s['x'],s['y']),'source',s['channel']) for s in case['sources']]
 route=nearest_route((0,0),goals);route_length=sum(math.dist(((0,0) if i==0 else route[i-1][0]),g[0]) for i,g in enumerate(route))
 # Euclidean MST between zero-radius scan stops and radius20 clearance disks is a valid travel lower bound IF all fixed scan stops are required.
 vertices=[((0.,0.),0.)]+[(p,0.) for p in policy.coverage_points() if math.dist(p,(0,0))>.001]+[((s['x'],s['y']),20.) for s in case['sources']]
 best=[math.inf]*len(vertices);best[0]=0.;done=set();mst=0.
 while len(done)<len(vertices):
  i=min((i for i in range(len(vertices)) if i not in done),key=lambda i:best[i]);done.add(i);mst+=best[i]
  for j in range(len(vertices)):
   if j not in done:best[j]=min(best[j],max(0.,math.dist(vertices[i][0],vertices[j][0])-vertices[i][1]-vertices[j][1]))
 rows.append({'id':case['case_id'],'n':len(case['sources']),'cost':client.cost,'hindsight_route_length':route_length,'fixed_cover_mst_lower_bound':mst,**sim.statistics()})
summary={phase:{k:statistics.mean(r['cost'].get(phase,{}).get(k,0) for r in rows) for k in ('time','move','actions')} for phase in ('discovery','localize','neighbor')}
summary['full']={'mean_seconds_per_source':statistics.mean(r['average_clear_time_s'] for r in rows),'hindsight_route_length':statistics.mean(r['hindsight_route_length'] for r in rows),'fixed_cover_mst_lower_bound':statistics.mean(r['fixed_cover_mst_lower_bound'] for r in rows)}
print(json.dumps(summary,indent=2));Path(__file__).with_name('profile_development_v2_384.json').write_text(json.dumps({'summary':summary,'episodes':rows},indent=2)+'\n',encoding='utf-8')

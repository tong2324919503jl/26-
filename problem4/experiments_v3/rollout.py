"""Belief-world rollout for discovery order; observation-only development code.

Generated worlds are hypothetical samples conditioned on the public history.
The real simulator, its case id, source count and source positions are never read.
The ordinary certified strategy still executes all real actions and termination.
"""
from __future__ import annotations
import copy,math,random
from problem3.geometry import distance,polygon_centroid,enclosing_circle
from problem3.simulator import LocalSimulator,ObservationClient
from problem4.experiments_v3.posterior import hemisphere_mask,Shared21Policy


def sample_polygon(poly,rng):
    if len(poly)<3:return rng.choice(poly)
    triangles=[(poly[0],poly[i],poly[i+1]) for i in range(1,len(poly)-1)]
    areas=[abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])) for a,b,c in triangles]
    if sum(areas)<1e-10:return polygon_centroid(poly)
    a,b,c=rng.choices(triangles,weights=areas)[0]
    u,v=rng.random(),rng.random()
    if u+v>1:u,v=1-u,1-v
    return a[0]+u*(b[0]-a[0])+v*(c[0]-a[0]),a[1]+u*(b[1]-a[1])+v*(c[1]-a[1])


def received(source,point):
    dx,dy=point[0]-source['x'],point[1]-source['y']
    if math.hypot(dx,dy)>source['radius']:return False
    angle=source['orientation_deg']
    return angle is None or dx*math.cos(math.radians(angle))+dy*math.sin(math.radians(angle))>=0


class HistorySimulator(LocalSimulator):
    def _error(self,ch):
        key=(ch,tuple(round(x,8) for x in self.position))
        if key in self.old_bearings:
            source=self.sources[ch]
            exact=math.degrees(math.atan2(source['y']-self.position[1],source['x']-self.position[0]))
            error=(self.old_bearings[key]-exact+180)%360-180
            return max(-1.,min(1.,error))
        return super()._error(ch)


class RolloutMixin:
    rollout_worlds=3
    rollout_choices=3
    rollout_interval=2
    rollout_budget=8
    rollout_gain=5.
    rollout_risk=0.
    def _rank_scores(self,rows):
        scores=[]
        for values in rows:
            mean=sum(values)/len(values)
            scores.append(mean+self.rollout_risk*math.sqrt(sum((v-mean)**2 for v in values)/len(values)))
        return scores
    def _choices(self,original,goals,client):
        by_key={self._goal_key(g):g for g in goals}
        choices=[original]
        for goal in [by_key[k] for k in self._route_keys if k in by_key]+sorted(goals,key=lambda g:distance(client.position,g[0])):
            if goal not in choices:choices.append(goal)
            if len(choices)>=self.rollout_choices:break
        return choices
    def _known_sample(self,ch,rng):
        positive=[p for p,a in self.observations[ch]]
        negative=getattr(self,'_negative_history',{}).get(ch,[])
        for _ in range(800):
            g=sample_polygon(self.regions[ch],rng)
            if math.hypot(*g)>1800:continue
            low=max(1000.,max(distance(g,p) for p in positive))
            if low>1500:continue
            r=rng.uniform(low,1500.);mask=(1<<64)-1;omni=True
            for p in positive:mask&=hemisphere_mask(p[0]-g[0],p[1]-g[1])
            for q in negative:
                if distance(g,q)<=r:mask&=((1<<64)-1)^hemisphere_mask(q[0]-g[0],q[1]-g[1]);omni=False
            if not mask and not omni:continue
            if omni and rng.random()<1/(1+mask.bit_count()/64):orientation=None
            else:
                options=[i for i in range(64) if mask&(1<<i)]
                if not options:continue
                orientation=360*(rng.choice(options)+.5)/64
            source=dict(channel=ch,x=g[0],y=g[1],radius=r,orientation_deg=orientation)
            if all(received(source,p) for p in positive) and not any(received(source,q) for q in negative):return source
        raise ValueError('No finite belief sample for a known source')
    def _world(self,rng):
        known=set(self.regions)|self.cleared;k=len(known)
        unseen=max(1e-12,1-self.scanned_mask.bit_count()/len(self.samples))
        ns=list(range(max(10,k),17));weights=[math.comb(n,k)*unseen**(n-k) for n in ns]
        n=rng.choices(ns,weights=weights)[0]
        sources=[dict(channel=ch,x=0.,y=0.,radius=1000.,orientation_deg=None) if ch in self.cleared else self._known_sample(ch,rng) for ch in known]
        for ch in rng.sample([ch for ch in range(1,21) if ch not in known],n-k):
            for _ in range(20000):
                r=1800*math.sqrt(rng.random());a=rng.uniform(0,math.tau)
                source=dict(channel=ch,x=r*math.cos(a),y=r*math.sin(a),radius=rng.uniform(1000,1500),orientation_deg=None if rng.random()<.5 else rng.uniform(0,360))
                if not any(received(source,p) for p in self.coverage_visited):break
            else:raise ValueError('No finite belief sample for an undiscovered source')
            sources.append(source)
        return dict(seed=rng.randrange(1<<40),sources=sources,noise='hash_uniform')
    def _continue(self,case,client,pending,goal):
        policy=copy.deepcopy(self);policy._rollout_disabled=True
        scans=list(pending);policy._shared_pending=scans
        sim=HistorySimulator(case);sim.old_bearings={(ch,tuple(round(x,8) for x in p)):a for ch,items in self.observations.items() for p,a in items}
        sim.enter();sim.position=tuple(client.position);sim.current_channel=client.current_channel;sim.cleared=set(self.cleared)
        virtual=ObservationClient(sim)
        steps=0
        while scans or any(ch not in policy.cleared for ch in policy.regions):
            if steps:
                goal=policy._route_goal(virtual,scans)
            _,kind,ident=goal
            if kind=='scan':policy._scan(virtual,scans.pop(ident))
            else:policy._localize(ident,virtual)
            policy._update_neighbors(virtual)
            if len(policy.cleared)==16:break
            steps+=1
            if steps>150:raise RuntimeError('Hypothetical rollout exceeded stage limit')
        if len(sim.cleared)!=len(sim.sources):raise RuntimeError('Hypothetical world contradicts completion')
        return sim.virtual_time_s/len(sim.sources)
    def _route_goal(self,client,pending):
        original=super()._route_goal(client,pending)
        if getattr(self,'_rollout_disabled',False):return original
        if not self.coverage_visited or len(pending)<3 or len(set(self.regions)|self.cleared)==16:return original
        self._rollout_calls=getattr(self,'_rollout_calls',0)+1
        if self._rollout_calls%self.rollout_interval or self.stats.get('rollout_decisions',0)>=self.rollout_budget:return original
        goals=[(p,'scan',i) for i,p in enumerate(pending)]+[(polygon_centroid(poly),'clear',ch) for ch,poly in self.regions.items() if ch not in self.cleared]
        choices=self._choices(original,goals,client)
        rng=random.Random(173119+self._rollout_calls*139)
        try:worlds=[self._world(rng) for _ in range(self.rollout_worlds)]
        except ValueError:
            self.stats['rollout_sampling_failures']=self.stats.get('rollout_sampling_failures',0)+1
            return original
        rows=[]
        for goal in choices:
            values=[]
            for world in worlds:
                try:values.append(self._continue(world,client,pending,goal))
                except Exception:values.append(100000.)
            rows.append(values)
        scores=self._rank_scores(rows)
        self.stats['rollout_decisions']=self.stats.get('rollout_decisions',0)+1
        best=min(range(len(choices)),key=lambda i:scores[i])
        if scores[best]<scores[0]-self.rollout_gain:
            self.stats['rollout_changed_goals']=self.stats.get('rollout_changed_goals',0)+1
            return choices[best]
        return original


class RolloutPolicy(RolloutMixin,Shared21Policy):pass
class FiveWorldRolloutPolicy(RolloutPolicy):rollout_worlds=5

class DiverseRolloutPolicy(RolloutPolicy):
    rollout_worlds=7
    rollout_choices=4
    rollout_risk=.25
    def _choices(self,original,goals,client):
        by_key={self._goal_key(g):g for g in goals}
        ordered=[by_key[k] for k in self._route_keys if k in by_key]
        scans=[g for g in ordered if g[1]=='scan'];clears=[g for g in ordered if g[1]=='clear']
        choices=[original]
        for goal in scans[:2]+clears[:2]+ordered:
            if goal not in choices:choices.append(goal)
            if len(choices)>=self.rollout_choices:break
        return choices

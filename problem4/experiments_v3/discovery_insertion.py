"""Cheap discovery precedence and future source insertion proxy for routing.

Latent states are drawn only from the public routing prior after conditioning
on already completed scans. Scores choose a route and provide no certificate.
"""
from __future__ import annotations
import math,random
from problem3.geometry import distance,polygon_centroid
from problem4.routing import nearest_seed,insertion_seed,two_opt,route_length
from problem4.experiments_v3.coverage_ring_policy import Ring12CoverPolicy
from problem4.experiments_v3.routing_shared import SharedBaselineMixin


def fixed_first_route(first,matrix):
    """Nearest construction with 2-opt on the suffix, retaining the first goal."""
    n=len(matrix)-1
    if n<=1:return [first]
    remaining=[i for i in range(n) if i!=first]
    mapping=remaining+[first]
    sub=[[matrix[i][j] for j in mapping] for i in mapping]
    suffix=two_opt(nearest_seed(sub),sub)
    return [first]+[remaining[i] for i in suffix]


def insertion_terms(route,matrix,scan_indices,particles):
    """Average extra travel and scan latency, allowing service after discovery.

    particles contains (distance to each goal, visible scan goal indexes).
    Removing40m on an inserted detour and20m at the free end is a heuristic
    optical-neighborhood allowance, never a feasible-route certificate.
    """
    extra_sum=latency_sum=0.
    for distances,visible in particles:
        scans=0;first=None
        for index,goal in enumerate(route):
            if goal in scan_indices:
                scans+=1
                if goal in visible:first=index;break
        if first is None:raise ValueError('Latent state has no remaining discovery point')
        extra=max(0.,distances[route[-1]]-20.)
        for a,b in zip(route[first:],route[first+1:]):
            extra=min(extra,max(0.,distances[a]+distances[b]-matrix[a][b]-40.))
        extra_sum+=extra;latency_sum+=scans
    return extra_sum/len(particles),latency_sum/len(particles)


class DiscoveryInsertionMixin:
    discovery_enabled=True
    discovery_samples=128
    discovery_first_seeds=6
    discovery_count_model='bounded'
    discovery_insertion_weight=1.
    discovery_latency_weight=1.
    discovery_gain_s=0.

    def _expected_unknown(self,known,unseen):
        fraction=unseen/len(self.samples)
        if self.discovery_count_model=='independent':
            return (20-known)*.65*fraction/(.35+.65*fraction)
        ns=list(range(max(10,known),17))
        weights=[math.comb(n,known)*fraction**(n-known) for n in ns]
        total=sum(weights)
        return sum((n-known)*w for n,w in zip(ns,weights))/total if total else 0.

    def _first_candidates(self,goals,matrix,original):
        scans=[i for i,g in enumerate(goals) if g[1]=='scan']
        clears=[i for i,g in enumerate(goals) if g[1]=='clear']
        nearest=lambda indices:sorted(indices,key=lambda i:matrix[-1][i])
        choices=[original[0]]
        choices+=nearest(scans)[:2]+nearest(clears)[:2]
        if scans:
            first=goals[nearest(scans)[0]][0]
            origin=self._discovery_origin
            angle=math.atan2(first[1]-origin[1],first[0]-origin[0])
            choices+=sorted(scans,key=lambda i:abs((math.atan2(goals[i][0][1]-origin[1],goals[i][0][0]-origin[0])-angle+math.pi)%math.tau-math.pi)/(1+matrix[-1][i]/1000),reverse=True)[:2]
        choices+=nearest(scans)+nearest(clears)
        return list(dict.fromkeys(choices))[:self.discovery_first_seeds]

    def _route_goal(self,client,pending):
        original_goal=super()._route_goal(client,pending)
        known=len(set(self.regions)|self.cleared)
        if (not self.discovery_enabled or not self.coverage_visited
                or known==16 or len(pending)<2):return original_goal
        latent=[i for i in range(len(self.samples)) if not (self.scanned_mask>>i)&1]
        if not latent:return original_goal
        expected=self._expected_unknown(known,len(latent))
        if expected<.025:return original_goal
        if len(latent)>self.discovery_samples:
            rng=random.Random(620331+self.scanned_mask%1000000007)
            latent=rng.sample(latent,self.discovery_samples)
        goals=[(p,'scan',i) for i,p in enumerate(pending)]+[(polygon_centroid(poly),'clear',ch) for ch,poly in self.regions.items() if ch not in self.cleared]
        key_to_index={self._goal_key(g):i for i,g in enumerate(goals)}
        original=[key_to_index[k] for k in self._route_keys if k in key_to_index]
        if len(original)!=len(goals):return original_goal
        points=[g[0] for g in goals]+[client.position]
        matrix=[[distance(a,b) for b in points] for a in points]
        scan_indices={i for i,g in enumerate(goals) if g[1]=='scan'}
        masks={i:self._mask(goals[i][0]) for i in scan_indices}
        particles=[]
        for sample_index in latent:
            location,_,_=self.samples[sample_index]
            visible={i for i,mask in masks.items() if (mask>>sample_index)&1}
            if not visible:
                self.stats['discovery_invalid_particles']=self.stats.get('discovery_invalid_particles',0)+1
                return original_goal
            particles.append(([distance(location,p) for p in points[:-1]],visible))
        candidates=[original,list(reversed(original)),two_opt(nearest_seed(matrix),matrix),two_opt(insertion_seed(matrix),matrix)]
        self._discovery_origin=client.position
        candidates.extend(fixed_first_route(i,matrix) for i in self._first_candidates(goals,matrix,original))
        candidates=list(dict.fromkeys(tuple(r) for r in candidates))
        def score(route):
            extra,latency=insertion_terms(route,matrix,scan_indices,particles)
            return route_length(route,matrix)/5+expected*(self.discovery_insertion_weight*extra/5+self.discovery_latency_weight*6*latency)
        scores=[score(route) for route in candidates]
        best=min(range(len(candidates)),key=lambda i:scores[i])
        self.stats['discovery_proxy_decisions']=self.stats.get('discovery_proxy_decisions',0)+1
        if scores[best]>=scores[0]-self.discovery_gain_s:return original_goal
        chosen=candidates[best]
        if chosen[0]!=original[0]:self.stats['discovery_proxy_changed_goals']=self.stats.get('discovery_proxy_changed_goals',0)+1
        self._route_keys=[self._goal_key(goals[i]) for i in chosen]
        return goals[chosen[0]]


def get_class(name):
    tokens=set(name.split('_'))
    attrs=dict(shared_min_channels=1,shared_radius_m=50.,shared_fresh_only=True)
    if 'base' in tokens:attrs['discovery_enabled']=False
    if 'soft' in tokens:attrs.update(discovery_insertion_weight=.5,discovery_latency_weight=.5)
    if 'strong' in tokens:attrs.update(discovery_insertion_weight=2.,discovery_latency_weight=2.)
    if 'legacy' in tokens:attrs['discovery_count_model']='independent'
    if 'noinsert' in tokens:attrs['discovery_insertion_weight']=0.
    if 'nolatency' in tokens:attrs['discovery_latency_weight']=0.
    if 'few' in tokens:attrs['discovery_first_seeds']=3
    return type(name,(DiscoveryInsertionMixin,SharedBaselineMixin,Ring12CoverPolicy),attrs)

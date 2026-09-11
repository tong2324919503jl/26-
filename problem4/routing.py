"""Observation-only open-tour planning for mixed directional search.

Visits are ordered by geometric travel cost with 2-opt reversals, Or-opt
relocations of one to three consecutive visits, several initial constructions,
and the previous route as a warm start. An approximate discovery prior accounts
for future channel-scanning cost. These choices affect speed only: the calling
policy must retain its independent coverage and clearance certificates.

Once 16 distinct channels have been discovered, further discovery is omitted.
Only actual successful clearance of all 16 certifies early termination.
"""
from __future__ import annotations
import math
from problem3.geometry import distance, polygon_centroid

def route_length(route,matrix):
    return sum(matrix[len(matrix)-1 if i==0 else route[i-1]][j] for i,j in enumerate(route))


def two_opt(route,matrix,moves=80):
    route=list(route);start=len(matrix)-1
    for _ in range(moves):
        best=-.01;change=None
        for i in range(len(route)-1):
            a=start if i==0 else route[i-1];b=route[i]
            for j in range(i+1,len(route)):
                c=route[j];d=route[j+1] if j+1<len(route) else None
                delta=matrix[a][c]-matrix[a][b]
                if d is not None:delta+=matrix[b][d]-matrix[c][d]
                if delta<best:best=delta;change=(i,j)
        if change is None:break
        i,j=change;route[i:j+1]=reversed(route[i:j+1])
    return route


def or_opt(route,matrix,max_moves=16,max_chain=3):
    """Relocate contiguous chains, maintaining the fixed start and free end."""
    route=list(route);start=len(matrix)-1;n=len(route)
    for _ in range(max_moves):
        best=-.01;change=None
        for k in range(1,min(max_chain,n-1)+1):
            for i in range(n-k+1):
                chain=route[i:i+k];rest=route[:i]+route[i+k:]
                a=start if i==0 else route[i-1];b=route[i+k] if i+k<n else None
                removal=-matrix[a][chain[0]]
                if b is not None:removal+=matrix[a][b]-matrix[chain[-1]][b]
                for j in range(len(rest)+1):
                    if j==i:continue
                    c=start if j==0 else rest[j-1];d=rest[j] if j<len(rest) else None
                    for reverse in (False,True) if k>1 else (False,):
                        first,last=(chain[-1],chain[0]) if reverse else (chain[0],chain[-1])
                        delta=removal+matrix[c][first]
                        if d is not None:delta+=matrix[last][d]-matrix[c][d]
                        if delta<best:best=delta;change=(i,k,j,reverse)
        if change is None:break
        i,k,j,reverse=change;chain=route[i:i+k];rest=route[:i]+route[i+k:]
        if reverse:chain.reverse()
        route=rest[:j]+chain+rest[j:]
        route=two_opt(route,matrix,20)
    return route


def nearest_seed(matrix,first=None):
    n=len(matrix)-1;remaining=set(range(n));route=[];last=n
    if first is not None:route=[first];remaining.remove(first);last=first
    while remaining:
        nxt=min(remaining,key=lambda i:matrix[last][i]);route.append(nxt);remaining.remove(nxt);last=nxt
    return route


def insertion_seed(matrix):
    n=len(matrix)-1;start=n;remaining=set(range(n))
    if not remaining:return []
    first=max(remaining,key=lambda i:matrix[start][i]);route=[first];remaining.remove(first)
    while remaining:
        best=None
        for point in remaining:
            for index in range(len(route)+1):
                a=start if index==0 else route[index-1];b=route[index] if index<len(route) else None
                extra=matrix[a][point]+(matrix[point][b]-matrix[a][b] if b is not None else 0)
                candidate=(extra,point,index)
                if best is None or candidate<best:best=candidate
        _,point,index=best;route.insert(index,point);remaining.remove(point)
    return route


class RoutingMixin:
    escape_oropt=True
    escape_chain=3
    escape_starts=4
    escape_warm=True
    escape_info_weight=1.
    escape_oropt_final_only=True

    # A discrete prior estimates future scanning cost only. It is never used
    # to remove source candidates or to certify completion.
    samples = None
    mask_cache = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scanned_mask = 0
        if type(self).samples is None:
            points = [(x,y) for x in range(-1800,1801,300)
                      for y in range(-1800,1801,300) if math.hypot(x,y)<=1800]
            type(self).samples = [(point,radius,angle) for point in points
                                  for radius in (1000,1250,1500)
                                  for angle in [None]*8+[i*math.tau/8 for i in range(8)]]

    def _mask(self, point):
        key = tuple(round(value,5) for value in point)
        if key not in self.mask_cache:
            mask = 0
            for index,(source,radius,angle) in enumerate(self.samples):
                dx,dy = point[0]-source[0],point[1]-source[1]
                if math.hypot(dx,dy)<=radius and (angle is None or
                        dx*math.cos(angle)+dy*math.sin(angle)>=-1e-8):
                    mask |= 1<<index
            self.mask_cache[key] = mask
        return self.mask_cache[key]

    def _scan(self, client, point):
        super()._scan(client,point)
        self.scanned_mask |= self._mask(point)

    @staticmethod
    def _goal_key(goal):
        p,kind,ident=goal
        return (kind,round(p[0],5),round(p[1],5)) if kind=='scan' else (kind,ident)

    def _route_goal(self,client,pending):
        known=set(self.regions)|self.cleared
        if len(known)==16:pending=[]
        goals=[(p,'scan',i) for i,p in enumerate(pending)]+[(polygon_centroid(p),'clear',ch) for ch,p in self.regions.items() if ch not in self.cleared]
        points=[g[0] for g in goals]+[client.position]
        matrix=[[distance(a,b) for b in points] for a in points]
        seeds=[nearest_seed(matrix)]
        if self.escape_starts>1:
            seeds.append(insertion_seed(matrix))
        if self.escape_starts>2:
            ordered=sorted(range(len(goals)),key=lambda i:math.atan2(goals[i][0][1],goals[i][0][0]))
            if ordered:
                cut=min(range(len(ordered)),key=lambda i:matrix[-1][ordered[i]])
                angular=ordered[cut:]+ordered[:cut]
                seeds.append(angular)
                if self.escape_starts>3:seeds.append([angular[0]]+list(reversed(angular[1:])))
        if self.escape_starts>4:
            nearest=sorted(range(len(goals)),key=lambda i:matrix[-1][i])
            seeds.extend(nearest_seed(matrix,i) for i in nearest[1:self.escape_starts-3])
        if self.escape_warm and hasattr(self,'_route_keys'):
            mapping={self._goal_key(g):i for i,g in enumerate(goals)}
            warm=[mapping[k] for k in self._route_keys if k in mapping]
            for point in range(len(goals)):
                if point in warm:continue
                best=min(range(len(warm)+1),key=lambda i:matrix[-1 if i==0 else warm[i-1]][point]+(matrix[point][warm[i]]-matrix[-1 if i==0 else warm[i-1]][warm[i]] if i<len(warm) else 0))
                warm.insert(best,point)
            seeds.append(warm)
        candidates=[]
        for seed in seeds:
            route=two_opt(seed,matrix)
            if self.escape_oropt and not self.escape_oropt_final_only:route=or_opt(route,matrix,max_chain=self.escape_chain)
            candidates.append(route)
        route=min(candidates,key=lambda r:route_length(r,matrix))
        if self.escape_oropt and self.escape_oropt_final_only:route=or_opt(route,matrix,max_chain=self.escape_chain)
        if self.escape_info_weight and pending and len(pending)>1:
            total=len(self.samples);unseen=total-self.scanned_mask.bit_count()
            if unseen:
                unknown=20-len(known);posterior=.65*unseen/(.35*total+.65*unseen)
                masks={i:self._mask(p) for i,p in enumerate(pending)}
                def score(r):
                    cost=route_length(r,matrix)/5;covered=self.scanned_mask
                    for index in r:
                        _,kind,ident=goals[index]
                        if kind=='scan':
                            cost+=self.escape_info_weight*6*unknown*((1-posterior)+posterior*(total-covered.bit_count())/unseen)
                            covered|=masks[ident]
                    return cost
                best=score(route)
                for _ in range(20):
                    changed=False
                    for i in range(len(route)-1):
                        for j in range(i+1,len(route)):
                            candidate=route[:i]+list(reversed(route[i:j+1]))+route[j+1:];cost=score(candidate)
                            if cost<best-.01:route=candidate;best=cost;changed=True;break
                        if changed:break
                    if not changed:break
        self._route_keys=[self._goal_key(goals[i]) for i in route]
        return goals[route[0]]


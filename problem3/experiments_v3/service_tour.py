"""Development: route a probe-then-clear service instead of a guessed point."""
from __future__ import annotations
from types import SimpleNamespace
from problem3.geometry import distance,enclosing_circle,polygon_centroid
from problem3.experiments_v3.candidate import SearchPolicy as Candidate
from problem4.routing import nearest_seed,insertion_seed,route_length


def directed_two_opt(route,matrix,moves=35):
    route=list(route);start=len(matrix)-1
    for _ in range(moves):
        prefix=[0.]
        for a,b in zip(route,route[1:]):prefix.append(prefix[-1]+matrix[b][a]-matrix[a][b])
        best=-.01;change=None
        for i in range(len(route)-1):
            a=start if not i else route[i-1];b=route[i]
            for j in range(i+1,len(route)):
                c=route[j];d=route[j+1] if j+1<len(route) else None
                delta=matrix[a][c]-matrix[a][b]+prefix[j]-prefix[i]
                if d is not None:delta+=matrix[b][d]-matrix[c][d]
                if delta<best:best=delta;change=(i,j)
        if change is None:break
        i,j=change;route[i:j+1]=reversed(route[i:j+1])
    return route


class ServiceTourMixin:
    service_penalty=1.
    service_adjust_probe=False
    def _route_goal(self,client,pending):
        original=super()._route_goal(client,pending)
        actual_pending=[] if len(set(self.regions)|self.cleared)==16 else pending
        goals=[(p,'scan',i) for i,p in enumerate(actual_pending)]
        goals += [(polygon_centroid(p),'clear',ch) for ch,p in self.regions.items() if ch not in self.cleared]
        points=[g[0] for g in goals]+[client.position]
        matrix=[[distance(a,b) for b in points] for a in points]
        for j,(_,kind,ch) in enumerate(goals):
            if kind!='clear':continue
            center,radius=enclosing_circle(self.regions[ch])
            if radius<=self.config.exploratory_clear_radius_m:continue
            for i,previous in enumerate(points):
                if i==j:continue
                probe=self._probe_point(ch,SimpleNamespace(position=previous),0)
                direct=distance(previous,points[j])
                matrix[i][j]=direct+self.service_penalty*max(0.,distance(previous,probe)+distance(probe,points[j])-direct)
        seeds=[nearest_seed(matrix),insertion_seed(matrix)]
        mapping={self._goal_key(g):i for i,g in enumerate(goals)}
        if hasattr(self,'_route_keys'):seeds.append([mapping[k] for k in self._route_keys if k in mapping])
        candidates=[directed_two_opt(r,matrix) for r in seeds if len(r)==len(goals)]
        route=min(candidates,key=lambda r:route_length(r,matrix))
        self._route_keys=[self._goal_key(goals[i]) for i in route]
        return goals[route[0]]


class ServicePolicy(ServiceTourMixin,Candidate):pass
class HalfServicePolicy(ServicePolicy):service_penalty=.5
class DoubleServicePolicy(ServicePolicy):service_penalty=2.

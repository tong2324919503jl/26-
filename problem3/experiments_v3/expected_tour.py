"""Expected edge lengths integrate public localization uncertainty in routing."""
from problem3.geometry import distance, polygon_centroid, enclosing_circle
from problem4.routing import nearest_seed, insertion_seed, two_opt, or_opt, route_length
from problem3.experiments_v3.lookahead import source_quadrature
from problem3.experiments_v3.coverage_family_tuning import get_policy

BasePolicy=get_policy(9,1700)


class ExpectedTourPolicy(BasePolicy):
    expected_edge_weight=1.
    def _route_goal(self,client,pending):
        original=super()._route_goal(client,pending)
        if len(set(self.regions)|self.cleared)==16:pending=[]
        goals=[(p,'scan',i) for i,p in enumerate(pending)]
        goals.extend((polygon_centroid(poly),'clear',ch) for ch,poly in self.regions.items() if ch not in self.cleared)
        supports=[]
        for p,kind,ch in goals:
            nodes=[]
            if kind=='clear' and enclosing_circle(self.regions[ch])[1]>60.:
                nodes=source_quadrature(self.regions[ch],self.observations[ch],self.negative_history.get(ch,[]),5)
            supports.append([(w,g) for w,g,_,_ in nodes] if nodes else [(1.,p)])
        supports.append([(1.,client.position)])
        points=[p for p,_,_ in goals]+[client.position]
        matrix=[[0.]*len(points) for _ in points]
        for i in range(len(points)):
            for j in range(i):
                center=distance(points[i],points[j])
                expected=sum(w*v*distance(g,h) for w,g in supports[i] for v,h in supports[j])
                matrix[i][j]=matrix[j][i]=center+self.expected_edge_weight*(expected-center)
        mapping={self._goal_key(goal):i for i,goal in enumerate(goals)}
        warm=[mapping[key] for key in self._route_keys if key in mapping]
        seeds=[nearest_seed(matrix),insertion_seed(matrix),warm]
        route=min((two_opt(r,matrix) for r in seeds),key=lambda r:route_length(r,matrix))
        route=or_opt(route,matrix)
        self._route_keys=[self._goal_key(goals[i]) for i in route]
        if goals[route[0]]!=original:self.stats['expected_route_changes']=self.stats.get('expected_route_changes',0)+1
        return goals[route[0]]


class HalfExpectedTourPolicy(ExpectedTourPolicy):expected_edge_weight=.5

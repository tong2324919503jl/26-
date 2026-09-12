"""Rebuild full mixed routes from alternative first actions; rank only."""
from problem3.geometry import distance, polygon_centroid
from problem4.routing import nearest_seed
from problem4.speed_policy import SearchPolicy as BasePolicy
from problem4.discovery_route import DiscoveryRouteMixin


def fixed_first_two_opt(route, matrix, moves=24):
    """Optimize an open route while retaining its specified first action."""
    route = list(route)
    for _ in range(moves):
        best, change = -.01, None
        for i in range(1, len(route)-1):
            a, b = route[i-1], route[i]
            for j in range(i+1, len(route)):
                c = route[j]
                d = route[j+1] if j+1 < len(route) else None
                delta = matrix[a][c] - matrix[a][b]
                if d is not None:
                    delta += matrix[b][d] - matrix[c][d]
                if delta < best:
                    best, change = delta, (i, j)
        if change is None:
            break
        i, j = change
        route[i:j+1] = reversed(route[i:j+1])
    return route


class GlobalDiscoveryMixin(DiscoveryRouteMixin):
    discovery_first_scans = 4
    discovery_first_clears = 3

    def _route_goal(self, client, pending):
        original = BasePolicy._route_goal(self, client, pending)
        if self.discovery_mode == 'off' or len(set(self.regions) | self.cleared) >= 16 or len(pending) < 2:
            return original
        context = self._discovery_context()
        if context is None:
            return original
        goals = [(p, 'scan', i) for i, p in enumerate(pending)]
        goals += [(polygon_centroid(poly), 'clear', ch) for ch, poly in self.regions.items()
                  if ch not in self.cleared]
        mapping = {self._goal_key(goal): i for i, goal in enumerate(goals)}
        original_ids = [mapping[key] for key in self._route_keys if key in mapping]
        if len(original_ids) != len(goals):
            return original
        points = [goal[0] for goal in goals] + [client.position]
        matrix = [[distance(a, b) for b in points] for a in points]
        firsts = {original_ids[0]}
        for kind, limit in (('scan', self.discovery_first_scans), ('clear', self.discovery_first_clears)):
            options = sorted((i for i, g in enumerate(goals) if g[1] == kind), key=lambda i: matrix[-1][i])
            firsts.update(options[:limit])
        candidates = [original_ids]
        for first in sorted(firsts):
            candidates.append(fixed_first_two_opt(nearest_seed(matrix, first), matrix))
        selected = min(candidates, key=lambda route: self._discovery_score([goals[i] for i in route], client, context))
        self.stats['discovery_global_choices'] = self.stats.get('discovery_global_choices', 0) + 1
        if selected[0] != original_ids[0]:
            self.stats['discovery_global_changed'] = self.stats.get('discovery_global_changed', 0) + 1
        self._route_keys = [self._goal_key(goals[i]) for i in selected]
        return goals[selected[0]]

    def _result(self, reason, coverage_complete):
        result = super()._result(reason, coverage_complete)
        result['effective_settings'].update(discovery_search='forced_first_full_route',
            discovery_first_scans=self.discovery_first_scans,
            discovery_first_clears=self.discovery_first_clears)
        return result


class SearchPolicy(GlobalDiscoveryMixin, BasePolicy):
    algorithm_version = 'problem4_v5_discovery_global_route'

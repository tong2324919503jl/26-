"""Geometry-only discovery scheduling; never a completion criterion.

Integrate continuous emitter orientation at deterministic equal-area source
nodes. The position/radius quadrature and count model rank scan/clear orders
only. Every certified layout station remains pending until actually scanned,
unless all 16 sources have actually been cleared by the inherited controller.
"""
from __future__ import annotations

from functools import lru_cache
import itertools
import math

import numpy as np

from problem3.geometry import distance, polygon_centroid
from problem4.speed_policy import SearchPolicy as BasePolicy


@lru_cache(maxsize=8)
def geometric_patterns(stations, radial_count=8, angular_count=32):
    """Return grouped visible-station masks, weights and location centroids.

    Positions are equal-area circular quadrature (not case sources). Radius
    uses a three-point quadrature. For each node and radius, split the entire
    orientation circle at all station visibility boundaries: every open arc
    has a constant station mask, and its angular length is integrated exactly.
    Omni/directional model weights are equal. No sampled node certifies cover.
    """
    if not stations or len(stations) > 60:
        raise ValueError('Geometry ranking requires between 1 and 60 stations')
    grouped = {}
    total_positions = radial_count * angular_count

    def add(mask, weight, source):
        row = grouped.setdefault(mask, [0., 0., 0.])
        row[0] += weight
        row[1] += weight * source[0]
        row[2] += weight * source[1]

    for ring in range(radial_count):
        radius = 1800. * math.sqrt((ring + .5) / radial_count)
        for angle_index in range(angular_count):
            angle = math.tau * (angle_index + .5 * (ring % 2)) / angular_count
            source = (radius * math.cos(angle), radius * math.sin(angle))
            for reception_radius, rw in ((1000., 1/6), (1250., 2/3), (1500., 1/6)):
                active = [(index, p[0] - source[0], p[1] - source[1])
                          for index, p in enumerate(stations) if distance(p, source) <= reception_radius]
                omnidirectional = sum(1 << index for index, _, _ in active)
                weight = .5 * rw / total_positions
                add(omnidirectional, weight, source)
                endpoints = {0., math.tau}
                for _, dx, dy in active:
                    bearing = math.atan2(dy, dx)
                    endpoints.add((bearing - math.pi/2) % math.tau)
                    endpoints.add((bearing + math.pi/2) % math.tau)
                endpoints = sorted(endpoints)
                for lo, hi in zip(endpoints, endpoints[1:]):
                    if hi - lo <= 1e-13:
                        continue
                    phi = (lo + hi) / 2
                    vx, vy = math.cos(phi), math.sin(phi)
                    mask = sum(1 << index for index, dx, dy in active if vx * dx + vy * dy >= 0)
                    add(mask, weight * (hi - lo) / math.tau, source)
    keys = sorted(grouped)
    patterns = np.array(keys, dtype=np.uint64)
    weights = np.array([grouped[k][0] for k in keys], dtype=float)
    centers = np.array([(grouped[k][1] / grouped[k][0], grouped[k][2] / grouped[k][0])
                        for k in keys], dtype=float)
    weights /= weights.sum()
    patterns.flags.writeable = weights.flags.writeable = centers.flags.writeable = False
    return patterns, weights, centers


def remaining_count(known_count, unseen_fraction):
    """Heuristic conditional count under uniform N=10,...,16; never a stop."""
    if known_count >= 16:
        return 0.
    if not 0 <= known_count <= 16:
        raise ValueError('Invalid publicly known channel count')
    u = max(1e-12, min(1. - 1e-12, unseen_fraction))
    p = 1. - u
    values = []
    for n in range(max(10, known_count), 17):
        logweight = (math.lgamma(n + 1) - math.lgamma(known_count + 1) -
                     math.lgamma(n - known_count + 1) + known_count * math.log(p) +
                     (n - known_count) * math.log(u))
        values.append((n - known_count, logweight))
    maximum = max(v for _, v in values)
    weighted = [(n, math.exp(v - maximum)) for n, v in values]
    return sum(n * w for n, w in weighted) / sum(w for _, w in weighted)


def local_orders(length, prefix=4, insertion_reach=8):
    """Bounded scan/clear permutations; every original action appears once."""
    base = tuple(range(length))
    count = min(length, prefix)
    seen = set()
    for initial in itertools.permutations(range(count)):
        candidate = initial + base[count:]
        if candidate not in seen:
            seen.add(candidate)
            yield candidate
    for index in range(count, min(length, insertion_reach)):
        candidate = (index,) + base[:index] + base[index+1:]
        if candidate not in seen:
            seen.add(candidate)
            yield candidate


class DiscoveryRouteMixin:
    discovery_mode = 'scan_savings'
    discovery_prefix = 4
    discovery_insertion_reach = 8
    discovery_radial_count = 8
    discovery_angular_count = 32

    def coverage_points(self):
        points = super().coverage_points()
        self._discovery_stations = tuple(tuple(point) for point in points)
        self._discovery_station_ids = {point: index for index, point in enumerate(self._discovery_stations)}
        return points

    def _discovery_context(self):
        if not hasattr(self, '_discovery_stations'):
            return None
        if any(tuple(p) not in self._discovery_station_ids for p in self.coverage_visited):
            return None  # Optional ranking cannot silently misrepresent new scan locations.
        patterns, weights, centers = geometric_patterns(self._discovery_stations,
            self.discovery_radial_count, self.discovery_angular_count)
        scanned = sum(1 << self._discovery_station_ids[p] for p in set(map(tuple, self.coverage_visited)))
        unseen = (patterns & np.uint64(scanned)) == 0
        unseen_mass = float(weights[unseen].sum())
        if unseen_mass < 1e-12:
            return None  # Return original routing, never claim completion.
        known = len(set(self.regions) | self.cleared)
        missing = remaining_count(known, unseen_mass)
        self.stats['discovery_geometry_patterns'] = len(patterns)
        return patterns, weights, centers, unseen, unseen_mass, known, missing

    def _discovery_score(self, ordered, client, context):
        patterns, weights, centers, unseen, unseen_mass, known, missing = context
        points = np.asarray([g[0] for g in ordered], dtype=float)
        path = np.vstack((np.asarray(client.position), points))
        movement = float(np.sqrt(np.sum(np.diff(path, axis=0)**2, axis=1)).sum())
        score = movement / 5.
        pending = unseen.copy()
        found = 0.
        if self.discovery_mode == 'service_detour':
            dist = np.sqrt(np.sum((points[:, None, :] - centers[None, :, :])**2, axis=2))
            # Earliest legal insertion is after the actual revealing scan.
            suffix = [None] * len(ordered)
            suffix[-1] = dist[-1].copy()  # Free final end, no compulsory return.
            for index in range(len(ordered) - 2, -1, -1):
                edge = distance(ordered[index][0], ordered[index+1][0])
                insertion = np.maximum(0., dist[index] + dist[index+1] - edge)
                suffix[index] = np.minimum(suffix[index+1], insertion)
        for index, (point, kind, _) in enumerate(ordered):
            if kind != 'scan':
                continue
            # Absent channels remain in the count; source hypotheses only
            # discount channels predicted to have been newly discovered.
            score += 6. * max(0., 20. - known - found)
            bit = np.uint64(1 << self._discovery_station_ids[tuple(point)])
            discovered = pending & ((patterns & bit) != 0)
            if not np.any(discovered):
                continue
            probability_mass = float(weights[discovered].sum()) / unseen_mass
            if self.discovery_mode == 'service_detour':
                score += missing * float((weights[discovered] * suffix[index][discovered]).sum()) / unseen_mass / 5.
            found += missing * probability_mass
            pending[discovered] = False
        return score

    def _route_goal(self, client, pending):
        original = super()._route_goal(client, pending)
        if self.discovery_mode == 'off' or len(set(self.regions) | self.cleared) >= 16:
            return original
        if len(pending) < 2:
            return original
        context = self._discovery_context()
        if context is None:
            return original
        goals = [(p, 'scan', i) for i, p in enumerate(pending)]
        goals += [(polygon_centroid(poly), 'clear', ch) for ch, poly in self.regions.items()
                  if ch not in self.cleared]
        mapping = {self._goal_key(goal): goal for goal in goals}
        route = [mapping[key] for key in self._route_keys if key in mapping]
        if len(route) != len(goals):
            return original
        best_route = route
        best_score = self._discovery_score(route, client, context)
        for order in local_orders(len(route), self.discovery_prefix, self.discovery_insertion_reach):
            candidate = [route[index] for index in order]
            score = self._discovery_score(candidate, client, context)
            if score < best_score - .01:
                best_score, best_route = score, candidate
        self.stats['discovery_reranks'] = self.stats.get('discovery_reranks', 0) + 1
        if self._goal_key(best_route[0]) != self._goal_key(original):
            self.stats['discovery_first_changed'] = self.stats.get('discovery_first_changed', 0) + 1
        self._route_keys = [self._goal_key(goal) for goal in best_route]
        return best_route[0]

    def _result(self, reason, coverage_complete):
        result = super()._result(reason, coverage_complete)
        result['discovery_model_ranking_only'] = True
        result['effective_settings'].update(discovery_mode=self.discovery_mode,
            discovery_prefix=self.discovery_prefix, discovery_insertion_reach=self.discovery_insertion_reach,
            discovery_radial_count=self.discovery_radial_count, discovery_angular_count=self.discovery_angular_count)
        return result


class SearchPolicy(DiscoveryRouteMixin, BasePolicy):
    algorithm_version = 'problem4_v5_discovery_route'

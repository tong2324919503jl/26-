"""Development experiment: replan all interior scans around future clear stops.

Future source estimates are exact *planned scan coordinates*, not declarations
that a source actually occupies that point. Every replaced pending set gets a
finite directional certificate. If the eventual clear location differs, the
planned scan remains mandatory until a new certificate removes it.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from problem3.geometry import distance, polygon_centroid
from problem4.policy import SearchPolicy
from problem4.routing import insertion_seed, nearest_seed, route_length, two_opt
from problem4.experiments.adaptive_coverage import AdaptiveCoverageMixin


class FutureCoverPolicy(SearchPolicy):
    future_scan_weight = 1.0
    future_min_saving = 10.0
    future_replan_limit = 6

    _sample_is_blind = staticmethod(AdaptiveCoverageMixin._sample_is_blind)
    _certify_replacement = AdaptiveCoverageMixin._certify_replacement

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cover_cert_cache = {}
        self._cover_bad_locations = []
        self._future_last_known = None
        self._future_replans = 0

    def _future_cost(self, client, pending):
        goals = list(pending)
        goals += [polygon_centroid(polygon) for ch, polygon in self.regions.items()
                  if ch not in self.cleared]
        points = goals + [client.position]
        matrix = [[distance(a, b) for b in points] for a in points]
        routes = [two_opt(seed, matrix) for seed in
                  (nearest_seed(matrix), insertion_seed(matrix))]
        travel = min(route_length(route, matrix) for route in routes)
        unknown = 20 - len(set(self.regions) | self.cleared)
        return travel / 5 + 6 * unknown * len(pending) * self.future_scan_weight

    def _future_replan(self, client, pending):
        known = set(self.regions) | self.cleared
        if len(known) == 16 or len(known) < 3 or self._future_replans >= self.future_replan_limit:
            return
        state = (len(known), len(self.cleared) // 2)
        if state == self._future_last_known:
            return
        self._future_last_known = state
        removable = [point for point in pending if math.hypot(*point) < 1800]
        if len(removable) < 2:
            return
        extras = [polygon_centroid(polygon) for ch, polygon in self.regions.items()
                  if ch not in self.cleared]
        if self.cleared:
            extras.append(tuple(client.position))
        extras = [point for point in extras if math.hypot(*point) < 1750
                  and min((distance(point, p) for p in self.coverage_visited + pending), default=9999) > 80]
        if len(extras) < 2:
            return
        self._future_replans += 1
        before = self._future_cost(client, pending)
        proposal = pending + extras
        # Adding all proposed stops first permits cooperative replacement;
        # deleting one point from the original layout was too restrictive.
        removable.sort(key=lambda p: min(distance(p, q) for q in extras))
        original_removed = 0
        for point in removable:
            candidate = list(proposal)
            candidate.remove(point)
            if self._certify_replacement(client, self.coverage_visited + candidate):
                proposal = candidate
                original_removed += 1
        if not original_removed:
            return
        # Newly added stops with no remaining proof obligation are discarded.
        extras.sort(key=lambda p: self._future_cost(client, [q for q in proposal if q != p]))
        for point in extras:
            candidate = list(proposal)
            candidate.remove(point)
            if self._certify_replacement(client, self.coverage_visited + candidate):
                proposal = candidate
        after = self._future_cost(client, proposal)
        self.stats['future_cover_proposals'] = self.stats.get('future_cover_proposals', 0) + 1
        if before - after < self.future_min_saving:
            return
        pending[:] = proposal
        self.stats['future_cover_replans'] = self.stats.get('future_cover_replans', 0) + 1
        self.stats['future_cover_points_removed'] = self.stats.get('future_cover_points_removed', 0) + original_removed
        self.stats['future_cover_estimated_saving_s'] = self.stats.get('future_cover_estimated_saving_s', 0.0) + before - after

    def _route_goal(self, client, pending):
        self._future_replan(client, pending)
        return super()._route_goal(client, pending)


class TravelFutureCoverPolicy(FutureCoverPolicy):
    future_scan_weight = .4


if __name__ == '__main__':
    import argparse
    from problem4.experiments.compare import evaluate
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=('development', 'development_v2'), default='development_v2')
    parser.add_argument('--count', type=int, default=12)
    args = parser.parse_args()
    folder = ROOT / 'problem4' / 'results' / 'iterations_v3'
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / f'coverage_future_{args.split}_{args.count}.json'
    body = {}
    for cls in (SearchPolicy, FutureCoverPolicy, TravelFutureCoverPolicy):
        summary, rows = evaluate(cls, args.split, args.count)
        body[cls.__name__] = {'summary': summary, 'episodes': rows}
        output.write_text(json.dumps(body, indent=2) + '\n', encoding='utf-8')
        print(cls.__name__, json.dumps(summary), flush=True)

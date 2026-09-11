"""Development-only replacement of future scans by an already reached stop.

Every accepted replacement has a finite half-plane/Voronoi certificate over
the full scan set. Travel and information estimates select proposals only;
they never remove a scan without that certificate.
"""
from __future__ import annotations

import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from problem3.geometry import distance, polygon_centroid
from problem4.coverage import directional_cover_certificate
from problem4.experiments.routing import nearest_route
from problem4.experiments.combined import CoverRadiusInfo


class AdaptiveCoverageMixin:
    replacement_distance_m = 800.0
    replacement_min_saving_s = 10.0
    replacement_min_route_saving_m = 80.0
    replacement_candidates = 4
    replacement_allow_multiple = True
    replacement_information_cost = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cover_cert_cache = {}
        self._cover_bad_locations = []

    def _remaining_cost(self, client, pending, immediate_scan=False):
        goals = [(point, "scan", index) for index, point in enumerate(pending)]
        goals += [(polygon_centroid(polygon), "clear", channel) for channel, polygon in self.regions.items() if channel not in self.cleared]
        route = nearest_route(client.position, goals, 40)
        travel = sum(distance(client.position if i == 0 else route[i - 1][0], goal[0]) for i, goal in enumerate(route))
        unknown = 20 - len(set(self.regions) | self.cleared)
        if not self.replacement_information_cost or not hasattr(self, "scanned_mask"):
            return travel / 5 + 6 * unknown * (len(pending) + immediate_scan), travel
        total = len(self.samples)
        unseen = total - self.scanned_mask.bit_count()
        if unseen == 0:
            return travel / 5 + 6 * unknown * (len(pending) + immediate_scan), travel
        posterior = .65 * unseen / (.35 * total + .65 * unseen)
        covered = self.scanned_mask
        reading = 0.0
        if immediate_scan:
            reading += 6 * unknown
            covered |= self._mask(client.position)
        for point, kind, _ in route:
            if kind == "scan":
                reading += 6 * unknown * ((1 - posterior) + posterior * (total - covered.bit_count()) / unseen)
                covered |= self._mask(point)
        return travel / 5 + self.info_weight * reading, travel

    @staticmethod
    def _sample_is_blind(points, source):
        if math.hypot(*source) > 1800:
            return False
        nearby = [point for point in points if distance(point, source) <= 1000]
        if any(distance(point, source) < 1e-8 for point in nearby):
            return False
        if len(nearby) < 2:
            return True
        angles = sorted(math.atan2(point[1] - source[1], point[0] - source[0]) for point in nearby)
        return max((angles[(i + 1) % len(angles)] - angles[i]) % math.tau for i in range(len(angles))) > math.pi + 1e-8

    def _certify_replacement(self, client, points):
        # Cache uses exact coordinates. Rounding must not promote a proof of a
        # nearby layout into a proof of the actual submitted scan locations.
        key = tuple(sorted(set(points)))
        if key in self._cover_cert_cache:
            self.stats["cover_certificate_cache_hits"] = self.stats.get("cover_certificate_cache_hits", 0) + 1
            return self._cover_cert_cache[key]
        if any(self._sample_is_blind(points, source) for source in self._cover_bad_locations):
            self.stats["cover_counterexample_rejections"] = self.stats.get("cover_counterexample_rejections", 0) + 1
            self._cover_cert_cache[key] = False
            return False
        client.check_budget()
        result = directional_cover_certificate(points)
        self.stats["cover_certificate_calls"] = self.stats.get("cover_certificate_calls", 0) + 1
        self.stats["cover_certificate_runtime_s"] = self.stats.get("cover_certificate_runtime_s", 0.0) + result.get("program_runtime_s", 0.0)
        certified = result["certified"]
        self._cover_cert_cache[key] = certified
        if not certified and result.get("witness") is not None:
            witness = result["witness"]
            self._cover_bad_locations.append(witness)
            # A Voronoi maximum may be a one-sided limit on a pair line.
            # Nearby real source points are rejection screens only.
            for dx, dy in ((.001, 0), (-.001, 0), (0, .001), (0, -.001)):
                self._cover_bad_locations.append((witness[0] + dx, witness[1] + dy))
            self._cover_bad_locations = self._cover_bad_locations[-60:]
        return certified

    def _opportunistic_replace(self, client, pending):
        if not pending or len(set(self.regions) | self.cleared) == 16:
            return
        point = client.position
        close = sorted((distance(point, candidate), i) for i, candidate in enumerate(pending) if distance(point, candidate) <= self.replacement_distance_m)
        if not close:
            return
        before, before_travel = self._remaining_cost(client, pending)
        proposals = []
        for _, index in close[:self.replacement_candidates]:
            remaining = pending[:index] + pending[index + 1:]
            after, after_travel = self._remaining_cost(client, remaining, immediate_scan=True)
            if before - after >= self.replacement_min_saving_s and before_travel - after_travel >= self.replacement_min_route_saving_m:
                proposals.append((before - after, index, remaining))
        if not proposals:
            return
        for savings, index, remaining in sorted(proposals, reverse=True):
            if not self._certify_replacement(client, self.coverage_visited + remaining + [point]):
                continue
            removed = 1
            if self.replacement_allow_multiple:
                # Removing two points cannot repair a failed single deletion,
                # so multiple deletions are tried only after a certified one.
                for extra in sorted(range(len(remaining)), key=lambda i: distance(point, remaining[i]))[:self.replacement_candidates]:
                    candidate = remaining[:extra] + remaining[extra + 1:]
                    if self._certify_replacement(client, self.coverage_visited + candidate + [point]):
                        remaining = candidate
                        removed += 1
                        break
            # Change the pending set only after every unknown-channel scan has
            # actually succeeded. A rejected/interrupted action aborts normally.
            self._scan(client, point)
            pending[:] = remaining
            self.stats["replaced_scan_points"] = self.stats.get("replaced_scan_points", 0) + removed
            self.stats["replacement_scan_stops"] = self.stats.get("replacement_scan_stops", 0) + 1
            self.stats["replacement_estimated_saving_s"] = self.stats.get("replacement_estimated_saving_s", 0.0) + savings
            return

    def run(self, client):
        pending = self.coverage_points()
        while pending or any(channel not in self.cleared for channel in self.regions):
            client.check_budget()
            if len(self.cleared) == 16:
                return self._result("maximum_source_count_cleared", not pending)
            _, action, identifier = self._route_goal(client, pending)
            if action == "scan":
                self._scan(client, pending.pop(identifier))
            else:
                self._localize(identifier, client)
                self._opportunistic_replace(client, pending)
            self._update_neighbors(client)
            if len(self.cleared) == 16:
                return self._result("maximum_source_count_cleared", not pending)
        return self._result("certified_coverage_and_all_detected_cleared", True)


class AdaptiveCoverRadiusInfo(AdaptiveCoverageMixin, CoverRadiusInfo):
    pass


class AggressiveAdaptiveCoverRadiusInfo(AdaptiveCoverRadiusInfo):
    replacement_distance_m = 1100.0
    replacement_min_saving_s = 0.0
    replacement_min_route_saving_m = 0.0
    replacement_candidates = 6


class TravelAdaptiveCoverRadiusInfo(AdaptiveCoverRadiusInfo):
    replacement_information_cost = False


if __name__ == "__main__":
    import argparse
    import json
    from problem4.experiments.compare import evaluate

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("development", "development_v2"), default="development_v2")
    parser.add_argument("--count", type=int, default=48)
    args = parser.parse_args()
    output_directory = ROOT / "problem4" / "results" / "iterations_v2"
    output_directory.mkdir(parents=True, exist_ok=True)
    output = output_directory / f"adaptive_coverage_{args.split}_{args.count}.json"
    body = {}
    for cls in (CoverRadiusInfo, AdaptiveCoverRadiusInfo, AggressiveAdaptiveCoverRadiusInfo, TravelAdaptiveCoverRadiusInfo):
        summary, rows = evaluate(cls, args.split, args.count)
        body[cls.__name__] = {"summary": summary, "episodes": rows}
        output.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        print(cls.__name__, json.dumps(summary), flush=True)

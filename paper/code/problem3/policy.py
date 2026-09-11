"""Black-box search, bounded-error localization and optical clearance policy.

The client contract deliberately exposes no source positions, count, receiver
radii or emission directions.  run() never enters or exits the official arena.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from problem3.geometry import (Point, Polygon, certified_covering_radius, distance, enclosing_circle,
    initial_region, intersect_bearing, optical_cover, polygon_centroid)


@dataclass
class PolicyConfig:
    ring_radius: float = 1150.0
    bearing_error_deg: float = 1.005
    max_probe_count: int = 5
    lateral_fraction: float = 0.12
    lateral_min_m: float = 45.0
    lateral_max_m: float = 140.0
    opportunistic_radius_m: float = 0.0
    optical_spacing_m: float = 26.0
    clear_guarantee_radius_m: float = 19.99
    exploratory_clear_radius_m: float = 55.0
    neighbor_updates: bool = True
    neighbor_max_distance_m: float = 1450.0
    neighbor_min_parallax_deg: float = 12.0
    adaptive_discovery: bool = False
    discovery_min_spacing_m: float = 700.0
    discovery_replacement_only: bool = True
    target_uncertainty_weight: float = 0.5


class SearchPolicy:
    """Seven-point certified omnidirectional search with adaptive goal visits.

    Override coverage_points() for a different certified discovery design.
    Negative readings do not shrink source polygons, making localization safe
    to reuse for a 180-degree directional emitter in problem 4.
    """
    def __init__(self, problem: int = 3, strategy: str = "adaptive", config=None):
        if strategy not in ("adaptive", "baseline", "optical"):
            raise ValueError("strategy must be adaptive, baseline, or optical")
        self.problem = problem
        self.strategy = strategy
        self.config = config if isinstance(config, PolicyConfig) else PolicyConfig(**(config or {}))
        if self.config.bearing_error_deg < 1.005:
            raise ValueError("Official two-decimal bearings require at least 1.005 degrees")
        if not 0 < self.config.clear_guarantee_radius_m < 20:
            raise ValueError("Clear guarantee radius must lie below 20 metres")
        self.regions: dict[int, Polygon] = {}
        self.observations: dict[int, list[tuple[Point, float]]] = {}
        self.cleared: set[int] = set()
        self.coverage_visited: list[Point] = []
        self.stats = {"measure_actions": 0, "clear_actions": 0,
                      "failed_clears": 0, "optical_fallbacks": 0,
                      "negative_localization_reads": 0}

    def coverage_points(self) -> list[Point]:
        radius = self.config.ring_radius
        # Closed analytical certificate for the center-plus-six-ring design.
        outer = math.sqrt(1800**2 + radius**2 - 2 * 1800 * radius * math.cos(math.pi / 6))
        if radius / math.sqrt(3) > 1000 or outer > 1000:
            raise ValueError("The chosen ring radius does not certify 1000m coverage")
        return [(0.0, 0.0)] + [(radius * math.cos(k * math.pi / 3),
                               radius * math.sin(k * math.pi / 3)) for k in range(6)]

    def _clear(self, client, point: Point, channel: int) -> bool:
        client.check_budget()
        response = client.clear(point, channel)
        if response.get("accepted") is not True:
            raise RuntimeError("Clear action was not accepted")
        self.stats["clear_actions"] += 1
        if response.get("clear_result") == "success":
            self.cleared.add(channel)
            return True
        if response.get("clear_result") != "no_target_in_range":
            raise RuntimeError(f"Invalid clear response: {response!r}")
        self.stats["failed_clears"] += 1
        return False

    def _measure(self, client, point: Point, channel: int) -> str:
        client.check_budget()
        response = client.measure(point, channel)
        if response.get("accepted") is not True:
            raise RuntimeError("Measure action was not accepted")
        self.stats["measure_actions"] += 1
        result = response.get("measure_result")
        if result == "near":
            if not self._clear(client, point, channel):
                raise RuntimeError("A near reading was followed by a failed optical clear")
        elif result == "direction":
            angle = float(response["svd_deg"])
            previous = self.regions.get(channel, initial_region())
            updated = intersect_bearing(previous, point, angle,
                                        error_deg=self.config.bearing_error_deg)
            if not updated:
                raise RuntimeError("Bearing intersection is empty: model/protocol inconsistency")
            self.regions[channel] = updated
            self.observations.setdefault(channel, []).append((point, angle))
        elif result != "no_signal":
            raise RuntimeError(f"Invalid measurement response: {response!r}")
        return result

    def _scan(self, client, point: Point) -> None:
        unknown = [ch for ch in range(1, 21) if ch not in self.regions and ch not in self.cleared]
        if client.current_channel in unknown:
            unknown.remove(client.current_channel)
            unknown.insert(0, client.current_channel)
        for channel in unknown:
            self._measure(client, point, channel)
        self.coverage_visited.append(point)

    def _update_neighbors(self, client) -> None:
        """Collect useful second bearings at a stop already paid for."""
        if self.strategy != "adaptive" or not self.config.neighbor_updates:
            return
        point = client.position
        for channel in list(self.regions):
            if channel in self.cleared:
                continue
            polygon = self.regions[channel]
            center, radius = enclosing_circle(polygon)
            if radius < 35 or distance(point, center) > self.config.neighbor_max_distance_m:
                continue
            origin, _ = self.observations[channel][-1]
            a = (origin[0] - center[0], origin[1] - center[1])
            b = (point[0] - center[0], point[1] - center[1])
            denominator = math.hypot(*a) * math.hypot(*b)
            sine = abs(a[0] * b[1] - a[1] * b[0]) / denominator if denominator else 0
            if sine >= math.sin(math.radians(self.config.neighbor_min_parallax_deg)):
                self._measure(client, point, channel)

    def _probe_point(self, channel: int, client, probe_index: int) -> Point:
        polygon = self.regions[channel]
        center = polygon_centroid(polygon)
        origin, bearing = self.observations[channel][-1]
        theta = math.radians(bearing)
        perpendicular = (-math.sin(theta), math.cos(theta))
        if self.strategy == "baseline" and len(self.observations[channel]) == 1:
            return (origin[0] + 200 * perpendicular[0], origin[1] + 200 * perpendicular[1])
        # Move towards the source while creating parallax.  An estimate drives
        # movement only: correctness comes from retained sectors and fallback.
        _, radius = enclosing_circle(polygon)
        if len(self.observations[channel]) > 1 and radius < 100:
            return center
        lateral = min(self.config.lateral_max_m, max(self.config.lateral_min_m,
                      distance(origin, center) * self.config.lateral_fraction))
        if probe_index % 2:
            lateral = -lateral
        return (center[0] + lateral * perpendicular[0],
                center[1] + lateral * perpendicular[1])

    def _localize(self, channel: int, client) -> bool:
        attempted_measure: set[tuple[float, float]] = set()
        attempted_clear: list[Point] = []
        if self.strategy != "optical":
            for probe_index in range(self.config.max_probe_count):
                polygon = self.regions[channel]
                center, radius = enclosing_circle(polygon)
                if radius <= self.config.clear_guarantee_radius_m:
                    if self._clear(client, center, channel):
                        return True
                    # Retain the region; unexpected failure must not certify success.
                    attempted_clear.append(center)
                elif radius <= self.config.exploratory_clear_radius_m and not attempted_clear:
                    if self._clear(client, polygon_centroid(polygon), channel):
                        return True
                    attempted_clear.append(polygon_centroid(polygon))
                point = self._probe_point(channel, client, probe_index)
                key = tuple(round(value, 6) for value in point)
                if key in attempted_measure:
                    break
                attempted_measure.add(key)
                result = self._measure(client, point, channel)
                if channel in self.cleared:
                    return True
                if result == "no_signal":
                    self.stats["negative_localization_reads"] += 1
                # Fixed error at one point: never average repeated readings.
        self.stats["optical_fallbacks"] += 1
        points = optical_cover(self.regions[channel], self.config.optical_spacing_m)
        # Nearest-neighbour ordering changes cost only, never the finite cover.
        while points:
            index = min(range(len(points)), key=lambda i: distance(client.position, points[i]))
            if self._clear(client, points.pop(index), channel):
                return True
        raise RuntimeError("Optical cover exhausted without clearance: model/protocol inconsistency")

    def run(self, client) -> dict:
        pending = self.coverage_points()
        while pending or any(channel not in self.cleared for channel in self.regions):
            client.check_budget()
            known = [channel for channel in self.regions if channel not in self.cleared]
            def target_cost(ch):
                return distance(client.position, polygon_centroid(self.regions[ch])) + self.config.target_uncertainty_weight * enclosing_circle(self.regions[ch])[1]
            channel = min(known, key=target_cost) if known else None
            waypoint_index = min(range(len(pending)), key=lambda i: distance(client.position, pending[i])) if pending else None
            visit_target = channel is not None and (waypoint_index is None or self.strategy != "baseline" and
                target_cost(channel) <=
                distance(client.position, pending[waypoint_index]) + 180)
            if visit_target:
                self._localize(channel, client)
                if self.problem == 3 and self.strategy == "adaptive" and self.config.adaptive_discovery:
                    if self.config.discovery_replacement_only:
                        for index in sorted(range(len(pending)), key=lambda i: distance(client.position, pending[i])):
                            replacement = self.coverage_visited + pending[:index] + pending[index + 1:] + [client.position]
                            if certified_covering_radius(replacement) <= 1000:
                                self._scan(client, client.position)
                                pending.pop(index)
                                break
                    elif not self.coverage_visited or min(distance(client.position, point) for point in self.coverage_visited) >= self.config.discovery_min_spacing_m:
                        self._scan(client, client.position)
                    # Remove only waypoints made redundant by actual full scans.
                    for index in reversed(range(len(pending))):
                        remaining = self.coverage_visited + pending[:index] + pending[index + 1:]
                        if certified_covering_radius(remaining) <= 1000:
                            pending.pop(index)
            elif waypoint_index is not None:
                self._scan(client, pending.pop(waypoint_index))
            else:
                self._localize(channel, client)
            self._update_neighbors(client)
            # Known upper count permits an earlier proof of completion.
            if len(self.cleared) == 16:
                return self._result("maximum_source_count_cleared", not pending)
        return self._result("certified_coverage_and_all_detected_cleared", True)

    def _result(self, reason: str, complete: bool) -> dict:
        return {"problem": self.problem, "strategy": self.strategy,
                "cleared_channels": sorted(self.cleared), "coverage_complete": complete,
                "completion_certified": complete or len(self.cleared) == 16,
                "termination_reason": reason, "coverage_points_visited": len(self.coverage_visited),
                "detected_channels": sorted(set(self.regions) | self.cleared),
                "config": asdict(self.config), **self.stats}

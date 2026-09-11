"""Mixed omnidirectional/directional search with a finite coverage certificate.

Only the public robot client is used.  In particular, source count, positions,
receive radii and transmitting directions are never read from the client.
"""
from __future__ import annotations

import math

from problem3.policy import SearchPolicy as OmnidirectionalPolicy
from problem3.geometry import clip_halfplane, distance, enclosing_circle, polygon_centroid

Point = tuple[float, float]
Triangle = tuple[Point, Point, Point]


def _cross(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segment_distance(point: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    denominator = dx * dx + dy * dy
    t = 0.0 if denominator == 0 else max(0.0, min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / denominator))
    return math.hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy)


def triangle_contains(triangle: Triangle, point: Point, tolerance: float = 1e-7) -> bool:
    """Inclusive test; tolerance has square-metre units."""
    cross = [_cross(triangle[i], triangle[(i + 1) % 3], point) for i in range(3)]
    return min(cross) >= -tolerance or max(cross) <= tolerance


def _triangle_intersects_disk(triangle: Triangle, radius: float) -> bool:
    if triangle_contains(triangle, (0.0, 0.0)):
        return True
    return any(_segment_distance((0.0, 0.0), triangle[i], triangle[(i + 1) % 3]) <= radius + 1e-8 for i in range(3))


def covering_triangles(radius: float = 1800.0, spacing: float = 990.0) -> list[Triangle]:
    """All triangles of the equilateral tiling that meet the target disk.

    Each such triangle has diameter ``spacing < 1000``.  A source in the
    triangle is therefore within reception distance of all its vertices.
    Since it is in their convex hull, every closed half-plane through the
    source contains at least one vertex.  This handles every unknown beam
    orientation, including sources on the target boundary radiating outward.
    """
    if not math.isfinite(radius) or radius <= 0:
        raise ValueError("radius must be positive and finite")
    if not math.isfinite(spacing) or not 0 < spacing < 1000:
        raise ValueError("directional coverage requires 0 < spacing < 1000")
    height = spacing * math.sqrt(3.0) / 2.0
    bound = math.ceil(2.0 * (radius + spacing) / spacing) + 2

    def vertex(i: int, j: int) -> Point:
        return (spacing * (i + j / 2.0), height * j)

    result = []
    for j in range(-bound, bound + 1):
        for i in range(-bound, bound + 1):
            lower = (vertex(i, j), vertex(i + 1, j), vertex(i, j + 1))
            upper = (vertex(i + 1, j + 1), vertex(i, j + 1), vertex(i + 1, j))
            for triangle in (lower, upper):
                if _triangle_intersects_disk(triangle, radius):
                    result.append(triangle)
    return result


def directional_coverage_points(radius: float = 1800.0, spacing: float = 990.0) -> list[Point]:
    """Return a deterministic finite set, starting at the initial position."""
    vertices = {vertex for triangle in covering_triangles(radius, spacing) for vertex in triangle}
    # The base policy decides the visit order.  This sorted form also provides
    # a reproducible serpentine baseline when fixed ordering is requested.
    height = spacing * math.sqrt(3.0) / 2.0
    points = sorted(vertices, key=lambda p: (round(p[1] / height), p[0] if round(p[1] / height) % 2 == 0 else -p[0]))
    origin = (0.0, 0.0)
    points.remove(origin)
    return [origin, *points]


def polar_covering_triangles() -> list[Triangle]:
    """A 25-vertex triangulated polygon containing the entire target disk.

    The outer dodecagon has inradius 1870*cos(15 degrees) > 1800.  Every
    triangle edge is at most 983.599 m, so the same convex-hull certificate
    applies with fewer search stops than the regular triangular tiling.
    """
    outer = [(1870 * math.cos(i * math.tau / 12), 1870 * math.sin(i * math.tau / 12)) for i in range(12)]
    inner = [(950 * math.cos((i + .5) * math.tau / 12), 950 * math.sin((i + .5) * math.tau / 12)) for i in range(12)]
    triangles = []
    for i in range(12):
        nxt = (i + 1) % 12
        triangles.append(((0.0, 0.0), inner[i], inner[nxt]))
        triangles.append((inner[i], outer[i], outer[nxt]))
        triangles.append((inner[i], outer[nxt], inner[nxt]))
    return triangles


def polar_coverage_points() -> list[Point]:
    vertices = {vertex for triangle in polar_covering_triangles() for vertex in triangle}
    return sorted(vertices, key=lambda p: (round(math.hypot(*p), 5), math.atan2(p[1], p[0])))


class SearchPolicy(OmnidirectionalPolicy):
    """Q4 reuses bounded-bearing localization with a stronger global cover."""

    route_refinements = 40

    def __init__(self, problem: int = 4, strategy: str = "adaptive", config=None):
        if problem != 4:
            raise ValueError("problem4.SearchPolicy requires problem=4")
        self._directional_strategy = strategy
        super().__init__(problem=problem, strategy=strategy, config=config)

    def coverage_points(self) -> list[Point]:
        return directional_coverage_points() if self._directional_strategy == "baseline" else polar_coverage_points()

    def _route_goal(self, client, pending):
        goals = [(point, "scan", index) for index, point in enumerate(pending)]
        goals += [(polygon_centroid(polygon), "clear", channel) for channel, polygon in self.regions.items() if channel not in self.cleared]
        route = []
        origin = client.position
        while goals:
            index = min(range(len(goals)), key=lambda i: distance(origin, goals[i][0]))
            goal = goals.pop(index)
            route.append(goal)
            origin = goal[0]
        for _ in range(self.route_refinements):
            changed = False
            for i in range(len(route) - 1):
                a = client.position if i == 0 else route[i - 1][0]
                b = route[i][0]
                for j in range(i + 1, len(route)):
                    c = route[j][0]
                    d = route[j + 1][0] if j + 1 < len(route) else None
                    old = distance(a, b) + (distance(c, d) if d is not None else 0)
                    new = distance(a, c) + (distance(b, d) if d is not None else 0)
                    if new + .01 < old:
                        route[i:j + 1] = reversed(route[i:j + 1])
                        changed = True
                        break
                if changed:
                    break
            if not changed:
                break
        return route[0]

    def run(self, client) -> dict:
        if self.strategy != "adaptive":
            return super().run(client)
        pending = self.coverage_points()
        while pending or any(channel not in self.cleared for channel in self.regions):
            client.check_budget()
            _, action, identifier = self._route_goal(client, pending)
            if action == "scan":
                self._scan(client, pending.pop(identifier))
            else:
                self._localize(identifier, client)
            self._update_neighbors(client)
            if len(self.cleared) == 16:
                return self._result("maximum_source_count_cleared", not pending)
        return self._result("certified_coverage_and_all_detected_cleared", True)

    def _localize(self, channel: int, client) -> bool:
        if self.strategy != "adaptive":
            return super()._localize(channel, client)
        attempted_clear = False
        attempted_measure = set()
        # Paired transverse probes handle the unknown beam side.  A single
        # negative result never removes a reception disk from the source set.
        for _ in range(5):
            polygon = self.regions[channel]
            center, radius = enclosing_circle(polygon)
            if radius <= self.config.clear_guarantee_radius_m:
                if self._clear(client, center, channel):
                    return True
            elif radius <= self.config.exploratory_clear_radius_m and not attempted_clear:
                attempted_clear = True
                if self._clear(client, polygon_centroid(polygon), channel):
                    return True
            anchor, bearing = self.observations[channel][-1]
            theta = math.radians(bearing)
            forward = (math.cos(theta), math.sin(theta))
            sideways = (-forward[1], forward[0])
            longitudinal = [(point[0] - anchor[0]) * forward[0] + (point[1] - anchor[1]) * forward[1] for point in polygon]
            step = (min(longitudinal) + max(longitudinal)) / 2
            width = max(35.0, min(140.0, .18 * step))
            width = max(width, step * math.tan(math.radians(self.config.bearing_error_deg)) + .01)
            midpoint = (anchor[0] + step * forward[0], anchor[1] + step * forward[1])
            probes = [(midpoint[0] + sign * width * sideways[0], midpoint[1] + sign * width * sideways[1]) for sign in (-1, 1)]
            probes.sort(key=lambda point: distance(client.position, point))
            all_in_range = all(distance(point, vertex) < 999.999 for point in probes for vertex in polygon)
            negative = 0
            for point in probes:
                key = (round(point[0], 7), round(point[1], 7))
                if key in attempted_measure:
                    continue
                attempted_measure.add(key)
                result = self._measure(client, point, channel)
                self.stats["paired_probe_actions"] = self.stats.get("paired_probe_actions", 0) + 1
                if channel in self.cleared:
                    return True
                if result == "direction":
                    break
                negative += 1
                self.stats["negative_localization_reads"] += 1
            if negative == 2 and all_in_range and step > 0:
                # Every feasible source beyond this cross-section has a point
                # of its anchor-to-source segment between the two probes.
                # That segment stays inside its closed emitting half-plane.
                # Two absent signals therefore certify that the source lies
                # before the cross-section, because distance was ruled out.
                constant = step + anchor[0] * forward[0] + anchor[1] * forward[1]
                updated = clip_halfplane(polygon, forward[0], forward[1], constant)
                if not updated:
                    raise RuntimeError("Paired negative observations contradict the feasible source set")
                self.regions[channel] = updated
                self.stats["paired_negative_clips"] = self.stats.get("paired_negative_clips", 0) + 1
        # Reuse the complete optical cell cover, without restarting radio
        # probes.  The ordinary fallback never relies on emission direction.
        from problem3.geometry import optical_cover
        self.stats["optical_fallbacks"] += 1
        points = optical_cover(self.regions[channel], self.config.optical_spacing_m)
        while points:
            index = min(range(len(points)), key=lambda i: distance(client.position, points[i]))
            if self._clear(client, points.pop(index), channel):
                return True
        raise RuntimeError("Optical cover exhausted without clearance: model/protocol inconsistency")

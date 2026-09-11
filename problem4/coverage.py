"""Finite directional-coverage certificates, using only the standard library.

For a hypothetical source g, let N(g) be the observation points within 1000 m.
Every closed emission half-plane through g contains a point of N(g) exactly
when g is in conv(N(g)). If not, a supporting pair line separates g from N(g).
For every oriented observation-point pair, we therefore cover the target disk
on the left with reception disks centred strictly on the left of that line.

The 0/1/2-neighbour cases also have a separating pair: with one neighbour a,
choose a second observation off the line ag; with collinear neighbours and g
beyond their segment, use the endpoint nearest g and any off-line observation.
For no neighbours use any noncollinear pair. The full observation hull must
strictly contain the target disk, so such off-line observations exist. A source
coinciding with its sole nearby observation is already in the neighbour hull.

Each pair check is ordinary disk coverage on a circular segment. Clip every
eligible site's Voronoi cell by that segment. The maximum distance on the cell
is attained at a vertex, an edge/circle intersection, or a farthest point of a
circular arc; all are enumerated. A sample grid is never used for acceptance.
Numerical clipping is outward and acceptance requires a separate metre margin.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import time

Point = tuple[float, float]

# Frozen after geometric optimization, independently certified again after
# rounding to six decimals. These constants never depend on simulator cases.
STATIC23_POINTS: tuple[Point, ...] = (
    (0.000000, 0.000000),
    (1864.500000, 0.000000),
    (1614.704365, 932.250000),
    (932.250000, 1614.704365),
    (0.000000, 1864.500000),
    (-932.250000, 1614.704365),
    (-1614.704365, 932.250000),
    (-1864.500000, 0.000000),
    (-1614.704365, -932.250000),
    (-932.250000, -1614.704365),
    (0.000000, -1864.500000),
    (932.250000, -1614.704365),
    (1614.704365, -932.250000),
    (1076.467178, 0.001385),
    (673.445446, 707.456053),
    (35.090167, 1039.476106),
    (-652.783202, 727.398374),
    (-1076.469577, 0.000000),
    (-804.167008, -363.249827),
    (-538.234788, -932.250000),
    (93.843216, -877.978803),
    (538.234788, -932.250000),
    (955.618224, -253.126730),
)


def static_coverage_points() -> list[Point]:
    return list(STATIC23_POINTS)


def legacy_coverage_points() -> list[Point]:
    return [(0.0, 0.0)] + [(950 * math.cos((i + .5) * math.tau / 12), 950 * math.sin((i + .5) * math.tau / 12)) for i in range(12)] + [(1870 * math.cos(i * math.tau / 12), 1870 * math.sin(i * math.tau / 12)) for i in range(12)]


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def convex_hull(points):
    points = sorted(set(points))
    if len(points) <= 1:
        return points
    lower, upper = [], []
    for point in points:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in reversed(points):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _clip(polygon, nx, ny, offset):
    if not polygon:
        return []
    norm = math.hypot(nx, ny)
    if norm == 0:
        return polygon if offset >= 0 else []
    nx, ny, offset = nx / norm, ny / norm, offset / norm + 1e-8
    answer = []
    a = polygon[-1]
    fa = nx * a[0] + ny * a[1] - offset
    for b in polygon:
        fb = nx * b[0] + ny * b[1] - offset
        if (fa <= 0) != (fb <= 0):
            t = fa / (fa - fb)
            answer.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
        if fb <= 0:
            answer.append(b)
        a, fa = b, fb
    return answer


def _contains(polygon, point):
    return bool(polygon) and all(_cross(a, b, point) >= -1e-6 * max(1.0, math.dist(a, b)) for a, b in zip(polygon, polygon[1:] + polygon[:1]))


def _disk_intersection_extrema(polygon, site, radius):
    candidates = [p for p in polygon if math.hypot(*p) <= radius + 1e-7]
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length2 = dx * dx + dy * dy
        if length2 < 1e-16:
            continue
        midpoint_t = -(a[0] * dx + a[1] * dy) / length2
        foot = (a[0] + midpoint_t * dx, a[1] + midpoint_t * dy)
        radial2 = radius * radius - foot[0] * foot[0] - foot[1] * foot[1]
        if radial2 < -1e-6:
            continue
        half_t = math.sqrt(max(0.0, radial2) / length2)
        for t in (midpoint_t - half_t, midpoint_t + half_t):
            if -1e-9 <= t <= 1 + 1e-9:
                candidates.append((a[0] + t * dx, a[1] + t * dy))
    norm = math.hypot(*site)
    far = (-radius * site[0] / norm, -radius * site[1] / norm) if norm else (radius, 0.0)
    if _contains(polygon, far):
        candidates.append(far)
    return candidates


def segment_cover_radius(sites, normal, offset, radius=1800.0, full_report=False):
    """Analytic maximum nearest-site distance on disk intersect n*x>=offset."""
    nx, ny = normal
    norm = math.hypot(nx, ny)
    if norm == 0:
        raise ValueError("A circular-segment normal must be nonzero")
    if norm * radius < offset - 1e-7:
        return {"radius_bound_m": 0.0, "witness": None, "cells": []}
    if not sites:
        return {"radius_bound_m": math.inf, "witness": (radius * nx / norm, radius * ny / norm), "cells": []}
    box = [(-radius, -radius), (radius, -radius), (radius, radius), (-radius, radius)]
    segment = _clip(box, -nx, -ny, -offset)
    worst, witness, cells = 0.0, None, []
    for site_index, site in enumerate(sites):
        cell = segment
        for other in sites:
            if other == site:
                continue
            nx2, ny2 = other[0] - site[0], other[1] - site[1]
            # Difference of squared norms as a dot product avoids cancellation
            # for nearly coincident sites and keeps reversed constraints
            # exactly antisymmetric before normalization. Otherwise two cells
            # can develop a numerical gap and omit part of the target disk.
            bound = (nx2 * (other[0] + site[0]) + ny2 * (other[1] + site[1])) / 2
            cell = _clip(cell, nx2, ny2, bound)
            if not cell:
                break
        candidates = _disk_intersection_extrema(cell, site, radius)
        if not candidates:
            continue
        point = max(candidates, key=lambda p: math.dist(p, site))
        value = math.dist(point, site)
        if value > worst:
            worst, witness = value, point
        if full_report:
            cells.append({"site_index": site_index, "radius_bound_m": value, "witness": point})
    return {"radius_bound_m": worst, "witness": witness, "cells": cells}


def directional_cover_certificate(points, target_radius=1800.0, receive_radius=1000.0, margin_m=1e-3, full_report=False, early_exit=True):
    """Return a conservative finite coverage report; no SciPy is required."""
    started = time.perf_counter()
    points = [tuple(map(float, p)) for p in points]
    if any(len(p) != 2 or not all(math.isfinite(x) for x in p) for p in points):
        raise ValueError("Coverage points must be finite coordinate pairs")
    if not all(math.isfinite(x) and x > 0 for x in (target_radius, receive_radius, margin_m)) or margin_m < 1e-4:
        raise ValueError("Radii must be positive; numerical margin must be at least 1e-4 m")
    fingerprint = hashlib.sha256(json.dumps(points, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    base = {"point_count": len(points), "points_sha256": fingerprint, "target_radius_m": target_radius,
            "receive_radius_m": receive_radius, "numerical_margin_m": margin_m}
    hull = convex_hull(points)
    if len(hull) < 3:
        return {**base, "certified": False, "reason": "degenerate_observation_hull"}
    hull_inradius = min((a[0] * b[1] - a[1] * b[0]) / math.dist(a, b) for a, b in zip(hull, hull[1:] + hull[:1]))
    if hull_inradius < target_radius + margin_m:
        return {**base, "certified": False, "reason": "target_disk_not_strictly_inside_hull", "hull_inradius_m": hull_inradius}
    worst, witness, worst_pair, checked, rows = 0.0, None, None, 0, []
    for i, j in itertools.permutations(range(len(points)), 2):
        a, b = points[i], points[j]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length == 0:
            continue
        normal = (-dy / length, dx / length)
        offset = normal[0] * a[0] + normal[1] * a[1]
        if offset >= target_radius:
            continue
        indices = [k for k, point in enumerate(points) if normal[0] * point[0] + normal[1] * point[1] > offset + 1e-7]
        result = segment_cover_radius([points[k] for k in indices], normal, offset, target_radius, full_report)
        value, point = result["radius_bound_m"], result["witness"]
        checked += 1
        if value > worst:
            worst, witness, worst_pair = value, point, [i, j]
        if full_report:
            rows.append({"pair": [i, j], "left_normal": normal, "line_offset": offset, "eligible_indices": indices, **result})
        if early_exit and worst >= receive_radius - margin_m:
            break
    answer = {**base, "certified": worst < receive_radius - margin_m,
              "hull_inradius_m": hull_inradius, "max_directional_radius_bound_m": worst,
              "witness": witness, "pair": worst_pair, "pair_checks": checked,
              "program_runtime_s": time.perf_counter() - started}
    if full_report:
        answer["points"] = points
        answer["pair_details"] = rows
    return answer

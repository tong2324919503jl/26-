"""Conservative floating-point geometry shared by problems 3 and 4.

All disks used for intersection are OUTER regular polygons.  Optical decisions
use an actual enclosing radius, never half of the polygon diameter.
"""
from __future__ import annotations

import math
import random

Point = tuple[float, float]
Polygon = list[Point]
GEOMETRY_MARGIN_M = 1e-6


def distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def clip_halfplane(polygon: Polygon, a: float, b: float, c: float) -> Polygon:
    """Clip by a*x+b*y <= c, with a small outward numerical margin."""
    if not polygon:
        return []
    c += GEOMETRY_MARGIN_M * math.hypot(a, b)
    output: Polygon = []
    previous = polygon[-1]
    fp = a * previous[0] + b * previous[1] - c
    for current in polygon:
        fc = a * current[0] + b * current[1] - c
        if (fc <= 0) != (fp <= 0):
            t = fp / (fp - fc)
            output.append((previous[0] + t * (current[0] - previous[0]),
                           previous[1] + t * (current[1] - previous[1])))
        if fc <= 0:
            output.append(current)
        previous, fp = current, fc
    return output


def initial_region(radius: float = 1800.0, sides: int = 96) -> Polygon:
    outer = radius / math.cos(math.pi / sides) + GEOMETRY_MARGIN_M
    return [(outer * math.cos((2 * k + 1) * math.pi / sides),
             outer * math.sin((2 * k + 1) * math.pi / sides)) for k in range(sides)]


def intersect_bearing(polygon: Polygon, point: Point, bearing: float,
                      error_deg: float = 1.005, receive_radius: float = 1500.0,
                      disk_sides: int = 48) -> Polygon:
    """Intersect an angular sector and a containing disk; retain true source."""
    result = list(polygon)
    low, high = map(math.radians, (bearing - error_deg, bearing + error_deg))
    # cross(low, x-point) >= 0; cross(high, x-point) <= 0.
    for a, b in ((math.sin(low), -math.cos(low)),
                 (-math.sin(high), math.cos(high))):
        result = clip_halfplane(result, a, b, a * point[0] + b * point[1])
    for k in range(disk_sides):
        angle = 2 * math.pi * k / disk_sides
        a, b = math.cos(angle), math.sin(angle)
        result = clip_halfplane(result, a, b, receive_radius + a * point[0] + b * point[1])
    return result


def polygon_centroid(polygon: Polygon) -> Point:
    if not polygon:
        raise ValueError("Empty feasible polygon")
    area2 = sx = sy = 0.0
    for p, q in zip(polygon, polygon[1:] + polygon[:1]):
        cross = p[0] * q[1] - q[0] * p[1]
        area2 += cross
        sx += (p[0] + q[0]) * cross
        sy += (p[1] + q[1]) * cross
    if abs(area2) < 1e-8:
        return (sum(p[0] for p in polygon) / len(polygon),
                sum(p[1] for p in polygon) / len(polygon))
    return sx / (3 * area2), sy / (3 * area2)


def _circle_three(a: Point, b: Point, c: Point):
    bx, by, cx, cy = b[0] - a[0], b[1] - a[1], c[0] - a[0], c[1] - a[1]
    determinant = 2 * (bx * cy - by * cx)
    if abs(determinant) < 1e-12:
        return None
    b2, c2 = bx * bx + by * by, cx * cx + cy * cy
    center = (a[0] + (cy * b2 - by * c2) / determinant,
              a[1] + (bx * c2 - cx * b2) / determinant)
    return center, distance(center, a)


def enclosing_circle(polygon: Polygon) -> tuple[Point, float]:
    """Randomized incremental minimum enclosing circle, verified outwards.

    The fixed shuffle makes experiments reproducible.  The final radius is
    recomputed against ALL vertices; any rounding can only loosen the bound.
    """
    if not polygon:
        raise ValueError("Empty feasible polygon")
    points = list(polygon)
    random.Random(20260911).shuffle(points)
    center, radius = points[0], 0.0
    for i, a in enumerate(points):
        if distance(center, a) <= radius + 1e-9:
            continue
        center, radius = a, 0.0
        for j, b in enumerate(points[:i]):
            if distance(center, b) <= radius + 1e-9:
                continue
            center = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            radius = distance(a, b) / 2
            for c in points[:j]:
                if distance(center, c) <= radius + 1e-9:
                    continue
                circle = _circle_three(a, b, c)
                if circle is not None:
                    center, radius = circle
    radius = max(distance(center, p) for p in polygon) + GEOMETRY_MARGIN_M
    return center, radius


def contains(polygon: Polygon, point: Point, tolerance: float = 1e-5) -> bool:
    if not polygon:
        return False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        cross = (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])
        if cross < -tolerance * max(1.0, distance(a, b)):
            return False
    return True


def optical_cover(polygon: Polygon, spacing: float = 26.0) -> list[Point]:
    """Finite 20m optical cover: rotated square cells, side <= 20*sqrt(2).

    Every cell intersecting the feasible polygon contributes its center, even
    when the center lies outside the polygon.  Omitting such boundary centers
    would invalidate coverage.  Rotation follows the longest polygon chord.
    """
    if not 0 < spacing <= 20 * math.sqrt(2) - 1e-3:
        raise ValueError("Optical square spacing must safely fit in radius 20")
    if not polygon:
        raise ValueError("Cannot cover an empty region")
    a, b = max(((a, b) for a in polygon for b in polygon),
               key=lambda pair: distance(*pair))
    chord = distance(a, b)
    ux, uy = ((b[0] - a[0]) / chord, (b[1] - a[1]) / chord) if chord else (1.0, 0.0)
    rotated = [(p[0] * ux + p[1] * uy, -p[0] * uy + p[1] * ux) for p in polygon]
    min_x, max_x = min(p[0] for p in rotated), max(p[0] for p in rotated)
    min_y, max_y = min(p[1] for p in rotated), max(p[1] for p in rotated)
    answer = []
    for ix in range(math.floor(min_x / spacing), math.floor(max_x / spacing) + 1):
        rows = range(math.floor(min_y / spacing), math.floor(max_y / spacing) + 1)
        if ix % 2:
            rows = reversed(rows)
        for iy in rows:
            cell = rotated
            for aa, bb, cc in ((1, 0, (ix + 1) * spacing), (-1, 0, -ix * spacing),
                               (0, 1, (iy + 1) * spacing), (0, -1, -iy * spacing)):
                cell = clip_halfplane(cell, aa, bb, cc)
            if cell:
                x, y = (ix + .5) * spacing, (iy + .5) * spacing
                answer.append((x * ux - y * uy, x * uy + y * ux))
    return answer


def certified_covering_radius(points: list[Point], radius: float = 1800.0) -> float:
    """Upper-bound distance from the target disk to its nearest scan point.

    Clip an outer target polygon into nearest-site Voronoi cells.  Euclidean
    distance to the cell's site is convex, hence its maximum over the polygon
    occurs at a vertex.  An upper bound <=1000 certifies omnidirectional cover.
    """
    if not points:
        return math.inf
    maximum = 0.0
    for point in points:
        cell = initial_region(radius)
        for other in points:
            if other == point:
                continue
            a, b = 2 * (other[0] - point[0]), 2 * (other[1] - point[1])
            c = other[0]**2 + other[1]**2 - point[0]**2 - point[1]**2
            cell = clip_halfplane(cell, a, b, c)
        if cell:
            maximum = max(maximum, max(distance(point, vertex) for vertex in cell))
    return maximum + GEOMETRY_MARGIN_M

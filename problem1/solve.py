"""Intersect bearing sectors, compute diameter, and test disk coverage.

Run from the repository: python -m problem1.solve
Run from anywhere: python /absolute/path/to/problem1/solve.py --demo

Only the Python standard library is required. Geometry predicates, intersections,
and circle comparisons use exact fractions of the supplied floating coefficients.
Trigonometric coefficients themselves have normal machine precision.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
import html
import itertools
import json
import math
from pathlib import Path
from typing import Iterable, Sequence


HERE = Path(__file__).resolve().parent
Number = int | float | Fraction
Point = tuple[Fraction, Fraction]


def rational(value: Number) -> Fraction:
    """Accept finite real numbers; booleans are not measurements."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Fraction)):
        raise ValueError(f"Expected a finite real number, got {value!r}")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("All coordinates and coefficients must be finite")
    return Fraction(value)


@dataclass(frozen=True)
class Measurement:
    x: float
    y: float
    bearing_deg: float
    error_deg: float = 1.0

    def __post_init__(self) -> None:
        for value in (self.x, self.y, self.bearing_deg, self.error_deg):
            rational(value)
        if not 0 <= self.error_deg < 90:
            raise ValueError("error_deg must be in [0, 90); the official value is 1")


@dataclass(frozen=True)
class HalfPlane:
    """Closed half-plane a*x + b*y <= c, with exact rational coefficients."""

    a: Number
    b: Number
    c: Number

    def __post_init__(self) -> None:
        for name in ("a", "b", "c"):
            object.__setattr__(self, name, rational(getattr(self, name)))

    def contains(self, point: Point) -> bool:
        return self.a * point[0] + self.b * point[1] <= self.c


def direction(angle_deg: float) -> Point:
    """Angle is counterclockwise from +x; exact cardinal axes avoid sin(pi)."""
    angle = float(angle_deg) % 360.0
    cardinal = {
        0.0: (1, 0), 90.0: (0, 1), 180.0: (-1, 0), 270.0: (0, -1)
    }
    if angle in cardinal:
        return tuple(Fraction(v) for v in cardinal[angle])  # type: ignore[return-value]
    # Reduce around the nearest cardinal axis, so theta and theta+180 use
    # exactly opposite stored coefficients and 359/1-degree rays are symmetric.
    quadrant = int((angle + 45.0) // 90.0)
    rad = math.radians(angle - 90.0 * quadrant)
    cosine, sine = Fraction(math.cos(rad)), Fraction(math.sin(rad))
    return ((cosine, sine), (-sine, cosine), (-cosine, -sine),
            (sine, -cosine))[quadrant % 4]


def bearing_halfplanes(measurements: Iterable[Measurement]) -> list[HalfPlane]:
    result = []
    for measurement in measurements:
        x, y = rational(measurement.x), rational(measurement.y)
        theta = float(measurement.bearing_deg) % 360.0
        lo = direction(theta - measurement.error_deg)
        hi = direction(theta + measurement.error_deg)
        forward = direction(theta)
        # cross(lo, X-S) >= 0; cross(hi, X-S) <= 0.
        # The forward constraint is redundant for 0 < error < 90 degrees;
        # it ensures an error-zero measurement is a ray instead of a full line.
        for a, b in ((lo[1], -lo[0]), (-hi[1], hi[0]),
                     (-forward[0], -forward[1])):
            result.append(HalfPlane(a, b, a * x + b * y))
    return result


def cross(a: Point, b: Point, c: Point) -> Fraction:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def distance_squared(a: Point, b: Point) -> Fraction:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def convex_hull(points: Iterable[Point]) -> list[Point]:
    """Counterclockwise hull with redundant collinear points removed."""
    points = sorted(set(points))
    if len(points) <= 1:
        return points
    lower: list[Point] = []
    upper: list[Point] = []
    for point in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def diameter_squared_bruteforce(points: Sequence[Point]) -> tuple[Fraction, tuple[Point, Point]]:
    """Independent O(k^2) reference for checking the rotating-calipers result."""
    if not points:
        raise ValueError("The empty set has no chosen diameter")
    best = Fraction(0)
    pair = (points[0], points[0])
    for first, second in itertools.combinations(points, 2):
        squared = distance_squared(first, second)
        candidate = tuple(sorted((first, second)))
        if squared > best or (squared == best and candidate < pair):
            best, pair = squared, candidate
    return best, pair


def diameter_squared_calipers(polygon: Sequence[Point]) -> tuple[Fraction, tuple[Point, Point]]:
    """Exact O(k) diameter on a CCW convex hull without redundant collinear points.

    Adapted from the teammate's antipodal-pair approach, retaining exact rational
    comparisons. Equal support areas mean parallel supporting edges: consider
    both endpoints, rather than dropping a possible farthest pair.
    """
    if len(polygon) <= 2:
        return diameter_squared_bruteforce(polygon)
    count = len(polygon)
    opposite = 1
    best = Fraction(0)
    pair = (polygon[0], polygon[0])

    def consider(first_index: int, second_index: int) -> None:
        nonlocal best, pair
        first, second = polygon[first_index], polygon[second_index]
        squared = distance_squared(first, second)
        candidate = tuple(sorted((first, second)))
        if squared > best or (squared == best and candidate < pair):
            best, pair = squared, candidate

    for index in range(count):
        next_index = (index + 1) % count

        def area(other: int) -> Fraction:
            return cross(polygon[index], polygon[next_index], polygon[other])

        while area((opposite + 1) % count) > area(opposite):
            opposite = (opposite + 1) % count
        consider(index, opposite)
        consider(next_index, opposite)
        if area((opposite + 1) % count) == area(opposite):
            consider(index, (opposite + 1) % count)
            consider(next_index, (opposite + 1) % count)
    return best, pair


def polygon_area(polygon: Sequence[Point]) -> Fraction:
    """Exact area; a point and a segment have zero area."""
    if len(polygon) < 3:
        return Fraction(0)
    origin = polygon[0]
    return abs(sum((cross(origin, polygon[index], polygon[index + 1])
                    for index in range(1, len(polygon) - 1)), Fraction(0))) / 2


def intersection_vertices(planes: Sequence[HalfPlane]) -> list[Point]:
    vertices: set[Point] = set()
    for first, second in itertools.combinations(planes, 2):
        det = first.a * second.b - second.a * first.b
        if det == 0:
            continue
        point = ((first.c * second.b - second.c * first.b) / det,
                 (first.a * second.c - second.a * first.c) / det)
        if all(plane.contains(point) for plane in planes):
            vertices.add(point)
    return convex_hull(vertices)


def feasible_witness(planes: Sequence[HalfPlane], vertices: Sequence[Point]) -> Point | None:
    """No artificial box: test vertices, origin, and boundary projections.

    A nonempty closed convex polyhedron has a nearest point to the origin.
    It is the origin, lies on a single supporting line as its projection, or
    has two linearly independent active boundaries and hence is a vertex.
    """
    if vertices:
        return vertices[0]
    zero = (Fraction(0), Fraction(0))
    if all(plane.contains(zero) for plane in planes):
        return zero
    for plane in planes:
        norm_squared = plane.a ** 2 + plane.b ** 2
        if norm_squared == 0:
            continue
        point = (plane.a * plane.c / norm_squared, plane.b * plane.c / norm_squared)
        if all(other.contains(point) for other in planes):
            return point
    return None


def recession_direction(planes: Sequence[HalfPlane]) -> Point | None:
    """Find d != 0 with A*d <= 0, iff a nonempty region is unbounded."""
    nonzero = [plane for plane in planes if plane.a != 0 or plane.b != 0]
    if not nonzero:
        return Fraction(1), Fraction(0)
    for plane in nonzero:
        for point in ((-plane.b, plane.a), (plane.b, -plane.a)):
            if all(other.a * point[0] + other.b * point[1] <= 0 for other in nonzero):
                return point
    return None


@dataclass(frozen=True)
class Circle:
    center: Point
    radius_squared: Fraction
    support: tuple[Point, ...]

    def contains(self, point: Point) -> bool:
        return distance_squared(self.center, point) <= self.radius_squared


def pair_circle(first: Point, second: Point) -> Circle:
    center = ((first[0] + second[0]) / 2, (first[1] + second[1]) / 2)
    return Circle(center, distance_squared(first, second) / 4, (first, second))


def triple_circle(first: Point, second: Point, third: Point) -> Circle | None:
    # Work relative to the first point; the rational computation is exact.
    ux, uy = second[0] - first[0], second[1] - first[1]
    vx, vy = third[0] - first[0], third[1] - first[1]
    det = 2 * (ux * vy - uy * vx)
    if det == 0:
        return None
    uu, vv = ux * ux + uy * uy, vx * vx + vy * vy
    center = (first[0] + (uu * vy - vv * uy) / det,
              first[1] + (ux * vv - vx * uu) / det)
    return Circle(center, distance_squared(center, first), (first, second, third))


def minimum_enclosing_circle(points: Sequence[Point]) -> Circle:
    """Enumerate all 1/2/3-point support circles; exact and deterministic.

    O(k^4) arithmetic operations in the worst case. Intended for the small
    vertex counts produced by a few bearing measurements, not large point clouds.
    """
    if not points:
        raise ValueError("The empty set has no chosen enclosing circle")
    if len(points) == 1:
        return Circle(points[0], Fraction(0), (points[0],))
    best: Circle | None = None
    for first, second in itertools.combinations(points, 2):
        circle = pair_circle(first, second)
        if (best is None or circle.radius_squared < best.radius_squared) and all(
                circle.contains(point) for point in points):
            best = circle
    for first, second, third in itertools.combinations(points, 3):
        circle = triple_circle(first, second, third)
        if circle is not None and (best is None or circle.radius_squared < best.radius_squared):
            if all(circle.contains(point) for point in points):
                best = circle
    if best is None:
        raise ArithmeticError("No enclosing support circle found")
    return best


def float_point(point: Point) -> list[float]:
    return [float(point[0]), float(point[1])]


def circle_record(circle: Circle) -> dict:
    radius = math.sqrt(float(circle.radius_squared))
    return {"center": float_point(circle.center), "radius_m": radius,
            "diameter_m": 2 * radius,
            "support_points": [float_point(point) for point in circle.support]}


def analyze_halfplanes(halfplanes: Iterable[HalfPlane]) -> dict:
    """Public general half-plane API, also used for degenerate-case verification."""
    planes = list(halfplanes)
    vertices = intersection_vertices(planes)
    witness = feasible_witness(planes, vertices)
    result = {
        "status": "empty", "vertices": [float_point(point) for point in vertices],
        "feasible_point": None if witness is None else float_point(witness),
        "diameter_m": None, "diameter_endpoints": None,
        "diameter_circle": None, "diameter_circle_covers": None,
        "minimum_enclosing_circle": None,
        "area_m2": None, "max_distance_from_diameter_center_m": None,
        "optical_localization": None,
    }
    if witness is None:
        result["reason"] = "The closed bearing constraints have no common point."
        return result
    ray = recession_direction(planes)
    if ray is not None:
        # Keep the direction small in the serialized output; scaling is positive.
        scale = max(abs(ray[0]), abs(ray[1]))
        result.update(status="unbounded", diameter_is_infinite=True,
                      recession_direction=float_point((ray[0] / scale, ray[1] / scale)),
                      reason="A nonzero direction d satisfies A*d <= 0; no finite diameter exists.")
        return result
    if not vertices:
        raise ArithmeticError("A nonempty bounded polyhedron must have a vertex")
    result["status"] = "point" if len(vertices) == 1 else "segment" if len(vertices) == 2 else "polygon"
    maximum_squared, (first, second) = diameter_squared_calipers(vertices)
    diameter_circle = pair_circle(first, second)
    minimum_circle = minimum_enclosing_circle(vertices)
    covers = all(diameter_circle.contains(point) for point in vertices)
    assert covers == (minimum_circle.radius_squared <= maximum_squared / 4)
    result.update(
        diameter_m=math.sqrt(float(maximum_squared)),
        diameter_endpoints=[float_point(first), float_point(second)],
        diameter_circle={**circle_record(diameter_circle), "covers_region": covers},
        diameter_circle_covers=covers,
        minimum_enclosing_circle=circle_record(minimum_circle),
        area_m2=float(polygon_area(vertices)),
        max_distance_from_diameter_center_m=math.sqrt(float(max(
            distance_squared(diameter_circle.center, point) for point in vertices))),
        optical_localization={
            "radius_m": 20.0,
            "guaranteed_from_enclosing_center": minimum_circle.radius_squared <= 400,
            "radius_margin_m": 20.0 - math.sqrt(float(minimum_circle.radius_squared)),
            "diameter_only_sufficient": maximum_squared <= 1200,
            "diameter_only_necessary": maximum_squared <= 1600,
            "scope": "Geometric coverage of the angular region; no travel or simulator action implied.",
        },
    )
    return result


def localize(measurements: Iterable[Measurement]) -> dict:
    measurements = list(measurements)
    result = analyze_halfplanes(bearing_halfplanes(measurements))
    result["measurement_count"] = len(measurements)
    result["model"] = "Closed angular sectors only; no range or target-disk clipping."
    result["angle_convention"] = "Degrees counterclockwise from the positive x-axis."
    return result


def load_measurements(path: Path) -> tuple[dict, list[Measurement]]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict) or not isinstance(document.get("measurements"), list):
        raise ValueError("Input must be an object containing a measurements list")
    measurements = []
    for index, row in enumerate(document["measurements"]):
        if not isinstance(row, dict) or not {"x", "y", "bearing_deg"} <= row.keys():
            raise ValueError(f"Measurement {index} requires x, y, bearing_deg")
        measurements.append(Measurement(row["x"], row["y"], row["bearing_deg"], row.get("error_deg", 1.0)))
    return document, measurements


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_region_svg(path: Path, result: dict, title: str) -> None:
    """Write a standalone vector plot, focused on the localization region."""
    vertices = result["vertices"]
    circle = result["minimum_enclosing_circle"]
    if circle is None:
        return
    cx, cy = circle["center"]
    radius = max(circle["radius_m"], 0.5)
    width, height = 860, 660
    plot_size = 470
    scale = plot_size / (2.5 * radius)
    ox, oy = width / 2, 325

    def screen(point: list[float]) -> tuple[float, float]:
        return ox + (point[0] - cx) * scale, oy - (point[1] - cy) * scale

    coordinates = " ".join(f"{x:.5f},{y:.5f}" for x, y in map(screen, vertices))
    diameter = result["diameter_circle"]
    dx, dy = screen(diameter["center"])
    pieces = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="860" height="660" viewBox="0 0 860 660">',
        '<rect width="860" height="660" fill="#f6f8fc"/>',
        '<g font-family="Arial, sans-serif" fill="#172b4d">',
        f'<text x="42" y="43" font-size="23" font-weight="700">{html.escape(title)}</text>',
        '<text x="42" y="72" font-size="14">Self-created example; coordinates in metres</text>',
        f'<circle cx="{ox}" cy="{oy}" r="{circle["radius_m"] * scale}" fill="none" stroke="#187c6c" stroke-width="2.5"/>',
        f'<circle cx="{dx}" cy="{dy}" r="{diameter["radius_m"] * scale}" fill="none" stroke="#df7524" stroke-width="2" stroke-dasharray="7 5"/>',
        f'<polygon points="{coordinates}" fill="#467fe633" stroke="#315a9c" stroke-width="2.5"/>',
    ]
    for index, vertex in enumerate(vertices):
        x, y = screen(vertex)
        pieces.append(f'<circle cx="{x}" cy="{y}" r="4" fill="#315a9c"/>')
        pieces.append(f'<text x="{x + 9}" y="{y - 10}" font-size="14">V{index + 1}</text>')
    values = [
        f'Region diameter D = {result["diameter_m"]:.6f} m',
        f'Minimum covering radius R = {circle["radius_m"]:.6f} m',
        f'Diameter-D disk covers region: {str(result["diameter_circle_covers"]).upper()}',
    ]
    pieces.extend(f'<text x="42" y="{555 + index * 25}" font-size="16">{value}</text>' for index, value in enumerate(values))
    pieces.extend([
        '<line x1="480" y1="557" x2="520" y2="557" stroke="#187c6c" stroke-width="3"/>',
        '<text x="532" y="562" font-size="14">Minimum covering circle</text>',
        '<line x1="480" y1="588" x2="520" y2="588" stroke="#df7524" stroke-width="3" stroke-dasharray="7 5"/>',
        '<text x="532" y="593" font-size="14">Circle with diameter D</text>',
        '</g></svg>',
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(pieces) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="JSON input; relative paths are resolved against problem1/")
    parser.add_argument("--output", type=Path, help="JSON output; relative paths are resolved against problem1/")
    parser.add_argument("--demo", action="store_true", help="Run all self-created examples (also the default)")
    args = parser.parse_args()
    if args.demo and args.input:
        parser.error("Choose --demo or --input, not both")
    if args.output and not args.input:
        parser.error("--output requires --input")
    paths = [args.input if args.input.is_absolute() else HERE / args.input] if args.input else sorted((HERE / "examples").glob("*.json"))
    for path in paths:
        document, measurements = load_measurements(path)
        result = localize(measurements)
        result["example_name"] = document.get("name", path.stem)
        result["data_origin"] = document.get("data_origin", "User-supplied input; no official benchmark implied.")
        output = (args.output if args.output.is_absolute() else HERE / args.output) if args.output else HERE / "results" / f"{path.stem}.result.json"
        write_json(output, result)
        write_region_svg(output.with_suffix(".svg"), result, document.get("plot_title", path.stem))
        print(f'{path.name}: status={result["status"]}, diameter={result["diameter_m"]}, covers={result["diameter_circle_covers"]}')
        print(f"  {output}")


if __name__ == "__main__":
    main()

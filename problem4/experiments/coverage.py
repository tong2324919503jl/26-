"""Static directional-coverage experiments; never reads simulator case truth.

The finite certificate checks every pair-supported half-plane.  Each check is
a usual disk-covering problem on a circular segment, solved by clipped Voronoi
cells, their edge/circle intersections, and circle-arc extrema.  Dense samples
are useful counterexample screens only and are never accepted as a proof.

Run from any directory: python <this file> --layout polar --certificate
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))

Point = tuple[float, float]

# Geometry-only development record. No simulator holdout/stress cases were
# opened or used. These search failures are not lower bounds on point count.
EXPERIMENT_RECORD = {
    "fixed_outer_radius_m": 1864.5,
    "fixed_outer_count": 12,
    "randomized_short_edge_search": [
        {"total_points": 22, "seeds": "0..99", "certified_layouts": 0},
        {"total_points": 23, "seeds": "0..99", "certified_layouts": 0},
        {"total_points": 24, "seeds": "0..99", "certified_layouts": 7,
         "successful_seeds": [8, 24, 37, 40, 46, 83, 99]},
    ],
    "successful_reduction": {"seed": 8, "removed_zero_based_index": 16,
                             "remaining_points": 23, "radius_bound_m": 984.418184105},
    "further_reduction": {"removed_inner_points_tried": 10, "random_seeds_each": 60,
                          "certified_22_point_layouts": 0},
    "open_route_heuristic_m": {"legacy_25": 17990.731819, "static_23": 17889.192456,
                               "coordinate_optimized_23": 17627.127253},
    "route_optimized_radius_bound_m": 999.884192822,
    "selection": "Keep the 984.418m static23 layout; route-only savings are small and the tighter candidate has less geometric margin.",
}


def clip(polygon, nx, ny, offset):
    """Clip nx*x+ny*y <= offset with a tiny outward length margin."""
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


def contains(polygon, p, tolerance=1e-6):
    return bool(polygon) and all((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -tolerance * max(1.0, math.dist(a, b)) for a, b in zip(polygon, polygon[1:] + polygon[:1]))


def circle_clip_extrema(polygon, site, radius):
    """Candidates for max |x-site| over polygon intersect the target disk."""
    candidates = [p for p in polygon if math.hypot(*p) <= radius + 1e-7]
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        aa, bb, cc = dx * dx + dy * dy, 2 * (a[0] * dx + a[1] * dy), a[0] * a[0] + a[1] * a[1] - radius * radius
        disc = bb * bb - 4 * aa * cc
        if aa < 1e-16 or disc < -1e-6:
            continue
        root = math.sqrt(max(0.0, disc))
        for t in ((-bb - root) / (2 * aa), (-bb + root) / (2 * aa)):
            if -1e-9 <= t <= 1 + 1e-9:
                candidates.append((a[0] + t * dx, a[1] + t * dy))
    norm = math.hypot(*site)
    far = (-radius * site[0] / norm, -radius * site[1] / norm) if norm else (radius, 0.0)
    if contains(polygon, far):
        candidates.append(far)
    return candidates


def segment_cover_radius(sites, normal, offset, radius=1800.0):
    """Largest distance to the nearest site on disk intersect n*x>=offset.

    On each clipped Voronoi cell the nearest site is fixed. A convex quadratic
    reaches its maximum at a polygon vertex, an edge/circle intersection, or
    the farthest point of a circular boundary arc. These are all enumerated.
    """
    nx, ny = normal
    norm = math.hypot(nx, ny)
    if norm * radius < offset - 1e-7:
        return 0.0, None
    if not sites:
        return math.inf, (radius * nx / norm, radius * ny / norm)
    box = [(-radius, -radius), (radius, -radius), (radius, radius), (-radius, radius)]
    segment = clip(box, -nx, -ny, -offset)
    worst, witness = 0.0, None
    for site in sites:
        cell = segment
        for other in sites:
            if other == site:
                continue
            ax, ay = other[0] - site[0], other[1] - site[1]
            bound = (other[0] ** 2 + other[1] ** 2 - site[0] ** 2 - site[1] ** 2) / 2
            cell = clip(cell, ax, ay, bound)
            if not cell:
                break
        for point in circle_clip_extrema(cell, site, radius):
            value = math.dist(point, site)
            if value > worst:
                worst, witness = value, point
    return worst, witness


def halfplane_certificate(points, target_radius=1800.0, receive_radius=1000.0, early_exit=True):
    """Finite sufficient certificate, substantially stronger than short edges.

    For each oriented pair line, the target disk on its left must be covered
    by reception disks of observation points strictly on its left. If a
    source lay outside the convex hull of its nearby observation points, a
    supporting edge of that hull would violate one of these checks. The same
    conclusion for 0/1/2 nearby points follows by a separating pair line; the
    initial convex-hull check rules out globally collinear degeneracies.

    The analytic maximum is computed in floating point; acceptance requires
    a 1e-4 metre margin rather than relying on a rounded equality.
    """
    from scipy.spatial import ConvexHull
    started = time.perf_counter()
    hull = ConvexHull(points)
    for nx, ny, offset in hull.equations:
        if target_radius * math.hypot(nx, ny) + offset >= -1e-4:
            return {"certified": False, "reason": "target_disk_not_strictly_inside_hull"}
    worst, witness, worst_pair, checked = 0.0, None, None, 0
    for i, j in itertools.permutations(range(len(points)), 2):
        a, b = points[i], points[j]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < 1e-6:
            continue
        normal = (-dy / length, dx / length)
        offset = normal[0] * a[0] + normal[1] * a[1]
        if offset >= target_radius:
            continue
        sites = [point for point in points if normal[0] * point[0] + normal[1] * point[1] > offset + 1e-7]
        value, point = segment_cover_radius(sites, normal, offset, target_radius)
        checked += 1
        if value > worst:
            worst, witness, worst_pair = value, point, [i, j]
        if early_exit and worst >= receive_radius - 1e-4:
            break
    return {"certified": worst < receive_radius - 1e-4,
            "max_directional_radius_bound_m": worst, "witness": witness,
            "pair": worst_pair, "pair_checks": checked,
            "program_runtime_s": time.perf_counter() - started}


def ring_layout(inner_count=12, outer_count=12, inner_radius=950.0, outer_radius=1870.0, inner_phase_deg=15.0, include_origin=True):
    points = [(0.0, 0.0)] if include_origin else []
    points += [(inner_radius * math.cos(math.radians(inner_phase_deg) + i * math.tau / inner_count), inner_radius * math.sin(math.radians(inner_phase_deg) + i * math.tau / inner_count)) for i in range(inner_count)]
    points += [(outer_radius * math.cos(i * math.tau / outer_count), outer_radius * math.sin(i * math.tau / outer_count)) for i in range(outer_count)]
    return points


def sample_counterexample(points, radial_steps=75, angular_steps=240, receive_radius=1000.0):
    """Cheap rejection screen; None means no sampled counterexample, not proof."""
    for radial_index in range(radial_steps + 1):
        radius = 1800.0 * radial_index / radial_steps
        for angular_index in range(angular_steps):
            theta = (angular_index + .1234567) * math.tau / angular_steps
            source = (radius * math.cos(theta), radius * math.sin(theta))
            angles = sorted(math.atan2(p[1] - source[1], p[0] - source[0]) for p in points if math.dist(p, source) <= receive_radius)
            if any(math.dist(p, source) < 1e-8 for p in points):
                continue
            if len(angles) < 2:
                return source
            largest_gap = max((angles[(i + 1) % len(angles)] - angles[i]) % math.tau for i in range(len(angles)))
            if largest_gap > math.pi + 1e-9:
                return source
    return None


def optimized_short_edge_layout(inner_count=11, outer_count=12, seed=0, outer_radius=1870.0, initial_points=None):
    """SOCP-shaped fixed-edge minmax optimization, with topology refresh.

    This is an experimental optimizer, not the runtime certificate. Returned
    layouts must independently pass the finite half-plane certificate.
    """
    import numpy as np
    from scipy.spatial import Delaunay
    from scipy.optimize import minimize
    rng = np.random.default_rng(seed)
    if initial_points is None:
        initial = ring_layout(inner_count, outer_count, outer_radius=outer_radius, inner_phase_deg=15.0)
        fixed = np.array([initial[0], *initial[1 + inner_count:]])
        movable = np.array(initial[1:1 + inner_count])
    else:
        fixed = np.array(initial_points[:outer_count + 1])
        movable = np.array(initial_points[outer_count + 1:])
    if seed:
        movable += rng.normal(size=movable.shape) * 140
    points = np.vstack([fixed, movable])
    nf = len(fixed)
    history = []
    for _ in range(6):
        triangles = Delaunay(points).simplices
        edges = np.array(sorted({tuple(sorted((int(t[i]), int(t[(i + 1) % 3])))) for t in triangles for i in range(3)}))
        ei, ej = edges.T

        def unpack(x):
            return np.vstack([fixed, x[:-1].reshape((-1, 2))])

        def constraint(x):
            p = unpack(x)
            return x[-1] - np.linalg.norm(p[ei] - p[ej], axis=1)

        def jacobian(x):
            p = unpack(x)
            delta = p[ei] - p[ej]
            delta /= np.maximum(np.linalg.norm(delta, axis=1)[:, None], 1e-10)
            jac = np.zeros((len(edges), len(x)))
            jac[:, -1] = 1
            for k, (i, j) in enumerate(edges):
                if i >= nf:
                    jac[k, 2 * (i - nf):2 * (i - nf) + 2] = -delta[k]
                if j >= nf:
                    jac[k, 2 * (j - nf):2 * (j - nf) + 2] = delta[k]
            return jac

        x = np.r_[points[nf:].flatten(), np.max(np.linalg.norm(points[ei] - points[ej], axis=1))]
        result = minimize(lambda x: x[-1], x, jac=lambda x: np.r_[np.zeros(len(x) - 1), 1], constraints=[{"type": "ineq", "fun": constraint, "jac": jacobian}], method="SLSQP", options={"maxiter": 300, "ftol": 1e-8})
        points = unpack(result.x)
        history.append({"max_edge_m": float(result.fun), "optimizer_success": bool(result.success)})
    return [tuple(map(float, p)) for p in points], history


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", choices=("polar", "optimized"), default="polar")
    parser.add_argument("--inner-count", type=int, default=12)
    parser.add_argument("--outer-count", type=int, default=12)
    parser.add_argument("--inner-radius", type=float, default=950)
    parser.add_argument("--outer-radius", type=float, default=1870)
    parser.add_argument("--inner-phase", type=float, default=15)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--certificate", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.layout == "optimized":
        points, history = optimized_short_edge_layout(args.inner_count, args.outer_count, args.seed, args.outer_radius)
    else:
        points, history = ring_layout(args.inner_count, args.outer_count, args.inner_radius, args.outer_radius, args.inner_phase), []
    output = {"point_count": len(points), "points": points, "optimization": history,
              "sample_counterexample": sample_counterexample(points)}
    if args.certificate:
        output["certificate"] = halfplane_certificate(points)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

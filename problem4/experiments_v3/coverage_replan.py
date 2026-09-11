"""Whole-interior certified cover replanning (development experiment only).

MILP proposes points using discrete source/heading constraints and a travel
surrogate. The proposal is accepted only by the finite analytic certificate;
its failed witnesses generate further constraints. No sampled coverage result
is treated as a proof. SciPy is an optimizer dependency of this experiment.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from problem4.coverage import directional_cover_certificate, static_coverage_points


def _beam_at_blind_source(points, source, radius=999.0):
    if math.hypot(*source) > 1800 + 1e-8:
        return None
    nearby = [point for point in points if math.dist(point, source) <= radius]
    if any(math.dist(point, source) < 1e-8 for point in nearby):
        return None
    if not nearby:
        return 0.0
    angles = sorted(math.atan2(point[1] - source[1], point[0] - source[0]) for point in nearby)
    gaps = [((angles[(i + 1) % len(angles)] - angles[i]) % math.tau, i) for i in range(len(angles))]
    if len(angles) == 1:
        return angles[0] + math.pi
    gap, index = max(gaps)
    return angles[index] + gap / 2 if gap > math.pi + 1e-9 else None


def actual_counterexample(points, report, radius=999.0):
    witness = report.get("witness")
    pair = report.get("pair")
    if witness is None or pair is None:
        return None
    a, b = (points[i] for i in pair)
    dx, dy = b[0] - a[0], b[1] - a[1]
    norm = math.hypot(dx, dy)
    normal = (-dy / norm, dx / norm)
    probes = [tuple(witness)]
    for step in (.001, .01, .1, 1.0, 3.0, 10.0):
        point = (witness[0] + step * normal[0], witness[1] + step * normal[1])
        length = math.hypot(*point)
        if length > 1800:
            point = (point[0] * (1800 - 1e-7) / length, point[1] * (1800 - 1e-7) / length)
        probes.append(point)
    for point in probes:
        angle = _beam_at_blind_source(points, point, radius)
        if angle is not None:
            return (point[0], point[1], angle)
    return None


def candidate_inner_points(previous=(), spacing=150, outer_count=None):
    points = {tuple(point) for point in previous}
    points.update(static_coverage_points()[13:])
    points.update((float(x), float(y)) for x in range(-1350, 1351, spacing)
                  for y in range(-1350, 1351, spacing) if math.hypot(x, y) <= 1400)
    if outer_count:
        for radius in (1450, 1600, 1750, 1790):
            for i in range(outer_count * 4):
                angle = i * math.tau / (outer_count * 4)
                points.add((radius * math.cos(angle), radius * math.sin(angle)))
    return sorted(points)


def source_heading_grid():
    states = []
    for radius in range(0, 1801, 200):
        angles = range(1) if radius == 0 else range(48)
        for index in angles:
            position_angle = (index + .123456) * math.tau / 48
            x, y = radius * math.cos(position_angle), radius * math.sin(position_angle)
            for beam in range(24):
                states.append((x, y, (beam + .23456) * math.tau / 24))
    return states


def _constraint_masks(fixed, candidates, states, radius=995.0):
    import numpy as np
    states = np.asarray(states, dtype=float)
    if not len(states):
        return []
    source = states[:, :2]
    normals = np.stack([np.cos(states[:, 2]), np.sin(states[:, 2])], axis=1)
    uncovered = np.ones(len(source), dtype=bool)
    for point in fixed:
        delta = np.asarray(point) - source
        covered = (np.sum(delta * delta, axis=1) <= radius ** 2) & (np.sum(delta * normals, axis=1) >= 0)
        uncovered &= ~covered
    source, normals = source[uncovered], normals[uncovered]
    masks = [0] * len(source)
    for i, point in enumerate(candidates):
        delta = np.asarray(point) - source
        covered = (np.sum(delta * delta, axis=1) <= radius ** 2) & (np.sum(delta * normals, axis=1) >= 0)
        for j in np.flatnonzero(covered):
            masks[j] |= 1 << i
    return sorted(set(masks), key=lambda mask: (mask.bit_count(), mask))


def _prune_redundant_masks(masks):
    retained = []
    for mask in sorted(set(masks), key=lambda m: (m.bit_count(), m)):
        if any(previous & mask == previous for previous in retained):
            continue
        retained.append(mask)
    return retained


def optimize_remaining_cover(fixed, candidates, costs=None, max_rounds=30, time_limit_s=2.0,
                             max_selected=10):
    """Return certified future inner points, or no accepted proposal."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import coo_matrix
    started = time.perf_counter()
    fixed, candidates = list(map(tuple, fixed)), list(map(tuple, candidates))
    costs = np.ones(len(candidates)) if costs is None else np.asarray(costs)
    masks = _constraint_masks(fixed, candidates, source_heading_grid())
    history = []
    for iteration in range(max_rounds):
        masks = _prune_redundant_masks(masks)
        if 0 in masks:
            return {"accepted": False, "reason": "candidate_pool_cannot_cover_witness", "history": history}
        row, column = [], []
        for i, mask in enumerate(masks):
            while mask:
                least = mask & -mask
                row.append(i)
                column.append(least.bit_length() - 1)
                mask ^= least
        row.extend([len(masks)] * len(candidates))
        column.extend(range(len(candidates)))
        matrix = coo_matrix((np.ones(len(row)), (row, column)), shape=(len(masks) + 1, len(candidates))).tocsc()
        solution = milp(costs, integrality=np.ones(len(candidates)), bounds=Bounds(0, 1),
                        constraints=LinearConstraint(matrix, np.r_[np.ones(len(masks)), 0],
                                                     np.r_[np.full(len(masks), np.inf), max_selected]),
                        options={"time_limit": time_limit_s, "mip_rel_gap": .005})
        if solution.x is None:
            return {"accepted": False, "reason": "optimizer_no_feasible_solution", "history": history,
                    "optimizer_message": solution.message}
        selected = [point for point, value in zip(candidates, solution.x) if value > .5]
        report = directional_cover_certificate(fixed + selected, receive_radius=999.0, full_report=True, early_exit=False)
        history.append({"round": iteration, "points": len(selected), "constraints": len(masks),
                        "objective": float(solution.fun), "certified": report["certified"],
                        "witness_bound_m": report.get("max_directional_radius_bound_m")})
        print("cover round", iteration, "points", len(selected), "constraints", len(masks),
              "bound", report.get("max_directional_radius_bound_m"), "elapsed", round(time.perf_counter()-started, 2), flush=True)
        if report["certified"]:
            report.pop("pair_details", None)
            return {"accepted": True, "points": selected, "certificate": report, "history": history,
                    "runtime_s": time.perf_counter() - started}
        counterexamples = []
        for detail in report.get("pair_details", []):
            if detail["radius_bound_m"] < 999.0:
                continue
            counterexample = actual_counterexample(fixed + selected, detail)
            if counterexample is not None:
                counterexamples.append(counterexample)
        if not counterexamples:
            return {"accepted": False, "reason": "unresolved_finite_certificate_witness", "history": history}
        new = _constraint_masks(fixed, candidates, counterexamples)
        if not new or all(mask in masks for mask in new):
            return {"accepted": False, "reason": "witness_refinement_did_not_progress", "history": history}
        masks.extend(new)
    return {"accepted": False, "reason": "certificate_round_limit", "history": history}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--free-point", nargs=2, type=float)
    parser.add_argument("--rounds", type=int, default=30)
    parser.add_argument("--spacing", type=int, default=150)
    parser.add_argument("--outer-count", type=int, default=12)
    parser.add_argument("--outer-radius", type=float, default=1864.5)
    parser.add_argument("--max-selected", type=int, default=10)
    parser.add_argument("--time-limit", type=float, default=2.0)
    args = parser.parse_args()
    static = static_coverage_points()
    fixed = ([(0.0, 0.0)] + [(args.outer_radius * math.cos(i * math.tau / args.outer_count),
                             args.outer_radius * math.sin(i * math.tau / args.outer_count))
                            for i in range(args.outer_count)]
             + ([tuple(args.free_point)] if args.free_point else []))
    result = optimize_remaining_cover(fixed, candidate_inner_points(spacing=args.spacing,
                                      outer_count=args.outer_count), max_rounds=args.rounds,
                                      max_selected=args.max_selected, time_limit_s=args.time_limit)
    result["fixed_points"] = fixed
    result["settings"] = vars(args)
    folder = ROOT / "problem4" / "results" / "iterations_v3"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"coverage_replan_outer{args.outer_count}" + ("_free" if args.free_point else "_static")
    (folder / f"{name}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))

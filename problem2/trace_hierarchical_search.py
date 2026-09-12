"""Record actual production candidate visits for a paper search-process figure.

The production search is called unchanged. A temporary wrapper records its
candidate-scoring calls, and its progress callback closes each real batch.
No candidate grid is reconstructed by this script.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import inspect
import json
import math
from pathlib import Path
import time

if __package__:
    from . import solve
else:
    import solve


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
DEFAULT_OUTPUT = ROOT / "results" / "hierarchical_trace_20260912"
EXPECTED_STAGES = ((100., 5., 1.), (20., 1., .5), (5., .25, .25))
EXCLUDED_GEOMETRY_FIELDS = {
    "worst_cell_outer_polygon_local_xy_m",
    "observed_max_cell_outer_polygon_local_xy_m",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounds(rows: list[dict], *, positive_only: bool = False) -> dict | None:
    points = [row["local_xy_m"] for row in rows
              if not positive_only or row["local_xy_m"][1] > 0]
    if not points:
        return None
    return {"x_min": min(p[0] for p in points), "x_max": max(p[0] for p in points),
            "y_min": min(p[1] for p in points), "y_max": max(p[1] for p in points)}


def key(q) -> tuple[float, float]:
    return tuple(round(x, 8) for x in q)


def trace_scene(name: str, station: tuple[float, float], reference: Path) -> dict:
    pending: list[dict] = []
    batches: list[dict] = []
    first_seen: dict[tuple, int] = {}
    identifiers: dict[tuple, int] = {}
    original = solve._candidate_row
    source_hash = sha256(ROOT / "solve.py")
    reference_hash = sha256(reference)
    reference_plan = json.loads(reference.read_text(encoding="utf-8"))

    def record(*args, **kwargs):
        row = original(*args, **kwargs)
        pending.append({k: v for k, v in row.items() if k not in EXCLUDED_GEOMETRY_FIELDS})
        return row

    def close_batch(message: str) -> None:
        level = len(batches) + 1
        is_final = level == len(EXPECTED_STAGES) + 1
        rows = pending.copy()
        pending.clear()
        for row in rows:
            point_key = key(row["local_xy_m"])
            if point_key not in first_seen:
                assert not is_final, "The final review must not introduce candidate coordinates."
                first_seen[point_key] = level
                identifiers[point_key] = len(identifiers) + 1
            q = row["local_xy_m"]
            beta = math.degrees(math.atan2(q[1], q[0]))
            radial_limit = solve.safe_radial_limit(beta)
            row.update({
                "candidate_id": identifiers[point_key],
                "first_seen_level": first_seen[point_key],
                "is_new": not is_final and first_seen[point_key] == level,
                "radius_m": math.hypot(*q),
                "azimuth_deg": beta,
                "is_safe_boundary_point": abs(math.hypot(*q) - radial_limit) < 1e-7,
            })
        new_rows = [r for r in rows if r["is_new"]]
        batch = {
            "phase": "final_review" if is_final else "search_stage",
            "level": None if is_final else level,
            "progress_message": message,
            "candidate_count": len(rows),
            "new_candidate_count": len(new_rows),
            "cumulative_bounds_local_xy_m": bounds(rows),
            "new_bounds_local_xy_m": bounds(new_rows),
            "new_positive_bounds_local_xy_m": bounds(new_rows, positive_only=True),
            "new_safe_boundary_count": sum(r["is_safe_boundary_point"] for r in new_rows),
            "rows": rows,
        }
        batches.append(batch)
        print(f"{name}: {message}; new={len(new_rows)}", flush=True)

    start = time.perf_counter()
    try:
        solve._candidate_row = record
        plan = solve.choose_second_refined(station, 0., progress=close_batch)
    finally:
        solve._candidate_row = original
    runtime = time.perf_counter() - start
    assert not pending and len(batches) == len(EXPECTED_STAGES) + 1
    assert source_hash == sha256(ROOT / "solve.py")
    assert reference_hash == sha256(reference)
    previous_keys: set[tuple] = set()
    for batch, history in zip(batches[:-1], plan["search_history"]):
        batch.update(history)
        current_keys = {key(r["local_xy_m"]) for r in batch["rows"]}
        assert len(current_keys) == len(batch["rows"]) == history["candidate_count"]
        assert previous_keys <= current_keys
        assert batch["new_candidate_count"] == len(current_keys - previous_keys)
        best = min(batch["rows"], key=solve._score_key)
        assert key(best["local_xy_m"]) == key(history["selected_local_xy_m"])
        assert abs(best["diameter_upper_bound_m"] - history["diameter_upper_bound_m"]) < 1e-10
        batch["selected"] = best
        batch["inherited_candidate_count"] = len(previous_keys)
        previous_keys = current_keys
    final = batches[-1]
    assert {key(r["local_xy_m"]) for r in final["rows"]} == previous_keys
    assert final["candidate_count"] == plan["safe_finite_bound_grid_count"]
    final.update({"angle_step_deg": plan["final_angle_step_deg"],
                  "selected": plan["selected"],
                  "fastest_near_best": plan["fastest_near_best"],
                  "candidate_threshold_m": plan["candidate_threshold_m"],
                  "scan_statistics": plan["scan_statistics"]["final"]})
    for batch in batches:
        for row in batch["rows"]:
            q = row["local_xy_m"]
            assert solve.guaranteed_reception(q)
            assert solve.direction_clearance(q) > 5 + solve.EPS
            assert math.hypot(*q) <= min(plan["move_budget_m"], 1005.) + solve.EPS
            assert solve.distance(tuple(row["xy_m"]), solve.rotate_local(q, station, 0.)) < 1e-9
            assert row["geometric_scan_complete"] or row["geometric_diameter_upper_bound_m"] is None
    for field in ("selected", "fastest_near_best"):
        assert key(plan[field]["local_xy_m"]) == key(reference_plan[field]["local_xy_m"])
        assert abs(plan[field]["diameter_upper_bound_m"] -
                   reference_plan[field]["diameter_upper_bound_m"]) < 1e-8
    assert plan["safe_finite_bound_grid_count"] == reference_plan["safe_finite_bound_grid_count"]
    assert plan["search_history"] == reference_plan["search_history"]
    return {
        "schema_version": 1,
        "scene": name,
        "data_provenance": "自建首验场景；真实调用当前生产选点程序取得的离线搜索轨迹，非官方数据或实测误差。",
        "capture_method": "Temporary _candidate_row wrapper; batches closed by real production progress callbacks; original restored in finally.",
        "omitted_fields": sorted(EXCLUDED_GEOMETRY_FIELDS),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime_seconds": runtime,
        "production_source": "problem2/solve.py",
        "production_sha256": source_hash,
        "reference_selection": reference.relative_to(REPO).as_posix(),
        "reference_selection_sha256": reference_hash,
        "first_station_xy_m": list(station),
        "first_bearing_deg": 0.,
        "parameters": {"move_budget_m": plan["move_budget_m"], "error_deg": plan["error_deg"],
                       "circle_sides": plan["circle_sides"], "stages": EXPECTED_STAGES,
                       "final_angle_step_deg": plan["final_angle_step_deg"],
                       "baseline_grid_step_m": plan["grid_step_m"],
                       "tolerance": plan["near_best_tolerance"], "early_stop": True},
        "stages": batches[:-1],
        "final_review": final,
        "validation": {"production_file_unchanged": True, "reference_file_unchanged": True,
                       "old_candidates_retained": True, "counts_match_search_history": True,
                       "all_candidates_safe": True, "selected_matches_existing_selection": True,
                       "fastest_near_best_matches_existing_selection": True,
                       "search_history_matches_existing_selection": True,
                       "final_review_contains_exact_visited_union": True},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_directory
    if not output.is_absolute():
        output = ROOT / output
    output.mkdir(parents=True, exist_ok=True)
    targets = [output / f"{name}.json" for name in ("origin", "boundary", "summary")]
    if any(p.exists() for p in targets):
        raise FileExistsError("This trace is immutable; use a new --output-directory to rerun.")
    signature = inspect.signature(solve.choose_second_refined)
    assert signature.parameters["stages"].default == EXPECTED_STAGES
    expected_defaults = {"move_budget_m": 1100., "tolerance": .1, "error_deg": 1.,
                         "circle_sides": 360, "final_angle_step_deg": .1,
                         "baseline_grid_step_m": 10., "early_stop": True}
    for parameter, expected in expected_defaults.items():
        assert signature.parameters[parameter].default == expected
    summaries = []
    for name, station, reference in [
        ("origin", (0., 0.), ROOT / "results" / "selection.json"),
        ("boundary", (1500., 0.), ROOT / "results" / "boundary" / "selection.json"),
    ]:
        result = trace_scene(name, station, reference)
        (output / f"{name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2,
                                                        allow_nan=False) + "\n", encoding="utf-8")
        summaries.append({"scene": name, "file": f"{name}.json",
                          "runtime_seconds": result["runtime_seconds"],
                          "production_sha256": result["production_sha256"],
                          "stages": [{k: v for k, v in b.items() if k not in {"rows", "selected"}}
                                     for b in result["stages"]],
                          "selected_local_xy_m": result["final_review"]["selected"]["local_xy_m"],
                          "final_diameter_upper_bound_m": result["final_review"]["selected"]["diameter_upper_bound_m"],
                          "validation": result["validation"]})
    (output / "summary.json").write_text(json.dumps({"schema_version": 1, "scenes": summaries},
                                                   ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                                         encoding="utf-8")
    print(f"Saved validated traces to {output}", flush=True)


if __name__ == "__main__":
    main()

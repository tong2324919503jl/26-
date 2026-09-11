"""Verify capped-scan equivalence and measure actual work saved, offline only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys
import time

import solve

ROOT = Path(__file__).resolve().parent


def point_signature(row: dict) -> tuple:
    return tuple(row["local_xy_m"])


def query_benchmark(name: str, first: tuple, bearing: float, error: float,
                    step: float, repeats: int) -> dict:
    polygon = solve.first_region_outer_local(first, bearing, error, 360)
    evaluator = solve.ContinuousDiameterEvaluator(polygon, error, step, circle_sides=360)
    points = [(a, b) for a in (250., 500., 750., 950.) for b in (100., 400., 660., 800.)
              if solve.guaranteed_reception((a, b), error)
              and solve.direction_clearance((a, b), error) > 5]
    # Include the mirrored branch without doubling all benchmark work.
    points.extend((a, -b) for a, b in points[:4])
    times = {False: [], True: []}
    rows_by_mode = {}
    for repetition in range(repeats):
        # Alternate order to reduce warm-up/order bias. Wall times remain local observations.
        for early in ((False, True) if repetition % 2 == 0 else (True, False)):
            started = time.perf_counter()
            rows = [solve._candidate_row(q, first, bearing, evaluator, early_stop=early)
                    for q in points]
            times[early].append(time.perf_counter() - started)
            rows_by_mode[early] = rows
    full, fast = rows_by_mode[False], rows_by_mode[True]
    maximum_difference = max(abs(a["diameter_upper_bound_m"] - b["diameter_upper_bound_m"])
                             for a, b in zip(full, fast))
    if maximum_difference > 1e-9:
        raise AssertionError(f"Capped score mismatch: {name}, {maximum_difference}")
    if [point_signature(r) for r in sorted(full, key=solve._score_key)] != [
            point_signature(r) for r in sorted(fast, key=solve._score_key)]:
        raise AssertionError(f"Candidate ranking changed: {name}")
    for a, b in zip(full, fast):
        if not b["score_exact_for_capped_objective"]:
            raise AssertionError("Early scan must determine the complete capped score")
        if b["scanned_cells"] > a["scanned_cells"]:
            raise AssertionError("Early scan did more cells than its full counterpart")
        if b["early_stopped"]:
            if b["geometric_diameter_upper_bound_m"] is not None:
                raise AssertionError("A partial maximum must not be reported as a complete B")
            if b["geometric_max_lower_bound_m"] < b["analytic_diameter_upper_bound_m"]:
                raise AssertionError("Early stopping occurred before the analytic cap was reached")
        elif b["geometric_diameter_upper_bound_m"] != a["geometric_diameter_upper_bound_m"]:
            raise AssertionError("Completed scans disagree on B")
    full_cells = sum(r["scanned_cells"] for r in full)
    fast_cells = sum(r["scanned_cells"] for r in fast)
    full_seconds, fast_seconds = statistics.median(times[False]), statistics.median(times[True])
    return {"name": name, "first_station_xy_m": first, "first_bearing_deg": bearing,
            "error_deg": error, "angle_step_deg": evaluator.step, "circle_sides": 360,
            "candidate_count": len(points), "repeats": repeats,
            "early_stopped_candidates": sum(r["early_stopped"] for r in fast),
            "full_scanned_cells": full_cells, "early_scanned_cells": fast_cells,
            "saved_cell_fraction": 1 - fast_cells / full_cells,
            "full_median_seconds": full_seconds, "early_median_seconds": fast_seconds,
            "measured_speed_ratio": full_seconds / fast_seconds,
            "max_score_difference_m": maximum_difference, "ranking_identical": True,
            "cells_counted_per_repeat": True,
            "candidate_scores": [{"local_xy_m": a["local_xy_m"],
                                  "full_capped_score_m": a["diameter_upper_bound_m"],
                                  "early_capped_score_m": b["diameter_upper_bound_m"],
                                  "full_B_m": a["geometric_diameter_upper_bound_m"],
                                  "early_B_m": b["geometric_diameter_upper_bound_m"],
                                  "analytic_A_m": b["analytic_diameter_upper_bound_m"],
                                  "scanned_cells": b["scanned_cells"],
                                  "early_stopped": b["early_stopped"]} for a, b in zip(full, fast)]}


def plan_benchmark() -> dict:
    plans, times = {}, {}
    for early in (False, True):
        started = time.perf_counter()
        plans[early] = solve.choose_second_refined((0., 0.), 0., early_stop=early)
        times[early] = time.perf_counter() - started
    full, fast = plans[False], plans[True]
    for field in ("selected", "fastest_near_best"):
        if point_signature(full[field]) != point_signature(fast[field]):
            raise AssertionError(f"End-to-end recommendation changed: {field}")
        if abs(full[field]["diameter_upper_bound_m"] - fast[field]["diameter_upper_bound_m"]) > 1e-9:
            raise AssertionError(f"End-to-end score changed: {field}")
    for field in ("shortlist", "pareto_frontier"):
        if [point_signature(r) for r in full[field]] != [point_signature(r) for r in fast[field]]:
            raise AssertionError(f"End-to-end candidate set changed: {field}")
    if [h["selected_local_xy_m"] for h in full["search_history"]] != [
            h["selected_local_xy_m"] for h in fast["search_history"]]:
        raise AssertionError("Early stopping changed the adaptive search path")
    if full["safe_finite_bound_grid_count"] != fast["safe_finite_bound_grid_count"]:
        raise AssertionError("The two modes visited different candidate sets")
    return {"first_station_xy_m": [0., 0.], "first_bearing_deg": 0.,
            "same_unified_geometry": True, "selected_identical": True,
            "search_path_and_candidate_order_identical": True,
            "selected_local_xy_m": fast["selected"]["local_xy_m"],
            "selected_score_m": fast["selected"]["diameter_upper_bound_m"],
            "visited_candidate_count": fast["safe_finite_bound_grid_count"],
            "full_seconds": times[False], "early_seconds": times[True],
            "measured_speed_ratio": times[False] / times[True],
            "full_scan_statistics": full["scan_statistics"],
            "early_scan_statistics": fast["scan_statistics"]}


def run(output: Path, repeats: int = 2, include_plan: bool = True) -> dict:
    scenarios = [("origin_coarse", (0., 0.), 0., 1., 1.),
                 ("origin_fine", (0., 0.), 0., 1., .1),
                 ("boundary_fine", (1500., 0.), 0., 1., .1),
                 ("rounded_bearing_error", (400., -200.), 25., 1.005, 1.)]
    queries = []
    for args in scenarios:
        row = query_benchmark(*args, repeats)
        queries.append(row)
        print(f"{row['name']}: scores identical, cells {row['full_scanned_cells']} -> {row['early_scanned_cells']}", flush=True)
    plan = plan_benchmark() if include_plan else None
    result = {"passed": True, "verified_at_utc": datetime.now(timezone.utc).isoformat(),
              "python_version": sys.version.split()[0],
              "scope": "Synthetic offline workload. Same unified geometry, candidates and angle grid; only early stopping changes. No official simulator.",
              "query_benchmarks": queries, "end_to_end_plan": plan,
              "interpretation": "Saved cell counts are deterministic for these inputs. Local wall times are observational, not a universal speedup guarantee. No pruning based on a large upper bound is used."}
    output.mkdir(parents=True, exist_ok=True)
    (output / "scoring_benchmark.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = ["# 第二问提前停止：等价性与计算量验证", "",
             "本实验只改变提前停止开关；统一几何模型、候选点、误差和读数网格均相同。比较的是同一模型下的完整扫描与短路扫描，不是与历史上较松模型混比。均为本地自建实验。", "",
             "| 场景 | 点数 | 提前停止点数 | 完整扫描单元 | 实际扫描单元 | 节省比例 | 完整/短路耗时比 |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in queries:
        lines.append(f"| {row['name']} | {row['candidate_count']} | {row['early_stopped_candidates']} | {row['full_scanned_cells']} | {row['early_scanned_cells']} | {row['saved_cell_fraction']:.2%} | {row['measured_speed_ratio']:.3f} |")
    lines += ["", "各场景最终评分和候选排序全部一致；短路时完整几何上界 B 记为 null，已扫描最大值只记为 B 的下界，最终有效保证由 A 提供。", "",
              f"单点评分耗时为交替先后顺序执行 {repeats} 次的中位数；表中扫描单元数按一次运行计。耗时比大于 1 表示本次短路运行较快，小于 1 表示较慢，不选择性删去无提速或变慢场景。"]
    if plan is not None:
        full_cells = plan["full_scan_statistics"]["overall"]["scanned_cells"]
        early_cells = plan["early_scan_statistics"]["overall"]["scanned_cells"]
        lines += ["", "## 完整选点流程", "",
                  f"默认原点案例访问 {plan['visited_candidate_count']} 个候选；两种模式的每层优选点、最终推荐点、近优备选和时间/直径非劣集合均一致。推荐点为 {plan['selected_local_xy_m']}，最终上界 {plan['selected_score_m']:.6f} 米。", "",
                  f"包括分层评分和最终复核，扫描单元从 {full_cells:,} 减至 {early_cells:,}，节省 {full_cells-early_cells:,} 个（{1-early_cells/full_cells:.3%}）；触发提前停止 {plan['early_scan_statistics']['overall']['early_stopped_candidates']} 次。", "",
                  f"本次完整扫描 {plan['full_seconds']:.3f} 秒，提前停止 {plan['early_seconds']:.3f} 秒，耗时比 {plan['measured_speed_ratio']:.3f}。这是单次整流程观测；精确分层扫描计数见 JSON。"]
    lines += ["", "## 边界", "", "当 B 始终小于 A，或 A 为无穷时，不能依据 A 提前停止；因此细网格可能几乎不节省扫描。提前停止只在已扫最大值达到 A 时生效，并不允许用 A 较大为理由淘汰候选点。", "",
              "复现：`python problem2/benchmark_scoring.py`。`--quick` 跳过完整选点双模式对照并默认写入独立的 `results/quick/`。", ""]
    (output / "scoring_benchmark.md").write_text("\n".join(lines), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    output = args.output or (ROOT / "results/quick" if args.quick else ROOT / "results")
    output = output if output.is_absolute() else ROOT / output
    run(output, args.repeats, not args.quick)


if __name__ == "__main__":
    main()

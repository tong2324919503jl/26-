"""同一先验、同一上界精度比较合并前后策略；自建数据，不连接模拟器。"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import solve

ROOT = Path(__file__).resolve().parent


def validate_reference_config(name: str, config: dict) -> None:
    """队友保存坐标仅对应这两组固定输入；阻止改样例后静默混用评分条件。"""
    expected = {"first_station_xy_m": [0., 0.] if name == "synthetic_case" else [1500., 0.],
                "first_bearing_deg": 0., "selection_mode": "refined", "error_deg": 1.,
                "move_budget_m": 1100., "grid_step_m": 10., "near_best_tolerance": .1,
                "circle_sides": 360, "final_angle_step_deg": .1}
    for key, value in expected.items():
        if config.get(key, value) != value:
            raise ValueError(f"固定比较案例 {name} 的 {key} 已改变；请用 solve.py 运行自定义案例，或同步更新全部基线与评分参数")
    default_stages = ((100., 5., 1.), (20., 1., .5), (5., .25, .25))
    if tuple(tuple(s) for s in config.get("search_stages", default_stages)) != default_stages:
        raise ValueError("固定比较案例的搜索网格已改变，请同步更新实验定义")


def compact(row: dict) -> dict:
    return {k: v for k, v in row.items() if "polygon" not in k}


def sample_strategy(first: tuple, first_bearing: float, q: tuple,
                    polygon: list, upper: float) -> dict:
    count, received, near, observations, largest, violations = 0, 0, 0, 0, 0., 0
    for ir in range(61):
        r = 6+(1500-6)*ir/60
        for ia in range(21):
            angle = math.radians(-1+2*ia/20)
            source = (r*math.cos(angle), r*math.sin(angle))
            world = solve.rotate_local(source, first, first_bearing)
            if math.hypot(*world) > 1800+solve.EPS:
                continue
            count += 1
            d = solve.distance(source, q)
            if d > max(1000., r)+1e-8:
                continue
            received += 1
            if d <= 5:
                near += 1
                continue
            for error in (-1., -.5, 0., .5, 1.):
                theta = solve.bearing(source, q)+error
                posterior = solve.clip_bearing(polygon, q, theta)
                if not posterior:
                    raise AssertionError("相容自建观测不应得到空区域")
                diameter = solve.polygon_diameter(posterior)
                largest = max(largest, diameter)
                violations += diameter > upper+1e-6
                observations += 1
    return {"source_grid_count": count, "source_grid_received": received,
            "source_grid_near": near, "direction_error_combinations": observations,
            "sample_reception_fraction": received/count if count else None,
            "sampled_outer_posterior_max_diameter_m": largest,
            "geometric_upper_violations": violations,
            "sample_note": "网格比例不是成功概率；最大值是有限自建情景的外包直径，不是连续最坏值"}


def run_comparison(output_dir: Path, include_extended: bool = True) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    scenarios, origin_plan = [], None
    for name in ("synthetic_case", "boundary_case"):
        config = json.loads((ROOT/"examples"/f"{name}.json").read_text(encoding="utf-8"))
        validate_reference_config(name, config)
        first, theta = tuple(config["first_station_xy_m"]), config["first_bearing_deg"]
        plan = solve.run_example(config, output_dir if name == "synthetic_case" else output_dir/"boundary")
        print(f"{name}: selected={plan['selected']['local_xy_m']}, bound={plan['selected']['diameter_upper_bound_m']:.6f}", flush=True)
        polygon = solve.first_region_outer_local(first, theta)
        evaluator = solve.ContinuousDiameterEvaluator(polygon, angle_step_deg=.1)
        legacy = solve.choose_second(first, theta)["selected"]
        # 队友 ZIP 已保存输出的坐标作为固定基线；不要求运行/依赖临时解压项目。
        teammate = ((848.0480961564259, 529.9192642332049) if name == "synthetic_case"
                    else (222.73863607376248, 222.73863607376248))
        points = [("legacy_analytic", "原仓解析选点", tuple(legacy["local_xy_m"])),
                  ("teammate_saved", "队友保存选点", teammate),
                  ("merged", "融合选点", tuple(plan["selected"]["local_xy_m"])),
                  ("merged_faster", "融合10%容差内最短已访点", tuple(plan["fastest_near_best"]["local_xy_m"]))]
        if name == "synthetic_case":
            origin_plan = plan
            points = [("forward", "沿示向前进750m", (750., 0.)),
                      ("transverse", "横向移动750m", (0., 750.)),
                      ("simple", "简明安全点800,600", (800., 600.))]+points
        rows = []
        for key, label, point in points:
            row = compact(solve._candidate_row(point, first, theta, evaluator))
            row.update({"key": key, "label": label,
                        "guaranteed_reception": solve.guaranteed_reception(point)})
            row.update(sample_strategy(first, theta, point, polygon, row["geometric_diameter_upper_bound_m"]))
            if row["geometric_upper_violations"]:
                raise AssertionError(f"几何上界检查失败: {name}/{key}")
            if row["guaranteed_reception"] and row["source_grid_count"] != row["source_grid_received"]:
                raise AssertionError(f"安全点收信检查失败: {name}/{key}")
            rows.append(row)
        scenarios.append({"name": name, "first_station_xy_m": first,
                          "first_bearing_deg": theta, "error_deg": 1.,
                          "circle_sides": 360, "angle_step_deg": .1,
                          "move_budget_m": 1100., "rows": rows})
    budgets, sensitivity = [], []
    if include_extended:
        polygon = solve.first_region_outer_local((0., 0.), 0.)
        evaluator = solve.ContinuousDiameterEvaluator(polygon, angle_step_deg=.1)
        for budget in (600., 800., 1000., 1100.):
            plan = origin_plan if budget == 1100 else solve.choose_second_refined((0., 0.), 0., move_budget_m=budget)
            baseline = plan["baseline_analytic_selected"]
            baseline_geo = evaluator.evaluate(tuple(baseline["local_xy_m"]))["geometric_diameter_upper_bound_m"]
            budgets.append({"move_budget_m": budget, "selected": compact(plan["selected"]),
                            "legacy_local_xy_m": baseline["local_xy_m"],
                            "legacy_same_geometric_bound_m": baseline_geo})
            print(f"budget {budget:g}: {plan['selected']['diameter_upper_bound_m']:.6f} m", flush=True)
        fixed_points = [(r["key"], tuple(r["local_xy_m"])) for r in scenarios[0]["rows"]
                        if r["key"] in ("legacy_analytic", "teammate_saved", "merged")]
        for sides, step in ((180, .2), (360, .1), (720, .05)):
            ev = solve.ContinuousDiameterEvaluator(solve.first_region_outer_local((0, 0), 0, circle_sides=sides),
                                                   angle_step_deg=step)
            sensitivity.append({"circle_sides": sides, "angle_step_deg": ev.step,
                                "fixed_candidate_bounds": [{"key": key, **compact(ev.evaluate(q))} for key, q in fixed_points]})
        fine = solve.choose_second_refined((0, 0), 0, circle_sides=720,
                                            stages=((100., 5., 1.), (20., 1., .5), (2.5, .125, .125)),
                                            final_angle_step_deg=.05)
        fine_evaluator = solve.ContinuousDiameterEvaluator(solve.first_region_outer_local((0, 0), 0, circle_sides=720),
                                                           angle_step_deg=.05)
        spatial_refinement = {"radial_step_m": 2.5, "azimuth_step_deg": .125,
                              "circle_sides": 720, "final_angle_step_deg": .05,
                              "selected": compact(fine["selected"]),
                              "default_point_same_fine_geometric_bound_m": fine_evaluator.evaluate(tuple(origin_plan["selected"]["local_xy_m"]))["geometric_diameter_upper_bound_m"],
                              "visited_candidate_count": fine["safe_finite_bound_grid_count"]}
        print(f"fine search: {fine['selected']['diameter_upper_bound_m']:.6f} m", flush=True)
    else:
        spatial_refinement = None
    result = {"data_provenance": "自建离线数学实验；不是官方数据、官方模拟器成绩或真实场地效果",
              "metric": "同一首读数外包、M=360、第二读数h=0.1度且半角增宽至1.05度的几何直径上界",
              "comparison_note": "解析上界131.221到几何上界的下降包含评价变紧；只能用相同几何评分比较选点。均非实际点估计误差。",
              "source_grid": {"radial_count": 61, "radius_min_m": 6, "radius_max_m": 1500,
                              "angle_count": 21, "first_angle_range_deg": [-1, 1], "second_errors_deg": [-1, -.5, 0, .5, 1],
                              "target_disk_filter": True, "reception_radius": "max(1000,r1)"},
              "scenarios": scenarios, "budgets": budgets, "precision_sensitivity": sensitivity,
              "spatial_refinement": spatial_refinement}
    (output_dir/"strategy_comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    save_report(result, output_dir/"strategy_comparison.md")
    return result


def save_report(result: dict, path: Path) -> None:
    lines = ["# 第二问合并后的同口径比较", "", result["data_provenance"]+"。", "",
             "全部策略先用相同的目标圆条件化先验、360边圆外包和0.1°读数网格评分，半角增宽到1.05°。表中 B 是连续读数下的几何直径上界；不安全点的 B 仅对返回示向度的分支有效。", ""]
    for scenario in result["scenarios"]:
        lines += [f"## 首点 {scenario['first_station_xy_m']}、示向度 {scenario['first_bearing_deg']}°", "",
                  "| 策略 | 第二点局部坐标/m | B/m | 移动+检测/s | 保证收信 | 自建网格收信 |", "|---|---|---:|---:|---|---:|"]
        for row in scenario["rows"]:
            a, b = row["local_xy_m"]
            lines.append(f"| {row['label']} | ({a:.3f},{b:.3f}) | {row['geometric_diameter_upper_bound_m']:.6f} | {row['move_and_detect_time_s']:.3f} | {'是' if row['guaranteed_reception'] else '否'} | {row['source_grid_received']}/{row['source_grid_count']} |")
        legacy = next(r for r in scenario["rows"] if r["key"] == "legacy_analytic")
        merged = next(r for r in scenario["rows"] if r["key"] == "merged")
        change = 1-merged["geometric_diameter_upper_bound_m"]/legacy["geometric_diameter_upper_bound_m"]
        lines += ["", f"在同一上界指标下，融合点相对原仓点下降 {change:.2%}。这表示所选策略获得更好的最坏直径保证；不能解释为真实定位误差同比下降。", ""]
    if result["budgets"]:
        lines += ["## 移动预算折中", "", "| 预算/m | 融合点局部坐标/m | 原仓点的同口径B/m | 融合B/m | 移动+检测/s |", "|---:|---|---:|---:|---:|"]
        for row in result["budgets"]:
            s = row["selected"]
            a, b = s["local_xy_m"]
            lines.append(f"| {row['move_budget_m']:.0f} | ({a:.3f},{b:.3f}) | {row['legacy_same_geometric_bound_m']:.6f} | {s['geometric_diameter_upper_bound_m']:.6f} | {s['move_and_detect_time_s']:.3f} |")
        lines += ["", "## 数值精度与空间细化", "", "固定三个候选点，只改变圆外包/读数网格精度，避免把换点和换评分混在一起。", "",
                  "| 圆边数 | 读数步长/° | 原仓点B/m | 队友点B/m | 默认融合点B/m |", "|---:|---:|---:|---:|---:|"]
        for row in result["precision_sensitivity"]:
            values = " | ".join(f"{r['geometric_diameter_upper_bound_m']:.6f}" for r in row["fixed_candidate_bounds"])
            lines.append(f"| {row['circle_sides']} | {row['angle_step_deg']:.2f} | {values} |")
        fine = result["spatial_refinement"]
        s = fine["selected"]
        a, b = s["local_xy_m"]
        lines += ["", f"进一步使用720边、0.05°读数网格和最后一层2.5m/0.125°空间细化，选点为({a:.6f},{b:.6f})m，上界为{s['geometric_diameter_upper_bound_m']:.6f}m；默认融合点在同一细评分下为{fine['default_point_same_fine_geometric_bound_m']:.6f}m。选点和排序可能随网格变化，未证明连续全局最优。", ""]
    lines += ["## 数据与保证边界", "", "每个场景先在6至1500米取61个距离、首方位±1°内取21个角度，再滤去目标圆外源；接收半径取与首次收信相容的最小值max(1000,r1)。对正常示向度分支枚举5个第二点固定误差。原点有1281个源组合，边界场景因目标圆过滤而较少。不同误差是不同自建情景，不是同点重复检测后平均。", "",
              "原始JSON保留样本外包直径最大值、正常读数组合数、上界违反次数及各评分参数。网格收信率不是现实成功概率；有限验证不能代替四圆盘及集合包含证明。", "",
              "20米内一次光学定位应另核验最小覆盖圆半径；B/2并非一般覆盖半径保证。只凭直径上界可用B/√3≤20作为充分条件，原点两点定位结果尚不满足。", "",
              "复现：`python problem2/compare_strategies.py`。`--quick`跳过预算与精度/空间敏感性，默认写入`results/quick/`；固定案例参数变化会明确报错，避免基线与融合策略混用不同条件。", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    output = args.output or (ROOT/"results"/"quick" if args.quick else ROOT/"results")
    output = output if output.is_absolute() else ROOT/output
    run_comparison(output, include_extended=not args.quick)


if __name__ == "__main__":
    main()

"""B 问题 2：有收信保证的第二检测点选择；仅使用 Python 标准库。"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
Point = tuple[float, float]
EPS = 1e-9


def distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def rotate_local(p: Point, origin: Point, bearing_deg: float) -> Point:
    t = math.radians(bearing_deg)
    return (origin[0] + p[0] * math.cos(t) - p[1] * math.sin(t),
            origin[1] + p[0] * math.sin(t) + p[1] * math.cos(t))


def to_local(p: Point, origin: Point, bearing_deg: float) -> Point:
    t = math.radians(bearing_deg)
    x, y = p[0] - origin[0], p[1] - origin[1]
    return x * math.cos(t) + y * math.sin(t), -x * math.sin(t) + y * math.cos(t)


def angular_error(a: float, b: float) -> float:
    return (a - b + 180.0) % 360.0 - 180.0


def bearing(source: Point, station: Point) -> float:
    return math.degrees(math.atan2(source[1] - station[1], source[0] - station[0])) % 360


def safe_centers(error_deg: float = 1.0) -> list[Point]:
    """四圆盘中心，相对于第一点的示向度局部坐标。"""
    e = math.radians(error_deg)
    return [(r * math.cos(e), sign * r * math.sin(e))
            for r in (5.0, 1000.0) for sign in (-1, 1)]


def guaranteed_reception(q_local: Point, error_deg: float = 1.0) -> bool:
    return all(distance(q_local, c) <= 1000.0 + EPS for c in safe_centers(error_deg))


def diameter_bound(q_local: Point, error_deg: float = 1.0) -> float:
    """每一种兼容第二次 direction 读数的定位区域直径的统一上界，米。

    来源是保守矩形角度界和两条有界宽度带的交集，而非线性化方差。
    不满足四圆盘安全约束或夹角无法保证时返回无穷。
    """
    if not guaranteed_reception(q_local, error_deg):
        return math.inf
    a, b = q_local
    e = math.radians(error_deg)
    h = abs(b) - 1500.0 * math.sin(e)
    k = max(abs(a - 5.0 * math.cos(e)), abs(a - 1500.0))
    if h <= 0:
        return math.inf
    beta = math.atan2(h, k) - e
    if beta <= 0:
        return math.inf
    r2_max = max(distance(q_local, (r * math.cos(e), sign * r * math.sin(e)))
                 for r in (5.0, 1500.0) for sign in (-1, 1))
    w1, w2 = 1500.0 * math.sin(e), r2_max * math.sin(e)
    return 2.0 * math.sqrt(w1*w1 + w2*w2 + 2.0*w1*w2*math.cos(beta)) / math.sin(beta)


def prior_nonempty(station: Point, bearing_deg: float, error_deg: float) -> bool:
    """检查首读数闭包与目标圆是否相交；首距=5的退化边界由文档说明。"""
    cx, cy = to_local((0.0, 0.0), station, bearing_deg)
    direction = math.degrees(math.atan2(cy, cx))
    phi = max(-error_deg, min(error_deg, direction))
    e = math.radians(phi)
    projection = cx * math.cos(e) + cy * math.sin(e)
    r = max(5.0, min(1500.0, projection))
    return math.hypot(cx-r*math.cos(e), cy-r*math.sin(e)) <= 1800.0 + EPS


def choose_second(station: Point, bearing_deg: float, *, grid_step_m: float = 10.0,
                  move_budget_m: float = 1100.0, tolerance: float = 0.10,
                  error_deg: float = 1.0) -> dict:
    """在明确有限网格上选择最小保证上界点；不要求机器人在目标圆内。"""
    values = (*station, bearing_deg, grid_step_m, move_budget_m, tolerance, error_deg)
    if not all(math.isfinite(v) for v in values):
        raise ValueError("所有输入必须为有限数值")
    if grid_step_m <= 0 or move_budget_m <= 0 or tolerance < 0:
        raise ValueError("网格步长、移动预算必须为正，容差不得为负")
    if not 0 < error_deg < 10:
        raise ValueError("本实现要求 0 < error_deg < 10；原题取 1 度")
    if not prior_nonempty(station, bearing_deg, error_deg):
        raise ValueError("第一点坐标/示向度与 1800 米目标圆、5 至 1500 米范围不相容")
    candidates = []
    # 四圆盘已蕴含 a>=0、a<=1005、|b|<=1000；只搜这一有界范围。
    for ia in range(math.floor(1005.0 / grid_step_m) + 1):
        a = ia * grid_step_m
        for ib in range(1, math.floor(1000.0 / grid_step_m) + 1):
            b = ib * grid_step_m
            if math.hypot(a, b) > move_budget_m + EPS:
                continue
            q = (a, b)
            bound = diameter_bound(q, error_deg)
            if not math.isfinite(bound):
                continue
            # 对称两侧均保留；评分相同时优先正侧，方便结果可重复。
            for sign in (1, -1):
                loc = (a, sign * b)
                candidates.append({"local_xy_m": list(loc),
                                   "xy_m": list(rotate_local(loc, station, bearing_deg)),
                                   "diameter_upper_bound_m": bound,
                                   "move_distance_m": math.hypot(a, b),
                                   "move_and_detect_time_s": math.hypot(a, b) / 5.0 + 5.0})
    if not candidates:
        raise ValueError("此网格/移动预算没有可提供非退化统一夹角保证的点；减小步长或增加预算")
    candidates.sort(key=lambda x: (x["diameter_upper_bound_m"], x["move_distance_m"],
                                   -x["local_xy_m"][1], x["local_xy_m"][0]))
    selected = candidates[0]
    threshold = selected["diameter_upper_bound_m"] * (1.0 + tolerance)
    shortlist = [q for q in candidates if q["diameter_upper_bound_m"] <= threshold + EPS]
    return {
        "method": "four_disk_reception_guarantee_and_uniform_diameter_bound",
        "data_provenance": "自建示例/用户输入；不是官方模拟器测试数据",
        "first_station_xy_m": list(station), "first_bearing_deg": bearing_deg % 360,
        "error_deg": error_deg, "grid_step_m": grid_step_m, "move_budget_m": move_budget_m,
        "near_best_tolerance": tolerance,
        "guaranteed_reception": True,
        "optimization_scope": "有限网格上统一直径上界最小；未证明连续域全局最优",
        "continuous_candidate_region": "四圆盘交集 ∩ 移动预算圆 ∩ {D_bound <= threshold}",
        "candidate_threshold_m": threshold,
        "selected": selected,
        "safe_finite_bound_grid_count": len(candidates),
        "near_best_grid_count": len(shortlist),
        "shortlist": shortlist,
    }


def clip_polygon(vertices: list[Point], normal: Point, offset: float) -> list[Point]:
    """裁剪半平面 normal·x<=offset；容差只用于包含边界。"""
    if not vertices:
        return []
    out = []
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        fa = normal[0] * a[0] + normal[1] * a[1] - offset
        fb = normal[0] * b[0] + normal[1] * b[1] - offset
        ain, bin_ = fa <= EPS, fb <= EPS
        if ain:
            out.append(a)
        if ain != bin_:
            t = fa / (fa - fb)
            out.append((a[0] + t * (b[0]-a[0]), a[1] + t * (b[1]-a[1])))
    return out


def posterior_outer_polygon(first: Point, first_bearing: float,
                            second: Point, second_bearing: float,
                            error_deg: float = 1.0, circle_sides: int = 720) -> list[Point]:
    """真定位区域的外包多边形：圆用相切半平面外包，保留两示向度扇区。

    保留首/次距<=5部分作为保守放松。不是原题纯示向度交会多边形的替代。
    """
    if circle_sides < 8:
        raise ValueError("circle_sides 至少为 8")
    vertices = [(-1800.0, -1800.0), (1800.0, -1800.0),
                (1800.0, 1800.0), (-1800.0, 1800.0)]
    for station, theta in ((first, first_bearing), (second, second_bearing)):
        for angle, sign in ((theta-error_deg, -1), (theta+error_deg, 1)):
            r = math.radians(angle)
            # 下边界要求cross(u,x-s)>=0，上边界要求<=0。
            normal = (-sign * math.sin(r), sign * math.cos(r))
            vertices = clip_polygon(vertices, normal, normal[0]*station[0] + normal[1]*station[1])
    for center, radius in (((0.0, 0.0), 1800.0), (first, 1500.0), (second, 1500.0)):
        for i in range(circle_sides):
            t = 2*math.pi*i/circle_sides
            normal = (math.cos(t), math.sin(t))
            vertices = clip_polygon(vertices, normal, radius + normal[0]*center[0]+normal[1]*center[1])
    # 补上证明中真实后验必满足的条带。这样近区放松和圆的外包不会突破条带界。
    q_local = to_local(second, first, first_bearing)
    e = math.radians(error_deg)
    r2_max = 1500.0
    if guaranteed_reception(q_local, error_deg):
        r2_max = max(distance(q_local, (r*math.cos(e), sign*r*math.sin(e)))
                     for r in (5.0, 1500.0) for sign in (-1, 1))
    for station, theta, radius in ((first, first_bearing, 1500.0),
                                   (second, second_bearing, r2_max)):
        t = math.radians(theta)
        for sign in (-1, 1):
            normal = (-sign*math.sin(t), sign*math.cos(t))
            offset = normal[0]*station[0] + normal[1]*station[1] + radius*math.sin(e)
            vertices = clip_polygon(vertices, normal, offset)
    return vertices


def polygon_diameter(vertices: Iterable[Point]) -> float:
    points = list(vertices)
    return max((distance(a, b) for a in points for b in points), default=0.0)


def save_svg(plan: dict, path: Path) -> None:
    """不用绘图库生成可缩放示意图；图内坐标为第一点的局部坐标。"""
    sx, sy = 470.0, 460.0
    scale = 0.32
    def xy(p):
        return sx + p[0]*scale, sy-p[1]*scale
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="860" viewBox="0 0 1120 860">',
             '<rect width="1120" height="860" fill="#f8fafc"/>',
             '<style>text{font-family:Arial,sans-serif;fill:#172554}.small{font-size:14px}</style>',
             '<text x="40" y="42" font-size="26" font-weight="bold">Problem 2: guaranteed-reception candidate region</text>',
             '<text x="40" y="71" font-size="16">Local coordinates: first measured bearing is the positive x-axis (metres).</text>']
    # 灰色采样只用于显示连续安全区域，不参与收信证明。
    for a in range(0, 1011, 10):
        for b in range(-1000, 1001, 10):
            if guaranteed_reception((a, b), plan["error_deg"]):
                x, y = xy((a, b))
                parts.append(f'<rect x="{x-1.7:.2f}" y="{y-1.7:.2f}" width="3.5" height="3.5" fill="#dbe3eb"/>')
    for c in safe_centers(plan["error_deg"]):
        x,y=xy(c)
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="320" fill="none" stroke="#94a3b8" stroke-width="1"/>')
    for row in plan["shortlist"]:
        x,y=xy(row["local_xy_m"])
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.2" fill="#2563eb" opacity="0.7"/>')
    e=math.radians(plan["error_deg"])
    prior=[(0.,0.),(1500*math.cos(e),1500*math.sin(e)),(1500*math.cos(e),-1500*math.sin(e))]
    points=" ".join(f"{xy(p)[0]:.2f},{xy(p)[1]:.2f}" for p in prior)
    parts.append(f'<polygon points="{points}" fill="#f59e0b" opacity="0.65"/>')
    for y in (-1000,-500,0,500,1000):
        xp,yp=xy((0,y))
        parts.append(f'<text x="{xp-55:.2f}" y="{yp+5:.2f}" class="small">{y}</text>')
    for x in (0,500,1000,1500):
        xp,yp=xy((x,0))
        parts.append(f'<text x="{xp-12:.2f}" y="{yp+28:.2f}" class="small">{x}</text>')
    parts.append(f'<line x1="{sx}" y1="{sy}" x2="990" y2="{sy}" stroke="#64748b"/>')
    x,y=xy(plan["selected"]["local_xy_m"])
    parts.append(f'<line x1="{sx}" y1="{sy}" x2="{x:.2f}" y2="{y:.2f}" stroke="#dc2626" stroke-width="2"/>')
    parts.append(f'<circle cx="{sx}" cy="{sy}" r="5" fill="#172554"/>')
    parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="7" fill="#dc2626" stroke="white" stroke-width="2"/>')
    parts.append(f'<text x="{x+12:.2f}" y="{y-10:.2f}" class="small">Selected second station</text>')
    a,b=plan["selected"]["local_xy_m"]
    bound=plan["selected"]["diameter_upper_bound_m"]
    parts.extend([
        '<rect x="35" y="752" width="1050" height="82" rx="10" fill="white" stroke="#cbd5e1"/>',
        '<text x="50" y="776" class="small">Grey: safe reception region. Blue: candidate grid points within the stated bound threshold. Orange: first bearing sector.</text>',
        f'<text x="50" y="800" class="small">Selected: ({a:.0f}, {b:.0f}) m | uniform diameter bound: {bound:.2f} m | grid: {plan["grid_step_m"]:g} m.</text>',
        '<text x="50" y="822" class="small">The source also lies in the global target disk. This conservative local strategy does not require a source-distance prior.</text>',
        '</svg>'])
    path.write_text("\n".join(parts), encoding="utf-8")


def run_example(config: dict, output_dir: Path) -> dict:
    first = tuple(map(float, config["first_station_xy_m"]))
    first_bearing = float(config["first_bearing_deg"])
    plan = choose_second(first, first_bearing, grid_step_m=float(config.get("grid_step_m", 10)),
                         move_budget_m=float(config.get("move_budget_m",1100)),
                         tolerance=float(config.get("near_best_tolerance",0.10)))
    output_dir.mkdir(parents=True,exist_ok=True)
    rows = plan.pop("shortlist")
    with (output_dir/"second_point_candidates.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.writer(f)
        writer.writerow(["local_a_m","local_b_m","x_m","y_m","diameter_upper_bound_m","move_distance_m","move_and_detect_time_s"])
        for q in rows:
            writer.writerow([*q["local_xy_m"],*q["xy_m"],q["diameter_upper_bound_m"],q["move_distance_m"],q["move_and_detect_time_s"]])
    save_svg({**plan,"shortlist":rows},output_dir/"candidate_region.svg")
    if "synthetic_source_xy_m" in config:
        source=tuple(map(float,config["synthetic_source_xy_m"]))
        second=tuple(plan["selected"]["xy_m"])
        radius=float(config.get("synthetic_reception_radius_m",1500))
        err=float(config.get("synthetic_second_error_deg",0.4))
        if not 1000 <= radius <= 1500 or distance(source,(0.,0.)) > 1800+EPS:
            raise ValueError("自建源不符合题目位置/接收半径限制")
        if not 5 < distance(source,first) <= radius:
            raise ValueError("自建源在第一点不能产生 direction")
        if abs(angular_error(first_bearing,bearing(source,first))) > 1+EPS or abs(err) > 1:
            raise ValueError("自建读数误差超出 ±1 度")
        if distance(source,second) > radius+EPS:
            raise AssertionError("保证收信失败")
        if distance(source,second) <= 5:
            plan["synthetic_observation"]={"status":"near","source_xy_m":list(source),"action":"直接光学定位与清除"}
        else:
            second_bearing=(bearing(source,second)+err)%360
            poly=posterior_outer_polygon(first,first_bearing,second,second_bearing)
            plan["synthetic_observation"]={
                "status":"direction","source_xy_m":list(source),"reception_radius_m":radius,
                "second_bearing_deg":second_bearing,"second_fixed_error_deg":err,
                "source_distance_from_second_m":distance(source,second),
                "posterior_outer_polygon_xy_m":[list(p) for p in poly],
                "posterior_outer_polygon_diameter_m":polygon_diameter(poly),
                "polygon_note":"两次扇区、目标圆和1500米接收圆相交的保守外包；圆用720个相切半平面，未扣除5米近区；另裁入解析上界证明中的有效条带"}
    (output_dir/"selection.json").write_text(json.dumps(plan,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return plan


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,default=ROOT/"examples"/"synthetic_case.json")
    parser.add_argument("--output",type=Path,default=ROOT/"results")
    args=parser.parse_args()
    # 自定义相对路径也相对本脚本目录，避免启动目录改变含义。
    input_path=args.input if args.input.is_absolute() else ROOT/args.input
    output_path=args.output if args.output.is_absolute() else ROOT/args.output
    plan=run_example(json.loads(input_path.read_text(encoding="utf-8-sig")),output_path)
    print(json.dumps({"selected":plan["selected"],"candidate_count":plan["near_best_grid_count"],
                      "output_dir":str(output_path.resolve())},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()

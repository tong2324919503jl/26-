"""B 问题 2：有收信保证的第二检测点选择；仅使用 Python 标准库。"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Callable, Iterable

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
            # 分类和交点都使用同一外扩边界 fa=EPS，避免边界容差导致线段外推。
            t = max(0., min(1., (fa-EPS)/(fa-fb)))
            out.append((a[0] + t * (b[0]-a[0]), a[1] + t * (b[1]-a[1])))
    return out


def posterior_outer_polygon(first: Point, first_bearing: float,
                            second: Point, second_bearing: float,
                            error_deg: float = 1.0, circle_sides: int = 720) -> list[Point]:
    """真定位区域的外包多边形：圆用相切半平面外包，保留两示向度扇区。

    保留首/次距<=5部分作为保守放松。不是原题纯示向度交会多边形的替代。
    """
    q_local = to_local(second, first, first_bearing)
    # 与几何评分共用局部首验外包，包括有效下界 x>=5 cos(error)。
    # 同一 circle_sides 时，显示后验是评分外包的子集；不混用世界坐标圆网格。
    vertices = first_region_outer_local(first, first_bearing, error_deg, circle_sides)
    theta_local = second_bearing-first_bearing
    vertices = clip_bearing(vertices, q_local, theta_local, error_deg)
    for i in range(circle_sides):
        t = 2*math.pi*i/circle_sides
        normal = (math.cos(t), math.sin(t))
        vertices = clip_polygon(vertices, normal, 1500+normal[0]*q_local[0]+normal[1]*q_local[1])
    # 继续裁入两个有效条带，才能让显示外包也满足解析条带上界。
    e = math.radians(error_deg)
    r2_max = 1500.0
    if guaranteed_reception(q_local, error_deg):
        r2_max = max(distance(q_local, (r*math.cos(e), sign*r*math.sin(e)))
                     for r in (5.0, 1500.0) for sign in (-1, 1))
    for station, theta, radius in (((0., 0.), 0., 1500.0),
                                   (q_local, theta_local, r2_max)):
        t = math.radians(theta)
        for sign in (-1, 1):
            normal = (-sign*math.sin(t), sign*math.cos(t))
            offset = normal[0]*station[0] + normal[1]*station[1] + radius*math.sin(e)
            vertices = clip_polygon(vertices, normal, offset)
    return [rotate_local(p, first, first_bearing) for p in vertices]


def polygon_diameter(vertices: Iterable[Point]) -> float:
    points = list(vertices)
    return max((distance(a, b) for a in points for b in points), default=0.0)


def clip_bearing(vertices: list[Point], station: Point, theta: float,
                 error_deg: float = 1.0) -> list[Point]:
    """用前向示向扇形裁剪，正确处理跨 0 度的读数。"""
    for angle, sign in ((theta-error_deg, -1), (theta+error_deg, 1)):
        r = math.radians(angle)
        n = (-sign*math.sin(r), sign*math.cos(r))
        vertices = clip_polygon(vertices, n, n[0]*station[0]+n[1]*station[1])
    return vertices


def first_region_outer_local(station: Point, bearing_deg: float,
                             error_deg: float = 1.0,
                             circle_sides: int = 360) -> list[Point]:
    """首读数可行集在首点局部坐标中的外包；目标圆约束源而非机器人。

    以外切半平面近似两个圆，并保留首距下界的有效线性约束
    x>=5 cos(error)。这仍可能包含首距<=5的少量点，属于保守放松。
    """
    if circle_sides < 8 or int(circle_sides) != circle_sides:
        raise ValueError("circle_sides 必须是至少为 8 的整数")
    if not prior_nonempty(station, bearing_deg, error_deg):
        raise ValueError("首读数与目标圆或接收距离范围不相容")
    vertices = clip_bearing([(-1500., -1500.), (1500., -1500.),
                             (1500., 1500.), (-1500., 1500.)], (0., 0.), 0., error_deg)
    center = to_local((0., 0.), station, bearing_deg)
    for c, radius in (((0., 0.), 1500.), (center, 1800.)):
        for i in range(circle_sides):
            t = 2*math.pi*i/circle_sides
            n = (math.cos(t), math.sin(t))
            vertices = clip_polygon(vertices, n, radius+n[0]*c[0]+n[1]*c[1])
    e = math.radians(error_deg)
    vertices = clip_polygon(vertices, (-1., 0.), -5*math.cos(e))
    for sign in (-1., 1.):
        vertices = clip_polygon(vertices, (0., sign), 1500*math.sin(e))
    if not vertices:
        raise ValueError("首读数可行区域为空")
    return vertices


class ContinuousDiameterEvaluator:
    """采用半格增宽，覆盖连续全部第二读数的几何直径上界。

    合并队友方案中的外包/增宽思想；没有用角噪声线性近似评分。
    这是双精度数学外包计算，不是区间算术认证。
    """

    def __init__(self, polygon: list[Point], error_deg: float = 1.,
                 angle_step_deg: float = .1):
        if not polygon:
            raise ValueError("首读数外包不能为空")
        if not math.isfinite(angle_step_deg) or not 0 < angle_step_deg <= 30:
            raise ValueError("角度扫描步长须在 (0,30] 度")
        self.count = math.ceil(360/angle_step_deg)
        self.step = 360/self.count
        self.error = error_deg
        self.widened_error = error_deg+self.step/2
        if not 0 < error_deg < 90 or self.widened_error >= 90:
            raise ValueError("原始和增宽误差半角须在 (0,90) 度")
        self.polygon = list(polygon)
        self.normals = []
        for i in range(self.count):
            angle = i*self.step
            lower, upper = map(math.radians, (angle-self.widened_error,
                                               angle+self.widened_error))
            self.normals.append((angle, (math.sin(lower), -math.cos(lower)),
                                 (-math.sin(upper), math.cos(upper))))

    def evaluate(self, q_local: Point) -> dict:
        maximum, worst_angle, worst_poly = 0., 0., []
        for angle, n1, n2 in self.normals:
            poly = clip_polygon(self.polygon, n1, n1[0]*q_local[0]+n1[1]*q_local[1])
            if not poly:
                continue
            poly = clip_polygon(poly, n2, n2[0]*q_local[0]+n2[1]*q_local[1])
            if not poly:
                continue
            value = polygon_diameter(poly)
            if value > maximum:
                maximum, worst_angle, worst_poly = value, angle, poly
        return {"geometric_diameter_upper_bound_m": maximum,
                "worst_cell_center_local_deg": worst_angle,
                "worst_cell_outer_polygon_local_xy_m": [list(v) for v in worst_poly]}


def direction_clearance(q_local: Point, error_deg: float = 1.) -> float:
    """位于前向半平面的安全点，到首示向扇形的外侧垂距。"""
    e = math.radians(error_deg)
    return abs(q_local[1])*math.cos(e)-q_local[0]*math.sin(e)


def safe_radial_limit(beta_deg: float, error_deg: float = 1.,
                       move_budget_m: float = 1100.) -> float:
    """给定局部移动方位，四圆盘在该射线上的精确半径上限。"""
    alpha = math.radians(abs(beta_deg)+error_deg)
    if abs(beta_deg)+error_deg >= 90:
        return 0.
    return min(move_budget_m, 2000*math.cos(alpha),
               5*math.cos(alpha)+math.sqrt(1000**2-25*math.sin(alpha)**2))


def _candidate_row(q_local: Point, station: Point, bearing_deg: float,
                   evaluator: ContinuousDiameterEvaluator) -> dict:
    geometric = evaluator.evaluate(q_local)
    strip = diameter_bound(q_local, evaluator.error)
    d = math.hypot(*q_local)
    return {"local_xy_m": list(q_local),
            "xy_m": list(rotate_local(q_local, station, bearing_deg)),
            "diameter_upper_bound_m": min(strip, geometric["geometric_diameter_upper_bound_m"]),
            "analytic_diameter_upper_bound_m": strip if math.isfinite(strip) else None,
            **geometric, "move_distance_m": d,
            "move_and_detect_time_s": d/5+5,
            "direction_clearance_m": direction_clearance(q_local, evaluator.error)}


def _score_key(row: dict) -> tuple:
    # 1e-7 米仅用于确定浮点平局顺序，不宣称更高精度的物理区别。
    return (round(row["diameter_upper_bound_m"], 7), row["move_distance_m"],
            -row["local_xy_m"][1], row["local_xy_m"][0])


def choose_second_refined(station: Point, bearing_deg: float, *,
                          move_budget_m: float = 1100., tolerance: float = .10,
                          error_deg: float = 1., circle_sides: int = 360,
                          stages: tuple = ((100., 5., 1.), (20., 1., .5), (5., .25, .25)),
                          final_angle_step_deg: float = .1,
                          baseline_grid_step_m: float = 10.,
                          progress: Callable[[str], None] | None = None) -> dict:
    """四圆盘安全域内，合并解析保底和目标圆条件化的连续读数上界。

    stages 每项为移动距离步长、移动方位步长、读数评分角步长。
    所有访问候选最后统一精度重新评分，才进行精度/时间比较。
    """
    if not all(math.isfinite(v) for v in (*station, bearing_deg, move_budget_m,
                                         tolerance, error_deg, baseline_grid_step_m)):
        raise ValueError("输入必须为有限数值")
    if move_budget_m <= 0 or tolerance < 0 or not 0 < error_deg < 10 or baseline_grid_step_m <= 0:
        raise ValueError("移动预算和网格步长须为正，容差非负，误差半角位于 (0,10) 度")
    if not stages or any(len(s) != 3 or any(not math.isfinite(v) or v <= 0 for v in s) for s in stages):
        raise ValueError("至少需要一层，每层包含三个正有限步长")
    polygon = first_region_outer_local(station, bearing_deg, error_deg, circle_sides)
    # 四圆盘蕴含 ||q|| <= 1005；目标圆不参与此处的机器人位置筛选。
    maximum_radius = min(move_budget_m, 1005.)
    visited: dict[tuple, Point] = {}
    history, best, last_r_step, last_beta_step = [], None, 0., 0.
    # 原实现优选点和两个直观安全点都参加统一评分，保证合并不会遗漏原候选。
    seeds = [(800., 600.), (800., -600.),
             (1000/math.sqrt(2), 1000/math.sqrt(2)),
             (1000/math.sqrt(2), -1000/math.sqrt(2))]
    try:
        baseline = choose_second(station, bearing_deg, grid_step_m=baseline_grid_step_m,
                                 move_budget_m=move_budget_m, error_deg=error_deg)
        q0 = baseline["selected"]["local_xy_m"]
        seeds += [tuple(q0), (q0[0], -q0[1])]
    except ValueError:
        baseline = None

    def allowed(q):
        return (math.hypot(*q) <= maximum_radius+EPS and
                guaranteed_reception(q, error_deg) and direction_clearance(q, error_deg) > 5+EPS)

    def grid(start, end, step):
        return [start+i*step for i in range(max(0, math.floor((end-start)/step+1e-8)+1))]

    for level, (r_step, beta_step, scan_step) in enumerate(stages):
        if best is None:
            radii = grid(r_step, maximum_radius, r_step)+[maximum_radius]
            betas = grid(-90., 90., beta_step)
        else:
            a, b = best["local_xy_m"]
            r0, beta0 = math.hypot(a, b), math.degrees(math.atan2(b, a))
            radii = grid(max(r_step, r0-last_r_step), min(maximum_radius, r0+last_r_step), r_step)+[r0]
            betas = []
            for center in (beta0, -beta0):
                betas += grid(center-last_beta_step, center+last_beta_step, beta_step)+[center]
        current = {key: value for key, value in visited.items()}  # 保留旧候选供下一层共同评分。
        for q in seeds:
            if allowed(q):
                current[tuple(round(x, 8) for x in q)] = q
        for beta in betas:
            # 四圆盘比队友三圆盘多出约 0~5 米薄层；显式加入安全边界避免漏搜。
            for r in radii+[safe_radial_limit(beta, error_deg, move_budget_m)]:
                t = math.radians(beta)
                q = (r*math.cos(t), r*math.sin(t))
                if allowed(q):
                    current[tuple(round(x, 8) for x in q)] = q
        if not current:
            raise ValueError("当前搜索没有保证正常示向度的候选；增加预算或减小网格")
        evaluator = ContinuousDiameterEvaluator(polygon, error_deg, scan_step)
        rows = [_candidate_row(q, station, bearing_deg, evaluator) for q in current.values()]
        best = min(rows, key=_score_key)
        visited.update(current)
        history.append({"level": level+1, "candidate_count": len(rows),
                        "radial_step_m": r_step, "azimuth_step_deg": beta_step,
                        "angle_step_deg": evaluator.step,
                        "selected_local_xy_m": best["local_xy_m"],
                        "diameter_upper_bound_m": best["diameter_upper_bound_m"]})
        if progress:
            progress(f"第 {level+1} 层 {len(rows)} 个候选，上界 {best['diameter_upper_bound_m']:.3f} 米")
        last_r_step, last_beta_step = r_step, beta_step
    evaluator = ContinuousDiameterEvaluator(polygon, error_deg, final_angle_step_deg)
    candidates = sorted((_candidate_row(q, station, bearing_deg, evaluator) for q in visited.values()), key=_score_key)
    selected = candidates[0]
    threshold = selected["diameter_upper_bound_m"]*(1+tolerance)
    shortlist = [q for q in candidates if q["diameter_upper_bound_m"] <= threshold+EPS]
    fastest = min(shortlist, key=lambda q: (q["move_distance_m"], _score_key(q)))
    # 在同一有限集合和同一评分精度下给出非劣的时间/直径代表点。
    pareto, best_bound = [], math.inf
    for q in sorted(candidates, key=lambda row: (row["move_distance_m"], _score_key(row))):
        if q["diameter_upper_bound_m"] < best_bound-1e-7:
            pareto.append(q)
            best_bound = q["diameter_upper_bound_m"]
    if progress:
        progress(f"统一精度复核 {len(candidates)} 个候选，上界 {selected['diameter_upper_bound_m']:.3f} 米")
    return {"method": "four_disk_target_conditioned_continuous_minimax_upper_bound",
            "data_provenance": "自建示例/用户输入；不是官方模拟器测试数据",
            "first_station_xy_m": list(station), "first_bearing_deg": bearing_deg % 360,
            "error_deg": error_deg, "move_budget_m": move_budget_m,
            "grid_step_m": baseline_grid_step_m, "near_best_tolerance": tolerance,
            "guaranteed_reception": True, "guaranteed_direction": True,
            "optimization_scope": "已访问有限候选集、统一精度下的保证上界最小；未证明连续域全局最优",
            "continuous_candidate_region": "四圆盘交集 ∩ 移动预算圆 ∩ {到首扇形垂距>5} ∩ {min(D_strip,B_geometry)<=threshold}",
            "candidate_threshold_m": threshold, "selected": selected,
            "fastest_near_best": fastest, "pareto_frontier": pareto,
            "safe_finite_bound_grid_count": len(candidates), "near_best_grid_count": len(shortlist),
            "shortlist": shortlist, "search_history": history,
            "circle_sides": circle_sides, "final_angle_step_deg": evaluator.step,
            "widened_error_deg": evaluator.widened_error,
            "first_outer_polygon_local_xy_m": [list(p) for p in polygon],
            "baseline_analytic_selected": baseline["selected"] if baseline else None,
            "numerical_note": "圆外包和半步增宽保证连续集合包含；双精度容差计算，不是区间算术认证"}


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
    prior=plan.get("first_outer_polygon_local_xy_m", [(0.,0.),(1500*math.cos(e),1500*math.sin(e)),(1500*math.cos(e),-1500*math.sin(e))])
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
        f'<text x="50" y="800" class="small">Selected: ({a:.2f}, {b:.2f}) m | uniform diameter bound: {bound:.2f} m | movement: {plan["selected"]["move_distance_m"]:.2f} m.</text>',
        '<text x="50" y="822" class="small">Blue dots are visited candidates, not an exact region boundary. The 1800 m target disk constrains the source only.</text>',
        '</svg>'])
    path.write_text("\n".join(parts), encoding="utf-8")


def run_example(config: dict, output_dir: Path) -> dict:
    first = tuple(map(float, config["first_station_xy_m"]))
    first_bearing = float(config["first_bearing_deg"])
    mode = config.get("selection_mode", "refined")
    common = {"move_budget_m": float(config.get("move_budget_m", 1100)),
              "tolerance": float(config.get("near_best_tolerance", .10)),
              "error_deg": float(config.get("error_deg", 1.))}
    if mode == "analytic":
        plan = choose_second(first, first_bearing,
                             grid_step_m=float(config.get("grid_step_m", 10)), **common)
    elif mode == "refined":
        plan = choose_second_refined(first, first_bearing, **common,
                                     baseline_grid_step_m=float(config.get("grid_step_m", 10)),
                                     circle_sides=int(config.get("circle_sides", 360)),
                                     stages=tuple(tuple(s) for s in config.get("search_stages", ((100., 5., 1.), (20., 1., .5), (5., .25, .25)))),
                                     final_angle_step_deg=float(config.get("final_angle_step_deg", .1)))
    else:
        raise ValueError("selection_mode 必须为 refined 或 analytic")
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
        if abs(angular_error(first_bearing,bearing(source,first))) > common["error_deg"]+EPS or abs(err) > common["error_deg"]:
            raise ValueError("自建读数误差超出 ±1 度")
        if distance(source,second) > radius+EPS:
            raise AssertionError("保证收信失败")
        if distance(source,second) <= 5:
            plan["synthetic_observation"]={"status":"near","source_xy_m":list(source),"action":"直接光学定位与清除"}
        else:
            second_bearing=(bearing(source,second)+err)%360
            poly=posterior_outer_polygon(first,first_bearing,second,second_bearing,
                                          error_deg=common["error_deg"], circle_sides=plan.get("circle_sides",720))
            plan["synthetic_observation"]={
                "status":"direction","source_xy_m":list(source),"reception_radius_m":radius,
                "second_bearing_deg":second_bearing,"second_fixed_error_deg":err,
                "source_distance_from_second_m":distance(source,second),
                "posterior_outer_polygon_xy_m":[list(p) for p in poly],
                "posterior_outer_polygon_diameter_m":polygon_diameter(poly),
                "polygon_note":f"与评分共用首验外包，含首距下界的有效约束x>=5cos(error)；圆用{plan.get('circle_sides',720)}个局部相切半平面，另裁入第二扇区、接收圆与两条有效条带；未完整扣除5米近区"}
    (output_dir/"selection.json").write_text(json.dumps(plan,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
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

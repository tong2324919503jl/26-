"""问题 2 的几何保证、噪声边界和路径约定验证；不访问官方模拟器。"""
import importlib.util
import json
import math
import random
from pathlib import Path
import tempfile
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "solve.py"
spec = importlib.util.spec_from_file_location("problem2_solver", MODULE_PATH)
solve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(solve)


class SecondPointTests(unittest.TestCase):
    def assert_polygon_contains(self, polygon, point, tolerance=1e-6):
        self.assertTrue(polygon)
        for a,b in zip(polygon,polygon[1:]+polygon[:1]):
            length=solve.distance(a,b)
            if length > 1e-10:
                cross=(b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0])
                self.assertGreaterEqual(cross/length,-tolerance)

    def test_pure_transverse_move_can_lose_signal(self):
        self.assertFalse(solve.guaranteed_reception((0, 100)))
        self.assertGreater(solve.distance((0, 100), (1000, 0)), 1000)

    def test_degenerate_crossing_has_no_finite_bound(self):
        self.assertTrue(solve.guaranteed_reception((500, 0)))
        self.assertTrue(math.isinf(solve.diameter_bound((500, 0))))

    def test_four_disk_receipt_on_dense_annular_sector(self):
        # 覆盖5、1000、1500米与±1度边界；半径取与第一次收信相容的最小值。
        for q in ((0, 0), (500, 800), (650, 700), (1000, 50)):
            self.assertTrue(solve.guaranteed_reception(q))
            for r in (5, 5.001, 50, 500, 999.999, 1000, 1000.001, 1200, 1500):
                for i in range(101):
                    t=math.radians(-1+0.02*i)
                    g=(r*math.cos(t), r*math.sin(t))
                    self.assertLessEqual(solve.distance(q,g),max(1000,r)+1e-8)

    def test_choice_and_rotation_equivariance(self):
        base=solve.choose_second((0,0),0,grid_step_m=25)
        shifted=solve.choose_second((100,-200),123,grid_step_m=25)
        self.assertEqual(base["selected"]["local_xy_m"],shifted["selected"]["local_xy_m"])
        q=base["selected"]["local_xy_m"]
        expected=solve.rotate_local(q,(100,-200),123)
        self.assertLess(solve.distance(expected,shifted["selected"]["xy_m"]),1e-8)

    def test_source_circle_does_not_constrain_robot(self):
        plan=solve.choose_second((2200,0),180,grid_step_m=25)
        self.assertTrue(plan["guaranteed_reception"])

    def test_impossible_first_observation_and_bad_inputs(self):
        with self.assertRaises(ValueError):
            solve.choose_second((2200,0),0)
        for kwargs in ({"grid_step_m":0},{"move_budget_m":-1},{"error_deg":0}):
            with self.assertRaises(ValueError):
                solve.choose_second((0,0),0,**kwargs)

    def test_near_best_grid_respects_budget_and_bound(self):
        p=solve.choose_second((0,0),359.5,grid_step_m=25,move_budget_m=850)
        for row in p["shortlist"]:
            self.assertLessEqual(row["move_distance_m"],850+1e-8)
            self.assertLessEqual(row["diameter_upper_bound_m"],p["candidate_threshold_m"]+1e-8)
            self.assertTrue(solve.guaranteed_reception(row["local_xy_m"]))

    def test_uniform_bound_against_exact_wedges_at_noise_extremes(self):
        # 对宽范围真实源与第二点固定误差，直接构造保守交会多边形核验。
        q=tuple(solve.choose_second((0,0),0,grid_step_m=25)["selected"]["xy_m"])
        bound=solve.diameter_bound(q)
        for r in (5.01,100,500,1000,1500):
            for first_angle in (-1,0,1):
                angle=math.radians(first_angle)
                source=(r*math.cos(angle),r*math.sin(angle))
                for noise in (-1,0,1):
                    theta=(solve.bearing(source,q)+noise)%360
                    poly=solve.posterior_outer_polygon((0,0),0,q,theta,circle_sides=720)
                    self.assertGreaterEqual(len(poly),3)
                    # 外包圆的微小放松也计入0.1米数值余量。
                    self.assertLessEqual(solve.polygon_diameter(poly),bound+0.1)
                    for a,b in zip(poly,poly[1:]+poly[:1]):
                        cross=(b[0]-a[0])*(source[1]-a[1])-(b[1]-a[1])*(source[0]-a[0])
                        self.assertGreaterEqual(cross,-1e-5)

    def test_bound_is_symmetric(self):
        for a,b in ((200,400),(500,800),(750,500)):
            self.assertEqual(solve.diameter_bound((a,b)),solve.diameter_bound((a,-b)))

    def test_translated_rotated_posterior_respects_bound(self):
        first,theta=(500.0,-400.0),123.0
        plan=solve.choose_second(first,theta,grid_step_m=25)
        q=tuple(plan["selected"]["xy_m"])
        source=solve.rotate_local((800.0,5.0),first,theta)
        bound=plan["selected"]["diameter_upper_bound_m"]
        for noise in (-1,0,1):
            theta2=(solve.bearing(source,q)+noise)%360
            poly=solve.posterior_outer_polygon(first,theta,q,theta2)
            self.assertGreaterEqual(len(poly),3)
            self.assertLessEqual(solve.polygon_diameter(poly),bound+1e-7)
            for a,b in zip(poly,poly[1:]+poly[:1]):
                cross=(b[0]-a[0])*(source[1]-a[1])-(b[1]-a[1])*(source[0]-a[0])
                self.assertGreaterEqual(cross,-1e-5)

    def test_example_is_reproducible_and_writes_parseable_outputs(self):
        config=json.loads((MODULE_PATH.parent/"examples"/"synthetic_case.json").read_text(encoding="utf-8"))
        config["grid_step_m"]=25
        config["search_stages"]=[[250,15,5]]
        config["final_angle_step_deg"]=2
        with tempfile.TemporaryDirectory() as tmp:
            result=solve.run_example(config,Path(tmp))
            reread=json.loads((Path(tmp)/"selection.json").read_text(encoding="utf-8"))
            self.assertEqual(result,reread)
            obs=result["synthetic_observation"]
            self.assertLess(obs["posterior_outer_polygon_diameter_m"],result["selected"]["diameter_upper_bound_m"])
            self.assertTrue((Path(tmp)/"second_point_candidates.csv").is_file())
            import xml.etree.ElementTree as ET
            ET.parse(Path(tmp)/"candidate_region.svg")

    def test_four_disk_boundary_extends_teammate_three_disk_region(self):
        for beta in (10,33,45,59):
            r=solve.safe_radial_limit(beta)
            q=(r*math.cos(math.radians(beta)),r*math.sin(math.radians(beta)))
            self.assertTrue(solve.guaranteed_reception(q))
            self.assertFalse(solve.guaranteed_reception((q[0]*1.000001,q[1]*1.000001)))
        r=solve.safe_radial_limit(33)
        self.assertGreater(r,1000)
        self.assertAlmostEqual(solve.safe_radial_limit(33,move_budget_m=600),600)

    def test_conditioned_outer_prior_contains_physical_sources(self):
        # 特别覆盖目标圆边界，世界坐标不能误作局部坐标。
        first, theta=(1500.,0.),0.
        poly=solve.first_region_outer_local(first,theta,circle_sides=720)
        self.assertLessEqual(max(p[0] for p in poly),300+1e-7)
        self.assertGreater(min(p[0] for p in poly),4.99)
        for r in (5.001,25,150,299.9):
            for angle in (-1,0,1):
                t=math.radians(angle)
                source=(r*math.cos(t),r*math.sin(t))
                for a,b in zip(poly,poly[1:]+poly[:1]):
                    self.assertGreaterEqual((b[0]-a[0])*(source[1]-a[1])-(b[1]-a[1])*(source[0]-a[0]),-1e-6)

    def test_widened_cells_cover_non_grid_observations(self):
        poly=solve.first_region_outer_local((0,0),0)
        q=(800.,600.)
        evaluator=solve.ContinuousDiameterEvaluator(poly,angle_step_deg=2)
        bound=evaluator.evaluate(q)["geometric_diameter_upper_bound_m"]
        candidate=solve.prepare_candidate_region_local(poly,q)
        rng=random.Random(71023)
        for _ in range(250):
            # 任意第二读数而不只取离散噪声端点。
            theta=rng.uniform(0,360)
            exact=solve.clip_candidate_observation_local(candidate,theta)
            self.assertLessEqual(solve.polygon_diameter(exact),bound+1e-7)
            nearest=round(theta/evaluator.step)*evaluator.step
            widened=solve.clip_candidate_observation_local(candidate,nearest,evaluator.widened_error)
            self.assertLessEqual(solve.polygon_diameter(exact),solve.polygon_diameter(widened)+1e-7)
            for point in exact:
                self.assert_polygon_contains(widened,point)

    def test_refined_selection_retains_baseline_and_shorter_option(self):
        p=solve.choose_second_refined((0,0),0,stages=((250,15,5),),final_angle_step_deg=2,
                                     baseline_grid_step_m=25)
        q=p["selected"]["local_xy_m"]
        self.assertTrue(solve.guaranteed_reception(q))
        self.assertGreater(solve.direction_clearance(q),5)
        evaluator=solve.ContinuousDiameterEvaluator(solve.first_region_outer_local((0,0),0),angle_step_deg=2)
        baseline=solve._candidate_row(tuple(p["baseline_analytic_selected"]["local_xy_m"]),(0,0),0,evaluator)
        self.assertLessEqual(p["selected"]["diameter_upper_bound_m"],baseline["diameter_upper_bound_m"]+1e-7)
        self.assertLessEqual(p["fastest_near_best"]["diameter_upper_bound_m"],p["candidate_threshold_m"]+1e-7)
        self.assertLessEqual(p["fastest_near_best"]["move_distance_m"],p["selected"]["move_distance_m"]+1e-7)
        self.assertGreater(len(p["pareto_frontier"]),1)

    def test_boundary_conditioning_changes_selection_and_allows_robot_outside(self):
        p=solve.choose_second_refined((1500,0),0,stages=((250,15,5),(50,3,2)),final_angle_step_deg=1)
        evaluator=solve.ContinuousDiameterEvaluator(solve.first_region_outer_local((1500,0),0),angle_step_deg=1)
        baseline=evaluator.evaluate((750.,660.))["geometric_diameter_upper_bound_m"]
        self.assertLess(p["selected"]["diameter_upper_bound_m"],baseline)
        self.assertLess(p["selected"]["move_distance_m"],600)
        outside=solve.choose_second_refined((2200,0),180,stages=((250,15,5),),final_angle_step_deg=2)
        self.assertTrue(outside["guaranteed_reception"])

    def test_refined_input_rejects_invalid_precision_and_stages(self):
        for kwargs in ({"circle_sides":3},{"stages":()}, {"stages":((1,-1,1),)},
                       {"final_angle_step_deg":0}, {"move_budget_m":float("nan")}):
            with self.assertRaises(ValueError):
                solve.choose_second_refined((0,0),0,**kwargs)

    def test_clipping_tolerance_does_not_extrapolate_vertices(self):
        poly=[(0,9e-10),(1,1.1e-9),(1,1),(0,1)]
        clipped=solve.clip_polygon(poly,(0,1),0)
        self.assertTrue(clipped)
        for x,y in clipped:
            self.assertGreaterEqual(x,0)
            self.assertLessEqual(x,1)
            self.assertLessEqual(y,solve.EPS+1e-16)

    def test_thin_boundary_posterior_uses_same_first_distance_lower_bound(self):
        for x,source_x in ((1794.,1799.5),(1794.9,1799.95)):
            first=(x,0.)
            p=solve.choose_second_refined(first,0,stages=((100,30,10),),
                                          final_angle_step_deg=1,baseline_grid_step_m=50)
            q=tuple(p["selected"]["xy_m"])
            theta=solve.bearing((source_x,0.),q)
            poly=solve.posterior_outer_polygon(first,0,q,theta,circle_sides=p["circle_sides"])
            self.assertLessEqual(solve.polygon_diameter(poly),p["selected"]["diameter_upper_bound_m"]+1e-7)
            self.assertGreaterEqual(min(v[0] for v in poly),x+5*math.cos(math.radians(1))-1e-7)

    def test_analytic_cap_short_circuit_equals_full_capped_score(self):
        ev=solve.ContinuousDiameterEvaluator(solve.first_region_outer_local((0,0),0),angle_step_deg=5)
        q=(750.,660.)
        capped=solve._candidate_row(q,(0,0),0,ev,early_stop=True)
        full=solve._candidate_row(q,(0,0),0,ev,early_stop=False)
        self.assertTrue(capped["early_stopped"])
        self.assertEqual(capped["diameter_upper_bound_m"],full["diameter_upper_bound_m"])
        self.assertEqual(capped["diameter_upper_bound_m"],solve.diameter_bound(q))
        self.assertLess(capped["scanned_cells"],capped["total_cells"])
        self.assertIsNone(capped["geometric_diameter_upper_bound_m"])
        self.assertIsNone(capped["worst_cell_center_local_deg"])
        self.assertIsNone(capped["worst_cell_outer_polygon_local_xy_m"])
        self.assertFalse(capped["geometric_scan_complete"])
        self.assertEqual(capped["stop_reason"],"analytic_cap_reached")
        self.assertTrue(capped["score_exact_for_capped_objective"])
        self.assertGreaterEqual(capped["geometric_max_lower_bound_m"],capped["analytic_diameter_upper_bound_m"])
        self.assertLessEqual(capped["geometric_max_lower_bound_m"],full["geometric_diameter_upper_bound_m"])

    def test_large_or_infinite_analytic_cap_does_not_stop(self):
        ev=solve.ContinuousDiameterEvaluator(solve.first_region_outer_local((0,0),0),angle_step_deg=5)
        for q in ((100.,100.),(500.,0.)):
            result=solve._candidate_row(q,(0,0),0,ev)
            self.assertFalse(result["early_stopped"])
            self.assertEqual(result["scanned_cells"],result["total_cells"])
            self.assertEqual(result["diameter_upper_bound_m"],result["geometric_diameter_upper_bound_m"])
        self.assertIsNone(solve._candidate_row((500.,0.),(0,0),0,ev)["analytic_diameter_upper_bound_m"])

    def test_cap_equality_boundary_stops_without_tolerance_shift(self):
        ev=solve.ContinuousDiameterEvaluator(solve.first_region_outer_local((0,0),0),angle_step_deg=5)
        q=(750.,660.)
        full=ev.evaluate(q,early_stop=False)
        cap=full["geometric_diameter_upper_bound_m"]
        equal=ev.evaluate(q,analytic_cap_m=cap)
        self.assertTrue(equal["early_stopped"])
        self.assertEqual(equal["geometric_max_lower_bound_m"],cap)
        self.assertEqual(equal["capped_diameter_upper_bound_m"],cap)
        above=ev.evaluate(q,analytic_cap_m=math.nextafter(cap,math.inf))
        self.assertFalse(above["early_stopped"])
        self.assertEqual(above["capped_diameter_upper_bound_m"],cap)
        zero=ev.evaluate(q,analytic_cap_m=0.)
        self.assertTrue(zero["early_stopped"])
        self.assertEqual(zero["capped_diameter_upper_bound_m"],0.)

    def test_search_recommendation_and_candidate_order_match_full_scan(self):
        options={"stages":((250,15,5),(100,5,2)),"final_angle_step_deg":2,
                 "baseline_grid_step_m":25}
        for first in ((0.,0.),(1500.,0.)):
            short=solve.choose_second_refined(first,0,early_stop=True,**options)
            full=solve.choose_second_refined(first,0,early_stop=False,**options)
            self.assertEqual(short["selected"]["local_xy_m"],full["selected"]["local_xy_m"])
            self.assertEqual(short["selected"]["diameter_upper_bound_m"],full["selected"]["diameter_upper_bound_m"])
            self.assertEqual(short["safe_finite_bound_grid_count"],full["safe_finite_bound_grid_count"])
            rows=lambda p:[(r["local_xy_m"],r["diameter_upper_bound_m"]) for r in p["shortlist"]]
            self.assertEqual(rows(short),rows(full))
            self.assertEqual(short["fastest_near_best"]["local_xy_m"],full["fastest_near_best"]["local_xy_m"])
            self.assertEqual(full["scan_statistics"]["overall"]["early_stopped_candidates"],0)
        self.assertGreater(solve.choose_second_refined((0,0),0,**options)["scan_statistics"]["overall"]["early_stopped_candidates"],0)

    def test_actual_posterior_uses_shared_candidate_geometry(self):
        first,theta=(500.,-400.),123.
        q_local=(750.,660.)
        second=solve.rotate_local(q_local,first,theta)
        source=solve.rotate_local((800.,5.),first,theta)
        theta2=solve.bearing(source,second)+.4
        prior=solve.first_region_outer_local(first,theta,circle_sides=180)
        candidate=solve.prepare_candidate_region_local(prior,q_local,circle_sides=180)
        local=solve.clip_candidate_observation_local(candidate,theta2-theta)
        actual=solve.posterior_outer_polygon(first,theta,second,theta2,circle_sides=180)
        self.assertEqual(len(local),len(actual))
        for a,b in zip(local,actual):
            self.assertLess(solve.distance(solve.rotate_local(a,first,theta),b),1e-8)
        self.assert_polygon_contains(actual,source)

    def test_circle_outer_relaxation_and_half_cell_endpoints_are_covered(self):
        # 极粗外切圆放松必须进入条带增宽，不能仅替换 sin(error)。
        q=(500.,400.)
        prior=solve.first_region_outer_local((0,0),0,circle_sides=8)
        candidate=solve.prepare_candidate_region_local(prior,q,circle_sides=8)
        theta=337.917140935712
        exact=solve.clip_candidate_observation_local(candidate,theta)
        widened=solve.clip_candidate_observation_local(candidate,theta+1.,2.)
        self.assertTrue(exact)
        for p in exact:
            self.assert_polygon_contains(widened,p)
        # 包括跨零和不整除360°的步长，使用实际h而不是输入近似。
        ev=solve.ContinuousDiameterEvaluator(prior,angle_step_deg=7.,circle_sides=8)
        bound=ev.evaluate(q)["geometric_diameter_upper_bound_m"]
        for center in (0.,ev.step,51*ev.step):
            for sign in (-1,1):
                angle=center+sign*ev.step/2
                actual=solve.clip_candidate_observation_local(candidate,angle)
                cell=solve.clip_candidate_observation_local(candidate,center,ev.widened_error)
                self.assertLessEqual(solve.polygon_diameter(actual),bound+1e-7)
                for p in actual:
                    self.assert_polygon_contains(cell,p)

    def test_near_projection_lower_bound_widens_with_angle(self):
        q=(500.,0.)
        candidate=solve.prepare_candidate_region_local(solve.first_region_outer_local((0,0),0),q)
        # 真距恰为5的闭包边界，实际读数+1度，增宽cell中心再+1度。
        source=(505.,0.)
        exact=solve.clip_candidate_observation_local(candidate,1.)
        cell=solve.clip_candidate_observation_local(candidate,2.,2.)
        self.assert_polygon_contains(exact,source)
        self.assert_polygon_contains(cell,source)
        for p in exact:
            self.assert_polygon_contains(cell,p)

    def test_early_stop_input_validation_and_example_switch(self):
        ev=solve.ContinuousDiameterEvaluator(solve.first_region_outer_local((0,0),0),angle_step_deg=5)
        for cap in (-1.,float("nan"),-math.inf):
            with self.assertRaises(ValueError):
                ev.evaluate((750,660),analytic_cap_m=cap)
        with self.assertRaises(ValueError):
            solve.choose_second_refined((0,0),0,early_stop="false")
        config={"first_station_xy_m":[0,0],"first_bearing_deg":0,
                "search_stages":[[250,15,5]],"final_angle_step_deg":5,"early_stop":False}
        with tempfile.TemporaryDirectory() as tmp:
            result=solve.run_example(config,Path(tmp))
            self.assertFalse(result["early_stop_enabled"])
            self.assertEqual(result["scan_statistics"]["overall"]["early_stopped_candidates"],0)


if __name__ == "__main__":
    unittest.main()

"""问题 2 的几何保证、噪声边界和路径约定验证；不访问官方模拟器。"""
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "solve.py"
spec = importlib.util.spec_from_file_location("problem2_solver", MODULE_PATH)
solve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(solve)


class SecondPointTests(unittest.TestCase):
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
        with tempfile.TemporaryDirectory() as tmp:
            result=solve.run_example(config,Path(tmp))
            reread=json.loads((Path(tmp)/"selection.json").read_text(encoding="utf-8"))
            self.assertEqual(result,reread)
            obs=result["synthetic_observation"]
            self.assertLess(obs["posterior_outer_polygon_diameter_m"],result["selected"]["diameter_upper_bound_m"])
            self.assertTrue((Path(tmp)/"second_point_candidates.csv").is_file())
            import xml.etree.ElementTree as ET
            ET.parse(Path(tmp)/"candidate_region.svg")


if __name__ == "__main__":
    unittest.main()

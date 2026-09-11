"""Version-2 public-interface integration and matched-comparison semantics."""
from __future__ import annotations

import math
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from problem3.scenarios import generate_case
from problem3.simulator import LocalSimulator, ObservationClient
from problem4.coverage import static_coverage_points
from problem4.legacy_policy import SearchPolicy as LegacyPolicy
from problem4.policy import SearchPolicy
from problem4.speed_policy import SearchPolicy as SpeedPolicy
from scripts.benchmark_search import get_policy, run_case


def _near_origin_case(count):
    # Public physical edge case, independent of held-out benchmark suites.
    sources = [dict(channel=1, x=-1.0, y=0.0, radius=1000.0, orientation_deg=0.0)]
    sources += [dict(channel=i, x=math.cos(i), y=math.sin(i), radius=1000.0,
                     orientation_deg=None) for i in range(2, count + 1)]
    return dict(case_id=f"integration_near_origin_{count}", problem=4,
                seed=991237 + count, split="unit", family="close_pairs",
                noise="extreme", sources=sources)


class Version2IntegrationTests(unittest.TestCase):
    def test_previous_and_legacy_entry_points_keep_distinct_layouts(self):
        self.assertEqual(get_policy(4, "previous").coverage_points(), static_coverage_points())
        self.assertIsInstance(get_policy(4, "legacy"), LegacyPolicy)
        self.assertNotIsInstance(get_policy(4, "legacy"), SearchPolicy)
        self.assertEqual(len(get_policy(4, "legacy").coverage_points()), 25)
        self.assertEqual(len(get_policy(4, "baseline").coverage_points()), 31)
        self.assertEqual(len(get_policy(4, "optical").coverage_points()), 25)
        with self.assertRaises(ValueError):
            get_policy(3, "legacy")

    def test_default_entry_selects_the_speed_version(self):
        policy = get_policy(4, "adaptive")
        self.assertIsInstance(policy, SpeedPolicy)
        self.assertEqual(policy.algorithm_version, "problem4_v4")
        self.assertEqual(len(policy.coverage_points()), 22)
        row, _ = run_case(_near_origin_case(16))
        self.assertEqual(row["algorithm_version"], "problem4_v4")
        self.assertEqual(row["policy"]["algorithm_version"], "problem4_v4")
        self.assertTrue(row["certified_full_clear"])
        self.assertFalse(row["coverage_complete"])
        self.assertEqual(row["policy"]["termination_reason"], "maximum_source_count_cleared")

    def test_legacy_alias_replays_the_original_policy_actions(self):
        case = generate_case(4, 2, "development_v2")
        alias, alias_events = run_case(case, "legacy", record=True)
        sim = LocalSimulator(case, record=True)
        sim.enter()
        LegacyPolicy().run(ObservationClient(sim))
        sim.exit()

        def physical_trace(events):
            return [(event["action"], event["position"], event["channel"],
                     {k: v for k, v in event["response"].items() if k != "real_timestamp_ms"})
                    for event in events]

        self.assertEqual(alias["strategy"], "legacy")
        self.assertEqual(alias["algorithm_version"], "problem4_v1")
        self.assertEqual(alias["policy"]["algorithm_version"], "problem4_v1")
        self.assertEqual(physical_trace(alias_events), physical_trace(sim.events))
        self.assertEqual(alias["virtual_time_s"], sim.virtual_time_s)

    def test_sixteen_successful_clears_certify_early_exit_without_fake_coverage(self):
        row, _ = run_case(_near_origin_case(16), "previous")
        self.assertIsNone(row["error"])
        self.assertEqual(row["cleared_count"], 16)
        self.assertTrue(row["completion_certified"])
        self.assertFalse(row["coverage_complete"])
        self.assertEqual(row["policy"]["termination_reason"], "maximum_source_count_cleared")
        self.assertLess(row["policy"]["coverage_points_visited"], 23)

    def test_sixteen_discoveries_omit_scans_but_do_not_certify_clearance(self):
        policy = SearchPolicy()
        square = [(99.0, -1.0), (101.0, -1.0), (101.0, 1.0), (99.0, 1.0)]
        policy.regions = {channel: list(square) for channel in range(1, 17)}
        policy.cleared = set(range(1, 16))
        pending = policy.coverage_points()
        retained = list(pending)
        goal = policy._route_goal(SimpleNamespace(position=(0.0, 0.0)), pending)
        self.assertEqual(goal[1:], ("clear", 16))
        self.assertEqual(pending, retained)
        self.assertFalse(policy._result("not_finished", False)["completion_certified"])

    def test_ten_early_clears_still_pay_for_complete_unknown_channel_search(self):
        row, _ = run_case(_near_origin_case(10), "previous")
        self.assertIsNone(row["error"])
        self.assertEqual(row["cleared_count"], 10)
        self.assertTrue(row["coverage_complete"])
        self.assertEqual(row["policy"]["coverage_points_visited"], 23)
        self.assertGreater(row["virtual_time_s"], row["last_clear_time_s"] + 1000)
        self.assertAlmostEqual(row["average_clear_time_s"], row["virtual_time_s"] / 10)
        self.assertEqual(row["algorithm_version"], "problem4_v2")
        self.assertEqual(row["policy"]["algorithm_version"], "problem4_v2")

    def test_fast_uncertified_exit_does_not_earn_a_threshold_reward(self):
        class UncertifiedPolicy:
            def run(self, client):
                for channel in range(1, 11):
                    client.clear((0.0, 0.0), channel)
                return {"cleared_channels": list(range(1, 11)), "coverage_complete": False,
                        "completion_certified": False, "termination_reason": "insufficient_evidence"}

        with patch("scripts.benchmark_search.get_policy", return_value=UncertifiedPolicy()):
            row, _ = run_case(_near_origin_case(10))
        self.assertEqual(row["cleared_count"], 10)
        self.assertLess(row["virtual_time_s"], 100)
        self.assertFalse(row["certified_full_clear"])
        self.assertFalse(row["threshold_passed"])
        self.assertLessEqual(row["reward"], -1000000)


if __name__ == "__main__":
    unittest.main()

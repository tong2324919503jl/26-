"""Checks for production promotion and public-state safety of speed planning."""
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

from problem3.geometry import certified_covering_radius, contains
from problem3.scenarios import generate_case
from problem3.simulator import LocalSimulator, ObservationClient
from problem3.speed_policy import SearchPolicy


ROOT = Path(__file__).resolve().parents[2]


class SpeedPolicyTests(unittest.TestCase):
    def test_negative_constraints_keep_actual_sources_in_difficult_cases(self):
        # Truth is available only to this external audit, never to the policy.
        for index in range(8):
            case = generate_case(3, index, 'development_v3')
            truth = {s['channel']: (s['x'], s['y']) for s in case['sources']}

            class AuditedPolicy(SearchPolicy):
                def _measure(policy, client, point, channel):
                    result = super()._measure(client, point, channel)
                    for ch, region in policy.regions.items():
                        if ch not in policy.cleared:
                            self.assertTrue(contains(region, truth[ch]), (index, ch))
                    return result

            sim = LocalSimulator(case)
            sim.enter()
            policy = AuditedPolicy()
            result = policy.run(ObservationClient(sim))
            sim.exit()
            self.assertTrue(result['completion_certified'])
            self.assertEqual(len(policy.cleared), len(truth))

    def test_both_ring_geometries_cover_continuous_target_disk(self):
        self.assertLess(certified_covering_radius(SearchPolicy().coverage_points()), 1000.)
        for phase in (0., .013, .19):
            ring = [(0., 0.)] + [(1700. * math.cos(phase + i * math.tau / 9),
                                 1700. * math.sin(phase + i * math.tau / 9)) for i in range(9)]
            self.assertLess(certified_covering_radius(ring), 1000.)

    def test_omni_negative_policy_rejects_directional_problem(self):
        with self.assertRaises(ValueError):
            SearchPolicy(problem=4)

    def test_production_imports_do_not_load_experiments(self):
        code = """
import sys, json
from problem3.speed_policy import SearchPolicy as P3
from problem4.speed_policy import SearchPolicy as P4
P3(); P4()
print(json.dumps([name for name in sys.modules if '.experiments' in name]))
"""
        done = subprocess.run([sys.executable, '-c', code], cwd=ROOT,
                              capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(done.stdout), [])


if __name__ == '__main__':
    unittest.main()

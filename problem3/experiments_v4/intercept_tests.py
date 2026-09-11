"""Pending-station invariants for a real-discovery interruption."""
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from problem3.experiments_v4.intercept import InterceptMixin


class FakeBase:
    def __init__(self, discover):
        self.discover = discover
        self.coverage_visited = [(0., 0.)]
        self.regions, self.cleared, self.stats = {}, set(), {}
        self._annular_decision = True

    def _route_goal(self, client, pending):
        return pending[0], 'scan', 0

    def _scan(self, client, point):
        self.coverage_visited.append(point)
        client.position = point
        if self.discover:
            self.regions[1] = [(1200., 100.)]


class FakePolicy(InterceptMixin, FakeBase):
    def _intercept_gain(self, point):
        return .2


class InterceptTests(unittest.TestCase):
    def simulate(self, discover, enabled=True, annular=True):
        policy = FakePolicy(discover)
        policy.intercept_enabled = enabled
        policy._annular_decision = annular
        client = SimpleNamespace(position=(1600., 0.))
        target, other = (-1200., 1000.), (-1700., 0.)
        pending = [target, other]
        _, _, index = policy._route_goal(client, pending)
        policy._scan(client, pending.pop(index))
        return policy, pending, target, other

    def test_discovery_restores_unvisited_target(self):
        policy, pending, target, other = self.simulate(True)
        self.assertEqual(pending, [target, other])
        self.assertNotIn(target, policy.coverage_visited)
        self.assertEqual(policy.stats['intercept_restored_stations'], 1)
        self.assertEqual(len(policy.coverage_visited), 2)

    def test_no_discovery_reaches_actual_target(self):
        policy, pending, target, other = self.simulate(False)
        self.assertEqual(pending, [other])
        self.assertEqual(policy.coverage_visited[-1], target)
        self.assertEqual(len(policy.coverage_visited), 3)
        self.assertNotIn('intercept_replans', policy.stats)

    def test_inactive_controls_have_no_midway_scan(self):
        for enabled, annular in ((False, True), (True, False)):
            policy, pending, target, other = self.simulate(True, enabled, annular)
            self.assertEqual(pending, [other])
            self.assertEqual(policy.coverage_visited, [(0., 0.), target])
            self.assertEqual(policy.stats, {})


if __name__ == '__main__':
    unittest.main()

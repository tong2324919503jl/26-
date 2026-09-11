"""Replay a legal current-default counterexample; no large audit-file dependency."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest

from problem3.simulator import LocalSimulator, ObservationClient


@unittest.skipUnless(importlib.util.find_spec('numpy') is not None,
                     'Optional probability-stop experiment requires NumPy')
class ProbabilityCounterexampleTests(unittest.TestCase):
    def test_nominal_exit_has_indistinguishable_legal_miss_but_v4_clears_all(self):
        from problem3.probability_stop import make_policy
        from problem4.speed_policy import SearchPolicy

        path = Path(__file__).resolve().parents[1]/'examples/probability_stop_counterexample.json'
        augmented = json.loads(path.read_text(encoding='utf-8'))
        original = copy.deepcopy(augmented)
        added_channel = original['counterexample']['added_source_channel']
        original['sources'] = [source for source in original['sources']
                               if source['channel'] != added_channel]
        self.assertEqual(len(original['sources']), 10)
        self.assertEqual(len(augmented['sources']), 11)
        self.assertEqual(original['seed'], augmented['seed'])

        def execute(case, policy):
            sim = LocalSimulator(case, record=True)
            sim.enter()
            result = policy.run(ObservationClient(sim))
            sim.exit()
            return result, sim

        runs = [execute(case, make_policy(4, probability_mode='nominal',
                                         threshold=.99, particles=131072))
                for case in (original, augmented)]
        for result, sim in runs:
            self.assertEqual(result['termination_reason'], 'experimental_probability_threshold')
            self.assertFalse(result['completion_certified'])
            self.assertFalse(result['coverage_complete'])
            self.assertGreaterEqual(result['probability_estimate']['nominal'], .99)
            self.assertEqual(len(sim.cleared), 10)
            self.assertFalse(sim.active)

        def public_trace(sim):
            return [(event['action'], event['channel'], event['position'],
                     {key: value for key, value in event['response'].items()
                      if key != 'real_timestamp_ms'}) for event in sim.events]

        self.assertEqual(len(runs[0][1].events), 310)
        self.assertEqual(public_trace(runs[0][1]), public_trace(runs[1][1]))
        self.assertEqual(runs[1][1].statistics()['source_count'], 11)
        self.assertNotIn(added_channel, runs[1][1].cleared)

        safe_result, safe = execute(augmented, SearchPolicy())
        self.assertTrue(safe_result['completion_certified'])
        self.assertEqual(len(safe.cleared), 11)
        self.assertIn(added_channel, safe.cleared)


if __name__ == '__main__': unittest.main()

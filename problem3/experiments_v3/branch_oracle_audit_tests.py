"""Independent small arithmetic tests for the read-only branch-pool audit."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from problem3.experiments_v3.branch_oracle_audit import PREFIX, containers, normalize, scope


class BranchAuditTests(unittest.TestCase):
    def valid_row(self):
        sim = dict(source_count=10, cleared_count=10, movement_m=1500., measure=20,
                   switch=19, failed_clear=2, clear=12, virtual_time_s=475.,
                   average_clear_time_s=47.5)
        return dict(id=PREFIX+'0000', sim=sim, seed=3610000,
                    policy=dict(problem=3, cleared_channels=list(range(10)), completion_certified=True))

    def test_total_time_includes_failed_clear_and_switch(self):
        row, error = normalize(self.valid_row())
        self.assertIsNone(error)
        self.assertEqual(row['average_s'], 47.5)

    def test_invalid_cost_incomplete_and_foreign_problem_rejected(self):
        row = self.valid_row()
        row['sim']['virtual_time_s'] += 1
        row['sim']['average_clear_time_s'] += .1
        self.assertEqual(normalize(row)[1], 'physical_cost_mismatch')
        row = self.valid_row()
        row['sim']['cleared_count'] = 9
        self.assertEqual(normalize(row)[1], 'not_full_clear')
        row = self.valid_row()
        row['policy']['problem'] = 4
        self.assertEqual(normalize(row)[1], 'not_p3_policy')
        row = self.valid_row()
        row['id'] = 'local_p3_holdout_v3_0000'
        self.assertEqual(normalize(row)[1], 'not_development_v2_case')

    def test_both_result_row_schemas_found_once(self):
        data = dict(a=dict(result=dict(rows=[self.valid_row()])), b=dict(episodes=[dict(case_id=PREFIX+'0001')]))
        found = list(containers(data))
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0][0], ('a', 'result', 'rows'))

    def test_paired_oracle_dedup_and_public_gate_arithmetic(self):
        def branch(name, costs):
            return dict(name=name, cases=len(costs), rows=[dict(case_id=f'{PREFIX}{i:04d}', source_count=10,
                        average_s=cost, time_s=10*cost) for i, cost in enumerate(costs)])
        choices = [branch('A', [300., 100.]), branch('B', [100., 300.]),
                   branch('A_duplicate', [300., 100.]), branch('incomplete', [50.])]
        result = scope(choices, 2, {PREFIX+'0000':True, PREFIX+'0001':False})
        self.assertEqual(result['eligible_run_records'], 3)
        self.assertEqual(result['unique_time_vectors'], 2)
        self.assertEqual(result['best_fixed_mean_s'], 200.)
        self.assertEqual(result['oracle_mean_s'], 100.)
        self.assertEqual(result['oracle_weighted_s'], 100.)
        self.assertEqual(result['greedy_portfolio'][1]['mean_s'], 100.)
        self.assertEqual(result['public_origin_empty_gate']['mean_s'], 100.)
        self.assertTrue(result['public_origin_empty_gate']['fitted_and_scored_on_same_data'])


if __name__ == '__main__':
    unittest.main()

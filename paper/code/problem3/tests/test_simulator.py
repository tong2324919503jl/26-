import math
import unittest

from problem3.simulator import LocalSimulator, ObservationClient
from problem3.scenarios import generate_case


def scene(sources, noise='extreme'):
    return dict(seed=77, noise=noise, sources=sources)


class SimulatorTests(unittest.TestCase):
    def test_attachment_time_example(self):
        s = LocalSimulator(scene([])); s.enter()
        self.assertEqual(s.measure((300, 400), 1)['virtual_time_s'], 105)
        self.assertEqual(s.measure((300, 400), 2)['virtual_time_s'], 111)
        self.assertEqual(s.clear((300, 0), 3)['virtual_time_s'], 194)
        self.assertEqual(s.measure((300, 0), 2)['virtual_time_s'], 199)
        self.assertEqual(s.exit()['virtual_time_s'], 199)

    def test_directional_backside_and_optical(self):
        s = LocalSimulator(scene([dict(channel=1, x=0, y=0, radius=1000, orientation_deg=0)]))
        s.enter()
        self.assertEqual(s.measure((-5, 0), 1)['measure_result'], 'no_signal')
        self.assertEqual(s.measure((0, 5), 1)['measure_result'], 'near')
        self.assertEqual(s.clear((-20, 0), 1)['clear_result'], 'success')
        self.assertEqual(s.clear((-20, 0), 1)['clear_result'], 'no_target_in_range')

    def test_fixed_local_error_rounding_and_boundary(self):
        s = LocalSimulator(scene([dict(channel=2, x=800, y=.0001, radius=1000)])); s.enter()
        a = s.measure((0, 0), 2)['svd_deg']
        self.assertEqual(a, s.measure((0, 0), 2)['svd_deg'])
        truth = math.degrees(math.atan2(.0001, 800))
        self.assertLessEqual(abs((a-truth+180)%360-180), 1.0050001)
        self.assertEqual(s.measure((-201, 0), 2)['measure_result'], 'no_signal')

    def test_invalid_action_does_not_move(self):
        s = LocalSimulator(scene([])); s.enter()
        for point, channel in [((float('nan'), 0), 1), ((0, 0), True), ((2000001, 0), 1)]:
            with self.assertRaises(ValueError):
                s.measure(point, channel)
        self.assertEqual(s.position, (0, 0)); self.assertEqual(s.virtual_time_s, 0)

    def test_facade_exposes_no_case_fields(self):
        c = ObservationClient(LocalSimulator(generate_case(4)))
        self.assertFalse(hasattr(c, 'sources')); self.assertFalse(hasattr(c, 'case'))

    def test_generator_reproducible_and_disjoint(self):
        seen = set()
        for problem in (3, 4):
            for split in ('development', 'holdout', 'stress'):
                for i in range(32):
                    c = generate_case(problem, i, split)
                    self.assertEqual(c, generate_case(problem, i, split))
                    self.assertNotIn(c['seed'], seen); seen.add(c['seed'])
                    self.assertTrue(10 <= len(c['sources']) <= 16)
                    LocalSimulator(c)
                    if problem == 4:
                        count = sum(s['orientation_deg'] is not None for s in c['sources'])
                        self.assertTrue(0 < count < len(c['sources']))


if __name__ == '__main__':
    unittest.main()

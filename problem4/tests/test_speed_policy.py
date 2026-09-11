"""Independent coverage and public-feedback QA for the frozen speed policy.

Source truth is owned only by the test and simulator. The policy receives the
ObservationClient facade; the test checks its completed updates afterwards.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from problem3.scenarios import generate_case
from problem3.simulator import LocalSimulator, ObservationClient
from problem4.coverage import directional_cover_certificate
from problem4.search_layout import STATIONS_SHA256, TEAMMATE22, coverage_points
from problem4.speed_policy import SearchPolicy
from problem4.tests.test_v2_integration import _near_origin_case


EXPECTED_STATIONS_SHA256 = '7dc92616892ba34956ad4d6fb5a0ca5f619aec8161acd39c92db8189d645c8fd'


def contains_source(polygon, point, tolerance_m=3e-5):
    """Independent oriented-edge/segment check, not the policy's predicate."""
    if not polygon:
        return False
    if len(polygon) == 1:
        return math.dist(point, polygon[0]) <= tolerance_m
    if len(polygon) == 2:
        a, b = polygon
        dx, dy = b[0]-a[0], b[1]-a[1]
        squared = dx*dx + dy*dy
        fraction = max(0., min(1., ((point[0]-a[0])*dx+(point[1]-a[1])*dy)/squared)) if squared else 0.
        projection = a[0]+fraction*dx, a[1]+fraction*dy
        return math.dist(point, projection) <= tolerance_m
    signed = []
    for a, b in zip(polygon, polygon[1:]+polygon[:1]):
        dx, dy = b[0]-a[0], b[1]-a[1]
        length = math.hypot(dx, dy)
        if length:
            signed.append((dx*(point[1]-a[1])-dy*(point[0]-a[0]))/length)
    return bool(signed) and (min(signed) >= -tolerance_m or max(signed) <= tolerance_m)


def hard_cases():
    """Eight public-model unit fixtures; no hidden or pressure suite is read."""
    for index in range(8):
        case = generate_case(4, 16+index, 'development_v3')
        case['case_id'] = f'speed_v4_unit_{index}_{case["family"]}'
        case['split'] = 'unit'
        case['noise'] = 'extreme' if index < 4 else 'bias'
        for number, source in enumerate(case['sources']):
            source['radius'] = 1000.
            # Leave one omnidirectional source and make the others directional.
            if number == len(case['sources'])-1:
                source['orientation_deg'] = None
            elif case['family'] in ('boundary', 'outward'):
                source['orientation_deg'] = math.degrees(math.atan2(source['y'], source['x'])) % 360
            elif case['family'] == 'grazing':
                inward = math.degrees(math.atan2(-source['y'], -source['x']))
                source['orientation_deg'] = (inward + 90 + (1e-7 if number % 2 else -1e-7)) % 360
            elif source['orientation_deg'] is None:
                source['orientation_deg'] = (number*137.5 + index*19.) % 360
        yield case


class SpeedCoverageTests(unittest.TestCase):
    def test_frozen_coordinates_hash_and_full_continuous_certificate(self):
        points = coverage_points()
        self.assertEqual(len(points), 22)
        self.assertEqual(points[0], (0., 0.))
        self.assertEqual(len(set(points)), 22)
        self.assertEqual(STATIONS_SHA256, EXPECTED_STATIONS_SHA256)
        digest = hashlib.sha256(json.dumps(points, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        self.assertEqual(digest, EXPECTED_STATIONS_SHA256)
        report = directional_cover_certificate(points, early_exit=False, full_report=True)
        self.assertTrue(report['certified'])
        self.assertEqual(report['points_sha256'], digest)
        self.assertLess(report['max_directional_radius_bound_m'], 999.999)
        self.assertGreater(report['hull_inradius_m'], 1800.001)
        self.assertEqual(len(report['pair_details']), report['pair_checks'])
        self.assertGreater(report['pair_checks'], 400)
        # Mutating a returned working list must not alter frozen constants.
        points.pop()
        self.assertEqual(tuple(coverage_points()), TEAMMATE22)

    def test_rotations_reflections_and_six_decimal_rounding_keep_coverage(self):
        # Rotations/reflections preserve the continuous physical model. Rounding
        # is checked afresh and never inherits the unrounded point fingerprint.
        for angle_deg in (0., 17., 73., 143.):
            angle = math.radians(angle_deg)
            cosine, sine = math.cos(angle), math.sin(angle)
            for reflected in (False, True):
                transformed = []
                for x, y in TEAMMATE22:
                    if reflected:
                        x = -x
                    transformed.append((x*cosine-y*sine, x*sine+y*cosine))
                for rounded in (False, True):
                    points = [(round(x, 6), round(y, 6)) for x, y in transformed] if rounded else transformed
                    with self.subTest(angle=angle_deg, reflected=reflected, rounded=rounded):
                        report = directional_cover_certificate(points, early_exit=False)
                        self.assertTrue(report['certified'], report)
                        self.assertLess(report['max_directional_radius_bound_m'], 999.999)
                        self.assertGreater(report['hull_inradius_m'], 1800.001)

    def test_removing_a_boundary_station_is_not_certified(self):
        points = coverage_points()
        points.pop(8)
        self.assertFalse(directional_cover_certificate(points)['certified'])


class SpeedPublicObservationTests(unittest.TestCase):
    def test_eight_hard_cases_retain_every_source_after_every_measure(self):
        total_measures = total_checks = directional_negative_reads = 0
        for case in hard_cases():
            with self.subTest(case=case['case_id']):
                truth = {source['channel']: (source['x'], source['y']) for source in case['sources']}
                simulator = LocalSimulator(case)
                simulator.enter()
                client = ObservationClient(simulator)
                policy = SearchPolicy()
                original_measure = policy._measure
                counters = dict(measures=0, checks=0, negative_known=0)

                def audit_after_measure(public_client, point, channel):
                    was_known = channel in policy.regions and channel not in policy.cleared
                    outcome = original_measure(public_client, point, channel)
                    counters['measures'] += 1
                    counters['negative_known'] += bool(was_known and outcome == 'no_signal')
                    for known_channel, polygon in policy.regions.items():
                        self.assertIn(known_channel, truth)
                        self.assertTrue(contains_source(polygon, truth[known_channel]),
                                        (case['case_id'], counters['measures'], channel,
                                         outcome, known_channel, truth[known_channel], polygon))
                        counters['checks'] += 1
                    return outcome

                # Auditing stays outside the production update and never changes
                # its result, candidate geometry, route, or source priors.
                with patch.object(policy, '_measure', side_effect=audit_after_measure):
                    result = policy.run(client)
                exit_response = simulator.exit()
                self.assertTrue(exit_response['accepted'])
                self.assertTrue(result['completion_certified'])
                self.assertEqual(result['algorithm_version'], 'problem4_v4')
                self.assertEqual(simulator.cleared, set(truth))
                self.assertEqual(set(result['cleared_channels']), set(truth))
                self.assertEqual(counters['measures'], simulator.counts['measure'])
                self.assertGreater(counters['checks'], 0)
                if len(truth) < 16:
                    self.assertTrue(result['coverage_complete'])
                    self.assertEqual(result['coverage_points_visited'], 22)
                total_measures += counters['measures']
                total_checks += counters['checks']
                directional_negative_reads += counters['negative_known']
        self.assertGreater(total_measures, 1000)
        self.assertGreater(total_checks, total_measures)
        self.assertGreater(directional_negative_reads, 0)

    def test_sixteen_successes_allow_early_stop_but_ten_require_all_stations(self):
        for count in (10, 16):
            with self.subTest(count=count):
                simulator = LocalSimulator(_near_origin_case(count))
                simulator.enter()
                policy = SearchPolicy()
                result = policy.run(ObservationClient(simulator))
                self.assertTrue(simulator.exit()['accepted'])
                self.assertEqual(len(simulator.cleared), count)
                self.assertTrue(result['completion_certified'])
                if count == 16:
                    self.assertFalse(result['coverage_complete'])
                    self.assertLess(result['coverage_points_visited'], 22)
                    self.assertEqual(result['termination_reason'], 'maximum_source_count_cleared')
                else:
                    self.assertTrue(result['coverage_complete'])
                    self.assertEqual(result['coverage_points_visited'], 22)
                    self.assertEqual(result['termination_reason'], 'certified_coverage_and_all_detected_cleared')
                    self.assertGreater(simulator.virtual_time_s, simulator.clear_times[-1]+1000)

    def test_sixteen_discoveries_do_not_claim_sixteen_successes(self):
        policy = SearchPolicy()
        square = [(99., -1.), (101., -1.), (101., 1.), (99., 1.)]
        policy.regions = {channel: list(square) for channel in range(1, 17)}
        policy.cleared = set(range(1, 16))
        pending = policy.coverage_points()
        retained = list(pending)
        goal = policy._route_goal(SimpleNamespace(position=(0., 0.)), pending)
        self.assertEqual(goal[1:], ('clear', 16))
        self.assertEqual(pending, retained)
        self.assertFalse(policy._result('not_finished', False)['completion_certified'])


if __name__ == '__main__':
    unittest.main()

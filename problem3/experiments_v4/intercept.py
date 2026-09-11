"""Interrupt a scheduled coverage trip after a real midway discovery.

Adapted from the teammate third-round package, retaining AggressiveBandPolicy's
hard geometry and certified coverage. Midway scans never discharge the original
station: when discovery interrupts the trip, that already-popped station is
restored to the live pending list before control returns to the shared run loop.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from problem3.experiments_v3.optical_band import AggressiveBandPolicy
from problem3.experiments_v3.benchmark import run
from problem3.geometry import certified_covering_radius, distance
from problem3.scenarios import generate_suite


class InterceptMixin:
    intercept_enabled = True
    intercept_step_m = 450.
    intercept_min_leg_m = 1100.
    intercept_min_start_radius_m = 1100.
    intercept_min_gain = .01
    intercept_feature_radius_m = 980.
    intercept_features = tuple((float(x), float(y))
        for x in range(-1800, 1801, 300) for y in range(-1800, 1801, 300)
        if math.hypot(x, y) <= 1800.)

    def _intercept_mask(self, point):
        if not hasattr(self, '_intercept_masks'):
            self._intercept_masks = {}
        key = tuple(point)
        if key not in self._intercept_masks:
            self._intercept_masks[key] = sum(1 << i for i, source in enumerate(self.intercept_features)
                if distance(source, key) <= self.intercept_feature_radius_m)
        return self._intercept_masks[key]

    def _intercept_gain(self, point):
        seen = 0
        for previous in self.coverage_visited:
            seen |= self._intercept_mask(previous)
        return (self._intercept_mask(point) & ~seen).bit_count() / len(self.intercept_features)

    def _route_goal(self, client, pending):
        goal = super()._route_goal(client, pending)
        # Keep the actual shared list. Its selected station is popped by
        # GlobalMixin.run immediately before calling our _scan override.
        self._intercept_pending = pending
        self._intercept_scheduled = (goal[0], goal[2]) if goal[1] == 'scan' else None
        return goal

    def _scan(self, client, point):
        scheduled = getattr(self, '_intercept_scheduled', None)
        self._intercept_scheduled = None
        start = client.position
        length = distance(start, point)
        eligible = (self.intercept_enabled and scheduled is not None and scheduled[0] == point
                    and getattr(self, '_annular_decision', False)
                    and length > self.intercept_min_leg_m
                    and math.hypot(*start) > self.intercept_min_start_radius_m)
        if eligible:
            fraction = min(.55, self.intercept_step_m / length)
            midway = (start[0] + fraction * (point[0] - start[0]),
                      start[1] + fraction * (point[1] - start[1]))
            if self._intercept_gain(midway) > self.intercept_min_gain:
                known = len(set(self.regions) | self.cleared)
                super()._scan(client, midway)
                self.stats['intercept_scans'] = self.stats.get('intercept_scans', 0) + 1
                if len(set(self.regions) | self.cleared) > known:
                    pending = self._intercept_pending
                    if point in pending:
                        raise RuntimeError('Interrupted station was unexpectedly already pending')
                    pending.insert(min(scheduled[1], len(pending)), point)
                    self.stats['intercept_replans'] = self.stats.get('intercept_replans', 0) + 1
                    self.stats['intercept_restored_stations'] = self.stats.get('intercept_restored_stations', 0) + 1
                    return
        return super()._scan(client, point)

    def _result(self, reason, coverage_complete):
        result = super()._result(reason, coverage_complete)
        result['intercept_settings'] = dict(enabled=self.intercept_enabled,
            step_m=self.intercept_step_m, minimum_leg_m=self.intercept_min_leg_m,
            minimum_start_radius_m=self.intercept_min_start_radius_m,
            minimum_gain=self.intercept_min_gain)
        # Independent final geometric check uses only actual full-scan points.
        # A computation failure must not be converted into a success result.
        if coverage_complete:
            radius = certified_covering_radius(self.coverage_visited)
            result['intercept_actual_scan_cover_radius_m'] = radius
            if radius > 999.999:
                raise RuntimeError('Actual scan points do not certify full coverage')
        return result


class Intercept450Policy(InterceptMixin, AggressiveBandPolicy):
    pass


class Intercept650Policy(Intercept450Policy):
    intercept_step_m = 650.
    intercept_min_leg_m = 1400.


class InterceptDisabledPolicy(Intercept450Policy):
    intercept_enabled = False


def fingerprints():
    paths = [Path(__file__)] + sorted((ROOT / 'problem3/experiments_v3').glob('*.py'))
    paths += [ROOT / name for name in ('problem3/policy.py', 'problem3/geometry.py',
              'problem3/scenarios.py', 'problem3/simulator.py', 'problem4/routing.py')]
    return {str(path.relative_to(ROOT)).replace('\\', '/'):
            hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', type=int, default=48)
    parser.add_argument('--branches', nargs='+', choices=('baseline', 'disabled', 'intercept450', 'intercept650'),
                        default=['baseline', 'intercept450', 'intercept650'])
    args = parser.parse_args()
    classes = dict(baseline=AggressiveBandPolicy, disabled=InterceptDisabledPolicy,
                   intercept450=Intercept450Policy, intercept650=Intercept650Policy)
    split = 'development_v3'
    cases = generate_suite(3, split, args.count)
    frozen = fingerprints()
    folder = ROOT / 'problem3/results/iterations_v4'
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / f'intercept_{split}_{args.count}_{"_".join(args.branches)}.json'
    body = dict(provenance='Synthetic development_v3 only. No platform, holdout, stress, or hidden state used by policies.',
                teammate_zip_sha256='bce6c749b633275e01c20913d1b9980b4f810cf6fad57f9de58732edbe5b4332',
                dependencies=frozen, split=split, count=args.count, branches={})
    for name in args.branches:
        if fingerprints() != frozen:
            raise RuntimeError('Frozen dependencies changed before comparison')
        cls = classes[name]
        result = run(cls, cases)
        if fingerprints() != frozen:
            raise RuntimeError('Frozen dependencies changed during comparison')
        summary = {key: value for key, value in result.items() if key != 'rows'}
        summary['intercept_scans'] = sum(row['policy'].get('intercept_scans', 0) for row in result['rows'])
        summary['intercept_replans'] = sum(row['policy'].get('intercept_replans', 0) for row in result['rows'])
        if name != 'baseline' and 'baseline' in body['branches']:
            baseline = body['branches']['baseline']['result']['rows']
            unchanged = 0
            for old, new in zip(baseline, result['rows']):
                # Only the public empty-origin condition may activate this.
                if not old['policy'].get('zero_origin_geometry', {}).get('triggered') or name == 'disabled':
                    if old['sim'] != new['sim']:
                        raise AssertionError('Inactive intercept changed physical behavior')
                    unchanged += 1
            summary['inactive_identical_cases'] = unchanged
        body['branches'][name] = dict(summary=summary, result=result)
        output.write_text(json.dumps(body, indent=2) + '\n', encoding='utf-8')
        print(name, json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()

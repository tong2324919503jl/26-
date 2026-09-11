"""Paired layout-only comparison: teammate irregular 22 versus current 21.

Coordinates copied exactly from the third-round ZIP's verified certificate.
No runtime dependency on the ZIP, tmp extraction, or official platform exists.
Shared baseline, localization and route settings are identical in both arms.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from problem4.coverage import directional_cover_certificate
from problem4.experiments_v3.coverage_ring_policy import Ring12CoverPolicy
from problem4.experiments_v3.routing_shared import SharedBaselineMixin
from problem3.scenarios import generate_suite
from problem3.simulator import LocalSimulator, ObservationClient

ZIP_SHA256 = 'bce6c749b633275e01c20913d1b9980b4f810cf6fad57f9de58732edbe5b4332'
CERTIFICATE_SHA256 = '72c68e85c5a9e647ce72282c75d5fd2cd4e0b148377739ca6c5578165f6599fa'
STATIONS_SHA256 = '7dc92616892ba34956ad4d6fb5a0ca5f619aec8161acd39c92db8189d645c8fd'
TEAMMATE22 = (
    (0.0, 0.0),
    (964.5515517477214, -2.5141093794892644),
    (604.2485387606617, 754.5477667140619),
    (-159.5260349827816, 924.9346196887958),
    (-914.1877328941633, 509.18399584126234),
    (-856.1934991432322, -432.59901140364667),
    (-213.50027740515807, -935.5760263970167),
    (594.9066003037709, -756.7604700722686),
    (1849.2346331352699, 1.8477590650225735),
    (1659.0142310264234, 810.4630919605346),
    (1144.9244448947306, 1449.5079701083196),
    (399.6637278191817, 1803.6166375363737),
    (-417.831619638129, 1796.9196774699847),
    (-1141.2857152918975, 1449.3583270101292),
    (-1656.2771869163237, 821.0709009719499),
    (-1850.3826834323652, -1.92387953251106),
    (-1663.6686851876796, -804.7262455989857),
    (-1144.2173381135444, -1450.2150768895058),
    (-400.51148688420454, -1802.8512706716435),
    (415.98386057310455, -1797.6850443347153),
    (1148.4599788006628, -1445.9724362023871),
    (1660.678046388523, -807.4462863480685),
)


class SharedSettings:
    shared_min_channels = 1
    shared_radius_m = 50.
    shared_fresh_only = True


class Teammate22Layout(Ring12CoverPolicy):
    ring_point_count = 22

    def coverage_points(self):
        return list(TEAMMATE22)


class Shared21Policy(SharedSettings, SharedBaselineMixin, Ring12CoverPolicy):
    pass


class Shared22Policy(SharedSettings, SharedBaselineMixin, Teammate22Layout):
    pass


def fingerprints():
    names = ('problem4/policy.py', 'problem4/coverage.py', 'problem4/localization.py',
             'problem4/routing.py', 'problem3/geometry.py', 'problem3/policy.py',
             'problem3/scenarios.py', 'problem3/simulator.py',
             'problem4/experiments_v3/coverage_ring_policy.py',
             'problem4/experiments_v3/routing_shared.py',
             'problem4/experiments_v3/routing.py',
             'problem4/experiments_v4/teammate_cover.py')
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}


def verify():
    if hashlib.sha256(json.dumps(TEAMMATE22, separators=(',', ':')).encode()).hexdigest() != STATIONS_SHA256:
        raise AssertionError('Copied coordinates differ from the teammate certificate')
    result = {}
    for cls in (Shared21Policy, Shared22Policy):
        policy = cls()
        points = policy.coverage_points()
        if points is not policy._shared_pending:
            raise AssertionError('Shared baseline lost the live pending list')
        cert = directional_cover_certificate(points)
        if not cert['certified']:
            raise AssertionError('Layout failed independent continuous coverage proof')
        result[cls.__name__] = cert
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', type=int, default=48)
    args = parser.parse_args()
    frozen, certificates = fingerprints(), verify()
    split = 'development_v3'
    cases = generate_suite(4, split, args.count)
    folder = ROOT / 'problem4/results/iterations_v4'
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / f'teammate_cover_{split}_{args.count}.json'
    body = dict(provenance='Synthetic paired development_v3 only, not official.',
                source_zip_sha256=ZIP_SHA256, source_certificate_sha256=CERTIFICATE_SHA256,
                certificates=certificates, dependencies=frozen, branches={})
    for cls in (Shared21Policy, Shared22Policy):
        rows, started = [], time.perf_counter()
        for case in cases:
            if fingerprints() != frozen:
                raise RuntimeError('Frozen dependency changed during comparison')
            simulator = LocalSimulator(case)
            simulator.enter()
            client = ObservationClient(simulator)
            error, result, cpu = None, {}, time.perf_counter()
            try:
                result = cls().run(client)
            except Exception as exc:
                error = repr(exc)
            sim = simulator.statistics()
            full = bool(not error and result.get('completion_certified') and sim['cleared_count'] == sim['source_count'])
            rows.append(dict(case_id=case['case_id'], seed=case['seed'], family=case['family'],
                             **sim, policy=result, error=error, full=full,
                             pass400=full and sim['average_clear_time_s'] <= 400,
                             program_runtime_s=time.perf_counter()-cpu))
        summary = dict(mean=statistics.mean(row['average_clear_time_s'] or 1000000 for row in rows),
            full=sum(row['full'] for row in rows), pass400=sum(row['pass400'] for row in rows),
            movement_m=statistics.mean(row['movement_m'] for row in rows),
            actions=statistics.mean(row['actions'] for row in rows), runtime_s=time.perf_counter()-started,
            max_case_runtime_s=max(row['program_runtime_s'] for row in rows),
            failures=[(row['case_id'], row['error']) for row in rows if not row['full']])
        body['branches'][cls.__name__] = dict(summary=summary, episodes=rows)
        if fingerprints() != frozen:
            raise RuntimeError('Frozen dependency changed after comparison')
        output.write_text(json.dumps(body, indent=2) + '\n', encoding='utf-8')
        print(cls.__name__, json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()

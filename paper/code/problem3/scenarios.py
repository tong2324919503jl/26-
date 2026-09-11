"""Diverse deterministic synthetic cases; official hidden data are never used."""
from __future__ import annotations

import math
import random

FAMILIES = ('uniform', 'clusters', 'boundary', 'outward', 'corridor',
            'close_pairs', 'grazing', 'short_radius')
SPLITS = {'development': (170000, 96), 'holdout': (290000, 192), 'stress': (430000, 96),
          'development_v2': (610000, 384), 'holdout_v2': (790000, 512),
          'stress_v2': (930000, 256),
          'development_v3': (1510000, 384), 'holdout_v3': (1690000, 512),
          'stress_v3': (1830000, 256)}


def generate_case(problem: int, index: int = 0, split: str = 'development') -> dict:
    seed = SPLITS[split][0] + index + 1000000*problem
    rng = random.Random(seed)
    family = FAMILIES[index % len(FAMILIES)]
    noise = ('hash_uniform', 'spatial', 'extreme', 'bias')[(index//8) % 4]
    n = 10 + rng.randrange(7)
    stress = split.startswith('stress')
    if stress:
        # Cross each family with BOTH counts and BOTH noise modes, rather than
        # accidentally coupling a family's index parity to its difficulty.
        n = 16 if (index // 8) % 2 else 10
        noise = ('extreme', 'bias')[(index // 16) % 2]
    rotation = rng.uniform(0, 2*math.pi)
    cluster_centers = [(rng.uniform(600, 1550)*math.cos(a),
                        rng.uniform(600, 1550)*math.sin(a)) for a in
                       (rotation, rotation+2.3, rotation+4.5)]
    channels = rng.sample(range(1, 21), n)
    directional_count = rng.randint(1, n-1) if problem == 4 else 0
    if problem == 4 and stress:
        directional_count = n-1
    sources = []
    for j, ch in enumerate(channels):
        a = rng.uniform(0, 2*math.pi)
        r = 1800*math.sqrt(rng.random())
        x, y = r*math.cos(a), r*math.sin(a)
        if family in ('boundary', 'outward'):
            a = rotation + 2*math.pi*j/n + rng.uniform(-.06, .06)
            r = 1800 if stress else rng.uniform(1690, 1800)
            x, y = r*math.cos(a), r*math.sin(a)
        elif family == 'clusters':
            cx, cy = cluster_centers[j % 3]
            x, y = cx+rng.gauss(0, 70), cy+rng.gauss(0, 70)
        elif family == 'corridor':
            length, offset = rng.uniform(-1770, 1770), rng.uniform(-12, 12)
            x = length*math.cos(rotation)-offset*math.sin(rotation)
            y = length*math.sin(rotation)+offset*math.cos(rotation)
        elif family == 'close_pairs' and j % 2:
            x = sources[-1]['x'] + rng.uniform(-8, 8)
            y = sources[-1]['y'] + rng.uniform(-8, 8)
        elif family == 'grazing':
            r = rng.choice((5.001, 19.999, 999.999, 1499.999, 1799.999))
            a = rotation + j*2*math.pi/n
            x, y = r*math.cos(a), r*math.sin(a)
        length = math.hypot(x, y)
        if length > 1800:
            x, y = x*1800/length, y*1800/length
        radius = rng.uniform(1000, 1500)
        if family in ('short_radius', 'outward', 'boundary') or stress:
            radius = 1000 if stress else rng.uniform(1000, 1030)
        orient = None
        if j < directional_count:
            orient = rng.uniform(0, 360)
            if family in ('outward', 'boundary'):
                orient = math.degrees(math.atan2(y, x)) + rng.uniform(-4, 4)
            elif family == 'grazing':
                orient = math.degrees(math.atan2(-y, -x)) + rng.choice((-90, 90)) + rng.uniform(-.01, .01)
            orient %= 360
        sources.append(dict(channel=ch, x=x, y=y, radius=radius, orientation_deg=orient))
    return dict(case_id=f'local_p{problem}_{split}_{index:04d}', problem=problem,
                provenance='self_constructed_not_official', seed=seed, split=split,
                family=family, noise=noise, sources=sources)


def generate_suite(problem: int, split: str, count: int | None = None):
    return [generate_case(problem, i, split) for i in range(count or SPLITS[split][1])]

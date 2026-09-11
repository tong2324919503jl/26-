"""Fresh synthetic suites for evaluating optional probabilistic early stopping.

These are NOT official cases and cannot establish a distribution-free miss rate.
Keep the safe v4 policy as the default.  A harness may read case metadata/truth;
the policy must receive only the existing ObservationClient public facade.

Each (problem, split) owns one million seeds, including optional count extensions.
The default development/calibration/holdout/stress sizes are 256/512/2048/512.
Calibration and holdout must stay unopened until the relevant model is frozen;
later tuning requires a new suite version, rather than reusing holdout outcomes.
No files or existing scenarios are read or changed by this module.
"""
from __future__ import annotations

import math
import random


SUITE_VERSION = 'probability_v1'
SEED_CAPACITY = 1_000_000
PROBLEM_SEED_STRIDE = 10_000_000
SPLITS = {
    'development': (71_000_000, 256),
    'calibration': (72_000_000, 512),
    'holdout': (73_000_000, 2048),
    'stress': (74_000_000, 512),
}
FAMILIES = (
    'uniform', 'clusters', 'boundary', 'outward', 'corridor',
    'close_pairs', 'grazing', 'short_radius',
    'boundary_outward_min', 'boundary_tangent_min', 'offcenter_cluster_min',
    'one_hidden_outward', 'two_hidden_opposite', 'remote_hidden_cluster',
    'nested_rings', 'range_shells',
)
HARD_FAMILIES = frozenset(FAMILIES[8:])
NOISE_MODES = ('hash_uniform', 'spatial', 'extreme', 'bias')


def _validate_request(problem: int, split: str) -> None:
    if type(problem) is not int or problem not in (3, 4):
        raise ValueError('problem must be 3 or 4')
    if not isinstance(split, str) or split not in SPLITS:
        raise ValueError(f'split must be one of {tuple(SPLITS)}')


def case_seed(problem: int, index: int, split: str = 'development') -> int:
    """Return a seed without generating or inspecting any source configuration."""
    _validate_request(problem, split)
    if type(index) is not int or not 0 <= index < SEED_CAPACITY:
        raise ValueError(f'index must be an integer in [0, {SEED_CAPACITY})')
    return SPLITS[split][0] + problem * PROBLEM_SEED_STRIDE + index


def _polar(radius: float, angle: float) -> tuple[float, float]:
    return radius * math.cos(angle), radius * math.sin(angle)


def _inside_disk(x: float, y: float) -> tuple[float, float]:
    length = math.hypot(x, y)
    if length > 1800:
        scale = math.nextafter(1800.0, 0.0) / length
        x, y = x * scale, y * scale
    return x, y


def _construct_case(problem: int, index: int, seed: int, split: str,
                    *, stress: bool) -> dict:
    """Internal construction; unit tests use dedicated, non-reserved seeds."""
    rng = random.Random(seed)
    family_index = index % len(FAMILIES)
    block = index // len(FAMILIES)
    family = FAMILIES[family_index]
    # Family, count and noise vary independently over complete 28-block cycles.
    # Every family sees all seven counts and four noises within development 256.
    n = 10 + (block + 3 * family_index) % 7
    noise = (('extreme', 'bias')[(block + family_index) % 2] if stress
             else NOISE_MODES[(block + family_index) % len(NOISE_MODES)])
    rotation = rng.uniform(0, math.tau)
    centers = [_polar(rng.uniform(500, 1450), rotation + offset)
               for offset in (0, 2.3, 4.5)]
    remote_center = _polar(rng.uniform(1500, 1700), rotation)
    channels = rng.sample(range(1, 21), n)
    hidden_count = {'one_hidden_outward': 1, 'two_hidden_opposite': 2,
                    'remote_hidden_cluster': 3}.get(family, 0)
    hidden_start = n - hidden_count
    directional_indices: set[int] = set()
    if problem == 4:
        if stress or family in HARD_FAMILIES:
            # Leave one background source omni, never one of the hidden sources.
            omni_index = rng.randrange(hidden_start)
            directional_indices = set(range(n)) - {omni_index}
        else:
            directional_indices = set(rng.sample(range(n), rng.randint(1, n - 1)))

    sources = []
    for j, channel in enumerate(channels):
        a = rng.uniform(0, math.tau)
        r = 1800 * math.sqrt(rng.random())
        x, y = _polar(r, a)
        if family in ('boundary', 'outward', 'boundary_outward_min',
                      'boundary_tangent_min'):
            a = rotation + math.tau * j / n + rng.uniform(-.055, .055)
            r = 1800 if stress or family in HARD_FAMILIES else rng.uniform(1690, 1800)
            x, y = _polar(r, a)
        elif family == 'clusters':
            cx, cy = centers[j % len(centers)]
            x, y = cx + rng.gauss(0, 70), cy + rng.gauss(0, 70)
        elif family == 'corridor':
            length, offset = rng.uniform(-1770, 1770), rng.uniform(-12, 12)
            x = length * math.cos(rotation) - offset * math.sin(rotation)
            y = length * math.sin(rotation) + offset * math.cos(rotation)
        elif family == 'close_pairs' and j % 2:
            x = sources[-1]['x'] + rng.uniform(-8, 8)
            y = sources[-1]['y'] + rng.uniform(-8, 8)
        elif family == 'grazing':
            r = rng.choice((5.001, 19.999, 999.999, 1499.999, 1799.999))
            x, y = _polar(r, rotation + j * math.tau / n)
        elif family == 'offcenter_cluster_min':
            x = remote_center[0] + rng.uniform(-35, 35)
            y = remote_center[1] + rng.uniform(-35, 35)
        elif hidden_count:
            if j < hidden_start:
                x, y = _polar(rng.uniform(60, 450), rng.uniform(0, math.tau))
            elif family == 'remote_hidden_cluster':
                x = remote_center[0] + rng.uniform(-35, 35)
                y = remote_center[1] + rng.uniform(-35, 35)
            else:
                a = rotation + (j - hidden_start) * math.pi + rng.uniform(-.02, .02)
                x, y = _polar(rng.uniform(1790, 1800), a)
        elif family == 'nested_rings':
            a = rotation + j * math.tau / n + rng.uniform(-.05, .05)
            r = rng.uniform(350, 850) if j < n // 2 else rng.uniform(1700, 1800)
            x, y = _polar(r, a)
        elif family == 'range_shells':
            # Optical/near/range boundaries are distinct; all remain legal sources.
            eps = rng.choice((.001, .01, .1))
            boundary = (5, 20, 1000, 1500, 1800)[j % 5]
            r = boundary + (rng.choice((-1, 1)) * eps if boundary < 1800 else -eps)
            x, y = _polar(r, rotation + j * math.tau / n + rng.uniform(-.01, .01))
        x, y = _inside_disk(x, y)
        radius = rng.uniform(1000, 1500)
        if stress or family in HARD_FAMILIES:
            radius = 1000.0
        elif family in ('short_radius', 'outward', 'boundary'):
            radius = rng.uniform(1000, 1030)

        orientation = None
        if j in directional_indices:
            radial = math.degrees(math.atan2(y, x))
            orientation = rng.uniform(0, 360)
            if family in ('outward', 'boundary', 'boundary_outward_min'):
                orientation = radial + rng.uniform(-4, 4)
            elif family == 'boundary_tangent_min':
                orientation = radial + rng.choice((-90, 90)) + rng.uniform(-.01, .01)
            elif family in ('grazing', 'range_shells'):
                orientation = radial + 180 + rng.choice((-90, 90)) + rng.uniform(-.01, .01)
            elif family == 'offcenter_cluster_min':
                orientation = math.degrees(rotation) + rng.uniform(-3, 3)
            elif hidden_count:
                # The easy prefix is actually visible at the origin.  Remaining
                # sources are far away and face outward; no strategy sees labels.
                orientation = radial + (180 if j < hidden_start else 0) + rng.uniform(-5, 5)
            elif family == 'nested_rings':
                orientation = radial + (180 if j < n // 2 else 0) + rng.uniform(-5, 5)
            orientation %= 360
        sources.append(dict(channel=channel, x=x, y=y, radius=radius,
                            orientation_deg=orientation))

    # Shuffling prevents list order from exposing hidden/easy source roles, even
    # to harness consumers.  The policy still receives no source list at all.
    rng.shuffle(sources)
    return dict(case_id=f'{SUITE_VERSION}_p{problem}_{split}_{index:06d}',
                suite_version=SUITE_VERSION, problem=problem,
                provenance='self_constructed_not_official', seed=seed,
                split=split, family=family, noise=noise, sources=sources)


def generate_case(problem: int, index: int = 0,
                  split: str = 'development') -> dict:
    """Generate one deterministic case without I/O or global RNG side effects."""
    seed = case_seed(problem, index, split)
    return _construct_case(problem, index, seed, split, stress=split == 'stress')


def generate_suite(problem: int, split: str = 'development',
                   count: int | None = None) -> list[dict]:
    """Generate the requested prefix; count=0 is empty, None uses split default."""
    _validate_request(problem, split)
    if count is None:
        count = SPLITS[split][1]
    if type(count) is not int or not 0 <= count <= SEED_CAPACITY:
        raise ValueError(f'count must be an integer in [0, {SEED_CAPACITY}]')
    return [generate_case(problem, i, split) for i in range(count)]

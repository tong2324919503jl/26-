"""Simultaneous numerical bounds for the optional probability-stop experiment.

Alpha controls source-prior Monte Carlo integration error, not arena failure.
The finite union covers EVERY subset of EVERY supported layout and all five
priors, so selecting a route or stopping time using the same particles is
allowed. Unsupported positions must disable the numerical guarded exit.
"""
from __future__ import annotations

from functools import lru_cache
import math

NUMERICAL_ALPHA = .001
PRIOR_COUNT = 5
POINT_TOLERANCE_M = 1e-6
REQUIRED_DETECTION_MARGIN_M = 1e-3


@lru_cache(maxsize=2)
def supported_layouts(problem):
    """Fixed v4 layouts, not a union of points from incompatible rotations."""
    if problem == 4:
        from problem4.search_layout import coverage_points
        return (tuple(coverage_points()),)
    if problem != 3:
        raise ValueError('Problem must be 3 or 4')
    layouts = []
    for count, radius, phases in ((6, 1150., 24), (9, 1700., 16)):
        for phase in range(phases):
            angle = math.tau * phase / (count * phases)
            layouts.append(((0., 0.),) + tuple(
                (radius * math.cos(angle + k * math.tau / count),
                 radius * math.sin(angle + k * math.tau / count))
                for k in range(count)))
    return tuple(layouts)


def hypothesis_count(problem):
    # Duplicate subsets shared by several layouts are harmless overcounting.
    # The prior count belongs here even when callers only pass max(qhat).
    return PRIOR_COUNT * sum(2**len(layout) for layout in supported_layouts(problem))


def supports_points(problem, points):
    """True only if all actual full scans match one supported layout.

    A match is Euclidean distance <= 1e-6 m. The caller MUST count detections
    using radius-0.001 m and beam projection >=0.001 m. To justify tolerance,
    let c be a canonical point, a its matched actual point, epsilon=1e-6.
    Canonical epsilon-inset detections are a subset of actual true detections;
    actual 0.001-inset detections are a subset of canonical epsilon-inset ones.
    Thus actual true miss mass <= canonical inset miss mass, and its empirical
    upper bound is <= the bound computed from actual deeply inset misses.
    The Chernoff union is over those finitely many canonical inset subsets.
    """
    layouts = supported_layouts(problem)
    try:
        actual = []
        for point in points:
            if len(point) != 2 or any(isinstance(value, bool) for value in point):
                return False
            point = tuple(float(value) for value in point)
            if not all(math.isfinite(value) for value in point):
                return False
            actual.append(point)
    except (TypeError, ValueError, OverflowError):
        return False
    return any(all(any(math.dist(point, canonical) <= POINT_TOLERANCE_M
                       for canonical in layout) for point in actual)
               for layout in layouts)


def bernoulli_kl(p, u):
    """KL(Bernoulli(p) || Bernoulli(u)), for 0 <= p <= u <= 1."""
    if not 0 <= p <= u <= 1:
        raise ValueError('KL arguments must satisfy 0 <= p <= u <= 1')
    if p == u:
        return 0.
    if u == 1:
        return math.inf
    if p == 0:
        return -math.log1p(-u)
    return p * math.log(p / u) + (1-p) * (math.log1p(-p) - math.log1p(-u))


def simultaneous_mass_upper(qhat, particles, problem):
    """Invert M*KL(qhat||u)=log(F/alpha), retaining the upper bracket.

    This is an unconditional-over-particle-draws simultaneous bound for the
    named priors and supported layouts. It is not a model-misspecification or
    frequentist full-clearance guarantee. Integrator seeds must be predeclared,
    not selected after observing higher reported probabilities.
    """
    if isinstance(qhat, bool) or not math.isfinite(qhat) or not 0 <= qhat <= 1:
        raise ValueError('Empirical mass must be finite and lie in [0, 1]')
    if type(particles) is not int or particles < 1:
        raise ValueError('Particle count must be a positive integer')
    target = math.log(hypothesis_count(problem) / NUMERICAL_ALPHA) / particles
    if qhat == 1:
        return 1.
    if qhat == 0:
        return min(1., math.nextafter(-math.expm1(-target), 1.))
    low, high = qhat, 1.
    for _ in range(80):
        middle = (low + high) / 2
        if middle == low or middle == high:
            break
        if bernoulli_kl(qhat, middle) >= target:
            high = middle
        else:
            low = middle
    return min(1., math.nextafter(high, 1.))

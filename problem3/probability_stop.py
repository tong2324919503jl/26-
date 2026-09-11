"""Experimental, assumption-dependent early exit for problems 3 and 4.

This module is never imported by the safe production entry points.  A sampled
prior is not a coverage proof.  In particular, unseen clustered or adversarial
sources need not follow any of these priors, even when the reported probability
is close to one.  NumPy is needed only for this optional experiment.
"""
from __future__ import annotations

import math
from functools import lru_cache


MODEL_VERSION = 'probability_stop_v1'
DEFAULT_PARTICLES = 131072
THRESHOLDS = (.80, .90, .95, .975, .99, .995, .999, .9999)
PRIORS = ('nominal', 'short_disk', 'outer_outward', 'boundary_uniform',
          'boundary_tangent')
MODES = ('nominal', 'robust', 'guarded')


def full_clear_probability(k: int, unseen_mass: float, count_growth: float = 1.) -> float:
    """Posterior under exchangeable iid sources and P(N=n) proportional to g**n.

    Conditional on the actual public history, the likelihood factors from the
    k detected sources cancel between possible N values.  The unknown channels
    contribute q**(N-k); uniform channel assignment leaves the binomial factor
    choose(N,k).  Adaptively chosen actions add no likelihood factor when they
    are deterministic functions of the preceding public history.  This does
    NOT justify iid priors for real, clustered source placements.
    """
    if type(k) is not int or not 0 <= k <= 16:
        raise ValueError('Detected count must be an integer in 0..16')
    if not math.isfinite(unseen_mass) or not 0 <= unseen_mass <= 1:
        raise ValueError('Unseen mass must lie in [0, 1]')
    if not math.isfinite(count_growth) or count_growth <= 0:
        raise ValueError('Count prior growth must be positive')
    if k < 10:
        return 0.
    return 1. / sum(math.comb(n, k) * (unseen_mass * count_growth)**(n-k)
                    for n in range(k, 17))


class ProbabilityModel:
    """Cached source-configuration integration, using observations only.

    Each particle is a WHOLE fixed source (position, radius, beam), so repeated
    no_signal readings are correlated correctly.  The +1/M floor prevents zero
    sampled survivors being called certainty; it is a numerical safeguard,
    NOT a statistical upper confidence bound.  The robust score is a sensitivity
    envelope over five stated priors, not a distribution-free probability bound.
    """
    def __init__(self, problem: int, particles: int = DEFAULT_PARTICLES,
                 integration_seed: int = 905117):
        if problem not in (3, 4) or type(particles) is not int or particles < 64:
            raise ValueError('Problem must be 3/4 and particles an integer >=64')
        import numpy as np
        self.np = np
        self.problem, self.particles = problem, particles
        self.integration_seed = integration_seed
        self._clouds = {}
        self._masks = {}
        self._estimates = {}
        for index, name in enumerate(PRIORS):
            rng = np.random.default_rng(integration_seed + 100 * problem + index)
            theta = rng.uniform(0, math.tau, particles)
            radial = 1800 * np.sqrt(rng.random(particles))
            radius = rng.uniform(1000, 1500, particles)
            beam = rng.uniform(0, math.tau, particles)
            directional = rng.random(particles) < .5 if problem == 4 else np.zeros(particles, bool)
            if name != 'nominal':
                radius[:] = 1000.
                if problem == 4:
                    directional[:] = True  # Harder than any mixture at fixed position/beam.
            if name == 'outer_outward':
                radial = rng.uniform(1690, 1800, particles)
                beam = theta + rng.uniform(-math.pi/45, math.pi/45, particles)
            if name.startswith('boundary_'):
                radial[:] = 1800.
            if name == 'boundary_tangent':
                beam = theta + rng.choice((-1., 1.), particles) * math.pi/2
                beam += rng.uniform(-math.pi/1800, math.pi/1800, particles)
            self._clouds[name] = (radial*np.cos(theta), radial*np.sin(theta),
                                  (radius-.001)**2, np.cos(beam), np.sin(beam), directional)
        self._full_mask = (1 << particles) - 1

    def _visible_mask(self, prior: str, point: tuple) -> int:
        # Exact public coordinates, with no rounding across visibility boundaries.
        key = (prior, tuple(point))
        if key not in self._masks:
            x, y, r2, bx, by, directional = self._clouds[prior]
            dx, dy = point[0]-x, point[1]-y
            visible = (dx*dx+dy*dy <= r2) & (~directional | (dx*bx+dy*by >= .001))
            self._masks[key] = int.from_bytes(self.np.packbits(visible, bitorder='little').tobytes(), 'little')
        return self._masks[key]

    def estimate(self, coverage_points, cleared_count: int, *, known_pending: bool = False) -> dict:
        points = tuple(sorted(set(tuple(p) for p in coverage_points)))
        key = (points, cleared_count, bool(known_pending))
        if key in self._estimates:
            return dict(self._estimates[key])
        masses = {}
        raw_masses = {}
        for prior in PRIORS:
            unseen = self._full_mask
            for point in points:
                unseen &= ~self._visible_mask(prior, point)
            raw_masses[prior] = unseen.bit_count()/self.particles
            masses[prior] = min(1., raw_masses[prior] + 1/self.particles)
        eligible = not known_pending and 10 <= cleared_count < 16
        nominal = full_clear_probability(cleared_count, masses['nominal'])
        robust = full_clear_probability(cleared_count, max(masses.values()), 2.)
        from problem3.probability_numeric import simultaneous_mass_upper, supports_points
        numerical_supported = supports_points(self.problem, points)
        upper_mass = (simultaneous_mass_upper(max(raw_masses.values()), self.particles, self.problem)
                      if numerical_supported else 1.)
        guarded = full_clear_probability(cleared_count, upper_mass, 2.) if numerical_supported else 0.
        if known_pending:
            nominal = robust = guarded = 0.
        result = dict(model_version=MODEL_VERSION, particles=self.particles,
                      integration_seed=self.integration_seed, eligible=eligible,
                      cleared_count=cleared_count, full_scan_count=len(points),
                      unseen_mass=masses, nominal=nominal, robust=robust, guarded=guarded,
                      guarded_unseen_mass_upper=upper_mass,
                      numerical_guard_supported=numerical_supported,
                      probability_is_conditional=True, completion_certified=False)
        self._estimates[key] = result
        return dict(result)


@lru_cache(maxsize=4)
def get_model(problem: int, particles: int = DEFAULT_PARTICLES) -> ProbabilityModel:
    return ProbabilityModel(problem, particles)


class _ProbabilityExit(Exception):
    def __init__(self, estimate):
        self.estimate = estimate


class ProbabilityStopMixin:
    """Stop only between complete v4 actions; never suppress real failures."""
    def __init__(self, *args, threshold: float = .99, probability_mode: str = 'guarded',
                 particles: int = DEFAULT_PARTICLES, **kwargs):
        if not math.isfinite(threshold) or not 0 < threshold < 1:
            raise ValueError('Threshold must lie strictly between 0 and 1')
        if probability_mode not in MODES:
            raise ValueError('Unknown probability mode')
        self.threshold, self.probability_mode = threshold, probability_mode
        self.probability_model = get_model(kwargs.get('problem', args[0] if args else 3), particles)
        self.probability_checks = 0
        super().__init__(*args, **kwargs)

    def _route_goal(self, client, pending):
        known = set(self.regions) | self.cleared
        if 10 <= len(self.cleared) < 16 and known <= self.cleared and pending:
            estimate = self.probability_model.estimate(self.coverage_visited, len(self.cleared))
            self.probability_checks += 1
            if estimate[self.probability_mode] >= self.threshold:
                raise _ProbabilityExit(estimate)
        return super()._route_goal(client, pending)

    def run(self, client):
        try:
            result = super().run(client)
        except _ProbabilityExit as exit_event:
            result = self._result('experimental_probability_threshold', False)
            result['completion_certified'] = False
            result['probability_estimate'] = exit_event.estimate
        result['base_algorithm_version'] = result.get('algorithm_version')
        result['algorithm_version'] = f'problem{self.problem}_{MODEL_VERSION}'
        result['probability_mode'] = self.probability_mode
        result['probability_threshold'] = self.threshold
        result['probability_checks'] = self.probability_checks
        return result


def make_policy(problem: int, **kwargs):
    if problem == 3:
        from problem3.speed_policy import SearchPolicy
    elif problem == 4:
        from problem4.speed_policy import SearchPolicy
    else:
        raise ValueError('Problem must be 3 or 4')
    class ExperimentalPolicy(ProbabilityStopMixin, SearchPolicy):
        pass
    return ExperimentalPolicy(problem=problem, **kwargs)

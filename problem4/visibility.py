"""Public-feedback visibility quadrature for probe ranking only.

Five position nodes and continuous orientation/radius intervals are NOT a
certified source cover. They never shrink regions, authorize clearance, or
terminate discovery. The inherited 22-station proof and finite optical fallback
remain in force. Radius endpoints and ambiguous negative readings are retained.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from problem3.geometry import (
    clip_halfplane, distance, enclosing_circle, intersect_bearing,
    optical_cover, polygon_centroid,
)
from problem4.optical_repair import area, bounding_strip
from problem4.speed_policy import SearchPolicy as BasePolicy

TAU = math.tau
FULL = ((0., TAU),)
TOL = 1e-10


def intersect_intervals(first, second):
    """Closed outer intersections; retain zero-width boundary hypotheses."""
    answer = []
    for a, b in first:
        for c, d in second:
            lo, hi = max(a, c), min(b, d)
            if lo <= hi + TOL:
                answer.append((lo, max(lo, hi)))
    answer.sort()
    merged = []
    for lo, hi in answer:
        if merged and lo <= merged[-1][1] + TOL:
            merged[-1] = (merged[-1][0], max(hi, merged[-1][1]))
        else:
            merged.append((lo, hi))
    return tuple(merged)


def hemisphere(point, source, positive=True):
    """Direction intervals facing point, or a closed outer back hemisphere."""
    dx, dy = point[0] - source[0], point[1] - source[1]
    if math.hypot(dx, dy) < 1e-10:
        return FULL if positive else ()
    center = math.atan2(dy, dx) + (0. if positive else math.pi)
    start = (center - math.pi / 2) % TAU
    end = start + math.pi
    return ((start, end),) if end <= TAU else ((0., end - TAU), (start, TAU))


def angular_mass(intervals):
    # Point hypotheses get a tiny ranking weight. This is not posterior proof.
    return sum(max(1e-12, b - a) for a, b in intervals)


def position_nodes(polygon, count=5):
    """Area-weighted centroids of long-axis strips, never a hard cover."""
    if count < 1:
        raise ValueError("At least one ranking node is required")
    axis, (low, high), _ = bounding_strip(polygon)
    if high - low < 1e-8:
        return ((polygon_centroid(polygon), 1.),)
    ux, uy = axis
    result = []
    for index in range(count):
        lo = low + (high - low) * index / count
        hi = low + (high - low) * (index + 1) / count
        piece = clip_halfplane(polygon, ux, uy, hi)
        piece = clip_halfplane(piece, -ux, -uy, -lo)
        if piece:
            result.append((polygon_centroid(piece), max(1e-8, area(piece))))
    total = sum(weight for _, weight in result)
    return tuple((point, weight / total) for point, weight in result)


@dataclass(frozen=True)
class VisibilityAtom:
    source: tuple
    low: float
    high: float
    orientations: tuple | None
    weight: float

    def detection_fraction(self, points):
        """Fraction satisfying every query; integrate radius threshold exactly."""
        required = max(distance(self.source, q) for q in points)
        if required > self.high + 1e-8:
            return 0.
        if self.high - self.low < 1e-9:
            radial = 1. if required <= self.high + 1e-8 else 0.
        else:
            radial = max(0., min(1., (self.high - max(self.low, required)) /
                                       (self.high - self.low)))
        if self.orientations is None:
            return radial
        feasible = self.orientations
        for point in points:
            feasible = intersect_intervals(feasible, hemisphere(point, self.source))
        return radial * min(1., angular_mass(feasible) / angular_mass(self.orientations))


def build_atoms(polygon, positives, negatives, count=5, directional_weight=.5):
    """Hypothetical nodes from observed geometry; no hidden source arguments.

    For fixed g, each radius interval has a constant set of in-range negatives.
    Only those impose a back-half-plane constraint. Farther negatives do not.
    Positive range boundaries 1000 and 1500 and zero-width limits are retained.
    """
    atoms = []
    for source, spatial_weight in position_nodes(polygon, count):
        needed = max((1000., *(distance(source, p) for p in positives)))
        if needed > 1500. + 1e-6:
            continue
        needed = min(1500., needed)
        allowed = FULL
        for positive in positives:
            allowed = intersect_intervals(allowed, hemisphere(positive, source))
        cuts = sorted((distance(source, q), q) for q in negatives)
        limits = sorted({needed, 1500., *(min(1500., max(needed, d)) for d, _ in cuts)})
        segments = list(zip(limits, limits[1:])) or [(needed, needed)]
        for low, high in segments:
            radius = (low + high) / 2
            orientations = allowed
            omni = True
            for separation, negative in cuts:
                if separation <= radius + 1e-9:
                    omni = False
                    orientations = intersect_intervals(
                        orientations, hemisphere(negative, source, False))
            radial_weight = max(1e-8, high - low) / 500.
            if omni and directional_weight < 1:
                atoms.append(VisibilityAtom(source, low, high, None,
                             spatial_weight * radial_weight * (1 - directional_weight)))
            if orientations and directional_weight > 0:
                atoms.append(VisibilityAtom(source, low, high, orientations,
                             spatial_weight * radial_weight * directional_weight *
                             angular_mass(orientations) / TAU))
    total = sum(atom.weight for atom in atoms)
    if not total:
        return ()  # An empty quadrature is never evidence of absence.
    return tuple(VisibilityAtom(a.source, a.low, a.high, a.orientations,
                               a.weight / total) for a in atoms)


class VisibilityMixin:
    visibility_nodes = 5
    visibility_mode = 'pair'
    visibility_quantiles = (.10, .20, .45, .70)
    visibility_directional_weight = .5
    visibility_uncertainty_weight = 1.
    visibility_noise = (-.8, 0., .8)

    def _visibility_atoms(self, channel):
        positive = tuple(p for p, _ in self.observations[channel])
        negative = tuple(getattr(self, '_negative_history', {}).get(channel, ()))
        poly = tuple(self.regions[channel])
        key = (poly, positive, negative, self.visibility_nodes,
               self.visibility_directional_weight)
        if not hasattr(self, '_visibility_cache'):
            self._visibility_cache = {}
        cached = self._visibility_cache.get(channel)
        if cached and cached[0] == key:
            return cached[1]
        atoms = build_atoms(poly, positive, negative, self.visibility_nodes,
                            self.visibility_directional_weight)
        self._visibility_cache[channel] = (key, atoms)
        self.stats['visibility_models'] = self.stats.get('visibility_models', 0) + 1
        self.stats['visibility_atoms_peak'] = max(self.stats.get('visibility_atoms_peak', 0), len(atoms))
        return atoms

    def _visibility_pair(self, polygon, anchor, bearing, quantile):
        """Use the inherited safe-pair construction and range test unchanged."""
        theta = math.radians(bearing)
        forward = (math.cos(theta), math.sin(theta))
        sideways = (-forward[1], forward[0])
        values = [((p[0] - anchor[0]) * forward[0] +
                   (p[1] - anchor[1]) * forward[1]) for p in polygon]
        low, high = min(values), max(values)
        step = low + quantile * (high - low)
        width = max(self.localization_width_min, min(self.localization_width_max,
                    self.localization_width_fraction * step))
        tangent = math.tan(math.radians(self.config.bearing_error_deg))
        width = max(width, step * tangent + .01)
        for _ in range(24):
            middle = (anchor[0] + step * forward[0], anchor[1] + step * forward[1])
            pair = tuple((middle[0] + sign * width * sideways[0],
                          middle[1] + sign * width * sideways[1]) for sign in (-1, 1))
            if max(distance(p, vertex) for p in pair for vertex in polygon) < 999.99:
                break
            step = .5 * step + .25 * (low + high)
            width = max(width, step * tangent + .01)
        middle = (anchor[0] + step * forward[0], anchor[1] + step * forward[1])
        pair = tuple((middle[0] + sign * width * sideways[0],
                      middle[1] + sign * width * sideways[1]) for sign in (-1, 1))
        in_range = all(distance(p, vertex) < 999.999 for p in pair for vertex in polygon)
        return step, forward, pair, in_range

    def _visibility_remaining(self, point, source, polygon, measured, cache):
        key = (point, source, measured)
        if key in cache:
            return cache[key]
        if not polygon:
            return 1e6
        radius = enclosing_circle(polygon)[1]
        if measured:
            bearing = math.degrees(math.atan2(source[1] - point[1], source[0] - point[0]))
            estimates = []
            for noise in self.visibility_noise:
                posterior = intersect_bearing(polygon, point, bearing + noise,
                                               self.config.bearing_error_deg)
                estimates.append(enclosing_circle(posterior)[1] if posterior else radius)
            radius = sum(estimates) / len(estimates)
        value = (distance(point, source) / 5. +
                 self.visibility_uncertainty_weight * max(0., radius - 19.5) / 5. +
                 5. * math.log2(max(1., radius / 19.5)))
        cache[key] = value
        return value

    def _visibility_score(self, client, channel, polygon, anchor, choice, atoms):
        step, forward, pair, in_range = choice
        first, second = pair
        score = distance(client.position, first) / 5. + 5. + (client.current_channel != channel)
        negative_poly = polygon
        if in_range and step > 0:
            bound = step + anchor[0] * forward[0] + anchor[1] * forward[1]
            negative_poly = clip_halfplane(polygon, forward[0], forward[1], bound)
        cache = {}
        for atom in atoms:
            p1 = atom.detection_fraction((first,))
            p2 = max(0., atom.detection_fraction((second,)) - atom.detection_fraction(pair))
            pnone = max(0., 1. - p1 - p2)
            after = p1 * self._visibility_remaining(first, atom.source, polygon, True, cache)
            after += (1. - p1) * (distance(first, second) / 5. + 5.)
            after += p2 * self._visibility_remaining(second, atom.source, polygon, True, cache)
            after += pnone * self._visibility_remaining(second, atom.source, negative_poly, False, cache)
            score += atom.weight * after
        return score

    def _visibility_choice(self, channel, client, attempted):
        polygon = self.regions[channel]
        anchor, bearing = self.observations[channel][-1]
        base = self._visibility_pair(polygon, anchor, bearing, self.localization_quantile)
        nearest = tuple(sorted(base[2], key=lambda p: distance(client.position, p)))
        base = (base[0], base[1], nearest, base[3])
        atoms = self._visibility_atoms(channel)
        if not atoms or self.visibility_mode == 'off':
            return base
        quantiles = ((self.localization_quantile,) if self.visibility_mode == 'order'
                     else tuple(dict.fromkeys((self.localization_quantile, *self.visibility_quantiles))))
        choices = []
        for quantile in quantiles:
            step, forward, pair, in_range = self._visibility_pair(polygon, anchor, bearing, quantile)
            if any((round(q[0], 7), round(q[1], 7)) in attempted for q in pair):
                continue
            for probes in (pair, tuple(reversed(pair))):
                choice = (step, forward, probes, in_range)
                choices.append((self._visibility_score(client, channel, polygon, anchor, choice, atoms), choice))
        if not choices:
            return base
        selected = min(choices, key=lambda item: item[0])[1]
        self.stats['visibility_choices'] = self.stats.get('visibility_choices', 0) + 1
        if selected[2] != base[2]:
            self.stats['visibility_changed'] = self.stats.get('visibility_changed', 0) + 1
        return selected

    def _localize(self, channel, client):
        """Same finite hard loop; only the next safe-pair ranking changes."""
        if self.visibility_mode == 'off':
            return super()._localize(channel, client)
        attempted_clear = False
        attempted_measure = set()
        for _ in range(self.localization_rounds):
            polygon = self.regions[channel]
            center, radius = enclosing_circle(polygon)
            if radius <= self.config.clear_guarantee_radius_m:
                if self._clear(client, center, channel):
                    return True
            elif radius <= self.config.exploratory_clear_radius_m and not attempted_clear:
                attempted_clear = True
                if self._clear(client, polygon_centroid(polygon), channel):
                    return True
            anchor, _ = self.observations[channel][-1]
            step, forward, probes, all_in_range = self._visibility_choice(channel, client, attempted_measure)
            negative = 0
            for point in probes:
                key = (round(point[0], 7), round(point[1], 7))
                if key in attempted_measure:
                    continue
                attempted_measure.add(key)
                result = self._measure(client, point, channel)
                self.stats['paired_probe_actions'] = self.stats.get('paired_probe_actions', 0) + 1
                if channel in self.cleared:
                    return True
                if result == 'direction':
                    break
                negative += 1
                self.stats['negative_localization_reads'] += 1
            if negative == 2 and all_in_range and step > 0:
                constant = step + anchor[0] * forward[0] + anchor[1] * forward[1]
                updated = clip_halfplane(polygon, forward[0], forward[1], constant)
                if not updated:
                    raise RuntimeError('Paired negatives contradict feasible region')
                self.regions[channel] = updated
                self.stats['paired_negative_clips'] = self.stats.get('paired_negative_clips', 0) + 1
        self.stats['optical_fallbacks'] += 1
        points = optical_cover(self.regions[channel], self.config.optical_spacing_m)
        while points:
            index = min(range(len(points)), key=lambda i: distance(client.position, points[i]))
            if self._clear(client, points.pop(index), channel):
                return True
        raise RuntimeError('Optical cover exhausted without clearance')

    def _result(self, reason, coverage_complete):
        result = super()._result(reason, coverage_complete)
        result['visibility_ranking_only'] = True
        result['effective_settings'].update(visibility_mode=self.visibility_mode,
            visibility_nodes=self.visibility_nodes, visibility_quantiles=self.visibility_quantiles,
            visibility_directional_weight=self.visibility_directional_weight,
            visibility_uncertainty_weight=self.visibility_uncertainty_weight)
        return result


class SearchPolicy(VisibilityMixin, BasePolicy):
    algorithm_version = 'problem4_v5_visibility_ranking'

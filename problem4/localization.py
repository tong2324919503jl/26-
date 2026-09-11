"""Conservative directional localization from positive and negative readings.

The mixin uses only the public client interface.  Movement proposals affect
cost, while retained bearing polygons and verified negative cuts establish
correctness.  Optical coverage remains the final, direction-independent path.
"""
from __future__ import annotations

import math

from problem3.geometry import (
    clip_halfplane, distance, enclosing_circle, optical_cover, polygon_centroid,
)


def _convex_hull(points):
    """Convex outer merge; preserve singleton and segment degeneracies."""
    ordered = sorted(set(points))
    if len(ordered) <= 2:
        return ordered

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for point in ordered:
        while len(lower) > 1 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in reversed(ordered):
        while len(upper) > 1 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


class LocalizationMixin:
    localization_quantile = .2
    localization_width_fraction = .04
    localization_width_min = 15.
    localization_width_max = 140.
    localization_rounds = 5
    localization_history_slices = 12

    def _history_point_in_range(self, point, cell, channel):
        """Prove Q is inside the unknown receiving radius for every g in cell.

        Either |Q-g| < 1000, or a previous positive P guarantees
        |Q-g| < |P-g| <= R.  The latter squared-distance difference is affine,
        so checking all vertices is sufficient.  The two negative points of
        a pair may use different positive observations for this proof.
        """
        if max(distance(point, vertex) for vertex in cell) < 999.999:
            return True
        qx, qy = point
        for positive, _ in self.observations[channel]:
            px, py = positive
            a, b = 2 * (px - qx), 2 * (py - qy)
            c = px * px + py * py - qx * qx - qy * qy
            if max(a * v[0] + b * v[1] - c for v in cell) < -.002:
                return True
        return False

    def _measure(self, client, point, channel):
        result = super()._measure(client, point, channel)
        if self.strategy != "adaptive":
            return result
        if not hasattr(self, "_negative_history"):
            self._negative_history = {}
        if result == "no_signal":
            history = self._negative_history.setdefault(channel, [])
            if point not in history:
                history.append(point)
        elif result == "direction":
            self._clip_history(channel)
        return result

    def _clip_history(self, channel):
        """Remove only shadow cones with a reception-distance certificate.

        A received anchor A and two absent points B,C rule out sources beyond
        segment BC in A's viewing cone when B,C are both in range.  Otherwise
        the emitting half-plane would contain an A-to-source segment point
        on BC while excluding all of BC, a contradiction.  For an omni source,
        an in-range negative is already impossible.  Splitting into narrow
        cells makes the distance proof useful without assuming a beam side.
        """
        negatives = self._negative_history.get(channel, [])
        if len(negatives) < 2:
            return
        polygon = self.regions[channel]
        _, bearing = self.observations[channel][-1]
        theta = math.radians(bearing)
        forward = (math.cos(theta), math.sin(theta))
        projections = [p[0] * forward[0] + p[1] * forward[1] for p in polygon]
        lower, upper = min(projections), max(projections)
        cells = []
        if upper - lower < 1e-9:
            cells = [list(polygon)]
        else:
            count = self.localization_history_slices
            for i in range(count):
                lo = lower + (upper - lower) * i / count
                hi = lower + (upper - lower) * (i + 1) / count
                cell = clip_halfplane(polygon, forward[0], forward[1], hi)
                cell = clip_halfplane(cell, -forward[0], -forward[1], -lo)
                if cell:
                    cells.append(cell)
        for a, _ in self.observations[channel]:
            for i, b_point in enumerate(negatives):
                for c_point in negatives[i + 1:]:
                    b, c = b_point, c_point
                    cross = ((b[0] - a[0]) * (c[1] - a[1])
                             - (b[1] - a[1]) * (c[0] - a[0]))
                    if abs(cross) < 1e-5:
                        continue
                    if cross < 0:
                        b, c = c, b
                    dx1, dy1 = b[0] - a[0], b[1] - a[1]
                    dx2, dy2 = c[0] - a[0], c[1] - a[1]
                    dx3, dy3 = c[0] - b[0], c[1] - b[1]
                    # cross(B-A,g-A)>=0, cross(C-A,g-A)<=0,
                    # and the side of BC opposite A.
                    forbidden = [
                        (dy1, -dx1, dy1 * a[0] - dx1 * a[1]),
                        (-dy2, dx2, -dy2 * a[0] + dx2 * a[1]),
                        (-dy3, dx3, -dy3 * b[0] + dx3 * b[1]),
                    ]
                    next_cells = []
                    for cell in cells:
                        if any(min(aa * v[0] + bb * v[1] - cc for v in cell) >= 1e-4
                               for aa, bb, cc in forbidden):
                            next_cells.append(cell)
                            continue
                        if not all(self._history_point_in_range(p, cell, channel) for p in (b, c)):
                            next_cells.append(cell)
                            continue
                        inside = cell
                        # Keep the union of the cone's three complement
                        # half-planes.  Outward clipping retains boundaries.
                        for aa, bb, cc in forbidden:
                            outside = clip_halfplane(inside, -aa, -bb, -cc)
                            if outside:
                                next_cells.append(outside)
                            inside = clip_halfplane(inside, aa, bb, cc)
                            if not inside:
                                break
                    cells = next_cells
                    if not cells:
                        raise RuntimeError("Historical negatives exhausted feasible cells")
                    if len(cells) > 128:
                        # Discard this optional refinement and retain the
                        # original region if its partition grows too large.
                        return
        self.regions[channel] = _convex_hull(p for cell in cells for p in cell)
        self.stats["history_clips"] = self.stats.get("history_clips", 0) + 1

    def _localize(self, channel, client):
        if self.strategy != "adaptive":
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
            anchor, bearing = self.observations[channel][-1]
            theta = math.radians(bearing)
            forward = (math.cos(theta), math.sin(theta))
            sideways = (-forward[1], forward[0])
            longitudinal = [((point[0] - anchor[0]) * forward[0]
                             + (point[1] - anchor[1]) * forward[1]) for point in polygon]
            low, high = min(longitudinal), max(longitudinal)
            step = low + self.localization_quantile * (high - low)
            width = max(self.localization_width_min, min(
                self.localization_width_max, self.localization_width_fraction * step))
            width = max(width, step * math.tan(math.radians(self.config.bearing_error_deg)) + .01)
            # Move the pair toward the interval midpoint until it is safely
            # in range.  The final explicit check below controls any cut even
            # if this bounded search fails to find such a position.
            for _range_step in range(24):
                midpoint = (anchor[0] + step * forward[0], anchor[1] + step * forward[1])
                pair = [(midpoint[0] + sign * width * sideways[0],
                         midpoint[1] + sign * width * sideways[1]) for sign in (-1, 1)]
                if max(distance(point, vertex) for point in pair for vertex in polygon) < 999.99:
                    break
                step = .5 * step + .25 * (low + high)
                width = max(width, step * math.tan(math.radians(self.config.bearing_error_deg)) + .01)
            midpoint = (anchor[0] + step * forward[0], anchor[1] + step * forward[1])
            probes = [(midpoint[0] + sign * width * sideways[0],
                       midpoint[1] + sign * width * sideways[1]) for sign in (-1, 1)]
            probes.sort(key=lambda point: distance(client.position, point))
            all_in_range = all(distance(point, vertex) < 999.999
                               for point in probes for vertex in polygon)
            negative = 0
            for point in probes:
                key = (round(point[0], 7), round(point[1], 7))
                if key in attempted_measure:
                    continue
                attempted_measure.add(key)
                result = self._measure(client, point, channel)
                self.stats["paired_probe_actions"] = self.stats.get("paired_probe_actions", 0) + 1
                if channel in self.cleared:
                    return True
                if result == "direction":
                    break
                negative += 1
                self.stats["negative_localization_reads"] += 1
            if negative == 2 and all_in_range and step > 0:
                constant = step + anchor[0] * forward[0] + anchor[1] * forward[1]
                updated = clip_halfplane(polygon, forward[0], forward[1], constant)
                if not updated:
                    raise RuntimeError("Paired negative observations contradict feasible region")
                self.regions[channel] = updated
                self.stats["paired_negative_clips"] = self.stats.get("paired_negative_clips", 0) + 1
        self.stats["optical_fallbacks"] += 1
        points = optical_cover(self.regions[channel], self.config.optical_spacing_m)
        while points:
            index = min(range(len(points)), key=lambda i: distance(client.position, points[i]))
            if self._clear(client, points.pop(index), channel):
                return True
        raise RuntimeError("Optical cover exhausted without clearance")

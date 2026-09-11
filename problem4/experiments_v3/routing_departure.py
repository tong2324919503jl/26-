"""Development-only short baseline followed by a fresh global tour decision.

The score predicts information, never removes a feasible point. Each channel
has a bounded number of extra observations and retains the production fallback.
"""
from __future__ import annotations

import math

from problem3.geometry import distance, enclosing_circle, intersect_bearing
from problem4.experiments_v3.coverage_ring_policy import Ring12CoverPolicy
from problem4.experiments_v3.routing_shared import SharedBaselineMixin


class DepartureBaselineMixin:
    departure_enabled = True
    departure_min_radius = 80.
    departure_min_leg = 300.
    departure_radii = (50., 100.)
    departure_max_per_source = 2
    departure_min_gain = 25.
    departure_detour_weight = .75
    departure_error_factor = 1.
    departure_batch = True
    departure_sample_score = False
    departure_forward = False

    def _departure_gain(self, channel, point):
        poly = self.regions[channel]
        center, uncertainty = enclosing_circle(poly)
        separation = distance(point, center)
        if uncertainty < self.departure_min_radius or separation > 1450:
            return 0.
        probability = max(0., min(1., (1500 - separation) / 500))
        if self.departure_sample_score:
            anchor, bearing = self.observations[channel][-1]
            direction = (math.cos(math.radians(bearing)), math.sin(math.radians(bearing)))
            projections = [p[0] * direction[0] + p[1] * direction[1] for p in poly]
            low, high = poly[projections.index(min(projections))], poly[projections.index(max(projections))]
            samples = [(low[0]*(1-t)+high[0]*t, low[1]*(1-t)+high[1]*t)
                       for t in (.1,.3,.5,.7,.9)]
            radii = []
            for sample in samples:
                angle = math.degrees(math.atan2(sample[1]-point[1], sample[0]-point[0]))
                for noise in (-.7, .7):
                    narrowed = intersect_bearing(poly, point, angle+noise)
                    radii.append(enclosing_circle(narrowed)[1] if narrowed else uncertainty)
            predicted = sum(radii) / len(radii)
        else:
            predicted = uncertainty
            b = (point[0]-center[0], point[1]-center[1])
            for anchor, _ in self.observations[channel]:
                a = (anchor[0]-center[0], anchor[1]-center[1])
                den = math.hypot(*a)*math.hypot(*b)
                sine = abs(a[0]*b[1]-a[1]*b[0])/den if den else 0.
                predicted = min(predicted, self.departure_error_factor*.01754*separation/max(.01,sine))
        return max(0., uncertainty-predicted)*probability

    def _localize(self, channel, client):
        if not self.departure_enabled:
            return super()._localize(channel, client)
        attempts = getattr(self, '_departure_attempts', None)
        if attempts is None:
            attempts = self._departure_attempts = {}
        origin = client.position
        center, uncertainty = enclosing_circle(self.regions[channel])
        old_attempts = attempts.setdefault(channel, [])
        if (uncertainty < self.departure_min_radius
                or distance(origin, center) < self.departure_min_leg
                or len(old_attempts) >= self.departure_max_per_source):
            return super()._localize(channel, client)
        eligible = [channel]
        if self.departure_batch:
            eligible += [ch for ch in self.regions if ch not in self.cleared and ch != channel]
        choices = []
        for radius in self.departure_radii:
            for index in range(24):
                angle = index*math.tau/24
                q = (origin[0]+radius*math.cos(angle), origin[1]+radius*math.sin(angle))
                if any(distance(q,p)<25 for p in old_attempts):
                    continue
                if self.departure_forward and distance(q,center)>distance(origin,center):
                    continue
                gain = self._departure_gain(channel, q)
                if gain < self.departure_min_gain:
                    continue
                gains = [(gain, channel)]
                for other in eligible[1:]:
                    value = self._departure_gain(other, q)
                    if value >= self.departure_min_gain:
                        gains.append((value, other))
                detour = radius+distance(q,center)-distance(origin,center)
                score = sum(g for g,ch in gains)-self.departure_detour_weight*detour
                choices.append((score,q,[ch for gain,ch in gains]))
        if not choices or max(x[0] for x in choices) <= 0:
            return super()._localize(channel, client)
        _, point, channels = max(choices,key=lambda x:x[0])
        old_attempts.append(point)
        if client.current_channel in channels:
            channels.remove(client.current_channel)
            channels.insert(0, client.current_channel)
        for other in channels:
            if other not in self.cleared:
                self._measure(client, point, other)
        self.stats['departure_baselines'] = self.stats.get('departure_baselines',0)+1
        self.stats['departure_reads'] = self.stats.get('departure_reads',0)+len(channels)
        # Legacy run() now updates neighbours and reruns the mixed route solver.
        # It does not continue the destination chosen from stale observations.
        return channel in self.cleared


def get_class(name):
    tokens = set(name.split('_'))
    attrs = dict(shared_min_channels=1, shared_radius_m=50., shared_fresh_only=True)
    if 'base' in tokens:
        attrs['departure_enabled'] = False
    if 'sample' in tokens:
        attrs['departure_sample_score'] = True
    if 'conservative' in tokens:
        attrs['departure_error_factor'] = 2.
    if 'small' in tokens:
        attrs['departure_radii'] = (50.,)
    if 'large' in tokens:
        attrs['departure_radii'] = (100.,)
    if 'once' in tokens:
        attrs['departure_max_per_source'] = 1
    if 'cheap' in tokens:
        attrs['departure_detour_weight'] = 2.
    if 'low' in tokens:
        attrs.update(departure_min_radius=40., departure_min_gain=15., departure_min_leg=200.)
    if 'forward' in tokens:
        attrs['departure_forward'] = True
    if 'solo' in tokens:
        attrs['departure_batch'] = False
    return type(name, (SharedBaselineMixin, DepartureBaselineMixin, Ring12CoverPolicy), attrs)

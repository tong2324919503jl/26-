"""Teammate-inspired posterior-size gate for measurements at a paid stop.

The noiseless hypothetical bearing ranks a read only; the real bounded bearing
is still passed to the original conservative region update.
"""
import math
from problem3.geometry import distance, enclosing_circle, intersect_bearing
from problem3.experiments_v3.optical_band import AggressiveBandPolicy
from problem4.experiments_v3.posterior import Shared21Policy


class PredictedGainMixin:
    bystander_max_radius = 75.
    bystander_fraction = .55
    bystander_max_distance = 1100.

    def _update_neighbors(self, client):
        point = client.position
        for channel in list(self.regions):
            if channel in self.cleared:
                continue
            polygon = self.regions[channel]
            center, radius = enclosing_circle(polygon)
            if max(distance(point, vertex) for vertex in polygon) < 19.99:
                self._clear(client, point, channel)
                continue
            if radius < 35. or distance(point, center) > self.bystander_max_distance:
                continue
            if any(distance(point, old) < 60. for old, _ in self.observations[channel]):
                continue
            negatives = getattr(self, '_negative_history', getattr(self, 'negative_history', {}))
            if any(distance(point, old) < 1. for old in negatives.get(channel, [])):
                continue
            angle = math.degrees(math.atan2(center[1] - point[1], center[0] - point[0]))
            posterior = intersect_bearing(polygon, point, angle, self.config.bearing_error_deg)
            if posterior and enclosing_circle(posterior)[1] < min(self.bystander_max_radius,
                                                                  self.bystander_fraction * radius):
                self._measure(client, point, channel)


class Predicted3Policy(PredictedGainMixin, AggressiveBandPolicy):
    pass


class Predicted4Policy(PredictedGainMixin, Shared21Policy):
    pass


class Broader4Policy(Predicted4Policy):
    bystander_max_radius = 100.
    bystander_fraction = .7


class Broader3Policy(Predicted3Policy):
    bystander_max_radius = 100.
    bystander_fraction = .7

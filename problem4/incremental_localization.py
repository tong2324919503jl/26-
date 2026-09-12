"""Resumable directional localization; only observed responses change regions.

One scheduled step issues one clear or one measurement (a near response retains
the core immediate same-position clear). Radio-pair evidence survives replans;
full optical fallback queues are finite and never silently discarded.
"""
from __future__ import annotations

import math

from problem3.geometry import clip_halfplane, distance, enclosing_circle, optical_cover, polygon_centroid
from problem3.policy import SearchPolicy as CorePolicy
from problem4.routing import RoutingMixin
from problem4.speed_policy import SearchPolicy as ProductionPolicy


class SearchPolicy(ProductionPolicy):
    algorithm_version = "problem4_v5_incremental"
    route_milestones = False
    incremental_radio_rounds = 5
    optical_incremental = True

    def __init__(self, problem=4, strategy="adaptive", config=None, **options):
        if options:
            raise ValueError(f"Unknown options: {sorted(options)}")
        super().__init__(problem=problem, strategy=strategy, config=config)
        self._steps = {}
        self._union_failures = {}
        self._union_counts = {}
        self._union_cache = {}

    def _state(self, channel):
        return self._steps.setdefault(channel, {
            "rounds": 0, "pair": None, "exploratory": False,
            "measure_keys": set(), "clear_keys": set(), "fallback": None,
        })

    @staticmethod
    def _key(point):
        return tuple(round(value, 7) for value in point)

    def _clear(self, client, point, channel):
        # Bypass ProductionPolicy's multi-clear Unionmass wrapper. Its same
        # conservative candidate generator is called explicitly in _localize.
        result = CorePolicy._clear(self, client, point, channel)
        self._state(channel)["clear_keys"].add(self._key(point))
        if not result:
            self._union_failures.setdefault(channel, []).append(tuple(point))
        return result

    def _new_pair(self, channel, client):
        polygon = self.regions[channel]
        anchor, bearing = self.observations[channel][-1]
        theta = math.radians(bearing)
        forward = (math.cos(theta), math.sin(theta))
        side = (-forward[1], forward[0])
        longitudinal = [((p[0]-anchor[0])*forward[0] + (p[1]-anchor[1])*forward[1]) for p in polygon]
        low, high = min(longitudinal), max(longitudinal)
        step = low + self.localization_quantile * (high-low)
        width = max(self.localization_width_min, min(self.localization_width_max,
                    self.localization_width_fraction*step))
        width = max(width, step*math.tan(math.radians(self.config.bearing_error_deg))+.01)
        for _ in range(24):
            midpoint = (anchor[0]+step*forward[0], anchor[1]+step*forward[1])
            probes = [(midpoint[0]+sign*width*side[0], midpoint[1]+sign*width*side[1]) for sign in (-1,1)]
            if max(distance(q,v) for q in probes for v in polygon) < 999.99:
                break
            step = .5*step+.25*(low+high)
            width = max(width, step*math.tan(math.radians(self.config.bearing_error_deg))+.01)
        midpoint = (anchor[0]+step*forward[0], anchor[1]+step*forward[1])
        probes = [(midpoint[0]+sign*width*side[0], midpoint[1]+sign*width*side[1]) for sign in (-1,1)]
        probes.sort(key=lambda q: distance(client.position,q))
        return {
            "points": probes, "index": 0, "negatives": 0, "anchor": anchor,
            "forward": forward, "step": step,
            "in_range": all(distance(q,v)<999.999 for q in probes for v in polygon),
            "observation_count": len(self.observations[channel]),
        }

    def _current_pair(self, channel, state):
        pair = state["pair"]
        # A bystander positive may have refined this source between steps.
        # The previous proof would remain safe, but a fresh pair can be cheaper.
        if pair and pair["observation_count"] != len(self.observations[channel]):
            state["pair"] = pair = None
        return pair

    def _fallback_points(self, channel, state):
        if state["fallback"] is None:
            state["fallback"] = optical_cover(self.regions[channel], self.config.optical_spacing_m)
            self.stats["optical_fallbacks"] += 1
        return state["fallback"]

    def _peek(self, channel, client):
        state = self._state(channel)
        polygon = self.regions[channel]
        center, radius = enclosing_circle(polygon)
        if radius <= self.config.clear_guarantee_radius_m and self._key(center) not in state["clear_keys"]:
            return center
        union = self._union_point(channel, client)
        if union is not None:
            return union
        if radius <= self.config.exploratory_clear_radius_m and not state["exploratory"]:
            return polygon_centroid(polygon)
        pair = self._current_pair(channel, state)
        if pair:
            return pair["points"][pair["index"]]
        if state["rounds"] < self.incremental_radio_rounds:
            return self._new_pair(channel, client)["points"][0]
        points = self._fallback_points(channel, state)
        if not points:
            raise RuntimeError("Finite optical fallback exhausted without clearance")
        return min(points, key=lambda p: distance(client.position,p))

    def _route_goal(self, client, pending):
        if not self.route_milestones:
            return super()._route_goal(client,pending)
        original = self.regions
        estimates = {ch:[self._peek(ch,client)] if ch not in self.cleared else poly
                     for ch,poly in original.items()}
        # RoutingMixin only reads polygon centroids. It never performs actions
        # or clipping while this temporary set of stage endpoints is present.
        try:
            self.regions = estimates
            return RoutingMixin._route_goal(self,client,pending)
        finally:
            self.regions = original

    def _localize(self, channel, client):
        state = self._state(channel)
        polygon = self.regions[channel]
        center, radius = enclosing_circle(polygon)
        self.stats["incremental_steps"] = self.stats.get("incremental_steps",0)+1
        if radius <= self.config.clear_guarantee_radius_m and self._key(center) not in state["clear_keys"]:
            return self._clear(client,center,channel)
        union = self._union_point(channel,client)
        if union is not None:
            self._union_counts[channel] = self._union_counts.get(channel,0)+1
            self.stats["union_clear_actions"] = self.stats.get("union_clear_actions",0)+1
            return self._clear(client,union,channel)
        if radius <= self.config.exploratory_clear_radius_m and not state["exploratory"]:
            state["exploratory"] = True
            return self._clear(client,polygon_centroid(polygon),channel)
        pair = self._current_pair(channel,state)
        while pair is None and state["rounds"] < self.incremental_radio_rounds:
            pair = self._new_pair(channel,client)
            state["rounds"] += 1
            # Skipped repeated probes cannot count as new negative evidence.
            while pair["index"] < 2 and self._key(pair["points"][pair["index"]]) in state["measure_keys"]:
                pair["index"] += 1
            if pair["index"] == 2:
                pair = None
        state["pair"] = pair
        if pair is not None:
            point = pair["points"][pair["index"]]
            state["measure_keys"].add(self._key(point))
            result = self._measure(client,point,channel)
            self.stats["paired_probe_actions"] = self.stats.get("paired_probe_actions",0)+1
            pair["index"] += 1
            if channel in self.cleared:
                state["pair"] = None
                return True
            if result == "direction":
                state["pair"] = None
                return False
            pair["negatives"] += 1
            self.stats["negative_localization_reads"] += 1
            if pair["index"] == 2:
                if pair["negatives"] == 2 and pair["in_range"] and pair["step"] > 0:
                    forward, anchor = pair["forward"], pair["anchor"]
                    constant = pair["step"] + anchor[0]*forward[0] + anchor[1]*forward[1]
                    updated = clip_halfplane(self.regions[channel],forward[0],forward[1],constant)
                    if not updated:
                        raise RuntimeError("Paired negative observations contradict feasible region")
                    self.regions[channel] = updated
                    self.stats["paired_negative_clips"] = self.stats.get("paired_negative_clips",0)+1
                state["pair"] = None
            return False
        points = self._fallback_points(channel,state)
        if not points:
            raise RuntimeError("Finite optical fallback exhausted without clearance")
        index = min(range(len(points)), key=lambda i: distance(client.position,points[i]))
        return self._clear(client,points.pop(index),channel)

    def _result(self, reason, coverage_complete):
        result = super()._result(reason,coverage_complete)
        result["algorithm_version"] = self.algorithm_version
        result["effective_settings"].update(resumable_localization=True,
            route_milestones=self.route_milestones, radio_rounds=self.incremental_radio_rounds)
        return result

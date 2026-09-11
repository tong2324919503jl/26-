"""Local synthetic environment, NOT the official simulator.

Policies receive an ObservationClient facade, never source coordinates/counts.
All elapsed times below are virtual seconds except explicitly real_* fields.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path


class SimulationLimit(RuntimeError):
    pass


class LocalSimulator:
    def __init__(self, case: dict, *, record: bool = False, action_limit: int = 20000):
        self.case = case
        self.sources = {s['channel']: dict(s) for s in case['sources']}
        if len(self.sources) != len(case['sources']):
            raise ValueError('Channels must be unique')
        for ch, source in self.sources.items():
            if type(ch) is not int or not 1 <= ch <= 20:
                raise ValueError('Invalid source channel')
            values = [source['x'], source['y'], source['radius']]
            if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                       and math.isfinite(v) for v in values):
                raise ValueError('Invalid source number')
            orientation = source.get('orientation_deg')
            if orientation is not None and (not isinstance(orientation, (int, float))
                    or isinstance(orientation, bool) or not math.isfinite(orientation)):
                raise ValueError('Invalid source orientation')
            if math.hypot(source['x'], source['y']) > 1800.000001:
                raise ValueError('Source outside target disk')
            if not 1000 <= source['radius'] <= 1500:
                raise ValueError('Invalid receiving radius')
        self.position = (0.0, 0.0)
        self.current_channel = 1
        self.virtual_time_s = 0.0
        self.active = False
        self.started = 0.0
        self.cleared: set[int] = set()
        self.clear_times: list[float] = []
        self.actions = 0
        self.action_limit = action_limit
        self.counts = dict(measure=0, clear=0, failed_clear=0, switch=0, no_signal=0)
        self.movement_m = 0.0
        self.record = record
        self.events: list[dict] = []

    def check_budget(self):
        if not self.active:
            raise SimulationLimit('Simulation not active')
        if self.actions >= self.action_limit or self.virtual_time_s >= 360000:
            raise SimulationLimit('Local action or virtual-time limit reached')
        if time.perf_counter() - self.started > 1180:
            raise SimulationLimit('Local wall-clock limit reached')

    def _response(self, **fields):
        return dict(accepted=True, virtual_time_s=round(self.virtual_time_s, 6),
                    real_timestamp_ms=int(time.time() * 1000), **fields)

    def enter(self):
        if self.active or self.started:
            raise SimulationLimit('Enter once per case')
        self.active = True
        self.started = time.perf_counter()
        return self._response(max_virtual_duration_s=360000, max_real_duration_s=1200,
                              remaining_real_duration_s=1200)

    def exit(self):
        if not self.active:
            raise SimulationLimit('Simulation not active')
        self.active = False
        return self._response(exit_reason='user_exit')

    def _move(self, point, channel):
        self.check_budget()
        if type(channel) is not int or not 1 <= channel <= 20:
            raise ValueError('Channel must be an integer in 1..20')
        if len(point) != 2 or any(isinstance(v, bool) or not math.isfinite(v) or
                                  abs(v) > 2000000 for v in point):
            raise ValueError('Invalid position')
        distance = math.dist(self.position, point)
        self.movement_m += distance
        self.virtual_time_s += distance / 5.0
        self.position = tuple(float(v) for v in point)
        self.actions += 1

    def _error(self, channel):
        x, y = self.position
        key = f"{self.case['seed']}|{channel}|{x:.9f}|{y:.9f}".encode()
        u = int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), 'big') / (2**64-1)
        mode = self.case.get('noise', 'hash_uniform')
        if mode == 'extreme':
            return 1.0 if u >= .5 else -1.0
        if mode == 'bias':
            return (1.0 if channel % 2 else -1.0) * (.8 + .2*u)
        if mode == 'spatial':
            return math.sin(x/145.0 + y/217.0 + self.case['seed'] + channel)
        return 2*u - 1

    def _log(self, action, channel, response):
        if self.record:
            self.events.append(dict(action=action, position=self.position,
                                    channel=channel, response=response))
        return response

    def measure(self, point, channel):
        self._move(point, channel)
        switched = channel != self.current_channel
        self.counts['switch'] += int(switched)
        self.current_channel = channel
        self.virtual_time_s += 5 + int(switched)
        self.counts['measure'] += 1
        result = 'no_signal'
        source = self.sources.get(channel)
        fields = {}
        if source and channel not in self.cleared:
            dx, dy = self.position[0] - source['x'], self.position[1] - source['y']
            dist = math.hypot(dx, dy)
            orient = source.get('orientation_deg')
            visible = orient is None or (dx*math.cos(math.radians(orient)) +
                                         dy*math.sin(math.radians(orient))) >= -1e-9
            if dist <= source['radius'] + 1e-9 and visible:
                if dist <= 5:
                    result = 'near'
                else:
                    result = 'direction'
                    bearing = math.degrees(math.atan2(-dy, -dx))
                    fields['svd_deg'] = round((bearing + self._error(channel)) % 360, 2) % 360
        self.counts['no_signal'] += int(result == 'no_signal')
        return self._log('measure', channel, self._response(measure_result=result, **fields))

    def clear(self, point, channel):
        self._move(point, channel)
        source = self.sources.get(channel)
        success = bool(source and channel not in self.cleared and
                       math.dist(self.position, (source['x'], source['y'])) <= 20 + 1e-9)
        self.virtual_time_s += 5 if success else 3
        self.counts['clear'] += 1
        self.counts['failed_clear'] += int(not success)
        if success:
            self.cleared.add(channel)
            self.clear_times.append(self.virtual_time_s)
        return self._log('clear', channel, self._response(
            clear_result='success' if success else 'no_target_in_range'))

    def statistics(self):
        n, k = len(self.sources), len(self.cleared)
        return dict(source_count=n, cleared_count=k, cleared_fraction=k/n if n else 1.0,
                    virtual_time_s=self.virtual_time_s,
                    average_clear_time_s=self.virtual_time_s/k if k else None,
                    last_clear_time_s=self.clear_times[-1] if k else None,
                    time_to_90_percent_s=(self.clear_times[math.ceil(.9*n)-1]
                                          if k >= math.ceil(.9*n) and n else None),
                    movement_m=self.movement_m, actions=self.actions, **self.counts)


class ObservationClient:
    """Deliberate API boundary; strategy code only sees public observations."""
    __slots__ = ('__sim',)

    def __init__(self, simulator):
        self.__sim = simulator

    @property
    def position(self):
        return self.__sim.position

    @property
    def current_channel(self):
        return self.__sim.current_channel

    @property
    def virtual_time_s(self):
        return self.__sim.virtual_time_s

    def check_budget(self):
        self.__sim.check_budget()

    def measure(self, point, channel):
        return self.__sim.measure(point, channel)

    def clear(self, point, channel):
        return self.__sim.clear(point, channel)

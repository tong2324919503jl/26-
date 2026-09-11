"""Read-only v4 trajectories for offline probabilistic-stop experiments.

``capture_case(case)`` completes the ordinary deterministic policy. It returns
chronologically ordered checkpoints with separate ``public`` and ``truth``
objects. Only the outer evaluator adds truth labels, after the policy returns.
No probability model or early-stop decision is part of this collector.

Checkpoint public fields include ``time_s``, ``position``, ``current_channel``,
``detected_channels``, ``cleared_channels``, ``coverage_visited``, ``scans``,
``no_signal_by_channel``, ``counts``, ``eligibility`` and ``final_safe``.
Channel keys in no-signal dictionaries are strings for stable JSON roundtrips.
Histories are prefix snapshots: later observations cannot leak into an earlier
checkpoint. Consumers can find the first eligible checkpoint crossing their
threshold, retaining the final safe checkpoint as the deterministic fallback.
"""
from __future__ import annotations

from copy import deepcopy

from problem3.speed_policy import SearchPolicy as Problem3Policy
from problem4.speed_policy import SearchPolicy as Problem4Policy


class ProbabilityTraceMixin:
    """Instrumentation using policy state and the public client only.

    In both production MROs, the run loop calls ``self._route_goal``. P4's
    shared-baseline planner calls ``super()._route_goal`` inside ``_scan``;
    that bypasses this leading mixin. The explicit scan/action/depth guards
    additionally prevent nested route calls from becoming stopping boundaries.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.trace_checkpoints = []
        self.trace_no_signal_events = []
        self.trace_scans = []
        self._trace_negatives = {}
        self._trace_scan_stack = []
        self._trace_action_depth = 0
        self._trace_route_depth = 0
        self._trace_running = False
        self._trace_switches = 0

    def _trace_counts(self):
        measures = self.stats.get('measure_actions', 0)
        clears = self.stats.get('clear_actions', 0)
        return {'measure': measures, 'clear': clears,
                'failed_clear': self.stats.get('failed_clears', 0),
                'successful_clear': len(self.cleared),
                'switch': self._trace_switches,
                'no_signal': len(self.trace_no_signal_events),
                'actions': measures + clears}

    def _measure(self, client, point, channel):
        action_index = self._trace_counts()['actions'] + 1
        switched = client.current_channel != channel
        self._trace_action_depth += 1
        try:
            result = super()._measure(client, point, channel)
        finally:
            self._trace_action_depth -= 1
        # A rejected/invalid action raises in the parent and never reaches here.
        self._trace_switches += int(switched)
        point = tuple(point)
        for scan in self._trace_scan_stack:
            if point == scan['point'] and channel in scan['required_channels']:
                scan['measured_channels'].add(channel)
                scan['last_required_time_s'] = float(client.virtual_time_s)
        if result == 'no_signal':
            self._trace_negatives.setdefault(channel, []).append(point)
            self.trace_no_signal_events.append({
                'channel': channel, 'position': list(point),
                'time_s': float(client.virtual_time_s),
                'action_index': action_index,
                'measurement_index': self.stats['measure_actions'],
            })
        return result

    def _clear(self, client, point, channel):
        self._trace_action_depth += 1
        try:
            return super()._clear(client, point, channel)
        finally:
            self._trace_action_depth -= 1

    def _scan(self, client, point):
        start_count = len(self.coverage_visited)
        scan = {
            'point': tuple(point),
            'required_channels': set(range(1, 21)) - set(self.regions) - self.cleared,
            'measured_channels': set(),
            'start_time_s': float(client.virtual_time_s),
            'last_required_time_s': float(client.virtual_time_s),
        }
        self._trace_scan_stack.append(scan)
        try:
            return super()._scan(client, point)
        finally:
            self._trace_scan_stack.pop()
            visited = self.coverage_visited[start_count:]
            if (scan['point'] in map(tuple, visited)
                    and scan['required_channels'] <= scan['measured_channels']):
                self.trace_scans.append({
                    'position': list(scan['point']),
                    'unknown_channels': sorted(scan['required_channels']),
                    'measured_channels': sorted(scan['measured_channels']),
                    'start_time_s': scan['start_time_s'],
                    'end_time_s': scan['last_required_time_s'],
                    'return_time_s': float(client.virtual_time_s),
                })

    def _trace_checkpoint(self, client, *, final_result=None):
        detected = set(self.regions) | self.cleared
        known_unresolved = detected - self.cleared
        eligible = len(self.cleared) >= 10 and not known_unresolved
        is_final = final_result is not None
        if not eligible and not is_final:
            return
        final_safe = bool(is_final and final_result.get('completion_certified')
                          and not known_unresolved)
        public = {
            'time_s': float(client.virtual_time_s),
            'position': list(client.position),
            'current_channel': client.current_channel,
            'detected_channels': sorted(detected),
            'cleared_channels': sorted(self.cleared),
            'coverage_visited': [list(p) for p in self.coverage_visited],
            'scans': deepcopy(self.trace_scans),
            'no_signal_by_channel': {
                str(ch): [list(p) for p in points]
                for ch, points in sorted(self._trace_negatives.items())
            },
            'counts': self._trace_counts(),
            'eligibility': eligible,
            'final_safe': final_safe,
            'boundary': 'final' if is_final else 'route_goal',
            'coverage_complete': bool(is_final and final_result.get('coverage_complete')),
        }
        self.trace_checkpoints.append({'index': len(self.trace_checkpoints),
                                       'public': public})

    def _route_goal(self, client, pending):
        if (self._trace_running and not self._trace_scan_stack
                and not self._trace_action_depth and not self._trace_route_depth):
            self._trace_checkpoint(client)
        self._trace_route_depth += 1
        try:
            return super()._route_goal(client, pending)
        finally:
            self._trace_route_depth -= 1

    def run(self, client):
        if self._trace_running or self.trace_checkpoints or self.trace_scans:
            raise RuntimeError('Use a fresh trace policy for each run')
        self._trace_running = True
        try:
            result = super().run(client)
            # A 16-source return or exhausted while-loop has no next route call.
            self._trace_checkpoint(client, final_result=result)
            return result
        finally:
            self._trace_running = False


class TracedProblem3Policy(ProbabilityTraceMixin, Problem3Policy):
    pass


class TracedProblem4Policy(ProbabilityTraceMixin, Problem4Policy):
    pass


def capture_case(case: dict, *, action_limit: int = 20000) -> dict:
    """Complete one baseline case, then label checkpoints outside the policy.

    A failed baseline is returned with ``error`` and no claimed safe endpoint;
    consumers must not silently treat it as a successful early-stop trial.
    This function performs no file writes, platform requests, or optimization.
    """
    from problem3.simulator import LocalSimulator, ObservationClient

    problem = case.get('problem')
    if type(problem) is not int or problem not in (3, 4):
        raise ValueError('case.problem must be 3 or 4')
    simulator = LocalSimulator(case, action_limit=action_limit)
    policy = (TracedProblem3Policy if problem == 3 else TracedProblem4Policy)()
    result = None
    error = None
    simulator.enter()
    try:
        result = policy.run(ObservationClient(simulator))
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
    finally:
        simulator.exit()
    statistics = simulator.statistics()

    # Truth is deliberately confined to this external, post-run evaluator.
    actual_channels = set(simulator.sources)
    checkpoints = deepcopy(policy.trace_checkpoints)
    for checkpoint in checkpoints:
        cleared = set(checkpoint['public']['cleared_channels'])
        remaining = actual_channels - cleared
        checkpoint['truth'] = {
            'source_count': len(actual_channels),
            'remaining_count': len(remaining),
            'all_cleared': not remaining,
        }
    final_safe = next((c['index'] for c in reversed(checkpoints)
                       if c['public']['final_safe']), None)
    return {
        'data_origin': 'local_simulation_not_official',
        'problem': problem, 'case_id': case.get('case_id'),
        'checkpoints': checkpoints,
        'final_safe_index': final_safe,
        'baseline_result': result,
        'baseline_statistics': statistics,
        'no_signal_events': deepcopy(policy.trace_no_signal_events),
        'error': error,
    }

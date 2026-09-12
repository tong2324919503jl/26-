"""Compose analytical visibility ranking with resumable hard localization."""
from problem4.incremental_localization import SearchPolicy as IncrementalPolicy
from problem4.visibility import VisibilityMixin


class SearchPolicy(IncrementalPolicy, VisibilityMixin):
    algorithm_version = "problem4_v5_incremental_visibility"

    def _new_pair(self, channel, client):
        state = self._state(channel)
        step, forward, points, in_range = self._visibility_choice(
            channel,client,state['measure_keys'])
        return {
            'points':list(points), 'index':0, 'negatives':0,
            'anchor':self.observations[channel][-1][0],
            'forward':forward, 'step':step, 'in_range':in_range,
            'observation_count':len(self.observations[channel]),
        }

    def _result(self, reason, coverage_complete):
        result = super()._result(reason,coverage_complete)
        result['visibility_ranking_only'] = True
        result['effective_settings'].update(visibility_mode=self.visibility_mode,
            visibility_nodes=self.visibility_nodes, visibility_quantiles=self.visibility_quantiles,
            visibility_directional_weight=self.visibility_directional_weight,
            visibility_uncertainty_weight=self.visibility_uncertainty_weight)
        return result

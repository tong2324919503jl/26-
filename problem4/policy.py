"""Q4 version 2: certified coverage, historical bearings, and shorter routes.

The previous delivery remains available as problem4.legacy_policy and through
--strategy legacy. Production algorithms do not import development experiments.
"""
from __future__ import annotations

from problem4.coverage import static_coverage_points
from problem4.localization import LocalizationMixin
from problem4.routing import RoutingMixin
from problem4.legacy_policy import (
    SearchPolicy as LegacyPolicy,
    covering_triangles, directional_coverage_points, polar_covering_triangles,
    polar_coverage_points, triangle_contains,
)


class SearchPolicy(RoutingMixin, LocalizationMixin, LegacyPolicy):
    """Keep completion proofs independent of heuristic route estimates."""

    def coverage_points(self):
        if self.strategy == "adaptive":
            return static_coverage_points()
        return super().coverage_points()

    def _result(self, reason, coverage_complete):
        result = super()._result(reason, coverage_complete)
        if self.strategy == "adaptive":
            result["algorithm_version"] = "problem4_v2"
            result["effective_settings"] = {
                "coverage_points": 23,
                "history_slices": self.localization_history_slices,
                "probe_quantile": self.localization_quantile,
                "probe_width_fraction": self.localization_width_fraction,
                "probe_min_width_m": self.localization_width_min,
                "probe_rounds": self.localization_rounds,
                "route_initial_constructions": self.escape_starts,
                "reuse_previous_route": self.escape_warm,
                "max_relocated_chain": self.escape_chain,
                "expected_scan_cost_weight": self.escape_info_weight,
            }
        return result

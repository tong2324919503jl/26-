"""Problem 4 speed candidate with independently certified 22-station coverage."""
from problem4.search_layout import coverage_points
from problem4.bystander import PredictedGainMixin
from problem4.optical_repair import UnionmassMixin
from problem4.policy import SearchPolicy as PreviousPolicy
from problem4.shared_baseline import SharedBaselineMixin




class SearchPolicy(PredictedGainMixin, UnionmassMixin, SharedBaselineMixin, PreviousPolicy):
    algorithm_version = "problem4_v4"
    shared_min_channels = 1
    shared_radius_m = 50.
    shared_fresh_only = True

    def __init__(self, problem=4, strategy="adaptive", config=None):
        if problem != 4 or strategy != "adaptive":
            raise ValueError("The speed policy requires problem 4, strategy adaptive")
        super().__init__(problem=problem, strategy=strategy, config=config)

    def coverage_points(self):
        points = coverage_points()
        self._shared_pending = points
        return points

    def _result(self, reason, coverage_complete):
        result = super()._result(reason, coverage_complete)
        result["algorithm_version"] = self.algorithm_version
        result["effective_settings"].update(coverage_points=22, shared_baseline_m=50.,
                                             optical_repair_max_actions=16, optical_repair_mode="unionmass",
                                             bystander_prediction_radius_m=75.)
        return result

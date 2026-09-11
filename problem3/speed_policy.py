"""Problem 3 speed candidate; the shared runner controls arena entry and exit."""
from problem3.lookahead import AggressiveBandPolicy


class SearchPolicy(AggressiveBandPolicy):
    algorithm_version = "problem3_v4"

    def __init__(self, problem=3, strategy="adaptive", config=None):
        if problem != 3 or strategy != "adaptive":
            raise ValueError("The speed policy requires problem 3, strategy adaptive")
        super().__init__(problem=problem, strategy=strategy, config=config)

    def _result(self, reason, coverage_complete):
        result = super()._result(reason, coverage_complete)
        result["algorithm_version"] = self.algorithm_version
        return result

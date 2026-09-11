"""Frozen P3 development candidate for composition with coverage experiments."""
from problem3.experiments_v3.policy import (
    AngularNeighborsMixin, BatchBaselineMixin, RotatingIncrementalPolicy,
)


class SearchPolicy(AngularNeighborsMixin, BatchBaselineMixin, RotatingIncrementalPolicy):
    batch_step = 100.
    batch_choice = "information"
    neighbor_angle_span = 40.

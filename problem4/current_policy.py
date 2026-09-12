"""Frozen P4 research candidate; complete discovery remains mandatory."""
from problem4.discovery_policy import SearchPolicy as ParentPolicy


class SearchPolicy(ParentPolicy):
    algorithm_version='problem4_v5_visibility_discovery'

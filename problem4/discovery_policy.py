"""Frozen visibility/incremental localization plus geometric scan ordering."""
from problem4.global_discovery import GlobalDiscoveryMixin
from problem4.incremental_visibility import SearchPolicy as IncrementalVisibility


class SearchPolicy(GlobalDiscoveryMixin, IncrementalVisibility):
    algorithm_version = 'problem4_v5_incremental_visibility_discovery'
    discovery_mode = 'scan_savings'
    route_milestones = False

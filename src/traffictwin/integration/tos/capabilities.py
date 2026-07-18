"""Evidence-based capability manifest for the read-only TOS Data adapter."""

from traffictwin.config.capabilities import (
    CapabilityManifest,
    CapabilitySet,
    CapabilitySupport,
)


def tos_data_capability_manifest() -> CapabilityManifest:
    """Return only capabilities established by the inspected data package."""

    unknown = CapabilitySupport.UNKNOWN
    return CapabilityManifest(
        adapter="tos_data_read_only",
        supports=CapabilitySet(
            seed_import=CapabilitySupport.FALSE,
            seed_export=CapabilitySupport.FALSE,
            run_bundle_import=CapabilitySupport.FALSE,
            direct_launch=CapabilitySupport.FALSE,
            asynchronous_launch=CapabilitySupport.FALSE,
            task_arrival_multiplier=unknown,
            workload_class_mix=unknown,
            workload_ordering=unknown,
            vehicle_count=unknown,
            vehicle_tier_mix=unknown,
            rsu_count=unknown,
            rsu_capacity=unknown,
            rsu_placement=unknown,
            rsu_failure=unknown,
            action_toggles=unknown,
            signal_timing=unknown,
            lane_closure=unknown,
        ),
    )

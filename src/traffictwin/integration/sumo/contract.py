"""Evidence-bounded source contract for Eclipse SUMO result ingestion."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.config.capabilities import CapabilityManifest, CapabilitySet, CapabilitySupport
from traffictwin.integration.sumo.models import SUMO_ADAPTER_VERSION


class SumoContractModel(BaseModel):
    """Strict base model for SUMO source-contract artifacts."""

    model_config = ConfigDict(extra="forbid")


class SumoFieldMapping(SumoContractModel):
    """One explicitly supported source mapping."""

    source: str
    destination: str | None
    unit: str | None
    status: str
    rule: str


class SumoSourceContract(SumoContractModel):
    """Machine-readable boundary of the v1 SUMO results adapter."""

    schema_version: str = "1.0"
    adapter_version: str = SUMO_ADAPTER_VERSION
    supported_sumo_versions: list[str]
    documentation: dict[str, str]
    mappings: list[SumoFieldMapping]
    capabilities: CapabilityManifest
    required_provenance: list[str]
    unsupported: list[str] = Field(default_factory=list)
    interpretation_limits: list[str] = Field(default_factory=list)

    def to_json(self) -> str:
        """Return a stable formatted JSON representation."""

        return self.model_dump_json(indent=2)


def sumo_results_capability_manifest() -> CapabilityManifest:
    """Return the deliberately import-only capability manifest."""

    disabled = CapabilitySupport.FALSE
    return CapabilityManifest(
        adapter="sumo_results_v1",
        supports=CapabilitySet(
            seed_import=disabled,
            seed_export=disabled,
            run_bundle_import=CapabilitySupport.TRUE,
            streaming_canonicalisation=disabled,
            time_windowed_metrics=disabled,
            latency_percentile_family=disabled,
            energy_metric_family=disabled,
            fairness_metric_family=disabled,
            spatial_rsu_metric_family=disabled,
            custom_metric_plugin_api=CapabilitySupport.TRUE,
            temporal_degradation_diagnosis=disabled,
            declarative_rule_authoring=CapabilitySupport.TRUE,
            fairness_disparity_diagnosis=disabled,
            energy_anomaly_diagnosis=disabled,
            nearest_flip_analysis=disabled,
            threshold_sensitivity_sweep=disabled,
            cross_rule_reasoning=disabled,
            paired_statistical_study=disabled,
            n_way_policy_ranking=disabled,
            equivalence_testing=disabled,
            regression_gate=disabled,
            power_analysis=disabled,
            difference_provenance=disabled,
            provenance_graph_export=disabled,
            provenance_completeness_score=disabled,
            parameter_sweep_composer=disabled,
            scenario_mutation_operators=disabled,
            measurement_noise_dropout_models=disabled,
            latex_research_export=disabled,
            analyst_annotations=disabled,
            structured_report_diffing=disabled,
            one_page_executive_summary=disabled,
            full_text_registry_search=disabled,
            registry_schema_migrations=disabled,
            canonical_table_caching=disabled,
            environment_doctor=disabled,
            ro_crate_archival_export=disabled,
            generalised_external_source_contract=CapabilitySupport.TRUE,
            direct_launch=disabled,
            asynchronous_launch=disabled,
            task_arrival_multiplier=disabled,
            workload_class_mix=disabled,
            workload_ordering=disabled,
            vehicle_count=disabled,
            vehicle_tier_mix=disabled,
            rsu_count=disabled,
            rsu_capacity=disabled,
            rsu_placement=disabled,
            rsu_failure=disabled,
            action_toggles=disabled,
            signal_timing=disabled,
            lane_closure=disabled,
        ),
    )


def sumo_source_contract() -> SumoSourceContract:
    """Return the versioned SUMO XML-to-TrafficTwin contract."""

    return SumoSourceContract(
        supported_sumo_versions=["1.27.x"],
        documentation={
            "tripinfo": "https://sumo.dlr.de/docs/Simulation/Output/TripInfo.html",
            "summary": "https://sumo.dlr.de/docs/Simulation/Output/Summary.html",
            "licence": "https://github.com/eclipse-sumo/sumo/blob/main/LICENSE",
        },
        mappings=[
            SumoFieldMapping(
                source="tripinfo.tripinfo@id",
                destination="TripRecord.trip_id and TripRecord.vehicle_id",
                unit=None,
                status="supported",
                rule="The SUMO vehicle identifier is retained unchanged.",
            ),
            SumoFieldMapping(
                source="tripinfo.tripinfo@depart",
                destination="TripRecord.departure_time_s",
                unit="s",
                status="supported_when_non_negative",
                rule="Undeparted records use SUMO's negative sentinel and remain source-only.",
            ),
            SumoFieldMapping(
                source="tripinfo.tripinfo@arrival",
                destination="TripRecord.arrival_time_s",
                unit="s",
                status="supported_for_completed_trips",
                rule="Negative arrival or a vaporized reason becomes an incomplete canonical trip.",
            ),
            SumoFieldMapping(
                source="tripinfo.tripinfo@duration",
                destination="TripRecord.duration_s",
                unit="s",
                status="supported_for_completed_trips",
                rule=(
                    "Elapsed time for unfinished/vaporized records is not relabelled as trip "
                    "duration."
                ),
            ),
            SumoFieldMapping(
                source="summary.step",
                destination=None,
                unit=None,
                status="source_specific_only",
                rule=(
                    "Summary running counts are occupancy snapshots, not interval flow counts; "
                    "all documented fields remain typed SumoSummaryStep evidence."
                ),
            ),
            SumoFieldMapping(
                source="fcd-export",
                destination=None,
                unit=None,
                status="unsupported",
                rule="FCD requires a separately approved explicit mapping contract.",
            ),
        ],
        capabilities=sumo_results_capability_manifest(),
        required_provenance=[
            "scenario_id",
            "scenario_url",
            "sumo_version",
            "licence_spdx",
            "retrieval_date",
            "redistribution_allowed",
            "raw XML SHA-256 checksums",
        ],
        unsupported=[
            "SUMO launch or rerun",
            "FCD canonicalisation",
            "personinfo and containerinfo canonicalisation",
            "summary-to-canonical traffic count mapping",
            "route identity not present in tripinfo output",
        ],
        interpretation_limits=[
            "A validated output package proves file compatibility, not scenario realism.",
            "SUMO summary ended may include vehicles removed without reaching their destination.",
            "Raw XML remains authoritative and is never rewritten by this adapter.",
        ],
    )

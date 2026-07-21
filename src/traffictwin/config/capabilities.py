"""Capability manifest models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CapabilitySupport(StrEnum):
    """Three-valued capability support state."""

    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"

    def to_manifest_value(self) -> bool | str:
        """Return a YAML-friendly representation."""

        if self is CapabilitySupport.TRUE:
            return True
        if self is CapabilitySupport.FALSE:
            return False
        return "unknown"


def _coerce_capability(value: object) -> CapabilitySupport:
    if isinstance(value, CapabilitySupport):
        return value
    if isinstance(value, bool):
        return CapabilitySupport.TRUE if value else CapabilitySupport.FALSE
    if isinstance(value, str):
        normalised = value.lower()
        if normalised in {"true", "supported"}:
            return CapabilitySupport.TRUE
        if normalised in {"false", "unsupported"}:
            return CapabilitySupport.FALSE
        if normalised == "unknown":
            return CapabilitySupport.UNKNOWN
    msg = f"capability must be true, false, or unknown; got {value!r}"
    raise ValueError(msg)


class CapabilitySet(BaseModel):
    """Supported actions and controls for an environment adapter."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    seed_import: CapabilitySupport = CapabilitySupport.TRUE
    seed_export: CapabilitySupport = CapabilitySupport.TRUE
    run_bundle_import: CapabilitySupport = CapabilitySupport.TRUE
    streaming_canonicalisation: CapabilitySupport = CapabilitySupport.UNKNOWN
    time_windowed_metrics: CapabilitySupport = CapabilitySupport.UNKNOWN
    latency_percentile_family: CapabilitySupport = CapabilitySupport.UNKNOWN
    energy_metric_family: CapabilitySupport = CapabilitySupport.UNKNOWN
    fairness_metric_family: CapabilitySupport = CapabilitySupport.UNKNOWN
    spatial_rsu_metric_family: CapabilitySupport = CapabilitySupport.UNKNOWN
    custom_metric_plugin_api: CapabilitySupport = CapabilitySupport.UNKNOWN
    temporal_degradation_diagnosis: CapabilitySupport = CapabilitySupport.UNKNOWN
    declarative_rule_authoring: CapabilitySupport = CapabilitySupport.UNKNOWN
    fairness_disparity_diagnosis: CapabilitySupport = CapabilitySupport.UNKNOWN
    energy_anomaly_diagnosis: CapabilitySupport = CapabilitySupport.UNKNOWN
    nearest_flip_analysis: CapabilitySupport = CapabilitySupport.UNKNOWN
    threshold_sensitivity_sweep: CapabilitySupport = CapabilitySupport.UNKNOWN
    cross_rule_reasoning: CapabilitySupport = CapabilitySupport.UNKNOWN
    paired_statistical_study: CapabilitySupport = CapabilitySupport.UNKNOWN
    n_way_policy_ranking: CapabilitySupport = CapabilitySupport.UNKNOWN
    equivalence_testing: CapabilitySupport = CapabilitySupport.UNKNOWN
    regression_gate: CapabilitySupport = CapabilitySupport.UNKNOWN
    power_analysis: CapabilitySupport = CapabilitySupport.UNKNOWN
    difference_provenance: CapabilitySupport = CapabilitySupport.UNKNOWN
    provenance_graph_export: CapabilitySupport = CapabilitySupport.UNKNOWN
    provenance_completeness_score: CapabilitySupport = CapabilitySupport.UNKNOWN
    parameter_sweep_composer: CapabilitySupport = CapabilitySupport.UNKNOWN
    scenario_mutation_operators: CapabilitySupport = CapabilitySupport.UNKNOWN
    measurement_noise_dropout_models: CapabilitySupport = CapabilitySupport.UNKNOWN
    latex_research_export: CapabilitySupport = CapabilitySupport.UNKNOWN
    analyst_annotations: CapabilitySupport = CapabilitySupport.UNKNOWN
    structured_report_diffing: CapabilitySupport = CapabilitySupport.UNKNOWN
    one_page_executive_summary: CapabilitySupport = CapabilitySupport.UNKNOWN
    full_text_registry_search: CapabilitySupport = CapabilitySupport.UNKNOWN
    registry_schema_migrations: CapabilitySupport = CapabilitySupport.UNKNOWN
    canonical_table_caching: CapabilitySupport = CapabilitySupport.UNKNOWN
    environment_doctor: CapabilitySupport = CapabilitySupport.UNKNOWN
    ro_crate_archival_export: CapabilitySupport = CapabilitySupport.UNKNOWN
    generalised_external_source_contract: CapabilitySupport = CapabilitySupport.UNKNOWN
    direct_launch: CapabilitySupport = CapabilitySupport.FALSE
    asynchronous_launch: CapabilitySupport = CapabilitySupport.FALSE
    task_arrival_multiplier: CapabilitySupport = CapabilitySupport.UNKNOWN
    workload_class_mix: CapabilitySupport = CapabilitySupport.UNKNOWN
    workload_ordering: CapabilitySupport = CapabilitySupport.UNKNOWN
    vehicle_count: CapabilitySupport = CapabilitySupport.UNKNOWN
    vehicle_tier_mix: CapabilitySupport = CapabilitySupport.UNKNOWN
    rsu_count: CapabilitySupport = CapabilitySupport.UNKNOWN
    rsu_capacity: CapabilitySupport = CapabilitySupport.UNKNOWN
    rsu_placement: CapabilitySupport = CapabilitySupport.UNKNOWN
    rsu_failure: CapabilitySupport = CapabilitySupport.UNKNOWN
    action_toggles: CapabilitySupport = CapabilitySupport.UNKNOWN
    signal_timing: CapabilitySupport = CapabilitySupport.UNKNOWN
    lane_closure: CapabilitySupport = CapabilitySupport.UNKNOWN

    @field_validator("*", mode="before")
    @classmethod
    def validate_capability(cls, value: object) -> CapabilitySupport:
        return _coerce_capability(value)

    def as_manifest_dict(self) -> dict[str, bool | str]:
        """Return a serialisable dictionary using booleans and `unknown`."""

        return {key: getattr(self, key).to_manifest_value() for key in type(self).model_fields}


class CapabilityManifest(BaseModel):
    """Environment capability manifest."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    adapter: str = Field(min_length=1)
    supports: CapabilitySet = Field(default_factory=CapabilitySet)

    def as_manifest_dict(self) -> dict[str, dict[str, str | dict[str, bool | str]]]:
        """Return the documented manifest shape."""

        return {
            "environment": {
                "adapter": self.adapter,
                "supports": self.supports.as_manifest_dict(),
            }
        }


RANDY_ENVIRONMENT_CAPABILITIES = (
    "direct_launch",
    "asynchronous_launch",
    "task_arrival_multiplier",
    "workload_class_mix",
    "workload_ordering",
    "vehicle_count",
    "vehicle_tier_mix",
    "rsu_count",
    "rsu_capacity",
    "rsu_placement",
    "rsu_failure",
    "action_toggles",
    "signal_timing",
    "lane_closure",
)


def default_export_import_manifest() -> CapabilityManifest:
    """Return the safe default manifest for import/export-only work."""

    return CapabilityManifest(
        adapter="generic_csv",
        supports=CapabilitySet(
            streaming_canonicalisation=CapabilitySupport.TRUE,
            time_windowed_metrics=CapabilitySupport.TRUE,
            latency_percentile_family=CapabilitySupport.TRUE,
            energy_metric_family=CapabilitySupport.TRUE,
            fairness_metric_family=CapabilitySupport.TRUE,
            spatial_rsu_metric_family=CapabilitySupport.TRUE,
            custom_metric_plugin_api=CapabilitySupport.TRUE,
            temporal_degradation_diagnosis=CapabilitySupport.TRUE,
            declarative_rule_authoring=CapabilitySupport.TRUE,
            fairness_disparity_diagnosis=CapabilitySupport.TRUE,
            energy_anomaly_diagnosis=CapabilitySupport.TRUE,
            nearest_flip_analysis=CapabilitySupport.TRUE,
            threshold_sensitivity_sweep=CapabilitySupport.TRUE,
            cross_rule_reasoning=CapabilitySupport.TRUE,
            paired_statistical_study=CapabilitySupport.TRUE,
            n_way_policy_ranking=CapabilitySupport.TRUE,
            equivalence_testing=CapabilitySupport.TRUE,
            regression_gate=CapabilitySupport.TRUE,
            power_analysis=CapabilitySupport.TRUE,
            difference_provenance=CapabilitySupport.TRUE,
            provenance_graph_export=CapabilitySupport.TRUE,
            provenance_completeness_score=CapabilitySupport.TRUE,
            parameter_sweep_composer=CapabilitySupport.TRUE,
            scenario_mutation_operators=CapabilitySupport.TRUE,
            measurement_noise_dropout_models=CapabilitySupport.TRUE,
            latex_research_export=CapabilitySupport.TRUE,
            analyst_annotations=CapabilitySupport.TRUE,
            structured_report_diffing=CapabilitySupport.TRUE,
            one_page_executive_summary=CapabilitySupport.TRUE,
            full_text_registry_search=CapabilitySupport.TRUE,
            registry_schema_migrations=CapabilitySupport.TRUE,
            canonical_table_caching=CapabilitySupport.TRUE,
            environment_doctor=CapabilitySupport.TRUE,
            ro_crate_archival_export=CapabilitySupport.TRUE,
            generalised_external_source_contract=CapabilitySupport.TRUE,
        ),
    )


def manifest_to_plain_dict(manifest: CapabilityManifest) -> dict[str, Any]:
    """Return a plain dictionary suitable for YAML dumping."""

    return manifest.as_manifest_dict()

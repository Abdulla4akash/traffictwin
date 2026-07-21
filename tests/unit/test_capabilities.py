from __future__ import annotations

import pytest

from traffictwin.config.capabilities import (
    RANDY_ENVIRONMENT_CAPABILITIES,
    CapabilitySet,
    CapabilitySupport,
    default_export_import_manifest,
)


def test_capability_coerces_true_false_unknown() -> None:
    capabilities = CapabilitySet(
        direct_launch=True,
        asynchronous_launch=False,
        task_arrival_multiplier="unknown",
    )

    assert capabilities.direct_launch is CapabilitySupport.TRUE
    assert capabilities.asynchronous_launch is CapabilitySupport.FALSE
    assert capabilities.task_arrival_multiplier is CapabilitySupport.UNKNOWN


def test_invalid_capability_value_rejected() -> None:
    with pytest.raises(ValueError, match="capability must be true, false, or unknown"):
        CapabilitySet(direct_launch="maybe")


def test_default_manifest_is_export_import_only() -> None:
    manifest = default_export_import_manifest()

    assert manifest.adapter == "generic_csv"
    assert manifest.supports.seed_export is CapabilitySupport.TRUE
    assert manifest.supports.run_bundle_import is CapabilitySupport.TRUE
    assert manifest.supports.streaming_canonicalisation is CapabilitySupport.TRUE
    assert manifest.supports.time_windowed_metrics is CapabilitySupport.TRUE
    assert manifest.supports.latency_percentile_family is CapabilitySupport.TRUE
    assert manifest.supports.energy_metric_family is CapabilitySupport.TRUE
    assert manifest.supports.fairness_metric_family is CapabilitySupport.TRUE
    assert manifest.supports.spatial_rsu_metric_family is CapabilitySupport.TRUE
    assert manifest.supports.custom_metric_plugin_api is CapabilitySupport.TRUE
    assert manifest.supports.temporal_degradation_diagnosis is CapabilitySupport.TRUE
    assert manifest.supports.declarative_rule_authoring is CapabilitySupport.TRUE
    assert manifest.supports.fairness_disparity_diagnosis is CapabilitySupport.TRUE
    assert manifest.supports.energy_anomaly_diagnosis is CapabilitySupport.TRUE
    assert manifest.supports.nearest_flip_analysis is CapabilitySupport.TRUE
    assert manifest.supports.threshold_sensitivity_sweep is CapabilitySupport.TRUE
    assert manifest.supports.cross_rule_reasoning is CapabilitySupport.TRUE
    assert manifest.supports.paired_statistical_study is CapabilitySupport.TRUE
    assert manifest.supports.n_way_policy_ranking is CapabilitySupport.TRUE
    assert manifest.supports.equivalence_testing is CapabilitySupport.TRUE
    assert manifest.supports.regression_gate is CapabilitySupport.TRUE
    assert manifest.supports.power_analysis is CapabilitySupport.TRUE
    assert manifest.supports.difference_provenance is CapabilitySupport.TRUE
    assert manifest.supports.provenance_graph_export is CapabilitySupport.TRUE
    assert manifest.supports.provenance_completeness_score is CapabilitySupport.TRUE
    assert manifest.supports.parameter_sweep_composer is CapabilitySupport.TRUE
    assert manifest.supports.scenario_mutation_operators is CapabilitySupport.TRUE
    assert manifest.supports.measurement_noise_dropout_models is CapabilitySupport.TRUE
    assert manifest.supports.latex_research_export is CapabilitySupport.TRUE
    assert manifest.supports.analyst_annotations is CapabilitySupport.TRUE
    assert manifest.supports.structured_report_diffing is CapabilitySupport.TRUE
    assert manifest.supports.one_page_executive_summary is CapabilitySupport.TRUE
    assert manifest.supports.full_text_registry_search is CapabilitySupport.TRUE
    assert manifest.supports.registry_schema_migrations is CapabilitySupport.TRUE
    assert manifest.supports.canonical_table_caching is CapabilitySupport.TRUE
    assert manifest.supports.environment_doctor is CapabilitySupport.TRUE
    assert manifest.supports.ro_crate_archival_export is CapabilitySupport.TRUE
    assert manifest.supports.generalised_external_source_contract is CapabilitySupport.TRUE
    assert manifest.supports.direct_launch is CapabilitySupport.FALSE
    assert manifest.supports.asynchronous_launch is CapabilitySupport.FALSE


def test_no_unsupported_randy_capability_defaults_to_true() -> None:
    manifest = default_export_import_manifest()

    for field_name in RANDY_ENVIRONMENT_CAPABILITIES:
        assert getattr(manifest.supports, field_name) is not CapabilitySupport.TRUE


def test_manifest_plain_dict_uses_bools_and_unknown() -> None:
    supports = default_export_import_manifest().supports.as_manifest_dict()

    assert supports["seed_export"] is True
    assert supports["direct_launch"] is False
    assert supports["rsu_capacity"] == "unknown"

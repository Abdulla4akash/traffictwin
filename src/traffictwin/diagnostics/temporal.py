"""Library orchestration for fixed-window EvidencePack construction and R6 evaluation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.evidence.builder import attach_temporal_evidence, build_evidence_pack
from traffictwin.evidence.pack import EvidencePack
from traffictwin.evidence.temporal import TemporalEvidence, TemporalEvidenceConfig
from traffictwin.ingestion.bundle import BundleValidationResult
from traffictwin.metrics.engine import compute_metrics_for_bundle, utc_now
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.plugins import MetricPluginRegistry
from traffictwin.metrics.windowed import (
    WindowedMetricConfig,
    WindowedMetricSeries,
    compute_windowed_metrics_for_bundle,
)
from traffictwin.rules.config import R6Config, RuleSetConfig
from traffictwin.rules.engine import evaluate_rules
from traffictwin.rules.models import RuleResult
from traffictwin.rules.r6_temporal_degradation import RecoveryAssessment


class TemporalDiagnosticAnalysis(BaseModel):
    """Complete typed R6 evaluation artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    temporal_evidence: TemporalEvidence
    evidence_pack: EvidencePack
    diagnostic_report: DiagnosticReport
    r6_result: RuleResult

    def to_json(self) -> str:
        """Return readable JSON."""

        return self.model_dump_json(indent=2)


class TemporalDiagnosisContract(BaseModel):
    """Machine-readable public boundary for DIA-01 temporal diagnosis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    capability: Literal["DIA-01"] = "DIA-01"
    rule_id: Literal["R6"] = "R6"
    rule_version: Literal["1.0"] = "1.0"
    ruleset_version: Literal["1.3"] = "1.3"
    evidence_boundary: Literal["EvidencePack.temporal_evidence"] = "EvidencePack.temporal_evidence"
    default_temporal_config: TemporalEvidenceConfig
    default_r6_config: R6Config
    missing_interval_policy: Literal["visible_breaks_consecutive_runs_never_zero"] = (
        "visible_breaks_consecutive_runs_never_zero"
    )
    event_policy: Literal["optional_researcher_declared_never_inferred"] = (
        "optional_researcher_declared_never_inferred"
    )
    deterioration_method: Literal["absolute_adverse_delta_from_baseline_mean_v1"] = (
        "absolute_adverse_delta_from_baseline_mean_v1"
    )
    recovery_states: list[str]
    limitations: list[str] = Field(default_factory=list)


def temporal_diagnosis_contract() -> TemporalDiagnosisContract:
    """Return the static versioned DIA-01 contract."""

    return TemporalDiagnosisContract(
        default_temporal_config=TemporalEvidenceConfig(),
        default_r6_config=R6Config(),
        recovery_states=[item.value for item in RecoveryAssessment],
        limitations=[
            "Threshold defaults are provisional synthetic-development values.",
            "R6 is descriptive and does not establish drift, incident causality, or root cause.",
            "Requested-range coverage is not proof of sensor completeness.",
        ],
    )


def evaluate_temporal_series(
    bundle_result: BundleValidationResult,
    window_series: WindowedMetricSeries,
    temporal_config: TemporalEvidenceConfig,
    metric_config: MetricEngineConfig | None = None,
    rule_config: RuleSetConfig | None = None,
    *,
    plugin_registry: MetricPluginRegistry | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> TemporalDiagnosticAnalysis:
    """Attach one existing series to EvidencePack and run the ordinary rule engine."""

    metrics = compute_metrics_for_bundle(
        bundle_result,
        metric_config,
        plugin_registry=plugin_registry,
        clock=clock,
    )
    base_pack = build_evidence_pack(
        bundle_result,
        metrics,
        metric_config,
        plugin_registry=plugin_registry,
        clock=clock,
    )
    pack = attach_temporal_evidence(base_pack, window_series, temporal_config)
    report = evaluate_rules(pack, rule_config, clock=clock)
    r6_result = next((result for result in report.results if result.rule_id == "R6"), None)
    if r6_result is None:
        raise ValueError("R6 must be enabled for a temporal diagnostic analysis")
    if pack.temporal_evidence is None:  # guarded by attach_temporal_evidence
        raise ValueError("temporal evidence attachment failed")
    return TemporalDiagnosticAnalysis(
        temporal_evidence=pack.temporal_evidence,
        evidence_pack=pack,
        diagnostic_report=report,
        r6_result=r6_result,
    )


def evaluate_temporal_bundle(
    bundle_result: BundleValidationResult,
    window_config: WindowedMetricConfig,
    temporal_config: TemporalEvidenceConfig,
    metric_config: MetricEngineConfig | None = None,
    rule_config: RuleSetConfig | None = None,
    *,
    plugin_registry: MetricPluginRegistry | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> TemporalDiagnosticAnalysis:
    """Compute fixed windows, build temporal EvidencePack, and evaluate R6."""

    series = compute_windowed_metrics_for_bundle(
        bundle_result,
        window_config,
        metric_config,
        plugin_registry=plugin_registry,
        clock=clock,
    )
    return evaluate_temporal_series(
        bundle_result,
        series,
        temporal_config,
        metric_config,
        rule_config,
        plugin_registry=plugin_registry,
        clock=clock,
    )

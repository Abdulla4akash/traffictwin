"""Run metric, windowed metric, diagnostic, rule, and evidence-pack services."""

from __future__ import annotations

from pydantic import ValidationError

from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.diagnostics.temporal import (
    TemporalDiagnosticAnalysis,
    evaluate_temporal_series,
)
from traffictwin.diagnostics.threshold_sweep import (
    ThresholdSensitivityReport,
    ThresholdSweepRequest,
    config_for_evaluated_point,
    evaluate_threshold_sweep,
)
from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.evidence.pack import EvidencePack
from traffictwin.evidence.temporal import TemporalEvidenceConfig
from traffictwin.ingestion.bundle import (
    BundleValidationResult,
)
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.plugins import MetricPluginApiContract, metric_plugin_api_contract
from traffictwin.metrics.results import MetricCollection
from traffictwin.metrics.windowed import (
    PartialWindowPolicy,
    WindowedMetricConfig,
    WindowedMetricSeries,
    WindowLimitExceededError,
    compute_windowed_metrics_for_bundle,
)
from traffictwin.rules.config import R6Config, R7Config, R8Config, RuleSetConfig
from traffictwin.rules.declarative import DeclarativeRuleContract, declarative_rule_contract
from traffictwin.rules.engine import evaluate_rules
from traffictwin.rules.models import RuleResult
from traffictwin.ui.services.models import ServiceError


def compute_run_metrics_for_ui(
    result: BundleValidationResult,
    config: MetricEngineConfig | None = None,
) -> MetricCollection:
    """Compute metrics through the Phase 3 engine."""

    return compute_metrics_for_bundle(result, config or MetricEngineConfig())


def metric_plugin_api_for_ui() -> MetricPluginApiContract:
    """Return the read-only trusted-extension boundary for UI explanation."""

    return metric_plugin_api_contract()


def declarative_rule_contract_for_ui() -> DeclarativeRuleContract:
    """Return the read-only closed declarative-rule grammar boundary for UI explanation."""

    return declarative_rule_contract()


def compute_windowed_metrics_for_ui(
    result: BundleValidationResult,
    *,
    width_s: float,
    alignment_origin_s: float = 0.0,
    analysis_start_s: float | None = None,
    analysis_end_s: float | None = None,
    partial_window_policy: str = "include",
) -> WindowedMetricSeries | ServiceError:
    """Validate UI inputs and call the deterministic fixed-window metric service."""

    try:
        config = WindowedMetricConfig(
            width_s=width_s,
            alignment_origin_s=alignment_origin_s,
            analysis_start_s=analysis_start_s,
            analysis_end_s=analysis_end_s,
            partial_window_policy=PartialWindowPolicy(partial_window_policy),
        )
        return compute_windowed_metrics_for_bundle(result, config)
    except (ValueError, WindowLimitExceededError) as exc:
        return ServiceError("Windowed metrics could not be computed.", str(exc))


def evaluate_temporal_diagnostics_for_ui(
    result: BundleValidationResult,
    series: WindowedMetricSeries,
    *,
    metric_key: str,
    minimum_window_coverage: float = 1.0,
    event_time_s: float | None = None,
    event_label: str | None = None,
    baseline_window_count: int = 2,
    minimum_evaluable_windows: int = 4,
    minimum_deterioration_delta: float = 0.10,
    sustained_window_count: int = 2,
    recovery_tolerance: float = 0.05,
    recovery_horizon_windows: int = 4,
) -> TemporalDiagnosticAnalysis | ServiceError:
    """Validate R6 controls and delegate all temporal calculations to library services."""

    try:
        temporal_config = TemporalEvidenceConfig(
            metric_key=metric_key,
            minimum_window_coverage=minimum_window_coverage,
            event_time_s=event_time_s,
            event_label=event_label,
        )
        rule_config = RuleSetConfig(
            r6=R6Config(
                baseline_window_count=baseline_window_count,
                minimum_evaluable_windows=minimum_evaluable_windows,
                minimum_deterioration_delta=minimum_deterioration_delta,
                sustained_window_count=sustained_window_count,
                recovery_tolerance=recovery_tolerance,
                recovery_horizon_windows=recovery_horizon_windows,
            )
        )
        return evaluate_temporal_series(
            result,
            series,
            temporal_config,
            rule_config=rule_config,
        )
    except ValueError as exc:
        return ServiceError("Temporal diagnosis could not be evaluated.", str(exc))


def evaluate_fairness_diagnostic_for_ui(
    pack: EvidencePack,
    *,
    dimension: str = "vehicle_tier_completion",
    minimum_outcome_gap: float = 0.20,
    minimum_group_support: int = 2,
) -> RuleResult | ServiceError:
    """Validate R7 controls and delegate all rule evaluation to the library engine."""

    try:
        r7 = R7Config.model_validate(
            {
                "dimension": dimension,
                "minimum_outcome_gap": minimum_outcome_gap,
                "minimum_group_support": minimum_group_support,
            }
        )
        config = RuleSetConfig.model_validate(
            {
                "r0": {"enabled": False},
                "r1": {"enabled": False},
                "r2": {"enabled": False},
                "r3": {"enabled": False},
                "r4": {"enabled": False},
                "r5": {"enabled": False},
                "r6": {"enabled": False},
                "r7": r7.model_dump(mode="json"),
                "r8": {"enabled": False},
            }
        )
        return evaluate_rules(pack, config).results[0]
    except ValueError as exc:
        return ServiceError("Operational fairness diagnosis could not be evaluated.", str(exc))


def evaluate_energy_diagnostic_for_ui(
    pack: EvidencePack,
    *,
    minimum_energy_per_completed_task_j: float = 1.50,
    minimum_completed_tasks: int = 10,
) -> RuleResult | ServiceError:
    """Validate R8 controls and delegate all rule evaluation to the library engine."""

    try:
        r8 = R8Config(
            minimum_energy_per_completed_task_j=minimum_energy_per_completed_task_j,
            minimum_completed_tasks=minimum_completed_tasks,
        )
        config = RuleSetConfig.model_validate(
            {
                "r0": {"enabled": False},
                "r1": {"enabled": False},
                "r2": {"enabled": False},
                "r3": {"enabled": False},
                "r4": {"enabled": False},
                "r5": {"enabled": False},
                "r6": {"enabled": False},
                "r7": {"enabled": False},
                "r8": r8.model_dump(mode="json"),
            }
        )
        return evaluate_rules(pack, config).results[0]
    except ValueError as exc:
        return ServiceError("Completed-task energy diagnosis could not be evaluated.", str(exc))


def evaluate_threshold_sweep_for_ui(
    pack: EvidencePack,
    *,
    rule_id: str,
    minimum_threshold: float,
    maximum_threshold: float,
    point_count: int,
    rule_config: RuleSetConfig | None = None,
) -> ThresholdSensitivityReport | ServiceError:
    """Validate DIA-06 controls and delegate the complete grid to the library service."""

    try:
        request = ThresholdSweepRequest(
            rule_id=rule_id,
            minimum_threshold=minimum_threshold,
            maximum_threshold=maximum_threshold,
            point_count=point_count,
        )
        return evaluate_threshold_sweep(pack, request, rule_config)
    except (RuntimeError, ValueError) as exc:
        return ServiceError("Threshold sensitivity could not be evaluated.", str(exc))


def parse_rule_config_json_for_ui(payload: str | bytes) -> RuleSetConfig | ServiceError:
    """Validate one explicitly supplied complete RuleSetConfig JSON payload."""

    try:
        return RuleSetConfig.model_validate_json(payload)
    except (UnicodeDecodeError, ValidationError, ValueError) as exc:
        return ServiceError("Rule configuration could not be imported.", str(exc))


def rule_config_json_for_ui(config: RuleSetConfig) -> str:
    """Return an explicit complete config export without persisting it."""

    return config.model_dump_json(indent=2)


def sweep_point_config_json_for_ui(
    report: ThresholdSensitivityReport,
    source_config: RuleSetConfig,
    threshold: float,
) -> str | ServiceError:
    """Return one complete validated config for an exact retained DIA-06 point."""

    try:
        config = config_for_evaluated_point(report, source_config, threshold)
        return rule_config_json_for_ui(config)
    except ValueError as exc:
        return ServiceError("Evaluated-point configuration could not be exported.", str(exc))


def build_evidence_pack_for_ui(
    result: BundleValidationResult,
    metrics: MetricCollection,
    config: MetricEngineConfig | None = None,
) -> EvidencePack:
    """Build an evidence pack through the Phase 3 evidence builder."""

    return build_evidence_pack(result, metrics, config or MetricEngineConfig())


def build_diagnostic_report_for_ui(pack: EvidencePack) -> DiagnosticReport:
    """Build deterministic diagnostics through the Phase 5 rules engine."""

    return evaluate_rules(pack)

"""TOS package, results, training, replay, and audit services."""

from __future__ import annotations

from pathlib import Path

from traffictwin.integration.tos import (
    TosCampaignComparisonReport,
    TosEvaluationRun,
    TosImportSummary,
    TosIntegrationReadinessReport,
    TosReplayFrame,
    TosReplayPoint,
    TosReproducibilityAudit,
    TosRsuReplayPoint,
    TosRsuRunSummary,
    TosTaskOutcomeSummary,
    TosTaskSample,
    TosTraceSummary,
    TosTrainingRun,
    TosTrainingRunSummary,
    TosValidationReport,
    audit_tos_package,
    build_evaluation_matrix,
    build_generalisation_matrix,
    build_static_results_atlas,
    build_tos_evidence_pack,
    build_tos_integration_readiness,
    build_tos_metric_trace,
    build_tos_research_report,
    build_tos_supervisor_pack_zip,
    compare_campaigns,
    import_evaluation_summaries,
    list_instrumented_runs,
    list_training_runs,
    load_replay_frame,
    load_replay_series,
    load_rsu_replay_series,
    load_task_sample,
    load_training_run,
    metric_collection_from_evaluation,
    read_evaluation_runs,
    summarise_rsu_run,
    summarise_task_outcomes,
    summarise_trace,
    tos_analysis_catalogue,
    tos_source_contract,
    validate_tos_package,
)
from traffictwin.integration.tos.readers import (
    TosPackageError,
    instrumented_key_for_run,
    list_pertask_runs,
)
from traffictwin.metrics.comparison import ComparisonReport, compare_metric_collections
from traffictwin.reporting.html import report_to_html
from traffictwin.reporting.markdown import report_to_markdown
from traffictwin.rules.engine import evaluate_rules
from traffictwin.storage.registry import (
    RegistryConflictError,
)
from traffictwin.ui.services.models import (
    ServiceError,
    TosPackageView,
    TosResultsView,
    TosRunAnalysis,
)


def inspect_tos_for_ui(
    path: str | Path,
    *,
    deep: bool = False,
) -> TosPackageView | ServiceError:
    """Inspect a TOS package through the integration boundary."""

    try:
        report = validate_tos_package(path, deep=deep)
        rows = read_evaluation_runs(path) if report.may_import_summaries else []
        return TosPackageView(
            source_path=Path(path).resolve(),
            report=report,
            evaluation_runs=rows,
            instrumented_runs=list_instrumented_runs(path),
            pertask_runs=list_pertask_runs(path),
            source_contract=tos_source_contract(),
        )
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS Data package could not be inspected.", str(exc))


def tos_results_for_ui(
    package_view: TosPackageView,
    *,
    measure_key: str = "tos.task.deadline_success.rate",
    evaluation_fleet: str = "uk2030",
) -> TosResultsView | ServiceError:
    """Prepare source matrix and domain labels without UI-side calculations."""

    try:
        return TosResultsView(
            matrix=build_evaluation_matrix(
                package_view.evaluation_runs,
                package_view.source_path,
                measure_key=measure_key,
                evaluation_fleet=evaluation_fleet,
            ),
            generalisation=build_generalisation_matrix(
                package_view.evaluation_runs, package_view.source_path
            ),
            measures=tos_analysis_catalogue(),
            campaigns=sorted(
                {
                    run.campaign
                    for run in package_view.evaluation_runs
                    if run.eval_fleet == evaluation_fleet
                }
            ),
            fleets=sorted({run.eval_fleet for run in package_view.evaluation_runs}),
        )
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS results matrix could not be prepared.", str(exc))


def compare_tos_campaigns_for_ui(
    package_view: TosPackageView,
    baseline_campaign: str,
    variation_campaign: str,
    *,
    measure_key: str,
    evaluation_fleet: str,
) -> TosCampaignComparisonReport | ServiceError:
    """Build a paired campaign report over common source fleet seeds."""

    try:
        return compare_campaigns(
            package_view.evaluation_runs,
            package_view.source_path,
            baseline_campaign,
            variation_campaign,
            evaluation_fleet=evaluation_fleet,
            measure_keys=[measure_key],
        )
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS paired campaign comparison could not be prepared.", str(exc))


def tos_training_runs_for_ui(
    package_view: TosPackageView,
) -> list[TosTrainingRunSummary] | ServiceError:
    """Index source training histories."""

    try:
        return list_training_runs(package_view.source_path)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS training histories could not be indexed.", str(exc))


def tos_training_run_for_ui(
    package_view: TosPackageView,
    training_id: str,
) -> TosTrainingRun | ServiceError:
    """Load one bounded source training history."""

    try:
        return load_training_run(package_view.source_path, training_id)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS training history could not be loaded.", str(exc))


def tos_trace_summary_for_ui(
    package_view: TosPackageView,
    trace_name: str,
) -> TosTraceSummary | ServiceError:
    """Load a bounded processed-FCD profile."""

    try:
        return summarise_trace(package_view.source_path, trace_name)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("Processed FCD trace could not be summarised.", str(exc))


def tos_rsu_summary_for_ui(
    package_view: TosPackageView,
    run_key: str,
) -> TosRsuRunSummary | ServiceError:
    """Summarise source RSU state for an instrumented run."""

    try:
        return summarise_rsu_run(package_view.source_path, run_key)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS RSU source state could not be summarised.", str(exc))


def tos_task_summary_for_ui(
    package_view: TosPackageView,
    run_key: str,
) -> TosTaskOutcomeSummary | ServiceError:
    """Aggregate one complete per-task showcase array."""

    try:
        return summarise_task_outcomes(package_view.source_path, run_key)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS per-task outcomes could not be summarised.", str(exc))


def tos_audit_for_ui(
    package_view: TosPackageView,
) -> TosReproducibilityAudit | ServiceError:
    """Build the read-only reproducibility audit."""

    try:
        return audit_tos_package(package_view.source_path)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS reproducibility audit could not be prepared.", str(exc))


def tos_readiness_for_ui(
    package_view: TosPackageView,
) -> TosIntegrationReadinessReport | ServiceError:
    """Build machine-readable integration and permission gates."""

    try:
        return build_tos_integration_readiness(package_view.source_path)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS integration readiness could not be prepared.", str(exc))


def tos_supervisor_pack_for_ui(
    package_view: TosPackageView,
    *,
    variation_campaign: str,
) -> bytes | ServiceError:
    """Build a private checksummed supervisor pack for deliberate download."""

    try:
        return build_tos_supervisor_pack_zip(
            package_view.source_path,
            variation_campaign=variation_campaign,
        )
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS supervisor pack could not be prepared.", str(exc))


def tos_report_exports_for_ui(
    package_view: TosPackageView,
    *,
    variation_campaign: str,
) -> tuple[str, str, str] | ServiceError:
    """Return Markdown report, HTML report, and aggregate-only static atlas."""

    try:
        report = build_tos_research_report(
            package_view.source_path, variation_campaign=variation_campaign
        )
        return (
            report_to_markdown(report),
            report_to_html(report),
            build_static_results_atlas(package_view.source_path),
        )
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS report exports could not be prepared.", str(exc))


def import_tos_for_ui(
    path: str | Path,
    registry_path: str | Path,
    report: TosValidationReport,
) -> TosImportSummary | ServiceError:
    """Import accepted TOS summaries through the idempotent registry service."""

    try:
        return import_evaluation_summaries(path, registry_path, validation_report=report)
    except (OSError, ValueError, TosPackageError, RegistryConflictError) as exc:
        return ServiceError("TOS evaluation summaries could not be imported.", str(exc))


def analyse_tos_run_for_ui(
    package_view: TosPackageView,
    run_identifier: str,
) -> TosRunAnalysis | ServiceError:
    """Build metrics, partial evidence, diagnostics, and provenance for one source row."""

    try:
        run = _find_tos_run(package_view.evaluation_runs, run_identifier)
        fingerprint = package_view.report.package_fingerprint
        if fingerprint is None:
            return ServiceError("TOS package fingerprint is unavailable.")
        collection = metric_collection_from_evaluation(run, fingerprint)
        pack = build_tos_evidence_pack(run, package_view.report, collection)
        diagnosis = evaluate_rules(pack)
        trace = build_tos_metric_trace(
            run,
            collection,
            package_view.report,
            "tos.task.deadline_success.rate",
        )
        return TosRunAnalysis(
            run=run,
            metric_collection=collection,
            evidence_pack=pack,
            diagnostic_report=diagnosis,
            completion_trace=trace,
        )
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS run analysis could not be prepared.", str(exc))


def compare_tos_runs_for_ui(
    package_view: TosPackageView,
    baseline_identifier: str,
    variation_identifier: str,
) -> ComparisonReport | ServiceError:
    """Compare two compatible source-summary runs through Phase 3 comparison logic."""

    try:
        baseline = _find_tos_run(package_view.evaluation_runs, baseline_identifier)
        variation = _find_tos_run(package_view.evaluation_runs, variation_identifier)
        fingerprint = package_view.report.package_fingerprint
        if fingerprint is None:
            return ServiceError("TOS package fingerprint is unavailable.")
        baseline_metrics = metric_collection_from_evaluation(baseline, fingerprint)
        variation_metrics = metric_collection_from_evaluation(variation, fingerprint)
        return compare_metric_collections(baseline_metrics, variation_metrics)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS source-summary comparison could not be prepared.", str(exc))


def load_tos_replay_for_ui(
    path: str | Path,
    run_key: str,
    index: int,
    *,
    max_vehicles: int = 100,
) -> TosReplayFrame | ServiceError:
    """Load one bounded TOS historical replay frame."""

    try:
        return load_replay_frame(path, run_key, index, max_vehicles=max_vehicles)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS replay frame could not be loaded.", str(exc))


def load_tos_replay_series_for_ui(
    path: str | Path,
    run_key: str,
) -> list[TosReplayPoint] | ServiceError:
    """Load the small logical replay series used by deterministic UI controls."""

    try:
        return list(load_replay_series(path, run_key))
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS logical replay series could not be loaded.", str(exc))


def load_tos_task_sample_for_ui(
    path: str | Path,
    run_key: str,
    *,
    limit: int = 50,
) -> TosTaskSample | ServiceError:
    """Load a bounded, read-only TOS per-task sample."""

    try:
        return load_task_sample(path, run_key, limit=limit)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS per-task sample could not be loaded.", str(exc))


def load_tos_rsu_series_for_ui(
    path: str | Path,
    run_key: str,
    *,
    stride: int = 1,
) -> list[TosRsuReplayPoint] | ServiceError:
    """Load interpreted, source-specific RSU history for visual inspection."""

    try:
        return load_rsu_replay_series(path, run_key, stride=stride)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS RSU replay history could not be loaded.", str(exc))


def _find_tos_run(
    rows: list[TosEvaluationRun],
    identifier: str,
) -> TosEvaluationRun:
    for row in rows:
        if identifier in {row.run_id, row.source_key, instrumented_key_for_run(row)}:
            return row
    raise TosPackageError(f"TOS evaluation run not found: {identifier}")

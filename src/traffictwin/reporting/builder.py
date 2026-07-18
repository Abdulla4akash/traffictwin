"""Build deterministic report payloads from existing TrafficTwin pipeline outputs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.ingestion.bundle import BundleValidationResult, validate_bundle
from traffictwin.metrics.comparison import ComparisonReport, compare_metric_collections
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.results import MetricCollection, MetricStatus
from traffictwin.provenance.query import build_provenance_context, get_run_provenance
from traffictwin.reporting.models import ReportBuildError, ResearchReport
from traffictwin.rules.engine import evaluate_rules

Clock = Callable[[], datetime]


def build_run_report(path: str | Path, *, clock: Clock | None = None) -> ResearchReport:
    """Build a single-run deterministic report."""

    now = _now(clock)
    analysis = _analysis(path, now)
    result, metrics, diagnostics = analysis
    manifest = result.manifest
    if manifest is None:
        raise ReportBuildError("run report requires a valid manifest")
    sections = [
        (
            "Report Summary",
            [
                "TrafficTwin standalone report.",
                _disclaimer(result),
                f"Run: `{manifest.run.run_id}`",
                f"Bundle: `{manifest.bundle.bundle_id}`",
            ],
        ),
        ("Run Provenance", _run_provenance(result)),
        ("Validation Results", _validation_lines(result)),
        ("Evidence Availability", _evidence_lines(result)),
        ("Metrics", _metric_lines(metrics)),
        ("Diagnostic Hypotheses", _diagnostic_lines(diagnostics)),
        ("Provenance Summary", _provenance_lines(path, now)),
        ("Limitations", _limitations()),
        ("Reproduction Commands", _reproduction_lines(path)),
    ]
    return ResearchReport(
        report_id=f"report-run-{manifest.run.run_id}",
        title=f"TrafficTwin Run Report: {manifest.run.run_id}",
        generated_at=now,
        source_reference=_safe_reference(path),
        synthetic=manifest.environment.name == "synthetic",
        sections=sections,
        warnings=[],
    )


def build_diagnostics_report(path: str | Path, *, clock: Clock | None = None) -> ResearchReport:
    """Build a diagnostic-report-focused Markdown/HTML payload."""

    now = _now(clock)
    result, metrics, diagnostics = _analysis(path, now)
    manifest = result.manifest
    if manifest is None:
        raise ReportBuildError("diagnostic report requires a valid manifest")
    return ResearchReport(
        report_id=f"report-diagnostics-{manifest.run.run_id}",
        title=f"TrafficTwin Diagnostic Report: {manifest.run.run_id}",
        generated_at=now,
        source_reference=_safe_reference(path),
        synthetic=manifest.environment.name == "synthetic",
        sections=[
            ("Report Summary", [_disclaimer(result), f"Run: `{manifest.run.run_id}`"]),
            ("Validation Results", _validation_lines(result)),
            ("Evidence Availability", _evidence_lines(result)),
            ("Diagnostic Hypotheses", _diagnostic_lines(diagnostics)),
            ("Metric Evidence Used", _metric_lines(metrics)),
            ("Limitations", _limitations()),
            ("Reproduction Commands", _reproduction_lines(path)),
        ],
    )


def build_comparison_report(
    baseline: str | Path,
    variation: str | Path,
    *,
    clock: Clock | None = None,
) -> ResearchReport:
    """Build a deterministic baseline-versus-variation report."""

    now = _now(clock)
    baseline_result, baseline_metrics, _ = _analysis(baseline, now)
    variation_result, variation_metrics, _ = _analysis(variation, now)
    comparison = compare_metric_collections(
        baseline_metrics,
        variation_metrics,
        baseline_seed=baseline_result.seed,
        variation_seed=variation_result.seed,
        clock=lambda: now,
    )
    return ResearchReport(
        report_id=f"report-compare-{baseline_metrics.run_id}-vs-{variation_metrics.run_id}",
        title=f"TrafficTwin Comparison: {baseline_metrics.run_id} vs {variation_metrics.run_id}",
        generated_at=now,
        source_reference=f"{_safe_reference(baseline)} vs {_safe_reference(variation)}",
        synthetic=baseline_metrics.results[0].synthetic and variation_metrics.results[0].synthetic,
        sections=[
            (
                "Report Summary",
                [
                    "Baseline-versus-variation comparison using deterministic Phase 3 deltas.",
                    (
                        "Synthetic data is software demonstration evidence only when the source "
                        "is synthetic."
                    ),
                ],
            ),
            ("Compatibility", _comparison_compatibility_lines(comparison)),
            ("Changed Seed Parameters", _seed_diff_lines(comparison)),
            ("Metric Deltas", _comparison_metric_lines(comparison)),
            ("Limitations", _limitations()),
            ("Reproduction Commands", _comparison_reproduction_lines(baseline, variation)),
        ],
    )


def build_full_report(
    path: str | Path,
    *,
    comparison_baseline: str | Path | None = None,
    clock: Clock | None = None,
) -> ResearchReport:
    """Build a full standalone report for one run, optionally with comparison context."""

    report = build_run_report(path, clock=clock)
    sections = list(report.sections)
    if comparison_baseline is not None:
        comparison_report = build_comparison_report(comparison_baseline, path, clock=clock)
        sections.append(("Comparison Context", _flatten_sections(comparison_report.sections)))
    return report.model_copy(
        update={
            "report_id": report.report_id.replace("report-run", "report-full", 1),
            "title": report.title.replace("Run Report", "Full Report"),
            "sections": sections,
        }
    )


def _analysis(
    path: str | Path,
    now: datetime,
) -> tuple[BundleValidationResult, MetricCollection, DiagnosticReport]:
    result = validate_bundle(path)
    if result.manifest is None or not result.report.may_import:
        raise ReportBuildError("reports require an accepted or warning-level bundle")
    metrics = compute_metrics_for_bundle(result, clock=lambda: now)
    evidence = build_evidence_pack(result, metrics, clock=lambda: now)
    diagnostics = evaluate_rules(evidence, clock=lambda: now)
    return result, metrics, diagnostics


def _run_provenance(result: BundleValidationResult) -> list[str]:
    manifest = result.manifest
    if manifest is None:
        return ["Manifest unavailable."]
    return [
        f"Experiment: `{manifest.run.experiment_id}`",
        f"Seed: `{manifest.run.seed_id}`",
        f"Algorithm/profile: `{manifest.run.algorithm}`",
        f"Checkpoint: `{manifest.run.checkpoint or 'none'}`",
        f"Random seed: `{manifest.run.random_seed}`",
        f"Environment: `{manifest.environment.name}` version `{manifest.environment.version}`",
        f"Bundle fingerprint: `{result.fingerprint}`",
    ]


def _validation_lines(result: BundleValidationResult) -> list[str]:
    report = result.report
    lines = [
        f"Status: `{report.status.value}`",
        f"May import: `{report.may_import}`",
        f"Findings: `{len(report.findings)}`",
    ]
    for severity, count in sorted(report.counts_by_severity.items()):
        lines.append(f"{severity}: `{count}`")
    if report.findings:
        codes = ", ".join(f"`{finding.code.value}`" for finding in report.findings)
        lines.append("Finding codes: " + codes)
    return lines


def _evidence_lines(result: BundleValidationResult) -> list[str]:
    counts = ", ".join(
        f"{key}={value}" for key, value in sorted(result.canonical.record_counts().items())
    )
    return [
        "Available: " + (", ".join(result.report.available_evidence_categories) or "none"),
        "Unavailable: " + (", ".join(result.report.unavailable_evidence_categories) or "none"),
        "Canonical counts: " + counts,
    ]


def _metric_lines(metrics: MetricCollection) -> list[str]:
    interesting = [
        "task.generated.count",
        "task.completed.count",
        "task.completion.rate",
        "task.incomplete.rate",
        "task.latency.p95_ms",
        "task.offload.rate",
        "infra.utilisation.p95",
        "infra.queue_length.max",
        "trip.duration.p95_s",
        "traffic.speed.mean_mps",
    ]
    by_key = metrics.by_key()
    lines = [f"Metric version: `{metrics.metric_version}`"]
    for key in interesting:
        metric = by_key.get(key)
        if metric is None:
            continue
        value = (
            _format_value(metric.value)
            if metric.status is MetricStatus.AVAILABLE
            else "Unavailable"
        )
        suffix = f" {metric.unit}" if metric.unit not in {"ratio", "count"} else ""
        reasons = (
            f" ({', '.join(reason.value for reason in metric.reason_codes)})"
            if metric.reason_codes
            else ""
        )
        lines.append(f"`{key}`: {value}{suffix}{reasons}")
    return lines


def _diagnostic_lines(report: DiagnosticReport) -> list[str]:
    lines = [
        f"Report: `{report.report_id}`",
        f"Overall readiness: `{report.overall_readiness.value}`",
        f"Triggered rules: {', '.join(report.triggered_rule_ids) or 'none'}",
        f"Insufficient rules: {', '.join(report.insufficient_rule_ids) or 'none'}",
    ]
    for result in report.results:
        hypothesis = result.hypothesis or "no candidate hypothesis"
        lines.append(
            f"`{result.rule_id}` {result.status.value}: {hypothesis} "
            f"(confidence `{result.confidence.value}`)"
        )
    return lines


def _provenance_lines(path: str | Path, now: datetime) -> list[str]:
    context = build_provenance_context(path)
    trace = get_run_provenance(context, clock=lambda: now)
    return [
        f"Trace: `{trace.trace_id}`",
        f"Completeness: `{trace.completeness.overall.value}`",
        f"Nodes: `{len(trace.nodes)}`",
        f"Edges: `{len(trace.edges)}`",
    ]


def _comparison_metric_lines(report: ComparisonReport) -> list[str]:
    lines: list[str] = []
    interesting = {
        "task.completion.rate",
        "task.incomplete.rate",
        "infra.queue_length.max",
        "infra.utilisation.p95",
        "trip.duration.p95_s",
        "traffic.speed.mean_mps",
    }
    for item in report.comparable_metrics:
        if item.metric_key not in interesting:
            continue
        lines.append(
            f"`{item.metric_key}`: baseline={_format_value(item.baseline)}, "
            f"variation={_format_value(item.variation)}, "
            f"delta={_format_value(item.absolute_delta)}, direction=`{item.direction.value}`"
        )
    if report.unavailable_comparisons:
        lines.append(f"Unavailable comparisons: `{len(report.unavailable_comparisons)}`")
    return lines


def _comparison_compatibility_lines(report: ComparisonReport) -> list[str]:
    return [
        f"Baseline: `{report.baseline_context.get('run_id')}`",
        f"Variation: `{report.variation_context.get('run_id')}`",
        f"Warnings: {', '.join(report.warnings) or 'none'}",
    ]


def _seed_diff_lines(report: ComparisonReport) -> list[str]:
    if not report.changed_seed_parameters:
        return ["No seed snapshot differences available."]
    return [
        f"`{item.get('path', 'unknown')}`: "
        f"`{item.get('baseline_value')}` -> `{item.get('variation_value')}`"
        for item in report.changed_seed_parameters
    ]


def _limitations() -> list[str]:
    return [
        "Synthetic records are deterministic software fixtures, not real-world validation.",
        "Diagnostic outputs are candidate hypotheses and do not establish root causes.",
        "No Randy/VEC, SUMO, live Manchester, near-live, or true-live integration is active.",
    ]


def _reproduction_lines(path: str | Path) -> list[str]:
    ref = _safe_reference(path)
    return [
        f"`traffictwin bundle validate {ref}`",
        f"`traffictwin metrics compute {ref}`",
        f"`traffictwin diagnose bundle {ref}`",
        f"`traffictwin provenance run {ref}`",
    ]


def _comparison_reproduction_lines(baseline: str | Path, variation: str | Path) -> list[str]:
    return [
        f"`traffictwin compare {_safe_reference(baseline)} {_safe_reference(variation)}`",
    ]


def _disclaimer(result: BundleValidationResult) -> str:
    if result.manifest is not None and result.manifest.environment.name == "synthetic":
        return (
            "This report uses synthetic fixture data, not live or externally validated traffic "
            "data."
        )
    return (
        "This report uses imported bundle data and should be interpreted according to its manifest."
    )


def _flatten_sections(sections: list[tuple[str, list[str]]]) -> list[str]:
    lines: list[str] = []
    for title, body in sections:
        lines.append(f"{title}:")
        lines.extend(body)
    return lines


def _format_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _safe_reference(path: str | Path) -> str:
    candidate = Path(path)
    if not candidate.is_absolute():
        return candidate.as_posix()
    try:
        return candidate.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return candidate.name


def _now(clock: Clock | None) -> datetime:
    return clock() if clock is not None else datetime.now(UTC)

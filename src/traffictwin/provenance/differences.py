"""Deterministic accepted-row lineage for baseline/variation metric differences."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from enum import StrEnum
from io import StringIO

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.ingestion.bundle import BundleValidationResult
from traffictwin.metrics.comparison import (
    ComparisonReport,
    ComparisonRequest,
    ComparisonStatus,
    MetricComparison,
    compare_metric_collections,
)
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import JsonScalar, JsonValue, MetricCollection
from traffictwin.provenance.contributions import (
    MetricContributionReport,
    MetricContributionRow,
    build_metric_contribution_report,
)

DIFFERENCE_PROVENANCE_SCHEMA_VERSION = "1.0"
DIFFERENCE_PROVENANCE_CAPABILITY_ID = "PRO-01"
NON_CAUSALITY_STATEMENT = (
    "This report records deterministic arithmetic and eligible input lineage only; it does not "
    "establish that any row, vehicle, RSU, or incident caused the observed difference."
)


class DifferenceContributionStatus(StrEnum):
    """Available difference-lineage modes and the explicit unavailable state."""

    ARITHMETIC = "arithmetic"
    LINEAGE_ONLY = "lineage_only"
    UNAVAILABLE = "unavailable"


class DifferenceSide(StrEnum):
    """Role of one input run in variation-minus-baseline arithmetic."""

    BASELINE = "baseline"
    VARIATION = "variation"


class DifferenceContributionRow(BaseModel):
    """One accepted canonical candidate row in a two-run difference ledger."""

    model_config = ConfigDict(extra="forbid")

    side: DifferenceSide
    run_id: str
    canonical_table: str
    record_id: str
    source_file: str
    source_row: int = Field(ge=1)
    included: bool
    inclusion_reason: str
    canonical_values: dict[str, JsonValue]
    run_metric_contribution: float | None = None
    signed_difference_contribution: float | None = None


class DifferenceSideSummary(BaseModel):
    """Candidate and eligibility counts for one comparison side."""

    model_config = ConfigDict(extra="forbid")

    side: DifferenceSide
    run_id: str
    input_fingerprint: str | None = None
    synthetic: bool | None = None
    candidate_row_count: int = Field(ge=0)
    included_row_count: int = Field(ge=0)
    excluded_row_count: int = Field(ge=0)


class DifferenceContributionReport(BaseModel):
    """Typed comparison lineage with weights only for admitted additive formulas."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = DIFFERENCE_PROVENANCE_SCHEMA_VERSION
    capability_id: str = DIFFERENCE_PROVENANCE_CAPABILITY_ID
    status: DifferenceContributionStatus
    metric_key: str
    unit: str | None = None
    comparison_basis: str = "variation_minus_baseline"
    baseline_value: JsonValue = None
    variation_value: JsonValue = None
    absolute_delta: float | None = None
    decomposition_method: str | None = None
    baseline: DifferenceSideSummary
    variation: DifferenceSideSummary
    rows: list[DifferenceContributionRow] = Field(default_factory=list)
    arithmetic_contribution_sum: float | None = None
    reconciles_to_absolute_delta: bool | None = None
    comparison_reason_codes: list[str] = Field(default_factory=list)
    compatibility_findings: list[str] = Field(default_factory=list)
    grouping: list[str] = Field(
        default_factory=lambda: ["comparison_side", "canonical_table", "source_file"]
    )
    limitations: list[str] = Field(default_factory=list)
    non_causality_statement: str = NON_CAUSALITY_STATEMENT

    def canonical_json(self) -> str:
        """Return deterministic JSON for equality, caching, and golden checks."""

        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def fingerprint(self) -> str:
        """Fingerprint the complete typed report."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def to_json(self) -> str:
        """Return readable deterministic JSON."""

        return self.model_dump_json(indent=2)


class DifferenceProvenanceContract(BaseModel):
    """Published PRO-01 v1.0 scientific and integrity boundary."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = DIFFERENCE_PROVENANCE_SCHEMA_VERSION
    capability_id: str = DIFFERENCE_PROVENANCE_CAPABILITY_ID
    comparison_basis: str = "variation_minus_baseline"
    required_compatibility: list[str]
    arithmetic_metric_methods: dict[str, str]
    lineage_only_classes: list[str]
    reconciliation_relative_tolerance: float
    reconciliation_absolute_tolerance: float
    complete_candidate_row_ledgers: bool = True
    unavailable_is_not_zero: bool = True
    non_causality_statement: str = NON_CAUSALITY_STATEMENT
    limitations: list[str]


class DifferenceContributionError(ValueError):
    """Raised when a difference ledger cannot be constructed faithfully."""


# These formulas are deliberately explicit. Adding a key requires proving that the sum of its
# accepted-row terms equals the ordinary run metric before any signed difference is exported.
ARITHMETIC_METRIC_METHODS: dict[str, str] = {
    "infra.queue_length.mean": "eligible queue_length divided by eligible row count",
    "infra.utilisation.mean": "eligible utilisation_fraction divided by eligible row count",
    "task.completed.count": "one per included completed task",
    "task.completion.rate": "completed indicator divided by accepted task count",
    "task.deadline_miss.completed_observed_rate": (
        "deadline-miss indicator divided by completed observed-latency count"
    ),
    "task.decision_share.local": "local indicator divided by recognised-decision count",
    "task.decision_share.unknown": "unknown indicator divided by accepted task count",
    "task.decision_share.v2i": "V2I indicator divided by recognised-decision count",
    "task.decision_share.v2v": "V2V indicator divided by recognised-decision count",
    "task.energy.mean_per_observed_task_j": "eligible energy_j divided by eligible row count",
    "task.energy.per_completed_j": "eligible completed-task energy_j divided by eligible row count",
    "task.energy_delay_product.mean_j_ms": (
        "eligible completed-task energy_j times latency_ms divided by eligible row count"
    ),
    "task.generated.count": "one per accepted task",
    "task.incomplete.rate": "incomplete indicator divided by accepted task count",
    "task.latency.count": "one per included latency observation",
    "task.latency.mean_ms": "eligible latency_ms divided by eligible row count",
    "task.offload.rate": "V2I-or-V2V indicator divided by recognised-decision count",
    "traffic.count.mean": "eligible count divided by eligible row count",
    "traffic.count.total": "eligible count",
    "traffic.observation.count": "one per accepted traffic observation",
    "traffic.speed.mean_mps": "eligible average_speed_mps divided by eligible row count",
    "trip.completed.count": "one per included completed trip",
    "trip.completion.rate": "completed indicator divided by accepted trip count",
    "trip.duration.count": "one per included duration observation",
    "trip.duration.mean_s": "eligible duration_s divided by eligible row count",
    "trip.incomplete.count": "one per included incomplete trip",
    "trip.records.count": "one per accepted trip record",
}

_ONE_PER_INCLUDED = {
    "task.completed.count",
    "task.generated.count",
    "task.latency.count",
    "traffic.observation.count",
    "trip.completed.count",
    "trip.duration.count",
    "trip.incomplete.count",
    "trip.records.count",
}


def difference_provenance_contract() -> DifferenceProvenanceContract:
    """Return the immutable PRO-01 method contract."""

    return DifferenceProvenanceContract(
        required_compatibility=[
            "ordinary metric-comparison experiment and random-seed policy",
            "metric implementation version",
            "metric unit",
            "available finite scalar metric values",
            "energy, fairness, or plugin semantic fingerprints where applicable",
        ],
        arithmetic_metric_methods=dict(sorted(ARITHMETIC_METRIC_METHODS.items())),
        lineage_only_classes=[
            "percentiles",
            "minimum and maximum extrema",
            "distinct counts",
            "episode and duration state-machine metrics",
            "grouped or mapping-valued metrics",
            "fairness and spatial aggregates",
            "trusted plugin metrics without a separately admitted decomposition",
        ],
        reconciliation_relative_tolerance=1e-12,
        reconciliation_absolute_tolerance=1e-12,
        limitations=[
            "Lineage-only reports intentionally contain no row weights.",
            "Mapping-valued metrics do not currently have an ordinary scalar difference and "
            "therefore remain unavailable rather than being flattened implicitly.",
            "Rows rejected before canonicalisation remain in validation findings, not in the "
            "accepted-row ledger.",
            "The report is deterministic provenance, not a causal attribution method.",
        ],
    )


def build_difference_contribution_report(
    baseline_bundle: BundleValidationResult,
    baseline_metrics: MetricCollection,
    variation_bundle: BundleValidationResult,
    variation_metrics: MetricCollection,
    metric_key: str,
    *,
    config: MetricEngineConfig | None = None,
) -> DifferenceContributionReport:
    """Build comparison-compatible accepted-row lineage for one metric."""

    comparison_report = compare_metric_collections(
        baseline_metrics,
        variation_metrics,
        ComparisonRequest(
            baseline_run_id=baseline_metrics.run_id,
            variation_run_id=variation_metrics.run_id,
            requested_metric_keys=[metric_key],
        ),
        baseline_seed=baseline_bundle.seed,
        variation_seed=variation_bundle.seed,
    )
    comparison = _single_comparison(comparison_report, metric_key)
    baseline_ledger = _build_ledger(baseline_bundle, baseline_metrics, metric_key, config)
    variation_ledger = _build_ledger(variation_bundle, variation_metrics, metric_key, config)
    summaries = (
        _side_summary(DifferenceSide.BASELINE, baseline_metrics, baseline_ledger),
        _side_summary(DifferenceSide.VARIATION, variation_metrics, variation_ledger),
    )
    findings = sorted({*comparison_report.warnings, *comparison.compatibility_findings})
    reasons = sorted({reason.value for reason in comparison.reason_codes})

    if comparison.status not in {ComparisonStatus.AVAILABLE, ComparisonStatus.PARTIAL}:
        rows = _lineage_rows(
            baseline_metrics.run_id,
            variation_metrics.run_id,
            baseline_ledger,
            variation_ledger,
        )
        return DifferenceContributionReport(
            status=DifferenceContributionStatus.UNAVAILABLE,
            metric_key=metric_key,
            unit=comparison.unit,
            baseline_value=comparison.baseline,
            variation_value=comparison.variation,
            baseline=summaries[0],
            variation=summaries[1],
            rows=rows,
            comparison_reason_codes=reasons,
            compatibility_findings=findings,
            limitations=_base_limitations(
                "The ordinary metric comparison is unavailable; candidate rows are retained "
                "for audit but no difference contribution is asserted."
            ),
        )

    if metric_key not in ARITHMETIC_METRIC_METHODS:
        return DifferenceContributionReport(
            status=DifferenceContributionStatus.LINEAGE_ONLY,
            metric_key=metric_key,
            unit=comparison.unit,
            baseline_value=comparison.baseline,
            variation_value=comparison.variation,
            absolute_delta=comparison.absolute_delta,
            baseline=summaries[0],
            variation=summaries[1],
            rows=_lineage_rows(
                baseline_metrics.run_id,
                variation_metrics.run_id,
                baseline_ledger,
                variation_ledger,
            ),
            comparison_reason_codes=reasons,
            compatibility_findings=findings,
            limitations=_base_limitations(
                "This metric is not admitted to the additive formula registry; eligible rows "
                "are exposed without fabricated weights."
            ),
        )

    if comparison.absolute_delta is None:
        raise DifferenceContributionError(
            f"arithmetic metric comparison has no absolute delta: {metric_key}"
        )
    rows = _arithmetic_rows(
        metric_key,
        baseline_metrics.run_id,
        variation_metrics.run_id,
        baseline_ledger,
        variation_ledger,
    )
    contribution_sum = math.fsum(
        row.signed_difference_contribution
        for row in rows
        if row.signed_difference_contribution is not None
    )
    reconciles = math.isclose(
        contribution_sum,
        comparison.absolute_delta,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )
    if not reconciles:
        raise DifferenceContributionError(
            "accepted-row contributions do not reconcile with the ordinary absolute delta for "
            f"{metric_key}: {contribution_sum} != {comparison.absolute_delta}"
        )
    return DifferenceContributionReport(
        status=DifferenceContributionStatus.ARITHMETIC,
        metric_key=metric_key,
        unit=comparison.unit,
        baseline_value=comparison.baseline,
        variation_value=comparison.variation,
        absolute_delta=comparison.absolute_delta,
        decomposition_method=ARITHMETIC_METRIC_METHODS[metric_key],
        baseline=summaries[0],
        variation=summaries[1],
        rows=rows,
        arithmetic_contribution_sum=contribution_sum,
        reconciles_to_absolute_delta=True,
        comparison_reason_codes=reasons,
        compatibility_findings=findings,
        limitations=_base_limitations(
            "Signed row terms reconcile to variation minus baseline under the declared formula."
        ),
    )


def difference_contribution_report_to_csv(report: DifferenceContributionReport) -> str:
    """Render one report as deterministic row-level CSV with integrity warnings repeated."""

    output = StringIO(newline="")
    fieldnames = [
        "schema_version",
        "capability_id",
        "status",
        "metric_key",
        "unit",
        "comparison_basis",
        "baseline_run_id",
        "variation_run_id",
        "baseline_value_json",
        "variation_value_json",
        "absolute_delta",
        "side",
        "run_id",
        "canonical_table",
        "record_id",
        "source_file",
        "source_row",
        "included",
        "inclusion_reason",
        "run_metric_contribution",
        "signed_difference_contribution",
        "canonical_values_json",
        "non_causality_statement",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    rows: list[DifferenceContributionRow | None] = list(report.rows) or [None]
    for row in rows:
        writer.writerow(
            {
                "schema_version": report.schema_version,
                "capability_id": report.capability_id,
                "status": report.status.value,
                "metric_key": report.metric_key,
                "unit": report.unit,
                "comparison_basis": report.comparison_basis,
                "baseline_run_id": report.baseline.run_id,
                "variation_run_id": report.variation.run_id,
                "baseline_value_json": _json_value(report.baseline_value),
                "variation_value_json": _json_value(report.variation_value),
                "absolute_delta": report.absolute_delta,
                "side": row.side.value if row is not None else "",
                "run_id": row.run_id if row is not None else "",
                "canonical_table": row.canonical_table if row is not None else "",
                "record_id": row.record_id if row is not None else "",
                "source_file": row.source_file if row is not None else "",
                "source_row": row.source_row if row is not None else "",
                "included": row.included if row is not None else "",
                "inclusion_reason": row.inclusion_reason if row is not None else "",
                "run_metric_contribution": (row.run_metric_contribution if row is not None else ""),
                "signed_difference_contribution": (
                    row.signed_difference_contribution if row is not None else ""
                ),
                "canonical_values_json": (
                    _json_value(row.canonical_values) if row is not None else ""
                ),
                "non_causality_statement": report.non_causality_statement,
            }
        )
    return output.getvalue()


def _single_comparison(report: ComparisonReport, metric_key: str) -> MetricComparison:
    comparable = report.comparable_metrics
    unavailable = report.unavailable_comparisons
    matches = [item for item in [*comparable, *unavailable] if item.metric_key == metric_key]
    if len(matches) != 1:
        raise DifferenceContributionError(
            f"ordinary comparison did not return exactly one result for {metric_key}"
        )
    return matches[0]


def _build_ledger(
    bundle: BundleValidationResult,
    metrics: MetricCollection,
    metric_key: str,
    config: MetricEngineConfig | None,
) -> MetricContributionReport:
    try:
        return build_metric_contribution_report(bundle, metrics, metric_key, config=config)
    except ValueError as exc:
        raise DifferenceContributionError(str(exc)) from exc


def _side_summary(
    side: DifferenceSide,
    metrics: MetricCollection,
    ledger: MetricContributionReport,
) -> DifferenceSideSummary:
    metric = metrics.by_key().get(ledger.metric_key)
    return DifferenceSideSummary(
        side=side,
        run_id=metrics.run_id,
        input_fingerprint=metrics.input_fingerprint,
        synthetic=metric.synthetic if metric is not None else None,
        candidate_row_count=ledger.candidate_row_count,
        included_row_count=ledger.included_row_count,
        excluded_row_count=ledger.excluded_row_count,
    )


def _lineage_rows(
    baseline_run_id: str,
    variation_run_id: str,
    baseline: MetricContributionReport,
    variation: MetricContributionReport,
) -> list[DifferenceContributionRow]:
    return [
        *[_difference_row(DifferenceSide.BASELINE, baseline_run_id, row) for row in baseline.rows],
        *[
            _difference_row(DifferenceSide.VARIATION, variation_run_id, row)
            for row in variation.rows
        ],
    ]


def _arithmetic_rows(
    metric_key: str,
    baseline_run_id: str,
    variation_run_id: str,
    baseline: MetricContributionReport,
    variation: MetricContributionReport,
) -> list[DifferenceContributionRow]:
    rows: list[DifferenceContributionRow] = []
    for side, run_id, report, sign in (
        (DifferenceSide.BASELINE, baseline_run_id, baseline, -1.0),
        (DifferenceSide.VARIATION, variation_run_id, variation, 1.0),
    ):
        for row in report.rows:
            contribution = _run_contribution(metric_key, row, report.included_row_count)
            rows.append(
                _difference_row(
                    side,
                    run_id,
                    row,
                    run_metric_contribution=contribution,
                    signed_difference_contribution=(
                        sign * contribution if contribution is not None else None
                    ),
                )
            )
    return rows


def _difference_row(
    side: DifferenceSide,
    run_id: str,
    row: MetricContributionRow,
    *,
    run_metric_contribution: float | None = None,
    signed_difference_contribution: float | None = None,
) -> DifferenceContributionRow:
    return DifferenceContributionRow(
        side=side,
        run_id=run_id,
        canonical_table=row.canonical_table,
        record_id=row.record_id,
        source_file=row.source_file,
        source_row=row.source_row,
        included=row.included,
        inclusion_reason=row.inclusion_reason,
        canonical_values=row.canonical_values,
        run_metric_contribution=run_metric_contribution,
        signed_difference_contribution=signed_difference_contribution,
    )


def _run_contribution(
    metric_key: str,
    row: MetricContributionRow,
    included_count: int,
) -> float | None:
    if not row.included:
        return None
    if metric_key in _ONE_PER_INCLUDED:
        return 1.0
    if included_count <= 0:
        raise DifferenceContributionError(
            f"included denominator is zero for arithmetic metric: {metric_key}"
        )
    values = row.canonical_values
    if metric_key == "task.completion.rate":
        return float(bool(values.get("completed"))) / included_count
    if metric_key == "task.incomplete.rate":
        return float(not bool(values.get("completed"))) / included_count
    if metric_key == "task.deadline_miss.completed_observed_rate":
        latency = _number(values, "latency_ms")
        deadline = _number(values, "deadline_ms")
        return float(latency > deadline) / included_count
    if metric_key.startswith("task.decision_share."):
        decision = str(values.get("decision"))
        expected = metric_key.rsplit(".", maxsplit=1)[-1]
        return float(decision == expected) / included_count
    if metric_key == "task.offload.rate":
        return float(values.get("decision") in {"v2i", "v2v"}) / included_count
    if metric_key == "task.latency.mean_ms":
        return _number(values, "latency_ms") / included_count
    if metric_key in {
        "task.energy.mean_per_observed_task_j",
        "task.energy.per_completed_j",
    }:
        return _number(values, "energy_j") / included_count
    if metric_key == "task.energy_delay_product.mean_j_ms":
        return _number(values, "energy_j") * _number(values, "latency_ms") / included_count
    if metric_key == "infra.queue_length.mean":
        return _number(values, "queue_length") / included_count
    if metric_key == "infra.utilisation.mean":
        return _number(values, "utilisation_fraction") / included_count
    if metric_key == "traffic.count.total":
        return _number(values, "count")
    if metric_key == "traffic.count.mean":
        return _number(values, "count") / included_count
    if metric_key == "traffic.speed.mean_mps":
        return _number(values, "average_speed_mps") / included_count
    if metric_key == "trip.completion.rate":
        completed = values.get("arrival_time_s") is not None or _trip_duration(values) is not None
        return float(completed) / included_count
    if metric_key == "trip.duration.mean_s":
        duration = _trip_duration(values)
        if duration is None:
            raise DifferenceContributionError("included trip row has no duration")
        return duration / included_count
    raise DifferenceContributionError(
        f"arithmetic metric has no row formula implementation: {metric_key}"
    )


def _trip_duration(values: dict[str, JsonValue]) -> float | None:
    duration = values.get("duration_s")
    if duration is not None:
        return _finite_number(duration, "duration_s")
    arrival = values.get("arrival_time_s")
    departure = values.get("departure_time_s")
    if arrival is None or departure is None:
        return None
    return _finite_number(arrival, "arrival_time_s") - _finite_number(departure, "departure_time_s")


def _number(values: dict[str, JsonValue], key: str) -> float:
    return _finite_number(values.get(key), key)


def _finite_number(value: object, key: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise DifferenceContributionError(f"included row has no finite numeric {key}")
    return float(value)


def _base_limitations(specific: str) -> list[str]:
    return [
        specific,
        "Both complete accepted canonical candidate-row ledgers are retained, including rows "
        "excluded by the ordinary metric eligibility predicate.",
        "Rows rejected before canonicalisation remain in each source validation report.",
        NON_CAUSALITY_STATEMENT,
    ]


def _json_value(value: JsonValue | JsonScalar) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)

from __future__ import annotations

import csv
from datetime import UTC, datetime
from io import StringIO

import pytest
from pydantic import ValidationError

from tests.helpers import fixed_clock
from traffictwin.provenance.completeness import (
    ClaimCompletenessClassification,
    ClaimEvidence,
    ClaimTraceDepth,
    CompletenessReportStatus,
    assess_claim_evidence,
    build_provenance_completeness_report,
    provenance_completeness_contract,
    provenance_completeness_report_to_csv,
)
from traffictwin.provenance.query import (
    ProvenanceContext,
    ProvenanceQueryError,
    build_provenance_context,
    get_comparison_provenance_completeness,
    get_difference_contributions,
    get_report_provenance_completeness,
)
from traffictwin.reporting.builder import build_full_report, build_run_report
from traffictwin.reporting.models import (
    ReportClaimKind,
    ReportClaimReference,
    ResearchReportType,
)


def _context(name: str) -> ProvenanceContext:
    return build_provenance_context(
        f"tests/fixtures/bundles/{name}",
        clock=fixed_clock,
    )


def test_run_report_inventory_reconciles_and_retains_unavailable_claims() -> None:
    context = _context("baseline_valid")

    report = get_report_provenance_completeness(context, clock=fixed_clock)
    rendered = build_run_report(context.bundle_path, clock=fixed_clock)

    assert report.capability_id == "PRO-03"
    assert report.report_type is ResearchReportType.RUN
    assert report.denominator_count == len(rendered.claim_references) == 33
    assert report.source_row_complete_count == 12
    assert report.aggregate_only_count == 1
    assert report.unavailable_count == 20
    assert report.score == pytest.approx(12 / 33)
    assert report.aggregate_or_better_fraction == pytest.approx(13 / 33)
    assert report.overall_status is CompletenessReportStatus.PARTIAL
    assert len({claim.claim_id for claim in report.claims}) == report.denominator_count
    assert report.unavailable_is_not_zero is True
    assert any(
        claim.classification is ClaimCompletenessClassification.UNAVAILABLE
        for claim in report.claims
    )
    assert {item.category for item in report.exclusions} == {
        "presentation_and_narrative",
        "identity_and_reproduction_metadata",
        "validation_and_evidence_inventory",
    }


def test_partial_evidence_cannot_inflate_the_source_row_score() -> None:
    baseline = get_report_provenance_completeness(_context("baseline_valid"), clock=fixed_clock)
    partial = get_report_provenance_completeness(_context("partial_valid"), clock=fixed_clock)

    assert partial.denominator_count == baseline.denominator_count == 33
    assert partial.source_row_complete_count == 7
    assert partial.aggregate_only_count == 1
    assert partial.unavailable_count == 25
    assert partial.score == pytest.approx(7 / 33)
    assert partial.score < baseline.score  # type: ignore[operator]
    r0 = next(claim for claim in partial.claims if claim.artifact_key == "R0")
    assert r0.classification is ClaimCompletenessClassification.AGGREGATE_ONLY
    assert "one_or_more_metric_dependencies_unavailable" in r0.reason_codes


def test_complete_claim_requires_a_reconciled_accepted_row_ledger() -> None:
    report = get_report_provenance_completeness(_context("baseline_valid"), clock=fixed_clock)
    completion = next(
        claim for claim in report.claims if claim.artifact_key == "task.completion.rate"
    )
    r2 = next(claim for claim in report.claims if claim.artifact_key == "R2")

    assert completion.classification is ClaimCompletenessClassification.SOURCE_ROW_COMPLETE
    assert completion.trace_depth is ClaimTraceDepth.SOURCE_ROW
    assert completion.candidate_source_row_count == 3
    assert completion.included_source_row_count == 3
    assert r2.classification is ClaimCompletenessClassification.AGGREGATE_ONLY
    assert r2.trace_depth is ClaimTraceDepth.SOURCE_ROW
    assert any(reason.startswith("missing_evidence:") for reason in r2.reason_codes)


def test_comparison_inventory_requires_complete_ledgers_on_both_sides() -> None:
    report = get_comparison_provenance_completeness(
        _context("baseline_valid"),
        _context("variation_valid"),
        clock=fixed_clock,
    )

    assert report.report_type is ResearchReportType.COMPARISON
    assert report.denominator_count == 14
    assert report.source_row_complete_count == 7
    assert report.aggregate_only_count == 0
    assert report.unavailable_count == 7
    assert report.score == 0.5
    completion = next(
        claim for claim in report.claims if claim.artifact_key == "task.completion.rate"
    )
    energy = next(
        claim
        for claim in report.claims
        if claim.artifact_key == "task.energy.mean_per_observed_task_j"
    )
    assert completion.classification is ClaimCompletenessClassification.SOURCE_ROW_COMPLETE
    assert completion.candidate_source_row_count == 7
    assert energy.classification is ClaimCompletenessClassification.UNAVAILABLE
    assert energy.candidate_source_row_count == 7


def test_full_report_inventory_matches_exact_typed_rendered_claims() -> None:
    baseline = _context("baseline_valid")
    variation = _context("variation_valid")

    report = get_report_provenance_completeness(
        variation,
        ResearchReportType.FULL,
        comparison_baseline=baseline,
        clock=fixed_clock,
    )
    rendered = build_full_report(
        variation.bundle_path,
        comparison_baseline=baseline.bundle_path,
        clock=fixed_clock,
    )

    assert report.denominator_count == len(rendered.claim_references) == 47
    assert report.source_row_complete_count == 19
    assert report.aggregate_only_count == 1
    assert report.unavailable_count == 27
    assert [claim.claim_id for claim in report.claims] == [
        claim.claim_id for claim in rendered.claim_references
    ]


def test_fingerprint_is_independent_of_generation_timestamp() -> None:
    context = _context("baseline_valid")

    first = get_report_provenance_completeness(
        context,
        clock=lambda: datetime(2026, 7, 20, tzinfo=UTC),
    )
    later = get_report_provenance_completeness(
        context,
        clock=lambda: datetime(2030, 1, 1, tzinfo=UTC),
    )

    assert first.generated_at != later.generated_at
    assert first.fingerprint() == later.fingerprint()
    assert [claim.trace_fingerprint for claim in first.claims] == [
        claim.trace_fingerprint for claim in later.claims
    ]


def test_zero_claim_denominator_is_null_not_perfect() -> None:
    report = build_provenance_completeness_report(
        report_id="report-empty",
        report_type=ResearchReportType.RUN,
        claim_evidence=[],
        exclusions=[],
        clock=fixed_clock,
    )

    assert report.denominator_count == 0
    assert report.score is None
    assert report.aggregate_or_better_fraction is None
    assert report.overall_status is CompletenessReportStatus.NO_CLAIMS


def test_csv_contains_one_row_for_every_denominator_claim() -> None:
    report = get_report_provenance_completeness(_context("baseline_valid"), clock=fixed_clock)

    rows = list(csv.DictReader(StringIO(provenance_completeness_report_to_csv(report))))

    assert len(rows) == report.denominator_count
    assert {row["claim_id"] for row in rows} == {claim.claim_id for claim in report.claims}
    assert all(row["denominator_count"] == "33" for row in rows)


def test_public_contract_and_query_reject_unsupported_report_types() -> None:
    contract = provenance_completeness_contract()

    assert contract.capability_id == "PRO-03"
    assert contract.unavailable_is_not_zero is True
    assert contract.supported_report_types == [
        ResearchReportType.RUN,
        ResearchReportType.DIAGNOSTICS,
        ResearchReportType.COMPARISON,
        ResearchReportType.FULL,
    ]
    assert "score=null" in contract.zero_denominator_policy
    with pytest.raises(ProvenanceQueryError, match="comparison completeness query"):
        get_report_provenance_completeness(_context("baseline_valid"), "comparison")
    with pytest.raises(ProvenanceQueryError, match="report_type must be one of"):
        get_report_provenance_completeness(_context("baseline_valid"), "unknown")


def test_report_model_rejects_counts_or_score_that_do_not_match_claims() -> None:
    report = get_report_provenance_completeness(_context("baseline_valid"), clock=fixed_clock)
    payload = report.model_dump(mode="python")

    with pytest.raises(ValidationError, match="class counts do not match claim inventory"):
        type(report).model_validate(
            {
                **payload,
                "source_row_complete_count": 11,
                "aggregate_only_count": 2,
            }
        )
    with pytest.raises(ValidationError, match="score does not reconcile"):
        type(report).model_validate({**payload, "score": 0.2})


def test_comparison_classification_rejects_cross_side_row_count_masking() -> None:
    baseline = _context("baseline_valid")
    variation = _context("variation_valid")
    difference = get_difference_contributions(
        baseline,
        variation,
        "task.completion.rate",
    )
    broken = difference.model_copy(
        update={
            "baseline": difference.baseline.model_copy(
                update={
                    "candidate_row_count": difference.baseline.candidate_row_count - 1,
                }
            ),
            "variation": difference.variation.model_copy(
                update={
                    "candidate_row_count": difference.variation.candidate_row_count + 1,
                }
            ),
        }
    )
    reference = ReportClaimReference(
        claim_id="report:test:comparison:task.completion.rate",
        claim_kind=ReportClaimKind.METRIC_COMPARISON,
        artifact_key="task.completion.rate",
        section="Metric Deltas",
        label="completion comparison",
    )

    assessment = assess_claim_evidence(
        ClaimEvidence(
            reference=reference,
            artifact_status=broken.status.value,
            difference_report=broken,
        )
    )

    assert assessment.classification is ClaimCompletenessClassification.AGGREGATE_ONLY
    assert "comparison_has_no_nonempty_complete_two_side_row_ledger" in assessment.reason_codes

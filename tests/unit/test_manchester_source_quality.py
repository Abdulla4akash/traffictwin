"""Discriminating tests for transparent source-quality diagnostics."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.snapshot_registry import (
    SnapshotRegistration,
    SnapshotValidationState,
)
from traffictwin.integration.manchester.source_operations_models import (
    EvidenceStanding,
    SourceFamily,
    SourceFreshnessStanding,
)
from traffictwin.integration.manchester.source_quality import (
    SourceQualityDiagnostics,
    SourceQualityInput,
    compute_source_quality_diagnostics,
)

UTC_A = datetime(2026, 7, 22, 10, 0, 0, tzinfo=UTC)
UTC_B = datetime(2026, 7, 22, 10, 1, 0, tzinfo=UTC)
UTC_C = datetime(2026, 7, 22, 10, 2, 0, tzinfo=UTC)
UTC_EVAL = datetime(2026, 7, 22, 13, 0, 0, tzinfo=UTC)


def _fp(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _input(**overrides: object) -> SourceQualityInput:
    base: dict[str, object] = {
        "source_family": SourceFamily.BODS,
        "evaluated_at_utc": UTC_EVAL,
        "total_expected_rows": 100,
        "present_rows": 80,
        "missing_rows": 20,
        "duplicate_rows": 5,
        "accepted_rows": 70,
        "rejected_rows": 10,
        "parser_warnings": (),
        "expected_interval_seconds": None,
        "observed_timestamps_utc": (),
        "spatial_cells_total": None,
        "spatial_cells_covered": None,
        "timestamp_start_utc": None,
        "timestamp_end_utc": None,
        "latest_retrieved_at_utc": UTC_A,
        "freshness": SourceFreshnessStanding.LIVE_VEHICLE,
        "limitations": ("Cannot infer general road traffic.",),
        "schema_version": None,
        "coverage_summary": None,
    }
    base.update(overrides)
    return SourceQualityInput(**base)  # type: ignore[arg-type]


def test_missingness_precise_math() -> None:
    diag = compute_source_quality_diagnostics(_input(total_expected_rows=100, missing_rows=20))
    assert diag.missingness == pytest.approx(0.2)
    # zero denominator returns None
    diag2 = compute_source_quality_diagnostics(_input(total_expected_rows=0, missing_rows=0))
    assert diag2.missingness is None


def test_duplicate_rate_precise() -> None:
    diag = compute_source_quality_diagnostics(_input(present_rows=80, duplicate_rows=5))
    assert diag.duplicate_rate == pytest.approx(0.0625)
    diag2 = compute_source_quality_diagnostics(_input(present_rows=0, duplicate_rows=0))
    assert diag2.duplicate_rate is None


def test_rejected_rate_precise() -> None:
    diag = compute_source_quality_diagnostics(_input(accepted_rows=70, rejected_rows=10))
    assert diag.rejected_rate == pytest.approx(0.125)
    diag2 = compute_source_quality_diagnostics(_input(accepted_rows=0, rejected_rows=0))
    assert diag2.rejected_rate is None


def test_spatial_coverage_precise() -> None:
    diag = compute_source_quality_diagnostics(
        _input(
            spatial_cells_total=10,
            spatial_cells_covered=7,
            total_expected_rows=10,
            present_rows=7,
            missing_rows=3,
            accepted_rows=7,
            rejected_rows=0,
            duplicate_rows=0,
        )
    )
    assert diag.spatial_coverage_rate == pytest.approx(0.7)
    diag2 = compute_source_quality_diagnostics(
        _input(spatial_cells_total=None, spatial_cells_covered=None)
    )
    assert diag2.spatial_coverage_rate is None
    diag3 = compute_source_quality_diagnostics(
        _input(
            spatial_cells_total=0,
            spatial_cells_covered=0,
            total_expected_rows=0,
            present_rows=0,
            missing_rows=0,
            accepted_rows=0,
            rejected_rows=0,
            duplicate_rows=0,
        )
    )
    assert diag3.spatial_coverage_rate is None


def test_timestamp_range_and_freshness() -> None:
    diag = compute_source_quality_diagnostics(
        _input(timestamp_start_utc=UTC_A, timestamp_end_utc=UTC_C, latest_retrieved_at_utc=UTC_A)
    )
    assert diag.timestamp_range_seconds == 120
    assert diag.freshness_delay_seconds == int((UTC_EVAL - UTC_A).total_seconds())
    diag2 = compute_source_quality_diagnostics(
        _input(timestamp_start_utc=None, timestamp_end_utc=None, latest_retrieved_at_utc=None)
    )
    assert diag2.timestamp_range_seconds is None
    assert diag2.freshness_delay_seconds is None


def test_interval_gaps_detected() -> None:
    # expected 60s, observed at 0s, 60s, 180s -> gap of 120s between 60 and 180
    diag = compute_source_quality_diagnostics(
        _input(
            expected_interval_seconds=60,
            observed_timestamps_utc=(UTC_A, UTC_B, UTC_C),
            total_expected_rows=3,
            present_rows=3,
            missing_rows=0,
            accepted_rows=3,
            rejected_rows=0,
            duplicate_rows=0,
        )
    )
    # UTC_A->UTC_B is 60s (no gap), UTC_B->UTC_C is 60s (no gap) -> 0 gaps
    assert diag.interval_gap_count == 0
    # Create gap: 10:00 and 10:02 with 60s expectation -> 120s gap
    diag2 = compute_source_quality_diagnostics(
        _input(
            expected_interval_seconds=60,
            observed_timestamps_utc=(UTC_A, UTC_C),
            total_expected_rows=2,
            present_rows=2,
            missing_rows=0,
            accepted_rows=2,
            rejected_rows=0,
            duplicate_rows=0,
        )
    )
    assert diag2.interval_gap_count == 1
    assert diag2.interval_gaps[0].gap_seconds == 120


def test_zero_denominators_return_none_not_raise() -> None:
    diag = compute_source_quality_diagnostics(
        _input(
            total_expected_rows=0,
            present_rows=0,
            missing_rows=0,
            duplicate_rows=0,
            accepted_rows=0,
            rejected_rows=0,
            spatial_cells_total=None,
            spatial_cells_covered=None,
        )
    )
    assert diag.missingness is None
    assert diag.duplicate_rate is None
    assert diag.rejected_rate is None
    assert diag.spatial_coverage_rate is None


def test_parser_warnings_and_counts() -> None:
    diag = compute_source_quality_diagnostics(
        _input(parser_warnings=("warning: truncated row", "warning: bad delimiter"))
    )
    assert diag.parser_warning_count == 2
    assert diag.parser_warnings == ("warning: truncated row", "warning: bad delimiter")


def test_limitations_passthrough() -> None:
    lim = ("Limitation: bus only.", "No city-wide coverage.")
    diag = compute_source_quality_diagnostics(_input(limitations=lim))
    assert diag.limitations == lim


def test_no_quality_score_field() -> None:
    diag = compute_source_quality_diagnostics(_input())
    assert not hasattr(diag, "quality_score")
    assert not hasattr(diag, "composite_score")
    assert not hasattr(diag, "score")
    # extra fields forbidden
    with pytest.raises(ValidationError):
        SourceQualityDiagnostics.model_validate(
            {**diag.model_dump(mode="python"), "quality_score": 0.9}
        )


def test_secret_value_refusal() -> None:
    with pytest.raises((ValidationError, ValueError)):
        _input(parser_warnings=("api_key= secret12345",))
    with pytest.raises((ValidationError, ValueError)):
        _input(limitations=("token: Bearer abcdefgh12345678",))
    with pytest.raises((ValidationError, ValueError)):
        SourceQualityInput(
            source_family=SourceFamily.BODS,
            evaluated_at_utc=UTC_EVAL,
            total_expected_rows=0,
            present_rows=0,
            missing_rows=0,
            duplicate_rows=0,
            accepted_rows=0,
            rejected_rows=0,
            parser_warnings=(),
            expected_interval_seconds=None,
            observed_timestamps_utc=(),
            limitations=("api_key=supersecretvalue",),
        )


def test_private_path_refusal() -> None:
    with pytest.raises((ValidationError, ValueError)):
        _input(parser_warnings=("check /Users/alice/data.csv",))
    with pytest.raises((ValidationError, ValueError)):
        _input(limitations=("see /tmp/private.csv",))
    with pytest.raises((ValidationError, ValueError)):
        SourceQualityInput(
            source_family=SourceFamily.BODS,
            evaluated_at_utc=UTC_EVAL,
            total_expected_rows=0,
            present_rows=0,
            missing_rows=0,
            duplicate_rows=0,
            accepted_rows=0,
            rejected_rows=0,
            parser_warnings=(),
            expected_interval_seconds=None,
            observed_timestamps_utc=(),
            limitations=("path /private/etc/passwd",),
        )


def test_bods_relabel_refusal_via_snapshot() -> None:
    # BODS must reference bus; general road traffic relabel rejected
    with pytest.raises((ValidationError, ValueError)):
        SnapshotRegistration(
            registration_id="reg-bods-bad",
            snapshot_identity="snap-bods-bad",
            content_fingerprint=_fp("bad"),
            retrieved_at_utc=UTC_A,
            source_family=SourceFamily.BODS,
            coverage_summary="General road traffic in Manchester",
            record_count=10,
            parser_version="p-1.0",
            schema_version="s-1.0",
            validation_state=SnapshotValidationState.ACCEPTED,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
            storage_reference="opaque://x/bods-bad",
            provenance_fingerprint=_fp("prov"),
            validation_receipt_fingerprint=_fp("val"),
            validated_at_utc=UTC_A,
            evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
        )


def test_model_copy_mutation_fails_closed() -> None:
    valid = _input(total_expected_rows=100, missing_rows=20)
    diag = compute_source_quality_diagnostics(valid)
    assert diag.missingness == pytest.approx(0.2)
    # Mutate via model_copy to inflate missing beyond total
    mutated = valid.model_copy(update={"missing_rows": 999})
    with pytest.raises((ValidationError, ValueError)):
        compute_source_quality_diagnostics(mutated)
    # Mutate timestamps to be unsorted
    mutated2 = valid.model_copy(update={"observed_timestamps_utc": (UTC_C, UTC_A)})
    with pytest.raises((ValidationError, ValueError)):
        compute_source_quality_diagnostics(mutated2)
    # Mutate to inject secret
    mutated3 = valid.model_copy(update={"parser_warnings": ("api_key=secret12345",)})
    with pytest.raises((ValidationError, ValueError)):
        compute_source_quality_diagnostics(mutated3)


def test_accepted_rejected_chronology() -> None:
    # latest after evaluated should fail
    with pytest.raises((ValidationError, ValueError)):
        _input(latest_retrieved_at_utc=datetime(2026, 7, 22, 14, 0, tzinfo=UTC))
    # timestamp start after end should fail
    with pytest.raises((ValidationError, ValueError)):
        _input(timestamp_start_utc=UTC_C, timestamp_end_utc=UTC_A)


def test_credential_absence_not_displayed_as_value() -> None:
    # Input has no credential value field; ensure model has no such field
    fields = set(SourceQualityInput.model_fields.keys())
    assert "credential_value" not in fields
    assert "api_key" not in fields
    assert "secret" not in fields
    assert "password" not in fields
    # Diagnostics also must not have credential values
    diag_fields = set(SourceQualityDiagnostics.model_fields.keys())
    assert "credential_value" not in diag_fields


def test_rights_freshness_snapshot_semantics_preserved() -> None:
    # DfT historical only, WebTRIS external, etc. are enforced at snapshot level
    # Verify source_quality respects freshness enum but does not inflate
    diag = compute_source_quality_diagnostics(
        _input(source_family=SourceFamily.DFT, freshness=SourceFreshnessStanding.HISTORICAL)
    )
    assert diag.freshness is SourceFreshnessStanding.HISTORICAL
    # TFGM diagnostic with unavailable freshness
    diag2 = compute_source_quality_diagnostics(
        _input(source_family=SourceFamily.TFGM, freshness=SourceFreshnessStanding.UNAVAILABLE)
    )
    assert diag2.freshness is SourceFreshnessStanding.UNAVAILABLE

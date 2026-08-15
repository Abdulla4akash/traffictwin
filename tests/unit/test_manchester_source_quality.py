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
    diag2 = compute_source_quality_diagnostics(_input(total_expected_rows=0, missing_rows=0))
    assert diag2.missingness is None
    diag3 = compute_source_quality_diagnostics(_input(total_expected_rows=None, missing_rows=None))
    assert diag3.missingness is None
    diag4 = compute_source_quality_diagnostics(_input(total_expected_rows=100, missing_rows=None))
    assert diag4.missingness is None


def test_duplicate_rate_precise() -> None:
    diag = compute_source_quality_diagnostics(_input(present_rows=80, duplicate_rows=5))
    assert diag.duplicate_rate == pytest.approx(0.0625)
    diag2 = compute_source_quality_diagnostics(_input(present_rows=0, duplicate_rows=0))
    assert diag2.duplicate_rate is None
    diag3 = compute_source_quality_diagnostics(_input(present_rows=None, duplicate_rows=None))
    assert diag3.duplicate_rate is None
    diag4 = compute_source_quality_diagnostics(_input(present_rows=80, duplicate_rows=None))
    assert diag4.duplicate_rate is None


def test_rejected_rate_precise() -> None:
    diag = compute_source_quality_diagnostics(_input(accepted_rows=70, rejected_rows=10))
    assert diag.rejected_rate == pytest.approx(0.125)
    diag2 = compute_source_quality_diagnostics(_input(accepted_rows=0, rejected_rows=0))
    assert diag2.rejected_rate is None


def test_unavailable_not_zero() -> None:
    diag = compute_source_quality_diagnostics(
        _input(
            total_expected_rows=None,
            present_rows=None,
            missing_rows=None,
            duplicate_rows=None,
            accepted_rows=7,
            rejected_rows=3,
            spatial_cells_total=None,
            spatial_cells_covered=None,
            expected_interval_seconds=None,
            observed_timestamps_utc=(),
            latest_retrieved_at_utc=None,
            parser_warnings=None,
        )
    )
    assert diag.total_expected_rows is None
    assert diag.present_rows is None
    assert diag.missing_rows is None
    assert diag.duplicate_rows is None
    assert diag.missingness is None
    assert diag.duplicate_rate is None
    assert diag.spatial_coverage_rate is None
    assert diag.timestamp_range_seconds is None
    assert diag.freshness_delay_seconds is None
    assert diag.interval_gap_count is None
    assert diag.interval_gaps == ()
    assert diag.parser_warning_count is None
    assert diag.parser_warnings is None
    assert diag.accepted_rows == 7
    assert diag.rejected_rows == 3
    assert diag.rejected_rate == pytest.approx(0.3)


def test_rejected_rate_row_unit_not_snapshot_mix() -> None:
    # accepted/rejected are row counts, not snapshot counts. 7+999 rows.
    diag = compute_source_quality_diagnostics(
        _input(accepted_rows=7, rejected_rows=999, total_expected_rows=None, missing_rows=None)
    )
    assert diag.rejected_rate == pytest.approx(999 / 1006)
    diag2 = compute_source_quality_diagnostics(
        _input(accepted_rows=999, rejected_rows=7, total_expected_rows=None, missing_rows=None)
    )
    assert diag2.rejected_rate == pytest.approx(7 / 1006)


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
    assert diag.interval_gap_count == 0
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
    with pytest.raises(ValidationError):
        SourceQualityDiagnostics.model_validate(
            {**diag.model_dump(mode="python"), "quality_score": 0.9}
        )


def test_secret_value_refusal() -> None:
    with pytest.raises((ValidationError, ValueError)):
        _input(parser_warnings=("api_key= secret12345",))
    with pytest.raises((ValidationError, ValueError)):
        _input(limitations=("token: Bearer [REDACTED]",))
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
    mutated = valid.model_copy(update={"missing_rows": 999})
    with pytest.raises((ValidationError, ValueError)):
        compute_source_quality_diagnostics(mutated)
    mutated2 = valid.model_copy(update={"observed_timestamps_utc": (UTC_C, UTC_A)})
    with pytest.raises((ValidationError, ValueError)):
        compute_source_quality_diagnostics(mutated2)
    mutated3 = valid.model_copy(update={"parser_warnings": ("api_key=secret12345",)})
    with pytest.raises((ValidationError, ValueError)):
        compute_source_quality_diagnostics(mutated3)


def test_model_copy_malformed_none_bypass() -> None:
    valid = _input(total_expected_rows=100, missing_rows=20, present_rows=80, duplicate_rows=5)
    mutated = valid.model_copy(update={"missing_rows": None})
    # None should be accepted as unavailable and yield missingness None, not 0
    diag = compute_source_quality_diagnostics(mutated)
    assert diag.missingness is None
    mutated2 = valid.model_copy(update={"total_expected_rows": None})
    diag2 = compute_source_quality_diagnostics(mutated2)
    assert diag2.missingness is None


def test_accepted_rejected_chronology() -> None:
    with pytest.raises((ValidationError, ValueError)):
        _input(latest_retrieved_at_utc=datetime(2026, 7, 22, 14, 0, tzinfo=UTC))
    with pytest.raises((ValidationError, ValueError)):
        _input(timestamp_start_utc=UTC_C, timestamp_end_utc=UTC_A)


def test_credential_absence_not_displayed_as_value() -> None:
    fields = set(SourceQualityInput.model_fields.keys())
    assert "credential_value" not in fields
    assert "api_key" not in fields
    assert "secret" not in fields
    assert "password" not in fields
    diag_fields = set(SourceQualityDiagnostics.model_fields.keys())
    assert "credential_value" not in diag_fields


def test_rights_freshness_snapshot_semantics_preserved() -> None:
    diag = compute_source_quality_diagnostics(
        _input(source_family=SourceFamily.DFT, freshness=SourceFreshnessStanding.HISTORICAL)
    )
    assert diag.freshness is SourceFreshnessStanding.HISTORICAL
    diag2 = compute_source_quality_diagnostics(
        _input(source_family=SourceFamily.TFGM, freshness=SourceFreshnessStanding.UNAVAILABLE)
    )
    assert diag2.freshness is SourceFreshnessStanding.UNAVAILABLE


def test_malformed_model_copy_spatial_bypass() -> None:
    valid = _input(spatial_cells_total=10, spatial_cells_covered=7)
    mutated = valid.model_copy(update={"spatial_cells_covered": 999})
    with pytest.raises((ValidationError, ValueError)):
        compute_source_quality_diagnostics(mutated)


def test_interval_gap_unmeasured_none_vs_measured_zero() -> None:
    # Unmeasured: no interval -> None
    diag_none = compute_source_quality_diagnostics(
        _input(expected_interval_seconds=None, observed_timestamps_utc=(), parser_warnings=None)
    )
    assert diag_none.interval_gap_count is None
    assert diag_none.interval_gaps == ()
    # Unmeasured: interval defined but only one timestamp (<2) -> None
    diag_one = compute_source_quality_diagnostics(
        _input(
            expected_interval_seconds=60,
            observed_timestamps_utc=(UTC_A,),
            parser_warnings=None,
        )
    )
    assert diag_one.interval_gap_count is None
    assert diag_one.interval_gaps == ()
    # Measured zero: interval defined and >=2 timestamps with no gap
    diag_zero = compute_source_quality_diagnostics(
        _input(
            expected_interval_seconds=60,
            observed_timestamps_utc=(UTC_A, UTC_B),
            parser_warnings=None,
        )
    )
    assert diag_zero.interval_gap_count == 0
    assert diag_zero.interval_gaps == ()
    # Measured one+: gap exists
    diag_one_gap = compute_source_quality_diagnostics(
        _input(
            expected_interval_seconds=60,
            observed_timestamps_utc=(UTC_A, UTC_C),
            parser_warnings=None,
        )
    )
    assert diag_one_gap.interval_gap_count == 1
    assert len(diag_one_gap.interval_gaps) == 1


def test_parser_warning_unmeasured_vs_measured() -> None:
    diag_none = compute_source_quality_diagnostics(_input(parser_warnings=None))
    assert diag_none.parser_warning_count is None
    assert diag_none.parser_warnings is None
    diag_zero = compute_source_quality_diagnostics(_input(parser_warnings=()))
    assert diag_zero.parser_warning_count == 0
    assert diag_zero.parser_warnings == ()
    diag_two = compute_source_quality_diagnostics(_input(parser_warnings=("w1", "w2")))
    assert diag_two.parser_warning_count == 2
    assert diag_two.parser_warnings == ("w1", "w2")


def test_record_count_bound_refuses_huge_forged() -> None:
    # Registry maximum is 10_000_000; larger accepted_rows must fail closed
    with pytest.raises((ValidationError, ValueError)):
        _input(accepted_rows=20_000_000, parser_warnings=None)
    with pytest.raises((ValidationError, ValueError)):
        SourceQualityInput(
            source_family=SourceFamily.BODS,
            evaluated_at_utc=UTC_EVAL,
            accepted_rows=10_000_001,
            rejected_rows=0,
            parser_warnings=None,
        )
    # Also via diagnostics model directly
    with pytest.raises((ValidationError, ValueError)):
        SourceQualityDiagnostics(
            source_family=SourceFamily.BODS,
            evaluated_at_utc=UTC_EVAL,
            accepted_rows=10_000_001,
            rejected_rows=0,
            interval_gap_count=None,
            parser_warning_count=None,
        )
    # Forged registry record_count > max should also fail when built through registry
    from traffictwin.integration.manchester.snapshot_registry import SnapshotRegistration

    with pytest.raises((ValidationError, ValueError)):
        SnapshotRegistration(
            registration_id="reg-huge",
            snapshot_identity="snap-huge",
            content_fingerprint=_fp("huge"),
            retrieved_at_utc=UTC_A,
            source_family=SourceFamily.BODS,
            coverage_summary="Bus transit positions in admitted GM box - huge",
            record_count=20_000_000,
            parser_version="p-1.0",
            schema_version="s-1.0",
            validation_state=SnapshotValidationState.ACCEPTED,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
            storage_reference="opaque://x/huge",
            provenance_fingerprint=_fp("prov-huge"),
            validation_receipt_fingerprint=_fp("val-huge"),
            validated_at_utc=UTC_A,
            evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
        )


def test_latest_helper_tie_break_registration_id() -> None:
    from traffictwin.integration.manchester.snapshot_registry import (
        SnapshotRegistration,
        SnapshotRegistry,
        latest_accepted_for_family,
        register_snapshot,
    )

    base = SnapshotRegistry(registered_at_utc=UTC_A, snapshots=())
    # Two snapshots with same retrieved_at, different registration_id; latest is max id
    reg_a = SnapshotRegistration(
        registration_id="reg-aaa",
        snapshot_identity="snap-aaa",
        content_fingerprint=_fp("aaa"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.DFT,
        coverage_summary="Admitted DfT count points in Manchester",
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://x/aaa",
        provenance_fingerprint=_fp("prov-aaa"),
        validation_receipt_fingerprint=_fp("val-aaa"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    reg_b = SnapshotRegistration(
        registration_id="reg-zzz",
        snapshot_identity="snap-zzz",
        content_fingerprint=_fp("zzz"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.DFT,
        coverage_summary="Admitted DfT count points in Manchester",
        record_count=20,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://x/zzz",
        provenance_fingerprint=_fp("prov-zzz"),
        validation_receipt_fingerprint=_fp("val-zzz"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    r = register_snapshot(base, reg_a)
    r = register_snapshot(r, reg_b)
    latest = latest_accepted_for_family(r, SourceFamily.DFT)
    assert latest is not None
    assert latest.registration_id == "reg-zzz"
    assert latest.record_count == 20


def test_split_brain_fingerprint_and_pointer_mismatch() -> None:
    import hashlib

    from traffictwin.integration.manchester.snapshot_registry import (
        SnapshotRegistration,
        SnapshotRegistry,
        SnapshotValidationState,
        register_snapshot,
    )
    from traffictwin.integration.manchester.source_operations_models import (
        SourceFamily,
        SourceFreshnessStanding,
    )
    from traffictwin.integration.manchester.source_operations_service import (
        build_source_operations_catalogue,
    )
    from traffictwin.ui.manchester_source_operations import build_quality_inputs_for_catalogue

    def fp(s: str) -> str:
        return hashlib.sha256(s.encode()).hexdigest()

    utc_eval = UTC_EVAL
    # Build a valid registry and catalogue
    base = SnapshotRegistry(registered_at_utc=UTC_A, snapshots=())
    dft_reg = SnapshotRegistration(
        registration_id="reg-dft-001",
        snapshot_identity="snap-dft-001",
        content_fingerprint=fp("dft-001"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.DFT,
        coverage_summary="Admitted DfT count points in Manchester",
        record_count=7,
        parser_version="dft-parser-1.0",
        schema_version="dft-schema-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://snapshots/dft-001",
        provenance_fingerprint=fp("prov-dft-001"),
        validation_receipt_fingerprint=fp("val-dft-001"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    web_reg = SnapshotRegistration(
        registration_id="reg-webtris-001",
        snapshot_identity="snap-webtris-001",
        content_fingerprint=fp("webtris-001"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.WEBTRIS,
        coverage_summary="Selected strategic-road sites only; external to Manchester",
        record_count=5,
        parser_version="webtris-parser-1.0",
        schema_version="webtris-schema-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://snapshots/webtris-001",
        provenance_fingerprint=fp("prov-webtris-001"),
        validation_receipt_fingerprint=fp("val-webtris-001"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA,
    )
    r = register_snapshot(base, dft_reg)
    r = register_snapshot(r, web_reg)
    from traffictwin.ui.manchester_source_operations import make_demonstrator_runtime

    runtime = make_demonstrator_runtime(utc_eval)
    cat = build_source_operations_catalogue(
        evaluated_at_utc=utc_eval, snapshot_registry=r, runtime_by_family=runtime
    )
    # Matching registry passes
    out = build_quality_inputs_for_catalogue(cat, r)
    assert out[SourceFamily.DFT].accepted_rows == 7
    # Mismatched fingerprint: different registry should fail closed
    other_base = SnapshotRegistry(registered_at_utc=UTC_A, snapshots=())
    other = register_snapshot(
        other_base,
        SnapshotRegistration(
            registration_id="reg-dft-other",
            snapshot_identity="snap-dft-other",
            content_fingerprint=fp("other"),
            retrieved_at_utc=UTC_A,
            source_family=SourceFamily.DFT,
            coverage_summary="Admitted DfT count points in Manchester",
            record_count=99,
            parser_version="p-1.0",
            schema_version="s-1.0",
            validation_state=SnapshotValidationState.ACCEPTED,
            freshness=SourceFreshnessStanding.HISTORICAL,
            storage_reference="opaque://x/other",
            provenance_fingerprint=fp("prov-other"),
            validation_receipt_fingerprint=fp("val-other"),
            validated_at_utc=UTC_A,
            evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
        ),
    )
    # Fingerprint mismatch must be typed failure
    with pytest.raises((ValueError, Exception), match="CATALOGUE_REGISTRY_MISMATCH|SPLIT_BRAIN"):
        build_quality_inputs_for_catalogue(cat, other)
    # Pointer mismatch: forge catalogue pointer via model_copy  # noqa: E501
    forged_cat = cat.model_copy(
        update={
            "sources": tuple(
                s.model_copy(
                    update={
                        "latest_accepted_snapshot": s.latest_accepted_snapshot.model_copy(
                            update={"registration_id": "reg-forged"}
                        )
                    }
                )
                if s.source.family is SourceFamily.DFT and s.latest_accepted_snapshot is not None
                else s
                for s in cat.sources
            )
        }
    )
    # Canonical revalidation should catch forged pointer or split-brain should fail
    with pytest.raises((ValueError, Exception)):
        build_quality_inputs_for_catalogue(forged_cat, r)

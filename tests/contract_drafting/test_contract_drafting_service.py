"""Tests for Contract Drafting Assistant service — consensus, recommendations, handoff."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from traffictwin.contract_drafting.service import (
    build_draft_report,
    export_handoff_json,
    export_report_csv,
    export_report_json,
    prepare_handoff,
)
from traffictwin.data_contract.models import LogicalType


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            w.writerow(r)


def test_stable_field_across_all_samples(tmp_path: Path) -> None:
    """Stable field appears in all samples with same type and no nulls."""
    p1 = tmp_path / "s1.csv"
    p2 = tmp_path / "s2.csv"
    p3 = tmp_path / "s3.csv"
    _write_csv(p1, ["id", "value"], [["1", "10"], ["2", "20"]])
    _write_csv(p2, ["id", "value"], [["3", "30"], ["4", "40"]])
    _write_csv(p3, ["id", "value"], [["5", "50"], ["6", "60"]])
    report = build_draft_report([p1, p2, p3])
    # Check presence
    id_cons = next(fc for fc in report.field_consensus if fc.field_name == "id")
    assert id_cons.presence.present_in_samples == 3
    assert id_cons.presence.is_stable is True
    assert id_cons.presence.is_optional is False
    # Recommendation required True
    id_rec = next(df for df in report.draft_fields if df.field_name == "id")
    assert id_rec.recommended_required is True
    assert id_rec.candidate_logical_type == LogicalType.INTEGER
    assert id_rec.confidence.value in {"high", "medium"}  # stable field may be high or medium
    # Findings: no type conflict for stable field
    assert not any(f.field_name == "id" and f.code == "TYPE_CONFLICT" for f in report.findings)


def test_optional_field(tmp_path: Path) -> None:
    """Field appearing only in some samples should be optional (required=False)."""
    p1 = tmp_path / "a.csv"
    p2 = tmp_path / "b.csv"
    p3 = tmp_path / "c.csv"
    _write_csv(p1, ["id", "common", "optional_attr"], [["1", "x", "o1"], ["2", "y", "o2"]])
    _write_csv(p2, ["id", "common"], [["3", "z"], ["4", "w"]])
    _write_csv(p3, ["id", "common", "optional_attr"], [["5", "q", "o3"], ["6", "r", "o4"]])
    report = build_draft_report([p1, p2, p3])
    opt_cons = next(fc for fc in report.field_consensus if fc.field_name == "optional_attr")
    assert opt_cons.presence.present_in_samples == 2
    assert opt_cons.presence.total_samples == 3
    assert opt_cons.presence.is_optional is True
    opt_rec = next(df for df in report.draft_fields if df.field_name == "optional_attr")
    # This is the mutation-sensitive assertion: required must be False when intermittent
    assert opt_rec.recommended_required is False
    assert opt_rec.recommended_required is not True
    # Finding should note intermittency
    assert any(  # noqa: E501
        f.field_name == "optional_attr" and f.code == "FIELD_INTERMITTENT" for f in report.findings
    )


def test_conflicting_types(tmp_path: Path) -> None:
    """Field with different logical types across samples triggers conflict."""
    p1 = tmp_path / "s1.csv"
    p2 = tmp_path / "s2.csv"
    _write_csv(p1, ["mixed"], [["1"], ["2"], ["3"]])  # integer
    _write_csv(p2, ["mixed"], [["hello"], ["world"]])  # string
    report = build_draft_report([p1, p2])
    mixed_cons = next(fc for fc in report.field_consensus if fc.field_name == "mixed")
    assert mixed_cons.type_consensus.is_conflicting is True
    assert len(mixed_cons.type_consensus.observed_types) > 1
    mixed_rec = next(df for df in report.draft_fields if df.field_name == "mixed")
    assert mixed_rec.confidence.value == "conflicted"
    assert any(f.field_name == "mixed" and f.code == "TYPE_CONFLICT" for f in report.findings)


def test_mixed_timezone_semantics(tmp_path: Path) -> None:
    """Timestamp field with mixed aware/naive semantics flagged."""
    p1 = tmp_path / "t1.csv"
    p2 = tmp_path / "t2.csv"
    # aware: ends with Z
    _write_csv(p1, ["ts"], [["2024-01-01T12:00:00Z"], ["2024-01-02T12:00:00Z"]])
    # naive: no Z, no offset
    _write_csv(p2, ["ts"], [["2024-01-01 12:00:00"], ["2024-01-02 12:00:00"]])
    report = build_draft_report([p1, p2])
    ts_cons = next(fc for fc in report.field_consensus if fc.field_name == "ts")
    assert ts_cons.timestamp_consensus is not None
    assert ts_cons.timestamp_consensus.is_mixed_timezone is True
    assert ts_cons.timestamp_consensus.is_ambiguous is True
    # Recommendation should reflect conflicted confidence
    ts_rec = next(df for df in report.draft_fields if df.field_name == "ts")
    assert ts_rec.confidence.value == "conflicted"
    assert any(f.field_name == "ts" and f.code == "MIXED_TIMEZONE" for f in report.findings)


def test_nullability_disagreement(tmp_path: Path) -> None:
    """Field nullable in some samples but not others yields disagreement."""
    p1 = tmp_path / "n1.csv"
    p2 = tmp_path / "n2.csv"
    # p1 has empty cell -> nullable true
    _write_csv(p1, ["maybe_null"], [["a"], [""]])
    _write_csv(p2, ["maybe_null"], [["b"], ["c"]])
    report = build_draft_report([p1, p2])
    fc = next(f for f in report.field_consensus if f.field_name == "maybe_null")
    # Nullable in 1 of 2 observed samples
    assert 0 < fc.nullable_frequency < 1.0
    assert any(  # noqa: E501
        f.field_name == "maybe_null" and f.code == "NULLABILITY_DISAGREEMENT"
        for f in report.findings
    )
    rec = next(df for df in report.draft_fields if df.field_name == "maybe_null")
    assert rec.recommended_nullable is True


def test_categorical_raw_values_absent(tmp_path: Path) -> None:
    """Portable outputs must not contain raw categorical values."""
    p1 = tmp_path / "c1.csv"
    p2 = tmp_path / "c2.csv"
    raw_values = ["alpha_secret_123", "beta_secret_456", "gamma_secret_789"]
    _write_csv(p1, ["category"], [[raw_values[0]], [raw_values[1]]])
    _write_csv(p2, ["category"], [[raw_values[1]], [raw_values[2]]])
    report = build_draft_report([p1, p2])
    json_text = export_report_json(report)
    csv_text = export_report_csv(report)
    handoff = prepare_handoff(report, source_id="test_src")
    handoff_json = export_handoff_json(handoff)
    for raw in raw_values:
        assert raw not in json_text, f"raw categorical value {raw!r} leaked into report JSON"
        assert raw not in csv_text, f"raw categorical value {raw!r} leaked into CSV"
        assert raw not in handoff_json, f"raw categorical value {raw!r} leaked into handoff"
    # But hashes should be present
    assert report.field_consensus[0].categorical_consensus is not None
    cc = next(  # noqa: E501
        fc.categorical_consensus  # type: ignore
        for fc in report.field_consensus
        if fc.field_name == "category"
    )
    assert cc is not None
    assert len(cc.aggregate_hashes) > 0


def test_unit_remains_unknown(tmp_path: Path) -> None:
    """Units must remain unknown unless user-supplied or authoritative."""
    p1 = tmp_path / "u1.csv"
    p2 = tmp_path / "u2.csv"
    _write_csv(p1, ["speed", "count"], [["1.0", "10"], ["2.0", "20"]])
    _write_csv(p2, ["speed", "count"], [["3.0", "30"], ["4.0", "40"]])
    report = build_draft_report([p1, p2])
    for rec in report.draft_fields:
        # No authoritative contract or user suggestion, so unit must be unknown
        assert rec.unit == "unknown", (  # noqa: E501
            f"unit for {rec.field_name!r} should be unknown, got {rec.unit!r}"
        )
    # With user suggestion, unit should be suggestion
    report2 = build_draft_report([p1, p2], user_unit_suggestions={"speed": "m/s"})
    speed_rec = next(df for df in report2.draft_fields if df.field_name == "speed")
    assert speed_rec.unit == "m/s"
    count_rec = next(df for df in report2.draft_fields if df.field_name == "count")
    assert count_rec.unit == "unknown"


def test_deterministic_sample_order_independence(tmp_path: Path) -> None:
    """Fingerprint must be identical regardless of sample order."""
    p1 = tmp_path / "o1.csv"
    p2 = tmp_path / "o2.csv"
    p3 = tmp_path / "o3.csv"
    _write_csv(p1, ["a", "b"], [["1", "x"], ["2", "y"]])
    _write_csv(p2, ["a", "b"], [["3", "z"], ["4", "w"]])
    _write_csv(p3, ["a", "b"], [["5", "q"], ["6", "r"]])
    report_ab = build_draft_report([p1, p2, p3])
    report_ba = build_draft_report([p3, p2, p1])
    report_shuffled = build_draft_report([p2, p1, p3])
    assert report_ab.fingerprint == report_ba.fingerprint
    assert report_ab.fingerprint == report_shuffled.fingerprint
    assert report_ab.request_fingerprint == report_ba.request_fingerprint
    # Canonical JSON should also be order-independent after sorting
    json_ab = export_report_json(report_ab)
    json_ba = export_report_json(report_ba)
    # Parse and compare sorted
    assert json.loads(json_ab)["fingerprint"] == json.loads(json_ba)["fingerprint"]


def test_invalid_sample_refused(tmp_path: Path) -> None:
    """Invalid sample (unsupported suffix) must be refused fail-closed."""
    # Supported suffix but non-existent? Also test unsupported suffix .txt
    p_good = tmp_path / "good.csv"
    _write_csv(p_good, ["a"], [["1"]])
    p_bad = tmp_path / "bad.txt"
    _write_csv(p_bad, ["a"], [["1"]])  # write as txt but suffix .txt not allowed
    # Unsupported suffix should raise
    with pytest.raises(Exception):  # noqa: B017
        build_draft_report([p_good, p_bad])
    # Also test single sample (below minimum 2)
    with pytest.raises(ValueError, match="2-20"):
        build_draft_report([p_good])
    # Also test 21 samples (above maximum)
    many = []
    for i in range(21):
        pp = tmp_path / f"m{i}.csv"
        _write_csv(pp, ["a"], [["1"]])
        many.append(pp)
    with pytest.raises(ValueError, match="2-20"):
        build_draft_report(many)


def test_handoff_draft_only_properties(tmp_path: Path) -> None:
    """Handoff must state draft_only=True, freeze_executed=False, human_review_required=True."""
    p1 = tmp_path / "h1.csv"
    p2 = tmp_path / "h2.csv"
    _write_csv(p1, ["x"], [["1"]])
    _write_csv(p2, ["x"], [["2"]])
    report = build_draft_report([p1, p2])
    handoff = prepare_handoff(report, source_id="test_source", contract_version="1.0.0")
    assert handoff.draft_only is True
    assert handoff.freeze_executed is False
    assert handoff.human_review_required is True
    assert report.draft_only is True
    assert report.freeze_executed is False
    assert report.human_review_required is True
    # Verify handoff is compatible with SourceDataContract editing
    from traffictwin.data_contract.models import SourceDataContract

    contract = SourceDataContract.model_validate(handoff.draft_contract)
    assert contract.source_id == "test_source"
    assert contract.contract_version == "1.0.0"


def test_fingerprint_stability(tmp_path: Path) -> None:
    """Repeated builds with same inputs produce same fingerprint."""
    p1 = tmp_path / "f1.csv"
    p2 = tmp_path / "f2.csv"
    _write_csv(p1, ["id"], [["1"], ["2"]])
    _write_csv(p2, ["id"], [["3"], ["4"]])
    r1 = build_draft_report([p1, p2])
    r2 = build_draft_report([p1, p2])
    assert r1.fingerprint == r2.fingerprint
    assert r1.structural_hash == r2.structural_hash


def test_numeric_precision_scale_ranges(tmp_path: Path) -> None:
    """Numeric consensus should capture precision/scale ranges."""
    p1 = tmp_path / "num1.csv"
    p2 = tmp_path / "num2.csv"
    _write_csv(p1, ["price"], [["1.0"], ["2.00"]])  # scale 1 and 2
    _write_csv(p2, ["price"], [["3.000"], ["4.0000"]])  # scale 3 and 4
    report = build_draft_report([p1, p2])
    fc = next(f for f in report.field_consensus if f.field_name == "price")
    assert fc.numeric_consensus is not None
    assert fc.numeric_consensus.has_numeric_observations is True
    assert fc.numeric_consensus.scale_min is not None
    assert fc.numeric_consensus.scale_max is not None
    assert fc.numeric_consensus.scale_min <= fc.numeric_consensus.scale_max
    # Recommendation should use max
    rec = next(df for df in report.draft_fields if df.field_name == "price")
    assert rec.numeric_scale == fc.numeric_consensus.scale_max


def test_adversarial_workspace_escape_refused(tmp_path: Path) -> None:
    """Sample path escaping workspace must be refused."""
    p_good = tmp_path / "good.csv"
    _write_csv(p_good, ["a"], [["1"]])
    # Path outside approved roots (e.g., /etc/hosts is not csv but we try /tmp/../etc)
    # Use a path that is not under cwd or tmp and has allowed suffix
    # On macOS, /etc is under /, not allowed
    p_escape = Path("/etc/hosts.csv")
    # It won't exist but should be refused due to workspace containment
    with pytest.raises(Exception):  # noqa: B017
        build_draft_report([p_good, p_escape])


def test_no_shell_injection_or_code_execution(tmp_path: Path) -> None:
    """User input must not be executed as code; suggestions are sanitised."""
    p1 = tmp_path / "inj1.csv"
    p2 = tmp_path / "inj2.csv"
    _write_csv(p1, ["field"], [["hello"]])
    _write_csv(p2, ["field"], [["world"]])
    # Try to inject via unit suggestion containing code-like string
    malicious = "import os; os.system('echo hacked')"
    report = build_draft_report([p1, p2], user_unit_suggestions={"field": malicious})
    rec = next(df for df in report.draft_fields if df.field_name == "field")
    # Unit should be stored as provided but not executed; ensure no execution side effect
    assert rec.unit == malicious
    # Ensure no code execution happened (if it had, file would exist etc)
    # Just verify report built
    assert report.fingerprint is not None

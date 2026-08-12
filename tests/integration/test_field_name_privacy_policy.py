"""Product-wide field-name privacy policy (V4 integration, Phase 9).

One deliberate policy spans the Data Contract Workbench and the Contract
Drafting Assistant:

- Schema field names are identity. They are preserved verbatim on every
  export surface (JSON, YAML, CSV, handoff, UI); two distinct fields never
  collapse to one identifier.
- Sensitive-looking field names are signalled explicitly with
  ``PRIVACY_REVIEW_REQUIRED`` — a flag a human reviews, not a rewrite.
- Raw values never enter portable exports; value redaction
  (``redact_value``) and CSV formula-injection protection are unchanged.

The earlier ``[REDACTED_SECRET_FIELD]`` placeholder violated the identity
rule: every secret-looking field in a drift CSV became the same string, so
the per-field report could no longer say which field drifted, while the
adjacent JSON export of the same report carried the exact names anyway.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from traffictwin.contract_drafting.service import (
    build_draft_report,
    export_report_csv,
    export_report_json,
    prepare_handoff,
)
from traffictwin.data_contract.exports import export_drift_csv, export_observation_csv
from traffictwin.data_contract.fingerprint import redact_value
from traffictwin.data_contract.models import (
    FieldObservation,
    LogicalType,
    SchemaDriftFinding,
    SchemaDriftReport,
    SchemaDriftSeverity,
    SchemaObservation,
)

_PLACEHOLDER = "[REDACTED_SECRET_FIELD]"
_FLAG = "PRIVACY_REVIEW_REQUIRED"


def _drift_report(field_names: list[str]) -> SchemaDriftReport:
    return SchemaDriftReport(
        contract_fingerprint="a" * 64,
        candidate_fingerprint="b" * 64,
        contract_version="1.0.0",
        source_id="src1",
        overall_severity=SchemaDriftSeverity.REVIEW_REQUIRED,
        findings=[
            SchemaDriftFinding(
                field_name=name,
                severity=SchemaDriftSeverity.REVIEW_REQUIRED,
                code="OPTIONAL_FIELD_ADDED",
                message=f"field {name} added",
            )
            for name in field_names
        ],
        summary={
            "blocked": 0,
            "review_required": len(field_names),
            "compatible": 0,
            "total": len(field_names),
        },
        fingerprint="c" * 64,
    )


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def test_two_distinct_secret_fields_stay_distinct_in_drift_csv() -> None:
    csv_text = export_drift_csv(_drift_report(["api_key", "session_token"]))
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    names = sorted(row["field_name"] for row in rows)
    assert names == ["api_key", "session_token"], "distinct fields must not collapse"
    assert _PLACEHOLDER not in csv_text
    assert all(row["privacy_review"] == _FLAG for row in rows)


def test_benign_traffic_fields_are_not_flagged() -> None:
    csv_text = export_drift_csv(_drift_report(["journey_time_s", "vehicle_count"]))
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert sorted(row["field_name"] for row in rows) == ["journey_time_s", "vehicle_count"]
    assert all(row["privacy_review"] == "" for row in rows)


def test_observation_csv_preserves_and_flags_without_leaking_values() -> None:
    observation = SchemaObservation(
        observation_id="obs1",
        source_label_redacted="source-1",
        total_observed_rows=2,
        field_observations=[
            FieldObservation(
                field_name="password_hash",
                observed_logical_type=LogicalType.STRING,
                observed_count=2,
                null_count=0,
            ),
            FieldObservation(
                field_name="speed_kmh",
                observed_logical_type=LogicalType.FLOAT,
                observed_count=2,
                null_count=0,
            ),
        ],
        fingerprint="d" * 64,
    )
    csv_text = export_observation_csv(observation)
    rows = {row["field_name"]: row for row in csv.DictReader(io.StringIO(csv_text))}
    assert set(rows) == {"password_hash", "speed_kmh"}
    assert rows["password_hash"]["privacy_review"] == _FLAG
    assert rows["speed_kmh"]["privacy_review"] == ""
    assert _PLACEHOLDER not in csv_text


def test_formula_injection_protection_survives_the_policy() -> None:
    # Field names cannot be formula-shaped at all (model validation requires a
    # leading letter), so formula-injection protection is exercised where free
    # text still flows: the message column.
    report = _drift_report(["api_key"])
    report = report.model_copy(
        update={
            "findings": [report.findings[0].model_copy(update={"message": "=cmd|' /C calc'!A0"})]
        }
    )
    csv_text = export_drift_csv(report)
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert rows[0]["message"].startswith("'="), "formula-safe prefix must remain"
    assert rows[0]["field_name"] == "api_key"
    assert rows[0]["privacy_review"] == _FLAG


def test_value_redaction_is_unchanged_by_the_field_name_policy() -> None:
    assert redact_value("sk-live-abcdef") == "[REDACTED_SECRET_VALUE]"
    assert redact_value("ordinary text") == "ordinary text"
    assert redact_value(None) is None


def test_workbench_and_drafting_assistant_share_one_policy(tmp_path: Path) -> None:
    """Same vocabulary, same identity rule, on both features' surfaces."""

    p1 = tmp_path / "s1.csv"
    p2 = tmp_path / "s2.csv"
    _write_csv(p1, ["api_key", "password", "speed_kmh"], [["a1", "p1", "31.5"]])
    _write_csv(p2, ["api_key", "password", "speed_kmh"], [["a2", "p2", "28.0"]])
    report = build_draft_report([p1, p2])

    drafting_csv = export_report_csv(report)
    drafting_json = export_report_json(report)
    handoff_json = json.dumps(
        prepare_handoff(report, source_id="src1", contract_version="1.0.0").draft_contract
    )
    workbench_csv = export_drift_csv(_drift_report(["api_key", "password", "speed_kmh"]))

    for surface in (drafting_csv, drafting_json, handoff_json, workbench_csv):
        assert _PLACEHOLDER not in surface, "no surface may collapse field identity"
        assert "api_key" in surface and "password" in surface

    flagged = {finding.field_name for finding in report.findings if finding.code == _FLAG}
    assert {"api_key", "password"}.issubset(flagged)
    assert "speed_kmh" not in flagged

    workbench_rows = {
        row["field_name"]: row["privacy_review"]
        for row in csv.DictReader(io.StringIO(workbench_csv))
    }
    assert workbench_rows["api_key"] == _FLAG
    assert workbench_rows["password"] == _FLAG
    assert workbench_rows["speed_kmh"] == ""

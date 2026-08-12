"""Tests for portable exports and fingerprint portability."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from traffictwin.data_contract.drift import compare_observation_to_contract
from traffictwin.data_contract.exports import (
    export_contract_json,
    export_contract_yaml,
    export_drift_csv,
    export_drift_json,
    export_observation_csv,
    export_observation_json,
)
from traffictwin.data_contract.inspection import inspect_tabular_sample
from traffictwin.data_contract.models import (
    FieldContract,
    LogicalType,
    PublicationClass,
    RightsAndRetentionContract,
    SourceDataContract,
)
from traffictwin.data_contract.service import create_frozen_version


def _contract_with_secret() -> SourceDataContract:
    return SourceDataContract(
        source_id="my_source",
        contract_version="1.0.0",
        fields=[
            FieldContract(field_name="api_key", required=True, logical_type=LogicalType.STRING),
            FieldContract(field_name="value", required=True, logical_type=LogicalType.STRING),
        ],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )


def test_portable_exports_exclude_raw_values(tmp_path: Path) -> None:
    p = tmp_path / "sample.csv"
    p.write_text("api_key,value\nsk-12345,hello\nsk-67890,world\n", encoding="utf-8")
    obs = inspect_tabular_sample(
        p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label=str(p)
    )
    contract = _contract_with_secret()
    frozen = create_frozen_version(contract)
    j = export_contract_json(contract)
    assert "sk-12345" not in j
    assert "sk-67890" not in j
    assert str(p) not in j
    assert "sk-12345" not in frozen.fingerprint
    # Observation portable exports must not contain raw row values
    obs_json = export_observation_json(obs)
    obs_csv = export_observation_csv(obs)
    assert "sk-12345" not in obs_json
    assert "sk-67890" not in obs_json
    assert "sk-12345" not in obs_csv
    assert "hello" not in obs_json  # categorical raw never in portable
    assert str(p) not in obs_csv


def test_fingerprint_portability(tmp_path: Path) -> None:
    contract = SourceDataContract(
        source_id="src1",
        contract_version="1.0.0",
        fields=[
            FieldContract(field_name="b", required=True, logical_type=LogicalType.STRING),
            FieldContract(field_name="a", required=True, logical_type=LogicalType.STRING),
        ],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    frozen = create_frozen_version(contract)
    contract2 = SourceDataContract(
        source_id="src1",
        contract_version="1.0.0",
        fields=[
            FieldContract(field_name="a", required=True, logical_type=LogicalType.STRING),
            FieldContract(field_name="b", required=True, logical_type=LogicalType.STRING),
        ],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    from traffictwin.data_contract.service import fingerprint_source_contract

    assert fingerprint_source_contract(contract) == fingerprint_source_contract(contract2)
    assert frozen.fingerprint == create_frozen_version(contract).fingerprint


def test_secret_field_names_are_preserved_and_flagged_in_csv_export() -> None:
    """Field names are identity: preserved verbatim, flagged for privacy review.

    The earlier ``[REDACTED_SECRET_FIELD]`` placeholder collapsed every
    secret-looking field to one identifier, so two distinct fields became
    indistinguishable in the very report meant to describe them per field.
    The product-wide policy (shared with the Contract Drafting Assistant)
    keeps the exact name and signals ``PRIVACY_REVIEW_REQUIRED`` explicitly.
    """
    contract = SourceDataContract(
        source_id="src1",
        contract_version="1.0.0",
        fields=[
            FieldContract(
                field_name="api_key_secret", required=True, logical_type=LogicalType.STRING
            )
        ],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    frozen = create_frozen_version(contract)
    from traffictwin.data_contract.models import (
        SchemaDriftFinding,
        SchemaDriftReport,
        SchemaDriftSeverity,
    )

    report = SchemaDriftReport(
        contract_fingerprint=frozen.fingerprint,
        candidate_fingerprint="b" * 64,
        contract_version="1.0.0",
        source_id="src1",
        overall_severity=SchemaDriftSeverity.REVIEW_REQUIRED,
        findings=[
            SchemaDriftFinding(
                field_name="api_key_secret",
                severity=SchemaDriftSeverity.REVIEW_REQUIRED,
                code="OPTIONAL_FIELD_ADDED",
                message="secret field",
            )
        ],
        summary={"blocked": 0, "review_required": 1, "compatible": 0, "total": 1},
        fingerprint="c" * 64,
    )
    csv_text = export_drift_csv(report)
    assert "[REDACTED_SECRET_FIELD]" not in csv_text
    assert "api_key_secret" in csv_text
    header, row = csv_text.strip().splitlines()[:2]
    assert header.split(",")[-1] == "privacy_review"
    assert row.split(",")[-1] == "PRIVACY_REVIEW_REQUIRED"


def test_formula_safe_csv_export() -> None:
    from traffictwin.data_contract.models import (
        SchemaDriftFinding,
        SchemaDriftReport,
        SchemaDriftSeverity,
    )

    report = SchemaDriftReport(
        contract_fingerprint="a" * 64,
        candidate_fingerprint="b" * 64,
        contract_version="1.0.0",
        source_id="src1",
        overall_severity=SchemaDriftSeverity.COMPATIBLE,
        findings=[
            SchemaDriftFinding(
                field_name="value",
                severity=SchemaDriftSeverity.COMPATIBLE,
                code="TYPE_COMPATIBLE",
                message="=cmd|' /C calc'!A0",
            ),
            SchemaDriftFinding(
                field_name="other",
                severity=SchemaDriftSeverity.COMPATIBLE,
                code="TYPE_COMPATIBLE",
                message="+123",
            ),
            SchemaDriftFinding(
                field_name="third",
                severity=SchemaDriftSeverity.COMPATIBLE,
                code="TYPE_COMPATIBLE",
                message="-2+2",
            ),
            SchemaDriftFinding(
                field_name="fourth",
                severity=SchemaDriftSeverity.COMPATIBLE,
                code="TYPE_COMPATIBLE",
                message="@evil",
            ),
            SchemaDriftFinding(
                field_name="safe",
                severity=SchemaDriftSeverity.COMPATIBLE,
                code="TYPE_COMPATIBLE",
                message="hello",
            ),
        ],
        summary={"blocked": 0, "review_required": 0, "compatible": 5, "total": 5},
        fingerprint="c" * 64,
    )
    csv_text = export_drift_csv(report)
    # Each dangerous prefix must be sanitised with leading '
    assert "'=cmd" in csv_text
    assert "'+123" in csv_text
    assert "'-2+2" in csv_text
    assert "'@evil" in csv_text
    # Safe value must remain unchanged (no extra ')
    assert ",hello" in csv_text or "hello" in csv_text
    # Ensure ordinary csv still parses
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    assert rows[0] == ["field_name", "severity", "code", "message", "privacy_review"]
    # Find the row for safe
    safe_row = next(r for r in rows if "safe" in r[0])
    assert safe_row[3] == "hello"


def test_drift_exports_deterministic(tmp_path: Path) -> None:
    p = tmp_path / "a.csv"
    p.write_text("id,value\n1,hello\n2,world\n", encoding="utf-8")
    obs = inspect_tabular_sample(
        p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    contract = SourceDataContract(
        source_id="src1",
        contract_version="1.0.0",
        fields=[
            FieldContract(field_name="id", required=True, logical_type=LogicalType.STRING),
            FieldContract(field_name="value", required=True, logical_type=LogicalType.STRING),
        ],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    frozen = create_frozen_version(contract)
    report = compare_observation_to_contract(frozen, obs)
    j1 = export_drift_json(report)
    j2 = export_drift_json(report)
    assert j1 == j2
    assert str(p) not in j1
    # Drift export must be valid JSON and contain expected keys
    parsed = json.loads(j1)
    assert "findings" in parsed
    assert "summary" in parsed


def test_yaml_export_is_deterministic() -> None:
    contract = SourceDataContract(
        source_id="src1",
        contract_version="1.0.0",
        fields=[FieldContract(field_name="a", required=True, logical_type=LogicalType.STRING)],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    y1 = export_contract_yaml(contract)
    y2 = export_contract_yaml(contract)
    assert y1 == y2
    assert "source_id" in y1

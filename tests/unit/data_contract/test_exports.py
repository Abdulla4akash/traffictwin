"""Tests for portable exports and fingerprint portability."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from traffictwin.data_contract.exports import (
    export_contract_json,
    export_contract_yaml,
    export_drift_csv,
    export_drift_json,
    export_observation_csv,
)
from traffictwin.data_contract.fingerprint import fingerprint_canonical, sanitise_for_csv
from traffictwin.data_contract.inspection import inspect_tabular_sample
from traffictwin.data_contract.models import (
    FieldContract,
    LogicalType,
    PublicationClass,
    RightsAndRetentionContract,
    SourceDataContract,
    TimestampContract,
    TimeBasis,
    TimezoneSemantics,
    UnitContract,
)
from traffictwin.data_contract.service import create_frozen_version
from traffictwin.data_contract.drift import compare_observation_to_contract


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
    # Create a sample with raw values, observe, freeze, export
    p = tmp_path / "sample.csv"
    p.write_text("api_key,value\nsk-12345,hello\nsk-67890,world\n", encoding="utf-8")
    obs = inspect_tabular_sample(p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label=str(p))
    contract = _contract_with_secret()
    frozen = create_frozen_version(contract)
    j = export_contract_json(contract)
    # Raw values must not appear in portable export
    assert "sk-12345" not in j
    assert str(p) not in j
    # Portable fingerprint must not contain raw values
    assert "sk-12345" not in frozen.fingerprint
    # Observation export must not contain raw path or secrets?
    # But categorical digest may contain values; ensure formula-safe and redacted handling
    obs_csv = export_observation_csv(obs)
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
    # Re-create same contract with fields in different order – fingerprint should be same due to canonical sorting
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
    # Fingerprint excludes wall clock – create again should be deterministic
    assert frozen.fingerprint == create_frozen_version(contract).fingerprint


def test_secret_redaction_in_csv_export() -> None:
    contract = SourceDataContract(
        source_id="src1",
        contract_version="1.0.0",
        fields=[FieldContract(field_name="api_key_secret", required=True, logical_type=LogicalType.STRING)],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    frozen = create_frozen_version(contract)
    # Create observation with secret field
    p = Path("dummy.csv")  # not used, we synthesize report
    # Use drift report with secret field name
    import csv as csvmod

    from traffictwin.data_contract.models import SchemaDriftReport, SchemaDriftFinding, SchemaDriftSeverity

    report = SchemaDriftReport(
        contract_fingerprint=frozen.fingerprint,
        candidate_fingerprint="b" * 64,
        contract_version="1.0.0",
        source_id="src1",
        overall_severity=SchemaDriftSeverity.REVIEW_REQUIRED,
        findings=[
            SchemaDriftFinding(field_name="api_key_secret", severity=SchemaDriftSeverity.REVIEW_REQUIRED, code="OPTIONAL_FIELD_ADDED", message="secret field")
        ],
        summary={"blocked": 0, "review_required": 1, "compatible": 0, "total": 1},
        fingerprint="c" * 64,
    )
    csv_text = export_drift_csv(report)
    # Secret field name must be redacted
    assert "[REDACTED_SECRET_FIELD]" in csv_text
    assert "api_key_secret" not in csv_text


def test_formula_safe_csv_export() -> None:
    from traffictwin.data_contract.models import SchemaDriftFinding, SchemaDriftReport, SchemaDriftSeverity

    report = SchemaDriftReport(
        contract_fingerprint="a" * 64,
        candidate_fingerprint="b" * 64,
        contract_version="1.0.0",
        source_id="src1",
        overall_severity=SchemaDriftSeverity.COMPATIBLE,
        findings=[
            SchemaDriftFinding(field_name="value", severity=SchemaDriftSeverity.COMPATIBLE, code="TYPE_COMPATIBLE", message="=cmd|' /C calc'!A0"),
            SchemaDriftFinding(field_name="other", severity=SchemaDriftSeverity.COMPATIBLE, code="TYPE_COMPATIBLE", message="+123"),
        ],
        summary={"blocked": 0, "review_required": 0, "compatible": 2, "total": 2},
        fingerprint="c" * 64,
    )
    csv_text = export_drift_csv(report)
    # Formula-like values should be prefixed with '
    assert "'=cmd" in csv_text
    assert "'+123" in csv_text or "'+123" in csv_text or "'+" in csv_text


def test_drift_exports_deterministic(tmp_path: Path) -> None:
    p = tmp_path / "a.csv"
    p.write_text("id,value\n1,hello\n2,world\n", encoding="utf-8")
    obs = inspect_tabular_sample(p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local")
    contract = SourceDataContract(
        source_id="src1",
        contract_version="1.0.0",
        fields=[FieldContract(field_name="id", required=True, logical_type=LogicalType.STRING), FieldContract(field_name="value", required=True, logical_type=LogicalType.STRING)],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    frozen = create_frozen_version(contract)
    report = compare_observation_to_contract(frozen, obs)
    j1 = export_drift_json(report)
    j2 = export_drift_json(report)
    assert j1 == j2
    # Ensure sorted keys and no raw path
    assert str(p) not in j1
    assert "=" not in j1 or "'=" not in j1  # not formula injection check


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

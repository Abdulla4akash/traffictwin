"""Adversarial / mutation tests for required guards."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

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
from traffictwin.data_contract.drift import compare_contracts, compare_observation_to_contract
from traffictwin.data_contract.inspection import inspect_tabular_sample
from traffictwin.data_contract.exports import export_contract_json, export_drift_csv


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def test_mutation_missing_required_field_classified_compatible_fails() -> None:
    """Mutation: change REQUIRED_FIELD_REMOVED from BLOCKED to COMPATIBLE should be caught."""
    contract = SourceDataContract(
        source_id="src1",
        contract_version="1.0.0",
        fields=[FieldContract(field_name="a", required=True, logical_type=LogicalType.STRING)],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    frozen = create_frozen_version(contract)
    # Simulate observation missing required field
    p = Path("/tmp/mut_test_adv1.csv")
    # Use drift logic directly: missing required field should be BLOCKED, not COMPATIBLE
    # If code were mutated to COMPATIBLE, this test would fail
    tmp = Path("/tmp")
    import tempfile
    import os

    # Create a temporary file for inspection
    import pathlib

    tmp_path = Path(tempfile.mkdtemp())
    pp = tmp_path / "obs.csv"
    _write_csv(pp, ["other"], [["1"]])
    obs = inspect_tabular_sample(pp, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local")
    report = compare_observation_to_contract(frozen, obs)
    finding = next((f for f in report.findings if f.code == "REQUIRED_FIELD_REMOVED"), None)
    assert finding is not None, "REQUIRED_FIELD_REMOVED finding must exist"
    assert finding.severity.value == "blocked", "Mutation would make this compatible – must remain blocked"


def test_mutation_unit_change_classified_compatible_fails() -> None:
    """Mutation: unit change from BLOCKED to COMPATIBLE should be caught."""
    contract = SourceDataContract(
        source_id="src1",
        contract_version="1.0.0",
        fields=[FieldContract(field_name="speed", required=True, logical_type=LogicalType.FLOAT, unit=UnitContract(unit="mps", dimension="speed"))],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    frozen = create_frozen_version(contract)
    candidate = SourceDataContract(
        source_id="src1",
        contract_version="1.0.1",
        fields=[FieldContract(field_name="speed", required=True, logical_type=LogicalType.FLOAT, unit=UnitContract(unit="kmh", dimension="speed"))],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    report = compare_contracts(frozen, candidate)
    finding = next((f for f in report.findings if f.code == "UNIT_CHANGED_INCOMPATIBLY"), None)
    assert finding is not None
    assert finding.severity.value == "blocked", "Unit change must be blocked, mutation to compatible should fail"


def test_mutation_timestamp_change_classified_compatible_fails() -> None:
    """Mutation: timestamp semantics change should remain BLOCKED."""
    contract = SourceDataContract(
        source_id="src1",
        contract_version="1.0.0",
        fields=[FieldContract(field_name="ts", required=True, logical_type=LogicalType.TIMESTAMP, timestamp=TimestampContract(time_basis=TimeBasis.ISO8601, timezone=TimezoneSemantics.UTC))],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    frozen = create_frozen_version(contract)
    candidate = SourceDataContract(
        source_id="src1",
        contract_version="1.0.1",
        fields=[FieldContract(field_name="ts", required=True, logical_type=LogicalType.TIMESTAMP, timestamp=TimestampContract(time_basis=TimeBasis.UNIX_EPOCH_SECONDS, timezone=TimezoneSemantics.UTC))],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    report = compare_contracts(frozen, candidate)
    finding = next((f for f in report.findings if f.code == "TIME_BASIS_CHANGED"), None)
    assert finding is not None
    assert finding.severity.value == "blocked"


def test_mutation_raw_values_in_portable_output_fails(tmp_path: Path) -> None:
    """Mutation: raw values leaking into portable JSON should be caught."""
    contract = SourceDataContract(
        source_id="src1",
        contract_version="1.0.0",
        fields=[FieldContract(field_name="value", required=True, logical_type=LogicalType.STRING)],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    p = tmp_path / "raw.csv"
    _write_csv(p, ["value"], [["SECRET_RAW_12345"]])
    obs = inspect_tabular_sample(p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label=str(p))
    j = export_contract_json(contract)
    assert "SECRET_RAW_12345" not in j
    assert str(p) not in j
    # If code were mutated to include raw values, this would fail
    assert "SECRET_RAW_12345" not in obs.fingerprint


def test_mutation_frozen_editable_fails() -> None:
    """Mutation: allowing frozen contract edit should be caught."""
    contract = SourceDataContract(
        source_id="src1",
        contract_version="1.0.0",
        fields=[FieldContract(field_name="a", required=True, logical_type=LogicalType.STRING)],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    frozen = create_frozen_version(contract)
    with pytest.raises(Exception):
        frozen.version = "2.0.0"  # type: ignore[attr-defined]
    # Also test that contract inside frozen cannot be mutated without new version
    with pytest.raises(Exception):
        frozen.contract.source_id = "hacked"  # type: ignore[attr-defined]


def test_mutation_unbounded_read_bypass_fails(tmp_path: Path) -> None:
    """Mutation: bypassing max_bytes limit should be caught."""
    p = tmp_path / "big.csv"
    # Create a file larger than limit
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["a"])
        for _ in range(100):
            w.writerow(["x" * 1000])
    # With tiny limit, should raise, not silently succeed
    with pytest.raises(Exception, match="exceeds"):
        inspect_tabular_sample(p, max_rows=10000, max_bytes=100, observation_id="obs_001", source_label="local")

"""Adversarial / mutation tests for required guards."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from traffictwin.data_contract.drift import compare_contracts, compare_observation_to_contract
from traffictwin.data_contract.exports import export_observation_csv, export_observation_json
from traffictwin.data_contract.inspection import inspect_tabular_sample
from traffictwin.data_contract.models import (
    FieldContract,
    LogicalType,
    PublicationClass,
    RightsAndRetentionContract,
    SourceDataContract,
    TimeBasis,
    TimestampContract,
    TimezoneSemantics,
    UnitContract,
)
from traffictwin.data_contract.service import create_frozen_version


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def test_mutation_missing_required_field_classified_compatible_fails(tmp_path: Path) -> None:
    """Mutation: change REQUIRED_FIELD_REMOVED from BLOCKED to COMPATIBLE should be caught."""
    contract = SourceDataContract(
        source_id="src1",
        contract_version="1.0.0",
        fields=[FieldContract(field_name="a", required=True, logical_type=LogicalType.STRING)],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    frozen = create_frozen_version(contract)
    pp = tmp_path / "obs.csv"
    _write_csv(pp, ["other"], [["1"]])
    obs = inspect_tabular_sample(
        pp, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    report = compare_observation_to_contract(frozen, obs)
    finding = next((f for f in report.findings if f.code == "REQUIRED_FIELD_REMOVED"), None)
    assert finding is not None, "REQUIRED_FIELD_REMOVED finding must exist"
    assert finding.severity.value == "blocked"


def test_mutation_unit_change_classified_compatible_fails() -> None:
    """Mutation: unit change from BLOCKED to COMPATIBLE should be caught."""
    contract = SourceDataContract(
        source_id="src1",
        contract_version="1.0.0",
        fields=[
            FieldContract(
                field_name="speed",
                required=True,
                logical_type=LogicalType.FLOAT,
                unit=UnitContract(unit="mps", dimension="speed"),
            )
        ],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    frozen = create_frozen_version(contract)
    candidate = SourceDataContract(
        source_id="src1",
        contract_version="1.0.1",
        fields=[
            FieldContract(
                field_name="speed",
                required=True,
                logical_type=LogicalType.FLOAT,
                unit=UnitContract(unit="kmh", dimension="speed"),
            )
        ],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    report = compare_contracts(frozen, candidate)
    finding = next((f for f in report.findings if f.code == "UNIT_CHANGED_INCOMPATIBLY"), None)
    assert finding is not None
    assert finding.severity.value == "blocked"


def test_mutation_timestamp_change_classified_compatible_fails() -> None:
    """Mutation: timestamp semantics change should remain BLOCKED."""
    contract = SourceDataContract(
        source_id="src1",
        contract_version="1.0.0",
        fields=[
            FieldContract(
                field_name="ts",
                required=True,
                logical_type=LogicalType.TIMESTAMP,
                timestamp=TimestampContract(
                    time_basis=TimeBasis.ISO8601, timezone=TimezoneSemantics.UTC
                ),
            )
        ],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    frozen = create_frozen_version(contract)
    candidate = SourceDataContract(
        source_id="src1",
        contract_version="1.0.1",
        fields=[
            FieldContract(
                field_name="ts",
                required=True,
                logical_type=LogicalType.TIMESTAMP,
                timestamp=TimestampContract(
                    time_basis=TimeBasis.UNIX_EPOCH_SECONDS, timezone=TimezoneSemantics.UTC
                ),
            )
        ],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    report = compare_contracts(frozen, candidate)
    finding = next((f for f in report.findings if f.code == "TIME_BASIS_CHANGED"), None)
    assert finding is not None
    assert finding.severity.value == "blocked"


def test_mutation_raw_values_in_portable_output_fails(tmp_path: Path) -> None:
    """Real path: categorical raw values must not appear in portable observation exports."""
    headers = ["name", "city", "token"]
    rows = [
        ["Jane Doe", "Manchester", "ghp_FAKE1234567890123456789012345678901234"],
        ["John Roe", "Leeds", "sk-fake-secret-value-1234567890"],
        ["Jane Doe", "Manchester", "AKIAIOSFODNN7EXAMPLE"],
    ]
    p = tmp_path / "raw.csv"
    _write_csv(p, headers, rows)
    obs = inspect_tabular_sample(
        p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    # Real exports
    j = export_observation_json(obs)
    csv_text = export_observation_csv(obs)
    # None of the raw values may appear in either export
    for raw in [
        "Jane Doe",
        "John Roe",
        "Manchester",
        "Leeds",
        "ghp_FAKE",
        "sk-fake",
        "AKIAIOSFODNN7EXAMPLE",
    ]:
        assert raw not in j, f"raw value {raw!r} leaked into JSON export"
        assert raw not in csv_text, f"raw value {raw!r} leaked into CSV export"
    # Structured observation must not store raw categorical members either
    payload = obs.model_dump(mode="json")
    payload_str = str(payload)
    for raw in ["Jane Doe", "Manchester"]:
        assert raw not in payload_str, "raw categorical member stored in portable observation"
    # Fingerprint is hex, never contains raw
    assert "Jane Doe" not in obs.fingerprint
    # Also ensure distinct_count/hash are present, not raw list
    for fo in obs.field_observations:
        assert (
            fo.categorical_aggregate_hash is None or "Jane Doe" not in fo.categorical_aggregate_hash
        )


def test_mutation_frozen_editable_fails() -> None:
    """Mutation: allowing frozen contract edit should be caught."""
    contract = SourceDataContract(
        source_id="src1",
        contract_version="1.0.0",
        fields=[FieldContract(field_name="a", required=True, logical_type=LogicalType.STRING)],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    frozen = create_frozen_version(contract)
    with pytest.raises(Exception):  # noqa: B017
        frozen.version = "2.0.0"  # type: ignore[attr-defined]
    with pytest.raises(Exception):  # noqa: B017
        frozen.contract.source_id = "hacked"  # type: ignore[attr-defined]


def test_mutation_unbounded_read_bypass_fails(tmp_path: Path) -> None:
    """Mutation: bypassing max_bytes limit should be caught."""
    p = tmp_path / "big.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["a"])
        for _ in range(100):
            w.writerow(["x" * 1000])
    with pytest.raises(Exception, match="exceeds"):
        inspect_tabular_sample(
            p, max_rows=10000, max_bytes=100, observation_id="obs_001", source_label="local"
        )

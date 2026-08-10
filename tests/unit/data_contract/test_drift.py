"""Tests for drift classification."""

from __future__ import annotations

import csv
from pathlib import Path

from traffictwin.data_contract.drift import compare_contracts, compare_observation_to_contract
from traffictwin.data_contract.inspection import inspect_tabular_sample
from traffictwin.data_contract.models import (
    FieldContract,
    LogicalType,
    PublicationClass,
    RightsAndRetentionContract,
    SchemaDriftSeverity,
    SourceDataContract,
    TimeBasis,
    TimestampContract,
    TimezoneSemantics,
    UnitContract,
)
from traffictwin.data_contract.service import create_frozen_version


def _contract(
    fields: list[FieldContract],
    source_id: str = "src1",
    version: str = "1.0.0",
    pub: PublicationClass = PublicationClass.PRIVATE,
) -> SourceDataContract:
    return SourceDataContract(
        source_id=source_id,
        contract_version=version,
        fields=fields,
        rights=RightsAndRetentionContract(publication_class=pub),
    )


def _field(
    name: str,
    required: bool = True,
    ltype: LogicalType = LogicalType.STRING,
    unit: UnitContract | None = None,
    ts: TimestampContract | None = None,
) -> FieldContract:
    return FieldContract(
        field_name=name, required=required, logical_type=ltype, unit=unit, timestamp=ts
    )


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def test_required_field_removed_is_blocked(tmp_path: Path) -> None:
    contract = _contract([_field("a", required=True), _field("b", required=True)])
    frozen = create_frozen_version(contract)
    # Observation missing required field "b"
    p = tmp_path / "obs.csv"
    _write_csv(p, ["a"], [["1"], ["2"]])
    obs = inspect_tabular_sample(
        p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    report = compare_observation_to_contract(frozen, obs)
    blocked = [f for f in report.findings if f.code == "REQUIRED_FIELD_REMOVED"]
    assert len(blocked) == 1
    assert blocked[0].severity == SchemaDriftSeverity.BLOCKED
    assert report.overall_severity == SchemaDriftSeverity.BLOCKED


def test_optional_field_added_is_review_required(tmp_path: Path) -> None:
    contract = _contract([_field("a", required=True)])
    frozen = create_frozen_version(contract)
    p = tmp_path / "obs2.csv"
    _write_csv(p, ["a", "extra"], [["1", "x"], ["2", "y"]])
    obs = inspect_tabular_sample(
        p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    report = compare_observation_to_contract(frozen, obs)
    added = [f for f in report.findings if f.code == "OPTIONAL_FIELD_ADDED"]
    assert len(added) == 1
    assert added[0].severity == SchemaDriftSeverity.REVIEW_REQUIRED


def test_required_nullable_is_review_required(tmp_path: Path) -> None:
    contract = _contract([_field("a", required=True, ltype=LogicalType.STRING)])
    frozen = create_frozen_version(contract)
    p = tmp_path / "obs3.csv"
    _write_csv(p, ["a"], [["1"], [""], ["3"]])
    obs = inspect_tabular_sample(
        p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    report = compare_observation_to_contract(frozen, obs)
    nullable = [f for f in report.findings if f.code == "REQUIRED_FIELD_BECOMES_NULLABLE"]
    assert len(nullable) == 1
    assert nullable[0].severity == SchemaDriftSeverity.REVIEW_REQUIRED


def test_incompatible_type_is_blocked(tmp_path: Path) -> None:
    contract = _contract([_field("count", required=True, ltype=LogicalType.INTEGER)])
    frozen = create_frozen_version(contract)
    p = tmp_path / "obs4.csv"
    _write_csv(p, ["count"], [["hello"], ["world"]])
    obs = inspect_tabular_sample(
        p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    report = compare_observation_to_contract(frozen, obs)
    blocked = [f for f in report.findings if f.code == "INCOMPATIBLE_LOGICAL_TYPE"]
    assert len(blocked) == 1
    assert blocked[0].severity == SchemaDriftSeverity.BLOCKED


def test_type_widening_is_review_required(tmp_path: Path) -> None:
    contract = _contract([_field("count", required=True, ltype=LogicalType.INTEGER)])
    frozen = create_frozen_version(contract)
    p = tmp_path / "obs5.csv"
    _write_csv(p, ["count"], [["1.5"], ["2.5"]])
    obs = inspect_tabular_sample(
        p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    report = compare_observation_to_contract(frozen, obs)
    widening = [f for f in report.findings if f.code == "TYPE_WIDENING"]
    assert len(widening) == 1
    assert widening[0].severity == SchemaDriftSeverity.REVIEW_REQUIRED


def test_timestamp_timezone_ambiguity_blocked(tmp_path: Path) -> None:
    contract = _contract(
        [
            FieldContract(
                field_name="ts",
                required=True,
                logical_type=LogicalType.TIMESTAMP,
                timestamp=TimestampContract(
                    time_basis=TimeBasis.ISO8601, timezone=TimezoneSemantics.UTC
                ),
            )
        ]
    )
    frozen = create_frozen_version(contract)
    # Naive timestamps without TZ should be blocked when UTC expected
    p = tmp_path / "obs6.csv"
    _write_csv(p, ["ts"], [["2024-01-01 00:00:00"], ["2024-01-02 00:00:00"]])
    obs = inspect_tabular_sample(
        p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    report = compare_observation_to_contract(frozen, obs)
    blocked = [f for f in report.findings if f.code == "TIMEZONE_SEMANTICS_CHANGED"]
    assert len(blocked) >= 1
    assert blocked[0].severity == SchemaDriftSeverity.BLOCKED


def test_unit_change_is_blocked() -> None:
    contract = _contract(
        [
            _field(
                "speed",
                required=True,
                ltype=LogicalType.FLOAT,
                unit=UnitContract(unit="mps", dimension="speed"),
            )
        ]
    )
    frozen = create_frozen_version(contract)
    candidate = _contract(
        [
            _field(
                "speed",
                required=True,
                ltype=LogicalType.FLOAT,
                unit=UnitContract(unit="kmh", dimension="speed"),
            )
        ],
        version="1.0.1",
    )
    report = compare_contracts(frozen, candidate)
    unit_blocked = [f for f in report.findings if f.code == "UNIT_CHANGED_INCOMPATIBLY"]
    assert len(unit_blocked) == 1
    assert unit_blocked[0].severity == SchemaDriftSeverity.BLOCKED


def test_field_reorder_is_compatible(tmp_path: Path) -> None:
    # Use integer types to avoid string/integer mismatch; focus on reorder
    contract = _contract(
        [_field("a", ltype=LogicalType.INTEGER), _field("b", ltype=LogicalType.INTEGER)]
    )
    frozen = create_frozen_version(contract)
    p = tmp_path / "obs7.csv"
    _write_csv(p, ["b", "a"], [["2", "1"], ["4", "3"]])
    obs = inspect_tabular_sample(
        p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    report = compare_observation_to_contract(frozen, obs)
    reorder = [f for f in report.findings if f.code == "COLUMN_REORDERING"]
    assert len(reorder) == 1
    assert reorder[0].severity == SchemaDriftSeverity.COMPATIBLE
    # Reorder alone should not make overall blocked when types match
    assert report.overall_severity == SchemaDriftSeverity.COMPATIBLE


def test_extra_fields_review_required(tmp_path: Path) -> None:
    contract = _contract([_field("a")])
    frozen = create_frozen_version(contract)
    p = tmp_path / "obs8.csv"
    _write_csv(p, ["a", "b", "c"], [["1", "2", "3"]])
    obs = inspect_tabular_sample(
        p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    report = compare_observation_to_contract(frozen, obs)
    added = [f for f in report.findings if f.code == "OPTIONAL_FIELD_ADDED"]
    assert len(added) == 2


def test_timestamp_semantics_change_blocked() -> None:
    contract = _contract(
        [
            FieldContract(
                field_name="ts",
                required=True,
                logical_type=LogicalType.TIMESTAMP,
                timestamp=TimestampContract(
                    time_basis=TimeBasis.ISO8601, timezone=TimezoneSemantics.UTC
                ),
            )
        ]
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
    time_basis = [f for f in report.findings if f.code == "TIME_BASIS_CHANGED"]
    assert len(time_basis) == 1
    assert time_basis[0].severity == SchemaDriftSeverity.BLOCKED


def test_source_identity_changed_blocked() -> None:
    contract = _contract([_field("a")], source_id="src1")
    frozen = create_frozen_version(contract)
    candidate = _contract([_field("a")], source_id="src2", version="1.0.1")
    report = compare_contracts(frozen, candidate)
    src = [f for f in report.findings if f.code == "SOURCE_IDENTITY_CHANGED"]
    assert len(src) == 1
    assert src[0].severity == SchemaDriftSeverity.BLOCKED


def test_privacy_weakening_blocked() -> None:
    contract = _contract([_field("a")], pub=PublicationClass.PRIVATE)
    frozen = create_frozen_version(contract)
    candidate = _contract([_field("a")], pub=PublicationClass.OPEN, version="1.0.1")
    report = compare_contracts(frozen, candidate)
    weak = [f for f in report.findings if f.code == "PRIVACY_CLASSIFICATION_WEAKENED"]
    assert len(weak) == 1
    assert weak[0].severity == SchemaDriftSeverity.BLOCKED

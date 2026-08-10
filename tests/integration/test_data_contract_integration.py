"""Integration tests for observe -> freeze -> compare -> export -> handoff."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from traffictwin.data_contract.exports import (
    export_contract_json,
    export_contract_yaml,
    export_drift_json,
    export_drift_csv,
    export_observation_csv,
)
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
from traffictwin.data_contract.service import (
    create_frozen_version,
    create_new_version_from_parent,
    prepare_handoff_to_manifest,
)
from traffictwin.data_contract.drift import compare_observation_to_contract


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def test_end_to_end_observe_freeze_compare_export_handoff(tmp_path: Path) -> None:
    # 1. Observe
    headers = ["timestamp", "vehicle_id", "speed"]
    rows = [["2024-01-01T00:00:00Z", "veh1", "12.5"], ["2024-01-01T00:01:00Z", "veh2", "15.0"]]
    p1 = tmp_path / "sample.csv"
    _write_csv(p1, headers, rows)
    obs = inspect_tabular_sample(p1, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local")
    assert obs.total_observed_rows == 2
    assert len(obs.field_observations) == 3

    # 2. Author contract from observation (confirm field identity etc.)
    contract = SourceDataContract(
        source_id="manchester_buses",
        contract_version="1.0.0",
        fields=[
            FieldContract(field_name="timestamp", required=True, logical_type=LogicalType.TIMESTAMP, timestamp=TimestampContract(time_basis=TimeBasis.ISO8601, timezone=TimezoneSemantics.UTC)),
            FieldContract(field_name="vehicle_id", required=True, logical_type=LogicalType.STRING),
            FieldContract(field_name="speed", required=False, logical_type=LogicalType.FLOAT, unit=UnitContract(unit="mps", dimension="speed")),
        ],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
        notes="initial contract",
    )

    # 3. Freeze
    frozen = create_frozen_version(contract)
    assert frozen.is_frozen
    assert frozen.fingerprint

    # 4. Compare later sample with drift (extra field + potential reorder)
    p2 = tmp_path / "later.csv"
    # Use float value "10.5" to keep type compatible (FLOAT expected, FLOAT observed)
    _write_csv(p2, ["vehicle_id", "timestamp", "speed", "extra"], [["veh3", "2024-01-02T00:00:00Z", "10.5", "newval"]])
    obs2 = inspect_tabular_sample(p2, max_rows=10, max_bytes=1_000_000, observation_id="obs_002", source_label="local")
    report = compare_observation_to_contract(frozen, obs2)
    # Extra field should be review_required; overall may be review due to extra field
    assert any(f.code == "OPTIONAL_FIELD_ADDED" for f in report.findings)
    # If reorder is detected, it should be compatible
    reorder_findings = [f for f in report.findings if f.code == "COLUMN_REORDERING"]
    if reorder_findings:
        assert reorder_findings[0].severity.value == "compatible"

    # 5. Export contract and drift
    contract_json = export_contract_json(contract)
    contract_yaml = export_contract_yaml(contract)
    drift_json = export_drift_json(report)
    drift_csv = export_drift_csv(report)
    obs_csv = export_observation_csv(obs)

    assert "manchester_buses" in contract_json
    assert "manchester_buses" in contract_yaml
    assert "OPTIONAL_FIELD_ADDED" in drift_json
    assert "field_name" in drift_csv
    assert "vehicle_id" in obs_csv

    # Verify portable exports exclude raw row values and paths
    assert str(p1) not in contract_json
    assert str(p2) not in drift_json
    assert "veh1" not in contract_json
    assert "veh1" not in drift_json

    # 6. Handoff (no auto-import)
    handoff = prepare_handoff_to_manifest(frozen, observation=obs2)
    assert handoff["import_auto_executed"] is False
    assert handoff["source_id"] == "manchester_buses"
    assert "handoff_fingerprint" in handoff


def test_amendment_lineage_integration(tmp_path: Path) -> None:
    contract_v1 = SourceDataContract(
        source_id="src1",
        contract_version="1.0.0",
        fields=[FieldContract(field_name="a", required=True, logical_type=LogicalType.STRING)],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    v1 = create_frozen_version(contract_v1)
    contract_v2 = SourceDataContract(
        source_id="src1",
        contract_version="1.0.1",
        fields=[
            FieldContract(field_name="a", required=True, logical_type=LogicalType.STRING),
            FieldContract(field_name="b", required=False, logical_type=LogicalType.STRING),
        ],
        rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
    )
    v2 = create_new_version_from_parent(v1, contract_v2, amendment_reason="add optional field b")
    assert v2.parent_fingerprint == v1.fingerprint
    assert v2.amendment_reason == "add optional field b"

    # Compare observation against v2 should not flag b as extra if present
    p = tmp_path / "obs.csv"
    _write_csv(p, ["a", "b"], [["1", "2"]])
    obs = inspect_tabular_sample(p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local")
    report = compare_observation_to_contract(v2, obs)
    # b is now expected, so no OPTIONAL_FIELD_ADDED for b
    assert not any(f.field_name == "b" and f.code == "OPTIONAL_FIELD_ADDED" for f in report.findings)

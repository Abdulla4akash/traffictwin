from __future__ import annotations

from pathlib import Path

from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.ingestion.manifest import BundleManifest
from traffictwin.validation.codes import ValidationCode


def test_manifest_model_accepts_valid_baseline() -> None:
    result = validate_bundle(Path("tests/fixtures/bundles/baseline_valid"))

    assert isinstance(result.manifest, BundleManifest)
    assert result.manifest.bundle.bundle_id == "bundle-baseline-001"
    assert result.manifest.files["tasks"].source_column_for("task_id") == "task_id"


def test_manifest_version_rejection() -> None:
    result = validate_bundle(Path("tests/fixtures/bundles/invalid_manifest"))

    assert not result.report.may_import
    assert result.report.findings[0].code is ValidationCode.MANIFEST_SCHEMA_UNSUPPORTED


def test_file_mapping_supports_non_default_source_columns(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "manifest.yaml").write_text(
        """
schema_version: "1.0"
bundle:
  bundle_id: "bundle-mapped-001"
  created_at: "2026-07-17T12:00:00Z"
  source: "synthetic_fixture"
run:
  run_id: "run-mapped-001"
  experiment_id: "exp-gridlock-001"
  seed_id: "s1-gridlock-baseline"
  algorithm: "MAPPO"
  checkpoint: null
  random_seed: 7
  execution_mode: "imported"
  started_at: null
  completed_at: null
environment:
  name: "synthetic"
  version: "1.0"
  commit: null
files:
  traffic_obs:
    path: "traffic.csv"
    schema_version: "1.0"
    required_columns: ["timestamp", "sensor_id"]
    column_map: {timestamp: "t", sensor_id: "sid", average_speed: "speed_kmh"}
    units: {timestamp: "s", average_speed: "km/h"}
provenance: {producer: "TrafficTwin tests", notes: "mapped fixture"}
""",
        encoding="utf-8",
    )
    (bundle / "seed.yaml").write_text(
        Path("tests/fixtures/bundles/baseline_valid/seed.yaml").read_text()
    )
    (bundle / "traffic.csv").write_text("t,sid,speed_kmh\n0,sensor-a,36\n", encoding="utf-8")

    result = validate_bundle(bundle)

    assert result.report.may_import
    assert result.canonical.traffic[0].average_speed_mps == 10.0


def test_unsupported_unit_rejected(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "manifest.yaml").write_text(
        """
schema_version: "1.0"
bundle:
  bundle_id: "bundle-unit-001"
  created_at: "2026-07-17T12:00:00Z"
  source: "synthetic_fixture"
run:
  run_id: "run-unit-001"
  experiment_id: "exp-gridlock-001"
  seed_id: "s1-gridlock-baseline"
  algorithm: "MAPPO"
  checkpoint: null
  random_seed: 7
  execution_mode: "imported"
  started_at: null
  completed_at: null
environment:
  name: "synthetic"
  version: "1.0"
  commit: null
files:
  tasks:
    path: "tasks.csv"
    schema_version: "1.0"
    required_columns:
      - "task_id"
      - "vehicle_id"
      - "task_class"
      - "arrival_time"
      - "deadline_ms"
      - "decision"
      - "completed"
    units: {arrival_time: "seconds", deadline_ms: "ms"}
provenance: {producer: "TrafficTwin tests", notes: "bad unit fixture"}
""",
        encoding="utf-8",
    )
    (bundle / "seed.yaml").write_text(
        Path("tests/fixtures/bundles/baseline_valid/seed.yaml").read_text()
    )
    (bundle / "tasks.csv").write_text(
        "task_id,vehicle_id,task_class,arrival_time,deadline_ms,decision,completed\n"
        "u1,veh-1,T1,0,100,local,true\n",
        encoding="utf-8",
    )

    result = validate_bundle(bundle)
    codes = {finding.code for finding in result.report.findings}

    assert ValidationCode.UNIT_CONVERSION_UNSUPPORTED in codes
    assert not result.report.may_import

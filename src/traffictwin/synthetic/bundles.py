"""Write deterministic synthetic TrafficTwin run bundles."""

from __future__ import annotations

import csv
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yaml

from traffictwin.config.seed_io import write_seed
from traffictwin.domain.energy import DEFAULT_TASK_ENERGY_CONTRACT
from traffictwin.domain.spatial import (
    DEFAULT_SYNTHETIC_SPATIAL_GRID_CONTRACT,
    DEFAULT_TASK_RSU_TARGET_CONTRACT,
)
from traffictwin.ingestion.hashes import sha256_file
from traffictwin.synthetic.config import SYNTHETIC_GENERATOR_VERSION, SyntheticScenarioConfig
from traffictwin.synthetic.generator import SyntheticRunData, generate_run_data
from traffictwin.synthetic.measurement import measurement_bundle_suffix

DETERMINISTIC_CREATED_AT = "2026-07-18T00:00:00Z"

FIELD_ORDER: dict[str, list[str]] = {
    "tasks": [
        "task_id",
        "vehicle_id",
        "task_class",
        "arrival_time",
        "deadline_ms",
        "decision",
        "completed",
        "completion_time",
        "latency_ms",
        "target_id",
        "workload_cycles",
        "data_size_bytes",
        "energy_j",
        "drop_reason",
    ],
    "infra_state": [
        "timestamp",
        "rsu_id",
        "queue_length",
        "utilisation",
        "arrivals",
        "active_tasks",
        "drops",
        "capacity",
    ],
    "vehicle_state": ["timestamp", "vehicle_id", "x", "y", "speed", "lane", "tier"],
    "traffic_obs": ["timestamp", "sensor_id", "count", "average_speed", "location"],
    "trips": ["trip_id", "vehicle_id", "departure_time", "arrival_time", "duration", "route_id"],
    "incidents": [
        "incident_id",
        "timestamp",
        "incident_type",
        "location",
        "severity",
        "duration",
        "lanes_closed",
        "demand_multiplier",
        "vehicles_involved",
    ],
}

REQUIRED_COLUMNS: dict[str, list[str]] = {
    "tasks": [
        "task_id",
        "vehicle_id",
        "task_class",
        "arrival_time",
        "deadline_ms",
        "decision",
        "completed",
        "target_id",
    ],
    "infra_state": ["timestamp", "rsu_id", "queue_length", "utilisation"],
    "vehicle_state": ["timestamp", "vehicle_id", "x", "y"],
    "traffic_obs": ["timestamp", "sensor_id"],
    "trips": ["trip_id", "departure_time"],
    "incidents": ["incident_id", "timestamp", "incident_type"],
}

UNITS: dict[str, dict[str, str]] = {
    "tasks": {
        "arrival_time": "s",
        "completion_time": "s",
        "deadline_ms": "ms",
        "latency_ms": "ms",
        "workload_cycles": "cycles",
        "data_size_bytes": "bytes",
        "energy_j": "J",
    },
    "infra_state": {"timestamp": "s", "utilisation": "fraction"},
    "vehicle_state": {"timestamp": "s", "x": "m", "y": "m", "speed": "m/s"},
    "traffic_obs": {"timestamp": "s", "average_speed": "m/s"},
    "trips": {"departure_time": "s", "arrival_time": "s", "duration": "s"},
    "incidents": {"timestamp": "s", "duration": "s"},
}


def write_synthetic_bundle(
    config: SyntheticScenarioConfig,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Generate and publish one deterministic synthetic run bundle transactionally."""

    destination = _validated_destination(output_dir)
    if destination.exists():
        if not overwrite:
            msg = f"bundle destination already exists: {destination}"
            raise FileExistsError(msg)
        if not destination.is_dir():
            raise ValueError(f"bundle destination is not a directory: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-synthetic-", dir=destination.parent)
    )
    working = temporary_root / "payload"
    working.mkdir()
    try:
        data = generate_run_data(config)
        write_seed(data.seed, working / "seed.yaml")
        for kind, rows in data.rows.items():
            _write_csv(working / f"{kind}.csv", kind, rows)
        manifest = _manifest(data, working)
        (working / "manifest.yaml").write_text(
            yaml.safe_dump(manifest, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        _publish_transactionally(working, destination, temporary_root)
    except Exception:
        shutil.rmtree(temporary_root, ignore_errors=True)
        raise
    shutil.rmtree(temporary_root, ignore_errors=True)
    return destination


def _validated_destination(output_dir: str | Path) -> Path:
    raw = str(output_dir)
    if not raw.strip():
        raise ValueError("synthetic bundle destination must not be empty")
    unresolved = Path(output_dir).expanduser()
    if unresolved.is_symlink():
        raise ValueError(f"synthetic bundle destination must not be a symbolic link: {unresolved}")
    destination = unresolved.resolve(strict=False)
    protected = (Path.cwd().resolve(), Path.home().resolve())
    if any(destination == item or item.is_relative_to(destination) for item in protected):
        raise ValueError(
            "synthetic bundle destination must not be the current directory, home directory, "
            "filesystem root, or one of their ancestors"
        )
    return destination


def _publish_transactionally(working: Path, destination: Path, temporary_root: Path) -> None:
    previous: Path | None = None
    if destination.exists():
        previous = temporary_root / "previous-destination"
        destination.replace(previous)
    try:
        working.replace(destination)
    except Exception:
        if previous is not None and previous.exists() and not destination.exists():
            previous.replace(destination)
        raise


def synthetic_bundle_id(config: SyntheticScenarioConfig) -> str:
    """Return the deterministic bundle ID including any EXP-03 model identity."""

    suffix = measurement_bundle_suffix(config.measurement_imperfections)
    return f"bundle-{config.scenario_id}-{config.random_seed}{suffix}"


def synthetic_run_id(config: SyntheticScenarioConfig) -> str:
    """Return the deterministic run ID including any EXP-03 model identity."""

    suffix = measurement_bundle_suffix(config.measurement_imperfections)
    return f"run-{config.scenario_id}-{config.random_seed}{suffix}"


def _write_csv(path: Path, kind: str, rows: list[dict[str, Any]]) -> None:
    fieldnames = FIELD_ORDER[kind]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def _manifest(data: SyntheticRunData, destination: Path) -> dict[str, Any]:
    config = data.config
    files: dict[str, dict[str, Any]] = {}
    for kind in sorted(data.rows):
        filename = f"{kind}.csv"
        files[kind] = {
            "path": filename,
            "schema_version": "1.0",
            "required_columns": REQUIRED_COLUMNS[kind],
            "column_map": {},
            "units": UNITS[kind],
            "checksum_sha256": sha256_file(destination / filename),
            "required": False,
        }
    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "bundle": {
            "bundle_id": synthetic_bundle_id(config),
            "created_at": DETERMINISTIC_CREATED_AT,
            "source": "synthetic_fixture",
        },
        "run": {
            "run_id": synthetic_run_id(config),
            "experiment_id": config.experiment_id,
            "seed_id": f"seed-{config.scenario_id}",
            "algorithm": config.policy_behavior.value,
            "checkpoint": None,
            "random_seed": config.random_seed,
            "execution_mode": "synthetic",
            "started_at": None,
            "completed_at": None,
        },
        "environment": {
            "name": "synthetic",
            "version": SYNTHETIC_GENERATOR_VERSION,
            "commit": None,
        },
        "energy_contract": DEFAULT_TASK_ENERGY_CONTRACT.model_dump(mode="json"),
        "files": files,
        "provenance": {
            "producer": config.provenance["producer"],
            "notes": (
                f"{config.provenance['notes']} Scenario={config.scenario_id}; "
                f"policy_profile={config.policy_behavior.value}; "
                f"synthetic_faults={','.join(config.synthetic_faults) or 'none'}."
            ),
        },
    }
    if {"tasks", "infra_state"}.issubset(files):
        manifest["task_rsu_target_contract"] = DEFAULT_TASK_RSU_TARGET_CONTRACT.model_dump(
            mode="json"
        )
    if "vehicle_state" in files:
        manifest["vehicle_spatial_grid_contract"] = (
            DEFAULT_SYNTHETIC_SPATIAL_GRID_CONTRACT.model_dump(mode="json")
        )
    if data.measurement_impairment_audit is not None:
        manifest["synthetic_measurement_impairment"] = data.measurement_impairment_audit.model_dump(
            mode="json"
        )
        manifest["provenance"]["notes"] += (
            " EXP-03 synthetic measurement impairment="
            f"{data.measurement_impairment_audit.audit_fingerprint}."
        )
    return manifest


def _csv_value(value: object | None) -> object:
    if value is None:
        return ""
    if isinstance(value, list):
        return "|".join(str(item) for item in value)
    return value

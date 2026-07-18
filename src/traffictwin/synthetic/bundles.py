"""Write deterministic synthetic TrafficTwin run bundles."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Any

import yaml

from traffictwin.config.seed_io import write_seed
from traffictwin.ingestion.hashes import sha256_file
from traffictwin.synthetic.config import SYNTHETIC_GENERATOR_VERSION, SyntheticScenarioConfig
from traffictwin.synthetic.generator import SyntheticRunData, generate_run_data

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
    "incidents": ["incident_id", "timestamp", "incident_type", "location", "severity"],
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
    ],
    "infra_state": ["timestamp", "rsu_id", "queue_length", "utilisation"],
    "vehicle_state": ["timestamp", "vehicle_id"],
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
    "vehicle_state": {"timestamp": "s", "speed": "m/s"},
    "traffic_obs": {"timestamp": "s", "average_speed": "m/s"},
    "trips": {"departure_time": "s", "arrival_time": "s", "duration": "s"},
    "incidents": {"timestamp": "s"},
}


def write_synthetic_bundle(
    config: SyntheticScenarioConfig,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Generate and write one deterministic synthetic run bundle."""

    destination = Path(output_dir)
    if destination.exists():
        if not overwrite:
            msg = f"bundle destination already exists: {destination}"
            raise FileExistsError(msg)
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    data = generate_run_data(config)
    write_seed(data.seed, destination / "seed.yaml")
    for kind, rows in data.rows.items():
        _write_csv(destination / f"{kind}.csv", kind, rows)
    manifest = _manifest(data, destination)
    (destination / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    return destination


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
    return {
        "schema_version": "1.0",
        "bundle": {
            "bundle_id": f"bundle-{config.scenario_id}-{config.random_seed}",
            "created_at": DETERMINISTIC_CREATED_AT,
            "source": "synthetic_fixture",
        },
        "run": {
            "run_id": f"run-{config.scenario_id}-{config.random_seed}",
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


def _csv_value(value: object | None) -> object:
    if value is None:
        return ""
    return value

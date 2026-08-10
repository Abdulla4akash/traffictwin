from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from analyze_e2_native_placement_pilot import SCALAR_PATHS  # noqa: E402
from analyze_e2b_placement_admission_factorial import interaction  # noqa: E402
from run_e2b_placement_admission_factorial import resolve_imported_vec_jax  # noqa: E402
from test_e2_native_placement_pilot import (  # noqa: E402
    manifest as e2_manifest,
    write_valid_run,
)
from validate_e2b_placement_admission_factorial import validate_run  # noqa: E402


def e2b_manifest() -> dict:
    value = e2_manifest()
    value["design"]["backhaul_ms"] = 0.0
    return value


def write_valid_ingress_dla_run(root: Path) -> Path:
    run = write_valid_run(root, rsu_lb="ingress_dla")
    with np.load(run / "per_task.npz", allow_pickle=False) as archive:
        task = {key: archive[key] for key in archive.files}
    task["task_outcome"][0, 1, 0] = 3
    task["task_selected_execution_rsu"][0, 1, 0] = 0
    np.savez_compressed(run / "per_task.npz", **task)

    summary = json.loads((run / "summary.json").read_text())
    summary["v2i_gate_rejected"] = 1.0
    summary["v2i_cap_rejected"] = 0.0
    summary["v2i_path_metrics"].update({
        "selected_target_count_per_rsu": [2, 0],
        "actual_execution_count_per_rsu": [1, 0],
        "ingress_to_execution_pair_matrix": [[1, 0], [0, 0]],
        "execution_share_per_rsu": [1.0, 0.0],
        "maximum_execution_share": 1.0,
        "imbalance_diagnostic": {"value": 1.0},
    })
    (run / "summary.json").write_text(json.dumps(summary))
    return run


def validate(run: Path) -> dict:
    return validate_run(
        run,
        arm={"id": "ingress_dla", "rsu_lb": "ingress_dla"},
        manifest=e2b_manifest(),
        expected_steps=1,
    )


def test_valid_ingress_dla_run_passes_all_path_rules(tmp_path: Path) -> None:
    result = validate(write_valid_ingress_dla_run(tmp_path / "run"))
    assert result["status"] == "passed", [
        check for check in result["checks"] if not check["pass"]
    ]
    assert result["gate_rejection_count_by_ingress_rsu"] == [1, 0]


def test_selected_target_different_from_ingress_fails(tmp_path: Path) -> None:
    run = write_valid_ingress_dla_run(tmp_path / "run")
    with np.load(run / "per_task.npz", allow_pickle=False) as archive:
        task = {key: archive[key] for key in archive.files}
    task["task_selected_execution_rsu"][0, 1, 0] = 1
    np.savez_compressed(run / "per_task.npz", **task)
    result = validate(run)
    assert result["status"] == "failed"
    assert not next(check["pass"] for check in result["checks"]
                    if check["name"] == "ingress_dla_selected_equals_ingress")


def test_forwarding_defect_fails(tmp_path: Path) -> None:
    run = write_valid_ingress_dla_run(tmp_path / "run")
    with np.load(run / "per_task.npz", allow_pickle=False) as archive:
        task = {key: archive[key] for key in archive.files}
    task["task_execution_rsu"][0, 0, 0] = 1
    task["task_forwarded"][0, 0, 0] = True
    np.savez_compressed(run / "per_task.npz", **task)
    result = validate(run)
    assert result["status"] == "failed"
    assert not next(check["pass"] for check in result["checks"]
                    if check["name"] == "ingress_dla_no_forwarding")


def test_gate_rejected_execution_defect_fails(tmp_path: Path) -> None:
    run = write_valid_ingress_dla_run(tmp_path / "run")
    with np.load(run / "per_task.npz", allow_pickle=False) as archive:
        task = {key: archive[key] for key in archive.files}
    task["task_execution_rsu"][0, 1, 0] = 0
    np.savez_compressed(run / "per_task.npz", **task)
    result = validate(run)
    assert result["status"] == "failed"
    assert not next(check["pass"] for check in result["checks"]
                    if check["name"] == "ingress_dla_gate_reject_execution_sentinel")


def test_gate_and_cap_summary_confusion_fails(tmp_path: Path) -> None:
    run = write_valid_ingress_dla_run(tmp_path / "run")
    summary = json.loads((run / "summary.json").read_text())
    summary["v2i_gate_rejected"] = 0.0
    summary["v2i_cap_rejected"] = 1.0
    (run / "summary.json").write_text(json.dumps(summary))
    result = validate(run)
    assert result["status"] == "failed"
    assert not next(check["pass"] for check in result["checks"]
                    if check["name"] == "outcome_3_v2i_gate_rejected")


def scalar_record(value: float) -> dict:
    record: dict = {}
    for path in SCALAR_PATHS.values():
        target = record
        for part in path[:-1]:
            target = target.setdefault(part, {})
        target[path[-1]] = value
    return record


def test_factorial_interaction_uses_declared_signs() -> None:
    records = {
        "off": scalar_record(1.0),
        "jsq": scalar_record(3.0),
        "ingress_dla": scalar_record(4.0),
        "dla": scalar_record(10.0),
    }
    result = interaction(records)
    assert result["formula"] == "DLA - JSQ - ingress_dla + off"
    assert set(result["differences"].values()) == {4.0}


def test_frozen_manifest_is_single_arm_and_sidecar_matches() -> None:
    path = ROOT / "docs/evaluation/e2b/e2b_placement_admission_factorial_manifest_v1.json"
    manifest = json.loads(path.read_text())
    assert [arm["id"] for arm in manifest["arms"]] == ["ingress_dla"]
    assert manifest["limits"]["full_runs"] == 1
    assert manifest["limits"]["additional_arms"] == 0
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert path.with_suffix(".sha256").read_text().split()[0] == digest


def test_runner_resolves_the_actual_production_vec_jax_import() -> None:
    path = ROOT / "docs/evaluation/e2b/e2b_placement_admission_factorial_manifest_v1.json"
    manifest = json.loads(path.read_text())
    resolved = resolve_imported_vec_jax(manifest)
    assert str(resolved) == manifest["paths"]["resolved_imported_vec_jax"]

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from analyze_e2d_per_task_placement_robustness import (  # noqa: E402
    paired_summary,
    substep_mechanism,
)
from run_e2d_per_task_placement_robustness import (  # noqa: E402
    required_free_bytes,
    storage_gate_passes,
    validate_manifest_contract,
    verify_review_gate,
    write_json_new,
)
from validate_e2d_per_task_placement_robustness import (  # noqa: E402
    format_command,
    reference_record,
    sha256,
    verify_reference_record,
)

MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs/evaluation/e2d/e2d_per_task_placement_robustness_manifest_v1.json"
)


def authorised_manifest() -> dict:
    return {
        "full_cell_order": [
            {"cell_index": seed, "fleet_seed": seed, "arm": "per_task_dla"} for seed in (1, 2, 3, 4)
        ],
        "existing_mode_replay_order": [
            {"replay_index": index, "fleet_seed": seed, "arm": arm}
            for index, (seed, arm) in enumerate(
                (
                    (1, "ingress_dla"),
                    (1, "dla"),
                    (2, "ingress_dla"),
                    (2, "dla"),
                    (3, "ingress_dla"),
                    (3, "dla"),
                    (4, "ingress_dla"),
                    (4, "dla"),
                ),
                start=1,
            )
        ],
        "arms": {
            "ingress_dla": {"rsu_lb": "ingress_dla"},
            "dla": {"rsu_lb": "dla"},
            "per_task_dla": {"rsu_lb": "per_task_dla"},
        },
        "command_template": [
            "python",
            "evaluator",
            "--max-steps",
            "{MAX_STEPS}",
            "--fleet-seed",
            "{FLEET_SEED}",
            "--rsu-lb",
            "{ARM}",
            "--rsu-backhaul-ms",
            "0.0",
            "--k8s-scale",
            "off",
            "--out-json",
            "{RUN_DIR}/summary.json",
        ],
    }


def test_primary_negative_direction_label() -> None:
    result = paired_summary([-0.02, -0.021, -0.019, -0.022], primary=True)
    assert (
        result["decision"]
        == "directional_deficit_persists_under_per_task_placement_within_bounded_draws"
    )
    assert result["sign_counts"] == {"negative": 4, "zero": 0, "positive": 0}
    assert result["confidence_interval"]["upper"] < 0.0
    assert result["tasks_used_as_independent_replicates"] is False


def test_primary_direction_mutations_cannot_reuse_negative_label() -> None:
    positive = paired_summary([0.02, 0.021, 0.019, 0.022], primary=True)
    mixed = paired_summary([-0.02, 0.02, -0.01, 0.01], primary=True)
    assert (
        positive["decision"] == "directional_advantage_for_per_task_placement_within_bounded_draws"
    )
    assert mixed["decision"] == "inconclusive_at_this_replication_size"


def test_paired_summary_requires_exactly_four_fleet_draws() -> None:
    with pytest.raises(ValueError, match="exactly four"):
        paired_summary([-0.1, -0.2, -0.3], primary=True)


def test_substep_mechanism_uses_candidate_order_for_switches() -> None:
    task = {
        "task_ingress_rsu": np.asarray([[[0, -1, 0, 0]]], dtype=np.int16),
        "task_selected_execution_rsu": np.asarray([[[0, -1, 1, 0]]], dtype=np.int16),
    }
    result = substep_mechanism(task)
    assert result["total_active_v2i_candidates"] == 3
    assert result["maximum_unique_selected_targets_in_one_substep"] == 2
    assert result["total_target_switches_in_candidate_order"] == 2
    assert result["maximum_candidates_sent_to_one_target_in_one_substep"] == 2


def test_candidate_order_permutation_changes_switch_sensitive_fixture() -> None:
    forward = {
        "task_ingress_rsu": np.asarray([[[0, 0, 0, 0]]], dtype=np.int16),
        "task_selected_execution_rsu": np.asarray([[[0, 0, 1, 1]]], dtype=np.int16),
    }
    permuted = {
        "task_ingress_rsu": forward["task_ingress_rsu"],
        "task_selected_execution_rsu": np.asarray([[[0, 1, 0, 1]]], dtype=np.int16),
    }
    assert substep_mechanism(forward)["total_target_switches_in_candidate_order"] == 1
    assert substep_mechanism(permuted)["total_target_switches_in_candidate_order"] == 3
    assert not np.array_equal(
        forward["task_selected_execution_rsu"],
        permuted["task_selected_execution_rsu"],
    )


def test_manifest_allows_only_four_new_per_task_cells() -> None:
    manifest = authorised_manifest()
    validate_manifest_contract(manifest)
    assert {cell["arm"] for cell in manifest["full_cell_order"]} == {"per_task_dla"}
    assert {cell["fleet_seed"] for cell in manifest["full_cell_order"]} == {1, 2, 3, 4}


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"cell_index": 1, "fleet_seed": 0, "arm": "per_task_dla"}, "full-cell"),
        ({"cell_index": 1, "fleet_seed": 1, "arm": "off"}, "full-cell"),
        ({"cell_index": 1, "fleet_seed": 1, "arm": "dla"}, "full-cell"),
    ],
)
def test_manifest_rejects_seed0_and_prohibited_full_arms(mutation: dict, message: str) -> None:
    manifest = authorised_manifest()
    manifest["full_cell_order"][0] = mutation
    with pytest.raises(RuntimeError, match=message):
        validate_manifest_contract(manifest)


def test_format_command_binds_only_declared_run(tmp_path: Path) -> None:
    manifest = authorised_manifest()
    run = manifest["full_cell_order"][2]
    command = format_command(manifest, run, tmp_path / "run", max_steps=3600)
    assert command[command.index("--rsu-lb") + 1] == "per_task_dla"
    assert command[command.index("--fleet-seed") + 1] == "3"
    assert command[command.index("--max-steps") + 1] == "3600"


def test_storage_ratio_gate_fails_below_twice_projection() -> None:
    projected = 850_000_000
    required = required_free_bytes(projected)
    assert required == 1_700_000_000
    assert storage_gate_passes(required, projected)
    assert not storage_gate_passes(required - 1, projected)


def test_write_json_new_refuses_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    write_json_new(path, {"first": True})
    with pytest.raises(FileExistsError):
        write_json_new(path, {"first": False})
    assert json.loads(path.read_text()) == {"first": True}


def test_review_gate_requires_exact_approve_and_all_three_identities(
    tmp_path: Path,
) -> None:
    review = tmp_path / "review.json"
    identities = {"traffictwin_commit": "t" * 40, "vec_env_commit": "v" * 40}
    review.write_text(
        json.dumps(
            {
                "verdict": "APPROVE",
                "traffictwin_commit": identities["traffictwin_commit"],
                "vec_env_commit": identities["vec_env_commit"],
                "manifest_sha256": "m" * 64,
            }
        )
    )
    assert verify_review_gate(review, identities, "m" * 64)["verdict"] == "APPROVE"
    review.write_text(
        json.dumps(
            {
                "verdict": "APPROVE_WITH_MINOR_FIXES",
                "traffictwin_commit": identities["traffictwin_commit"],
                "vec_env_commit": identities["vec_env_commit"],
                "manifest_sha256": "m" * 64,
            }
        )
    )
    with pytest.raises(RuntimeError, match="APPROVE identity mismatch"):
        verify_review_gate(review, identities, "m" * 64)


def test_reference_hash_verification_detects_mutation(tmp_path: Path) -> None:
    payloads = {
        "summary.json": b"{}\n",
        "per_step.npz": b"step",
        "per_task.npz": b"task",
        "checksums.sha256": b"ledger",
    }
    for name, payload in payloads.items():
        (tmp_path / name).write_bytes(payload)
    import hashlib

    record = {
        "root": str(tmp_path),
        "summary_sha256": hashlib.sha256(payloads["summary.json"]).hexdigest(),
        "per_step_sha256": hashlib.sha256(payloads["per_step.npz"]).hexdigest(),
        "per_task_sha256": hashlib.sha256(payloads["per_task.npz"]).hexdigest(),
        "checksums_sha256": hashlib.sha256(payloads["checksums.sha256"]).hexdigest(),
    }
    assert verify_reference_record(record)["pass"]
    (tmp_path / "per_task.npz").write_bytes(b"changed")
    assert not verify_reference_record(record)["pass"]


def test_decision_record_preserves_construct_and_claim_boundaries() -> None:
    record = (
        Path(__file__).resolve().parents[1]
        / "docs/evaluation/e2d/e2d_per_task_placement_robustness_decision_record_2026-08-11.md"
    ).read_text()
    for phrase in (
        "per-task sequential least-busy",
        "shortest-workload placement",
        "all configured RSUs",
        "lowest RSU index",
        "Individual tasks are never statistical replicates",
        "not confirmed physical task-result return",
        "exact `APPROVE`",
    ):
        assert phrase in record


def test_frozen_manifest_sidecar_and_authorised_inventory() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    sidecar = MANIFEST_PATH.with_suffix(".sha256")
    assert sidecar.read_text().split()[0] == sha256(MANIFEST_PATH)
    validate_manifest_contract(manifest)
    assert manifest["design"]["seed0_authorised"] is False
    assert manifest["analysis"]["task_level_pseudoreplication_allowed"] is False
    assert manifest["review_gate"]["required_verdict"] == "APPROVE"
    assert manifest["compute_and_storage"]["projected_total_evaluator_wall_seconds"] < 108000
    assert (
        manifest["compute_and_storage"]["initial_observed_free_bytes"]
        >= manifest["compute_and_storage"]["minimum_initial_free_bytes"]
    )


def test_all_reused_e2c_reference_hashes_are_bound_and_verify() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    checked = 0
    for seed in (1, 2, 3, 4):
        for arm in ("ingress_dla", "dla"):
            for phase in ("smoke", "full"):
                assert verify_reference_record(reference_record(manifest, seed, arm, phase))["pass"]
                checked += 1
    assert checked == 16


def test_manifest_binds_exact_source_and_input_hashes() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    assert (
        sha256(Path(manifest["paths"]["evaluator"]))
        == manifest["repositories"]["vec_env"]["evaluator_sha256"]
    )
    assert (
        sha256(Path(manifest["paths"]["per_task_placement_helper"]))
        == manifest["repositories"]["vec_env"]["per_task_helper_sha256"]
    )
    assert (
        sha256(Path(manifest["inputs"]["actor"]["path"])) == manifest["inputs"]["actor"]["sha256"]
    )
    assert (
        sha256(Path(manifest["inputs"]["trace"]["path"])) == manifest["inputs"]["trace"]["sha256"]
    )

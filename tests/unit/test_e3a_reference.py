"""Archived controls must remain exact for task decisions and tamper-evident."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


SPEC = importlib.util.spec_from_file_location(
    "e3a_reference", Path(__file__).parents[2]
    / "docs/evaluation/e3a_csf3_2026-09-11/qualification_reference.py"
)
REF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REF)


@pytest.fixture
def archives(tmp_path):
    ref, got = tmp_path / "ref", tmp_path / "got"
    ref.mkdir(); got.mkdir()
    keys = ["model", "T", "maxN", "rsu_max_concurrent", "fleet", "fleet_seed",
            "obs_variant", "lambda_arrival", "rsu_service_mult", "rsu_lb",
            "rsu_backhaul_ms", "k8s_scale", "rsu_cap_mode", "substep_queue",
            "veh_queue_mode", "enter_reset", "reset_soc_on_enter", "fleet_tier_hist",
            "n_offered", "n_admitted", "total_tasks", "completion", "completion_admitted",
            "v2i_gate_rejected", "v2i_cap_rejected", "local_mqd_rejected",
            "v2v_mqd_rejected", "v2i_unavailable", "v2v_unavailable",
            "t1_completion", "t2_completion", "t3_completion", "t1_share", "t2_share", "t3_share"]
    for dest in (ref, got):
        (dest / "summary.json").write_text(json.dumps(dict.fromkeys(keys, 1)))
        (dest / "command.json").write_text("{}")
        np.savez(dest / "per_step.npz", veh_action=np.array([1], np.int8),
                 veh_actor_logits=np.array([0.0], np.float32))
        np.savez(dest / "per_task.npz", task_met=np.array([True]),
                 task_lat_ms=np.array([100.0], np.float32))
    (ref / "validation.json").write_text(json.dumps(dict(status="passed", sha256={
        name: REF.sha(ref / name) for name in ["summary.json", "command.json", "per_step.npz", "per_task.npz"]
    })))
    return ref, got


def test_new_instrumentation_does_not_hide_discrete_drift(archives):
    ref, got = archives
    np.savez(got / "per_task.npz", task_met=np.array([False]),
             task_lat_ms=np.array([100.0], np.float32), extra=np.array([99]))
    result = REF.compare_reference(ref, got)
    assert not result["passed"]
    assert result["failed_fields"][0]["field"] == "task_met"


def test_reference_tamper_is_not_a_new_baseline(archives):
    ref, got = archives
    (ref / "command.json").write_text('{"altered": true}')
    with pytest.raises(ValueError, match="hash changed"):
        REF.compare_reference(ref, got)


def test_missing_inherited_field_cannot_pass(archives):
    ref, got = archives
    np.savez(got / "per_step.npz", veh_action=np.array([1], np.int8))
    with pytest.raises(ValueError, match="Missing inherited"):
        REF.compare_reference(ref, got)


def test_logit_tolerance_and_new_telemetry(archives):
    ref, got = archives
    np.savez(got / "per_step.npz", veh_action=np.array([1], np.int8),
             veh_actor_logits=np.array([9e-6], np.float32), extra=np.array([42]))
    assert REF.compare_reference(ref, got)["passed"]
    np.savez(got / "per_step.npz", veh_action=np.array([1], np.int8),
             veh_actor_logits=np.array([1.1e-5], np.float32))
    assert not REF.compare_reference(ref, got)["passed"]


def cpu_receipts(archives):
    for index, directory in enumerate(archives):
        runtime = dict(python="3.11.15", packages={"jax": "0.4.30"}, machine="x86_64",
                       environment={"OMP_NUM_THREADS": "4"}, cpu_affinity=list(range(4)),
                       cpu_model="AMD" if index == 0 else "Intel")
        (directory / "RUNTIME.json").write_text(json.dumps(runtime))
        config = dict(arm="p2c_dla", steps=10, fleet_seed=1, evaluator_seed=0,
                      n_vehicles=2488, n_rsus=10, enter_reset=False, inputs={"trace": "sealed"},
                      command=["python", "evaluator.py", "--seed", "0", "--out-json", str(directory / "summary.json")])
        (directory / "COMMAND.json").write_text(json.dumps(config))
        receipt = dict(status="passed", configuration=config, source_commit="a" * 40,
                       seal_sha256="b" * 64, shared_input_hashes={"tasks": "c" * 64},
                       runtime_sha256=REF.sha(directory / "RUNTIME.json"),
                       offered=1, admitted=1, successes=1, terminal_failures=0,
                       forwarded=0, outcome_counts=[0, 1], type_counts=[1],
                       output_sha256={name: REF.sha(directory / name)
                                      for name in ["summary.json", "per_step.npz", "per_task.npz"]})
        (directory / "VALIDATED.json").write_text(json.dumps(receipt))


def test_cpu_smoke_cannot_accept_other_valid_sampled_pair(archives):
    ref, got = archives
    for directory, pair in [(ref, [1, 4]), (got, [2, 4])]:
        np.savez(directory / "per_task.npz", task_p2c_sampled_pair=np.array([pair], np.int16))
    cpu_receipts(archives)
    result = REF.compare_cross_cpu(ref, got)
    assert not result["passed"]
    assert result["failed_fields"][0]["field"] == "task_p2c_sampled_pair"


def test_cpu_smoke_accepts_cpu_change_but_rejects_thread_change(archives):
    ref, got = archives
    cpu_receipts(archives)
    assert REF.compare_cross_cpu(ref, got)["passed"]
    runtime = json.loads((got / "RUNTIME.json").read_text())
    runtime["environment"]["OMP_NUM_THREADS"] = "8"
    (got / "RUNTIME.json").write_text(json.dumps(runtime))
    receipt = json.loads((got / "VALIDATED.json").read_text())
    receipt["runtime_sha256"] = REF.sha(got / "RUNTIME.json")
    (got / "VALIDATED.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="thread environment differs"):
        REF.compare_cross_cpu(ref, got)

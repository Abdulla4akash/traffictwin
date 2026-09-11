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

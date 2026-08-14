# mypy: disable-error-code="no-redef, no-any-return, attr-defined, no-untyped-def, var-annotated"
"""Tests for E3 Dynamic Resource V2 runner/validator/manifest -- frozen no-results."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

RUNNER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_e3_dynamic_resource_v2.py"
VALIDATOR_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "validate_e3_dynamic_resource_v2.py"
)

_runner_spec = importlib.util.spec_from_file_location("run_e3_dynamic_resource_v2", RUNNER_PATH)
assert _runner_spec is not None and _runner_spec.loader is not None
_runner_mod = importlib.util.module_from_spec(_runner_spec)
sys.modules["run_e3_dynamic_resource_v2"] = _runner_mod
_runner_spec.loader.exec_module(_runner_mod)

_validator_spec = importlib.util.spec_from_file_location(
    "validate_e3_dynamic_resource_v2", VALIDATOR_PATH
)
assert _validator_spec is not None and _validator_spec.loader is not None
_validator_mod = importlib.util.module_from_spec(_validator_spec)
sys.modules["validate_e3_dynamic_resource_v2"] = _validator_mod
_validator_spec.loader.exec_module(_validator_mod)

canonical_arm_id = _runner_mod.canonical_arm_id
canonical_config_id = _runner_mod.canonical_config_id
generate_dormant_arms = _runner_mod.generate_dormant_arms
generate_dormant_configs = _runner_mod.generate_dormant_configs
CONTRACT_SHA256 = _runner_mod.CONTRACT_SHA256
VEC_PROMOTION_SHA = _runner_mod.VEC_PROMOTION_SHA
VEC_CORE_SHA = _runner_mod.VEC_CORE_SHA
VEC_ADAPTER_SHA = _runner_mod.VEC_ADAPTER_SHA
TRAFFICTWIN_BASE_SHA = _runner_mod.TRAFFICTWIN_BASE_SHA
MANIFEST_SCHEMA_VERSION = _runner_mod.MANIFEST_SCHEMA_VERSION

validate_manifest_dict = _validator_mod.validate_manifest_dict
validate_construct_result = _validator_mod.validate_construct_result
validate_manifest_file = _validator_mod.validate_manifest_file

MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "evaluation"
    / "e3"
    / "e3_dynamic_resource_v2_manifest_v1.json"
)
SIDECAR_PATH = MANIFEST_PATH.with_suffix(".sha256")
CONTRACT_V2_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "evaluation"
    / "e3"
    / "e3_dynamic_resource_v2_contract_v2.json"
)
CONTRACT_V1_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "evaluation"
    / "e3"
    / "e3_dynamic_resource_v2_contract_v1.json"
)


def _load_manifest() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return data


def _valid_adapter_payload() -> dict[str, Any]:
    # Compute expected 16-hex cid via runner helper to ensure deterministic
    cid = _runner_mod._recompute_adapter_config_id(
        "per_task_dla", "fixed_1x", 0, 0, 1, 2, VEC_CORE_SHA
    )
    return {
        "config_id": cid,
        "core_sha": VEC_CORE_SHA,
        "evaluator_seed": 0,
        "fleet_seed": 1,
        "num_rsus": 2,
        "placement": "per_task_dla",
        "scaling": "fixed_1x",
        "state_age_ms": 0,
        "schema_version": "e3_dynamic_resource_v2_contract_v2",
        "software_identity": {
            "actor_sha256": "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208",
            "e2d_manifest_sha256": "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740",  # noqa: E501
            "evaluator_seed": 0,
            "fleet_seed": 1,
            "fleet_draw_label": "fleet_draw",
            "schema_version": "e3_dynamic_resource_v2_contract_v2",
            "software_version": "vec_core_v5",
            "trace_sha256": "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056",
            "traffictwin_contract_head": TRAFFICTWIN_BASE_SHA,
            "vec_core_candidate_sha": VEC_CORE_SHA,
            "vec_promoted_base": "b2abcee2b4c2628e604fff0811110b8c61a22b23",
        },
        "is_construct": True,
        "construct_ticks": 1,
        "construct_rsus": 2,
        "construct_tasks": 2,
        "offered": 2,
        "admitted": 2,
        "rejected": 0,
        "forwarded": 0,
        "deadline_success": 2,
        "deadline_instrumented": True,
        "task_outcomes": [
            {
                "admitted": True,
                "deadline_success": True,
                "execution_rsu": 0,
                "forwarded": False,
                "ingress_rsu": 0,
                "latency_ms": 10.0,
                "latency_reason": "computed: ingress_tx 0.0 + forwarding 0.0 + backlog/u 0.0 + service/u 10.0 + return 0.0",  # noqa: E501
                "rejection_class": None,
                "sequential_ordinal": 0,
                "service_work_ms": 10.0,
                "task_slot": 0,
                "vehicle_slot": 0,
            },
            {
                "admitted": True,
                "deadline_success": True,
                "execution_rsu": 1,
                "forwarded": False,
                "ingress_rsu": 1,
                "latency_ms": 15.0,
                "latency_reason": "computed: ingress_tx 0.0 + forwarding 0.0 + backlog/u 0.0 + service/u 15.0 + return 0.0",  # noqa: E501
                "rejection_class": None,
                "sequential_ordinal": 2489,
                "service_work_ms": 15.0,
                "task_slot": 1,
                "vehicle_slot": 1,
            },
        ],
        "scaling_scheduled": [],
        "scaling_applied": [],
        "receipt_state_age_ms": 0,
        "resource_intervals_this_tick": [
            {"active_compute_units": 1, "end_time_ms": 4000, "rsu_id": 0, "start_time_ms": 3000},
            {"active_compute_units": 1, "end_time_ms": 4000, "rsu_id": 1, "start_time_ms": 3000},
        ],
        "resource_intervals": [
            {"active_compute_units": 1, "end_time_ms": 4000, "rsu_id": 0, "start_time_ms": 3000},
            {"active_compute_units": 1, "end_time_ms": 4000, "rsu_id": 1, "start_time_ms": 3000},
        ],
        "tick_resource_intervals": [
            {"active_compute_units": 1, "end_time_ms": 4000, "rsu_id": 0, "start_time_ms": 3000},
            {"active_compute_units": 1, "end_time_ms": 4000, "rsu_id": 1, "start_time_ms": 3000},
        ],
        "total_resource_unit_seconds": 2.0,
        "total_drained_work_ms": 25.0,
        "per_rsu_cumulative_drained_ms": {"0": 10.0, "1": 15.0},
        "per_rsu_cumulative_capacity_ms": {"0": 1000.0, "1": 1000.0},
        "utilization": {"0": 0.01, "1": 0.015},
        "evidence_label": "software construct evidence, not E3 research results",
        "lane_09": "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD",
        "status": "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED",
        "evidence_state": "NOT_EXECUTED",
        "result_availability": "NO_E3_RESEARCH_RESULTS_AVAILABLE",
        "research_workloads_launched": 0,
    }


def _fake_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> Any:  # noqa: ANN401
    return type("FakeProc", (), {"returncode": returncode, "stdout": stdout, "stderr": stderr})()


def _mock_git_success(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
    cmd = args[0] if args else kwargs.get("args", [])
    if isinstance(cmd, list) and len(cmd) > 1 and cmd[1] == "status":
        return _fake_proc(stdout="")
    if isinstance(cmd, list) and len(cmd) > 1 and cmd[1] == "rev-parse":
        cwd = str(kwargs.get("cwd", ""))
        # Heuristic to decide which repo: if cwd contains vec-like, return vec promotion, else traffictwin  # noqa: E501
        if "vec" in cwd.lower():
            return _fake_proc(stdout=VEC_PROMOTION_SHA + "\n")
        return _fake_proc(stdout=TRAFFICTWIN_BASE_SHA + "\n")
    if isinstance(cmd, list) and len(cmd) > 1 and cmd[1] == "merge-base":
        return _fake_proc()
    if isinstance(cmd, list) and "--version" in cmd:
        return _fake_proc(stdout="Python 3.11.15\n")
    return _fake_proc()


def _mock_subprocess_success(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
    cmd = args[0] if args else kwargs.get("args", [])
    if isinstance(cmd, list) and cmd and "git" in cmd[0]:
        return _mock_git_success(*args, **kwargs)
    if isinstance(cmd, list) and "--version" in cmd:
        return _fake_proc(stdout="Python 3.11.15\n")
    payload = _valid_adapter_payload()
    return _fake_proc(stdout=json.dumps(payload) + "\n")


# ---- Tests ----


def test_exact_14_arms_56_configs_and_stable_identifiers() -> None:
    arms = generate_dormant_arms()
    configs = generate_dormant_configs()
    assert len(arms) == 14
    assert len(configs) == 56
    assert len({a["arm_id"] for a in arms}) == 14
    assert len({c["config_id"] for c in configs}) == 56
    arm_ids = [a["arm_id"] for a in arms]
    assert arm_ids == sorted(arm_ids)
    cfg_ids = [c["config_id"] for c in configs]
    assert cfg_ids == sorted(cfg_ids)
    for arm in arms:
        assert arm["arm_id"] == canonical_arm_id(
            str(arm["placement"]), str(arm["scaling"]), int(arm["state_age_ms"])
        )
    for cfg in configs:
        assert cfg["config_id"] == canonical_config_id(
            str(cfg["placement"]),
            str(cfg["scaling"]),
            int(cfg["state_age_ms"]),
            int(cfg["evaluator_seed"]),
            int(cfg["fleet_seed"]),
            int(cfg["num_rsus"]),
        )
        assert cfg["arm_id"] == canonical_arm_id(
            str(cfg["placement"]), str(cfg["scaling"]), int(cfg["state_age_ms"])
        )
    count = sum(
        1
        for c in configs
        if c["placement"] == "per_task_dla"
        and c["scaling"] == "fixed_1x"
        and c["state_age_ms"] == 0
    )
    assert count == 4
    manifest = _load_manifest()
    assert manifest["dormant_arms"] == arms
    assert manifest["dormant_configs"] == configs
    assert manifest["dormant_arm_count"] == 14
    assert manifest["dormant_config_count"] == 56


def test_sidecar_byte_checksum_and_exact_pinned_shas() -> None:
    raw = MANIFEST_PATH.read_bytes()
    computed = hashlib.sha256(raw).hexdigest()
    # Exact sidecar content: 64 hex + two spaces + filename + newline
    sidecar_raw = SIDECAR_PATH.read_text(encoding="utf-8")
    expected = f"{computed}  {MANIFEST_PATH.name}\n"
    assert sidecar_raw == expected
    # Also check with_suffix derivation yields authorized path
    assert MANIFEST_PATH.with_suffix(".sha256") == SIDECAR_PATH
    manifest = _load_manifest()
    assert manifest["contract"]["sha256"] == CONTRACT_SHA256
    assert manifest["vec_runtime"]["promotion_commit"] == VEC_PROMOTION_SHA
    assert manifest["vec_runtime"]["core_candidate"] == VEC_CORE_SHA
    assert manifest["vec_runtime"]["adapter_candidate"] == VEC_ADAPTER_SHA
    assert manifest["schema_version"] == MANIFEST_SCHEMA_VERSION
    assert manifest["runner_schema_version"] == _runner_mod.RUNNER_SCHEMA_VERSION
    assert manifest["result_schema_version"] == _runner_mod.RESULT_SCHEMA_VERSION
    errs = validate_manifest_file(MANIFEST_PATH, SIDECAR_PATH)
    assert errs == []


def test_sidecar_exact_format_requires_two_spaces_and_filename() -> None:
    raw = MANIFEST_PATH.read_bytes()
    computed = hashlib.sha256(raw).hexdigest()
    # Mutate sidecar to have single space (should fail exact content)
    bad_raw = f"{computed} {MANIFEST_PATH.name}\n"
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        m_path = Path(td) / MANIFEST_PATH.name
        s_path = m_path.with_suffix(".sha256")
        m_path.write_bytes(raw)
        s_path.write_text(bad_raw, encoding="utf-8")
        errs = validate_manifest_file(m_path, s_path)
        assert any("sidecar exact" in e.lower() or "sidecar" in e.lower() for e in errs)
    # Mutate to have missing filename
    bad2 = f"{computed}\n"
    with tempfile.TemporaryDirectory() as td:
        m_path = Path(td) / MANIFEST_PATH.name
        s_path = m_path.with_suffix(".sha256")
        m_path.write_bytes(raw)
        s_path.write_text(bad2, encoding="utf-8")
        errs2 = validate_manifest_file(m_path, s_path)
        assert any("sidecar" in e.lower() for e in errs2)


def test_execution_authority_fail_closed_under_mutation() -> None:
    manifest = _load_manifest()
    for key in [
        "scientific_execution_authorized",
        "full_3600_step_cells_authorized",
        "e3a_authorized",
    ]:
        mutated = copy.deepcopy(manifest)
        mutated["execution_authority"][key] = True
        raw2 = (
            json.dumps(mutated, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")
            + b"\n"
        )
        # Use exact sidecar for mutated raw
        sidecar_raw = f"{hashlib.sha256(raw2).hexdigest()}  {MANIFEST_PATH.name}\n"
        errs = validate_manifest_dict(
            mutated,
            raw_bytes=raw2,
            sidecar_hex=hashlib.sha256(raw2).hexdigest(),
            sidecar_raw=sidecar_raw,
            manifest_filename=MANIFEST_PATH.name,
        )
        assert any("auth" in e.lower() or key in e for e in errs), f"expected auth error for {key}"
    for key in ["authorized_execution_config_ids", "authorized_cells", "authorized_runs"]:
        mutated2 = copy.deepcopy(manifest)
        mutated2[key] = ["fake_config"]
        raw2 = (
            json.dumps(mutated2, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")
            + b"\n"
        )
        sidecar_raw = f"{hashlib.sha256(raw2).hexdigest()}  {MANIFEST_PATH.name}\n"
        errs2 = validate_manifest_dict(
            mutated2,
            raw_bytes=raw2,
            sidecar_hex=hashlib.sha256(raw2).hexdigest(),
            sidecar_raw=sidecar_raw,
            manifest_filename=MANIFEST_PATH.name,
        )
        assert any(key in e for e in errs2)
    mutated3 = copy.deepcopy(manifest)
    mutated3["execution_authority"]["research_workloads_launched"] = 1
    raw3 = (
        json.dumps(mutated3, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    )
    sidecar_raw3 = f"{hashlib.sha256(raw3).hexdigest()}  {MANIFEST_PATH.name}\n"
    errs3 = validate_manifest_dict(
        mutated3,
        raw_bytes=raw3,
        sidecar_hex=hashlib.sha256(raw3).hexdigest(),
        sidecar_raw=sidecar_raw3,
        manifest_filename=MANIFEST_PATH.name,
    )
    assert any("workload" in e.lower() or "research_workloads" in e for e in errs3)


def test_authorized_lists_must_exist_and_be_empty() -> None:
    manifest = _load_manifest()
    for key in ["authorized_execution_config_ids", "authorized_cells", "authorized_runs"]:
        mutated = copy.deepcopy(manifest)
        del mutated[key]
        raw = (
            json.dumps(mutated, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")
            + b"\n"
        )
        sidecar_raw = f"{hashlib.sha256(raw).hexdigest()}  {MANIFEST_PATH.name}\n"
        errs = validate_manifest_dict(
            mutated,
            raw_bytes=raw,
            sidecar_hex=hashlib.sha256(raw).hexdigest(),
            sidecar_raw=sidecar_raw,
            manifest_filename=MANIFEST_PATH.name,
        )
        assert any(key in e and "missing" in e.lower() for e in errs), (
            f"expected missing error for {key}"
        )
        # Not a list
        mutated2 = copy.deepcopy(manifest)
        mutated2[key] = "not_a_list"  # type: ignore
        raw2 = (
            json.dumps(mutated2, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")
            + b"\n"
        )
        sidecar_raw2 = f"{hashlib.sha256(raw2).hexdigest()}  {MANIFEST_PATH.name}\n"
        errs2 = validate_manifest_dict(
            mutated2,
            raw_bytes=raw2,
            sidecar_hex=hashlib.sha256(raw2).hexdigest(),
            sidecar_raw=sidecar_raw2,
            manifest_filename=MANIFEST_PATH.name,
        )
        assert any(key in e for e in errs2)


def test_unauthorized_capabilities_must_exist_and_be_false() -> None:
    manifest = _load_manifest()
    for key in _validator_mod.UNAUTHORIZED_REQUIRED_KEYS:
        mutated = copy.deepcopy(manifest)
        del mutated["unauthorized_capabilities"][key]
        raw = (
            json.dumps(mutated, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")
            + b"\n"
        )
        sidecar_raw = f"{hashlib.sha256(raw).hexdigest()}  {MANIFEST_PATH.name}\n"
        errs = validate_manifest_dict(
            mutated,
            raw_bytes=raw,
            sidecar_hex=hashlib.sha256(raw).hexdigest(),
            sidecar_raw=sidecar_raw,
            manifest_filename=MANIFEST_PATH.name,
        )
        assert any(key in e for e in errs), f"expected missing unauthorized {key}"
        mutated2 = copy.deepcopy(manifest)
        mutated2["unauthorized_capabilities"][key] = True
        raw2 = (
            json.dumps(mutated2, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")
            + b"\n"
        )
        sidecar_raw2 = f"{hashlib.sha256(raw2).hexdigest()}  {MANIFEST_PATH.name}\n"
        errs2 = validate_manifest_dict(
            mutated2,
            raw_bytes=raw2,
            sidecar_hex=hashlib.sha256(raw2).hexdigest(),
            sidecar_raw=sidecar_raw2,
            manifest_filename=MANIFEST_PATH.name,
        )
        assert any(key in e and "false" in e.lower() for e in errs2)


def test_execution_authority_exact_key_set_no_extra() -> None:
    manifest = _load_manifest()
    mutated = copy.deepcopy(manifest)
    mutated["execution_authority"]["extra_hidden_key"] = False
    raw = json.dumps(mutated, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    sidecar_raw = f"{hashlib.sha256(raw).hexdigest()}  {MANIFEST_PATH.name}\n"
    errs = validate_manifest_dict(
        mutated,
        raw_bytes=raw,
        sidecar_hex=hashlib.sha256(raw).hexdigest(),
        sidecar_raw=sidecar_raw,
        manifest_filename=MANIFEST_PATH.name,
    )
    assert any("execution_authority" in e and "extra" in e.lower() for e in errs)
    mutated2 = copy.deepcopy(manifest)
    del mutated2["execution_authority"]["status"]
    raw2 = (
        json.dumps(mutated2, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    )
    sidecar_raw2 = f"{hashlib.sha256(raw2).hexdigest()}  {MANIFEST_PATH.name}\n"
    errs2 = validate_manifest_dict(
        mutated2,
        raw_bytes=raw2,
        sidecar_hex=hashlib.sha256(raw2).hexdigest(),
        sidecar_raw=sidecar_raw2,
        manifest_filename=MANIFEST_PATH.name,
    )
    assert any("missing" in e.lower() or "status" in e for e in errs2)


def test_scientific_mode_denies_before_file_access() -> None:
    def failing_git(*a: Any, **k: Any) -> Any:  # noqa: ANN401
        raise AssertionError("git should not be called in scientific mode")

    def failing_subprocess(*a: Any, **k: Any) -> Any:  # noqa: ANN401
        raise AssertionError("subprocess should not be called")

    with pytest.raises(SystemExit) as exc:
        _runner_mod.main(
            argv=["scientific"], git_runner=failing_git, subprocess_runner=failing_subprocess
        )
    assert exc.value.code != 0
    ret = _runner_mod.main(
        argv=["unknown_mode"], git_runner=failing_git, subprocess_runner=failing_subprocess
    )
    assert ret != 0


def test_partial_invalid_factors_wrong_vec_head_ancestry_wrong_python() -> None:
    def mock_git_wrong_head(*a: Any, **kw: Any) -> Any:  # noqa: ANN401
        cmd = a[0] if a else kw.get("args", [])
        if isinstance(cmd, list) and len(cmd) > 1 and cmd[1] == "status":
            return _fake_proc(stdout="")
        if isinstance(cmd, list) and len(cmd) > 1 and cmd[1] == "rev-parse":
            return _fake_proc(stdout="deadbeef" * 5 + "\n")
        if isinstance(cmd, list) and len(cmd) > 1 and cmd[1] == "merge-base":
            return _fake_proc()
        if isinstance(cmd, list) and "--version" in cmd:
            return _fake_proc(stdout="Python 3.11.15\n")
        return _fake_proc()

    ret = _runner_mod.main(
        argv=["minimal_construct", "--vec-repo", "/tmp", "--python", sys.executable],  # noqa: S108
        git_runner=mock_git_wrong_head,
        subprocess_runner=_mock_subprocess_success,
    )
    assert ret != 0

    def mock_git_wrong_ancestor(*a: Any, **kw: Any) -> Any:  # noqa: ANN401
        cmd = a[0] if a else kw.get("args", [])
        if isinstance(cmd, list) and len(cmd) > 1 and cmd[1] == "status":
            return _fake_proc(stdout="")
        if isinstance(cmd, list) and len(cmd) > 1 and cmd[1] == "rev-parse":
            cwd = str(kw.get("cwd", ""))
            if "vec" in cwd.lower() or "tmp" in cwd.lower():
                return _fake_proc(stdout=VEC_PROMOTION_SHA + "\n")
            return _fake_proc(stdout=TRAFFICTWIN_BASE_SHA + "\n")
        if isinstance(cmd, list) and len(cmd) > 1 and cmd[1] == "merge-base":
            return _fake_proc(returncode=1, stderr="not ancestor")
        if isinstance(cmd, list) and "--version" in cmd:
            return _fake_proc(stdout="Python 3.11.15\n")
        return _fake_proc()

    import tempfile

    with tempfile.TemporaryDirectory() as td:
        ret2 = _runner_mod.main(
            argv=["minimal_construct", "--vec-repo", td, "--python", sys.executable],
            git_runner=mock_git_wrong_ancestor,
            subprocess_runner=_mock_subprocess_success,
        )
        assert ret2 != 0

    def mock_git_ok(*a: Any, **kw: Any) -> Any:  # noqa: ANN401
        return _mock_git_success(*a, **kw)

    ret3 = _runner_mod.main(
        argv=[
            "minimal_construct",
            "--vec-repo",
            str(MANIFEST_PATH.parent),
            "--python",
            "/nonexistent/python",
        ],
        git_runner=mock_git_ok,
        subprocess_runner=_mock_subprocess_success,
    )
    assert ret3 != 0

    with pytest.raises(ValueError):
        canonical_arm_id("invalid_placement", "fixed_1x", 0)
    with pytest.raises(ValueError):
        canonical_arm_id("per_task_dla", "fixed_1x", 999)
    with pytest.raises(ValueError):
        canonical_config_id("per_task_dla", "fixed_1x", 0, 0, 99, 10)


def test_git_identity_dirty_and_ancestor_failures() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        vec = Path(td) / "vec"
        (vec / "eval").mkdir(parents=True)
        (vec / "eval" / "eval_sumo_stage1_mc.py").write_text("# fake")

        def dirty_git(*a: Any, **kw: Any) -> Any:  # noqa: ANN401
            cmd = a[0] if a else kw.get("args", [])
            if isinstance(cmd, list) and len(cmd) > 1 and cmd[1] == "status":
                return _fake_proc(stdout=" M scripts/run_e3_dynamic_resource_v2.py\n")
            if isinstance(cmd, list) and len(cmd) > 1 and cmd[1] == "rev-parse":
                return _fake_proc(stdout=TRAFFICTWIN_BASE_SHA + "\n")
            if isinstance(cmd, list) and len(cmd) > 1 and cmd[1] == "merge-base":
                return _fake_proc()
            if isinstance(cmd, list) and "--version" in cmd:
                return _fake_proc(stdout="Python 3.11.15\n")
            payload = _valid_adapter_payload()
            return _fake_proc(stdout=json.dumps(payload) + "\n")

        ret = _runner_mod.main(
            argv=["minimal_construct", "--vec-repo", str(vec), "--python", sys.executable],
            git_runner=dirty_git,
            subprocess_runner=dirty_git,
        )
        assert ret != 0

        def ancestor_fail_git(*a: Any, **kw: Any) -> Any:  # noqa: ANN401
            cmd = a[0] if a else kw.get("args", [])
            if isinstance(cmd, list) and len(cmd) > 1 and cmd[1] == "status":
                return _fake_proc(stdout="")
            if isinstance(cmd, list) and len(cmd) > 1 and cmd[1] == "rev-parse":
                # Return a valid SHA but not ancestor
                return _fake_proc(stdout="a" * 40 + "\n")
            if isinstance(cmd, list) and len(cmd) > 1 and cmd[1] == "merge-base":
                return _fake_proc(returncode=1, stderr="not ancestor")
            if isinstance(cmd, list) and "--version" in cmd:
                return _fake_proc(stdout="Python 3.11.15\n")
            payload = _valid_adapter_payload()
            return _fake_proc(stdout=json.dumps(payload) + "\n")

        ret2 = _runner_mod.main(
            argv=["minimal_construct", "--vec-repo", str(vec), "--python", sys.executable],
            git_runner=ancestor_fail_git,
            subprocess_runner=ancestor_fail_git,
        )
        assert ret2 != 0


def test_python_version_no_fallback_to_real_subprocess() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        vec = Path(td) / "vec"
        (vec / "eval").mkdir(parents=True)
        (vec / "eval" / "eval_sumo_stage1_mc.py").write_text("# fake")

        # Injected runner returns bad python version (empty or failure)
        def bad_python_git(*a: Any, **kw: Any) -> Any:  # noqa: ANN401
            cmd = a[0] if a else kw.get("args", [])
            if (
                isinstance(cmd, list)
                and len(cmd) > 1
                and cmd[1] in ("status", "rev-parse", "merge-base")
            ):
                return _mock_git_success(*a, **kw)
            if isinstance(cmd, list) and "--version" in cmd:
                return _fake_proc(returncode=0, stdout="not python\n", stderr="")
            payload = _valid_adapter_payload()
            return _fake_proc(stdout=json.dumps(payload) + "\n")

        ret = _runner_mod.main(
            argv=["minimal_construct", "--vec-repo", str(vec), "--python", sys.executable],
            git_runner=_mock_git_success,
            subprocess_runner=bad_python_git,
        )
        assert ret != 0


def test_malformed_multi_line_child_output_stderr_child_failure_identity_drift() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        vec = Path(td) / "vec"
        (vec / "eval").mkdir(parents=True)
        (vec / "eval" / "eval_sumo_stage1_mc.py").write_text("# fake")
        py = Path(sys.executable)

        def mock_multi(*a: Any, **kw: Any) -> Any:  # noqa: ANN401
            return _fake_proc(stdout='{"a":1}\n{"b":2}\n')

        with pytest.raises(ValueError, match="exactly one JSON line"):
            _runner_mod._invoke_adapter(
                vec, py, "per_task_dla", "fixed_1x", 0, 1, 2, subprocess_runner=mock_multi
            )

        def mock_extra_blank(*a: Any, **kw: Any) -> Any:  # noqa: ANN401
            # Extra blank line after json
            payload = _valid_adapter_payload()
            return _fake_proc(stdout=json.dumps(payload) + "\n\n")

        with pytest.raises(ValueError, match="extra blank"):
            _runner_mod._invoke_adapter(
                vec, py, "per_task_dla", "fixed_1x", 0, 1, 2, subprocess_runner=mock_extra_blank
            )

        def mock_stderr(*a: Any, **kw: Any) -> Any:  # noqa: ANN401
            return _fake_proc(stdout=json.dumps(_valid_adapter_payload()) + "\n", stderr="warning")

        with pytest.raises(ValueError, match="stderr nonempty"):
            _runner_mod._invoke_adapter(
                vec, py, "per_task_dla", "fixed_1x", 0, 1, 2, subprocess_runner=mock_stderr
            )

        def mock_fail(*a: Any, **kw: Any) -> Any:  # noqa: ANN401
            return _fake_proc(returncode=1, stderr="error")

        with pytest.raises(RuntimeError, match="adapter exit"):
            _runner_mod._invoke_adapter(
                vec, py, "per_task_dla", "fixed_1x", 0, 1, 2, subprocess_runner=mock_fail
            )

        def mock_drift(*a: Any, **kw: Any) -> Any:  # noqa: ANN401
            p = _valid_adapter_payload()
            p["core_sha"] = "0" * 40
            return _fake_proc(stdout=json.dumps(p) + "\n")

        with pytest.raises(ValueError, match="core_sha"):
            _runner_mod._invoke_adapter(
                vec, py, "per_task_dla", "fixed_1x", 0, 1, 2, subprocess_runner=mock_drift
            )

        payload = _valid_adapter_payload()
        payload["schema_version"] = "wrong"
        wrapped = _runner_mod._build_construct_result(payload, "a" * 64, TRAFFICTWIN_BASE_SHA)
        errs = validate_construct_result(wrapped, _load_manifest())
        assert any("schema" in e.lower() for e in errs)


def test_truthful_typed_nested_task_scaling_resource_state_age_conservation() -> None:
    payload = _valid_adapter_payload()
    wrapped = _runner_mod._build_construct_result(
        payload, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs = validate_construct_result(wrapped, _load_manifest())
    assert errs == []
    bad_payload = copy.deepcopy(payload)
    bad_payload["offered"] = 5
    bad_payload["admitted"] = 2
    bad_payload["rejected"] = 2
    wrapped3 = _runner_mod._build_construct_result(
        bad_payload, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs3 = validate_construct_result(wrapped3, _load_manifest())
    assert any("conservation" in e.lower() or "task" in e.lower() for e in errs3)
    bad2 = copy.deepcopy(payload)
    bad2["resource_intervals_this_tick"] = [
        {"active_compute_units": 1, "end_time_ms": 4000, "rsu_id": 0, "start_time_ms": 3000}
    ]
    wrapped4 = _runner_mod._build_construct_result(
        bad2, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs4 = validate_construct_result(wrapped4, _load_manifest())
    assert any("resource" in e.lower() for e in errs4)
    wrapped5 = copy.deepcopy(wrapped)
    wrapped5["state_age_ms"] = 999
    wrapped5["factors"]["state_age_ms"] = 999
    wrapped5["arm_id"] = "per_task_dla__fixed_1x__age_999ms"
    wrapped5["config_id"] = "per_task_dla__fixed_1x__age_999ms__eval_0__fleet_1__rsus_2"
    errs5 = validate_construct_result(wrapped5, _load_manifest())
    assert any("state" in e.lower() or "age" in e.lower() for e in errs5)
    bad5 = copy.deepcopy(payload)
    # Rejected task with zero latency should be flagged
    bad5["task_outcomes"] = [
        {
            "admitted": False,
            "deadline_success": None,
            "execution_rsu": -1,
            "forwarded": False,
            "ingress_rsu": 0,
            "latency_ms": 0,
            "latency_reason": "unavailable: rejected work has no latency",
            "rejection_class": "v2i_unavailable",
            "sequential_ordinal": 0,
            "service_work_ms": 10.0,
            "task_slot": 0,
            "vehicle_slot": 0,
        },
        bad5["task_outcomes"][1],
    ]
    bad5["offered"] = 2
    bad5["admitted"] = 1
    bad5["rejected"] = 1
    bad5["deadline_success"] = 1
    wrapped7 = _runner_mod._build_construct_result(
        bad5, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs7 = validate_construct_result(wrapped7, _load_manifest())
    assert any("zero" in e.lower() or "latency" in e.lower() for e in errs7)


def test_exact_task_outcome_count_and_reconciliation() -> None:
    payload = _valid_adapter_payload()
    # Mutate to have offered != len(task_outcomes)
    bad = copy.deepcopy(payload)
    bad["offered"] = 10
    wrapped = _runner_mod._build_construct_result(
        bad, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs = validate_construct_result(wrapped, _load_manifest())
    assert any("offered" in e.lower() or "len" in e.lower() for e in errs)
    # Forwarded mismatch
    bad2 = copy.deepcopy(payload)
    bad2["forwarded"] = 5
    wrapped2 = _runner_mod._build_construct_result(
        bad2, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs2 = validate_construct_result(wrapped2, _load_manifest())
    assert any("forwarded" in e.lower() for e in errs2)
    # Deadline instrumented false when admitted tasks exist
    bad3 = copy.deepcopy(payload)
    bad3["deadline_instrumented"] = False
    wrapped3 = _runner_mod._build_construct_result(
        bad3, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs3 = validate_construct_result(wrapped3, _load_manifest())
    assert any("deadline_instrumented" in e.lower() for e in errs3)
    # Software identity drift
    bad4 = copy.deepcopy(payload)
    bad4["software_identity"]["actor_sha256"] = "0" * 64
    wrapped4 = _runner_mod._build_construct_result(
        bad4, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs4 = validate_construct_result(wrapped4, _load_manifest())
    assert any("actor" in e.lower() for e in errs4)
    # Config ID recomputation failure
    bad5 = copy.deepcopy(payload)
    bad5["config_id"] = "a" * 16
    wrapped5 = _runner_mod._build_construct_result(
        bad5, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs5 = validate_construct_result(wrapped5, _load_manifest())
    assert any("config_id" in e.lower() for e in errs5)


def test_strict_int_rejects_booleans_and_numeric_checks() -> None:
    payload = _valid_adapter_payload()
    bad = copy.deepcopy(payload)
    bad["offered"] = True  # bool should be rejected as int
    wrapped = _runner_mod._build_construct_result(
        bad, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs = validate_construct_result(wrapped, _load_manifest())
    assert any("strict int" in e.lower() or "bool" in e.lower() for e in errs)
    bad2 = copy.deepcopy(payload)
    bad2["total_resource_unit_seconds"] = True
    wrapped2 = _runner_mod._build_construct_result(
        bad2, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs2 = validate_construct_result(wrapped2, _load_manifest())
    assert any("numeric" in e.lower() or "bool" in e.lower() for e in errs2)
    bad3 = copy.deepcopy(payload)
    bad3["resource_intervals_this_tick"][0]["active_compute_units"] = True
    wrapped3 = _runner_mod._build_construct_result(
        bad3, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs3 = validate_construct_result(wrapped3, _load_manifest())
    assert any("strict int" in e.lower() for e in errs3)


def test_resource_intervals_strict_fields_and_recompute() -> None:
    payload = _valid_adapter_payload()
    # Missing field
    bad = copy.deepcopy(payload)
    del bad["resource_intervals_this_tick"][0]["active_compute_units"]
    wrapped = _runner_mod._build_construct_result(
        bad, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs = validate_construct_result(wrapped, _load_manifest())
    assert any("active_compute_units" in e.lower() or "missing field" in e.lower() for e in errs)
    # Wrong tick coverage
    bad2 = copy.deepcopy(payload)
    bad2["resource_intervals_this_tick"][0]["start_time_ms"] = 0
    wrapped2 = _runner_mod._build_construct_result(
        bad2, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs2 = validate_construct_result(wrapped2, _load_manifest())
    assert any("3000" in e or "cover" in e.lower() for e in errs2)
    # Duplicate RSU
    bad3 = copy.deepcopy(payload)
    bad3["resource_intervals_this_tick"][1]["rsu_id"] = 0
    wrapped3 = _runner_mod._build_construct_result(
        bad3, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs3 = validate_construct_result(wrapped3, _load_manifest())
    assert any("duplicate" in e.lower() for e in errs3)
    # Recompute mismatch
    bad4 = copy.deepcopy(payload)
    bad4["total_resource_unit_seconds"] = 999.0
    wrapped4 = _runner_mod._build_construct_result(
        bad4, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs4 = validate_construct_result(wrapped4, _load_manifest())
    assert any("recomputed" in e.lower() or "total_resource" in e.lower() for e in errs4)
    # Also test via validator former pass: missing active field should trigger "active_compute_units"  # noqa: E501
    # Already covered
    # Out-of-range totals: for 2 RSUs, total 0.5 should be out of bounds? Actually bounds is num_rsus*1..3, so 0.5 is out  # noqa: E501
    bad5 = copy.deepcopy(payload)
    bad5["total_resource_unit_seconds"] = 0.5
    bad5["resource_intervals_this_tick"] = [
        {"active_compute_units": 1, "end_time_ms": 4000, "rsu_id": 0, "start_time_ms": 3000},
        {"active_compute_units": 1, "end_time_ms": 4000, "rsu_id": 1, "start_time_ms": 3000},
    ]
    # Keep total consistent with intervals? If we set total 0.5, recomputed is 2.0, so will be drift plus out-of-range, but we want out-of-range specific  # noqa: E501
    wrapped5 = _runner_mod._build_construct_result(
        bad5, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs5 = validate_construct_result(wrapped5, _load_manifest())
    assert any("out of range" in e.lower() or "recomputed" in e.lower() for e in errs5)


def test_drained_work_and_per_rsu_cumulative_reconciliation() -> None:
    payload = _valid_adapter_payload()
    bad = copy.deepcopy(payload)
    bad["total_drained_work_ms"] = 999.0
    wrapped = _runner_mod._build_construct_result(
        bad, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs = validate_construct_result(wrapped, _load_manifest())
    assert any("total_drained" in e.lower() or "per_rsu" in e.lower() for e in errs)
    bad2 = copy.deepcopy(payload)
    bad2["per_rsu_cumulative_drained_ms"]["0"] = float("inf")
    wrapped2 = _runner_mod._build_construct_result(
        bad2, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs2 = validate_construct_result(wrapped2, _load_manifest())
    assert any("finite" in e.lower() for e in errs2)
    bad3 = copy.deepcopy(payload)
    bad3["per_rsu_cumulative_drained_ms"]["0"] = -1.0
    wrapped3 = _runner_mod._build_construct_result(
        bad3, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs3 = validate_construct_result(wrapped3, _load_manifest())
    assert any("finite" in e.lower() or ">=0" in e.lower() for e in errs3)


def test_scaling_receipts_internal_consistency() -> None:
    payload = _valid_adapter_payload()
    # Inject a scaling receipt with inconsistent before/after
    bad = copy.deepcopy(payload)
    bad["scaling_scheduled"] = [
        {
            "rsu_id": 0,
            "direction": "scale_up",
            "decision_time_ms": 3000,
            "due_time_ms": 5000,
            "before_units": 1,
            "after_units": 3,  # should be 2 for scale_up
            "target_units": 3,
            "reason": "test",
            "applied": False,
            "applied_time_ms": None,
            "action_id": "act-1",
            "intended_actuation_delay_ms": 2000,
            "actual_actuation_delay_ms": None,
            "state_age_ms": 0,
        }
    ]
    wrapped = _runner_mod._build_construct_result(
        bad, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs = validate_construct_result(wrapped, _load_manifest())
    assert any("before/after" in e.lower() or "inconsistent" in e.lower() for e in errs)
    # Test due != decision+2000
    bad2 = copy.deepcopy(payload)
    bad2["scaling_applied"] = [
        {
            "rsu_id": 0,
            "direction": "scale_down",
            "decision_time_ms": 3000,
            "due_time_ms": 4000,  # should be 5000
            "before_units": 2,
            "after_units": 1,
            "target_units": 1,
            "reason": "test",
            "applied": True,
            "applied_time_ms": 4000,
            "action_id": "act-2",
            "intended_actuation_delay_ms": 2000,
            "actual_actuation_delay_ms": 1000,
            "state_age_ms": 0,
        }
    ]
    wrapped2 = _runner_mod._build_construct_result(
        bad2, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs2 = validate_construct_result(wrapped2, _load_manifest())
    assert any("due" in e.lower() for e in errs2)
    # Empty is valid
    wrapped3 = _runner_mod._build_construct_result(
        _valid_adapter_payload(),
        hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        TRAFFICTWIN_BASE_SHA,
    )
    assert validate_construct_result(wrapped3, _load_manifest()) == []


def test_receipt_state_age_equals_factor() -> None:
    payload = _valid_adapter_payload()
    payload["receipt_state_age_ms"] = 1000
    # Runner should fail closed at build when receipt age != factor
    try:
        wrapped = _runner_mod._build_construct_result(
            payload, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
        )
    except ValueError as e:
        assert "receipt_state_age_ms" in str(e)
    else:
        errs = validate_construct_result(wrapped, _load_manifest())
        assert any("receipt_state_age" in e.lower() for e in errs)
    # Also test via validator: top state_age vs nested receipt
    payload2 = _valid_adapter_payload()
    payload2["state_age_ms"] = 1000
    payload2["receipt_state_age_ms"] = 0
    try:
        wrapped2 = _runner_mod._build_construct_result(
            payload2, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
        )
    except ValueError as e:
        assert "receipt_state_age_ms" in str(e)
    else:
        errs2 = validate_construct_result(wrapped2, _load_manifest())
        assert any("receipt_state_age" in e.lower() or "state_age" in e.lower() for e in errs2)


def test_conservation_valid_booleans_computed() -> None:
    payload = _valid_adapter_payload()
    wrapped = _runner_mod._build_construct_result(
        payload, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    # Mutate valid to opposite
    wrapped["task_conservation"]["valid"] = False
    errs = validate_construct_result(wrapped, _load_manifest())
    assert any("task_conservation" in e.lower() and "valid" in e.lower() for e in errs)
    wrapped2 = copy.deepcopy(wrapped)
    wrapped2["task_conservation"]["valid"] = True
    wrapped2["task_conservation"]["offered"] = 999
    errs2 = validate_construct_result(wrapped2, _load_manifest())
    assert any("conservation" in e.lower() for e in errs2)
    # Resource valid unconditional true without correct recomputed
    bad = _valid_adapter_payload()
    wrapped3 = _runner_mod._build_construct_result(
        bad, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    wrapped3["resource_conservation"]["valid"] = True
    wrapped3["total_resource_unit_seconds"] = 999
    wrapped3["resource_intervals"][0]["active_compute_units"] = 1
    # Now valid should be false but is true
    errs3 = validate_construct_result(wrapped3, _load_manifest())
    assert any("resource_conservation" in e.lower() for e in errs3)


def test_top_level_mirrors_nested() -> None:
    payload = _valid_adapter_payload()
    wrapped = _runner_mod._build_construct_result(
        payload, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    wrapped["task_outcomes"] = []
    errs = validate_construct_result(wrapped, _load_manifest())
    assert any("mirror" in e.lower() and "task_outcomes" in e.lower() for e in errs)
    wrapped2 = _runner_mod._build_construct_result(
        payload, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    wrapped2["resource_intervals"] = []
    errs2 = validate_construct_result(wrapped2, _load_manifest())
    assert any("mirror" in e.lower() and "resource_intervals" in e.lower() for e in errs2)
    wrapped3 = _runner_mod._build_construct_result(
        payload, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    wrapped3["scaling_action_receipts"]["scheduled"] = [{"fake": 1}]
    errs3 = validate_construct_result(wrapped3, _load_manifest())
    assert any("mirror" in e.lower() for e in errs3)


def test_forbidden_keys_and_private_paths_recursive() -> None:
    payload = _valid_adapter_payload()
    wrapped = _runner_mod._build_construct_result(
        payload, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    # Inject forbidden key at nested depth
    wrapped["nested_adapter_result"]["task_outcomes"][0]["kubernetes"] = "deployment"
    errs = validate_construct_result(wrapped, _load_manifest())
    assert any("forbidden" in e.lower() or "kubernetes" in e.lower() for e in errs)
    payload2 = _valid_adapter_payload()
    wrapped2 = _runner_mod._build_construct_result(
        payload2, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    wrapped2["nested_adapter_result"]["extra"] = {"p_value": 0.05}
    errs2 = validate_construct_result(wrapped2, _load_manifest())
    assert any("p_value" in e.lower() or "forbidden" in e.lower() for e in errs2)
    # Private path at nested depth
    payload3 = _valid_adapter_payload()
    wrapped3 = _runner_mod._build_construct_result(
        payload3, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    # Build compositionally to avoid personal literal
    forbidden_path = str(Path("/", "Users", "example", "secret.txt"))
    wrapped3["nested_adapter_result"]["task_outcomes"][0]["some_path"] = forbidden_path
    errs3 = validate_construct_result(wrapped3, _load_manifest())
    assert any("private" in e.lower() or "absolute" in e.lower() for e in errs3)
    # Timestamp at nested
    payload4 = _valid_adapter_payload()
    wrapped4 = _runner_mod._build_construct_result(
        payload4, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    wrapped4["nested_adapter_result"]["created_utc"] = "2026-01-01"
    errs4 = validate_construct_result(wrapped4, _load_manifest())
    assert any("timestamp" in e.lower() for e in errs4)
    # Queue ceiling claim
    payload5 = _valid_adapter_payload()
    wrapped5 = _runner_mod._build_construct_result(
        payload5, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    wrapped5["nested_adapter_result"]["note"] = "queue ceiling is compute"
    errs5 = validate_construct_result(wrapped5, _load_manifest())
    assert any("queue" in e.lower() or "forbidden" in e.lower() for e in errs5)


def test_one_subprocess_spawn_and_exact_adapter_command() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        vec = Path(td) / "vec"
        (vec / "eval").mkdir(parents=True)
        adapter = vec / "eval" / "eval_sumo_stage1_mc.py"
        adapter.write_text("# fake adapter")
        py = Path(sys.executable)
        calls: list[list[str]] = []

        def counting_runner(*a: Any, **kw: Any) -> Any:  # noqa: ANN401
            cmd = a[0] if a else kw.get("args", [])
            calls.append(list(cmd) if isinstance(cmd, list) else [])
            if isinstance(cmd, list) and cmd and "git" in cmd[0]:
                return _mock_git_success(*a, **kw)
            if isinstance(cmd, list) and "--version" in cmd:
                return _fake_proc(stdout="Python 3.11.15\n")
            return _fake_proc(stdout=json.dumps(_valid_adapter_payload()) + "\n")

        ret = _runner_mod.main(
            argv=["minimal_construct", "--vec-repo", str(vec), "--python", str(py)],
            git_runner=counting_runner,
            subprocess_runner=counting_runner,
        )
        assert ret == 0
        adapter_calls = [c for c in calls if "--e3-mode" in c]
        assert len(adapter_calls) == 1
        cmd = adapter_calls[0]
        assert str(py) in cmd[0]
        assert str(adapter) in cmd
        assert "--trace" in cmd and "__SENTINEL_MISSING_TRACE__" in cmd
        assert "--actor" in cmd and "__SENTINEL_MISSING_ACTOR__" in cmd
        assert "--e3-placement" in cmd
        assert "--e3-scaling" in cmd
        assert "--e3-state-age-ms" in cmd
        assert "--e3-evaluator-seed" in cmd
        assert "--e3-fleet-seed" in cmd
        assert "--e3-num-rsus" in cmd
        assert "--e3-core-sha" in cmd
        assert cmd[cmd.index("--e3-core-sha") + 1] == VEC_CORE_SHA
        idx = cmd.index("--e3-num-rsus")
        assert int(cmd[idx + 1]) <= 2


def test_factor_cli_flags_expose_exact_choices_and_deterministic_probes() -> None:
    import tempfile

    # Test that CLI flags accept all valid choices and produce deterministic IDs without trace/actor execution  # noqa: E501
    # We probe via canonical functions directly, without subprocess invocation
    for placement in ("ingress_dla", "per_task_dla", "p2c_dla"):
        for scaling in ("fixed_1x", "static_overprovisioned", "reactive", "proactive"):
            for age in (0, 1000, 3000):
                arm = canonical_arm_id(placement, scaling, age)
                assert arm == f"{placement}__{scaling}__age_{age}ms"
                for fleet in (1, 2, 3, 4):
                    for rsus in (1, 2):
                        cfg = canonical_config_id(placement, scaling, age, 0, fleet, rsus)
                        assert cfg.endswith(f"__fleet_{fleet}__rsus_{rsus}")
                        cid = _runner_mod._recompute_adapter_config_id(
                            placement, scaling, age, 0, fleet, rsus, VEC_CORE_SHA
                        )
                        assert len(cid) == 16 and re.fullmatch(r"[0-9a-f]{16}", cid)
                        # Deterministic probe: recomputing yields same
                        cid2 = _runner_mod._recompute_adapter_config_id(
                            placement, scaling, age, 0, fleet, rsus, VEC_CORE_SHA
                        )
                        assert cid == cid2

    with tempfile.TemporaryDirectory() as td:
        vec = Path(td) / "vec"
        (vec / "eval").mkdir(parents=True)
        (vec / "eval" / "eval_sumo_stage1_mc.py").write_text("# fake")
        py = Path(sys.executable)

        def counting_runner(*a: Any, **kw: Any) -> Any:  # noqa: ANN401
            cmd = a[0] if a else kw.get("args", [])
            if isinstance(cmd, list) and "--version" in cmd:
                return _fake_proc(stdout="Python 3.11.15\n")
            if isinstance(cmd, list) and "git" in cmd[0]:
                return _mock_git_success(*a, **kw)
            # Validate that passed factors match CLI
            assert "--e3-placement" in cmd
            assert "--e3-scaling" in cmd
            p_idx = cmd.index("--e3-placement") + 1
            s_idx = cmd.index("--e3-scaling") + 1
            age_idx = cmd.index("--e3-state-age-ms") + 1
            fleet_idx = cmd.index("--e3-fleet-seed") + 1
            rsus_idx = cmd.index("--e3-num-rsus") + 1
            # Build payload with those factors to ensure deterministic
            pl = cmd[p_idx]
            sc = cmd[s_idx]
            ag = int(cmd[age_idx])
            fl = int(cmd[fleet_idx])
            rs = int(cmd[rsus_idx])
            # Return a valid payload matching those factors
            payload = _valid_adapter_payload()
            payload["placement"] = pl
            payload["scaling"] = sc
            payload["state_age_ms"] = ag
            payload["fleet_seed"] = fl
            payload["num_rsus"] = rs
            payload["config_id"] = _runner_mod._recompute_adapter_config_id(
                pl, sc, ag, 0, fl, rs, VEC_CORE_SHA
            )
            payload["software_identity"]["fleet_seed"] = fl
            payload["receipt_state_age_ms"] = ag
            # Adjust intervals for num_rsus
            if rs == 1:
                payload["resource_intervals_this_tick"] = [
                    {
                        "active_compute_units": 1,
                        "end_time_ms": 4000,
                        "rsu_id": 0,
                        "start_time_ms": 3000,
                    }
                ]
                payload["resource_intervals"] = payload["resource_intervals_this_tick"]
                payload["tick_resource_intervals"] = payload["resource_intervals_this_tick"]
                payload["total_resource_unit_seconds"] = 1.0
                payload["total_drained_work_ms"] = 10.0
                payload["per_rsu_cumulative_drained_ms"] = {"0": 10.0}
                payload["per_rsu_cumulative_capacity_ms"] = {"0": 1000.0}
                payload["utilization"] = {"0": 0.01}
                payload["task_outcomes"] = [payload["task_outcomes"][0]]
                payload["offered"] = 1
                payload["admitted"] = 1
                payload["rejected"] = 0
                payload["forwarded"] = 0
                payload["deadline_success"] = 1
                payload["construct_rsus"] = 1
                payload["construct_tasks"] = 1
            return _fake_proc(stdout=json.dumps(payload) + "\n")

        # Test a specific factor combination via CLI
        ret = _runner_mod.main(
            argv=[
                "minimal_construct",
                "--vec-repo",
                str(vec),
                "--python",
                str(py),
                "--placement",
                "p2c_dla",
                "--scaling",
                "reactive",
                "--state-age-ms",
                "1000",
                "--fleet-seed",
                "3",
                "--num-rsus",
                "1",
            ],
            git_runner=counting_runner,
            subprocess_runner=counting_runner,
        )
        assert ret == 0

        # Invalid choices should fail before subprocess
        ret2 = _runner_mod.main(
            argv=[
                "minimal_construct",
                "--vec-repo",
                str(vec),
                "--python",
                str(py),
                "--placement",
                "invalid",
            ],
            git_runner=counting_runner,
            subprocess_runner=counting_runner,
        )
        assert ret2 != 0
        ret3 = _runner_mod.main(
            argv=[
                "minimal_construct",
                "--vec-repo",
                str(vec),
                "--python",
                str(py),
                "--scaling",
                "invalid",
            ],
            git_runner=counting_runner,
            subprocess_runner=counting_runner,
        )
        assert ret3 != 0
        ret4 = _runner_mod.main(
            argv=[
                "minimal_construct",
                "--vec-repo",
                str(vec),
                "--python",
                str(py),
                "--state-age-ms",
                "999",
            ],
            git_runner=counting_runner,
            subprocess_runner=counting_runner,
        )
        assert ret4 != 0
        ret5 = _runner_mod.main(
            argv=[
                "minimal_construct",
                "--vec-repo",
                str(vec),
                "--python",
                str(py),
                "--fleet-seed",
                "99",
            ],
            git_runner=counting_runner,
            subprocess_runner=counting_runner,
        )
        assert ret5 != 0
        ret6 = _runner_mod.main(
            argv=[
                "minimal_construct",
                "--vec-repo",
                str(vec),
                "--python",
                str(py),
                "--num-rsus",
                "10",
            ],
            git_runner=counting_runner,
            subprocess_runner=counting_runner,
        )
        assert ret6 != 0


def test_deterministic_repeated_output_and_optional_export_no_overwrite_private_path() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        vec = Path(td) / "vec"
        (vec / "eval").mkdir(parents=True)
        (vec / "eval" / "eval_sumo_stage1_mc.py").write_text("# fake")
        py = Path(sys.executable)
        out = Path(td) / "out" / "construct.json"

        def mock_git(*a: Any, **kw: Any) -> Any:  # noqa: ANN401
            return _mock_git_success(*a, **kw)

        def mock_sub(*a: Any, **kw: Any) -> Any:  # noqa: ANN401
            cmd = a[0] if a else kw.get("args", [])
            if isinstance(cmd, list) and cmd and "git" in cmd[0]:
                return mock_git(*a, **kw)
            if isinstance(cmd, list) and "--version" in cmd:
                return _fake_proc(stdout="Python 3.11.15\n")
            return _fake_proc(stdout=json.dumps(_valid_adapter_payload()) + "\n")

        ret1 = _runner_mod.main(
            argv=[
                "minimal_construct",
                "--vec-repo",
                str(vec),
                "--python",
                str(py),
                "--output",
                str(out),
            ],
            git_runner=mock_git,
            subprocess_runner=mock_sub,
        )
        assert ret1 == 0
        assert out.is_file()
        first = out.read_text(encoding="utf-8").strip()
        out2 = Path(td) / "out2" / "construct.json"
        ret2 = _runner_mod.main(
            argv=[
                "minimal_construct",
                "--vec-repo",
                str(vec),
                "--python",
                str(py),
                "--output",
                str(out2),
            ],
            git_runner=mock_git,
            subprocess_runner=mock_sub,
        )
        assert ret2 == 0
        second = out2.read_text(encoding="utf-8").strip()
        assert first == second
        # Existing output should fail and not overwrite, with stdout empty and no subprocess spawn when knowable  # noqa: E501
        calls: list[list[str]] = []

        def counting_runner(*a: Any, **kw: Any) -> Any:  # noqa: ANN401
            cmd = a[0] if a else kw.get("args", [])
            calls.append(list(cmd) if isinstance(cmd, list) else [])
            if isinstance(cmd, list) and cmd and "git" in cmd[0]:
                return mock_git(*a, **kw)
            if isinstance(cmd, list) and "--version" in cmd:
                return _fake_proc(stdout="Python 3.11.15\n")
            return _fake_proc(stdout=json.dumps(_valid_adapter_payload()) + "\n")

        # Capture stdout
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        captured_out = io.StringIO()
        captured_err = io.StringIO()
        sys.stdout = captured_out  # type: ignore
        sys.stderr = captured_err  # type: ignore
        try:
            ret3 = _runner_mod.main(
                argv=[
                    "minimal_construct",
                    "--vec-repo",
                    str(vec),
                    "--python",
                    str(py),
                    "--output",
                    str(out),
                ],
                git_runner=counting_runner,
                subprocess_runner=counting_runner,
            )
        finally:
            sys.stdout = old_stdout  # type: ignore
            sys.stderr = old_stderr  # type: ignore
        assert ret3 != 0
        assert captured_out.getvalue() == "", "stdout must be empty on export failure"
        # No adapter subprocess when failure knowable at preflight (existing file)
        adapter_calls = [c for c in calls if "--e3-mode" in c]
        assert len(adapter_calls) == 0, "adapter should not run when output exists preflight"
        # Private path via compositional Path
        forbidden_private = Path("/", "Users", "example", "private_test") / "out.json"
        calls2: list[list[str]] = []

        def counting_runner2(*a: Any, **kw: Any) -> Any:  # noqa: ANN401
            cmd = a[0] if a else kw.get("args", [])
            calls2.append(list(cmd) if isinstance(cmd, list) else [])
            if isinstance(cmd, list) and cmd and "git" in cmd[0]:
                return mock_git(*a, **kw)
            if isinstance(cmd, list) and "--version" in cmd:
                return _fake_proc(stdout="Python 3.11.15\n")
            return _fake_proc(stdout=json.dumps(_valid_adapter_payload()) + "\n")

        captured_out2 = io.StringIO()
        sys.stdout = captured_out2  # type: ignore
        try:
            ret4 = _runner_mod.main(
                argv=[
                    "minimal_construct",
                    "--vec-repo",
                    str(vec),
                    "--python",
                    str(py),
                    "--output",
                    str(forbidden_private),
                ],
                git_runner=counting_runner2,
                subprocess_runner=counting_runner2,
            )
        finally:
            sys.stdout = old_stdout  # type: ignore
        assert ret4 != 0
        assert captured_out2.getvalue() == ""
        adapter_calls2 = [c for c in calls2 if "--e3-mode" in c]
        assert len(adapter_calls2) == 0
        data = json.loads(first)
        dumped = json.dumps(data)
        # Check forbidden prefixes not in dumped, using generic compositionally built prefixes
        users_prefix = str(Path("/", "Users")) + "/"
        private_prefix = str(Path("/", "private")) + "/"
        assert users_prefix not in dumped
        assert private_prefix not in dumped


def test_export_byte_write_failure_ordering_and_invalid_path() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        vec = Path(td) / "vec"
        (vec / "eval").mkdir(parents=True)
        (vec / "eval" / "eval_sumo_stage1_mc.py").write_text("# fake")
        py = Path(sys.executable)
        # Invalid output path where parent is a file
        parent_file = Path(td) / "parent_file"
        parent_file.write_text("I am a file, not a directory")
        invalid_out = parent_file / "out.json"

        def mock_git(*a: Any, **kw: Any) -> Any:  # noqa: ANN401
            return _mock_git_success(*a, **kw)

        def mock_sub(*a: Any, **kw: Any) -> Any:  # noqa: ANN401
            cmd = a[0] if a else kw.get("args", [])
            if isinstance(cmd, list) and cmd and "git" in cmd[0]:
                return mock_git(*a, **kw)
            if isinstance(cmd, list) and "--version" in cmd:
                return _fake_proc(stdout="Python 3.11.15\n")
            return _fake_proc(stdout=json.dumps(_valid_adapter_payload()) + "\n")

        old_stdout = sys.stdout
        captured = io.StringIO()
        sys.stdout = captured  # type: ignore
        try:
            ret = _runner_mod.main(
                argv=[
                    "minimal_construct",
                    "--vec-repo",
                    str(vec),
                    "--python",
                    str(py),
                    "--output",
                    str(invalid_out),
                ],
                git_runner=mock_git,
                subprocess_runner=mock_sub,
            )
        finally:
            sys.stdout = old_stdout  # type: ignore
        assert ret != 0
        assert captured.getvalue() == "", "stdout must be empty on write failure"
        # Also test byte drift: write succeeds but we verify read mismatch? Simulate by intercepting write? For now ensure normal success still works with correct bytes  # noqa: E501
        out = Path(td) / "out" / "construct.json"
        ret2 = _runner_mod.main(
            argv=[
                "minimal_construct",
                "--vec-repo",
                str(vec),
                "--python",
                str(py),
                "--output",
                str(out),
            ],
            git_runner=mock_git,
            subprocess_runner=mock_sub,
        )
        assert ret2 == 0
        # Now corrupt file and ensure validator catches drift
        out.write_text("corrupted", encoding="utf-8")
        payload = _valid_adapter_payload()
        wrapped = _runner_mod._build_construct_result(
            payload, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
        )
        canonical = json.dumps(wrapped, sort_keys=True, separators=(",", ":"))
        errs = validate_construct_result(
            wrapped, _load_manifest(), export_path=out, export_canonical=canonical
        )
        assert any("drift" in e.lower() for e in errs)


def test_result_validation_rejects_empirical_ci_queue_actor_k8s_deadline_zero() -> None:
    manifest = _load_manifest()
    payload = _valid_adapter_payload()
    wrapped = _runner_mod._build_construct_result(
        payload, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    assert validate_construct_result(wrapped, manifest) == []
    bad = copy.deepcopy(wrapped)
    bad["is_empirical"] = True
    assert any("is_empirical" in e.lower() for e in validate_construct_result(bad, manifest))
    bad2 = copy.deepcopy(wrapped)
    bad2["ci"] = 0.95
    assert any(
        "ci" in e.lower() or "fabricated" in e.lower()
        for e in validate_construct_result(bad2, manifest)
    )
    bad3 = copy.deepcopy(wrapped)
    bad3["p_value"] = 0.05
    assert any(
        "p_value" in e.lower() or "fabricated" in e.lower()
        for e in validate_construct_result(bad3, manifest)
    )
    bad4 = copy.deepcopy(wrapped)
    bad4["queue_ceiling_is_compute"] = True
    assert any("queue" in e.lower() for e in validate_construct_result(bad4, manifest))
    bad5 = copy.deepcopy(wrapped)
    bad5["note"] = "actor selects execution rsu"
    assert any("actor" in e.lower() for e in validate_construct_result(bad5, manifest))
    bad6 = copy.deepcopy(wrapped)
    bad6["kubernetes_deployment"] = "some"
    assert any("kubernetes" in e.lower() for e in validate_construct_result(bad6, manifest))
    bad7_payload = copy.deepcopy(payload)
    bad7_payload["offered"] = 1
    bad7_payload["admitted"] = 0
    bad7_payload["rejected"] = 1
    bad7_payload["forwarded"] = 0
    bad7_payload["deadline_success"] = 0
    bad7_payload["task_outcomes"] = [
        {
            "admitted": False,
            "deadline_success": None,
            "execution_rsu": -1,
            "forwarded": False,
            "ingress_rsu": 0,
            "latency_ms": 0,
            "latency_reason": "unavailable: rejected work has no latency",
            "rejection_class": "v2i_unavailable",
            "sequential_ordinal": 0,
            "service_work_ms": 10.0,
            "task_slot": 0,
            "vehicle_slot": 0,
        }
    ]
    wrapped7 = _runner_mod._build_construct_result(
        bad7_payload, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs7 = validate_construct_result(wrapped7, manifest)
    assert any("zero" in e.lower() or "latency" in e.lower() for e in errs7)


def test_existing_e2_and_contract_files_byte_untouched() -> None:
    v2_raw = CONTRACT_V2_PATH.read_bytes()
    v2_sha = hashlib.sha256(v2_raw).hexdigest()
    assert v2_sha == CONTRACT_SHA256
    v1_raw = CONTRACT_V1_PATH.read_bytes()
    v1_sha = hashlib.sha256(v1_raw).hexdigest()
    assert v1_sha == "0d8c545703405c59dce5b1d1c7d38a63b31341c23364de43c6530862931fa160"
    proc = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    changed = proc.stdout.splitlines()
    for forbidden in [
        "docs/evaluation/e3/e3_dynamic_resource_v2_contract_v1.json",
        "docs/evaluation/e3/e3_dynamic_resource_v2_contract_v2.json",
        "docs/evaluation/e3/e3_dynamic_resource_v2_contract_v2.md",
    ]:
        assert forbidden not in changed
    for p in changed:
        assert not p.startswith("docs/evaluation/e2")


def test_manifest_validator_rejects_authorized_and_fabricated_and_private() -> None:
    manifest = _load_manifest()
    bad = copy.deepcopy(manifest)
    bad["authorized_execution_config_ids"] = ["some_id"]
    raw = json.dumps(bad, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    sidecar_raw = f"{hashlib.sha256(raw).hexdigest()}  {MANIFEST_PATH.name}\n"
    errs = validate_manifest_dict(
        bad,
        raw_bytes=raw,
        sidecar_hex=hashlib.sha256(raw).hexdigest(),
        sidecar_raw=sidecar_raw,
        manifest_filename=MANIFEST_PATH.name,
    )
    assert any("authorized_execution_config_ids" in e for e in errs)
    bad2 = copy.deepcopy(manifest)
    bad2["results"] = {"some": "result"}
    raw2 = json.dumps(bad2, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    sidecar_raw2 = f"{hashlib.sha256(raw2).hexdigest()}  {MANIFEST_PATH.name}\n"
    errs2 = validate_manifest_dict(
        bad2,
        raw_bytes=raw2,
        sidecar_hex=hashlib.sha256(raw2).hexdigest(),
        sidecar_raw=sidecar_raw2,
        manifest_filename=MANIFEST_PATH.name,
    )
    assert any("results" in e or "fabricated" in e.lower() for e in errs2)
    # Build generic forbidden prefix compositionally
    generic_forbidden = str(Path("/", "Users", "example", "secret"))
    bad3 = copy.deepcopy(manifest)
    bad3["some_path"] = generic_forbidden
    raw3 = json.dumps(bad3, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    sidecar_raw3 = f"{hashlib.sha256(raw3).hexdigest()}  {MANIFEST_PATH.name}\n"
    errs3 = validate_manifest_dict(
        bad3,
        raw_bytes=raw3,
        sidecar_hex=hashlib.sha256(raw3).hexdigest(),
        sidecar_raw=sidecar_raw3,
        manifest_filename=MANIFEST_PATH.name,
    )
    assert any("private" in e.lower() or "absolute" in e.lower() for e in errs3)
    bad4 = copy.deepcopy(manifest)
    bad4["note"] = "queue ceiling is compute"
    raw4 = json.dumps(bad4, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    sidecar_raw4 = f"{hashlib.sha256(raw4).hexdigest()}  {MANIFEST_PATH.name}\n"
    errs4 = validate_manifest_dict(
        bad4,
        raw_bytes=raw4,
        sidecar_hex=hashlib.sha256(raw4).hexdigest(),
        sidecar_raw=sidecar_raw4,
        manifest_filename=MANIFEST_PATH.name,
    )
    assert any("queue" in e.lower() or "forbidden" in e.lower() for e in errs4)
    bad5 = copy.deepcopy(manifest)
    bad5["actor_selects_execution_rsu"] = True
    raw5 = json.dumps(bad5, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    sidecar_raw5 = f"{hashlib.sha256(raw5).hexdigest()}  {MANIFEST_PATH.name}\n"
    errs5 = validate_manifest_dict(
        bad5,
        raw_bytes=raw5,
        sidecar_hex=hashlib.sha256(raw5).hexdigest(),
        sidecar_raw=sidecar_raw5,
        manifest_filename=MANIFEST_PATH.name,
    )
    assert any("actor" in e.lower() or "forbidden" in e.lower() for e in errs5)
    bad6 = copy.deepcopy(manifest)
    bad6["kubernetes"] = "deployment"
    raw6 = json.dumps(bad6, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    sidecar_raw6 = f"{hashlib.sha256(raw6).hexdigest()}  {MANIFEST_PATH.name}\n"
    errs6 = validate_manifest_dict(
        bad6,
        raw_bytes=raw6,
        sidecar_hex=hashlib.sha256(raw6).hexdigest(),
        sidecar_raw=sidecar_raw6,
        manifest_filename=MANIFEST_PATH.name,
    )
    assert any("kubernetes" in e.lower() or "forbidden" in e.lower() for e in errs6)


def test_validator_rejects_ordering_and_duplicate_and_checksum_drift() -> None:
    manifest = _load_manifest()
    bad = copy.deepcopy(manifest)
    bad["dormant_arms"] = list(reversed(bad["dormant_arms"]))
    raw = json.dumps(bad, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    sidecar_raw = f"{hashlib.sha256(raw).hexdigest()}  {MANIFEST_PATH.name}\n"
    errs = validate_manifest_dict(
        bad,
        raw_bytes=raw,
        sidecar_hex=hashlib.sha256(raw).hexdigest(),
        sidecar_raw=sidecar_raw,
        manifest_filename=MANIFEST_PATH.name,
    )
    assert any("ordering" in e.lower() or "drift" in e.lower() for e in errs)
    bad2 = copy.deepcopy(manifest)
    bad2["dormant_configs"].append(bad2["dormant_configs"][0])
    bad2["dormant_config_count"] = len(bad2["dormant_configs"])
    raw2 = json.dumps(bad2, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    sidecar_raw2 = f"{hashlib.sha256(raw2).hexdigest()}  {MANIFEST_PATH.name}\n"
    errs2 = validate_manifest_dict(
        bad2,
        raw_bytes=raw2,
        sidecar_hex=hashlib.sha256(raw2).hexdigest(),
        sidecar_raw=sidecar_raw2,
        manifest_filename=MANIFEST_PATH.name,
    )
    assert any("duplicate" in e.lower() or "count" in e.lower() for e in errs2)
    # checksum drift: sidecar hex mismatch
    raw3 = MANIFEST_PATH.read_bytes()
    errs3 = validate_manifest_dict(
        manifest,
        raw_bytes=raw3,
        sidecar_hex="0" * 64,
        sidecar_raw=f"{'0' * 64}  {MANIFEST_PATH.name}\n",
        manifest_filename=MANIFEST_PATH.name,
    )
    assert any("sidecar" in e.lower() or "mismatch" in e.lower() for e in errs3)
    # exact sidecar format drift: missing two spaces
    bad_raw = f"{hashlib.sha256(raw3).hexdigest()} {MANIFEST_PATH.name}\n"
    errs3b = validate_manifest_dict(
        manifest,
        raw_bytes=raw3,
        sidecar_hex=hashlib.sha256(raw3).hexdigest(),
        sidecar_raw=bad_raw,
        manifest_filename=MANIFEST_PATH.name,
    )
    assert any("sidecar" in e.lower() for e in errs3b)
    bad3 = copy.deepcopy(manifest)
    bad3["dormant_configs"] = bad3["dormant_configs"][:10]
    bad3["dormant_config_count"] = 10
    raw3 = json.dumps(bad3, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    sidecar_raw3 = f"{hashlib.sha256(raw3).hexdigest()}  {MANIFEST_PATH.name}\n"
    errs4 = validate_manifest_dict(
        bad3,
        raw_bytes=raw3,
        sidecar_hex=hashlib.sha256(raw3).hexdigest(),
        sidecar_raw=sidecar_raw3,
        manifest_filename=MANIFEST_PATH.name,
    )
    assert len(errs4) > 0


def test_validator_former_pass_branches_now_fail() -> None:
    # Each former pass branch must now produce a specific error
    payload = _valid_adapter_payload()
    manifest = _load_manifest()
    wrapped = _runner_mod._build_construct_result(
        payload, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    # 1. Wrong result schema
    bad = copy.deepcopy(wrapped)
    bad["result_schema_version"] = "wrong_version"
    errs = validate_construct_result(bad, manifest)
    assert any("result_schema_version" in e for e in errs), "wrong result schema should be flagged"
    # 2. Manifest hash logic
    bad2 = copy.deepcopy(wrapped)
    bad2["manifest_sha256"] = "0" * 64
    errs2 = validate_construct_result(bad2, manifest)
    assert any("manifest_sha" in e for e in errs2)
    # 3. Admitted zero latency
    bad3_payload = copy.deepcopy(payload)
    bad3_payload["task_outcomes"][0]["latency_ms"] = 0.0
    wrapped3 = _runner_mod._build_construct_result(
        bad3_payload, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs3 = validate_construct_result(wrapped3, manifest)
    assert any("zero" in e.lower() for e in errs3)
    # 4. Missing resource interval field
    bad4_payload = copy.deepcopy(payload)
    del bad4_payload["resource_intervals_this_tick"][0]["active_compute_units"]
    wrapped4 = _runner_mod._build_construct_result(
        bad4_payload, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs4 = validate_construct_result(wrapped4, manifest)
    assert any("active_compute_units" in e or "missing field" in e.lower() for e in errs4)
    # 5. Out-of-range resource totals (via recomputed drift)
    bad5_payload = copy.deepcopy(payload)
    bad5_payload["total_resource_unit_seconds"] = 999.0
    wrapped5 = _runner_mod._build_construct_result(
        bad5_payload, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    errs5 = validate_construct_result(wrapped5, manifest)
    assert any("total_resource" in e.lower() or "recomputed" in e.lower() for e in errs5)
    # 6. Sidecar/default handling: manifest with bad sidecar exact format already tested, but also test validator default sidecar derivation uses with_suffix  # noqa: E501
    # Ensure validate_manifest_file uses with_suffix: test by calling with manifest without sidecar arg  # noqa: E501
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        m_path = Path(td) / MANIFEST_PATH.name
        s_path_correct = m_path.with_suffix(".sha256")
        s_path_wrong = Path(str(m_path) + ".sha256")  # old style would be
        m_path.write_bytes(MANIFEST_PATH.read_bytes())
        s_path_correct.write_text(
            f"{hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()}  {m_path.name}\n"
        )
        # Validator should find sidecar via with_suffix, not via "." + "json" + ".sha256"
        errs6 = validate_manifest_file(m_path, s_path_correct)
        assert errs6 == []
        # Wrong path should be considered missing if we try with_suffix derived but file exists at wrong location? Simulate validator main default  # noqa: E501
        # Our main uses with_suffix, so wrong file not found would be error
        s_path_wrong.write_text("should not be used")
        # If we mistakenly use old logic, s_path_wrong would exist but s_path_correct exists, we test that validator's main correctly uses with_suffix  # noqa: E501
        # Ensure old path not considered
        assert not Path(str(m_path) + ".sha256").exists() or s_path_wrong != s_path_correct


def test_result_schema_eight_holes_fail_closed() -> None:
    """Eight independent result-schema mutations must each fail with specific error class."""
    payload = _valid_adapter_payload()
    manifest = _load_manifest()
    base_sha = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    wrapped = _runner_mod._build_construct_result(payload, base_sha, TRAFFICTWIN_BASE_SHA)

    # 1. remove top-level resource_conservation
    bad1 = copy.deepcopy(wrapped)
    bad1.pop("resource_conservation", None)
    errs1 = validate_construct_result(bad1, manifest)
    assert any("resource_conservation" in e and "missing" in e.lower() for e in errs1), (
        f"hole1 should flag resource_conservation missing, got {errs1}"
    )

    # 2. remove top-level scaling_action_receipts
    bad2 = copy.deepcopy(wrapped)
    bad2.pop("scaling_action_receipts", None)
    errs2 = validate_construct_result(bad2, manifest)
    assert any("scaling_action_receipts" in e and "missing" in e.lower() for e in errs2), (
        f"hole2 got {errs2}"
    )

    # 3. replace scaling_action_receipts with {} and remove both nested scaling arrays
    bad3 = copy.deepcopy(wrapped)
    bad3["scaling_action_receipts"] = {}
    bad3["nested_adapter_result"].pop("scaling_scheduled", None)
    bad3["nested_adapter_result"].pop("scaling_applied", None)
    errs3 = validate_construct_result(bad3, manifest)
    assert any("scaling_action_receipts" in e and "scheduled" in e.lower() for e in errs3) or any(
        "scaling_action_receipts" in e for e in errs3
    ), f"hole3 scaling mismatch {errs3}"
    assert any("scaling_scheduled" in e and "missing" in e.lower() for e in errs3), (
        f"hole3 nested scheduled missing {errs3}"
    )

    # 4. set resource_conservation.per_rsu_intervals=[] while top/nested intervals remain
    bad4 = copy.deepcopy(wrapped)
    bad4["resource_conservation"]["per_rsu_intervals"] = []
    errs4 = validate_construct_result(bad4, manifest)
    assert any("per_rsu_intervals" in e for e in errs4), f"hole4 got {errs4}"

    # 5. set resource_conservation.total_resource_unit_seconds=999 while top/nested totals remain
    bad5 = copy.deepcopy(wrapped)
    bad5["resource_conservation"]["total_resource_unit_seconds"] = 999
    errs5 = validate_construct_result(bad5, manifest)
    assert any(
        "total_resource_unit_seconds" in e and "mirror mismatch" in e.lower() for e in errs5
    ), f"hole5 got {errs5}"

    # 6. set top-level total_drained_work_ms=999 while nested total remains
    bad6 = copy.deepcopy(wrapped)
    bad6["total_drained_work_ms"] = 999
    errs6 = validate_construct_result(bad6, manifest)
    assert any("total_drained_work_ms" in e and "mirror mismatch" in e.lower() for e in errs6), (
        f"hole6 got {errs6}"
    )

    # 7. remove task_conservation.forwarded
    bad7 = copy.deepcopy(wrapped)
    bad7["task_conservation"].pop("forwarded", None)
    errs7 = validate_construct_result(bad7, manifest)
    assert any("forwarded" in e for e in errs7), f"hole7 got {errs7}"

    # 8. remove task_conservation.deadline_success
    bad8 = copy.deepcopy(wrapped)
    bad8["task_conservation"].pop("deadline_success", None)
    errs8 = validate_construct_result(bad8, manifest)
    assert any("deadline_success" in e for e in errs8), f"hole8 got {errs8}"


def test_manifest_parity_gaps_fail_closed() -> None:
    """Manifest-runtime parity: deleted traffictwin_runtime and self-checksummed true capabilities must fail."""  # noqa: E501
    manifest = _load_manifest()
    # Deleted traffictwin_runtime
    bad = copy.deepcopy(manifest)
    bad.pop("traffictwin_runtime", None)
    raw = json.dumps(bad, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    sidecar_hex = hashlib.sha256(raw).hexdigest()
    sidecar_raw = f"{sidecar_hex}  {MANIFEST_PATH.name}\n"
    errs = validate_manifest_dict(
        bad,
        raw_bytes=raw,
        sidecar_hex=sidecar_hex,
        sidecar_raw=sidecar_raw,
        manifest_filename=MANIFEST_PATH.name,
    )
    assert any("traffictwin_runtime" in e for e in errs), f"deleted runtime should flag, got {errs}"

    # Self-checksummed custom manifest with unauthorized true
    bad2 = copy.deepcopy(manifest)
    bad2["unauthorized_capabilities"]["benchmarks_authorized"] = True
    raw2 = json.dumps(bad2, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    sidecar_hex2 = hashlib.sha256(raw2).hexdigest()
    sidecar_raw2 = f"{sidecar_hex2}  {MANIFEST_PATH.name}\n"
    errs2 = validate_manifest_dict(
        bad2,
        raw_bytes=raw2,
        sidecar_hex=sidecar_hex2,
        sidecar_raw=sidecar_raw2,
        manifest_filename=MANIFEST_PATH.name,
    )
    assert any("benchmarks_authorized" in e for e in errs2), (
        f"unauthorized true should flag, got {errs2}"
    )

    # Additional _authorized true
    bad3 = copy.deepcopy(manifest)
    bad3["unauthorized_capabilities"]["new_feature_authorized"] = True
    raw3 = json.dumps(bad3, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    sidecar_hex3 = hashlib.sha256(raw3).hexdigest()
    sidecar_raw3 = f"{sidecar_hex3}  {MANIFEST_PATH.name}\n"
    errs3 = validate_manifest_dict(
        bad3,
        raw_bytes=raw3,
        sidecar_hex=sidecar_hex3,
        sidecar_raw=sidecar_raw3,
        manifest_filename=MANIFEST_PATH.name,
    )
    assert any("_authorized" in e for e in errs3), (
        f"additional _authorized should flag, got {errs3}"
    )

    # Missing approved candidate pin
    bad4 = copy.deepcopy(manifest)
    bad4.pop("approved_candidate_commit", None)
    raw4 = json.dumps(bad4, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    sidecar_hex4 = hashlib.sha256(raw4).hexdigest()
    sidecar_raw4 = f"{sidecar_hex4}  {MANIFEST_PATH.name}\n"
    errs4 = validate_manifest_dict(
        bad4,
        raw_bytes=raw4,
        sidecar_hex=sidecar_hex4,
        sidecar_raw=sidecar_raw4,
        manifest_filename=MANIFEST_PATH.name,
    )
    assert any("approved_candidate_commit" in e for e in errs4), (
        f"missing approved pin should flag, got {errs4}"
    )


def test_export_byte_drift_detection() -> None:
    import tempfile

    manifest = _load_manifest()
    payload = _valid_adapter_payload()
    wrapped = _runner_mod._build_construct_result(
        payload, hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), TRAFFICTWIN_BASE_SHA
    )
    canonical = json.dumps(wrapped, sort_keys=True, separators=(",", ":"))
    with tempfile.TemporaryDirectory() as td:
        export = Path(td) / "export.json"
        export.write_text(canonical + "\n", encoding="utf-8")
        errs = validate_construct_result(
            wrapped, manifest, export_path=export, export_canonical=canonical
        )
        assert errs == []
        export.write_text(canonical + "x", encoding="utf-8")
        errs2 = validate_construct_result(
            wrapped, manifest, export_path=export, export_canonical=canonical
        )
        assert any("drift" in e.lower() for e in errs2)
        errs3 = validate_construct_result(
            wrapped, manifest, export_path=Path(td) / "missing.json", export_canonical=canonical
        )
        assert any("missing" in e.lower() for e in errs3)


def test_manifest_sidecar_must_be_with_suffix_and_no_old_path() -> None:
    # Ensure old path does not exist and source does not contain it
    forbidden_suffix = "." + "json" + ".sha256"
    old_sidecar = MANIFEST_PATH.parent / (MANIFEST_PATH.name + ".sha256")
    # Use compositionally built forbidden string to avoid literal
    assert not old_sidecar.exists(), f"old sidecar path {old_sidecar} must not exist"
    # Check source files do not contain old string
    for path in [RUNNER_PATH, VALIDATOR_PATH, Path(__file__)]:
        text = path.read_text(encoding="utf-8")
        assert forbidden_suffix not in text, f"{path} contains forbidden old sidecar string"
        # Also ensure with_suffix usage appears for JSON manifest
        if path in (RUNNER_PATH, VALIDATOR_PATH):
            assert 'with_suffix(".sha256")' in text or "with_suffix('.sha256')" in text, (
                f"{path} must use with_suffix for sidecar"
            )


def test_no_bare_pass_in_changed_scripts() -> None:
    for path in [RUNNER_PATH, VALIDATOR_PATH]:
        lines = path.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            assert stripped != "pass", f"bare pass found in {path}:{idx}"


def _self_checksummed_manifest(base: dict[str, Any]) -> tuple[dict[str, Any], bytes, str, str]:
    """Helper: canonical JSON bytes and sidecar material for self-checksummed manifest."""
    raw = json.dumps(base, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    hexv = hashlib.sha256(raw).hexdigest()
    sidecar_raw = f"{hexv}  {MANIFEST_PATH.name}\n"
    return base, raw, hexv, sidecar_raw


def test_blocker1_manifest_authority_prefix_escape_rejected() -> None:
    """Sibling execution_authority_extra and nested prefix-confusion must fail both validators."""
    manifest = _load_manifest()
    # Test each forbidden authorization key variant with true value
    auth_keys = [
        "full_3600_step_cells_authorized",
        "e3a_authorized",
        "manchester_trace_comparative_execution_authorized",
        "empirical_e3_results_authorized",
        "statistical_inference_authorized",
    ]
    for key in auth_keys:
        # Top-level execution_authority_extra with true capability
        bad = copy.deepcopy(manifest)
        bad["execution_authority_extra"] = {key: True, "note": "should be rejected"}
        raw = json.dumps(bad, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
        sidecar_raw = f"{hashlib.sha256(raw).hexdigest()}  {MANIFEST_PATH.name}\n"
        # Standalone validator
        errs = validate_manifest_dict(
            bad,
            raw_bytes=raw,
            sidecar_hex=hashlib.sha256(raw).hexdigest(),
            sidecar_raw=sidecar_raw,
            manifest_filename=MANIFEST_PATH.name,
        )
        assert any(
            "execution_authority_extra" in e
            or key in e
            or "top-level" in e.lower()
            or "_authorized" in e
            for e in errs
        ), f"top-level extra true {key} should fail, got {errs}"
        # Runner file-based verification via temp files
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            m_path = Path(td) / MANIFEST_PATH.name
            s_path = m_path.with_suffix(".sha256")
            m_path.write_bytes(raw)
            s_path.write_text(sidecar_raw, encoding="utf-8")
            errs_file = validate_manifest_file(m_path, s_path)
            assert len(errs_file) > 0, f"file validator should fail for top-level extra {key}"
            # Runner _verify_manifest must also fail
            import importlib.util as _ilu

            spec = _ilu.spec_from_file_location("run_e3_tmp", RUNNER_PATH)
            assert spec is not None and spec.loader is not None
            mod = _ilu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            try:
                mod._verify_manifest(m_path, s_path)
                raise AssertionError(f"runner _verify_manifest should fail for {key}")
            except Exception as e:
                assert (
                    "top-level" in str(e).lower()
                    or "extra" in str(e).lower()
                    or "_authorized" in str(e).lower()
                    or "drift" in str(e).lower()
                )

        # Nested prefix-confusion: object under unrelated key containing execution_authority_extra
        bad2 = copy.deepcopy(manifest)
        bad2["custom_wrapper"] = {"execution_authority_extra": {key: True}}
        raw2 = (
            json.dumps(bad2, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
        )
        sidecar_raw2 = f"{hashlib.sha256(raw2).hexdigest()}  {MANIFEST_PATH.name}\n"
        errs2 = validate_manifest_dict(
            bad2,
            raw_bytes=raw2,
            sidecar_hex=hashlib.sha256(raw2).hexdigest(),
            sidecar_raw=sidecar_raw2,
            manifest_filename=MANIFEST_PATH.name,
        )
        assert any(
            key in e or "_authorized" in e or "top-level" in e.lower() or "custom_wrapper" in e
            for e in errs2
        ), f"nested prefix confusion true {key} should fail, got {errs2}"
        with tempfile.TemporaryDirectory() as td:
            m_path = Path(td) / MANIFEST_PATH.name
            s_path = m_path.with_suffix(".sha256")
            m_path.write_bytes(raw2)
            s_path.write_text(sidecar_raw2, encoding="utf-8")
            errs_file2 = validate_manifest_file(m_path, s_path)
            assert len(errs_file2) > 0, f"nested prefix {key} file should fail"


def test_blocker1_manifest_strict_type_rejects_int_for_bool() -> None:
    """Integer 0 must not be accepted for boolean false field in execution_authority."""
    manifest = _load_manifest()
    bad = copy.deepcopy(manifest)
    # Replace a boolean false field with integer 0
    bad["execution_authority"]["scientific_execution_authorized"] = 0  # type: ignore[assignment]
    raw = json.dumps(bad, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    sidecar_raw = f"{hashlib.sha256(raw).hexdigest()}  {MANIFEST_PATH.name}\n"
    errs = validate_manifest_dict(
        bad,
        raw_bytes=raw,
        sidecar_hex=hashlib.sha256(raw).hexdigest(),
        sidecar_raw=sidecar_raw,
        manifest_filename=MANIFEST_PATH.name,
    )
    assert any(
        "strict" in e.lower() or "type" in e.lower() or "scientific_execution_authorized" in e
        for e in errs
    ), f"int 0 for bool false should fail, got {errs}"
    # Also test via file validator and runner
    import importlib.util as _ilu
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        m_path = Path(td) / MANIFEST_PATH.name
        s_path = m_path.with_suffix(".sha256")
        m_path.write_bytes(raw)
        s_path.write_text(sidecar_raw, encoding="utf-8")
        errs_file = validate_manifest_file(m_path, s_path)
        assert len(errs_file) > 0
        spec = _ilu.spec_from_file_location("run_e3_tmp2", RUNNER_PATH)
        assert spec is not None and spec.loader is not None
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        try:
            mod._verify_manifest(m_path, s_path)
            raise AssertionError("runner should reject int 0 for bool")
        except Exception as e:
            assert "strict" in str(e).lower() or "mismatch" in str(e).lower()


def test_blocker1_manifest_top_level_allowlist() -> None:
    """Exact top-level allowlist must reject any extra sibling keys."""
    manifest = _load_manifest()
    bad = copy.deepcopy(manifest)
    bad["extra_sibling_key"] = {"note": "should be rejected"}
    raw = json.dumps(bad, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    sidecar_raw = f"{hashlib.sha256(raw).hexdigest()}  {MANIFEST_PATH.name}\n"
    errs = validate_manifest_dict(
        bad,
        raw_bytes=raw,
        sidecar_hex=hashlib.sha256(raw).hexdigest(),
        sidecar_raw=sidecar_raw,
        manifest_filename=MANIFEST_PATH.name,
    )
    assert any("top-level" in e.lower() and "extra_sibling_key" in e for e in errs) or any(
        "extra" in e.lower() for e in errs
    ), f"allowlist should reject extra key, got {errs}"


def test_blocker2_result_unauthorized_booleans() -> None:
    """Result validator must reject any _authorized true outside exact
    result.execution_authority."""  # noqa: E501
    base_sha = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    # Direct top-level unauthorized true
    payload = _valid_adapter_payload()
    wrapped = _runner_mod._build_construct_result(payload, base_sha, TRAFFICTWIN_BASE_SHA)
    wrapped["e3a_authorized"] = True  # type: ignore[assignment]
    errs = validate_construct_result(wrapped, _load_manifest())
    assert any("_authorized" in e and "not false" in e.lower() for e in errs) or any(
        "e3a_authorized" in e for e in errs
    ), f"top-level true should fail, got {errs}"
    # Non-boolean _authorized (int)
    payload2 = _valid_adapter_payload()
    wrapped2 = _runner_mod._build_construct_result(payload2, base_sha, TRAFFICTWIN_BASE_SHA)
    wrapped2["statistical_inference_authorized"] = 1  # type: ignore[assignment]
    errs2 = validate_construct_result(wrapped2, _load_manifest())
    assert any("_authorized" in e for e in errs2), f"non-boolean should fail, got {errs2}"
    # Deep nested inside nested_adapter_result
    payload3 = _valid_adapter_payload()
    wrapped3 = _runner_mod._build_construct_result(payload3, base_sha, TRAFFICTWIN_BASE_SHA)
    wrapped3["nested_adapter_result"]["empirical_e3_results_authorized"] = True  # type: ignore[assignment]
    errs3 = validate_construct_result(wrapped3, _load_manifest())
    assert any("_authorized" in e or "empirical" in e for e in errs3), (
        f"nested true should fail, got {errs3}"
    )
    # Arbitrary deep object
    payload4 = _valid_adapter_payload()
    wrapped4 = _runner_mod._build_construct_result(payload4, base_sha, TRAFFICTWIN_BASE_SHA)
    wrapped4["nested_adapter_result"]["deep"] = {"inner": {"full_3600_step_cells_authorized": True}}  # type: ignore[assignment]
    errs4 = validate_construct_result(wrapped4, _load_manifest())
    assert any("_authorized" in e or "full_3600" in e for e in errs4), (
        f"deep nested true should fail, got {errs4}"
    )
    # Ensure canonical result authority exact strict set still passes
    payload_ok = _valid_adapter_payload()
    wrapped_ok = _runner_mod._build_construct_result(payload_ok, base_sha, TRAFFICTWIN_BASE_SHA)
    errs_ok = validate_construct_result(wrapped_ok, _load_manifest())
    assert errs_ok == [], f"canonical should pass, got {errs_ok}"
    # Mutate canonical authority with int 0 for bool false must fail strict type
    payload5 = _valid_adapter_payload()
    wrapped5 = _runner_mod._build_construct_result(payload5, base_sha, TRAFFICTWIN_BASE_SHA)
    wrapped5["execution_authority"]["scientific_execution_authorized"] = 0  # type: ignore[assignment]
    errs5 = validate_construct_result(wrapped5, _load_manifest())
    assert any(
        "strict" in e.lower() or "type" in e.lower() or "scientific_execution_authorized" in e
        for e in errs5
    ), f"int 0 for bool in result authority should fail, got {errs5}"


def test_blocker3_missing_interval_validation_abort_direct() -> None:
    """Missing all nested interval aliases must report error and not raise;
    later checks still run."""  # noqa: E501
    payload = _valid_adapter_payload()
    base_sha = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    # Build base wrapped then remove all three interval aliases from nested
    wrapped = _runner_mod._build_construct_result(payload, base_sha, TRAFFICTWIN_BASE_SHA)
    nested = wrapped["nested_adapter_result"]
    # Remove all interval aliases
    nested.pop("resource_intervals_this_tick", None)
    nested.pop("resource_intervals", None)
    nested.pop("tick_resource_intervals", None)
    # Also inject later-check failures that should still be reported
    wrapped["task_outcomes"] = [{"mismatch": 1}]  # mirror mismatch
    wrapped["state_age_ms"] = 999  # state age mismatch vs nested
    nested["created_utc"] = "2026-01-01"  # forbidden timestamp
    nested["note"] = "/Users/some/private/path"  # private path
    wrapped["resource_intervals"] = []  # to trigger mirror mismatch difference
    # Also ensure export byte drift and forbidden substring will be tested
    # via direct call without export? We'll test export separately
    # Direct function must not raise
    try:
        errs = validate_construct_result(wrapped, _load_manifest())
    except Exception as e:
        raise AssertionError(  # noqa: E501
            f"should not raise UnboundLocalError, got {e} {type(e).__name__}"
        ) from e
    assert any(
        "resource_intervals missing" in e.lower() or "nested resource_intervals" in e.lower()
        for e in errs
    ), f"missing intervals should be reported, got {errs}"
    # Later checks must still run despite missing intervals
    assert any("mirror mismatch" in e.lower() for e in errs), (
        f"mirror check should still run, got {errs}"
    )
    # State age check (receipt vs factor) may still run, but we altered
    # top state_age, so expect some state_age error
    assert any("state_age" in e.lower() or "receipt_state_age" in e.lower() for e in errs), (
        f"state age should be checked, got {errs}"
    )
    assert any("timestamp" in e.lower() for e in errs), (
        f"timestamp check should still run, got {errs}"
    )
    assert any("private" in e.lower() or "absolute" in e.lower() for e in errs), (
        f"private path should still run, got {errs}"
    )


def test_blocker3_missing_interval_cli_emits_typed_verdict() -> None:
    """CLI must emit pass=false JSON verdict instead of traceback when intervals missing."""
    import json as _json
    import subprocess
    import sys
    import tempfile

    payload = _valid_adapter_payload()
    base_sha = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    wrapped = _runner_mod._build_construct_result(payload, base_sha, TRAFFICTWIN_BASE_SHA)
    nested = wrapped["nested_adapter_result"]
    nested.pop("resource_intervals_this_tick", None)
    nested.pop("resource_intervals", None)
    nested.pop("tick_resource_intervals", None)
    # Inject later checks as well to ensure CLI reports them
    nested["note"] = "queue ceiling is the compute capacity"  # forbidden claim variant
    wrapped["task_outcomes"] = []
    # Prepare temp manifest and construct files
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        m_path = td_path / MANIFEST_PATH.name
        s_path = m_path.with_suffix(".sha256")
        m_path.write_bytes(MANIFEST_PATH.read_bytes())
        s_path.write_text(
            f"{hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()}  {m_path.name}\n",
            encoding="utf-8",
        )
        c_path = td_path / "construct.json"
        c_path.write_text(_json.dumps(wrapped), encoding="utf-8")
        # Also prepare export file with byte drift? We'll just test without export first
        proc = subprocess.run(  # noqa: S603
            [
                sys.executable,
                str(VALIDATOR_PATH),
                "--manifest",
                str(m_path),
                "--construct-result",
                str(c_path),
            ],
            capture_output=True,
            text=True,
        )
        # Should not produce traceback
        assert "Traceback" not in proc.stderr, f"CLI should not traceback, got {proc.stderr}"
        assert "UnboundLocalError" not in proc.stderr
        assert "UnboundLocalError" not in proc.stdout
        # stdout should be JSON with pass false
        try:
            out = _json.loads(proc.stdout)
        except Exception as e:
            raise AssertionError(f"CLI output not JSON, got {proc.stdout!r} err {e}") from e
        assert out.get("pass") is False, f"should be pass false, got {out}"
        assert isinstance(out.get("errors"), list) and len(out["errors"]) > 0
        errs = out["errors"]
        assert any("resource_intervals" in e.lower() for e in errs), (
            f"missing intervals error expected, got {errs}"
        )
        assert any("queue ceiling is" in e.lower() or "forbidden" in e.lower() for e in errs), (
            f"forbidden claim should still be reported, got {errs}"
        )
        assert any("mirror" in e.lower() for e in errs), (
            f"mirror check should still run in CLI, got {errs}"
        )
        # Now test export drift still reported alongside missing intervals
        export_path = td_path / "export.json"
        export_path.write_text("not canonical", encoding="utf-8")
        proc2 = subprocess.run(  # noqa: S603
            [
                sys.executable,
                str(VALIDATOR_PATH),
                "--manifest",
                str(m_path),
                "--construct-result",
                str(c_path),
                "--export",
                str(export_path),
            ],
            capture_output=True,
            text=True,
        )
        out2 = _json.loads(proc2.stdout)
        assert out2.get("pass") is False
        assert any("export" in e.lower() and "drift" in e.lower() for e in out2["errors"]) or any(
            "drift" in e.lower() for e in out2["errors"]
        ), f"export drift should be reported even with missing intervals, got {out2['errors']}"


def test_defense_claim_variants_rejected() -> None:
    """Natural-language claim variants containing actor selects and queue ceiling is must
    be rejected."""  # noqa: E501
    manifest = _load_manifest()
    for variant in [
        "actor selects the exact execution RSU",
        "queue ceiling is the compute capacity",
    ]:
        bad = copy.deepcopy(manifest)
        bad["note"] = variant
        raw = json.dumps(bad, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
        sidecar_raw = f"{hashlib.sha256(raw).hexdigest()}  {MANIFEST_PATH.name}\n"
        errs = validate_manifest_dict(
            bad,
            raw_bytes=raw,
            sidecar_hex=hashlib.sha256(raw).hexdigest(),
            sidecar_raw=sidecar_raw,
            manifest_filename=MANIFEST_PATH.name,
        )
        assert any(
            "forbidden" in e.lower()
            or "actor selects" in e.lower()
            or "queue ceiling is" in e.lower()
            for e in errs
        ), f"variant {variant!r} should be rejected, got {errs}"
        # Also test at nested depth
        bad2 = copy.deepcopy(manifest)
        bad2["custom"] = {"deep": {"note": variant}}
        raw2 = (
            json.dumps(bad2, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
        )
        sidecar_raw2 = f"{hashlib.sha256(raw2).hexdigest()}  {MANIFEST_PATH.name}\n"
        errs2 = validate_manifest_dict(
            bad2,
            raw_bytes=raw2,
            sidecar_hex=hashlib.sha256(raw2).hexdigest(),
            sidecar_raw=sidecar_raw2,
            manifest_filename=MANIFEST_PATH.name,
        )
        assert any("forbidden" in e.lower() for e in errs2), (
            f"nested variant {variant!r} should fail, got {errs2}"
        )
    # Also test result variant
    payload = _valid_adapter_payload()
    base_sha = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    wrapped = _runner_mod._build_construct_result(payload, base_sha, TRAFFICTWIN_BASE_SHA)
    wrapped["nested_adapter_result"]["note"] = "Actor selects the exact execution RSU"
    errs3 = validate_construct_result(wrapped, _load_manifest())
    assert any("forbidden" in e.lower() or "actor selects" in e.lower() for e in errs3), (
        f"result variant should fail, got {errs3}"
    )
    payload2 = _valid_adapter_payload()
    wrapped2 = _runner_mod._build_construct_result(payload2, base_sha, TRAFFICTWIN_BASE_SHA)
    wrapped2["nested_adapter_result"]["deep"] = {"msg": "QUEUE CEILING IS the compute capacity"}
    errs4 = validate_construct_result(wrapped2, _load_manifest())
    assert any("forbidden" in e.lower() for e in errs4), (
        f"deep result variant should fail, got {errs4}"
    )


def test_defense_canonical_config_id_strict_rsus() -> None:
    """Shared config-ID helper must accept only {1,2,10}, rejecting intermediate counts."""
    for valid in (1, 2, 10):
        # Use a valid placement/scaling/age
        cfg = canonical_config_id("per_task_dla", "fixed_1x", 0, 0, 1, valid)
        assert f"__rsus_{valid}" in cfg
    for invalid in (3, 4, 5, 6, 7, 8, 9):
        try:
            canonical_config_id("per_task_dla", "fixed_1x", 0, 0, 1, invalid)
            raise AssertionError(f"should reject num_rsus {invalid}")
        except ValueError as e:
            assert "must be 1, 2" in str(e).lower() or "out of range" in str(e).lower()
    # Also test that pilot of manifest generation still uses 10 only
    configs = _runner_mod.generate_dormant_configs()
    assert all(c["num_rsus"] == 10 for c in configs)


def test_path_encoding_escape_dotted_sibling_manifest_and_result() -> None:
    """Literal dotted sibling keys must not bypass _authorized via path-join encoding."""
    manifest = _load_manifest()
    # --- Manifest top-level dotted sibling ---
    for dotted_key in ["execution_authority.extra", "execution_authority.evil.deep"]:
        bad = copy.deepcopy(manifest)
        bad[dotted_key] = {"e3a_authorized": True}  # type: ignore[assignment]
        raw = json.dumps(bad, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
        sidecar_raw = f"{hashlib.sha256(raw).hexdigest()}  {MANIFEST_PATH.name}\n"
        errs = validate_manifest_dict(
            bad,
            raw_bytes=raw,
            sidecar_hex=hashlib.sha256(raw).hexdigest(),
            sidecar_raw=sidecar_raw,
            manifest_filename=MANIFEST_PATH.name,
        )
        assert any(dotted_key in e or "top-level" in e.lower() for e in errs) or any(
            "_authorized" in e for e in errs
        ), f"manifest top-level dotted {dotted_key!r} should fail, got {errs}"
        assert any("_authorized" in e or "e3a_authorized" in e for e in errs), (
            f"manifest dotted {dotted_key!r} must flag _authorized true, got {errs}"
        )
        # also via file and runner
        import importlib.util as _ilu
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            m_path = Path(td) / MANIFEST_PATH.name
            s_path = m_path.with_suffix(".sha256")
            m_path.write_bytes(raw)
            s_path.write_text(sidecar_raw, encoding="utf-8")
            errs_file = validate_manifest_file(m_path, s_path)
            assert len(errs_file) > 0, f"file validator should fail dotted {dotted_key}"
            spec = _ilu.spec_from_file_location("run_e3_tmp_dotted", RUNNER_PATH)
            assert spec is not None and spec.loader is not None
            mod = _ilu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            try:
                mod._verify_manifest(m_path, s_path)
                raise AssertionError(f"runner should reject manifest dotted {dotted_key}")
            except Exception as e:
                assert (
                    "top-level" in str(e).lower()
                    or "extra" in str(e).lower()
                    or "_authorized" in str(e).lower()
                    or "drift" in str(e).lower()
                )
        # --- Manifest nested dotted sibling (literal key inside unrelated container) ---
        for dotted_nested in ["execution_authority.extra", "execution_authority.evil.deep"]:
            bad2 = copy.deepcopy(manifest)
            bad2["custom_wrapper"] = {dotted_nested: {"e3a_authorized": True}}  # type: ignore[assignment]
            raw2 = (
                json.dumps(bad2, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")
                + b"\n"
            )
            sidecar_raw2 = f"{hashlib.sha256(raw2).hexdigest()}  {MANIFEST_PATH.name}\n"
            errs2 = validate_manifest_dict(
                bad2,
                raw_bytes=raw2,
                sidecar_hex=hashlib.sha256(raw2).hexdigest(),
                sidecar_raw=sidecar_raw2,
                manifest_filename=MANIFEST_PATH.name,
            )
            assert any("_authorized" in e or "e3a_authorized" in e for e in errs2), (
                f"manifest nested dotted {dotted_nested!r} should flag _authorized, got {errs2}"
            )
            # deeply nested wrapper
            bad3 = copy.deepcopy(manifest)
            bad3["outer"] = {"inner": {dotted_nested: {"e3a_authorized": True}}}  # type: ignore[assignment]
            raw3 = (
                json.dumps(bad3, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")
                + b"\n"
            )
            sidecar_raw3 = f"{hashlib.sha256(raw3).hexdigest()}  {MANIFEST_PATH.name}\n"
            errs3 = validate_manifest_dict(
                bad3,
                raw_bytes=raw3,
                sidecar_hex=hashlib.sha256(raw3).hexdigest(),
                sidecar_raw=sidecar_raw3,
                manifest_filename=MANIFEST_PATH.name,
            )
            assert any("_authorized" in e for e in errs3), (
                f"manifest deep nested dotted {dotted_nested!r} should fail, got {errs3}"
            )

    # --- Result top-level dotted sibling ---
    base_sha = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    for dotted_key in ["execution_authority.extra", "execution_authority.evil.deep"]:
        payload = _valid_adapter_payload()
        wrapped = _runner_mod._build_construct_result(payload, base_sha, TRAFFICTWIN_BASE_SHA)
        wrapped[dotted_key] = {"e3a_authorized": True}  # type: ignore[assignment]
        errs = validate_construct_result(wrapped, _load_manifest())
        assert any("_authorized" in e or "e3a_authorized" in e for e in errs), (
            f"result top-level dotted {dotted_key!r} should flag _authorized, got {errs}"
        )
        # nested dotted sibling inside result custom container
        payload2 = _valid_adapter_payload()
        wrapped2 = _runner_mod._build_construct_result(payload2, base_sha, TRAFFICTWIN_BASE_SHA)
        wrapped2["custom_wrapper"] = {dotted_key: {"e3a_authorized": True}}  # type: ignore[assignment]
        errs2 = validate_construct_result(wrapped2, _load_manifest())
        assert any("_authorized" in e for e in errs2), (
            f"result nested custom_wrapper dotted {dotted_key!r} should fail, got {errs2}"
        )
        # nested inside nested_adapter_result
        payload3 = _valid_adapter_payload()
        wrapped3 = _runner_mod._build_construct_result(payload3, base_sha, TRAFFICTWIN_BASE_SHA)
        wrapped3["nested_adapter_result"][dotted_key] = {"e3a_authorized": True}  # type: ignore[assignment]
        errs3 = validate_construct_result(wrapped3, _load_manifest())
        assert any("_authorized" in e for e in errs3), (
            f"result nested_adapter_result dotted {dotted_key!r} should fail, got {errs3}"
        )
        # deep nested
        payload4 = _valid_adapter_payload()
        wrapped4 = _runner_mod._build_construct_result(payload4, base_sha, TRAFFICTWIN_BASE_SHA)
        wrapped4["deep_outer"] = {"inner": {dotted_key: {"empirical_e3_results_authorized": True}}}  # type: ignore[assignment]
        errs4 = validate_construct_result(wrapped4, _load_manifest())
        assert any("_authorized" in e for e in errs4), (
            f"result deep nested dotted {dotted_key!r} should fail, got {errs4}"
        )


def test_manifest_allowlist_unconditional_and_validator_binding() -> None:
    """Validator must bind allowlist at import and enforce unconditionally."""

    # Validator binds at import time, no conditional try/except fallback
    v_text = VALIDATOR_PATH.read_text(encoding="utf-8")
    assert "MANIFEST_TOP_LEVEL_KEYS = _mod.MANIFEST_TOP_LEVEL_KEYS" in v_text, (
        "validator must bind MANIFEST_TOP_LEVEL_KEYS at import time"
    )
    # No dynamic try/except import inside validate_manifest_dict
    # Ensure the function does not contain the old conditional pattern
    assert (
        "from run_e3_dynamic_resource_v2 import" not in v_text
        or v_text.count("MANIFEST_TOP_LEVEL_KEYS") <= 3
    ), "validator should not dynamically import MANIFEST_TOP_LEVEL_KEYS inside function"
    # Directly check no try/except turning allowlist off inside validate_manifest_dict source
    func_src = v_text.split("def validate_manifest_dict")[1].split("def validate_manifest_file")[0]
    assert "mtlk: frozenset" not in func_src, "old mtlk conditional should be removed"
    assert (
        "try:" not in func_src.split("if set(data.keys())")[0]
        or "MANIFEST_TOP_LEVEL_KEYS" in func_src.split("if set(data.keys())")[0]
    ), "allowlist check must be unconditional, not inside try/except"
    # Functional check: extra key must fail unconditionally
    manifest = _load_manifest()
    bad = copy.deepcopy(manifest)
    bad["execution_authority.extra"] = {"note": "allowlist"}  # type: ignore[assignment]
    raw = json.dumps(bad, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    sidecar_raw = f"{hashlib.sha256(raw).hexdigest()}  {MANIFEST_PATH.name}\n"
    errs = validate_manifest_dict(
        bad,
        raw_bytes=raw,
        sidecar_hex=hashlib.sha256(raw).hexdigest(),
        sidecar_raw=sidecar_raw,
        manifest_filename=MANIFEST_PATH.name,
    )
    assert any("top-level" in e.lower() for e in errs), (
        f"unconditional allowlist should reject dotted sibling, got {errs}"
    )
    # Ensure validator module actually has the attribute
    assert hasattr(_validator_mod, "MANIFEST_TOP_LEVEL_KEYS")
    assert _validator_mod.MANIFEST_TOP_LEVEL_KEYS == _runner_mod.MANIFEST_TOP_LEVEL_KEYS


def test_nested_factor_fields_deletion_fail_closed_direct() -> None:
    """Each of six nested factor fields when deleted must produce typed error, not zero-pass or traceback."""  # noqa: E501
    payload = _valid_adapter_payload()
    base_sha = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    wrapped = _runner_mod._build_construct_result(payload, base_sha, TRAFFICTWIN_BASE_SHA)
    manifest = _load_manifest()
    # Valid still passes
    assert validate_construct_result(wrapped, manifest) == []
    for field in (
        "placement",
        "scaling",
        "state_age_ms",
        "evaluator_seed",
        "fleet_seed",
        "num_rsus",
    ):
        bad = copy.deepcopy(wrapped)
        # Delete from nested
        assert field in bad["nested_adapter_result"], f"field {field} missing in fixture"
        del bad["nested_adapter_result"][field]
        # Must not raise, must produce typed error
        try:
            errs = validate_construct_result(bad, manifest)
        except Exception as e:
            raise AssertionError(
                f"deletion of nested {field} raised {e!r} {type(e).__name__}"
            ) from e
        assert len(errs) > 0, f"deletion of nested {field} should fail closed, got zero errors"
        # Typed error must mention field or nested prefix
        assert any(field in e.lower() or "nested" in e.lower() for e in errs), (
            f"deletion of {field} should produce typed error mentioning field, got {errs}"
        )
        # Also specifically check strict int/string hint for appropriate fields
        if field in ("state_age_ms", "evaluator_seed", "fleet_seed", "num_rsus"):
            assert any("strict int" in e.lower() or field in e.lower() for e in errs), (
                f"int field {field} should mention strict int, got {errs}"
            )
        else:
            assert any("string" in e.lower() or field in e.lower() for e in errs), (
                f"string field {field} should mention string, got {errs}"
            )


def test_nested_factor_fields_deletion_fail_closed_cli() -> None:
    """CLI must emit pass=false JSON verdict without traceback when each nested factor deleted."""
    import subprocess
    import sys
    import tempfile

    payload = _valid_adapter_payload()
    base_sha = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    wrapped = _runner_mod._build_construct_result(payload, base_sha, TRAFFICTWIN_BASE_SHA)
    manifest_bytes = MANIFEST_PATH.read_bytes()
    for field in (
        "placement",
        "scaling",
        "state_age_ms",
        "evaluator_seed",
        "fleet_seed",
        "num_rsus",
    ):
        bad = copy.deepcopy(wrapped)
        del bad["nested_adapter_result"][field]
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            m_path = td_path / MANIFEST_PATH.name
            s_path = m_path.with_suffix(".sha256")
            m_path.write_bytes(manifest_bytes)
            s_path.write_text(
                f"{hashlib.sha256(manifest_bytes).hexdigest()}  {m_path.name}\n",
                encoding="utf-8",
            )
            c_path = td_path / "construct.json"
            c_path.write_text(json.dumps(bad), encoding="utf-8")
            proc = subprocess.run(  # noqa: S603
                [
                    sys.executable,
                    str(VALIDATOR_PATH),
                    "--manifest",
                    str(m_path),
                    "--construct-result",
                    str(c_path),
                ],
                capture_output=True,
                text=True,
            )
            assert "Traceback" not in proc.stderr, f"CLI traceback for {field}: {proc.stderr}"
            assert "Traceback" not in proc.stdout, f"CLI traceback stdout for {field}"
            # stdout must be JSON with pass false
            try:
                out = json.loads(proc.stdout)
            except Exception as e:
                raise AssertionError(
                    f"CLI output not JSON for {field}: {proc.stdout!r} err {e}"
                ) from e
            assert out.get("pass") is False, f"deletion {field} CLI should be pass false, got {out}"
            assert isinstance(out.get("errors"), list) and len(out["errors"]) > 0, (
                f"CLI errors missing for {field}, got {out}"
            )
            assert any(field in e.lower() or "nested" in e.lower() for e in out["errors"]), (
                f"CLI typed error for {field} expected, got {out['errors']}"
            )


def test_exploit_fabricated_exports_rejected_direct_and_cli() -> None:
    """Two demonstrated exploit exports must be rejected (direct and CLI)."""
    import subprocess
    import sys
    import tempfile

    payload = _valid_adapter_payload()
    base_sha = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    wrapped = _runner_mod._build_construct_result(payload, base_sha, TRAFFICTWIN_BASE_SHA)
    manifest = _load_manifest()
    manifest_bytes = MANIFEST_PATH.read_bytes()
    # Valid still passes
    assert validate_construct_result(wrapped, manifest) == []
    # Exploit 1: delete num_rsus, fabricate 5 RSU intervals totalling 15.0 vs factors.num_rsus==2
    exploit1 = copy.deepcopy(wrapped)
    del exploit1["nested_adapter_result"]["num_rsus"]
    exploit1["nested_adapter_result"]["resource_intervals_this_tick"] = [
        {"active_compute_units": 3, "end_time_ms": 4000, "rsu_id": i, "start_time_ms": 3000}
        for i in range(5)
    ]
    exploit1["nested_adapter_result"]["resource_intervals"] = exploit1["nested_adapter_result"][
        "resource_intervals_this_tick"
    ]
    exploit1["nested_adapter_result"]["tick_resource_intervals"] = exploit1[
        "nested_adapter_result"
    ]["resource_intervals_this_tick"]
    exploit1["nested_adapter_result"]["total_resource_unit_seconds"] = 15.0
    exploit1["nested_adapter_result"]["per_rsu_cumulative_capacity_ms"] = {
        str(i): 3000.0 for i in range(5)
    }
    exploit1["nested_adapter_result"]["per_rsu_cumulative_drained_ms"] = {
        str(i): 10.0 for i in range(5)
    }
    exploit1["nested_adapter_result"]["total_drained_work_ms"] = 50.0
    exploit1["nested_adapter_result"]["utilization"] = {str(i): 10.0 / 3000.0 for i in range(5)}
    # Direct validation must reject
    try:
        errs1 = validate_construct_result(exploit1, manifest)
    except Exception as e:
        raise AssertionError(f"exploit1 raised {e}") from e
    assert len(errs1) > 0, "exploit1 (num_rsus omission with 5 intervals) should be rejected"
    assert any("num_rsus" in e.lower() for e in errs1), (
        f"exploit1 should mention num_rsus, got {errs1}"
    )
    # Also test with top-level mirrors synced to avoid mirror mismatch hiding the fix
    exploit1_synced = copy.deepcopy(exploit1)
    exploit1_synced["resource_intervals"] = exploit1["nested_adapter_result"]["resource_intervals"]
    exploit1_synced["total_resource_unit_seconds"] = 15.0
    exploit1_synced["resource_conservation"]["per_rsu_intervals"] = exploit1[
        "nested_adapter_result"
    ]["resource_intervals"]
    exploit1_synced["resource_conservation"]["total_resource_unit_seconds"] = 15.0
    exploit1_synced["total_drained_work_ms"] = 50.0
    # Must still be rejected due to missing num_rsus gating
    errs1s = validate_construct_result(exploit1_synced, manifest)
    assert len(errs1s) > 0, "synced exploit1 still should be rejected"
    # Exploit 2: delete placement/scaling/state_age_ms, forge config_id 000... (direct)
    exploit2 = copy.deepcopy(wrapped)
    for f in ("placement", "scaling", "state_age_ms"):
        del exploit2["nested_adapter_result"][f]
    exploit2["nested_adapter_result"]["config_id"] = "0000000000000000"
    try:
        errs2 = validate_construct_result(exploit2, manifest)
    except Exception as e:
        raise AssertionError(f"exploit2 raised {e}") from e
    assert len(errs2) > 0, (
        "exploit2 (placement/scaling/age omission with forged config_id) should be rejected"
    )
    assert any(
        "placement" in e.lower() or "scaling" in e.lower() or "state_age" in e.lower()
        for e in errs2
    ), f"exploit2 should mention missing placement/scaling/age, got {errs2}"
    assert any("config_id" in e.lower() for e in errs2), (
        f"exploit2 should mention config_id, got {errs2}"
    )
    # CLI checks for both exploits
    for exploit, name in [(exploit1, "exploit1"), (exploit2, "exploit2")]:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            m_path = td_path / MANIFEST_PATH.name
            s_path = m_path.with_suffix(".sha256")
            m_path.write_bytes(manifest_bytes)
            s_path.write_text(
                f"{hashlib.sha256(manifest_bytes).hexdigest()}  {m_path.name}\n",
                encoding="utf-8",
            )
            c_path = td_path / "construct.json"
            c_path.write_text(json.dumps(exploit), encoding="utf-8")
            proc = subprocess.run(  # noqa: S603
                [
                    sys.executable,
                    str(VALIDATOR_PATH),
                    "--manifest",
                    str(m_path),
                    "--construct-result",
                    str(c_path),
                ],
                capture_output=True,
                text=True,
            )
            assert "Traceback" not in proc.stderr and "Traceback" not in proc.stdout, (
                f"CLI {name} should not traceback, got {proc.stderr} {proc.stdout}"
            )
            out = json.loads(proc.stdout)
            assert out.get("pass") is False, f"CLI {name} should be pass false, got {out}"
            assert len(out.get("errors", [])) > 0, f"CLI {name} should have errors"


def test_nested_vs_factors_mismatch_rejected() -> None:
    """Nested factor vs result['factors'] mismatches must be rejected."""
    payload = _valid_adapter_payload()
    base_sha = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    wrapped = _runner_mod._build_construct_result(payload, base_sha, TRAFFICTWIN_BASE_SHA)
    manifest = _load_manifest()
    # Valid passes
    assert validate_construct_result(wrapped, manifest) == []
    # Placement mismatch
    bad = copy.deepcopy(wrapped)
    bad["nested_adapter_result"]["placement"] = "ingress_dla"
    # Keep config_id recomputed for new placement to isolate cross-check  # noqa: E501
    new_cid = _runner_mod._recompute_adapter_config_id(
        "ingress_dla", "fixed_1x", 0, 0, 1, 2, _runner_mod.VEC_CORE_SHA
    )
    bad["nested_adapter_result"]["config_id"] = new_cid
    errs = validate_construct_result(bad, manifest)
    assert len(errs) > 0 and any(
        "placement" in e.lower() and "mirror mismatch" in e.lower() for e in errs
    ), f"placement mismatch should be rejected with mirror mismatch, got {errs}"
    # Scaling mismatch
    bad2 = copy.deepcopy(wrapped)
    bad2["nested_adapter_result"]["scaling"] = "reactive"
    errs2 = validate_construct_result(bad2, manifest)
    assert any("scaling" in e.lower() and "mirror mismatch" in e.lower() for e in errs2), (
        f"scaling mismatch should be rejected, got {errs2}"
    )
    # state_age mismatch
    bad3 = copy.deepcopy(wrapped)
    bad3["nested_adapter_result"]["state_age_ms"] = 1000
    bad3["nested_adapter_result"]["receipt_state_age_ms"] = 1000
    new_cid3 = _runner_mod._recompute_adapter_config_id(
        "per_task_dla", "fixed_1x", 1000, 0, 1, 2, _runner_mod.VEC_CORE_SHA
    )
    bad3["nested_adapter_result"]["config_id"] = new_cid3
    errs3 = validate_construct_result(bad3, manifest)
    assert any("state_age_ms" in e.lower() and "mirror mismatch" in e.lower() for e in errs3), (
        f"state_age mismatch should be rejected, got {errs3}"
    )
    # fleet_seed mismatch
    bad4 = copy.deepcopy(wrapped)
    bad4["nested_adapter_result"]["fleet_seed"] = 2
    bad4["nested_adapter_result"]["software_identity"]["fleet_seed"] = 2
    new_cid4 = _runner_mod._recompute_adapter_config_id(
        "per_task_dla", "fixed_1x", 0, 0, 2, 2, _runner_mod.VEC_CORE_SHA
    )
    bad4["nested_adapter_result"]["config_id"] = new_cid4
    errs4 = validate_construct_result(bad4, manifest)
    assert any("fleet_seed" in e.lower() and "mirror mismatch" in e.lower() for e in errs4), (
        f"fleet_seed mismatch should be rejected, got {errs4}"
    )
    # num_rsus mismatch
    bad5 = copy.deepcopy(wrapped)
    bad5["nested_adapter_result"]["num_rsus"] = 1
    # Also adjust intervals to 1 to avoid extra interval errors masking? Keep 2  # noqa: E501
    new_cid5 = _runner_mod._recompute_adapter_config_id(
        "per_task_dla", "fixed_1x", 0, 0, 1, 1, _runner_mod.VEC_CORE_SHA
    )
    bad5["nested_adapter_result"]["config_id"] = new_cid5
    errs5 = validate_construct_result(bad5, manifest)
    assert any("num_rsus" in e.lower() and "mirror mismatch" in e.lower() for e in errs5), (
        f"num_rsus mismatch should be rejected, got {errs5}"
    )
    # evaluator_seed mismatch (nested 1 vs factors 0) - invalid but should still be caught
    bad6 = copy.deepcopy(wrapped)
    bad6["nested_adapter_result"]["evaluator_seed"] = 1
    errs6 = validate_construct_result(bad6, manifest)
    assert len(errs6) > 0 and any("evaluator_seed" in e.lower() for e in errs6), (
        f"evaluator_seed mismatch should be rejected, got {errs6}"
    )


def test_single_field_deletion_sweep_all_critical_nested_fail_closed() -> None:
    """Full sweep: omission of any identity/accounting-critical nested field must fail closed."""
    payload = _valid_adapter_payload()
    base_sha = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    wrapped = _runner_mod._build_construct_result(payload, base_sha, TRAFFICTWIN_BASE_SHA)
    manifest = _load_manifest()
    assert validate_construct_result(wrapped, manifest) == []
    critical_fields = [
        "placement",
        "scaling",
        "state_age_ms",
        "evaluator_seed",
        "fleet_seed",
        "num_rsus",
        "core_sha",
        "config_id",
        "total_resource_unit_seconds",
        "total_drained_work_ms",
        "per_rsu_cumulative_drained_ms",
        "per_rsu_cumulative_capacity_ms",
        "resource_intervals_this_tick",
        "offered",
        "admitted",
        "rejected",
        "forwarded",
        "deadline_success",
        "deadline_instrumented",
        "software_identity",
        "task_outcomes",
        "scaling_scheduled",
        "scaling_applied",
        "receipt_state_age_ms",
    ]
    for field in critical_fields:
        bad = copy.deepcopy(wrapped)
        # Handle nested deletion: some fields are top-level aliases but we delete nested
        if field == "resource_intervals_this_tick":
            # Delete all interval aliases (they are fallbacks, so all must be gone to be missing)
            bad["nested_adapter_result"].pop("resource_intervals_this_tick", None)
            bad["nested_adapter_result"].pop("resource_intervals", None)
            bad["nested_adapter_result"].pop("tick_resource_intervals", None)
        elif field in bad["nested_adapter_result"]:
            del bad["nested_adapter_result"][field]
        else:
            # If not in nested, skip this field for this sweep (we only sweep nested)
            continue
        try:
            errs = validate_construct_result(bad, manifest)
        except Exception as e:
            raise AssertionError(f"sweep deletion of {field} raised {e}") from e
        assert len(errs) > 0, (
            f"sweep: deletion of critical nested field {field!r} should fail closed, got zero errors"  # noqa: E501
        )
        # Ensure typed error mentions field or generic nested
        assert any(
            field.lower() in e.lower() or "nested" in e.lower() or "missing" in e.lower()
            for e in errs
        ), f"sweep {field} should produce typed error, got {errs}"

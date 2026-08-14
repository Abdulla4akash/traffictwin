#!/usr/bin/env python3
"""Fail-closed validator for E3 Dynamic Resource V2 manifest and construct result."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
from pathlib import Path
from typing import Any, Final, TypeGuard

_spec = importlib.util.spec_from_file_location(
    "run_e3_dynamic_resource_v2",
    Path(__file__).resolve().parent / "run_e3_dynamic_resource_v2.py",
)
if _spec is None or _spec.loader is None:
    raise ImportError("cannot load runner")
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
BLOCKED_BY_RESEARCHER_EXECUTION_HOLD = _mod.BLOCKED_BY_RESEARCHER_EXECUTION_HOLD
CONTRACT_SHA256 = _mod.CONTRACT_SHA256
CONTRACT_SCHEMA_VERSION = _mod.CONTRACT_SCHEMA_VERSION
E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED = _mod.E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED
FORBIDDEN_ABSOLUTE_PREFIXES = _mod.FORBIDDEN_ABSOLUTE_PREFIXES
MANIFEST_SCHEMA_VERSION = _mod.MANIFEST_SCHEMA_VERSION
NO_E3_RESEARCH_RESULTS_AVAILABLE = _mod.NO_E3_RESEARCH_RESULTS_AVAILABLE
NOT_EXECUTED = _mod.NOT_EXECUTED
RESULT_SCHEMA_VERSION = _mod.RESULT_SCHEMA_VERSION
RUNNER_SCHEMA_VERSION = _mod.RUNNER_SCHEMA_VERSION
SCENARIO_RSUS = _mod.SCENARIO_RSUS
TRAFFICTWIN_BASE_SHA = _mod.TRAFFICTWIN_BASE_SHA
APPROVED_CANDIDATE_SHA = _mod.APPROVED_CANDIDATE_SHA
PROMOTED_CHECKPOINT_SHA = _mod.PROMOTED_CHECKPOINT_SHA
VEC_ADAPTER_SHA = _mod.VEC_ADAPTER_SHA
VEC_CORE_SHA = _mod.VEC_CORE_SHA
VEC_PROMOTION_SHA = _mod.VEC_PROMOTION_SHA
ACTOR_SHA256 = _mod.ACTOR_SHA256
TRACE_SHA256 = _mod.TRACE_SHA256
E2D_MANIFEST_SHA256 = _mod.E2D_MANIFEST_SHA256
VEC_PROMOTED_BASE = _mod.VEC_PROMOTED_BASE
canonical_arm_id = _mod.canonical_arm_id
canonical_config_id = _mod.canonical_config_id
generate_dormant_arms = _mod.generate_dormant_arms
generate_dormant_configs = _mod.generate_dormant_configs
_collect_recursive_manifest_errors = _mod._collect_recursive_manifest_errors
_check_unauthorized_capabilities_strict = _mod._check_unauthorized_capabilities_strict
MANIFEST_TOP_LEVEL_KEYS = _mod.MANIFEST_TOP_LEVEL_KEYS
UNAUTHORIZED_REQUIRED_KEYS = _mod.UNAUTHORIZED_REQUIRED_KEYS
FORBIDDEN_MANIFEST_KEYS = _mod.FORBIDDEN_MANIFEST_KEYS
FORBIDDEN_RESULT_KEYS = _mod.FORBIDDEN_RESULT_KEYS
FORBIDDEN_SUBSTRINGS_LOWER = _mod.FORBIDDEN_SUBSTRINGS_LOWER
EXECUTION_AUTHORITY_EXPECTED: Final[dict[str, Any]] = {
    "status": E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED,
    "lane_09": BLOCKED_BY_RESEARCHER_EXECUTION_HOLD,
    "scientific_execution_authorized": False,
    "engineering_functionality_authorized": True,
    "minimal_construct_smoke_only": True,
    "manchester_trace_comparative_execution_authorized": False,
    "full_3600_step_cells_authorized": False,
    "e3a_authorized": False,
    "e3b_authorized": False,
    "e3c_authorized": False,
    "reduced_pilot_exploratory_campaign_authorized": False,
    "multi_seed_or_fleet_draw_execution_authorized": False,
    "performance_evidence_benchmark_authorized": False,
    "empirical_e3_results_authorized": False,
    "statistical_inference_authorized": False,
    "research_workloads_launched": 0,
    "evidence_state": NOT_EXECUTED,
    "result_availability": NO_E3_RESEARCH_RESULTS_AVAILABLE,
    "smoke_is_scientific_evidence": False,
    "software_completion_depends_on_experiment": False,
    "hold_release_authority": "future_explicit_researcher_instruction_only",
    "planned_56_cell_design_is_dormant_predeclaration": True,
    "dormant_predeclaration_note": (
        "The planned 56-cell design is retained only as a dormant predeclaration; "
        "planned cells are not execution authority and cannot run under this hold."
    ),
}

# Imported from runner: FORBIDDEN_MANIFEST_KEYS, FORBIDDEN_RESULT_KEYS, FORBIDDEN_SUBSTRINGS_LOWER, UNAUTHORIZED_REQUIRED_KEYS  # noqa: E501


def _compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_strict_int(v: object) -> TypeGuard[int]:
    return type(v) is int


def _is_strict_bool(v: object) -> TypeGuard[bool]:
    return type(v) is bool


def _is_finite_number(v: object) -> bool:
    if type(v) is bool:
        return False
    if not isinstance(v, (int, float)):
        return False
    return math.isfinite(float(v))


def _is_execution_authority_path(path: str) -> bool:
    return path == "manifest.execution_authority" or path == "result.execution_authority"


def _collect_recursive_errors(obj: Any, path: str, errors: list[str]) -> None:  # noqa: ANN401
    """Recursively reject forbidden keys, timestamps, private paths, actor/k8s claims."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            low_k = str(k).lower()
            # timestamp keys
            if "timestamp" in low_k or "created_utc" in low_k or "generated_at" in low_k:
                errors.append(f"forbidden timestamp key {k!r} at {path}")
            # forbidden result/claim keys exact
            if low_k in (
                "ci",
                "p_value",
                "confidence_interval",
                "benchmark_wall_seconds",
                "performance_evidence",
                "manchester_comparison",
                "inference_result",
                "results",
                "benchmark_results",
                "ci_result",
                "performance",
            ):
                errors.append(f"forbidden fabricated key {k!r} at {path}")
            # forbidden substrings in keys (kubernetes, queue ceiling, actor selects, etc)
            for substr in FORBIDDEN_SUBSTRINGS_LOWER:
                if substr in low_k:
                    errors.append(f"forbidden substring {substr!r} in key {k!r} at {path}")
            # capability key ending in _authorized must be false outside exact execution_authority
            if (
                not _is_execution_authority_path(path)
                and low_k.endswith("_authorized")
                and v is not False
            ):
                errors.append(f"unauthorized capability {k!r} not false at {path}, got {v!r}")
            _collect_recursive_errors(v, f"{path}.{k}", errors)
            # Check value if string contains forbidden absolute prefixes
            if isinstance(v, str):
                for prefix in FORBIDDEN_ABSOLUTE_PREFIXES:
                    if prefix in v:
                        errors.append(
                            f"private absolute path value {v!r} at {path}.{k} contains {prefix!r}"
                        )
                if "/private" in v or "/var/tmp" in v:  # noqa: S108
                    errors.append(f"private path value {v!r} at {path}.{k}")
                low_v = v.lower()
                for substr in FORBIDDEN_SUBSTRINGS_LOWER:
                    if substr in low_v:
                        errors.append(
                            f"forbidden substring {substr!r} in string value at {path}.{k}"
                        )
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            _collect_recursive_errors(item, f"{path}[{idx}]", errors)
            if isinstance(item, str):
                for prefix in FORBIDDEN_ABSOLUTE_PREFIXES:
                    if prefix in item:
                        errors.append(
                            f"private absolute path in list at {path}[{idx}] contains {prefix!r}"
                        )
                low_v = item.lower()
                for substr in FORBIDDEN_SUBSTRINGS_LOWER:
                    if substr in low_v:
                        errors.append(
                            f"forbidden substring {substr!r} in list string at {path}[{idx}]"
                        )
    elif isinstance(obj, str):
        for prefix in FORBIDDEN_ABSOLUTE_PREFIXES:
            if prefix in obj:
                errors.append(f"private absolute path string {obj!r} at {path} contains {prefix!r}")
        low_v = obj.lower()
        for substr in FORBIDDEN_SUBSTRINGS_LOWER:
            if substr in low_v:
                errors.append(f"forbidden substring {substr!r} at {path}")


def _load_json_bytes(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    data: dict[str, Any] = json.loads(raw.decode("utf-8"))
    return data, raw


def validate_manifest_dict(
    data: dict[str, Any],
    raw_bytes: bytes | None = None,
    sidecar_hex: str | None = None,
    sidecar_raw: str | None = None,
    manifest_filename: str | None = None,
) -> list[str]:
    errors: list[str] = []
    if set(data.keys()) != MANIFEST_TOP_LEVEL_KEYS:
        extra = set(data.keys()) - set(MANIFEST_TOP_LEVEL_KEYS)
        missing = set(MANIFEST_TOP_LEVEL_KEYS) - set(data.keys())
        errors.append(f"manifest top-level key set drift extra={extra} missing={missing}")
    # Schema version
    if data.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        errors.append(
            f"schema_version {data.get('schema_version')!r} != {MANIFEST_SCHEMA_VERSION!r}"
        )
    # Contract pin
    contract = data.get("contract")
    if not isinstance(contract, dict):
        errors.append("contract missing or not dict")
    else:
        if contract.get("sha256") != CONTRACT_SHA256:
            errors.append(f"contract sha256 {contract.get('sha256')!r} drift")
        if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
            errors.append("contract schema_version drift")
        if contract.get("path") != "docs/evaluation/e3/e3_dynamic_resource_v2_contract_v2.json":
            errors.append("contract path drift")
    # Vec runtime
    vec = data.get("vec_runtime")
    if not isinstance(vec, dict):
        errors.append("vec_runtime missing")
    else:
        if vec.get("promotion_commit") != VEC_PROMOTION_SHA:
            errors.append(f"promotion {vec.get('promotion_commit')!r} drift")
        if vec.get("core_candidate") != VEC_CORE_SHA:
            errors.append(f"core {vec.get('core_candidate')!r} drift")
        if vec.get("adapter_candidate") != VEC_ADAPTER_SHA:
            errors.append(f"adapter {vec.get('adapter_candidate')!r} drift")
    # Runner/result schema
    if data.get("runner_schema_version") != RUNNER_SCHEMA_VERSION:
        errors.append(f"runner_schema_version {data.get('runner_schema_version')!r} drift")
    if data.get("result_schema_version") != RESULT_SCHEMA_VERSION:
        errors.append(f"result_schema_version {data.get('result_schema_version')!r} drift")
    # Explicit TrafficTwin successor pins
    if data.get("approved_candidate_commit") != APPROVED_CANDIDATE_SHA:
        errors.append(
            f"approved_candidate_commit {data.get('approved_candidate_commit')!r} != {APPROVED_CANDIDATE_SHA!r}"  # noqa: E501
        )
    if data.get("promoted_checkpoint_commit") != PROMOTED_CHECKPOINT_SHA:
        errors.append(
            f"promoted_checkpoint_commit {data.get('promoted_checkpoint_commit')!r} != {PROMOTED_CHECKPOINT_SHA!r}"  # noqa: E501
        )
    ttr = data.get("traffictwin_runtime")
    if not isinstance(ttr, dict):
        errors.append("traffictwin_runtime missing")
    else:
        if ttr.get("base_commit") != PROMOTED_CHECKPOINT_SHA:
            errors.append(
                f"traffictwin_runtime.base_commit {ttr.get('base_commit')!r} != {PROMOTED_CHECKPOINT_SHA!r}"  # noqa: E501
            )
        if ttr.get("base_commit") != TRAFFICTWIN_BASE_SHA:
            errors.append(
                f"traffictwin_runtime.base_commit {ttr.get('base_commit')!r} != traffictwin base {TRAFFICTWIN_BASE_SHA!r}"  # noqa: E501
            )
    # Execution authority exact key set and values
    auth = data.get("execution_authority")
    if not isinstance(auth, dict):
        errors.append("execution_authority missing")
    else:
        if set(auth.keys()) != set(EXECUTION_AUTHORITY_EXPECTED.keys()):
            extra = set(auth.keys()) - set(EXECUTION_AUTHORITY_EXPECTED.keys())
            missing = set(EXECUTION_AUTHORITY_EXPECTED.keys()) - set(auth.keys())
            errors.append(f"execution_authority key set drift extra={extra} missing={missing}")
        for k, v in EXECUTION_AUTHORITY_EXPECTED.items():
            got = auth.get(k)
            if got != v or type(got) is not type(v):
                errors.append(f"auth {k!r} {got!r} != {v!r} (strict type)")
        if (
            auth.get("research_workloads_launched") != 0
            or type(auth.get("research_workloads_launched")) is not int
        ):
            errors.append("research_workloads_launched nonzero")
        if auth.get("scientific_execution_authorized") is not False:
            errors.append("scientific_execution_authorized not false")
    # Factors
    factors = data.get("factors")
    if not isinstance(factors, dict):
        errors.append("factors missing")
    else:
        if factors.get("evaluator_seed") != 0:
            errors.append("factors evaluator_seed drift")
        if tuple(factors.get("fleet_seeds", [])) != (1, 2, 3, 4):
            errors.append("fleet_seeds drift")
        if factors.get("scenario_rsus") != SCENARIO_RSUS:
            errors.append("scenario_rsus drift")
    # Dormant arms/configs
    arms = data.get("dormant_arms")
    configs = data.get("dormant_configs")
    if not isinstance(arms, list) or len(arms) != 14:
        errors.append(f"dormant_arms count {len(arms) if isinstance(arms, list) else 'bad'} !=14")
    else:
        try:
            expected_arms = generate_dormant_arms()
            if arms != expected_arms:
                errors.append("dormant_arms ordering/identity drift")
        except Exception as e:
            errors.append(f"arm generation failed: {e}")
        if len({a.get("arm_id") for a in arms}) != 14:
            errors.append("duplicate arm_id")
        for a in arms:
            if not isinstance(a, dict):
                errors.append("arm not dict")
                continue
            try:
                exp = canonical_arm_id(
                    str(a["placement"]), str(a["scaling"]), int(a["state_age_ms"])
                )
                if a.get("arm_id") != exp:
                    errors.append(f"arm_id {a.get('arm_id')!r} != canonical {exp!r}")
            except Exception as e:
                errors.append(f"arm_id validation failed: {e}")
    if not isinstance(configs, list) or len(configs) != 56:
        errors.append(
            f"dormant_configs count {len(configs) if isinstance(configs, list) else 'bad'} !=56"
        )
    else:
        try:
            expected_configs = generate_dormant_configs()
            if configs != expected_configs:
                errors.append("dormant_configs ordering/identity drift")
        except Exception as e:
            errors.append(f"config generation failed: {e}")
        if len({c.get("config_id") for c in configs}) != 56:
            errors.append("duplicate config_id")
        for c in configs:
            if not isinstance(c, dict):
                errors.append("config not dict")
                continue
            try:
                exp = canonical_config_id(
                    str(c["placement"]),
                    str(c["scaling"]),
                    int(c["state_age_ms"]),
                    int(c["evaluator_seed"]),
                    int(c["fleet_seed"]),
                    int(c["num_rsus"]),
                )
                if c.get("config_id") != exp:
                    errors.append(f"config_id {c.get('config_id')!r} != canonical {exp!r}")
                if c.get("arm_id") != canonical_arm_id(
                    str(c["placement"]), str(c["scaling"]), int(c["state_age_ms"])
                ):
                    errors.append(f"config arm_id mismatch for {c.get('config_id')}")
            except Exception as e:
                errors.append(f"config_id validation failed: {e}")
        count_fixed = sum(
            1
            for c in configs
            if c.get("placement") == "per_task_dla"
            and c.get("scaling") == "fixed_1x"
            and c.get("state_age_ms") == 0
        )
        if count_fixed != 4:
            errors.append(f"overlap proof failed count_fixed {count_fixed} !=4")
    # Authorized lists: must exist, are lists, and are empty (require, not merely check-if-present)
    for key in ("authorized_execution_config_ids", "authorized_cells", "authorized_runs"):
        if key not in data:
            errors.append(f"{key} missing, must be empty list")
        else:
            val = data.get(key)
            if not isinstance(val, list):
                errors.append(f"{key} must be list, got {type(val).__name__}")
            elif len(val) != 0:
                errors.append(f"{key} must be empty, got {val!r}")
    # Unauthorized capabilities: every exact key must exist and be false, no additional _authorized true  # noqa: E501
    unauth = data.get("unauthorized_capabilities")
    if not isinstance(unauth, dict):
        errors.append("unauthorized_capabilities missing")
    else:
        strict_errs = _check_unauthorized_capabilities_strict(unauth)
        errors.extend(strict_errs)
        # Also enforce no additional _authorized true anywhere via recursive check already, but keep explicit  # noqa: E501
        for k, v in unauth.items():
            if k.endswith("_authorized") and v is not False:
                errors.append(f"unauthorized {k} not false at top, got {v!r}")
            if k.endswith("_authorized") and type(v) is not bool:
                errors.append(f"unauthorized {k} must be strict bool false, got {type(v).__name__}")
    # Forbidden keys at top but also need recursive check later
    for fk in FORBIDDEN_MANIFEST_KEYS:
        if fk in data:
            errors.append(f"manifest contains fabricated key {fk!r}")
    # Private absolute paths - check dumped and also recursive values will be checked later
    dumped = json.dumps(data)
    for prefix in FORBIDDEN_ABSOLUTE_PREFIXES:
        if prefix in dumped:
            errors.append(f"manifest contains forbidden absolute prefix {prefix!r}")
    if "/private" in dumped or "/var/tmp" in dumped:  # noqa: S108
        errors.append("manifest contains private path")
    # Non-deterministic timestamp keys at top
    for k in data:
        low = k.lower()
        if "timestamp" in low or "created_utc" in low or "generated_at" in low:
            errors.append(f"manifest contains timestamp key {k!r}")
    # Queue/compute conflation, actor selection, kubernetes in dumped lower
    lower = dumped.lower()
    for substr in FORBIDDEN_SUBSTRINGS_LOWER:
        if substr in lower:
            errors.append(f"manifest contains forbidden substring {substr!r}")
    # Canonical bytes and sidecar exact content checks
    if raw_bytes is not None:
        canonical = (
            json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
        )
        if raw_bytes != canonical:
            if raw_bytes.rstrip(b"\n") != canonical.rstrip(b"\n"):
                errors.append("manifest not canonical sorted/indented")
            else:
                errors.append("manifest byte drift vs canonical")
        if sidecar_hex is not None:
            computed = _compute_sha256(raw_bytes)
            if sidecar_hex != computed:
                errors.append(f"sidecar mismatch {sidecar_hex!r} vs {computed!r}")
        if sidecar_raw is not None and manifest_filename is not None:
            computed = _compute_sha256(raw_bytes)
            expected_sidecar = f"{computed}  {manifest_filename}\n"
            if sidecar_raw != expected_sidecar:
                errors.append(
                    f"sidecar exact content mismatch {sidecar_raw!r} != {expected_sidecar!r}"
                )
    # Scientific authorization double check
    if data.get("execution_authority", {}).get("scientific_execution_authorized") is True:
        errors.append("scientific authorized must be false")
    if data.get("execution_authority", {}).get("research_workloads_launched") != 0:
        errors.append("workloads nonzero")
    # Recursive forbidden check at any nesting depth (both helpers for parity)
    _collect_recursive_errors(data, "manifest", errors)
    # Also use shared runner helper to enforce _authorized parity
    _collect_recursive_manifest_errors(data, "manifest", errors)
    return errors


def validate_manifest_file(manifest_path: Path, sidecar_path: Path) -> list[str]:
    errors: list[str] = []
    if not manifest_path.is_file():
        return [f"manifest missing: {manifest_path}"]
    if not sidecar_path.is_file():
        return [f"sidecar missing: {sidecar_path}"]
    raw = manifest_path.read_bytes()
    # Exact sidecar content check: <64 lower hex><two spaces><manifest filename>\n
    sidecar_raw = sidecar_path.read_text(encoding="utf-8")
    computed = _compute_sha256(raw)
    expected = f"{computed}  {manifest_path.name}\n"
    if sidecar_raw != expected:
        errors.append(f"sidecar exact content mismatch {sidecar_raw!r} != {expected!r}")
        # Also provide mismatch if hex differs
        first_token = sidecar_raw.strip().split()[0] if sidecar_raw.strip() else ""
        if first_token != computed:
            errors.append(f"sidecar mismatch {first_token!r} vs {computed!r}")
        return errors
    sidecar_hex = computed
    try:
        data: dict[str, Any] = json.loads(raw.decode("utf-8"))
    except Exception as e:
        return [f"manifest JSON parse failed: {e}"]
    errs = validate_manifest_dict(
        data,
        raw_bytes=raw,
        sidecar_hex=sidecar_hex,
        sidecar_raw=sidecar_raw,
        manifest_filename=manifest_path.name,
    )
    errors.extend(errs)
    return errors


def validate_construct_result(
    result: dict[str, Any],
    manifest_data: dict[str, Any] | None = None,
    export_path: Path | None = None,
    export_canonical: str | None = None,
) -> list[str]:
    errors: list[str] = []
    # Schema versions - exact
    if result.get("schema_version") != RESULT_SCHEMA_VERSION:
        errors.append(
            f"result schema_version {result.get('schema_version')!r} != {RESULT_SCHEMA_VERSION!r}"
        )
    if result.get("runner_schema_version") != RUNNER_SCHEMA_VERSION:
        errors.append(
            f"runner_schema_version {result.get('runner_schema_version')!r} != {RUNNER_SCHEMA_VERSION!r}"  # noqa: E501
        )
    if result.get("result_schema_version") != RESULT_SCHEMA_VERSION:
        errors.append(
            f"result_schema_version {result.get('result_schema_version')!r} != {RESULT_SCHEMA_VERSION!r}"  # noqa: E501
        )
    # Manifest hash exact
    manifest_sha = result.get("manifest_sha256")
    if (
        not isinstance(manifest_sha, str)
        or len(manifest_sha) != 64
        or not re.fullmatch(r"[0-9a-f]{64}", manifest_sha)
    ):
        errors.append(f"manifest_sha256 invalid {manifest_sha!r}")
    else:
        if manifest_data is not None:
            canonical_manifest = (
                json.dumps(manifest_data, sort_keys=True, indent=2, ensure_ascii=False).encode(
                    "utf-8"
                )
                + b"\n"
            )
            expected_manifest = _compute_sha256(canonical_manifest)
            if manifest_sha != expected_manifest:
                errors.append(f"manifest_sha mismatch {manifest_sha!r} vs {expected_manifest!r}")
    # TrafficTwin SHA
    tt_sha = result.get("traffictwin_git_sha")
    if (
        not isinstance(tt_sha, str)
        or len(tt_sha) != 40
        or not re.fullmatch(r"[0-9a-f]{40}", tt_sha)
    ):
        errors.append(f"traffictwin_git_sha invalid {tt_sha!r}")
    # Vec runtime
    vec = result.get("vec_runtime")
    if not isinstance(vec, dict):
        errors.append("vec_runtime missing")
    else:
        if vec.get("promotion_commit") != VEC_PROMOTION_SHA:
            errors.append("vec promotion drift")
        if vec.get("core_candidate") != VEC_CORE_SHA:
            errors.append("vec core drift")
        if vec.get("adapter_candidate") != VEC_ADAPTER_SHA:
            errors.append("vec adapter drift")
    # Execution authority/hold exact key set and values
    auth = result.get("execution_authority")
    if not isinstance(auth, dict):
        errors.append("execution_authority missing in result")
    else:
        if set(auth.keys()) != set(EXECUTION_AUTHORITY_EXPECTED.keys()):
            extra = set(auth.keys()) - set(EXECUTION_AUTHORITY_EXPECTED.keys())
            missing = set(EXECUTION_AUTHORITY_EXPECTED.keys()) - set(auth.keys())
            errors.append(f"result auth key set drift extra={extra} missing={missing}")
        for k, v in EXECUTION_AUTHORITY_EXPECTED.items():
            got = auth.get(k)
            if got != v or type(got) is not type(v):
                errors.append(f"result auth {k!r} {got!r} != {v!r} (strict type)")
    # Hold fields at top level
    for k in ("status", "lane_09", "evidence_state", "result_availability"):
        expected: Any = EXECUTION_AUTHORITY_EXPECTED.get(k)
        if result.get(k) != expected:
            errors.append(f"result {k} {result.get(k)!r} != {expected!r}")
    if result.get("research_workloads_launched") != 0:
        errors.append("research_workloads_launched nonzero")
    elif not _is_strict_int(result.get("research_workloads_launched")):
        errors.append("research_workloads_launched must be strict int")
    if result.get("is_construct") is not True:
        errors.append("is_construct must be true")
    if not _is_strict_bool(result.get("is_construct")):
        errors.append("is_construct must be strict bool true")
    if result.get("is_empirical") is not False:
        errors.append("is_empirical must be false")
    if result.get("is_scientific_evidence") is not False:
        errors.append("is_scientific_evidence must be false")
    if (
        result.get("construct_classification")
        != "software_construct_evidence_not_e3_research_results"
    ):
        errors.append("construct_classification drift")
    # Factors and arm/config identifiers
    factors = result.get("factors")
    if not isinstance(factors, dict):
        errors.append("factors missing")
        factors = {}
        placement = None
        scaling = None
        state_age = None
        fleet_seed = None
        num_rsus = None
        evaluator_seed = None
    else:
        placement = factors.get("placement")
        scaling = factors.get("scaling")
        state_age = factors.get("state_age_ms")
        fleet_seed = factors.get("fleet_seed")
        num_rsus = factors.get("num_rsus")
        evaluator_seed = factors.get("evaluator_seed")
        if placement not in ("ingress_dla", "per_task_dla", "p2c_dla"):
            errors.append(f"factors placement invalid {placement!r}")
        if scaling not in ("fixed_1x", "static_overprovisioned", "reactive", "proactive"):
            errors.append(f"factors scaling invalid {scaling!r}")
        if state_age not in (0, 1000, 3000):
            errors.append(f"factors state_age invalid {state_age!r}")
        elif not _is_strict_int(state_age):
            errors.append("factors state_age_ms must be strict int, rejecting bool")
        if evaluator_seed != 0:
            errors.append("evaluator_seed must be 0")
        elif not _is_strict_int(evaluator_seed):
            errors.append("evaluator_seed must be strict int")
        if fleet_seed not in (1, 2, 3, 4):
            errors.append("fleet_seed invalid")
        elif not _is_strict_int(fleet_seed):
            errors.append("fleet_seed must be strict int")
        if num_rsus not in (1, 2):
            errors.append(f"num_rsus {num_rsus!r} must be 1 or 2 for construct")
        elif not _is_strict_int(num_rsus):
            errors.append("num_rsus must be strict int")
        # Arm/config id canonical
        arm_id = result.get("arm_id")
        config_id = result.get("config_id")
        try:
            if (
                isinstance(placement, str)
                and isinstance(scaling, str)
                and _is_strict_int(state_age)
            ):
                expected_arm = canonical_arm_id(str(placement), str(scaling), int(state_age))
                if arm_id != expected_arm:
                    errors.append(f"arm_id {arm_id!r} != canonical {expected_arm!r}")
            else:
                errors.append("arm_id cannot be validated due to invalid factors")
        except Exception as e:
            errors.append(f"arm/config id validation failed: {e}")
        try:
            if (
                isinstance(placement, str)
                and isinstance(scaling, str)
                and _is_strict_int(state_age)
                and _is_strict_int(evaluator_seed)
                and _is_strict_int(fleet_seed)
                and _is_strict_int(num_rsus)
            ):
                expected_cfg = canonical_config_id(
                    str(placement),
                    str(scaling),
                    int(state_age),
                    int(evaluator_seed),
                    int(fleet_seed),
                    int(num_rsus),
                )
                if config_id != expected_cfg:
                    errors.append(f"config_id {config_id!r} != canonical {expected_cfg!r}")
            else:
                errors.append("config_id cannot be validated due to invalid factors")
        except Exception as e:
            errors.append(f"arm/config id validation failed: {e}")
        if result.get("state_age_ms") != state_age:
            errors.append("state_age_ms mismatch vs factors")
        elif not _is_strict_int(result.get("state_age_ms")):
            errors.append("state_age_ms must be strict int")
    # Nested adapter result - strict validation
    nested = result.get("nested_adapter_result")
    if not isinstance(nested, dict):
        errors.append("nested_adapter_result missing or not dict")
        nested = {}
    else:
        # Check nested identity/hold
        if nested.get("core_sha") != VEC_CORE_SHA:
            errors.append("nested core_sha drift")
        if nested.get("lane_09") != BLOCKED_BY_RESEARCHER_EXECUTION_HOLD:
            errors.append("nested lane_09 drift")
        if nested.get("status") != E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED:
            errors.append("nested status drift")
        if nested.get("evidence_state") != NOT_EXECUTED:
            errors.append("nested evidence_state drift")
        if nested.get("result_availability") != NO_E3_RESEARCH_RESULTS_AVAILABLE:
            errors.append("nested result_availability drift")
        if nested.get("research_workloads_launched") != 0:
            errors.append("nested workloads nonzero")
        elif not _is_strict_int(nested.get("research_workloads_launched")):
            errors.append("nested workloads must be strict int")
        if nested.get("schema_version") != "e3_dynamic_resource_v2_contract_v2":
            errors.append(f"nested schema_version {nested.get('schema_version')!r} drift")
        # Config ID 16-hex recomputation
        cid = nested.get("config_id")
        if not isinstance(cid, str) or not re.fullmatch(r"[0-9a-f]{16}", cid):
            errors.append(f"nested config_id invalid {cid!r}")
        else:
            try:
                placement_n = nested.get("placement")
                scaling_n = nested.get("scaling")
                age_n = nested.get("state_age_ms")
                eval_n = nested.get("evaluator_seed")
                fleet_n = nested.get("fleet_seed")
                rsus_n = nested.get("num_rsus")
                core_n = nested.get("core_sha")
                if (
                    isinstance(placement_n, str)
                    and isinstance(scaling_n, str)
                    and _is_strict_int(age_n)
                    and _is_strict_int(eval_n)
                    and _is_strict_int(fleet_n)
                    and _is_strict_int(rsus_n)
                    and isinstance(core_n, str)
                ):
                    payload = json.dumps(
                        {
                            "core_sha": core_n,
                            "evaluator_seed": eval_n,
                            "fleet_seed": fleet_n,
                            "num_rsus": rsus_n,
                            "placement": placement_n,
                            "scaling": scaling_n,
                            "state_age_ms": age_n,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    expected_cid = hashlib.sha256(payload.encode()).hexdigest()[:16]
                    if cid != expected_cid:
                        errors.append(f"nested config_id {cid!r} != recomputed {expected_cid!r}")
            except Exception as e:
                errors.append(f"nested config_id recomputation failed: {e}")
        # software_identity strict
        ident = nested.get("software_identity")
        if not isinstance(ident, dict):
            errors.append("nested software_identity missing or not dict")
        else:
            if ident.get("vec_core_candidate_sha") != VEC_CORE_SHA:
                errors.append("nested software_identity vec_core_candidate_sha drift")
            if ident.get("traffictwin_contract_head") != TRAFFICTWIN_BASE_SHA:
                errors.append("nested software_identity traffictwin_contract_head drift")
            if ident.get("vec_promoted_base") != VEC_PROMOTED_BASE:
                errors.append("software_identity vec_promoted_base drift")
            if ident.get("e2d_manifest_sha256") != E2D_MANIFEST_SHA256:
                errors.append("software_identity e2d_manifest_sha256 drift")
            if ident.get("actor_sha256") != ACTOR_SHA256:
                errors.append("software_identity actor_sha256 drift")
            if ident.get("trace_sha256") != TRACE_SHA256:
                errors.append("software_identity trace_sha256 drift")
            if ident.get("schema_version") != CONTRACT_SCHEMA_VERSION:
                errors.append("software_identity schema_version drift")
            if ident.get("evaluator_seed") != 0:
                errors.append("software_identity evaluator_seed drift")
            if (
                ident.get("fleet_seed") != fleet_seed
                if isinstance(fleet_seed, int)
                else ident.get("fleet_seed") not in (1, 2, 3, 4)
            ):
                errors.append("software_identity fleet_seed drift")
            if ident.get("fleet_draw_label") != "fleet_draw":
                errors.append("software_identity fleet_draw_label drift")
            if ident.get("traffictwin_contract_head") != TRAFFICTWIN_BASE_SHA:
                errors.append("ident traffictwin_contract_head mismatch")
        # deadline_instrumented exact true
        if nested.get("deadline_instrumented") is not True:
            errors.append("nested deadline_instrumented must be true")
        elif not _is_strict_bool(nested.get("deadline_instrumented")):
            errors.append("deadline_instrumented must be strict bool true")
        # Task counts strict int rejecting bools
        offered = nested.get("offered")
        admitted = nested.get("admitted")
        rejected = nested.get("rejected")
        forwarded = nested.get("forwarded")
        deadline_success = nested.get("deadline_success")
        for name, val in (
            ("offered", offered),
            ("admitted", admitted),
            ("rejected", rejected),
            ("forwarded", forwarded),
            ("deadline_success", deadline_success),
        ):
            if not _is_strict_int(val):
                errors.append(
                    f"nested {name} must be strict int, rejecting bool, got {val!r} type {type(val).__name__}"  # noqa: E501
                )
        if _is_strict_int(offered) and _is_strict_int(admitted) and _is_strict_int(rejected):  # noqa: E501, SIM102
            if offered != admitted + rejected:  # noqa: SIM102
                errors.append(f"nested task conservation {offered} != {admitted}+{rejected}")
            # Check valid boolean computed later
        if _is_strict_int(forwarded) and _is_strict_int(admitted):  # noqa: SIM102
            if forwarded > admitted:  # noqa: SIM102
                errors.append(f"nested forwarded {forwarded} > admitted {admitted}")
        if _is_strict_int(deadline_success) and _is_strict_int(admitted):  # noqa: SIM102
            if deadline_success > admitted:  # noqa: SIM102
                errors.append(f"nested deadline_success {deadline_success} > admitted {admitted}")
        # Exact task outcome count and reconciliation
        task_outcomes = nested.get("task_outcomes")
        if not isinstance(task_outcomes, list):
            errors.append("nested task_outcomes not list")
            task_outcomes = []
        else:
            if len(task_outcomes) != offered if _is_strict_int(offered) else False:
                errors.append(f"nested task_outcomes len {len(task_outcomes)} != offered {offered}")
            if len(task_outcomes) > 2:
                errors.append("nested task_outcomes >2")
            if len(task_outcomes) not in (1, 2):
                errors.append(
                    f"nested task_outcomes count must be 1 or 2, got {len(task_outcomes)}"
                )
            live_admitted = 0
            live_forwarded = 0
            live_deadline = 0
            for t in task_outcomes:
                if not isinstance(t, dict):
                    errors.append("task_outcome not dict")
                    continue
                admitted_flag = t.get("admitted")
                if not _is_strict_bool(admitted_flag):
                    errors.append(
                        f"task_outcome admitted must be strict bool, got {admitted_flag!r}"
                    )
                    continue
                latency = t.get("latency_ms")
                deadline = t.get("deadline_success")
                reason = t.get("latency_reason")
                forwarded_flag = t.get("forwarded")
                if not _is_strict_bool(forwarded_flag):
                    errors.append(
                        f"task_outcome forwarded must be strict bool, got {forwarded_flag!r}"
                    )
                if admitted_flag:
                    live_admitted += 1
                    if forwarded_flag is True:
                        live_forwarded += 1
                    if deadline is True:
                        live_deadline += 1
                    if (
                        latency is None
                        or type(latency) is bool
                        or not isinstance(latency, (int, float))
                    ):
                        errors.append(f"admitted missing latency {t!r}")
                    else:
                        if not math.isfinite(float(latency)):
                            errors.append(f"admitted latency not finite {t!r}")
                        if float(latency) == 0.0:
                            errors.append(f"admitted zero latency not allowed {t!r}")
                    if not _is_strict_bool(deadline):
                        errors.append(f"admitted missing bool deadline {t!r}")
                    if not isinstance(reason, str) or "computed" not in reason:
                        errors.append(f"admitted missing computed reason {t!r}")
                else:
                    if latency is not None:
                        if latency == 0 or latency == 0.0:
                            errors.append(f"rejected zero-filled latency {t!r}")
                        else:
                            errors.append(f"rejected latency must be null {t!r}")
                    if deadline is not None:
                        errors.append(f"rejected deadline must be null {t!r}")
                    if forwarded_flag is True:
                        errors.append(f"rejected forwarded must be false {t!r}")
                    if not isinstance(reason, str) or reason == "":
                        errors.append(f"rejected missing reason string {t!r}")
            if _is_strict_int(admitted) and admitted != live_admitted:
                errors.append(f"admitted {admitted} != live admitted {live_admitted}")
            if _is_strict_int(forwarded) and forwarded != live_forwarded:
                errors.append(f"forwarded {forwarded} != live forwarded {live_forwarded}")
            if _is_strict_int(deadline_success) and deadline_success != live_deadline:
                errors.append(f"deadline_success {deadline_success} != live {live_deadline}")
        # Resource intervals strict integer fields, cover each RSU exactly once for 1000ms tick, recompute sum  # noqa: E501
        intervals = (
            nested.get("resource_intervals_this_tick")
            or nested.get("resource_intervals")
            or nested.get("tick_resource_intervals")
        )
        # Initialize for fail-closed completeness when intervals absent
        num_rsus_nested: Any = nested.get("num_rsus")
        total: Any = nested.get("total_resource_unit_seconds")
        seen: set[int] = set()
        total_from_intervals = 0.0
        if not isinstance(intervals, list):
            errors.append("nested resource_intervals missing")
            intervals = []
            # Still validate total presence/type even when intervals missing
            if type(total) is bool or not isinstance(total, (int, float)):
                errors.append(
                    "nested total_resource_unit_seconds not numeric strict, rejecting bool"
                )
            else:
                if not math.isfinite(float(total)):
                    errors.append("nested total_resource_unit_seconds not finite")
                if _is_strict_int(num_rsus_nested):
                    lo = int(num_rsus_nested) * 1
                    hi = int(num_rsus_nested) * 3
                    if not (lo - 1e-9 <= float(total) <= hi + 1e-9):
                        errors.append(
                            f"nested total_resource_unit_seconds {total} out of range [{lo},{hi}] for {num_rsus_nested} RSUs"  # noqa: E501
                        )
        else:
            if _is_strict_int(num_rsus_nested) and len(intervals) != num_rsus_nested:
                errors.append(
                    f"nested resource_intervals len {len(intervals)} != num_rsus {num_rsus_nested}"
                )
            for iv in intervals:
                if not isinstance(iv, dict):
                    errors.append("interval not dict")
                    continue
                for field in ("rsu_id", "start_time_ms", "end_time_ms", "active_compute_units"):
                    if field not in iv:
                        errors.append(f"interval missing field {field!r}")
                    elif not _is_strict_int(iv[field]):
                        errors.append(
                            f"interval field {field} must be strict int, got {iv[field]!r}"
                        )
                if not all(
                    _is_strict_int(iv.get(f))
                    for f in ("rsu_id", "start_time_ms", "end_time_ms", "active_compute_units")
                ):
                    continue
                rsu = int(iv["rsu_id"])
                start = int(iv["start_time_ms"])
                end = int(iv["end_time_ms"])
                units = int(iv["active_compute_units"])
                if rsu in seen:
                    errors.append(f"duplicate rsu_id {rsu}")
                seen.add(rsu)
                if _is_strict_int(num_rsus_nested) and (rsu < 0 or rsu >= int(num_rsus_nested)):
                    errors.append(f"rsu_id {rsu} out of range for num_rsus {num_rsus_nested}")
                if start != 3000 or end != 4000:
                    errors.append(f"interval must cover 3000-4000, got {start}-{end}")
                if end - start != 1000:
                    errors.append(f"interval duration must be 1000, got {end - start}")
                if units < 1 or units > 3:
                    errors.append(f"active_compute_units {units} out of bounds 1..3")
                total_from_intervals += float(units) * ((end - start) / 1000.0)
            if _is_strict_int(num_rsus_nested):  # noqa: SIM102
                if seen != set(range(int(num_rsus_nested))):  # noqa: SIM102
                    errors.append(f"intervals must cover each RSU exactly once, got {seen}")
            if type(total) is bool or not isinstance(total, (int, float)):
                errors.append(
                    "nested total_resource_unit_seconds not numeric strict, rejecting bool"
                )
            else:
                if not math.isfinite(float(total)):
                    errors.append("nested total_resource_unit_seconds not finite")
                elif not math.isclose(float(total), total_from_intervals, rel_tol=0, abs_tol=1e-9):
                    errors.append(
                        f"nested total_resource_unit_seconds {total} != recomputed {total_from_intervals}"  # noqa: E501
                    )
                # Also check out-of-range for given RSUs (should be between num_rsus*1 and num_rsus*3)  # noqa: E501
                if _is_strict_int(num_rsus_nested):
                    lo = int(num_rsus_nested) * 1
                    hi = int(num_rsus_nested) * 3
                    if not (lo - 1e-9 <= float(total) <= hi + 1e-9):  # noqa: E501
                        errors.append(
                            f"nested total_resource_unit_seconds {total} out of range [{lo},{hi}] for {num_rsus_nested} RSUs"  # noqa: E501
                        )
        # Drained work / per-RSU cumulative accounting reconciles and finite/nonnegative
        total_drained = nested.get("total_drained_work_ms")
        if type(total_drained) is bool or not isinstance(total_drained, (int, float)):
            errors.append("nested total_drained_work_ms not numeric strict")
        else:
            if not math.isfinite(float(total_drained)) or float(total_drained) < 0:
                errors.append("nested total_drained_work_ms must be finite >=0")
        per_drained = nested.get("per_rsu_cumulative_drained_ms")
        per_cap = nested.get("per_rsu_cumulative_capacity_ms")
        if not isinstance(per_drained, dict):
            errors.append("nested per_rsu_cumulative_drained_ms not dict")
            per_drained = {}
        if not isinstance(per_cap, dict):
            errors.append("nested per_rsu_cumulative_capacity_ms not dict")
            per_cap = {}
        sum_drained = 0.0
        for k, v in per_drained.items():
            if type(v) is bool or not isinstance(v, (int, float)):
                errors.append(f"per_rsu drained for {k} must be numeric strict not bool, got {v!r}")
            elif not math.isfinite(float(v)) or float(v) < 0:
                errors.append(f"per_rsu drained for {k} must be finite >=0, got {v}")
            else:
                sum_drained += float(v)
        if isinstance(total_drained, (int, float)) and not isinstance(total_drained, bool):  # noqa: E501, SIM102
            if not math.isclose(float(total_drained), sum_drained, rel_tol=0, abs_tol=1e-9):
                errors.append(f"nested total_drained {total_drained} != sum per_rsu {sum_drained}")
        sum_cap = 0.0
        for k, v in per_cap.items():
            if type(v) is bool or not isinstance(v, (int, float)):
                errors.append(f"per_rsu capacity for {k} must be numeric strict, got {v!r}")
            elif not math.isfinite(float(v)) or float(v) < 0:
                errors.append(f"per_rsu capacity for {k} must be finite >=0, got {v}")
            else:
                sum_cap += float(v)
        if isinstance(total, (int, float)) and not isinstance(total, bool):
            expected_cap = float(total) * 1000.0
            if not math.isclose(sum_cap, expected_cap, rel_tol=0, abs_tol=1e-9):
                errors.append(f"nested per_rsu capacity sum {sum_cap} != total*1000 {expected_cap}")
        # Per-RSU exact string key set for RSUs 0..n-1, capacity per RSU reconciles to interval, utilization reconciles  # noqa: E501
        if _is_strict_int(num_rsus_nested):
            expected_keys = {str(i) for i in range(int(num_rsus_nested))}
            if set(per_drained.keys()) != expected_keys:
                errors.append(
                    f"per_rsu drained keys {set(per_drained.keys())!r} != expected {expected_keys!r}"  # noqa: E501
                )
            if set(per_cap.keys()) != expected_keys:
                errors.append(
                    f"per_rsu capacity keys {set(per_cap.keys())!r} != expected {expected_keys!r}"
                )
            interval_map: dict[int, int] = {}
            if isinstance(intervals, list):
                for iv in intervals:
                    if (
                        isinstance(iv, dict)
                        and _is_strict_int(iv.get("rsu_id"))
                        and _is_strict_int(iv.get("active_compute_units"))
                    ):
                        interval_map[int(iv["rsu_id"])] = int(iv["active_compute_units"])
            for rsu_str in expected_keys:
                cap_val = per_cap.get(rsu_str)
                if isinstance(cap_val, (int, float)) and not isinstance(cap_val, bool):
                    rsu_int = int(rsu_str)
                    expected_units = interval_map.get(rsu_int)
                    if expected_units is not None:
                        expected_cap_ms = float(expected_units) * 1000.0
                        if not math.isclose(
                            float(cap_val), expected_cap_ms, rel_tol=0, abs_tol=1e-9
                        ):
                            errors.append(
                                f"per_rsu capacity for {rsu_str} {cap_val} != interval units {expected_units}*1000 {expected_cap_ms}"  # noqa: E501
                            )
            util = nested.get("utilization")
            if util is not None:
                if not isinstance(util, dict):
                    errors.append("nested utilization not dict")
                else:
                    if set(util.keys()) != expected_keys:
                        errors.append(
                            f"utilization keys {set(util.keys())!r} != expected {expected_keys!r}"
                        )
                    for rsu_str in expected_keys:
                        util_val = util.get(rsu_str)
                        if util_val is not None:
                            if type(util_val) is bool or not isinstance(util_val, (int, float)):
                                errors.append(f"utilization for {rsu_str} must be numeric not bool")
                            elif (
                                not math.isfinite(float(util_val))
                                or float(util_val) < 0
                                or float(util_val) > 1 + 1e-9
                            ):
                                errors.append(f"utilization for {rsu_str} out of [0,1]")
                            else:
                                cap = per_cap.get(rsu_str)
                                drained = per_drained.get(rsu_str)
                                if (
                                    isinstance(cap, (int, float))
                                    and isinstance(drained, (int, float))
                                    and not isinstance(cap, bool)
                                    and not isinstance(drained, bool)
                                ):
                                    if float(cap) == 0:
                                        if float(util_val) != 0:
                                            errors.append(
                                                f"utilization for {rsu_str} nonzero but capacity zero"  # noqa: E501
                                            )
                                    else:
                                        expected_util = float(drained) / float(cap)
                                        if not math.isclose(
                                            float(util_val), expected_util, rel_tol=0, abs_tol=1e-9
                                        ):
                                            errors.append(
                                                f"utilization for {rsu_str} {util_val} != drained/capacity {expected_util}"  # noqa: E501
                                            )
        # Scaling receipts must exist as lists (empty valid), typed lifecycle, and applied semantics
        for key in ("scaling_scheduled", "scaling_applied"):
            lst = nested.get(key)
            if lst is None:
                errors.append(f"nested {key} missing, must be list")
                continue
            if not isinstance(lst, list):
                errors.append(f"nested {key} not list")
                continue
            for item in lst:
                if not isinstance(item, dict):
                    errors.append(f"{key} item not dict")
                    continue
                for field in (
                    "rsu_id",
                    "direction",
                    "decision_time_ms",
                    "due_time_ms",
                    "before_units",
                    "after_units",
                    "target_units",
                    "reason",
                    "applied",
                    "action_id",
                ):
                    if field not in item:
                        errors.append(f"{key} item missing {field!r}")
                if "rsu_id" in item and not _is_strict_int(item["rsu_id"]):
                    errors.append(f"{key} rsu_id must be strict int")
                if item.get("direction") not in ("scale_up", "scale_down"):
                    errors.append(f"{key} direction invalid {item.get('direction')!r}")
                if "decision_time_ms" in item and not _is_strict_int(item["decision_time_ms"]):
                    errors.append(f"{key} decision_time_ms must be strict int")
                if "due_time_ms" in item and not _is_strict_int(item["due_time_ms"]):
                    errors.append(f"{key} due_time_ms must be strict int")
                if _is_strict_int(item.get("decision_time_ms")) and _is_strict_int(  # noqa: SIM102
                    item.get("due_time_ms")
                ):
                    if item["due_time_ms"] != item["decision_time_ms"] + 2000:
                        errors.append(
                            f"{key} due {item['due_time_ms']} != decision+2000 {item['decision_time_ms'] + 2000}"  # noqa: E501
                        )
                before = item.get("before_units")
                after = item.get("after_units")
                target = item.get("target_units")
                if (
                    not _is_strict_int(before)
                    or not _is_strict_int(after)
                    or not _is_strict_int(target)
                ):
                    errors.append(f"{key} units must be strict int")
                else:
                    direction = item.get("direction")
                    if direction == "scale_up":
                        if after != before + 1 or target != after:
                            errors.append(
                                f"{key} scale_up before/after/target inconsistent {before}->{after} target {target}"  # noqa: E501
                            )
                    elif direction == "scale_down":  # noqa: SIM102
                        if after != before - 1 or target != after:
                            errors.append(
                                f"{key} scale_down before/after/target inconsistent {before}->{after} target {target}"  # noqa: E501
                            )
                if "applied" in item and not _is_strict_bool(item["applied"]):
                    errors.append(f"{key} applied must be strict bool")
                # Scaling applied semantics: scheduled must be false, applied must be true for nonempty  # noqa: E501
                if key == "scaling_scheduled" and item.get("applied") is True:
                    errors.append(f"{key} item applied must be false for scheduled, got true")
                if key == "scaling_applied" and item.get("applied") is False:
                    errors.append(f"{key} item applied must be true for applied, got false")
                applied_time = item.get("applied_time_ms")
                if item.get("applied") is True:
                    if not _is_strict_int(applied_time):
                        errors.append(f"{key} applied_time_ms must be strict int when applied")
                    elif applied_time != item.get("due_time_ms"):
                        errors.append(f"{key} applied_time_ms must equal due when applied")
                elif item.get("applied") is False:  # noqa: SIM102
                    if applied_time is not None:
                        errors.append(f"{key} applied_time_ms must be null when not applied")
                sa = item.get("state_age_ms")
                if sa is not None:
                    if not _is_strict_int(sa):
                        errors.append(f"{key} state_age_ms must be strict int")
                    elif _is_strict_int(nested.get("receipt_state_age_ms")) and sa != nested.get(
                        "receipt_state_age_ms"
                    ):
                        errors.append(
                            f"{key} state_age_ms {sa} != receipt_state_age {nested.get('receipt_state_age_ms')}"  # noqa: E501
                        )
                if not isinstance(item.get("reason"), str) or item.get("reason") == "":
                    errors.append(f"{key} reason must be non-empty string")
                if not isinstance(item.get("action_id"), str) or item.get("action_id") == "":
                    errors.append(f"{key} action_id must be non-empty string")
        # receipt_state_age equals factor/top-level state age will be checked below
    # Top-level task_outcomes, resource_intervals and scaling receipt arrays byte/value mirror nested  # noqa: E501
    task_outcomes_top = result.get("task_outcomes")
    if task_outcomes_top is not None:
        if not isinstance(task_outcomes_top, list):
            errors.append("task_outcomes not list")
        elif isinstance(nested, dict):
            nested_tasks = nested.get("task_outcomes")
            if task_outcomes_top != nested_tasks:
                errors.append("task_outcomes mirror mismatch: top-level != nested")
        if isinstance(task_outcomes_top, list) and len(task_outcomes_top) > 2:
            errors.append("task_outcomes >2")
    else:
        if isinstance(nested, dict) and nested.get("task_outcomes") is not None:
            errors.append("task_outcomes missing top-level but nested exists, mirror failed")
    ri = result.get("resource_intervals")
    if ri is not None:
        if not isinstance(ri, list):
            errors.append("resource_intervals not list")
        elif isinstance(nested, dict):
            nested_intervals_any = (
                nested.get("resource_intervals_this_tick")
                or nested.get("resource_intervals")
                or nested.get("tick_resource_intervals")
            )
            if ri != nested_intervals_any:
                errors.append("resource_intervals mirror mismatch: top-level != nested")
        # Also check strict ints for top-level intervals? Already checked nested but also need top-level strict validation  # noqa: E501
        for iv in ri if isinstance(ri, list) else []:
            if not isinstance(iv, dict):
                errors.append("top resource interval not dict")
                continue
            for field in ("rsu_id", "start_time_ms", "end_time_ms", "active_compute_units"):
                if field not in iv:
                    errors.append(f"top interval missing {field}")
                elif not _is_strict_int(iv[field]):
                    errors.append(f"top interval {field} must be strict int")
    else:
        if isinstance(nested, dict) and (
            nested.get("resource_intervals_this_tick") is not None
            or nested.get("resource_intervals") is not None
        ):
            errors.append("resource_intervals missing top-level, mirror failed")
    sac = result.get("scaling_action_receipts")
    if not isinstance(sac, dict):
        errors.append("scaling_action_receipts missing or not dict")
    else:
        expected_sac_keys = {"scheduled", "applied"}
        if set(sac.keys()) != expected_sac_keys:
            errors.append(
                f"scaling_action_receipts must have exactly {expected_sac_keys}, got {set(sac.keys())}"  # noqa: E501
            )
        for k in ("scheduled", "applied"):
            if k not in sac:
                errors.append(f"scaling_action_receipts {k} missing, must be list")
            elif not isinstance(sac[k], list):
                errors.append(f"scaling_action_receipts {k} not list")
            elif isinstance(nested, dict):
                nested_key = "scaling_scheduled" if k == "scheduled" else "scaling_applied"
                nested_val = nested.get(nested_key)
                if nested_val is None:
                    errors.append(f"nested {nested_key} missing, cannot mirror scaling {k}")
                elif not isinstance(nested_val, list):
                    errors.append(f"nested {nested_key} not list for mirror")
                elif sac[k] != nested_val:
                    errors.append(f"scaling_action_receipts {k} mirror mismatch")
    # Task conservation exact typed summary
    tc = result.get("task_conservation")
    if not isinstance(tc, dict):
        errors.append("task_conservation missing or not dict")
    else:
        required_tc_keys = {
            "offered",
            "admitted",
            "rejected",
            "forwarded",
            "deadline_success",
            "valid",
        }
        if set(tc.keys()) != required_tc_keys:
            missing = required_tc_keys - set(tc.keys())
            extra = set(tc.keys()) - required_tc_keys
            if missing:
                errors.append(f"task_conservation missing keys {missing}")
            if extra:
                errors.append(f"task_conservation extra keys {extra}")
        valid_flag = tc.get("valid")
        if not _is_strict_bool(valid_flag):
            errors.append("task_conservation valid must be strict bool")
        for name in ("offered", "admitted", "rejected", "forwarded", "deadline_success"):
            if name not in tc:
                errors.append(f"task_conservation {name} missing")
            elif not _is_strict_int(tc[name]):
                errors.append(f"task_conservation {name} must be strict int, got {tc[name]!r}")
        if all(_is_strict_int(tc.get(n)) for n in ("offered", "admitted", "rejected")):
            offered_t = tc["offered"]
            admitted_t = tc["admitted"]
            rejected_t = tc["rejected"]
            expected_valid = offered_t == admitted_t + rejected_t
            if valid_flag != expected_valid:
                errors.append(
                    f"task_conservation valid {valid_flag!r} != computed {expected_valid} for {offered_t}=={admitted_t}+{rejected_t}"  # noqa: E501
                )
            if offered_t != admitted_t + rejected_t:
                errors.append("task_conservation failed conservation")
        if isinstance(nested, dict):
            for name in ("offered", "admitted", "rejected", "forwarded", "deadline_success"):
                if tc.get(name) != nested.get(name):
                    errors.append(
                        f"task_conservation {name} {tc.get(name)!r} != nested {nested.get(name)!r} mirror mismatch"  # noqa: E501
                    )
    rc = result.get("resource_conservation")
    if not isinstance(rc, dict):
        errors.append("resource_conservation missing or not dict")
    else:
        required_rc_keys = {"per_rsu_intervals", "total_resource_unit_seconds", "valid"}
        if set(rc.keys()) != required_rc_keys:
            missing = required_rc_keys - set(rc.keys())
            extra = set(rc.keys()) - required_rc_keys
            if missing:
                errors.append(f"resource_conservation missing keys {missing}")
            if extra:
                errors.append(f"resource_conservation extra keys {extra}")
        valid_rc = rc.get("valid")
        if not _is_strict_bool(valid_rc):
            errors.append("resource_conservation valid must be strict bool")
        per_intervals = rc.get("per_rsu_intervals")
        if per_intervals is None:
            errors.append("resource_conservation per_rsu_intervals missing")
        elif not isinstance(per_intervals, list):
            errors.append("resource_conservation per_rsu_intervals not list")
        else:
            intervals_top = result.get("resource_intervals")
            nested_intervals = None
            if isinstance(nested, dict):
                nested_intervals = (
                    nested.get("resource_intervals_this_tick")
                    or nested.get("resource_intervals")
                    or nested.get("tick_resource_intervals")
                )
            if isinstance(intervals_top, list) and per_intervals != intervals_top:
                errors.append(
                    "resource_conservation per_rsu_intervals != top-level resource_intervals mirror mismatch"  # noqa: E501
                )
            if isinstance(nested_intervals, list) and per_intervals != nested_intervals:
                errors.append(
                    "resource_conservation per_rsu_intervals != nested intervals mirror mismatch"
                )
            if (
                len(per_intervals) == 0
                and isinstance(intervals_top, list)
                and len(intervals_top) != 0
            ):
                errors.append(
                    "resource_conservation per_rsu_intervals empty while top intervals nonempty"
                )
        total_rc = rc.get("total_resource_unit_seconds")
        if total_rc is None:
            errors.append("resource_conservation total_resource_unit_seconds missing")
        elif type(total_rc) is bool or not isinstance(total_rc, (int, float)):
            errors.append(
                "resource_conservation total_resource_unit_seconds must be numeric not bool"
            )
        elif not math.isfinite(float(total_rc)):
            errors.append("resource_conservation total_resource_unit_seconds not finite")
        else:
            top_total = result.get("total_resource_unit_seconds")
            nested_total = (
                nested.get("total_resource_unit_seconds") if isinstance(nested, dict) else None
            )
            if isinstance(top_total, (int, float)) and not isinstance(top_total, bool):
                if not math.isclose(float(total_rc), float(top_total), rel_tol=0, abs_tol=1e-9):
                    errors.append(
                        f"resource_conservation total_resource_unit_seconds {total_rc!r} != top-level {top_total!r} mirror mismatch"  # noqa: E501
                    )
            else:
                errors.append(
                    "top-level total_resource_unit_seconds missing or not numeric for mirror check"
                )
            if (
                isinstance(nested_total, (int, float))
                and not isinstance(nested_total, bool)
                and not math.isclose(float(total_rc), float(nested_total), rel_tol=0, abs_tol=1e-9)
            ):
                errors.append(
                    f"resource_conservation total_resource_unit_seconds {total_rc!r} != nested {nested_total!r} mirror mismatch"  # noqa: E501
                )
        intervals_top = result.get("resource_intervals")
        total_top = result.get("total_resource_unit_seconds")
        if (
            isinstance(intervals_top, list)
            and isinstance(total_top, (int, float))
            and not isinstance(total_top, bool)
        ):
            recomputed = 0.0
            ok = True
            for iv in intervals_top:
                if not isinstance(iv, dict) or not all(
                    _is_strict_int(iv.get(f))
                    for f in ("active_compute_units", "start_time_ms", "end_time_ms")
                ):
                    ok = False
                    break
                recomputed += float(iv["active_compute_units"]) * (
                    (int(iv["end_time_ms"]) - int(iv["start_time_ms"])) / 1000.0
                )
            expected_rc_valid = (
                math.isclose(float(total_top), recomputed, rel_tol=0, abs_tol=1e-9) if ok else False
            )
            if valid_rc != expected_rc_valid:
                errors.append(
                    f"resource_conservation valid {valid_rc!r} != computed {expected_rc_valid} for total {total_top} vs recomputed {recomputed}"  # noqa: E501
                )
        else:
            if valid_rc is True:
                errors.append("resource_conservation valid unconditional true without proper types")
    # Top-level total drained work and resource-unit-seconds mirror nested values
    top_drained = result.get("total_drained_work_ms")
    nested_drained = nested.get("total_drained_work_ms") if isinstance(nested, dict) else None
    if type(top_drained) is bool or not isinstance(top_drained, (int, float)):
        errors.append("top-level total_drained_work_ms missing or not numeric strict")
    elif isinstance(nested_drained, (int, float)) and not isinstance(nested_drained, bool):
        if not math.isfinite(float(top_drained)) or float(top_drained) < 0:
            errors.append("top-level total_drained_work_ms must be finite >=0")
        elif not math.isclose(float(top_drained), float(nested_drained), rel_tol=0, abs_tol=1e-9):
            errors.append(
                f"top-level total_drained_work_ms {top_drained!r} != nested {nested_drained!r} mirror mismatch"  # noqa: E501
            )
    else:
        errors.append("nested total_drained_work_ms missing for top mirror")
    top_total_rus = result.get("total_resource_unit_seconds")
    nested_total_rus2 = (
        nested.get("total_resource_unit_seconds") if isinstance(nested, dict) else None
    )
    if type(top_total_rus) is bool or not isinstance(top_total_rus, (int, float)):
        errors.append("top-level total_resource_unit_seconds missing or not numeric strict")
    elif isinstance(nested_total_rus2, (int, float)) and not isinstance(nested_total_rus2, bool):
        if not math.isfinite(float(top_total_rus)):
            errors.append("top-level total_resource_unit_seconds not finite")
        elif not math.isclose(
            float(top_total_rus), float(nested_total_rus2), rel_tol=0, abs_tol=1e-9
        ):
            errors.append(
                f"top-level total_resource_unit_seconds {top_total_rus!r} != nested {nested_total_rus2!r} mirror mismatch"  # noqa: E501
            )
    else:
        errors.append("nested total_resource_unit_seconds missing for top mirror")
    # Receipt state age remains required, strict, and reconciled
    receipt_age_nested = nested.get("receipt_state_age_ms") if isinstance(nested, dict) else None
    top_state_age = result.get("state_age_ms")
    factors_age = factors.get("state_age_ms") if isinstance(factors, dict) else None
    if not _is_strict_int(receipt_age_nested):
        errors.append("receipt_state_age_ms must be strict int")
    if not _is_strict_int(top_state_age):
        errors.append("top state_age_ms must be strict int")
    if not _is_strict_int(factors_age):
        errors.append("factors state_age_ms must be strict int")
    if (
        _is_strict_int(receipt_age_nested)
        and _is_strict_int(top_state_age)
        and receipt_age_nested != top_state_age
    ):
        errors.append(
            f"receipt_state_age_ms {receipt_age_nested} != top state_age_ms {top_state_age}"
        )
    if (
        _is_strict_int(receipt_age_nested)
        and _is_strict_int(factors_age)
        and receipt_age_nested != factors_age
    ):
        errors.append(
            f"receipt_state_age_ms {receipt_age_nested} != factors state_age_ms {factors_age}"
        )
    if (
        _is_strict_int(top_state_age)
        and _is_strict_int(factors_age)
        and top_state_age != factors_age
    ):
        errors.append(f"top state_age_ms {top_state_age} != factors state_age_ms {factors_age}")
    # Private absolute paths and forbidden substrings at any nesting
    _collect_recursive_errors(result, "result", errors)
    # Fabricated result/CI/performance keys already handled recursively, but also explicit top check
    for fk in FORBIDDEN_RESULT_KEYS:
        if fk in result:
            errors.append(f"result contains fabricated key {fk!r}")
    # Non-deterministic timestamp keys at top
    for k in result:
        low = k.lower()
        if "timestamp" in low or "created_utc" in low or "generated_at" in low:
            errors.append(f"result contains timestamp key {k!r}")
    # Also check nested for timestamps via recursive already; add explicit check for top-level nested keys?  # noqa: E501
    # Export byte drift
    if export_path is not None and export_canonical is not None:
        if not export_path.is_file():
            errors.append(f"export missing: {export_path}")
        else:
            exported = export_path.read_text(encoding="utf-8")
            # Must be exactly canonical + single newline
            if exported != export_canonical + "\n":
                errors.append("export byte drift")
    if "vec_repo" in result or "python_exe" in result:
        errors.append("result contains input path key")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate E3 manifest and optional construct result"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("docs/evaluation/e3/e3_dynamic_resource_v2_manifest_v1.json"),
    )
    parser.add_argument("--sidecar", type=Path, default=None)
    parser.add_argument("--construct-result", type=Path, default=None, dest="construct_result")
    parser.add_argument("--export", type=Path, default=None, help="export path to check byte drift")
    args = parser.parse_args()
    manifest_path: Path = args.manifest
    if args.sidecar is not None:
        sidecar_path: Path = args.sidecar
    else:
        if manifest_path.suffix == ".json":
            sidecar_path = manifest_path.with_suffix(".sha256")
        else:
            sidecar_path = Path(str(manifest_path) + ".sha256")
    errors: list[str] = validate_manifest_file(manifest_path, sidecar_path)
    manifest_data: dict[str, Any] | None = None
    if not errors:
        try:
            manifest_data, _ = _load_json_bytes(manifest_path)
        except Exception:
            manifest_data = None
    if args.construct_result:
        if not args.construct_result.is_file():
            errors.append(f"construct_result missing: {args.construct_result}")
        else:
            try:
                cr_data: dict[str, Any] = json.loads(
                    args.construct_result.read_text(encoding="utf-8")
                )
            except Exception as e:
                errors.append(f"construct_result parse failed: {e}")
                cr_data = {}
            export_canonical: str | None = None
            if args.export:
                try:
                    export_canonical = json.dumps(cr_data, sort_keys=True, separators=(",", ":"))
                except Exception:
                    export_canonical = None
            cr_errors = validate_construct_result(
                cr_data, manifest_data, export_path=args.export, export_canonical=export_canonical
            )
            errors.extend(cr_errors)
    if args.export and not args.construct_result:
        errors.append("--export requires --construct-result")
    result = {"pass": len(errors) == 0, "errors": errors, "error_count": len(errors)}
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

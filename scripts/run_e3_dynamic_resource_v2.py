#!/usr/bin/env python3
"""Typed runner for E3 Dynamic Resource V2 -- frozen manifest + minimal construct."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final, TypeGuard

CONTRACT_SHA256: Final[str] = "f0d6eb913df6c2165a63ddcb0fd4980368e9bb80bbd38db964273ba3925f4870"
CONTRACT_SCHEMA_VERSION: Final[str] = "e3_dynamic_resource_v2_contract_v2"
CONTRACT_PATH: Final[str] = "docs/evaluation/e3/e3_dynamic_resource_v2_contract_v2.json"
VEC_PROMOTION_SHA: Final[str] = "dc606770059f0c4a413bac2217d7f38600b74fff"
VEC_CORE_SHA: Final[str] = "53e34db6146da40118a6c816f6a1ffaa2596ddf3"
VEC_ADAPTER_SHA: Final[str] = "c37f97ea66b236dfc662bfdd6bee7eab1a775bbc"
TRAFFICTWIN_BASE_SHA: Final[str] = "211a6662151ccad43187f8a2ce3f75a57515408d"
APPROVED_CANDIDATE_SHA: Final[str] = "ac8e410f7708188a9dd6e13e1c0311297176839d"
PROMOTED_CHECKPOINT_SHA: Final[str] = "211a6662151ccad43187f8a2ce3f75a57515408d"
MANIFEST_SCHEMA_VERSION: Final[str] = "e3_dynamic_resource_v2_manifest_v1"
RUNNER_SCHEMA_VERSION: Final[str] = "e3_dynamic_resource_v2_runner_v1"
RESULT_SCHEMA_VERSION: Final[str] = "e3_dynamic_resource_v2_construct_result_v1"
E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED: Final[str] = "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED"
BLOCKED_BY_RESEARCHER_EXECUTION_HOLD: Final[str] = "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD"
NOT_EXECUTED: Final[str] = "NOT_EXECUTED"
NO_E3_RESEARCH_RESULTS_AVAILABLE: Final[str] = "NO_E3_RESEARCH_RESULTS_AVAILABLE"

EXECUTION_AUTHORITY: Final[dict[str, Any]] = {
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

VALID_PLACEMENTS: Final[tuple[str, ...]] = ("ingress_dla", "per_task_dla", "p2c_dla")
VALID_SCALINGS: Final[tuple[str, ...]] = (
    "fixed_1x",
    "static_overprovisioned",
    "reactive",
    "proactive",
)
VALID_STATE_AGES: Final[tuple[int, ...]] = (0, 1000, 3000)
FLEET_SEEDS: Final[tuple[int, ...]] = (1, 2, 3, 4)
EVALUATOR_SEED: Final[int] = 0
SCENARIO_RSUS: Final[int] = 10

# Identity hashes for software_identity
ACTOR_SHA256: Final[str] = "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208"
TRACE_SHA256: Final[str] = "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"
E2D_MANIFEST_SHA256: Final[str] = "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740"
VEC_PROMOTED_BASE: Final[str] = "b2abcee2b4c2628e604fff0811110b8c61a22b23"

FORBIDDEN_ABSOLUTE_PREFIXES: Final[tuple[str, ...]] = (  # noqa: S108
    "/Users/",  # noqa: S108
    "/private/",  # noqa: S108
    "/tmp/",  # noqa: S108
    "/var/",  # noqa: S108
    "/etc/",  # noqa: S108
    "/home/",  # noqa: S108
)

UNAUTHORIZED_REQUIRED_KEYS: Final[tuple[str, ...]] = (
    "full_3600_step_cells_authorized",
    "ten_step_trace_smoke_authorized",
    "benchmarks_authorized",
    "pilots_authorized",
    "manchester_comparisons_authorized",
    "multi_draw_execution_authorized",
    "inference_authorized",
)

FORBIDDEN_MANIFEST_KEYS: Final[tuple[str, ...]] = (
    "results",
    "benchmark_results",
    "ci_result",
    "performance",
    "result_dir",
    "output_dir",
)

FORBIDDEN_RESULT_KEYS: Final[tuple[str, ...]] = (
    "ci",
    "p_value",
    "confidence_interval",
    "benchmark_wall_seconds",
    "performance_evidence",
    "manchester_comparison",
    "inference_result",
)

FORBIDDEN_SUBSTRINGS_LOWER: Final[tuple[str, ...]] = (
    "queue_ceiling_is_compute",
    "queue ceiling is compute",
    "queue ceiling is",
    "actor selects execution",
    "actor selects",
    "actor_selects",
    "kubernetes",
    "k8s_deployment",
)

SENTINEL_TRACE: Final[str] = "__SENTINEL_MISSING_TRACE__"
SENTINEL_ACTOR: Final[str] = "__SENTINEL_MISSING_ACTOR__"

MANIFEST_TOP_LEVEL_KEYS: Final[frozenset[str]] = frozenset(
    {
        "approved_candidate_commit",
        "authorized_cells",
        "authorized_execution_config_ids",
        "authorized_runs",
        "campaign",
        "contract",
        "dormant_arm_count",
        "dormant_arms",
        "dormant_config_count",
        "dormant_configs",
        "execution_authority",
        "factors",
        "promoted_checkpoint_commit",
        "provenance",
        "result_schema_version",
        "runner_schema_version",
        "schema_version",
        "traffictwin_runtime",
        "unauthorized_capabilities",
        "vec_runtime",
    }
)


def _is_manifest_execution_authority_path(path: str) -> bool:
    return path == "manifest.execution_authority"


def _collect_recursive_manifest_errors(obj: Any, path: str, errors: list[str]) -> None:  # noqa: E501, ANN401
    """Shared helper: recursively reject forbidden keys, timestamps, private paths, claims."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            low_k = str(k).lower()
            if "timestamp" in low_k or "created_utc" in low_k or "generated_at" in low_k:
                errors.append(f"forbidden timestamp key {k!r} at {path}")
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
            for substr in FORBIDDEN_SUBSTRINGS_LOWER:
                if substr in low_k:
                    errors.append(f"forbidden substring {substr!r} in key {k!r} at {path}")
            # capability key ending in _authorized must be false (no additional true)
            # Exclude execution_authority's documented true key; it has its own strict check
            if (
                not _is_manifest_execution_authority_path(path)
                and low_k.endswith("_authorized")
                and v is not False
            ):
                errors.append(f"unauthorized capability {k!r} not false at {path}, got {v!r}")  # noqa: E501
            _collect_recursive_manifest_errors(v, f"{path}.{k}", errors)
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
            _collect_recursive_manifest_errors(item, f"{path}[{idx}]", errors)
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


def _check_unauthorized_capabilities_strict(unauth: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    for k in UNAUTHORIZED_REQUIRED_KEYS:
        if k not in unauth:
            errs.append(f"unauthorized {k} missing, must be false")
        elif unauth[k] is not False:
            errs.append(f"unauthorized {k} must be false, got {unauth[k]!r}")
    for k, v in unauth.items():
        if k.endswith("_authorized") and v is not False:
            errs.append(f"unauthorized {k} not false, got {v!r}")
        if k.endswith("_authorized") and type(v) is not bool:
            errs.append(f"unauthorized {k} must be strict bool false, got {type(v).__name__}")
    return errs


def canonical_arm_id(placement: str, scaling: str, state_age_ms: int) -> str:
    """Deterministic arm identifier containing placement, scaling, state age ms."""
    if not isinstance(placement, str) or not isinstance(scaling, str):
        raise TypeError("placement/scaling must be str")
    if type(state_age_ms) is not int:
        raise TypeError("state_age_ms must be int")
    if placement not in VALID_PLACEMENTS:
        raise ValueError(f"invalid placement {placement!r}")
    if scaling not in VALID_SCALINGS:
        raise ValueError(f"invalid scaling {scaling!r}")
    if state_age_ms not in VALID_STATE_AGES:
        raise ValueError(f"invalid state_age_ms {state_age_ms!r}")
    return f"{placement}__{scaling}__age_{state_age_ms}ms"


def canonical_config_id(
    placement: str,
    scaling: str,
    state_age_ms: int,
    evaluator_seed: int,
    fleet_seed: int,
    num_rsus: int,
) -> str:
    """Deterministic config identifier adds evaluator, fleet, RSUs to arm id."""
    arm = canonical_arm_id(placement, scaling, state_age_ms)
    if type(evaluator_seed) is not int or type(fleet_seed) is not int or type(num_rsus) is not int:
        raise TypeError("seed/rsus must be int")
    if evaluator_seed != EVALUATOR_SEED:
        raise ValueError(f"evaluator_seed must be {EVALUATOR_SEED}")
    if fleet_seed not in FLEET_SEEDS:
        raise ValueError(f"fleet_seed must be in {FLEET_SEEDS}")
    if num_rsus not in (1, 2, SCENARIO_RSUS):
        raise ValueError(f"num_rsus {num_rsus} must be 1, 2, or {SCENARIO_RSUS}")
    return f"{arm}__eval_{evaluator_seed}__fleet_{fleet_seed}__rsus_{num_rsus}"


def _recompute_adapter_config_id(
    placement: str,
    scaling: str,
    state_age_ms: int,
    evaluator_seed: int,
    fleet_seed: int,
    num_rsus: int,
    core_sha: str,
) -> str:
    """Recompute adapter 16-hex config ID from canonical factor payload."""
    payload = json.dumps(
        {
            "core_sha": core_sha,
            "evaluator_seed": evaluator_seed,
            "fleet_seed": fleet_seed,
            "num_rsus": num_rsus,
            "placement": placement,
            "scaling": scaling,
            "state_age_ms": state_age_ms,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def generate_dormant_arms() -> list[dict[str, Any]]:
    """Exact 14 unique placement/scaling/state-age arms (no E3a/E3b duplicate)."""
    arms: list[tuple[str, str, int]] = []
    for placement in ("ingress_dla", "per_task_dla", "p2c_dla"):
        arms.append((placement, "fixed_1x", 0))
    for scaling in ("static_overprovisioned", "reactive", "proactive"):
        arms.append(("per_task_dla", scaling, 0))
    for placement in ("per_task_dla", "p2c_dla"):
        for age in (1000, 3000):
            arms.append((placement, "fixed_1x", age))
    for scaling in ("reactive", "proactive"):
        for age in (1000, 3000):
            arms.append(("per_task_dla", scaling, age))
    if len(arms) != 14:
        raise RuntimeError(f"arm count {len(arms)} !=14")
    if len(set(arms)) != 14:
        raise RuntimeError("duplicate arms")
    result: list[dict[str, Any]] = []
    for placement, scaling, age in arms:
        arm_id = canonical_arm_id(placement, scaling, age)
        result.append(
            {
                "arm_id": arm_id,
                "placement": placement,
                "scaling": scaling,
                "state_age_ms": age,
            }
        )
    result.sort(key=lambda x: str(x["arm_id"]))
    if len({r["arm_id"] for r in result}) != 14:
        raise RuntimeError("arm_id duplicate after sort")
    return result


def generate_dormant_configs() -> list[dict[str, Any]]:
    """Exact 56 dormant configs: 14 arms x 4 fleet seeds, evaluator 0, RSUs 10."""
    arms = generate_dormant_arms()
    configs: list[dict[str, Any]] = []
    for arm in arms:
        for fleet_seed in FLEET_SEEDS:
            cfg_id = canonical_config_id(
                str(arm["placement"]),
                str(arm["scaling"]),
                int(arm["state_age_ms"]),
                EVALUATOR_SEED,
                fleet_seed,
                SCENARIO_RSUS,
            )
            configs.append(
                {
                    "config_id": cfg_id,
                    "arm_id": str(arm["arm_id"]),
                    "placement": str(arm["placement"]),
                    "scaling": str(arm["scaling"]),
                    "state_age_ms": int(arm["state_age_ms"]),
                    "evaluator_seed": EVALUATOR_SEED,
                    "fleet_seed": fleet_seed,
                    "num_rsus": SCENARIO_RSUS,
                }
            )
    if len(configs) != 56:
        raise RuntimeError(f"config count {len(configs)} !=56")
    if len({c["config_id"] for c in configs}) != 56:
        raise RuntimeError("duplicate config_id")
    count_fixed = sum(
        1
        for c in configs
        if c["placement"] == "per_task_dla"
        and c["scaling"] == "fixed_1x"
        and c["state_age_ms"] == 0
    )
    if count_fixed != 4:
        raise RuntimeError(f"overlap proof failed: count {count_fixed} !=4")
    configs.sort(key=lambda x: str(x["config_id"]))
    return configs


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _manifest_paths(manifest_arg: Path | None = None) -> tuple[Path, Path]:
    root = _repo_root()
    if manifest_arg is not None:
        manifest = manifest_arg
        if manifest.suffix == ".json":
            sidecar = manifest.with_suffix(".sha256")
        else:
            sidecar = Path(str(manifest) + ".sha256")
        return manifest, sidecar
    manifest = root / "docs" / "evaluation" / "e3" / "e3_dynamic_resource_v2_manifest_v1.json"
    sidecar = manifest.with_suffix(".sha256")
    return manifest, sidecar


def _compute_sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check_git_clean(repo_path: Path, git_runner: Callable[..., Any] | None) -> None:
    runner = git_runner or subprocess.run
    proc = runner(
        ["git", "status", "--porcelain"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git status failed: {proc.stderr}")
    if proc.stdout.strip() != "":
        raise RuntimeError(f"worktree dirty: {proc.stdout[:500]!r}")


def _check_git_ancestor(
    base_sha: str, head_sha: str, repo_path: Path, git_runner: Callable[..., Any] | None
) -> None:
    runner = git_runner or subprocess.run
    proc = runner(
        ["git", "merge-base", "--is-ancestor", base_sha, head_sha],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"base {base_sha!r} not ancestor of {head_sha!r}")


def _get_traffictwin_git_sha(git_runner: Callable[..., Any] | None = None) -> str:
    runner = git_runner or subprocess.run
    root = _repo_root()
    _check_git_clean(root, git_runner)
    proc = runner(
        ["git", "rev-parse", "HEAD"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git rev-parse HEAD failed: {proc.stderr}")
    sha = proc.stdout.strip()
    if len(sha) != 40 or not all(c in "0123456789abcdef" for c in sha):
        raise RuntimeError(f"invalid git sha {sha!r}")
    _check_git_ancestor(TRAFFICTWIN_BASE_SHA, sha, root, git_runner)
    return sha


def _verify_contract_bytes() -> None:
    root = _repo_root()
    contract_path = root / CONTRACT_PATH
    if not contract_path.is_file():
        raise FileNotFoundError(f"contract missing: {contract_path}")
    data = contract_path.read_bytes()
    sha = _compute_sha256_bytes(data)
    if sha != CONTRACT_SHA256:
        raise ValueError(f"contract bytes sha {sha!r} != {CONTRACT_SHA256!r}")


def _verify_manifest(
    manifest_path: Path,
    sidecar_path: Path,
) -> tuple[dict[str, Any], str]:
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest missing: {manifest_path}")
    if not sidecar_path.is_file():
        raise FileNotFoundError(f"sidecar missing: {sidecar_path}")
    raw = manifest_path.read_bytes()
    computed = _compute_sha256_bytes(raw)
    # Strict sidecar content: 64 lower hex, two spaces, manifest filename, newline
    sidecar_raw = sidecar_path.read_text(encoding="utf-8")
    expected_sidecar = f"{computed}  {manifest_path.name}\n"
    if sidecar_raw != expected_sidecar:
        # Provide detailed mismatch
        if (sidecar_raw.strip().split()[0] if sidecar_raw.strip() else "") != computed:
            raise ValueError(f"sidecar mismatch: {sidecar_raw[:80]!r} vs {expected_sidecar[:80]!r}")
        raise ValueError(f"sidecar exact format mismatch: {sidecar_raw!r} != {expected_sidecar!r}")
    try:
        data: dict[str, Any] = json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"manifest JSON parse failed: {e}") from e
    canonical = (
        json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    )
    if raw != canonical:
        if raw.rstrip(b"\n") != canonical.rstrip(b"\n"):
            raise ValueError("manifest not canonical sorted/indented")
        if raw != canonical:
            raise ValueError("manifest byte drift vs canonical")
    if set(data.keys()) != MANIFEST_TOP_LEVEL_KEYS:
        extra = set(data.keys()) - set(MANIFEST_TOP_LEVEL_KEYS)
        missing = set(MANIFEST_TOP_LEVEL_KEYS) - set(data.keys())
        raise ValueError(f"manifest top-level key set drift extra={extra} missing={missing}")
    if data.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version {data.get('schema_version')!r} != {MANIFEST_SCHEMA_VERSION!r}"
        )
    contract = data.get("contract")
    if not isinstance(contract, dict):
        raise ValueError("contract missing")
    if contract.get("sha256") != CONTRACT_SHA256:
        raise ValueError(f"contract sha256 {contract.get('sha256')!r} != {CONTRACT_SHA256!r}")
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise ValueError("contract schema_version mismatch")
    if contract.get("path") != CONTRACT_PATH:
        raise ValueError("contract path mismatch")
    vec = data.get("vec_runtime")
    if not isinstance(vec, dict):
        raise ValueError("vec_runtime missing")
    if vec.get("promotion_commit") != VEC_PROMOTION_SHA:
        raise ValueError("vec promotion mismatch")
    if vec.get("core_candidate") != VEC_CORE_SHA:
        raise ValueError("vec core mismatch")
    if vec.get("adapter_candidate") != VEC_ADAPTER_SHA:
        raise ValueError("vec adapter mismatch")
    if data.get("runner_schema_version") != RUNNER_SCHEMA_VERSION:
        raise ValueError("runner_schema_version mismatch")
    if data.get("result_schema_version") != RESULT_SCHEMA_VERSION:
        raise ValueError("result_schema_version mismatch")
    auth = data.get("execution_authority")
    if not isinstance(auth, dict):
        raise ValueError("execution_authority missing")
    for k, v in EXECUTION_AUTHORITY.items():
        got = auth.get(k)
        if got != v or type(got) is not type(v):
            raise ValueError(f"execution_authority {k!r} mismatch: {got!r} != {v!r} (strict type)")
    # Ensure no extra hidden authority key and exact key set
    if set(auth.keys()) != set(EXECUTION_AUTHORITY.keys()):
        extra = set(auth.keys()) - set(EXECUTION_AUTHORITY.keys())
        missing = set(EXECUTION_AUTHORITY.keys()) - set(auth.keys())
        raise ValueError(f"execution_authority key set drift extra={extra} missing={missing}")
    factors = data.get("factors")
    if not isinstance(factors, dict):
        raise ValueError("factors missing")
    if factors.get("evaluator_seed") != EVALUATOR_SEED:
        raise ValueError("evaluator_seed mismatch")
    if tuple(factors.get("fleet_seeds", [])) != FLEET_SEEDS:
        raise ValueError("fleet_seeds mismatch")
    if factors.get("scenario_rsus") != SCENARIO_RSUS:
        raise ValueError("scenario_rsus mismatch")
    arms = data.get("dormant_arms")
    configs = data.get("dormant_configs")
    if not isinstance(arms, list) or len(arms) != 14:
        raise ValueError(f"dormant_arms count {len(arms) if isinstance(arms, list) else '?'} !=14")
    if not isinstance(configs, list) or len(configs) != 56:
        raise ValueError(
            f"dormant_configs count {len(configs) if isinstance(configs, list) else '?'} !=56"
        )
    expected_arms = generate_dormant_arms()
    expected_configs = generate_dormant_configs()
    if arms != expected_arms:
        raise ValueError("dormant_arms ordering/identity drift")
    if configs != expected_configs:
        raise ValueError("dormant_configs ordering/identity drift")
    if len({c["config_id"] for c in configs}) != 56:
        raise ValueError("duplicate config_id")
    # Approved candidate and promoted checkpoint pins
    if data.get("approved_candidate_commit") != APPROVED_CANDIDATE_SHA:
        raise ValueError(
            f"approved_candidate_commit {data.get('approved_candidate_commit')!r} != {APPROVED_CANDIDATE_SHA!r}"  # noqa: E501
        )
    if data.get("promoted_checkpoint_commit") != PROMOTED_CHECKPOINT_SHA:
        raise ValueError(
            f"promoted_checkpoint_commit {data.get('promoted_checkpoint_commit')!r} != {PROMOTED_CHECKPOINT_SHA!r}"  # noqa: E501
        )
    # Traffictwin runtime base_commit must equal promoted checkpoint
    ttr = data.get("traffictwin_runtime")
    if not isinstance(ttr, dict):
        raise ValueError("traffictwin_runtime missing")
    if ttr.get("base_commit") != PROMOTED_CHECKPOINT_SHA:
        raise ValueError(
            f"traffictwin_runtime.base_commit {ttr.get('base_commit')!r} != {PROMOTED_CHECKPOINT_SHA!r}"  # noqa: E501
        )
    for key in ("authorized_execution_config_ids", "authorized_cells", "authorized_runs"):
        if key not in data:
            raise ValueError(f"{key} missing, must be empty list")
        val = data.get(key)
        if not isinstance(val, list):
            raise ValueError(f"{key} must be list, got {type(val).__name__}")
        if len(val) != 0:
            raise ValueError(f"{key} must be empty list, got {val!r}")
    raw_str = raw.decode("utf-8")
    for prefix in FORBIDDEN_ABSOLUTE_PREFIXES:
        if prefix in raw_str:
            raise ValueError(f"manifest contains forbidden absolute prefix {prefix!r}")
    if "/private" in raw_str or "/var/tmp" in raw_str:  # noqa: S108
        raise ValueError("manifest contains private path")
    forbidden_keys = [
        "results",
        "benchmark_results",
        "ci_result",
        "performance",
    ]
    for fk in forbidden_keys:
        if fk in data:
            raise ValueError(f"manifest contains fabricated key {fk!r}")
    unauth = data.get("unauthorized_capabilities")
    if not isinstance(unauth, dict):
        raise ValueError("unauthorized_capabilities missing")
    unauth_errs = _check_unauthorized_capabilities_strict(unauth)
    if unauth_errs:
        raise ValueError(f"unauthorized_capabilities fail-closed: {unauth_errs[0]}")
    # Recursive rejection of forbidden claims, fabricated keys, timestamps, private paths, and capability auth  # noqa: E501
    rec_errors: list[str] = []
    _collect_recursive_manifest_errors(data, "manifest", rec_errors)
    if rec_errors:
        raise ValueError(f"manifest recursive forbidden: {rec_errors[0]}")
    for k in data:
        low = k.lower()
        if "timestamp" in low or "created_utc" in low or "generated_at" in low:
            raise ValueError(f"manifest contains timestamp key {k!r} (must be absent)")
    return data, computed


def _validate_vec_runtime(
    vec_repo: Path,
    python_exe: Path,
    git_runner: Callable[..., Any] | None = None,
    python_runner: Callable[..., Any] | None = None,
) -> None:
    git_run = git_runner or subprocess.run
    py_run = python_runner or subprocess.run
    if not vec_repo.is_dir():
        raise FileNotFoundError(f"vec repo missing: {vec_repo}")
    if not python_exe.is_file():
        raise FileNotFoundError(f"python exe missing: {python_exe}")
    # Vec worktree must be clean
    _check_git_clean(vec_repo, git_runner)
    proc = git_run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(vec_repo),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git rev-parse HEAD failed: {proc.stderr}")
    head = proc.stdout.strip()
    if head != VEC_PROMOTION_SHA:
        raise ValueError(f"vec HEAD {head!r} != promotion {VEC_PROMOTION_SHA!r}")
    for candidate, label in ((VEC_CORE_SHA, "core"), (VEC_ADAPTER_SHA, "adapter")):
        proc2 = git_run(
            ["git", "merge-base", "--is-ancestor", candidate, head],
            cwd=str(vec_repo),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc2.returncode != 0:
            raise ValueError(f"vec {label} {candidate!r} not ancestor of {head!r}")
    # python version check strictly via injected runner, no fallback
    proc3 = py_run(
        [str(python_exe), "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc3.returncode != 0:
        raise ValueError(f"python exe invalid: {proc3.stderr}")
    out = (proc3.stdout + proc3.stderr).strip()
    if not re.search(r"Python 3\.\d+\.\d+", out):
        raise ValueError(f"python version not recognizable: {out!r}")


def _is_strict_int(v: object) -> TypeGuard[int]:
    return type(v) is int


def _is_finite_number(v: object) -> bool:
    if type(v) is bool:
        return False
    if not isinstance(v, (int, float)):
        return False
    return math.isfinite(float(v))


def _invoke_adapter(
    vec_repo: Path,
    python_exe: Path,
    placement: str,
    scaling: str,
    state_age_ms: int,
    fleet_seed: int,
    num_rsus: int,
    subprocess_runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    runner = subprocess_runner or subprocess.run
    if type(num_rsus) is not int or num_rsus not in (1, 2):
        raise ValueError(f"num_rsus {num_rsus} must be 1 or 2")
    if placement not in VALID_PLACEMENTS:
        raise ValueError(f"placement {placement} invalid")
    if scaling not in VALID_SCALINGS:
        raise ValueError(f"scaling {scaling} invalid")
    if state_age_ms not in VALID_STATE_AGES:
        raise ValueError(f"state_age_ms {state_age_ms} invalid")
    if fleet_seed not in FLEET_SEEDS:
        raise ValueError(f"fleet_seed {fleet_seed} invalid")
    adapter = vec_repo / "eval" / "eval_sumo_stage1_mc.py"
    if not adapter.is_file():
        raise FileNotFoundError(f"adapter missing: {adapter}")
    cmd: list[str] = [
        str(python_exe),
        str(adapter),
        "--trace",
        SENTINEL_TRACE,
        "--actor",
        SENTINEL_ACTOR,
        "--e3-mode",
        "minimal_construct",
        "--e3-placement",
        placement,
        "--e3-scaling",
        scaling,
        "--e3-state-age-ms",
        str(state_age_ms),
        "--e3-evaluator-seed",
        str(EVALUATOR_SEED),
        "--e3-fleet-seed",
        str(fleet_seed),
        "--e3-num-rsus",
        str(num_rsus),
        "--e3-core-sha",
        VEC_CORE_SHA,
    ]
    proc = runner(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"adapter exit {proc.returncode}: {proc.stderr[:500]}")
    if proc.stderr and proc.stderr.strip():
        raise ValueError(f"adapter stderr nonempty on success: {proc.stderr[:500]!r}")
    raw_out: str = proc.stdout
    if raw_out == "":
        raise ValueError("adapter stdout empty")
    if not raw_out.endswith("\n"):
        raise ValueError("adapter stdout must end with single newline")
    # Exactly one trailing newline
    if raw_out.endswith("\n\n"):
        raise ValueError("adapter stdout has extra blank trailing line")
    inner = raw_out[:-1]
    if "\n" in inner:
        raise ValueError(
            f"adapter stdout not exactly one JSON line: {inner.count(chr(10)) + 1} lines"
        )
    if inner.strip() == "":
        raise ValueError("adapter stdout empty after stripping newline")
    try:
        data: dict[str, Any] = json.loads(inner)
    except Exception as e:
        raise ValueError(f"adapter stdout not JSON: {e} raw {inner[:500]!r}") from e
    # Strict field validation
    if data.get("core_sha") != VEC_CORE_SHA:
        raise ValueError(f"adapter core_sha {data.get('core_sha')!r} drift")
    if data.get("placement") != placement:
        raise ValueError("adapter placement drift")
    if data.get("scaling") != scaling:
        raise ValueError("adapter scaling drift")
    if data.get("state_age_ms") != state_age_ms:
        raise ValueError("adapter state_age_ms drift")
    if data.get("evaluator_seed") != EVALUATOR_SEED:
        raise ValueError("adapter evaluator_seed drift")
    if data.get("fleet_seed") != fleet_seed:
        raise ValueError("adapter fleet_seed drift")
    if data.get("num_rsus") != num_rsus:
        raise ValueError("adapter num_rsus drift")
    if data.get("lane_09") != BLOCKED_BY_RESEARCHER_EXECUTION_HOLD:
        raise ValueError("adapter lane_09 drift")
    if data.get("status") != E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED:
        raise ValueError("adapter status drift")
    if data.get("evidence_state") != NOT_EXECUTED:
        raise ValueError("adapter evidence_state drift")
    if data.get("result_availability") != NO_E3_RESEARCH_RESULTS_AVAILABLE:
        raise ValueError("adapter result_availability drift")
    if data.get("research_workloads_launched") != 0:
        raise ValueError("adapter workloads nonzero")
    # Config ID recomputation
    cid = data.get("config_id")
    if not isinstance(cid, str) or len(cid) != 16 or not re.fullmatch(r"[0-9a-f]{16}", cid):
        raise ValueError(f"adapter config_id invalid {cid!r}")
    expected_cid = _recompute_adapter_config_id(
        placement, scaling, state_age_ms, EVALUATOR_SEED, fleet_seed, num_rsus, VEC_CORE_SHA
    )
    if cid != expected_cid:
        raise ValueError(f"adapter config_id {cid!r} != expected {expected_cid!r}")
    # software_identity strict validation
    ident = data.get("software_identity")
    if not isinstance(ident, dict):
        raise ValueError("software_identity missing or not dict")
    if ident.get("vec_core_candidate_sha") != VEC_CORE_SHA:
        raise ValueError("software_identity vec_core_candidate_sha drift")
    if ident.get("traffictwin_contract_head") != TRAFFICTWIN_BASE_SHA:
        raise ValueError("software_identity traffictwin_contract_head drift")
    if ident.get("vec_promoted_base") != VEC_PROMOTED_BASE:
        raise ValueError("software_identity vec_promoted_base drift")
    if ident.get("e2d_manifest_sha256") != E2D_MANIFEST_SHA256:
        raise ValueError("software_identity e2d_manifest_sha256 drift")
    if ident.get("actor_sha256") != ACTOR_SHA256:
        raise ValueError("software_identity actor_sha256 drift")
    if ident.get("trace_sha256") != TRACE_SHA256:
        raise ValueError("software_identity trace_sha256 drift")
    if ident.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise ValueError("software_identity schema_version drift")
    if ident.get("evaluator_seed") != EVALUATOR_SEED:
        raise ValueError("software_identity evaluator_seed drift")
    if ident.get("fleet_seed") != fleet_seed:
        raise ValueError("software_identity fleet_seed drift")
    if ident.get("fleet_draw_label") != "fleet_draw":
        raise ValueError("software_identity fleet_draw_label drift")
    # deadline instrumentation exact
    if data.get("deadline_instrumented") is not True:
        raise ValueError("deadline_instrumented must be true")
    # Strict int checks for task counts rejecting bools
    offered = data.get("offered")
    admitted = data.get("admitted")
    rejected = data.get("rejected")
    if not _is_strict_int(offered) or not _is_strict_int(admitted) or not _is_strict_int(rejected):
        raise ValueError("adapter task counts must be strict int, rejecting bool")
    if offered != admitted + rejected:
        raise ValueError(f"task conservation failed: {offered} != {admitted}+{rejected}")
    forwarded = data.get("forwarded")
    deadline_success = data.get("deadline_success")
    if not _is_strict_int(forwarded) or not _is_strict_int(deadline_success):
        raise ValueError("forwarded/deadline_success must be strict int")
    # Exact reconciliation to task_outcomes
    task_outcomes = data.get("task_outcomes")
    if not isinstance(task_outcomes, list):
        raise ValueError("task_outcomes not list")
    if len(task_outcomes) != offered:
        raise ValueError(f"task_outcomes len {len(task_outcomes)} != offered {offered}")
    if len(task_outcomes) > 2:
        raise ValueError(f"task_outcomes len {len(task_outcomes)} >2")
    # Compute live counts from outcomes
    live_admitted = 0
    live_forwarded = 0
    live_deadline = 0
    for t in task_outcomes:
        if not isinstance(t, dict):
            raise ValueError("task_outcome not dict")
        if type(t.get("admitted")) is not bool:
            raise ValueError(f"task_outcome admitted must be bool: {t!r}")
        admitted_flag = t.get("admitted")
        latency = t.get("latency_ms")
        deadline = t.get("deadline_success")
        reason = t.get("latency_reason")
        forwarded_flag = t.get("forwarded")
        if type(forwarded_flag) is not bool:
            raise ValueError(f"task_outcome forwarded must be bool: {t!r}")
        if admitted_flag:
            live_admitted += 1
            if forwarded_flag:
                live_forwarded += 1
            if deadline is True:
                live_deadline += 1
            if latency is None or type(latency) is bool or not isinstance(latency, (int, float)):
                raise ValueError(f"admitted task missing finite latency: {t!r}")
            if not math.isfinite(float(latency)):
                raise ValueError(f"admitted latency not finite: {t!r}")
            if float(latency) == 0.0:
                raise ValueError(f"admitted task zero latency not allowed: {t!r}")
            if type(deadline) is not bool:
                raise ValueError(f"admitted task missing bool deadline_success: {t!r}")
            if not isinstance(reason, str) or "computed" not in reason:
                raise ValueError(f"admitted task missing computed reason: {t!r}")
        else:
            if latency is not None:
                if latency == 0 or latency == 0.0:
                    raise ValueError(f"rejected task zero-filled latency: {t!r}")
                raise ValueError(f"rejected task latency must be null: {t!r}")
            if deadline is not None:
                raise ValueError(f"rejected task deadline must be null: {t!r}")
            if not isinstance(reason, str) or reason == "":
                raise ValueError(f"rejected task missing latency_reason string: {t!r}")
            if forwarded_flag:
                raise ValueError(f"rejected task forwarded must be false: {t!r}")
    if admitted != live_admitted:
        raise ValueError(f"admitted {admitted} != live admitted {live_admitted}")
    if rejected != offered - live_admitted:
        raise ValueError(f"rejected {rejected} != live rejected {offered - live_admitted}")
    if forwarded != live_forwarded:
        raise ValueError(f"forwarded {forwarded} != live forwarded {live_forwarded}")
    if deadline_success != live_deadline:
        raise ValueError(f"deadline_success {deadline_success} != live {live_deadline}")
    # receipt_state_age check
    receipt_age = data.get("receipt_state_age_ms")
    if not _is_strict_int(receipt_age):
        raise ValueError("receipt_state_age_ms must be strict int")
    if receipt_age != state_age_ms:
        raise ValueError(f"receipt_state_age_ms {receipt_age} != state_age_ms {state_age_ms}")
    # Resource intervals strict validation
    intervals = data.get("resource_intervals_this_tick")
    if intervals is None:
        intervals = data.get("resource_intervals")
    if intervals is None:
        intervals = data.get("tick_resource_intervals")
    if not isinstance(intervals, list):
        raise ValueError("resource_intervals missing")
    if len(intervals) != num_rsus:
        raise ValueError(f"resource_intervals len {len(intervals)} != num_rsus {num_rsus}")
    seen_rsu: set[int] = set()
    total_from_intervals = 0.0
    for iv in intervals:
        if not isinstance(iv, dict):
            raise ValueError("interval not dict")
        for f in ("rsu_id", "start_time_ms", "end_time_ms", "active_compute_units"):
            if f not in iv:
                raise ValueError(f"interval missing field {f!r}")
            if not _is_strict_int(iv[f]):
                raise ValueError(f"interval field {f} must be strict int, got {iv[f]!r}")
        rsu = iv["rsu_id"]
        start = iv["start_time_ms"]
        end = iv["end_time_ms"]
        units = iv["active_compute_units"]
        if rsu in seen_rsu:
            raise ValueError(f"duplicate rsu_id {rsu}")
        seen_rsu.add(rsu)
        if rsu < 0 or rsu >= num_rsus:
            raise ValueError(f"rsu_id {rsu} out of range for num_rsus {num_rsus}")
        if start != 3000 or end != 4000:
            raise ValueError(f"interval must cover 3000-4000, got {start}-{end}")
        if end - start != 1000:
            raise ValueError(f"interval duration must be 1000, got {end - start}")
        if units < 1 or units > 3:
            raise ValueError(f"active_compute_units {units} out of bounds 1..3")
        total_from_intervals += float(units) * ((end - start) / 1000.0)
    if seen_rsu != set(range(num_rsus)):
        raise ValueError(f"intervals must cover each RSU exactly once, got {seen_rsu}")
    total = data.get("total_resource_unit_seconds")
    if type(total) is bool or not isinstance(total, (int, float)):
        raise ValueError("total_resource_unit_seconds must be numeric not bool")
    if not math.isfinite(float(total)):
        raise ValueError("total_resource_unit_seconds not finite")
    if not math.isclose(float(total), total_from_intervals, rel_tol=0, abs_tol=1e-9):
        raise ValueError(
            f"total_resource_unit_seconds {total} != recomputed {total_from_intervals}"
        )
    # Per-RSU cumulative accounting
    drained = data.get("total_drained_work_ms")
    if type(drained) is bool or not isinstance(drained, (int, float)):
        raise ValueError("total_drained_work_ms not numeric not bool")
    if not math.isfinite(float(drained)) or float(drained) < 0:
        raise ValueError("total_drained_work_ms must be finite >=0")
    per_drained = data.get("per_rsu_cumulative_drained_ms")
    per_cap = data.get("per_rsu_cumulative_capacity_ms")
    if not isinstance(per_drained, dict) or not isinstance(per_cap, dict):
        raise ValueError("per_rsu cumulative missing")
    sum_drained = 0.0
    for _k, v in per_drained.items():
        if type(v) is bool or not isinstance(v, (int, float)):
            raise ValueError("per_rsu drained must be numeric not bool")
        if not math.isfinite(float(v)) or float(v) < 0:
            raise ValueError("per_rsu drained must be finite >=0")
        sum_drained += float(v)
    if not math.isclose(float(drained), sum_drained, rel_tol=0, abs_tol=1e-9):
        raise ValueError(f"total_drained {drained} != sum per_rsu {sum_drained}")
    sum_cap = 0.0
    for _k, v in per_cap.items():
        if type(v) is bool or not isinstance(v, (int, float)):
            raise ValueError("per_rsu capacity must be numeric not bool")
        if not math.isfinite(float(v)) or float(v) < 0:
            raise ValueError("per_rsu capacity must be finite >=0")
        sum_cap += float(v)
    expected_cap = float(total) * 1000.0
    if not math.isclose(sum_cap, expected_cap, rel_tol=0, abs_tol=1e-9):
        raise ValueError(f"per_rsu capacity sum {sum_cap} != total*1000 {expected_cap}")
    # Utilization check finite nonnegative
    util = data.get("utilization")
    if util is not None:
        if not isinstance(util, dict):
            raise ValueError("utilization not dict")
        for _k, v in util.items():
            if type(v) is bool or not isinstance(v, (int, float)):
                raise ValueError("utilization value must be numeric not bool")
            if not math.isfinite(float(v)) or float(v) < 0 or float(v) > 1 + 1e-9:
                raise ValueError("utilization out of [0,1] or not finite")
    # Scaling receipts validation
    for key in ("scaling_scheduled", "scaling_applied"):
        lst = data.get(key)
        if lst is None:
            continue
        if not isinstance(lst, list):
            raise ValueError(f"{key} not list")
        for item in lst:
            if not isinstance(item, dict):
                raise ValueError(f"{key} item not dict")
            # Require exact typed lifecycle fields
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
                    raise ValueError(f"{key} item missing {field!r}")
            if not _is_strict_int(item["rsu_id"]):
                raise ValueError("scaling rsu_id must be strict int")
            if item["direction"] not in ("scale_up", "scale_down"):
                raise ValueError("scaling direction invalid")
            if not _is_strict_int(item["decision_time_ms"]) or not _is_strict_int(
                item["due_time_ms"]
            ):
                raise ValueError("scaling decision/due must be strict int")
            if item["due_time_ms"] != item["decision_time_ms"] + 2000:
                raise ValueError("scaling due != decision+2000")
            before = item["before_units"]
            after = item["after_units"]
            target = item["target_units"]
            if (
                not _is_strict_int(before)
                or not _is_strict_int(after)
                or not _is_strict_int(target)
            ):
                raise ValueError("scaling units must be strict int")
            if item["direction"] == "scale_up":
                if after != before + 1 or target != after:
                    raise ValueError("scale_up before/after/target inconsistent")
            else:
                if after != before - 1 or target != after:
                    raise ValueError("scale_down before/after/target inconsistent")
            if type(item["applied"]) is not bool:
                raise ValueError("scaling applied must be bool")
            applied_time = item.get("applied_time_ms")
            if item["applied"]:
                if not _is_strict_int(applied_time):
                    raise ValueError("applied_time_ms must be int when applied true")
                if applied_time != item["due_time_ms"]:
                    raise ValueError("applied_time_ms must equal due when applied")
            else:
                if applied_time is not None:
                    raise ValueError("applied_time_ms must be null when not applied")
            # state_age consistency if present
            sa = item.get("state_age_ms")
            if sa is not None:
                if not _is_strict_int(sa):
                    raise ValueError("scaling state_age_ms must be int")
                if sa != state_age_ms:
                    raise ValueError("scaling receipt state_age_ms mismatch")
            if not isinstance(item["reason"], str) or item["reason"] == "":
                raise ValueError("scaling reason must be non-empty string")
            if not isinstance(item["action_id"], str) or item["action_id"] == "":
                raise ValueError("scaling action_id must be non-empty string")
    # Additional checks for construct ticks etc
    ct = data.get("construct_ticks")
    if ct is not None and ct != 1:
        raise ValueError(f"construct_ticks {ct!r} !=1")
    cr = data.get("construct_rsus")
    if cr is not None and cr != num_rsus:
        raise ValueError(f"construct_rsus {cr!r} != {num_rsus}")
    ctasks = data.get("construct_tasks")
    if ctasks is not None and ctasks not in (1, 2):
        raise ValueError(f"construct_tasks {ctasks!r} not in 1..2")
    return data


def _build_construct_result(
    adapter_data: dict[str, Any],
    manifest_sha: str,
    traffictwin_sha: str,
) -> dict[str, Any]:
    placement = str(adapter_data["placement"])
    scaling = str(adapter_data["scaling"])
    state_age_ms = int(adapter_data["state_age_ms"])
    fleet_seed = int(adapter_data["fleet_seed"])
    num_rsus = int(adapter_data["num_rsus"])
    arm_id = canonical_arm_id(placement, scaling, state_age_ms)
    config_id = canonical_config_id(
        placement, scaling, state_age_ms, EVALUATOR_SEED, fleet_seed, num_rsus
    )
    # Verify mirrors before wrapping
    nested_task = adapter_data.get("task_outcomes")
    nested_intervals = adapter_data.get("resource_intervals_this_tick")
    if nested_intervals is None:
        nested_intervals = adapter_data.get("resource_intervals")
    nested_scheduled = adapter_data.get("scaling_scheduled", [])
    nested_applied = adapter_data.get("scaling_applied", [])
    # Ensure exact recomputation of totals already validated in _invoke_adapter
    result: dict[str, Any] = {
        "arm_id": arm_id,
        "config_id": config_id,
        "construct_classification": "software_construct_evidence_not_e3_research_results",
        "evidence_label": "software construct evidence, not E3 research results",
        "execution_authority": dict(EXECUTION_AUTHORITY),
        "evidence_state": NOT_EXECUTED,
        "factors": {
            "evaluator_seed": EVALUATOR_SEED,
            "fleet_seed": fleet_seed,
            "num_rsus": num_rsus,
            "placement": placement,
            "scaling": scaling,
            "state_age_ms": state_age_ms,
        },
        "is_construct": True,
        "is_empirical": False,
        "is_scientific_evidence": False,
        "lane_09": BLOCKED_BY_RESEARCHER_EXECUTION_HOLD,
        "manifest_sha256": manifest_sha,
        "nested_adapter_result": adapter_data,
        "research_workloads_launched": 0,
        "resource_conservation": {
            "per_rsu_intervals": adapter_data.get("resource_intervals_this_tick", []),
            "total_resource_unit_seconds": adapter_data.get("total_resource_unit_seconds"),
            "valid": True,
        },
        "resource_intervals": adapter_data.get(
            "resource_intervals_this_tick", adapter_data.get("resource_intervals", [])
        ),
        "result_availability": NO_E3_RESEARCH_RESULTS_AVAILABLE,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "runner_schema_version": RUNNER_SCHEMA_VERSION,
        "scaling_action_receipts": {
            "applied": adapter_data.get("scaling_applied", []),
            "scheduled": adapter_data.get("scaling_scheduled", []),
        },
        "schema_version": RESULT_SCHEMA_VERSION,
        "state_age_ms": state_age_ms,
        "status": E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED,
        "task_conservation": {
            "admitted": adapter_data.get("admitted"),
            "deadline_success": adapter_data.get("deadline_success"),
            "forwarded": adapter_data.get("forwarded"),
            "offered": adapter_data.get("offered"),
            "rejected": adapter_data.get("rejected"),
            "valid": adapter_data.get("offered")
            == adapter_data.get("admitted", 0) + adapter_data.get("rejected", 0),
        },
        "task_outcomes": adapter_data.get("task_outcomes", []),
        "total_drained_work_ms": adapter_data.get("total_drained_work_ms"),
        "total_resource_unit_seconds": adapter_data.get("total_resource_unit_seconds"),
        "traffictwin_git_sha": traffictwin_sha,
        "vec_runtime": {
            "adapter_candidate": VEC_ADAPTER_SHA,
            "core_candidate": VEC_CORE_SHA,
            "promotion_commit": VEC_PROMOTION_SHA,
        },
    }
    # Compute conservation valid booleans correctly rather than unconditional true
    offered = adapter_data.get("offered")
    admitted = adapter_data.get("admitted")
    rejected = adapter_data.get("rejected")
    task_valid = (
        isinstance(offered, int)
        and isinstance(admitted, int)
        and isinstance(rejected, int)
        and offered == admitted + rejected
    )
    result["task_conservation"]["valid"] = task_valid
    # Resource conservation valid: recompute from intervals
    intervals = result["resource_intervals"]
    total_rus = result["total_resource_unit_seconds"]
    res_valid = False
    if isinstance(intervals, list) and isinstance(total_rus, (int, float)):
        try:
            recomputed = sum(
                float(iv.get("active_compute_units", 0))
                * ((int(iv.get("end_time_ms", 0)) - int(iv.get("start_time_ms", 0))) / 1000.0)
                for iv in intervals
                if isinstance(iv, dict)
            )
            res_valid = math.isclose(float(total_rus), recomputed, rel_tol=0, abs_tol=1e-9)
        except Exception:
            res_valid = False
    result["resource_conservation"]["valid"] = res_valid
    # Verify mirrors: top-level task_outcomes must byte/value mirror nested
    if result["task_outcomes"] != nested_task:
        raise ValueError("task_outcomes mirror mismatch")
    if result["resource_intervals"] != nested_intervals:
        raise ValueError("resource_intervals mirror mismatch")
    if result["scaling_action_receipts"]["scheduled"] != nested_scheduled:
        raise ValueError("scaling scheduled mirror mismatch")
    if result["scaling_action_receipts"]["applied"] != nested_applied:
        raise ValueError("scaling applied mirror mismatch")
    # Verify receipt state age matches factor
    if adapter_data.get("receipt_state_age_ms") != state_age_ms:
        raise ValueError("receipt_state_age_ms != state_age_ms")
    if result["state_age_ms"] != state_age_ms:
        raise ValueError("result state_age_ms != factor")
    dumped = json.dumps(result)
    for prefix in FORBIDDEN_ABSOLUTE_PREFIXES:
        if prefix in dumped:
            raise ValueError(f"output contains forbidden absolute prefix {prefix!r}")
    # Recursively check forbidden claims at any depth will be handled by validator, but also fail here if found  # noqa: E501
    lower = dumped.lower()
    for substr in (
        "queue_ceiling_is_compute",
        "queue ceiling is compute",
        "queue ceiling is",
        "actor selects execution",
        "actor selects",
        "actor_selects",
        "kubernetes",
        "k8s_deployment",
    ):
        if substr in lower:
            raise ValueError(f"output contains forbidden substring {substr!r}")
    return result


def main(
    argv: list[str] | None = None,
    git_runner: Callable[..., Any] | None = None,
    subprocess_runner: Callable[..., Any] | None = None,
) -> int:
    raw_argv = argv if argv is not None else sys.argv[1:]
    if not raw_argv:
        print("missing mode: minimal_construct or scientific", file=sys.stderr)
        return 1
    mode = raw_argv[0]
    if mode == "scientific":
        print(
            f"{E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED}: "
            "scientific execution not authorized; research_workloads_launched=0",
            file=sys.stderr,
        )
        sys.exit(1)
    if mode not in ("minimal_construct",):
        print(f"unknown mode {mode!r}: only minimal_construct or scientific", file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(prog="run_e3_dynamic_resource_v2.py", add_help=False)
    parser.add_argument("mode", choices=["minimal_construct"])
    parser.add_argument("--vec-repo", dest="vec_repo", required=True, type=str)
    parser.add_argument("--python", dest="python_exe", required=True, type=str)
    parser.add_argument("--manifest", dest="manifest", required=False, type=str, default=None)
    parser.add_argument("--output", dest="output", required=False, type=str, default=None)
    parser.add_argument(
        "--placement",
        dest="placement",
        required=False,
        type=str,
        default="per_task_dla",
        choices=VALID_PLACEMENTS,
    )
    parser.add_argument(
        "--scaling",
        dest="scaling",
        required=False,
        type=str,
        default="fixed_1x",
        choices=VALID_SCALINGS,
    )
    parser.add_argument(
        "--state-age-ms",
        dest="state_age_ms",
        required=False,
        type=int,
        default=0,
        choices=VALID_STATE_AGES,
    )
    parser.add_argument(
        "--fleet-seed", dest="fleet_seed", required=False, type=int, default=1, choices=FLEET_SEEDS
    )
    parser.add_argument(
        "--num-rsus", dest="num_rsus", required=False, type=int, default=2, choices=(1, 2)
    )
    try:
        args = parser.parse_args(raw_argv)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 1
    # Preflight explicit output target before manifest/Git/child execution
    output_path: Path | None = None
    if args.output:
        output_path = Path(str(args.output))
        out_str = str(output_path)
        if "/Users/" in out_str or "/private/" in out_str:
            print(f"output path contains forbidden private prefix in {out_str!r}", file=sys.stderr)
            return 1
        if output_path.exists():
            print(f"output exists, refusing to overwrite: {output_path}", file=sys.stderr)
            return 1
        # Also preflight parent is not writable? Try to check if parent exists as file
        try:
            if output_path.parent.exists() and not output_path.parent.is_dir():
                print(f"output parent not directory: {output_path.parent}", file=sys.stderr)
                return 1
        except Exception as e:
            print(f"output preflight failed: {e}", file=sys.stderr)
            return 1
    # Verify contract bytes before anything else
    try:
        _verify_contract_bytes()
    except Exception as e:
        print(f"contract bytes validation failed: {e}", file=sys.stderr)
        return 1
    try:
        manifest_path, sidecar_path = _manifest_paths(
            Path(args.manifest) if args.manifest else None
        )
        _manifest_data, manifest_sha = _verify_manifest(manifest_path, sidecar_path)
    except Exception as e:
        print(f"manifest validation failed: {e}", file=sys.stderr)
        return 1
    vec_repo = Path(str(args.vec_repo))
    python_exe = Path(str(args.python_exe))
    try:
        _validate_vec_runtime(
            vec_repo, python_exe, git_runner=git_runner, python_runner=subprocess_runner
        )
    except Exception as e:
        print(f"vec runtime validation failed: {e}", file=sys.stderr)
        return 1
    try:
        tt_sha = _get_traffictwin_git_sha(git_runner=git_runner)
    except Exception as e:
        print(f"traffictwin git sha failed: {e}", file=sys.stderr)
        return 1
    placement = str(args.placement)
    scaling = str(args.scaling)
    state_age_ms = int(args.state_age_ms)
    fleet_seed = int(args.fleet_seed)
    num_rsus = int(args.num_rsus)
    # Validate factor combinations produce valid arm/config IDs before spawn
    try:
        _ = canonical_arm_id(placement, scaling, state_age_ms)
        _ = canonical_config_id(
            placement, scaling, state_age_ms, EVALUATOR_SEED, fleet_seed, num_rsus
        )
        _ = _recompute_adapter_config_id(
            placement, scaling, state_age_ms, EVALUATOR_SEED, fleet_seed, num_rsus, VEC_CORE_SHA
        )
    except Exception as e:
        print(f"factor validation failed: {e}", file=sys.stderr)
        return 1
    try:
        adapter_data = _invoke_adapter(
            vec_repo,
            python_exe,
            placement,
            scaling,
            state_age_ms,
            fleet_seed,
            num_rsus,
            subprocess_runner=subprocess_runner,
        )
    except Exception as e:
        print(f"adapter invocation failed: {e}", file=sys.stderr)
        return 1
    try:
        wrapped = _build_construct_result(adapter_data, manifest_sha, tt_sha)
    except Exception as e:
        print(f"wrap failed: {e}", file=sys.stderr)
        return 1
    try:
        tc = wrapped["task_conservation"]
        if not tc.get("valid"):
            raise ValueError("task conservation invalid")
        rc = wrapped["resource_conservation"]
        if not rc.get("valid"):
            raise ValueError("resource conservation invalid")
        ri = wrapped["resource_intervals"]
        if not isinstance(ri, list) or len(ri) != num_rsus:
            raise ValueError("resource intervals invalid")
    except Exception as e:
        print(f"result validation failed: {e}", file=sys.stderr)
        return 1
    canonical = json.dumps(wrapped, sort_keys=True, separators=(",", ":"))
    if "\n" in canonical:
        print("canonical JSON must be single line", file=sys.stderr)
        return 1
    # Export handling: write exclusively and verify before printing stdout
    if output_path is not None:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"output parent mkdir failed: {e}", file=sys.stderr)
            return 1
        try:
            with open(output_path, "x", encoding="utf-8") as f:
                f.write(canonical)
                f.write("\n")
        except FileExistsError:
            print(f"output exists (race), refusing: {output_path}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"output write failed: {e}", file=sys.stderr)
            return 1
        try:
            written_raw = output_path.read_text(encoding="utf-8")
            # Must be exactly canonical + single newline
            if written_raw != canonical + "\n":
                print("export byte drift", file=sys.stderr)
                return 1
        except Exception as e:
            print(f"export verify failed: {e}", file=sys.stderr)
            return 1
    # Only after successful export verification, print to stdout
    print(canonical)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

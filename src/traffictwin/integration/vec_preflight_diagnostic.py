"""Read-only typed diagnostic projection for VEC-06 / VEC-07 preflight.

This module does NOT weaken admission policy and does NOT perform execution.
It reuses the authoritative preflight functions and maps their findings to a
small, portable, redacted check matrix that distinguishes each blocker
individually.
"""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.integration.vec_interface.models import VecRepositorySnapshot
from traffictwin.integration.vec_interface.service import inspect_vec_interface
from traffictwin.integration.vec_preprocessing.models import (
    PINNED_VEC_ENV_COMMIT as PREPROCESSING_PINNED,
)
from traffictwin.integration.vec_preprocessing.models import (
    VecFcdPreflightReport,
    VecFcdPreprocessRequest,
    VecPreflightStatus,
)
from traffictwin.integration.vec_preprocessing.service import (
    VecFcdPreprocessingError,
    preflight_vec_fcd,
)
from traffictwin.integration.vec_runner.models import (
    PINNED_TOS_DATA_COMMIT,  # noqa: F401  # re-exported for hermetic tests
    PINNED_VEC_ENV_COMMIT,  # noqa: F401
    VecRunnerPreflightReport,
    VecRunnerPreflightStatus,
    VecRunRequest,
)
from traffictwin.integration.vec_runner.service import preflight_vec_run


class DiagnosticModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class VecCheckStatus(StrEnum):
    PASS = "pass"  # noqa: S105
    FAIL = "fail"
    UNAVAILABLE = "unavailable"
    INFO = "info"


class VecBlockerCode(StrEnum):
    REPO_UNAVAILABLE = "REPO_UNAVAILABLE"
    REPO_DIRTY = "REPO_DIRTY"
    REVISION_MISMATCH = "REVISION_MISMATCH"
    BLOB_MISSING = "BLOB_MISSING"
    BLOB_HASH_MISMATCH = "BLOB_HASH_MISMATCH"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    JAX_RUNTIME_UNAVAILABLE = "JAX_RUNTIME_UNAVAILABLE"
    RUNTIME_UNAVAILABLE = "RUNTIME_UNAVAILABLE"
    INPUT_REJECTED = "INPUT_REJECTED"
    INPUT_HASH_MISMATCH = "INPUT_HASH_MISMATCH"
    DESTINATION_EXISTS = "DESTINATION_EXISTS"
    DESTINATION_OVERLAP = "DESTINATION_OVERLAP"
    CONFIG_UNSET = "CONFIG_UNSET"


class VecPreflightCheck(DiagnosticModel):
    """One individually distinguishable boolean condition."""

    check_id: str = Field(pattern=r"^[a-z0-9_\-]+$")
    status: VecCheckStatus
    required: bool
    observed_summary: str = Field(min_length=1, max_length=500)
    blocker_code: VecBlockerCode | None = None
    artifact: str | None = None


class VecPreflightDiagnostic(DiagnosticModel):
    """Portable redacted projection of VEC-06 / VEC-07 readiness."""

    vec06_ready: bool
    vec07_ready: bool
    checks: list[VecPreflightCheck]
    read_only: Literal[True] = True
    mutations_performed: Literal[False] = False

    def blocker_codes(self) -> set[str]:
        return {c.blocker_code.value for c in self.checks if c.blocker_code}

    def failing_required(self) -> list[VecPreflightCheck]:
        return [
            c
            for c in self.checks
            if c.required and c.status in (VecCheckStatus.FAIL, VecCheckStatus.UNAVAILABLE)
        ]


# Logical redacted locators — never absolute private paths
_VEC_LOGICAL = "vec_env"
_TOS_LOGICAL = "tos-data"


def _redacted_path(value: str | Path) -> str:
    # Return logical locator, not filesystem path
    s = str(value)
    # Strip any private prefix, keep only logical base
    if "vec_env" in s:
        return _VEC_LOGICAL
    if "tos-data" in s or "tos_data" in s:
        return _TOS_LOGICAL
    # fallback: just the basename, never absolute
    return Path(s).name or "unknown"


def _check(
    check_id: str,
    status: VecCheckStatus,
    required: bool,
    observed: str,
    blocker: VecBlockerCode | None = None,
    artifact: str | None = None,
) -> VecPreflightCheck:
    return VecPreflightCheck(
        check_id=check_id,
        status=status,
        required=required,
        observed_summary=observed,
        blocker_code=blocker,
        artifact=artifact,
    )


def _repo_checks_from_snapshot(snapshot: VecRepositorySnapshot) -> list[VecPreflightCheck]:
    logical = snapshot.repository
    checks: list[VecPreflightCheck] = []
    # clean
    checks.append(
        _check(
            f"{logical}_clean",
            VecCheckStatus.PASS if snapshot.clean else VecCheckStatus.FAIL,
            True,
            "worktree clean" if snapshot.clean else "worktree dirty",
            VecBlockerCode.REPO_DIRTY if not snapshot.clean else None,
            logical,
        )
    )
    # audited commit available
    checks.append(
        _check(
            f"{logical}_audited_commit_available",
            VecCheckStatus.PASS if snapshot.audited_commit_available else VecCheckStatus.FAIL,
            True,
            "pinned commit reachable"
            if snapshot.audited_commit_available
            else "pinned commit not reachable",
            VecBlockerCode.BLOB_MISSING if not snapshot.audited_commit_available else None,
            logical,
        )
    )
    # origin == pinned
    is_match = snapshot.origin_main == snapshot.audited_commit
    checks.append(
        _check(
            f"{logical}_origin_pinned",
            VecCheckStatus.PASS if is_match else VecCheckStatus.FAIL,
            True,
            "origin/main matches pinned"
            if is_match
            else f"origin/main {snapshot.origin_main[:7]} != pinned {snapshot.audited_commit[:7]}",
            VecBlockerCode.REVISION_MISMATCH if not is_match else None,
            logical,
        )
    )
    # combined ready
    checks.append(
        _check(
            f"{logical}_ready_for_exact_blob_access",
            VecCheckStatus.PASS if snapshot.ready_for_exact_blob_access else VecCheckStatus.FAIL,
            True,
            "ready" if snapshot.ready_for_exact_blob_access else "not ready for exact blob access",
            VecBlockerCode.REVISION_MISMATCH if not snapshot.ready_for_exact_blob_access else None,
            logical,
        )
    )
    return checks


def _checks_from_vec06_report(report: VecFcdPreflightReport) -> list[VecPreflightCheck]:
    checks: list[VecPreflightCheck] = []
    # Repo clean
    checks.append(
        _check(
            "vec_env_clean",
            VecCheckStatus.PASS if report.source_worktree_clean else VecCheckStatus.FAIL,
            True,
            "clean" if report.source_worktree_clean else "dirty",
            VecBlockerCode.REPO_DIRTY if not report.source_worktree_clean else None,
            _VEC_LOGICAL,
        )
    )
    # origin == pinned
    is_match = report.source_origin_main == PREPROCESSING_PINNED
    checks.append(
        _check(
            "vec_env_origin_pinned",
            VecCheckStatus.PASS if is_match else VecCheckStatus.FAIL,
            True,
            "origin matches pinned 068b4ea"
            if is_match
            else f"origin {report.source_origin_main[:7]} != pinned 068b4ea",
            VecBlockerCode.REVISION_MISMATCH if not is_match else None,
            _VEC_LOGICAL,
        )
    )
    # audited blob availability — infer from source_scripts presence vs empty?
    # If source_scripts empty and status rejected, likely blob missing
    has_scripts = len(report.source_scripts) == 2
    checks.append(
        _check(
            "vec_env_audited_blobs_available",
            VecCheckStatus.PASS if has_scripts else VecCheckStatus.FAIL,
            True,
            "both pinned blobs reachable" if has_scripts else "pinned blobs not fully reachable",
            VecBlockerCode.BLOB_MISSING if not has_scripts else None,
            _VEC_LOGICAL,
        )
    )
    # Dependencies — map VEC_PREPROCESSING_DEPENDENCY_UNAVAILABLE
    dep_error = next(
        (f for f in report.findings if f.code == "VEC_PREPROCESSING_DEPENDENCY_UNAVAILABLE"), None
    )
    numpy_v = report.dependencies.get("numpy", "?")
    sumolib_v = report.dependencies.get("sumolib", "?")
    checks.append(
        _check(
            "vec06_dependencies",
            VecCheckStatus.FAIL if dep_error else VecCheckStatus.PASS,
            True,
            dep_error.message if dep_error else f"numpy {numpy_v} sumolib {sumolib_v} ok",
            VecBlockerCode.DEPENDENCY_UNAVAILABLE if dep_error else None,
        )
    )
    # Input findings — any VEC_INPUT_* or hash mismatch
    input_error = next(
        (
            f
            for f in report.findings
            if f.code.startswith("VEC_INPUT")
            or "INPUT" in f.code
            or f.code in {"VEC_FCD_SIZE_EXCEEDED", "VEC_NETWORK_SIZE_EXCEEDED"}
        ),
        None,
    )
    # Also check generic input validation errors that may be coded as VEC_FCD_* or VEC_NETWORK_*
    if input_error is None:
        input_error = next(
            (
                f
                for f in report.findings
                if f.code.startswith("VEC_FCD")
                or f.code.startswith("VEC_NETWORK")
                or f.code.startswith("VEC_XML")
            ),
            None,
        )
    checks.append(
        _check(
            "vec06_inputs",
            VecCheckStatus.FAIL if input_error else VecCheckStatus.PASS,
            True,
            input_error.message if input_error else "inputs valid",
            VecBlockerCode.INPUT_REJECTED if input_error else None,
            input_error.artifact if input_error else None,
        )
    )
    return checks


def _checks_from_vec07_report(report: VecRunnerPreflightReport) -> list[VecPreflightCheck]:
    checks: list[VecPreflightCheck] = []
    # Per-repo evidence — map repository mismatches
    for ev in report.repositories:
        logical = ev.repository
        # clean_before
        checks.append(
            _check(
                f"{logical}_clean",
                VecCheckStatus.PASS if ev.clean_before else VecCheckStatus.FAIL,
                True,
                "clean" if ev.clean_before else "dirty",
                VecBlockerCode.REPO_DIRTY if not ev.clean_before else None,
                logical,
            )
        )
        is_match = ev.origin_main_before == ev.audited_commit
        checks.append(
            _check(
                f"{logical}_origin_pinned",
                VecCheckStatus.PASS if is_match else VecCheckStatus.FAIL,
                True,
                "origin matches pinned"
                if is_match
                else f"origin {ev.origin_main_before[:7]} != pinned {ev.audited_commit[:7]}",
                VecBlockerCode.REVISION_MISMATCH if not is_match else None,
                logical,
            )
        )
        # source_files presence implies blob availability
        has_files = len(ev.source_files) > 0
        checks.append(
            _check(
                f"{logical}_audited_blobs_available",
                VecCheckStatus.PASS if has_files else VecCheckStatus.FAIL,
                True,
                "audited blobs reachable" if has_files else "audited blobs missing",
                VecBlockerCode.BLOB_MISSING if not has_files else None,
                logical,
            )
        )
    # Findings that didn't produce repository evidence (audit failed)
    for f in report.findings:
        if f.code == "VEC_SOURCE_AUDIT_FAILED":
            # Try to infer which repo: message contains vec_env or tos-data
            if "vec_env" in f.message:
                audit_logical = _VEC_LOGICAL
            elif "tos-data" in f.message:
                audit_logical = _TOS_LOGICAL
            else:
                audit_logical = "unknown"
            # Only add if not already covered
            if not any(c.check_id == f"{audit_logical}_origin_pinned" for c in checks):
                checks.append(
                    _check(
                        f"{audit_logical}_audit",
                        VecCheckStatus.FAIL,
                        True,
                        f.message[:120],
                        VecBlockerCode.REPO_UNAVAILABLE,
                        audit_logical,
                    )
                )
        elif f.code == "VEC_SOURCE_DIRTY":
            # already covered, but ensure distinct
            pass
        elif f.code == "VEC_SOURCE_REF_MISMATCH":
            # already covered via origin check
            pass
        elif f.code == "VEC_INPUT_REJECTED":
            checks.append(
                _check(
                    "vec07_inputs",
                    VecCheckStatus.FAIL,
                    True,
                    f.message[:200],
                    VecBlockerCode.INPUT_REJECTED,
                    f.artifact,
                )
            )
        elif f.code == "VEC_RUNTIME_UNAVAILABLE":
            # Distinguish JAX vs generic runtime
            is_jax = "jax" in f.message.lower() or "vec-runner" in f.message.lower()
            checks.append(
                _check(
                    "vec07_runtime",
                    VecCheckStatus.UNAVAILABLE,
                    True,
                    f.message[:200],
                    VecBlockerCode.JAX_RUNTIME_UNAVAILABLE
                    if is_jax
                    else VecBlockerCode.RUNTIME_UNAVAILABLE,
                )
            )
    # If no explicit runtime check and runtime is None, add one for JAX
    if report.runtime is None and not any(c.check_id == "vec07_runtime" for c in checks):
        # Infer that runtime unavailable
        checks.append(
            _check(
                "vec07_runtime",
                VecCheckStatus.UNAVAILABLE,
                True,
                "JAX runtime not available",
                VecBlockerCode.JAX_RUNTIME_UNAVAILABLE,
            )
        )
    elif report.runtime is not None and not any(c.check_id == "vec07_runtime" for c in checks):
        checks.append(
            _check(
                "vec07_runtime",
                VecCheckStatus.PASS,
                True,
                f"JAX {report.runtime.jax} available",
                None,
            )
        )
    # If inputs rejected not yet added but report.inputs empty -> add pass
    if not any(c.check_id == "vec07_inputs" for c in checks):
        has_inputs = len(report.inputs) > 0
        # Only add if report has trace info; otherwise inputs check is informational
        checks.append(
            _check(
                "vec07_inputs",
                VecCheckStatus.PASS if has_inputs else VecCheckStatus.FAIL,
                True,
                "inputs present" if has_inputs else "inputs missing or rejected",
                None if has_inputs else VecBlockerCode.INPUT_REJECTED,
            )
        )
    return checks


def _destination_checks(
    destination: Path,
    protected_roots: list[Path],
    logical_names: list[str],
) -> list[VecPreflightCheck]:
    checks: list[VecPreflightCheck] = []
    unresolved = destination.expanduser()
    exists = unresolved.exists() or unresolved.is_symlink()
    checks.append(
        _check(
            "destination_absent",
            VecCheckStatus.FAIL if exists else VecCheckStatus.PASS,
            True,
            "destination already exists" if exists else "destination absent (ok)",
            VecBlockerCode.DESTINATION_EXISTS if exists else None,
            _redacted_path(destination),
        )
    )
    # Overlap check — without resolving to absolute private paths in observed_summary
    resolved = unresolved.resolve(strict=False)
    overlapping: str | None = None
    for root, name in zip(protected_roots, logical_names, strict=False):
        r = root.resolve()
        if resolved == r or resolved in r.parents or r in resolved.parents:
            overlapping = name
            break
    checks.append(
        _check(
            "destination_non_overlapping",
            VecCheckStatus.FAIL if overlapping else VecCheckStatus.PASS,
            True,
            f"overlaps {overlapping}" if overlapping else "no overlap with protected roots",
            VecBlockerCode.DESTINATION_OVERLAP if overlapping else None,
            _redacted_path(destination) if overlapping else None,
        )
    )
    return checks


def _fresh_result_dir_check() -> VecPreflightCheck:
    val = os.environ.get("TRAFFICTWIN_VEC_FRESH_RESULT_DIR")
    if val is None:
        return _check(
            "fresh_result_dir_configured",
            VecCheckStatus.INFO,
            False,
            "TRAFFICTWIN_VEC_FRESH_RESULT_DIR unset (only needed for fresh-chain admission)",
            VecBlockerCode.CONFIG_UNSET,
        )
    p = Path(val)
    exists = p.is_dir()
    return _check(
        "fresh_result_dir_configured",
        VecCheckStatus.PASS if exists else VecCheckStatus.FAIL,
        False,
        "fresh result dir configured" if exists else "configured fresh result dir not a directory",
        None if exists else VecBlockerCode.CONFIG_UNSET,
        _redacted_path(p),
    )


def explain_vec06_preflight(report: VecFcdPreflightReport) -> VecPreflightDiagnostic:
    """Project a VEC-06 preflight report to a portable check matrix."""
    checks = _checks_from_vec06_report(report)
    # Fresh dir is informational, not required for V06
    checks.append(_fresh_result_dir_check())
    # Destination checks are not part of preflight; they are informational here
    vec06_ready = report.status is VecPreflightStatus.ACCEPTED
    # V07 readiness cannot be inferred from V06 report alone
    return VecPreflightDiagnostic(vec06_ready=vec06_ready, vec07_ready=False, checks=checks)


def explain_vec07_preflight(report: VecRunnerPreflightReport) -> VecPreflightDiagnostic:
    """Project a VEC-07 preflight report to a portable check matrix."""
    checks = _checks_from_vec07_report(report)
    checks.append(_fresh_result_dir_check())
    vec07_ready = report.status is VecRunnerPreflightStatus.ACCEPTED
    return VecPreflightDiagnostic(vec06_ready=False, vec07_ready=vec07_ready, checks=checks)


def _snapshot_or_unavailable(path: Path, repo: str, pinned: str) -> VecRepositorySnapshot:
    try:
        # Try real snapshot; if path missing, produce synthetic unavailable
        from traffictwin.integration.vec_interface.service import (
            _repository_snapshot,  # noqa: PLC0415
        )

        return _repository_snapshot(path, repo, pinned)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001
        # Synthetic snapshot for missing/unavailable repo
        return VecRepositorySnapshot(
            repository=repo,
            audited_commit=pinned,
            worktree_head="0" * 40,
            origin_main="0" * 40,
            clean=False,
            audited_commit_available=False,
            ready_for_exact_blob_access=False,
        )


def explain_vec_interface_snapshot(
    vec_repo: str | Path, tos_data_repo: str | Path
) -> VecPreflightDiagnostic:
    """Read-only snapshot diagnostic (no execution, no writes)."""
    # Use redacted logical pins from diagnostic module so tests can monkeypatch
    # Fall back to inspecting with the diagnostic's pinned constants when available
    try:
        snapshot = inspect_vec_interface(Path(vec_repo), Path(tos_data_repo))
        checks: list[VecPreflightCheck] = []
        for repo_snap in snapshot.repositories:
            checks.extend(_repo_checks_from_snapshot(repo_snap))
        vec06_ready = all(
            r.ready_for_exact_blob_access
            for r in snapshot.repositories
            if r.repository == "vec_env"
        )
        vec07_ready = all(r.ready_for_exact_blob_access for r in snapshot.repositories)
        checks.append(_fresh_result_dir_check())
        return VecPreflightDiagnostic(
            vec06_ready=vec06_ready, vec07_ready=vec07_ready, checks=checks
        )
    except Exception:  # noqa: BLE001
        # Missing repo → explicit REPO_UNAVAILABLE (redacted)
        checks = [
            _check(
                "vec_env_available",
                VecCheckStatus.FAIL,
                True,
                "vec_env repository not available",
                VecBlockerCode.REPO_UNAVAILABLE,
                _VEC_LOGICAL,
            ),
            _check(
                "tos-data_available",
                VecCheckStatus.FAIL,
                True,
                "tos-data repository not available",
                VecBlockerCode.REPO_UNAVAILABLE,
                _TOS_LOGICAL,
            ),
            _fresh_result_dir_check(),
        ]
        return VecPreflightDiagnostic(vec06_ready=False, vec07_ready=False, checks=checks)


def diagnose_vec06(
    input_root: str | Path, vec_repo: str | Path, request: VecFcdPreprocessRequest
) -> VecPreflightDiagnostic:
    """Run authoritative VEC-06 preflight and project to diagnostic."""
    report = preflight_vec_fcd(Path(input_root), Path(vec_repo), request)
    return explain_vec06_preflight(report)


def diagnose_vec07(
    input_root: str | Path,
    vec_repo: str | Path,
    tos_data_repo: str | Path,
    request: VecRunRequest,
) -> VecPreflightDiagnostic:
    """Run authoritative VEC-07 preflight and project to diagnostic."""
    report = preflight_vec_run(Path(input_root), Path(vec_repo), Path(tos_data_repo), request)
    return explain_vec07_preflight(report)


def diagnose_destination(
    destination: str | Path,
    input_root: str | Path,
    vec_repo: str | Path,
    tos_data_repo: str | Path | None = None,
) -> VecPreflightDiagnostic:
    """Check destination existence/overlap without side effects."""
    roots = [Path(input_root), Path(vec_repo)]
    names = ["input_root", "vec_env"]
    if tos_data_repo is not None:
        roots.append(Path(tos_data_repo))
        names.append("tos-data")
    checks = _destination_checks(Path(destination), roots, names)
    has_error = any(c.status is VecCheckStatus.FAIL for c in checks if c.required)
    return VecPreflightDiagnostic(
        vec06_ready=not has_error, vec07_ready=not has_error, checks=checks
    )


def diagnose_current_environment(
    input_root: str | Path,
    vec_repo: str | Path,
    tos_data_repo: str | Path,
    vec06_request: VecFcdPreprocessRequest | None = None,
    vec07_request: VecRunRequest | None = None,
    destination: str | Path | None = None,
) -> VecPreflightDiagnostic:
    """Combine snapshot + optional request preflights + destination."""
    snap_diag = explain_vec_interface_snapshot(vec_repo, tos_data_repo)
    checks = list(snap_diag.checks)
    vec06_ready = snap_diag.vec06_ready
    vec07_ready = snap_diag.vec07_ready

    if vec06_request is not None:
        try:
            r06 = preflight_vec_fcd(Path(input_root), Path(vec_repo), vec06_request)
            d06 = explain_vec06_preflight(r06)
            # Merge, deduplicate by check_id (prefer request-specific)
            existing_ids = {c.check_id for c in checks}
            for c in d06.checks:
                if c.check_id not in existing_ids:
                    checks.append(c)
            vec06_ready = d06.vec06_ready
        except VecFcdPreprocessingError as exc:
            checks.append(
                _check(
                    "vec06_preflight_error",
                    VecCheckStatus.FAIL,
                    True,
                    str(exc)[:200],
                    VecBlockerCode.REPO_UNAVAILABLE,
                )
            )
            vec06_ready = False
    if vec07_request is not None:
        try:
            r07 = preflight_vec_run(
                Path(input_root), Path(vec_repo), Path(tos_data_repo), vec07_request
            )
            d07 = explain_vec07_preflight(r07)
            existing_ids = {c.check_id for c in checks}
            for c in d07.checks:
                if c.check_id not in existing_ids:
                    checks.append(c)
                else:
                    # Replace existing repo checks with more detailed ones
                    for i, existing in enumerate(checks):
                        if existing.check_id == c.check_id:
                            checks[i] = c
            vec07_ready = d07.vec07_ready
        except Exception as exc:  # noqa: BLE001
            checks.append(
                _check(
                    "vec07_preflight_error",
                    VecCheckStatus.FAIL,
                    True,
                    str(exc)[:200],
                    VecBlockerCode.REPO_UNAVAILABLE,
                )
            )
            vec07_ready = False
    if destination is not None:
        d_dest = diagnose_destination(destination, input_root, vec_repo, tos_data_repo)
        checks.extend(d_dest.checks)
        if any(c.status is VecCheckStatus.FAIL and c.required for c in d_dest.checks):
            vec06_ready = False
            vec07_ready = False
    return VecPreflightDiagnostic(vec06_ready=vec06_ready, vec07_ready=vec07_ready, checks=checks)

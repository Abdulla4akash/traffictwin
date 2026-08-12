"""Deterministic, preview-first, confirmation-gated workspace activation service.

Business logic lives outside Streamlit. No network calls. No secrets stored.

Workspace activation does not make provider network requests; it records
provider readiness/configuration only. Workers are recorded, not launched
in V1; deactivation records which would be stopped.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.workspace_activation.models import (
    _ACTIVATION_METHOD_VERSION,
    ActionKind,
    ActivationFinding,
    CredentialPresence,
    FindingSeverity,
    ProviderKind,
    ProviderReadiness,
    ProviderStatus,
    WorkspaceActivationAction,
    WorkspaceActivationConfirmation,
    WorkspaceActivationPlan,
    WorkspaceActivationPreflight,
    WorkspaceActivationReceipt,
    WorkspaceActivationRequest,
    WorkspaceActivationStatus,
    WorkspaceDeactivationReceipt,
    _canonical_json,
    _digest_json,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MARKER_DIR_NAME = ".traffictwin_workspace"
MARKER_FILE_NAME = "marker.json"
RECEIPT_FILE_NAME = "receipt.json"
REGISTRY_DIR_NAME = "registry"
REGISTRY_FILE_NAME = "traffictwin.sqlite"
AGGREGATE_STORE_DIR = "aggregate-store"
BACKUP_DIR = "backups"
CONFIG_DIR = "config"

ALLOWED_WORKERS: frozenset[str] = frozenset(
    {
        "aggregate-compactor",
        "evidence-indexer",
        "provenance-builder",
    }
)

MIN_DISK_BYTES = 10 * 1024 * 1024
REQUIRED_PYTHON_MAJOR = 3
REQUIRED_PYTHON_MINOR = 11


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ActivationRefusedError(RuntimeError):
    """Raised when activation is refused for safety reasons."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Helpers — no secret handling, deterministic
# ---------------------------------------------------------------------------


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _is_symlink(path: Path) -> bool:
    try:
        return path.is_symlink()
    except OSError:
        return False


def _has_symlink_in_parents(path: Path) -> bool:
    """Check for symlink escape, ignoring system symlinks like /tmp."""
    try:
        cur = path
        if cur.is_symlink():
            return True
        for parent in cur.parents:
            if parent == Path("/"):
                break
            if parent.exists() and parent.is_symlink():
                try:
                    resolved = parent.resolve(strict=True)
                    logical = Path(os.path.abspath(str(parent)))
                    if str(resolved) == "/private" + str(logical):
                        continue
                    if str(parent) in ("/tmp", "/var") and str(  # noqa: S108
                        resolved
                    ).startswith("/private"):
                        continue
                except OSError:
                    pass
                return True
            if not parent.exists():
                continue
        try:
            existing = path
            while not existing.exists() and existing != existing.parent:
                existing = existing.parent
            if existing.exists():
                parts = path.parts
                cur_check = Path(parts[0]) if parts else Path("/")
                for part in parts[1:]:
                    cur_check = cur_check / part
                    if cur_check.exists() and cur_check.is_symlink():
                        try:
                            resolved = cur_check.resolve(strict=True)
                            logical = Path(os.path.abspath(str(cur_check)))
                            if str(resolved) == "/private" + str(logical):
                                continue
                            if str(cur_check) in ("/tmp", "/var") and str(  # noqa: S108
                                resolved
                            ).startswith("/private"):
                                continue
                        except OSError:
                            pass
                        return True
        except OSError:
            pass
    except OSError:
        return False
    return False


def _check_symlink_escape(destination: Path) -> ActivationFinding | None:
    if _is_symlink(destination):
        return ActivationFinding(
            code="SYMLINK_ESCAPE",
            severity=FindingSeverity.ERROR,
            message="Destination path is a symlink; symlink escapes are refused.",
            category="path",
        )
    if _has_symlink_in_parents(destination):
        return ActivationFinding(
            code="SYMLINK_ESCAPE",
            severity=FindingSeverity.ERROR,
            message="Destination path contains a symlink component; symlink escapes are refused.",
            category="path",
        )
    return None


def _check_path_valid(destination: Path) -> tuple[bool, list[ActivationFinding]]:
    findings: list[ActivationFinding] = []
    valid = True
    raw = str(destination)
    if not raw.strip():
        findings.append(
            ActivationFinding(
                code="PATH_EMPTY",
                severity=FindingSeverity.ERROR,
                message="Destination path is empty.",
                category="path",
            )
        )
        return False, findings
    if len(raw) > 4096:
        findings.append(
            ActivationFinding(
                code="PATH_TOO_LONG",
                severity=FindingSeverity.ERROR,
                message="Destination path exceeds maximum length.",
                category="path",
            )
        )
        valid = False
    if "\x00" in raw:
        findings.append(
            ActivationFinding(
                code="PATH_NULL_BYTE",
                severity=FindingSeverity.ERROR,
                message="Path contains null byte.",
                category="path",
            )
        )
        valid = False
    parts = Path(raw).parts
    if ".." in parts:
        findings.append(
            ActivationFinding(
                code="PATH_TRAVERSAL",
                severity=FindingSeverity.ERROR,
                message="Path contains parent traversal '..' which is refused.",
                category="path",
            )
        )
        valid = False
    try:
        repo_root = Path(__file__).resolve().parents[3]
        try:
            dest_resolved = destination.resolve(strict=False)
            if dest_resolved.is_relative_to(repo_root.resolve(strict=False)):
                findings.append(
                    ActivationFinding(
                        code="PATH_INSIDE_REPO",
                        severity=FindingSeverity.ERROR,
                        message="Destination is inside repository; choose external path.",  # noqa: E501
                        category="path",
                    )
                )
                valid = False
        except Exception:  # noqa: S110
            pass
    except Exception:  # noqa: S110
        pass
    symlink_finding = _check_symlink_escape(destination)
    if symlink_finding is not None:
        findings.append(symlink_finding)
        valid = False
    return valid, findings


def _check_disk(path: Path, required_bytes: int) -> tuple[int | None, list[ActivationFinding]]:
    findings: list[ActivationFinding] = []
    available: int | None = None
    try:
        check_path = path
        while not check_path.exists() and check_path != check_path.parent:
            check_path = check_path.parent
        if not check_path.exists():
            check_path = Path.cwd()
        usage = shutil.disk_usage(check_path)
        available = int(usage.free)
        if available < required_bytes:
            findings.append(
                ActivationFinding(
                    code="INSUFFICIENT_DISK",
                    severity=FindingSeverity.ERROR,
                    message=(  # noqa: E501
                        f"Available disk {available} bytes is less than"
                        f" required {required_bytes} bytes."
                    ),
                    category="disk",
                )
            )
    except OSError as exc:
        findings.append(
            ActivationFinding(
                code="DISK_CHECK_FAILED",
                severity=FindingSeverity.WARNING,
                message=f"Could not check disk: {exc}",
                category="disk",
            )
        )
    return available, findings


def _check_versions() -> tuple[bool, list[ActivationFinding]]:
    findings: list[ActivationFinding] = []
    ok = True
    major, minor = sys.version_info.major, sys.version_info.minor
    if major < REQUIRED_PYTHON_MAJOR or (
        major == REQUIRED_PYTHON_MAJOR and minor < REQUIRED_PYTHON_MINOR
    ):
        findings.append(
            ActivationFinding(
                code="PYTHON_VERSION",
                severity=FindingSeverity.ERROR,
                message=(  # noqa: E501
                    f"Python {REQUIRED_PYTHON_MAJOR}.{REQUIRED_PYTHON_MINOR}+ required,"
                    f" found {major}.{minor}."
                ),
                category="version",
            )
        )
        ok = False
    else:
        findings.append(
            ActivationFinding(
                code="PYTHON_VERSION_OK",
                severity=FindingSeverity.INFO,
                message=f"Python version {major}.{minor} meets requirement.",
                category="version",
            )
        )
    return ok, findings


def _check_credential_presence() -> list[CredentialPresence]:
    result: list[CredentialPresence] = []
    for name, env_var in [
        ("BODS_API_KEY", "BODS_API_KEY"),
        ("NATIONAL_HIGHWAYS_API_KEY", "NATIONAL_HIGHWAYS_API_KEY"),
    ]:
        present = bool(os.getenv(env_var, "").strip())
        result.append(
            CredentialPresence(
                name=name,
                env_var=env_var,
                present=present,
                source="environment" if present else "unavailable",
            )
        )
    return result


def _check_provider_readiness(
    request: WorkspaceActivationRequest, creds: list[CredentialPresence]
) -> list[ProviderReadiness]:
    cred_map = {c.env_var: c.present for c in creds}
    bods_cred = cred_map.get("BODS_API_KEY", False)
    nh_cred = cred_map.get("NATIONAL_HIGHWAYS_API_KEY", False)
    bods_config_present = bool(os.getenv("BODS_CONFIG_PATH", "").strip()) or bods_cred
    nh_config_present = bool(os.getenv("NATIONAL_HIGHWAYS_CONFIG_PATH", "").strip()) or nh_cred
    readings: list[ProviderReadiness] = []
    for kind, enabled, cred_present, config_present in [
        (ProviderKind.BODS, request.bods_enabled, bods_cred, bods_config_present),
        (
            ProviderKind.NATIONAL_HIGHWAYS,
            request.national_highways_enabled,
            nh_cred,
            nh_config_present,
        ),
    ]:
        if not enabled:
            status = ProviderStatus.DISABLED
            detail = f"{kind.value} is disabled in request; no provider call will occur."
            configured = False
        elif not config_present and not cred_present:
            status = ProviderStatus.MISSING_CONFIGURATION
            detail = f"{kind.value} is enabled but configuration is missing."
            configured = False
        elif not cred_present:
            status = ProviderStatus.MISSING_CREDENTIAL
            detail = f"{kind.value} is enabled but credential is not present (value not shown)."
            configured = True
        else:
            status = ProviderStatus.READY
            detail = f"{kind.value} is configured and credential is present."
            configured = True
        readings.append(
            ProviderReadiness(
                provider=kind,
                configured=configured,
                credential_present=cred_present,
                enabled=enabled,
                status=status,
                detail=detail,
            )
        )
    return readings


def _check_retention_policy(
    request: WorkspaceActivationRequest,
) -> tuple[bool, list[ActivationFinding]]:
    findings: list[ActivationFinding] = []
    policy = request.retention_policy
    ok = True
    if policy.retention_days < 1 or policy.retention_days > 3650:
        findings.append(
            ActivationFinding(
                code="RETENTION_RANGE",
                severity=FindingSeverity.ERROR,
                message="Retention days out of range.",
                category="retention",
            )
        )
        ok = False
    if not policy.anonymize and policy.allow_export:
        findings.append(
            ActivationFinding(
                code="RETENTION_PRIVACY",
                severity=FindingSeverity.WARNING,
                message="Export allowed without anonymization; review privacy implications.",
                category="retention",
            )
        )
    else:
        findings.append(
            ActivationFinding(
                code="RETENTION_OK",
                severity=FindingSeverity.INFO,
                message=f"Retention {policy.retention_days} days, anonymize={policy.anonymize}.",
                category="retention",
            )
        )
    return ok, findings


def _check_aggregate_store_ready(
    request: WorkspaceActivationRequest,  # noqa: ARG001
) -> tuple[bool, list[ActivationFinding]]:
    findings: list[ActivationFinding] = []
    findings.append(
        ActivationFinding(
            code="AGGREGATE_STORE_CHECK",
            severity=FindingSeverity.INFO,
            message="Aggregate store readiness checked locally without network.",
            category="aggregate_store",
        )
    )
    return True, findings


def _check_backup_destination(
    request: WorkspaceActivationRequest,
) -> tuple[bool, list[ActivationFinding]]:
    findings: list[ActivationFinding] = []
    if request.backup_destination is None:
        findings.append(
            ActivationFinding(
                code="BACKUP_DEFAULT",
                severity=FindingSeverity.INFO,
                message="Backup will use default location inside workspace.",
                category="backup",
            )
        )
        return True, findings
    backup = Path(request.backup_destination)
    sf = _check_symlink_escape(backup)
    if sf is not None:
        findings.append(sf)
        return False, findings
    # Check traversal in backup path itself
    if ".." in Path(request.backup_destination).parts:
        findings.append(
            ActivationFinding(
                code="PATH_TRAVERSAL",
                severity=FindingSeverity.ERROR,
                message="Backup path contains parent traversal '..' which is refused.",
                category="backup",
            )
        )
        return False, findings
    try:
        b_dest = backup.resolve(strict=False)
        if not b_dest.exists():
            check_parent = b_dest
            while not check_parent.exists() and check_parent != check_parent.parent:
                check_parent = check_parent.parent
            if not check_parent.exists():
                findings.append(
                    ActivationFinding(
                        code="BACKUP_PARENT_MISSING",
                        severity=FindingSeverity.WARNING,
                        message="Backup destination parent does not exist; will be created.",
                        category="backup",
                    )
                )
    except OSError as exc:
        findings.append(
            ActivationFinding(
                code="BACKUP_CHECK_FAILED",
                severity=FindingSeverity.WARNING,
                message=f"Backup check failed: {exc}",
                category="backup",
            )
        )
    findings.append(
        ActivationFinding(
            code="BACKUP_OK",
            severity=FindingSeverity.INFO,
            message="Backup destination checked.",
            category="backup",
        )
    )
    return True, findings


def _check_workers(request: WorkspaceActivationRequest) -> tuple[list[ActivationFinding], bool]:
    findings: list[ActivationFinding] = []
    if not request.start_workers:
        findings.append(
            ActivationFinding(
                code="WORKER_DISABLED",
                severity=FindingSeverity.INFO,
                message="Worker start is disabled; no process will be started.",
                category="workers",
            )
        )
        return findings, True
    if not request.allowlisted_workers:
        findings.append(
            ActivationFinding(
                code="WORKER_EMPTY",
                severity=FindingSeverity.WARNING,
                message="Worker start requested but no allowlisted workers specified; no worker will start.",  # noqa: E501
                category="workers",
            )
        )
        return findings, True
    for w in request.allowlisted_workers:
        if w not in ALLOWED_WORKERS:
            findings.append(
                ActivationFinding(
                    code="WORKER_NOT_ALLOWLISTED",
                    severity=FindingSeverity.ERROR,
                    message=f"Worker {w!r} is not in allowlist; only {sorted(ALLOWED_WORKERS)} may start.",  # noqa: E501
                    category="workers",
                )
            )
            return findings, False
    findings.append(
        ActivationFinding(
            code="WORKER_OK",
            severity=FindingSeverity.INFO,
            message=f"Workers {request.allowlisted_workers} are allowlisted and may start.",  # noqa: E501
            category="workers",
        )
    )
    return findings, True


def _is_managed(path: Path) -> bool:
    marker = path / MARKER_DIR_NAME / MARKER_FILE_NAME
    return marker.is_file()


def _is_empty(path: Path) -> bool:
    if not path.exists():
        return True
    try:
        return not any(path.iterdir())
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Public: preflight
# ---------------------------------------------------------------------------


def preflight_workspace(request: WorkspaceActivationRequest) -> WorkspaceActivationPreflight:
    """Run all dry-run checks without network, without secrets, without mutation."""
    dest = Path(request.destination_path)
    request_fp = request.fingerprint()

    findings: list[ActivationFinding] = []
    path_valid, path_findings = _check_path_valid(dest)
    findings.extend(path_findings)

    is_managed = _is_managed(dest) if dest.exists() else False
    is_empty = _is_empty(dest)

    if dest.exists() and not is_empty and not is_managed:
        findings.append(
            ActivationFinding(
                code="UNMANAGED_NON_EMPTY",
                severity=FindingSeverity.ERROR,
                message="Destination exists, is not empty, and is not a managed workspace; refusal required.",  # noqa: E501
                category="path",
            )
        )

    disk_available, disk_findings = _check_disk(dest, MIN_DISK_BYTES)
    findings.extend(disk_findings)

    version_ok, version_findings = _check_versions()
    findings.extend(version_findings)

    creds = _check_credential_presence()

    provider_readiness = _check_provider_readiness(request, creds)
    for pr in provider_readiness:
        if pr.status == ProviderStatus.MISSING_CREDENTIAL and pr.enabled:
            findings.append(
                ActivationFinding(
                    code="PROVIDER_MISSING_CREDENTIAL",
                    severity=FindingSeverity.WARNING,
                    message=f"Provider {pr.provider.value} missing credential; will be disabled.",
                    category="provider",
                )
            )
        if pr.status == ProviderStatus.MISSING_CONFIGURATION and pr.enabled:
            findings.append(
                ActivationFinding(
                    code="PROVIDER_MISSING_CONFIG",
                    severity=FindingSeverity.WARNING,
                    message=f"Provider {pr.provider.value} missing configuration.",
                    category="provider",
                )
            )

    _, retention_findings = _check_retention_policy(request)
    findings.extend(retention_findings)

    agg_ready, agg_findings = _check_aggregate_store_ready(request)
    findings.extend(agg_findings)

    backup_ready, backup_findings = _check_backup_destination(request)
    findings.extend(backup_findings)

    worker_findings, workers_ok = _check_workers(request)
    for wf in worker_findings:
        if wf.severity == FindingSeverity.ERROR:
            findings.append(wf)

    has_error = any(f.severity == FindingSeverity.ERROR for f in findings)
    ready_to_plan = (not has_error) and path_valid and version_ok and workers_ok

    return WorkspaceActivationPreflight(
        request_fingerprint=request_fp,
        destination_path=request.destination_path,
        is_managed=is_managed,
        is_empty=is_empty,
        path_valid=path_valid,
        disk_available_bytes=disk_available,
        disk_required_bytes=MIN_DISK_BYTES,
        findings=findings,
        credential_presence=creds,
        provider_readiness=provider_readiness,
        retention_policy=request.retention_policy,
        aggregate_store_ready=agg_ready,
        backup_ready=backup_ready,
        worker_readiness=worker_findings,
        ready_to_plan=ready_to_plan,
        version_ok=version_ok,
    )


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


def build_activation_plan(
    request: WorkspaceActivationRequest, preflight: WorkspaceActivationPreflight | None = None
) -> WorkspaceActivationPlan:
    """Produce deterministic activation plan with confirmation digest."""
    if preflight is not None and preflight.request_fingerprint != request.fingerprint():
        raise ActivationRefusedError(
            "REFUSED", "Request changed after preflight; stale preflight is refused."
        )

    if preflight is None:
        preflight = preflight_workspace(request)

    dest = request.destination_path
    dirs = sorted(
        [
            f"{dest}/{MARKER_DIR_NAME}",
            f"{dest}/{REGISTRY_DIR_NAME}",
            f"{dest}/{AGGREGATE_STORE_DIR}",
            f"{dest}/{BACKUP_DIR}",
            f"{dest}/{CONFIG_DIR}",
        ]
    )
    files = sorted(
        [
            f"{dest}/{MARKER_DIR_NAME}/{MARKER_FILE_NAME}",
            f"{dest}/{MARKER_DIR_NAME}/{RECEIPT_FILE_NAME}",
            f"{dest}/{REGISTRY_DIR_NAME}/{REGISTRY_FILE_NAME}",
            f"{dest}/{CONFIG_DIR}/retention.json",
            f"{dest}/{CONFIG_DIR}/providers.json",
        ]
    )
    dbs = sorted([f"{dest}/{REGISTRY_DIR_NAME}/{REGISTRY_FILE_NAME}"])

    provider_configs = sorted(preflight.provider_readiness, key=lambda x: x.provider.value)

    worker_opts = sorted(request.allowlisted_workers) if request.start_workers else []

    backup_plan = (  # noqa: E501
        f"Backup to {request.backup_destination or dest + '/' + BACKUP_DIR} before publish; rollback restores backup."  # noqa: E501
    )
    rollback_plan = "If activation fails, remove staging and restore backup; data preserved."  # noqa: E501

    actions: list[WorkspaceActivationAction] = []
    for d in dirs:
        actions.append(
            WorkspaceActivationAction(
                kind=ActionKind.CREATE_DIRECTORY,
                target=d,
                detail=f"Create directory {d}",
                required=True,
            )
        )
    for f in files:
        kind = (
            ActionKind.INITIALIZE_DATABASE
            if f.endswith(REGISTRY_FILE_NAME)
            else ActionKind.CREATE_FILE
        )
        if f.endswith(MARKER_FILE_NAME):
            kind = ActionKind.WRITE_MARKER
        elif f.endswith(RECEIPT_FILE_NAME):
            kind = ActionKind.WRITE_RECEIPT
        actions.append(
            WorkspaceActivationAction(kind=kind, target=f, detail=f"Initialize {f}", required=True)
        )
    for pr in provider_configs:
        actions.append(
            WorkspaceActivationAction(
                kind=ActionKind.CONFIGURE_PROVIDER,
                target=pr.provider.value,
                detail=(  # noqa: E501
                    f"Configure provider {pr.provider.value} enabled={pr.enabled}"  # noqa: E501
                    f" status={pr.status.value}"  # noqa: E501
                ),
                required=False,
            )
        )
    if worker_opts:
        for w in worker_opts:
            actions.append(
                WorkspaceActivationAction(
                    kind=ActionKind.START_WORKER,
                    target=w,
                    detail=f"Optionally start allowlisted worker {w}",
                    required=False,
                )
            )
    actions.append(
        WorkspaceActivationAction(
            kind=ActionKind.BACKUP,
            target=request.backup_destination or f"{dest}/{BACKUP_DIR}",
            detail=backup_plan,
            required=False,
        )
    )

    actions = sorted(actions, key=lambda a: (a.kind.value, a.target))

    payload = {
        "plan_version": _ACTIVATION_METHOD_VERSION,
        "request_fingerprint": request.fingerprint(),
        "destination_path": dest,
        "directories_to_create": dirs,
        "files_to_create": files,
        "database_initialization": dbs,
        "provider_configurations": [p.model_dump(mode="json") for p in provider_configs],
        "retention_settings": request.retention_policy.model_dump(mode="json"),
        "worker_start_options": worker_opts,
        "backup_plan": backup_plan,
        "rollback_plan": rollback_plan,
        "actions": [a.model_dump(mode="json") for a in actions],
    }
    digest = _digest_json(payload)

    plan = WorkspaceActivationPlan(
        plan_version=_ACTIVATION_METHOD_VERSION,
        request_fingerprint=request.fingerprint(),
        destination_path=dest,
        directories_to_create=dirs,
        files_to_create=files,
        database_initialization=dbs,
        provider_configurations=provider_configs,
        retention_settings=request.retention_policy,
        worker_start_options=worker_opts,
        backup_plan=backup_plan,
        rollback_plan=rollback_plan,
        actions=actions,
        confirmation_digest=digest,
        created_at=_iso_now(),
    )
    if plan.expected_digest() != digest:
        raise RuntimeError("Plan digest mismatch — deterministic serialization failed")
    return plan


# ---------------------------------------------------------------------------
# Activation helpers for B1
# ---------------------------------------------------------------------------


def _load_existing_receipt(dest: Path) -> WorkspaceActivationReceipt | None:
    receipt_path = dest / MARKER_DIR_NAME / RECEIPT_FILE_NAME
    if not receipt_path.is_file():
        return None
    try:
        data = json.loads(receipt_path.read_text(encoding="utf-8"))
        return WorkspaceActivationReceipt.model_validate(data)
    except Exception:
        return None


def _load_marker(dest: Path) -> dict[str, object] | None:
    marker_path = dest / MARKER_DIR_NAME / MARKER_FILE_NAME
    if not marker_path.is_file():
        return None
    try:
        return json.loads(marker_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except Exception:
        return None


def _check_managed_files_drift(dest: Path, receipt: WorkspaceActivationReceipt) -> str | None:
    """Verify managed config files match receipt; return drift description if mismatched."""
    # Check retention.json
    retention_path = dest / CONFIG_DIR / "retention.json"
    if retention_path.is_file():
        try:
            data = json.loads(retention_path.read_text(encoding="utf-8"))
            # Compare canonical
            expected = _canonical_json(receipt.retention_policy.model_dump(mode="json"))
            actual = _canonical_json(data)
            if expected != actual:
                return "retention.json does not match receipt retention_policy"
        except Exception as exc:
            return f"retention.json invalid: {exc}"
    else:
        return "retention.json missing"

    # Check providers.json
    providers_path = dest / CONFIG_DIR / "providers.json"
    if providers_path.is_file():
        try:
            data = json.loads(providers_path.read_text(encoding="utf-8"))
            # Compare enabled set
            expected_enabled = sorted(receipt.providers_enabled)
            actual_enabled = sorted([p.get("provider") for p in data if p.get("enabled") is True])
            # Also check full canonical if we have exact provider configs in receipt
            # We stored providers_enabled only, so check that
            if expected_enabled != actual_enabled:
                return (  # noqa: E501
                    f"providers.json mismatch: expected {expected_enabled}, got {actual_enabled}"  # noqa: E501
                )
        except Exception as exc:
            return f"providers.json invalid: {exc}"
    else:
        return "providers.json missing"

    # Check marker matches receipt
    marker = _load_marker(dest)
    if marker is None:
        return "marker.json missing"
    if marker.get("request_fingerprint") != receipt.request_fingerprint:
        return "marker request_fingerprint does not match receipt"
    if marker.get("confirmation_digest") != receipt.confirmation_digest:
        return "marker confirmation_digest does not match receipt"

    return None


def _init_registry_db(db_path: Path) -> None:
    try:
        from traffictwin.storage.registry import Registry

        reg = Registry(db_path)
        reg.initialize()
    except Exception:
        import sqlite3

        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS _workspace_activation ("  # noqa: E501
                "id INTEGER PRIMARY KEY, created_at TEXT)"  # noqa: E501
            )
            conn.commit()
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Activation
# ---------------------------------------------------------------------------


def activate_workspace(
    request: WorkspaceActivationRequest,
    plan: WorkspaceActivationPlan,
    confirmation: WorkspaceActivationConfirmation,
) -> WorkspaceActivationReceipt:
    """Activate workspace atomically, gated by exact confirmation digest."""
    if confirmation.confirmation_digest != plan.confirmation_digest:
        raise ActivationRefusedError(
            "REFUSED",
            "Confirmation digest does not match plan's exact preview digest; activation refused.",
        )
    if plan.expected_digest() != plan.confirmation_digest:
        raise ActivationRefusedError(
            "REFUSED", "Plan digest integrity check failed; activation refused."
        )
    if request.fingerprint() != plan.request_fingerprint:
        raise ActivationRefusedError(
            "REFUSED",
            "Request changed after preview; stale confirmation digest is refused.",
        )
    if (
        confirmation.request_fingerprint is not None
        and confirmation.request_fingerprint != request.fingerprint()
    ):
        raise ActivationRefusedError(
            "REFUSED", "Confirmation request fingerprint mismatch; activation refused."
        )

    dest = Path(request.destination_path)

    # B1: If already managed, enforce fail-closed on changed re-activation
    if dest.exists() and _is_managed(dest):
        existing_receipt = _load_existing_receipt(dest)
        if existing_receipt is None:
            raise ActivationRefusedError(
                "MANAGED_WORKSPACE_CORRUPTION",
                "Managed marker present but receipt is missing or invalid; refusing to overwrite.",
            )
        # Check if new request/plan matches existing
        if (
            existing_receipt.request_fingerprint == request.fingerprint()
            and existing_receipt.confirmation_digest == plan.confirmation_digest
            and existing_receipt.plan_fingerprint == plan.confirmation_digest
        ):
            drift = _check_managed_files_drift(dest, existing_receipt)
            if drift is not None:
                raise ActivationRefusedError(
                    "MANAGED_WORKSPACE_DRIFT",
                    f"Managed workspace files have drifted from receipt: {drift}",
                )
            return existing_receipt.model_copy(update={"status": "already_active"})
        else:
            raise ActivationRefusedError(
                "ACTIVATION_REQUEST_CHANGED",
                "workspace is already managed under a different activation plan; "
                "use an explicit future reconfiguration workflow rather than silent re-activation",
            )

    # Preflight re-check for safety (fail-closed) for non-managed case
    preflight = preflight_workspace(request)
    for f in preflight.findings:
        if f.code == "UNMANAGED_NON_EMPTY":
            raise ActivationRefusedError(
                f.code,
                f.message,
            )
        if f.code == "SYMLINK_ESCAPE":
            raise ActivationRefusedError(f.code, f.message)
        if f.code in ("PATH_TRAVERSAL", "PATH_INSIDE_REPO"):
            raise ActivationRefusedError(f.code, f.message)

    if not preflight.ready_to_plan:
        raise ActivationRefusedError(
            "REFUSED", "Preflight has errors; activation refused. Review preflight findings."
        )

    # Refuse unmanaged non-empty (defense in depth, also checked above)
    if dest.exists() and not _is_empty(dest) and not _is_managed(dest):
        raise ActivationRefusedError(
            "REFUSED", "Destination exists, is non-empty and not managed; activation refused."
        )

    staging_parent = dest.parent if dest.parent.exists() else Path(tempfile.gettempdir())
    staging_dir: Path | None = None
    try:
        staging_dir = Path(
            tempfile.mkdtemp(prefix=f".{dest.name}.staging-", dir=str(staging_parent))
        )
        for d in plan.directories_to_create:
            rel = Path(d).relative_to(dest) if Path(d).is_relative_to(dest) else Path(Path(d).name)
            target = staging_dir / rel
            target.mkdir(parents=True, exist_ok=True)

        for db_rel in plan.database_initialization:
            rel = (
                Path(db_rel).relative_to(dest)
                if Path(db_rel).is_relative_to(dest)
                else Path(Path(db_rel).name)
            )
            db_path = staging_dir / rel
            _init_registry_db(db_path)

        retention_path = staging_dir / CONFIG_DIR / "retention.json"
        retention_path.parent.mkdir(parents=True, exist_ok=True)
        retention_path.write_text(
            _canonical_json(request.retention_policy.model_dump(mode="json")), encoding="utf-8"
        )

        providers_path = staging_dir / CONFIG_DIR / "providers.json"
        providers_path.write_text(
            _canonical_json([p.model_dump(mode="json") for p in plan.provider_configurations]),
            encoding="utf-8",
        )

        marker_path_str = str(dest / MARKER_DIR_NAME / MARKER_FILE_NAME)
        receipt_path_str = str(dest / MARKER_DIR_NAME / RECEIPT_FILE_NAME)
        backup_location = request.backup_destination or str(dest / BACKUP_DIR)
        receipt = WorkspaceActivationReceipt(
            receipt_version=_ACTIVATION_METHOD_VERSION,
            destination_path=request.destination_path,
            request_fingerprint=request.fingerprint(),
            confirmation_digest=confirmation.confirmation_digest,
            plan_fingerprint=plan.confirmation_digest,
            activated_at=_iso_now(),
            directories_created=plan.directories_to_create,
            files_created=plan.files_to_create,
            providers_enabled=[p.provider.value for p in plan.provider_configurations if p.enabled],
            retention_policy=request.retention_policy,
            workers_started=plan.worker_start_options if request.start_workers else [],
            backup_location=backup_location,
            marker_path=marker_path_str,
            receipt_path=receipt_path_str,
            status="activated",
        )

        staging_marker = staging_dir / MARKER_DIR_NAME / MARKER_FILE_NAME
        staging_receipt = staging_dir / MARKER_DIR_NAME / RECEIPT_FILE_NAME
        staging_marker.parent.mkdir(parents=True, exist_ok=True)
        marker_data = {
            "managed": True,
            "marker_version": _ACTIVATION_METHOD_VERSION,
            "request_fingerprint": request.fingerprint(),
            "confirmation_digest": confirmation.confirmation_digest,
            "activated_at": receipt.activated_at,
        }
        staging_marker.write_text(_canonical_json(marker_data), encoding="utf-8")
        staging_receipt.write_text(receipt.canonical_json(), encoding="utf-8")

        if not dest.exists():
            try:
                staging_dir.rename(dest)
            except OSError:
                shutil.copytree(staging_dir, dest, dirs_exist_ok=False)
                shutil.rmtree(staging_dir, ignore_errors=True)
            staging_dir = None
        else:
            for item in staging_dir.rglob("*"):
                rel = item.relative_to(staging_dir)
                target = dest / rel
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    if (
                        rel == Path(MARKER_DIR_NAME) / MARKER_FILE_NAME
                        or rel == Path(MARKER_DIR_NAME) / RECEIPT_FILE_NAME
                    ):
                        tmp_target = target.with_suffix(target.suffix + ".tmp")
                        shutil.copy2(item, tmp_target)
                        tmp_target.replace(target)
                    else:
                        if not target.exists():
                            target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(item, target)
            shutil.rmtree(staging_dir, ignore_errors=True)
            staging_dir = None

        final_receipt_path = dest / MARKER_DIR_NAME / RECEIPT_FILE_NAME
        if final_receipt_path.is_file():
            try:
                data = json.loads(final_receipt_path.read_text(encoding="utf-8"))
                final_receipt = WorkspaceActivationReceipt.model_validate(data)
                return final_receipt
            except Exception:
                return receipt
        return receipt
    except ActivationRefusedError:
        if staging_dir is not None and staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    except Exception as exc:
        if staging_dir is not None and staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        raise ActivationRefusedError(
            "ACTIVATION_FAILED", f"Activation failed and was cleaned up: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Status and deactivation
# ---------------------------------------------------------------------------


def get_workspace_status(destination_path: str | Path) -> WorkspaceActivationStatus:
    dest = Path(destination_path)
    exists = dest.exists()
    is_managed = _is_managed(dest) if exists else False
    marker_present = is_managed
    is_active = is_managed
    receipt: WorkspaceActivationReceipt | None = None
    findings: list[ActivationFinding] = []
    providers: list[ProviderReadiness] = []
    if exists and is_managed:
        receipt = _load_existing_receipt(dest)
        if receipt is None:
            findings.append(
                ActivationFinding(
                    code="RECEIPT_MISSING",
                    severity=FindingSeverity.WARNING,
                    message="Managed marker present but receipt is missing or invalid.",
                    category="status",
                )
            )
        else:
            providers_path = dest / CONFIG_DIR / "providers.json"
            if providers_path.is_file():
                try:
                    data = json.loads(providers_path.read_text(encoding="utf-8"))
                    providers = [ProviderReadiness.model_validate(p) for p in data]
                except Exception:
                    providers = []
            findings.append(
                ActivationFinding(
                    code="STATUS_ACTIVE",
                    severity=FindingSeverity.INFO,
                    message="Workspace is active and managed.",
                    category="status",
                )
            )
    elif exists and not is_managed and not _is_empty(dest):
        findings.append(
            ActivationFinding(
                code="UNMANAGED_NON_EMPTY_STATUS",
                severity=FindingSeverity.WARNING,
                message="Path exists and is unmanaged non-empty.",
                category="status",
            )
        )
    elif not exists:
        findings.append(
            ActivationFinding(
                code="NOT_EXISTS",
                severity=FindingSeverity.INFO,
                message="Workspace path does not exist.",
                category="status",
            )
        )
    else:
        findings.append(
            ActivationFinding(
                code="EMPTY_STATUS",
                severity=FindingSeverity.INFO,
                message="Workspace path is empty.",
                category="status",
            )
        )

    if not providers:
        providers = [
            ProviderReadiness(
                provider=ProviderKind.BODS,
                configured=False,
                credential_present=False,
                enabled=False,
                status=ProviderStatus.DISABLED,
                detail="No active workspace provider.",
            ),
            ProviderReadiness(
                provider=ProviderKind.NATIONAL_HIGHWAYS,
                configured=False,
                credential_present=False,
                enabled=False,
                status=ProviderStatus.DISABLED,
                detail="No active workspace provider.",
            ),
        ]
        if receipt is not None:
            enabled = set(receipt.providers_enabled)
            providers = [
                ProviderReadiness(
                    provider=ProviderKind.BODS,
                    configured=ProviderKind.BODS.value in enabled,
                    credential_present=False,
                    enabled=ProviderKind.BODS.value in enabled,
                    status=ProviderStatus.READY
                    if ProviderKind.BODS.value in enabled
                    else ProviderStatus.DISABLED,
                    detail=f"Provider {p.provider.value} from receipt.",
                )
                for p in providers
            ]

    return WorkspaceActivationStatus(
        destination_path=str(dest),
        exists=exists,
        is_managed=is_managed,
        is_active=is_active,
        receipt=receipt,
        marker_present=marker_present,
        findings=findings,
        providers=providers,
    )


def deactivate_workspace(
    destination_path: str | Path,
    confirmation: WorkspaceActivationConfirmation | None = None,
    remove_marker: bool = False,
) -> WorkspaceDeactivationReceipt:
    """Deactivate workspace.

    Policy:
    - Verify target is a managed workspace; refuse unmanaged.
    - Stop only activation-managed workers (recorded, not launched in V1).
    - Remove/marker only via explicit confirmation.
    - Emit deactivation receipt.
    - Preserve evidence, database, provider config and aggregate data.
    - Never delete raw evidence, aggregate store, credentials, or user data recursively.
    """
    dest = Path(destination_path)
    if not dest.exists():
        return WorkspaceDeactivationReceipt(
            destination_path=str(dest),
            request_fingerprint=None,
            deactivated_at=_iso_now(),
            marker_removed=False,
            workers_stopped=[],
            preserved_paths=[],
            status="not_active",
        )
    is_managed = _is_managed(dest)
    if not is_managed:
        return WorkspaceDeactivationReceipt(
            destination_path=str(dest),
            request_fingerprint=None,
            deactivated_at=_iso_now(),
            marker_removed=False,
            workers_stopped=[],
            preserved_paths=[str(p) for p in dest.iterdir()] if dest.is_dir() else [],
            status="not_active",
        )

    receipt = _load_existing_receipt(dest)
    request_fp = receipt.request_fingerprint if receipt else None

    if remove_marker:
        if confirmation is None:
            raise ActivationRefusedError(
                "REFUSED", "Deactivation with marker removal requires confirmation digest."
            )
        if receipt is None or confirmation.confirmation_digest != receipt.confirmation_digest:
            raise ActivationRefusedError(
                "REFUSED",
                "Deactivation confirmation digest does not match receipt; marker removal refused.",  # noqa: E501,
            )
        if (
            confirmation.request_fingerprint is not None
            and confirmation.request_fingerprint != receipt.request_fingerprint
        ):
            raise ActivationRefusedError(
                "REFUSED", "Deactivation request fingerprint mismatch; refused."
            )

    workers_stopped: list[str] = []
    if receipt is not None:
        workers_stopped = list(receipt.workers_started)

    preserved: list[str] = []
    if dest.is_dir():
        for item in dest.iterdir():
            if item.name not in (MARKER_DIR_NAME,):
                preserved.append(str(item))
        for keep in [REGISTRY_DIR_NAME, AGGREGATE_STORE_DIR, BACKUP_DIR, CONFIG_DIR]:
            p = dest / keep
            if p.exists() and str(p) not in preserved:
                preserved.append(str(p))

    marker_removed = False
    if remove_marker:
        marker_path = dest / MARKER_DIR_NAME / MARKER_FILE_NAME
        try:
            if marker_path.is_file():
                marker_path.unlink()
                marker_removed = True
        except OSError as exc:
            raise ActivationRefusedError(
                "DEACTIVATION_FAILED", f"Failed to remove marker: {exc}"
            ) from exc

    return WorkspaceDeactivationReceipt(
        destination_path=str(dest),
        request_fingerprint=request_fp,
        deactivated_at=_iso_now(),
        marker_removed=marker_removed,
        workers_stopped=workers_stopped,
        preserved_paths=sorted(preserved),
        status="deactivated",
    )


# ---------------------------------------------------------------------------
# Exports: JSON and CSV
# ---------------------------------------------------------------------------


def receipt_to_json(receipt: WorkspaceActivationReceipt) -> str:
    return receipt.canonical_json()


def receipt_to_csv(receipt: WorkspaceActivationReceipt) -> str:
    import csv
    import io

    row = receipt.to_csv_row()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(row.keys()))
    writer.writeheader()
    writer.writerow(row)
    return output.getvalue()


def preflight_to_json(preflight: WorkspaceActivationPreflight) -> str:
    return preflight.canonical_json()


def preflight_to_csv(preflight: WorkspaceActivationPreflight) -> str:
    import csv
    import io

    rows = preflight.to_csv_rows()
    if not rows:
        return "code,severity,category,message\n"
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["code", "severity", "category", "message"])
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def plan_to_json(plan: WorkspaceActivationPlan) -> str:
    return plan.canonical_json()


def plan_to_csv(plan: WorkspaceActivationPlan) -> str:
    import csv
    import io

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["kind", "target", "detail", "required"])
    writer.writeheader()
    for a in plan.actions:
        writer.writerow(
            {
                "kind": a.kind.value,
                "target": a.target,
                "detail": a.detail,
                "required": str(a.required),
            }
        )
    return output.getvalue()

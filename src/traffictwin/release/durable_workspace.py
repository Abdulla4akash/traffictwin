"""Preview-confirmed durable v0.7 workspace creation.

This module wraps the existing REL-01 workspace layout with the operational
assurances required by ``NEXT-01``: a path-free preview, exact confirmation,
owner-only permissions, an empty baseline registry backup, an isolated restore
drill, atomic publication, and exact retry.  It never discovers an existing
private workspace and never acquires or imports source data.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
from collections.abc import Callable
from ctypes import CDLL, c_char_p, c_int, c_uint, get_errno
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.release.compatibility import (
    V07_ACTIVE_REGISTRY,
    V07_REQUIRED_DIRECTORIES,
    V07CompatibilityError,
    V07WorkspaceInspection,
    initialise_v07_workspace,
    inspect_v07_workspace,
    v07_workspace_contract,
)
from traffictwin.storage.migrations import (
    CURRENT_REGISTRY_SCHEMA_VERSION,
    inspect_registry_migrations,
)

DURABLE_WORKSPACE_SCHEMA_VERSION: Literal["traffictwin.durable-workspace.v1"] = (
    "traffictwin.durable-workspace.v1"
)
DURABLE_WORKSPACE_METHOD_VERSION: Literal["v07-durable-workspace-1.0"] = "v07-durable-workspace-1.0"
DURABLE_WORKSPACE_RECEIPT_RELATIVE_PATH = Path("registry/durable-workspace-receipt.json")
DURABLE_WORKSPACE_BACKUP_RELATIVE_PATH = Path("registry/baseline-backup/traffictwin.sqlite")
DURABLE_WORKSPACE_MINIMUM_FREE_BYTES = 8 * 1024 * 1024
DURABLE_WORKSPACE_MAX_RECEIPT_BYTES = 256 * 1024
_STAGING_PREFIX = ".traffictwin-v07-durable-"


class V07DurableWorkspaceError(RuntimeError):
    """A path-free typed durable-workspace refusal."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class V07DurableWorkspacePlan(BaseModel):
    """Mutation-free, path-free plan for one new durable workspace."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["traffictwin.durable-workspace.v1"] = DURABLE_WORKSPACE_SCHEMA_VERSION
    method_version: Literal["v07-durable-workspace-1.0"] = DURABLE_WORKSPACE_METHOD_VERSION
    capability_id: Literal["REL-01"] = "REL-01"
    capability_status: Literal["planned"] = "planned"
    operation: Literal["new_only_durable_workspace"] = "new_only_durable_workspace"
    workspace_handle: str = Field(pattern=r"^workspace-[0-9a-f]{16}$")
    workspace_contract_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    required_directories: tuple[str, ...]
    target_absent: Literal[True] = True
    parent_owned_by_current_user: Literal[True] = True
    parent_owner_only: Literal[True] = True
    repository_descendant: Literal[False] = False
    required_free_bytes: Literal[8388608] = 8388608
    available_free_bytes: int = Field(ge=0)
    orphan_staging_handles: tuple[str, ...] = ()
    baseline_backup_required: Literal[True] = True
    isolated_restore_required: Literal[True] = True
    source_acquisition_authorised: Literal[False] = False
    activatable: bool
    blockers: tuple[str, ...] = ()
    actions: tuple[str, ...]

    @model_validator(mode="after")
    def validate_plan(self) -> V07DurableWorkspacePlan:
        if self.required_directories != V07_REQUIRED_DIRECTORIES:
            raise ValueError("required directories must match the v0.7 workspace contract")
        expected_activatable = (
            not self.blockers
            and not self.orphan_staging_handles
            and self.available_free_bytes >= self.required_free_bytes
        )
        if self.activatable != expected_activatable:
            raise ValueError("activatable must match blockers, orphan state, and free space")
        return self

    def confirmation_fingerprint(self) -> str:
        """Return a stable confirmation digest excluding changing free-space telemetry."""

        payload = self.model_dump(mode="json", exclude={"available_free_bytes", "activatable"})
        return _sha256_bytes(_canonical_json(payload).encode("utf-8"))


class V07BaselineBackupReceipt(BaseModel):
    """Proof that the empty active registry was copied and restored in isolation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["traffictwin.durable-workspace.v1"] = DURABLE_WORKSPACE_SCHEMA_VERSION
    registry_relative_path: Literal["registry/traffictwin.sqlite"] = V07_ACTIVE_REGISTRY
    backup_relative_path: Literal["registry/baseline-backup/traffictwin.sqlite"] = (
        "registry/baseline-backup/traffictwin.sqlite"
    )
    registry_schema_version: int = Field(ge=1)
    registry_size_bytes: int = Field(ge=1)
    registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    backup_size_bytes: int = Field(ge=1)
    backup_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    restored_size_bytes: int = Field(ge=1)
    restored_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    isolated_restore_verified: Literal[True] = True

    @model_validator(mode="after")
    def validate_reconciliation(self) -> V07BaselineBackupReceipt:
        if not (self.registry_size_bytes == self.backup_size_bytes == self.restored_size_bytes):
            raise ValueError("registry, backup, and restored sizes must match")
        if not (self.registry_sha256 == self.backup_sha256 == self.restored_sha256):
            raise ValueError("registry, backup, and restored digests must match")
        if self.registry_schema_version != CURRENT_REGISTRY_SCHEMA_VERSION:
            raise ValueError("baseline backup must use the current registry schema")
        return self


class V07DurableWorkspaceReceipt(BaseModel):
    """Path-free terminal receipt for an atomically published durable workspace."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["traffictwin.durable-workspace.v1"] = DURABLE_WORKSPACE_SCHEMA_VERSION
    method_version: Literal["v07-durable-workspace-1.0"] = DURABLE_WORKSPACE_METHOD_VERSION
    capability_id: Literal["REL-01"] = "REL-01"
    capability_status: Literal["planned"] = "planned"
    operation: Literal["new_only_durable_workspace"] = "new_only_durable_workspace"
    workspace_handle: str = Field(pattern=r"^workspace-[0-9a-f]{16}$")
    plan_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at_utc: datetime
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    active_registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_backup: V07BaselineBackupReceipt
    workspace_reopened_and_verified: Literal[True] = True
    owner_only_permissions_verified: Literal[True] = True
    contains_accepted_source_data: Literal[False] = False
    source_acquisition_performed: Literal[False] = False
    historical_store_activated: Literal[False] = False
    private_path_persisted: Literal[False] = False
    exact_retry: bool = False

    @model_validator(mode="after")
    def validate_receipt(self) -> V07DurableWorkspaceReceipt:
        if self.created_at_utc.tzinfo is None or self.created_at_utc.utcoffset() is None:
            raise ValueError("created_at_utc must be timezone-aware")
        if self.active_registry_sha256 != self.baseline_backup.registry_sha256:
            raise ValueError("active registry must match the verified baseline backup")
        return self

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        return _sha256_bytes(self.canonical_json().encode("utf-8"))


@dataclass(frozen=True, slots=True)
class V07DurableWorkspaceResult:
    """Private operational paths plus the safe public receipt."""

    workspace_path: Path
    receipt_path: Path
    inspection: V07WorkspaceInspection
    receipt: V07DurableWorkspaceReceipt


def preview_durable_v07_workspace(path: str | Path) -> V07DurableWorkspacePlan:
    """Build a mutation-free, path-free plan for a new durable workspace."""

    try:
        return _preview_durable_v07_workspace(path)
    except V07DurableWorkspaceError:
        raise
    except OSError as exc:
        raise V07DurableWorkspaceError(
            "WORKSPACE_IO_FAILED", "durable workspace preview could not inspect local state"
        ) from exc


def _preview_durable_v07_workspace(path: str | Path) -> V07DurableWorkspacePlan:
    """Implement preview after the public path-free error boundary."""

    target = Path(path)
    resolved = target.resolve(strict=False)
    _validate_target_identity(resolved)
    if os.path.lexists(target):
        raise V07DurableWorkspaceError("TARGET_EXISTS", "durable workspace target already exists")
    repository = Path(__file__).resolve().parents[3]
    if resolved.is_relative_to(repository):
        raise V07DurableWorkspaceError(
            "REPOSITORY_TARGET_FORBIDDEN", "durable workspace must be outside the repository"
        )
    parent = _validated_parent(target)
    available = shutil.disk_usage(parent).free
    orphan_handles = _orphan_staging_handles(parent)
    blockers: list[str] = []
    if available < DURABLE_WORKSPACE_MINIMUM_FREE_BYTES:
        blockers.append("INSUFFICIENT_FREE_SPACE")
    if orphan_handles:
        blockers.append("ORPHAN_STAGING_PRESENT")
    return V07DurableWorkspacePlan(
        workspace_handle=_workspace_handle(resolved),
        workspace_contract_fingerprint=v07_workspace_contract().fingerprint(),
        required_directories=V07_REQUIRED_DIRECTORIES,
        available_free_bytes=available,
        orphan_staging_handles=orphan_handles,
        activatable=not blockers,
        blockers=tuple(blockers),
        actions=(
            "Create the exact v0.7 workspace layout in private staging.",
            "Create and inspect the empty active registry.",
            "Copy the empty registry and verify an isolated restore.",
            "Write a path-free receipt and publish by atomic rename.",
        ),
    )


def create_durable_v07_workspace(
    path: str | Path,
    *,
    expected_plan_fingerprint: str,
    clock: Callable[[], datetime] | None = None,
    fault_hook: Callable[[str], None] | None = None,
) -> V07DurableWorkspaceResult:
    """Create, backup, restore-verify, and atomically publish one workspace."""

    try:
        return _create_durable_v07_workspace(
            path,
            expected_plan_fingerprint=expected_plan_fingerprint,
            clock=clock,
            fault_hook=fault_hook,
        )
    except V07DurableWorkspaceError:
        raise
    except V07CompatibilityError as exc:
        raise V07DurableWorkspaceError(
            "WORKSPACE_CONTRACT_FAILED", "v0.7 workspace contract validation failed"
        ) from exc
    except OSError as exc:
        raise V07DurableWorkspaceError(
            "WORKSPACE_IO_FAILED", "durable workspace publication could not complete"
        ) from exc


def _create_durable_v07_workspace(
    path: str | Path,
    *,
    expected_plan_fingerprint: str,
    clock: Callable[[], datetime] | None = None,
    fault_hook: Callable[[str], None] | None = None,
) -> V07DurableWorkspaceResult:
    """Implement creation after the public path-free error boundary."""

    target = Path(path)
    if os.path.lexists(target):
        return _load_exact_retry(target, expected_plan_fingerprint)
    plan = preview_durable_v07_workspace(target)
    if plan.confirmation_fingerprint() != expected_plan_fingerprint:
        raise V07DurableWorkspaceError(
            "PLAN_MISMATCH", "workspace plan changed or was not confirmed exactly"
        )
    if not plan.activatable:
        raise V07DurableWorkspaceError("PLAN_BLOCKED", "workspace plan has unresolved blockers")
    parent = _validated_parent(target)
    staging = parent / f"{_STAGING_PREFIX}{expected_plan_fingerprint[:16]}"
    if os.path.lexists(staging):
        raise V07DurableWorkspaceError(
            "ORPHAN_STAGING_PRESENT", "an earlier durable-workspace staging area is unresolved"
        )
    published = False
    try:
        initial = initialise_v07_workspace(staging, clock=clock)
        _apply_owner_only_permissions(staging)
        _call_fault(fault_hook, "workspace_created")
        backup = _create_and_verify_baseline_backup(staging)
        _call_fault(fault_hook, "baseline_backup_verified")
        inspection = inspect_v07_workspace(staging)
        _verify_empty_workspace(staging)
        created_at = _utc_now(clock)
        receipt = V07DurableWorkspaceReceipt(
            workspace_handle=plan.workspace_handle,
            plan_fingerprint=expected_plan_fingerprint,
            created_at_utc=created_at,
            manifest_sha256=inspection.manifest_sha256,
            active_registry_sha256=inspection.active_registry_sha256,
            baseline_backup=backup,
        )
        receipt_path = staging / DURABLE_WORKSPACE_RECEIPT_RELATIVE_PATH
        _write_new_bytes(receipt_path, (receipt.canonical_json() + "\n").encode("utf-8"))
        _apply_owner_only_permissions(staging)
        _verify_owner_only_layout(staging)
        _call_fault(fault_hook, "receipt_written")
        if os.path.lexists(target):
            raise V07DurableWorkspaceError(
                "TARGET_COLLISION", "durable workspace target appeared before publication"
            )
        _call_fault(fault_hook, "before_publish")
        _atomic_rename_new_only(staging, target)
        published = True
        _fsync_directory(parent)
        _call_fault(fault_hook, "after_publish")
    except Exception:
        if not published and os.path.lexists(staging):
            shutil.rmtree(staging)
        raise
    inspection = inspect_v07_workspace(target)
    _verify_owner_only_layout(target)
    _verify_persisted_backup(target, receipt.baseline_backup)
    if initial.inspection.manifest_sha256 != inspection.manifest_sha256:
        raise V07DurableWorkspaceError(
            "POST_PUBLICATION_MISMATCH", "workspace manifest changed during publication"
        )
    return V07DurableWorkspaceResult(
        workspace_path=target,
        receipt_path=target / DURABLE_WORKSPACE_RECEIPT_RELATIVE_PATH,
        inspection=inspection,
        receipt=receipt,
    )


def load_durable_workspace_receipt(path: str | Path) -> V07DurableWorkspaceReceipt:
    """Load and validate the bounded path-free receipt from one known workspace."""

    root = Path(path)
    receipt_path = root / DURABLE_WORKSPACE_RECEIPT_RELATIVE_PATH
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise V07DurableWorkspaceError(
            "RECEIPT_MISSING", "durable workspace receipt is missing or unsafe"
        )
    if receipt_path.stat().st_size > DURABLE_WORKSPACE_MAX_RECEIPT_BYTES:
        raise V07DurableWorkspaceError(
            "RECEIPT_OVERSIZED", "durable workspace receipt is too large"
        )
    try:
        return V07DurableWorkspaceReceipt.model_validate_json(receipt_path.read_bytes())
    except (OSError, ValueError) as exc:
        raise V07DurableWorkspaceError(
            "RECEIPT_INVALID", "durable workspace receipt failed validation"
        ) from exc


def _load_exact_retry(target: Path, expected_plan_fingerprint: str) -> V07DurableWorkspaceResult:
    try:
        inspection = inspect_v07_workspace(target)
        receipt = load_durable_workspace_receipt(target)
        _verify_owner_only_layout(target)
        _verify_persisted_backup(target, receipt.baseline_backup)
    except Exception as exc:
        if isinstance(exc, V07DurableWorkspaceError):
            raise
        raise V07DurableWorkspaceError(
            "EXISTING_TARGET_UNMANAGED", "existing target is not an exact durable workspace"
        ) from exc
    if receipt.plan_fingerprint != expected_plan_fingerprint:
        raise V07DurableWorkspaceError(
            "EXISTING_TARGET_CONFLICT", "existing durable workspace binds a different plan"
        )
    if receipt.workspace_handle != _workspace_handle(target.resolve(strict=True)):
        raise V07DurableWorkspaceError(
            "WORKSPACE_HANDLE_MISMATCH", "existing durable workspace moved or changed identity"
        )
    if inspection.manifest_sha256 != receipt.manifest_sha256:
        raise V07DurableWorkspaceError(
            "MANIFEST_MISMATCH", "existing durable workspace manifest changed"
        )
    if inspection.active_registry_sha256 != receipt.active_registry_sha256:
        raise V07DurableWorkspaceError(
            "REGISTRY_MISMATCH", "existing durable workspace registry changed"
        )
    retried = receipt.model_copy(update={"exact_retry": True})
    return V07DurableWorkspaceResult(
        workspace_path=target,
        receipt_path=target / DURABLE_WORKSPACE_RECEIPT_RELATIVE_PATH,
        inspection=inspection,
        receipt=retried,
    )


def _create_and_verify_baseline_backup(root: Path) -> V07BaselineBackupReceipt:
    registry = root / V07_ACTIVE_REGISTRY
    backup = root / DURABLE_WORKSPACE_BACKUP_RELATIVE_PATH
    backup.parent.mkdir(parents=True, exist_ok=False)
    os.chmod(backup.parent, 0o700)
    shutil.copyfile(registry, backup)
    os.chmod(backup, 0o600)
    _fsync_file(backup)
    _fsync_directory(backup.parent)
    with tempfile.TemporaryDirectory(prefix="restore-drill-", dir=root / "quarantine") as temp:
        restored = Path(temp) / "traffictwin.sqlite"
        shutil.copyfile(backup, restored)
        os.chmod(restored, 0o600)
        _fsync_file(restored)
        status = inspect_registry_migrations(restored)
        if status.current_version != CURRENT_REGISTRY_SCHEMA_VERSION:
            raise V07DurableWorkspaceError(
                "RESTORE_SCHEMA_MISMATCH", "restored baseline registry schema is unsupported"
            )
        receipt = V07BaselineBackupReceipt(
            registry_schema_version=status.current_version,
            registry_size_bytes=registry.stat().st_size,
            registry_sha256=_sha256_file(registry),
            backup_size_bytes=backup.stat().st_size,
            backup_sha256=_sha256_file(backup),
            restored_size_bytes=restored.stat().st_size,
            restored_sha256=_sha256_file(restored),
        )
    return receipt


def _verify_persisted_backup(root: Path, expected: V07BaselineBackupReceipt) -> None:
    registry = root / V07_ACTIVE_REGISTRY
    backup = root / DURABLE_WORKSPACE_BACKUP_RELATIVE_PATH
    if backup.is_symlink() or not backup.is_file():
        raise V07DurableWorkspaceError("BACKUP_MISSING", "baseline backup is missing or unsafe")
    try:
        observed = V07BaselineBackupReceipt(
            registry_schema_version=inspect_registry_migrations(backup).current_version,
            registry_size_bytes=registry.stat().st_size,
            registry_sha256=_sha256_file(registry),
            backup_size_bytes=backup.stat().st_size,
            backup_sha256=_sha256_file(backup),
            restored_size_bytes=backup.stat().st_size,
            restored_sha256=_sha256_file(backup),
        )
    except Exception as exc:
        raise V07DurableWorkspaceError(
            "BACKUP_INVALID", "persisted baseline backup failed validation"
        ) from exc
    if observed != expected:
        raise V07DurableWorkspaceError(
            "BACKUP_MISMATCH", "persisted baseline backup no longer reconciles"
        )


def _verify_empty_workspace(root: Path) -> None:
    for relative in (
        "manchester/raw",
        "manchester/accepted",
        "manchester/projections",
        "manchester/mappings",
        "manchester/calibrations",
        "manchester/comparisons",
        "runs",
        "exports",
    ):
        if any((root / relative).iterdir()):
            raise V07DurableWorkspaceError(
                "WORKSPACE_NOT_EMPTY", "new durable workspace contains unexpected source data"
            )


def _validated_parent(target: Path) -> Path:
    parent = target.parent
    if parent.is_symlink() or not parent.is_dir():
        raise V07DurableWorkspaceError(
            "PARENT_INVALID", "target parent must be an existing non-symlinked directory"
        )
    resolved = parent.resolve(strict=True)
    details = resolved.stat()
    if details.st_uid != os.getuid():
        raise V07DurableWorkspaceError(
            "PARENT_NOT_OWNED", "target parent must be owned by the current user"
        )
    mode = stat.S_IMODE(details.st_mode)
    if mode & 0o077 or mode & 0o700 != 0o700:
        raise V07DurableWorkspaceError(
            "PARENT_PERMISSIONS_UNSAFE", "target parent must have owner-only read/write/search"
        )
    return resolved


def _validate_target_identity(target: Path) -> None:
    blocked = {Path("/").resolve(), Path.home().resolve(), Path.cwd().resolve()}
    if target in blocked or target.parent == target:
        raise V07DurableWorkspaceError("TARGET_UNSAFE", "durable workspace target is too broad")


def _apply_owner_only_permissions(root: Path) -> None:
    for directory, child_directories, files in os.walk(root):
        current = Path(directory)
        os.chmod(current, 0o700)
        for name in child_directories:
            os.chmod(current / name, 0o700)
        for name in files:
            os.chmod(current / name, 0o600)


def _verify_owner_only_layout(root: Path) -> None:
    for directory, child_directories, files in os.walk(root):
        current = Path(directory)
        _verify_owned_mode(current, expected=0o700)
        for name in child_directories:
            _verify_owned_mode(current / name, expected=0o700)
        for name in files:
            _verify_owned_mode(current / name, expected=0o600)


def _verify_owned_mode(path: Path, *, expected: int) -> None:
    if path.is_symlink():
        raise V07DurableWorkspaceError("SYMLINK_FORBIDDEN", "workspace layout contains a symlink")
    details = path.stat()
    if details.st_uid != os.getuid() or stat.S_IMODE(details.st_mode) != expected:
        raise V07DurableWorkspaceError("PERMISSIONS_MISMATCH", "workspace layout is not owner-only")


def _orphan_staging_handles(parent: Path) -> tuple[str, ...]:
    handles = []
    for candidate in parent.iterdir():
        if candidate.name.startswith(_STAGING_PREFIX):
            handles.append(f"staging-{_sha256_bytes(candidate.name.encode())[:12]}")
    return tuple(sorted(handles))


def _workspace_handle(path: Path) -> str:
    return f"workspace-{_sha256_bytes(str(path).encode())[:16]}"


def _write_new_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(path, 0o600)
    _fsync_directory(path.parent)


def _fsync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_rename_new_only(source: Path, target: Path) -> None:
    """Atomically publish one directory while refusing an appearing target."""

    if sys.platform == "darwin":
        libc = CDLL(None, use_errno=True)
        renamex_np = libc.renamex_np
        renamex_np.argtypes = (c_char_p, c_char_p, c_uint)
        renamex_np.restype = c_int
        result = renamex_np(os.fsencode(source), os.fsencode(target), 0x00000004)
    elif sys.platform.startswith("linux"):
        libc = CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is None:
            raise V07DurableWorkspaceError(
                "ATOMIC_PUBLICATION_UNAVAILABLE",
                "new-only atomic directory publication is unavailable",
            )
        renameat2.argtypes = (c_int, c_char_p, c_int, c_char_p, c_uint)
        renameat2.restype = c_int
        result = renameat2(-100, os.fsencode(source), -100, os.fsencode(target), 1)
    else:
        if os.path.lexists(target):
            raise V07DurableWorkspaceError(
                "TARGET_COLLISION", "durable workspace target appeared before publication"
            )
        os.rename(source, target)
        return
    if result == 0:
        return
    error_number = get_errno()
    if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
        raise V07DurableWorkspaceError(
            "TARGET_COLLISION", "durable workspace target appeared before publication"
        )
    raise V07DurableWorkspaceError(
        "ATOMIC_PUBLICATION_FAILED", "new-only atomic workspace publication failed"
    )


def _utc_now(clock: Callable[[], datetime] | None) -> datetime:
    value = (clock or (lambda: datetime.now(UTC)))()
    if value.tzinfo is None or value.utcoffset() is None:
        raise V07DurableWorkspaceError("CLOCK_INVALID", "clock must be timezone-aware")
    return value.astimezone(UTC)


def _call_fault(hook: Callable[[str], None] | None, stage: str) -> None:
    if hook is not None:
        hook(stage)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

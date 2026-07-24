"""REL-01 attested v0.6 registry activation with backup and rollback.

This slice activates an ADR-058-attested v0.6 registry as the active v0.7
registry. The backup registry and its reconciling receipt are published
together in one atomic directory rename before the active registry is
swapped, so the receipt is durable the instant the backup exists. The
migration identity is derived only from the source registry, so a retry after
any interruption resolves to the same backup directory and resumes
deterministically: an already-activated registry is acknowledged idempotently,
and a published-but-not-activated backup completes its swap. The previous
active registry is therefore never orphaned. Rollback restores the backup
(idempotently) while the active registry matches either the activated or the
pre-migration state, and records a reconciling rollback receipt. The frozen
v0.6 registry schema equals the current v0.7 schema, so no schema
transformation occurs; a source at any other version, or one living inside the
target workspace, is refused rather than transformed.

A completed activation is operational plumbing only: it accepts no scientific
payload, proves no capability, and `REL-01` remains ``planned``.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.release.attestation import (
    V06ProducerAttestation,
    verify_v06_producer_attestation,
)
from traffictwin.release.compatibility import (
    V06_REGISTRY_SCHEMA_VERSION,
    V07_ACTIVE_REGISTRY,
    inspect_v07_workspace,
)
from traffictwin.storage.migrations import (
    CURRENT_REGISTRY_SCHEMA_VERSION,
    inspect_registry_migrations,
)

V06_MIGRATION_SCHEMA_VERSION = "traffictwin.v06-migration.v1"
MIGRATION_BACKUP_ROOT = "compatibility/backups"
MIGRATION_RECEIPT_NAME = "migration-receipt.json"
ROLLBACK_RECEIPT_NAME = "rollback-receipt.json"
BACKUP_REGISTRY_NAME = "previous-active-registry.sqlite"
MIGRATION_FREE_SPACE_RESERVE_BYTES = 1024 * 1024
MAX_RECEIPT_BYTES = 64 * 1024

# Backup paths are always the exact internally-computed layout below. Pinning
# them by pattern means a tampered or hand-crafted receipt carrying a traversal
# or absolute path fails to load rather than steering a byte copy off the
# fixed backup location.
_BACKUP_DIRECTORY_PATTERN = r"^compatibility/backups/mig-[0-9a-f]{16}$"
_BACKUP_REGISTRY_PATTERN = (
    r"^compatibility/backups/mig-[0-9a-f]{16}/previous-active-registry\.sqlite$"
)
_MIGRATION_RECEIPT_PATTERN = r"^compatibility/backups/mig-[0-9a-f]{16}/migration-receipt\.json$"


class V06MigrationError(ValueError):
    """Typed refusal for unsafe or unverifiable migration requests."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class _MigrationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)

    def canonical_json(self) -> str:
        """Return byte-stable JSON for this artifact."""

        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    def fingerprint(self) -> str:
        """Return the SHA-256 identity of this exact artifact."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class V06MigrationPreview(_MigrationModel):
    """Read-only plan for one attested same-schema activation."""

    schema_version: Literal["traffictwin.v06-migration.v1"] = "traffictwin.v06-migration.v1"
    capability_id: Literal["REL-01"] = "REL-01"
    capability_status: Literal["planned"] = "planned"
    operation: Literal["attested_same_schema_activation"] = "attested_same_schema_activation"
    attestation_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_product_version: Literal["0.6.0"] = "0.6.0"
    source_registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_registry_size_bytes: int = Field(ge=1)
    source_schema_version: int = Field(ge=1)
    target_schema_version: int = Field(ge=1)
    schema_transformation_required: Literal[False] = False
    active_registry_sha256_before: str = Field(pattern=r"^[0-9a-f]{64}$")
    migration_id: str = Field(pattern=r"^mig-[0-9a-f]{16}$")
    backup_relative_directory: str = Field(pattern=_BACKUP_DIRECTORY_PATTERN)
    backup_registry_relative_path: str = Field(pattern=_BACKUP_REGISTRY_PATTERN)
    receipt_relative_path: str = Field(pattern=_MIGRATION_RECEIPT_PATTERN)
    required_free_bytes: int = Field(ge=1)
    available_free_bytes: int = Field(ge=0)
    source_mutation_allowed: Literal[False] = False
    automatic_execution: Literal[False] = False
    rollback_supported: Literal[True] = True
    actions: tuple[str, ...]
    blockers: tuple[str, ...]

    @property
    def has_required_space(self) -> bool:
        """Return whether the workspace currently has enough free bytes."""

        return self.available_free_bytes >= self.required_free_bytes


class V06MigrationReceipt(_MigrationModel):
    """Receipt proving one backed-up, byte-exact, attested activation."""

    schema_version: Literal["traffictwin.v06-migration.v1"] = "traffictwin.v06-migration.v1"
    capability_id: Literal["REL-01"] = "REL-01"
    capability_status: Literal["planned"] = "planned"
    migration_id: str = Field(pattern=r"^mig-[0-9a-f]{16}$")
    migrated_at: datetime
    attestation_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_product_version: Literal["0.6.0"] = "0.6.0"
    source_registry_sha256_before: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_registry_sha256_after: str = Field(pattern=r"^[0-9a-f]{64}$")
    backup_registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    active_registry_sha256_before: str = Field(pattern=r"^[0-9a-f]{64}$")
    active_registry_sha256_after: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_schema_version: int = Field(ge=1)
    target_schema_version: int = Field(ge=1)
    backup_registry_relative_path: str = Field(pattern=_BACKUP_REGISTRY_PATTERN)
    source_unchanged_during_migration: Literal[True] = True
    rollback_available: Literal[True] = True
    scientific_admission: Literal["unavailable"] = "unavailable"

    @model_validator(mode="after")
    def validate_reconciliation(self) -> V06MigrationReceipt:
        """Reject any receipt whose hashes do not reconcile."""

        if self.migrated_at.tzinfo is None or self.migrated_at.utcoffset() is None:
            raise ValueError("migrated_at must include a timezone")
        if self.source_registry_sha256_before != self.source_registry_sha256_after:
            raise ValueError("the source registry must remain unchanged")
        if self.active_registry_sha256_after != self.source_registry_sha256_before:
            raise ValueError("the activated registry must be byte-exact with the source")
        if self.backup_registry_sha256 != self.active_registry_sha256_before:
            raise ValueError("the backup must be byte-exact with the previous active registry")
        expected_path = f"{MIGRATION_BACKUP_ROOT}/{self.migration_id}/{BACKUP_REGISTRY_NAME}"
        if self.backup_registry_relative_path != expected_path:
            raise ValueError("backup path must embed the receipt migration_id exactly")
        return self


class V06RollbackReceipt(_MigrationModel):
    """Receipt proving one byte-exact restoration of the previous registry."""

    schema_version: Literal["traffictwin.v06-migration.v1"] = "traffictwin.v06-migration.v1"
    capability_id: Literal["REL-01"] = "REL-01"
    capability_status: Literal["planned"] = "planned"
    migration_id: str = Field(pattern=r"^mig-[0-9a-f]{16}$")
    rolled_back_at: datetime
    migration_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    active_registry_sha256_before_rollback: str = Field(pattern=r"^[0-9a-f]{64}$")
    restored_registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    backup_preserved: Literal[True] = True
    rollback_complete: Literal[True] = True

    @model_validator(mode="after")
    def validate_time(self) -> V06RollbackReceipt:
        """Refuse naive timestamps."""

        if self.rolled_back_at.tzinfo is None or self.rolled_back_at.utcoffset() is None:
            raise ValueError("rolled_back_at must include a timezone")
        return self


@dataclass(frozen=True)
class V06MigrationResult:
    """Operational paths plus receipt for one completed activation."""

    backup_directory: Path
    backup_registry_path: Path
    receipt_path: Path
    receipt: V06MigrationReceipt


@dataclass(frozen=True)
class V06RollbackResult:
    """Operational paths plus receipt for one completed rollback."""

    receipt_path: Path
    receipt: V06RollbackReceipt


def preview_v06_migration(
    source_registry: str | Path,
    target_workspace: str | Path,
    attestation: V06ProducerAttestation,
) -> V06MigrationPreview:
    """Build the read-only activation plan; nothing is written."""

    root = Path(target_workspace)
    inspection = inspect_v07_workspace(root)
    source = _safe_closed_registry(Path(source_registry), root)
    verification = verify_v06_producer_attestation(attestation, source)
    if not verification.verified:
        raise V06MigrationError(
            "ATTESTATION_NOT_VERIFIED",
            f"attestation does not bind the current source bytes: {verification.failure}",
        )
    source_status = inspect_registry_migrations(source)
    if source_status.current_version != V06_REGISTRY_SCHEMA_VERSION:
        raise V06MigrationError(
            "SOURCE_SCHEMA_UNSUPPORTED",
            "only the frozen v0.6 registry schema is accepted: "
            f"expected={V06_REGISTRY_SCHEMA_VERSION}, observed={source_status.current_version}",
        )
    if V06_REGISTRY_SCHEMA_VERSION != CURRENT_REGISTRY_SCHEMA_VERSION:
        raise V06MigrationError(
            "CROSS_SCHEMA_UNSUPPORTED",
            "cross-schema migration is not implemented; a schema change requires a new "
            "reviewed decision",
        )
    source_bytes = source.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    active_sha256 = inspection.active_registry_sha256
    # The migration identity depends only on the source registry, so a retry
    # after any interruption resolves to the same backup directory and resumes
    # deterministically regardless of the active registry's current bytes.
    migration_id = _migration_id_for(source_sha256)
    backup_directory = f"{MIGRATION_BACKUP_ROOT}/{migration_id}"
    active = root / V07_ACTIVE_REGISTRY
    required = len(source_bytes) + active.stat().st_size + MIGRATION_FREE_SPACE_RESERVE_BYTES
    return V06MigrationPreview(
        attestation_fingerprint=attestation.fingerprint(),
        source_registry_sha256=source_sha256,
        source_registry_size_bytes=len(source_bytes),
        source_schema_version=source_status.current_version,
        target_schema_version=CURRENT_REGISTRY_SCHEMA_VERSION,
        active_registry_sha256_before=active_sha256,
        migration_id=migration_id,
        backup_relative_directory=backup_directory,
        backup_registry_relative_path=f"{backup_directory}/{BACKUP_REGISTRY_NAME}",
        receipt_relative_path=f"{backup_directory}/{MIGRATION_RECEIPT_NAME}",
        required_free_bytes=required,
        available_free_bytes=shutil.disk_usage(root).free,
        actions=(
            f"Publish the backup registry and its reconciling receipt together under "
            f"{backup_directory} before the active registry changes.",
            "Atomically replace the active v0.7 registry with the attested source bytes.",
            "Resume idempotently on retry; keep the source registry and backup unchanged for "
            "rollback.",
        ),
        blockers=(
            "The backup and receipt are published together before activation; a retry after any "
            "interruption resumes to the committed state rather than orphaning the previous "
            "registry.",
            "Activation transfers operational state only; scientific admission stays unavailable.",
        ),
    )


def migrate_v06_registry(
    source_registry: str | Path,
    target_workspace: str | Path,
    attestation: V06ProducerAttestation,
    *,
    clock: Callable[[], datetime] | None = None,
) -> V06MigrationResult:
    """Back up the active registry, then activate the attested source bytes.

    The backup registry and its reconciling receipt are published together in
    one atomic directory rename before the active registry is swapped, so the
    receipt is durable the instant the backup exists. A retry after any
    interruption resumes deterministically: if the swap already happened it
    returns the committed result, and if only the backup was published it
    completes the swap. The previous registry is therefore never orphaned.
    """

    root = Path(target_workspace).resolve(strict=True)
    preview = preview_v06_migration(source_registry, root, attestation)
    source = _safe_closed_registry(Path(source_registry), root)
    active = root / V07_ACTIVE_REGISTRY
    backup_directory = root / preview.backup_relative_directory
    if backup_directory.is_symlink():
        raise V06MigrationError(
            "BACKUP_DIRECTORY_UNSAFE",
            f"backup directory path is a symlink: {backup_directory}",
        )
    if backup_directory.exists():
        return _resume_migration(root, source, preview, active, backup_directory)
    if not preview.has_required_space:
        raise V06MigrationError(
            "INSUFFICIENT_FREE_SPACE",
            "the workspace lacks the free bytes required for backup plus activation",
        )
    active_bytes = active.read_bytes()
    if hashlib.sha256(active_bytes).hexdigest() != preview.active_registry_sha256_before:
        raise V06MigrationError(
            "ACTIVE_REGISTRY_CHANGED", "the active registry changed since the preview"
        )
    source_bytes = source.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != preview.source_registry_sha256:
        raise V06MigrationError(
            "SOURCE_REGISTRY_CHANGED", "the source registry changed since the preview"
        )
    receipt = V06MigrationReceipt(
        migration_id=preview.migration_id,
        migrated_at=_utc_now(clock),
        attestation_fingerprint=preview.attestation_fingerprint,
        source_registry_sha256_before=preview.source_registry_sha256,
        source_registry_sha256_after=preview.source_registry_sha256,
        backup_registry_sha256=preview.active_registry_sha256_before,
        active_registry_sha256_before=preview.active_registry_sha256_before,
        active_registry_sha256_after=preview.source_registry_sha256,
        source_schema_version=preview.source_schema_version,
        target_schema_version=preview.target_schema_version,
        backup_registry_relative_path=preview.backup_registry_relative_path,
    )
    staging = Path(tempfile.mkdtemp(prefix=".traffictwin-v06-migration-", dir=root))
    try:
        # Build a fully-populated publish directory (backup registry + receipt)
        # and stage the new active bytes, then commit both with atomic renames.
        backup_publish = staging / "publish"
        backup_publish.mkdir()
        (backup_publish / BACKUP_REGISTRY_NAME).write_bytes(active_bytes)
        _fsync_file(backup_publish / BACKUP_REGISTRY_NAME)
        _write_new_bytes(
            backup_publish / MIGRATION_RECEIPT_NAME,
            (receipt.canonical_json() + "\n").encode("utf-8"),
        )
        staged_active = staging / "activated-registry.sqlite"
        staged_active.write_bytes(source_bytes)
        _fsync_file(staged_active)
        _safe_backup_parent(root, backup_directory)
        os.rename(backup_publish, backup_directory)
        _fsync_directory(backup_directory.parent)
        # Commit point: the receipt is durable. The swap below is idempotent and
        # resumable via _resume_migration if interrupted here.
        os.replace(staged_active, active)
        _fsync_directory(active.parent)
        return V06MigrationResult(
            backup_directory=backup_directory,
            backup_registry_path=backup_directory / BACKUP_REGISTRY_NAME,
            receipt_path=backup_directory / MIGRATION_RECEIPT_NAME,
            receipt=receipt,
        )
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _resume_migration(
    root: Path,
    source: Path,
    preview: V06MigrationPreview,
    active: Path,
    backup_directory: Path,
) -> V06MigrationResult:
    """Resume or acknowledge a migration whose backup directory already exists."""

    receipt_path = backup_directory / MIGRATION_RECEIPT_NAME
    backup_registry = backup_directory / BACKUP_REGISTRY_NAME
    if not receipt_path.is_file():
        raise V06MigrationError(
            "MIGRATION_QUARANTINED",
            "a backup directory exists without a receipt; manual recovery is required "
            f"before retrying: {backup_directory}",
        )
    receipt = load_v06_migration_receipt(receipt_path)
    if receipt.active_registry_sha256_after != preview.source_registry_sha256:
        raise V06MigrationError(
            "MIGRATION_SOURCE_MISMATCH",
            "an existing migration receipt does not match the current source registry",
        )
    if (
        backup_registry.is_symlink()
        or not backup_registry.is_file()
        or hashlib.sha256(backup_registry.read_bytes()).hexdigest()
        != receipt.backup_registry_sha256
    ):
        raise V06MigrationError(
            "BACKUP_BYTES_CHANGED", "the existing backup no longer matches its receipt"
        )
    if active.is_symlink() or not active.is_file():
        raise V06MigrationError(
            "ACTIVE_REGISTRY_MISSING_OR_UNSAFE",
            f"active registry must be a regular non-symlinked file: {active}",
        )
    active_sha256 = hashlib.sha256(active.read_bytes()).hexdigest()
    result = V06MigrationResult(
        backup_directory=backup_directory,
        backup_registry_path=backup_registry,
        receipt_path=receipt_path,
        receipt=receipt,
    )
    if active_sha256 == receipt.active_registry_sha256_after:
        return result  # already activated; idempotent acknowledgement
    if active_sha256 == receipt.active_registry_sha256_before:
        source_bytes = source.read_bytes()
        if hashlib.sha256(source_bytes).hexdigest() != receipt.active_registry_sha256_after:
            raise V06MigrationError(
                "SOURCE_REGISTRY_CHANGED",
                "the source registry changed since the interrupted migration",
            )
        staging = Path(tempfile.mkdtemp(prefix=".traffictwin-v06-resume-", dir=root))
        try:
            staged_active = staging / "activated-registry.sqlite"
            staged_active.write_bytes(source_bytes)
            _fsync_file(staged_active)
            os.replace(staged_active, active)
            _fsync_directory(active.parent)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return result
    raise V06MigrationError(
        "ACTIVE_REGISTRY_DIVERGED",
        "the active registry matches neither the pre- nor post-activation state of an "
        "existing migration; manual review is required",
    )


def load_v06_migration_receipt(path: str | Path) -> V06MigrationReceipt:
    """Load one bounded migration receipt, failing closed on drift."""

    artifact = Path(path)
    if artifact.is_symlink() or not artifact.is_file():
        raise V06MigrationError(
            "RECEIPT_MISSING_OR_UNSAFE",
            f"migration receipt must be a regular non-symlinked file: {artifact}",
        )
    if artifact.stat().st_size > MAX_RECEIPT_BYTES:
        raise V06MigrationError("RECEIPT_OVERSIZED", "receipt exceeds the bounded size")
    try:
        return V06MigrationReceipt.model_validate_json(artifact.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise V06MigrationError("RECEIPT_INVALID", str(exc)) from exc


def rollback_v06_migration(
    target_workspace: str | Path,
    receipt_path: str | Path,
    *,
    clock: Callable[[], datetime] | None = None,
) -> V06RollbackResult:
    """Restore the backed-up registry while the receipt still matches reality."""

    root = Path(target_workspace).resolve(strict=True)
    receipt = load_v06_migration_receipt(receipt_path)
    backup = _safe_workspace_path(root, receipt.backup_registry_relative_path)
    if backup.is_symlink() or not backup.is_file():
        raise V06MigrationError(
            "BACKUP_MISSING_OR_UNSAFE",
            f"backup registry must be a regular non-symlinked file: {backup}",
        )
    backup_bytes = backup.read_bytes()
    if hashlib.sha256(backup_bytes).hexdigest() != receipt.backup_registry_sha256:
        raise V06MigrationError(
            "BACKUP_BYTES_CHANGED", "the backup no longer matches the migration receipt"
        )
    active = root / V07_ACTIVE_REGISTRY
    if active.is_symlink() or not active.is_file():
        raise V06MigrationError(
            "ACTIVE_REGISTRY_MISSING_OR_UNSAFE",
            f"active registry must be a regular non-symlinked file: {active}",
        )
    active_sha256 = hashlib.sha256(active.read_bytes()).hexdigest()
    already_restored = active_sha256 == receipt.backup_registry_sha256
    if not already_restored and active_sha256 != receipt.active_registry_sha256_after:
        raise V06MigrationError(
            "ACTIVE_REGISTRY_DIVERGED",
            "the active registry matches neither the activated nor the pre-migration state; "
            "rollback would destroy unrecognised state and requires manual review",
        )
    rollback_path = backup.parent / ROLLBACK_RECEIPT_NAME
    if rollback_path.is_symlink():
        raise V06MigrationError(
            "ROLLBACK_RECEIPT_UNSAFE", f"rollback receipt path is a symlink: {rollback_path}"
        )
    # Restore first (idempotent: skip if already restored), then record the
    # rollback. A crash after the restore but before the receipt is completed on
    # retry because the active registry already equals the backup.
    staging = Path(tempfile.mkdtemp(prefix=".traffictwin-v06-rollback-", dir=root))
    try:
        if not already_restored:
            staged = staging / "restored-registry.sqlite"
            staged.write_bytes(backup_bytes)
            _fsync_file(staged)
            os.replace(staged, active)
            _fsync_directory(active.parent)
        restored_sha256 = hashlib.sha256(active.read_bytes()).hexdigest()
        if restored_sha256 != receipt.backup_registry_sha256:
            raise V06MigrationError(
                "ROLLBACK_VERIFICATION_FAILED",
                "the restored registry does not match the recorded backup hash",
            )
        if rollback_path.exists():
            existing = load_v06_rollback_receipt(rollback_path)
            if existing.migration_receipt_fingerprint != receipt.fingerprint():
                raise V06MigrationError(
                    "ROLLBACK_RECEIPT_MISMATCH",
                    "an unrelated rollback receipt already occupies this migration",
                )
            return V06RollbackResult(receipt_path=rollback_path, receipt=existing)
        rollback = V06RollbackReceipt(
            migration_id=receipt.migration_id,
            rolled_back_at=_utc_now(clock),
            migration_receipt_fingerprint=receipt.fingerprint(),
            active_registry_sha256_before_rollback=active_sha256,
            restored_registry_sha256=restored_sha256,
        )
        _write_new_bytes(rollback_path, (rollback.canonical_json() + "\n").encode("utf-8"))
        _fsync_directory(rollback_path.parent)
        return V06RollbackResult(receipt_path=rollback_path, receipt=rollback)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def load_v06_rollback_receipt(path: str | Path) -> V06RollbackReceipt:
    """Load one bounded rollback receipt, failing closed on drift."""

    artifact = Path(path)
    if artifact.is_symlink() or not artifact.is_file():
        raise V06MigrationError(
            "ROLLBACK_RECEIPT_MISSING_OR_UNSAFE",
            f"rollback receipt must be a regular non-symlinked file: {artifact}",
        )
    if artifact.stat().st_size > MAX_RECEIPT_BYTES:
        raise V06MigrationError("ROLLBACK_RECEIPT_OVERSIZED", "receipt exceeds the bounded size")
    try:
        return V06RollbackReceipt.model_validate_json(artifact.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise V06MigrationError("ROLLBACK_RECEIPT_INVALID", str(exc)) from exc


def _safe_closed_registry(source: Path, workspace_root: Path) -> Path:
    if source.is_symlink() or not source.is_file():
        raise V06MigrationError(
            "SOURCE_MISSING_OR_UNSAFE",
            f"source registry must be a regular non-symlinked file: {source}",
        )
    for suffix in ("-wal", "-shm", "-journal"):
        if source.with_name(source.name + suffix).exists():
            raise V06MigrationError(
                "SOURCE_NOT_CHECKPOINTED",
                "migration requires a closed, checkpointed source without sidecars",
            )
    resolved = source.resolve(strict=True)
    resolved_root = workspace_root.resolve(strict=True)
    if resolved == (resolved_root / V07_ACTIVE_REGISTRY):
        raise V06MigrationError(
            "SOURCE_IS_ACTIVE_REGISTRY", "the active v0.7 registry cannot be its own source"
        )
    if resolved.is_relative_to(resolved_root):
        raise V06MigrationError(
            "SOURCE_INSIDE_WORKSPACE",
            "the migration source must live outside the target v0.7 workspace so a "
            "compatibility copy or backup can never become the active registry",
        )
    return resolved


def _migration_id_for(source_sha256: str) -> str:
    """Return the deterministic source-derived migration identity."""

    return "mig-" + hashlib.sha256(source_sha256.encode("utf-8")).hexdigest()[:16]


def _safe_backup_parent(root: Path, backup_directory: Path) -> None:
    """Create the backup parent, refusing any symlinked ancestor inside root."""

    resolved_root = root.resolve(strict=True)
    parent = backup_directory.parent
    ancestors: list[Path] = []
    current = parent
    while current != root and current != current.parent:
        ancestors.append(current)
        current = current.parent
    for ancestor in reversed(ancestors):
        if ancestor.is_symlink():
            raise V06MigrationError(
                "BACKUP_PARENT_UNSAFE",
                f"backup ancestor path is a symlink: {ancestor}",
            )
        ancestor.mkdir(exist_ok=True)
    if not parent.resolve(strict=True).is_relative_to(resolved_root):
        raise V06MigrationError(
            "BACKUP_PARENT_UNSAFE", f"backup parent escapes the workspace: {parent}"
        )


def _safe_workspace_path(root: Path, relative: str) -> Path:
    """Resolve a workspace-relative path, refusing traversal and escapes.

    The receipt fields are already pattern-pinned, so this is defence in depth
    against any future field whose validator is relaxed or bypassed.
    """

    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise V06MigrationError(
            "UNSAFE_RECEIPT_PATH", f"unsafe workspace-relative path: {relative}"
        )
    resolved_root = root.resolve(strict=True)
    resolved = (root / candidate).resolve(strict=False)
    if not resolved.is_relative_to(resolved_root):
        raise V06MigrationError(
            "RECEIPT_PATH_ESCAPES_WORKSPACE", f"receipt path escapes the workspace: {relative}"
        )
    return root / candidate


def _write_new_bytes(path: Path, payload: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _fsync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _utc_now(clock: Callable[[], datetime] | None) -> datetime:
    instant = datetime.now(UTC) if clock is None else clock()
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise V06MigrationError("NAIVE_CLOCK", "the migration clock must be timezone-aware")
    return instant

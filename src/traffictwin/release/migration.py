"""REL-01 attested v0.6 registry activation with backup and rollback.

This slice activates an ADR-058-attested v0.6 registry as the active v0.7
registry only after publishing a durable byte-exact backup of the current
active registry. The frozen v0.6 registry schema equals the current v0.7
schema, so no schema transformation occurs; a source at any other version is
refused rather than transformed. Interruption before the receipt exists
leaves a quarantined backup directory without a receipt and never corrupts
the source or the previous active registry. Rollback restores the backed-up
registry only while the active registry still matches the migration receipt.

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
    backup_relative_directory: str
    backup_registry_relative_path: str
    receipt_relative_path: str
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
    backup_registry_relative_path: str
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
    migration_id = (
        "mig-" + hashlib.sha256(f"{source_sha256}:{active_sha256}".encode()).hexdigest()[:16]
    )
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
            f"Publish a durable byte-exact backup of the active registry under {backup_directory}.",
            "Atomically replace the active v0.7 registry with the attested source bytes.",
            "Write the reconciling migration receipt beside the backup.",
            "Keep the source registry and backup unchanged for rollback.",
        ),
        blockers=(
            "A backup directory without a receipt is a quarantined interrupted migration and "
            "must be inspected before retrying.",
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
    """Back up the active registry, then activate the attested source bytes."""

    root = Path(target_workspace).resolve(strict=True)
    preview = preview_v06_migration(source_registry, root, attestation)
    if not preview.has_required_space:
        raise V06MigrationError(
            "INSUFFICIENT_FREE_SPACE",
            "the workspace lacks the free bytes required for backup plus activation",
        )
    source = Path(source_registry).resolve(strict=True)
    active = root / V07_ACTIVE_REGISTRY
    backup_directory = root / preview.backup_relative_directory
    if backup_directory.exists() or backup_directory.is_symlink():
        receipt_state = (
            "completed" if (backup_directory / MIGRATION_RECEIPT_NAME).is_file() else "quarantined"
        )
        raise V06MigrationError(
            "MIGRATION_ALREADY_PRESENT",
            f"backup directory already exists ({receipt_state}): {backup_directory}",
        )
    staging = Path(tempfile.mkdtemp(prefix=".traffictwin-v06-migration-", dir=root))
    try:
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
        staged_backup = staging / BACKUP_REGISTRY_NAME
        staged_backup.write_bytes(active_bytes)
        _fsync_file(staged_backup)
        staged_active = staging / "activated-registry.sqlite"
        staged_active.write_bytes(source_bytes)
        _fsync_file(staged_active)
        backup_directory.parent.mkdir(parents=True, exist_ok=True)
        backup_publish = staging / "publish"
        backup_publish.mkdir()
        os.rename(staged_backup, backup_publish / BACKUP_REGISTRY_NAME)
        os.rename(backup_publish, backup_directory)
        _fsync_directory(backup_directory.parent)
        # The durable backup exists before the active registry changes; an
        # interruption from here leaves a receipt-less quarantined backup.
        os.replace(staged_active, active)
        _fsync_directory(active.parent)
        activated_sha256 = hashlib.sha256(active.read_bytes()).hexdigest()
        receipt = V06MigrationReceipt(
            migration_id=preview.migration_id,
            migrated_at=_utc_now(clock),
            attestation_fingerprint=preview.attestation_fingerprint,
            source_registry_sha256_before=preview.source_registry_sha256,
            source_registry_sha256_after=hashlib.sha256(source.read_bytes()).hexdigest(),
            backup_registry_sha256=hashlib.sha256(
                (backup_directory / BACKUP_REGISTRY_NAME).read_bytes()
            ).hexdigest(),
            active_registry_sha256_before=preview.active_registry_sha256_before,
            active_registry_sha256_after=activated_sha256,
            source_schema_version=preview.source_schema_version,
            target_schema_version=preview.target_schema_version,
            backup_registry_relative_path=preview.backup_registry_relative_path,
        )
        receipt_path = backup_directory / MIGRATION_RECEIPT_NAME
        _write_new_bytes(receipt_path, (receipt.canonical_json() + "\n").encode("utf-8"))
        return V06MigrationResult(
            backup_directory=backup_directory,
            backup_registry_path=backup_directory / BACKUP_REGISTRY_NAME,
            receipt_path=receipt_path,
            receipt=receipt,
        )
    finally:
        shutil.rmtree(staging, ignore_errors=True)


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
    backup = root / receipt.backup_registry_relative_path
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
    if active_sha256 != receipt.active_registry_sha256_after:
        raise V06MigrationError(
            "ACTIVE_REGISTRY_DIVERGED",
            "the active registry changed after activation; rollback would destroy new "
            "state and requires manual review",
        )
    staging = Path(tempfile.mkdtemp(prefix=".traffictwin-v06-rollback-", dir=root))
    try:
        staged = staging / "restored-registry.sqlite"
        staged.write_bytes(backup_bytes)
        _fsync_file(staged)
        os.replace(staged, active)
        _fsync_directory(active.parent)
        restored_sha256 = hashlib.sha256(active.read_bytes()).hexdigest()
        rollback = V06RollbackReceipt(
            migration_id=receipt.migration_id,
            rolled_back_at=_utc_now(clock),
            migration_receipt_fingerprint=receipt.fingerprint(),
            active_registry_sha256_before_rollback=active_sha256,
            restored_registry_sha256=restored_sha256,
        )
        rollback_path = backup.parent / ROLLBACK_RECEIPT_NAME
        _write_new_bytes(rollback_path, (rollback.canonical_json() + "\n").encode("utf-8"))
        return V06RollbackResult(receipt_path=rollback_path, receipt=rollback)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


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
    if resolved == (workspace_root / V07_ACTIVE_REGISTRY).resolve():
        raise V06MigrationError(
            "SOURCE_IS_ACTIVE_REGISTRY", "the active v0.7 registry cannot be its own source"
        )
    return resolved


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

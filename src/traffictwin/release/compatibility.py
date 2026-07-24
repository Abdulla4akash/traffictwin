"""v0.7 workspace isolation and read-only v0.6 compatibility copies.

This module is deliberately not a cross-release schema migrator.  It creates a
separately marked v0.7 workspace and can place a byte-exact, non-active copy of
one closed v0.6 registry inside it.  Activation and schema migration remain
separate REL-01 acceptance work.
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

from traffictwin.release.metadata import current_release_metadata
from traffictwin.storage.migrations import (
    CURRENT_REGISTRY_SCHEMA_VERSION,
    RegistryMigrationState,
    RegistryMigrationStatus,
    inspect_registry_migrations,
)
from traffictwin.storage.registry import Registry

REL_01_CAPABILITY_ID: Literal["REL-01"] = "REL-01"
V07_WORKSPACE_SCHEMA_VERSION: Literal["traffictwin.workspace.v0.7.v1"] = (
    "traffictwin.workspace.v0.7.v1"
)
V07_WORKSPACE_KIND: Literal["traffictwin_v0_7"] = "traffictwin_v0_7"
V07_WORKSPACE_NAMESPACE: Literal["workspace-v0.7"] = "workspace-v0.7"
V07_CACHE_NAMESPACE: Literal["traffictwin-cache-v0.7"] = "traffictwin-cache-v0.7"
V07_MANIFEST_NAME = "workspace-v0.7.json"
V07_ACTIVE_REGISTRY: Literal["registry/traffictwin.sqlite"] = "registry/traffictwin.sqlite"
V06_COMPATIBILITY_ROOT = "compatibility/v0.6"
V06_REGISTRY_SCHEMA_VERSION = 5
MAX_WORKSPACE_MANIFEST_BYTES = 64 * 1024
COPY_FREE_SPACE_RESERVE_BYTES = 1024 * 1024

V07_REQUIRED_DIRECTORIES: tuple[str, ...] = (
    "registry",
    "manchester/raw",
    "manchester/accepted",
    "manchester/projections",
    "manchester/mappings",
    "manchester/calibrations",
    "manchester/comparisons",
    "runs",
    "exports",
    "cache/v0.7",
    V06_COMPATIBILITY_ROOT,
    "quarantine",
)


class V07CompatibilityError(RuntimeError):
    """Base error for v0.7 workspace or v0.6 compatibility-copy failures."""


class V07WorkspaceError(V07CompatibilityError):
    """Raised when a v0.7 workspace target or marker is invalid."""


class V06RegistryCopyError(V07CompatibilityError):
    """Raised when a v0.6 registry cannot be copied without mutation."""


class V07WorkspaceContract(BaseModel):
    """Published REL-01 foundation contract."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["traffictwin.workspace.v0.7.v1"] = V07_WORKSPACE_SCHEMA_VERSION
    capability_id: Literal["REL-01"] = REL_01_CAPABILITY_ID
    capability_status: Literal["planned"] = "planned"
    workspace_kind: Literal["traffictwin_v0_7"] = V07_WORKSPACE_KIND
    workspace_namespace: Literal["workspace-v0.7"] = V07_WORKSPACE_NAMESPACE
    cache_namespace: Literal["traffictwin-cache-v0.7"] = V07_CACHE_NAMESPACE
    active_registry: Literal["registry/traffictwin.sqlite"] = V07_ACTIVE_REGISTRY
    required_directories: list[str]
    source_policy: list[str]
    copy_policy: list[str]
    exclusions: list[str]
    limitations: list[str]

    def canonical_json(self) -> str:
        """Return byte-stable JSON for the exact foundation contract."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Return the SHA-256 identity of this exact contract."""

        return _sha256_bytes(self.canonical_json().encode("utf-8"))


class V07WorkspaceManifest(BaseModel):
    """Strict marker for one isolated v0.7 workspace."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["traffictwin.workspace.v0.7.v1"] = V07_WORKSPACE_SCHEMA_VERSION
    workspace_kind: Literal["traffictwin_v0_7"] = V07_WORKSPACE_KIND
    workspace_namespace: Literal["workspace-v0.7"] = V07_WORKSPACE_NAMESPACE
    design_version: Literal["0.7"] = "0.7"
    implementation_status: Literal["foundation_not_release"] = "foundation_not_release"
    created_at: datetime
    producer_package_version: str = Field(min_length=1)
    cache_namespace: Literal["traffictwin-cache-v0.7"] = V07_CACHE_NAMESPACE
    active_registry: Literal["registry/traffictwin.sqlite"] = V07_ACTIVE_REGISTRY
    required_directories: list[str]
    compatibility_source_mutation_allowed: Literal[False] = False
    compatibility_activation_automatic: Literal[False] = False

    @model_validator(mode="after")
    def validate_exact_layout_and_time(self) -> V07WorkspaceManifest:
        """Keep the marker unambiguous and independent from machine locale."""

        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        if self.required_directories != list(V07_REQUIRED_DIRECTORIES):
            raise ValueError("required_directories must match the v0.7 layout exactly")
        return self

    def canonical_json(self) -> str:
        """Return byte-stable JSON for this workspace marker."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Return the SHA-256 identity of this exact marker."""

        return _sha256_bytes(self.canonical_json().encode("utf-8"))


class V07WorkspaceInspection(BaseModel):
    """Verified structural state of one v0.7 workspace."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["traffictwin.workspace.v0.7.v1"] = V07_WORKSPACE_SCHEMA_VERSION
    capability_id: Literal["REL-01"] = REL_01_CAPABILITY_ID
    capability_status: Literal["planned"] = "planned"
    valid: Literal[True] = True
    manifest: V07WorkspaceManifest
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    active_registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    active_registry_status: RegistryMigrationStatus


class V06RegistryCopyPreview(BaseModel):
    """Non-mutating plan for one compatibility snapshot copy."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["traffictwin.compatibility-copy.v1"] = (
        "traffictwin.compatibility-copy.v1"
    )
    capability_id: Literal["REL-01"] = REL_01_CAPABILITY_ID
    capability_status: Literal["planned"] = "planned"
    operation: Literal["copy_only_not_migration"] = "copy_only_not_migration"
    source_product_version: None = None
    source_registry_schema_version: int = Field(ge=1)
    source_registry_state: RegistryMigrationState
    source_registry_schema_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_registry_size_bytes: int = Field(ge=1)
    target_active_registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_relative_directory: str = Field(pattern=r"^compatibility/v0\.6/[0-9a-f]{16}$")
    copied_registry_relative_path: str
    receipt_relative_path: str
    required_free_bytes: int = Field(ge=1)
    available_free_bytes: int = Field(ge=0)
    backup_required: Literal[False] = False
    backup_relative_path: None = None
    source_mutation_allowed: Literal[False] = False
    automatic_activation: Literal[False] = False
    unsupported_records: list[str]
    blockers: list[str]
    actions: list[str]

    @property
    def has_required_space(self) -> bool:
        """Return whether the previewed destination currently has enough free bytes."""

        return self.available_free_bytes >= self.required_free_bytes

    def canonical_json(self) -> str:
        """Return byte-stable JSON for the exact preview."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Return the SHA-256 identity of this exact preview."""

        return _sha256_bytes(self.canonical_json().encode("utf-8"))


class V06RegistryCopyReceipt(BaseModel):
    """Receipt proving one byte-exact, non-active compatibility copy."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["traffictwin.compatibility-copy-receipt.v1"] = (
        "traffictwin.compatibility-copy-receipt.v1"
    )
    capability_id: Literal["REL-01"] = REL_01_CAPABILITY_ID
    capability_status: Literal["planned"] = "planned"
    copy_id: str = Field(pattern=r"^v06-[0-9a-f]{16}$")
    copied_at: datetime
    operation: Literal["copy_only_not_migration"] = "copy_only_not_migration"
    source_product_version: None = None
    source_registry_schema_version: int = Field(ge=1)
    source_registry_schema_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_registry_sha256_before: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_registry_sha256_after: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_registry_size_bytes: int = Field(ge=1)
    copied_registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    copied_registry_size_bytes: int = Field(ge=1)
    target_active_registry_sha256_before: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_active_registry_sha256_after: str = Field(pattern=r"^[0-9a-f]{64}$")
    copied_registry_relative_path: str
    source_unchanged_during_copy: Literal[True] = True
    active_registry_unchanged_during_copy: Literal[True] = True
    byte_exact: Literal[True] = True
    automatic_activation: Literal[False] = False
    scientific_admission: Literal["unavailable"] = "unavailable"
    limitations: list[str]

    @model_validator(mode="after")
    def validate_reconciliation(self) -> V06RegistryCopyReceipt:
        """Reject any receipt whose hashes or byte counts do not reconcile."""

        if not (
            self.source_registry_sha256_before
            == self.source_registry_sha256_after
            == self.copied_registry_sha256
        ):
            raise ValueError("source and copied registry hashes must match exactly")
        if self.source_registry_size_bytes != self.copied_registry_size_bytes:
            raise ValueError("source and copied registry sizes must match exactly")
        if self.target_active_registry_sha256_before != self.target_active_registry_sha256_after:
            raise ValueError("the active v0.7 registry must remain unchanged")
        return self

    def canonical_json(self) -> str:
        """Return byte-stable JSON for this compatibility-copy receipt."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Return the SHA-256 identity of this exact receipt."""

        return _sha256_bytes(self.canonical_json().encode("utf-8"))


@dataclass(frozen=True)
class V07WorkspaceInitialiseResult:
    """Operational paths plus verified state for one new workspace."""

    path: Path
    manifest_path: Path
    active_registry_path: Path
    inspection: V07WorkspaceInspection


@dataclass(frozen=True)
class V06RegistryCopyResult:
    """Operational paths plus receipt for one compatibility copy."""

    directory: Path
    registry_path: Path
    receipt_path: Path
    receipt: V06RegistryCopyReceipt


def v07_workspace_contract() -> V07WorkspaceContract:
    """Return the exact planned REL-01 foundation contract."""

    return V07WorkspaceContract(
        required_directories=list(V07_REQUIRED_DIRECTORIES),
        source_policy=[
            "The v0.6.0 tag and every source workspace/registry are read-only inputs.",
            "A registry file must be regular, non-symlinked, closed, and free of "
            "WAL/journal files.",
            "Registry structure is inspected through SQLite immutable read-only mode before copy.",
        ],
        copy_policy=[
            "A v0.7 workspace is created new-only under a distinct marker and cache namespace.",
            "Compatibility copies are byte-exact and published under compatibility/v0.6.",
            "The active v0.7 registry is never replaced, migrated, or activated by a copy.",
            "Source, copied, and active-registry hashes reconcile in the receipt.",
        ],
        exclusions=[
            "No in-place cross-release migration or downgrade is implemented.",
            "No copied registry is automatically activated.",
            "No bundle, raw input, accepted output, export, or private source artifact is copied.",
        ],
        limitations=[
            "A registry does not encode enough evidence to prove its producing package version.",
            "Side-by-side clean-checkout acceptance, package/release version alignment, and "
            "final release reconciliation remain pending REL-01 work.",
            "A structural copy does not revalidate stored scientific payloads.",
        ],
    )


def initialise_v07_workspace(
    path: str | Path,
    *,
    clock: Callable[[], datetime] | None = None,
) -> V07WorkspaceInitialiseResult:
    """Atomically create a separately marked, new-only v0.7 workspace."""

    target = Path(path)
    _ensure_safe_new_target(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".traffictwin-v07-workspace-", dir=target.parent))
    try:
        for relative in V07_REQUIRED_DIRECTORIES:
            (staging / relative).mkdir(parents=True, exist_ok=True)
        active_registry = staging / V07_ACTIVE_REGISTRY
        Registry(active_registry).initialize()
        manifest = V07WorkspaceManifest(
            created_at=_utc_now(clock),
            producer_package_version=current_release_metadata().version,
            required_directories=list(V07_REQUIRED_DIRECTORIES),
        )
        _write_new_bytes(
            staging / V07_MANIFEST_NAME,
            (manifest.canonical_json() + "\n").encode("utf-8"),
        )
        inspect_v07_workspace(staging)
        if _lexists(target):
            raise FileExistsError(f"v0.7 workspace target already exists: {target}")
        os.rename(staging, target)
        _fsync_directory(target.parent)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    inspection = inspect_v07_workspace(target)
    return V07WorkspaceInitialiseResult(
        path=target,
        manifest_path=target / V07_MANIFEST_NAME,
        active_registry_path=target / V07_ACTIVE_REGISTRY,
        inspection=inspection,
    )


def inspect_v07_workspace(path: str | Path) -> V07WorkspaceInspection:
    """Inspect a v0.7 workspace without changing its files or registry."""

    root = Path(path)
    if root.is_symlink() or not root.is_dir():
        raise V07WorkspaceError(f"v0.7 workspace must be a non-symlinked directory: {root}")
    manifest_path = root / V07_MANIFEST_NAME
    _require_regular_file(manifest_path, label="v0.7 workspace manifest")
    if manifest_path.stat().st_size > MAX_WORKSPACE_MANIFEST_BYTES:
        raise V07WorkspaceError("v0.7 workspace manifest exceeds the bounded size limit")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = V07WorkspaceManifest.model_validate(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise V07WorkspaceError(f"invalid v0.7 workspace manifest: {exc}") from exc
    for relative in manifest.required_directories:
        directory = _safe_relative_path(root, relative)
        if directory.is_symlink() or not directory.is_dir():
            raise V07WorkspaceError(f"required v0.7 directory is missing or unsafe: {relative}")
    active_registry = _safe_relative_path(root, manifest.active_registry)
    _require_regular_file(active_registry, label="active v0.7 registry")
    try:
        status = inspect_registry_migrations(active_registry)
    except Exception as exc:
        raise V07WorkspaceError(f"active v0.7 registry inspection failed: {exc}") from exc
    if status.current_version != CURRENT_REGISTRY_SCHEMA_VERSION:
        raise V07WorkspaceError(
            f"active v0.7 registry is not at the supported schema version: {status.current_version}"
        )
    return V07WorkspaceInspection(
        manifest=manifest,
        manifest_sha256=_sha256_file(manifest_path),
        active_registry_sha256=_sha256_file(active_registry),
        active_registry_status=status,
    )


def preview_v06_registry_copy(
    source_registry: str | Path,
    target_workspace: str | Path,
) -> V06RegistryCopyPreview:
    """Build a non-mutating preview for a byte-exact compatibility copy."""

    root = Path(target_workspace)
    workspace = inspect_v07_workspace(root)
    source = _validated_closed_source_registry(Path(source_registry), root)
    try:
        source_status = inspect_registry_migrations(source)
    except Exception as exc:
        raise V06RegistryCopyError(f"source registry inspection failed: {exc}") from exc
    if source_status.current_version != V06_REGISTRY_SCHEMA_VERSION:
        raise V06RegistryCopyError(
            "source registry does not match the frozen v0.6 registry schema: "
            f"expected={V06_REGISTRY_SCHEMA_VERSION}, observed={source_status.current_version}; "
            "cross-release schema migration requires a separate accepted decision"
        )
    source_size = source.stat().st_size
    source_sha256 = _sha256_file(source)
    copy_id = f"v06-{source_sha256[:16]}"
    target_relative_directory = f"{V06_COMPATIBILITY_ROOT}/{source_sha256[:16]}"
    required_free = source_size + COPY_FREE_SPACE_RESERVE_BYTES
    available_free = shutil.disk_usage(root).free
    return V06RegistryCopyPreview(
        source_registry_schema_version=source_status.current_version,
        source_registry_state=source_status.state,
        source_registry_schema_fingerprint=source_status.schema_fingerprint,
        source_registry_sha256=source_sha256,
        source_registry_size_bytes=source_size,
        target_active_registry_sha256=workspace.active_registry_sha256,
        target_relative_directory=target_relative_directory,
        copied_registry_relative_path=f"{target_relative_directory}/registry.sqlite",
        receipt_relative_path=f"{target_relative_directory}/copy-receipt.json",
        required_free_bytes=required_free,
        available_free_bytes=available_free,
        unsupported_records=[],
        blockers=[
            "The source registry does not encode a verifiable producer package version.",
            "This copy is not an activation, schema migration, downgrade, or scientific review.",
        ],
        actions=[
            f"Create one new compatibility snapshot {copy_id}.",
            "Copy the closed source registry without metadata or in-place writes.",
            "Reconcile source, copied, and active-registry hashes before atomic publication.",
            "Leave the copied registry non-active for later reviewed migration work.",
        ],
    )


def copy_v06_registry(
    source_registry: str | Path,
    target_workspace: str | Path,
    *,
    clock: Callable[[], datetime] | None = None,
) -> V06RegistryCopyResult:
    """Publish one byte-exact, non-active copy without mutating either active registry."""

    source = Path(source_registry)
    root = Path(target_workspace)
    preview = preview_v06_registry_copy(source, root)
    root = root.resolve(strict=True)
    source = _validated_closed_source_registry(source, root)
    if not preview.has_required_space:
        raise V06RegistryCopyError(
            "insufficient free space for compatibility copy: "
            f"required={preview.required_free_bytes}, available={preview.available_free_bytes}"
        )
    destination = _safe_relative_path(root, preview.target_relative_directory)
    if _lexists(destination):
        raise FileExistsError(f"compatibility snapshot already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".traffictwin-v06-copy-", dir=destination.parent))
    copied = staging / "registry.sqlite"
    active_registry = root / V07_ACTIVE_REGISTRY
    try:
        shutil.copyfile(source, copied)
        os.chmod(copied, 0o600)
        _fsync_file(copied)
        copied_size = copied.stat().st_size
        copied_sha256 = _sha256_file(copied)
        source_after = _validated_closed_source_registry(source, root)
        source_sha256_after = _sha256_file(source_after)
        active_sha256_after = _sha256_file(active_registry)
        try:
            copied_status = inspect_registry_migrations(copied)
        except Exception as exc:
            raise V06RegistryCopyError(f"copied registry verification failed: {exc}") from exc
        if copied_status.schema_fingerprint != preview.source_registry_schema_fingerprint:
            raise V06RegistryCopyError("copied registry schema fingerprint changed during copy")
        if not (
            copied_size == preview.source_registry_size_bytes
            and copied_sha256 == preview.source_registry_sha256 == source_sha256_after
        ):
            raise V06RegistryCopyError("source registry changed or copy was not byte-exact")
        if active_sha256_after != preview.target_active_registry_sha256:
            raise V06RegistryCopyError("active v0.7 registry changed during compatibility copy")
        receipt = V06RegistryCopyReceipt(
            copy_id=f"v06-{preview.source_registry_sha256[:16]}",
            copied_at=_utc_now(clock),
            source_registry_schema_version=preview.source_registry_schema_version,
            source_registry_schema_fingerprint=preview.source_registry_schema_fingerprint,
            source_registry_sha256_before=preview.source_registry_sha256,
            source_registry_sha256_after=source_sha256_after,
            source_registry_size_bytes=preview.source_registry_size_bytes,
            copied_registry_sha256=copied_sha256,
            copied_registry_size_bytes=copied_size,
            target_active_registry_sha256_before=preview.target_active_registry_sha256,
            target_active_registry_sha256_after=active_sha256_after,
            copied_registry_relative_path=preview.copied_registry_relative_path,
            limitations=[
                "The producing v0.6 package version is not proven by the registry alone.",
                "The copy is not active and no stored payload was reinterpreted or revalidated.",
                "Full migration, backup, activation, rollback, and downgrade refusal remain "
                "pending.",
            ],
        )
        _write_new_bytes(
            staging / "copy-receipt.json",
            (receipt.canonical_json() + "\n").encode("utf-8"),
        )
        _fsync_directory(staging)
        if _lexists(destination):
            raise FileExistsError(f"compatibility snapshot already exists: {destination}")
        os.rename(staging, destination)
        _fsync_directory(destination.parent)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return V06RegistryCopyResult(
        directory=destination,
        registry_path=destination / "registry.sqlite",
        receipt_path=destination / "copy-receipt.json",
        receipt=receipt,
    )


def _validated_closed_source_registry(source: Path, target_root: Path) -> Path:
    _require_regular_file(source, label="source v0.6 registry")
    resolved_source = source.resolve(strict=True)
    resolved_target = target_root.resolve(strict=True)
    if resolved_source == (resolved_target / V07_ACTIVE_REGISTRY).resolve():
        raise V06RegistryCopyError(
            "the active v0.7 registry cannot be its own compatibility source"
        )
    if resolved_source.is_relative_to(resolved_target):
        raise V06RegistryCopyError(
            "the v0.6 compatibility source must be outside the v0.7 workspace"
        )
    sidecars = [
        Path(f"{resolved_source}-wal"),
        Path(f"{resolved_source}-shm"),
        Path(f"{resolved_source}-journal"),
    ]
    present = [path.name for path in sidecars if _lexists(path)]
    if present:
        raise V06RegistryCopyError(
            "source registry must be closed and checkpointed; sidecar files are present: "
            + ", ".join(sorted(present))
        )
    if resolved_source.stat().st_size <= 0:
        raise V06RegistryCopyError("source v0.6 registry is empty")
    return resolved_source


def _ensure_safe_new_target(target: Path) -> None:
    resolved = target.resolve(strict=False)
    blocked = {Path("/").resolve(), Path.home().resolve(), Path.cwd().resolve()}
    if resolved in blocked or resolved.parent == resolved:
        raise V07WorkspaceError(f"unsafe v0.7 workspace target: {target}")
    if _lexists(target):
        raise FileExistsError(f"v0.7 workspace target already exists: {target}")


def _safe_relative_path(root: Path, relative: str) -> Path:
    candidate_relative = Path(relative)
    if candidate_relative.is_absolute() or ".." in candidate_relative.parts:
        raise V07WorkspaceError(f"unsafe workspace-relative path: {relative}")
    resolved_root = root.resolve(strict=True)
    resolved_candidate = (root / candidate_relative).resolve(strict=False)
    if not resolved_candidate.is_relative_to(resolved_root):
        raise V07WorkspaceError(f"workspace path escapes its root: {relative}")
    return root / candidate_relative


def _require_regular_file(path: Path, *, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise V07WorkspaceError(f"{label} must be a non-symlinked regular file: {path}")


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
    value = (clock or (lambda: datetime.now(UTC)))()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock must return a timezone-aware datetime")
    return value.astimezone(UTC)


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


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

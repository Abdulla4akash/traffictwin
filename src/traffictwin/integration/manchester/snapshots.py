"""Atomic, new-only, fail-closed publication of immutable Manchester snapshots.

This module is the source-neutral snapshot half of Gate B / ``MAN-01``. It
performs no network access, no parsing of member content, no freshness
computation, and no logging; raw bytes are preserved exactly and hashes — not
filesystem permissions — are the integrity authority.
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path

from traffictwin.integration.manchester.models import (
    MANIFEST_FILE_NAME,
    QUARANTINE_MANIFEST_FILE_NAME,
    QUARANTINE_RECEIPT_FILE_NAME,
    RAW_DIRECTORY_NAME,
    RECEIPT_FILE_NAME,
    ManchesterQuarantineManifest,
    ManchesterQuarantineReceipt,
    ManchesterSnapshotManifest,
    ManchesterSnapshotPolicy,
    ManchesterSnapshotReceipt,
    ManchesterValidationState,
    build_raw_fingerprint,
    sha256_hex,
)

MAX_MANIFEST_FILE_BYTES = 8_000_000
MAX_RECEIPT_FILE_BYTES = 1_000_000
QUARANTINE_DIRECTORY_NAME = "quarantine"
ACCEPTED_DIRECTORY_NAME = "accepted"


class ManchesterSnapshotError(RuntimeError):
    """Typed refusal raised by snapshot publication or verification."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def publish_manchester_snapshot(
    workspace_root: str | Path,
    manifest: ManchesterSnapshotManifest,
    members: Mapping[str, bytes],
    policy: ManchesterSnapshotPolicy,
) -> ManchesterSnapshotReceipt:
    """Atomically publish one immutable snapshot; new-only and fail-closed.

    The destination directory ``<workspace_root>/<snapshot_id>`` must not
    exist. All raw bytes are written to an isolated temporary sibling, every
    member is re-hashed and reconciled against the manifest, files are made
    read-only where the platform supports it, and only then is the directory
    renamed into place. Failure never leaves a partial destination and never
    touches any existing snapshot.
    """

    root = Path(workspace_root)
    if not root.is_dir() or root.is_symlink():
        raise ManchesterSnapshotError(
            "WORKSPACE_INVALID", "workspace root must be an existing non-symlink directory"
        )
    if manifest.validation_state is ManchesterValidationState.REJECTED:
        raise ManchesterSnapshotError(
            "MANIFEST_REJECTED", "a rejected snapshot manifest cannot be published"
        )
    _check_policy(manifest, policy)
    _check_members_against_manifest(manifest, members)

    destination = root / manifest.snapshot_id
    lock_path = root / f".{manifest.snapshot_id}.publish.lock"
    lock_fd = _acquire_publication_lock(lock_path)
    temporary_root: Path | None = None
    try:
        if destination.exists() or destination.is_symlink():
            raise ManchesterSnapshotError(
                "DESTINATION_EXISTS",
                f"snapshot destination {manifest.snapshot_id!r} already exists; "
                "accepted snapshots are never replaced",
            )

        temporary_root = Path(
            tempfile.mkdtemp(prefix=f".{manifest.snapshot_id}-staging-", dir=root)
        )
        payload = temporary_root / "payload"
        raw_root = payload / RAW_DIRECTORY_NAME
        raw_root.mkdir(parents=True)

        for member in manifest.members:
            target = raw_root / member.relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as handle:
                handle.write(members[member.relative_path])

        manifest_bytes = manifest.canonical_json().encode("utf-8")
        manifest_path = payload / MANIFEST_FILE_NAME
        manifest_path.write_bytes(manifest_bytes)

        verified_count, verified_bytes = _verify_raw_tree(manifest, raw_root, policy)

        receipt = ManchesterSnapshotReceipt(
            snapshot_id=manifest.snapshot_id,
            manifest_fingerprint=manifest.fingerprint(),
            manifest_file_sha256=sha256_hex(manifest_bytes),
            raw_fingerprint=manifest.raw_fingerprint,
            verified_member_count=verified_count,
            verified_total_bytes=verified_bytes,
            policy=policy,
            read_only_applied=_apply_read_only(payload),
        )
        (payload / RECEIPT_FILE_NAME).write_bytes(receipt.canonical_json().encode("utf-8"))
        _make_file_read_only(payload / RECEIPT_FILE_NAME)

        if destination.exists() or destination.is_symlink():
            raise ManchesterSnapshotError(
                "DESTINATION_EXISTS",
                f"snapshot destination {manifest.snapshot_id!r} appeared during staging",
            )
        _rename_into_place(payload, destination)
        return receipt
    finally:
        if temporary_root is not None:
            shutil.rmtree(temporary_root, ignore_errors=True)
        _release_publication_lock(lock_fd, lock_path)


def publish_manchester_quarantine(
    workspace_root: str | Path,
    manifest: ManchesterQuarantineManifest,
    members: Mapping[str, bytes],
    policy: ManchesterSnapshotPolicy,
) -> ManchesterQuarantineReceipt:
    """Atomically preserve one complete acquisition before any parser runs."""

    quarantine_root = _workspace_area(workspace_root, QUARANTINE_DIRECTORY_NAME, create=True)
    _check_policy(manifest, policy)
    _check_members_against_manifest(manifest, members)
    destination = quarantine_root / manifest.snapshot_id
    lock_path = quarantine_root / f".{manifest.snapshot_id}.publish.lock"
    lock_fd = _acquire_publication_lock(lock_path)
    temporary_root: Path | None = None
    try:
        if destination.exists() or destination.is_symlink():
            raise ManchesterSnapshotError(
                "DESTINATION_EXISTS",
                f"quarantine destination {manifest.snapshot_id!r} already exists",
            )
        temporary_root = Path(
            tempfile.mkdtemp(prefix=f".{manifest.snapshot_id}-staging-", dir=quarantine_root)
        )
        payload = temporary_root / "payload"
        raw_root = payload / RAW_DIRECTORY_NAME
        raw_root.mkdir(parents=True)
        for member in manifest.members:
            target = raw_root / member.relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as handle:
                handle.write(members[member.relative_path])

        manifest_bytes = manifest.canonical_json().encode("utf-8")
        (payload / QUARANTINE_MANIFEST_FILE_NAME).write_bytes(manifest_bytes)
        verified_count, verified_bytes = _verify_raw_tree(manifest, raw_root, policy)
        receipt = ManchesterQuarantineReceipt(
            snapshot_id=manifest.snapshot_id,
            manifest_fingerprint=manifest.fingerprint(),
            manifest_file_sha256=sha256_hex(manifest_bytes),
            raw_fingerprint=manifest.raw_fingerprint,
            verified_member_count=verified_count,
            verified_total_bytes=verified_bytes,
            policy=policy,
            read_only_applied=_apply_read_only(payload),
        )
        (payload / QUARANTINE_RECEIPT_FILE_NAME).write_bytes(
            receipt.canonical_json().encode("utf-8")
        )
        _make_file_read_only(payload / QUARANTINE_RECEIPT_FILE_NAME)
        if destination.exists() or destination.is_symlink():
            raise ManchesterSnapshotError(
                "DESTINATION_EXISTS",
                f"quarantine destination {manifest.snapshot_id!r} appeared during staging",
            )
        _rename_into_place(payload, destination)
        return receipt
    finally:
        if temporary_root is not None:
            shutil.rmtree(temporary_root, ignore_errors=True)
        _release_publication_lock(lock_fd, lock_path)


def verify_manchester_quarantine(snapshot_dir: str | Path) -> ManchesterQuarantineReceipt:
    """Reopen and fully verify a pre-parse quarantine artifact."""

    directory = Path(snapshot_dir)
    if directory.is_symlink() or not directory.is_dir():
        raise ManchesterSnapshotError(
            "QUARANTINE_INVALID", "quarantine path must be an existing non-symlink directory"
        )
    _verify_top_level_layout(
        directory,
        manifest_name=QUARANTINE_MANIFEST_FILE_NAME,
        receipt_name=QUARANTINE_RECEIPT_FILE_NAME,
    )
    manifest_bytes = _read_bounded(
        directory / QUARANTINE_MANIFEST_FILE_NAME, MAX_MANIFEST_FILE_BYTES
    )
    manifest = ManchesterQuarantineManifest.model_validate_json(manifest_bytes)
    if manifest.snapshot_id != directory.name:
        raise ManchesterSnapshotError(
            "SNAPSHOT_ID_MISMATCH", "directory name does not match the quarantine snapshot id"
        )
    receipt_bytes = _read_bounded(directory / QUARANTINE_RECEIPT_FILE_NAME, MAX_RECEIPT_FILE_BYTES)
    receipt = ManchesterQuarantineReceipt.model_validate_json(receipt_bytes)
    _reconcile_quarantine_receipt(manifest, manifest_bytes, receipt)
    _check_policy(manifest, receipt.policy)
    verified_count, verified_bytes = _verify_raw_tree(
        manifest, directory / RAW_DIRECTORY_NAME, receipt.policy
    )
    if receipt.verified_member_count != verified_count:
        raise ManchesterSnapshotError(
            "RECEIPT_MISMATCH", "quarantine receipt member count does not reconcile"
        )
    if receipt.verified_total_bytes != verified_bytes:
        raise ManchesterSnapshotError(
            "RECEIPT_MISMATCH", "quarantine receipt byte total does not reconcile"
        )
    return receipt


def promote_manchester_quarantine(
    workspace_root: str | Path,
    accepted_manifest: ManchesterSnapshotManifest,
) -> ManchesterSnapshotReceipt:
    """Promote verified quarantined bytes only after source validation succeeds."""

    if accepted_manifest.validation_state is ManchesterValidationState.REJECTED:
        raise ManchesterSnapshotError(
            "MANIFEST_REJECTED", "a rejected validation result remains quarantined"
        )
    quarantine_root = _workspace_area(workspace_root, QUARANTINE_DIRECTORY_NAME, create=False)
    quarantine_dir = quarantine_root / accepted_manifest.snapshot_id
    receipt = verify_manchester_quarantine(quarantine_dir)
    manifest_bytes = _read_bounded(
        quarantine_dir / QUARANTINE_MANIFEST_FILE_NAME, MAX_MANIFEST_FILE_BYTES
    )
    quarantine_manifest = ManchesterQuarantineManifest.model_validate_json(manifest_bytes)
    _check_promotion_identity(quarantine_manifest, accepted_manifest)
    members: dict[str, bytes] = {}
    for member in quarantine_manifest.members:
        payload = _read_bounded(
            quarantine_dir / RAW_DIRECTORY_NAME / member.relative_path,
            receipt.policy.max_member_bytes,
        )
        if len(payload) != member.byte_size or sha256_hex(payload) != member.sha256:
            raise ManchesterSnapshotError(
                "MEMBER_MUTATED", f"quarantined member {member.relative_path!r} changed"
            )
        members[member.relative_path] = payload
    accepted_root = _workspace_area(workspace_root, ACCEPTED_DIRECTORY_NAME, create=True)
    return publish_manchester_snapshot(
        accepted_root,
        accepted_manifest,
        members,
        receipt.policy,
    )


def quarantine_validate_and_promote(
    workspace_root: str | Path,
    quarantine_manifest: ManchesterQuarantineManifest,
    members: Mapping[str, bytes],
    policy: ManchesterSnapshotPolicy,
    validator: Callable[[Path, ManchesterQuarantineManifest], ManchesterSnapshotManifest],
) -> ManchesterSnapshotReceipt:
    """Enforce quarantine-before-validator ordering and promote only its accepted result.

    A validator exception or rejected result leaves the verified quarantine untouched
    and creates no accepted destination.
    """

    publish_manchester_quarantine(workspace_root, quarantine_manifest, members, policy)
    quarantine_root = _workspace_area(workspace_root, QUARANTINE_DIRECTORY_NAME, create=False)
    quarantine_dir = quarantine_root / quarantine_manifest.snapshot_id
    verify_manchester_quarantine(quarantine_dir)
    accepted_manifest = validator(quarantine_dir, quarantine_manifest)
    return promote_manchester_quarantine(workspace_root, accepted_manifest)


def verify_manchester_snapshot(snapshot_dir: str | Path) -> ManchesterSnapshotReceipt:
    """Reopen a snapshot and re-verify every hash, size, and fingerprint.

    Returns the stored receipt only after the raw tree, manifest, and receipt
    all reconcile exactly; any drift raises :class:`ManchesterSnapshotError`.
    """

    directory = Path(snapshot_dir)
    if directory.is_symlink() or not directory.is_dir():
        raise ManchesterSnapshotError(
            "SNAPSHOT_INVALID", "snapshot path must be an existing non-symlink directory"
        )

    _verify_top_level_layout(directory)
    manifest_bytes = _read_bounded(directory / MANIFEST_FILE_NAME, MAX_MANIFEST_FILE_BYTES)
    manifest = ManchesterSnapshotManifest.model_validate_json(manifest_bytes)
    if manifest.snapshot_id != directory.name:
        raise ManchesterSnapshotError(
            "SNAPSHOT_ID_MISMATCH", "directory name does not match the manifest snapshot id"
        )

    receipt_bytes = _read_bounded(directory / RECEIPT_FILE_NAME, MAX_RECEIPT_FILE_BYTES)
    receipt = ManchesterSnapshotReceipt.model_validate_json(receipt_bytes)
    if receipt.snapshot_id != manifest.snapshot_id:
        raise ManchesterSnapshotError(
            "RECEIPT_MISMATCH", "receipt snapshot id does not match the manifest"
        )
    if receipt.manifest_file_sha256 != sha256_hex(manifest_bytes):
        raise ManchesterSnapshotError(
            "RECEIPT_MISMATCH", "receipt does not match the stored manifest bytes"
        )
    if receipt.manifest_fingerprint != manifest.fingerprint():
        raise ManchesterSnapshotError(
            "RECEIPT_MISMATCH", "receipt does not match the manifest fingerprint"
        )
    if receipt.raw_fingerprint != manifest.raw_fingerprint:
        raise ManchesterSnapshotError(
            "RECEIPT_MISMATCH", "receipt does not match the raw fingerprint"
        )
    _check_policy(manifest, receipt.policy)
    raw_root = directory / RAW_DIRECTORY_NAME
    verified_count, verified_bytes = _verify_raw_tree(manifest, raw_root, receipt.policy)
    if build_raw_fingerprint(manifest.members) != manifest.raw_fingerprint:
        raise ManchesterSnapshotError(
            "FINGERPRINT_MISMATCH", "raw fingerprint no longer matches the inventory"
        )
    if receipt.verified_member_count != verified_count:
        raise ManchesterSnapshotError(
            "RECEIPT_MISMATCH", "receipt member count does not match the verified inventory"
        )
    if receipt.verified_total_bytes != verified_bytes:
        raise ManchesterSnapshotError(
            "RECEIPT_MISMATCH", "receipt byte total does not match the verified inventory"
        )
    return receipt


def read_manchester_member(snapshot_dir: str | Path, relative_path: str) -> bytes:
    """Return one raw member's exact bytes after hash verification."""

    directory = Path(snapshot_dir)
    receipt = verify_manchester_snapshot(directory)
    manifest_bytes = _read_bounded(directory / MANIFEST_FILE_NAME, MAX_MANIFEST_FILE_BYTES)
    manifest = ManchesterSnapshotManifest.model_validate_json(manifest_bytes)
    for member in manifest.members:
        if member.relative_path == relative_path:
            target = directory / RAW_DIRECTORY_NAME / member.relative_path
            if target.is_symlink():
                raise ManchesterSnapshotError(
                    "MEMBER_SYMLINK", f"member {relative_path!r} is a symlink"
                )
            payload = _read_bounded(target, receipt.policy.max_member_bytes)
            if len(payload) != member.byte_size or sha256_hex(payload) != member.sha256:
                raise ManchesterSnapshotError(
                    "MEMBER_MUTATED", f"member {relative_path!r} no longer matches its hash"
                )
            return payload
    raise ManchesterSnapshotError(
        "MEMBER_UNKNOWN", f"member {relative_path!r} is not in the manifest inventory"
    )


def _check_policy(
    manifest: ManchesterSnapshotManifest | ManchesterQuarantineManifest,
    policy: ManchesterSnapshotPolicy,
) -> None:
    if manifest.member_count > policy.max_member_count:
        raise ManchesterSnapshotError(
            "POLICY_MEMBER_COUNT",
            f"{manifest.member_count} members exceed the bound {policy.max_member_count}",
        )
    for member in manifest.members:
        if member.byte_size > policy.max_member_bytes:
            raise ManchesterSnapshotError(
                "POLICY_MEMBER_BYTES",
                f"member {member.relative_path!r} exceeds {policy.max_member_bytes} bytes",
            )
    if manifest.total_bytes > policy.max_total_bytes:
        raise ManchesterSnapshotError(
            "POLICY_TOTAL_BYTES",
            f"{manifest.total_bytes} total bytes exceed the bound {policy.max_total_bytes}",
        )


def _check_members_against_manifest(
    manifest: ManchesterSnapshotManifest | ManchesterQuarantineManifest,
    members: Mapping[str, bytes],
) -> None:
    manifest_paths = [member.relative_path for member in manifest.members]
    supplied_paths = sorted(members)
    if supplied_paths != manifest_paths:
        raise ManchesterSnapshotError(
            "MEMBER_SET_MISMATCH",
            "supplied member paths do not exactly match the manifest inventory",
        )
    for member in manifest.members:
        payload = members[member.relative_path]
        if len(payload) != member.byte_size:
            raise ManchesterSnapshotError(
                "MEMBER_SIZE_MISMATCH",
                f"member {member.relative_path!r} size does not match the manifest",
            )
        if sha256_hex(payload) != member.sha256:
            raise ManchesterSnapshotError(
                "MEMBER_HASH_MISMATCH",
                f"member {member.relative_path!r} bytes do not match the manifest hash",
            )


def _verify_raw_tree(
    manifest: ManchesterSnapshotManifest | ManchesterQuarantineManifest,
    raw_root: Path,
    policy: ManchesterSnapshotPolicy,
) -> tuple[int, int]:
    if raw_root.is_symlink() or not raw_root.is_dir():
        raise ManchesterSnapshotError(
            "RAW_TREE_INVALID", "raw member directory is missing or is a symlink"
        )
    expected = {member.relative_path: member for member in manifest.members}
    observed: set[str] = set()
    total = 0
    for path in sorted(raw_root.rglob("*")):
        if path.is_symlink():
            raise ManchesterSnapshotError(
                "MEMBER_SYMLINK", f"raw tree contains a symlink at {path.name!r}"
            )
        if path.is_dir():
            continue
        relative = path.relative_to(raw_root).as_posix()
        member = expected.get(relative)
        if member is None:
            raise ManchesterSnapshotError(
                "MEMBER_UNEXPECTED", f"raw tree contains an uninventoried file {relative!r}"
            )
        observed_size = path.stat().st_size
        if observed_size > policy.max_member_bytes:
            raise ManchesterSnapshotError(
                "POLICY_MEMBER_BYTES", "raw member tree exceeds its stored verification bounds"
            )
        if total + observed_size > policy.max_total_bytes:
            raise ManchesterSnapshotError(
                "POLICY_TOTAL_BYTES", "raw member tree exceeds its stored verification bounds"
            )
        if observed_size != member.byte_size:
            raise ManchesterSnapshotError(
                "MEMBER_SIZE_MISMATCH", f"member {relative!r} size drifted from the manifest"
            )
        payload = path.read_bytes()
        if len(payload) > policy.max_member_bytes:
            raise ManchesterSnapshotError(
                "POLICY_MEMBER_BYTES", "raw member tree exceeds its stored verification bounds"
            )
        if total + len(payload) > policy.max_total_bytes:
            raise ManchesterSnapshotError(
                "POLICY_TOTAL_BYTES", "raw member tree exceeds its stored verification bounds"
            )
        if len(payload) != member.byte_size:
            raise ManchesterSnapshotError(
                "MEMBER_SIZE_MISMATCH", f"member {relative!r} size drifted from the manifest"
            )
        if sha256_hex(payload) != member.sha256:
            raise ManchesterSnapshotError(
                "MEMBER_MUTATED", f"member {relative!r} bytes drifted from the manifest hash"
            )
        observed.add(relative)
        total += len(payload)
    missing = set(expected) - observed
    if missing:
        raise ManchesterSnapshotError(
            "MEMBER_MISSING", f"{len(missing)} inventoried members are missing from the raw tree"
        )
    return len(observed), total


def _apply_read_only(payload: Path) -> bool:
    """Best-effort read-only marking; hashes remain the integrity authority."""

    if os.name != "posix":
        return False
    for path in sorted(payload.rglob("*"), reverse=True):
        if path.is_file() and not path.is_symlink():
            _make_file_read_only(path)
    return True


def _make_file_read_only(path: Path) -> None:
    if os.name == "posix":
        path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def _acquire_publication_lock(lock_path: Path) -> int:
    try:
        descriptor = os.open(
            lock_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            stat.S_IRUSR | stat.S_IWUSR,
        )
    except FileExistsError as exc:
        raise ManchesterSnapshotError(
            "PUBLICATION_LOCKED", "another writer owns this snapshot publication"
        ) from exc
    try:
        os.write(descriptor, b"traffictwin-manchester-snapshot-publication\n")
    except OSError as exc:
        os.close(descriptor)
        lock_path.unlink(missing_ok=True)
        raise ManchesterSnapshotError(
            "PUBLICATION_FAILED", "publication lock could not be initialised"
        ) from exc
    return descriptor


def _release_publication_lock(descriptor: int, lock_path: Path) -> None:
    owned_inode = os.fstat(descriptor).st_ino
    os.close(descriptor)
    try:
        current = os.lstat(lock_path)
    except FileNotFoundError:
        return
    if current.st_ino == owned_inode:
        lock_path.unlink(missing_ok=True)


def _verify_top_level_layout(
    directory: Path,
    *,
    manifest_name: str = MANIFEST_FILE_NAME,
    receipt_name: str = RECEIPT_FILE_NAME,
) -> None:
    expected = {manifest_name, RAW_DIRECTORY_NAME, receipt_name}
    entries = list(directory.iterdir())
    if any(entry.is_symlink() for entry in entries):
        raise ManchesterSnapshotError(
            "SNAPSHOT_INVALID", "snapshot top-level entries must not be symlinks"
        )
    observed = {entry.name for entry in entries}
    if observed != expected:
        raise ManchesterSnapshotError(
            "SNAPSHOT_INVALID", "snapshot top-level inventory does not match the contract"
        )


def _workspace_area(workspace_root: str | Path, name: str, *, create: bool) -> Path:
    root = Path(workspace_root)
    if root.is_symlink() or not root.is_dir():
        raise ManchesterSnapshotError(
            "WORKSPACE_INVALID", "workspace root must be an existing non-symlink directory"
        )
    area = root / name
    if create:
        try:
            area.mkdir(mode=0o700, exist_ok=True)
        except OSError as exc:
            raise ManchesterSnapshotError(
                "WORKSPACE_INVALID", f"workspace area {name!r} could not be created"
            ) from exc
    if area.is_symlink() or not area.is_dir():
        raise ManchesterSnapshotError(
            "WORKSPACE_INVALID", f"workspace area {name!r} is missing or unsafe"
        )
    return area


def _reconcile_quarantine_receipt(
    manifest: ManchesterQuarantineManifest,
    manifest_bytes: bytes,
    receipt: ManchesterQuarantineReceipt,
) -> None:
    if receipt.snapshot_id != manifest.snapshot_id:
        raise ManchesterSnapshotError(
            "RECEIPT_MISMATCH", "quarantine receipt snapshot id does not match"
        )
    if receipt.manifest_file_sha256 != sha256_hex(manifest_bytes):
        raise ManchesterSnapshotError(
            "RECEIPT_MISMATCH", "quarantine receipt does not match manifest bytes"
        )
    if receipt.manifest_fingerprint != manifest.fingerprint():
        raise ManchesterSnapshotError(
            "RECEIPT_MISMATCH", "quarantine receipt does not match manifest fingerprint"
        )
    if receipt.raw_fingerprint != manifest.raw_fingerprint:
        raise ManchesterSnapshotError(
            "RECEIPT_MISMATCH", "quarantine receipt does not match raw fingerprint"
        )


def _check_promotion_identity(
    quarantine: ManchesterQuarantineManifest,
    accepted: ManchesterSnapshotManifest,
) -> None:
    common_fields = (
        "snapshot_id",
        "source",
        "request",
        "retrieval",
        "http",
        "members",
        "member_count",
        "total_bytes",
        "raw_fingerprint",
        "publication_class",
        "licence_id",
        "attribution_text",
        "access_date",
        "synthetic",
    )
    if any(getattr(quarantine, field) != getattr(accepted, field) for field in common_fields):
        raise ManchesterSnapshotError(
            "PROMOTION_IDENTITY_MISMATCH",
            "accepted manifest provenance differs from the pre-parse quarantine",
        )


def _rename_into_place(payload: Path, destination: Path) -> None:
    try:
        payload.rename(destination)
    except OSError as exc:
        raise ManchesterSnapshotError(
            "PUBLICATION_FAILED", "atomic rename into the destination failed"
        ) from exc


def _read_bounded(path: Path, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ManchesterSnapshotError(
            "SNAPSHOT_INVALID", f"required snapshot file {path.name!r} is missing or unsafe"
        )
    size = path.stat().st_size
    if size > limit:
        raise ManchesterSnapshotError(
            "SNAPSHOT_INVALID", f"snapshot file {path.name!r} exceeds its {limit}-byte bound"
        )
    payload = path.read_bytes()
    if len(payload) > limit:
        raise ManchesterSnapshotError(
            "SNAPSHOT_INVALID", f"snapshot file {path.name!r} exceeds its {limit}-byte bound"
        )
    return payload

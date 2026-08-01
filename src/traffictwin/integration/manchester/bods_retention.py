"""Explicit, fail-closed retention controls for private BODS snapshot families.

The BODS feed can contain vehicle identifiers in its immutable private raw
snapshot.  This boundary inventories the accepted/quarantine pair as one
snapshot family, verifies every artifact before making a decision, protects
the newest and currently displayed families, and produces a deterministic
preview.  Deletion is never automatic: applying a preview requires an exact
confirmation string and a byte-identical re-preview immediately beforehand.

This is a precautionary local engineering control, not a claim that the
project's legal/data-management retention basis has been approved.  Secure
erasure cannot be guaranteed by a portable filesystem deletion.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from traffictwin.integration.manchester.bods_acquisition import BODS_SOURCE_ID
from traffictwin.integration.manchester.map_layers import ManchesterMapScene
from traffictwin.integration.manchester.models import (
    MANIFEST_FILE_NAME,
    QUARANTINE_MANIFEST_FILE_NAME,
    ManchesterQuarantineManifest,
    ManchesterSnapshotManifest,
    ManchesterSnapshotModel,
)
from traffictwin.integration.manchester.snapshots import (
    ACCEPTED_DIRECTORY_NAME,
    MAX_MANIFEST_FILE_BYTES,
    QUARANTINE_DIRECTORY_NAME,
    ManchesterSnapshotError,
    verify_manchester_quarantine,
    verify_manchester_snapshot,
)
from traffictwin.release.compatibility import V07WorkspaceError, inspect_v07_workspace

BODS_RETENTION_SCHEMA_VERSION = "1.0"
BODS_RETENTION_METHOD_VERSION = "manchester-bods-retention-1.0"
BODS_RETENTION_POLICY_VERSION = "bods-private-retention-v1"
BODS_RETENTION_RECEIPT_DIRECTORY = Path("manchester/retention")
BODS_RETENTION_MAX_SCENE_BYTES = 8 * 1024 * 1024
BODS_RETENTION_DEFAULT_MAX_AGE_HOURS = 24
BODS_RETENTION_DEFAULT_MAX_SNAPSHOTS = 240
BODS_RETENTION_CONFIRMATION_PREFIX = "DELETE PRIVATE BODS SNAPSHOTS"


class BodsRetentionError(RuntimeError):
    """Typed retention refusal that never contains a private absolute path."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class BodsRetentionPolicy(ManchesterSnapshotModel):
    """Precautionary local bounds; not a legal retention approval."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-05"] = "MAN-05"
    method_version: Literal["manchester-bods-retention-1.0"] = "manchester-bods-retention-1.0"
    policy_version: Literal["bods-private-retention-v1"] = "bods-private-retention-v1"
    max_snapshot_age_hours: int = Field(default=BODS_RETENTION_DEFAULT_MAX_AGE_HOURS, ge=1, le=168)
    max_snapshot_count: int = Field(default=BODS_RETENTION_DEFAULT_MAX_SNAPSHOTS, ge=1, le=1_440)
    minimum_newest_snapshots_to_keep: int = Field(default=1, ge=1, le=24)
    explicit_operator_confirmation_required: Literal[True] = True
    delete_accepted_and_quarantine_together: Literal[True] = True
    protect_active_live_scene: Literal[True] = True
    publication_class: Literal["private"] = "private"
    raw_vehicle_identifiers_may_be_present: Literal[True] = True
    public_export_available: Literal[False] = False
    legal_retention_basis_approved: Literal[False] = False
    secure_erasure_guaranteed: Literal[False] = False

    @model_validator(mode="after")
    def validate_bounds(self) -> BodsRetentionPolicy:
        if self.minimum_newest_snapshots_to_keep > self.max_snapshot_count:
            raise ValueError("minimum keep count cannot exceed the snapshot-count bound")
        return self


class BodsRetentionSnapshotDecision(ManchesterSnapshotModel):
    """One verified private snapshot family and its proposed disposition."""

    snapshot_id: str = Field(pattern=r"^bods_siri_vm-\d{8}T\d{6}Z-[0-9a-f]{12}$")
    retrieval_started_at_utc: datetime
    raw_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    accepted_present: bool
    quarantine_present: Literal[True] = True
    private_bytes: int = Field(ge=1)
    disposition: Literal["keep", "delete"]
    reasons: tuple[
        Literal[
            "within_bounds",
            "age_limit_exceeded",
            "count_limit_exceeded",
            "newest_minimum",
            "active_live_scene",
        ],
        ...,
    ]

    @model_validator(mode="after")
    def validate_decision(self) -> BodsRetentionSnapshotDecision:
        if self.retrieval_started_at_utc.tzinfo is None:
            raise ValueError("retrieval time must be timezone-aware")
        if not self.reasons or tuple(sorted(set(self.reasons))) != self.reasons:
            raise ValueError("retention reasons must be sorted and unique")
        protected = {"newest_minimum", "active_live_scene"}.intersection(self.reasons)
        expired = {"age_limit_exceeded", "count_limit_exceeded"}.intersection(self.reasons)
        if self.disposition == "delete" and (protected or not expired):
            raise ValueError("only unprotected out-of-bound families may be deleted")
        if self.disposition == "keep" and expired and not protected:
            raise ValueError("an unprotected out-of-bound family cannot be kept")
        if "within_bounds" in self.reasons and (protected or expired):
            raise ValueError("within-bounds cannot be combined with another reason")
        return self


class BodsRetentionPlan(ManchesterSnapshotModel):
    """Deterministic preview; no deletion occurs while creating this model."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-05"] = "MAN-05"
    method_version: Literal["manchester-bods-retention-1.0"] = "manchester-bods-retention-1.0"
    source_id: Literal["bods_siri_vm"] = "bods_siri_vm"
    evaluated_at_utc: datetime
    policy: BodsRetentionPolicy
    active_live_snapshot_ids: tuple[str, ...]
    decisions: tuple[BodsRetentionSnapshotDecision, ...]
    snapshot_family_count: int = Field(ge=0)
    retained_family_count: int = Field(ge=0)
    deletion_candidate_count: int = Field(ge=0)
    private_bytes_total: int = Field(ge=0)
    deletion_candidate_bytes: int = Field(ge=0)
    count_limit_satisfied_after_apply: bool
    destructive_action_performed: Literal[False] = False
    automatic_deletion_available: Literal[False] = False
    legal_retention_basis_approved: Literal[False] = False
    secure_erasure_guaranteed: Literal[False] = False

    @model_validator(mode="after")
    def validate_plan(self) -> BodsRetentionPlan:
        if self.evaluated_at_utc.tzinfo is None or self.evaluated_at_utc.utcoffset() != timedelta(
            0
        ):
            raise ValueError("evaluation time must be UTC")
        ids = tuple(item.snapshot_id for item in self.decisions)
        if ids != tuple(sorted(ids)) or len(set(ids)) != len(ids):
            raise ValueError("retention decisions must have sorted unique snapshot ids")
        active = tuple(sorted(set(self.active_live_snapshot_ids)))
        if self.active_live_snapshot_ids != active or not set(active).issubset(ids):
            raise ValueError("active snapshot ids must be sorted, unique, and inventoried")
        deleted = tuple(item for item in self.decisions if item.disposition == "delete")
        retained = tuple(item for item in self.decisions if item.disposition == "keep")
        if self.snapshot_family_count != len(self.decisions):
            raise ValueError("snapshot family count must match decisions")
        if self.retained_family_count != len(retained):
            raise ValueError("retained count must match decisions")
        if self.deletion_candidate_count != len(deleted):
            raise ValueError("deletion count must match decisions")
        if self.private_bytes_total != sum(item.private_bytes for item in self.decisions):
            raise ValueError("private byte total must match decisions")
        if self.deletion_candidate_bytes != sum(item.private_bytes for item in deleted):
            raise ValueError("candidate byte total must match decisions")
        expected_satisfied = len(retained) <= self.policy.max_snapshot_count
        if self.count_limit_satisfied_after_apply != expected_satisfied:
            raise ValueError("post-apply count status must follow retained decisions")
        return self

    def confirmation_text(self) -> str:
        """Return the exact acknowledgement required to apply this preview."""

        return f"{BODS_RETENTION_CONFIRMATION_PREFIX} {self.fingerprint()[:12]}"


class BodsRetentionReceipt(ManchesterSnapshotModel):
    """In-memory audit receipt for one explicitly applied deletion plan."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-05"] = "MAN-05"
    method_version: Literal["manchester-bods-retention-1.0"] = "manchester-bods-retention-1.0"
    plan: BodsRetentionPlan
    plan_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    completed_at_utc: datetime
    deleted_snapshot_ids: tuple[str, ...]
    deleted_family_count: int = Field(ge=0)
    deleted_private_bytes: int = Field(ge=0)
    accepted_directories_deleted: int = Field(ge=0)
    quarantine_directories_deleted: int = Field(ge=0)
    explicit_operator_confirmation_received: Literal[True] = True
    filesystem_deletion_completed: Literal[True] = True
    secure_erasure_guaranteed: Literal[False] = False
    public_export_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_receipt(self) -> BodsRetentionReceipt:
        if self.completed_at_utc.tzinfo is None or self.completed_at_utc.utcoffset() != timedelta(
            0
        ):
            raise ValueError("completion time must be UTC")
        if self.deleted_snapshot_ids != tuple(sorted(set(self.deleted_snapshot_ids))):
            raise ValueError("deleted snapshot ids must be sorted and unique")
        if self.plan_fingerprint != self.plan.fingerprint():
            raise ValueError("plan fingerprint must bind the embedded retention plan")
        expected = tuple(item for item in self.plan.decisions if item.disposition == "delete")
        if self.deleted_snapshot_ids != tuple(item.snapshot_id for item in expected):
            raise ValueError("deleted snapshot ids must match the embedded plan")
        if self.deleted_family_count != len(self.deleted_snapshot_ids):
            raise ValueError("deleted family count must match the snapshot ids")
        if self.deleted_private_bytes != sum(item.private_bytes for item in expected):
            raise ValueError("deleted private bytes must match the embedded plan")
        expected_accepted = sum(item.accepted_present for item in expected)
        if self.accepted_directories_deleted != expected_accepted:
            raise ValueError("accepted deletion count must match the embedded plan")
        if self.accepted_directories_deleted > self.deleted_family_count:
            raise ValueError("accepted deletion count cannot exceed family count")
        if self.quarantine_directories_deleted != self.deleted_family_count:
            raise ValueError("every deleted family must include its quarantine directory")
        return self


def preview_bods_retention(
    workspace_root: str | Path,
    policy: BodsRetentionPolicy | None = None,
    *,
    evaluated_at_utc: datetime | None = None,
) -> BodsRetentionPlan:
    """Verify and preview bounded retention without changing the filesystem."""

    workspace = _validated_workspace(workspace_root)
    selected_policy = BodsRetentionPolicy() if policy is None else policy
    evaluated = datetime.now(UTC) if evaluated_at_utc is None else evaluated_at_utc
    if evaluated.tzinfo is None or evaluated.utcoffset() != timedelta(0):
        raise BodsRetentionError("TIME_INVALID", "retention evaluation requires a UTC timestamp")

    inventory = _inventory_snapshot_families(workspace)
    active_ids = _active_live_snapshot_ids(workspace)
    missing_active = set(active_ids).difference(inventory)
    if missing_active:
        raise BodsRetentionError(
            "ACTIVE_SCENE_DANGLING",
            "the current live scene references a BODS snapshot outside the verified inventory",
        )

    ordered_newest = sorted(inventory.values(), key=lambda item: (item[0], item[1]), reverse=True)
    newest_ids = {
        snapshot_id
        for _retrieved, snapshot_id, _raw, _accepted, _bytes in ordered_newest[
            : selected_policy.minimum_newest_snapshots_to_keep
        ]
    }
    protected_ids = newest_ids.union(active_ids)
    cutoff = evaluated - timedelta(hours=selected_policy.max_snapshot_age_hours)
    age_ids = {
        snapshot_id
        for retrieved, snapshot_id, _raw, _accepted, _bytes in ordered_newest
        if retrieved < cutoff
    }
    overflow = max(0, len(ordered_newest) - selected_policy.max_snapshot_count)
    count_ids: set[str] = set()
    for _retrieved, snapshot_id, _raw, _accepted, _bytes in reversed(ordered_newest):
        if len(count_ids) >= overflow:
            break
        if snapshot_id not in protected_ids:
            count_ids.add(snapshot_id)

    decisions: list[BodsRetentionSnapshotDecision] = []
    for retrieved, snapshot_id, raw_fingerprint, accepted, private_bytes in inventory.values():
        reasons: set[str] = set()
        if snapshot_id in newest_ids:
            reasons.add("newest_minimum")
        if snapshot_id in active_ids:
            reasons.add("active_live_scene")
        if snapshot_id in age_ids:
            reasons.add("age_limit_exceeded")
        if snapshot_id in count_ids:
            reasons.add("count_limit_exceeded")
        protected = bool({"newest_minimum", "active_live_scene"}.intersection(reasons))
        expired = bool({"age_limit_exceeded", "count_limit_exceeded"}.intersection(reasons))
        disposition: Literal["keep", "delete"] = "delete" if expired and not protected else "keep"
        if not reasons:
            reasons.add("within_bounds")
        decisions.append(
            BodsRetentionSnapshotDecision(
                snapshot_id=snapshot_id,
                retrieval_started_at_utc=retrieved,
                raw_fingerprint=raw_fingerprint,
                accepted_present=accepted,
                private_bytes=private_bytes,
                disposition=disposition,
                reasons=tuple(sorted(reasons)),  # type: ignore[arg-type]
            )
        )
    decisions.sort(key=lambda item: item.snapshot_id)
    deleted = tuple(item for item in decisions if item.disposition == "delete")
    retained = tuple(item for item in decisions if item.disposition == "keep")
    return BodsRetentionPlan(
        evaluated_at_utc=evaluated,
        policy=selected_policy,
        active_live_snapshot_ids=active_ids,
        decisions=tuple(decisions),
        snapshot_family_count=len(decisions),
        retained_family_count=len(retained),
        deletion_candidate_count=len(deleted),
        private_bytes_total=sum(item.private_bytes for item in decisions),
        deletion_candidate_bytes=sum(item.private_bytes for item in deleted),
        count_limit_satisfied_after_apply=len(retained) <= selected_policy.max_snapshot_count,
    )


def apply_bods_retention(
    workspace_root: str | Path,
    plan: BodsRetentionPlan,
    *,
    confirmation: str,
    utc_now: Callable[[], datetime] | None = None,
) -> BodsRetentionReceipt:
    """Apply an unchanged preview after exact, explicit operator confirmation."""

    workspace = _validated_workspace(workspace_root)
    if confirmation != plan.confirmation_text():
        raise BodsRetentionError(
            "CONFIRMATION_REQUIRED", "the exact preview-bound confirmation text is required"
        )
    current = preview_bods_retention(
        workspace,
        plan.policy,
        evaluated_at_utc=plan.evaluated_at_utc,
    )
    if current != plan:
        raise BodsRetentionError(
            "PLAN_DRIFT", "the verified snapshot inventory changed; create and review a new preview"
        )
    candidates = tuple(item for item in plan.decisions if item.disposition == "delete")
    completed = datetime.now(UTC) if utc_now is None else utc_now()
    if completed.tzinfo is None or completed.utcoffset() != timedelta(0):
        raise BodsRetentionError("TIME_INVALID", "retention completion requires a UTC timestamp")
    accepted_deleted = 0
    quarantine_deleted = 0
    for item in candidates:
        accepted = workspace / ACCEPTED_DIRECTORY_NAME / item.snapshot_id
        quarantine = workspace / QUARANTINE_DIRECTORY_NAME / item.snapshot_id
        if accepted.exists():
            _delete_verified_directory(accepted, workspace / ACCEPTED_DIRECTORY_NAME)
            accepted_deleted += 1
        _delete_verified_directory(quarantine, workspace / QUARANTINE_DIRECTORY_NAME)
        quarantine_deleted += 1
    return BodsRetentionReceipt(
        plan=plan,
        plan_fingerprint=plan.fingerprint(),
        completed_at_utc=completed,
        deleted_snapshot_ids=tuple(item.snapshot_id for item in candidates),
        deleted_family_count=len(candidates),
        deleted_private_bytes=sum(item.private_bytes for item in candidates),
        accepted_directories_deleted=accepted_deleted,
        quarantine_directories_deleted=quarantine_deleted,
    )


def _inventory_snapshot_families(
    workspace: Path,
) -> dict[str, tuple[datetime, str, str, bool, int]]:
    accepted_root = _safe_area(workspace, ACCEPTED_DIRECTORY_NAME)
    quarantine_root = _safe_area(workspace, QUARANTINE_DIRECTORY_NAME)
    accepted = _source_directories(accepted_root)
    quarantined = _source_directories(quarantine_root)
    inventory: dict[str, tuple[datetime, str, str, bool, int]] = {}
    for snapshot_id in sorted(set(accepted).union(quarantined)):
        quarantine_dir = quarantined.get(snapshot_id)
        if quarantine_dir is None:
            raise BodsRetentionError(
                "SNAPSHOT_FAMILY_INCOMPLETE",
                "an accepted BODS snapshot has no matching verified quarantine family",
            )
        try:
            verify_manchester_quarantine(quarantine_dir)
            quarantine_manifest = ManchesterQuarantineManifest.model_validate_json(
                _read_bounded(quarantine_dir / QUARANTINE_MANIFEST_FILE_NAME)
            )
        except (ManchesterSnapshotError, ValueError) as exc:
            raise BodsRetentionError(
                "QUARANTINE_INVALID", "a BODS quarantine family failed verification"
            ) from exc
        if quarantine_manifest.source.source_id != BODS_SOURCE_ID:
            raise BodsRetentionError("SOURCE_MISMATCH", "a BODS-named family has another source id")
        accepted_dir = accepted.get(snapshot_id)
        if accepted_dir is not None:
            try:
                verify_manchester_snapshot(accepted_dir)
                accepted_manifest = ManchesterSnapshotManifest.model_validate_json(
                    _read_bounded(accepted_dir / MANIFEST_FILE_NAME)
                )
            except (ManchesterSnapshotError, ValueError) as exc:
                raise BodsRetentionError(
                    "ACCEPTED_SNAPSHOT_INVALID", "an accepted BODS family failed verification"
                ) from exc
            if (
                accepted_manifest.source.source_id != BODS_SOURCE_ID
                or accepted_manifest.raw_fingerprint != quarantine_manifest.raw_fingerprint
                or accepted_manifest.retrieval != quarantine_manifest.retrieval
            ):
                raise BodsRetentionError(
                    "SNAPSHOT_FAMILY_MISMATCH",
                    "accepted and quarantine BODS artifacts do not describe one snapshot family",
                )
        private_bytes = _tree_bytes(quarantine_dir)
        if accepted_dir is not None:
            private_bytes += _tree_bytes(accepted_dir)
        inventory[snapshot_id] = (
            quarantine_manifest.retrieval.started_at_utc,
            snapshot_id,
            quarantine_manifest.raw_fingerprint,
            accepted_dir is not None,
            private_bytes,
        )
    return inventory


def _active_live_snapshot_ids(workspace: Path) -> tuple[str, ...]:
    target = workspace / "manchester" / "scenes" / "live_vehicles.json"
    if not target.exists():
        return ()
    if (
        target.is_symlink()
        or not target.is_file()
        or target.stat().st_size > BODS_RETENTION_MAX_SCENE_BYTES
    ):
        raise BodsRetentionError(
            "ACTIVE_SCENE_INVALID", "the local live scene is missing or unsafe"
        )
    try:
        scene = ManchesterMapScene.model_validate_json(target.read_bytes())
    except ValueError as exc:
        raise BodsRetentionError("ACTIVE_SCENE_INVALID", "the local live scene is invalid") from exc
    if scene.mode != "live_vehicles":
        raise BodsRetentionError("ACTIVE_SCENE_INVALID", "the local live scene has the wrong mode")
    return tuple(
        sorted(
            {
                layer.request.snapshot_id
                for layer in scene.layers
                if layer.request.source == BODS_SOURCE_ID and layer.request.snapshot_id is not None
            }
        )
    )


def _source_directories(root: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    if not root.exists():
        return found
    for child in root.iterdir():
        if not child.name.startswith(f"{BODS_SOURCE_ID}-"):
            continue
        if child.is_symlink() or not child.is_dir():
            raise BodsRetentionError("SNAPSHOT_PATH_UNSAFE", "a BODS snapshot path is unsafe")
        found[child.name] = child
    return found


def _safe_area(workspace: Path, name: str) -> Path:
    area = workspace / name
    if area.parent.resolve(strict=True) != workspace.resolve(strict=True):
        raise BodsRetentionError("WORKSPACE_INVALID", "a required snapshot area is unsafe")
    if area.exists() and (area.is_symlink() or not area.is_dir()):
        raise BodsRetentionError("WORKSPACE_INVALID", "a required snapshot area is unsafe")
    return area


def _tree_bytes(root: Path) -> int:
    total = 0
    for directory, names, files in os.walk(root, followlinks=False):
        base = Path(directory)
        if base.is_symlink():
            raise BodsRetentionError(
                "SNAPSHOT_PATH_UNSAFE", "snapshot trees cannot contain symlinks"
            )
        for name in (*names, *files):
            path = base / name
            if path.is_symlink():
                raise BodsRetentionError(
                    "SNAPSHOT_PATH_UNSAFE", "snapshot trees cannot contain symlinks"
                )
        total += sum((base / name).stat().st_size for name in files)
    return total


def _delete_verified_directory(target: Path, expected_parent: Path) -> None:
    if (
        target.is_symlink()
        or not target.is_dir()
        or target.parent.resolve(strict=True) != expected_parent.resolve(strict=True)
        or not target.name.startswith(f"{BODS_SOURCE_ID}-")
    ):
        raise BodsRetentionError("DELETE_TARGET_UNSAFE", "a retention deletion target is unsafe")

    def make_writable_and_retry(function: Callable[..., object], path: str, _info: object) -> None:
        os.chmod(path, 0o700)
        function(path)

    try:
        # ``onerror`` is supported throughout the project's Python 3.11+
        # range. Python 3.12's newer ``onexc`` spelling is not available on
        # the still-supported 3.11 CI runner.
        shutil.rmtree(target, onerror=make_writable_and_retry)
    except OSError as exc:
        raise BodsRetentionError(
            "DELETE_FAILED", "a verified private snapshot directory could not be deleted"
        ) from exc


def _read_bounded(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_MANIFEST_FILE_BYTES:
        raise BodsRetentionError("MANIFEST_INVALID", "a snapshot manifest is missing or unsafe")
    return path.read_bytes()


def _validated_workspace(workspace_root: str | Path) -> Path:
    workspace = Path(workspace_root)
    try:
        inspect_v07_workspace(workspace)
    except V07WorkspaceError as exc:
        raise BodsRetentionError(
            "WORKSPACE_INVALID", "configure a valid isolated v0.7 workspace first"
        ) from exc
    return workspace.resolve(strict=True)

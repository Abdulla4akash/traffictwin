"""Offline tests for explicit private BODS snapshot retention controls."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from tests.unit.test_manchester_bods_acquisition import (
    API_KEY,
    BOX,
    POLICY,
    make_transport,
    siri_xml,
    vehicle_activity,
)
from traffictwin.integration.manchester.bods_acquisition import (
    BodsAcquisitionRequest,
    acquire_bods_snapshot,
)
from traffictwin.integration.manchester.bods_live import refresh_bods_live_scene
from traffictwin.integration.manchester.bods_retention import (
    BodsRetentionError,
    BodsRetentionPlan,
    BodsRetentionPolicy,
    apply_bods_retention,
    preview_bods_retention,
)
from traffictwin.release.compatibility import initialise_v07_workspace


def _clock(start: datetime) -> Callable[[], datetime]:
    values = iter(start + timedelta(seconds=offset) for offset in range(20))
    return lambda: next(values)


def _acquire(
    workspace: Path,
    started_at: datetime,
    vehicle_ref: str,
    *,
    publish_scene: bool = False,
) -> str:
    calls: list[tuple[str, str, dict[str, str]]] = []
    payload = siri_xml([vehicle_activity(vehicle_ref)])
    with httpx.Client(transport=make_transport(payload, calls)) as client:
        if publish_scene:
            live_result = refresh_bods_live_scene(
                workspace,
                BOX,
                api_key=API_KEY,
                synthetic=True,
                http_client=client,
                utc_now=_clock(started_at),
            )
            snapshot_id = live_result.summary.snapshot_id
        else:
            acquisition_result = acquire_bods_snapshot(
                workspace,
                BodsAcquisitionRequest(
                    bounding_box=BOX,
                    policy=POLICY,
                    synthetic=True,
                ),
                api_key=API_KEY,
                http_client=client,
                utc_now=_clock(started_at),
            )
            snapshot_id = acquisition_result.snapshot_id
    assert len(calls) == 1
    return snapshot_id


def _workspace_with_three_families(tmp_path: Path) -> tuple[Path, tuple[str, str, str]]:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    oldest = _acquire(workspace, datetime(2026, 7, 21, 8, tzinfo=UTC), "OLD-VEHICLE")
    newest = _acquire(workspace, datetime(2026, 7, 23, 12, tzinfo=UTC), "NEW-VEHICLE")
    active = _acquire(
        workspace,
        datetime(2026, 7, 22, 12, tzinfo=UTC),
        "ACTIVE-VEHICLE",
        publish_scene=True,
    )
    return workspace, (oldest, active, newest)


def test_preview_is_read_only_and_protects_newest_and_active_scene(tmp_path: Path) -> None:
    workspace, (oldest, active, newest) = _workspace_with_three_families(tmp_path)
    before = sorted(path.relative_to(workspace) for path in workspace.rglob("*"))

    plan = preview_bods_retention(
        workspace,
        BodsRetentionPolicy(max_snapshot_age_hours=24, max_snapshot_count=2),
        evaluated_at_utc=datetime(2026, 7, 24, 12, tzinfo=UTC),
    )

    assert sorted(path.relative_to(workspace) for path in workspace.rglob("*")) == before
    assert plan.snapshot_family_count == 3
    assert plan.deletion_candidate_count == 1
    assert plan.active_live_snapshot_ids == (active,)
    by_id = {item.snapshot_id: item for item in plan.decisions}
    assert by_id[oldest].disposition == "delete"
    assert "age_limit_exceeded" in by_id[oldest].reasons
    assert by_id[active].disposition == "keep"
    assert "active_live_scene" in by_id[active].reasons
    assert by_id[newest].disposition == "keep"
    assert "newest_minimum" in by_id[newest].reasons
    assert plan.count_limit_satisfied_after_apply is True
    assert plan.destructive_action_performed is False
    assert plan.automatic_deletion_available is False
    assert plan.legal_retention_basis_approved is False


def test_apply_requires_exact_confirmation_and_deletes_complete_family(tmp_path: Path) -> None:
    workspace, (oldest, active, newest) = _workspace_with_three_families(tmp_path)
    plan = preview_bods_retention(
        workspace,
        BodsRetentionPolicy(max_snapshot_age_hours=24, max_snapshot_count=2),
        evaluated_at_utc=datetime(2026, 7, 24, 12, tzinfo=UTC),
    )

    with pytest.raises(BodsRetentionError) as excinfo:
        apply_bods_retention(workspace, plan, confirmation="yes")
    assert excinfo.value.code == "CONFIRMATION_REQUIRED"
    assert (workspace / "accepted" / oldest).is_dir()

    receipt = apply_bods_retention(
        workspace,
        plan,
        confirmation=plan.confirmation_text(),
        utc_now=lambda: datetime(2026, 7, 24, 12, 1, tzinfo=UTC),
    )

    assert receipt.deleted_snapshot_ids == (oldest,)
    assert receipt.plan == plan
    assert receipt.deleted_family_count == 1
    assert receipt.accepted_directories_deleted == 1
    assert receipt.quarantine_directories_deleted == 1
    assert not (workspace / "accepted" / oldest).exists()
    assert not (workspace / "quarantine" / oldest).exists()
    for retained in (active, newest):
        assert (workspace / "accepted" / retained).is_dir()
        assert (workspace / "quarantine" / retained).is_dir()
    post = preview_bods_retention(
        workspace,
        plan.policy,
        evaluated_at_utc=plan.evaluated_at_utc,
    )
    assert post.deletion_candidate_count == 0


def test_apply_refuses_inventory_drift(tmp_path: Path) -> None:
    workspace, _ids = _workspace_with_three_families(tmp_path)
    plan = preview_bods_retention(
        workspace,
        BodsRetentionPolicy(max_snapshot_age_hours=24, max_snapshot_count=2),
        evaluated_at_utc=datetime(2026, 7, 24, 12, tzinfo=UTC),
    )
    _acquire(workspace, datetime(2026, 7, 23, 13, tzinfo=UTC), "DRIFT-VEHICLE")

    with pytest.raises(BodsRetentionError) as excinfo:
        apply_bods_retention(
            workspace,
            plan,
            confirmation=plan.confirmation_text(),
        )
    assert excinfo.value.code == "PLAN_DRIFT"


def test_empty_workspace_preview_is_valid(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    plan = preview_bods_retention(
        workspace,
        evaluated_at_utc=datetime(2026, 7, 24, 12, tzinfo=UTC),
    )
    assert plan.snapshot_family_count == 0
    assert plan.deletion_candidate_count == 0
    assert plan.private_bytes_total == 0


def test_preview_fails_closed_on_symlinked_bods_family(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    outside = tmp_path / "outside"
    outside.mkdir()
    attack = workspace / "quarantine" / "bods_siri_vm-20260722T100000Z-aaaaaaaaaaaa"
    attack.symlink_to(outside, target_is_directory=True)

    with pytest.raises(BodsRetentionError) as excinfo:
        preview_bods_retention(
            workspace,
            evaluated_at_utc=datetime(2026, 7, 24, 12, tzinfo=UTC),
        )
    assert excinfo.value.code == "SNAPSHOT_PATH_UNSAFE"
    assert outside.is_dir()


def test_plan_reload_rejects_mutated_counts(tmp_path: Path) -> None:
    workspace, _ids = _workspace_with_three_families(tmp_path)
    plan = preview_bods_retention(
        workspace,
        BodsRetentionPolicy(max_snapshot_age_hours=24, max_snapshot_count=2),
        evaluated_at_utc=datetime(2026, 7, 24, 12, tzinfo=UTC),
    )
    payload = plan.model_dump(mode="json")
    payload["deletion_candidate_count"] = 0
    with pytest.raises(ValidationError):
        BodsRetentionPlan.model_validate(payload)

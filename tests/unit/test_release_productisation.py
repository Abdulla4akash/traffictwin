from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.tos_helpers import write_tos_package
from traffictwin.demo.workspace import initialise_workspace
from traffictwin.integration.tos.readiness import (
    ReadinessStatus,
    build_tos_integration_readiness,
)
from traffictwin.integration.tos.supervisor import (
    build_tos_supervisor_pack_zip,
    stage_public_tos_atlas,
    write_tos_supervisor_pack,
)
from traffictwin.release.deployment import stage_synthetic_demo_site

FIXED_NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


def test_tos_readiness_keeps_missing_evidence_and_permissions_explicit(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")

    report = build_tos_integration_readiness(package, clock=lambda: FIXED_NOW)

    assert report.capabilities["summary_import"] is ReadinessStatus.READY
    assert report.capabilities["canonical_conversion"] is ReadinessStatus.BLOCKED
    assert report.capabilities["direct_launch"] is ReadinessStatus.BLOCKED
    assert report.capabilities["public_tos_atlas"] is ReadinessStatus.UNKNOWN
    permission = next(gate for gate in report.gates if gate.gate_id == "G10_PUBLICATION_PERMISSION")
    assert permission.status is ReadinessStatus.UNKNOWN
    assert "/Users/" not in report.to_json()


def test_explicit_permission_only_opens_the_permission_gate(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")

    report = build_tos_integration_readiness(
        package,
        publication_permission=True,
        fixture_permission=True,
        clock=lambda: FIXED_NOW,
    )

    assert report.capabilities["public_tos_atlas"] is ReadinessStatus.READY
    assert report.capabilities["canonical_conversion"] is ReadinessStatus.BLOCKED
    assert report.capabilities["direct_launch"] is ReadinessStatus.BLOCKED


def test_supervisor_pack_is_checksummed_private_and_deterministic(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    first = write_tos_supervisor_pack(
        package,
        tmp_path / "first",
        variation_campaign="capscalar_mappo",
        clock=lambda: FIXED_NOW,
    )
    second = write_tos_supervisor_pack(
        package,
        tmp_path / "second",
        variation_campaign="capscalar_mappo",
        clock=lambda: FIXED_NOW,
    )

    first_manifest = json.loads(first.manifest.read_text(encoding="utf-8"))
    second_manifest = json.loads(second.manifest.read_text(encoding="utf-8"))
    assert first_manifest == second_manifest
    assert first_manifest["classification"] == "private_research_material"
    assert first_manifest["publication_permission_required"] is True
    assert "direct_launch" in first_manifest["blocked_capabilities"]
    for line in first.checksums.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", maxsplit=1)
        assert hashlib.sha256((first.directory / relative).read_bytes()).hexdigest() == digest

    first_zip = build_tos_supervisor_pack_zip(
        package,
        variation_campaign="capscalar_mappo",
        clock=lambda: FIXED_NOW,
    )
    second_zip = build_tos_supervisor_pack_zip(
        package,
        variation_campaign="capscalar_mappo",
        clock=lambda: FIXED_NOW,
    )
    assert first_zip == second_zip


def test_public_tos_atlas_requires_explicit_permission(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    with pytest.raises(PermissionError, match="confirm-publication-permission"):
        stage_public_tos_atlas(package, tmp_path / "public")

    index = stage_public_tos_atlas(
        package,
        tmp_path / "confirmed",
        publication_permission_confirmed=True,
        clock=lambda: FIXED_NOW,
    )
    assert index.name == "index.html"
    html = index.read_text(encoding="utf-8").lower()
    assert "research-use notice" in html
    assert "public sharing requires confirmation" in html


def test_static_demo_site_contains_only_precomputed_synthetic_outputs(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    initialise_workspace(workspace)

    first = stage_synthetic_demo_site(workspace, tmp_path / "site-a")
    second = stage_synthetic_demo_site(workspace, tmp_path / "site-b")

    assert first == second
    assert first.synthetic is True
    assert first.live_data is False
    assert first.external_integration is False
    assert len(first.scenarios) == 6
    html = (tmp_path / "site-a/index.html").read_text(encoding="utf-8")
    assert "Synthetic-only demonstration" in html
    assert "task.completion.rate" in html
    assert "/Users/" not in html
    assert "NaN" not in html
    assert "Infinity" not in html


def test_static_site_overwrite_requires_a_valid_marker(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    initialise_workspace(workspace)
    unsafe = tmp_path / "unsafe"
    unsafe.mkdir()
    (unsafe / "keep.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(PermissionError, match="unmarked"):
        stage_synthetic_demo_site(workspace, unsafe, overwrite=True)
    assert (unsafe / "keep.txt").read_text(encoding="utf-8") == "keep"

    safe = tmp_path / "safe"
    stage_synthetic_demo_site(workspace, safe)
    stage_synthetic_demo_site(workspace, safe, overwrite=True)
    assert (safe / "site-manifest.json").exists()

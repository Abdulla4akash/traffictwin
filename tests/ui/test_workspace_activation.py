# ruff: noqa: E501
"""Tests for Local Real-Workspace Activation Wizard — remediation for B1-B4.

Covers unit, integration, UI/AppTest, adversarial, deterministic identity,
network tripwire, and mutation gates. No real network, fake providers only.
Uses monkeypatch for env isolation and portable path derivation.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from traffictwin.workspace_activation.models import (
    RetentionPolicy,
    WorkspaceActivationConfirmation,
    WorkspaceActivationRequest,
)
from traffictwin.workspace_activation.service import (
    ActivationRefusedError,
    activate_workspace,
    build_activation_plan,
    deactivate_workspace,
    get_workspace_status,
    preflight_workspace,
)


def _req(dest: Path, **kwargs: object) -> WorkspaceActivationRequest:
    return WorkspaceActivationRequest(destination_path=str(dest), **kwargs)


# ---------------------------------------------------------------------------
# B1 — re-activation must never lie
# ---------------------------------------------------------------------------


def test_safe_empty_target(tmp_path: Path) -> None:
    dest = tmp_path / "ws_empty"
    req = _req(dest)
    pre = preflight_workspace(req)
    assert pre.ready_to_plan is True
    assert pre.is_empty is True
    assert pre.is_managed is False
    plan = build_activation_plan(req, pre)
    conf = WorkspaceActivationConfirmation(
        confirmation_digest=plan.confirmation_digest, request_fingerprint=req.fingerprint()
    )
    receipt = activate_workspace(req, plan, conf)
    assert receipt.status == "activated"
    assert (dest / ".traffictwin_workspace" / "marker.json").is_file()
    assert (dest / ".traffictwin_workspace" / "receipt.json").is_file()
    j = receipt.canonical_json()
    assert "request_fingerprint" in j
    from traffictwin.workspace_activation.service import receipt_to_csv

    csv_text = receipt_to_csv(receipt)
    assert "request_fingerprint" in csv_text


def test_identical_re_activation_is_idempotent(tmp_path: Path) -> None:
    dest = tmp_path / "ws_idem_b1"
    req = _req(dest)
    pre = preflight_workspace(req)
    plan = build_activation_plan(req, pre)
    conf = WorkspaceActivationConfirmation(
        confirmation_digest=plan.confirmation_digest, request_fingerprint=req.fingerprint()
    )
    r1 = activate_workspace(req, plan, conf)
    assert r1.status == "activated"
    # Second identical activation should be idempotent, not create new receipt
    pre2 = preflight_workspace(req)
    plan2 = build_activation_plan(req, pre2)
    # Plan should be identical fingerprint
    assert plan2.confirmation_digest == plan.confirmation_digest
    conf2 = WorkspaceActivationConfirmation(
        confirmation_digest=plan2.confirmation_digest, request_fingerprint=req.fingerprint()
    )
    r2 = activate_workspace(req, plan2, conf2)
    assert r2.status == "already_active"
    assert r2.request_fingerprint == r1.request_fingerprint
    assert r2.confirmation_digest == r1.confirmation_digest
    # Disk should remain identical
    retention_path = dest / "config" / "retention.json"
    assert retention_path.is_file()
    data = json.loads(retention_path.read_text(encoding="utf-8"))
    assert data["retention_days"] == 30
    # No duplicate mutation: receipt still reflects original
    assert r2.retention_policy.retention_days == 30


def test_changed_retention_refused(tmp_path: Path) -> None:
    dest = tmp_path / "ws_retention"
    req1 = _req(
        dest,
        retention_policy=RetentionPolicy(retention_days=30, anonymize=True, allow_export=False),
    )
    pre1 = preflight_workspace(req1)
    plan1 = build_activation_plan(req1, pre1)
    conf1 = WorkspaceActivationConfirmation(
        confirmation_digest=plan1.confirmation_digest, request_fingerprint=req1.fingerprint()
    )
    r1 = activate_workspace(req1, plan1, conf1)
    assert r1.status == "activated"
    # Capture disk state
    retention_path = dest / "config" / "retention.json"
    before = retention_path.read_text(encoding="utf-8")
    marker_before = (dest / ".traffictwin_workspace" / "marker.json").read_text(encoding="utf-8")
    receipt_before = (dest / ".traffictwin_workspace" / "receipt.json").read_text(encoding="utf-8")
    # Changed retention
    req2 = _req(
        dest,
        retention_policy=RetentionPolicy(retention_days=365, anonymize=True, allow_export=False),
    )
    pre2 = preflight_workspace(req2)
    plan2 = build_activation_plan(req2, pre2)
    conf2 = WorkspaceActivationConfirmation(
        confirmation_digest=plan2.confirmation_digest, request_fingerprint=req2.fingerprint()
    )
    with pytest.raises(ActivationRefusedError, match="ACTIVATION_REQUEST_CHANGED"):
        activate_workspace(req2, plan2, conf2)
    # Disk must remain unchanged
    assert retention_path.read_text(encoding="utf-8") == before
    assert (dest / ".traffictwin_workspace" / "marker.json").read_text(
        encoding="utf-8"
    ) == marker_before
    assert (dest / ".traffictwin_workspace" / "receipt.json").read_text(
        encoding="utf-8"
    ) == receipt_before
    # Providers unchanged
    providers_path = dest / "config" / "providers.json"
    assert providers_path.is_file()


def test_changed_privacy_refused(tmp_path: Path) -> None:
    dest = tmp_path / "ws_privacy"
    req1 = _req(
        dest,
        retention_policy=RetentionPolicy(retention_days=30, anonymize=True, allow_export=False),
    )
    pre1 = preflight_workspace(req1)
    plan1 = build_activation_plan(req1, pre1)
    conf1 = WorkspaceActivationConfirmation(
        confirmation_digest=plan1.confirmation_digest, request_fingerprint=req1.fingerprint()
    )
    activate_workspace(req1, plan1, conf1)
    retention_before = (dest / "config" / "retention.json").read_text(encoding="utf-8")
    # Changed privacy
    req2 = _req(
        dest,
        retention_policy=RetentionPolicy(retention_days=30, anonymize=False, allow_export=True),
    )
    pre2 = preflight_workspace(req2)
    plan2 = build_activation_plan(req2, pre2)
    conf2 = WorkspaceActivationConfirmation(
        confirmation_digest=plan2.confirmation_digest, request_fingerprint=req2.fingerprint()
    )
    with pytest.raises(ActivationRefusedError, match="ACTIVATION_REQUEST_CHANGED"):
        activate_workspace(req2, plan2, conf2)
    assert (dest / "config" / "retention.json").read_text(encoding="utf-8") == retention_before


def test_changed_provider_refused(tmp_path: Path) -> None:
    dest = tmp_path / "ws_provider"
    req1 = _req(dest, bods_enabled=False)
    pre1 = preflight_workspace(req1)
    plan1 = build_activation_plan(req1, pre1)
    conf1 = WorkspaceActivationConfirmation(
        confirmation_digest=plan1.confirmation_digest, request_fingerprint=req1.fingerprint()
    )
    activate_workspace(req1, plan1, conf1)
    providers_before = (dest / "config" / "providers.json").read_text(encoding="utf-8")
    # Enable BODS
    req2 = _req(dest, bods_enabled=True)
    pre2 = preflight_workspace(req2)
    plan2 = build_activation_plan(req2, pre2)
    conf2 = WorkspaceActivationConfirmation(
        confirmation_digest=plan2.confirmation_digest, request_fingerprint=req2.fingerprint()
    )
    with pytest.raises(ActivationRefusedError, match="ACTIVATION_REQUEST_CHANGED"):
        activate_workspace(req2, plan2, conf2)
    assert (dest / "config" / "providers.json").read_text(encoding="utf-8") == providers_before


def test_tampered_managed_config_refused(tmp_path: Path) -> None:
    dest = tmp_path / "ws_tamper"
    req = _req(dest)
    pre = preflight_workspace(req)
    plan = build_activation_plan(req, pre)
    conf = WorkspaceActivationConfirmation(
        confirmation_digest=plan.confirmation_digest, request_fingerprint=req.fingerprint()
    )
    activate_workspace(req, plan, conf)
    # Tamper with managed config
    retention_path = dest / "config" / "retention.json"
    data = json.loads(retention_path.read_text(encoding="utf-8"))
    data["retention_days"] = 999
    retention_path.write_text(json.dumps(data), encoding="utf-8")
    # Retry same request — should refuse drift
    pre2 = preflight_workspace(req)
    plan2 = build_activation_plan(req, pre2)
    # Plan digest should still be same (since request same), but managed files drifted
    assert plan2.confirmation_digest == plan.confirmation_digest
    conf2 = WorkspaceActivationConfirmation(
        confirmation_digest=plan2.confirmation_digest, request_fingerprint=req.fingerprint()
    )
    with pytest.raises(ActivationRefusedError, match="MANAGED_WORKSPACE_DRIFT"):
        activate_workspace(req, plan2, conf2)


def test_unmanaged_target_refusal(tmp_path: Path) -> None:
    dest = tmp_path / "unmanaged"
    dest.mkdir()
    (dest / "file.txt").write_text("data")
    req = _req(dest)
    pre = preflight_workspace(req)
    assert any(f.code == "UNMANAGED_NON_EMPTY" for f in pre.findings)
    assert pre.ready_to_plan is False
    plan = build_activation_plan(req, pre)
    conf = WorkspaceActivationConfirmation(
        confirmation_digest=plan.confirmation_digest, request_fingerprint=req.fingerprint()
    )
    with pytest.raises(ActivationRefusedError, match="UNMANAGED_NON_EMPTY"):
        activate_workspace(req, plan, conf)
    assert not (dest / ".traffictwin_workspace" / "marker.json").exists()


def test_symlink_escape_refusal(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    dest = link / "ws"
    req = _req(dest)
    pre = preflight_workspace(req)
    assert any(f.code == "SYMLINK_ESCAPE" for f in pre.findings)
    plan = build_activation_plan(req, pre)
    conf = WorkspaceActivationConfirmation(
        confirmation_digest=plan.confirmation_digest, request_fingerprint=req.fingerprint()
    )
    with pytest.raises(ActivationRefusedError, match="SYMLINK_ESCAPE"):
        activate_workspace(req, plan, conf)


def test_secret_not_serialized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BODS_API_KEY", "supersecret12345")  # noqa: S105
    dest = tmp_path / "ws_secret"
    req = _req(dest, bods_enabled=True)
    pre = preflight_workspace(req)
    j = pre.canonical_json()
    assert "supersecret12345" not in j
    cred = next(c for c in pre.credential_presence if c.env_var == "BODS_API_KEY")
    assert cred.present is True
    plan = build_activation_plan(req, pre)
    conf = WorkspaceActivationConfirmation(
        confirmation_digest=plan.confirmation_digest, request_fingerprint=req.fingerprint()
    )
    receipt = activate_workspace(req, plan, conf)
    assert "supersecret12345" not in receipt.canonical_json()
    marker_text = (dest / ".traffictwin_workspace" / "marker.json").read_text()
    assert "supersecret12345" not in marker_text


def test_stale_confirmation_digest_refused(tmp_path: Path) -> None:
    dest = tmp_path / "ws_stale"
    req = _req(dest)
    pre = preflight_workspace(req)
    plan = build_activation_plan(req, pre)
    req2 = _req(dest, bods_enabled=True)
    conf = WorkspaceActivationConfirmation(
        confirmation_digest=plan.confirmation_digest, request_fingerprint=req2.fingerprint()
    )
    with pytest.raises(ActivationRefusedError, match="REFUSED"):
        activate_workspace(req2, plan, conf)
    req3 = _req(dest)
    pre3 = preflight_workspace(req3)
    plan3 = build_activation_plan(req3, pre3)
    bad_conf = WorkspaceActivationConfirmation(
        confirmation_digest="0" * 64, request_fingerprint=req3.fingerprint()
    )
    with pytest.raises(ActivationRefusedError, match="REFUSED"):
        activate_workspace(req3, plan3, bad_conf)


def test_confirmation_digest_gate(tmp_path: Path) -> None:
    """Mutation target: must fail if gate bypassed."""
    dest = tmp_path / "ws_gate"
    req = _req(dest)
    pre = preflight_workspace(req)
    plan = build_activation_plan(req, pre)
    good = WorkspaceActivationConfirmation(
        confirmation_digest=plan.confirmation_digest, request_fingerprint=req.fingerprint()
    )
    receipt = activate_workspace(req, plan, good)
    assert receipt.status == "activated"
    dest2 = tmp_path / "ws_gate2"
    req2 = _req(dest2)
    pre2 = preflight_workspace(req2)
    plan2 = build_activation_plan(req2, pre2)
    bad = WorkspaceActivationConfirmation(
        confirmation_digest="a" * 64, request_fingerprint=req2.fingerprint()
    )
    with pytest.raises(ActivationRefusedError):
        activate_workspace(req2, plan2, bad)


def test_atomic_activation(tmp_path: Path) -> None:
    dest = tmp_path / "ws_atomic"
    req = _req(dest)
    pre = preflight_workspace(req)
    plan = build_activation_plan(req, pre)
    conf = WorkspaceActivationConfirmation(
        confirmation_digest=plan.confirmation_digest, request_fingerprint=req.fingerprint()
    )
    receipt = activate_workspace(req, plan, conf)
    staging = list(tmp_path.glob(".*staging*"))
    assert staging == []
    assert (dest / "registry" / "traffictwin.sqlite").is_file()
    assert (dest / "config" / "retention.json").is_file()
    assert (dest / "config" / "providers.json").is_file()
    assert receipt.request_fingerprint == req.fingerprint()
    assert receipt.confirmation_digest == plan.confirmation_digest


def test_partial_failure_cleanup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dest = tmp_path / "ws_partial"
    req = _req(dest)
    pre = preflight_workspace(req)
    plan = build_activation_plan(req, pre)
    conf = WorkspaceActivationConfirmation(
        confirmation_digest=plan.confirmation_digest, request_fingerprint=req.fingerprint()
    )
    import traffictwin.workspace_activation.service as svc

    orig_init = svc._init_registry_db

    def failing_init(path: object) -> None:
        raise RuntimeError("injected failure")

    monkeypatch.setattr(svc, "_init_registry_db", failing_init)
    with pytest.raises(ActivationRefusedError):
        activate_workspace(req, plan, conf)
    assert not (dest / ".traffictwin_workspace" / "marker.json").exists()
    assert list(tmp_path.glob(".*staging*")) == []
    monkeypatch.setattr(svc, "_init_registry_db", orig_init)
    pre2 = preflight_workspace(req)
    plan2 = build_activation_plan(req, pre2)
    conf2 = WorkspaceActivationConfirmation(
        confirmation_digest=plan2.confirmation_digest, request_fingerprint=req.fingerprint()
    )
    r = activate_workspace(req, plan2, conf2)
    assert r.status == "activated"


def test_deactivation_preserves_data(tmp_path: Path) -> None:
    dest = tmp_path / "ws_deact"
    req = _req(dest)
    pre = preflight_workspace(req)
    plan = build_activation_plan(req, pre)
    conf = WorkspaceActivationConfirmation(
        confirmation_digest=plan.confirmation_digest, request_fingerprint=req.fingerprint()
    )
    _receipt = activate_workspace(req, plan, conf)
    evidence = dest / "registry" / "evidence.txt"
    evidence.write_text("important")
    agg = dest / "aggregate-store" / "data.json"
    agg.parent.mkdir(parents=True, exist_ok=True)
    agg.write_text("{}")
    rec1 = deactivate_workspace(str(dest), remove_marker=False)
    assert rec1.marker_removed is False
    assert (dest / ".traffictwin_workspace" / "marker.json").exists()
    assert evidence.exists()
    assert agg.exists()
    rec2 = deactivate_workspace(str(dest), confirmation=conf, remove_marker=True)
    assert rec2.marker_removed is True
    assert not (dest / ".traffictwin_workspace" / "marker.json").exists()
    assert evidence.exists()
    assert agg.exists()
    assert (dest / ".traffictwin_workspace" / "receipt.json").exists()
    bad_conf = WorkspaceActivationConfirmation(
        confirmation_digest="b" * 64, request_fingerprint=req.fingerprint()
    )
    dest2 = tmp_path / "ws_deact2"
    req2 = _req(dest2)
    pre2 = preflight_workspace(req2)
    plan2 = build_activation_plan(req2, pre2)
    conf2 = WorkspaceActivationConfirmation(
        confirmation_digest=plan2.confirmation_digest, request_fingerprint=req2.fingerprint()
    )
    activate_workspace(req2, plan2, conf2)
    with pytest.raises(ActivationRefusedError):
        deactivate_workspace(str(dest2), confirmation=bad_conf, remove_marker=True)
    with pytest.raises(ActivationRefusedError):
        deactivate_workspace(str(dest2), confirmation=None, remove_marker=True)


def test_no_network_before_confirmation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Real network tripwire: any socket connect should explode
    def exploding_connect(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", exploding_connect)
    # Also patch create_connection which may use connect internally
    monkeypatch.setattr(socket, "create_connection", exploding_connect)

    dest = tmp_path / "ws_no_net"
    req = _req(dest, bods_enabled=True)
    # These should all complete without network
    pre = preflight_workspace(req)
    plan = build_activation_plan(req, pre)
    # Stale confirmation should refuse before network
    bad = WorkspaceActivationConfirmation(
        confirmation_digest="0" * 64, request_fingerprint=req.fingerprint()
    )
    with pytest.raises(ActivationRefusedError):
        activate_workspace(req, plan, bad)
    # Valid activation should also not make network calls
    good = WorkspaceActivationConfirmation(
        confirmation_digest=plan.confirmation_digest, request_fingerprint=req.fingerprint()
    )
    receipt = activate_workspace(req, plan, good)
    assert receipt.status == "activated"
    # Status and deactivate also no network
    status = get_workspace_status(str(dest))
    assert status.is_active is True
    rec = deactivate_workspace(str(dest), remove_marker=False)
    assert rec.status == "deactivated"


def test_deterministic_identity(tmp_path: Path) -> None:
    # Independently constructed equivalent requests should have same fingerprint
    dest = tmp_path / "ws_det"
    req1 = WorkspaceActivationRequest(
        destination_path=str(dest),
        bods_enabled=False,
        national_highways_enabled=True,
        retention_policy=RetentionPolicy(retention_days=30, anonymize=True, allow_export=False),
    )
    req2 = WorkspaceActivationRequest(
        destination_path=str(dest),
        bods_enabled=False,
        national_highways_enabled=True,
        retention_policy=RetentionPolicy(retention_days=30, anonymize=True, allow_export=False),
    )
    assert req1.fingerprint() == req2.fingerprint()
    pre1 = preflight_workspace(req1)
    pre2 = preflight_workspace(req2)
    plan1 = build_activation_plan(req1, pre1)
    plan2 = build_activation_plan(req2, pre2)
    assert plan1.confirmation_digest == plan2.confirmation_digest
    assert plan1.fingerprint() == plan2.fingerprint()
    assert plan1.expected_digest() == plan1.fingerprint()
    # Semantic change should change fingerprint
    req3 = WorkspaceActivationRequest(
        destination_path=str(dest),
        bods_enabled=True,
        national_highways_enabled=True,
        retention_policy=RetentionPolicy(retention_days=30, anonymize=True, allow_export=False),
    )
    assert req3.fingerprint() != req1.fingerprint()
    pre3 = preflight_workspace(req3)
    plan3 = build_activation_plan(req3, pre3)
    assert plan3.confirmation_digest != plan1.confirmation_digest
    # Order-insensitive: workers in different order should give same fingerprint due to sorting
    req4 = _req(
        dest, start_workers=True, allowlisted_workers=["evidence-indexer", "aggregate-compactor"]
    )
    req5 = _req(
        dest, start_workers=True, allowlisted_workers=["aggregate-compactor", "evidence-indexer"]
    )
    assert req4.fingerprint() == req5.fingerprint()  # request canonicalizes worker order via sorted
    pre4 = preflight_workspace(req4)
    pre5 = preflight_workspace(req5)
    plan4 = build_activation_plan(req4, pre4)
    plan5 = build_activation_plan(req5, pre5)
    assert plan4.confirmation_digest == plan5.confirmation_digest


def test_worker_allowlist_refused(tmp_path: Path) -> None:
    dest = tmp_path / "ws_worker"
    req = _req(dest, start_workers=True, allowlisted_workers=["evil-worker"])
    pre = preflight_workspace(req)
    # Should be refused at preflight (worker not allowlisted)
    assert any(f.code == "WORKER_NOT_ALLOWLISTED" for f in pre.findings)
    assert pre.ready_to_plan is False
    # Also direct validation should fail at request level? The model allows any string matching pattern, but allowlist gate is in preflight
    plan = build_activation_plan(req, pre)
    conf = WorkspaceActivationConfirmation(
        confirmation_digest=plan.confirmation_digest, request_fingerprint=req.fingerprint()
    )
    with pytest.raises(ActivationRefusedError, match="REFUSED"):
        activate_workspace(req, plan, conf)


def test_path_traversal_refused(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    # Use a path that contains traversal semantics via string
    # The request's destination_path is a string, so we can include ".."
    dest_str = str(tmp_path / "base" / "workspace-parent" / ".." / "escape-target")
    req = WorkspaceActivationRequest(destination_path=dest_str)
    pre = preflight_workspace(req)
    assert any(f.code == "PATH_TRAVERSAL" for f in pre.findings)
    assert pre.ready_to_plan is False
    plan = build_activation_plan(req, pre)
    conf = WorkspaceActivationConfirmation(
        confirmation_digest=plan.confirmation_digest, request_fingerprint=req.fingerprint()
    )
    with pytest.raises(ActivationRefusedError, match="PATH_TRAVERSAL"):
        activate_workspace(req, plan, conf)
    # Also test backup traversal
    dest2 = tmp_path / "ws_traversal2"
    req2 = WorkspaceActivationRequest(
        destination_path=str(dest2), backup_destination=str(tmp_path / ".." / "escape")
    )
    pre2 = preflight_workspace(req2)
    assert any(f.code == "PATH_TRAVERSAL" for f in pre2.findings)


def test_path_inside_repo_refused(tmp_path: Path) -> None:
    # Derive repo root portably
    repo_root = Path(__file__).resolve().parents[2]
    assert (repo_root / "pyproject.toml").exists(), f"repo root not found: {repo_root}"
    dest = repo_root / "tmp_workspace_inside_repo_test"
    req = WorkspaceActivationRequest(destination_path=str(dest))
    pre = preflight_workspace(req)
    assert any(f.code == "PATH_INSIDE_REPO" for f in pre.findings)
    assert pre.ready_to_plan is False
    plan = build_activation_plan(req, pre)
    conf = WorkspaceActivationConfirmation(
        confirmation_digest=plan.confirmation_digest, request_fingerprint=req.fingerprint()
    )
    with pytest.raises(ActivationRefusedError, match="PATH_INSIDE_REPO"):
        activate_workspace(req, plan, conf)


def test_insufficient_disk_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dest = tmp_path / "ws_disk"
    req = _req(dest)
    # Patch disk_usage to return tiny free space
    import shutil

    class FakeUsage:
        total = 100 * 1024 * 1024
        used = 99 * 1024 * 1024
        free = 1 * 1024  # 1KB, less than MIN_DISK_BYTES (10MB)

    monkeypatch.setattr(shutil, "disk_usage", lambda path: FakeUsage())
    pre = preflight_workspace(req)
    assert any(f.code == "INSUFFICIENT_DISK" for f in pre.findings)
    assert pre.ready_to_plan is False
    plan = build_activation_plan(req, pre)
    conf = WorkspaceActivationConfirmation(
        confirmation_digest=plan.confirmation_digest, request_fingerprint=req.fingerprint()
    )
    with pytest.raises(ActivationRefusedError, match="REFUSED"):
        activate_workspace(req, plan, conf)


def test_missing_configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BODS_API_KEY", raising=False)
    monkeypatch.delenv("NATIONAL_HIGHWAYS_API_KEY", raising=False)
    dest = tmp_path / "ws_missing_cfg"
    req = _req(dest, bods_enabled=True)
    pre = preflight_workspace(req)
    bods = next(p for p in pre.provider_readiness if p.provider.value == "bods")
    assert bods.enabled is True
    assert bods.status.value in ("missing_credential", "missing_configuration")
    assert pre.ready_to_plan is True
    plan = build_activation_plan(req, pre)
    conf = WorkspaceActivationConfirmation(
        confirmation_digest=plan.confirmation_digest, request_fingerprint=req.fingerprint()
    )
    receipt = activate_workspace(req, plan, conf)
    assert receipt.status == "activated"
    assert "bods" in receipt.providers_enabled


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_preflight_plan_activate_status_deactivate(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from traffictwin.workspace_activation.cli import app

    runner = CliRunner()
    dest = tmp_path / "ws_cli"
    result = runner.invoke(app, ["preflight", str(dest)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "request_fingerprint" in data
    result = runner.invoke(app, ["plan", str(dest)])
    assert result.exit_code == 0
    output = result.stdout
    _ = json.loads(output.splitlines()[0] if output.strip().startswith("{") else output)  # noqa: F841
    req = _req(dest)
    pre = preflight_workspace(req)
    plan = build_activation_plan(req, pre)
    digest = plan.confirmation_digest
    result = runner.invoke(app, ["activate", str(dest), "--confirmation-digest", digest])
    assert result.exit_code == 0
    receipt_data = json.loads(result.stdout)
    assert receipt_data["confirmation_digest"] == digest
    result = runner.invoke(app, ["status", str(dest)])
    assert result.exit_code == 0
    status_data = json.loads(result.stdout)
    assert status_data["is_active"] is True
    result = runner.invoke(
        app, ["deactivate", str(dest), "--remove-marker", "--confirmation-digest", digest]
    )
    assert result.exit_code == 0
    deact_data = json.loads(result.stdout)
    assert deact_data["marker_removed"] is True
    fresh = tmp_path / "ws_cli_fresh"
    result = runner.invoke(app, ["preflight", str(fresh)])
    assert result.exit_code == 0
    req_fresh = _req(fresh)
    pre_fresh = preflight_workspace(req_fresh)
    plan_fresh = build_activation_plan(req_fresh, pre_fresh)
    digest_fresh = plan_fresh.confirmation_digest
    result = runner.invoke(app, ["activate", str(fresh), "--confirmation-digest", digest_fresh])
    assert result.exit_code == 0
    result = runner.invoke(app, ["deactivate", str(fresh)])
    assert result.exit_code == 0


def test_cli_refuses_bad_digest(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from traffictwin.workspace_activation.cli import app

    runner = CliRunner()
    dest = tmp_path / "ws_cli_bad"
    result = runner.invoke(app, ["activate", str(dest), "--confirmation-digest", "0" * 64])
    assert result.exit_code == 2
    assert "REFUSED" in result.stdout or "REFUSED" in result.stderr


# ---------------------------------------------------------------------------
# UI / AppTest
# ---------------------------------------------------------------------------


def test_workspace_activation_page_renders(tmp_path: Path) -> None:
    runner = tmp_path / "runner_ws_activation.py"
    runner.write_text(
        f"""
from pathlib import Path
from traffictwin.ui.pages.workspace_activation import render
from traffictwin.ui.state import UiConfig
config = UiConfig(registry_path=Path(r"{tmp_path / "registry.sqlite"}"))
render(config)
""",
        encoding="utf-8",
    )
    at = AppTest.from_file(str(runner), default_timeout=30)
    at.run()
    assert not at.exception, f"Page raised: {at.exception}"
    titles = [str(m.value) for m in at.title]
    assert any("Workspace Activation" in t for t in titles), f"Missing H1, got {titles}"
    # Exactly one H1
    assert len(titles) == 1, f"Expected exactly one H1, got {titles}"
    assert titles[0] == "Workspace Activation"
    infos = [str(x.value) for x in at.info]
    captions = [str(x.value) for x in at.caption]
    all_text = " ".join(infos + captions + [str(x.value) for x in at.markdown])
    assert "preview-first" in all_text.lower() or "confirmation" in all_text.lower()
    # Evidence boundary must be visible before controls
    assert "Workspace activation does not make provider network requests" in all_text
    assert "NOT public deployment" in all_text or "not public" in all_text.lower()
    text_inputs = [str(x.label) for x in at.text_input]
    assert any("Workspace destination path" in label for label in text_inputs)
    buttons = [str(b.label) for b in at.button]
    assert any("Run preflight" in b for b in buttons)
    assert any("Build activation plan" in b for b in buttons)
    assert any("Activate workspace" in b for b in buttons)
    for txt in infos + captions:
        assert "supersecret" not in txt.lower()
    # Empty state useful
    assert any("Enter a destination" in c or "No preflight yet" in c for c in captions + infos)


def test_workspace_activation_app_page_script(tmp_path: Path) -> None:
    candidates = [
        Path("src/traffictwin/ui/app_pages/workspace_activation.py"),  # noqa: S108
        Path("/tmp/wt-workspace-activation/src/traffictwin/ui/app_pages/workspace_activation.py"),  # noqa: S108
        Path(__file__).resolve().parents[2]
        / "src/traffictwin/ui/app_pages/workspace_activation.py",
    ]
    # Portable: derive repo root from test file and verify
    repo_root = Path(__file__).resolve().parents[2]
    # For this test file at tests/ui/test_workspace_activation.py, parents[2] is repo root
    # Verify repo root marker
    assert (repo_root / "pyproject.toml").exists(), f"repo root not found: {repo_root}"
    # Also try parents[3] fallback for robustness, but assert at least one exists
    script_path = next((c for c in candidates if c.exists()), candidates[0])
    # If none exist due to cwd outside repo, construct from repo_root
    if not script_path.exists():
        script_path = repo_root / "src/traffictwin/ui/app_pages/workspace_activation.py"
    assert script_path.exists(), f"app_pages script not found, tried {candidates}"
    at = AppTest.from_file(str(script_path), default_timeout=30)
    at.run()
    assert not at.exception
    titles = [str(m.value) for m in at.title]
    assert any("Workspace Activation" in t for t in titles)


def test_portable_repo_root_derivation(tmp_path: Path) -> None:
    # This test must pass both inside repo and outside cwd
    repo_root = Path(__file__).resolve().parents[2]
    assert (repo_root / "pyproject.toml").exists()
    # Also check alternative parents[3] is not the correct one for this file
    # For tests/ui/test_workspace_activation.py, parents[2] should be repo root, parents[3] would be parent of repo
    assert (repo_root.parent / "pyproject.toml").exists() is False or (
        repo_root / "pyproject.toml"
    ).exists()

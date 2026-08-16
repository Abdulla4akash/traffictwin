"""Fail-closed availability gates for the three Guided Demo modes."""

from __future__ import annotations

from pathlib import Path

import httpx

from tests.unit.test_manchester_bods_acquisition import (
    API_KEY,
    BOX,
    BOX_VALUE,
    make_clock,
    make_transport,
    siri_xml,
)
from tests.unit.test_manchester_webtris_acquisition import acquire, make_request
from traffictwin.demo.workspace import initialise_workspace
from traffictwin.integration.manchester.bods_live_control import (
    coordinated_bods_live_refresh,
)
from traffictwin.release.compatibility import initialise_v07_workspace
from traffictwin.release.durable_workspace import (
    create_durable_v07_workspace,
    preview_durable_v07_workspace,
)
from traffictwin.ui.guided_demo_modes import (
    assess_historical_demo,
    assess_live_bus_demo,
    assess_synthetic_demo,
)

_CONFIGURED_ENV = {
    "BODS_API_KEY": "gate-test-secret",
    "TRAFFICTWIN_BODS_BOUNDING_BOX": BOX_VALUE,
}


def _durable_workspace(tmp_path: Path) -> Path:
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    workspace = parent / "workspace-v0.7"
    preview = preview_durable_v07_workspace(workspace)
    create_durable_v07_workspace(
        workspace,
        expected_plan_fingerprint=preview.confirmation_fingerprint(),
    )
    return workspace


def _synthetic_bods_snapshot(workspace: Path) -> None:
    with httpx.Client(transport=make_transport(siri_xml(), [])) as client:
        coordinated_bods_live_refresh(
            workspace,
            BOX,
            api_key=API_KEY,
            synthetic=True,
            http_client=client,
            utc_now=make_clock(),
        )


class TestTheSyntheticGate:
    def test_no_workspace_is_unavailable(self, tmp_path: Path) -> None:
        assessment = assess_synthetic_demo(workspace=None, registry=tmp_path / "registry.sqlite")
        assert assessment.status == "unavailable"
        assert assessment.reason == "workspace_unconfigured"

    def test_an_initialised_demo_workspace_is_ready(self, tmp_path: Path) -> None:
        workspace = tmp_path / "demo"
        initialise_workspace(workspace)
        assessment = assess_synthetic_demo(
            workspace=workspace, registry=workspace / "registry.sqlite"
        )
        assert assessment.status == "ready"
        assert assessment.baseline_bundle is not None
        assert assessment.variation_bundle is not None
        assert (assessment.baseline_bundle / "manifest.yaml").is_file()
        assert (assessment.variation_bundle / "manifest.yaml").is_file()

    def test_a_missing_preset_pair_is_refused(self, tmp_path: Path) -> None:
        workspace = tmp_path / "demo"
        initialise_workspace(workspace)
        (workspace / "bundles" / "stressed_demand" / "manifest.yaml").unlink()
        assessment = assess_synthetic_demo(
            workspace=workspace, registry=workspace / "registry.sqlite"
        )
        assert assessment.status == "unavailable"
        assert assessment.reason == "bundles_missing"


class TestTheLiveBusGate:
    def test_no_workspace_is_unavailable(self) -> None:
        assessment = assess_live_bus_demo(None, environment=_CONFIGURED_ENV)
        assert assessment.status == "unavailable"
        assert assessment.reason == "workspace_unconfigured"

    def test_a_plain_directory_is_refused(self, tmp_path: Path) -> None:
        assessment = assess_live_bus_demo(tmp_path, environment=_CONFIGURED_ENV)
        assert assessment.status == "unavailable"
        assert assessment.reason == "workspace_invalid"

    def test_a_non_durable_workspace_is_refused(self, tmp_path: Path) -> None:
        workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
        assessment = assess_live_bus_demo(workspace, environment=_CONFIGURED_ENV)
        assert assessment.status == "unavailable"
        assert assessment.reason == "workspace_not_durable"

    def test_a_missing_credential_is_refused(self, tmp_path: Path) -> None:
        workspace = _durable_workspace(tmp_path)
        assessment = assess_live_bus_demo(
            workspace, environment={"TRAFFICTWIN_BODS_BOUNDING_BOX": BOX_VALUE}
        )
        assert assessment.status == "unavailable"
        assert assessment.reason == "credential_missing"

    def test_a_missing_request_scope_is_refused(self, tmp_path: Path) -> None:
        workspace = _durable_workspace(tmp_path)
        assessment = assess_live_bus_demo(
            workspace, environment={"BODS_API_KEY": "gate-test-secret"}
        )
        assert assessment.status == "unavailable"
        assert assessment.reason == "scope_missing"

    def test_an_invalid_request_scope_is_refused(self, tmp_path: Path) -> None:
        workspace = _durable_workspace(tmp_path)
        assessment = assess_live_bus_demo(
            workspace,
            environment={
                "BODS_API_KEY": "gate-test-secret",
                "TRAFFICTWIN_BODS_BOUNDING_BOX": "not-a-box",
            },
        )
        assert assessment.status == "unavailable"
        assert assessment.reason == "configuration_invalid"

    def test_configured_without_accepted_evidence_is_refused(self, tmp_path: Path) -> None:
        workspace = _durable_workspace(tmp_path)
        assessment = assess_live_bus_demo(workspace, environment=_CONFIGURED_ENV)
        assert assessment.status == "unavailable"
        assert assessment.reason == "no_accepted_evidence"

    def test_a_synthetic_snapshot_is_refused_not_substituted(self, tmp_path: Path) -> None:
        workspace = _durable_workspace(tmp_path)
        _synthetic_bods_snapshot(workspace)
        assessment = assess_live_bus_demo(workspace, environment=_CONFIGURED_ENV)
        assert assessment.status == "unavailable"
        assert assessment.reason == "synthetic_evidence_refused"
        assert assessment.scene is None

    def test_no_message_leaks_secret_or_coordinates(self, tmp_path: Path) -> None:
        workspace = _durable_workspace(tmp_path)
        for environment in (
            _CONFIGURED_ENV,
            {"TRAFFICTWIN_BODS_BOUNDING_BOX": BOX_VALUE},
            {"BODS_API_KEY": "gate-test-secret"},
        ):
            assessment = assess_live_bus_demo(workspace, environment=environment)
            assert "gate-test-secret" not in assessment.message
            assert BOX_VALUE not in assessment.message
            assert str(workspace) not in assessment.message


class TestTheHistoricalGate:
    def test_no_workspace_is_unavailable(self) -> None:
        assessment = assess_historical_demo(None)
        assert assessment.status == "unavailable"
        assert assessment.reason == "workspace_unconfigured"
        assert "No accepted historical evidence" in assessment.message

    def test_an_empty_workspace_has_no_accepted_evidence(self, tmp_path: Path) -> None:
        workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
        assessment = assess_historical_demo(workspace)
        assert assessment.status == "unavailable"
        assert assessment.reason == "no_accepted_daily_reports"

    def test_synthetic_flagged_evidence_is_refused_not_substituted(self, tmp_path: Path) -> None:
        workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
        acquire(workspace, make_request())
        assessment = assess_historical_demo(workspace)
        assert assessment.status == "unavailable"
        assert assessment.reason == "synthetic_only_evidence"
        assert assessment.timeseries is None

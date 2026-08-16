"""Display-safe availability assessments for the three Guided Demo modes.

Each assessment composes existing evidence and configuration contracts and
fails closed. No assessment performs a network request, mutates evidence,
launches a research workload, or substitutes one evidence class for another:
an unavailable mode stays visibly unavailable. Messages never contain
credential values, request-scope coordinates, or private paths.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from traffictwin.demo.workspace import workspace_status
from traffictwin.integration.manchester.bods_auto_refresh import (
    BodsAutoRefreshError,
    configured_bods_auto_refresh_seconds,
    configured_bods_bounding_box,
)
from traffictwin.integration.manchester.bods_live import BodsLiveRefreshSummary
from traffictwin.integration.manchester.bods_live_control import (
    BodsLiveControlError,
    load_bods_live_control_state,
)
from traffictwin.integration.manchester.map_layers import ManchesterMapScene
from traffictwin.integration.manchester.webtris_acquisition import (
    WebtrisAcceptedSnapshotSummary,
)
from traffictwin.integration.manchester.webtris_timeseries import WebtrisTimeseriesResult
from traffictwin.release.compatibility import V07WorkspaceError, inspect_v07_workspace
from traffictwin.release.durable_workspace import (
    V07DurableWorkspaceError,
    load_durable_workspace_receipt,
)
from traffictwin.ui.manchester_operations import (
    accepted_webtris_daily_options,
    load_local_manchester_scene,
    load_local_webtris_catalogue,
    load_local_webtris_timeseries,
)

SYNTHETIC_DEMO_BASELINE_SCENARIO = "baseline"
SYNTHETIC_DEMO_VARIATION_SCENARIO = "stressed_demand"

SyntheticDemoReason = Literal[
    "ready",
    "workspace_unconfigured",
    "workspace_invalid",
    "bundles_missing",
]
LiveBusDemoReason = Literal[
    "ready",
    "workspace_unconfigured",
    "workspace_invalid",
    "workspace_not_durable",
    "configuration_invalid",
    "credential_missing",
    "scope_missing",
    "control_state_invalid",
    "no_accepted_evidence",
    "synthetic_evidence_refused",
    "scene_unavailable",
]
HistoricalDemoReason = Literal[
    "ready",
    "workspace_unconfigured",
    "no_accepted_daily_reports",
    "synthetic_only_evidence",
    "accepted_evidence_rejected",
    "replay_failed",
]


@dataclass(frozen=True, slots=True)
class SyntheticDemoAssessment:
    """Fail-closed readiness of the deterministic synthetic demo pair."""

    status: Literal["ready", "unavailable"]
    reason: SyntheticDemoReason
    message: str
    workspace: Path | None = None
    registry: Path | None = None
    baseline_bundle: Path | None = None
    variation_bundle: Path | None = None


@dataclass(frozen=True, slots=True)
class LiveBusDemoAssessment:
    """Fail-closed readiness of the latest accepted BODS bus-position evidence."""

    status: Literal["ready", "unavailable"]
    reason: LiveBusDemoReason
    message: str
    summary: BodsLiveRefreshSummary | None = None
    scene: ManchesterMapScene | None = None
    scope_configured: bool = False
    auto_refresh_interval_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class HistoricalDemoAssessment:
    """Fail-closed readiness of accepted local historical WebTRIS evidence."""

    status: Literal["ready", "unavailable"]
    reason: HistoricalDemoReason
    message: str
    snapshot: WebtrisAcceptedSnapshotSummary | None = None
    timeseries: WebtrisTimeseriesResult | None = None


def assess_synthetic_demo(*, workspace: Path | None, registry: Path) -> SyntheticDemoAssessment:
    """Check the demo workspace holds the deterministic preset pair.

    ``workspace``/``registry`` come from ``resolve_effective_demo_paths`` so the
    page resolves paths exactly once per render.
    """

    if workspace is None:
        return SyntheticDemoAssessment(
            status="unavailable",
            reason="workspace_unconfigured",
            message=(
                "No standalone demo workspace is configured for this app "
                "process. Create the deterministic demo workspace to run the "
                "synthetic demo."
            ),
        )
    if not workspace_status(workspace).valid_workspace:
        return SyntheticDemoAssessment(
            status="unavailable",
            reason="workspace_invalid",
            message="The configured demo workspace failed its validity check.",
        )
    baseline = workspace / "bundles" / SYNTHETIC_DEMO_BASELINE_SCENARIO
    variation = workspace / "bundles" / SYNTHETIC_DEMO_VARIATION_SCENARIO
    missing = [
        name
        for name, path in (
            (SYNTHETIC_DEMO_BASELINE_SCENARIO, baseline),
            (SYNTHETIC_DEMO_VARIATION_SCENARIO, variation),
        )
        if not (path / "manifest.yaml").is_file()
    ]
    if missing:
        return SyntheticDemoAssessment(
            status="unavailable",
            reason="bundles_missing",
            message=(
                "The demo workspace does not contain the deterministic preset "
                f"pair ({', '.join(missing)} absent). Re-initialise the demo "
                "workspace to restore it."
            ),
            workspace=workspace,
            registry=registry,
        )
    return SyntheticDemoAssessment(
        status="ready",
        reason="ready",
        message="Deterministic synthetic preset pair available.",
        workspace=workspace,
        registry=registry,
        baseline_bundle=baseline,
        variation_bundle=variation,
    )


def _credential_present(environment: Mapping[str, str]) -> bool:
    value = environment.get("BODS_API_KEY")
    return value is not None and bool(value.strip())


def assess_live_bus_demo(
    workspace_path: str | Path | None,
    *,
    environment: Mapping[str, str],
) -> LiveBusDemoAssessment:
    """Check the existing BODS contracts and the latest accepted evidence.

    This composes the same public contracts the release preflight uses —
    workspace inspection, durable receipt reconciliation, credential
    presence, declared request scope, control state, and the
    integrity-checked local scene — without inventing a second BODS
    configuration mechanism.
    """

    if workspace_path is None:
        return LiveBusDemoAssessment(
            status="unavailable",
            reason="workspace_unconfigured",
            message="BODS is not currently configured for this workspace.",
        )
    workspace = Path(workspace_path)
    try:
        inspection = inspect_v07_workspace(workspace)
    except V07WorkspaceError:
        return LiveBusDemoAssessment(
            status="unavailable",
            reason="workspace_invalid",
            message="The configured workspace is not a valid isolated v0.7 workspace.",
        )
    try:
        receipt = load_durable_workspace_receipt(workspace)
    except V07DurableWorkspaceError:
        return LiveBusDemoAssessment(
            status="unavailable",
            reason="workspace_not_durable",
            message="The configured workspace has no verified durable workspace receipt.",
        )
    if receipt.manifest_sha256 != inspection.manifest_sha256:
        return LiveBusDemoAssessment(
            status="unavailable",
            reason="workspace_not_durable",
            message="The durable workspace receipt no longer matches the workspace manifest.",
        )
    try:
        interval = configured_bods_auto_refresh_seconds(environment)
        box = configured_bods_bounding_box(environment)
    except BodsAutoRefreshError:
        return LiveBusDemoAssessment(
            status="unavailable",
            reason="configuration_invalid",
            message="The BODS refresh configuration for this app process is invalid.",
        )
    if not _credential_present(environment):
        return LiveBusDemoAssessment(
            status="unavailable",
            reason="credential_missing",
            message="BODS is not currently configured for this workspace.",
            scope_configured=box is not None,
            auto_refresh_interval_seconds=interval,
        )
    if box is None:
        return LiveBusDemoAssessment(
            status="unavailable",
            reason="scope_missing",
            message=(
                "No BODS request scope is declared for this app process, so "
                "the live bus demo stays unavailable."
            ),
            auto_refresh_interval_seconds=interval,
        )
    try:
        control_state = load_bods_live_control_state(workspace)
    except BodsLiveControlError:
        return LiveBusDemoAssessment(
            status="unavailable",
            reason="control_state_invalid",
            message="The local BODS control state failed its integrity contract.",
            scope_configured=True,
            auto_refresh_interval_seconds=interval,
        )
    summary = control_state.latest_success
    if summary is None:
        return LiveBusDemoAssessment(
            status="unavailable",
            reason="no_accepted_evidence",
            message=(
                "BODS is configured, but no accepted BODS bus-position "
                "snapshot exists in this workspace yet."
            ),
            scope_configured=True,
            auto_refresh_interval_seconds=interval,
        )
    if summary.synthetic_records > 0:
        return LiveBusDemoAssessment(
            status="unavailable",
            reason="synthetic_evidence_refused",
            message=(
                "The latest accepted snapshot contains synthetic records; the "
                "live bus demo shows only genuine BODS evidence."
            ),
            scope_configured=True,
            auto_refresh_interval_seconds=interval,
        )
    loaded = load_local_manchester_scene(workspace, "live_vehicles")
    if loaded.status != "available" or loaded.scene is None:
        return LiveBusDemoAssessment(
            status="unavailable",
            reason="scene_unavailable",
            message=loaded.message,
            summary=summary,
            scope_configured=True,
            auto_refresh_interval_seconds=interval,
        )
    return LiveBusDemoAssessment(
        status="ready",
        reason="ready",
        message="Latest accepted BODS bus-position evidence is ready.",
        summary=summary,
        scene=loaded.scene,
        scope_configured=True,
        auto_refresh_interval_seconds=interval,
    )


def assess_historical_demo(
    workspace_path: str | Path | None,
) -> HistoricalDemoAssessment:
    """Check for accepted, non-synthetic local WebTRIS daily-report evidence.

    Synthetic-flagged accepted snapshots are refused: the historical demo
    never presents synthetic evidence as historical observation.
    """

    catalogue = load_local_webtris_catalogue(workspace_path)
    if catalogue.status == "rejected":
        return HistoricalDemoAssessment(
            status="unavailable",
            reason="accepted_evidence_rejected",
            message=catalogue.message,
        )
    if catalogue.status == "unavailable" or catalogue.catalogue is None:
        reason: HistoricalDemoReason = (
            "workspace_unconfigured"
            if catalogue.reason == "workspace_unconfigured"
            else "no_accepted_daily_reports"
        )
        return HistoricalDemoAssessment(
            status="unavailable",
            reason=reason,
            message="No accepted historical evidence is currently available.",
        )
    options = accepted_webtris_daily_options(catalogue.catalogue)
    source_options = tuple(item for item in options if not item.synthetic)
    if not source_options:
        return HistoricalDemoAssessment(
            status="unavailable",
            reason="synthetic_only_evidence" if options else "no_accepted_daily_reports",
            message=(
                "No accepted historical evidence is currently available. "
                "Synthetic-flagged snapshots are never presented as "
                "historical observation."
            ),
        )
    newest = source_options[0]
    loaded = load_local_webtris_timeseries(
        workspace_path, newest.snapshot_id, ("observed", "missing")
    )
    if loaded.status != "available" or loaded.result is None:
        return HistoricalDemoAssessment(
            status="unavailable",
            reason="replay_failed",
            message=loaded.message,
            snapshot=newest,
        )
    if loaded.result.synthetic:
        return HistoricalDemoAssessment(
            status="unavailable",
            reason="synthetic_only_evidence",
            message=(
                "The rebuilt result carries a synthetic flag, so it is "
                "refused as historical evidence."
            ),
            snapshot=newest,
        )
    return HistoricalDemoAssessment(
        status="ready",
        reason="ready",
        message="Accepted historical WebTRIS evidence rebuilt from immutable local evidence.",
        snapshot=newest,
        timeseries=loaded.result,
    )

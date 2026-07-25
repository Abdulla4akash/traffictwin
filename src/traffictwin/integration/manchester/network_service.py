"""Thin read-only service over accepted baseline-network candidates.

This is the boundary a later Manchester Operations page reads through.  It is
deliberately read-only and offline:

*   it never fetches anything over the network;
*   it never runs ``netconvert`` or any other subprocess;
*   it never computes a scientific result;
*   it reports availability and honest status, including the reasons a real
    Manchester baseline is still unavailable.

A UI page calls these functions and renders their output.  Acquisition and
building stay in the CLI, where an operator authorises them explicitly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field

from traffictwin.integration.manchester.map_matching import (
    ManchesterMapMatchingPreflight,
    current_map_matching_preflight,
)
from traffictwin.integration.manchester.models import ManchesterSnapshotModel
from traffictwin.integration.manchester.network_build import (
    SUPPORTED_SUMO_VERSION_PREFIX,
    ManchesterBaselineNetworkBinding,
    NetworkBuildError,
    discover_netconvert,
    load_binding,
    netconvert_identity,
)
from traffictwin.integration.manchester.network_scope import (
    BaselineScopeDecision,
    baseline_scope_decision,
)

NETWORK_SERVICE_SCHEMA_VERSION: Literal["1.0"] = "1.0"
NETWORK_SERVICE_METHOD_VERSION: Literal["manchester-baseline-network-service-1.0"] = (
    "manchester-baseline-network-service-1.0"
)

#: Networks live beside the other Manchester workspace areas.  The directory is
#: created on demand by the CLI and is not part of the strict REL-01 required
#: layout, so adding it cannot invalidate an existing v0.7 workspace.
NETWORKS_DIRECTORY_NAME: Literal["networks"] = "networks"

MAX_LISTED_NETWORKS = 200


class NetworkServiceModel(ManchesterSnapshotModel):
    """Strict frozen base for read-only service views."""


class ToolchainAvailability(NetworkServiceModel):
    """Whether the reviewed build toolchain is present, without running a build."""

    schema_version: Literal["1.0"] = "1.0"
    available: bool
    reported_version: str | None = Field(default=None, max_length=64)
    required_version_prefix: Literal["1.27."] = SUPPORTED_SUMO_VERSION_PREFIX
    blocker: str | None = Field(default=None, max_length=96)


class NetworkCandidateSummary(NetworkServiceModel):
    """One accepted candidate, summarised without exposing any private path."""

    schema_version: Literal["1.0"] = "1.0"
    network_id: str
    network_identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    network_bytes: int = Field(ge=0)
    validation_status: Literal["accepted", "rejected"]
    edge_count: int = Field(ge=0)
    junction_count: int = Field(ge=0)
    connection_count: int = Field(ge=0)
    traffic_light_count: int = Field(ge=0)
    proj_parameter: str
    baseline_scope: str
    sub_area_filter_scope: str
    licence_id: str
    attribution_text: str
    required_areas_covered: bool
    byte_reproducible: Literal[False] = False
    semantically_reproducible: Literal[True] = True
    calibration_performed: Literal[False] = False
    accepted_for_real_matching: Literal[False] = False


class BaselineNetworkStatus(NetworkServiceModel):
    """Complete honest status for the baseline-network foundation."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    method_version: Literal["manchester-baseline-network-service-1.0"] = (
        NETWORK_SERVICE_METHOD_VERSION
    )
    decision_record: Literal["ADR-059"] = "ADR-059"
    capability_status: Literal["planned"] = "planned"
    practical_state: Literal["foundation_only"] = "foundation_only"
    gate: Literal["Gate-D step 1 (network binding) only"] = "Gate-D step 1 (network binding) only"
    scope: BaselineScopeDecision
    toolchain: ToolchainAvailability
    candidates: tuple[NetworkCandidateSummary, ...]
    candidate_count: int = Field(ge=0)
    map_matching_preflight: ManchesterMapMatchingPreflight
    #: What this foundation still cannot do, kept visible rather than implied.
    unavailable_reasons: tuple[str, ...]
    calibration_available: Literal[False] = False
    comparison_available: Literal[False] = False
    live_traffic_available: Literal[False] = False
    performs_network_access: Literal[False] = False
    performs_subprocess_execution: Literal[False] = False


def toolchain_availability() -> ToolchainAvailability:
    """Report toolchain presence without building anything."""

    if discover_netconvert() is None:
        return ToolchainAvailability(available=False, blocker="SUMO_TOOLCHAIN_UNAVAILABLE")
    try:
        identity = netconvert_identity()
    except NetworkBuildError as exc:
        return ToolchainAvailability(available=False, blocker=exc.code)
    return ToolchainAvailability(available=True, reported_version=identity.reported_version)


def _summarise(binding: ManchesterBaselineNetworkBinding) -> NetworkCandidateSummary:
    return NetworkCandidateSummary(
        network_id=binding.network_id,
        network_identity_sha256=binding.network_identity_sha256,
        network_bytes=binding.network_bytes,
        validation_status=binding.validation.status,
        edge_count=binding.validation.structure.edge_count,
        junction_count=binding.validation.structure.junction_count,
        connection_count=binding.validation.structure.connection_count,
        traffic_light_count=binding.validation.structure.traffic_light_count,
        proj_parameter=binding.validation.location.proj_parameter,
        baseline_scope=binding.baseline_scope,
        sub_area_filter_scope=binding.sub_area_filter_scope,
        licence_id=binding.licence_id,
        attribution_text=binding.attribution_text,
        required_areas_covered=all(
            area.inside_network_boundary for area in binding.validation.required_areas
        ),
    )


def list_network_candidates(
    networks_root: str | Path,
) -> tuple[NetworkCandidateSummary, ...]:
    """List accepted candidates from local storage, verifying each digest."""

    root = Path(networks_root)
    if root.is_symlink() or not root.is_dir():
        return ()
    summaries: list[NetworkCandidateSummary] = []
    for child in sorted(root.iterdir())[:MAX_LISTED_NETWORKS]:
        if child.is_symlink() or not child.is_dir() or child.name.startswith("."):
            continue
        try:
            binding = load_binding(child)
        except (NetworkBuildError, ValueError):
            # A candidate that no longer verifies is omitted rather than shown
            # as healthy; the CLI `verify` command reports the exact failure.
            continue
        summaries.append(_summarise(binding))
    return tuple(summaries)


def inspect_network_candidate(network_dir: str | Path) -> ManchesterBaselineNetworkBinding:
    """Reopen and fully re-verify one accepted candidate."""

    return load_binding(network_dir)


def baseline_network_status(networks_root: str | Path | None = None) -> BaselineNetworkStatus:
    """Return the complete honest status for the baseline-network foundation."""

    candidates = list_network_candidates(networks_root) if networks_root is not None else ()
    reasons = [
        "No approved real-source map-matching policy exists, so site-to-edge "
        "matching against this network remains unavailable.",
        "No calibration objective, bounds, or uncertainty treatment is approved, "
        "so no demand calibration is available.",
        "No ManchesterComparisonMetricContract is approved, so observed-versus-"
        "simulated goodness-of-fit remains unavailable.",
        "DfT calibration evidence covers Manchester local authority only; Greater "
        "Manchester locations without observations are uncovered, never zero.",
    ]
    if not candidates:
        reasons.insert(0, "No accepted baseline-network candidate exists in this workspace.")
    return BaselineNetworkStatus(
        scope=baseline_scope_decision(),
        toolchain=toolchain_availability(),
        candidates=candidates,
        candidate_count=len(candidates),
        map_matching_preflight=current_map_matching_preflight(),
        unavailable_reasons=tuple(reasons),
    )

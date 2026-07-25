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

import os
import tempfile
from pathlib import Path
from typing import Literal, NamedTuple, TypeAlias

from pydantic import Field, model_validator

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
from traffictwin.integration.manchester.network_connectivity import (
    ManchesterNetworkConnectivityReport,
)
from traffictwin.integration.manchester.network_decode import (
    SUPPORTED_OSMIUM_MAJOR,
    NetworkDecodeError,
    discover_osmium,
    osmium_identity,
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

#: Where the CLI persists a completed connectivity review, beside the binding.
#: The service **reads** this file and never computes a review: a review streams
#: the whole network and walks the graph, which an ordinary Streamlit rerun must
#: never trigger.
CONNECTIVITY_RECORD_NAME: Literal["connectivity.json"] = "connectivity.json"

#: Bound on a stored review, so a hostile or corrupt record cannot be read into
#: memory.  A real Greater Manchester review is well under a megabyte.
MAX_CONNECTIVITY_RECORD_BYTES = 8_000_000

ConnectivityRecordState: TypeAlias = Literal[
    "available",
    "absent",
    "stale",
    "unreadable",
    "refused_symlink",
    "refused_oversized",
]


class NetworkServiceModel(ManchesterSnapshotModel):
    """Strict frozen base for read-only service views."""


class ToolchainAvailability(NetworkServiceModel):
    """Whether the reviewed build toolchain is present, without running a build."""

    schema_version: Literal["1.0"] = "1.0"
    available: bool
    reported_version: str | None = Field(default=None, max_length=64)
    required_version_prefix: str = Field(min_length=1, max_length=16)
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
    semantic_reproducibility: str
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
    decoder: ToolchainAvailability
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
    """Report build-toolchain presence without building anything."""

    if discover_netconvert() is None:
        return ToolchainAvailability(
            available=False,
            required_version_prefix=SUPPORTED_SUMO_VERSION_PREFIX,
            blocker="SUMO_TOOLCHAIN_UNAVAILABLE",
        )
    try:
        identity = netconvert_identity()
    except NetworkBuildError as exc:
        return ToolchainAvailability(
            available=False,
            required_version_prefix=SUPPORTED_SUMO_VERSION_PREFIX,
            blocker=exc.code,
        )
    return ToolchainAvailability(
        available=True,
        reported_version=identity.reported_version,
        required_version_prefix=SUPPORTED_SUMO_VERSION_PREFIX,
    )


def decoder_availability() -> ToolchainAvailability:
    """Report decoder presence without decoding anything.

    A PBF extract cannot become a network without this, because netconvert
    1.27.1 reads OSM XML only.
    """

    if discover_osmium() is None:
        return ToolchainAvailability(
            available=False,
            required_version_prefix=SUPPORTED_OSMIUM_MAJOR,
            blocker="OSMIUM_TOOLCHAIN_UNAVAILABLE",
        )
    try:
        identity = osmium_identity()
    except NetworkDecodeError as exc:
        return ToolchainAvailability(
            available=False,
            required_version_prefix=SUPPORTED_OSMIUM_MAJOR,
            blocker=exc.code,
        )
    return ToolchainAvailability(
        available=True,
        reported_version=identity.reported_version,
        required_version_prefix=SUPPORTED_OSMIUM_MAJOR,
    )


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
        semantic_reproducibility=binding.semantic_reproducibility,
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


class ConnectivityReviewAvailability(NetworkServiceModel):
    """Whether a persisted connectivity review exists, and whether it still fits.

    A review is only meaningful for the network it was computed from, so the
    recorded identity is compared against the candidate's current identity.  A
    review whose identity no longer matches is reported ``stale`` rather than
    shown: it describes a different network.
    """

    schema_version: Literal["1.0"] = "1.0"
    network_id: str
    state: ConnectivityRecordState
    network_identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_identity_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    review_network_id: str | None = Field(default=None, max_length=64)
    reason: str | None = Field(default=None, max_length=300)
    review: ManchesterNetworkConnectivityReport | None = None
    #: Reading a stored review never recomputes one, and never runs a probe.
    performs_network_traversal: Literal[False] = False
    proves_universal_routability: Literal[False] = False

    @model_validator(mode="after")
    def validate_availability(self) -> ConnectivityReviewAvailability:
        if (self.review is not None) != (self.state == "available"):
            raise ValueError("a review is published only when the record is available")
        if self.review is not None and (
            self.review.network_identity_sha256 != self.network_identity_sha256
            or self.review.network_id != self.network_id
        ):
            # The binding is re-checked on the model itself, not only where the
            # record was read. Otherwise a caller could assemble an "available"
            # view whose embedded review describes a different network.
            raise ValueError(
                "an available review must name the same network id and identity "
                "as the candidate it is published against"
            )
        return self


class ConnectivityRecordRead(NamedTuple):
    """The outcome of reading one stored review, with failures kept distinct.

    Collapsing "no record yet" and "the record is corrupt" into one absent
    answer would report a damaged file as merely missing, and the operator
    would re-run a review instead of investigating a file that failed to
    parse.  Each failure therefore keeps its own state.
    """

    state: ConnectivityRecordState
    review: ManchesterNetworkConnectivityReport | None
    reason: str | None


def read_connectivity_record(network_dir: str | Path) -> ConnectivityRecordRead:
    """Read a persisted connectivity review, distinguishing every failure."""

    record = Path(network_dir) / CONNECTIVITY_RECORD_NAME
    if record.is_symlink():
        return ConnectivityRecordRead(
            "refused_symlink",
            None,
            "The stored review is a symlink, which is refused rather than followed.",
        )
    if not record.is_file():
        return ConnectivityRecordRead(
            "absent",
            None,
            "No connectivity review is stored for this candidate. Run "
            "`integration manchester network connectivity` to produce one.",
        )
    try:
        # The bound is enforced by the read itself rather than by a prior
        # stat(): a file that grows between the two calls would pass the check
        # and then be read in full. One byte past the bound is enough to know
        # the record is oversized without holding the oversized content.
        with record.open("rb") as handle:
            raw = handle.read(MAX_CONNECTIVITY_RECORD_BYTES + 1)
    except OSError:
        return ConnectivityRecordRead(
            "unreadable", None, "The stored review could not be read from disk."
        )
    if len(raw) > MAX_CONNECTIVITY_RECORD_BYTES:
        return ConnectivityRecordRead(
            "refused_oversized",
            None,
            "The stored review is larger than the reviewed bound admits and was not read.",
        )
    try:
        payload = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ConnectivityRecordRead(
            "unreadable", None, "The stored review is not valid UTF-8 and is not shown."
        )
    try:
        review = ManchesterNetworkConnectivityReport.model_validate_json(payload)
    except ValueError:
        return ConnectivityRecordRead(
            "unreadable",
            None,
            "The stored review did not parse as a connectivity report and is not shown.",
        )
    return ConnectivityRecordRead("available", review, None)


def write_connectivity_record(
    network_dir: str | Path, review: ManchesterNetworkConnectivityReport
) -> Path:
    """Persist one review atomically, so a partial record is never left behind."""

    target = Path(network_dir) / CONNECTIVITY_RECORD_NAME
    if target.is_symlink():
        raise NetworkBuildError(
            "CONNECTIVITY_RECORD_SYMLINK", "the connectivity record path is a symlink"
        )
    payload = review.canonical_json().encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.stem}-", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def connectivity_record_matches(
    review: ManchesterNetworkConnectivityReport,
    *,
    network_id: str,
    network_identity_sha256: str,
) -> bool:
    """Whether a stored review actually describes this candidate.

    Both the semantic identity **and** the network id must agree.  A matching
    digest under a different id is not the same artifact, and publishing it
    would attribute one network's connectivity to another.
    """

    return (
        review.network_identity_sha256 == network_identity_sha256
        and review.network_id == network_id
    )


def connectivity_review_availability(
    networks_root: str | Path,
) -> tuple[ConnectivityReviewAvailability, ...]:
    """Report, per candidate, whether a usable connectivity review is on disk."""

    root = Path(networks_root)
    if root.is_symlink() or not root.is_dir():
        return ()
    results: list[ConnectivityReviewAvailability] = []
    for child in sorted(root.iterdir())[:MAX_LISTED_NETWORKS]:
        if child.is_symlink() or not child.is_dir() or child.name.startswith("."):
            continue
        try:
            binding = load_binding(child)
        except (NetworkBuildError, ValueError):
            continue
        state, review, reason = read_connectivity_record(child)
        if review is not None and not connectivity_record_matches(
            review,
            network_id=binding.network_id,
            network_identity_sha256=binding.network_identity_sha256,
        ):
            state = "stale"
            reason = (
                "The stored review does not name the same network identity and id as "
                "this candidate, so it describes a different network and is not shown."
            )
        results.append(
            ConnectivityReviewAvailability(
                network_id=binding.network_id,
                state=state,
                network_identity_sha256=binding.network_identity_sha256,
                review_identity_sha256=(
                    review.network_identity_sha256 if review is not None else None
                ),
                review_network_id=review.network_id if review is not None else None,
                reason=reason,
                review=review if state == "available" else None,
            )
        )
    return tuple(results)


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
        decoder=decoder_availability(),
        candidates=candidates,
        candidate_count=len(candidates),
        map_matching_preflight=current_map_matching_preflight(),
        unavailable_reasons=tuple(reasons),
    )

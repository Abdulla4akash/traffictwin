"""Session-scoped bus identity over quarantined BODS snapshots (decision F0).

The accepted MAN-05 scene deliberately prevents cross-snapshot vehicle
linking: its pseudonyms bake each record's own timestamp into the token and
declare ``identity_scope: "snapshot_only"``. Bus-fleet experiments need to
follow one vehicle across the snapshots of a single attended observation
session, so this module implements the owner-approved remedy as a *layer over
the private quarantine*, leaving the accepted parser and its artifacts
untouched.

The privacy contract, enforced structurally rather than by promise:

- a session token is an HMAC of the raw vehicle reference under a random
  per-session salt that exists only in process memory — linkage is possible
  within one declared session and impossible across sessions;
- raw vehicle references never leave the extraction function, and published
  measurements are aggregates only;
- extraction refuses to parse a byte before the quarantine receipt and the
  member's SHA-256 verify, and refuses a synthetic/real mismatch.

Buses remain bus evidence throughout; nothing here can become a road-traffic
count.
"""

from __future__ import annotations

import gzip
import hashlib
import hmac
import json
import math
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal
from xml.etree.ElementTree import Element, ParseError, fromstring

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import (
    QUARANTINE_MANIFEST_FILE_NAME,
    RAW_DIRECTORY_NAME,
    ManchesterQuarantineManifest,
    ManchesterSnapshotModel,
)
from traffictwin.integration.manchester.snapshots import (
    QUARANTINE_DIRECTORY_NAME,
    verify_manchester_quarantine,
)

SESSION_IDENTITY_POLICY_ID: Literal["manchester-bods-session-identity-1.0"] = (
    "manchester-bods-session-identity-1.0"
)

_EARTH_RADIUS_M = 6_371_008.8
_MAX_MEMBER_BYTES = 16 * 1024 * 1024
_TOKEN_HEX_LENGTH = 24
_MINIMUM_SALT_BYTES = 16


class BodsSessionIdentityError(RuntimeError):
    """Raised when session extraction or measurement cannot proceed safely."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class SessionObservation(ManchesterSnapshotModel):
    """One position fix carrying a session-scoped pseudonym, never a raw ref."""

    policy_id: Literal["manchester-bods-session-identity-1.0"] = SESSION_IDENTITY_POLICY_ID
    snapshot_id: str = Field(min_length=1, max_length=200)
    session_token: str = Field(pattern=r"^[0-9a-f]{24}$")
    recorded_at_utc: datetime
    longitude: Decimal = Field(ge=-180, le=180)
    latitude: Decimal = Field(ge=-90, le=90)
    bearing_degrees: Decimal | None = Field(default=None, ge=0, le=360)
    velocity_mps: Decimal | None = Field(default=None, ge=0)
    line_ref: str | None = Field(default=None, max_length=200)
    identity_scope: Literal["single_observation_session"] = "single_observation_session"
    raw_reference_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_time(self) -> SessionObservation:
        if self.recorded_at_utc.tzinfo is None or self.recorded_at_utc.utcoffset() != UTC.utcoffset(
            self.recorded_at_utc
        ):
            raise ValueError("recorded_at_utc must be UTC")
        return self


class SessionExtractionResult(ManchesterSnapshotModel):
    """Extraction outcome for one snapshot; counts keep the denominator honest."""

    snapshot_id: str
    member_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    activities_seen: int = Field(ge=0)
    observations_extracted: int = Field(ge=0)
    malformed_skipped: int = Field(ge=0)
    observations: tuple[SessionObservation, ...] = ()

    @model_validator(mode="after")
    def validate_counts(self) -> SessionExtractionResult:
        if self.observations_extracted != len(self.observations):
            raise ValueError("extracted count must match the observation tuple")
        if self.observations_extracted + self.malformed_skipped != self.activities_seen:
            raise ValueError("extracted plus malformed must account for every activity")
        return self


class SessionCadenceMeasurement(ManchesterSnapshotModel):
    """Aggregate-only cadence evidence for one attended observation session."""

    schema_version: Literal["1.0"] = "1.0"
    policy_id: Literal["manchester-bods-session-identity-1.0"] = SESSION_IDENTITY_POLICY_ID
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"
    snapshot_ids: tuple[str, ...] = Field(min_length=2)
    snapshot_count: int = Field(ge=2)
    vehicles_seen_total: int = Field(ge=0)
    vehicles_linked_across_snapshots: int = Field(ge=0)
    observation_count: int = Field(ge=0)
    repeated_identical_fix_count: int = Field(ge=0)
    update_delta_seconds_median: float | None = Field(default=None, ge=0)
    update_delta_seconds_p90: float | None = Field(default=None, ge=0)
    update_delta_seconds_max: float | None = Field(default=None, ge=0)
    displacement_m_median: float | None = Field(default=None, ge=0)
    displacement_m_p90: float | None = Field(default=None, ge=0)
    displacement_m_max: float | None = Field(default=None, ge=0)
    implied_speed_mps_max: float | None = Field(default=None, ge=0)
    aggregates_only: Literal[True] = True
    raw_identifiers_published: Literal[False] = False
    salt_persisted: Literal[False] = False
    cross_session_linkable: Literal[False] = False
    transit_vehicle_only: Literal[True] = True
    road_traffic_volume_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_counts(self) -> SessionCadenceMeasurement:
        if self.snapshot_count != len(self.snapshot_ids):
            raise ValueError("snapshot count must match the id tuple")
        if self.vehicles_linked_across_snapshots > self.vehicles_seen_total:
            raise ValueError("linked vehicles cannot exceed vehicles seen")
        return self


def extract_session_observations_from_member(
    member_bytes: bytes,
    *,
    snapshot_id: str,
    session_salt: bytes,
) -> SessionExtractionResult:
    """Extract session-tokenised fixes from one raw SIRI-VM member.

    Raw vehicle references exist only inside this function; the returned
    observations carry HMAC session tokens and the fields a trajectory needs.
    """

    if len(session_salt) < _MINIMUM_SALT_BYTES:
        raise BodsSessionIdentityError(
            "SALT_TOO_SHORT",
            f"the session salt must be at least {_MINIMUM_SALT_BYTES} random bytes",
        )
    if len(member_bytes) > _MAX_MEMBER_BYTES:
        raise BodsSessionIdentityError(
            "MEMBER_TOO_LARGE", "the raw member exceeds the bounded size"
        )
    if member_bytes[:2] == b"\x1f\x8b":
        # The quarantine preserves the exact wire bytes, which BODS serves
        # gzip-compressed; integrity was verified over the stored bytes above.
        try:
            member_bytes = gzip.decompress(member_bytes)
        except OSError as exc:
            raise BodsSessionIdentityError(
                "MEMBER_NOT_XML", "the gzip member could not be decompressed"
            ) from exc
        if len(member_bytes) > _MAX_MEMBER_BYTES:
            raise BodsSessionIdentityError(
                "MEMBER_TOO_LARGE", "the decompressed member exceeds the bounded size"
            )
    try:
        root = fromstring(member_bytes.decode("utf-8"))  # noqa: S314 - hash-verified quarantined bytes from the accepted acquisition boundary
    except (UnicodeDecodeError, ParseError, ValueError) as exc:
        raise BodsSessionIdentityError(
            "MEMBER_NOT_XML", "the raw member is not parseable SIRI XML"
        ) from exc
    observations: list[SessionObservation] = []
    activities_seen = 0
    malformed = 0
    for activity in _descendants(root, "VehicleActivity"):
        activities_seen += 1
        observation = _observation_from_activity(activity, snapshot_id, session_salt)
        if observation is None:
            malformed += 1
        else:
            observations.append(observation)
    return SessionExtractionResult(
        snapshot_id=snapshot_id,
        member_sha256=hashlib.sha256(member_bytes).hexdigest(),
        activities_seen=activities_seen,
        observations_extracted=len(observations),
        malformed_skipped=malformed,
        observations=tuple(observations),
    )


def extract_session_observations(
    workspace_root: str | Path,
    snapshot_id: str,
    *,
    session_salt: bytes,
    expected_synthetic: bool = False,
) -> SessionExtractionResult:
    """Extract from one quarantined snapshot after verifying every identity."""

    snapshot_dir = Path(workspace_root) / QUARANTINE_DIRECTORY_NAME / snapshot_id
    verify_manchester_quarantine(snapshot_dir)
    manifest_path = snapshot_dir / QUARANTINE_MANIFEST_FILE_NAME
    try:
        manifest = ManchesterQuarantineManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
        raise BodsSessionIdentityError(
            "MANIFEST_INVALID", "the quarantine manifest could not be read"
        ) from exc
    if manifest.snapshot_id != snapshot_id:
        raise BodsSessionIdentityError(
            "SNAPSHOT_MISMATCH", "the manifest does not belong to the requested snapshot"
        )
    if manifest.synthetic != expected_synthetic:
        raise BodsSessionIdentityError(
            "SYNTHETIC_MISMATCH",
            "the quarantined evidence class does not match the caller's declaration",
        )
    if len(manifest.members) != 1:
        raise BodsSessionIdentityError(
            "MEMBER_COUNT_INVALID", "BODS quarantines hold exactly one member"
        )
    member = manifest.members[0]
    member_path = snapshot_dir / RAW_DIRECTORY_NAME / member.relative_path
    if member_path.is_symlink() or not member_path.is_file():
        raise BodsSessionIdentityError("MEMBER_MISSING", "the raw member file is missing or unsafe")
    member_bytes = member_path.read_bytes()
    if hashlib.sha256(member_bytes).hexdigest() != member.sha256:
        raise BodsSessionIdentityError(
            "MEMBER_HASH_MISMATCH", "the raw member does not match its manifest identity"
        )
    return extract_session_observations_from_member(
        member_bytes, snapshot_id=snapshot_id, session_salt=session_salt
    )


def measure_session_cadence(
    results: list[SessionExtractionResult],
) -> SessionCadenceMeasurement:
    """Reduce one session's extractions to aggregate cadence evidence."""

    snapshot_ids = [result.snapshot_id for result in results]
    if len(snapshot_ids) != len(set(snapshot_ids)):
        raise BodsSessionIdentityError(
            "DUPLICATE_SNAPSHOT", "each snapshot enters the session exactly once"
        )
    if len(snapshot_ids) < 2:
        raise BodsSessionIdentityError("SESSION_TOO_SHORT", "cadence needs at least two snapshots")
    by_token: dict[str, list[SessionObservation]] = defaultdict(list)
    for result in results:
        for observation in result.observations:
            by_token[observation.session_token].append(observation)

    deltas: list[float] = []
    displacements: list[float] = []
    implied_speeds: list[float] = []
    repeated = 0
    linked = 0
    for observations in by_token.values():
        distinct = sorted(
            {(obs.recorded_at_utc, obs.longitude, obs.latitude) for obs in observations},
            key=lambda item: item[0],
        )
        repeated += len(observations) - len(distinct)
        if len({item[0] for item in distinct}) >= 2:
            linked += 1
        for earlier, later in zip(distinct, distinct[1:], strict=False):
            delta = (later[0] - earlier[0]).total_seconds()
            if delta <= 0:
                continue
            displacement = _haversine_m(earlier[1], earlier[2], later[1], later[2])
            deltas.append(delta)
            displacements.append(displacement)
            implied_speeds.append(displacement / delta)

    return SessionCadenceMeasurement(
        snapshot_ids=tuple(snapshot_ids),
        snapshot_count=len(snapshot_ids),
        vehicles_seen_total=len(by_token),
        vehicles_linked_across_snapshots=linked,
        observation_count=sum(result.observations_extracted for result in results),
        repeated_identical_fix_count=repeated,
        update_delta_seconds_median=_percentile(deltas, 0.5),
        update_delta_seconds_p90=_percentile(deltas, 0.9),
        update_delta_seconds_max=max(deltas) if deltas else None,
        displacement_m_median=_percentile(displacements, 0.5),
        displacement_m_p90=_percentile(displacements, 0.9),
        displacement_m_max=max(displacements) if displacements else None,
        implied_speed_mps_max=max(implied_speeds) if implied_speeds else None,
    )


def _observation_from_activity(
    activity: Element, snapshot_id: str, session_salt: bytes
) -> SessionObservation | None:
    recorded_text = _text(_first(activity, "RecordedAtTime"))
    journey = _first(activity, "MonitoredVehicleJourney")
    if recorded_text is None or journey is None:
        return None
    location = _first(journey, "VehicleLocation")
    raw_reference = _text(_first(journey, "VehicleRef"))
    if location is None or raw_reference is None:
        return None
    longitude = _text(_first(location, "Longitude"))
    latitude = _text(_first(location, "Latitude"))
    if longitude is None or latitude is None:
        return None
    try:
        recorded_at = datetime.fromisoformat(recorded_text.replace("Z", "+00:00"))
        observation = SessionObservation(
            snapshot_id=snapshot_id,
            session_token=hmac.new(
                session_salt, raw_reference.encode("utf-8"), hashlib.sha256
            ).hexdigest()[:_TOKEN_HEX_LENGTH],
            recorded_at_utc=recorded_at,
            longitude=Decimal(longitude),
            latitude=Decimal(latitude),
            bearing_degrees=_optional_decimal(_text(_first(journey, "Bearing"))),
            velocity_mps=_optional_decimal(_text(_first(journey, "Velocity"))),
            line_ref=_text(_first(journey, "LineRef")),
        )
    except (ValueError, InvalidOperation):
        return None
    return observation


def _descendants(root: Element, localname: str) -> list[Element]:
    return [element for element in root.iter() if _localname(element.tag) == localname]


def _first(parent: Element, localname: str) -> Element | None:
    for child in parent.iter():
        if child is not parent and _localname(child.tag) == localname:
            return child
    return None


def _localname(tag: object) -> str:
    text = str(tag)
    return text.rsplit("}", 1)[-1]


def _text(element: Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    value = element.text.strip()
    return value or None


def _optional_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def _haversine_m(lon_a: Decimal, lat_a: Decimal, lon_b: Decimal, lat_b: Decimal) -> float:
    phi_a, phi_b = math.radians(float(lat_a)), math.radians(float(lat_b))
    d_phi = phi_b - phi_a
    d_lambda = math.radians(float(lon_b) - float(lon_a))
    inner = (
        math.sin(d_phi / 2) ** 2 + math.cos(phi_a) * math.cos(phi_b) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(inner))


def measurement_to_json(measurement: SessionCadenceMeasurement) -> str:
    """Serialise the aggregate measurement deterministically for publication."""

    return json.dumps(
        measurement.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False
    )

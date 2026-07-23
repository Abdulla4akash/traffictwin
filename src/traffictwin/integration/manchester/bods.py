"""MAN-05 candidate: privacy-safe offline BODS SIRI-VM parser.

This module parses immutable raw XML snapshot bytes through the shared hardened
XML boundary. It performs no acquisition, stores no raw VehicleRef in derived
records, and cannot activate Bee Network membership while GA-BEE-1 is open.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Literal
from xml.etree.ElementTree import Element

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import (
    ManchesterFindingSeverity,
    ManchesterSnapshotModel,
    ManchesterValidationState,
    sha256_hex,
)
from traffictwin.integration.manchester.xml import ManchesterXmlError, XmlPolicy, parse_xml

BODS_ADAPTER_SCHEMA_VERSION = "1.0"
BODS_ADAPTER_METHOD_VERSION = "manchester-bods-siri-vm-1.0"
BODS_ADAPTER_CAPABILITY_ID = "MAN-05"
BODS_SIRI_NAMESPACE = "http://www.siri.org.uk/siri"
BODS_XML_SCHEMA_INSTANCE_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"
BODS_FRESHNESS_POLICY_VERSION = "manchester-freshness-v1"
BODS_LIVE_AGE_SECONDS = 60
MAX_SIRI_BYTES = 16_000_000
MAX_VEHICLE_ACTIVITIES = 50_000

_SNAPSHOT_ID_PATTERN = r"^[a-z0-9][a-z0-9_.-]{0,95}-\d{8}T\d{6}Z-[0-9a-f]{12}$"
_MEMBER_PATH_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}(/[A-Za-z0-9][A-Za-z0-9._-]{0,99}){0,9}$"

FreshnessState = Literal["live_vehicle", "stale", "historical", "synthetic"]
Occupancy = Literal["full", "standingAvailable", "seatsAvailable"]
VehicleJourneyRefSource = Literal["VehicleJourneyRef", "FramedVehicleJourneyRef"]


class BodsAdapterError(RuntimeError):
    """Broken lineage or unsupported caller invocation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class BodsModel(ManchesterSnapshotModel):
    """Strict frozen base for MAN-05 candidate artifacts."""


class BodsMemberRef(BodsModel):
    """Exact private raw SIRI-VM snapshot member lineage."""

    snapshot_id: str = Field(pattern=_SNAPSHOT_ID_PATTERN)
    member_path: str = Field(pattern=_MEMBER_PATH_PATTERN)
    member_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_encoding: Literal["identity", "gzip"] = "identity"
    parser_payload_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    publication_class: Literal["private_raw"] = "private_raw"
    synthetic: bool

    @model_validator(mode="after")
    def validate_content_identity(self) -> BodsMemberRef:
        if self.content_encoding == "identity" and self.parser_payload_sha256 is not None:
            raise ValueError("identity members cannot carry a separate parser-payload hash")
        if self.content_encoding == "gzip" and self.parser_payload_sha256 is None:
            raise ValueError("gzip members require the decoded parser-payload hash")
        return self


class BodsBoundingBox(BodsModel):
    """Explicit request scope; geography does not imply Bee membership."""

    min_longitude: Decimal = Field(ge=-180, le=180)
    min_latitude: Decimal = Field(ge=-90, le=90)
    max_longitude: Decimal = Field(ge=-180, le=180)
    max_latitude: Decimal = Field(ge=-90, le=90)

    @model_validator(mode="after")
    def validate_bounds(self) -> BodsBoundingBox:
        if self.min_longitude >= self.max_longitude or self.min_latitude >= self.max_latitude:
            raise ValueError("bounding box minimums must precede maximums")
        return self

    def contains(self, longitude: Decimal, latitude: Decimal) -> bool:
        return (
            self.min_longitude <= longitude <= self.max_longitude
            and self.min_latitude <= latitude <= self.max_latitude
        )


class BodsParseScope(BodsModel):
    """Deterministic evaluation instant and geographic scope."""

    evaluated_at_utc: datetime
    mode: Literal["live", "offline_replay"]
    bounding_box: BodsBoundingBox
    freshness_policy_version: Literal["manchester-freshness-v1"] = "manchester-freshness-v1"
    live_age_ceiling_seconds: Literal[60] = 60
    bee_membership_policy: Literal["unavailable_ga_bee_1"] = "unavailable_ga_bee_1"
    retention_policy: Literal["unapproved"] = "unapproved"

    @model_validator(mode="after")
    def validate_utc(self) -> BodsParseScope:
        utc_offset = UTC.utcoffset(self.evaluated_at_utc)
        if self.evaluated_at_utc.tzinfo is None or self.evaluated_at_utc.utcoffset() != utc_offset:
            raise ValueError("evaluated_at_utc must be explicitly UTC")
        return self


class BodsFinding(BodsModel):
    """One redacted deterministic parser finding."""

    code: str = Field(pattern=r"^[A-Z0-9_]+$", max_length=96)
    severity: ManchesterFindingSeverity
    message: str = Field(min_length=1, max_length=500)
    activity_index: int | None = Field(default=None, ge=0)


class LiveTransitVehicleObservation(BodsModel):
    """Privacy-safe transit position that cannot become a road-count record."""

    source: BodsMemberRef
    activity_index: int = Field(ge=0)
    response_timestamp_utc: datetime
    producer_ref: str = Field(min_length=1, max_length=200)
    recorded_at_utc: datetime
    valid_until_utc: datetime
    freshness_state: FreshnessState
    freshness_policy_version: Literal["manchester-freshness-v1"] = "manchester-freshness-v1"
    operator_ref: str = Field(min_length=1, max_length=100)
    line_ref: str = Field(min_length=1, max_length=200)
    published_line_name: str = Field(min_length=1, max_length=200)
    direction_ref: str = Field(min_length=1, max_length=100)
    origin_ref: str = Field(min_length=1, max_length=200)
    origin_name: str = Field(min_length=1, max_length=300)
    destination_ref: str = Field(min_length=1, max_length=200)
    destination_name: str | None = Field(default=None, max_length=300)
    longitude: Decimal = Field(ge=-180, le=180)
    latitude: Decimal = Field(ge=-90, le=90)
    bearing_degrees: Decimal | None = Field(default=None, ge=0, le=360)
    velocity_mps: Decimal | None = Field(default=None, ge=0)
    occupancy: Occupancy | None = None
    block_ref: str | None = Field(default=None, min_length=1, max_length=200)
    vehicle_journey_ref: str | None = Field(default=None, min_length=1, max_length=300)
    vehicle_journey_ref_source: VehicleJourneyRefSource | None = None
    vehicle_token: str = Field(pattern=r"^[0-9a-f]{24}$")
    vehicle_ref_redacted: Literal[True] = True
    identity_scope: Literal["snapshot_only"] = "snapshot_only"
    bee_network_membership: Literal["unverified"] = "unverified"
    bee_network_membership_available: Literal[False] = False
    evidence_kind: Literal["live_transit_vehicle_position"] = "live_transit_vehicle_position"
    transit_vehicle_only: Literal[True] = True
    road_traffic_volume_available: Literal[False] = False
    private_vehicle_flow_available: Literal[False] = False
    passenger_inference_available: Literal[False] = False
    public_export_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_times(self) -> LiveTransitVehicleObservation:
        for value in (
            self.response_timestamp_utc,
            self.recorded_at_utc,
            self.valid_until_utc,
        ):
            if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
                raise ValueError("all BODS timestamps must be UTC")
        if self.valid_until_utc < self.recorded_at_utc:
            raise ValueError("ValidUntilTime cannot precede RecordedAtTime")
        if self.source.synthetic and self.freshness_state != "synthetic":
            raise ValueError("synthetic source records must remain synthetic")
        if (self.vehicle_journey_ref is None) != (self.vehicle_journey_ref_source is None):
            raise ValueError("journey reference and its source must be available together")
        return self


class BodsParseCounts(BodsModel):
    """Complete activity accounting for one snapshot member."""

    activities_seen: int = Field(ge=0)
    records_accepted: int = Field(ge=0)
    malformed: int = Field(ge=0)
    outside_bounds: int = Field(ge=0)
    duplicate_collapsed: int = Field(ge=0)
    conflicting_duplicates: int = Field(ge=0)
    profile_missing_bearing: int = Field(ge=0)
    profile_missing_block_ref: int = Field(ge=0)
    profile_missing_vehicle_journey_ref: int = Field(ge=0)
    profile_alternate_vehicle_journey_ref: int = Field(ge=0)
    live_vehicle: int = Field(ge=0)
    stale: int = Field(ge=0)
    historical: int = Field(ge=0)
    synthetic: int = Field(ge=0)


class BodsParseReport(BodsModel):
    """Deterministic, privacy-safe result of one offline SIRI-VM parse."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-05"] = "MAN-05"
    method_version: Literal["manchester-bods-siri-vm-1.0"] = "manchester-bods-siri-vm-1.0"
    source: BodsMemberRef
    scope: BodsParseScope
    status: ManchesterValidationState
    findings: tuple[BodsFinding, ...] = ()
    counts: BodsParseCounts
    records: tuple[LiveTransitVehicleObservation, ...] = ()
    raw_vehicle_identifiers_in_output: Literal[False] = False
    retention_policy_approved: Literal[False] = False
    public_export_available: Literal[False] = False
    bee_network_membership_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_report(self) -> BodsParseReport:
        if self.counts.records_accepted != len(self.records):
            raise ValueError("records_accepted must match records")
        profile_counts = (
            self.counts.profile_missing_bearing,
            self.counts.profile_missing_block_ref,
            self.counts.profile_missing_vehicle_journey_ref,
            self.counts.profile_alternate_vehicle_journey_ref,
        )
        if any(value > self.counts.records_accepted for value in profile_counts):
            raise ValueError("profile-gap counts cannot exceed accepted records")
        expected_profile_counts = (
            sum(record.bearing_degrees is None for record in self.records),
            sum(record.block_ref is None for record in self.records),
            sum(record.vehicle_journey_ref is None for record in self.records),
            sum(
                record.vehicle_journey_ref_source == "FramedVehicleJourneyRef"
                for record in self.records
            ),
        )
        if profile_counts != expected_profile_counts:
            raise ValueError("profile-gap counts must match accepted records")
        state_counts = {
            "live_vehicle": self.counts.live_vehicle,
            "stale": self.counts.stale,
            "historical": self.counts.historical,
            "synthetic": self.counts.synthetic,
        }
        for state, expected in state_counts.items():
            if sum(record.freshness_state == state for record in self.records) != expected:
                raise ValueError("freshness counts must match records")
        errors = any(f.severity is ManchesterFindingSeverity.ERROR for f in self.findings)
        warnings = any(f.severity is ManchesterFindingSeverity.WARNING for f in self.findings)
        if self.status is ManchesterValidationState.ACCEPTED and (errors or warnings):
            raise ValueError("accepted reports cannot carry findings")
        if self.status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS and (
            errors or not warnings
        ):
            raise ValueError("warning acceptance requires warnings and no errors")
        if self.status is ManchesterValidationState.REJECTED and not errors:
            raise ValueError("rejected reports require errors")
        return self


def bods_freshness_state(
    *,
    recorded_at_utc: datetime,
    valid_until_utc: datetime,
    evaluated_at_utc: datetime,
    mode: Literal["live", "offline_replay"],
    synthetic: bool,
) -> FreshnessState:
    """Apply the frozen v1 freshness rule without reading wall-clock time."""

    for value in (recorded_at_utc, valid_until_utc, evaluated_at_utc):
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise BodsAdapterError(
                "NON_UTC_FRESHNESS_INPUT",
                "freshness inputs must be explicit UTC instants",
            )
    if valid_until_utc < recorded_at_utc:
        raise BodsAdapterError(
            "INVALID_VALIDITY_WINDOW",
            "ValidUntilTime cannot precede RecordedAtTime",
        )
    if synthetic:
        return "synthetic"
    if mode == "offline_replay":
        return "historical"
    age_seconds = (evaluated_at_utc - recorded_at_utc).total_seconds()
    if 0 <= age_seconds <= BODS_LIVE_AGE_SECONDS and evaluated_at_utc <= valid_until_utc:
        return "live_vehicle"
    return "stale"


def parse_bods_siri_vm(
    member: tuple[BodsMemberRef, bytes], scope: BodsParseScope
) -> BodsParseReport:
    """Parse one immutable SIRI-VM member through the hardened XML boundary."""

    ref, payload = member
    if len(payload) > MAX_SIRI_BYTES:
        raise BodsAdapterError("MEMBER_TOO_LARGE", "SIRI member exceeds byte bound")
    expected_payload_sha256 = ref.parser_payload_sha256 or ref.member_sha256
    if sha256_hex(payload) != expected_payload_sha256:
        raise BodsAdapterError("MEMBER_HASH_MISMATCH", "SIRI member bytes changed")
    findings: list[BodsFinding] = []
    try:
        parsed = parse_xml(
            payload,
            policy=XmlPolicy(
                max_input_bytes=MAX_SIRI_BYTES,
                max_elements=500_000,
                max_depth=40,
                max_attributes_per_element=5,
                max_text_characters=8_000_000,
                allowed_root_local_names=("Siri",),
                allowed_namespaces=(BODS_SIRI_NAMESPACE,),
                allowed_attribute_namespaces=(
                    BODS_SIRI_NAMESPACE,
                    BODS_XML_SCHEMA_INSTANCE_NAMESPACE,
                ),
            ),
        )
    except ManchesterXmlError:
        _add(findings, "MALFORMED_OR_UNSAFE_XML", "SIRI XML failed the hardened boundary")
        return _report(ref, scope, findings, [], 0, 0, 0, 0, 0)

    try:
        service_delivery = _one(parsed.root, "ServiceDelivery")
        response_timestamp = _utc_datetime(_text(_one(service_delivery, "ResponseTimestamp")))
        producer_ref = _bounded_text(_text(_one(service_delivery, "ProducerRef")), 200)
        deliveries = _children(service_delivery, "VehicleMonitoringDelivery")
        if not deliveries:
            raise ValueError("VehicleMonitoringDelivery is required")
    except (ValueError, InvalidOperation):
        _add(findings, "MALFORMED_DELIVERY", "SIRI delivery envelope violates the profile")
        return _report(ref, scope, findings, [], 0, 0, 0, 0, 0)

    activities = [
        activity for delivery in deliveries for activity in _children(delivery, "VehicleActivity")
    ]
    if len(activities) > MAX_VEHICLE_ACTIVITIES:
        raise BodsAdapterError("TOO_MANY_ACTIVITIES", "activity count exceeds bound")
    candidates: list[tuple[str, str, LiveTransitVehicleObservation, tuple[str, ...]]] = []
    malformed = 0
    outside = 0
    for index, activity in enumerate(activities):
        try:
            raw_vehicle_ref, record, profile_gaps = _parse_activity(
                ref,
                index,
                activity,
                response_timestamp,
                producer_ref,
                scope,
            )
        except (BodsAdapterError, ValueError, TypeError, InvalidOperation):
            malformed += 1
            _add(
                findings,
                "MALFORMED_ACTIVITY",
                "vehicle activity violates the mandatory SIRI-VM profile",
                index,
            )
            continue
        if not scope.bounding_box.contains(record.longitude, record.latitude):
            outside += 1
            _add(
                findings,
                "OUTSIDE_BOUNDING_BOX",
                "vehicle activity is outside the declared geographic scope",
                index,
                ManchesterFindingSeverity.WARNING,
            )
            continue
        key = f"{raw_vehicle_ref}\0{record.recorded_at_utc.isoformat()}"
        candidates.append((key, raw_vehicle_ref, record, profile_gaps))

    accepted: list[LiveTransitVehicleObservation] = []
    duplicate_collapsed = 0
    conflicts = 0
    groups: dict[str, list[tuple[LiveTransitVehicleObservation, tuple[str, ...]]]] = {}
    for key, _raw_vehicle_ref, record, profile_gaps in candidates:
        groups.setdefault(key, []).append((record, profile_gaps))
    accepted_profile_gaps: Counter[str] = Counter()
    for key in sorted(groups):
        group = groups[key]
        neutral = {
            record.model_copy(
                update={"activity_index": 0, "source": group[0][0].source}
            ).fingerprint()
            for record, _profile_gaps in group
        }
        if len(neutral) == 1:
            accepted.append(group[0][0])
            accepted_profile_gaps.update(group[0][1])
            if len(group) > 1:
                duplicate_collapsed += len(group) - 1
                _add(
                    findings,
                    "DUPLICATE_ACTIVITY",
                    "identical vehicle activity was collapsed",
                    severity=ManchesterFindingSeverity.WARNING,
                )
        else:
            conflicts += len(group)
            _add(
                findings,
                "CONFLICTING_ACTIVITY",
                "same vehicle/time identity carries conflicting values",
            )

    profile_messages = {
        "PROFILE_MISSING_BEARING": "accepted activities omit profile-mandatory Bearing",
        "PROFILE_MISSING_BLOCK_REF": "accepted activities omit profile-mandatory BlockRef",
        "PROFILE_MISSING_VEHICLE_JOURNEY_REF": (
            "accepted activities omit both direct and framed vehicle-journey identity"
        ),
        "PROFILE_ALTERNATE_VEHICLE_JOURNEY_REF": (
            "accepted activities use FramedVehicleJourneyRef/DatedVehicleJourneyRef "
            "instead of the profile's direct VehicleJourneyRef"
        ),
    }
    for code in sorted(accepted_profile_gaps):
        _add(
            findings,
            code,
            f"{profile_messages[code]} ({accepted_profile_gaps[code]} records)",
            severity=ManchesterFindingSeverity.WARNING,
        )

    accepted.sort(key=lambda record: (record.recorded_at_utc, record.vehicle_token))
    return _report(
        ref,
        scope,
        findings,
        accepted,
        len(activities),
        malformed,
        outside,
        duplicate_collapsed,
        conflicts,
        accepted_profile_gaps,
    )


def _parse_activity(
    ref: BodsMemberRef,
    index: int,
    activity: Element,
    response_timestamp: datetime,
    producer_ref: str,
    scope: BodsParseScope,
) -> tuple[str, LiveTransitVehicleObservation, tuple[str, ...]]:
    recorded_at = _utc_datetime(_text(_one(activity, "RecordedAtTime")))
    valid_until = _utc_datetime(_text(_one(activity, "ValidUntilTime")))
    journey = _one(activity, "MonitoredVehicleJourney")
    location = _one(journey, "VehicleLocation")
    raw_vehicle_ref = _bounded_text(_text(_one(journey, "VehicleRef")), 300)
    longitude = _decimal(_text(_one(location, "Longitude")))
    latitude = _decimal(_text(_one(location, "Latitude")))
    token = sha256(f"{ref.snapshot_id}\0{raw_vehicle_ref}".encode()).hexdigest()[:24]
    optional_velocity = _optional_text(journey, "Velocity")
    optional_occupancy = _occupancy(_optional_text(journey, "Occupancy"))
    optional_bearing = _optional_text(journey, "Bearing")
    optional_block_ref = _optional_bounded_text(journey, "BlockRef", 200)
    direct_journey_ref = _optional_bounded_text(journey, "VehicleJourneyRef", 300)
    framed_journey_refs = _children(journey, "FramedVehicleJourneyRef")
    if len(framed_journey_refs) > 1:
        raise ValueError("FramedVehicleJourneyRef cannot repeat")
    framed_journey_ref = (
        None
        if not framed_journey_refs
        else _required_child_text(framed_journey_refs[0], "DatedVehicleJourneyRef", 300)
    )
    if direct_journey_ref is not None:
        vehicle_journey_ref = direct_journey_ref
        vehicle_journey_ref_source: VehicleJourneyRefSource | None = "VehicleJourneyRef"
    elif framed_journey_ref is not None:
        vehicle_journey_ref = framed_journey_ref
        vehicle_journey_ref_source = "FramedVehicleJourneyRef"
    else:
        vehicle_journey_ref = None
        vehicle_journey_ref_source = None
    profile_gaps: list[str] = []
    if optional_bearing is None:
        profile_gaps.append("PROFILE_MISSING_BEARING")
    if optional_block_ref is None:
        profile_gaps.append("PROFILE_MISSING_BLOCK_REF")
    if vehicle_journey_ref is None:
        profile_gaps.append("PROFILE_MISSING_VEHICLE_JOURNEY_REF")
    elif vehicle_journey_ref_source == "FramedVehicleJourneyRef":
        profile_gaps.append("PROFILE_ALTERNATE_VEHICLE_JOURNEY_REF")
    state = bods_freshness_state(
        recorded_at_utc=recorded_at,
        valid_until_utc=valid_until,
        evaluated_at_utc=scope.evaluated_at_utc,
        mode=scope.mode,
        synthetic=ref.synthetic,
    )
    record = LiveTransitVehicleObservation(
        source=ref,
        activity_index=index,
        response_timestamp_utc=response_timestamp,
        producer_ref=producer_ref,
        recorded_at_utc=recorded_at,
        valid_until_utc=valid_until,
        freshness_state=state,
        operator_ref=_required_child_text(journey, "OperatorRef", 100),
        line_ref=_required_child_text(journey, "LineRef", 200),
        published_line_name=_required_child_text(journey, "PublishedLineName", 200),
        direction_ref=_required_child_text(journey, "DirectionRef", 100),
        origin_ref=_required_child_text(journey, "OriginRef", 200),
        origin_name=_required_child_text(journey, "OriginName", 300),
        destination_ref=_required_child_text(journey, "DestinationRef", 200),
        destination_name=_optional_bounded_text(journey, "DestinationName", 300),
        longitude=longitude,
        latitude=latitude,
        bearing_degrees=None if optional_bearing is None else _decimal(optional_bearing),
        velocity_mps=None if optional_velocity is None else _decimal(optional_velocity),
        occupancy=optional_occupancy,
        block_ref=optional_block_ref,
        vehicle_journey_ref=vehicle_journey_ref,
        vehicle_journey_ref_source=vehicle_journey_ref_source,
        vehicle_token=token,
    )
    return raw_vehicle_ref, record, tuple(sorted(profile_gaps))


def _report(
    ref: BodsMemberRef,
    scope: BodsParseScope,
    findings: Sequence[BodsFinding],
    records: Sequence[LiveTransitVehicleObservation],
    seen: int,
    malformed: int,
    outside: int,
    duplicates: int,
    conflicts: int,
    profile_gaps: Counter[str] | None = None,
) -> BodsParseReport:
    gaps = Counter() if profile_gaps is None else profile_gaps
    ordered_findings = tuple(
        sorted(
            findings,
            key=lambda finding: (
                finding.code,
                -1 if finding.activity_index is None else finding.activity_index,
                finding.message,
            ),
        )
    )
    return BodsParseReport(
        source=ref,
        scope=scope,
        status=_status(ordered_findings),
        findings=ordered_findings,
        counts=BodsParseCounts(
            activities_seen=seen,
            records_accepted=len(records),
            malformed=malformed,
            outside_bounds=outside,
            duplicate_collapsed=duplicates,
            conflicting_duplicates=conflicts,
            profile_missing_bearing=gaps["PROFILE_MISSING_BEARING"],
            profile_missing_block_ref=gaps["PROFILE_MISSING_BLOCK_REF"],
            profile_missing_vehicle_journey_ref=gaps["PROFILE_MISSING_VEHICLE_JOURNEY_REF"],
            profile_alternate_vehicle_journey_ref=gaps["PROFILE_ALTERNATE_VEHICLE_JOURNEY_REF"],
            live_vehicle=sum(record.freshness_state == "live_vehicle" for record in records),
            stale=sum(record.freshness_state == "stale" for record in records),
            historical=sum(record.freshness_state == "historical" for record in records),
            synthetic=sum(record.freshness_state == "synthetic" for record in records),
        ),
        records=tuple(records),
    )


def _children(parent: Element, local_name: str) -> list[Element]:
    return [child for child in parent if _local_name(child.tag) == local_name]


def _one(parent: Element, local_name: str) -> Element:
    matches = _children(parent, local_name)
    if len(matches) != 1:
        raise ValueError(f"{local_name} must occur exactly once")
    return matches[0]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(element: Element) -> str:
    if element.text is None:
        raise ValueError("required XML text is absent")
    return element.text


def _bounded_text(value: str, maximum: int) -> str:
    if not value or value.strip() != value or len(value) > maximum:
        raise ValueError("XML text is empty, padded, or oversized")
    return value


def _required_child_text(parent: Element, name: str, maximum: int) -> str:
    return _bounded_text(_text(_one(parent, name)), maximum)


def _optional_text(parent: Element, name: str) -> str | None:
    matches = _children(parent, name)
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError(f"{name} cannot repeat")
    return _text(matches[0])


def _optional_bounded_text(parent: Element, name: str, maximum: int) -> str | None:
    value = _optional_text(parent, name)
    return None if value is None else _bounded_text(value, maximum)


def _occupancy(value: str | None) -> Occupancy | None:
    if value is None:
        return None
    if value == "full":
        return "full"
    if value == "standingAvailable":
        return "standingAvailable"
    if value == "seatsAvailable":
        return "seatsAvailable"
    raise ValueError("unknown Occupancy")


def _decimal(value: str) -> Decimal:
    parsed = Decimal(_bounded_text(value, 100))
    if not parsed.is_finite():
        raise ValueError("numeric XML value must be finite")
    return parsed


def _utc_datetime(value: str) -> datetime:
    text = _bounded_text(value, 40)
    if text.endswith("Z"):
        normalised = f"{text[:-1]}+00:00"
    elif text.endswith("+00:00"):
        normalised = text
    else:
        raise ValueError("BODS timestamp must use an explicit UTC designator")
    if "T" not in text:
        raise ValueError("BODS timestamp must use ISO date-time syntax")
    parsed = datetime.fromisoformat(normalised)
    if parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError("BODS timestamp must be UTC")
    return parsed


def _add(
    findings: list[BodsFinding],
    code: str,
    message: str,
    activity_index: int | None = None,
    severity: ManchesterFindingSeverity = ManchesterFindingSeverity.ERROR,
) -> None:
    findings.append(
        BodsFinding(
            code=code,
            severity=severity,
            message=message,
            activity_index=activity_index,
        )
    )


def _status(findings: Sequence[BodsFinding]) -> ManchesterValidationState:
    if any(finding.severity is ManchesterFindingSeverity.ERROR for finding in findings):
        return ManchesterValidationState.REJECTED
    if findings:
        return ManchesterValidationState.ACCEPTED_WITH_WARNINGS
    return ManchesterValidationState.ACCEPTED

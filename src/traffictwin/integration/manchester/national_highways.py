"""Strict DATEX II JSON projection for current National Highways REST feeds.

The parser accepts the three schemas observed and audited on 24 July 2026:
Road and Lane Closures v2, Speed Managed Areas v1, and Digital VMS v1. It
preserves the raw response elsewhere; this module emits only bounded,
source-separated operational records inside a caller-declared envelope.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, TypeAlias, cast

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import ManchesterSnapshotModel, sha256_hex

NATIONAL_HIGHWAYS_SCHEMA_VERSION = "2026-07-24"
NATIONAL_HIGHWAYS_PARSER_VERSION = "national-highways-datex-json-1.0"
NATIONAL_HIGHWAYS_SOURCE_HOST = "api.data.nationalhighways.co.uk"
NATIONAL_HIGHWAYS_TERMS_URI = "https://developer.data.nationalhighways.co.uk/terms"
NATIONAL_HIGHWAYS_ATTRIBUTION = "Powered by National Highways’ Transport Data Feeds"
NATIONAL_HIGHWAYS_LICENCE_ID = "NH-Transport-Data-Feeds"
MAX_NATIONAL_HIGHWAYS_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_NATIONAL_HIGHWAYS_RECORDS = 20_000
MAX_TEXT = 500

NationalHighwaysProduct: TypeAlias = Literal["closures", "speed_limits", "vms"]
NationalHighwaysEventType: TypeAlias = Literal["planned", "unplanned"]

_SOURCE_BY_PRODUCT = {
    "closures": "national_highways_closures",
    "speed_limits": "national_highways_speed_limits",
    "vms": "national_highways_vms",
}
_GEOMETRY_BY_PRODUCT = {
    "closures": "road_closure_position",
    "speed_limits": "temporary_speed_restriction_position",
    "vms": "variable_message_sign_position",
}


class NationalHighwaysError(ValueError):
    """Typed schema, scope, or replay refusal."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class NationalHighwaysEnvelope(ManchesterSnapshotModel):
    """Explicit WGS84 study envelope; not an administrative-boundary claim."""

    min_longitude: Decimal = Field(ge=-180, le=180)
    min_latitude: Decimal = Field(ge=-90, le=90)
    max_longitude: Decimal = Field(ge=-180, le=180)
    max_latitude: Decimal = Field(ge=-90, le=90)
    basis: Literal["caller_declared_study_envelope"] = "caller_declared_study_envelope"
    official_boundary: Literal[False] = False

    @model_validator(mode="after")
    def validate_bounds(self) -> NationalHighwaysEnvelope:
        if self.min_longitude >= self.max_longitude or self.min_latitude >= self.max_latitude:
            raise ValueError("National Highways study envelope must have increasing bounds")
        return self

    def contains(self, latitude: Decimal, longitude: Decimal) -> bool:
        """Return whether one declared source coordinate is inside the envelope."""

        return (
            self.min_latitude <= latitude <= self.max_latitude
            and self.min_longitude <= longitude <= self.max_longitude
        )

    def query_value(self) -> str:
        """Return the Digital VMS north/west/south/east order observed by the API."""

        return f"{self.min_latitude},{self.min_longitude},{self.max_latitude},{self.max_longitude}"


def default_manchester_operational_envelope() -> NationalHighwaysEnvelope:
    """Return the reviewed broad study envelope, explicitly not an official boundary."""

    return NationalHighwaysEnvelope(
        min_longitude=Decimal("-2.60"),
        min_latitude=Decimal("53.30"),
        max_longitude=Decimal("-1.90"),
        max_latitude=Decimal("53.70"),
    )


class NationalHighwaysRecord(ManchesterSnapshotModel):
    """One privacy-safe, in-envelope operational feature."""

    product: NationalHighwaysProduct
    source_id: Literal[
        "national_highways_closures",
        "national_highways_speed_limits",
        "national_highways_vms",
    ]
    record_token: str = Field(pattern=r"^[0-9a-f]{24}$")
    source_record_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    publication_time_utc: datetime
    record_updated_at_utc: datetime | None = None
    valid_from_utc: datetime | None = None
    valid_until_utc: datetime | None = None
    latitude: Decimal = Field(ge=-90, le=90)
    longitude: Decimal = Field(ge=-180, le=180)
    source_geometry_point_count: int = Field(ge=1)
    source_geometry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    location_description: str = Field(min_length=1, max_length=MAX_TEXT)
    road_name: str | None = Field(default=None, max_length=80)
    direction: str | None = Field(default=None, max_length=80)
    operational_type: str = Field(min_length=1, max_length=160)
    validity_status: str | None = Field(default=None, max_length=80)
    temporary_speed_limit_kph: Decimal | None = Field(default=None, ge=0, le=300)
    vms_working_status: str | None = Field(default=None, max_length=80)
    vms_description: str | None = Field(default=None, max_length=160)
    vms_message_information_types: tuple[str, ...] = ()
    vms_reason_for_setting: str | None = Field(default=None, max_length=MAX_TEXT)
    vms_message_set_at_utc: datetime | None = None
    literal_display_text_available: Literal[False] = False
    strategic_road_network_only: Literal[True] = True
    measured_speed_available: Literal[False] = False
    traffic_volume_available: Literal[False] = False
    congestion_measure_available: Literal[False] = False
    synthetic: bool

    @model_validator(mode="after")
    def validate_record(self) -> NationalHighwaysRecord:
        expected_source = _SOURCE_BY_PRODUCT[self.product]
        if self.source_id != expected_source:
            raise ValueError("record source must match its product")
        for value in (
            self.publication_time_utc,
            self.record_updated_at_utc,
            self.valid_from_utc,
            self.valid_until_utc,
            self.vms_message_set_at_utc,
        ):
            if value is not None and (value.tzinfo is None or value.utcoffset() != timedelta(0)):
                raise ValueError("National Highways instants must be UTC")
        if (
            self.valid_from_utc is not None
            and self.valid_until_utc is not None
            and self.valid_until_utc < self.valid_from_utc
        ):
            raise ValueError("record validity window is reversed")
        is_speed = self.product == "speed_limits"
        if is_speed != (self.temporary_speed_limit_kph is not None):
            raise ValueError("only speed-limit records may carry a temporary limit")
        is_vms = self.product == "vms"
        vms_values = (
            self.vms_working_status,
            self.vms_description,
            self.vms_reason_for_setting,
            self.vms_message_set_at_utc,
        )
        has_vms_metadata = any(value is not None for value in vms_values) or bool(
            self.vms_message_information_types
        )
        if not is_vms and has_vms_metadata:
            raise ValueError("VMS metadata may exist only on VMS records")
        if self.vms_message_information_types != tuple(
            sorted(set(self.vms_message_information_types))
        ):
            raise ValueError("VMS information types must be sorted and unique")
        return self


class NationalHighwaysParseCounts(ManchesterSnapshotModel):
    """Complete input-to-output reconciliation for one response."""

    source_items_seen: int = Field(ge=0)
    records_accepted: int = Field(ge=0)
    outside_envelope: int = Field(ge=0)
    coordinates_missing: int = Field(ge=0)
    exact_duplicates_collapsed: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> NationalHighwaysParseCounts:
        if self.source_items_seen != (
            self.records_accepted
            + self.outside_envelope
            + self.coordinates_missing
            + self.exact_duplicates_collapsed
        ):
            raise ValueError("National Highways parse counts must reconcile")
        return self


class NationalHighwaysParseReport(ManchesterSnapshotModel):
    """Deterministic source-separated projection of one exact raw response."""

    schema_version: Literal["2026-07-24"] = "2026-07-24"
    method_version: Literal["national-highways-datex-json-1.0"] = "national-highways-datex-json-1.0"
    product: NationalHighwaysProduct
    source_id: Literal[
        "national_highways_closures",
        "national_highways_speed_limits",
        "national_highways_vms",
    ]
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    publication_time_utc: datetime
    feed_type: str = Field(min_length=1, max_length=80)
    model_base_version: str = Field(min_length=1, max_length=80)
    envelope: NationalHighwaysEnvelope
    envelope_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: tuple[NationalHighwaysRecord, ...]
    counts: NationalHighwaysParseCounts
    complete_reconciliation: Literal[True] = True
    source_geometry_preserved_in_raw_snapshot: Literal[True] = True
    representative_point_is_source_vertex: Literal[True] = True
    source_fusion_performed: Literal[False] = False
    synthetic: bool

    @model_validator(mode="after")
    def validate_report(self) -> NationalHighwaysParseReport:
        if self.source_id != _SOURCE_BY_PRODUCT[self.product]:
            raise ValueError("parse-report source must match its product")
        if self.envelope_fingerprint != self.envelope.fingerprint():
            raise ValueError("parse report must bind the exact study envelope")
        keys = tuple(record.record_token for record in self.records)
        if keys != tuple(sorted(keys)) or len(set(keys)) != len(keys):
            raise ValueError("records must have sorted unique tokens")
        if any(record.product != self.product for record in self.records):
            raise ValueError("a parse report cannot mix products")
        if any(record.synthetic != self.synthetic for record in self.records):
            raise ValueError("parse-report evidence class cannot be mixed")
        if self.counts.records_accepted != len(self.records):
            raise ValueError("accepted count must match embedded records")
        return self


def parse_national_highways_payload(
    payload: bytes,
    *,
    product: NationalHighwaysProduct,
    envelope: NationalHighwaysEnvelope,
    synthetic: bool,
) -> NationalHighwaysParseReport:
    """Parse one bounded DATEX II JSON response and retain only in-envelope source points."""

    if not payload or len(payload) > MAX_NATIONAL_HIGHWAYS_RESPONSE_BYTES:
        raise NationalHighwaysError("PAYLOAD_SIZE_INVALID", "response is empty or exceeds 8 MiB")
    try:
        document = json.loads(payload, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, NationalHighwaysError) as exc:
        raise NationalHighwaysError("JSON_INVALID", "response is not duplicate-free JSON") from exc
    if not isinstance(document, dict) or tuple(document) != ("D2Payload",):
        raise NationalHighwaysError("TOP_LEVEL_SCHEMA_DRIFT", "expected exactly D2Payload")
    root = _mapping(document["D2Payload"], "D2Payload")
    feed_type = _text(root.get("feedType"), "feedType", 80)
    expected_feed = "vmsPublication" if product == "vms" else "SituationPublication"
    if feed_type != expected_feed:
        raise NationalHighwaysError("FEED_TYPE_MISMATCH", "feedType does not match the product")
    publication_time = _utc(root.get("publicationTime"), "publicationTime")
    model_version_key = "modelBaseVersionG" if product == "vms" else "modelBaseVersion"
    model_version = _text(root.get(model_version_key), model_version_key, 80)
    source_items = _source_items(root, product)
    if len(source_items) > MAX_NATIONAL_HIGHWAYS_RECORDS:
        raise NationalHighwaysError("RECORD_LIMIT_EXCEEDED", "response record count is unbounded")

    accepted: dict[str, NationalHighwaysRecord] = {}
    outside = 0
    missing = 0
    duplicates = 0
    for source_item in source_items:
        projected = _project_item(
            source_item,
            product=product,
            publication_time=publication_time,
            envelope=envelope,
            synthetic=synthetic,
        )
        if projected is None:
            coordinates = _coordinates(source_item, product)
            if coordinates:
                outside += 1
            else:
                missing += 1
            continue
        if projected.record_token in accepted:
            if accepted[projected.record_token] != projected:
                raise NationalHighwaysError(
                    "IDENTIFIER_CONFLICT", "one source identifier has conflicting content"
                )
            duplicates += 1
            continue
        accepted[projected.record_token] = projected
    records = tuple(sorted(accepted.values(), key=lambda item: item.record_token))
    return NationalHighwaysParseReport(
        product=product,
        source_id=cast(Any, _SOURCE_BY_PRODUCT[product]),
        raw_sha256=sha256_hex(payload),
        publication_time_utc=publication_time,
        feed_type=feed_type,
        model_base_version=model_version,
        envelope=envelope,
        envelope_fingerprint=envelope.fingerprint(),
        records=records,
        counts=NationalHighwaysParseCounts(
            source_items_seen=len(source_items),
            records_accepted=len(records),
            outside_envelope=outside,
            coordinates_missing=missing,
            exact_duplicates_collapsed=duplicates,
        ),
        synthetic=synthetic,
    )


def _source_items(
    root: dict[str, object], product: NationalHighwaysProduct
) -> list[dict[str, object]]:
    if product == "vms":
        items: list[dict[str, object]] = []
        for controller in _list_of_mappings(root.get("vmsControllerStatus"), "vmsControllerStatus"):
            controller_ref = _mapping(controller.get("vmsControllerReference"), "controller ref")
            controller_id = _text(controller_ref.get("idG"), "controller id", 300)
            for status in _list_of_mappings(controller.get("vmsStatus"), "vmsStatus"):
                body = dict(_mapping(status.get("vmsStatus"), "vms status body"))
                body["_controller_id"] = controller_id
                body["_vms_index"] = status.get("vmsIndex")
                items.append(body)
        return items
    wrapper_key = (
        "sitRoadOrCarriagewayOrLaneManagement" if product == "closures" else "sitSpeedManagement"
    )
    items = []
    for situation in _list_of_mappings(root.get("situation"), "situation"):
        situation_id = _text(situation.get("idG"), "situation id", 300)
        for wrapper in _list_of_mappings(situation.get("situationRecord"), "situationRecord"):
            if tuple(wrapper) != (wrapper_key,):
                raise NationalHighwaysError(
                    "RECORD_SCHEMA_DRIFT", f"expected exactly {wrapper_key} wrapper"
                )
            body = dict(_mapping(wrapper[wrapper_key], wrapper_key))
            body["_situation_id"] = situation_id
            items.append(body)
    return items


def _project_item(
    item: dict[str, object],
    *,
    product: NationalHighwaysProduct,
    publication_time: datetime,
    envelope: NationalHighwaysEnvelope,
    synthetic: bool,
) -> NationalHighwaysRecord | None:
    coordinates = _coordinates(item, product)
    in_scope = tuple((lat, lon) for lat, lon in coordinates if envelope.contains(lat, lon))
    if not in_scope:
        return None
    centre_lat = (envelope.min_latitude + envelope.max_latitude) / Decimal(2)
    centre_lon = (envelope.min_longitude + envelope.max_longitude) / Decimal(2)
    latitude, longitude = min(
        in_scope,
        key=lambda point: abs(point[0] - centre_lat) + abs(point[1] - centre_lon),
    )
    source_id = _source_identifier(item, product)
    item_bytes = _canonical_bytes(item)
    item_sha = sha256_hex(item_bytes)
    record_token = sha256_hex(f"{product}:{source_id}".encode())[:24]
    geometry_sha = sha256_hex(
        json.dumps(
            [[str(lat), str(lon)] for lat, lon in coordinates],
            separators=(",", ":"),
        ).encode("utf-8")
    )
    if product == "vms":
        return _vms_record(
            item,
            publication_time=publication_time,
            latitude=latitude,
            longitude=longitude,
            coordinate_count=len(coordinates),
            geometry_sha=geometry_sha,
            item_sha=item_sha,
            record_token=record_token,
            synthetic=synthetic,
        )
    return _situation_record(
        item,
        product=product,
        publication_time=publication_time,
        latitude=latitude,
        longitude=longitude,
        coordinate_count=len(coordinates),
        geometry_sha=geometry_sha,
        item_sha=item_sha,
        record_token=record_token,
        synthetic=synthetic,
    )


def _situation_record(
    item: dict[str, object],
    *,
    product: Literal["closures", "speed_limits"],
    publication_time: datetime,
    latitude: Decimal,
    longitude: Decimal,
    coordinate_count: int,
    geometry_sha: str,
    item_sha: str,
    record_token: str,
    synthetic: bool,
) -> NationalHighwaysRecord:
    location = _mapping(item.get("locationReference"), "locationReference")
    linear = _mapping(location.get("locLinearLocation"), "locLinearLocation")
    supplementary = _mapping(
        linear.get("supplementaryPositionalDescription"),
        "supplementaryPositionalDescription",
    )
    description = _text(supplementary.get("locationDescription"), "locationDescription", MAX_TEXT)
    road_name: str | None = None
    direction: str | None = None
    single = location.get("locSingleRoadLinearLocation")
    if isinstance(single, dict):
        linears = _list_of_mappings(single.get("linearWithinLinearElement"), "linear element")
        if linears:
            direction = _optional_text(linears[0].get("directionOnLinearSection"), 80)
            element = linears[0].get("linearElement")
            if isinstance(element, dict):
                coded = element.get("locLinearElementByCode")
                if isinstance(coded, dict):
                    road_name = _optional_text(coded.get("roadName"), 80)
    validity = _mapping(item.get("validity"), "validity")
    validity_time = _mapping(validity.get("validityTimeSpecification"), "validityTimeSpecification")
    valid_from = _optional_utc(validity_time.get("overallStartTime"), "overallStartTime")
    valid_until = _optional_utc(validity_time.get("overallEndTime"), "overallEndTime")
    cause = item.get("cause")
    cause_type = None
    if isinstance(cause, dict):
        cause_type = _optional_text(cause.get("causeType"), 80)
    speed: Decimal | None = None
    if product == "closures":
        kind = item.get("roadOrCarriagewayOrLaneManagementType")
        value = _mapping(kind, "road management type").get("value")
        operational_type = _text(value, "road management type value", 160)
    else:
        speed = _decimal(item.get("temporarySpeedLimit"), "temporarySpeedLimit")
        detailed = cause.get("detailedCauseType") if isinstance(cause, dict) else None
        speed_kind = detailed.get("speedManagementType") if isinstance(detailed, dict) else None
        operational_type = _optional_text(speed_kind, 160) or "temporarySpeedLimit"
    if cause_type:
        operational_type = f"{operational_type}:{cause_type}"[:160]
    return NationalHighwaysRecord(
        product=product,
        source_id=cast(Any, _SOURCE_BY_PRODUCT[product]),
        record_token=record_token,
        source_record_fingerprint=item_sha,
        publication_time_utc=publication_time,
        record_updated_at_utc=_optional_utc(
            item.get("situationRecordVersionTime"), "situationRecordVersionTime"
        ),
        valid_from_utc=valid_from,
        valid_until_utc=valid_until,
        latitude=latitude,
        longitude=longitude,
        source_geometry_point_count=coordinate_count,
        source_geometry_sha256=geometry_sha,
        location_description=description,
        road_name=road_name,
        direction=direction,
        operational_type=operational_type,
        validity_status=_optional_text(validity.get("validityStatus"), 80),
        temporary_speed_limit_kph=speed,
        synthetic=synthetic,
    )


def _vms_record(
    item: dict[str, object],
    *,
    publication_time: datetime,
    latitude: Decimal,
    longitude: Decimal,
    coordinate_count: int,
    geometry_sha: str,
    item_sha: str,
    record_token: str,
    synthetic: bool,
) -> NationalHighwaysRecord:
    extension = _mapping(item.get("vmsStatusExtensionG"), "vmsStatusExtensionG")
    point = _mapping(
        _mapping(extension.get("vmsLocation"), "vmsLocation").get("locPointLocation"),
        "locPointLocation",
    )
    supplementary = _mapping(
        point.get("supplementaryPositionalDescription"),
        "supplementaryPositionalDescription",
    )
    road_name = None
    road_info = supplementary.get("roadInformation")
    if isinstance(road_info, list) and road_info:
        road_name = _optional_text(_mapping(road_info[0], "roadInformation").get("roadName"), 80)
    direction = None
    extension_position = supplementary.get("supplementaryPositionalDescriptionExtensionG")
    if isinstance(extension_position, dict):
        direction = _optional_text(extension_position.get("direction"), 80)
    message_types: set[str] = set()
    reason: str | None = None
    message_time: datetime | None = None
    for wrapper in _list_of_mappings(item.get("vmsMessage"), "vmsMessage"):
        message = _mapping(wrapper.get("vmsMessage"), "vmsMessage body")
        raw_types = message.get("messageInformationType")
        if isinstance(raw_types, list):
            for raw_type in raw_types:
                message_types.add(_text(raw_type, "messageInformationType", 80).strip())
        candidate_reason = _optional_text(message.get("reasonForSetting"), MAX_TEXT)
        candidate_time = _optional_utc(message.get("timeLastSet"), "timeLastSet")
        if candidate_time is not None and (message_time is None or candidate_time > message_time):
            message_time = candidate_time
            reason = candidate_reason
    description = _optional_text(extension.get("description"), 160)
    working = _optional_text(item.get("workingStatus"), 80)
    vms_type = _optional_text(extension.get("vmsType"), 160) or "digitalVms"
    return NationalHighwaysRecord(
        product="vms",
        source_id="national_highways_vms",
        record_token=record_token,
        source_record_fingerprint=item_sha,
        publication_time_utc=publication_time,
        record_updated_at_utc=message_time,
        latitude=latitude,
        longitude=longitude,
        source_geometry_point_count=coordinate_count,
        source_geometry_sha256=geometry_sha,
        location_description=_text(
            supplementary.get("locationDescription"), "locationDescription", MAX_TEXT
        ),
        road_name=road_name,
        direction=direction,
        operational_type=vms_type,
        vms_working_status=working,
        vms_description=description,
        vms_message_information_types=tuple(sorted(message_types)),
        vms_reason_for_setting=reason,
        vms_message_set_at_utc=message_time,
        synthetic=synthetic,
    )


def _coordinates(
    item: dict[str, object], product: NationalHighwaysProduct
) -> tuple[tuple[Decimal, Decimal], ...]:
    if product == "vms":
        extension = item.get("vmsStatusExtensionG")
        if not isinstance(extension, dict):
            return ()
        location = extension.get("vmsLocation")
        point = location.get("locPointLocation") if isinstance(location, dict) else None
        by_coordinates = point.get("pointByCoordinates") if isinstance(point, dict) else None
        coordinates = (
            by_coordinates.get("pointCoordinates") if isinstance(by_coordinates, dict) else None
        )
        if not isinstance(coordinates, dict):
            return ()
        try:
            return (
                (
                    _decimal(coordinates.get("latitude"), "latitude"),
                    _decimal(coordinates.get("longitude"), "longitude"),
                ),
            )
        except NationalHighwaysError:
            return ()
    location = item.get("locationReference")
    linear = location.get("locLinearLocation") if isinstance(location, dict) else None
    gml = linear.get("gmlLineString") if isinstance(linear, dict) else None
    line = gml.get("locGmlLineString") if isinstance(gml, dict) else None
    if not isinstance(line, dict):
        return ()
    if line.get("srsName") not in {"ESPG::4326", "EPSG::4326"} or line.get("srsDimension") != 2:
        return ()
    pos_list = line.get("posList")
    if not isinstance(pos_list, str):
        return ()
    try:
        numbers = tuple(Decimal(value) for value in pos_list.split())
    except InvalidOperation:
        return ()
    if not numbers or len(numbers) % 2:
        return ()
    result = tuple(zip(numbers[::2], numbers[1::2], strict=True))
    if any(not (-90 <= lat <= 90 and -180 <= lon <= 180) for lat, lon in result):
        return ()
    return result


def _source_identifier(item: dict[str, object], product: NationalHighwaysProduct) -> str:
    if product == "vms":
        return f"{item.get('_controller_id')}:{item.get('_vms_index')}"
    return f"{item.get('_situation_id')}:{item.get('idG')}:{item.get('versionG')}"


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise NationalHighwaysError("DUPLICATE_JSON_KEY", "duplicate JSON key encountered")
        result[key] = value
    return result


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise NationalHighwaysError("SCHEMA_DRIFT", f"{label} must be an object")
    return cast(dict[str, object], value)


def _list_of_mappings(value: object, label: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise NationalHighwaysError("SCHEMA_DRIFT", f"{label} must be an array")
    if any(not isinstance(item, dict) for item in value):
        raise NationalHighwaysError("SCHEMA_DRIFT", f"{label} entries must be objects")
    return cast(list[dict[str, object]], value)


def _text(value: object, label: str, limit: int) -> str:
    if not isinstance(value, str):
        raise NationalHighwaysError("SCHEMA_DRIFT", f"{label} must be text")
    result = " ".join(value.split())
    if not result or len(result) > limit:
        raise NationalHighwaysError("TEXT_INVALID", f"{label} is empty or too long")
    return result


def _optional_text(value: object, limit: int) -> str | None:
    if value is None:
        return None
    return _text(value, "optional text", limit)


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise NationalHighwaysError("SCHEMA_DRIFT", f"{label} must be numeric")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise NationalHighwaysError("NUMBER_INVALID", f"{label} is invalid") from exc
    if not result.is_finite():
        raise NationalHighwaysError("NUMBER_INVALID", f"{label} must be finite")
    return result


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise NationalHighwaysError("TIME_INVALID", f"{label} must be a Z-form UTC instant")
    try:
        result = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise NationalHighwaysError("TIME_INVALID", f"{label} is not ISO-8601") from exc
    return result.astimezone(UTC)


def _optional_utc(value: object, label: str) -> datetime | None:
    return None if value is None else _utc(value, label)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

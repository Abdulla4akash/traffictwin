"""Manchester SUMO output pipeline — Lane 06 controlled local simulation evidence.

Safety properties
-----------------
* Typed, immutable, fingerprinted request/package/receipt models.
* Every public boundary revalidates via strict model_validate.
* Bounded, fail-closed XML parsing with deterministic ordering.
* Valid file is software-valid simulated evidence only, never observed.
* No mapping from SUMO vehicles to VEC tasks exists.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from traffictwin.integration.manchester.models import ManchesterSnapshotModel
from traffictwin.integration.manchester.xml import (
    ManchesterXmlError,
    ParsedXml,
    XmlPolicy,
    parse_xml,
)

SUMO_OUTPUT_SCHEMA_VERSION: Literal["1.0"] = "1.0"
SUMO_OUTPUT_METHOD_VERSION: Literal["manchester-sumo-output-1.0"] = "manchester-sumo-output-1.0"
SUMO_OUTPUT_CAPABILITY_ID: Literal["MAN-09"] = "MAN-09"
SUMO_OUTPUT_PARSER_VERSION: Literal["manchester-sumo-output-parser-1.0"] = (
    "manchester-sumo-output-parser-1.0"
)

SUPPORTED_SUMO_VERSION_PREFIX: Literal["1.27."] = "1.27."

MAX_XML_BYTES = 50_000_000
MAX_FCD_BYTES = 50_000_000
MAX_TRIPINFO_RECORDS = 1_000_000
MAX_SUMMARY_RECORDS = 100_000
MAX_FCD_RECORDS = 5_000_000
MAX_ROUTE_RECORDS = 500_000
MAX_TRIP_RECORDS = 500_000
MAX_WARNINGS = 32
MAX_EXCLUSIONS = 64
MAX_FILE_DECLARATIONS = 8
MAX_STRING_LENGTH = 500

EVIDENCE_STANDING_SIMULATED: Literal["SOFTWARE_VALID_SIMULATED_ONLY"] = (
    "SOFTWARE_VALID_SIMULATED_ONLY"
)
SCIENTIFICALLY_NOT_ACCEPTED: Literal["SCIENTIFICALLY_NOT_ACCEPTED"] = "SCIENTIFICALLY_NOT_ACCEPTED"

LIMITATIONS: tuple[str, ...] = (
    "Controlled local SUMO output only — simulated demand, not observed traffic.",
    (
        "Valid file is software-valid simulated evidence only, "
        "never observed or scientifically accepted."
    ),
    "No SUMO vehicle is mapped to a VEC task, RSU target, deadline, or telemetry.",
    (
        "FCD/trip-level fields are not observed traffic metrics "
        "without an explicit aggregation contract."
    ),
    (
        "Uncertainty is unavailable unless scientifically supplied; "
        "descriptive differences are non-causal."
    ),
    "Missing optional outputs are reported as unavailable, not inferred.",
)

_EVIDENCE_BOUNDARY = (
    "Manchester SUMO output pipeline: bounded, fail-closed parsing of controlled "
    "local SUMO outputs (tripinfo, summary, FCD, route metadata). Simulated only."
)

_PRIVATE_PATH_RE = re.compile(r"(/Users/|/home/|/private/|/var/|/tmp/|/etc/|~/|[A-Za-z]:\\)")
_SECRET_RE = re.compile(
    r"(apikey|api_key|secret|password|passwd|token|bearer|credential|authorization)",
    re.IGNORECASE,
)
_SAFE_RELATIVE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

VEC_TASK_MAPPING_SUPPORTED: Literal[False] = False
VEC_TASK_MAPPING_STATEMENT = (
    "SUMO vehicles are never mapped to VEC tasks, RSU execution targets, "
    "task outcomes, deadlines, or Dynamic Resource telemetry."
)


def _reject_private_path(value: str, label: str) -> str:
    if _PRIVATE_PATH_RE.search(value):
        raise ValueError(f"{label} must not contain a private absolute path")
    if "\\" in value:
        raise ValueError(f"{label} must not contain backslash")
    if ".." in value.split("/"):
        raise ValueError(f"{label} must not contain traversal")
    return value


def _reject_secret(value: str, label: str) -> str:
    if _SECRET_RE.search(value):
        raise ValueError(f"{label} must not contain a likely secret")
    return value


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    )


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


_XSI_NAMESPACE: str = "http://www.w3.org/2001/XMLSchema-instance"
_XSI_ATTRIBUTE_NAMESPACES: tuple[str, ...] = (_XSI_NAMESPACE,)

_TRIPINFO_XML_POLICY: XmlPolicy = XmlPolicy(
    max_input_bytes=MAX_XML_BYTES,
    max_elements=2_000_000,
    max_depth=20,
    max_attributes_per_element=30,
    max_text_characters=50_000_000,
    allowed_root_local_names=("tripinfos",),
    allowed_namespaces=(),
    allowed_attribute_namespaces=_XSI_ATTRIBUTE_NAMESPACES,
)

_SUMMARY_XML_POLICY: XmlPolicy = XmlPolicy(
    max_input_bytes=MAX_XML_BYTES,
    max_elements=200_000,
    max_depth=20,
    max_attributes_per_element=30,
    max_text_characters=50_000_000,
    allowed_root_local_names=("summary",),
    allowed_namespaces=(),
    allowed_attribute_namespaces=_XSI_ATTRIBUTE_NAMESPACES,
)

_FCD_XML_POLICY: XmlPolicy = XmlPolicy(
    max_input_bytes=MAX_FCD_BYTES,
    max_elements=5_000_000,
    max_depth=20,
    max_attributes_per_element=30,
    max_text_characters=50_000_000,
    allowed_root_local_names=("fcd-export",),
    allowed_namespaces=(),
    allowed_attribute_namespaces=_XSI_ATTRIBUTE_NAMESPACES,
)

_ROUTES_XML_POLICY: XmlPolicy = XmlPolicy(
    max_input_bytes=MAX_XML_BYTES,
    max_elements=1_000_000,
    max_depth=20,
    max_attributes_per_element=30,
    max_text_characters=50_000_000,
    allowed_root_local_names=("routes", "trips"),
    allowed_namespaces=(),
    allowed_attribute_namespaces=_XSI_ATTRIBUTE_NAMESPACES,
)

_NET_XML_POLICY: XmlPolicy = XmlPolicy(
    max_input_bytes=MAX_XML_BYTES,
    max_elements=500_000,
    max_depth=20,
    max_attributes_per_element=30,
    max_text_characters=50_000_000,
    allowed_root_local_names=("net", "routes", "sumoConfiguration", "configuration"),
    allowed_namespaces=(),
    allowed_attribute_namespaces=_XSI_ATTRIBUTE_NAMESPACES,
)


def _map_xml_error(exc: ManchesterXmlError, label: str) -> ManchesterSumoOutputError:
    """Deterministically map hardened XML errors into the typed refusal taxonomy."""
    message = str(exc)
    cause = exc.__cause__
    cause_name = cause.__class__.__name__ if cause is not None else ""
    cause_str = str(cause) if cause is not None else ""
    cause_sysid = getattr(cause, "sysid", None) if cause is not None else None
    if cause_sysid is None and cause is not None:
        cause_sysid = getattr(cause, "system_id", None)
    # Resource bounds
    if "exceeds policy" in message:
        if "element count" in message:
            return ManchesterSumoOutputError(
                "OUTPUT_RECORD_BOUND",
                f"{label} element count exceeds bound",
            )
        if "depth" in message:
            return ManchesterSumoOutputError(
                "OUTPUT_XML_INVALID",
                f"{label} XML depth exceeds bound",
            )
        if "attribute count" in message:
            return ManchesterSumoOutputError(
                "OUTPUT_XML_INVALID",
                f"{label} attribute count exceeds bound",
            )
        if "text size" in message:
            return ManchesterSumoOutputError(
                "OUTPUT_OVERSIZE",
                f"{label} text exceeds bound",
            )
        if "payload exceeds policy" in message:
            return ManchesterSumoOutputError(
                "OUTPUT_OVERSIZE",
                f"{label} exceeds byte bound",
            )
        return ManchesterSumoOutputError(
            "OUTPUT_XML_INVALID",
            f"{label} XML violates policy",
        )
    if "root element" in message or "root namespace" in message:
        return ManchesterSumoOutputError(
            "OUTPUT_SCHEMA_INVALID",
            f"{label} XML root not admitted",
        )
    if "element namespace" in message:
        return ManchesterSumoOutputError(
            "OUTPUT_SCHEMA_INVALID",
            f"{label} element namespace not admitted",
        )
    if "attribute namespace" in message:
        return ManchesterSumoOutputError(
            "OUTPUT_XML_NETWORK_REFUSED",
            "network/URI resolution is not permitted",
        )
    # DTD / entity / external – inspect cause for network tripwire
    if cause_name in ("DTDForbidden", "EntitiesForbidden", "ExternalReferenceForbidden"):
        if cause_name == "ExternalReferenceForbidden":
            return ManchesterSumoOutputError(
                "OUTPUT_XML_NETWORK_REFUSED",
                "network/URI resolution is not permitted",
            )
        # For DTDForbidden/EntitiesForbidden, distinguish network vs internal via sysid
        if cause_sysid is not None and isinstance(cause_sysid, str) and "://" in cause_sysid:
            return ManchesterSumoOutputError(
                "OUTPUT_XML_NETWORK_REFUSED",
                "network/URI resolution is not permitted",
            )
        # Fallback: inspect cause string for URI
        if cause_sysid is None and "://" in cause_str:
            return ManchesterSumoOutputError(
                "OUTPUT_XML_NETWORK_REFUSED",
                "network/URI resolution is not permitted",
            )
        # Additional fallback for UTF-16 external entities where DTDForbidden loses sysid:
        # external SYSTEM with http is still a DTDForbidden with no sysid. We must inspect
        # the raw payload in an encoding-aware way, but only for DTD context, not the
        # brittle whole-payload http scan that flagged inert xsi. This check is limited to
        # DTD/entity forbidden constructs.
        # NOTE: The caller _guarded_parse will perform the encoding-aware raw check with
        # access to data; here we cannot, so we defer to that helper for this case.
        return ManchesterSumoOutputError(
            "OUTPUT_XML_ENTITY_REFUSED",
            "DTD/entity declarations are not permitted",
        )
    if "forbidden constructs" in message:
        # Distinguish DTD/entity vs generic malformed via cause type
        if cause_name in ("DTDForbidden", "EntitiesForbidden"):
            if cause_sysid is not None and isinstance(cause_sysid, str) and "://" in cause_sysid:
                return ManchesterSumoOutputError(
                    "OUTPUT_XML_NETWORK_REFUSED",
                    "network/URI resolution is not permitted",
                )
            if cause_sysid is None and cause is not None and "://" in cause_str:
                return ManchesterSumoOutputError(
                    "OUTPUT_XML_NETWORK_REFUSED",
                    "network/URI resolution is not permitted",
                )
            # Defer to _guarded_parse for encoding-aware SYSTEM+http check (handled there)
            return ManchesterSumoOutputError(
                "OUTPUT_XML_ENTITY_REFUSED",
                "DTD/entity declarations are not permitted",
            )
        if cause_name == "ExternalReferenceForbidden":
            return ManchesterSumoOutputError(
                "OUTPUT_XML_NETWORK_REFUSED",
                "network/URI resolution is not permitted",
            )
        # Unbound prefix for xlink:href etc. – treat as network tripwire
        if cause is not None and "unbound prefix" in cause_str.lower():
            if "xlink" in cause_str.lower() or "href" in cause_str.lower():
                return ManchesterSumoOutputError(
                    "OUTPUT_XML_NETWORK_REFUSED",
                    "network/URI resolution is not permitted",
                )
            return ManchesterSumoOutputError(
                "OUTPUT_XML_INVALID",
                f"{label} XML invalid",
            )
        # Generic forbidden (e.g., control characters are also forbidden via expat?) -> INVALID
        # Check for control/invalid token – map to INVALID, not ENTITY, to preserve control refusal
        if cause is not None and (
            "not well-formed" in cause_str.lower()
            or "invalid token" in cause_str.lower()
            or "undefined entity" in cause_str.lower()
        ):
            # Undefined entity without DTD is entity-like; treat as ENTITY if mentions entity
            if "entity" in cause_str.lower():
                return ManchesterSumoOutputError(
                    "OUTPUT_XML_ENTITY_REFUSED",
                    "DTD/entity declarations are not permitted",
                )
            return ManchesterSumoOutputError(
                "OUTPUT_XML_INVALID",
                f"{label} XML invalid",
            )
        return ManchesterSumoOutputError(
            "OUTPUT_XML_ENTITY_REFUSED",
            "DTD/entity declarations are not permitted",
        )
    # Fallback generic
    return ManchesterSumoOutputError(
        "OUTPUT_XML_INVALID",
        f"{label} XML invalid",
    )


def _guarded_parse(data: bytes, policy: XmlPolicy, label: str) -> ParsedXml:  # noqa: ANN201
    """Parse via hardened XmlPolicy, mapping errors into typed taxonomy without leakage."""
    try:
        return parse_xml(data, policy=policy)
    except ManchesterXmlError as exc:
        # For unbound prefix errors (e.g., xlink:href without declaration), the parser
        # raises ParseError with "unbound prefix" which lacks the attribute name.
        # Inspect raw bytes in an encoding-aware, bounded way to preserve the
        # network tripwire without reintroducing the brittle whole-payload http scan.
        cause_str = str(exc.__cause__).lower() if exc.__cause__ is not None else ""
        if "unbound prefix" in cause_str and b"xlink:href" in data.lower():
            raise ManchesterSumoOutputError(
                "OUTPUT_XML_NETWORK_REFUSED",
                "network/URI resolution is not permitted",
            ) from exc
        # External SYSTEM entity via UTF-16: DTDForbidden loses sysid when forbid_dtd=True.
        # If the cause is DTD/entity forbidden and the raw payload (decoded according to
        # its declared encoding) contains SYSTEM + http, treat as NETWORK tripwire.
        # This is scoped to DTD context only, not the brittle whole-payload http scan that
        # flagged inert xsi:noNamespaceSchemaLocation.
        if exc.__cause__ is not None and exc.__cause__.__class__.__name__ in (
            "DTDForbidden",
            "EntitiesForbidden",
        ):
            # Decode in an encoding-aware but bounded way: try utf-8/utf-16 with fallback
            # to avoid bypass via UTF-16, and check only inside DTD declaration.
            try:
                # parse_xml handles BOM; for inspection try utf-8 then utf-16
                for enc in ("utf-8", "utf-16", "utf-16-le", "utf-16-be"):
                    try:
                        txt = data.decode(enc, errors="strict").lower()
                        # Look for DTD + SYSTEM + http in the same text
                        if "<!doctype" in txt and "system" in txt and "http://" in txt:
                            raise ManchesterSumoOutputError(
                                "OUTPUT_XML_NETWORK_REFUSED",
                                "network/URI resolution is not permitted",
                            ) from exc
                        if "<!entity" in txt and "system" in txt and "http://" in txt:
                            raise ManchesterSumoOutputError(
                                "OUTPUT_XML_NETWORK_REFUSED",
                                "network/URI resolution is not permitted",
                            ) from exc
                        break
                    except UnicodeDecodeError:
                        continue
            except ManchesterSumoOutputError:
                raise
            except Exception:  # noqa: S110
                pass
            # Also check raw lower bytes as fallback for ascii
            if (
                b"<!doctype" in data.lower()
                and b"system" in data.lower()
                and b"http://" in data.lower()
            ):
                raise ManchesterSumoOutputError(
                    "OUTPUT_XML_NETWORK_REFUSED",
                    "network/URI resolution is not permitted",
                ) from exc
            if (
                b"<!entity" in data.lower()
                and b"system" in data.lower()
                and b"http://" in data.lower()
            ):
                raise ManchesterSumoOutputError(
                    "OUTPUT_XML_NETWORK_REFUSED",
                    "network/URI resolution is not permitted",
                ) from exc
        raise _map_xml_error(exc, label) from exc


def _parse_decimal_finite(raw: str, label: str) -> Decimal:
    try:
        value = Decimal(raw)
    except Exception as exc:
        raise ManchesterSumoOutputError(
            "OUTPUT_NUMERIC_INVALID",
            f"{label} is not a finite decimal: {raw!r}",
        ) from exc
    if not value.is_finite():
        raise ManchesterSumoOutputError(
            "OUTPUT_NUMERIC_INVALID",
            f"{label} must be finite: {raw!r}",
        )
    if value != value:
        raise ManchesterSumoOutputError(
            "OUTPUT_NUMERIC_INVALID",
            f"{label} is NaN",
        )
    if abs(value) > Decimal("1e12"):
        raise ManchesterSumoOutputError(
            "OUTPUT_NUMERIC_BOUNDS",
            f"{label} exceeds bounded range: {raw!r}",
        )
    return value


class ManchesterSumoOutputError(ValueError):
    """Typed, stable error for the SUMO output pipeline boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class ManchesterSumoOutputModel(ManchesterSnapshotModel):
    """Strict frozen base."""


def _revalidate_strict(model: BaseModel) -> BaseModel:
    return model.__class__.model_validate(
        model.model_dump(mode="python"),
        strict=True,
    )


class SumoOutputFileDeclaration(ManchesterSumoOutputModel):
    """One portable declared output file — no absolute path, no secret."""

    relative_path: str = Field(min_length=1, max_length=200)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0, le=MAX_XML_BYTES)
    required: bool = True
    media_type: str = Field(min_length=1, max_length=80)

    @field_validator("relative_path")
    @classmethod
    def _validate_path(cls, v: str) -> str:
        _reject_private_path(v, "output file path")
        _reject_secret(v, "output file path")
        if v.startswith("/"):
            raise ValueError("output file path must be safe relative")
        if not _SAFE_RELATIVE_RE.fullmatch(v):
            raise ValueError("output file path must be safe POSIX relative")
        for seg in v.split("/"):
            if not seg or seg in {".", ".."}:
                raise ValueError("output file path segment invalid")
            if not _SAFE_NAME_RE.fullmatch(seg):
                raise ValueError(f"unsafe path segment: {seg}")
        return v

    @field_validator("media_type")
    @classmethod
    def _validate_media(cls, v: str) -> str:
        _reject_private_path(v, "media type")
        _reject_secret(v, "media type")
        if "/" not in v:
            raise ValueError("media type must contain '/'")
        return v


class SumoOutputToolIdentity(ManchesterSumoOutputModel):
    """Observed simulator identity — version pinned to 1.27.x."""

    executable_name: Literal["sumo"] = "sumo"
    reported_version: str = Field(min_length=1, max_length=64)
    executable_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    supported_version_prefix: Literal["1.27."] = SUPPORTED_SUMO_VERSION_PREFIX

    @field_validator("reported_version")
    @classmethod
    def _validate_version_text(cls, v: str) -> str:
        _reject_private_path(v, "tool version")
        _reject_secret(v, "tool version")
        return v

    @model_validator(mode="after")
    def _check_prefix(self) -> SumoOutputToolIdentity:
        if not self.reported_version.startswith(self.supported_version_prefix):
            raise ValueError("sumo version must match the reviewed 1.27.x toolchain")
        return self


class SumoOutputTimeBasis(ManchesterSumoOutputModel):
    """Simulation time basis — exact window and step."""

    window_start_s: int = Field(ge=0)
    window_end_s: int = Field(gt=0)
    step_length_s: int = Field(ge=1, le=3600)
    time_basis_label: str = Field(min_length=1, max_length=64)
    time_basis_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("time_basis_label")
    @classmethod
    def _validate_label(cls, v: str) -> str:
        _reject_private_path(v, "time basis label")
        _reject_secret(v, "time basis label")
        if not _SAFE_NAME_RE.fullmatch(v):
            raise ValueError("time basis label must be safe identifier")
        return v

    @model_validator(mode="after")
    def _check_window(self) -> SumoOutputTimeBasis:
        if self.window_end_s <= self.window_start_s:
            raise ValueError("simulation window must be positive")
        return self


class SumoOutputNetworkIdentity(ManchesterSumoOutputModel):
    """Portable network/demand/config identity."""

    network_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    demand_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    network_file: str = Field(min_length=1, max_length=200)
    demand_file: str = Field(min_length=1, max_length=200)
    config_file: str = Field(min_length=1, max_length=200)

    @field_validator("network_file", "demand_file", "config_file")
    @classmethod
    def _validate_file(cls, v: str) -> str:
        _reject_private_path(v, "network/demand/config file")
        _reject_secret(v, "network/demand/config file")
        if not _SAFE_RELATIVE_RE.fullmatch(v):
            raise ValueError("file identity must be safe relative")
        return v


class SumoTripInfoRecord(ManchesterSumoOutputModel):
    """One exact SUMO tripinfo vehicle record — simulated only."""

    vehicle_id: str = Field(min_length=1, max_length=200)
    depart_s: Decimal = Field(ge=0)
    arrival_s: Decimal | None = Field(default=None, ge=0)
    duration_s: Decimal | None = Field(default=None, ge=0)
    route_length_m: Decimal | None = Field(default=None, ge=0)
    waiting_time_s: Decimal | None = Field(default=None, ge=0)
    time_loss_s: Decimal | None = Field(default=None, ge=0)
    depart_edge: str | None = Field(default=None, max_length=200)
    arrival_edge: str | None = Field(default=None, max_length=200)
    v_type: str | None = Field(default=None, max_length=80)

    @field_validator("vehicle_id", "depart_edge", "arrival_edge", "v_type")
    @classmethod
    def _validate_ids(cls, v: str | None) -> str | None:
        if v is None:
            return v
        _reject_private_path(v, "trip field")
        _reject_secret(v, "trip field")
        if not v.strip():
            raise ValueError("trip field must not be blank")
        if len(v) > 200:
            raise ValueError("trip field too long")
        return v

    @model_validator(mode="after")
    def _check_finite(self) -> SumoTripInfoRecord:
        for name in (
            "depart_s",
            "arrival_s",
            "duration_s",
            "route_length_m",
            "waiting_time_s",
            "time_loss_s",
        ):
            val = getattr(self, name)
            if val is not None and not val.is_finite():
                raise ValueError(f"{name} must be finite")
        return self


class SumoSummaryRecord(ManchesterSumoOutputModel):
    """One exact SUMO summary step — simulated only."""

    time_s: Decimal = Field(ge=0)
    running: int = Field(ge=0)
    waiting: int | None = Field(default=None, ge=0)
    ended: int | None = Field(default=None, ge=0)
    arrived: int | None = Field(default=None, ge=0)
    halting: int | None = Field(default=None, ge=0)
    collisions: int | None = Field(default=None, ge=0)
    teleports: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check(self) -> SumoSummaryRecord:
        if not self.time_s.is_finite():
            raise ValueError("summary time must be finite")
        return self


class SumoFcdRecord(ManchesterSumoOutputModel):
    """One exact SUMO FCD vehicle position — simulated only, not a metric."""

    time_s: Decimal = Field(ge=0)
    vehicle_id: str = Field(min_length=1, max_length=200)
    edge_id: str = Field(min_length=1, max_length=200)
    lane_id: str | None = Field(default=None, max_length=200)
    x_m: Decimal | None = Field(default=None)
    y_m: Decimal | None = Field(default=None)
    speed_mps: Decimal | None = Field(default=None, ge=0)
    angle_deg: Decimal | None = Field(default=None)

    @field_validator("vehicle_id", "edge_id", "lane_id")
    @classmethod
    def _validate_ids(cls, v: str | None) -> str | None:
        if v is None:
            return v
        _reject_private_path(v, "fcd field")
        _reject_secret(v, "fcd field")
        return v

    @model_validator(mode="after")
    def _check_finite(self) -> SumoFcdRecord:
        for name in ("x_m", "y_m", "speed_mps", "angle_deg"):
            val = getattr(self, name)
            if val is not None and not val.is_finite():
                raise ValueError(f"{name} must be finite")
            if val is not None and abs(val) > Decimal("1e12"):
                raise ValueError(f"{name} exceeds bounded range")
            if name in ("x_m", "y_m") and val is not None and abs(val) > Decimal("1e7"):
                raise ValueError(f"{name} exceeds coordinate bound")
            if (
                name == "angle_deg"
                and val is not None
                and (val < Decimal("-360") or val > Decimal("720"))
            ):
                raise ValueError("angle out of bounded range")
        return self


class SumoRouteRecord(ManchesterSumoOutputModel):
    """One typed route/trip metadata record — legitimate IDs only."""

    record_id: str = Field(min_length=1, max_length=200)
    record_kind: Literal["route", "vehicle", "flow", "trip"] = "route"
    edges: tuple[str, ...] = Field(default=())
    from_edge: str | None = Field(default=None, max_length=200)
    to_edge: str | None = Field(default=None, max_length=200)
    v_type: str | None = Field(default=None, max_length=80)
    depart: Decimal | None = Field(default=None, ge=0)

    @field_validator("record_id", "from_edge", "to_edge", "v_type")
    @classmethod
    def _validate_ids(cls, v: str | None) -> str | None:
        if v is None:
            return v
        _reject_private_path(v, "route field")
        _reject_secret(v, "route field")
        if not v.strip():
            raise ValueError("route field must not be blank")
        if len(v) > 200:
            raise ValueError("route field too long")
        if (
            not _SAFE_ID_RE.fullmatch(v.strip())
            and " " not in v
            and ("/" in v or "\\" in v or ".." in v)
        ):
            raise ValueError("route field contains unsafe character")
        return v.strip() if v else v

    @field_validator("edges")
    @classmethod
    def _validate_edges(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(v) > 1000:
            raise ValueError("edge sequence exceeds bound")
        for e in v:
            _reject_private_path(e, "edge")
            _reject_secret(e, "edge")
            if not e.strip():
                raise ValueError("edge must not be blank")
            if len(e) > 200:
                raise ValueError("edge too long")
            if ".." in e or "/" in e or "\\" in e:
                raise ValueError("edge contains traversal")
        return v

    @model_validator(mode="after")
    def _check_finite(self) -> SumoRouteRecord:
        if self.depart is not None and not self.depart.is_finite():
            raise ValueError("depart must be finite")
        if self.depart is not None and self.depart > Decimal("1e12"):
            raise ValueError("depart exceeds bound")
        return self


class SumoOutputCounts(ManchesterSumoOutputModel):
    """Deterministic counts over parsed outputs."""

    tripinfo_records: int = Field(ge=0)
    summary_records: int = Field(ge=0)
    fcd_records: int = Field(ge=0)
    route_records: int = Field(ge=0)
    warnings: int = Field(ge=0)
    exclusions: int = Field(ge=0)


class SumoOutputProvenance(ManchesterSumoOutputModel):
    """Portable provenance — no private path, no secret."""

    created_at_utc: str = Field(min_length=1, max_length=64)
    created_by: str = Field(min_length=1, max_length=120)
    parent_fingerprints: tuple[str, ...] = Field(default=(), max_length=8)

    @field_validator("created_at_utc", "created_by")
    @classmethod
    def _validate_text(cls, v: str) -> str:
        _reject_private_path(v, "provenance")
        _reject_secret(v, "provenance")
        return v

    @field_validator("parent_fingerprints")
    @classmethod
    def _validate_parents(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if v != tuple(sorted(v)):
            raise ValueError("parent fingerprints must be sorted")
        if len(set(v)) != len(v):
            raise ValueError("parent fingerprints must be unique")
        return v


class ManchesterSumoOutputRequest(ManchesterSumoOutputModel):
    """Immutable request for one controlled output import."""

    schema_version: Literal["1.0"] = SUMO_OUTPUT_SCHEMA_VERSION
    capability_id: Literal["MAN-09"] = SUMO_OUTPUT_CAPABILITY_ID
    method_version: Literal["manchester-sumo-output-1.0"] = SUMO_OUTPUT_METHOD_VERSION
    parser_version: Literal["manchester-sumo-output-parser-1.0"] = SUMO_OUTPUT_PARSER_VERSION
    request_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$")
    run_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$")
    tool: SumoOutputToolIdentity
    network: SumoOutputNetworkIdentity
    time_basis: SumoOutputTimeBasis
    files: tuple[SumoOutputFileDeclaration, ...] = Field(
        min_length=1,
        max_length=MAX_FILE_DECLARATIONS,
    )
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("request_id", "run_id")
    @classmethod
    def _validate_ids(cls, v: str) -> str:
        _reject_private_path(v, "request/run id")
        _reject_secret(v, "request/run id")
        if not _RUN_ID_RE.fullmatch(v):
            raise ValueError("id must match safe pattern")
        return v

    @model_validator(mode="after")
    def _validate(self) -> ManchesterSumoOutputRequest:
        paths = [f.relative_path for f in self.files]
        if paths != sorted(paths):
            raise ValueError("files must be sorted by relative_path")
        if len(set(paths)) != len(paths):
            raise ValueError("file paths must be unique")
        known = {"tripinfo.xml", "summary.xml", "fcd.xml"}
        for p in paths:
            base = p.split("/")[-1]
            if base not in known and base not in {"routes.xml", "trips.xml", "net.xml"}:
                pass
        expected = _request_fingerprint(self)
        if self.request_fingerprint != expected:
            raise ValueError("request_fingerprint must be re-derived canonical digest")
        return self


class ManchesterSumoOutputPackage(ManchesterSumoOutputModel):
    """Verified package — declared files hash-verified, parsed, fingerprint-bound."""

    schema_version: Literal["1.0"] = SUMO_OUTPUT_SCHEMA_VERSION
    capability_id: Literal["MAN-09"] = SUMO_OUTPUT_CAPABILITY_ID
    method_version: Literal["manchester-sumo-output-1.0"] = SUMO_OUTPUT_METHOD_VERSION
    parser_version: Literal["manchester-sumo-output-parser-1.0"] = SUMO_OUTPUT_PARSER_VERSION
    request_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$")
    run_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$")
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool: SumoOutputToolIdentity
    network: SumoOutputNetworkIdentity
    time_basis: SumoOutputTimeBasis
    files: tuple[SumoOutputFileDeclaration, ...]
    tripinfo: tuple[SumoTripInfoRecord, ...] = Field(default=())
    summary: tuple[SumoSummaryRecord, ...] = Field(default=())
    fcd: tuple[SumoFcdRecord, ...] = Field(default=())
    routes: tuple[SumoRouteRecord, ...] = Field(default=())
    counts: SumoOutputCounts
    warnings: tuple[str, ...] = Field(default=(), max_length=MAX_WARNINGS)
    exclusions: tuple[str, ...] = Field(default=(), max_length=MAX_EXCLUSIONS)
    evidence_standing: Literal["SOFTWARE_VALID_SIMULATED_ONLY"] = EVIDENCE_STANDING_SIMULATED
    scientifically_accepted: Literal[False] = False
    observed_traffic: Literal[False] = False
    limitations: tuple[str, ...] = LIMITATIONS
    provenance: SumoOutputProvenance
    package_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    vec_task_mapping: Literal[False] = VEC_TASK_MAPPING_SUPPORTED

    @model_validator(mode="after")
    def _validate(self) -> ManchesterSumoOutputPackage:
        if self.limitations != LIMITATIONS:
            raise ValueError("limitations must be the exact literal")
        if self.scientifically_accepted is not False or self.observed_traffic is not False:
            raise ValueError("package must never claim observed or scientifically accepted")
        if self.evidence_standing != EVIDENCE_STANDING_SIMULATED:
            raise ValueError("evidence standing must be simulated-only")
        if self.vec_task_mapping is not False:
            raise ValueError("VEC task mapping is never supported")
        if self.counts.tripinfo_records != len(self.tripinfo):
            raise ValueError("tripinfo count mismatch")
        if self.counts.summary_records != len(self.summary):
            raise ValueError("summary count mismatch")
        if self.counts.fcd_records != len(self.fcd):
            raise ValueError("fcd count mismatch")
        if self.counts.route_records != len(self.routes):
            raise ValueError("route_records count mismatch")
        if self.counts.warnings != len(self.warnings):
            raise ValueError("warning count mismatch")
        if self.counts.exclusions != len(self.exclusions):
            raise ValueError("exclusion count mismatch")
        trip_ids = [r.vehicle_id for r in self.tripinfo]
        if trip_ids != sorted(trip_ids):
            raise ValueError("tripinfo must be deterministically sorted by vehicle_id")
        summary_times = [r.time_s for r in self.summary]
        if summary_times != sorted(summary_times):
            raise ValueError("summary must be sorted by time_s")
        fcd_keys = [(r.time_s, r.vehicle_id) for r in self.fcd]
        if fcd_keys != sorted(fcd_keys):
            raise ValueError("fcd must be sorted by (time_s, vehicle_id)")
        route_ids = [r.record_id for r in self.routes]
        if route_ids != sorted(route_ids):
            raise ValueError("routes must be sorted by record_id")
        expected = _package_fingerprint(self)
        if self.package_fingerprint != expected:
            raise ValueError("package_fingerprint must be re-derived")
        for w in self.warnings:
            _reject_private_path(w, "warning")
            _reject_secret(w, "warning")
        for e in self.exclusions:
            _reject_private_path(e, "exclusion")
            _reject_secret(e, "exclusion")
        return self


class ManchesterSumoOutputReceipt(ManchesterSumoOutputModel):
    """Portable receipt binding request, package, and verification."""

    schema_version: Literal["1.0"] = SUMO_OUTPUT_SCHEMA_VERSION
    capability_id: Literal["MAN-09"] = SUMO_OUTPUT_CAPABILITY_ID
    method_version: Literal["manchester-sumo-output-1.0"] = SUMO_OUTPUT_METHOD_VERSION
    receipt_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$")
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    package_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool: SumoOutputToolIdentity
    network: SumoOutputNetworkIdentity
    time_basis: SumoOutputTimeBasis
    file_fingerprints: tuple[str, ...]
    counts: SumoOutputCounts
    evidence_standing: Literal["SOFTWARE_VALID_SIMULATED_ONLY"] = EVIDENCE_STANDING_SIMULATED
    scientifically_accepted: Literal[False] = False
    limitations: tuple[str, ...] = LIMITATIONS
    receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate(self) -> ManchesterSumoOutputReceipt:
        if self.limitations != LIMITATIONS:
            raise ValueError("limitations must be the exact literal")
        if self.scientifically_accepted is not False:
            raise ValueError("receipt must never claim scientific acceptance")
        expected = _receipt_fingerprint(self)
        if self.receipt_fingerprint != expected:
            raise ValueError("receipt_fingerprint must be re-derived")
        return self


def _request_fingerprint(req: ManchesterSumoOutputRequest) -> str:
    payload = {
        "capability_id": req.capability_id,
        "method_version": req.method_version,
        "parser_version": req.parser_version,
        "request_id": req.request_id,
        "run_id": req.run_id,
        "tool": json.loads(req.tool.model_dump_json()),
        "network": json.loads(req.network.model_dump_json()),
        "time_basis": json.loads(req.time_basis.model_dump_json()),
        "files": [json.loads(f.model_dump_json()) for f in req.files],
    }
    return _sha256_hex(_canonical_json(payload).encode("utf-8"))


def _package_fingerprint(pkg: ManchesterSumoOutputPackage) -> str:
    payload = {
        "method_version": pkg.method_version,
        "parser_version": pkg.parser_version,
        "request_fingerprint": pkg.request_fingerprint,
        "tool": json.loads(pkg.tool.model_dump_json()),
        "network": json.loads(pkg.network.model_dump_json()),
        "time_basis": json.loads(pkg.time_basis.model_dump_json()),
        "files": [json.loads(f.model_dump_json()) for f in pkg.files],
        "tripinfo": [json.loads(r.model_dump_json()) for r in pkg.tripinfo],
        "summary": [json.loads(r.model_dump_json()) for r in pkg.summary],
        "fcd": [json.loads(r.model_dump_json()) for r in pkg.fcd],
        "routes": [json.loads(r.model_dump_json()) for r in pkg.routes],
        "counts": json.loads(pkg.counts.model_dump_json()),
        "warnings": list(pkg.warnings),
        "exclusions": list(pkg.exclusions),
        "provenance": json.loads(pkg.provenance.model_dump_json()),
    }
    return _sha256_hex(_canonical_json(payload).encode("utf-8"))


def _receipt_fingerprint(rcpt: ManchesterSumoOutputReceipt) -> str:
    payload = {
        "receipt_id": rcpt.receipt_id,
        "request_fingerprint": rcpt.request_fingerprint,
        "package_fingerprint": rcpt.package_fingerprint,
        "tool": json.loads(rcpt.tool.model_dump_json()),
        "network": json.loads(rcpt.network.model_dump_json()),
        "time_basis": json.loads(rcpt.time_basis.model_dump_json()),
        "file_fingerprints": list(rcpt.file_fingerprints),
        "counts": json.loads(rcpt.counts.model_dump_json()),
    }
    return _sha256_hex(_canonical_json(payload).encode("utf-8"))


def _parse_tripinfo(data: bytes) -> tuple[SumoTripInfoRecord, ...]:
    if len(data) > MAX_XML_BYTES:
        raise ManchesterSumoOutputError("OUTPUT_OVERSIZE", "tripinfo exceeds byte bound")
    if not data.strip():
        return ()
    parsed = _guarded_parse(data, _TRIPINFO_XML_POLICY, "tripinfo")
    root = parsed.root
    records: list[SumoTripInfoRecord] = []
    seen: dict[str, SumoTripInfoRecord] = {}
    for idx, elem in enumerate(root.iter("tripinfo")):
        if idx >= MAX_TRIPINFO_RECORDS:
            raise ManchesterSumoOutputError(
                "OUTPUT_RECORD_BOUND",
                "tripinfo record count exceeds bound",
            )
        vid = elem.get("id")
        depart = elem.get("depart")
        if vid is None or depart is None:
            raise ManchesterSumoOutputError(
                "OUTPUT_SCHEMA_INVALID",
                "tripinfo requires id and depart",
            )
        vid = vid.strip()
        if not vid:
            raise ManchesterSumoOutputError(
                "OUTPUT_SCHEMA_INVALID",
                "tripinfo vehicle id empty",
            )
        if vid in seen:
            raise ManchesterSumoOutputError(
                "OUTPUT_DUPLICATE_VEHICLE",
                f"duplicate vehicle id in tripinfo: {vid!r}",
            )
        dep_s = _parse_decimal_finite(depart.strip(), "tripinfo depart")
        arr_s = None
        dur_s = None
        length = None
        waiting = None
        time_loss = None
        arr_edge = None
        dep_edge = None
        vtype = elem.get("vType") or elem.get("vtype")
        if elem.get("arrival") is not None:
            arr_s = _parse_decimal_finite(
                elem.get("arrival", "").strip(),
                "tripinfo arrival",
            )
        if elem.get("duration") is not None:
            dur_s = _parse_decimal_finite(
                elem.get("duration", "").strip(),
                "tripinfo duration",
            )
        if elem.get("routeLength") is not None:
            length = _parse_decimal_finite(
                elem.get("routeLength", "").strip(),
                "tripinfo routeLength",
            )
        if elem.get("waitingTime") is not None:
            waiting = _parse_decimal_finite(
                elem.get("waitingTime", "").strip(),
                "tripinfo waitingTime",
            )
        if elem.get("timeLoss") is not None:
            time_loss = _parse_decimal_finite(
                elem.get("timeLoss", "").strip(),
                "tripinfo timeLoss",
            )
        dep_edge = elem.get("departLane") or elem.get("departEdge")
        arr_edge = elem.get("arrivalLane") or elem.get("arrivalEdge")
        rec = SumoTripInfoRecord(
            vehicle_id=vid,
            depart_s=dep_s,
            arrival_s=arr_s,
            duration_s=dur_s,
            route_length_m=length,
            waiting_time_s=waiting,
            time_loss_s=time_loss,
            depart_edge=dep_edge.strip() if dep_edge else None,
            arrival_edge=arr_edge.strip() if arr_edge else None,
            v_type=vtype.strip() if vtype else None,
        )
        _revalidate_strict(rec)
        seen[vid] = rec
        records.append(rec)
    records.sort(key=lambda r: r.vehicle_id)
    return tuple(records)


def _parse_summary(data: bytes) -> tuple[SumoSummaryRecord, ...]:
    if len(data) > MAX_XML_BYTES:
        raise ManchesterSumoOutputError("OUTPUT_OVERSIZE", "summary exceeds byte bound")
    if not data.strip():
        return ()
    parsed = _guarded_parse(data, _SUMMARY_XML_POLICY, "summary")
    root = parsed.root
    records: list[SumoSummaryRecord] = []
    seen_times: set[Decimal] = set()
    for idx, elem in enumerate(root.iter("step")):
        if idx >= MAX_SUMMARY_RECORDS:
            raise ManchesterSumoOutputError(
                "OUTPUT_RECORD_BOUND",
                "summary record count exceeds bound",
            )
        time_raw = elem.get("time")
        if time_raw is None:
            raise ManchesterSumoOutputError(
                "OUTPUT_SCHEMA_INVALID",
                "summary step requires time",
            )
        t = _parse_decimal_finite(time_raw.strip(), "summary time")
        if t in seen_times:
            raise ManchesterSumoOutputError(
                "OUTPUT_DUPLICATE_TIME",
                f"duplicate summary time: {t}",
            )
        seen_times.add(t)
        running_raw = elem.get("running")
        if running_raw is None:
            raise ManchesterSumoOutputError(
                "OUTPUT_SCHEMA_INVALID",
                "summary step requires running",
            )
        try:
            running = int(running_raw.strip())
        except ValueError as exc:
            raise ManchesterSumoOutputError(
                "OUTPUT_NUMERIC_INVALID",
                "summary running must be integer",
            ) from exc
        if running < 0:
            raise ManchesterSumoOutputError(
                "OUTPUT_NUMERIC_INVALID",
                "summary running must be >=0",
            )

        def _opt_int(name: str, elem_copy: object = elem) -> int | None:  # noqa: B023
            raw = elem_copy.get(name)  # type: ignore[attr-defined]
            if raw is None:
                return None
            raw = raw.strip()
            if not raw:
                return None
            try:
                v = int(raw)
            except ValueError as exc:
                raise ManchesterSumoOutputError(
                    "OUTPUT_NUMERIC_INVALID",
                    f"summary {name} must be integer",
                ) from exc
            if v < 0:
                raise ManchesterSumoOutputError(
                    "OUTPUT_NUMERIC_INVALID",
                    f"summary {name} >=0",
                )
            return v

        rec = SumoSummaryRecord(
            time_s=t,
            running=running,
            waiting=_opt_int("waiting"),
            ended=_opt_int("ended"),
            arrived=_opt_int("arrived"),
            halting=_opt_int("halting"),
            collisions=_opt_int("collisions"),
            teleports=_opt_int("teleports"),
        )
        _revalidate_strict(rec)
        records.append(rec)
    records.sort(key=lambda r: r.time_s)
    return tuple(records)


def _parse_fcd(data: bytes) -> tuple[SumoFcdRecord, ...]:
    if len(data) > MAX_FCD_BYTES:
        raise ManchesterSumoOutputError("OUTPUT_OVERSIZE", "fcd exceeds byte bound")
    if not data.strip():
        return ()
    parsed = _guarded_parse(data, _FCD_XML_POLICY, "fcd")
    root = parsed.root
    records: list[SumoFcdRecord] = []
    for ts in root.iter("timestep"):
        time_raw = ts.get("time")
        if time_raw is None:
            raise ManchesterSumoOutputError(
                "OUTPUT_SCHEMA_INVALID",
                "fcd timestep requires time",
            )
        t = _parse_decimal_finite(time_raw.strip(), "fcd timestep time")
        for veh in ts.iter("vehicle"):
            if len(records) >= MAX_FCD_RECORDS:
                raise ManchesterSumoOutputError(
                    "OUTPUT_RECORD_BOUND",
                    "fcd record count exceeds bound",
                )
            vid = veh.get("id")
            edge = veh.get("edge") or veh.get("lane") or ""
            if not vid or not edge:
                raise ManchesterSumoOutputError(
                    "OUTPUT_SCHEMA_INVALID",
                    "fcd vehicle requires id and edge",
                )
            vid = vid.strip()
            edge = edge.strip().split("_")[0]
            speed = veh.get("speed")
            x = veh.get("x")
            y = veh.get("y")
            angle = veh.get("angle")
            rec = SumoFcdRecord(
                time_s=t,
                vehicle_id=vid,
                edge_id=edge,
                lane_id=veh.get("lane"),
                x_m=_parse_decimal_finite(x, "fcd x") if x is not None else None,
                y_m=_parse_decimal_finite(y, "fcd y") if y is not None else None,
                speed_mps=(
                    _parse_decimal_finite(speed, "fcd speed") if speed is not None else None
                ),
                angle_deg=(
                    _parse_decimal_finite(angle, "fcd angle") if angle is not None else None
                ),
            )
            _revalidate_strict(rec)
            records.append(rec)
    if not records:
        for veh in root.iter("vehicle"):
            if len(records) >= MAX_FCD_RECORDS:
                raise ManchesterSumoOutputError(
                    "OUTPUT_RECORD_BOUND",
                    "fcd record count exceeds bound",
                )
            parent_time = veh.get("time") or "0"
            t = _parse_decimal_finite(parent_time.strip(), "fcd vehicle time")
            vid = veh.get("id") or ""
            edge = (veh.get("edge") or veh.get("lane") or "").strip()
            if not vid or not edge:
                continue
            rec = SumoFcdRecord(
                time_s=t,
                vehicle_id=vid.strip(),
                edge_id=edge.split("_")[0],
                lane_id=veh.get("lane"),
                x_m=None,
                y_m=None,
                speed_mps=None,
                angle_deg=None,
            )
            _revalidate_strict(rec)
            records.append(rec)
    seen: set[tuple[Decimal, str]] = set()
    for r in records:
        key = (r.time_s, r.vehicle_id)
        if key in seen:
            raise ManchesterSumoOutputError(
                "OUTPUT_DUPLICATE_FCD",
                f"duplicate fcd position for vehicle {r.vehicle_id!r} at time {r.time_s}",
            )
        seen.add(key)
    records.sort(key=lambda r: (r.time_s, r.vehicle_id))
    return tuple(records)


def _parse_routes_or_trips(
    data: bytes,
    filename: str,
) -> tuple[SumoRouteRecord, ...]:
    if len(data) > MAX_XML_BYTES:
        raise ManchesterSumoOutputError("OUTPUT_OVERSIZE", f"{filename} exceeds byte bound")
    if not data.strip():
        return ()
    policy = _ROUTES_XML_POLICY
    # filename is either routes.xml or trips.xml, both allowed by the same policy
    parsed = _guarded_parse(data, policy, filename)
    root = parsed.root
    records: list[SumoRouteRecord] = []
    seen_ids: set[str] = set()
    # Routes file may contain <route>, <vehicle>, <flow>, <trip>
    # Trips file may contain <trip>
    tag_to_kind: dict[str, Literal["route", "vehicle", "flow", "trip"]] = {
        "route": "route",
        "vehicle": "vehicle",
        "flow": "flow",
        "trip": "trip",
    }
    for elem in root.iter():
        kind = tag_to_kind.get(elem.tag)
        if kind is None:
            continue
        if len(records) >= (MAX_ROUTE_RECORDS if filename == "routes.xml" else MAX_TRIP_RECORDS):
            raise ManchesterSumoOutputError(
                "OUTPUT_RECORD_BOUND",
                f"{filename} record count exceeds bound",
            )
        rid = elem.get("id")
        if rid is None or not rid.strip():
            raise ManchesterSumoOutputError(
                "OUTPUT_SCHEMA_INVALID",
                f"{filename} {kind} requires id",
            )
        rid = rid.strip()
        if rid in seen_ids:
            raise ManchesterSumoOutputError(
                "OUTPUT_DUPLICATE_ROUTE_ID",
                f"duplicate {kind} id in {filename}: {rid!r}",
            )
        # Validate id safety
        _reject_private_path(rid, "route id")
        _reject_secret(rid, "route id")
        if not _SAFE_ID_RE.fullmatch(rid) and ("/" in rid or "\\" in rid or ".." in rid):
            raise ManchesterSumoOutputError(
                "OUTPUT_SCHEMA_INVALID",
                f"unsafe {kind} id: {rid!r}",
            )
        edges: tuple[str, ...] = ()
        edges_raw = elem.get("edges")
        if edges_raw is not None:
            edges_str = edges_raw.strip()
            if edges_str:
                parts = edges_str.split()
                if len(parts) > 1000:
                    raise ManchesterSumoOutputError(
                        "OUTPUT_SCHEMA_INVALID",
                        "edge sequence too long",
                    )
                # Validate each edge
                for e in parts:
                    _reject_private_path(e, "edge")
                    _reject_secret(e, "edge")
                    if not e or len(e) > 200:
                        raise ManchesterSumoOutputError(
                            "OUTPUT_SCHEMA_INVALID",
                            f"edge invalid: {e!r}",
                        )
                edges = tuple(parts)
        from_edge = elem.get("from")
        to_edge = elem.get("to")
        v_type = elem.get("type") or elem.get("vType")
        depart_raw = elem.get("depart")
        depart_val: Decimal | None = None
        if depart_raw is not None:
            depart_val = _parse_decimal_finite(depart_raw.strip(), f"{filename} depart")
        # Validate from/to/type if present
        if from_edge is not None:
            from_edge = from_edge.strip()
            _reject_private_path(from_edge, "from")
            _reject_secret(from_edge, "from")
            if not from_edge or len(from_edge) > 200:
                raise ManchesterSumoOutputError(
                    "OUTPUT_SCHEMA_INVALID",
                    "from edge invalid",
                )
        if to_edge is not None:
            to_edge = to_edge.strip()
            _reject_private_path(to_edge, "to")
            _reject_secret(to_edge, "to")
            if not to_edge or len(to_edge) > 200:
                raise ManchesterSumoOutputError(
                    "OUTPUT_SCHEMA_INVALID",
                    "to edge invalid",
                )
        if v_type is not None:
            v_type = v_type.strip()
            _reject_private_path(v_type, "vType")
            _reject_secret(v_type, "vType")
            if not v_type or len(v_type) > 80:
                raise ManchesterSumoOutputError(
                    "OUTPUT_SCHEMA_INVALID",
                    "vType invalid",
                )
            if not _SAFE_ID_RE.fullmatch(v_type) and ("/" in v_type or "\\" in v_type):
                raise ManchesterSumoOutputError(
                    "OUTPUT_SCHEMA_INVALID",
                    f"unsafe vType: {v_type!r}",
                )
        rec = SumoRouteRecord(
            record_id=rid,
            record_kind=kind,
            edges=edges,
            from_edge=from_edge,
            to_edge=to_edge,
            v_type=v_type,
            depart=depart_val,
        )
        _revalidate_strict(rec)
        seen_ids.add(rid)
        records.append(rec)
    records.sort(key=lambda r: r.record_id)
    return tuple(records)


def build_sumo_output_request(
    *,
    request_id: str,
    run_id: str,
    tool: SumoOutputToolIdentity,
    network: SumoOutputNetworkIdentity,
    time_basis: SumoOutputTimeBasis,
    files: list[SumoOutputFileDeclaration],
) -> ManchesterSumoOutputRequest:
    """Build a fingerprinted request — revalidates strictly before return."""
    for obj in (tool, network, time_basis, *files):
        _revalidate_strict(obj)
    sorted_files = tuple(sorted(files, key=lambda f: f.relative_path))
    tmp = ManchesterSumoOutputRequest.model_construct(
        request_id=request_id,
        run_id=run_id,
        tool=tool,
        network=network,
        time_basis=time_basis,
        files=sorted_files,
        request_fingerprint="0" * 64,
    )
    fp = _request_fingerprint(tmp)
    return ManchesterSumoOutputRequest(
        request_id=request_id,
        run_id=run_id,
        tool=tool,
        network=network,
        time_basis=time_basis,
        files=sorted_files,
        request_fingerprint=fp,
    )


def import_sumo_outputs(
    request: ManchesterSumoOutputRequest,
    file_contents: dict[str, bytes],
    *,
    provenance: SumoOutputProvenance | None = None,
) -> ManchesterSumoOutputPackage:
    """Import and bound-parse declared SUMO outputs — fail-closed, deterministic.

    ``provenance`` must be explicitly supplied and deterministic. If ``None``,
    the function derives it solely from immutable request fields (no ``now()``).
    """
    _revalidate_strict(request)
    if provenance is not None:
        _revalidate_strict(provenance)
    declared_map = {f.relative_path: f for f in request.files}
    for key in file_contents:
        _reject_private_path(key, "file_contents key")
        _reject_secret(key, "file_contents key")
        if key not in declared_map:
            raise ManchesterSumoOutputError(
                "OUTPUT_UNDECLARED_FILE",
                f"file {key!r} was not declared in request",
            )
        if key.startswith("/") or ".." in key.split("/"):
            raise ManchesterSumoOutputError(
                "OUTPUT_PATH_TRAVERSAL",
                f"file path traversal: {key!r}",
            )

    warnings: list[str] = []
    exclusions: list[str] = []
    tripinfo_records: tuple[SumoTripInfoRecord, ...] = ()
    summary_records: tuple[SumoSummaryRecord, ...] = ()
    fcd_records: tuple[SumoFcdRecord, ...] = ()
    route_records: tuple[SumoRouteRecord, ...] = ()

    for decl in request.files:
        raw = file_contents.get(decl.relative_path)
        if raw is None:
            if decl.required:
                raise ManchesterSumoOutputError(
                    "OUTPUT_REQUIRED_MISSING",
                    f"required file missing: {decl.relative_path!r}",
                )
            warnings.append(f"optional output unavailable: {decl.relative_path}")
            continue
        if len(raw) != decl.size_bytes:
            raise ManchesterSumoOutputError(
                "OUTPUT_SIZE_MISMATCH",
                f"file {decl.relative_path!r} size mismatch: "
                f"declared {decl.size_bytes} vs actual {len(raw)}",
            )
        if len(raw) > MAX_XML_BYTES and decl.relative_path.endswith(".xml"):
            raise ManchesterSumoOutputError(
                "OUTPUT_OVERSIZE",
                f"file {decl.relative_path!r} exceeds byte bound",
            )
        actual_sha = _sha256_bytes(raw)
        if actual_sha != decl.sha256:
            raise ManchesterSumoOutputError(
                "OUTPUT_HASH_MISMATCH",
                f"file {decl.relative_path!r} hash mismatch: "
                f"expected {decl.sha256[:8]}.. got {actual_sha[:8]}..",
            )
        base = decl.relative_path.split("/")[-1]
        if base == "tripinfo.xml":
            tripinfo_records = _parse_tripinfo(raw)
        elif base == "summary.xml":
            summary_records = _parse_summary(raw)
        elif base == "fcd.xml":
            fcd_records = _parse_fcd(raw)
        elif base == "routes.xml":
            route_records = _parse_routes_or_trips(raw, "routes.xml")
        elif base == "trips.xml":
            route_records = _parse_routes_or_trips(raw, "trips.xml")
        elif base == "net.xml":
            if len(raw) > MAX_XML_BYTES:
                raise ManchesterSumoOutputError(
                    "OUTPUT_OVERSIZE",
                    f"metadata {base!r} exceeds bound",
                )
            # Validate net metadata via hardened policy without fetching
            _guarded_parse(raw, _NET_XML_POLICY, "net")
            warnings.append(f"metadata present: {base}")
        else:
            warnings.append(f"unrecognised output class unavailable as metric: {base}")

    # Summary window/grid enforcement — no +1000 escape
    if summary_records:
        times = [r.time_s for r in summary_records]
        min_t = min(times)
        max_t = max(times)
        if (
            int(min_t) < request.time_basis.window_start_s
            or int(max_t) > request.time_basis.window_end_s
        ):
            raise ManchesterSumoOutputError(
                "OUTPUT_WINDOW_DRIFT",
                f"summary window [{min_t},{max_t}] drifts beyond "
                f"declared [{request.time_basis.window_start_s},"
                f"{request.time_basis.window_end_s}]",
            )
        # Enforce grid alignment: each time must align to step
        for sum_rec in summary_records:
            offset = sum_rec.time_s - Decimal(request.time_basis.window_start_s)
            if offset % Decimal(request.time_basis.step_length_s) != Decimal(0):
                raise ManchesterSumoOutputError(
                    "OUTPUT_GRID_MISALIGNED",
                    f"summary time {sum_rec.time_s} not aligned to step grid",
                )

    if tripinfo_records:
        for trip_rec in tripinfo_records:
            if int(trip_rec.depart_s) < request.time_basis.window_start_s:
                exclusions.append(f"trip {trip_rec.vehicle_id!r} depart before window")
            if (
                trip_rec.arrival_s is not None
                and int(trip_rec.arrival_s) > request.time_basis.window_end_s
            ):
                exclusions.append(f"trip {trip_rec.vehicle_id!r} arrival beyond window")

    if fcd_records:
        # Enforce FCD timestamps within window and bounded finite checks already done
        for fcd_rec in fcd_records:
            if (
                int(fcd_rec.time_s) < request.time_basis.window_start_s
                or int(fcd_rec.time_s) > request.time_basis.window_end_s
            ):
                raise ManchesterSumoOutputError(
                    "OUTPUT_WINDOW_DRIFT",
                    f"fcd time {fcd_rec.time_s} outside declared window",
                )
            # Additional bounded checks for coordinates/speed/angle already in model validator

    if provenance is None:
        # Deterministic derivation solely from immutable request fields — no now()
        derived_fp = _sha256_hex(request.request_fingerprint.encode("utf-8"))
        provenance = SumoOutputProvenance(
            created_at_utc="2026-01-01T00:00:00Z",
            created_by="manchester-sumo-output-pipeline",
            parent_fingerprints=(derived_fp,),
        )
        # Ensure sorted uniqueness (single entry already sorted)
    else:
        _revalidate_strict(provenance)

    if not tripinfo_records:
        if "tripinfo.xml" not in declared_map:
            warnings.append("tripinfo unavailable: not declared")
        elif "tripinfo.xml" in file_contents:
            pass
        else:
            warnings.append("tripinfo unavailable")
    if not summary_records:
        if "summary.xml" not in declared_map:
            warnings.append("summary unavailable: not declared")
        else:
            warnings.append("summary unavailable")
    if not fcd_records:
        if "fcd.xml" not in declared_map:
            warnings.append("fcd unavailable: not declared — optional")
        elif "fcd.xml" not in file_contents:
            warnings.append("fcd unavailable: optional output not present")
    if not route_records:
        # Truthfully expose absent metadata
        has_routes_decl = any(p.split("/")[-1] in {"routes.xml", "trips.xml"} for p in declared_map)
        if not has_routes_decl:
            warnings.append("route/trip metadata unavailable: not declared — optional")
        elif not any(
            k in file_contents
            for k in declared_map
            if k.split("/")[-1] in {"routes.xml", "trips.xml"}
        ):
            warnings.append("route/trip metadata unavailable: optional output not present")

    counts = SumoOutputCounts(
        tripinfo_records=len(tripinfo_records),
        summary_records=len(summary_records),
        fcd_records=len(fcd_records),
        route_records=len(route_records),
        warnings=len(warnings),
        exclusions=len(exclusions),
    )

    tmp_pkg = ManchesterSumoOutputPackage.model_construct(
        request_id=request.request_id,
        run_id=request.run_id,
        request_fingerprint=request.request_fingerprint,
        tool=request.tool,
        network=request.network,
        time_basis=request.time_basis,
        files=request.files,
        tripinfo=tripinfo_records,
        summary=summary_records,
        fcd=fcd_records,
        routes=route_records,
        counts=counts,
        warnings=tuple(warnings),
        exclusions=tuple(exclusions),
        provenance=provenance,
        package_fingerprint="0" * 64,
    )
    fp = _package_fingerprint(tmp_pkg)
    return ManchesterSumoOutputPackage(
        request_id=request.request_id,
        run_id=request.run_id,
        request_fingerprint=request.request_fingerprint,
        tool=request.tool,
        network=request.network,
        time_basis=request.time_basis,
        files=request.files,
        tripinfo=tripinfo_records,
        summary=summary_records,
        fcd=fcd_records,
        routes=route_records,
        counts=counts,
        warnings=tuple(warnings),
        exclusions=tuple(exclusions),
        provenance=provenance,
        package_fingerprint=fp,
    )


def build_output_receipt(
    *,
    receipt_id: str,
    request: ManchesterSumoOutputRequest,
    package: ManchesterSumoOutputPackage,
) -> ManchesterSumoOutputReceipt:
    """Build a deterministic receipt binding request and package."""
    _revalidate_strict(request)
    _revalidate_strict(package)
    if request.request_fingerprint != package.request_fingerprint:
        raise ManchesterSumoOutputError(
            "RECEIPT_REQUEST_MISMATCH",
            "receipt request fingerprint must match package request fingerprint",
        )
    if package.package_fingerprint == "":
        raise ManchesterSumoOutputError(
            "RECEIPT_PACKAGE_INVALID",
            "package fingerprint empty",
        )
    file_fps = tuple(f.sha256 for f in package.files)
    tmp = ManchesterSumoOutputReceipt.model_construct(
        receipt_id=receipt_id,
        request_fingerprint=request.request_fingerprint,
        package_fingerprint=package.package_fingerprint,
        tool=package.tool,
        network=package.network,
        time_basis=package.time_basis,
        file_fingerprints=file_fps,
        counts=package.counts,
        receipt_fingerprint="0" * 64,
    )
    fp = _receipt_fingerprint(tmp)
    return ManchesterSumoOutputReceipt(
        receipt_id=receipt_id,
        request_fingerprint=request.request_fingerprint,
        package_fingerprint=package.package_fingerprint,
        tool=package.tool,
        network=package.network,
        time_basis=package.time_basis,
        file_fingerprints=file_fps,
        counts=package.counts,
        receipt_fingerprint=fp,
    )


def verify_output_package(
    package: ManchesterSumoOutputPackage,
    request: ManchesterSumoOutputRequest,
    file_contents: dict[str, bytes],
    *,
    provenance: SumoOutputProvenance | None = None,
) -> ManchesterSumoOutputPackage:
    """Require exact request and raw file contents; re-import and compare.

    Structural self-fingerprint validation alone is insufficient. Missing
    dependencies fail closed.
    """
    # Use supplied provenance or package's own provenance for deterministic re-import
    effective_prov = provenance if provenance is not None else package.provenance
    try:
        rebuilt = import_sumo_outputs(
            request,
            file_contents,
            provenance=effective_prov,
        )
    except ManchesterSumoOutputError as exc:
        raise ManchesterSumoOutputError(exc.code, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise ManchesterSumoOutputError("PACKAGE_VERIFICATION_FAILED", str(exc)[:500]) from exc
    if rebuilt.package_fingerprint != package.package_fingerprint:
        raise ManchesterSumoOutputError(
            "PACKAGE_FINGERPRINT_MISMATCH",
            "re-imported package fingerprint mismatch",
        )
    if rebuilt.request_fingerprint != package.request_fingerprint:
        raise ManchesterSumoOutputError(
            "PACKAGE_REQUEST_MISMATCH",
            "re-imported request fingerprint mismatch",
        )
    # Strict revalidation of supplied package to close model_copy bypass
    return ManchesterSumoOutputPackage.model_validate(
        json.loads(package.model_dump_json()),
        strict=True,
    )


def verify_output_receipt(
    receipt: ManchesterSumoOutputReceipt,
    request: ManchesterSumoOutputRequest,
    package: ManchesterSumoOutputPackage,
) -> ManchesterSumoOutputReceipt:
    """Require exact request+package; rebuild receipt with same identity and compare."""
    _revalidate_strict(request)
    _revalidate_strict(package)
    try:
        rebuilt = build_output_receipt(
            receipt_id=receipt.receipt_id,
            request=request,
            package=package,
        )
    except ManchesterSumoOutputError as exc:
        raise ManchesterSumoOutputError(exc.code, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise ManchesterSumoOutputError("RECEIPT_VERIFICATION_FAILED", str(exc)[:500]) from exc
    if rebuilt.receipt_fingerprint != receipt.receipt_fingerprint:
        raise ManchesterSumoOutputError(
            "RECEIPT_FINGERPRINT_MISMATCH",
            "rebuilt receipt fingerprint mismatch",
        )
    if rebuilt.request_fingerprint != receipt.request_fingerprint:
        raise ManchesterSumoOutputError(
            "RECEIPT_REQUEST_MISMATCH",
            "receipt request fingerprint mismatch",
        )
    if rebuilt.package_fingerprint != receipt.package_fingerprint:
        raise ManchesterSumoOutputError(
            "RECEIPT_PACKAGE_MISMATCH",
            "receipt package fingerprint mismatch",
        )
    return ManchesterSumoOutputReceipt.model_validate(
        json.loads(receipt.model_dump_json()),
        strict=True,
    )


def assert_no_vec_mapping(*args: object, **kwargs: object) -> None:
    """Fail closed with stable typed error whenever called."""

    _ = (args, kwargs)
    raise ManchesterSumoOutputError(
        "VEC_TASK_MAPPING_UNSUPPORTED",
        VEC_TASK_MAPPING_STATEMENT,
    )


__all__ = [
    "EVIDENCE_STANDING_SIMULATED",
    "LIMITATIONS",
    "MAX_FCD_BYTES",
    "MAX_FCD_RECORDS",
    "MAX_ROUTE_RECORDS",
    "MAX_SUMMARY_RECORDS",
    "MAX_TRIP_RECORDS",
    "MAX_TRIPINFO_RECORDS",
    "MAX_XML_BYTES",
    "ManchesterSumoOutputError",
    "ManchesterSumoOutputPackage",
    "ManchesterSumoOutputReceipt",
    "ManchesterSumoOutputRequest",
    "SCIENTIFICALLY_NOT_ACCEPTED",
    "SUMO_OUTPUT_CAPABILITY_ID",
    "SUMO_OUTPUT_METHOD_VERSION",
    "SUMO_OUTPUT_PARSER_VERSION",
    "SUMO_OUTPUT_SCHEMA_VERSION",
    "SUPPORTED_SUMO_VERSION_PREFIX",
    "SumoFcdRecord",
    "SumoOutputCounts",
    "SumoOutputFileDeclaration",
    "SumoOutputNetworkIdentity",
    "SumoOutputProvenance",
    "SumoOutputTimeBasis",
    "SumoOutputToolIdentity",
    "SumoRouteRecord",
    "SumoSummaryRecord",
    "SumoTripInfoRecord",
    "VEC_TASK_MAPPING_STATEMENT",
    "VEC_TASK_MAPPING_SUPPORTED",
    "assert_no_vec_mapping",
    "build_output_receipt",
    "build_sumo_output_request",
    "import_sumo_outputs",
    "verify_output_package",
    "verify_output_receipt",
]

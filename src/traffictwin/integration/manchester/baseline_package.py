"""Typed, deterministic candidate Manchester simulation baseline package.

This module composes the **existing** Manchester foundations rather than
duplicating them:

* ``network_scope`` — geographic scope and extract envelope
* ``network_build`` — frozen ``netconvert`` builder and location contract
* ``network_geometry`` — real edge geometry and fidelity tagging
* ``network_connectivity`` — motor-eligible connectivity reviews
* ``network_service`` — read-only candidate discovery over accepted bindings
* ``boundary_reference`` — ONS display-boundary reference assets
* ``demand_reconstruction`` — count-constrained candidate demand
* ``map_matching`` — synthetic harness and fail-closed preflight
* ``calibration`` — deterministic calibration candidate evaluation
* ``models`` / ``snapshots`` — canonical JSON, SHA-256, provenance and
  bounded-string conventions

The package captures geographic/network identity, explicit source and
evidence standing, rights/licence standing, portable network-file identities
and SHA-256 fingerprints, boundary and demand identities, map-match policy
identity, calibration contract/receipt identity, limitations, provenance,
rejection reasons, and acceptance-decision identity.

Central invariant
-----------------
File/package validation and scientific acceptance are **separate**:

* ``SOFTWARE_VALID`` validates that the candidate's portable artefacts are
  structurally sound, hash-consistent, and free of leakage/traversal/divergence.
* ``SCIENTIFICALLY_ACCEPTED_BASELINE`` is an explicit, attributable, UTC-
  timestamped decision that references the exact frozen candidate fingerprint
  and requires all declared prerequisites.

``SOFTWARE_VALID`` never implies ``SCIENTIFICALLY_ACCEPTED_BASELINE``.
A synthetically usable engineering baseline may be ``SOFTWARE_VALID`` while
scientifically unaccepted. A merely readable or hash-correct network is not
scientific evidence. Provider-data absence remains
``PROVIDER_DATA_REQUIRED`` (or an equally clear typed blocked standing).

The module performs no acquisition, no network-content download, no SUMO
launch, no observation invention, and no Dynamic Resource/E3 mutation.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Reuse canonical conventions from the snapshot layer instead of
# redefining them.  The import is intentional: it keeps JSON
# canonicalisation and SHA-256 handling identical to the existing
# snapshot/provenance contracts.
from traffictwin.integration.manchester.models import (  # noqa: F401 - re-export for reuse transparency
    canonical_json as _canonical_json_from_models,
)

# Reuse the reviewed toolchain prefix so network-tool identity stays
# aligned with ``network_build``.
from traffictwin.integration.manchester.network_build import (  # noqa: F401
    SUPPORTED_SUMO_VERSION_PREFIX,
)

# Reuse scope constants so geographic identity cannot drift from the
# approved ``network_scope`` contract.
from traffictwin.integration.manchester.network_scope import (  # noqa: F401
    BASELINE_SCOPE as SCOPE_BASELINE,
)
from traffictwin.integration.manchester.network_scope import (
    SUB_AREA_SCOPE as SCOPE_SUB_AREA,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MANCHESTER_BASELINE_PACKAGE_SCHEMA_VERSION: Literal["1.0"] = "1.0"
MANCHESTER_BASELINE_PACKAGE_METHOD_VERSION: Literal["manchester-baseline-package-1.0"] = (
    "manchester-baseline-package-1.0"
)
MANCHESTER_BASELINE_PACKAGE_CAPABILITY_ID: Literal["MAN-09"] = "MAN-09"

# Standing literals — the type system enforces the separation.
SOFTWARE_VALID: Literal["SOFTWARE_VALID"] = "SOFTWARE_VALID"
SOFTWARE_INVALID: Literal["SOFTWARE_INVALID"] = "SOFTWARE_INVALID"
SCIENTIFICALLY_ACCEPTED_BASELINE: Literal["SCIENTIFICALLY_ACCEPTED_BASELINE"] = (
    "SCIENTIFICALLY_ACCEPTED_BASELINE"
)
SCIENTIFICALLY_NOT_ACCEPTED: Literal["SCIENTIFICALLY_NOT_ACCEPTED"] = "SCIENTIFICALLY_NOT_ACCEPTED"
PROVIDER_DATA_REQUIRED: Literal["PROVIDER_DATA_REQUIRED"] = "PROVIDER_DATA_REQUIRED"

SoftwareStanding: TypeAlias = Literal["SOFTWARE_VALID", "SOFTWARE_INVALID"]
ScientificStanding: TypeAlias = Literal[
    "SCIENTIFICALLY_ACCEPTED_BASELINE",
    "SCIENTIFICALLY_NOT_ACCEPTED",
    "PROVIDER_DATA_REQUIRED",
]
SourceStanding: TypeAlias = Literal[
    "SYNTHETIC_ENGINEERING",
    "OBSERVED_MANCHESTER_EVIDENCE",
    "PROVIDER_DATA_REQUIRED",
]
EvidenceStanding: TypeAlias = Literal[
    "SYNTHETIC_ENGINEERING",
    "OBSERVED_MANCHESTER_EVIDENCE",
    "PROVIDER_DATA_REQUIRED",
]
RightsStanding: TypeAlias = Literal[
    "ODbL-1.0",
    "OGL-3.0",
    "UNKNOWN",
    "UNLICENSED",
]

RejectionReason: TypeAlias = Literal[
    "PROVIDER_DATA_REQUIRED",
    "RIGHTS_UNKNOWN",
    "RIGHTS_UNLICENSED",
    "NETWORK_HASH_MISMATCH",
    "PROVENANCE_BROKEN",
    "PROVENANCE_CHAIN_MISMATCH",
    "MISSING_CALIBRATION",
    "MAP_MATCH_POLICY_UNAPPROVED",
    "BOUNDARY_MISMATCH",
    "DEMAND_MISMATCH",
    "CANDIDATE_TAMPERED",
    "MISMATCHED_CANDIDATE_FINGERPRINT",
    "SECRET_OR_PATH_LEAKAGE",
    "BUILD_RECEIPT_MISSING",
    "EVIDENCE_NOT_PRODUCTION",
    "TEMPORAL_VIOLATION",
    "SOFTWARE_NOT_VALID",
    "EXPLICIT_NON_ACCEPTANCE",
]

# Bounded collection limits
MAX_NETWORK_FILES = 8
MAX_SOURCES = 16
MAX_LIMITATIONS = 16
MAX_REJECTION_REASONS = 16
MAX_PROVENANCE_HOPS = 8
MAX_STRING_LENGTH = 300
MAX_IDENTIFIER_LENGTH = 200

# Secret / private-path refusal patterns — mirrors ``models.py``.
_PRIVATE_PATH_RE = re.compile(r"(/Users/|/home/|/private/|/var/|/tmp/|/etc/|~/|[A-Za-z]:\\)")
_SECRET_TOKEN_RE = re.compile(
    r"(apikey|api_key|secret|password|passwd|token|bearer|credential|authorization)",
    re.IGNORECASE,
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_RELATIVE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$")
_TRAVERSAL_RE = re.compile(r"(^|/)(\.\.)(/|$)")


# UTC helpers
def _is_utc(dt: datetime) -> bool:
    return dt.tzinfo is not None and dt.utcoffset() == timedelta(0)


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _reject_private_path(value: str, label: str) -> str:
    if _PRIVATE_PATH_RE.search(value):
        raise ValueError(f"{label} must not contain a private absolute path")
    if _TRAVERSAL_RE.search(value):
        raise ValueError(f"{label} must not contain traversal")
    if "\\" in value:
        raise ValueError(f"{label} must not contain backslash")
    if _SECRET_TOKEN_RE.search(value):
        raise ValueError(f"{label} must not contain likely secret")
    return value


# ---------------------------------------------------------------------------
# Base model
# ---------------------------------------------------------------------------


class BaselinePackageModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        return _sha256_hex(self.canonical_json().encode("utf-8"))


# ---------------------------------------------------------------------------
# Typed error
# ---------------------------------------------------------------------------


class ManchesterBaselinePackageError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


# ---------------------------------------------------------------------------
# Portable network file identity — reuse of snapshot portable conventions
# ---------------------------------------------------------------------------


class PortableNetworkFile(BaselinePackageModel):
    """One portable, hash-bound network artefact (no absolute path)."""

    relative_path: str = Field(min_length=1, max_length=MAX_IDENTIFIER_LENGTH)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int = Field(ge=1, le=8_000_000_000)
    media_type: str = Field(min_length=1, max_length=120)

    @field_validator("relative_path")
    @classmethod
    def _validate_path(cls, v: str) -> str:
        _reject_private_path(v, "network file path")
        if v.startswith("/") or v.startswith("./"):
            raise ValueError("network file path must be safe relative")
        if ".." in v.split("/"):
            raise ValueError("network file path must not contain traversal")
        if not _SAFE_RELATIVE_RE.fullmatch(v):
            raise ValueError("network file path must be safe POSIX")
        for seg in v.split("/"):
            if not _SAFE_NAME_RE.fullmatch(seg) and "." in seg:
                # allow dot in final extension but validate segments
                if not re.fullmatch(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$", seg):
                    raise ValueError(f"unsafe path segment: {seg}")
            elif not seg or seg in {".", ".."}:
                raise ValueError("network file path segment invalid")
        pp = PurePosixPath(v)
        if pp.is_absolute():
            raise ValueError("network file path must be relative")
        return pp.as_posix()

    @field_validator("media_type")
    @classmethod
    def _validate_media(cls, v: str) -> str:
        _reject_private_path(v, "media type")
        if "/" not in v:
            raise ValueError("media type must contain '/'")
        if _SECRET_TOKEN_RE.search(v):
            raise ValueError("media type must not contain secret")
        return v


# ---------------------------------------------------------------------------
# Geographic / network identity — derived from network_scope/boundary
# ---------------------------------------------------------------------------


class GeographicIdentity(BaselinePackageModel):
    """Geographic scope derived from the approved ONS display geometry."""

    schema_version: Literal["1.0"] = "1.0"
    baseline_scope: Literal["greater_manchester_combined_authority"] = SCOPE_BASELINE
    baseline_official_code: Literal["E47000001"] = "E47000001"
    sub_area_scope: Literal["manchester_local_authority"] = SCOPE_SUB_AREA
    sub_area_official_code: Literal["E08000003"] = "E08000003"
    envelope_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    boundary_asset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    boundary_asset_name: str = Field(min_length=1, max_length=80)
    coordinate_reference_system: Literal["EPSG:4326"] = "EPSG:4326"
    distance_reference_system: Literal["EPSG:27700"] = "EPSG:27700"

    @field_validator("boundary_asset_name")
    @classmethod
    def _validate_asset(cls, v: str) -> str:
        _reject_private_path(v, "boundary asset name")
        if not v.endswith(".geojson"):
            raise ValueError("boundary asset must be a geojson file")
        return v


class NetworkIdentity(BaselinePackageModel):
    """Network tool and structural identity (no content retrieval)."""

    tool_reported_version: str = Field(min_length=1, max_length=64)
    tool_supported_prefix: Literal["1.27."] = SUPPORTED_SUMO_VERSION_PREFIX
    tool_executable_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    network_files: tuple[PortableNetworkFile, ...] = Field(
        min_length=1, max_length=MAX_NETWORK_FILES
    )
    network_identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    edge_count: int = Field(ge=0)
    junction_count: int = Field(ge=0)

    @field_validator("tool_reported_version")
    @classmethod
    def _validate_version(cls, v: str) -> str:
        _reject_private_path(v, "tool version")
        if _SECRET_TOKEN_RE.search(v):
            raise ValueError("tool version must not contain secret")
        if not v.startswith(SUPPORTED_SUMO_VERSION_PREFIX):
            raise ValueError("tool version must match reviewed 1.27.x")
        return v

    @model_validator(mode="after")
    def _validate_network(self) -> NetworkIdentity:
        paths = [f.relative_path for f in self.network_files]
        if paths != sorted(paths):
            raise ValueError("network files must be sorted by relative_path")
        if len(set(paths)) != len(paths):
            raise ValueError("network file paths must be unique")
        folded = {p.casefold() for p in paths}
        if len(folded) != len(paths):
            raise ValueError("network file paths must be unique case-insensitively")
        # network_identity recomputed from sorted file identities (path+sha+size)
        inventory = [
            {"relative_path": f.relative_path, "sha256": f.sha256, "byte_size": f.byte_size}
            for f in sorted(self.network_files, key=lambda x: x.relative_path)
        ]
        expected = _sha256_hex(_canonical_json(inventory).encode("utf-8"))
        if self.network_identity_sha256 != expected:
            raise ValueError("network_identity_sha256 must bind sorted file inventory")
        return self


# ---------------------------------------------------------------------------
# Boundary / demand / map-match / calibration identities
# ---------------------------------------------------------------------------


class BoundaryIdentity(BaselinePackageModel):
    scope: Literal["greater_manchester_combined_authority", "manchester_local_authority"]
    asset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    asset_name: str = Field(min_length=1, max_length=80)
    identity_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("asset_name")
    @classmethod
    def _validate_asset(cls, v: str) -> str:
        _reject_private_path(v, "boundary asset")
        return v

    @model_validator(mode="after")
    def _validate_fingerprint(self) -> BoundaryIdentity:
        payload = {
            "scope": self.scope,
            "asset_sha256": self.asset_sha256,
            "asset_name": self.asset_name,
        }
        expected = _sha256_hex(_canonical_json(payload).encode("utf-8"))
        if self.identity_fingerprint != expected:
            raise ValueError("boundary fingerprint must bind scope and asset")
        return self


class DemandIdentity(BaselinePackageModel):
    demand_label: Literal["count_constrained_candidate_demand"] = (
        "count_constrained_candidate_demand"
    )
    acceptance_basis: Literal["owner_policy_accepted_candidate"] = "owner_policy_accepted_candidate"
    identity_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshot_ids: tuple[str, ...] = Field(default=(), max_length=32)
    provider_evidence_available: bool

    @field_validator("source_snapshot_ids")
    @classmethod
    def _validate_sources(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if v != tuple(sorted(v)):
            raise ValueError("source snapshot ids must be sorted")
        if len(set(v)) != len(v):
            raise ValueError("source snapshot ids must be unique")
        folded = {x.casefold() for x in v}
        if len(folded) != len(v):
            raise ValueError("source snapshot ids must be unique case-insensitively")
        for sid in v:
            _reject_private_path(sid, "source snapshot id")
            if _SECRET_TOKEN_RE.search(sid):
                raise ValueError("source snapshot id must not contain secret")
            if not re.fullmatch(
                r"^[a-z0-9][a-z0-9_.-]{0,95}-\d{8}T\d{6}Z-[0-9a-f]{12}$", sid
            ) and not _SAFE_IDENTIFIER_RE.fullmatch(sid):
                raise ValueError("source snapshot id must be safe identifier")
        return v

    @model_validator(mode="after")
    def _validate_demand(self) -> DemandIdentity:
        if not self.provider_evidence_available and self.source_snapshot_ids:
            raise ValueError("provider-absent demand cannot carry source snapshot ids")
        if self.provider_evidence_available and not self.source_snapshot_ids:
            raise ValueError("provider evidence available requires nonempty source snapshot ids")
        return self


class MapMatchPolicyIdentity(BaselinePackageModel):
    policy_id: str = Field(min_length=1, max_length=120)
    policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_for_manchester: bool
    requires_named_person_review: bool

    @field_validator("policy_id")
    @classmethod
    def _validate_policy(cls, v: str) -> str:
        _reject_private_path(v, "policy id")
        if not _SAFE_IDENTIFIER_RE.fullmatch(v):
            raise ValueError("policy id must be safe identifier")
        return v


class CalibrationIdentity(BaselinePackageModel):
    contract_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    receipt_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    contract_version: str | None = Field(default=None, max_length=64)
    evidence_class: Literal["synthetic_development", "production"] = "synthetic_development"
    calibration_performed: bool

    @field_validator("contract_version")
    @classmethod
    def _validate_version(cls, v: str | None) -> str | None:
        if v is None:
            return v
        _reject_private_path(v, "contract version")
        if _SECRET_TOKEN_RE.search(v):
            raise ValueError("contract version must not contain secret")
        return v

    @model_validator(mode="after")
    def _validate_cal(self) -> CalibrationIdentity:
        if self.calibration_performed and self.contract_fingerprint is None:
            raise ValueError("performed calibration must carry contract fingerprint")
        if self.contract_fingerprint is None and self.receipt_fingerprint is not None:
            raise ValueError("receipt requires contract fingerprint")
        if self.evidence_class == "production" and not self.calibration_performed:
            raise ValueError("production calibration requires calibration_performed=True")
        return self


# ---------------------------------------------------------------------------
# Source / rights / evidence standing
# ---------------------------------------------------------------------------


class SourceAndRights(BaselinePackageModel):
    source_standing: SourceStanding
    evidence_standing: EvidenceStanding
    evidence_class: Literal["synthetic_test_only", "synthetic_development", "production"] = (
        "synthetic_test_only"
    )
    rights_standing: RightsStanding
    licence_id: str = Field(min_length=1, max_length=64)
    attribution_text: str = Field(min_length=1, max_length=500)
    rights_required_for_acceptance: bool = True

    @field_validator("licence_id")
    @classmethod
    def _validate_licence(cls, v: str) -> str:
        _reject_private_path(v, "licence id")
        if _SECRET_TOKEN_RE.search(v):
            raise ValueError("licence id must not contain secret")
        if not re.fullmatch(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$", v):
            raise ValueError("licence id must be safe identifier")
        return v

    @field_validator("attribution_text")
    @classmethod
    def _validate_attr(cls, v: str) -> str:
        _reject_private_path(v, "attribution text")
        if _SECRET_TOKEN_RE.search(v):
            raise ValueError("attribution must not contain secret")
        return v

    @model_validator(mode="after")
    def _validate_rights(self) -> SourceAndRights:
        if (
            self.source_standing == "PROVIDER_DATA_REQUIRED"
            and self.evidence_standing != "PROVIDER_DATA_REQUIRED"
        ):
            raise ValueError("provider-data-required source must have matching evidence standing")
        if (
            self.source_standing != "PROVIDER_DATA_REQUIRED"
            and self.evidence_standing == "PROVIDER_DATA_REQUIRED"
        ):
            raise ValueError(
                "evidence PROVIDER_DATA_REQUIRED implies source PROVIDER_DATA_REQUIRED"
            )
        # Rights leakage: synthetic may still have known licence;
        # production must not be unknown if acceptance requires
        return self


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


class BaselineProvenance(BaselinePackageModel):
    created_at_utc: datetime
    created_by: str = Field(min_length=1, max_length=120)
    software_version: str = Field(min_length=1, max_length=64)
    method_version: Literal["manchester-baseline-package-1.0"] = (
        MANCHESTER_BASELINE_PACKAGE_METHOD_VERSION
    )
    parent_fingerprints: tuple[str, ...] = Field(default=(), max_length=MAX_PROVENANCE_HOPS)
    chain_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @field_validator("created_at_utc")
    @classmethod
    def _validate_time(cls, v: datetime) -> datetime:
        if not _is_utc(v):
            raise ValueError("provenance timestamp must be timezone-aware UTC")
        return v

    @field_validator("created_by")
    @classmethod
    def _validate_by(cls, v: str) -> str:
        _reject_private_path(v, "provenance creator")
        if len(v.strip()) == 0:
            raise ValueError("provenance creator must be non-empty")
        return v

    @field_validator("software_version")
    @classmethod
    def _validate_sw(cls, v: str) -> str:
        _reject_private_path(v, "software version")
        if _SECRET_TOKEN_RE.search(v):
            raise ValueError("software version must not contain secret")
        return v

    @field_validator("parent_fingerprints")
    @classmethod
    def _validate_parents(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if v != tuple(sorted(v)):
            raise ValueError("parent fingerprints must be sorted")
        if len(set(v)) != len(v):
            raise ValueError("parent fingerprints must be unique")
        return v

    @model_validator(mode="after")
    def _validate_chain(self) -> BaselineProvenance:
        if self.chain_fingerprint is not None:
            # Chain must bind exact sorted parent set deterministically.
            expected = _sha256_hex(_canonical_json(list(self.parent_fingerprints)).encode("utf-8"))
            if self.chain_fingerprint != expected:
                raise ValueError("chain_fingerprint must bind exact sorted parent fingerprints")
        return self


# ---------------------------------------------------------------------------
# Candidate package — the frozen, fingerprint-bound candidate
# ---------------------------------------------------------------------------


class ManchesterBaselineCandidatePackage(BaselinePackageModel):
    """Frozen candidate baseline package (file-identities only, no retrieval)."""

    schema_version: Literal["1.0"] = MANCHESTER_BASELINE_PACKAGE_SCHEMA_VERSION
    capability_id: Literal["MAN-09"] = MANCHESTER_BASELINE_PACKAGE_CAPABILITY_ID
    method_version: Literal["manchester-baseline-package-1.0"] = (
        MANCHESTER_BASELINE_PACKAGE_METHOD_VERSION
    )
    package_id: str = Field(min_length=1, max_length=80)
    geographic_identity: GeographicIdentity
    network_identity: NetworkIdentity
    boundary_identity: BoundaryIdentity
    demand_identity: DemandIdentity
    map_match_policy_identity: MapMatchPolicyIdentity
    calibration_identity: CalibrationIdentity
    source_and_rights: SourceAndRights
    limitations: tuple[str, ...] = Field(min_length=1, max_length=MAX_LIMITATIONS)
    provenance: BaselineProvenance
    # Explicit block: provider-data-absence is typed, not hidden
    provider_data_required: bool
    # Declared prerequisites that acceptance must satisfy
    prerequisites: tuple[str, ...] = Field(min_length=1, max_length=16)
    # Evidence that software validation was performed (hash binding placeholder)
    build_receipt_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @field_validator("package_id")
    @classmethod
    def _validate_pid(cls, v: str) -> str:
        _reject_private_path(v, "package id")
        if not re.fullmatch(r"^[a-z0-9][a-z0-9_.-]{0,79}$", v):
            raise ValueError("package id must be safe lowercase identifier")
        return v

    @field_validator("limitations")
    @classmethod
    def _validate_limits(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(v)) != len(v):
            raise ValueError("limitations must be unique")
        for item in v:
            if not 1 <= len(item) <= 400:
                raise ValueError("limitation length out of bounds")
            _reject_private_path(item, "limitation")
            if _SECRET_TOKEN_RE.search(item):
                raise ValueError("limitation must not contain secret")
        return v

    @field_validator("prerequisites")
    @classmethod
    def _validate_prereq(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if v != tuple(sorted(v)):
            raise ValueError("prerequisites must be sorted")
        if len(set(v)) != len(v):
            raise ValueError("prerequisites must be unique")
        for item in v:
            _reject_private_path(item, "prerequisite")
            if not re.fullmatch(r"^[a-z0-9][a-z0-9_.-]{1,63}$", item):
                raise ValueError("prerequisite must be safe identifier")
        return v

    @model_validator(mode="after")
    def _validate_candidate(self) -> ManchesterBaselineCandidatePackage:
        if self.provider_data_required:
            if self.source_and_rights.source_standing != "PROVIDER_DATA_REQUIRED":
                raise ValueError("provider_data_required must be reflected in source standing")
            if self.demand_identity.provider_evidence_available:
                raise ValueError("provider_data_required contradicts available demand evidence")
        else:
            if self.source_and_rights.source_standing == "PROVIDER_DATA_REQUIRED":
                raise ValueError(
                    "source PROVIDER_DATA_REQUIRED implies provider_data_required true"
                )
            if self.source_and_rights.evidence_standing == "PROVIDER_DATA_REQUIRED":
                raise ValueError(
                    "evidence PROVIDER_DATA_REQUIRED implies provider_data_required true"
                )
        if self.source_and_rights.evidence_class == "production":
            if not self.demand_identity.provider_evidence_available:
                raise ValueError("production evidence requires provider demand evidence")
            if self.demand_identity.source_snapshot_ids == ():
                raise ValueError("production demand requires nonempty source snapshot ids")
            if self.source_and_rights.source_standing != "OBSERVED_MANCHESTER_EVIDENCE":
                raise ValueError("production requires OBSERVED_MANCHESTER_EVIDENCE source")
            if self.source_and_rights.evidence_standing != "OBSERVED_MANCHESTER_EVIDENCE":
                raise ValueError("production requires OBSERVED_MANCHESTER_EVIDENCE standing")
        if self.boundary_identity.asset_sha256 != self.geographic_identity.boundary_asset_sha256:
            raise ValueError("boundary asset mismatch with geographic identity")
        if self.boundary_identity.asset_name != self.geographic_identity.boundary_asset_name:
            raise ValueError("boundary asset name mismatch with geographic identity")
        return self

    def candidate_fingerprint(self) -> str:
        return self.fingerprint()


# ---------------------------------------------------------------------------
# Software validation — file/package validation only, never scientific
# ---------------------------------------------------------------------------


class ManchesterBaselineSoftwareValidation(BaselinePackageModel):
    schema_version: Literal["1.0"] = MANCHESTER_BASELINE_PACKAGE_SCHEMA_VERSION
    capability_id: Literal["MAN-09"] = MANCHESTER_BASELINE_PACKAGE_CAPABILITY_ID
    method_version: Literal["manchester-baseline-package-1.0"] = (
        MANCHESTER_BASELINE_PACKAGE_METHOD_VERSION
    )
    candidate_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_package_id: str = Field(min_length=1, max_length=80)
    network_identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    software_standing: SoftwareStanding
    # Scientific standing is always structurally false here — SOFTWARE_VALID never upgrades.
    scientific_standing: Literal["SCIENTIFICALLY_NOT_ACCEPTED"] = "SCIENTIFICALLY_NOT_ACCEPTED"
    scientifically_accepted: Literal[False] = False
    checks_performed: tuple[str, ...] = Field(min_length=1, max_length=16)
    rejection_reasons: tuple[RejectionReason, ...] = Field(default=())
    validated_at_utc: datetime
    # Explicit: software valid does not claim scientific evidence
    is_scientific_evidence: Literal[False] = False

    @field_validator("validated_at_utc")
    @classmethod
    def _validate_time(cls, v: datetime) -> datetime:
        if not _is_utc(v):
            raise ValueError("validation timestamp must be UTC")
        return v

    @field_validator("checks_performed")
    @classmethod
    def _validate_checks(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if v != tuple(sorted(v)):
            raise ValueError("checks must be sorted")
        if len(set(v)) != len(v):
            raise ValueError("checks must be unique")
        for c in v:
            if _PRIVATE_PATH_RE.search(c):
                raise ValueError("check must not contain private path")
        return v

    @field_validator("rejection_reasons")
    @classmethod
    def _validate_reasons(cls, v: tuple[RejectionReason, ...]) -> tuple[RejectionReason, ...]:
        if v != tuple(sorted(v)):
            raise ValueError("rejection reasons must be sorted")
        if len(set(v)) != len(v):
            raise ValueError("rejection reasons must be unique")
        return v

    @model_validator(mode="after")
    def _validate_software(self) -> ManchesterBaselineSoftwareValidation:
        if self.software_standing == "SOFTWARE_VALID" and self.rejection_reasons:
            raise ValueError("SOFTWARE_VALID cannot carry rejection reasons")
        if self.software_standing == "SOFTWARE_INVALID" and not self.rejection_reasons:
            raise ValueError("SOFTWARE_INVALID requires rejection reasons")
        if self.scientifically_accepted is not False:
            raise ValueError("software validation must never be scientifically accepted")
        if self.is_scientific_evidence is not False:
            raise ValueError("software validation is never scientific evidence")
        return self


# ---------------------------------------------------------------------------
# Scientific acceptance — explicit attributable timestamped decision
# ---------------------------------------------------------------------------


class ManchesterBaselineAcceptanceDecision(BaselinePackageModel):
    """Explicit attributable scientific acceptance decision.

    The decision is structurally self-consistent when ``decision_fingerprint``
    matches the canonical JSON digest of its semantic fields. A
    self-consistent payload is **not** scientific evidence on its own;
    scientific standing is verified only by :func:`verify_baseline_acceptance`
    against the exact candidate and software-validation receipt. The
    fingerprint is a plain SHA-256 digest for binding, not cryptographic
    authenticity.

    An ``SCIENTIFICALLY_ACCEPTED_BASELINE`` decision immutably binds the
    exact software-validation receipt
    (``software_validation_fingerprint`` == ``ManchesterBaselineSoftwareValidation.fingerprint()``)
    and the exact candidate build receipt
    (``candidate_build_receipt_fingerprint`` == ``candidate.build_receipt_fingerprint``).
    Non-accepted / provider-blocked decisions carry ``None`` for both bindings;
    any other combination is rejected during model validation.
    """

    schema_version: Literal["1.0"] = MANCHESTER_BASELINE_PACKAGE_SCHEMA_VERSION
    capability_id: Literal["MAN-09"] = MANCHESTER_BASELINE_PACKAGE_CAPABILITY_ID
    method_version: Literal["manchester-baseline-package-1.0"] = (
        MANCHESTER_BASELINE_PACKAGE_METHOD_VERSION
    )
    candidate_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_package_id: str = Field(min_length=1, max_length=80)
    scientific_standing: ScientificStanding
    decided_by: str = Field(min_length=1, max_length=120)
    decided_at_utc: datetime
    rationale: str = Field(min_length=1, max_length=800)
    prerequisites_verified: tuple[str, ...] = Field(min_length=1, max_length=16)
    rejection_reasons: tuple[RejectionReason, ...] = Field(default=())
    # Immutable binding to the exact receipts used for acceptance.
    # Accepted decisions must carry both; non-accepted must carry neither.
    software_validation_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    candidate_build_receipt_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    # Attributable: decision fingerprint binds candidate + attribution + time
    # + receipt bindings. See class docstring: binding is a plain digest, not
    # cryptographic authenticity; verification requires exact objects.
    decision_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("decided_by")
    @classmethod
    def _validate_by(cls, v: str) -> str:
        _reject_private_path(v, "decided_by")
        if not v.strip():
            raise ValueError("decided_by must be non-empty")
        return v

    @field_validator("decided_at_utc")
    @classmethod
    def _validate_time(cls, v: datetime) -> datetime:
        if not _is_utc(v):
            raise ValueError("decision timestamp must be UTC")
        return v

    @field_validator("rationale")
    @classmethod
    def _validate_rationale(cls, v: str) -> str:
        _reject_private_path(v, "rationale")
        if _SECRET_TOKEN_RE.search(v):
            raise ValueError("rationale must not contain secret")
        return v

    @field_validator("prerequisites_verified")
    @classmethod
    def _validate_prereq(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if v != tuple(sorted(v)):
            raise ValueError("prerequisites_verified must be sorted")
        if len(set(v)) != len(v):
            raise ValueError("prerequisites_verified must be unique")
        for p in v:
            _reject_private_path(p, "prerequisite")
        return v

    @field_validator("rejection_reasons")
    @classmethod
    def _validate_rejection_reasons(
        cls, v: tuple[RejectionReason, ...]
    ) -> tuple[RejectionReason, ...]:
        if v != tuple(sorted(v)):
            raise ValueError("rejection_reasons must be sorted")
        if len(set(v)) != len(v):
            raise ValueError("rejection_reasons must be unique")
        return v

    @model_validator(mode="after")
    def _validate_decision(self) -> ManchesterBaselineAcceptanceDecision:
        payload = {
            "candidate_fingerprint": self.candidate_fingerprint,
            "candidate_package_id": self.candidate_package_id,
            "candidate_build_receipt_fingerprint": self.candidate_build_receipt_fingerprint,
            "decided_by": self.decided_by,
            "decided_at_utc": self.decided_at_utc.isoformat(),
            "prerequisites_verified": list(self.prerequisites_verified),
            "rationale": self.rationale,
            "rejection_reasons": list(self.rejection_reasons),
            "schema_version": self.schema_version,
            "capability_id": self.capability_id,
            "method_version": self.method_version,
            "scientific_standing": self.scientific_standing,
            "software_validation_fingerprint": self.software_validation_fingerprint,
        }
        expected = _sha256_hex(_canonical_json(payload).encode("utf-8"))
        if self.decision_fingerprint != expected:
            raise ValueError(
                "decision_fingerprint must bind candidate, standing, attribution, "
                "time, prerequisites, rejection_reasons and receipt bindings"
            )
        if self.scientific_standing == "SCIENTIFICALLY_ACCEPTED_BASELINE":
            if self.rejection_reasons:
                raise ValueError("accepted decision cannot carry rejection reasons")
            if self.software_validation_fingerprint is None:
                raise ValueError("accepted decision must carry software_validation_fingerprint")
            if self.candidate_build_receipt_fingerprint is None:
                raise ValueError("accepted decision must carry candidate_build_receipt_fingerprint")
        else:
            if self.software_validation_fingerprint is not None:
                raise ValueError(
                    "non-accepted decision must not carry software_validation_fingerprint"
                )
            if self.candidate_build_receipt_fingerprint is not None:
                raise ValueError(
                    "non-accepted decision must not carry candidate_build_receipt_fingerprint"
                )
            if self.scientific_standing == "PROVIDER_DATA_REQUIRED" and not self.rejection_reasons:
                raise ValueError("PROVIDER_DATA_REQUIRED must carry rejection reasons")
        return self

    def verify(
        self,
        candidate: ManchesterBaselineCandidatePackage,
        software_validation: ManchesterBaselineSoftwareValidation | None,
    ) -> None:
        """Verify this decision against the exact candidate and software validation.

        Reuses the same prerequisite checker as the builder so the two cannot
        drift. Fails closed via :class:`ManchesterBaselinePackageError` unless
        every identity, standing, prerequisite, timestamp, and
        provider/rights/map-match/calibration/build-receipt precondition still
        matches. Does not invent or retrieve provider evidence and never
        self-upgrades ``scientific_standing``.

        Structural self-consistency (matching ``decision_fingerprint``) alone
        does not confer scientific standing; only successful verification
        against the exact objects does. The fingerprint is a plain digest, not
        cryptographic authenticity.
        """
        verify_baseline_acceptance(self, candidate, software_validation)


# ---------------------------------------------------------------------------
# Public API — deterministic builders / validators
# ---------------------------------------------------------------------------


def build_candidate_package(
    *,
    package_id: str,
    geographic_identity: GeographicIdentity,
    network_identity: NetworkIdentity,
    boundary_identity: BoundaryIdentity,
    demand_identity: DemandIdentity,
    map_match_policy_identity: MapMatchPolicyIdentity,
    calibration_identity: CalibrationIdentity,
    source_and_rights: SourceAndRights,
    limitations: tuple[str, ...],
    provenance: BaselineProvenance,
    provider_data_required: bool,
    prerequisites: tuple[str, ...],
    build_receipt_fingerprint: str | None = None,
) -> ManchesterBaselineCandidatePackage:
    return ManchesterBaselineCandidatePackage(
        package_id=package_id,
        geographic_identity=geographic_identity,
        network_identity=network_identity,
        boundary_identity=boundary_identity,
        demand_identity=demand_identity,
        map_match_policy_identity=map_match_policy_identity,
        calibration_identity=calibration_identity,
        source_and_rights=source_and_rights,
        limitations=limitations,
        provenance=provenance,
        provider_data_required=provider_data_required,
        prerequisites=prerequisites,
        build_receipt_fingerprint=build_receipt_fingerprint,
    )


def validate_candidate_software(
    candidate: ManchesterBaselineCandidatePackage,
    *,
    validated_at_utc: datetime | None = None,
    package_root: object | None = None,
) -> ManchesterBaselineSoftwareValidation:
    """Validate portable file/package structure only.

    **Exact meaning of SOFTWARE_VALID** (narrow coherent design):
    * Validates that portable identities are structurally sound, hash-bound,
      sorted, unique, and free of traversal/secret/private-path leakage.
    * Recomputes ``network_identity_sha256`` from the sorted portable file
      inventory and checks the boundary fingerprint — i.e. self-consistency
      of the *claimed* metadata.
    * Does **not** prove actual file existence or byte-level hash correctness
      on disk — a merely claimed ``sha256``/``byte_size`` is not silently
      treated as proof of file validity. Actual artefact verification
      requires either (a) an exact ``build_receipt_fingerprint`` carried in
      the candidate and externally verified by the build system, or
      (b) a caller-supplied explicit ``package_root`` that this function
      verifies against the declared ``relative_path``/``sha256``/``byte_size``
      without leaking absolute paths in errors. When ``package_root`` is
      ``None`` only (a) self-consistency is checked, and production
      scientific acceptance must still require (a).

    Never upgrades to scientific acceptance. Returns ``SOFTWARE_VALID`` only
    when the above structural checks pass and temporal order
    ``provenance.created_at_utc <= validated_at_utc`` holds (both aware UTC).
    No internal ``datetime.now`` is used to decide validity of a frozen
    artifact; ``validated_at_utc`` is the explicit evaluation time. When
    ``validated_at_utc`` is ``None`` it defaults to ``datetime.now(UTC)``
    for convenience but provenance is still compared to that explicit value,
    so repeated calls with the same explicit timestamp are deterministic.
    """
    if validated_at_utc is None:
        validated_at_utc = datetime.now(UTC)
    if not _is_utc(validated_at_utc):
        raise ManchesterBaselinePackageError(
            "TIMESTAMP_NOT_UTC", "validation timestamp must be UTC"
        )
    if package_root is not None:
        # Narrow explicit-root verification without leaking paths.
        # Caller must supply a concrete filesystem root (path-like) when
        # byte-level artefact verification is desired; errors never echo
        # the absolute root. This branch is intentionally narrow and
        # fail-closed on traversal/secret leakage rather than inventing
        # observations.
        from pathlib import Path

        try:
            root = Path(str(package_root))
        except Exception as exc:
            raise ManchesterBaselinePackageError(
                "SECRET_OR_PATH_LEAKAGE", f"package_root invalid: {exc}"
            ) from exc
        # Do not leak root in messages; only validate declared relatives.
        for pf in candidate.network_identity.network_files:
            rel = pf.relative_path
            # pf.relative_path already validated as safe relative; re-check
            if _TRAVERSAL_RE.search(rel) or rel.startswith("/"):
                raise ManchesterBaselinePackageError(
                    "SECRET_OR_PATH_LEAKAGE", "network file path invalid"
                )
            target = root / rel
            try:
                data = target.read_bytes()
            except Exception:
                raise ManchesterBaselinePackageError(
                    "NETWORK_HASH_MISMATCH",
                    "declared network file not verifiable at package_root",
                ) from None
            if len(data) != pf.byte_size:
                raise ManchesterBaselinePackageError(
                    "NETWORK_HASH_MISMATCH", "byte_size mismatch for declared file"
                )
            actual = _sha256_hex(data)
            if actual != pf.sha256:
                raise ManchesterBaselinePackageError(
                    "NETWORK_HASH_MISMATCH", "sha256 mismatch for declared file"
                )

    # Perform deterministic checks without reading filesystem/network beyond
    # the optional explicit package_root above.
    reasons: list[RejectionReason] = []
    # Check network file hash binding already enforced; but double-check any candidate tampering
    # by recomputing network identity.
    inventory = [
        {"relative_path": f.relative_path, "sha256": f.sha256, "byte_size": f.byte_size}
        for f in sorted(candidate.network_identity.network_files, key=lambda x: x.relative_path)
    ]
    expected_net = _sha256_hex(_canonical_json(inventory).encode("utf-8"))
    if expected_net != candidate.network_identity.network_identity_sha256:
        reasons.append("NETWORK_HASH_MISMATCH")
    # Deterministic temporal coherence: provenance must not be after validation.
    if candidate.provenance.created_at_utc > validated_at_utc:
        reasons.append("PROVENANCE_BROKEN")
    # Also reject naïve cross-field tamper where provenance chain is inconsistent
    # — already enforced by BaselineProvenance model validator, but also
    # surface here as rejection reason for stale candidates.
    # Boundary fingerprint already validated.

    standing: SoftwareStanding = "SOFTWARE_INVALID" if reasons else "SOFTWARE_VALID"
    # Keep rejection reasons sorted and deduped
    reasons_sorted = tuple(sorted(set(reasons)))

    # Ensure scientific_standing never upgraded.
    return ManchesterBaselineSoftwareValidation(
        candidate_fingerprint=candidate.fingerprint(),
        candidate_package_id=candidate.package_id,
        network_identity_sha256=candidate.network_identity.network_identity_sha256,
        software_standing=standing,
        scientific_standing="SCIENTIFICALLY_NOT_ACCEPTED",
        scientifically_accepted=False,
        checks_performed=tuple(
            sorted(
                [
                    "boundary_fingerprint",
                    "demand_source_ids_sorted",
                    "limitations_bounded",
                    "network_file_identities",
                    "no_private_paths",
                    "rights_sanitized",
                    "provenance_utc",
                ]
            )
        ),
        rejection_reasons=reasons_sorted,
        validated_at_utc=validated_at_utc,
        is_scientific_evidence=False,
    )


def _check_scientific_acceptance_preconditions(
    *,
    candidate: ManchesterBaselineCandidatePackage,
    software_validation: ManchesterBaselineSoftwareValidation,
    prerequisites_verified: tuple[str, ...],
    decided_at_utc: datetime,
) -> None:
    """Shared prerequisite checker for builder and verifier.

    Fails closed via :class:`ManchesterBaselinePackageError` unless every
    identity, standing, prerequisite, timestamp, provider/rights/map-match/
    calibration/build-receipt precondition for
    ``SCIENTIFICALLY_ACCEPTED_BASELINE`` still holds. Does not invent or
    retrieve provider evidence and does not self-upgrade standing. Reused by
    :func:`decide_baseline_acceptance` and
    :func:`verify_baseline_acceptance` so the two cannot drift.

    Canonical revalidation
    ~~~~~~~~~~~~~~~~~~~~~~
    ``ManchesterBaselineCandidatePackage`` and
    ``ManchesterBaselineSoftwareValidation`` are revalidated from
    ``model_dump`` at this shared boundary before any standing is read.
    This closes the ``model_copy(update=...)`` bypass where Pydantic
    validators are skipped. Failures are mapped to stable typed error codes
    with portable messages.

    Canonical receipt
    ~~~~~~~~~~~~~~~~~
    The supplied ``software_validation`` must be the exact receipt that
    :func:`validate_candidate_software` would produce for the same
    ``candidate`` and explicit ``validated_at_utc``. All semantic fields
    and the full ``checks_performed`` set are compared without filesystem
    I/O or current time; package-root byte verification remains represented
    by the candidate's external build receipt.
    """
    # Canonical revalidation: close model_copy/update bypass.
    try:
        ManchesterBaselineCandidatePackage.model_validate(candidate.model_dump())
    except Exception as exc:
        raise ManchesterBaselinePackageError(
            "CANDIDATE_TAMPERED",
            f"candidate revalidation failed: {exc}",
        ) from exc
    try:
        ManchesterBaselineSoftwareValidation.model_validate(software_validation.model_dump())
    except Exception as exc:
        raise ManchesterBaselinePackageError(
            "CANDIDATE_TAMPERED",
            f"software validation revalidation failed: {exc}",
        ) from exc
    # Exact software validation binding and temporal ordering
    if software_validation.candidate_fingerprint != candidate.fingerprint():
        raise ManchesterBaselinePackageError(
            "MISMATCHED_CANDIDATE_FINGERPRINT",
            "software validation references a different candidate",
        )
    if software_validation.candidate_package_id != candidate.package_id:
        raise ManchesterBaselinePackageError(
            "MISMATCHED_CANDIDATE_FINGERPRINT",
            "software validation package_id mismatch",
        )
    if software_validation.software_standing != "SOFTWARE_VALID":
        raise ManchesterBaselinePackageError(
            "SOFTWARE_NOT_VALID",
            "scientifically accepted baseline requires SOFTWARE_VALID first",
        )
    if (
        software_validation.network_identity_sha256
        != candidate.network_identity.network_identity_sha256
    ):
        raise ManchesterBaselinePackageError(
            "NETWORK_HASH_MISMATCH",
            "network hash changed since software validation",
        )
    if not _is_utc(software_validation.validated_at_utc):
        raise ManchesterBaselinePackageError(
            "TIMESTAMP_NOT_UTC", "software validation timestamp must be UTC"
        )
    if candidate.provenance.created_at_utc > software_validation.validated_at_utc:
        raise ManchesterBaselinePackageError(
            "TEMPORAL_VIOLATION",
            "software validation is before provenance creation",
        )
    if software_validation.validated_at_utc > decided_at_utc:
        raise ManchesterBaselinePackageError(
            "TEMPORAL_VIOLATION",
            "decision is before software validation",
        )
    # Canonical receipt: supplied validation must equal the validator's
    # deterministic output for the same candidate and explicit timestamp.
    # No filesystem I/O or current time is used; package_root remains None.
    try:
        _expected_validation = validate_candidate_software(
            candidate, validated_at_utc=software_validation.validated_at_utc
        )
    except ManchesterBaselinePackageError:
        raise
    except Exception as exc:
        raise ManchesterBaselinePackageError(
            "CANDIDATE_TAMPERED",
            f"software validation canonical check failed: {exc}",
        ) from exc
    if software_validation != _expected_validation:
        raise ManchesterBaselinePackageError(
            "CANDIDATE_TAMPERED",
            "software validation is not the canonical receipt for the exact candidate and validated_at_utc",  # noqa: E501
        )
    # Prerequisites exactness
    declared = set(candidate.prerequisites)
    verified = set(prerequisites_verified)
    missing = declared - verified
    if missing:
        raise ManchesterBaselinePackageError(
            "MISSING_PREREQUISITES",
            f"acceptance requires prerequisites {sorted(missing)}",
        )
    extra = verified - declared
    if extra:
        raise ManchesterBaselinePackageError(
            "MISSING_PREREQUISITES",
            f"verified prerequisites not declared {sorted(extra)}",
        )
    # Production standing — never inflated from synthetic
    if candidate.source_and_rights.source_standing != "OBSERVED_MANCHESTER_EVIDENCE":
        raise ManchesterBaselinePackageError(
            "EVIDENCE_NOT_PRODUCTION",
            "scientific acceptance requires OBSERVED_MANCHESTER_EVIDENCE source",
        )
    if candidate.source_and_rights.evidence_standing != "OBSERVED_MANCHESTER_EVIDENCE":
        raise ManchesterBaselinePackageError(
            "EVIDENCE_NOT_PRODUCTION",
            "scientific acceptance requires OBSERVED_MANCHESTER_EVIDENCE standing",
        )
    if candidate.source_and_rights.evidence_class != "production":
        raise ManchesterBaselinePackageError(
            "EVIDENCE_NOT_PRODUCTION",
            "scientific acceptance requires production evidence_class",
        )
    if candidate.calibration_identity.evidence_class != "production":
        raise ManchesterBaselinePackageError(
            "EVIDENCE_NOT_PRODUCTION",
            "scientific acceptance requires production calibration evidence_class",
        )
    if not candidate.demand_identity.provider_evidence_available:
        raise ManchesterBaselinePackageError(
            "PROVIDER_DATA_REQUIRED",
            "production acceptance requires provider demand evidence",
        )
    if not candidate.demand_identity.source_snapshot_ids:
        raise ManchesterBaselinePackageError(
            "PROVIDER_DATA_REQUIRED",
            "production acceptance requires nonempty provider snapshot identities",
        )
    if not candidate.map_match_policy_identity.approved_for_manchester:
        raise ManchesterBaselinePackageError(
            "MAP_MATCH_POLICY_UNAPPROVED",
            "scientific acceptance requires approved map-match policy",
        )
    if not candidate.calibration_identity.calibration_performed:
        raise ManchesterBaselinePackageError(
            "MISSING_CALIBRATION",
            "scientific acceptance requires calibration_performed=True",
        )
    if candidate.calibration_identity.contract_fingerprint is None:
        raise ManchesterBaselinePackageError(
            "MISSING_CALIBRATION",
            "scientific acceptance requires calibration contract fingerprint",
        )
    if candidate.calibration_identity.receipt_fingerprint is None:
        raise ManchesterBaselinePackageError(
            "MISSING_CALIBRATION",
            "scientific acceptance requires calibration receipt fingerprint",
        )
    if (
        candidate.source_and_rights.rights_required_for_acceptance
        and candidate.source_and_rights.rights_standing
        in (
            "UNKNOWN",
            "UNLICENSED",
        )
    ):
        code = (
            "RIGHTS_UNKNOWN"
            if candidate.source_and_rights.rights_standing == "UNKNOWN"
            else "RIGHTS_UNLICENSED"
        )
        raise ManchesterBaselinePackageError(
            code,
            "acceptance requires known licensed rights",
        )
    if candidate.build_receipt_fingerprint is None:
        raise ManchesterBaselinePackageError(
            "BUILD_RECEIPT_MISSING",
            "scientifically accepted baseline requires exact build receipt fingerprint",
        )


def decide_baseline_acceptance(
    candidate: ManchesterBaselineCandidatePackage,
    *,
    decided_by: str,
    decided_at_utc: datetime,
    scientific_standing: ScientificStanding,
    rationale: str,
    prerequisites_verified: tuple[str, ...],
    software_validation: ManchesterBaselineSoftwareValidation | None = None,
) -> ManchesterBaselineAcceptanceDecision:
    """Create an explicit attributable timestamped acceptance decision.

    Fail-closed rules (scientific acceptance requires **all** of the following,
    each bound into ``decision_fingerprint``):

    * Exact ``ManchesterBaselineSoftwareValidation`` for the **same**
      candidate/network with ``SOFTWARE_VALID`` and coherent timestamp
      ``provenance.created_at_utc <= software_validation.validated_at_utc
      <= decided_at_utc`` (all aware UTC, deterministic, no internal
      ``datetime.now``). ``software_validation=None`` is never accepted for
      ``SCIENTIFICALLY_ACCEPTED_BASELINE``. Provider-blocked / explicit
      non-acceptance (``PROVIDER_DATA_REQUIRED`` / ``SCIENTIFICALLY_NOT_ACCEPTED``)
      may remain possible without software validation if truthfully typed.
    * Production-class ``OBSERVED_MANCHESTER_EVIDENCE`` standing
      (``source_standing``, ``evidence_standing``, ``evidence_class ==
      "production"`` for both ``SourceAndRights`` and
      ``CalibrationIdentity``). Any synthetic ``synthetic_test_only`` /
      ``synthetic_development`` / ``SYNTHETIC_ENGINEERING`` is never
      scientifically accepted, even if caller booleans are forged.
    * Non-empty sorted ``source_snapshot_ids`` and
      ``provider_evidence_available==True``.
    * Known/licensed rights when ``rights_required_for_acceptance`` (no
      ``UNKNOWN``/``UNLICENSED``).
    * Approved map-match policy (``approved_for_manchester==True``).
    * ``calibration_performed==True`` **and** both
      ``contract_fingerprint`` and ``receipt_fingerprint`` present and
      valid SHA-256.
    * Exact ``build_receipt_fingerprint`` on the candidate (narrow design:
      ``SOFTWARE_VALID`` as defined in ``validate_candidate_software`` only
      checks claimed hash self-consistency, not live file bytes; production
      acceptance therefore requires an externally verified receipt; see that
      function's docstring).
    * All declared ``prerequisites`` verified and no extras.
    * Truthful ``rejection_reasons`` bound into the fingerprint; a
      deliberately ``SCIENTIFICALLY_NOT_ACCEPTED`` decision never invents
      ``CANDIDATE_TAMPERED`` — it uses ``EXPLICIT_NON_ACCEPTANCE`` or
      the attributable ``rationale`` when no other blocker exists.
    * Deterministic temporal coherence; reversed/future-relative-to-evaluation
      timestamps are rejected with ``TEMPORAL_VIOLATION``/``PROVENANCE_BROKEN``.
    """
    _reject_private_path(decided_by, "decided_by")
    _reject_private_path(rationale, "rationale")
    if not _is_utc(decided_at_utc):
        raise ManchesterBaselinePackageError("TIMESTAMP_NOT_UTC", "decision timestamp must be UTC")
    # Deterministic temporal coherence: provenance <= decision always;
    # software validation ordering checked below for ACCEPTED path.
    # No internal datetime.now is used — decided_at_utc is the explicit evaluation time.
    if candidate.provenance.created_at_utc > decided_at_utc:
        raise ManchesterBaselinePackageError(
            "TEMPORAL_VIOLATION",
            "decision is before provenance creation",
        )

    # Build truthful rejection reasons for non-acceptance paths up-front
    # (never invent CANDIDATE_TAMPERED for an explicit non-acceptance).
    rejection_reasons: list[RejectionReason] = []

    if (
        candidate.provider_data_required
        or candidate.source_and_rights.source_standing == "PROVIDER_DATA_REQUIRED"
        or candidate.source_and_rights.evidence_standing == "PROVIDER_DATA_REQUIRED"
    ):
        if scientific_standing == "SCIENTIFICALLY_ACCEPTED_BASELINE":
            raise ManchesterBaselinePackageError(
                "PROVIDER_DATA_REQUIRED",
                "scientific acceptance requires provider observations; "
                "standing is PROVIDER_DATA_REQUIRED",
            )
        if "PROVIDER_DATA_REQUIRED" not in rejection_reasons:
            rejection_reasons.append("PROVIDER_DATA_REQUIRED")

    if (
        candidate.source_and_rights.rights_required_for_acceptance
        and candidate.source_and_rights.rights_standing in ("UNKNOWN", "UNLICENSED")
    ):
        if scientific_standing == "SCIENTIFICALLY_ACCEPTED_BASELINE":
            code = (
                "RIGHTS_UNKNOWN"
                if candidate.source_and_rights.rights_standing == "UNKNOWN"
                else "RIGHTS_UNLICENSED"
            )
            raise ManchesterBaselinePackageError(
                code,
                "acceptance requires known licensed rights",
            )
        rejection_reasons.append(
            "RIGHTS_UNKNOWN"
            if candidate.source_and_rights.rights_standing == "UNKNOWN"
            else "RIGHTS_UNLICENSED"
        )

    if scientific_standing == "SCIENTIFICALLY_ACCEPTED_BASELINE":
        if software_validation is None:
            raise ManchesterBaselinePackageError(
                "SOFTWARE_NOT_VALID",
                "scientific acceptance requires an exact ManchesterBaselineSoftwareValidation",
            )
        # Reuse shared checker so builder and verifier cannot drift.
        _check_scientific_acceptance_preconditions(
            candidate=candidate,
            software_validation=software_validation,
            prerequisites_verified=prerequisites_verified,
            decided_at_utc=decided_at_utc,
        )

    # Truthful non-acceptance: never invent CANDIDATE_TAMPERED
    if scientific_standing == "PROVIDER_DATA_REQUIRED":
        if not rejection_reasons:
            # Truthfully blocked only if provider data truly missing; otherwise require explicit
            if candidate.provider_data_required:
                rejection_reasons.append("PROVIDER_DATA_REQUIRED")
            else:
                raise ManchesterBaselinePackageError(
                    "PROVIDER_DATA_REQUIRED",
                    "PROVIDER_DATA_REQUIRED standing requires truthful provider-data absence",
                )
    elif scientific_standing == "SCIENTIFICALLY_NOT_ACCEPTED" and not rejection_reasons:
        # Allow attributable rationale with no invented tamper. Use an explicit
        # truthful reason so the decision remains attributable and the
        # fingerprint binds it, but do not claim tamper evidence.
        rejection_reasons.append("EXPLICIT_NON_ACCEPTANCE")

    # PROVIDER_DATA_REQUIRED decisions must carry rejection reasons (model enforces)
    # Non-accepted decisions without blocker now carry EXPLICIT_NON_ACCEPTANCE truthfully.

    sorted_prereq = tuple(sorted(prerequisites_verified))
    sorted_reasons = tuple(sorted(set(rejection_reasons)))
    # For accepted baseline, model requires no rejection reasons — strip the
    # synthetic explicit reason we may have added above for non-accepted only.
    if scientific_standing == "SCIENTIFICALLY_ACCEPTED_BASELINE":
        sorted_reasons = ()

    # Receipt bindings: accepted carries exact fingerprints; non-accepted carries None.
    if scientific_standing == "SCIENTIFICALLY_ACCEPTED_BASELINE":
        # software_validation presence already checked; candidate build receipt also
        # checked inside the shared checker.
        assert software_validation is not None
        software_validation_fingerprint: str | None = software_validation.fingerprint()
        candidate_build_receipt_fingerprint: str | None = candidate.build_receipt_fingerprint
    else:
        software_validation_fingerprint = None
        candidate_build_receipt_fingerprint = None

    # Fingerprint must bind every semantic decision field including receipt bindings.
    fingerprint_payload = {
        "candidate_fingerprint": candidate.fingerprint(),
        "candidate_package_id": candidate.package_id,
        "candidate_build_receipt_fingerprint": candidate_build_receipt_fingerprint,
        "decided_by": decided_by,
        "decided_at_utc": decided_at_utc.isoformat(),
        "prerequisites_verified": sorted(sorted_prereq),
        "rationale": rationale,
        "rejection_reasons": sorted(sorted_reasons),
        "schema_version": MANCHESTER_BASELINE_PACKAGE_SCHEMA_VERSION,
        "capability_id": MANCHESTER_BASELINE_PACKAGE_CAPABILITY_ID,
        "method_version": MANCHESTER_BASELINE_PACKAGE_METHOD_VERSION,
        "scientific_standing": scientific_standing,
        "software_validation_fingerprint": software_validation_fingerprint,
    }
    decision_fingerprint = _sha256_hex(_canonical_json(fingerprint_payload).encode("utf-8"))

    # Build model — it will re-validate decision_fingerprint binding and
    # receipt presence rules.
    return ManchesterBaselineAcceptanceDecision(
        candidate_fingerprint=candidate.fingerprint(),
        candidate_package_id=candidate.package_id,
        scientific_standing=scientific_standing,
        decided_by=decided_by,
        decided_at_utc=decided_at_utc,
        rationale=rationale,
        prerequisites_verified=sorted_prereq,
        rejection_reasons=sorted_reasons,
        software_validation_fingerprint=software_validation_fingerprint,
        candidate_build_receipt_fingerprint=candidate_build_receipt_fingerprint,
        decision_fingerprint=decision_fingerprint,
    )


def verify_baseline_acceptance(
    decision: ManchesterBaselineAcceptanceDecision,
    candidate: ManchesterBaselineCandidatePackage,
    software_validation: ManchesterBaselineSoftwareValidation | None,
) -> None:
    """Verify a decision against the exact candidate and software validation.

    Fails closed via :class:`ManchesterBaselinePackageError` unless **every**
    identity, standing, prerequisite, timestamp, provider/rights/map-match/
    calibration/build-receipt precondition still matches the exact objects
    supplied. Reuses :func:`_check_scientific_acceptance_preconditions` so
    builder and verifier cannot drift.

    The function does not invent or retrieve provider evidence, does not
    perform I/O, does not consult current time, and never self-upgrades
    ``scientific_standing`` — a ``SCIENTIFICALLY_NOT_ACCEPTED`` or
    ``PROVIDER_DATA_REQUIRED`` decision remains non-accepted even when the
    candidate would now satisfy production preconditions.

    A structurally self-consistent decision (matching ``decision_fingerprint``)
    is **not** sufficient for scientific standing; only successful verification
    against the exact fingerprints proves the binding. The fingerprint itself
    is a plain SHA-256 digest and does not provide cryptographic authenticity.
    """
    # 1. Canonical revalidation: fingerprint must still bind the decision's
    #    own fields (catches model_copy mutation where fingerprint was not
    #    updated, or where new binding fields were altered).
    try:
        ManchesterBaselineAcceptanceDecision.model_validate(decision.model_dump())
    except Exception as exc:
        raise ManchesterBaselinePackageError(
            "CANDIDATE_TAMPERED",
            f"decision revalidation failed: {exc}",
        ) from exc

    # 2. Exact candidate binding
    if decision.candidate_fingerprint != candidate.fingerprint():
        raise ManchesterBaselinePackageError(
            "MISMATCHED_CANDIDATE_FINGERPRINT",
            "decision candidate_fingerprint does not match exact candidate",
        )
    if decision.candidate_package_id != candidate.package_id:
        raise ManchesterBaselinePackageError(
            "MISMATCHED_CANDIDATE_FINGERPRINT",
            "decision candidate_package_id does not match exact candidate",
        )

    # 3. Standing-specific binding checks
    if decision.scientific_standing == "SCIENTIFICALLY_ACCEPTED_BASELINE":
        # Build-receipt binding for accepted: must match exact candidate receipt
        if decision.candidate_build_receipt_fingerprint != candidate.build_receipt_fingerprint:
            raise ManchesterBaselinePackageError(
                "BUILD_RECEIPT_MISSING",
                "decision build receipt binding does not match exact candidate",
            )
        if software_validation is None:
            raise ManchesterBaselinePackageError(
                "SOFTWARE_NOT_VALID",
                "accepted decision verification requires exact software validation",
            )
        if decision.software_validation_fingerprint is None:
            raise ManchesterBaselinePackageError(
                "SOFTWARE_NOT_VALID",
                "accepted decision lacks software_validation_fingerprint binding",
            )
        if decision.software_validation_fingerprint != software_validation.fingerprint():
            raise ManchesterBaselinePackageError(
                "MISMATCHED_CANDIDATE_FINGERPRINT",
                "decision software_validation_fingerprint does not match exact validation",
            )
        # Software validation must itself be bound to the exact candidate
        if software_validation.candidate_fingerprint != candidate.fingerprint():
            raise ManchesterBaselinePackageError(
                "MISMATCHED_CANDIDATE_FINGERPRINT",
                "software validation references a different candidate than decision",
            )
        # Temporal ordering + all production preconditions via shared checker
        _check_scientific_acceptance_preconditions(
            candidate=candidate,
            software_validation=software_validation,
            prerequisites_verified=decision.prerequisites_verified,
            decided_at_utc=decision.decided_at_utc,
        )
        # Also ensure decision's own verified prerequisites exactly equal
        # candidate's declared prerequisites (already checked inside helper,
        # but double-check decision field matches candidate).
        if set(decision.prerequisites_verified) != set(candidate.prerequisites):
            raise ManchesterBaselinePackageError(
                "MISSING_PREREQUISITES",
                "decision prerequisites_verified does not match candidate prerequisites",
            )
        # Rejection reasons must be empty for accepted (model already enforces)
        if decision.rejection_reasons:
            raise ManchesterBaselinePackageError(
                "EVIDENCE_NOT_PRODUCTION",
                "accepted decision must not carry rejection reasons",
            )
    else:
        # Non-accepted / provider-blocked must carry no receipt bindings and
        # must be coherent; verification must not upgrade standing.
        if decision.software_validation_fingerprint is not None:
            raise ManchesterBaselinePackageError(
                "SOFTWARE_NOT_VALID",
                "non-accepted decision must not carry software binding",
            )
        if decision.candidate_build_receipt_fingerprint is not None:
            raise ManchesterBaselinePackageError(
                "BUILD_RECEIPT_MISSING",
                "non-accepted decision must not carry build receipt binding",
            )
        # For PROVIDER_DATA_REQUIRED, ensure truthful provider absence; do not
        # invent evidence.
        if decision.scientific_standing == "PROVIDER_DATA_REQUIRED":
            if not candidate.provider_data_required:
                raise ManchesterBaselinePackageError(
                    "PROVIDER_DATA_REQUIRED",
                    "PROVIDER_DATA_REQUIRED decision requires truthful provider_data_required",
                )
            if "PROVIDER_DATA_REQUIRED" not in decision.rejection_reasons:
                raise ManchesterBaselinePackageError(
                    "PROVIDER_DATA_REQUIRED",
                    "PROVIDER_DATA_REQUIRED decision must carry that rejection reason",
                )
        # SCIENTIFICALLY_NOT_ACCEPTED remains non-accepted even if candidate now
        # satisfies production — do not self-upgrade.


def _helper_canonical_fingerprint_for_candidate(
    candidate: ManchesterBaselineCandidatePackage,
) -> str:
    return candidate.fingerprint()


# Convenience for deterministic building in tests
def make_synthetic_candidate(
    *,
    package_id: str = "synthetic-baseline-001",
    rights_standing: RightsStanding = "ODbL-1.0",
    provider_data_required: bool = True,
    approved_map_match: bool = False,
) -> ManchesterBaselineCandidatePackage:
    """Return a minimal valid synthetic engineering candidate.

    Software-valid, scientifically blocked.
    """
    now = datetime.now(UTC)
    # deterministic portable file
    pf = PortableNetworkFile(
        relative_path="networks/synthetic/network.xml",
        sha256="a" * 64,
        byte_size=12345,
        media_type="application/xml",
    )
    inv = [{"relative_path": pf.relative_path, "sha256": pf.sha256, "byte_size": pf.byte_size}]
    net_sha = _sha256_hex(_canonical_json(inv).encode("utf-8"))
    geo = GeographicIdentity(
        envelope_fingerprint="b" * 64,
        boundary_asset_sha256="c" * 64,
        boundary_asset_name="greater_manchester_combined_authority.geojson",
    )
    net = NetworkIdentity(
        tool_reported_version="1.27.1",
        tool_executable_sha256="d" * 64,
        network_files=(pf,),
        network_identity_sha256=net_sha,
        edge_count=100,
        junction_count=50,
    )
    bound_payload = {
        "scope": "greater_manchester_combined_authority",
        "asset_sha256": "c" * 64,
        "asset_name": "greater_manchester_combined_authority.geojson",
    }
    bound_fp = _sha256_hex(_canonical_json(bound_payload).encode("utf-8"))
    boundary = BoundaryIdentity(
        scope="greater_manchester_combined_authority",
        asset_sha256="c" * 64,
        asset_name="greater_manchester_combined_authority.geojson",
        identity_fingerprint=bound_fp,
    )
    demand = DemandIdentity(
        identity_fingerprint="e" * 64,
        source_snapshot_ids=(),
        provider_evidence_available=not provider_data_required,
    )
    mmap = MapMatchPolicyIdentity(
        policy_id="manchester-dft-map-match-owner-policy-1.1",
        policy_fingerprint="f" * 64,
        approved_for_manchester=approved_map_match,
        requires_named_person_review=True,
    )
    cal = CalibrationIdentity(
        contract_fingerprint=None,
        receipt_fingerprint=None,
        contract_version=None,
        evidence_class="synthetic_development",
        calibration_performed=False,
    )
    src = SourceAndRights(
        source_standing="PROVIDER_DATA_REQUIRED"
        if provider_data_required
        else "SYNTHETIC_ENGINEERING",
        evidence_standing="PROVIDER_DATA_REQUIRED"
        if provider_data_required
        else "SYNTHETIC_ENGINEERING",
        evidence_class="synthetic_test_only" if provider_data_required else "synthetic_development",
        rights_standing=rights_standing,
        licence_id="ODbL-1.0"
        if rights_standing not in ("UNKNOWN", "UNLICENSED")
        else rights_standing,
        attribution_text="© OpenStreetMap contributors, ODbL 1.0",
        rights_required_for_acceptance=True,
    )
    prov = BaselineProvenance(
        created_at_utc=now,
        created_by="test-engineer@example.com",
        software_version="0.7.0",
    )
    return ManchesterBaselineCandidatePackage(
        package_id=package_id,
        geographic_identity=geo,
        network_identity=net,
        boundary_identity=boundary,
        demand_identity=demand,
        map_match_policy_identity=mmap,
        calibration_identity=cal,
        source_and_rights=src,
        limitations=(
            "Synthetic engineering baseline only: no provider calibration or scientific evidence",
        ),
        provenance=prov,
        provider_data_required=provider_data_required,
        prerequisites=tuple(sorted(["boundary", "demand", "network"])),
    )


BaselineBoundaryIdentity = BoundaryIdentity
BaselineDemandIdentity = DemandIdentity
BaselineCalibrationIdentity = CalibrationIdentity
BaselineMapMatchPolicyIdentity = MapMatchPolicyIdentity

__all__ = [
    "MANCHESTER_BASELINE_PACKAGE_CAPABILITY_ID",
    "MANCHESTER_BASELINE_PACKAGE_METHOD_VERSION",
    "MANCHESTER_BASELINE_PACKAGE_SCHEMA_VERSION",
    "PROVIDER_DATA_REQUIRED",
    "SCIENTIFICALLY_ACCEPTED_BASELINE",
    "SCIENTIFICALLY_NOT_ACCEPTED",
    "SOFTWARE_INVALID",
    "SOFTWARE_VALID",
    "BaselineBoundaryIdentity",
    "BaselineCalibrationIdentity",
    "BaselineDemandIdentity",
    "BaselineMapMatchPolicyIdentity",
    "BaselinePackageModel",
    "BaselineProvenance",
    "BoundaryIdentity",
    "CalibrationIdentity",
    "DemandIdentity",
    "GeographicIdentity",
    "ManchesterBaselineAcceptanceDecision",
    "ManchesterBaselineCandidatePackage",
    "ManchesterBaselinePackageError",
    "ManchesterBaselineSoftwareValidation",
    "MapMatchPolicyIdentity",
    "NetworkIdentity",
    "PortableNetworkFile",
    "SourceAndRights",
    "build_candidate_package",
    "decide_baseline_acceptance",
    "make_synthetic_candidate",
    "validate_candidate_software",
    "verify_baseline_acceptance",
]

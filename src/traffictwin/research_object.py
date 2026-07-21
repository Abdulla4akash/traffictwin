"""Deterministic, permission-aware RO-Crate archival export for TrafficTwin."""

from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import os
import re
import sys
import tempfile
import zipfile
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Self
from urllib.parse import quote, unquote

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.ingestion.bundle import BundleValidationResult, validate_bundle
from traffictwin.ingestion.cache import canonical_schema_fingerprint, manifest_mapping_fingerprint
from traffictwin.ingestion.hashes import bundle_fingerprint
from traffictwin.ingestion.loader import BundleLoadError, open_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.provenance.builder import build_run_trace
from traffictwin.release.metadata import current_release_metadata
from traffictwin.reporting.builder import build_run_report
from traffictwin.reporting.html import report_to_html
from traffictwin.reporting.markdown import report_to_markdown
from traffictwin.rules.engine import evaluate_rules

RESEARCH_OBJECT_SCHEMA_VERSION: Literal["1.0"] = "1.0"
RESEARCH_OBJECT_CONTRACT_VERSION: Literal["traffictwin-ro-crate-v1"] = "traffictwin-ro-crate-v1"
RESEARCH_OBJECT_CAPABILITY_ID: Literal["OPS-04"] = "OPS-04"
RO_CRATE_VERSION: Literal["1.3"] = "1.3"
RO_CRATE_CONTEXT = "https://w3id.org/ro/crate/1.3/context"
RO_CRATE_SPECIFICATION = "https://w3id.org/ro/crate/1.3"
CFF_VERSION: Literal["1.2.0"] = "1.2.0"
MAX_RAW_FILE_COUNT = 64
MAX_RAW_FILE_BYTES = 10_000_000
MAX_RAW_TOTAL_BYTES = 10_000_000
MAX_ARCHIVE_FILE_COUNT = 128
MAX_ARCHIVE_MEMBER_BYTES = 20_000_000
MAX_ARCHIVE_TOTAL_BYTES = 50_000_000
REQUIRED_ARCHIVE_MEMBERS = (
    "CITATION.cff",
    "checksums.sha256",
    "research-object-manifest.json",
    "ro-crate-metadata.json",
)
_FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_PATH = re.compile(r"(?i)(?<![\w])(?:[a-z]:[\\/][^\s\"'<>]+)")
_FILE_URI = re.compile(r"(?i)file://[^\s\"'<>]+")
_HOME_PATH = re.compile(r"(?<![\w])~[/\\][^\s\"'<>]+")
_POSIX_PATH = re.compile(r"(?<![/\w])/(?!/)[^\s\"'<>]+")
_PATH_REDACTION = "[redacted absolute path]"


class ResearchObjectError(ValueError):
    """Raised when an archival request cannot be satisfied safely."""


class ResearchObjectModel(BaseModel):
    """Strict base for OPS-04 models."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class RawEvidenceDisposition(StrEnum):
    """How raw evidence is represented in the research object."""

    EMBED = "embed"
    REFERENCE = "reference"
    EXCLUDE = "exclude"


class PublicationScope(StrEnum):
    """Declared audience for the generated archive."""

    PRIVATE = "private"
    PUBLIC = "public"


class PermissionStatus(StrEnum):
    """Explicit permission state for raw evidence."""

    NOT_REQUIRED = "not_required"
    CONFIRMED = "confirmed"
    UNKNOWN = "unknown"
    DENIED = "denied"


class InventoryDisposition(StrEnum):
    """Whether one inventory entry is physically present or externally referenced."""

    EMBEDDED = "embedded"
    REFERENCED = "referenced"


class CitationAuthor(ResearchObjectModel):
    """CFF-compatible person identity."""

    given_names: str = Field(min_length=1, max_length=200)
    family_names: str = Field(min_length=1, max_length=200)
    orcid: str | None = Field(default=None, pattern=r"^https://orcid\.org/[0-9X-]+$")
    affiliation: str | None = Field(default=None, min_length=1, max_length=300)

    @model_validator(mode="after")
    def reject_local_paths(self) -> Self:
        """Keep caller-supplied citation identity free of local absolute paths."""

        for value in (self.given_names, self.family_names, self.orcid, self.affiliation):
            if value is not None and _safe_text(value) != value:
                raise ValueError("citation author fields must not contain absolute local paths")
        return self


def _default_authors() -> list[CitationAuthor]:
    return [CitationAuthor(given_names="Abdulla Al Mamun", family_names="Akash")]


class ResearchObjectRequest(ResearchObjectModel):
    """Complete caller-owned publication and raw-evidence policy."""

    schema_version: Literal["1.0"] = RESEARCH_OBJECT_SCHEMA_VERSION
    publication_date: date
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, min_length=1, max_length=2_000)
    authors: list[CitationAuthor] = Field(
        default_factory=_default_authors,
        min_length=1,
        max_length=20,
    )
    publication_scope: PublicationScope = PublicationScope.PRIVATE
    raw_evidence: RawEvidenceDisposition = RawEvidenceDisposition.REFERENCE
    permission_status: PermissionStatus = PermissionStatus.UNKNOWN
    permission_basis: str | None = Field(default=None, min_length=1, max_length=2_000)
    licence_statement: str = Field(
        default=(
            "TrafficTwin repository licence is not specified; this crate grants no additional "
            "reuse rights."
        ),
        min_length=1,
        max_length=2_000,
    )
    raw_evidence_licence: str | None = Field(default=None, min_length=1, max_length=1_000)
    persistent_identifier: str | None = Field(default=None, min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def validate_permission_declaration(self) -> Self:
        """Reject contradictory or evidence-free permission assertions."""

        if self.permission_status is PermissionStatus.CONFIRMED and not self.permission_basis:
            raise ValueError("confirmed raw-evidence permission requires permission_basis")
        if (
            self.permission_status is PermissionStatus.DENIED
            and self.raw_evidence is not RawEvidenceDisposition.EXCLUDE
        ):
            raise ValueError("denied raw evidence must use raw_evidence=exclude")
        for value in (
            self.title,
            self.description,
            self.permission_basis,
            self.licence_statement,
            self.raw_evidence_licence,
            self.persistent_identifier,
        ):
            if value is not None and _safe_text(value) != value:
                raise ValueError(
                    "research-object declarations must not contain absolute local paths"
                )
        return self

    def canonical_json(self) -> str:
        """Return stable request JSON."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Fingerprint every caller-owned archival decision."""

        return _sha256(self.canonical_json().encode("utf-8"))


class ResolvedInclusionPolicy(ResearchObjectModel):
    """Source-aware policy actually applied by the builder."""

    publication_scope: PublicationScope
    raw_evidence: RawEvidenceDisposition
    permission_status: PermissionStatus
    permission_basis: str
    licence_statement: str
    raw_evidence_licence: str
    synthetic: bool
    row_level_provenance_included: bool
    path_redaction: bool = True


class ResearchObjectInventoryEntry(ResearchObjectModel):
    """Checksummed embedded payload or explicit raw-evidence reference."""

    role: str = Field(pattern=r"^[a-z0-9_.-]+$")
    disposition: InventoryDisposition
    crate_path: str | None = None
    source_path: str | None = None
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_size: int = Field(ge=0)
    encoding_format: str = Field(min_length=1)
    synthetic: bool
    licence: str

    @model_validator(mode="after")
    def validate_paths(self) -> Self:
        """Keep embedded and referenced path semantics disjoint."""

        if self.disposition is InventoryDisposition.EMBEDDED:
            if self.crate_path is None:
                raise ValueError("embedded inventory entries require crate_path")
            _validate_archive_name(self.crate_path)
        elif self.crate_path is not None:
            raise ValueError("referenced inventory entries cannot declare crate_path")
        if self.source_path is not None:
            _validate_source_relative_path(self.source_path)
        return self


class ResearchObjectExclusion(ResearchObjectModel):
    """Aggregate exclusion that intentionally carries no raw identifier or checksum."""

    category: str
    count: int = Field(gt=0)
    reason: str
    identifiers_included: bool = False
    checksums_included: bool = False


class ResearchObjectSource(ResearchObjectModel):
    """Exact source identity without an absolute local path."""

    bundle_id: str
    run_id: str
    source_mode: Literal["synthetic", "imported_historical"]
    bundle_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_file_count: int = Field(ge=0)
    raw_total_bytes: int = Field(ge=0)
    raw_evidence: RawEvidenceDisposition


class ResearchObjectSoftware(ResearchObjectModel):
    """Software and method versions used to build the crate."""

    package: str
    version: str
    python_version: str
    canonical_schema_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_mapping_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    validator_version: str
    metric_version: str
    evidence_schema_version: str
    diagnostic_schema_version: str
    ruleset_version: str
    provenance_schema_version: str


class ResearchObjectManifest(ResearchObjectModel):
    """TrafficTwin research-object inventory linking all typed artifacts."""

    schema_version: Literal["1.0"] = RESEARCH_OBJECT_SCHEMA_VERSION
    capability_id: Literal["OPS-04"] = RESEARCH_OBJECT_CAPABILITY_ID
    contract_version: Literal["traffictwin-ro-crate-v1"] = RESEARCH_OBJECT_CONTRACT_VERSION
    ro_crate_version: Literal["1.3"] = RO_CRATE_VERSION
    cff_version: Literal["1.2.0"] = CFF_VERSION
    object_id: str = Field(pattern=r"^urn:traffictwin:research-object:[0-9a-f]{64}$")
    title: str
    description: str
    publication_date: date
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source: ResearchObjectSource
    policy: ResolvedInclusionPolicy
    software: ResearchObjectSoftware
    inventory: list[ResearchObjectInventoryEntry]
    exclusions: list[ResearchObjectExclusion] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    integrity_statements: list[str]

    @model_validator(mode="after")
    def validate_inventory(self) -> Self:
        """Require stable unique inventory identities and complete raw accounting."""

        crate_paths = [entry.crate_path for entry in self.inventory if entry.crate_path is not None]
        if len(crate_paths) != len(set(crate_paths)):
            raise ValueError("research-object inventory contains duplicate crate paths")
        source_paths = [
            entry.source_path for entry in self.inventory if entry.source_path is not None
        ]
        if len(source_paths) != len(set(source_paths)):
            raise ValueError("research-object inventory contains duplicate source paths")
        represented = len(source_paths)
        excluded = sum(item.count for item in self.exclusions if item.category == "raw_evidence")
        if represented + excluded != self.source.raw_file_count:
            raise ValueError("raw inventory and exclusions do not reconcile to raw_file_count")
        return self

    def canonical_json(self) -> str:
        """Return stable manifest JSON."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Fingerprint the complete non-self-referential inventory."""

        return _sha256(self.canonical_json().encode("utf-8"))


class ResearchObjectContract(ResearchObjectModel):
    """Published OPS-04 method and safety contract."""

    schema_version: Literal["1.0"] = RESEARCH_OBJECT_SCHEMA_VERSION
    capability_id: Literal["OPS-04"] = RESEARCH_OBJECT_CAPABILITY_ID
    contract_version: Literal["traffictwin-ro-crate-v1"] = RESEARCH_OBJECT_CONTRACT_VERSION
    ro_crate_specification: str = RO_CRATE_SPECIFICATION
    ro_crate_context: str = RO_CRATE_CONTEXT
    cff_version: Literal["1.2.0"] = CFF_VERSION
    source_boundary: str
    raw_evidence_modes: dict[str, str]
    public_permission_policy: list[str]
    deterministic_publication: list[str]
    required_members: list[str]
    embedded_artifact_roles: list[str]
    checksum_policy: str
    redaction_policy: str
    limits: dict[str, int]
    exclusions: list[str]

    def canonical_json(self) -> str:
        """Return stable contract JSON."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Fingerprint the archival method contract."""

        return _sha256(self.canonical_json().encode("utf-8"))


class ResearchObjectArchiveReceipt(ResearchObjectModel):
    """Receipt for one verified atomic ZIP publication."""

    archive_name: str
    archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    archive_size: int = Field(gt=0)
    object_id: str
    manifest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    member_count: int = Field(gt=0)
    embedded_count: int = Field(ge=0)
    referenced_count: int = Field(ge=0)
    raw_evidence: RawEvidenceDisposition
    deterministic_zip: bool = True
    verified_before_publication: bool = True


class ResearchObjectVerification(ResearchObjectModel):
    """Bounded offline verification result for an attached RO-Crate ZIP."""

    valid: bool
    archive_sha256: str | None = None
    object_id: str | None = None
    manifest_fingerprint: str | None = None
    member_count: int = Field(default=0, ge=0)
    checksum_count: int = Field(default=0, ge=0)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class _CffAuthor(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    given_names: str = Field(alias="given-names")
    family_names: str = Field(alias="family-names")
    orcid: str | None = None
    affiliation: str | None = None


class _CitationFile(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    cff_version: Literal["1.2.0"] = Field(alias="cff-version")
    message: str
    type: Literal["dataset"]
    title: str
    authors: list[_CffAuthor] = Field(min_length=1)
    version: str
    date_released: date = Field(alias="date-released")
    abstract: str
    keywords: list[str]
    identifiers: list[dict[str, str]] | None = None


@dataclass(frozen=True)
class BuiltResearchObject:
    """In-memory crate ready for deterministic packaging."""

    manifest: ResearchObjectManifest
    members: dict[str, bytes]


@dataclass(frozen=True)
class _RawFile:
    relative_path: str
    content: bytes
    sha256: str
    encoding_format: str


def research_object_contract() -> ResearchObjectContract:
    """Return the versioned OPS-04 contract."""

    return ResearchObjectContract(
        source_boundary=(
            "One accepted ordinary generic directory or ZIP bundle. SUMO and TOS remain explicit "
            "unsupported source-specific boundaries for OPS-04 v1."
        ),
        raw_evidence_modes={
            "embed": "Copy bounded raw files only for synthetic or explicitly permitted evidence.",
            "reference": (
                "Retain relative names, sizes, and SHA-256 identities without copying raw bytes."
            ),
            "exclude": ("Retain only an aggregate exclusion count/reason; no raw names or hashes."),
        },
        public_permission_policy=[
            "Unknown or denied external raw evidence must be excluded from a public crate.",
            (
                "Embedding external raw evidence requires confirmed permission, a written basis, "
                "and a licence statement."
            ),
            (
                "TrafficTwin-labelled synthetic evidence resolves to permission not_required but "
                "remains visibly synthetic."
            ),
        ],
        deterministic_publication=[
            (
                "Caller supplies publication_date; all derived artifact timestamps use midnight "
                "UTC on that date."
            ),
            (
                "Archive members are sorted, uncompressed, and carry one fixed ZIP timestamp and "
                "permission mode."
            ),
            (
                "The complete crate is built and verified in memory before an atomic destination "
                "replacement."
            ),
        ],
        required_members=list(REQUIRED_ARCHIVE_MEMBERS),
        embedded_artifact_roles=[
            "source_manifest",
            "validation",
            "canonical_contract",
            "metrics",
            "evidence_pack",
            "diagnostics",
            "provenance",
            "structured_report",
            "markdown_report",
            "html_report",
            "software_metadata",
            "inclusion_policy",
            "citation",
        ],
        checksum_policy=(
            "checksums.sha256 covers every payload member and research-object-manifest.json; "
            "ro-crate-metadata.json is structurally verified and the receipt fingerprints the "
            "complete ZIP bytes."
        ),
        redaction_policy=(
            "Absolute POSIX, Windows, home-relative, and file-URI paths are redacted from derived "
            "JSON and report artifacts; archive inventory paths are crate- or bundle-relative."
        ),
        limits={
            "max_raw_file_count": MAX_RAW_FILE_COUNT,
            "max_raw_file_bytes": MAX_RAW_FILE_BYTES,
            "max_raw_total_bytes": MAX_RAW_TOTAL_BYTES,
            "max_archive_file_count": MAX_ARCHIVE_FILE_COUNT,
            "max_archive_member_bytes": MAX_ARCHIVE_MEMBER_BYTES,
            "max_archive_total_bytes": MAX_ARCHIVE_TOTAL_BYTES,
        },
        exclusions=[
            (
                "No registry, cache, credentials, external package, simulator, or network "
                "resource is discovered or copied."
            ),
            (
                "No DOI, repository URL, licence, publication permission, or scientific validity "
                "is inferred."
            ),
            "No metric, diagnostic, or provenance logic is implemented in the archive renderer.",
        ],
    )


def build_research_object(
    bundle: str | Path,
    request: ResearchObjectRequest,
) -> BuiltResearchObject:
    """Build a deterministic attached RO-Crate entirely in memory."""

    source = Path(bundle)
    if source.is_symlink():
        raise ResearchObjectError("research-object source must not be a symbolic link")
    try:
        with open_bundle(source, max_uncompressed_bytes=MAX_RAW_TOTAL_BYTES) as workspace:
            if workspace.root.is_symlink():
                raise ResearchObjectError("research-object workspace must not be a symbolic link")
            result = validate_bundle(workspace.root)
            _require_accepted_bundle(result)
            raw_files = _read_raw_files(workspace.root)
            expected = bundle_fingerprint(
                [workspace.root / item.relative_path for item in raw_files],
                workspace.root,
            )
            if result.fingerprint != expected:
                raise ResearchObjectError("raw bundle changed while the research object was built")
            return _build_from_open_bundle(workspace.root, result, raw_files, request)
    except (BundleLoadError, OSError, zipfile.BadZipFile) as exc:
        raise ResearchObjectError(str(exc)) from exc


def create_research_object_archive(
    bundle: str | Path,
    destination: str | Path,
    request: ResearchObjectRequest,
    *,
    overwrite: bool = False,
) -> ResearchObjectArchiveReceipt:
    """Build, verify, and atomically publish a deterministic RO-Crate ZIP."""

    target = Path(destination)
    _validate_destination(target, overwrite=overwrite)
    built = build_research_object(bundle, request)
    archive = _zip_bytes(built.members)
    verification = verify_research_object_bytes(archive)
    if not verification.valid:
        raise ResearchObjectError(
            "generated research object failed verification: " + "; ".join(verification.errors)
        )
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(archive)
            handle.flush()
            os.fsync(handle.fileno())
        if target.is_symlink():
            raise ResearchObjectError("research-object destination must not be a symbolic link")
        if target.exists() and not overwrite:
            raise FileExistsError(f"research-object destination already exists: {target}")
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return ResearchObjectArchiveReceipt(
        archive_name=target.name,
        archive_sha256=_sha256(archive),
        archive_size=len(archive),
        object_id=built.manifest.object_id,
        manifest_fingerprint=built.manifest.fingerprint(),
        member_count=len(built.members),
        embedded_count=sum(
            entry.disposition is InventoryDisposition.EMBEDDED for entry in built.manifest.inventory
        ),
        referenced_count=sum(
            entry.disposition is InventoryDisposition.REFERENCED
            for entry in built.manifest.inventory
        ),
        raw_evidence=built.manifest.source.raw_evidence,
    )


def verify_research_object(path: str | Path) -> ResearchObjectVerification:
    """Verify an OPS-04 ZIP without extracting or changing it."""

    source = Path(path)
    if source.is_symlink() or not source.is_file():
        return ResearchObjectVerification(
            valid=False,
            errors=["research-object archive must be a direct non-symlink file"],
        )
    try:
        payload = source.read_bytes()
    except OSError as exc:
        return ResearchObjectVerification(valid=False, errors=[str(exc)])
    return verify_research_object_bytes(payload)


def verify_research_object_bytes(payload: bytes) -> ResearchObjectVerification:
    """Verify bounded ZIP structure, CFF, RO-Crate metadata, manifest, and checksums."""

    archive_sha256 = _sha256(payload)
    errors: list[str] = []
    warnings: list[str] = []
    object_id: str | None = None
    manifest_fingerprint: str | None = None
    checksum_count = 0
    member_count = 0
    if len(payload) > MAX_ARCHIVE_TOTAL_BYTES:
        return ResearchObjectVerification(
            valid=False,
            archive_sha256=archive_sha256,
            errors=["research-object archive exceeds the total-byte ceiling"],
        )
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            infos = archive.infolist()
            member_count = len(infos)
            _validate_archive_infos(infos)
            members = {info.filename: archive.read(info) for info in infos}
    except (OSError, ResearchObjectError, zipfile.BadZipFile, RuntimeError) as exc:
        return ResearchObjectVerification(
            valid=False,
            archive_sha256=archive_sha256,
            member_count=member_count,
            errors=[str(exc)],
        )
    missing = sorted(set(REQUIRED_ARCHIVE_MEMBERS) - set(members))
    if missing:
        errors.append("missing required members: " + ", ".join(missing))
    manifest: ResearchObjectManifest | None = None
    if "research-object-manifest.json" in members:
        try:
            manifest = ResearchObjectManifest.model_validate_json(
                members["research-object-manifest.json"]
            )
            object_id = manifest.object_id
            manifest_fingerprint = manifest.fingerprint()
        except (ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid research-object manifest: {exc}")
    if "CITATION.cff" in members:
        try:
            parsed_cff = yaml.safe_load(members["CITATION.cff"])
            _CitationFile.model_validate(parsed_cff)
        except (ValueError, yaml.YAMLError) as exc:
            errors.append(f"invalid CITATION.cff: {exc}")
    checksums: dict[str, str] = {}
    if "checksums.sha256" in members:
        try:
            checksums = _parse_checksums(members["checksums.sha256"])
            checksum_count = len(checksums)
        except ResearchObjectError as exc:
            errors.append(str(exc))
    expected_checksum_members = set(members) - {"checksums.sha256", "ro-crate-metadata.json"}
    if checksums and set(checksums) != expected_checksum_members:
        errors.append("checksum inventory does not match archive payload members")
    for name, expected in checksums.items():
        content = members.get(name)
        if content is None or _sha256(content) != expected:
            errors.append(f"checksum mismatch: {name}")
    if manifest is not None:
        _verify_manifest_inventory(manifest, members, checksums, errors)
    if "ro-crate-metadata.json" in members:
        _verify_ro_crate_metadata(members["ro-crate-metadata.json"], members, errors)
    if (
        manifest is not None
        and manifest.policy.publication_scope is PublicationScope.PUBLIC
        and manifest.source.source_mode == "imported_historical"
        and manifest.source.raw_evidence is not RawEvidenceDisposition.EXCLUDE
        and manifest.policy.permission_status is not PermissionStatus.CONFIRMED
    ):
        errors.append("public external raw evidence lacks confirmed permission")
    return ResearchObjectVerification(
        valid=not errors,
        archive_sha256=archive_sha256,
        object_id=object_id,
        manifest_fingerprint=manifest_fingerprint,
        member_count=member_count,
        checksum_count=checksum_count,
        errors=sorted(set(errors)),
        warnings=warnings,
    )


def _build_from_open_bundle(
    root: Path,
    result: BundleValidationResult,
    raw_files: list[_RawFile],
    request: ResearchObjectRequest,
) -> BuiltResearchObject:
    manifest = result.manifest
    assert manifest is not None
    assert result.fingerprint is not None
    if request.raw_evidence is RawEvidenceDisposition.EXCLUDE:
        request = _request_without_raw_identifiers(request, raw_files)
    policy = _resolve_policy(request, synthetic=manifest.environment.name == "synthetic")
    fixed_time = datetime.combine(request.publication_date, time.min, tzinfo=UTC)
    normalised_report = result.report.model_copy(update={"import_timestamp": fixed_time}, deep=True)
    stable_result = replace(
        result,
        source=Path(manifest.bundle.bundle_id),
        report=normalised_report,
    )

    def clock() -> datetime:
        return fixed_time

    metrics = compute_metrics_for_bundle(stable_result, clock=clock)
    evidence = build_evidence_pack(stable_result, metrics, clock=clock)
    evidence = evidence.model_copy(
        update={
            "provenance": {
                **evidence.provenance,
                "bundle_source": f"urn:sha256:{result.fingerprint}",
            }
        },
        deep=True,
    )
    diagnostics = evaluate_rules(evidence, clock=clock)
    provenance = build_run_trace(
        stable_result,
        metrics,
        evidence,
        diagnostics,
        clock=clock,
        sample_limit=25 if policy.row_level_provenance_included else 0,
    )
    report = build_run_report(root, clock=clock).model_copy(
        update={"source_reference": f"urn:sha256:{result.fingerprint}"},
        deep=True,
    )
    title = request.title or f"TrafficTwin research object for {manifest.run.run_id}"
    description = request.description or (
        "Deterministic TrafficTwin metrics, evidence, diagnostic hypotheses, provenance, and "
        f"reports for run {manifest.run.run_id}."
    )
    software = ResearchObjectSoftware(
        package="traffictwin",
        version=current_release_metadata().version,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        canonical_schema_fingerprint=canonical_schema_fingerprint(),
        manifest_mapping_fingerprint=manifest_mapping_fingerprint(manifest),
        validator_version=normalised_report.validator_version,
        metric_version=metrics.metric_version,
        evidence_schema_version=evidence.schema_version,
        diagnostic_schema_version=diagnostics.schema_version,
        ruleset_version=diagnostics.ruleset_version,
        provenance_schema_version=provenance.schema_version,
    )
    canonical_contract = {
        "schema_version": RESEARCH_OBJECT_SCHEMA_VERSION,
        "bundle_manifest_schema_version": manifest.schema_version,
        "canonical_schema_fingerprint": software.canonical_schema_fingerprint,
        "manifest_mapping_fingerprint": software.manifest_mapping_fingerprint,
        "validator_version": software.validator_version,
        "metric_version": software.metric_version,
        "evidence_schema_version": software.evidence_schema_version,
        "diagnostic_schema_version": software.diagnostic_schema_version,
        "ruleset_version": software.ruleset_version,
        "provenance_schema_version": software.provenance_schema_version,
    }
    base_payloads: dict[str, tuple[bytes, str]] = {
        "artifacts/bundle-manifest.json": (
            _json_bytes(manifest.model_dump(mode="json")),
            "source_manifest",
        ),
        "artifacts/validation-report.json": (
            _json_bytes(normalised_report.model_dump(mode="json")),
            "validation",
        ),
        "artifacts/canonical-contract.json": (
            _json_bytes(canonical_contract),
            "canonical_contract",
        ),
        "artifacts/metrics.json": (
            _json_bytes(metrics.model_dump(mode="json")),
            "metrics",
        ),
        "artifacts/evidence-pack.json": (
            _json_bytes(evidence.model_dump(mode="json")),
            "evidence_pack",
        ),
        "artifacts/diagnostics.json": (
            _json_bytes(diagnostics.model_dump(mode="json")),
            "diagnostics",
        ),
        "artifacts/provenance.json": (
            _json_bytes(provenance.model_dump(mode="json")),
            "provenance",
        ),
        "artifacts/report.json": (
            _json_bytes(report.model_dump(mode="json")),
            "structured_report",
        ),
        "reports/run-report.md": (
            report_to_markdown(report).encode("utf-8"),
            "markdown_report",
        ),
        "reports/run-report.html": (
            report_to_html(report).encode("utf-8"),
            "html_report",
        ),
        "software/software-metadata.json": (
            _json_bytes(software.model_dump(mode="json")),
            "software_metadata",
        ),
        "policy/inclusion-policy.json": (
            _json_bytes(
                {
                    "request": request.model_dump(mode="json"),
                    "request_fingerprint": request.fingerprint(),
                    "resolved": policy.model_dump(mode="json"),
                }
            ),
            "inclusion_policy",
        ),
        "CITATION.cff": (
            _citation_bytes(request, title, description),
            "citation",
        ),
    }
    if policy.raw_evidence is RawEvidenceDisposition.EXCLUDE:
        base_payloads = {
            crate_path: (_exclude_raw_identifiers(content, raw_files), role)
            for crate_path, (content, role) in base_payloads.items()
        }
    inventory: list[ResearchObjectInventoryEntry] = []
    members: dict[str, bytes] = {}
    for crate_path, (content, role) in sorted(base_payloads.items()):
        _add_embedded_entry(
            inventory,
            members,
            crate_path=crate_path,
            content=content,
            role=role,
            synthetic=policy.synthetic,
            licence=request.licence_statement,
        )
    exclusions: list[ResearchObjectExclusion] = []
    if policy.raw_evidence is RawEvidenceDisposition.EMBED:
        for item in raw_files:
            _add_embedded_entry(
                inventory,
                members,
                crate_path=f"data/raw/{item.relative_path}",
                source_path=item.relative_path,
                content=item.content,
                role="raw_evidence",
                encoding_format=item.encoding_format,
                synthetic=policy.synthetic,
                licence=policy.raw_evidence_licence,
            )
    elif policy.raw_evidence is RawEvidenceDisposition.REFERENCE:
        inventory.extend(
            ResearchObjectInventoryEntry(
                role="raw_evidence",
                disposition=InventoryDisposition.REFERENCED,
                source_path=item.relative_path,
                sha256=item.sha256,
                content_size=len(item.content),
                encoding_format=item.encoding_format,
                synthetic=policy.synthetic,
                licence=policy.raw_evidence_licence,
            )
            for item in raw_files
        )
    elif raw_files:
        exclusions.append(
            ResearchObjectExclusion(
                category="raw_evidence",
                count=len(raw_files),
                reason=(
                    "Raw identifiers, names, checksums, and bytes were excluded by the declared "
                    "permission-aware policy."
                ),
            )
        )
    source = ResearchObjectSource(
        bundle_id=manifest.bundle.bundle_id,
        run_id=manifest.run.run_id,
        source_mode="synthetic" if policy.synthetic else "imported_historical",
        bundle_fingerprint=result.fingerprint,
        raw_file_count=len(raw_files),
        raw_total_bytes=sum(len(item.content) for item in raw_files),
        raw_evidence=policy.raw_evidence,
    )
    object_id = "urn:traffictwin:research-object:" + _sha256(
        _canonical_json(
            {
                "contract_version": RESEARCH_OBJECT_CONTRACT_VERSION,
                "request_fingerprint": request.fingerprint(),
                "source_fingerprint": result.fingerprint,
                "software": software.model_dump(mode="json"),
            }
        ).encode("utf-8")
    )
    research_manifest = ResearchObjectManifest(
        object_id=object_id,
        title=title,
        description=description,
        publication_date=request.publication_date,
        request_fingerprint=request.fingerprint(),
        source=source,
        policy=policy,
        software=software,
        inventory=sorted(
            inventory,
            key=lambda item: (item.crate_path or "", item.source_path or "", item.role),
        ),
        exclusions=exclusions,
        warnings=[
            _exclude_raw_identifiers(item.encode("utf-8"), raw_files).decode("utf-8")
            for item in _research_object_warnings(policy, report.warnings)
        ]
        if policy.raw_evidence is RawEvidenceDisposition.EXCLUDE
        else _research_object_warnings(policy, report.warnings),
        integrity_statements=[
            "All metrics were computed by the versioned TrafficTwin metric engine.",
            "All diagnostic hypotheses were evaluated by deterministic rules over EvidencePack.",
            "Provenance records lineage and does not establish causality.",
            "Raw source evidence was not modified while building this archive.",
        ],
    )
    members["research-object-manifest.json"] = _json_bytes(
        research_manifest.model_dump(mode="json")
    )
    checksums = {name: _sha256(content) for name, content in sorted(members.items())}
    members["checksums.sha256"] = _checksum_bytes(checksums)
    members["ro-crate-metadata.json"] = _ro_crate_metadata_bytes(
        research_manifest,
        request,
        members,
    )
    if len(members) > MAX_ARCHIVE_FILE_COUNT:
        raise ResearchObjectError("research object exceeds the archive file-count ceiling")
    if sum(len(content) for content in members.values()) > MAX_ARCHIVE_TOTAL_BYTES:
        raise ResearchObjectError("research object exceeds the archive total-byte ceiling")
    final_raw_files = _read_raw_files(root)
    if [(item.relative_path, item.sha256, len(item.content)) for item in final_raw_files] != [
        (item.relative_path, item.sha256, len(item.content)) for item in raw_files
    ]:
        raise ResearchObjectError("raw bundle changed while the research object was built")
    return BuiltResearchObject(manifest=research_manifest, members=dict(sorted(members.items())))


def _require_accepted_bundle(result: BundleValidationResult) -> None:
    if (
        not result.report.may_import
        or result.manifest is None
        or result.seed is None
        or result.fingerprint is None
    ):
        raise ResearchObjectError(
            "research-object export requires an accepted bundle with manifest, seed, and "
            "fingerprint"
        )


def _read_raw_files(root: Path) -> list[_RawFile]:
    paths = sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix())
    if any(path.is_symlink() for path in paths):
        raise ResearchObjectError("raw bundle symbolic links are not supported for archival export")
    files = [path for path in paths if path.is_file()]
    if len(files) > MAX_RAW_FILE_COUNT:
        raise ResearchObjectError("raw bundle exceeds the archival file-count ceiling")
    raw: list[_RawFile] = []
    total = 0
    for path in files:
        relative = path.relative_to(root).as_posix()
        _validate_source_relative_path(relative)
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise ResearchObjectError(f"raw evidence is unreadable: {relative}") from exc
        if len(content) > MAX_RAW_FILE_BYTES:
            raise ResearchObjectError(f"raw evidence file exceeds the byte ceiling: {relative}")
        total += len(content)
        if total > MAX_RAW_TOTAL_BYTES:
            raise ResearchObjectError("raw bundle exceeds the archival total-byte ceiling")
        raw.append(
            _RawFile(
                relative_path=relative,
                content=content,
                sha256=_sha256(content),
                encoding_format=_media_type(relative),
            )
        )
    return raw


def _resolve_policy(
    request: ResearchObjectRequest,
    *,
    synthetic: bool,
) -> ResolvedInclusionPolicy:
    permission = request.permission_status
    basis = request.permission_basis
    raw_licence = request.raw_evidence_licence
    if synthetic and permission is PermissionStatus.UNKNOWN:
        permission = PermissionStatus.NOT_REQUIRED
        basis = (
            "The source manifest labels the bundle synthetic; no external-source publication "
            "permission is inferred or required for copying these generated fixture bytes."
        )
    if permission is PermissionStatus.NOT_REQUIRED and not synthetic:
        raise ResearchObjectError(
            "permission_status=not_required is valid only for TrafficTwin-labelled synthetic "
            "evidence"
        )
    if (
        permission is PermissionStatus.DENIED
        and request.raw_evidence is not RawEvidenceDisposition.EXCLUDE
    ):
        raise ResearchObjectError("denied raw evidence must be excluded")
    if not synthetic and request.raw_evidence is RawEvidenceDisposition.EMBED:
        if permission is not PermissionStatus.CONFIRMED:
            raise ResearchObjectError(
                "embedding imported raw evidence requires confirmed permission"
            )
        if raw_licence is None:
            raise ResearchObjectError(
                "embedding imported raw evidence requires raw_evidence_licence"
            )
    if (
        request.publication_scope is PublicationScope.PUBLIC
        and not synthetic
        and request.raw_evidence is not RawEvidenceDisposition.EXCLUDE
    ):
        if permission is not PermissionStatus.CONFIRMED:
            raise ResearchObjectError(
                "public imported raw evidence must be excluded unless permission is confirmed"
            )
        if raw_licence is None:
            raise ResearchObjectError("public imported raw evidence requires raw_evidence_licence")
    if raw_licence is None:
        raw_licence = (
            "TrafficTwin-labelled synthetic evidence; repository licence remains unspecified."
            if synthetic
            else "No raw-evidence licence asserted."
        )
    if basis is None:
        basis = {
            PermissionStatus.UNKNOWN: "Raw-evidence permission is unknown.",
            PermissionStatus.DENIED: "Raw-evidence permission is denied.",
            PermissionStatus.NOT_REQUIRED: "External-source permission is not required.",
            PermissionStatus.CONFIRMED: "Raw-evidence permission was explicitly confirmed.",
        }[permission]
    return ResolvedInclusionPolicy(
        publication_scope=request.publication_scope,
        raw_evidence=request.raw_evidence,
        permission_status=permission,
        permission_basis=basis,
        licence_statement=request.licence_statement,
        raw_evidence_licence=raw_licence,
        synthetic=synthetic,
        row_level_provenance_included=(request.raw_evidence is RawEvidenceDisposition.EMBED),
    )


def _add_embedded_entry(
    inventory: list[ResearchObjectInventoryEntry],
    members: dict[str, bytes],
    *,
    crate_path: str,
    content: bytes,
    role: str,
    synthetic: bool,
    licence: str,
    source_path: str | None = None,
    encoding_format: str | None = None,
) -> None:
    _validate_archive_name(crate_path)
    if crate_path in members:
        raise ResearchObjectError(f"duplicate research-object member: {crate_path}")
    if len(content) > MAX_ARCHIVE_MEMBER_BYTES:
        raise ResearchObjectError(f"research-object member exceeds byte ceiling: {crate_path}")
    members[crate_path] = content
    inventory.append(
        ResearchObjectInventoryEntry(
            role=role,
            disposition=InventoryDisposition.EMBEDDED,
            crate_path=crate_path,
            source_path=source_path,
            sha256=_sha256(content),
            content_size=len(content),
            encoding_format=encoding_format or _media_type(crate_path),
            synthetic=synthetic,
            licence=licence,
        )
    )


def _citation_bytes(
    request: ResearchObjectRequest,
    title: str,
    description: str,
) -> bytes:
    payload: dict[str, Any] = {
        "cff-version": CFF_VERSION,
        "message": "If you use this TrafficTwin research object, cite it using this metadata.",
        "type": "dataset",
        "title": title,
        "authors": [
            {
                "given-names": author.given_names,
                "family-names": author.family_names,
                **({"orcid": author.orcid} if author.orcid is not None else {}),
                **({"affiliation": author.affiliation} if author.affiliation is not None else {}),
            }
            for author in request.authors
        ],
        "version": RESEARCH_OBJECT_SCHEMA_VERSION,
        "date-released": request.publication_date.isoformat(),
        "abstract": description,
        "keywords": [
            "TrafficTwin",
            "research object",
            "traffic simulation",
            "vehicular edge computing",
            "reproducibility",
        ],
    }
    if request.persistent_identifier is not None:
        payload["identifiers"] = [{"type": "other", "value": request.persistent_identifier}]
    rendered = yaml.safe_dump(
        payload,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    _CitationFile.model_validate(yaml.safe_load(rendered))
    return rendered.encode("utf-8")


def _ro_crate_metadata_bytes(
    manifest: ResearchObjectManifest,
    request: ResearchObjectRequest,
    members: dict[str, bytes],
) -> bytes:
    file_entities = []
    has_part = []
    inventory_by_path = {
        entry.crate_path: entry for entry in manifest.inventory if entry.crate_path is not None
    }
    for path, content in sorted(members.items()):
        if path == "ro-crate-metadata.json":
            continue
        entity_id = _uri_path(path)
        entry = inventory_by_path.get(path)
        file_entities.append(
            {
                "@id": entity_id,
                "@type": "File",
                "name": PurePosixPath(path).name,
                "description": (
                    f"TrafficTwin {entry.role.replace('_', ' ')} payload."
                    if entry is not None
                    else "TrafficTwin research-object integrity payload."
                ),
                "encodingFormat": (
                    entry.encoding_format if entry is not None else _media_type(path)
                ),
                "contentSize": len(content),
                "sha256": _sha256(content),
            }
        )
        has_part.append({"@id": entity_id})
    author_entities: list[dict[str, Any]] = []
    author_refs: list[dict[str, str]] = []
    for index, author in enumerate(request.authors, start=1):
        author_id = author.orcid or f"#author-{index:02d}"
        author_refs.append({"@id": author_id})
        author_entities.append(
            {
                "@id": author_id,
                "@type": "Person",
                "name": f"{author.given_names} {author.family_names}",
                **({"affiliation": author.affiliation} if author.affiliation is not None else {}),
            }
        )
    source_description = {
        RawEvidenceDisposition.EMBED: "Raw evidence is embedded under data/raw/.",
        RawEvidenceDisposition.REFERENCE: (
            "Raw evidence is referenced by bundle-relative name, size, and SHA-256 in the "
            "TrafficTwin research-object manifest; raw bytes are not copied."
        ),
        RawEvidenceDisposition.EXCLUDE: (
            "Raw evidence names, hashes, and bytes are excluded by the declared policy."
        ),
    }[manifest.source.raw_evidence]
    graph: list[dict[str, Any]] = [
        {
            "@id": "ro-crate-metadata.json",
            "@type": "CreativeWork",
            "about": {"@id": "./"},
            "conformsTo": {"@id": RO_CRATE_SPECIFICATION},
        },
        {
            "@id": "./",
            "@type": "Dataset",
            "name": manifest.title,
            "description": manifest.description,
            "datePublished": manifest.publication_date.isoformat(),
            "license": manifest.policy.licence_statement,
            "identifier": request.persistent_identifier or manifest.object_id,
            "author": author_refs,
            "publisher": author_refs[0],
            "hasPart": has_part,
            "mentions": [
                {"@id": "#source-bundle"},
                {"@id": "#inclusion-policy"},
                {"@id": "#traffictwin"},
                {"@id": "#archive-action"},
            ],
            "keywords": [
                "TrafficTwin",
                "research object",
                "reproducibility",
                manifest.source.source_mode,
            ],
        },
        {
            "@id": "#source-bundle",
            "@type": "CreativeWork",
            "name": f"TrafficTwin source bundle {manifest.source.bundle_id}",
            "description": source_description,
            "identifier": f"urn:sha256:{manifest.source.bundle_fingerprint}",
        },
        {
            "@id": "#inclusion-policy",
            "@type": "CreativeWork",
            "name": "TrafficTwin raw-evidence inclusion policy",
            "description": (
                f"{manifest.policy.raw_evidence.value}; "
                f"permission={manifest.policy.permission_status.value}; "
                f"scope={manifest.policy.publication_scope.value}."
            ),
        },
        {
            "@id": "#traffictwin",
            "@type": "SoftwareApplication",
            "name": "TrafficTwin",
            "version": manifest.software.version,
        },
        {
            "@id": "#archive-action",
            "@type": "CreateAction",
            "name": "Build deterministic TrafficTwin research object",
            "actionStatus": "http://schema.org/CompletedActionStatus",
            "endTime": f"{manifest.publication_date.isoformat()}T00:00:00+00:00",
            "agent": author_refs[0],
            "instrument": {"@id": "#traffictwin"},
            "object": {"@id": "#source-bundle"},
            "result": {"@id": "./"},
        },
        *author_entities,
        *file_entities,
    ]
    return _json_bytes({"@context": RO_CRATE_CONTEXT, "@graph": graph})


def _research_object_warnings(
    policy: ResolvedInclusionPolicy,
    report_warnings: list[str],
) -> list[str]:
    warnings = {
        *report_warnings,
        (
            "This research object preserves deterministic software evidence; it does not "
            "establish external validity."
        ),
        "Provenance lineage is not causal attribution.",
    }
    if policy.synthetic:
        warnings.add("Synthetic evidence is not real-world or calibrated simulation evidence.")
    if "not specified" in policy.licence_statement.lower():
        warnings.add("TrafficTwin repository licence remains unspecified.")
    if policy.permission_status is PermissionStatus.UNKNOWN:
        warnings.add("Raw-evidence permission remains unknown.")
    return sorted(warnings)


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    target = io.BytesIO()
    with zipfile.ZipFile(target, mode="w", compression=zipfile.ZIP_STORED) as archive:
        for name, content in sorted(members.items()):
            _validate_archive_name(name)
            info = zipfile.ZipInfo(name, date_time=_FIXED_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    return target.getvalue()


def _validate_archive_infos(infos: list[zipfile.ZipInfo]) -> None:
    if len(infos) > MAX_ARCHIVE_FILE_COUNT:
        raise ResearchObjectError("research-object archive exceeds the file-count ceiling")
    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise ResearchObjectError("research-object archive contains duplicate members")
    total = 0
    for info in infos:
        _validate_archive_name(info.filename)
        if info.is_dir():
            raise ResearchObjectError("research-object archive directory entries are not supported")
        if info.compress_type != zipfile.ZIP_STORED:
            raise ResearchObjectError(
                f"research-object member is not deterministically stored: {info.filename}"
            )
        if info.date_time != _FIXED_ZIP_TIMESTAMP:
            raise ResearchObjectError(
                f"research-object member has a non-deterministic timestamp: {info.filename}"
            )
        mode = info.external_attr >> 16
        if mode and (mode & 0o170000) == 0o120000:
            raise ResearchObjectError("research-object archive symbolic links are not supported")
        if info.create_system != 3 or mode != 0o100644:
            raise ResearchObjectError(
                f"research-object member has a non-deterministic file mode: {info.filename}"
            )
        if info.file_size > MAX_ARCHIVE_MEMBER_BYTES:
            raise ResearchObjectError(
                f"research-object member exceeds byte ceiling: {info.filename}"
            )
        total += info.file_size
        if total > MAX_ARCHIVE_TOTAL_BYTES:
            raise ResearchObjectError("research-object archive exceeds the total-byte ceiling")


def _parse_checksums(payload: bytes) -> dict[str, str]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ResearchObjectError("checksums.sha256 is not UTF-8") from exc
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line:
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2 or not _SHA256.fullmatch(parts[0]):
            raise ResearchObjectError("checksums.sha256 contains an invalid line")
        name = parts[1]
        _validate_archive_name(name)
        if name in result:
            raise ResearchObjectError("checksums.sha256 contains duplicate paths")
        result[name] = parts[0]
    return result


def _verify_manifest_inventory(
    manifest: ResearchObjectManifest,
    members: dict[str, bytes],
    checksums: dict[str, str],
    errors: list[str],
) -> None:
    embedded = {
        entry.crate_path: entry
        for entry in manifest.inventory
        if entry.disposition is InventoryDisposition.EMBEDDED
    }
    expected = set(embedded)
    actual = set(members) - {
        "checksums.sha256",
        "research-object-manifest.json",
        "ro-crate-metadata.json",
    }
    if expected != actual:
        errors.append("manifest embedded inventory does not match archive payload members")
    for path, entry in embedded.items():
        if path is None:
            continue
        content = members.get(path)
        if content is None:
            errors.append(f"manifest payload is missing: {path}")
            continue
        if len(content) != entry.content_size or _sha256(content) != entry.sha256:
            errors.append(f"manifest size/checksum mismatch: {path}")
        if checksums.get(path) != entry.sha256:
            errors.append(f"checksum file disagrees with manifest: {path}")


def _verify_ro_crate_metadata(
    payload: bytes,
    members: dict[str, bytes],
    errors: list[str],
) -> None:
    try:
        metadata = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"invalid ro-crate-metadata.json: {exc}")
        return
    if not isinstance(metadata, dict) or metadata.get("@context") != RO_CRATE_CONTEXT:
        errors.append("RO-Crate metadata uses the wrong or missing @context")
        return
    graph = metadata.get("@graph")
    if not isinstance(graph, list) or not all(isinstance(item, dict) for item in graph):
        errors.append("RO-Crate metadata must contain a flat @graph list")
        return
    ids = [item.get("@id") for item in graph]
    if any(not isinstance(item, str) for item in ids) or len(ids) != len(set(ids)):
        errors.append("RO-Crate @graph entity IDs must be present and unique")
        return
    by_id = {str(item["@id"]): item for item in graph}
    descriptor = by_id.get("ro-crate-metadata.json")
    root = by_id.get("./")
    if not isinstance(descriptor, dict):
        errors.append("RO-Crate metadata descriptor is missing")
    else:
        if descriptor.get("@type") != "CreativeWork":
            errors.append("RO-Crate metadata descriptor has the wrong @type")
        if descriptor.get("about") != {"@id": "./"}:
            errors.append("RO-Crate metadata descriptor does not reference the root")
        if descriptor.get("conformsTo") != {"@id": RO_CRATE_SPECIFICATION}:
            errors.append("RO-Crate metadata descriptor has the wrong conformsTo")
    if not isinstance(root, dict):
        errors.append("RO-Crate root data entity is missing")
        return
    for key in ("name", "description", "datePublished", "license", "hasPart"):
        if key not in root:
            errors.append(f"RO-Crate root is missing {key}")
    if root.get("@type") != "Dataset":
        errors.append("RO-Crate root data entity has the wrong @type")
    has_part = root.get("hasPart")
    part_ids = (
        {
            item.get("@id")
            for item in has_part
            if isinstance(has_part, list) and isinstance(item, dict)
        }
        if isinstance(has_part, list)
        else set()
    )
    expected_parts = {_uri_path(name) for name in members if name != "ro-crate-metadata.json"}
    if part_ids != expected_parts:
        errors.append("RO-Crate root hasPart does not match attached payload files")
    for entity_id in expected_parts:
        entity = by_id.get(entity_id)
        member_name = unquote(entity_id)
        content = members.get(member_name)
        if not isinstance(entity, dict) or content is None:
            errors.append(f"RO-Crate file entity is missing: {member_name}")
            continue
        if entity.get("@type") != "File":
            errors.append(f"RO-Crate payload entity is not File: {member_name}")
        if entity.get("contentSize") != len(content):
            errors.append(f"RO-Crate contentSize mismatch: {member_name}")
        if entity.get("sha256") != _sha256(content):
            errors.append(f"RO-Crate sha256 mismatch: {member_name}")


def _validate_destination(target: Path, *, overwrite: bool) -> None:
    if target.suffix.lower() != ".zip":
        raise ResearchObjectError("research-object destination must use the .zip suffix")
    if target.is_symlink():
        raise ResearchObjectError("research-object destination must not be a symbolic link")
    if target.exists() and not target.is_file():
        raise ResearchObjectError("research-object destination must be a file path")
    if target.exists() and not overwrite:
        raise FileExistsError(f"research-object destination already exists: {target}")
    parent = target.parent
    if parent.is_symlink() or not parent.is_dir():
        raise ResearchObjectError(
            "research-object destination parent must be an existing non-symlink directory"
        )


def _validate_archive_name(name: str) -> None:
    if not name or "\\" in name or "\x00" in name:
        raise ResearchObjectError("research-object archive member has an unsafe path")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ResearchObjectError(f"unsafe research-object archive path: {name}")


def _validate_source_relative_path(name: str) -> None:
    if not name or "\\" in name or "\x00" in name:
        raise ResearchObjectError("raw evidence has an unsafe relative path")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ResearchObjectError(f"unsafe raw-evidence path: {name}")


def _checksum_bytes(checksums: dict[str, str]) -> bytes:
    return "".join(f"{digest}  {name}\n" for name, digest in sorted(checksums.items())).encode(
        "utf-8"
    )


def _exclude_raw_identifiers(payload: bytes, raw_files: list[_RawFile]) -> bytes:
    """Remove bundle-relative raw names from a disclosure-minimised derived artifact."""

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ResearchObjectError(
            "exclude policy cannot safely inspect a derived non-UTF-8 artifact"
        ) from exc
    tokens: set[str] = set()
    for item in raw_files:
        tokens.add(item.relative_path)
        tokens.add(json.dumps(item.relative_path, ensure_ascii=False)[1:-1])
        tokens.add(_uri_path(item.relative_path))
    for token in sorted(tokens, key=lambda value: (-len(value), value)):
        if token:
            text = text.replace(token, "[excluded raw path]")
    return text.encode("utf-8")


def _request_without_raw_identifiers(
    request: ResearchObjectRequest,
    raw_files: list[_RawFile],
) -> ResearchObjectRequest:
    payload = _json_bytes(request.model_dump(mode="json"))
    redacted = _exclude_raw_identifiers(payload, raw_files)
    return ResearchObjectRequest.model_validate_json(redacted)


def _json_bytes(payload: object) -> bytes:
    return (
        json.dumps(
            _redact_value(payload),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _redact_value(value: object) -> object:
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return {_safe_text(str(key)): _redact_value(item) for key, item in sorted(value.items())}
    return value


def _safe_text(value: str) -> str:
    result = value
    for pattern in (_FILE_URI, _WINDOWS_PATH, _HOME_PATH, _POSIX_PATH):
        result = pattern.sub(_PATH_REDACTION, result)
    return result


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _media_type(path: str) -> str:
    suffix = PurePosixPath(path).suffix.lower()
    explicit = {
        ".cff": "text/yaml",
        ".csv": "text/csv",
        ".gz": "application/gzip",
        ".json": "application/json",
        ".md": "text/markdown",
        ".parquet": "application/vnd.apache.parquet",
        ".xml": "application/xml",
        ".yaml": "application/yaml",
        ".yml": "application/yaml",
    }
    return explicit.get(suffix) or mimetypes.guess_type(path)[0] or "application/octet-stream"


def _uri_path(path: str) -> str:
    return quote(path, safe="/._-~")

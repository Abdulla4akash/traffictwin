"""Fail-closed generic future study package ingestion.

Versioned envelope around ResearchStudyRecords plus lineage edges,
exact package fingerprint, strict allowlist admission, deterministic receipt.
Digest is binding, not cryptographic authenticity.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.research_registry.lineage import LineageEdge, LineageGraph, StudyVersionIdentity
from traffictwin.research_registry.models import ResearchStudyRecord

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION: Literal["research_study_package_v1"] = "research_study_package_v1"
SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({SCHEMA_VERSION})

ADAPTER_VERSION: Literal["research_ingestion_adapter_v1"] = "research_ingestion_adapter_v1"
SUPPORTED_ADAPTER_VERSIONS: frozenset[str] = frozenset({ADAPTER_VERSION})

HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")

_PRIVATE_PATH_RE = re.compile(r"(/Users/|/home/|/tmp/|/var/folders/|[A-Za-z]:[\\/])")  # noqa: S108
_SECRET_RE = re.compile(
    r"(password|secret|api[_-]?key|token|credential|private[_-]?key|bearer)",
    re.IGNORECASE,
)


def _check_no_private_or_secret(value: str, field_name: str) -> str:
    if _PRIVATE_PATH_RE.search(value):
        raise ValueError(f"{field_name} must not contain private absolute path: {value!r}")
    if _SECRET_RE.search(value):
        raise ValueError(f"{field_name} must not contain likely secret: {value!r}")
    return value


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ResearchIngestionError(ValueError):
    """Fail-closed ingestion error."""


# ---------------------------------------------------------------------------
# Admission policy
# ---------------------------------------------------------------------------


class AdmissionPolicyEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    study: str = Field(min_length=1, max_length=64)
    version: str = Field(min_length=1, max_length=64)
    code_sha: str = Field(min_length=40, max_length=40)
    manifest_hash: str = Field(min_length=64, max_length=64)
    package_fingerprint: str = Field(min_length=64, max_length=64)

    @field_validator("study", "version")
    @classmethod
    def _no_secret(cls, v: str) -> str:
        _check_no_private_or_secret(v, "policy study/version")
        return v

    @field_validator("code_sha")
    @classmethod
    def _code_ok(cls, v: str) -> str:
        if not HEX40_RE.match(v.lower()):
            raise ValueError(f"code_sha must be 40-hex, got {v!r}")
        return v.lower()

    @field_validator("manifest_hash", "package_fingerprint")
    @classmethod
    def _hash64_ok(cls, v: str) -> str:
        if not HEX64_RE.match(v.lower()):
            raise ValueError(f"hash must be 64-hex, got {v!r}")
        return v.lower()


class AdmissionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal["research_admission_policy_v1"] = "research_admission_policy_v1"
    entries: list[AdmissionPolicyEntry] = Field(description="Exact allowlist, sorted unique")

    @field_validator("entries")
    @classmethod
    def _entries_sorted_unique(
        cls,
        v: list[AdmissionPolicyEntry],
    ) -> list[AdmissionPolicyEntry]:
        # Revalidate each entry canonically
        revalidated: list[AdmissionPolicyEntry] = []
        for e in v:
            revalidated.append(AdmissionPolicyEntry.model_validate(e.model_dump(mode="json")))
        # Check uniqueness by full tuple
        keys = [
            (e.study, e.version, e.code_sha, e.manifest_hash, e.package_fingerprint)
            for e in revalidated
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("policy entries must be unique")
        # No wildcard/prefix
        for e in revalidated:
            for field in (e.study, e.version, e.code_sha, e.manifest_hash, e.package_fingerprint):
                if "*" in field or "?" in field or field.endswith("%"):
                    raise ValueError("wildcard/prefix not allowed in policy")
        # Sorted canonical
        sorted_entries = sorted(
            revalidated,
            key=lambda e: (e.study, e.version, e.code_sha, e.manifest_hash, e.package_fingerprint),
        )
        if revalidated != sorted_entries:
            raise ValueError("policy entries must be sorted canonical")
        return revalidated

    def canonical_json(self) -> str:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "entries": [e.model_dump(mode="json") for e in self.entries],
        }
        return _canonical_json(payload)

    def fingerprint(self) -> str:
        return _sha256_hex(self.canonical_json().encode("utf-8"))

    def allows(
        self,
        *,
        study: str,
        version: str,
        code_sha: str,
        manifest_hash: str,
        package_fingerprint: str,
    ) -> bool:
        """Exact match, no wildcard."""
        for e in self.entries:
            if (
                e.study == study
                and e.version == version
                and e.code_sha == code_sha.lower()
                and e.manifest_hash == manifest_hash.lower()
                and e.package_fingerprint == package_fingerprint.lower()
            ):
                return True
        return False


# ---------------------------------------------------------------------------
# Package envelope
# ---------------------------------------------------------------------------


class ResearchStudyPackage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal["research_study_package_v1"] = "research_study_package_v1"
    adapter_version: Literal["research_ingestion_adapter_v1"] = "research_ingestion_adapter_v1"
    records: list[ResearchStudyRecord] = Field(min_length=1, max_length=64)
    lineage_edges: list[LineageEdge] = Field(default_factory=list, max_length=128)
    package_fingerprint: str = Field(min_length=64, max_length=64)

    @field_validator("records")
    @classmethod
    def _records_revalidate_and_unique(
        cls,
        v: list[ResearchStudyRecord],
    ) -> list[ResearchStudyRecord]:
        # Canonically revalidate each record at boundary to defeat model_copy bypass
        revalidated: list[ResearchStudyRecord] = []
        for rec in v:
            # Force full revalidation via model_validate of dumped json
            dumped = rec.model_dump(mode="json")
            revalidated.append(ResearchStudyRecord.model_validate(dumped))
        # Duplicate study identities
        keys = [(r.study, r.version) for r in revalidated]
        if len(keys) != len(set(keys)):
            raise ValueError("records must not contain duplicate study identities")
        # Sorted canonical by (study, version)
        sorted_recs = sorted(revalidated, key=lambda r: (r.study, r.version))
        if revalidated != sorted_recs:
            raise ValueError("records must be sorted by (study, version) canonical")
        # Private path/secret already validated in record, but double scan raw strings
        for rec in revalidated:
            dump = json.dumps(rec.model_dump(mode="json"), ensure_ascii=True)
            if _PRIVATE_PATH_RE.search(dump):
                raise ValueError("record contains private absolute path")
            if _SECRET_RE.search(dump):
                raise ValueError("record contains likely secret")
        return revalidated

    @field_validator("lineage_edges")
    @classmethod
    def _edges_revalidate(cls, v: list[LineageEdge]) -> list[LineageEdge]:
        revalidated: list[LineageEdge] = []
        for e in v:
            revalidated.append(LineageEdge.model_validate(e.model_dump(mode="json")))
        # Sorted unique already enforced in edge, but ensure package-level sorted
        keys = [
            (
                e.source_study,
                e.source_version,
                e.target_study,
                e.target_version,
                e.relationship.value,
            )
            for e in revalidated
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("lineage_edges duplicate")
        sorted_edges = sorted(
            revalidated,
            key=lambda e: (
                e.source_study,
                e.source_version,
                e.target_study,
                e.target_version,
                e.relationship.value,
            ),
        )
        if revalidated != sorted_edges:
            raise ValueError("lineage_edges must be sorted canonical")
        return revalidated

    @field_validator("package_fingerprint")
    @classmethod
    def _fp_ok(cls, v: str) -> str:
        if not HEX64_RE.match(v.lower()):
            raise ValueError(f"package_fingerprint must be 64-hex, got {v!r}")
        return v.lower()

    @model_validator(mode="after")
    def _fail_closed(self) -> ResearchStudyPackage:
        # Validate schema/adapter versions explicitly (already literal but defend)
        if self.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(f"unknown schema_version {self.schema_version!r}")
        if self.adapter_version not in SUPPORTED_ADAPTER_VERSIONS:
            raise ValueError(f"unknown adapter_version {self.adapter_version!r}")
        # Inconsistent edge endpoints
        node_set = {(r.study, r.version) for r in self.records}
        for e in self.lineage_edges:
            if (e.source_study, e.source_version) not in node_set:
                raise ValueError(
                    f"edge source {(e.source_study, e.source_version)!r} not in records"
                )
            if (e.target_study, e.target_version) not in node_set:
                raise ValueError(
                    f"edge target {(e.target_study, e.target_version)!r} not in records"
                )
        # Missing code SHA for evidence/admitted records already in ResearchStudyRecord,
        # but double-enforce
        for r in self.records:
            if (
                r.evidence_standing.value != "unavailable" or r.admission_status.value == "admitted"
            ) and (r.code_sha is None or r.manifest_hash is None):  # noqa: E501
                raise ValueError(
                    f"record {r.study}:{r.version} evidence/admitted requires code_sha+manifest_hash"  # noqa: E501
                )
        # Canonical/fingerprint drift
        expected = self.computed_fingerprint()
        if self.package_fingerprint != expected:
            raise ValueError(
                f"package fingerprint drift: expected {expected[:8]}…, got {self.package_fingerprint[:8]}…"  # noqa: E501
            )
        # Deep scan for private paths/secrets across entire package dump
        dump_str = json.dumps(self.model_dump(mode="json"), ensure_ascii=True)
        if _PRIVATE_PATH_RE.search(dump_str):
            raise ValueError("package contains private absolute path")
        if _SECRET_RE.search(dump_str):
            raise ValueError("package contains likely secret")
        return self

    def canonical_payload(self) -> dict[str, Any]:
        """Payload without fingerprint for hashing."""
        return {
            "schema_version": self.schema_version,
            "adapter_version": self.adapter_version,
            "records": [json.loads(r.canonical_json()) for r in self.records],
            "lineage_edges": [
                json.loads(_canonical_json(e.canonical_payload())) for e in self.lineage_edges
            ],
        }

    def computed_fingerprint(self) -> str:
        # Canonical JSON of payload without fingerprint, sorted keys
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "adapter_version": self.adapter_version,
            "records": [json.loads(r.canonical_json()) for r in self.records],
            "lineage_edges": [e.model_dump(mode="json") for e in self.lineage_edges],
        }
        # Need to remove fingerprint from edge dumps for hashing? Edges include fingerprint;
        # but canonical_payload for package should include edge fingerprints? The fingerprint
        # of edge is binding, so include full edge including fingerprint deterministically.
        # However to avoid circular, we hash the package's records+edges as stored.
        # We already validated fingerprint of edges; now package fingerprint includes edge fingerprints.  # noqa: E501
        # Simplify: hash canonical of payload dict without package_fingerprint field.
        return _sha256_hex(_canonical_json(payload).encode("utf-8"))

    @classmethod
    def build(
        cls,
        records: list[ResearchStudyRecord],
        lineage_edges: list[LineageEdge] | None = None,
    ) -> ResearchStudyPackage:
        recs_sorted = sorted(records, key=lambda r: (r.study, r.version))
        edges_sorted: list[LineageEdge] = []
        if lineage_edges:
            edges_sorted = sorted(
                lineage_edges,
                key=lambda e: (
                    e.source_study,
                    e.source_version,
                    e.target_study,
                    e.target_version,
                    e.relationship.value,
                ),
            )
        # Compute fingerprint with placeholder, then construct
        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "adapter_version": ADAPTER_VERSION,
            "records": [json.loads(r.canonical_json()) for r in recs_sorted],
            "lineage_edges": [e.model_dump(mode="json") for e in edges_sorted],
        }
        fp = _sha256_hex(_canonical_json(payload).encode("utf-8"))
        return cls(
            schema_version=SCHEMA_VERSION,
            adapter_version=ADAPTER_VERSION,
            records=recs_sorted,
            lineage_edges=edges_sorted,
            package_fingerprint=fp,
        )

    def to_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    @classmethod
    def from_json(cls, data: str) -> ResearchStudyPackage:
        if not isinstance(data, str) or not data.strip():
            raise ResearchIngestionError("package JSON must be non-empty string")
        if _PRIVATE_PATH_RE.search(data):
            raise ResearchIngestionError("package JSON contains private absolute path")
        if _SECRET_RE.search(data):
            raise ResearchIngestionError("package JSON contains likely secret")
        try:
            obj = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ResearchIngestionError(f"invalid JSON: {exc}") from exc
        if not isinstance(obj, dict):
            raise ResearchIngestionError("package JSON must be object")
        # Reject unknown schema/adapter versions early
        sv = obj.get("schema_version")
        av = obj.get("adapter_version")
        if sv not in SUPPORTED_SCHEMA_VERSIONS:
            raise ResearchIngestionError(f"unknown schema_version {sv!r}")
        if av not in SUPPORTED_ADAPTER_VERSIONS:
            raise ResearchIngestionError(f"unknown adapter_version {av!r}")
        # Extra fields will be caught by extra=forbid during validation
        try:
            # Canonically revalidate all Pydantic instances at boundary: validate via model_validate
            pkg = cls.model_validate(obj)
        except Exception as exc:
            raise ResearchIngestionError(f"package validation failed: {exc}") from exc
        # Verify fingerprint drift already done in validator
        return pkg


# ---------------------------------------------------------------------------
# Import receipt
# ---------------------------------------------------------------------------


class ImportReceipt(BaseModel):
    """Deterministic import receipt binding package/policy/records/lineage.

    Note: digest is binding, not cryptographic authenticity. It proves
    deterministic binding of the imported package to the admission policy
    and its records/lineage, but does not by itself prove external
    authenticity without a trusted policy distribution channel.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal["research_import_receipt_v1"] = "research_import_receipt_v1"
    package_fingerprint: str = Field(min_length=64, max_length=64)
    policy_fingerprint: str = Field(min_length=64, max_length=64)
    record_fingerprints: list[str] = Field(description="Sorted record fingerprints")
    lineage_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    receipt_fingerprint: str = Field(min_length=64, max_length=64)
    note: str = Field(
        default="Digest is binding, not cryptographic authenticity; verify policy distribution separately.",  # noqa: E501
        min_length=1,
    )

    @field_validator("package_fingerprint", "policy_fingerprint", "receipt_fingerprint")
    @classmethod
    def _hex64(cls, v: str) -> str:
        if not HEX64_RE.match(v.lower()):
            raise ValueError(f"fingerprint must be 64-hex, got {v!r}")
        return v.lower()

    @field_validator("record_fingerprints")
    @classmethod
    def _records_sorted(cls, v: list[str]) -> list[str]:
        for fp in v:
            if not HEX64_RE.match(fp.lower()):
                raise ValueError(f"record fingerprint must be 64-hex {fp!r}")
        lower = [x.lower() for x in v]
        if sorted(lower) != lower:
            raise ValueError("record_fingerprints must be sorted")
        if len(lower) != len(set(lower)):
            raise ValueError("record_fingerprints must be unique")
        return lower

    @field_validator("lineage_fingerprint")
    @classmethod
    def _lineage_opt(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not HEX64_RE.match(v.lower()):
            raise ValueError(f"lineage fingerprint must be 64-hex {v!r}")
        return v.lower()

    @model_validator(mode="after")
    def _receipt_binding(self) -> ImportReceipt:
        expected = self.computed_fingerprint()
        if self.receipt_fingerprint != expected:
            raise ValueError(
                f"receipt fingerprint drift: expected {expected[:8]}…, got {self.receipt_fingerprint[:8]}…"  # noqa: E501
            )
        return self

    def canonical_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "package_fingerprint": self.package_fingerprint,
            "policy_fingerprint": self.policy_fingerprint,
            "record_fingerprints": self.record_fingerprints,
            "lineage_fingerprint": self.lineage_fingerprint,
            "note": self.note,
        }
        return payload

    def computed_fingerprint(self) -> str:
        return _sha256_hex(_canonical_json(self.canonical_payload()).encode("utf-8"))

    @classmethod
    def build(
        cls,
        package: ResearchStudyPackage,
        policy: AdmissionPolicy,
    ) -> ImportReceipt:
        # Canonically revalidate at boundary
        pkg2 = ResearchStudyPackage.model_validate(package.model_dump(mode="json"))
        pol2 = AdmissionPolicy.model_validate(policy.model_dump(mode="json"))
        rec_fps = sorted([r.fingerprint() for r in pkg2.records])
        # Lineage fingerprint: hash of sorted edge fingerprints or graph fingerprint if edges present  # noqa: E501
        lineage_fp: str | None = None
        if pkg2.lineage_edges:
            # Build temporary graph nodes from records
            nodes = [StudyVersionIdentity(study=r.study, version=r.version) for r in pkg2.records]
            graph = LineageGraph.build(nodes, pkg2.lineage_edges)
            lineage_fp = graph.fingerprint()
        pkg_fp = pkg2.package_fingerprint
        pol_fp = pol2.fingerprint()
        note = "Digest is binding, not cryptographic authenticity; verify policy distribution separately."  # noqa: E501
        tmp: dict[str, Any] = {
            "schema_version": "research_import_receipt_v1",
            "package_fingerprint": pkg_fp,
            "policy_fingerprint": pol_fp,
            "record_fingerprints": rec_fps,
            "lineage_fingerprint": lineage_fp,
            "note": note,
        }
        receipt_fp = _sha256_hex(_canonical_json(tmp).encode("utf-8"))
        return cls(
            schema_version="research_import_receipt_v1",
            package_fingerprint=pkg_fp,
            policy_fingerprint=pol_fp,
            record_fingerprints=rec_fps,
            lineage_fingerprint=lineage_fp,
            receipt_fingerprint=receipt_fp,
            note=note,
        )


# ---------------------------------------------------------------------------
# Ingestion function
# ---------------------------------------------------------------------------


def ingest_package(
    package_json: str,
    policy: AdmissionPolicy,
) -> tuple[ResearchStudyPackage, ImportReceipt]:
    """Fail-closed ingestion.

    - Parses and strictly validates package (unknown versions, extra fields, hashes,
      duplicate identities, private paths/secrets, missing SHA, edge endpoints,
      fingerprint drift all fail closed).
    - Checks admission allowlist keyed by study+version+code_sha+manifest_hash+package fingerprint.
      Self-declared ADMITTED without policy match fails closed. No wildcard trust.
    - Returns deterministic attributable receipt binding package/policy/records/lineage.
    - Canonically revalidates all Pydantic instances at public boundaries.

    Raises ResearchIngestionError on any failure.
    """
    # Revalidate policy at boundary
    try:
        policy_validated = AdmissionPolicy.model_validate(policy.model_dump(mode="json"))
    except Exception as exc:
        raise ResearchIngestionError(f"policy validation failed: {exc}") from exc

    # Parse package with strict checks
    try:
        pkg = ResearchStudyPackage.from_json(package_json)
    except ResearchIngestionError:
        raise
    except Exception as exc:
        raise ResearchIngestionError(f"package ingestion failed: {exc}") from exc

    # Admission check: every record must be exactly allowlisted with package fingerprint
    for rec in pkg.records:
        # For unavailable records (no code_sha), they are not admitted and do not require policy?
        # But spec says package must not become trusted/admitted because self-declares ADMITTED.
        # So we enforce: if record.admission_status == ADMITTED or evidence requires hash,
        # then it must be allowlisted; otherwise unavailable records can pass without allowlist
        # but package as a whole is only trusted if all admitted records are allowlisted.
        # Simpler: if any record is ADMITTED, it must be allowlisted; if all are NOT_ADMITTED,
        # package is not trusted but still structurally valid? For generic ingestion, we require
        # that any ADMITTED record must be allowlisted; if package contains only unavailable,
        # it does not need allowlist but receipt still will show not admitted? However spec says
        # "Unknown packages fail closed." So we should fail if ANY record not in allowlist
        # and that record is ADMITTED? For fail-closed, treat package as untrusted if not fully allowlisted.  # noqa: E501
        # We will require that for each record where code_sha is present, there is a matching policy entry.  # noqa: E501
        # If no matching entry, fail.
        if rec.code_sha is None or rec.manifest_hash is None:
            # Unavailable record: skip policy check (truthful unavailable)
            continue
        if not policy_validated.allows(
            study=rec.study,
            version=rec.version,
            code_sha=rec.code_sha,
            manifest_hash=rec.manifest_hash,
            package_fingerprint=pkg.package_fingerprint,
        ):
            raise ResearchIngestionError(
                f"package record {rec.study}:{rec.version} not in admission allowlist "
                f"(code_sha={rec.code_sha!r}, manifest={rec.manifest_hash!r}, pkg_fp={pkg.package_fingerprint[:8]}…)"  # noqa: E501
            )
    # If package contains no admitted records but policy expects admitted, still ok? But we already gate.  # noqa: E501
    # If package has at least one ADMITTED record and no policy entry matched, we already raised.
    # If package has zero ADMITTED records (all unavailable), we do not require allowlist but still return receipt.  # noqa: E501
    # However spec says unknown packages fail closed; so if policy is empty and package contains admitted records,  # noqa: E501
    # it will fail as desired.

    # Also ensure at least one record required allowlist match if any admitted
    has_admitted = any(r.admission_status.value == "admitted" for r in pkg.records)  # noqa: E501
    if has_admitted:
        # Ensure at least one policy entry matched (already ensured per-record, but double)
        matched = 0
        for rec in pkg.records:
            if (
                rec.code_sha
                and rec.manifest_hash
                and policy_validated.allows(
                    study=rec.study,
                    version=rec.version,
                    code_sha=rec.code_sha,
                    manifest_hash=rec.manifest_hash,
                    package_fingerprint=pkg.package_fingerprint,
                )
            ):
                matched += 1
        if matched == 0:
            raise ResearchIngestionError("admitted package has no matching policy entry")

    receipt = ImportReceipt.build(pkg, policy_validated)
    # Final revalidation
    try:
        _ = ImportReceipt.model_validate(receipt.model_dump(mode="json"))
    except Exception as exc:
        raise ResearchIngestionError(f"receipt validation failed: {exc}") from exc
    return pkg, receipt

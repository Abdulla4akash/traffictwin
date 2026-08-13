"""Registry service: deterministic snapshot combining admitted + unavailable.

Conflict on same identity/different content; exact reimport idempotent.
Preserves source/admission distinction.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.research_registry.adapters import (
    build_e2_study_package,
    build_unavailable_index_records,
)
from traffictwin.research_registry.ingestion import (
    AdmissionPolicy,
    ImportReceipt,
    ResearchStudyPackage,
    ingest_package,
)
from traffictwin.research_registry.lineage import LineageEdge, LineageGraph, StudyVersionIdentity
from traffictwin.research_registry.models import AdmissionStatus, ResearchStudyRecord, StudyStatus


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


class RegistrySnapshot(BaseModel):
    """Inspectable registry snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    records: list[ResearchStudyRecord] = Field(description="Admitted records, sorted unique")
    unavailable_records: list[ResearchStudyRecord] = Field(default_factory=list)
    lineage: LineageGraph = Field(description="Lineage graph")
    receipts: list[ImportReceipt] = Field(description="Exact admission receipts, sorted")
    snapshot_fingerprint: str = Field(min_length=64, max_length=64)

    @field_validator("records")
    @classmethod
    def _records_ok(cls, v: list[ResearchStudyRecord]) -> list[ResearchStudyRecord]:
        revalidated = [ResearchStudyRecord.model_validate(r.model_dump(mode="json")) for r in v]
        keys = [(r.study, r.version) for r in revalidated]
        if len(keys) != len(set(keys)):
            raise ValueError("snapshot records duplicate identity")
        if keys != sorted(keys):
            raise ValueError("snapshot records must be sorted")
        return revalidated

    @field_validator("unavailable_records")
    @classmethod
    def _unavailable_ok(cls, v: list[ResearchStudyRecord]) -> list[ResearchStudyRecord]:
        revalidated = [ResearchStudyRecord.model_validate(r.model_dump(mode="json")) for r in v]
        keys = [(r.study, r.version) for r in revalidated]
        if len(keys) != len(set(keys)):
            raise ValueError("unavailable duplicate")
        if keys != sorted(keys):
            raise ValueError("unavailable must be sorted")
        for r in revalidated:
            if r.evidence_standing.value != "unavailable":
                raise ValueError("unavailable record must have UNAVAILABLE standing")
        return revalidated

    @model_validator(mode="after")
    def _fingerprint_check(self) -> RegistrySnapshot:
        admitted_keys = {(r.study, r.version) for r in self.records}
        unavailable_keys = {(r.study, r.version) for r in self.unavailable_records}
        if admitted_keys & unavailable_keys:
            raise ValueError("admitted and unavailable overlap")
        expected = self.computed_fingerprint()
        if self.snapshot_fingerprint != expected:
            raise ValueError(
                f"snapshot fingerprint drift expected {expected[:8]}…, got {self.snapshot_fingerprint[:8]}…"  # noqa: E501
            )
        return self

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "records": [json.loads(r.canonical_json()) for r in self.records],
            "unavailable_records": [
                json.loads(r.canonical_json()) for r in self.unavailable_records
            ],
            "lineage": json.loads(self.lineage.canonical_json()),
            "receipts": [
                json.loads(_canonical_json(r.model_dump(mode="json"))) for r in self.receipts
            ],
        }

    def computed_fingerprint(self) -> str:
        return _sha256_hex(_canonical_json(self.canonical_payload()).encode("utf-8"))

    # ---- Retrieval helpers -------------------------------------------------

    def get_by_identity(self, study: str, version: str) -> ResearchStudyRecord | None:
        for r in self.records:
            if r.study == study and r.version == version:
                return r
        for r in self.unavailable_records:
            if r.study == study and r.version == version:
                return r
        return None

    def get_by_status(self, status: StudyStatus) -> list[ResearchStudyRecord]:
        return [r for r in self.records + self.unavailable_records if r.status == status]

    def get_by_admission(self, admission: AdmissionStatus) -> list[ResearchStudyRecord]:
        return [
            r for r in self.records + self.unavailable_records if r.admission_status == admission
        ]

    def product_links(self) -> list[str]:
        links: set[str] = set()
        for r in self.records:
            if r.product_links:
                links.update(r.product_links)
        return sorted(links)

    def limitations(self) -> list[str]:
        out: set[str] = set()
        for r in self.records:
            if r.limitations:
                out.update(r.limitations)
        return sorted(out)

    @classmethod
    def build(
        cls,
        records: list[ResearchStudyRecord],
        unavailable_records: list[ResearchStudyRecord],
        lineage: LineageGraph,
        receipts: list[ImportReceipt],
    ) -> RegistrySnapshot:
        recs_sorted = sorted(records, key=lambda r: (r.study, r.version))
        unavail_sorted = sorted(unavailable_records, key=lambda r: (r.study, r.version))
        receipts_sorted = sorted(receipts, key=lambda r: r.receipt_fingerprint)
        payload: dict[str, Any] = {
            "records": [json.loads(r.canonical_json()) for r in recs_sorted],
            "unavailable_records": [json.loads(r.canonical_json()) for r in unavail_sorted],
            "lineage": json.loads(lineage.canonical_json()),
            "receipts": [r.model_dump(mode="json") for r in receipts_sorted],
        }
        fp = _sha256_hex(_canonical_json(payload).encode("utf-8"))
        return cls(
            records=recs_sorted,
            unavailable_records=unavail_sorted,
            lineage=lineage,
            receipts=receipts_sorted,
            snapshot_fingerprint=fp,
        )


class RegistryService:
    """Deterministically combines admitted packages; generic snapshot never injects.

    The generic service only snapshots records and exact lineage edges explicitly
    imported/constructed into that instance. It never infers edges or injects
    unavailable index records from study-letter names. The built-in E2 convenience
    explicitly opts into the supported unavailable index and carries its declared
    E2 lineage via the ingested package; that opt-in is visible at construction
    (with_default_e2) and not a fallback in generic snapshot/get.
    """

    def __init__(self, admission_policy: AdmissionPolicy) -> None:
        self._policy = AdmissionPolicy.model_validate(admission_policy.model_dump(mode="json"))
        self._records: dict[tuple[str, str], ResearchStudyRecord] = {}
        self._fingerprints: dict[tuple[str, str], str] = {}
        self._receipts: list[ImportReceipt] = []
        self._lineage_edges: list[LineageEdge] = []
        self._seen_package_fps: set[str] = set()
        self._unavailable_records: list[ResearchStudyRecord] = []

    @property
    def policy(self) -> AdmissionPolicy:
        return self._policy

    def ingest(self, package_json: str) -> ImportReceipt:
        """Ingest package JSON via fail-closed path, handle idempotency/conflict."""
        pkg, receipt = ingest_package(package_json, self._policy)
        # Idempotency: if same package fingerprint already seen, return existing receipt if exact
        if pkg.package_fingerprint in self._seen_package_fps:
            # Find existing receipt for same package
            for r in self._receipts:
                if r.package_fingerprint == pkg.package_fingerprint:
                    # Ensure exact same records; otherwise conflict
                    existing_fps = set(r.record_fingerprints)
                    new_fps = {rec.fingerprint() for rec in pkg.records}
                    if existing_fps == new_fps:
                        return r
                    raise ValueError("conflicting package content for same fingerprint")
            # If not found but fingerprint seen, still idempotent (should not happen)
            return receipt
        # Conflict detection: same identity different content
        for rec in pkg.records:
            key = (rec.study, rec.version)
            new_fp = rec.fingerprint()
            if key in self._records:
                old_fp = self._fingerprints[key]
                if old_fp != new_fp:
                    raise ValueError(
                        f"conflict on same identity {key}: different content "
                        f"{old_fp[:8]}… vs {new_fp[:8]}…; do not silently supersede"
                    )
                # Exact same content: idempotent, already stored
                continue
            # New identity
            self._records[key] = ResearchStudyRecord.model_validate(rec.model_dump(mode="json"))
            self._fingerprints[key] = new_fp
        # Merge lineage edges (must be consistent)
        for e in pkg.lineage_edges:
            # Check duplicate
            if e not in self._lineage_edges:
                # Ensure no conflicting duplicate fingerprint? Already sorted unique per package
                # If same source/target/relationship but different fingerprint/rationale, conflict
                for existing in self._lineage_edges:
                    if (
                        existing.source_study == e.source_study
                        and existing.source_version == e.source_version
                        and existing.target_study == e.target_study
                        and existing.target_version == e.target_version
                        and existing.relationship == e.relationship
                    ):
                        if existing.fingerprint != e.fingerprint:
                            raise ValueError(
                                f"lineage edge conflict for {e.source_study}->{e.target_study}"
                            )
                        break
                else:
                    self._lineage_edges.append(e)
        self._lineage_edges = sorted(
            self._lineage_edges,
            key=lambda x: (
                x.source_study,
                x.source_version,
                x.target_study,
                x.target_version,
                x.relationship.value,
            ),
        )
        self._receipts.append(receipt)
        self._receipts = sorted(self._receipts, key=lambda r: r.receipt_fingerprint)
        self._seen_package_fps.add(pkg.package_fingerprint)
        return receipt

    def ingest_package(self, pkg: ResearchStudyPackage) -> ImportReceipt:
        """Ingest already-built package object."""
        return self.ingest(pkg.to_json())

    def include_unavailable(self, records: list[ResearchStudyRecord] | None = None) -> None:
        """Explicitly opt into supported unavailable index records."""
        if records is None:
            records = build_unavailable_index_records()
        revalidated: list[ResearchStudyRecord] = []
        for r in records:
            revalidated.append(ResearchStudyRecord.model_validate(r.model_dump(mode="json")))
            if r.evidence_standing.value != "unavailable":
                raise ValueError("unavailable record must have UNAVAILABLE standing")
        admitted_keys = {(rec.study, rec.version) for rec in self._records.values()}
        filtered = [r for r in revalidated if (r.study, r.version) not in admitted_keys]
        self._unavailable_records = sorted(filtered, key=lambda x: (x.study, x.version))

    def snapshot(self) -> RegistrySnapshot:
        """Build deterministic snapshot of only explicitly ingested records and edges."""
        records = sorted(self._records.values(), key=lambda r: (r.study, r.version))
        unavailable_filtered = sorted(self._unavailable_records, key=lambda r: (r.study, r.version))
        admitted_keys = {(r.study, r.version) for r in records}
        unavailable_filtered = [
            r for r in unavailable_filtered if (r.study, r.version) not in admitted_keys
        ]
        nodes: list[StudyVersionIdentity] = [
            StudyVersionIdentity(study=r.study, version=r.version) for r in records
        ]
        nodes = sorted(nodes, key=lambda n: (n.study, n.version))
        if self._lineage_edges:
            lineage = LineageGraph.build(nodes=nodes, edges=self._lineage_edges)
        else:
            lineage = LineageGraph(nodes=nodes, edges=[])
        snapshot = RegistrySnapshot.build(
            records=records,
            unavailable_records=unavailable_filtered,
            lineage=lineage,
            receipts=list(self._receipts),
        )
        return RegistrySnapshot.model_validate(snapshot.model_dump(mode="json"))

    def get(self, study: str, version: str) -> ResearchStudyRecord | None:
        key = (study, version)
        if key in self._records:
            return self._records[key]
        for r in self._unavailable_records:
            if r.study == study and r.version == version:
                return r
        return None

    @classmethod
    def with_default_e2(cls) -> RegistryService:
        """Convenience: service preloaded with exact E2 package and explicit unavailable index."""
        pkg = build_e2_study_package()
        from traffictwin.research_registry.adapters import build_default_e2_admission_policy

        policy = build_default_e2_admission_policy(pkg)
        svc = cls(policy)
        svc.ingest_package(pkg)
        svc.include_unavailable(build_unavailable_index_records())
        return svc

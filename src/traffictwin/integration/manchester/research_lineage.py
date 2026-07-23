"""Deterministic MAN-11 source-to-VEC research-lineage contracts.

The builder in this module records already-produced evidence.  It performs no
acquisition, projection, calibration, SUMO execution, VEC execution, metric
calculation, publication, or capability acceptance.  A reference is admitted
only as a contiguous link in the frozen Manchester-to-VEC chain, and a
complete chain remains evidence of reproducible software flow rather than
proof that a Randy policy is scientifically valid for Manchester.
"""

from __future__ import annotations

import re
from enum import StrEnum
from itertools import pairwise
from typing import Literal, Self

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import (
    ManchesterPublicationClass,
    ManchesterSnapshotModel,
    canonical_json,
    sha256_hex,
)

MANCHESTER_RESEARCH_LINEAGE_SCHEMA_VERSION: Literal["1.0"] = "1.0"
MANCHESTER_RESEARCH_LINEAGE_METHOD_VERSION: Literal["manchester-research-lineage-1.0"] = (
    "manchester-research-lineage-1.0"
)
MANCHESTER_RESEARCH_LINEAGE_CAPABILITY_ID: Literal["MAN-11"] = "MAN-11"

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_ARTIFACT_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"
_SNAPSHOT_ID_PATTERN = r"^[a-z0-9][a-z0-9_.-]{0,95}-\d{8}T\d{6}Z-[0-9a-f]{12}$"


class ManchesterResearchLineageError(ValueError):
    """Typed refusal raised before an invalid lineage can be represented."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class ManchesterLineageStageName(StrEnum):
    """Frozen stage order from v0.7 Gate E and accepted VEC-06--VEC-12."""

    SOURCE_SNAPSHOT = "source_snapshot"
    PROJECTION = "projection"
    NETWORK_MAPPING = "network_mapping"
    CALIBRATION = "calibration"
    SUMO_EXECUTION = "sumo_execution"
    FCD_PREPROCESSING = "fcd_preprocessing"
    VEC_EXECUTION = "vec_execution"
    VEC_REPRODUCTION = "vec_reproduction"
    SCIENTIFIC_ADMISSION = "scientific_admission"
    THIN_INTERFACE = "thin_interface"
    PERMISSION_PACK = "permission_pack"
    RESEARCH_ARCHIVE = "research_archive"


class ManchesterLineageArtifactKind(StrEnum):
    """Exact artifact kind admitted at each MAN-11 lineage stage."""

    SOURCE_SNAPSHOT = "manchester_source_snapshot"
    PROJECTION_REPORT = "manchester_projection_report"
    NETWORK_MAPPING = "manchester_network_mapping"
    CALIBRATION_REPORT = "manchester_calibration_report"
    SUMO_EXECUTION_RECEIPT = "sumo_execution_receipt"
    FCD_PREPROCESS_RECEIPT = "vec_fcd_preprocess_receipt"
    VEC_EXECUTION_RECEIPT = "vec_execution_receipt"
    VEC_REPRODUCTION_REPORT = "vec_reproduction_report"
    SCIENTIFIC_ADMISSION_REPORT = "vec_scientific_admission_report"
    VEC_INTERFACE_SNAPSHOT = "vec_interface_snapshot"
    DISSERTATION_PACK_MANIFEST = "vec_dissertation_pack_manifest"
    END_TO_END_ARCHIVE_RECEIPT = "vec_end_to_end_archive_receipt"


class ManchesterLineageStageState(StrEnum):
    """Whether one stage has an exact, contiguous artifact binding."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ManchesterLineageReason(StrEnum):
    """Deterministic reason for one stage state."""

    AVAILABLE = "available"
    ARTIFACT_NOT_SUPPLIED = "artifact_not_supplied"
    UPSTREAM_STAGE_UNAVAILABLE = "upstream_stage_unavailable"


class ManchesterLineageChainState(StrEnum):
    """Overall completeness without implying scientific or capability acceptance."""

    EMPTY = "empty"
    PARTIAL = "partial"
    COMPLETE = "complete"


class ManchesterLineageEvidenceLabel(StrEnum):
    """Truth-preserving semantic label derived from stage and source class."""

    SYNTHETIC_DEVELOPMENT = "synthetic_development"
    OBSERVED_MANCHESTER_EVIDENCE = "observed_manchester_evidence"
    MANCHESTER_CALIBRATION_CANDIDATE = "manchester_calibration_candidate"
    MANCHESTER_CALIBRATED_SIMULATION = "manchester_calibrated_simulation"
    RANDY_POLICY_ON_MANCHESTER_CALIBRATED_SIMULATION = (
        "randy_policy_on_manchester_calibrated_simulation"
    )


STAGE_ORDER: tuple[ManchesterLineageStageName, ...] = tuple(ManchesterLineageStageName)

_EXPECTED_KIND = {
    ManchesterLineageStageName.SOURCE_SNAPSHOT: ManchesterLineageArtifactKind.SOURCE_SNAPSHOT,
    ManchesterLineageStageName.PROJECTION: ManchesterLineageArtifactKind.PROJECTION_REPORT,
    ManchesterLineageStageName.NETWORK_MAPPING: ManchesterLineageArtifactKind.NETWORK_MAPPING,
    ManchesterLineageStageName.CALIBRATION: ManchesterLineageArtifactKind.CALIBRATION_REPORT,
    ManchesterLineageStageName.SUMO_EXECUTION: (
        ManchesterLineageArtifactKind.SUMO_EXECUTION_RECEIPT
    ),
    ManchesterLineageStageName.FCD_PREPROCESSING: (
        ManchesterLineageArtifactKind.FCD_PREPROCESS_RECEIPT
    ),
    ManchesterLineageStageName.VEC_EXECUTION: (ManchesterLineageArtifactKind.VEC_EXECUTION_RECEIPT),
    ManchesterLineageStageName.VEC_REPRODUCTION: (
        ManchesterLineageArtifactKind.VEC_REPRODUCTION_REPORT
    ),
    ManchesterLineageStageName.SCIENTIFIC_ADMISSION: (
        ManchesterLineageArtifactKind.SCIENTIFIC_ADMISSION_REPORT
    ),
    ManchesterLineageStageName.THIN_INTERFACE: (
        ManchesterLineageArtifactKind.VEC_INTERFACE_SNAPSHOT
    ),
    ManchesterLineageStageName.PERMISSION_PACK: (
        ManchesterLineageArtifactKind.DISSERTATION_PACK_MANIFEST
    ),
    ManchesterLineageStageName.RESEARCH_ARCHIVE: (
        ManchesterLineageArtifactKind.END_TO_END_ARCHIVE_RECEIPT
    ),
}

_CAPABILITY_IDS: dict[ManchesterLineageStageName, tuple[str, ...]] = {
    ManchesterLineageStageName.SOURCE_SNAPSHOT: ("MAN-01",),
    ManchesterLineageStageName.PROJECTION: ("MAN-07",),
    ManchesterLineageStageName.NETWORK_MAPPING: ("MAN-09",),
    ManchesterLineageStageName.CALIBRATION: ("MAN-09",),
    ManchesterLineageStageName.SUMO_EXECUTION: ("MAN-11",),
    ManchesterLineageStageName.FCD_PREPROCESSING: ("VEC-06",),
    ManchesterLineageStageName.VEC_EXECUTION: ("VEC-07",),
    ManchesterLineageStageName.VEC_REPRODUCTION: ("VEC-08",),
    ManchesterLineageStageName.SCIENTIFIC_ADMISSION: ("VEC-09",),
    ManchesterLineageStageName.THIN_INTERFACE: ("VEC-10",),
    ManchesterLineageStageName.PERMISSION_PACK: ("VEC-11",),
    ManchesterLineageStageName.RESEARCH_ARCHIVE: ("VEC-12",),
}


class ManchesterLineageArtifactReference(ManchesterSnapshotModel):
    """Portable identity for one already-validated upstream artifact.

    The model carries no artifact bytes or filesystem path.  The immediate
    parent digest is mandatory after the first stage, making a skipped gate or
    an unbound downstream result unrepresentable.
    """

    stage: ManchesterLineageStageName
    artifact_kind: ManchesterLineageArtifactKind
    artifact_id: str = Field(pattern=_ARTIFACT_ID_PATTERN)
    artifact_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    contract_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    parent_artifact_fingerprints: tuple[str, ...] = Field(max_length=1)
    source_snapshot_ids: tuple[str, ...] = Field(max_length=32)
    publication_class: ManchesterPublicationClass
    synthetic: bool

    @model_validator(mode="after")
    def validate_stage_shape(self) -> Self:
        if self.artifact_kind is not _EXPECTED_KIND[self.stage]:
            raise ValueError(f"{self.stage.value} requires {_EXPECTED_KIND[self.stage].value}")
        if self.stage is ManchesterLineageStageName.SOURCE_SNAPSHOT:
            if self.parent_artifact_fingerprints:
                raise ValueError("the source snapshot stage cannot name a parent artifact")
            if not self.source_snapshot_ids:
                raise ValueError("the source snapshot stage requires snapshot ids")
        else:
            if len(self.parent_artifact_fingerprints) != 1:
                raise ValueError("every downstream stage requires exactly one parent fingerprint")
            if self.source_snapshot_ids:
                raise ValueError("only the source snapshot stage may carry snapshot ids")
        if self.source_snapshot_ids != tuple(sorted(set(self.source_snapshot_ids))):
            raise ValueError("source snapshot ids must be unique and sorted")
        if any(
            re.fullmatch(_SNAPSHOT_ID_PATTERN, value) is None for value in self.source_snapshot_ids
        ):
            raise ValueError("source snapshot ids must have the immutable snapshot-id shape")
        return self


class ManchesterLineageStage(ManchesterSnapshotModel):
    """One re-derived stage truth in the fixed MAN-11 chain."""

    stage: ManchesterLineageStageName
    position: int = Field(ge=1, le=len(STAGE_ORDER))
    capability_ids: tuple[str, ...]
    state: ManchesterLineageStageState
    reason: ManchesterLineageReason
    artifact: ManchesterLineageArtifactReference | None
    evidence_label: ManchesterLineageEvidenceLabel | None


class ManchesterLineageEdge(ManchesterSnapshotModel):
    """One fixed adjacent dependency and its currently bound identity."""

    upstream: ManchesterLineageStageName
    downstream: ManchesterLineageStageName
    active: bool
    upstream_artifact_fingerprint: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    downstream_artifact_fingerprint: str | None = Field(default=None, pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_edge_state(self) -> Self:
        fingerprints_present = (
            self.upstream_artifact_fingerprint is not None
            and self.downstream_artifact_fingerprint is not None
        )
        if self.active != fingerprints_present:
            raise ValueError("active edges require both artifact fingerprints")
        if not self.active and (
            self.upstream_artifact_fingerprint is not None
            or self.downstream_artifact_fingerprint is not None
        ):
            raise ValueError("inactive edges cannot carry artifact fingerprints")
        return self


class ManchesterResearchLineage(ManchesterSnapshotModel):
    """Self-validating source-to-VEC lineage without widened scientific claims."""

    schema_version: Literal["1.0"] = MANCHESTER_RESEARCH_LINEAGE_SCHEMA_VERSION
    capability_id: Literal["MAN-11"] = MANCHESTER_RESEARCH_LINEAGE_CAPABILITY_ID
    method_version: Literal["manchester-research-lineage-1.0"] = (
        MANCHESTER_RESEARCH_LINEAGE_METHOD_VERSION
    )
    artifacts: tuple[ManchesterLineageArtifactReference, ...]
    stages: tuple[ManchesterLineageStage, ...] = Field(min_length=len(STAGE_ORDER))
    edges: tuple[ManchesterLineageEdge, ...] = Field(min_length=len(STAGE_ORDER) - 1)
    chain_state: ManchesterLineageChainState
    available_stage_count: int = Field(ge=0, le=len(STAGE_ORDER))
    unavailable_stage_count: int = Field(ge=0, le=len(STAGE_ORDER))
    furthest_available_stage: ManchesterLineageStageName | None
    source_snapshot_ids: tuple[str, ...]
    graph_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    public_export_available: Literal[False] = False
    execution_performed_by_lineage_builder: Literal[False] = False
    artifact_bytes_embedded: Literal[False] = False
    capability_acceptance_performed: Literal[False] = False
    domain_validity_established: Literal[False] = False
    causal_claim_available: Literal[False] = False
    randy_policy_validated_for_manchester: Literal[False] = False
    generated_analysis_sites_are_canonical_infrastructure: Literal[False] = False
    interpretation_statement: Literal[
        "A complete lineage proves that named artifacts form the declared Manchester-to-VEC "
        "software chain; it does not prove Manchester realism, Randy-policy domain validity, "
        "causality, public-hosting permission, or capability acceptance."
    ] = (
        "A complete lineage proves that named artifacts form the declared Manchester-to-VEC "
        "software chain; it does not prove Manchester realism, Randy-policy domain validity, "
        "causality, public-hosting permission, or capability acceptance."
    )

    @model_validator(mode="after")
    def validate_rederived_lineage(self) -> Self:
        derived = _derive_lineage(self.artifacts)
        expected: dict[str, object] = {
            "artifacts": derived.artifacts,
            "stages": derived.stages,
            "edges": derived.edges,
            "chain_state": derived.chain_state,
            "available_stage_count": derived.available_stage_count,
            "unavailable_stage_count": len(STAGE_ORDER) - derived.available_stage_count,
            "furthest_available_stage": derived.furthest_available_stage,
            "source_snapshot_ids": derived.source_snapshot_ids,
            "graph_fingerprint": derived.graph_fingerprint,
        }
        for field_name, expected_value in expected.items():
            if getattr(self, field_name) != expected_value:
                raise ValueError(f"{field_name} must be re-derived from the embedded artifacts")
        return self


class _DerivedLineage(ManchesterSnapshotModel):
    artifacts: tuple[ManchesterLineageArtifactReference, ...]
    stages: tuple[ManchesterLineageStage, ...]
    edges: tuple[ManchesterLineageEdge, ...]
    chain_state: ManchesterLineageChainState
    available_stage_count: int
    furthest_available_stage: ManchesterLineageStageName | None
    source_snapshot_ids: tuple[str, ...]
    graph_fingerprint: str


def build_manchester_research_lineage(
    artifacts: (
        tuple[ManchesterLineageArtifactReference, ...] | list[ManchesterLineageArtifactReference]
    ),
) -> ManchesterResearchLineage:
    """Build a canonical MAN-11 graph from a contiguous prefix of artifact references."""

    try:
        derived = _derive_lineage(tuple(artifacts))
    except ValueError as exc:
        raise ManchesterResearchLineageError("LINEAGE_REFUSED", str(exc)) from exc
    return ManchesterResearchLineage(
        artifacts=derived.artifacts,
        stages=derived.stages,
        edges=derived.edges,
        chain_state=derived.chain_state,
        available_stage_count=derived.available_stage_count,
        unavailable_stage_count=len(STAGE_ORDER) - derived.available_stage_count,
        furthest_available_stage=derived.furthest_available_stage,
        source_snapshot_ids=derived.source_snapshot_ids,
        graph_fingerprint=derived.graph_fingerprint,
    )


def _derive_lineage(
    artifacts: tuple[ManchesterLineageArtifactReference, ...],
) -> _DerivedLineage:
    if len(artifacts) > len(STAGE_ORDER):
        raise ValueError("the lineage contains more artifacts than the fixed stage catalogue")
    expected_prefix = STAGE_ORDER[: len(artifacts)]
    observed_stages = tuple(item.stage for item in artifacts)
    if observed_stages != expected_prefix:
        raise ValueError("artifacts must form the exact contiguous stage prefix")
    if len(set(observed_stages)) != len(observed_stages):
        raise ValueError("a lineage stage may appear only once")
    if len({item.artifact_id for item in artifacts}) != len(artifacts):
        raise ValueError("artifact ids must be unique across the lineage")
    if len({item.artifact_fingerprint for item in artifacts}) != len(artifacts):
        raise ValueError("artifact fingerprints must be unique across the lineage")

    if artifacts:
        source_synthetic = artifacts[0].synthetic
        if any(item.synthetic != source_synthetic for item in artifacts):
            raise ValueError("every artifact must preserve the source synthetic classification")
        for previous, current in pairwise(artifacts):
            if current.parent_artifact_fingerprints != (previous.artifact_fingerprint,):
                raise ValueError("each artifact must bind the exact immediate-parent fingerprint")

    by_stage = {item.stage: item for item in artifacts}
    stages: list[ManchesterLineageStage] = []
    upstream_available = True
    for position, stage_name in enumerate(STAGE_ORDER, start=1):
        artifact = by_stage.get(stage_name)
        available = artifact is not None and upstream_available
        if available:
            assert artifact is not None
            state = ManchesterLineageStageState.AVAILABLE
            reason = ManchesterLineageReason.AVAILABLE
            evidence_label = _evidence_label(stage_name, artifact.synthetic)
        else:
            state = ManchesterLineageStageState.UNAVAILABLE
            reason = (
                ManchesterLineageReason.ARTIFACT_NOT_SUPPLIED
                if upstream_available
                else ManchesterLineageReason.UPSTREAM_STAGE_UNAVAILABLE
            )
            evidence_label = None
            artifact = None
        stages.append(
            ManchesterLineageStage(
                stage=stage_name,
                position=position,
                capability_ids=_CAPABILITY_IDS[stage_name],
                state=state,
                reason=reason,
                artifact=artifact,
                evidence_label=evidence_label,
            )
        )
        upstream_available = available

    edges = tuple(
        ManchesterLineageEdge(
            upstream=upstream.stage,
            downstream=downstream.stage,
            active=(
                upstream.state is ManchesterLineageStageState.AVAILABLE
                and downstream.state is ManchesterLineageStageState.AVAILABLE
            ),
            upstream_artifact_fingerprint=(
                upstream.artifact.artifact_fingerprint
                if upstream.artifact is not None and downstream.artifact is not None
                else None
            ),
            downstream_artifact_fingerprint=(
                downstream.artifact.artifact_fingerprint
                if upstream.artifact is not None and downstream.artifact is not None
                else None
            ),
        )
        for upstream, downstream in pairwise(stages)
    )
    available_count = len(artifacts)
    if available_count == 0:
        chain_state = ManchesterLineageChainState.EMPTY
        furthest = None
        source_snapshot_ids: tuple[str, ...] = ()
    elif available_count == len(STAGE_ORDER):
        chain_state = ManchesterLineageChainState.COMPLETE
        furthest = STAGE_ORDER[-1]
        source_snapshot_ids = artifacts[0].source_snapshot_ids
    else:
        chain_state = ManchesterLineageChainState.PARTIAL
        furthest = STAGE_ORDER[available_count - 1]
        source_snapshot_ids = artifacts[0].source_snapshot_ids

    stage_tuple = tuple(stages)
    graph_payload = {
        "artifacts": [item.model_dump(mode="json") for item in artifacts],
        "stages": [item.model_dump(mode="json") for item in stage_tuple],
        "edges": [item.model_dump(mode="json") for item in edges],
    }
    return _DerivedLineage(
        artifacts=artifacts,
        stages=stage_tuple,
        edges=edges,
        chain_state=chain_state,
        available_stage_count=available_count,
        furthest_available_stage=furthest,
        source_snapshot_ids=source_snapshot_ids,
        graph_fingerprint=sha256_hex(canonical_json(graph_payload).encode("utf-8")),
    )


def _evidence_label(
    stage: ManchesterLineageStageName,
    synthetic: bool,
) -> ManchesterLineageEvidenceLabel:
    if synthetic:
        return ManchesterLineageEvidenceLabel.SYNTHETIC_DEVELOPMENT
    if stage in {
        ManchesterLineageStageName.SOURCE_SNAPSHOT,
        ManchesterLineageStageName.PROJECTION,
        ManchesterLineageStageName.NETWORK_MAPPING,
    }:
        return ManchesterLineageEvidenceLabel.OBSERVED_MANCHESTER_EVIDENCE
    if stage is ManchesterLineageStageName.CALIBRATION:
        return ManchesterLineageEvidenceLabel.MANCHESTER_CALIBRATION_CANDIDATE
    if stage in {
        ManchesterLineageStageName.SUMO_EXECUTION,
        ManchesterLineageStageName.FCD_PREPROCESSING,
    }:
        return ManchesterLineageEvidenceLabel.MANCHESTER_CALIBRATED_SIMULATION
    return ManchesterLineageEvidenceLabel.RANDY_POLICY_ON_MANCHESTER_CALIBRATED_SIMULATION

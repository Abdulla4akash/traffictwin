from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.models import ManchesterPublicationClass
from traffictwin.integration.manchester.research_lineage import (
    STAGE_ORDER,
    ManchesterLineageArtifactKind,
    ManchesterLineageArtifactReference,
    ManchesterLineageChainState,
    ManchesterLineageEvidenceLabel,
    ManchesterLineageReason,
    ManchesterLineageStageName,
    ManchesterLineageStageState,
    ManchesterResearchLineage,
    ManchesterResearchLineageError,
    build_manchester_research_lineage,
)


def digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


KIND_BY_STAGE = {
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


def make_artifacts(
    count: int, *, synthetic: bool = False
) -> tuple[ManchesterLineageArtifactReference, ...]:
    artifacts: list[ManchesterLineageArtifactReference] = []
    for index, stage in enumerate(STAGE_ORDER[:count]):
        artifact_fingerprint = digest(f"artifact-{index}")
        artifacts.append(
            ManchesterLineageArtifactReference(
                stage=stage,
                artifact_kind=KIND_BY_STAGE[stage],
                artifact_id=f"artifact:{index}:{stage.value}",
                artifact_fingerprint=artifact_fingerprint,
                contract_fingerprint=digest(f"contract-{index}"),
                parent_artifact_fingerprints=(
                    (artifacts[-1].artifact_fingerprint,) if artifacts else ()
                ),
                source_snapshot_ids=(
                    ("dft-20260723T120000Z-aaaaaaaaaaaa",) if not artifacts else ()
                ),
                publication_class=ManchesterPublicationClass.PRIVATE,
                synthetic=synthetic,
            )
        )
    return tuple(artifacts)


def payload(lineage: ManchesterResearchLineage) -> dict[str, Any]:
    return lineage.model_dump(mode="json")


def test_empty_lineage_exposes_every_stage_as_unavailable() -> None:
    lineage = build_manchester_research_lineage([])

    assert lineage.chain_state is ManchesterLineageChainState.EMPTY
    assert lineage.available_stage_count == 0
    assert lineage.unavailable_stage_count == len(STAGE_ORDER)
    assert lineage.furthest_available_stage is None
    assert lineage.source_snapshot_ids == ()
    assert lineage.stages[0].reason is ManchesterLineageReason.ARTIFACT_NOT_SUPPLIED
    assert all(stage.state is ManchesterLineageStageState.UNAVAILABLE for stage in lineage.stages)
    assert all(not edge.active for edge in lineage.edges)


def test_partial_lineage_identifies_first_missing_and_downstream_blockers() -> None:
    lineage = build_manchester_research_lineage(make_artifacts(3))

    assert lineage.chain_state is ManchesterLineageChainState.PARTIAL
    assert lineage.furthest_available_stage is ManchesterLineageStageName.NETWORK_MAPPING
    assert lineage.available_stage_count == 3
    assert lineage.stages[3].reason is ManchesterLineageReason.ARTIFACT_NOT_SUPPLIED
    assert lineage.stages[4].reason is ManchesterLineageReason.UPSTREAM_STAGE_UNAVAILABLE
    assert [edge.active for edge in lineage.edges[:3]] == [True, True, False]


def test_complete_observed_chain_preserves_semantic_transitions() -> None:
    lineage = build_manchester_research_lineage(make_artifacts(len(STAGE_ORDER)))

    assert lineage.chain_state is ManchesterLineageChainState.COMPLETE
    assert lineage.available_stage_count == len(STAGE_ORDER)
    assert lineage.unavailable_stage_count == 0
    assert all(edge.active for edge in lineage.edges)
    labels = {stage.stage: stage.evidence_label for stage in lineage.stages}
    assert labels[ManchesterLineageStageName.SOURCE_SNAPSHOT] is (
        ManchesterLineageEvidenceLabel.OBSERVED_MANCHESTER_EVIDENCE
    )
    assert labels[ManchesterLineageStageName.CALIBRATION] is (
        ManchesterLineageEvidenceLabel.MANCHESTER_CALIBRATION_CANDIDATE
    )
    assert labels[ManchesterLineageStageName.SUMO_EXECUTION] is (
        ManchesterLineageEvidenceLabel.MANCHESTER_CALIBRATED_SIMULATION
    )
    assert labels[ManchesterLineageStageName.VEC_EXECUTION] is (
        ManchesterLineageEvidenceLabel.RANDY_POLICY_ON_MANCHESTER_CALIBRATED_SIMULATION
    )


def test_synthetic_classification_is_preserved_through_every_stage() -> None:
    lineage = build_manchester_research_lineage(make_artifacts(len(STAGE_ORDER), synthetic=True))

    assert all(
        stage.evidence_label is ManchesterLineageEvidenceLabel.SYNTHETIC_DEVELOPMENT
        for stage in lineage.stages
    )


def test_gap_or_reordered_stage_is_refused() -> None:
    artifacts = list(make_artifacts(3))

    with pytest.raises(ManchesterResearchLineageError, match="contiguous stage prefix"):
        build_manchester_research_lineage([artifacts[0], artifacts[2]])
    with pytest.raises(ManchesterResearchLineageError, match="contiguous stage prefix"):
        build_manchester_research_lineage(list(reversed(artifacts)))


def test_wrong_parent_binding_is_refused() -> None:
    artifacts = list(make_artifacts(2))
    artifacts[1] = artifacts[1].model_copy(
        update={"parent_artifact_fingerprints": (digest("wrong-parent"),)}
    )

    with pytest.raises(ManchesterResearchLineageError, match="immediate-parent fingerprint"):
        build_manchester_research_lineage(artifacts)


def test_synthetic_state_cannot_change_mid_chain() -> None:
    artifacts = list(make_artifacts(2))
    artifacts[1] = artifacts[1].model_copy(update={"synthetic": True})

    with pytest.raises(ManchesterResearchLineageError, match="synthetic classification"):
        build_manchester_research_lineage(artifacts)


def test_stage_requires_its_exact_artifact_kind() -> None:
    data = make_artifacts(1)[0].model_dump(mode="json")
    data["artifact_kind"] = ManchesterLineageArtifactKind.PROJECTION_REPORT.value

    with pytest.raises(ValidationError, match="requires manchester_source_snapshot"):
        ManchesterLineageArtifactReference.model_validate_json(json.dumps(data))


def test_source_and_downstream_reference_shapes_are_distinct() -> None:
    source = make_artifacts(1)[0].model_dump(mode="json")
    source["source_snapshot_ids"] = []
    with pytest.raises(ValidationError, match="requires snapshot ids"):
        ManchesterLineageArtifactReference.model_validate_json(json.dumps(source))

    source = make_artifacts(1)[0].model_dump(mode="json")
    source["parent_artifact_fingerprints"] = [digest("parent")]
    with pytest.raises(ValidationError, match="cannot name a parent"):
        ManchesterLineageArtifactReference.model_validate_json(json.dumps(source))

    downstream = make_artifacts(2)[1].model_dump(mode="json")
    downstream["parent_artifact_fingerprints"] = []
    with pytest.raises(ValidationError, match="exactly one parent"):
        ManchesterLineageArtifactReference.model_validate_json(json.dumps(downstream))

    downstream = make_artifacts(2)[1].model_dump(mode="json")
    downstream["source_snapshot_ids"] = ["dft-20260723T120000Z-aaaaaaaaaaaa"]
    with pytest.raises(ValidationError, match="only the source snapshot"):
        ManchesterLineageArtifactReference.model_validate_json(json.dumps(downstream))


@pytest.mark.parametrize(
    "snapshot_ids",
    [
        ("unsafe",),
        (
            "webtris-20260723T120000Z-bbbbbbbbbbbb",
            "dft-20260723T120000Z-aaaaaaaaaaaa",
        ),
        (
            "dft-20260723T120000Z-aaaaaaaaaaaa",
            "dft-20260723T120000Z-aaaaaaaaaaaa",
        ),
    ],
)
def test_source_snapshot_ids_are_safe_sorted_and_unique(snapshot_ids: tuple[str, ...]) -> None:
    data = make_artifacts(1)[0].model_dump(mode="json")
    data["source_snapshot_ids"] = snapshot_ids

    with pytest.raises(ValidationError, match="snapshot ids"):
        ManchesterLineageArtifactReference.model_validate_json(json.dumps(data))


@pytest.mark.parametrize("field_name", ["artifact_id", "artifact_fingerprint"])
def test_artifact_identities_must_be_unique(field_name: str) -> None:
    artifacts = list(make_artifacts(2))
    artifacts[1] = artifacts[1].model_copy(update={field_name: getattr(artifacts[0], field_name)})

    with pytest.raises(ManchesterResearchLineageError, match="must be unique"):
        build_manchester_research_lineage(artifacts)


def test_complete_chain_does_not_widen_scientific_or_publication_claims() -> None:
    lineage = build_manchester_research_lineage(make_artifacts(len(STAGE_ORDER)))

    assert lineage.public_export_available is False
    assert lineage.execution_performed_by_lineage_builder is False
    assert lineage.artifact_bytes_embedded is False
    assert lineage.capability_acceptance_performed is False
    assert lineage.domain_validity_established is False
    assert lineage.causal_claim_available is False
    assert lineage.randy_policy_validated_for_manchester is False
    assert lineage.generated_analysis_sites_are_canonical_infrastructure is False


def test_canonical_round_trip_is_stable() -> None:
    lineage = build_manchester_research_lineage(make_artifacts(6))
    restored = ManchesterResearchLineage.model_validate_json(lineage.canonical_json())

    assert restored == lineage
    assert restored.fingerprint() == lineage.fingerprint()
    assert restored.graph_fingerprint == lineage.graph_fingerprint


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("available_stage_count", 0),
        ("unavailable_stage_count", 0),
        ("chain_state", "complete"),
        ("furthest_available_stage", "research_archive"),
        ("source_snapshot_ids", []),
        ("graph_fingerprint", digest("forged")),
    ],
)
def test_derived_top_level_fields_cannot_be_forged(field_name: str, value: object) -> None:
    data = payload(build_manchester_research_lineage(make_artifacts(4)))
    data[field_name] = value

    with pytest.raises(ValidationError, match="must be re-derived"):
        ManchesterResearchLineage.model_validate_json(json.dumps(data))


def test_stage_or_edge_mutation_fails_reload() -> None:
    data = payload(build_manchester_research_lineage(make_artifacts(4)))
    data["stages"][0]["capability_ids"] = ["MAN-11"]
    with pytest.raises(ValidationError, match="stages must be re-derived"):
        ManchesterResearchLineage.model_validate_json(json.dumps(data))

    data = payload(build_manchester_research_lineage(make_artifacts(4)))
    data["edges"][0]["downstream_artifact_fingerprint"] = digest("forged")
    with pytest.raises(ValidationError, match="edges must be re-derived"):
        ManchesterResearchLineage.model_validate_json(json.dumps(data))


def test_embedded_parent_mutation_fails_reload() -> None:
    data = payload(build_manchester_research_lineage(make_artifacts(4)))
    data["artifacts"][2]["parent_artifact_fingerprints"] = [digest("forged")]

    with pytest.raises(ValidationError, match="immediate-parent fingerprint"):
        ManchesterResearchLineage.model_validate_json(json.dumps(data))


def test_extra_fields_and_claim_escalation_are_forbidden() -> None:
    source = make_artifacts(1)[0].model_dump(mode="json")
    source["path"] = "/private/source.json"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ManchesterLineageArtifactReference.model_validate_json(json.dumps(source))

    data = payload(build_manchester_research_lineage(make_artifacts(2)))
    data["domain_validity_established"] = True
    with pytest.raises(ValidationError):
        ManchesterResearchLineage.model_validate_json(json.dumps(data))

"""Tests for the TOS publication-manifest policy used by accepted VEC-11.

All commits, hashes, paths, and values are synthetic. No real Randy artifact is
read, copied, or published, and no candidate source commit is treated as
verified.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from traffictwin.integration.tos.publication import (
    MANDATORY_EXCLUDED_KINDS,
    PUBLICATION_REQUIRED_ENGINE_VERSION,
    SELECTED_SEED_MARKER,
    ExcludedArtifact,
    IncludedArtifact,
    PublicationArtifactKind,
    PublicationExclusionReason,
    PublicationPermissionBasis,
    PublicationPermissionState,
    PublicationRepository,
    PublicationSourceLabels,
    RepositoryCitation,
    SanitisationDeclaration,
    TosPublicationManifest,
    default_excluded_inventory,
    permitted_artifact_kinds,
)

SYNTHETIC_VEC_ENV_COMMIT = "a" * 40
SYNTHETIC_TOS_DATA_COMMIT = "b" * 40
SAMPLE_SHA256 = hashlib.sha256(b"synthetic sanitised sample").hexdigest()
AGGREGATE_SHA256 = hashlib.sha256(b"synthetic aggregate output").hexdigest()


def make_citations() -> list[RepositoryCitation]:
    return [
        RepositoryCitation(
            repository=PublicationRepository.VEC_ENV,
            reviewed_commit=SYNTHETIC_VEC_ENV_COMMIT,
            citation_text=(
                f"Synthetic Author, vec_env, commit {SYNTHETIC_VEC_ENV_COMMIT[:12]}, 2026."
            ),
            url="https://example.invalid/vec_env",
        ),
        RepositoryCitation(
            repository=PublicationRepository.TOS_DATA,
            reviewed_commit=SYNTHETIC_TOS_DATA_COMMIT,
            citation_text=(
                f"Synthetic Author, tos-data, commit {SYNTHETIC_TOS_DATA_COMMIT[:12]}, 2026."
            ),
        ),
    ]


def make_permission() -> PublicationPermissionBasis:
    return PublicationPermissionBasis(
        basis="Written owner response permitting sanitised samples and aggregates.",
        granted_on=date(2026, 7, 21),
        scope="Sanitised samples and aggregate outputs in this repository and dissertation.",
    )


def make_sanitisation() -> SanitisationDeclaration:
    return SanitisationDeclaration(
        statement="Synthetic fixture sanitisation removing secrets, paths, and raw data.",
        secrets_removed=True,
        private_paths_and_machine_information_removed=True,
        actor_checkpoints_excluded=True,
        third_party_sumo_assets_excluded=True,
        raw_datasets_reduced_to_sanitised_sample=True,
        schema_and_units_preserved=True,
    )


def make_sample_artifact(**overrides: object) -> IncludedArtifact:
    payload: dict[str, Any] = {
        "relative_path": "samples/wd_am_sanitised_sample.csv",
        "kind": PublicationArtifactKind.SANITISED_SAMPLE,
        "permission_state": PublicationPermissionState.WRITTEN_OWNER_PERMISSION,
        "sha256": SAMPLE_SHA256,
        "size_bytes": 2_048,
        "description": "Synthetic sanitised matched-sample fixture.",
        "labels": PublicationSourceLabels(
            source_mode="instrumented",
            campaign="baseline",
            scenario="wd_am",
            fleet="uk2030",
            fleet_seed=0,
            evaluator_seed=7,
        ),
    }
    payload.update(overrides)
    return IncludedArtifact(**payload)


def make_aggregate_artifact(**overrides: object) -> IncludedArtifact:
    payload: dict[str, Any] = {
        "relative_path": "aggregates/deadline_success_by_campaign.json",
        "kind": PublicationArtifactKind.AGGREGATE,
        "permission_state": PublicationPermissionState.WRITTEN_OWNER_PERMISSION,
        "sha256": AGGREGATE_SHA256,
        "size_bytes": 512,
        "description": "Synthetic aggregate deadline-success summary.",
    }
    payload.update(overrides)
    return IncludedArtifact(**payload)


def make_manifest(**overrides: object) -> TosPublicationManifest:
    payload: dict[str, Any] = {
        "engine_version": PUBLICATION_REQUIRED_ENGINE_VERSION,
        "citations": make_citations(),
        "permission": make_permission(),
        "sanitisation": make_sanitisation(),
        "included": [make_sample_artifact(), make_aggregate_artifact()],
        "excluded": default_excluded_inventory(),
        "limitations": [
            "Synthetic fixture values only; no real Randy artifact is published.",
            "Aggregates carry their source denominators and are not causal claims.",
        ],
    }
    payload.update(overrides)
    return TosPublicationManifest(**payload)


def test_valid_sanitised_sample_manifest() -> None:
    manifest = make_manifest(included=[make_sample_artifact()])

    assert manifest.engine_version == "v2_post_nrsus_fix"
    assert [citation.repository.value for citation in manifest.citations] == [
        "tos-data",
        "vec_env",
    ]
    assert manifest.included[0].kind is PublicationArtifactKind.SANITISED_SAMPLE
    assert manifest.included[0].labels is not None
    assert manifest.included[0].labels.scenario == "wd_am"
    assert manifest.permission.granted_on == date(2026, 7, 21)
    assert all(citation.commit_verification == "caller_supplied" for citation in manifest.citations)


def test_valid_aggregate_manifest() -> None:
    manifest = make_manifest(included=[make_aggregate_artifact()])

    assert manifest.included[0].kind is PublicationArtifactKind.AGGREGATE
    assert manifest.selected_seed_disclosure is None
    assert len(manifest.fingerprint()) == 64
    json.loads(manifest.canonical_json())


def test_fingerprint_is_deterministic_and_order_insensitive() -> None:
    manifest = make_manifest()
    permuted = make_manifest(
        citations=list(reversed(make_citations())),
        included=[make_aggregate_artifact(), make_sample_artifact()],
        excluded=list(reversed(default_excluded_inventory())),
    )

    assert manifest.canonical_json() == permuted.canonical_json()
    assert manifest.fingerprint() == permuted.fingerprint()
    assert [item.relative_path for item in permuted.included] == sorted(
        item.relative_path for item in permuted.included
    )
    assert [item.kind.value for item in permuted.excluded] == sorted(
        item.kind.value for item in permuted.excluded
    )


@pytest.mark.parametrize(
    "path",
    [
        "/absolute/sample.csv",
        "../escape.csv",
        "samples/../escape.csv",
        "samples/./sample.csv",
        "samples//sample.csv",
        "samples\\sample.csv",
        "C:/samples/sample.csv",
        "~/samples/sample.csv",
        "samples/",
        "",
    ],
)
def test_unsafe_relative_paths_rejected(path: str) -> None:
    with pytest.raises(ValidationError, match="portable path"):
        make_sample_artifact(relative_path=path)


@pytest.mark.parametrize(
    "digest",
    [
        "not-a-hash",
        "abc123",
        SAMPLE_SHA256[:-1],
        SAMPLE_SHA256 + "0",
        SAMPLE_SHA256.upper(),
    ],
)
def test_invalid_sha256_rejected(digest: str) -> None:
    with pytest.raises(ValidationError, match="sha256"):
        make_sample_artifact(sha256=digest)


def test_invalid_reviewed_commit_rejected() -> None:
    with pytest.raises(ValidationError, match="reviewed_commit"):
        RepositoryCitation(
            repository=PublicationRepository.VEC_ENV,
            reviewed_commit="not-a-commit",
            citation_text="Synthetic Author, vec_env, commit not-a-commit, 2026.",
        )


def test_citation_must_mention_reviewed_commit() -> None:
    with pytest.raises(ValidationError, match="citation_text must cite the reviewed commit"):
        RepositoryCitation(
            repository=PublicationRepository.VEC_ENV,
            reviewed_commit=SYNTHETIC_VEC_ENV_COMMIT,
            citation_text="Synthetic Author, vec_env, no commit stated, 2026.",
        )


@pytest.mark.parametrize("missing", ["vec_env", "tos-data"])
def test_missing_repository_citation_rejected(missing: str) -> None:
    kept = [citation for citation in make_citations() if citation.repository.value != missing]
    with pytest.raises(ValidationError, match=missing):
        make_manifest(citations=[kept[0], kept[0]])


@pytest.mark.parametrize("engine_version", ["", "v1", "v2", "V2_POST_NRSUS_FIX"])
def test_wrong_engine_version_rejected(engine_version: str) -> None:
    with pytest.raises(ValidationError, match="engine version"):
        make_manifest(engine_version=engine_version)


def test_missing_engine_version_rejected() -> None:
    payload = make_manifest().model_dump(mode="json")
    del payload["engine_version"]
    with pytest.raises(ValidationError, match="engine_version"):
        TosPublicationManifest.model_validate(payload)


def test_selected_seed_path_requires_flag_and_disclosure() -> None:
    with pytest.raises(ValidationError, match="uses_selected_seed"):
        make_sample_artifact(relative_path="samples/ukfleettrain_mappo_s102_sample.csv")

    selected = make_sample_artifact(
        relative_path="samples/ukfleettrain_mappo_s102_sample.csv",
        uses_selected_seed=True,
    )
    with pytest.raises(ValidationError, match="selected_seed_disclosure"):
        make_manifest(included=[selected])

    manifest = make_manifest(
        included=[selected],
        selected_seed_disclosure=(
            f"The {SELECTED_SEED_MARKER} rows are a best-of-seeds selection, not an "
            "average over evaluator seeds."
        ),
    )
    assert manifest.selected_seed_disclosure is not None


def test_selected_seed_label_in_campaign_requires_disclosure() -> None:
    selected = make_aggregate_artifact(
        labels=PublicationSourceLabels(campaign="ukfleettrain_mappo_s102"),
        uses_selected_seed=True,
    )
    with pytest.raises(ValidationError, match="selected_seed_disclosure"):
        make_manifest(included=[selected])


def test_disclosure_must_retain_selected_seed_label() -> None:
    with pytest.raises(ValidationError, match=SELECTED_SEED_MARKER):
        make_manifest(selected_seed_disclosure="Best seed was selected.")


@pytest.mark.parametrize(
    "kind",
    [
        PublicationArtifactKind.RAW_DATASET,
        PublicationArtifactKind.FULL_REPOSITORY,
        PublicationArtifactKind.ACTOR_CHECKPOINT,
        PublicationArtifactKind.PRIVATE_MACHINE_INFORMATION,
        PublicationArtifactKind.THIRD_PARTY_SUMO_ASSET,
    ],
)
def test_non_permitted_kinds_refused(kind: PublicationArtifactKind) -> None:
    with pytest.raises(ValidationError, match="outside the written permission"):
        make_sample_artifact(kind=kind)


@pytest.mark.parametrize(
    "state",
    [PublicationPermissionState.UNKNOWN, PublicationPermissionState.DENIED],
)
def test_unknown_or_denied_permission_refused(state: PublicationPermissionState) -> None:
    with pytest.raises(ValidationError, match="cannot be published"):
        make_sample_artifact(permission_state=state)


def test_extra_fields_rejected() -> None:
    with pytest.raises(ValidationError, match="unexpected_field"):
        make_manifest(unexpected_field="value")
    with pytest.raises(ValidationError, match="surprise"):
        make_sample_artifact(surprise=True)
    with pytest.raises(ValidationError, match="extra"):
        SanitisationDeclaration.model_validate(
            {
                "statement": "Synthetic fixture sanitisation statement.",
                "secrets_removed": True,
                "private_paths_and_machine_information_removed": True,
                "actor_checkpoints_excluded": True,
                "third_party_sumo_assets_excluded": True,
                "raw_datasets_reduced_to_sanitised_sample": True,
                "schema_and_units_preserved": True,
                "extra": "no",
            }
        )


def test_incomplete_sanitisation_declaration_rejected() -> None:
    with pytest.raises(ValidationError, match="actor_checkpoints_excluded"):
        SanitisationDeclaration(
            statement="Synthetic fixture sanitisation statement.",
            secrets_removed=True,
            private_paths_and_machine_information_removed=True,
            actor_checkpoints_excluded=False,
            third_party_sumo_assets_excluded=True,
            raw_datasets_reduced_to_sanitised_sample=True,
            schema_and_units_preserved=True,
        )


def test_excluded_artifacts_remain_visible() -> None:
    manifest = make_manifest()
    declared_kinds = {artifact.kind for artifact in manifest.excluded}
    assert declared_kinds >= MANDATORY_EXCLUDED_KINDS

    canonical = manifest.canonical_json()
    for kind in MANDATORY_EXCLUDED_KINDS:
        assert kind.value in canonical
    assert "frozen actor checkpoints" in canonical


def test_missing_mandatory_exclusion_rejected() -> None:
    partial = [
        artifact
        for artifact in default_excluded_inventory()
        if artifact.kind is not PublicationArtifactKind.ACTOR_CHECKPOINT
    ]
    with pytest.raises(ValidationError, match="actor_checkpoint"):
        make_manifest(excluded=partial)


def test_duplicate_included_paths_rejected() -> None:
    with pytest.raises(ValidationError, match="repeat a relative path"):
        make_manifest(included=[make_sample_artifact(), make_sample_artifact()])


def test_duplicate_excluded_entries_rejected() -> None:
    inventory = default_excluded_inventory()
    with pytest.raises(ValidationError, match="repeat a kind and identifier"):
        make_manifest(excluded=[*inventory, inventory[0]])


def test_empty_and_oversized_artifacts_rejected() -> None:
    with pytest.raises(ValidationError, match="size_bytes"):
        make_sample_artifact(size_bytes=0)
    with pytest.raises(ValidationError, match="size_bytes"):
        make_sample_artifact(size_bytes=100_000_001)


def test_manifest_is_frozen() -> None:
    manifest = make_manifest()
    with pytest.raises(ValidationError, match="frozen"):
        manifest.engine_version = "v3"  # type: ignore[misc]


def test_permitted_kinds_are_samples_and_aggregates_only() -> None:
    assert permitted_artifact_kinds() == (
        PublicationArtifactKind.AGGREGATE,
        PublicationArtifactKind.SANITISED_SAMPLE,
    )
    assert PublicationExclusionReason.PERMISSION_UNKNOWN.value == "permission_unknown"


def test_absolute_path_text_rejected_in_excluded_identifier() -> None:
    with pytest.raises(ValidationError, match="local absolute paths"):
        ExcludedArtifact(
            identifier="/home/randy/private/raw.npz",
            kind=PublicationArtifactKind.RAW_DATASET,
            reason=PublicationExclusionReason.OUTSIDE_WRITTEN_PERMISSION,
            detail="Raw dataset excluded.",
        )

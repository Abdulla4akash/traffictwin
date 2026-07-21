"""Permission-aware publication-manifest policy for Randy/TOS-derived artifacts.

This module defines the strict, deterministic manifest models and current
written-permission policy for Randy/TOS-derived dissertation artifacts. The
accepted VEC-11 execution layer in ``integration.vec_publication`` applies this
policy to exact inspected source evidence. This policy module itself does not
inspect external repositories, copy artifacts, or verify source commits.

Current policy scope (written owner permission, 21 July 2026 response):

- only sanitised samples and aggregate outputs may be included;
- full raw datasets, complete repositories, actor/checkpoint redistribution,
  private machine information, third-party SUMO assets, and anything with
  unknown or denied permission are refused and must remain visible as
  excluded artifacts;
- both ``vec_env`` and ``tos-data`` must be cited with caller-supplied reviewed
  commits (this library never asserts a commit was verified);
- the engine version must be exactly ``v2_post_nrsus_fix``;
- any artifact touching the best-of-seeds ``_s102`` selection requires an
  explicit disclosure that retains the ``_s102`` label.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.integration.tos.models import TOS_EXPECTED_ENGINE_VERSION

TOS_PUBLICATION_POLICY_VERSION: Literal["tos-publication-policy-1.0"] = "tos-publication-policy-1.0"
PUBLICATION_REQUIRED_ENGINE_VERSION = TOS_EXPECTED_ENGINE_VERSION
SELECTED_SEED_MARKER = "_s102"
MAX_INCLUDED_ARTIFACTS = 256
MAX_EXCLUDED_ARTIFACTS = 256
MAX_INCLUDED_ARTIFACT_BYTES = 50_000_000
MAX_INCLUDED_TOTAL_BYTES = 100_000_000
_MAX_PORTABLE_PATH_LENGTH = 500
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_COMMIT_PATTERN = r"^[0-9a-f]{40}$"
_COMMIT_CITATION_PREFIX_LENGTH = 12


class PublicationPolicyModel(BaseModel):
    """Strict, immutable base for publication-policy models."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def canonical_json(self) -> str:
        """Return the canonical JSON form used for fingerprinting."""

        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    def fingerprint(self) -> str:
        """Return the SHA-256 fingerprint of the canonical JSON form."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class PublicationRepository(StrEnum):
    """Source repositories that must both be cited."""

    VEC_ENV = "vec_env"
    TOS_DATA = "tos-data"


class PublicationArtifactKind(StrEnum):
    """Every artifact category the policy can name, permitted or not."""

    SANITISED_SAMPLE = "sanitised_sample"
    AGGREGATE = "aggregate"
    RAW_DATASET = "raw_dataset"
    FULL_REPOSITORY = "full_repository"
    ACTOR_CHECKPOINT = "actor_checkpoint"
    PRIVATE_MACHINE_INFORMATION = "private_machine_information"
    THIRD_PARTY_SUMO_ASSET = "third_party_sumo_asset"


PERMITTED_PUBLICATION_KINDS = frozenset(
    {
        PublicationArtifactKind.SANITISED_SAMPLE,
        PublicationArtifactKind.AGGREGATE,
    }
)
MANDATORY_EXCLUDED_KINDS = frozenset(
    {
        PublicationArtifactKind.RAW_DATASET,
        PublicationArtifactKind.FULL_REPOSITORY,
        PublicationArtifactKind.ACTOR_CHECKPOINT,
        PublicationArtifactKind.PRIVATE_MACHINE_INFORMATION,
        PublicationArtifactKind.THIRD_PARTY_SUMO_ASSET,
    }
)


class PublicationPermissionState(StrEnum):
    """Explicit permission state for one artifact."""

    WRITTEN_OWNER_PERMISSION = "written_owner_permission"
    UNKNOWN = "unknown"
    DENIED = "denied"


class PublicationExclusionReason(StrEnum):
    """Why an artifact stays out of the publication set."""

    OUTSIDE_WRITTEN_PERMISSION = "outside_written_permission"
    PERMISSION_UNKNOWN = "permission_unknown"
    PERMISSION_DENIED = "permission_denied"
    PRIVATE_INFORMATION = "private_information"
    THIRD_PARTY_RIGHTS = "third_party_rights"


def permitted_artifact_kinds() -> tuple[PublicationArtifactKind, ...]:
    """Return the artifact kinds the current written permission covers."""

    return tuple(sorted(PERMITTED_PUBLICATION_KINDS, key=lambda kind: kind.value))


def _validate_portable_relative_path(value: str) -> str:
    if not value or len(value) > _MAX_PORTABLE_PATH_LENGTH:
        raise ValueError(
            f"portable path must be 1-{_MAX_PORTABLE_PATH_LENGTH} characters: {value!r}"
        )
    if "\\" in value or ":" in value or any(ord(char) < 32 for char in value):
        raise ValueError(
            "portable path must use forward slashes without drive letters or "
            f"control characters: {value!r}"
        )
    if value.startswith(("/", "~")):
        raise ValueError(f"portable path must be relative: {value!r}")
    if any(segment in {"", ".", ".."} for segment in value.split("/")):
        raise ValueError(f"portable path must not contain empty, '.', or '..' segments: {value!r}")
    return value


def _validate_portable_text(value: str) -> str:
    if "\\" in value or "\x00" in value or any(ord(char) < 32 for char in value):
        raise ValueError(f"text must not contain backslashes or control characters: {value!r}")
    if value.startswith(("/", "~")) or "file://" in value:
        raise ValueError(f"text must not carry local absolute paths: {value!r}")
    return value


class RepositoryCitation(PublicationPolicyModel):
    """Citation for one source repository at a caller-supplied reviewed commit.

    The reviewed commit is recorded exactly as supplied; this model does not
    verify that the commit exists or matches any remote reference.
    """

    repository: PublicationRepository
    reviewed_commit: str = Field(pattern=_COMMIT_PATTERN)
    commit_verification: Literal["caller_supplied"] = "caller_supplied"
    citation_text: str = Field(min_length=10, max_length=2_000)
    url: str | None = Field(default=None, pattern=r"^https?://\S+$", max_length=500)

    @field_validator("citation_text")
    @classmethod
    def validate_citation_text(cls, value: str) -> str:
        return _validate_portable_text(value)

    @model_validator(mode="after")
    def validate_commit_in_citation(self) -> Self:
        prefix = self.reviewed_commit[:_COMMIT_CITATION_PREFIX_LENGTH]
        if prefix not in self.citation_text:
            raise ValueError(
                "citation_text must cite the reviewed commit with at least its "
                f"first {_COMMIT_CITATION_PREFIX_LENGTH} characters ({prefix})"
            )
        return self


class PublicationPermissionBasis(PublicationPolicyModel):
    """The written basis, date, and scope of the owner permission."""

    basis: str = Field(min_length=10, max_length=2_000)
    granted_on: date
    scope: str = Field(min_length=10, max_length=2_000)
    licence_statement: str = Field(
        default=(
            "Owner permission covers sanitised samples and aggregate outputs only "
            "and is not a formal software or data licence."
        ),
        min_length=10,
        max_length=2_000,
    )

    @field_validator("basis", "scope", "licence_statement")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _validate_portable_text(value)


class SanitisationDeclaration(PublicationPolicyModel):
    """Explicit declaration of what sanitisation removed and preserved."""

    statement: str = Field(min_length=10, max_length=2_000)
    secrets_removed: bool
    private_paths_and_machine_information_removed: bool
    actor_checkpoints_excluded: bool
    third_party_sumo_assets_excluded: bool
    raw_datasets_reduced_to_sanitised_sample: bool
    schema_and_units_preserved: bool

    @field_validator("statement")
    @classmethod
    def validate_statement(cls, value: str) -> str:
        return _validate_portable_text(value)

    @model_validator(mode="after")
    def validate_declaration_is_complete(self) -> Self:
        required = {
            "secrets_removed": self.secrets_removed,
            "private_paths_and_machine_information_removed": (
                self.private_paths_and_machine_information_removed
            ),
            "actor_checkpoints_excluded": self.actor_checkpoints_excluded,
            "third_party_sumo_assets_excluded": self.third_party_sumo_assets_excluded,
            "raw_datasets_reduced_to_sanitised_sample": (
                self.raw_datasets_reduced_to_sanitised_sample
            ),
            "schema_and_units_preserved": self.schema_and_units_preserved,
        }
        failed = sorted(name for name, satisfied in required.items() if not satisfied)
        if failed:
            raise ValueError(
                "sanitisation declaration must affirm every guarantee; "
                f"missing: {', '.join(failed)}"
            )
        return self


class PublicationSourceLabels(PublicationPolicyModel):
    """Source, campaign, scenario, fleet, and seed labels where applicable."""

    source_mode: str | None = Field(default=None, min_length=1, max_length=200)
    campaign: str | None = Field(default=None, min_length=1, max_length=200)
    scenario: str | None = Field(default=None, min_length=1, max_length=200)
    fleet: str | None = Field(default=None, min_length=1, max_length=200)
    actor: str | None = Field(default=None, min_length=1, max_length=200)
    trace_day: str | None = Field(default=None, min_length=1, max_length=200)
    trace_window: str | None = Field(default=None, min_length=1, max_length=200)
    fleet_seed: int | None = Field(default=None, ge=0)
    evaluator_seed: int | None = Field(default=None, ge=0)

    @field_validator(
        "source_mode",
        "campaign",
        "scenario",
        "fleet",
        "actor",
        "trace_day",
        "trace_window",
    )
    @classmethod
    def validate_label_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_portable_text(value)

    def text_values(self) -> tuple[str, ...]:
        """Return every populated string label for policy scanning."""

        return tuple(
            value
            for value in (
                self.source_mode,
                self.campaign,
                self.scenario,
                self.fleet,
                self.actor,
                self.trace_day,
                self.trace_window,
            )
            if value is not None
        )


class IncludedArtifact(PublicationPolicyModel):
    """One artifact the manifest publishes under the written permission."""

    relative_path: str
    kind: PublicationArtifactKind
    permission_state: PublicationPermissionState
    sha256: str = Field(pattern=_SHA256_PATTERN)
    size_bytes: int = Field(ge=1, le=MAX_INCLUDED_ARTIFACT_BYTES)
    description: str = Field(min_length=1, max_length=500)
    labels: PublicationSourceLabels | None = None
    uses_selected_seed: bool = False

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        return _validate_portable_relative_path(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return _validate_portable_text(value)

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if self.kind not in PERMITTED_PUBLICATION_KINDS:
            raise ValueError(
                f"artifact kind {self.kind.value!r} is outside the written permission; "
                "only sanitised samples and aggregate outputs may be published"
            )
        if self.permission_state is not PublicationPermissionState.WRITTEN_OWNER_PERMISSION:
            raise ValueError(
                f"artifact permission is {self.permission_state.value!r}; unknown or "
                "denied permission cannot be published and must be recorded as an "
                "excluded artifact"
            )
        if not self.uses_selected_seed and self._mentions_selected_seed():
            raise ValueError(
                f"artifact references the {SELECTED_SEED_MARKER} best-of-seeds selection "
                "and must set uses_selected_seed=True"
            )
        return self

    def _mentions_selected_seed(self) -> bool:
        values = [self.relative_path, self.description]
        if self.labels is not None:
            values.extend(self.labels.text_values())
        return any(SELECTED_SEED_MARKER in value for value in values)

    @property
    def requires_selected_seed_disclosure(self) -> bool:
        """Whether this artifact obliges the manifest to carry the disclosure."""

        return self.uses_selected_seed or self._mentions_selected_seed()


class ExcludedArtifact(PublicationPolicyModel):
    """One artifact that stays out of the publication set but remains visible."""

    identifier: str = Field(min_length=1, max_length=300)
    kind: PublicationArtifactKind
    reason: PublicationExclusionReason
    detail: str = Field(min_length=1, max_length=500)

    @field_validator("identifier", "detail")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _validate_portable_text(value)


def default_excluded_inventory() -> list[ExcludedArtifact]:
    """Return the standing exclusions the current permission scope requires."""

    return [
        ExcludedArtifact(
            identifier="full raw TOS result datasets",
            kind=PublicationArtifactKind.RAW_DATASET,
            reason=PublicationExclusionReason.OUTSIDE_WRITTEN_PERMISSION,
            detail=(
                "The written permission covers sanitised samples and aggregates "
                "only; complete raw datasets are not redistributed."
            ),
        ),
        ExcludedArtifact(
            identifier="complete vec_env and tos-data repositories",
            kind=PublicationArtifactKind.FULL_REPOSITORY,
            reason=PublicationExclusionReason.OUTSIDE_WRITTEN_PERMISSION,
            detail=(
                "Repository redistribution is not granted; the sources are cited "
                "by reviewed commit instead."
            ),
        ),
        ExcludedArtifact(
            identifier="frozen actor checkpoints",
            kind=PublicationArtifactKind.ACTOR_CHECKPOINT,
            reason=PublicationExclusionReason.OUTSIDE_WRITTEN_PERMISSION,
            detail=(
                "Actor and checkpoint binaries are not redistributed without a "
                "separate written basis."
            ),
        ),
        ExcludedArtifact(
            identifier="private machine and environment records",
            kind=PublicationArtifactKind.PRIVATE_MACHINE_INFORMATION,
            reason=PublicationExclusionReason.PRIVATE_INFORMATION,
            detail=(
                "Hostnames, usernames, local absolute paths, and machine records "
                "are removed from every published artifact."
            ),
        ),
        ExcludedArtifact(
            identifier="third-party SUMO network and FCD assets",
            kind=PublicationArtifactKind.THIRD_PARTY_SUMO_ASSET,
            reason=PublicationExclusionReason.THIRD_PARTY_RIGHTS,
            detail=(
                "Third-party SUMO assets carry their own rights and are not "
                "republished under the owner permission."
            ),
        ),
    ]


class TosPublicationManifest(PublicationPolicyModel):
    """Strict, deterministic manifest for one permission-bounded publication set."""

    schema_version: Literal["1.0"] = "1.0"
    policy_version: Literal["tos-publication-policy-1.0"] = TOS_PUBLICATION_POLICY_VERSION
    engine_version: str
    citations: list[RepositoryCitation] = Field(min_length=2, max_length=2)
    permission: PublicationPermissionBasis
    sanitisation: SanitisationDeclaration
    selected_seed_disclosure: str | None = Field(default=None, min_length=1, max_length=2_000)
    included: list[IncludedArtifact] = Field(min_length=1, max_length=MAX_INCLUDED_ARTIFACTS)
    excluded: list[ExcludedArtifact] = Field(min_length=1, max_length=MAX_EXCLUDED_ARTIFACTS)
    limitations: list[str] = Field(min_length=1, max_length=64)

    @field_validator("selected_seed_disclosure")
    @classmethod
    def validate_disclosure_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_portable_text(value)

    @field_validator("engine_version")
    @classmethod
    def validate_engine_version(cls, value: str) -> str:
        if value != PUBLICATION_REQUIRED_ENGINE_VERSION:
            raise ValueError(
                "current publication policy requires engine version "
                f"{PUBLICATION_REQUIRED_ENGINE_VERSION!r}; got {value!r}"
            )
        return value

    @field_validator("citations")
    @classmethod
    def sort_citations(cls, value: list[RepositoryCitation]) -> list[RepositoryCitation]:
        return sorted(value, key=lambda citation: citation.repository.value)

    @field_validator("included")
    @classmethod
    def sort_included(cls, value: list[IncludedArtifact]) -> list[IncludedArtifact]:
        return sorted(value, key=lambda artifact: artifact.relative_path)

    @field_validator("excluded")
    @classmethod
    def sort_excluded(cls, value: list[ExcludedArtifact]) -> list[ExcludedArtifact]:
        return sorted(value, key=lambda artifact: (artifact.kind.value, artifact.identifier))

    @field_validator("limitations")
    @classmethod
    def validate_limitations(cls, value: list[str]) -> list[str]:
        for limitation in value:
            if not 1 <= len(limitation) <= 1_000:
                raise ValueError("each limitation must be 1-1000 characters")
            _validate_portable_text(limitation)
        if len(set(value)) != len(value):
            raise ValueError("limitations must not contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_manifest_policy(self) -> Self:
        cited = [citation.repository for citation in self.citations]
        missing = sorted(
            repository.value for repository in PublicationRepository if repository not in cited
        )
        if missing:
            raise ValueError(
                f"manifest must cite both source repositories; missing: {', '.join(missing)}"
            )

        included_paths = [artifact.relative_path for artifact in self.included]
        if len(set(included_paths)) != len(included_paths):
            raise ValueError("included artifacts must not repeat a relative path")

        excluded_keys = [(artifact.kind, artifact.identifier) for artifact in self.excluded]
        if len(set(excluded_keys)) != len(excluded_keys):
            raise ValueError("excluded artifacts must not repeat a kind and identifier pair")

        declared_excluded_kinds = {artifact.kind for artifact in self.excluded}
        undeclared = sorted(
            kind.value for kind in MANDATORY_EXCLUDED_KINDS - declared_excluded_kinds
        )
        if undeclared:
            raise ValueError(
                "manifest must keep every non-permitted category visible as an "
                f"excluded artifact; missing kinds: {', '.join(undeclared)}"
            )

        total_bytes = sum(artifact.size_bytes for artifact in self.included)
        if total_bytes > MAX_INCLUDED_TOTAL_BYTES:
            raise ValueError(
                f"included artifacts total {total_bytes} bytes, above the "
                f"{MAX_INCLUDED_TOTAL_BYTES}-byte publication bound"
            )

        needs_disclosure = any(
            artifact.requires_selected_seed_disclosure for artifact in self.included
        )
        if needs_disclosure and self.selected_seed_disclosure is None:
            raise ValueError(
                f"manifest publishes {SELECTED_SEED_MARKER} best-of-seeds material and "
                "must carry an explicit selected_seed_disclosure"
            )
        if (
            self.selected_seed_disclosure is not None
            and SELECTED_SEED_MARKER not in self.selected_seed_disclosure
        ):
            raise ValueError(
                f"selected_seed_disclosure must retain the {SELECTED_SEED_MARKER} label"
            )
        return self

"""Strict end-to-end reproducibility artifact models for VEC-12."""

from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
from typing import Literal, Self, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VEC_RESEARCH_VERSION: Literal["vec-end-to-end-research-artifact-1.0"] = (
    "vec-end-to-end-research-artifact-1.0"
)
VEC_RESEARCH_MANIFEST_PATH = "manifest.json"
VEC_RESEARCH_CHECKSUMS_PATH = "checksums.sha256"
VEC_RESEARCH_ARCHIVE_NAME = "vec_end_to_end_research_artifact.zip"

VEC_RESEARCH_PAYLOAD_PATHS = (
    "CITATION.cff",
    "README.md",
    "contracts/tos_source_contract_v2.json",
    "contracts/vec_dissertation_pack_contract.json",
    "contracts/vec_fcd_preprocessing_contract.json",
    "contracts/vec_identity_contract.json",
    "contracts/vec_interface_contract.json",
    "contracts/vec_reproduction_contract.json",
    "contracts/vec_runner_contract.json",
    "contracts/vec_scientific_admission_contract.json",
    "contracts/vec_task_join_contract.json",
    "contracts/vec_trip_join_contract.json",
    "evidence/vec_identity_verification.json",
    "evidence/vec_interface_verification.json",
    "evidence/vec_reproduction_report.json",
    "evidence/vec_scientific_admission_report.json",
    "evidence/vec_source_snapshot_audit.json",
    "evidence/vec_task_join_verification.json",
    "evidence/vec_trip_join_verification.json",
    "limitations.json",
    "method/vec_end_to_end_contract.json",
    "provenance.json",
    "publication/aggregate_metrics_s102.csv",
    "publication/manifest.json",
    "publication/sanitised_matched_sample_s102.csv",
)
VEC_RESEARCH_ALL_PATHS = tuple(
    sorted((*VEC_RESEARCH_PAYLOAD_PATHS, VEC_RESEARCH_MANIFEST_PATH, VEC_RESEARCH_CHECKSUMS_PATH))
)
VEC_RESEARCH_LIMITATIONS = (
    (
        "VEC-08 reproduces the protocol-seed ukfleettrain-MAPPO case; VEC-09/VEC-11 "
        "report the distinct disclosed _s102 best-of-seeds run."
    ),
    (
        "Numerical equivalence is established only for the recorded Apple-arm64 CPU, "
        "Python, NumPy, JAX, and JAXLIB environment and frozen tolerances."
    ),
    "Deadline success is not eventual physical task completion.",
    "Eligible decision-time targets are not confirmed transfers or execution targets.",
    (
        "VEC-08 observes an aggregate energy reduction, but compatible per-task energy "
        "evidence remains unavailable to VEC-09."
    ),
    (
        "R1, R2, and R7 remain blocked; R6 is conditional; no diagnostic threshold or "
        "finding was evaluated."
    ),
    (
        "VEC-06 is an accepted alternative preprocessing path but was not consumed by the "
        "selected VEC-08 reproduction case."
    ),
    "Metric comparisons are deterministic and descriptive; no causal claim is made.",
    "The three-row publication sample is pseudonymised and rounded, not anonymous or exact.",
    (
        "Written owner permission is not a formal software/data licence, and public hosting "
        "remains unauthorised."
    ),
    (
        "The archive embeds no raw NPZ/XML, execution output bytes, checkpoint, source "
        "repository, private path, or identity mapping."
    ),
)

CapabilityId: TypeAlias = Literal[
    "VEC-01",
    "VEC-02",
    "VEC-03",
    "VEC-04",
    "VEC-05",
    "VEC-06",
    "VEC-07",
    "VEC-08",
    "VEC-09",
    "VEC-10",
    "VEC-11",
    "VEC-12",
]


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _portable_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or value.startswith(("~", "/"))
        or "\\" in value
        or ":" in value
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(ord(char) < 32 for char in value)
    ):
        raise ValueError(f"unsafe portable artifact path: {value!r}")
    return value


class VecResearchModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        return _sha256(self.canonical_json().encode())


class VecResearchInventoryEntry(VecResearchModel):
    path: str
    role: str = Field(pattern=r"^[a-z0-9_.-]+$")
    capability: CapabilityId
    permission_class: Literal["audit_or_software_metadata", "sanitised_sample", "aggregate"]
    media_type: Literal["application/json", "text/csv", "text/markdown", "text/yaml"]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0, le=1_000_000)
    raw_external_bytes: Literal[False] = False

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _portable_path(value)


class VecCapabilityEvidence(VecResearchModel):
    capability: CapabilityId
    status: Literal["accepted"] = "accepted"
    relationship_to_published_result: Literal[
        "direct_evidence",
        "separate_execution_evidence",
        "accepted_alternative_input_path_not_used",
        "thin_interface",
        "permission_bounded_output",
    ]
    evidence_paths: tuple[str, ...]

    @field_validator("evidence_paths")
    @classmethod
    def validate_paths(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or tuple(sorted(set(value))) != value:
            raise ValueError("capability evidence paths must be non-empty, unique, and sorted")
        return tuple(_portable_path(path) for path in value)


class VecLineageEdge(VecResearchModel):
    upstream: CapabilityId
    downstream: CapabilityId
    relationship: str = Field(min_length=3, max_length=200)
    consumed_in_selected_result: bool


class VecSourceBinding(VecResearchModel):
    vec_env_commit: Literal["068b4ea33e640f206ce6a7d04f3d6fae2ac831f4"] = (
        "068b4ea33e640f206ce6a7d04f3d6fae2ac831f4"
    )
    tos_data_commit: Literal["f6c67acbed3360dba3a0d5c8d1fd557caa99ecff"] = (
        "f6c67acbed3360dba3a0d5c8d1fd557caa99ecff"
    )
    audit_outcome: Literal["accepted_with_scoped_blockers"] = "accepted_with_scoped_blockers"
    source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_repositories_modified: Literal[False] = False


class VecObservedOutputReference(VecResearchModel):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0)
    embedded: Literal[False] = False

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _portable_path(value)


class VecEnvironmentBinding(VecResearchModel):
    engine_version: Literal["v2_post_nrsus_fix"] = "v2_post_nrsus_fix"
    python: str
    numpy: str
    jax: str
    jaxlib: str
    jax_backend: str
    jax_device_count: int = Field(ge=1)
    platform: str
    machine: str
    processor: str
    environment_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class VecReproductionBinding(VecResearchModel):
    case_id: Literal["ukfleettrain-mappo_we_uk2030_fs0"] = "ukfleettrain-mappo_we_uk2030_fs0"
    selected_seed_label: Literal["protocol_seed_not_best_of_seeds"] = (
        "protocol_seed_not_best_of_seeds"
    )
    grade: Literal["numerically_equivalent"] = "numerically_equivalent"
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    runner_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    acceptance_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reproduction_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_check_count: int = Field(ge=1)
    within_tolerance_check_count: int = Field(ge=1)
    mismatch_count: Literal[0] = 0
    outputs: tuple[VecObservedOutputReference, ...]
    environment: VecEnvironmentBinding
    raw_inputs_modified: Literal[False] = False
    external_repositories_modified: Literal[False] = False

    @model_validator(mode="after")
    def validate_outputs(self) -> Self:
        expected = ("execution_receipt.json", "per-step.npz", "per-task.npz", "run.json")
        if tuple(item.path for item in self.outputs) != expected:
            raise ValueError("reproduction outputs must cover the exact accepted output set")
        return self


class VecDiagnosticReadiness(VecResearchModel):
    rule_id: Literal["R1", "R2", "R6", "R7"]
    status: Literal["blocked", "conditional"]
    threshold_evaluated: Literal[False] = False
    finding_emitted: Literal[False] = False
    missing_evidence: tuple[str, ...]

    @field_validator("missing_evidence")
    @classmethod
    def validate_missing_evidence(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or len(value) != len(set(value)):
            raise ValueError("diagnostic readiness requires unique missing-evidence reasons")
        return value


class VecScientificBinding(VecResearchModel):
    selected_run_label: Literal["fcd_s102_uk2030_we_fs0"] = "fcd_s102_uk2030_we_fs0"
    selection_label: Literal["_s102_best_of_seeds"] = "_s102_best_of_seeds"
    scientific_admission_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_join_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    trip_join_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    available_metric_count: Literal[18] = 18
    unavailable_metric_count: Literal[8] = 8
    diagnostics: tuple[VecDiagnosticReadiness, ...]
    thresholds_calibrated_on_evaluation: Literal[False] = False
    diagnostic_findings_emitted: Literal[False] = False
    causal_claims_made: Literal[False] = False

    @model_validator(mode="after")
    def validate_diagnostics(self) -> Self:
        if [item.rule_id for item in self.diagnostics] != ["R1", "R2", "R6", "R7"]:
            raise ValueError("diagnostic readiness must cover R1, R2, R6, and R7 in order")
        if [item.status for item in self.diagnostics] != [
            "blocked",
            "blocked",
            "conditional",
            "blocked",
        ]:
            raise ValueError("diagnostic readiness states do not match VEC-09")
        return self


class VecPublicationBinding(VecResearchModel):
    pack_version: Literal["vec-dissertation-pack-1.0"] = "vec-dissertation-pack-1.0"
    pack_manifest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    sample_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    aggregate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sample_count: Literal[3] = 3
    aggregate_metric_count: Literal[26] = 26
    permission_granted_on: Literal["2026-07-21"] = "2026-07-21"
    permission_scope: Literal["repository_and_dissertation_sanitised_samples_and_aggregates"] = (
        "repository_and_dissertation_sanitised_samples_and_aggregates"
    )
    pseudonym_mapping_retained: Literal[False] = False
    anonymity_claimed: Literal[False] = False
    public_hosting_authorized: Literal[False] = False


class VecExcludedMaterial(VecResearchModel):
    category: Literal[
        "raw_source_datasets",
        "source_vehicle_ids_and_mapping",
        "actor_checkpoints",
        "private_paths_and_machine_names",
        "third_party_sumo_assets",
        "raw_execution_outputs",
        "diagnostic_findings",
        "public_hosting_claim",
    ]
    reason: str = Field(min_length=5, max_length=500)
    embedded: Literal[False] = False


class VecEndToEndManifest(VecResearchModel):
    schema_version: Literal["1.0"] = "1.0"
    capability: Literal["VEC-12"] = "VEC-12"
    status: Literal["accepted"] = "accepted"
    artifact_version: Literal["vec-end-to-end-research-artifact-1.0"] = VEC_RESEARCH_VERSION
    artifact_id: str = Field(pattern=r"^urn:traffictwin:vec-research:[0-9a-f]{64}$")
    publication_date: Literal["2026-07-21"] = "2026-07-21"
    title: Literal["TrafficTwin audited VEC end-to-end reproducibility artifact"] = (
        "TrafficTwin audited VEC end-to-end reproducibility artifact"
    )
    source: VecSourceBinding
    reproduction: VecReproductionBinding
    scientific: VecScientificBinding
    publication: VecPublicationBinding
    capabilities: tuple[VecCapabilityEvidence, ...]
    lineage: tuple[VecLineageEdge, ...]
    inventory: tuple[VecResearchInventoryEntry, ...]
    exclusions: tuple[VecExcludedMaterial, ...]
    limitations: tuple[str, ...]
    project_licence_selected: Literal[False] = False
    permission_is_formal_licence: Literal[False] = False
    offline_verifiable: Literal[True] = True
    raw_external_bytes_embedded: Literal[False] = False

    @model_validator(mode="after")
    def validate_complete_reconciliation(self) -> Self:
        expected_capabilities = (
            ("VEC-01", "direct_evidence", ("evidence/vec_source_snapshot_audit.json",)),
            (
                "VEC-02",
                "direct_evidence",
                ("contracts/tos_source_contract_v2.json", "publication/manifest.json"),
            ),
            (
                "VEC-03",
                "direct_evidence",
                (
                    "contracts/vec_identity_contract.json",
                    "evidence/vec_identity_verification.json",
                ),
            ),
            (
                "VEC-04",
                "direct_evidence",
                (
                    "contracts/vec_task_join_contract.json",
                    "evidence/vec_task_join_verification.json",
                ),
            ),
            (
                "VEC-05",
                "direct_evidence",
                (
                    "contracts/vec_trip_join_contract.json",
                    "evidence/vec_trip_join_verification.json",
                ),
            ),
            (
                "VEC-06",
                "accepted_alternative_input_path_not_used",
                ("contracts/vec_fcd_preprocessing_contract.json",),
            ),
            (
                "VEC-07",
                "separate_execution_evidence",
                (
                    "contracts/vec_runner_contract.json",
                    "evidence/vec_reproduction_report.json",
                ),
            ),
            (
                "VEC-08",
                "separate_execution_evidence",
                (
                    "contracts/vec_reproduction_contract.json",
                    "evidence/vec_reproduction_report.json",
                ),
            ),
            (
                "VEC-09",
                "direct_evidence",
                (
                    "contracts/vec_scientific_admission_contract.json",
                    "evidence/vec_scientific_admission_report.json",
                ),
            ),
            (
                "VEC-10",
                "thin_interface",
                (
                    "contracts/vec_interface_contract.json",
                    "evidence/vec_interface_verification.json",
                ),
            ),
            (
                "VEC-11",
                "permission_bounded_output",
                (
                    "contracts/vec_dissertation_pack_contract.json",
                    "publication/aggregate_metrics_s102.csv",
                    "publication/manifest.json",
                    "publication/sanitised_matched_sample_s102.csv",
                ),
            ),
        )
        observed_capabilities = tuple(
            (
                item.capability,
                item.relationship_to_published_result,
                item.evidence_paths,
            )
            for item in self.capabilities
        )
        if observed_capabilities != expected_capabilities:
            raise ValueError("capability evidence must exactly bind VEC-01 through VEC-11")
        inventory_paths = [item.path for item in self.inventory]
        if inventory_paths != sorted(set(inventory_paths)):
            raise ValueError("inventory paths must be unique and sorted")
        if tuple(inventory_paths) != VEC_RESEARCH_PAYLOAD_PATHS:
            raise ValueError("inventory must exactly cover the VEC-12 payload contract")
        available = set(inventory_paths)
        if any(path not in available for item in self.capabilities for path in item.evidence_paths):
            raise ValueError("capability evidence references an absent inventory path")
        expected_lineage = (
            ("VEC-01", "VEC-02", "audited source defines the observed contract", True),
            ("VEC-02", "VEC-03", "trace and occupancy contract bounds identity", True),
            ("VEC-02", "VEC-04", "per-step and per-task contract bounds task joins", True),
            ("VEC-03", "VEC-04", "occupancy identity binds task rows", True),
            ("VEC-03", "VEC-05", "occupancy identity binds complete trips", True),
            ("VEC-04", "VEC-09", "accepted task evidence supplies admitted metrics", True),
            ("VEC-05", "VEC-09", "accepted trip evidence supplies duration metrics", True),
            ("VEC-06", "VEC-07", "accepted alternative preprocessing input path", False),
            ("VEC-07", "VEC-08", "execution receipt binds the reproduction run", True),
            ("VEC-08", "VEC-09", "separate pinned engine reproduction prerequisite", True),
            ("VEC-09", "VEC-10", "thin interface renders accepted science", True),
            ("VEC-04", "VEC-11", "task evidence supplies the sanitised sample", True),
            ("VEC-05", "VEC-11", "trip evidence supplies the sanitised sample", True),
            ("VEC-09", "VEC-11", "admitted metric states supply aggregates", True),
            ("VEC-10", "VEC-12", "interface verification is reconciled", True),
            ("VEC-11", "VEC-12", "permission-bounded output is embedded", True),
        )
        observed_lineage = tuple(
            (
                item.upstream,
                item.downstream,
                item.relationship,
                item.consumed_in_selected_result,
            )
            for item in self.lineage
        )
        if observed_lineage != expected_lineage:
            raise ValueError("lineage must exactly cover the accepted VEC dependency graph")
        expected_exclusions = {
            "raw_source_datasets",
            "source_vehicle_ids_and_mapping",
            "actor_checkpoints",
            "private_paths_and_machine_names",
            "third_party_sumo_assets",
            "raw_execution_outputs",
            "diagnostic_findings",
            "public_hosting_claim",
        }
        if {item.category for item in self.exclusions} != expected_exclusions:
            raise ValueError("the complete mandatory excluded inventory is required")
        if self.limitations != VEC_RESEARCH_LIMITATIONS:
            raise ValueError("the complete mandatory VEC-12 limitations are required")
        expected_id = vec_research_artifact_id(
            self.model_dump(mode="json", exclude={"artifact_id"})
        )
        if self.artifact_id != expected_id:
            raise ValueError("artifact_id does not match the reconciled manifest content")
        return self


class VecEndToEndContract(VecResearchModel):
    schema_version: Literal["1.0"] = "1.0"
    capability: Literal["VEC-12"] = "VEC-12"
    status: Literal["implemented"] = "implemented"
    artifact_version: Literal["vec-end-to-end-research-artifact-1.0"] = VEC_RESEARCH_VERSION
    permitted_members: tuple[str, ...] = VEC_RESEARCH_ALL_PATHS
    fixed_zip_timestamp: tuple[int, int, int, int, int, int] = (1980, 1, 1, 0, 0, 0)
    maximum_member_count: Literal[32] = 32
    maximum_member_bytes: Literal[1000000] = 1_000_000
    maximum_total_bytes: Literal[2000000] = 2_000_000
    required_bindings: tuple[str, ...] = (
        "VEC-01 source snapshots and VEC-02 contract",
        "VEC-07 request and execution receipt through VEC-08",
        "validated output hashes and numerical reproduction grade",
        "VEC-03/VEC-04/VEC-05 identity, task, and trip joins",
        "VEC-09 metrics and diagnostic readiness without findings",
        "VEC-10 thin interface evidence",
        "VEC-11 permission manifest, sample, and aggregates",
        "environment, lineage, limitations, citations, and exclusions",
    )
    checksum_policy: str = (
        "checksums.sha256 covers every member except itself; the archive receipt separately "
        "fingerprints the complete ZIP bytes."
    )
    publication_policy: str = (
        "Embed only audit/software metadata, the VEC-11 sanitised sample, and aggregates; carry "
        "no raw source/execution bytes, identity mapping, checkpoint, or public-hosting claim."
    )


class VecEndToEndReceipt(VecResearchModel):
    schema_version: Literal["1.0"] = "1.0"
    capability: Literal["VEC-12"] = "VEC-12"
    status: Literal["accepted"] = "accepted"
    archive_name: Literal["vec_end_to_end_research_artifact.zip"] = (
        "vec_end_to_end_research_artifact.zip"
    )
    archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    archive_size_bytes: int = Field(gt=0, le=2_000_000)
    artifact_id: str = Field(pattern=r"^urn:traffictwin:vec-research:[0-9a-f]{64}$")
    manifest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    member_count: int = Field(gt=0, le=32)
    deterministic_zip: Literal[True] = True
    offline_verified_before_publication: Literal[True] = True
    external_repositories_modified: Literal[False] = False


class VecEndToEndVerification(VecResearchModel):
    valid: bool
    archive_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    artifact_id: str | None = None
    manifest_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    member_count: int = Field(default=0, ge=0, le=32)
    checksum_count: int = Field(default=0, ge=0, le=32)
    errors: tuple[str, ...] = ()


def vec_research_artifact_id(manifest_without_id: object) -> str:
    digest = _sha256(_canonical_json(manifest_without_id).encode())
    return f"urn:traffictwin:vec-research:{digest}"


def vec_end_to_end_contract() -> VecEndToEndContract:
    return VecEndToEndContract()

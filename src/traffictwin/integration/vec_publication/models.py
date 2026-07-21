"""Strict models for the permission-bounded VEC dissertation pack (VEC-11)."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.domain.enums import Decision, TaskClass
from traffictwin.integration.tos.publication import (
    PublicationArtifactKind,
    TosPublicationManifest,
)
from traffictwin.integration.vec_task_join import VecTargetAvailability

VEC_DISSERTATION_PACK_VERSION: Literal["vec-dissertation-pack-1.0"] = "vec-dissertation-pack-1.0"
VEC_DISSERTATION_SELECTION_LABEL: Literal["_s102_best_of_seeds"] = "_s102_best_of_seeds"
VEC_DISSERTATION_RUN_LABEL: Literal["fcd_s102_uk2030_we_fs0"] = "fcd_s102_uk2030_we_fs0"
VEC_DISSERTATION_SAMPLE_PATH = "sanitised_matched_sample_s102.csv"
VEC_DISSERTATION_AGGREGATE_PATH = "aggregate_metrics_s102.csv"
VEC_DISSERTATION_MANIFEST_PATH = "manifest.json"
VEC_DISSERTATION_SAMPLE_COUNT = 3


class VecPublicationModel(BaseModel):
    """Strict, immutable base with deterministic canonical fingerprints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def canonical_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


class VecSanitisedMatchedSample(VecPublicationModel):
    """One rounded, pseudonymised task/trip row with no source identifier or clock."""

    sample_id: str = Field(pattern=r"^sample-[0-9]{3}$")
    scenario: Literal["we"] = "we"
    selection_label: Literal["_s102_best_of_seeds"] = VEC_DISSERTATION_SELECTION_LABEL
    task_class: TaskClass
    deadline_met: bool
    latency_ms_rounded_10: int = Field(ge=0)
    slot_tier: int = Field(ge=0, le=2)
    slot_is_ev: bool
    action: Decision
    target_availability: VecTargetAvailability
    trip_duration_s_rounded_10: int = Field(ge=0)
    trip_route_length_m_rounded_100: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_semantics(self) -> Self:
        if self.task_class is TaskClass.UNKNOWN or self.action is Decision.UNKNOWN:
            raise ValueError("published VEC samples cannot contain unknown audited codes")
        if self.latency_ms_rounded_10 % 10:
            raise ValueError("latency must be rounded to a 10 ms increment")
        if self.trip_duration_s_rounded_10 % 10:
            raise ValueError("trip duration must be rounded to a 10 s increment")
        if self.trip_route_length_m_rounded_100 % 100:
            raise ValueError("route length must be rounded to a 100 m increment")
        expected = (
            VecTargetAvailability.NOT_APPLICABLE_LOCAL
            if self.action is Decision.LOCAL
            else self.target_availability
        )
        if self.action is Decision.LOCAL and self.target_availability is not expected:
            raise ValueError("local actions must use not_applicable_local target availability")
        if self.action is not Decision.LOCAL and self.target_availability is (
            VecTargetAvailability.NOT_APPLICABLE_LOCAL
        ):
            raise ValueError("offload actions cannot use not_applicable_local target availability")
        numeric = (
            self.latency_ms_rounded_10,
            self.trip_duration_s_rounded_10,
            self.trip_route_length_m_rounded_100,
        )
        if not all(math.isfinite(value) for value in numeric):
            raise ValueError("published numeric values must be finite")
        return self


class VecDissertationPackManifest(VecPublicationModel):
    """Machine-verifiable manifest for the smallest authorised VEC publication pack."""

    schema_version: Literal["1.0"] = "1.0"
    capability: Literal["VEC-11"] = "VEC-11"
    status: Literal["accepted"] = "accepted"
    pack_version: Literal["vec-dissertation-pack-1.0"] = VEC_DISSERTATION_PACK_VERSION
    vec_env_commit: Literal["068b4ea33e640f206ce6a7d04f3d6fae2ac831f4"] = (
        "068b4ea33e640f206ce6a7d04f3d6fae2ac831f4"
    )
    tos_data_commit: Literal["f6c67acbed3360dba3a0d5c8d1fd557caa99ecff"] = (
        "f6c67acbed3360dba3a0d5c8d1fd557caa99ecff"
    )
    engine_version: Literal["v2_post_nrsus_fix"] = "v2_post_nrsus_fix"
    selected_run_label: Literal["fcd_s102_uk2030_we_fs0"] = VEC_DISSERTATION_RUN_LABEL
    selection_label: Literal["_s102_best_of_seeds"] = VEC_DISSERTATION_SELECTION_LABEL
    scientific_admission_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_join_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    trip_join_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    sample_count: Literal[3] = 3
    aggregate_metric_count: int = Field(ge=1)
    available_metric_count: int = Field(ge=1)
    unavailable_metric_count: int = Field(ge=1)
    identifier_treatment: Literal["sequential_pseudonyms_no_mapping_retained"] = (
        "sequential_pseudonyms_no_mapping_retained"
    )
    value_minimisation: tuple[str, ...] = (
        "source vehicle IDs, slots, task indices, trace times, full-day times, and targets removed",
        "latency rounded to 10 ms",
        "trip duration rounded to 10 s",
        "route length rounded to 100 m",
    )
    pseudonym_mapping_retained: Literal[False] = False
    anonymity_claimed: Literal[False] = False
    public_hosting_authorized: Literal[False] = False
    publication_policy: TosPublicationManifest

    @model_validator(mode="after")
    def validate_pack(self) -> Self:
        if self.available_metric_count + self.unavailable_metric_count != (
            self.aggregate_metric_count
        ):
            raise ValueError("available and unavailable metrics must reconcile to the aggregate")
        if self.publication_policy.engine_version != self.engine_version:
            raise ValueError("publication policy and pack engine versions must match")
        included = {item.relative_path: item for item in self.publication_policy.included}
        if set(included) != {
            VEC_DISSERTATION_SAMPLE_PATH,
            VEC_DISSERTATION_AGGREGATE_PATH,
        }:
            raise ValueError("pack must contain exactly the sanitised sample and aggregate CSV")
        if included[VEC_DISSERTATION_SAMPLE_PATH].kind is not (
            PublicationArtifactKind.SANITISED_SAMPLE
        ):
            raise ValueError("sample CSV must be declared as a sanitised sample")
        if included[VEC_DISSERTATION_AGGREGATE_PATH].kind is not (
            PublicationArtifactKind.AGGREGATE
        ):
            raise ValueError("aggregate CSV must be declared as an aggregate")
        if not all(item.uses_selected_seed for item in included.values()):
            raise ValueError("every published file must disclose the selected _s102 evidence")
        return self


class VecDissertationPackContract(VecPublicationModel):
    """Frozen method and safety boundary for VEC-11."""

    schema_version: Literal["1.0"] = "1.0"
    capability: Literal["VEC-11"] = "VEC-11"
    status: Literal["implemented"] = "implemented"
    pack_version: Literal["vec-dissertation-pack-1.0"] = VEC_DISSERTATION_PACK_VERSION
    permitted_files: tuple[str, str, str] = (
        VEC_DISSERTATION_AGGREGATE_PATH,
        VEC_DISSERTATION_MANIFEST_PATH,
        VEC_DISSERTATION_SAMPLE_PATH,
    )
    sample_rows: Literal[3] = 3
    permission_scope: tuple[str, ...] = ("sanitised samples", "aggregate outputs")
    mandatory_disclosures: tuple[str, ...] = (
        "both source repositories and reviewed commits",
        "engine v2_post_nrsus_fix",
        "_s102 best-of-seeds selection",
        "pseudonymisation is not anonymity",
        "owner permission is not a formal licence",
    )
    excluded_material: tuple[str, ...] = (
        "raw datasets and source identifiers",
        "complete repositories",
        "actor checkpoints",
        "private paths and machine information",
        "third-party SUMO assets",
    )
    publication_rule: str = (
        "Create a new directory atomically; refuse existing destinations, extra files, "
        "hash mismatches, raw identifiers, local paths, or missing disclosures."
    )


def vec_dissertation_pack_contract() -> VecDissertationPackContract:
    """Return the frozen VEC-11 publication contract."""

    return VecDissertationPackContract()

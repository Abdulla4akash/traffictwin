"""MAN-06 candidate: fail-closed bridge to accepted Randy/VEC evidence.

The bridge consumes only the already-verified VEC-11 dissertation pack. It
does not inspect Randy's repositories, import raw traces, expose identities,
perform network access, or turn simulation evidence into live/geographic
Manchester observations.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal

from pydantic import Field, JsonValue, field_validator, model_validator

from traffictwin.integration.manchester.models import ManchesterSnapshotModel
from traffictwin.integration.vec_publication.models import (
    VEC_DISSERTATION_AGGREGATE_PATH,
    VEC_DISSERTATION_MANIFEST_PATH,
    VEC_DISSERTATION_SAMPLE_PATH,
    VecDissertationPackManifest,
    VecSanitisedMatchedSample,
)
from traffictwin.integration.vec_publication.service import (
    AGGREGATE_COLUMNS,
    SAMPLE_COLUMNS,
    verify_vec_dissertation_pack,
)

RANDY_BRIDGE_SCHEMA_VERSION = "1.0"
RANDY_BRIDGE_METHOD_VERSION = "manchester-randy-bridge-1.0"
RANDY_BRIDGE_CAPABILITY_ID = "MAN-06"
MAX_BRIDGE_MEMBER_BYTES = 50_000_000

_EXPECTED_COMMITS = {
    "vec_env": "068b4ea33e640f206ce6a7d04f3d6fae2ac831f4",
    "tos-data": "f6c67acbed3360dba3a0d5c8d1fd557caa99ecff",
}
_PRIVATE_TEXT_MARKERS = ("/Users/", "/home/", "file://", "\\")


class RandyBridgeError(ValueError):
    """Raised when verified VEC-11 evidence changes while being bridged."""


class RandyBridgeModel(ManchesterSnapshotModel):
    """Strict frozen base for MAN-06 candidate artifacts."""


class RandyBridgeCitation(RandyBridgeModel):
    """One exact repository citation preserved from the VEC-11 manifest."""

    repository: Literal["vec_env", "tos-data"]
    reviewed_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    citation_text: str = Field(min_length=10, max_length=2_000)
    url: str = Field(pattern=r"^https://gitlab\.cs\.man\.ac\.uk/\S+$", max_length=500)

    @field_validator("citation_text", "url")
    @classmethod
    def validate_safe_text(cls, value: str) -> str:
        if any(marker in value for marker in _PRIVATE_TEXT_MARKERS):
            raise ValueError("citation text carries a private path")
        return value

    @model_validator(mode="after")
    def validate_binding(self) -> RandyBridgeCitation:
        if self.reviewed_commit != _EXPECTED_COMMITS[self.repository]:
            raise ValueError("citation is not bound to the accepted reviewed commit")
        if self.reviewed_commit[:12] not in self.citation_text:
            raise ValueError("citation does not disclose the reviewed commit")
        return self


class RandyBridgeMember(RandyBridgeModel):
    """Hash and byte identity of one accepted VEC-11 pack member."""

    relative_path: Literal[
        "aggregate_metrics_s102.csv",
        "manifest.json",
        "sanitised_matched_sample_s102.csv",
    ]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0, le=MAX_BRIDGE_MEMBER_BYTES)


class RandyAggregateMetric(RandyBridgeModel):
    """One VEC-09 metric state carried through the permission-safe pack."""

    metric_key: str = Field(pattern=r"^[a-z0-9][a-z0-9._]{1,127}$")
    status: Literal["available", "unavailable"]
    value: JsonValue
    unit: str = Field(min_length=1, max_length=100)
    scope: str = Field(min_length=1, max_length=100)
    missing_evidence: tuple[str, ...] = ()

    @field_validator("unit", "scope")
    @classmethod
    def validate_short_text(cls, value: str) -> str:
        if value.strip() != value or any(marker in value for marker in _PRIVATE_TEXT_MARKERS):
            raise ValueError("metric text must be trimmed and portable")
        return value

    @field_validator("missing_evidence")
    @classmethod
    def validate_missing_evidence(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        for value in values:
            if (
                not value
                or value.strip() != value
                or len(value) > 500
                or any(marker in value for marker in _PRIVATE_TEXT_MARKERS)
            ):
                raise ValueError("missing-evidence text must be bounded and portable")
        return values

    @model_validator(mode="after")
    def validate_state(self) -> RandyAggregateMetric:
        if self.status == "available" and (self.value is None or self.missing_evidence):
            raise ValueError("available metric needs a value and no missing evidence")
        if self.status == "unavailable" and (self.value is not None or not self.missing_evidence):
            raise ValueError("unavailable metric needs null value and missing evidence")
        _reject_non_finite(self.value)
        return self


class RandyManchesterBridgeReport(RandyBridgeModel):
    """A permission- and claim-bounded view of the accepted VEC-11 pack."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-06"] = "MAN-06"
    method_version: Literal["manchester-randy-bridge-1.0"] = "manchester-randy-bridge-1.0"
    status: Literal["candidate"] = "candidate"
    source_capability: Literal["VEC-11"] = "VEC-11"
    source_pack_status: Literal["accepted"] = "accepted"
    source_pack_version: Literal["vec-dissertation-pack-1.0"] = "vec-dissertation-pack-1.0"
    source_pack_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_pack_manifest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    members: tuple[RandyBridgeMember, ...]
    citations: tuple[RandyBridgeCitation, ...]
    engine_version: Literal["v2_post_nrsus_fix"] = "v2_post_nrsus_fix"
    selected_run_label: Literal["fcd_s102_uk2030_we_fs0"] = "fcd_s102_uk2030_we_fs0"
    selection_label: Literal["_s102_best_of_seeds"] = "_s102_best_of_seeds"
    scientific_admission_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_join_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    trip_join_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    samples: tuple[VecSanitisedMatchedSample, ...]
    metrics: tuple[RandyAggregateMetric, ...]
    available_metric_count: int = Field(ge=1)
    unavailable_metric_count: int = Field(ge=1)
    evidence_kind: Literal["randy_tos_sanitised_case_study"] = "randy_tos_sanitised_case_study"
    temporal_semantics: Literal["simulation_clock_removed_by_sanitisation"] = (
        "simulation_clock_removed_by_sanitisation"
    )
    display_mode: Literal["non_geographic_case_study"] = "non_geographic_case_study"
    non_geographic_replay_available: Literal[True] = True
    geographic_map_layer_available: Literal[False] = False
    geographic_unavailable_reason: Literal["no_evidenced_coordinate_projection"] = (
        "no_evidenced_coordinate_projection"
    )
    canonical_manchester_projection_available: Literal[False] = False
    freshness_state_available: Literal[False] = False
    live_data: Literal[False] = False
    general_manchester_telemetry: Literal[False] = False
    public_hosting_authorized: Literal[False] = False
    permission_is_formal_licence: Literal[False] = False
    permission_scope: Literal["repository_and_dissertation_sanitised_samples_and_aggregates"] = (
        "repository_and_dissertation_sanitised_samples_and_aggregates"
    )
    pseudonymisation_is_anonymity: Literal[False] = False
    raw_source_identity_available: Literal[False] = False
    physical_completion_available: Literal[False] = False
    confirmed_transfer_target_available: Literal[False] = False
    per_task_energy_available: Literal[False] = False
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def validate_report(self) -> RandyManchesterBridgeReport:
        if tuple(member.relative_path for member in self.members) != tuple(
            sorted(member.relative_path for member in self.members)
        ):
            raise ValueError("member inventory must be sorted")
        if len(self.members) != 3 or len({member.relative_path for member in self.members}) != 3:
            raise ValueError("bridge must bind exactly three VEC-11 members")
        if tuple(citation.repository for citation in self.citations) != ("tos-data", "vec_env"):
            raise ValueError("bridge must cite both reviewed repositories in stable order")
        if len(self.samples) != 3:
            raise ValueError("bridge must retain the exact three-row sanitised sample")
        if any(sample.selection_label != self.selection_label for sample in self.samples):
            raise ValueError("every sample must disclose the _s102 selection")
        if tuple(metric.metric_key for metric in self.metrics) != tuple(
            sorted(metric.metric_key for metric in self.metrics)
        ):
            raise ValueError("aggregate metrics must be sorted")
        available = sum(metric.status == "available" for metric in self.metrics)
        unavailable = sum(metric.status == "unavailable" for metric in self.metrics)
        if (available, unavailable) != (
            self.available_metric_count,
            self.unavailable_metric_count,
        ):
            raise ValueError("metric status counts must reconcile")
        required_limitations = {
            "Pseudonymisation reduces direct identification but is not anonymity.",
            "Deadline success is not eventual physical task completion.",
            "Eligible targets are not transfer confirmation or execution targets.",
            (
                "Owner permission is not a formal software or data licence; "
                "public hosting is not authorised."
            ),
        }
        if not required_limitations.issubset(self.limitations):
            raise ValueError("mandatory VEC-11 limitations are absent")
        return self


def load_randy_manchester_bridge(pack_path: Path) -> RandyManchesterBridgeReport:
    """Verify and project one accepted VEC-11 directory without leaking its path."""

    manifest = verify_vec_dissertation_pack(pack_path)
    payloads = _read_verified_payloads(pack_path, manifest)
    samples = _parse_samples(payloads[VEC_DISSERTATION_SAMPLE_PATH])
    metrics = _parse_metrics(payloads[VEC_DISSERTATION_AGGREGATE_PATH])
    citations = tuple(
        sorted(
            (
                RandyBridgeCitation(
                    repository=citation.repository.value,
                    reviewed_commit=citation.reviewed_commit,
                    citation_text=citation.citation_text,
                    url=citation.url or "",
                )
                for citation in manifest.publication_policy.citations
            ),
            key=lambda citation: citation.repository,
        )
    )
    members = tuple(
        RandyBridgeMember(
            relative_path=path,  # type: ignore[arg-type]
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
        )
        for path, payload in sorted(payloads.items())
    )
    return RandyManchesterBridgeReport(
        source_pack_manifest_sha256=hashlib.sha256(
            payloads[VEC_DISSERTATION_MANIFEST_PATH]
        ).hexdigest(),
        source_pack_manifest_fingerprint=manifest.fingerprint(),
        members=members,
        citations=citations,
        scientific_admission_fingerprint=manifest.scientific_admission_fingerprint,
        task_join_report_fingerprint=manifest.task_join_report_fingerprint,
        trip_join_report_fingerprint=manifest.trip_join_report_fingerprint,
        samples=samples,
        metrics=metrics,
        available_metric_count=manifest.available_metric_count,
        unavailable_metric_count=manifest.unavailable_metric_count,
        limitations=tuple(manifest.publication_policy.limitations),
    )


def _read_verified_payloads(
    pack_path: Path,
    manifest: VecDissertationPackManifest,
) -> dict[str, bytes]:
    expected = {
        VEC_DISSERTATION_SAMPLE_PATH,
        VEC_DISSERTATION_AGGREGATE_PATH,
        VEC_DISSERTATION_MANIFEST_PATH,
    }
    payloads = {name: (pack_path / name).read_bytes() for name in expected}
    included = {
        artifact.relative_path: artifact for artifact in manifest.publication_policy.included
    }
    for name in (VEC_DISSERTATION_SAMPLE_PATH, VEC_DISSERTATION_AGGREGATE_PATH):
        payload = payloads[name]
        artifact = included[name]
        if len(payload) != artifact.size_bytes or hashlib.sha256(payload).hexdigest() != (
            artifact.sha256
        ):
            raise RandyBridgeError("VEC-11 pack changed after verification")
    manifest_again = VecDissertationPackManifest.model_validate_json(
        payloads[VEC_DISSERTATION_MANIFEST_PATH]
    )
    if manifest_again != manifest:
        raise RandyBridgeError("VEC-11 manifest changed after verification")
    return payloads


def _parse_samples(payload: bytes) -> tuple[VecSanitisedMatchedSample, ...]:
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8"), newline=""))
    if tuple(reader.fieldnames or ()) != SAMPLE_COLUMNS:
        raise RandyBridgeError("VEC-11 sample columns changed")
    return tuple(VecSanitisedMatchedSample.model_validate(row) for row in reader)


def _parse_metrics(payload: bytes) -> tuple[RandyAggregateMetric, ...]:
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8"), newline=""))
    if tuple(reader.fieldnames or ()) != AGGREGATE_COLUMNS:
        raise RandyBridgeError("VEC-11 aggregate columns changed")
    rows: list[RandyAggregateMetric] = []
    for row in reader:
        value = _safe_json(row["value_json"])
        missing = _safe_json(row["missing_evidence_json"])
        if not isinstance(missing, list) or not all(isinstance(item, str) for item in missing):
            raise RandyBridgeError("VEC-11 missing-evidence value is not a string list")
        rows.append(
            RandyAggregateMetric.model_validate(
                {
                    "metric_key": row["metric_key"],
                    "status": row["status"],
                    "value": value,
                    "unit": row["unit"],
                    "scope": row["scope"],
                    "missing_evidence": tuple(missing),
                }
            )
        )
    return tuple(rows)


def _safe_json(value: str) -> JsonValue:
    try:
        parsed: JsonValue = json.loads(
            value,
            parse_constant=lambda token: _reject_json_constant(token),
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise RandyBridgeError("VEC-11 aggregate contains invalid JSON") from exc
    _reject_non_finite(parsed)
    return parsed


def _reject_json_constant(token: str) -> JsonValue:
    raise ValueError(f"non-finite JSON constant is forbidden: {token}")


def _reject_non_finite(value: JsonValue) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("aggregate metric value must be finite")
    if isinstance(value, Mapping):
        for item in value.values():
            _reject_non_finite(item)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            _reject_non_finite(item)

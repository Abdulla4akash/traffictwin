"""Build and verify the deterministic permission-bounded VEC-12 research artifact."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast

from traffictwin.integration.tos.contract_v2 import (
    TOS_DATA_AUDITED_COMMIT,
    VEC_ENV_AUDITED_COMMIT,
    tos_source_contract_v2,
)
from traffictwin.integration.vec_identity import (
    VecIdentityCoverageReport,
    vec_identity_contract,
)
from traffictwin.integration.vec_interface import (
    VecArtifactInspection,
    VecInterfaceSnapshot,
    vec_interface_contract,
)
from traffictwin.integration.vec_preprocessing import vec_fcd_preprocessing_contract
from traffictwin.integration.vec_publication import (
    vec_dissertation_pack_contract,
    verify_vec_dissertation_pack,
)
from traffictwin.integration.vec_reproduction import (
    VecReproductionReport,
    vec_reproduction_contract,
)
from traffictwin.integration.vec_runner import vec_runner_contract
from traffictwin.integration.vec_science import (
    VecScientificAdmissionReport,
    vec_scientific_admission_contract,
)
from traffictwin.integration.vec_task_join import VecTaskJoinReport, vec_task_join_contract
from traffictwin.integration.vec_trip_join import VecTripJoinReport, vec_trip_join_contract
from traffictwin.metrics.results import MetricStatus

from .models import (
    VEC_RESEARCH_ALL_PATHS,
    VEC_RESEARCH_ARCHIVE_NAME,
    VEC_RESEARCH_CHECKSUMS_PATH,
    VEC_RESEARCH_LIMITATIONS,
    VEC_RESEARCH_MANIFEST_PATH,
    VEC_RESEARCH_PAYLOAD_PATHS,
    VecCapabilityEvidence,
    VecDiagnosticReadiness,
    VecEndToEndManifest,
    VecEndToEndReceipt,
    VecEndToEndVerification,
    VecEnvironmentBinding,
    VecExcludedMaterial,
    VecLineageEdge,
    VecObservedOutputReference,
    VecPublicationBinding,
    VecReproductionBinding,
    VecResearchInventoryEntry,
    VecScientificBinding,
    VecSourceBinding,
    vec_end_to_end_contract,
    vec_research_artifact_id,
)

MAX_MEMBER_COUNT = 32
MAX_MEMBER_BYTES = 1_000_000
MAX_TOTAL_BYTES = 2_000_000
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_LOCAL_PATH = re.compile(rb"(?:file://|/Users/|/home/|(?:^|[\"'\s])[A-Za-z]:[\\/])")

_SOURCE_FILES = {
    "tos_source_contract_v2.json": "contracts/tos_source_contract_v2.json",
    "vec_dissertation_pack_contract.json": "contracts/vec_dissertation_pack_contract.json",
    "vec_fcd_preprocessing_contract.json": "contracts/vec_fcd_preprocessing_contract.json",
    "vec_identity_contract.json": "contracts/vec_identity_contract.json",
    "vec_interface_contract.json": "contracts/vec_interface_contract.json",
    "vec_reproduction_contract.json": "contracts/vec_reproduction_contract.json",
    "vec_runner_contract.json": "contracts/vec_runner_contract.json",
    "vec_scientific_admission_contract.json": ("contracts/vec_scientific_admission_contract.json"),
    "vec_task_join_contract.json": "contracts/vec_task_join_contract.json",
    "vec_trip_join_contract.json": "contracts/vec_trip_join_contract.json",
    "vec_identity_verification.json": "evidence/vec_identity_verification.json",
    "vec_interface_verification.json": "evidence/vec_interface_verification.json",
    "vec_reproduction_report.json": "evidence/vec_reproduction_report.json",
    "vec_scientific_admission_report.json": ("evidence/vec_scientific_admission_report.json"),
    "vec_source_snapshot_audit.json": "evidence/vec_source_snapshot_audit.json",
    "vec_task_join_verification.json": "evidence/vec_task_join_verification.json",
    "vec_trip_join_verification.json": "evidence/vec_trip_join_verification.json",
}
_PUBLICATION_FILES = {
    "aggregate_metrics_s102.csv": "publication/aggregate_metrics_s102.csv",
    "manifest.json": "publication/manifest.json",
    "sanitised_matched_sample_s102.csv": "publication/sanitised_matched_sample_s102.csv",
}


class VecEndToEndResearchError(ValueError):
    """Raised when accepted evidence cannot support a safe VEC-12 artifact."""


@dataclass(frozen=True)
class BuiltVecEndToEndArtifact:
    manifest: VecEndToEndManifest
    members: dict[str, bytes]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode()


def _read_json(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VecEndToEndResearchError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise VecEndToEndResearchError(f"{label} must contain one JSON object")
    return cast(dict[str, Any], value)


def _read_source_file(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise VecEndToEndResearchError(f"required evidence is not a regular file: {path.name}")
    payload = path.read_bytes()
    if not payload or len(payload) > MAX_MEMBER_BYTES:
        raise VecEndToEndResearchError(f"required evidence is outside the size bound: {path.name}")
    if _LOCAL_PATH.search(payload):
        raise VecEndToEndResearchError(
            f"required evidence carries a private local path: {path.name}"
        )
    return payload


def _require_generated_contract(
    payload: bytes,
    expected: dict[str, Any],
    label: str,
) -> None:
    if _read_json(payload, label) != expected:
        raise VecEndToEndResearchError(f"{label} is stale or does not match the library contract")


def _validate_join_reports(
    identity_record: dict[str, Any],
    task_record: dict[str, Any],
    trip_record: dict[str, Any],
) -> tuple[VecTaskJoinReport, VecTripJoinReport]:
    if (
        identity_record.get("status") != "accepted"
        or identity_record.get("external_source_unchanged") is not True
        or identity_record.get("source_commit") != TOS_DATA_AUDITED_COMMIT
    ):
        raise VecEndToEndResearchError("VEC-03 verification is not accepted and immutable")
    identity_reports = [
        VecIdentityCoverageReport.model_validate(item)
        for item in cast(list[object], identity_record.get("reports"))
    ]
    if len(identity_reports) != 5 or any(item.status != "accepted" for item in identity_reports):
        raise VecEndToEndResearchError("VEC-03 must contain five accepted identity reports")

    if (
        task_record.get("status") != "accepted"
        or task_record.get("external_source_unchanged") is not True
        or task_record.get("source_commit") != TOS_DATA_AUDITED_COMMIT
    ):
        raise VecEndToEndResearchError("VEC-04 verification is not accepted and immutable")
    tasks = [
        VecTaskJoinReport.model_validate(item)
        for item in cast(list[object], task_record.get("reports"))
    ]
    selected_task = next(
        (item for item in tasks if item.run_label == "fcd_s102_uk2030_we_fs0"), None
    )
    if len(tasks) != 6 or selected_task is None:
        raise VecEndToEndResearchError("VEC-04 does not contain the six accepted task joins")

    if (
        trip_record.get("status") != "accepted"
        or trip_record.get("external_source_unchanged") is not True
        or trip_record.get("source_commit") != TOS_DATA_AUDITED_COMMIT
        or trip_record.get("raw_vehicle_ids_published") is not False
    ):
        raise VecEndToEndResearchError("VEC-05 verification is not accepted and sanitised")
    trips = [
        VecTripJoinReport.model_validate(item)
        for item in cast(list[object], trip_record.get("reports"))
    ]
    selected_trip = next((item for item in trips if item.scenario == "we"), None)
    if len(trips) != 5 or selected_trip is None:
        raise VecEndToEndResearchError("VEC-05 does not contain the five accepted trip joins")
    return selected_task, selected_trip


def _capabilities() -> tuple[VecCapabilityEvidence, ...]:
    return (
        VecCapabilityEvidence(
            capability="VEC-01",
            relationship_to_published_result="direct_evidence",
            evidence_paths=("evidence/vec_source_snapshot_audit.json",),
        ),
        VecCapabilityEvidence(
            capability="VEC-02",
            relationship_to_published_result="direct_evidence",
            evidence_paths=(
                "contracts/tos_source_contract_v2.json",
                "publication/manifest.json",
            ),
        ),
        VecCapabilityEvidence(
            capability="VEC-03",
            relationship_to_published_result="direct_evidence",
            evidence_paths=(
                "contracts/vec_identity_contract.json",
                "evidence/vec_identity_verification.json",
            ),
        ),
        VecCapabilityEvidence(
            capability="VEC-04",
            relationship_to_published_result="direct_evidence",
            evidence_paths=(
                "contracts/vec_task_join_contract.json",
                "evidence/vec_task_join_verification.json",
            ),
        ),
        VecCapabilityEvidence(
            capability="VEC-05",
            relationship_to_published_result="direct_evidence",
            evidence_paths=(
                "contracts/vec_trip_join_contract.json",
                "evidence/vec_trip_join_verification.json",
            ),
        ),
        VecCapabilityEvidence(
            capability="VEC-06",
            relationship_to_published_result="accepted_alternative_input_path_not_used",
            evidence_paths=("contracts/vec_fcd_preprocessing_contract.json",),
        ),
        VecCapabilityEvidence(
            capability="VEC-07",
            relationship_to_published_result="separate_execution_evidence",
            evidence_paths=(
                "contracts/vec_runner_contract.json",
                "evidence/vec_reproduction_report.json",
            ),
        ),
        VecCapabilityEvidence(
            capability="VEC-08",
            relationship_to_published_result="separate_execution_evidence",
            evidence_paths=(
                "contracts/vec_reproduction_contract.json",
                "evidence/vec_reproduction_report.json",
            ),
        ),
        VecCapabilityEvidence(
            capability="VEC-09",
            relationship_to_published_result="direct_evidence",
            evidence_paths=(
                "contracts/vec_scientific_admission_contract.json",
                "evidence/vec_scientific_admission_report.json",
            ),
        ),
        VecCapabilityEvidence(
            capability="VEC-10",
            relationship_to_published_result="thin_interface",
            evidence_paths=(
                "contracts/vec_interface_contract.json",
                "evidence/vec_interface_verification.json",
            ),
        ),
        VecCapabilityEvidence(
            capability="VEC-11",
            relationship_to_published_result="permission_bounded_output",
            evidence_paths=(
                "contracts/vec_dissertation_pack_contract.json",
                "publication/aggregate_metrics_s102.csv",
                "publication/manifest.json",
                "publication/sanitised_matched_sample_s102.csv",
            ),
        ),
    )


def _lineage() -> tuple[VecLineageEdge, ...]:
    values = (
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
    return tuple(
        VecLineageEdge(
            upstream=cast(Any, upstream),
            downstream=cast(Any, downstream),
            relationship=relationship,
            consumed_in_selected_result=consumed,
        )
        for upstream, downstream, relationship, consumed in values
    )


def _excluded() -> tuple[VecExcludedMaterial, ...]:
    reasons = {
        "raw_source_datasets": (
            "Only audit metadata, sanitised sample rows, and aggregates are embedded."
        ),
        "source_vehicle_ids_and_mapping": (
            "Sequential pseudonyms have no retained or published source mapping."
        ),
        "actor_checkpoints": (
            "Checkpoint hashes may be referenced by accepted evidence; binary bytes are excluded."
        ),
        "private_paths_and_machine_names": (
            "Portable evidence contains no local absolute path, user, or host name."
        ),
        "third_party_sumo_assets": (
            "Network, route, FCD, and other third-party SUMO bytes are excluded."
        ),
        "raw_execution_outputs": (
            "VEC-08 output hashes and sizes are bound without NPZ or JSON output bytes."
        ),
        "diagnostic_findings": (
            "VEC-09 evaluated readiness only; it calibrated no threshold and emitted no finding."
        ),
        "public_hosting_claim": (
            "Project licence and complete external publication bases remain unresolved."
        ),
    }
    return tuple(
        VecExcludedMaterial(category=cast(Any, category), reason=reason)
        for category, reason in sorted(reasons.items())
    )


def _citation_bytes() -> bytes:
    return (
        "cff-version: 1.2.0\n"
        "message: Cite TrafficTwin and both reviewed source repositories when using this "
        "artifact.\n"
        "title: TrafficTwin audited VEC end-to-end reproducibility artifact\n"
        "type: dataset\n"
        "authors:\n"
        "  - given-names: Abdulla Al Mamun\n"
        "    family-names: Akash\n"
        "version: '0.6'\n"
        "date-released: 2026-07-21\n"
        "abstract: Permission-bounded offline evidence for TrafficTwin VEC-01 through VEC-12.\n"
        "references:\n"
        "  - type: software\n"
        "    title: vec_env\n"
        "    authors:\n"
        "      - name: Randy Putra\n"
        "    repository-code: https://gitlab.cs.man.ac.uk/e62992rp/vec_env\n"
        f"    version: {VEC_ENV_AUDITED_COMMIT}\n"
        "  - type: dataset\n"
        "    title: tos-data\n"
        "    authors:\n"
        "      - name: Randy Putra\n"
        "    repository-code: https://gitlab.cs.man.ac.uk/e62992rp/tos-data\n"
        f"    version: {TOS_DATA_AUDITED_COMMIT}\n"
    ).encode()


def _readme_bytes() -> bytes:
    return (
        b"# TrafficTwin VEC end-to-end reproducibility artifact\n\n"
        b"This deterministic VEC-12 archive reconciles the accepted VEC-01 through VEC-11 "
        b"contracts and evidence. Verify it offline with:\n\n"
        b"```bash\ntraffictwin integration vec research-verify "
        b"vec_end_to_end_research_artifact.zip\n```\n\n"
        b"The VEC-08 protocol-seed reproduction is distinct from the VEC-09/VEC-11 `_s102` "
        b"best-of-seeds scientific result. The archive embeds no raw source or execution bytes, "
        b"checkpoint, source identity mapping, private path, or third-party SUMO asset. "
        b"Pseudonymisation is not anonymity. Owner permission is not a formal licence, and public "
        b"hosting remains unauthorised. See `manifest.json`, `provenance.json`, and "
        b"`limitations.json` for the machine-readable boundary.\n"
    )


def _inventory_entry(path: str, payload: bytes) -> VecResearchInventoryEntry:
    capability = "VEC-12"
    role = PurePosixPath(path).stem.replace("-", "_")
    permission_class = "audit_or_software_metadata"
    media_type = "application/json"
    if path == "CITATION.cff":
        role, media_type = "citation", "text/yaml"
    elif path == "README.md":
        role, media_type = "readme", "text/markdown"
    elif path.endswith(".csv"):
        media_type = "text/csv"
    if path.startswith("contracts/tos_"):
        capability = "VEC-02"
    elif "dissertation_pack_contract" in path or path.startswith("publication/"):
        capability = "VEC-11"
    elif "fcd_preprocessing" in path:
        capability = "VEC-06"
    elif "identity" in path:
        capability = "VEC-03"
    elif "task_join" in path:
        capability = "VEC-04"
    elif "trip_join" in path:
        capability = "VEC-05"
    elif "runner" in path:
        capability = "VEC-07"
    elif "reproduction" in path:
        capability = "VEC-08"
    elif "scientific_admission" in path:
        capability = "VEC-09"
    elif "interface" in path:
        capability = "VEC-10"
    elif "source_snapshot" in path:
        capability = "VEC-01"
    if path.endswith("sanitised_matched_sample_s102.csv"):
        permission_class = "sanitised_sample"
        role = "sanitised_matched_sample"
    elif path.endswith("aggregate_metrics_s102.csv"):
        permission_class = "aggregate"
        role = "aggregate_metrics"
    elif path == "evidence/vec_scientific_admission_report.json":
        permission_class = "aggregate"
    return VecResearchInventoryEntry(
        path=path,
        role=role,
        capability=cast(Any, capability),
        permission_class=cast(Any, permission_class),
        media_type=cast(Any, media_type),
        sha256=_sha256(payload),
        size_bytes=len(payload),
    )


def build_vec_end_to_end_artifact(generated_root: Path) -> BuiltVecEndToEndArtifact:
    """Reconcile accepted generated evidence and build all VEC-12 members in memory."""

    if generated_root.is_symlink():
        raise VecEndToEndResearchError("generated evidence root must not be a symbolic link")
    root = generated_root.resolve(strict=True)
    if not root.is_dir():
        raise VecEndToEndResearchError("generated evidence root must be a real directory")
    members: dict[str, bytes] = {}
    for source_name, archive_path in _SOURCE_FILES.items():
        members[archive_path] = _read_source_file(root / source_name)
    publication_root = root / "vec_dissertation_pack"
    if publication_root.is_symlink() or not publication_root.is_dir():
        raise VecEndToEndResearchError("VEC-11 publication evidence must be a real directory")
    publication_manifest = verify_vec_dissertation_pack(publication_root)
    for source_name, archive_path in _PUBLICATION_FILES.items():
        members[archive_path] = _read_source_file(publication_root / source_name)

    contract_checks = {
        "contracts/tos_source_contract_v2.json": tos_source_contract_v2().model_dump(mode="json"),
        "contracts/vec_dissertation_pack_contract.json": (
            vec_dissertation_pack_contract().model_dump(mode="json")
        ),
        "contracts/vec_fcd_preprocessing_contract.json": (
            vec_fcd_preprocessing_contract().model_dump(mode="json")
        ),
        "contracts/vec_identity_contract.json": vec_identity_contract().model_dump(mode="json"),
        "contracts/vec_interface_contract.json": vec_interface_contract().model_dump(mode="json"),
        "contracts/vec_reproduction_contract.json": (
            vec_reproduction_contract().model_dump(mode="json")
        ),
        "contracts/vec_runner_contract.json": vec_runner_contract().model_dump(mode="json"),
        "contracts/vec_scientific_admission_contract.json": (
            vec_scientific_admission_contract().model_dump(mode="json")
        ),
        "contracts/vec_task_join_contract.json": vec_task_join_contract().model_dump(mode="json"),
        "contracts/vec_trip_join_contract.json": vec_trip_join_contract().model_dump(mode="json"),
    }
    for path, expected in contract_checks.items():
        _require_generated_contract(members[path], expected, path)

    source_audit = _read_json(
        members["evidence/vec_source_snapshot_audit.json"], "VEC-01 source audit"
    )
    if source_audit.get("audit_outcome") != "accepted_with_scoped_blockers":
        raise VecEndToEndResearchError("VEC-01 source audit is not accepted")
    sources = cast(dict[str, Any], source_audit.get("sources"))
    if (
        sources.get("vec_env", {}).get("audited_commit") != VEC_ENV_AUDITED_COMMIT
        or sources.get("tos-data", {}).get("audited_commit") != TOS_DATA_AUDITED_COMMIT
        or sources.get("vec_env", {}).get("worktree_clean") is not True
        or sources.get("tos-data", {}).get("worktree_clean") is not True
    ):
        raise VecEndToEndResearchError("VEC-01 source bindings do not match the audited commits")

    selected_task, selected_trip = _validate_join_reports(
        _read_json(members["evidence/vec_identity_verification.json"], "VEC-03"),
        _read_json(members["evidence/vec_task_join_verification.json"], "VEC-04"),
        _read_json(members["evidence/vec_trip_join_verification.json"], "VEC-05"),
    )
    reproduction = VecReproductionReport.model_validate_json(
        members["evidence/vec_reproduction_report.json"]
    )
    if reproduction.grade.value != "numerically_equivalent" or reproduction.repeat_run is None:
        raise VecEndToEndResearchError("VEC-08 reproduction is not numerically equivalent")
    science_record = _read_json(members["evidence/vec_scientific_admission_report.json"], "VEC-09")
    if (
        science_record.get("status") != "accepted"
        or science_record.get("selection_label_preserved") != "_s102_best_of_seeds"
        or science_record.get("raw_vehicle_ids_published") is not False
        or science_record.get("external_source_unchanged") is not True
    ):
        raise VecEndToEndResearchError("VEC-09 wrapper is not accepted and permission-safe")
    science = VecScientificAdmissionReport.model_validate(science_record["admission"])
    if (
        science.reproduction_report_fingerprint != reproduction.fingerprint()
        or science.task_join_report_fingerprint != selected_task.fingerprint()
        or science.trip_join_report_fingerprint != selected_trip.fingerprint()
    ):
        raise VecEndToEndResearchError("VEC-09 does not bind the accepted VEC-04/05/08 evidence")

    interface_record = _read_json(members["evidence/vec_interface_verification.json"], "VEC-10")
    interface_snapshot = VecInterfaceSnapshot.model_validate(interface_record["snapshot"])
    interface_inspection = VecArtifactInspection.model_validate(
        interface_record["artifact_inspection"]
    )
    if (
        interface_record.get("status") != "accepted"
        or interface_record.get("contract_fingerprint") != vec_interface_contract().fingerprint()
        or interface_record.get("scientific_report_fingerprint") != science.fingerprint()
        or interface_record.get("external_source_unchanged") is not True
        or interface_record.get("private_paths_published") is not False
        or not all(item.ready_for_exact_blob_access for item in interface_snapshot.repositories)
        or interface_inspection.artifact_fingerprint != science.fingerprint()
    ):
        raise VecEndToEndResearchError("VEC-10 does not bind the accepted source and science state")
    if (
        publication_manifest.scientific_admission_fingerprint != science.fingerprint()
        or publication_manifest.task_join_report_fingerprint != selected_task.fingerprint()
        or publication_manifest.trip_join_report_fingerprint != selected_trip.fingerprint()
        or publication_manifest.public_hosting_authorized is not False
    ):
        raise VecEndToEndResearchError("VEC-11 does not bind the accepted joins and science")

    metrics = science.evidence_pack.metric_collection.results
    available = sum(item.status is MetricStatus.AVAILABLE for item in metrics)
    unavailable = sum(item.status is MetricStatus.UNAVAILABLE for item in metrics)
    diagnostics = tuple(
        VecDiagnosticReadiness(
            rule_id=cast(Any, item.rule_id),
            status=cast(Any, item.status.value),
            threshold_evaluated=item.threshold_evaluated,
            finding_emitted=item.finding_emitted,
            missing_evidence=item.missing_evidence,
        )
        for item in science.rule_readiness
    )
    runtime = reproduction.runtime
    environment = VecEnvironmentBinding(
        python=str(runtime["python"]),
        numpy=str(runtime["numpy"]),
        jax=str(runtime["jax"]),
        jaxlib=str(runtime["jaxlib"]),
        jax_backend=str(runtime["jax_backend"]),
        jax_device_count=int(runtime["jax_device_count"]),
        platform=str(runtime["platform"]),
        machine=str(runtime["machine"]),
        processor=str(runtime["processor"]),
        environment_sha256=str(runtime["environment_sha256"]),
    )
    observed_outputs = tuple(
        VecObservedOutputReference(
            path=item.path,
            sha256=item.sha256,
            size_bytes=item.size_bytes,
        )
        for item in reproduction.observed_sources
    )
    reproduction_binding = VecReproductionBinding(
        request_fingerprint=reproduction.request_fingerprint,
        runner_receipt_fingerprint=reproduction.runner_receipt_fingerprint,
        acceptance_receipt_sha256=reproduction.repeat_run.acceptance_receipt_sha256,
        reproduction_report_fingerprint=reproduction.fingerprint(),
        exact_check_count=reproduction.summary.exact,
        within_tolerance_check_count=reproduction.summary.within_tolerance,
        mismatch_count=reproduction.summary.mismatch,
        outputs=observed_outputs,
        environment=environment,
    )
    scientific_binding = VecScientificBinding(
        scientific_admission_fingerprint=science.fingerprint(),
        task_join_report_fingerprint=selected_task.fingerprint(),
        trip_join_report_fingerprint=selected_trip.fingerprint(),
        available_metric_count=available,
        unavailable_metric_count=unavailable,
        diagnostics=diagnostics,
    )
    included = {
        item.relative_path: item for item in publication_manifest.publication_policy.included
    }
    publication_binding = VecPublicationBinding(
        pack_manifest_fingerprint=publication_manifest.fingerprint(),
        sample_sha256=included["sanitised_matched_sample_s102.csv"].sha256,
        aggregate_sha256=included["aggregate_metrics_s102.csv"].sha256,
        sample_count=publication_manifest.sample_count,
        aggregate_metric_count=publication_manifest.aggregate_metric_count,
        permission_granted_on=(
            publication_manifest.publication_policy.permission.granted_on.isoformat()
        ),
        pseudonym_mapping_retained=publication_manifest.pseudonym_mapping_retained,
        anonymity_claimed=publication_manifest.anonymity_claimed,
        public_hosting_authorized=publication_manifest.public_hosting_authorized,
    )
    source_binding = VecSourceBinding(
        source_snapshot_sha256=_sha256(members["evidence/vec_source_snapshot_audit.json"])
    )
    capabilities = _capabilities()
    lineage = _lineage()
    exclusions = _excluded()

    provenance = {
        "schema_version": "1.0",
        "capability": "VEC-12",
        "source": source_binding.model_dump(mode="json"),
        "reproduction": reproduction_binding.model_dump(mode="json"),
        "scientific": scientific_binding.model_dump(mode="json"),
        "publication": publication_binding.model_dump(mode="json"),
        "capabilities": [item.model_dump(mode="json") for item in capabilities],
        "lineage": [item.model_dump(mode="json") for item in lineage],
    }
    members.update(
        {
            "CITATION.cff": _citation_bytes(),
            "README.md": _readme_bytes(),
            "limitations.json": _json_bytes(
                {
                    "schema_version": "1.0",
                    "capability": "VEC-12",
                    "limitations": VEC_RESEARCH_LIMITATIONS,
                }
            ),
            "method/vec_end_to_end_contract.json": _json_bytes(
                vec_end_to_end_contract().model_dump(mode="json")
            ),
            "provenance.json": _json_bytes(provenance),
        }
    )
    if tuple(sorted(members)) != VEC_RESEARCH_PAYLOAD_PATHS:
        raise VecEndToEndResearchError("builder payload set does not match the VEC-12 contract")
    inventory = tuple(_inventory_entry(path, members[path]) for path in sorted(members))
    identity_payload = VecEndToEndManifest.model_construct(
        artifact_id="urn:traffictwin:vec-research:" + "0" * 64,
        source=source_binding,
        reproduction=reproduction_binding,
        scientific=scientific_binding,
        publication=publication_binding,
        capabilities=capabilities,
        lineage=lineage,
        inventory=inventory,
        exclusions=exclusions,
        limitations=VEC_RESEARCH_LIMITATIONS,
    ).model_dump(mode="json", exclude={"artifact_id"})
    artifact_id = vec_research_artifact_id(identity_payload)
    manifest = VecEndToEndManifest(
        artifact_id=artifact_id,
        source=source_binding,
        reproduction=reproduction_binding,
        scientific=scientific_binding,
        publication=publication_binding,
        capabilities=capabilities,
        lineage=lineage,
        inventory=inventory,
        exclusions=exclusions,
        limitations=VEC_RESEARCH_LIMITATIONS,
    )
    members[VEC_RESEARCH_MANIFEST_PATH] = _json_bytes(manifest.model_dump(mode="json"))
    members[VEC_RESEARCH_CHECKSUMS_PATH] = _checksums_bytes(members)
    return BuiltVecEndToEndArtifact(manifest=manifest, members=members)


def _checksums_bytes(members: dict[str, bytes]) -> bytes:
    names = sorted(name for name in members if name != VEC_RESEARCH_CHECKSUMS_PATH)
    return "".join(f"{_sha256(members[name])}  {name}\n" for name in names).encode()


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    if tuple(sorted(members)) != VEC_RESEARCH_ALL_PATHS:
        raise VecEndToEndResearchError("archive member set does not match the VEC-12 contract")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_STORED, allowZip64=False) as zf:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100444 << 16
            zf.writestr(info, members[name])
    return buffer.getvalue()


def _verify_archive_bytes(payload: bytes) -> tuple[VecEndToEndManifest, int]:
    if not payload or len(payload) > MAX_TOTAL_BYTES:
        raise VecEndToEndResearchError("archive is empty or exceeds the VEC-12 size bound")
    try:
        with zipfile.ZipFile(io.BytesIO(payload), mode="r") as zf:
            infos = zf.infolist()
            names = [item.filename for item in infos]
            if len(infos) > MAX_MEMBER_COUNT or tuple(names) != VEC_RESEARCH_ALL_PATHS:
                raise VecEndToEndResearchError("archive member set/order violates the contract")
            if len(names) != len(set(names)):
                raise VecEndToEndResearchError("archive contains duplicate member names")
            total = 0
            members: dict[str, bytes] = {}
            for info in infos:
                archive_path = PurePosixPath(info.filename)
                mode = info.external_attr >> 16
                if (
                    archive_path.is_absolute()
                    or ".." in archive_path.parts
                    or info.is_dir()
                    or mode != 0o100444
                    or info.compress_type != zipfile.ZIP_STORED
                    or info.date_time != _ZIP_TIMESTAMP
                    or info.file_size <= 0
                    or info.file_size > MAX_MEMBER_BYTES
                    or info.compress_size != info.file_size
                ):
                    raise VecEndToEndResearchError(
                        f"unsafe or non-deterministic archive member: {info.filename}"
                    )
                total += info.file_size
                if total > MAX_TOTAL_BYTES:
                    raise VecEndToEndResearchError("archive members exceed the total size bound")
                members[info.filename] = zf.read(info)
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise VecEndToEndResearchError("archive is not a valid bounded ZIP") from exc

    checksums = members[VEC_RESEARCH_CHECKSUMS_PATH].decode("ascii").splitlines()
    expected_names = sorted(name for name in members if name != VEC_RESEARCH_CHECKSUMS_PATH)
    expected_lines = [f"{_sha256(members[name])}  {name}" for name in expected_names]
    if checksums != expected_lines:
        raise VecEndToEndResearchError("checksums.sha256 does not match every payload member")
    manifest = VecEndToEndManifest.model_validate_json(members[VEC_RESEARCH_MANIFEST_PATH])
    inventory = {item.path: item for item in manifest.inventory}
    for inventory_path in VEC_RESEARCH_PAYLOAD_PATHS:
        item = inventory[inventory_path]
        if item.size_bytes != len(members[inventory_path]) or item.sha256 != _sha256(
            members[inventory_path]
        ):
            raise VecEndToEndResearchError(f"manifest inventory mismatch for {inventory_path}")
    for name, content in members.items():
        if _LOCAL_PATH.search(content):
            raise VecEndToEndResearchError(f"archive member carries a private local path: {name}")
    sample = list(
        csv.DictReader(
            io.StringIO(members["publication/sanitised_matched_sample_s102.csv"].decode())
        )
    )
    if len(sample) != manifest.publication.sample_count:
        raise VecEndToEndResearchError("publication sample count does not match the manifest")
    return manifest, len(checksums)


def verify_vec_end_to_end_archive(path: Path) -> VecEndToEndVerification:
    """Verify a VEC-12 ZIP offline without extraction or external repository access."""

    try:
        if path.is_symlink() or not path.is_file():
            raise VecEndToEndResearchError("archive must be a regular file, not a symlink")
        payload = path.read_bytes()
        manifest, checksum_count = _verify_archive_bytes(payload)
        return VecEndToEndVerification(
            valid=True,
            archive_sha256=_sha256(payload),
            artifact_id=manifest.artifact_id,
            manifest_fingerprint=manifest.fingerprint(),
            member_count=len(VEC_RESEARCH_ALL_PATHS),
            checksum_count=checksum_count,
        )
    except (OSError, UnicodeDecodeError, KeyError, ValueError) as exc:
        return VecEndToEndVerification(valid=False, errors=(str(exc),))


def create_vec_end_to_end_archive(
    generated_root: Path,
    destination: Path,
) -> VecEndToEndReceipt:
    """Build, verify, and atomically publish a new VEC-12 archive."""

    destination = destination.absolute()
    if destination.name != VEC_RESEARCH_ARCHIVE_NAME:
        raise VecEndToEndResearchError(f"destination filename must be {VEC_RESEARCH_ARCHIVE_NAME}")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"destination already exists: {destination}")
    built = build_vec_end_to_end_artifact(generated_root)
    payload = _zip_bytes(built.members)
    verified_manifest, _ = _verify_archive_bytes(payload)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o444)
        os.link(temporary_name, destination)
        Path(temporary_name).unlink()
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return VecEndToEndReceipt(
        archive_sha256=_sha256(payload),
        archive_size_bytes=len(payload),
        artifact_id=verified_manifest.artifact_id,
        manifest_fingerprint=verified_manifest.fingerprint(),
        member_count=len(built.members),
    )

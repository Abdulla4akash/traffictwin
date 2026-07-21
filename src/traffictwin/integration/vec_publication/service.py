"""Derive, publish, and verify the permission-bounded VEC-11 dissertation pack."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import numpy as np

from traffictwin.domain.enums import Decision, TaskClass
from traffictwin.integration.tos.contract_v2 import (
    TOS_DATA_AUDITED_COMMIT,
    VEC_ENV_AUDITED_COMMIT,
)
from traffictwin.integration.tos.publication import (
    IncludedArtifact,
    PublicationArtifactKind,
    PublicationPermissionBasis,
    PublicationPermissionState,
    PublicationRepository,
    PublicationSourceLabels,
    RepositoryCitation,
    SanitisationDeclaration,
    TosPublicationManifest,
    default_excluded_inventory,
)
from traffictwin.integration.vec_identity import VecIdentitySnapshot
from traffictwin.integration.vec_science import VecScientificAdmissionReport
from traffictwin.integration.vec_task_join import (
    VecTargetAvailability,
    VecTaskJoinReport,
    build_task_join_report,
)
from traffictwin.integration.vec_trip_join import VecTripJoinDataset

from .models import (
    VEC_DISSERTATION_AGGREGATE_PATH,
    VEC_DISSERTATION_MANIFEST_PATH,
    VEC_DISSERTATION_RUN_LABEL,
    VEC_DISSERTATION_SAMPLE_COUNT,
    VEC_DISSERTATION_SAMPLE_PATH,
    VecDissertationPackManifest,
    VecSanitisedMatchedSample,
)

SAMPLE_COLUMNS = (
    "sample_id",
    "scenario",
    "selection_label",
    "task_class",
    "deadline_met",
    "latency_ms_rounded_10",
    "slot_tier",
    "slot_is_ev",
    "action",
    "target_availability",
    "trip_duration_s_rounded_10",
    "trip_route_length_m_rounded_100",
)
AGGREGATE_COLUMNS = (
    "metric_key",
    "status",
    "value_json",
    "unit",
    "scope",
    "missing_evidence_json",
)
_ACTIONS = (Decision.LOCAL, Decision.V2I, Decision.V2V)
_TASK_CLASSES = (TaskClass.T1, TaskClass.T2, TaskClass.T3)
_ABSOLUTE_PATH = re.compile(rb"(?:file://|/Users/|/home/|(?:^|[\"'\s])[A-Za-z]:[\\/])")


class VecDissertationPackError(ValueError):
    """Raised when source evidence or an on-disk pack violates VEC-11."""


def _round_to(value: float, quantum: int) -> int:
    scaled = Decimal(str(float(value))) / Decimal(quantum)
    return int(scaled.quantize(Decimal("1"), rounding=ROUND_HALF_UP) * quantum)


def _availability(action_code: int, rsu: int, peer: int) -> VecTargetAvailability:
    if action_code == 0:
        return VecTargetAvailability.NOT_APPLICABLE_LOCAL
    target = rsu if action_code == 1 else peer
    return (
        VecTargetAvailability.ELIGIBLE_TARGET
        if target >= 0
        else VecTargetAvailability.NO_ELIGIBLE_TARGET
    )


def derive_sanitised_matched_sample(
    trace_arrays: Mapping[str, Any],
    perstep_arrays: Mapping[str, Any],
    pertask_arrays: Mapping[str, Any],
    identity: VecIdentitySnapshot,
    task_report: VecTaskJoinReport,
    trip_dataset: VecTripJoinDataset,
    scientific_admission: VecScientificAdmissionReport,
) -> tuple[VecSanitisedMatchedSample, ...]:
    """Derive three action-diverse, rounded rows from fully accepted matched evidence."""

    rebuilt = build_task_join_report(
        trace_arrays,
        perstep_arrays,
        pertask_arrays,
        identity,
        run_label=VEC_DISSERTATION_RUN_LABEL,
    )
    if rebuilt != task_report:
        raise VecDissertationPackError("task report does not match rebuilt accepted evidence")
    if scientific_admission.run_label != VEC_DISSERTATION_RUN_LABEL:
        raise VecDissertationPackError("scientific admission is not the disclosed _s102 run")
    if scientific_admission.task_join_report_fingerprint != task_report.fingerprint():
        raise VecDissertationPackError("scientific admission does not bind the task report")
    if scientific_admission.trip_join_report_fingerprint != trip_dataset.report.fingerprint():
        raise VecDissertationPackError("scientific admission does not bind the trip report")
    if trip_dataset.report.identity_snapshot_fingerprint != identity.fingerprint():
        raise VecDissertationPackError("trip dataset does not bind the identity snapshot")

    perstep = {key: np.asarray(value) for key, value in perstep_arrays.items()}
    pertask = {key: np.asarray(value) for key, value in pertask_arrays.items()}
    trips = {item.sumo_vehicle_id: item for item in trip_dataset.matched}
    spans: dict[str, list[Any]] = {}
    for span in identity.spans:
        if span.sumo_vehicle_id in trips:
            spans.setdefault(span.sumo_vehicle_id, []).append(span)
    candidates = sorted(
        spans,
        key=lambda vehicle_id: hashlib.sha256(f"VEC-11-selection:{vehicle_id}".encode()).digest(),
    )
    selected: list[tuple[str, int, int, int]] = []
    used: set[str] = set()
    # Prefer one row for each audited action. The order lets the tiny synthetic fixture
    # cover V2V, V2I, and local while aliases remain unrelated to the source ordering.
    for desired_action in (Decision.V2V, Decision.V2I, Decision.LOCAL):
        desired_code = _ACTIONS.index(desired_action)
        found: tuple[str, int, int, int] | None = None
        for vehicle_id in candidates:
            if vehicle_id in used:
                continue
            for span in sorted(spans[vehicle_id], key=lambda item: (item.t_enter, item.slot)):
                for time_index in range(span.t_enter, span.t_exit + 1):
                    if int(perstep["veh_action"][time_index, span.slot]) != desired_code:
                        continue
                    active = np.flatnonzero(pertask["task_active"][time_index, :, span.slot])
                    if active.size:
                        found = (vehicle_id, time_index, span.slot, int(active[0]))
                        break
                if found is not None:
                    break
            if found is not None:
                break
        if found is not None:
            selected.append(found)
            used.add(found[0])

    if len(selected) != VEC_DISSERTATION_SAMPLE_COUNT:
        raise VecDissertationPackError(
            "accepted matched evidence cannot provide three distinct action-diverse sample rows"
        )

    rows: list[VecSanitisedMatchedSample] = []
    for index, (vehicle_id, time_index, slot, task_index) in enumerate(selected, start=1):
        action_code = int(perstep["veh_action"][time_index, slot])
        rsu = int(perstep["veh_best_rsu"][time_index, slot])
        peer = int(perstep["veh_best_v2v"][time_index, slot])
        trip = trips[vehicle_id]
        rows.append(
            VecSanitisedMatchedSample(
                sample_id=f"sample-{index:03d}",
                task_class=_TASK_CLASSES[int(pertask["task_type"][time_index, task_index, slot])],
                deadline_met=bool(pertask["task_met"][time_index, task_index, slot]),
                latency_ms_rounded_10=_round_to(
                    float(pertask["task_lat_ms"][time_index, task_index, slot]), 10
                ),
                slot_tier=int(perstep["slot_tier"][slot]),
                slot_is_ev=bool(perstep["slot_is_ev"][slot]),
                action=_ACTIONS[action_code],
                target_availability=_availability(action_code, rsu, peer),
                trip_duration_s_rounded_10=_round_to(trip.duration_s, 10),
                trip_route_length_m_rounded_100=_round_to(trip.route_length_m, 100),
            )
        )
    return tuple(rows)


def _sample_bytes(rows: Sequence[VecSanitisedMatchedSample]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=SAMPLE_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        payload = row.model_dump(mode="json")
        writer.writerow({key: payload[key] for key in SAMPLE_COLUMNS})
    return buffer.getvalue().encode()


def _aggregate_bytes(report: VecScientificAdmissionReport) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=AGGREGATE_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for metric in report.evidence_pack.metric_collection.results:
        payload = metric.model_dump(mode="json")
        writer.writerow(
            {
                "metric_key": payload["metric_key"],
                "status": payload["status"],
                "value_json": json.dumps(
                    payload["value"], sort_keys=True, separators=(",", ":"), allow_nan=False
                ),
                "unit": payload["unit"],
                "scope": payload["scope"],
                "missing_evidence_json": json.dumps(
                    payload["missing_evidence"],
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ),
            }
        )
    return buffer.getvalue().encode()


def _artifact(
    path: str,
    kind: PublicationArtifactKind,
    payload: bytes,
    description: str,
) -> IncludedArtifact:
    return IncludedArtifact(
        relative_path=path,
        kind=kind,
        permission_state=PublicationPermissionState.WRITTEN_OWNER_PERMISSION,
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        description=description,
        labels=PublicationSourceLabels(
            source_mode="instrumented",
            campaign="fcd_s102",
            scenario="we",
            fleet="uk2030",
            fleet_seed=0,
        ),
        uses_selected_seed=True,
    )


def render_vec_dissertation_pack(
    rows: Sequence[VecSanitisedMatchedSample],
    scientific_admission: VecScientificAdmissionReport,
    task_report: VecTaskJoinReport,
    trip_dataset: VecTripJoinDataset,
    *,
    sensitive_vehicle_ids: Sequence[str],
) -> tuple[VecDissertationPackManifest, dict[str, bytes]]:
    """Render a complete pack in memory and prove no supplied source ID leaked."""

    if scientific_admission.run_label != VEC_DISSERTATION_RUN_LABEL:
        raise VecDissertationPackError("scientific admission is not the disclosed _s102 run")
    if scientific_admission.task_join_report_fingerprint != task_report.fingerprint():
        raise VecDissertationPackError("scientific admission does not bind the task report")
    if scientific_admission.trip_join_report_fingerprint != trip_dataset.report.fingerprint():
        raise VecDissertationPackError("scientific admission does not bind the trip report")
    if task_report.source_commit != TOS_DATA_AUDITED_COMMIT:
        raise VecDissertationPackError("task report is not from the audited tos-data commit")
    if task_report.scenario != "we" or trip_dataset.report.scenario != "we":
        raise VecDissertationPackError(
            "VEC-11 pack evidence must use the disclosed weekend scenario"
        )
    if len(rows) != VEC_DISSERTATION_SAMPLE_COUNT:
        raise VecDissertationPackError("VEC-11 publishes exactly three sanitised sample rows")
    if [row.sample_id for row in rows] != ["sample-001", "sample-002", "sample-003"]:
        raise VecDissertationPackError("sample aliases must be unique, sequential, and ordered")
    if {row.action for row in rows} != {Decision.LOCAL, Decision.V2I, Decision.V2V}:
        raise VecDissertationPackError("the three-row sample must cover local, V2I, and V2V")
    if not sensitive_vehicle_ids:
        raise VecDissertationPackError("source identifier inventory is required for leak scanning")
    sample_payload = _sample_bytes(rows)
    aggregate_payload = _aggregate_bytes(scientific_admission)
    payloads = {
        VEC_DISSERTATION_SAMPLE_PATH: sample_payload,
        VEC_DISSERTATION_AGGREGATE_PATH: aggregate_payload,
    }
    joined_payload = b"\n".join(payloads.values())
    leaked = [value for value in sensitive_vehicle_ids if value.encode() in joined_payload]
    if leaked:
        raise VecDissertationPackError("a source vehicle identifier survived sanitisation")
    if _ABSOLUTE_PATH.search(joined_payload):
        raise VecDissertationPackError("published payload carries a local absolute path")

    metrics = scientific_admission.evidence_pack.metric_collection.results
    available = sum(metric.status.value == "available" for metric in metrics)
    policy = TosPublicationManifest(
        engine_version="v2_post_nrsus_fix",
        citations=[
            RepositoryCitation(
                repository=PublicationRepository.VEC_ENV,
                reviewed_commit=VEC_ENV_AUDITED_COMMIT,
                commit_verification="caller_supplied",
                citation_text=(
                    "Randy Putra, vec_env source repository, reviewed commit "
                    f"{VEC_ENV_AUDITED_COMMIT[:12]}, 2026."
                ),
                url="https://gitlab.cs.man.ac.uk/e62992rp/vec_env",
            ),
            RepositoryCitation(
                repository=PublicationRepository.TOS_DATA,
                reviewed_commit=TOS_DATA_AUDITED_COMMIT,
                commit_verification="caller_supplied",
                citation_text=(
                    "Randy Putra, tos-data evidence repository, reviewed commit "
                    f"{TOS_DATA_AUDITED_COMMIT[:12]}, 2026."
                ),
                url="https://gitlab.cs.man.ac.uk/e62992rp/tos-data",
            ),
        ],
        permission=PublicationPermissionBasis(
            basis="Written source-owner response received for the TrafficTwin dissertation.",
            granted_on=date(2026, 7, 21),
            scope="Sanitised samples and aggregate outputs in this repository and dissertation.",
        ),
        sanitisation=SanitisationDeclaration(
            statement=(
                "Three source-matched rows use sequential pseudonyms, remove source identity and "
                "clock fields, round numeric values, and retain only declared schema and units."
            ),
            secrets_removed=True,
            private_paths_and_machine_information_removed=True,
            actor_checkpoints_excluded=True,
            third_party_sumo_assets_excluded=True,
            raw_datasets_reduced_to_sanitised_sample=True,
            schema_and_units_preserved=True,
        ),
        selected_seed_disclosure=(
            "The _s102 rows and aggregates are a disclosed best-of-seeds selection, not an "
            "average over evaluator seeds."
        ),
        included=[
            _artifact(
                VEC_DISSERTATION_SAMPLE_PATH,
                PublicationArtifactKind.SANITISED_SAMPLE,
                sample_payload,
                "Three-row pseudonymised and rounded matched task-trip _s102 sample.",
            ),
            _artifact(
                VEC_DISSERTATION_AGGREGATE_PATH,
                PublicationArtifactKind.AGGREGATE,
                aggregate_payload,
                "Accepted and unavailable VEC-09 _s102 aggregate metric states.",
            ),
        ],
        excluded=default_excluded_inventory(),
        limitations=[
            "Pseudonymisation reduces direct identification but is not anonymity.",
            "Rounded sample rows are illustrative and must not be used to reproduce exact values.",
            "Deadline success is not eventual physical task completion.",
            "Eligible targets are not transfer confirmation or execution targets.",
            (
                "Owner permission is not a formal software or data licence; "
                "public hosting is not authorised."
            ),
        ],
    )
    manifest = VecDissertationPackManifest(
        scientific_admission_fingerprint=scientific_admission.fingerprint(),
        task_join_report_fingerprint=task_report.fingerprint(),
        trip_join_report_fingerprint=trip_dataset.report.fingerprint(),
        aggregate_metric_count=len(metrics),
        available_metric_count=available,
        unavailable_metric_count=len(metrics) - available,
        publication_policy=policy,
    )
    payloads[VEC_DISSERTATION_MANIFEST_PATH] = (
        json.dumps(
            manifest.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode()
    return manifest, payloads


def write_vec_dissertation_pack(destination: Path, payloads: Mapping[str, bytes]) -> None:
    """Publish a rendered pack to a new destination directory atomically."""

    expected = {
        VEC_DISSERTATION_SAMPLE_PATH,
        VEC_DISSERTATION_AGGREGATE_PATH,
        VEC_DISSERTATION_MANIFEST_PATH,
    }
    if set(payloads) != expected:
        raise VecDissertationPackError("rendered pack contains an unexpected file set")
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    try:
        for name in sorted(payloads):
            path = temporary / name
            with path.open("xb") as handle:
                handle.write(payloads[name])
                handle.flush()
                os.fsync(handle.fileno())
            path.chmod(0o444)
        verify_vec_dissertation_pack(temporary)
        temporary.rename(destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def verify_vec_dissertation_pack(path: Path) -> VecDissertationPackManifest:
    """Verify the exact pack inventory, manifest, CSV shapes, hashes, and safety boundary."""

    if path.is_symlink() or not path.is_dir():
        raise VecDissertationPackError("pack must be a real directory, not a symlink")
    children = tuple(sorted(item.name for item in path.iterdir()))
    expected = tuple(
        sorted(
            (
                VEC_DISSERTATION_AGGREGATE_PATH,
                VEC_DISSERTATION_MANIFEST_PATH,
                VEC_DISSERTATION_SAMPLE_PATH,
            )
        )
    )
    invalid_child = any(item.is_symlink() or not item.is_file() for item in path.iterdir())
    if children != expected or invalid_child:
        raise VecDissertationPackError("pack must contain exactly three regular files")
    manifest_payload = (path / VEC_DISSERTATION_MANIFEST_PATH).read_bytes()
    if _ABSOLUTE_PATH.search(manifest_payload):
        raise VecDissertationPackError("manifest carries a local absolute path")
    manifest = VecDissertationPackManifest.model_validate_json(manifest_payload)
    for artifact in manifest.publication_policy.included:
        payload = (path / artifact.relative_path).read_bytes()
        if len(payload) != artifact.size_bytes:
            raise VecDissertationPackError(f"size mismatch for {artifact.relative_path}")
        if hashlib.sha256(payload).hexdigest() != artifact.sha256:
            raise VecDissertationPackError(f"hash mismatch for {artifact.relative_path}")
        if _ABSOLUTE_PATH.search(payload):
            raise VecDissertationPackError(f"local path found in {artifact.relative_path}")

    with (path / VEC_DISSERTATION_SAMPLE_PATH).open(newline="", encoding="utf-8") as handle:
        sample_reader = csv.DictReader(handle)
        if tuple(sample_reader.fieldnames or ()) != SAMPLE_COLUMNS:
            raise VecDissertationPackError("sanitised sample columns do not match the contract")
        sample_rows = [VecSanitisedMatchedSample.model_validate(row) for row in sample_reader]
    if len(sample_rows) != manifest.sample_count:
        raise VecDissertationPackError("sample row count does not match the manifest")

    with (path / VEC_DISSERTATION_AGGREGATE_PATH).open(newline="", encoding="utf-8") as handle:
        aggregate_reader = csv.DictReader(handle)
        if tuple(aggregate_reader.fieldnames or ()) != AGGREGATE_COLUMNS:
            raise VecDissertationPackError("aggregate columns do not match the contract")
        aggregate_rows = list(aggregate_reader)
    if len(aggregate_rows) != manifest.aggregate_metric_count:
        raise VecDissertationPackError("aggregate row count does not match the manifest")
    if [row["metric_key"] for row in aggregate_rows] != sorted(
        row["metric_key"] for row in aggregate_rows
    ):
        raise VecDissertationPackError("aggregate metric keys must be sorted")
    for row in aggregate_rows:
        json.loads(row["value_json"])
        json.loads(row["missing_evidence_json"])
    return manifest

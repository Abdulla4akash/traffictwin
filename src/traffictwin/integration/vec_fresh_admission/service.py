"""Owner-approved-candidate scientific admission for fresh VEC-07 executions.

The service closes the fresh-run evidence gap: a completed VEC-07 receipt's
published ``per-step.npz``/``per-task.npz`` arrays are re-verified
byte-for-byte, joined against the pinned trace identity, reduced to the same
deterministic metric definitions the accepted VEC-09 admission uses, and
stored through ``Registry.register_bundle_import`` plus
``Registry.store_metric_collection`` so the STA-01 paired-study tooling can
consume them. Every metric is stamped with a caller-declared study context
whose pairing seed is read from the executed request, never typed in.

What this deliberately does not do: it never grades reproduction (VEC-08),
never reuses the audited ``_s102`` VEC-09 artifact, never admits a truncated
(smoke) execution, never fabricates trip evidence, and never labels the result
beyond ``owner_approved_candidate``.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import subprocess
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from traffictwin.domain.enums import ExecutionMode, RunStatus, ValidationStatus
from traffictwin.domain.run import Run
from traffictwin.integration.tos.contract_v2 import TOS_DATA_AUDITED_COMMIT
from traffictwin.integration.vec_fresh_admission.models import (
    STANDING_FRESH_ADMISSION_LIMITATIONS,
    VEC_FRESH_ADMISSION_METHOD_VERSION,
    VecFreshAdmissionOutcome,
    VecFreshRunAdmissionRecord,
    VecFreshRunStudyContext,
    VecPairingSeedSource,
)
from traffictwin.integration.vec_identity import (
    VecIdentitySnapshot,
    build_vehicle_identity_snapshot,
)
from traffictwin.integration.vec_runner.models import (
    PINNED_ACTORS,
    PINNED_REVIEWED_TRACES,
    PINNED_VEC_ENV_COMMIT,
    VecExecutionReceipt,
    VecTerminalStatus,
)
from traffictwin.integration.vec_task_join import VecTaskJoinReport, build_task_join_report
from traffictwin.metrics.results import (
    MetricCollection,
    MetricStatus,
    MetricValue,
    UnavailableReason,
)
from traffictwin.storage.registry import Registry

REVIEWED_TRACE_SCENARIOS = {
    "a2612865f5e1ef6d066975d6430693225f5d16060f139176548c8ae020e428be": "we",
}
_ENVIRONMENT = "randy-vec"
_ENVIRONMENT_VERSION = "v2_post_nrsus_fix"
_RECEIPT_FILE = "execution_receipt.json"
_RECEIPT_LIMIT_BYTES = 8_000_000
_HASH_CHUNK_BYTES = 1024 * 1024
_PERSTEP_FILE = "per-step.npz"
_PERTASK_FILE = "per-task.npz"


class VecFreshAdmissionError(ValueError):
    """Raised when a fresh execution cannot be admitted safely."""


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def build_fresh_run_admission(
    trace_arrays: Mapping[str, Any],
    perstep_arrays: Mapping[str, Any],
    pertask_arrays: Mapping[str, Any],
    identity: VecIdentitySnapshot,
    receipt: VecExecutionReceipt,
    study: VecFreshRunStudyContext,
    *,
    computed_at: datetime,
    receipt_file_sha256: str | None = None,
    occupancy_sha256: str | None = None,
    tos_data_commit: str | None = None,
) -> tuple[VecFreshRunAdmissionRecord, MetricCollection]:
    """Compute admitted fresh-run metrics and the typed admission record.

    The task join revalidates every array against the identity snapshot, so a
    trace, per-step, or per-task artifact that does not belong to this
    execution's inputs fails closed before any metric exists.
    """

    if receipt.status is not VecTerminalStatus.COMPLETED:
        raise VecFreshAdmissionError(
            f"only completed executions are admissible; receipt status is {receipt.status.value}"
        )
    if receipt.output_fingerprint is None:
        raise VecFreshAdmissionError("completed receipt is missing its output fingerprint")
    request = receipt.request
    trace_steps = int(trace_arrays["T"])
    if request.max_steps != trace_steps:
        raise VecFreshAdmissionError(
            "TRUNCATED_EXECUTION_REFUSED: the request ran "
            f"{request.max_steps} of {trace_steps} trace steps; a truncated (smoke) "
            "execution cannot reconcile against the trace identity and is never "
            "scientific evidence"
        )
    reviewed = request.trace_sha256 in PINNED_REVIEWED_TRACES
    if not reviewed and not study.synthetic_fixture:
        raise VecFreshAdmissionError(
            "UNREVIEWED_TRACE_REFUSED: policy 1.0 admits only the pinned reviewed "
            "trace; an unreviewed trace needs a validated VEC-06 receipt and a "
            "reviewed policy extension"
        )
    task_report = build_task_join_report(
        trace_arrays,
        perstep_arrays,
        pertask_arrays,
        identity,
        run_label=request.run_id,
    )
    receipt_fingerprint = receipt.fingerprint()
    registry_run_id = f"vec:fresh:{receipt_fingerprint[:16]}"
    pairing_random_seed = {
        VecPairingSeedSource.FLEET_SEED: request.fleet_seed,
        VecPairingSeedSource.EVALUATOR_SEED: request.evaluator_seed,
    }[study.pairing_seed_source]
    collection = _compute_metric_collection(
        perstep_arrays,
        pertask_arrays,
        task_report,
        receipt,
        study,
        run_id=registry_run_id,
        random_seed=pairing_random_seed,
        computed_at=computed_at,
    )
    record = VecFreshRunAdmissionRecord(
        request=request,
        request_fingerprint=receipt.request_fingerprint,
        receipt_fingerprint=receipt_fingerprint,
        receipt_file_sha256=receipt_file_sha256,
        output_fingerprint=receipt.output_fingerprint,
        started_at_utc=receipt.started_at_utc,
        finished_at_utc=receipt.finished_at_utc,
        reviewed_trace=reviewed,
        trace_sha256=request.trace_sha256,
        occupancy_sha256=occupancy_sha256,
        tos_data_commit=tos_data_commit,
        identity_snapshot_fingerprint=identity.fingerprint(),
        task_join_report_fingerprint=task_report.fingerprint(),
        metric_collection_run_id=registry_run_id,
        metric_collection_fingerprint=_collection_fingerprint(collection),
        available_metric_count=sum(
            item.status is MetricStatus.AVAILABLE for item in collection.results
        ),
        unavailable_metric_count=collection.unavailable_count,
        study=study,
        pairing_random_seed=pairing_random_seed,
        admitted_at_utc=computed_at.isoformat(),
        registry_run_id=registry_run_id,
        registry_bundle_id=f"vec-fresh:{receipt_fingerprint}",
        limitations=list(STANDING_FRESH_ADMISSION_LIMITATIONS),
    )
    return record, collection


def register_fresh_run_admission(
    record: VecFreshRunAdmissionRecord,
    collection: MetricCollection,
    registry_path: str | Path,
    *,
    clock: Callable[[], datetime] = _utc_now,
) -> VecFreshAdmissionOutcome:
    """Store one admission as a registry run plus its metric collection.

    ``register_bundle_import`` alone never yields study-visible metrics; the
    paired ``store_metric_collection`` write is what makes the run scientific
    for STA-01, so both writes happen here or neither does.
    """

    if collection.run_id != record.metric_collection_run_id:
        raise VecFreshAdmissionError("metric collection does not belong to this record")
    if _collection_fingerprint(collection) != record.metric_collection_fingerprint:
        raise VecFreshAdmissionError("metric collection does not match its recorded fingerprint")
    registry_file = Path(registry_path).resolve(strict=False)
    if registry_file.is_dir():
        raise VecFreshAdmissionError("registry path must name a SQLite file, not a directory")
    if Path(registry_path).is_symlink():
        raise VecFreshAdmissionError("registry path must not be a symbolic link")
    if not registry_file.parent.is_dir():
        raise VecFreshAdmissionError("registry parent directory must already exist")
    now = clock()
    run = Run(
        run_id=record.registry_run_id,
        experiment_id=record.study.experiment_id,
        seed_id=record.study.seed_id,
        algorithm=record.request.actor_id,
        checkpoint=PINNED_ACTORS[record.request.actor_id][0],
        random_seed=record.pairing_random_seed,
        environment_version=_ENVIRONMENT_VERSION,
        environment_commit=PINNED_VEC_ENV_COMMIT,
        started_at=datetime.fromisoformat(record.started_at_utc),
        ended_at=datetime.fromisoformat(record.finished_at_utc),
        execution_mode=ExecutionMode.DIRECT_LAUNCH,
        status=RunStatus.COMPLETED,
        source_bundle=record.registry_bundle_id,
        validation_status=ValidationStatus.VALID,
        created_at=now,
        updated_at=now,
    )
    registry = Registry(registry_file)
    import_result = registry.register_bundle_import(
        run=run,
        bundle_id=record.registry_bundle_id,
        source_reference=f"vec-fresh:{record.study.experiment_id}",
        fingerprint=record.stable_fingerprint(),
        manifest_json=record.model_dump_json(),
        validation_report_json=_validation_report_json(record),
    )
    metrics_created = registry.store_metric_collection(
        run_id=record.metric_collection_run_id,
        metric_version=record.metric_version,
        source_fingerprint=record.task_join_report_fingerprint,
        payload_json=collection.model_dump_json(),
    )
    return VecFreshAdmissionOutcome(
        run_created=import_result.created,
        run_idempotent=import_result.idempotent,
        metrics_created=metrics_created,
        registry_run_id=import_result.run_id,
        registry_bundle_id=import_result.bundle_id,
        stable_fingerprint=record.stable_fingerprint(),
        registry_reference=registry_file.name,
    )


def admit_vec_fresh_run(
    result_dir: str | Path,
    registry_path: str | Path,
    study: VecFreshRunStudyContext,
    *,
    tos_data_repo: str | Path,
    clock: Callable[[], datetime] = _utc_now,
    computed_at: datetime | None = None,
) -> tuple[VecFreshRunAdmissionRecord, VecFreshAdmissionOutcome]:
    """Admit one published fresh VEC-07 execution end to end.

    The pipeline re-verifies the receipt and every published byte, reads the
    trace and occupancy identity evidence as exact Git blobs from the audited
    tos-data commit, joins, computes metrics, and registers the result. Any
    mismatch refuses before the registry is touched.
    """

    if study.synthetic_fixture:
        raise VecFreshAdmissionError(
            "the operational admission path never accepts a synthetic fixture context"
        )
    supplied_root = Path(result_dir)
    if supplied_root.is_symlink():
        raise VecFreshAdmissionError("result directory must be an existing non-symlink directory")
    root = supplied_root.resolve(strict=False)
    if not root.is_dir():
        raise VecFreshAdmissionError("result directory must be an existing non-symlink directory")
    receipt = _load_receipt(root)
    if receipt.status is not VecTerminalStatus.COMPLETED:
        raise VecFreshAdmissionError(
            f"only completed executions are admissible; receipt status is {receipt.status.value}"
        )
    if receipt.external_repositories_modified or receipt.raw_inputs_modified:
        raise VecFreshAdmissionError("receipt reports mutated sources or inputs; admission refused")
    scenario = REVIEWED_TRACE_SCENARIOS.get(receipt.request.trace_sha256)
    if scenario is None:
        raise VecFreshAdmissionError(
            "UNREVIEWED_TRACE_REFUSED: policy 1.0 admits only the pinned reviewed "
            "trace; an unreviewed trace needs a validated VEC-06 receipt and a "
            "reviewed policy extension"
        )
    _verify_outputs_on_disk(root, receipt)
    perstep = _load_published_npz(root, receipt, _PERSTEP_FILE)
    pertask = _load_published_npz(root, receipt, _PERTASK_FILE)

    repo = Path(tos_data_repo)
    if repo.is_symlink() or not repo.is_dir():
        raise VecFreshAdmissionError("tos-data repository path is missing or unsafe")
    trace_blob = _read_audited_blob(repo, PINNED_REVIEWED_TRACES[receipt.request.trace_sha256])
    if hashlib.sha256(trace_blob).hexdigest() != receipt.request.trace_sha256:
        raise VecFreshAdmissionError(
            "audited trace blob does not match the executed request trace hash"
        )
    occupancy_blob = _read_audited_blob(repo, f"occupancy/occupancy_{scenario}.csv")
    with np.load(io.BytesIO(trace_blob), allow_pickle=False) as archive:
        trace = {key: archive[key] for key in archive.files}
    reader = csv.reader(io.StringIO(occupancy_blob.decode("utf-8-sig")))
    identity = build_vehicle_identity_snapshot(
        trace,
        tuple(next(reader)),
        list(reader),
        scenario=scenario,
    )
    record, collection = build_fresh_run_admission(
        trace,
        perstep,
        pertask,
        identity,
        receipt,
        study,
        computed_at=computed_at or clock(),
        receipt_file_sha256=_sha256_file(root / _RECEIPT_FILE),
        occupancy_sha256=hashlib.sha256(occupancy_blob).hexdigest(),
        tos_data_commit=TOS_DATA_AUDITED_COMMIT,
    )
    outcome = register_fresh_run_admission(record, collection, registry_path, clock=clock)
    return record, outcome


def _compute_metric_collection(
    perstep_arrays: Mapping[str, Any],
    pertask_arrays: Mapping[str, Any],
    task_report: VecTaskJoinReport,
    receipt: VecExecutionReceipt,
    study: VecFreshRunStudyContext,
    *,
    run_id: str,
    random_seed: int,
    computed_at: datetime,
) -> MetricCollection:
    """Reduce fresh arrays with the accepted VEC-09 metric definitions.

    The definitions are intentionally identical to the accepted source-run
    admission so the two implementations stay comparable; a drift-guard test
    asserts value equality on shared fixtures. Only the run-context stamp and
    the reproduction claim differ, and the eight metrics VEC-09 keeps
    unavailable stay unavailable here with the same blockers.
    """

    request = receipt.request

    def _metric(
        key: str,
        value: int | float | dict[str, float],
        unit: str,
        scope: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> MetricValue:
        return MetricValue(
            metric_key=key,
            status=MetricStatus.AVAILABLE,
            value=value,
            unit=unit,
            scope=scope,
            required_evidence=[
                "completed VEC-07 execution receipt",
                "VEC-04 task join over the pinned trace identity",
            ],
            warnings=[
                "Owner-approved candidate fresh-run evidence; deadline success is "
                "not physical completion.",
                "No threshold was calibrated or evaluated by this admission.",
            ],
            implementation_version=VEC_FRESH_ADMISSION_METHOD_VERSION,
            run_id=run_id,
            experiment_id=study.experiment_id,
            seed_id=study.seed_id,
            algorithm=request.actor_id,
            checkpoint=PINNED_ACTORS[request.actor_id][0],
            random_seed=random_seed,
            synthetic=study.synthetic_fixture,
            environment=_ENVIRONMENT,
            environment_version=_ENVIRONMENT_VERSION,
            environment_commit=PINNED_VEC_ENV_COMMIT,
            computed_at=computed_at,
            metadata={
                "pairing_seed_source": study.pairing_seed_source.value,
                "fleet": request.fleet.value,
                "fleet_seed": request.fleet_seed,
                "evaluator_seed": request.evaluator_seed,
                "rsu_capacity_per_vehicle": request.rsu_capacity_per_vehicle,
                "max_steps": request.max_steps,
                **(metadata or {}),
            },
        )

    def _unavailable(key: str, unit: str, blocker: str) -> MetricValue:
        return MetricValue(
            metric_key=key,
            status=MetricStatus.UNAVAILABLE,
            unit=unit,
            scope="run",
            missing_evidence=[blocker],
            reason_codes=[UnavailableReason.REQUIRED_FIELD_UNAVAILABLE],
            warnings=["Fresh-run admission refuses to infer or relabel the missing evidence."],
            implementation_version=VEC_FRESH_ADMISSION_METHOD_VERSION,
            run_id=run_id,
            experiment_id=study.experiment_id,
            seed_id=study.seed_id,
            algorithm=request.actor_id,
            checkpoint=PINNED_ACTORS[request.actor_id][0],
            random_seed=random_seed,
            synthetic=study.synthetic_fixture,
            environment=_ENVIRONMENT,
            environment_version=_ENVIRONMENT_VERSION,
            environment_commit=PINNED_VEC_ENV_COMMIT,
            computed_at=computed_at,
        )

    active = np.asarray(pertask_arrays["task_active"], dtype=bool)
    met = np.asarray(pertask_arrays["task_met"], dtype=bool)
    task_type = np.asarray(pertask_arrays["task_type"])
    latency = np.asarray(pertask_arrays["task_lat_ms"])
    action = np.broadcast_to(np.asarray(perstep_arrays["veh_action"])[:, None, :], active.shape)
    tier = np.broadcast_to(np.asarray(perstep_arrays["slot_tier"])[None, None, :], active.shape)
    best_rsu = np.broadcast_to(np.asarray(perstep_arrays["veh_best_rsu"])[:, None, :], active.shape)
    best_v2v = np.broadcast_to(np.asarray(perstep_arrays["veh_best_v2v"])[:, None, :], active.shape)
    total = int(active.sum())
    if total <= 0:
        raise VecFreshAdmissionError("at least one reconciled task is required")
    deadline_met = int((active & met).sum())
    action_counts = {code: int((active & (action == code)).sum()) for code in (0, 1, 2)}
    class_rates: dict[str, float] = {}
    class_support: dict[str, int] = {}
    for code, label in enumerate(("T1", "T2", "T3")):
        cohort = active & (task_type == code)
        count = int(cohort.sum())
        if count:
            class_rates[label] = float((cohort & met).sum()) / count
            class_support[label] = count
    tier_rates: dict[str, float] = {}
    tier_support: dict[str, int] = {}
    for code in (0, 1, 2):
        cohort = active & (tier == code)
        count = int(cohort.sum())
        if count:
            tier_rates[str(code)] = float((cohort & met).sum()) / count
            tier_support[str(code)] = count
    offload = active & ((action == 1) | (action == 2))
    offload_count = int(offload.sum())
    no_target = active & (((action == 1) & (best_rsu < 0)) | ((action == 2) & (best_v2v < 0)))
    no_target_count = int(no_target.sum())

    results = [
        _metric("task.generated.count", total, "count", "run"),
        _metric(
            "task.latency.mean_ms",
            float(latency[active].mean(dtype=np.float64)),
            "ms",
            "run",
        ),
        *[
            _metric(
                f"task.decision_share.{label}",
                action_counts[code] / total,
                "ratio",
                "run",
            )
            for code, label in ((0, "local"), (1, "v2i"), (2, "v2v"))
        ],
        _metric("task.decision_share.unknown", 0.0, "ratio", "run"),
        _metric(
            "task.offload.rate",
            (action_counts[1] + action_counts[2]) / total,
            "ratio",
            "run",
        ),
        _metric(
            "tos.task.deadline_success.rate",
            deadline_met / total,
            "ratio",
            "run",
            metadata={"outcome_semantics": "deadline_met_per_arrival"},
        ),
        _metric(
            "tos.task.deadline_success.rate_by_class",
            class_rates,
            "ratio",
            "task_class",
            metadata={
                "task_type_codes": "0=T1,1=T2,2=T3",
                "group_support_counts": class_support,
                "unsupported_groups_omitted": True,
            },
        ),
        _metric(
            "tos.task.deadline_success.rate_by_slot_tier",
            tier_rates,
            "ratio",
            "slot_tier",
            metadata={
                "group_support_counts": tier_support,
                "attribute_interpretation": ("operational_slot_assignment_not_protected_attribute"),
            },
        ),
        _metric(
            "tos.operational.slot_tier.deadline_success.max_gap",
            max(tier_rates.values()) - min(tier_rates.values()),
            "ratio",
            "run",
            metadata={"group_support_counts": tier_support, "group_count": len(tier_rates)},
        ),
        _metric(
            "tos.task.no_eligible_target.rate_among_offload",
            no_target_count / offload_count if offload_count else 0.0,
            "ratio",
            "run",
            metadata={
                "no_eligible_target_count": no_target_count,
                "offload_task_count": offload_count,
                "failure_inferred": False,
            },
        ),
    ]
    unavailable = {
        "task.completed.count": ("count", "physical completion evidence is absent"),
        "task.completion.rate": ("ratio", "physical completion evidence is absent"),
        "task.energy.per_completed_j": ("J/task", "per-task energy evidence is absent"),
        "infra.utilisation.mean": ("ratio", "canonical CPU utilisation evidence is absent"),
        "infra.queue.mean_tasks": ("tasks", "canonical queue-length evidence is absent"),
        "fairness.vehicle_tier.completion_rate.max_gap": (
            "ratio",
            "slot-tier deadline success is not stable-vehicle physical completion",
        ),
        "spatial.rsu.task.completion_rate_by_target": (
            "ratio",
            "eligible targets are not confirmed execution targets",
        ),
        "trip.completion.rate": (
            "ratio",
            "trip evidence is trace-level and excluded from fresh-run admission",
        ),
    }
    for key, (unit, blocker) in unavailable.items():
        results.append(_unavailable(key, unit, blocker))
    results.sort(key=lambda item: item.metric_key)
    return MetricCollection(
        run_id=run_id,
        metric_version=VEC_FRESH_ADMISSION_METHOD_VERSION,
        results=results,
        unavailable_count=sum(item.status is MetricStatus.UNAVAILABLE for item in results),
        partial_count=0,
        generated_at=computed_at,
        input_fingerprint=task_report.fingerprint(),
    )


def _collection_fingerprint(collection: MetricCollection) -> str:
    payload = json.dumps(
        collection.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _validation_report_json(record: VecFreshRunAdmissionRecord) -> str:
    checks = {
        "receipt_status": "completed",
        "outputs_reverified_on_disk": not record.study.synthetic_fixture,
        "reviewed_trace": record.reviewed_trace,
        "synthetic_fixture": record.study.synthetic_fixture,
        "policy_id": record.policy_id,
        "research_status": record.research_status,
        "reproduction_graded": record.reproduction_graded,
    }
    return json.dumps(checks, sort_keys=True, separators=(",", ":"))


def _load_receipt(root: Path) -> VecExecutionReceipt:
    receipt_path = root / _RECEIPT_FILE
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise VecFreshAdmissionError("execution_receipt.json is missing or unsafe")
    if receipt_path.stat().st_size > _RECEIPT_LIMIT_BYTES:
        raise VecFreshAdmissionError("execution receipt exceeds the bounded size")
    try:
        return VecExecutionReceipt.model_validate_json(receipt_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise VecFreshAdmissionError(f"execution receipt is not valid: {exc}") from exc


def _verify_outputs_on_disk(root: Path, receipt: VecExecutionReceipt) -> None:
    for evidence in receipt.outputs:
        try:
            path = _safe_file_under(root, evidence.path, label="published output")
            size = path.stat().st_size
            digest = _sha256_file(path)
        except OSError as exc:
            raise VecFreshAdmissionError(
                f"published output could not be read safely: {evidence.path}"
            ) from exc
        if size != evidence.size_bytes or digest != evidence.sha256:
            raise VecFreshAdmissionError(
                f"published output does not match its receipt identity: {evidence.path}"
            )


def _load_published_npz(root: Path, receipt: VecExecutionReceipt, name: str) -> dict[str, Any]:
    evidence = next((item for item in receipt.outputs if item.path == name), None)
    if evidence is None:
        raise VecFreshAdmissionError(f"receipt does not publish the required output: {name}")
    path = _safe_file_under(root, evidence.path, label="published output")
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def _read_audited_blob(repo: Path, path: str) -> bytes:
    git = shutil.which("git")
    if git is None:
        raise VecFreshAdmissionError("git executable is required to read audited evidence")
    try:
        status = subprocess.run(  # noqa: S603 - resolved Git executable, fixed read-only argv
            [git, "-C", str(repo), "status", "--porcelain=v1", "--untracked-files=all"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        if status:
            raise VecFreshAdmissionError("tos-data repository must be clean")
        origin_main = subprocess.run(  # noqa: S603 - resolved Git executable, fixed argv
            [git, "-C", str(repo), "rev-parse", "refs/remotes/origin/main"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if origin_main != TOS_DATA_AUDITED_COMMIT:
            raise VecFreshAdmissionError(
                "tos-data origin/main is not at the audited commit; admission refused"
            )
        blob = subprocess.run(  # noqa: S603 - resolved Git executable, fixed argv
            [git, "-C", str(repo), "show", f"{TOS_DATA_AUDITED_COMMIT}:{path}"],
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise VecFreshAdmissionError(f"audited tos-data blob could not be read: {path}") from exc
    return blob


def _safe_file_under(root: Path, relative_path: str, *, label: str) -> Path:
    candidate = root
    for part in Path(relative_path).parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise VecFreshAdmissionError(f"{label} is missing or unsafe: {relative_path}")
    resolved = candidate.resolve(strict=False)
    if root not in resolved.parents or not resolved.is_file():
        raise VecFreshAdmissionError(f"{label} is missing or unsafe: {relative_path}")
    return resolved


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()

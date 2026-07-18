"""Reproducibility audit for the read-only TOS results package."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.integration.tos.analysis_models import (
    TosAuditCheck,
    TosAuditStatus,
    TosReproducibilityAudit,
)
from traffictwin.integration.tos.models import TOS_VEC_ENV_EVIDENCE_COMMIT
from traffictwin.integration.tos.readers import (
    list_instrumented_runs,
    list_pertask_runs,
    package_fingerprint,
    package_git_commit,
    read_evaluation_runs,
    safe_package_path,
)
from traffictwin.integration.tos.training import list_training_runs

Clock = Callable[[], datetime]


def audit_tos_package(
    root: str | Path,
    *,
    clock: Clock | None = None,
) -> TosReproducibilityAudit:
    """Audit present and absent artifacts without modifying the source package."""

    package = Path(root).resolve()
    evaluation_runs = read_evaluation_runs(package)
    actors = sorted({run.actor for run in evaluation_runs})
    training = list_training_runs(package)
    training_ids = {run.training_id for run in training}
    actor_training_matches = sum(
        actor.removesuffix("_actor_params.npz") in training_ids for actor in actors
    )
    checkpoint_files = list(package.rglob("*_actor_params.npz"))
    summaries = list(safe_package_path(package, "training").glob("*_greedy_eval.json"))
    traces = list(safe_package_path(package, "traces").glob("*.npz"))
    instrumented = list_instrumented_runs(package)
    per_task = list_pertask_runs(package)
    checks = [
        TosAuditCheck(
            code="EVALUATION_MATRIX_PRESENT",
            status=TosAuditStatus.PASS,
            message=f"The package contains {len(evaluation_runs)} validated evaluation rows.",
            evidence=["evals/eval_results_master.csv"],
        ),
        TosAuditCheck(
            code="TRAINING_HISTORY_REFERENCES_MATCHED",
            status=(
                TosAuditStatus.PASS
                if actor_training_matches == len(actors)
                else TosAuditStatus.WARNING
            ),
            message=(
                f"{actor_training_matches} of {len(actors)} unique actor references have a "
                "matching training-history basename."
            ),
            evidence=["training/*.csv", "evals/eval_results_master.csv"],
        ),
        TosAuditCheck(
            code="CHECKPOINT_PAYLOADS_UNAVAILABLE",
            status=TosAuditStatus.BLOCKED,
            message=(
                "Evaluation rows name actor checkpoints, but checkpoint payloads are not present "
                "in the inspected results package."
            ),
            evidence=actors,
            affected_capabilities=["checkpoint_loading", "direct_launch"],
        ),
        TosAuditCheck(
            code="INSTRUMENTED_COVERAGE_PARTIAL",
            status=TosAuditStatus.INFORMATION,
            message=(
                f"Per-step arrays cover {len(instrumented)} showcase runs; this is not the full "
                f"{len(evaluation_runs)}-row evaluation matrix."
            ),
            evidence=["instrumented/perstep/", "instrumented/json/"],
        ),
        TosAuditCheck(
            code="PERTASK_COVERAGE_PARTIAL",
            status=TosAuditStatus.INFORMATION,
            message=f"Per-task arrays are available for {len(per_task)} showcase runs.",
            evidence=["instrumented/pertask/"],
        ),
        TosAuditCheck(
            code="PROCESSED_FCD_ONLY",
            status=TosAuditStatus.WARNING,
            message=(
                "Processed FCD traces are present, but raw SUMO configuration and trip outputs "
                "are not included."
            ),
            evidence=["traces/*.npz"],
            affected_capabilities=["trip_metrics", "raw_sumo_reproduction"],
        ),
        TosAuditCheck(
            code="INSTRUMENTATION_WRITER_UNAVAILABLE",
            status=TosAuditStatus.BLOCKED,
            message=(
                "The inspected vec_env source explains array semantics but does not contain the "
                "writer that produced the supplied instrumented files."
            ),
            evidence=[f"vec_env commit {TOS_VEC_ENV_EVIDENCE_COMMIT}"],
            affected_capabilities=["instrumented_writer_reproducible", "direct_launch"],
        ),
    ]
    if checkpoint_files:
        checks[2] = TosAuditCheck(
            code="CHECKPOINT_PAYLOADS_PRESENT",
            status=TosAuditStatus.PASS,
            message=f"The package contains {len(checkpoint_files)} actor checkpoint payloads.",
            evidence=[path.relative_to(package).as_posix() for path in checkpoint_files],
        )
    return TosReproducibilityAudit(
        package_fingerprint=package_fingerprint(package),
        package_commit=package_git_commit(package),
        semantics_source_commit=TOS_VEC_ENV_EVIDENCE_COMMIT,
        evaluation_run_count=len(evaluation_runs),
        unique_actor_reference_count=len(actors),
        actor_checkpoint_file_count=len(checkpoint_files),
        actor_training_history_match_count=actor_training_matches,
        training_history_count=len(training),
        training_summary_count=len(summaries),
        instrumented_run_count=len(instrumented),
        per_task_run_count=len(per_task),
        trace_count=len(traces),
        checks=checks,
        generated_at=(clock or _utc_now)(),
        warnings=[
            "This audit checks package consistency and coverage, not scientific validity.",
            "Machine record contents are not exposed because they may contain private host data.",
        ],
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)

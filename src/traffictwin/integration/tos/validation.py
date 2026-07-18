"""Package-specific validation for Randy's documented TOS Data artifacts."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.integration.tos.models import (
    TOS_EXPECTED_ENGINE_VERSION,
    NpzArrayHeader,
    TosEvaluationRun,
    TosFindingSeverity,
    TosIntegrationCapabilities,
    TosPackageInventory,
    TosSummary,
    TosValidationFinding,
    TosValidationReport,
    TosValidationStatus,
)
from traffictwin.integration.tos.readers import (
    EXPECTED_EVALUATION_COLUMNS,
    TosPackageError,
    evaluation_headers,
    instrumented_key_for_run,
    package_fingerprint,
    package_git_commit,
    read_evaluation_runs,
    read_npz_headers,
    read_summary,
    safe_package_path,
)

PERSTEP_REQUIRED = {
    "times": 1,
    "arrivals": 1,
    "done": 1,
    "lat_sum": 1,
    "active": 1,
    "n_local": 1,
    "n_v2i": 1,
    "n_v2v": 1,
    "veh_action": 2,
    "veh_k": 2,
    "veh_done": 2,
    "veh_queue_ms": 2,
    "rsu_busy_ms": 2,
    "rsu_load": 2,
}
PERTASK_REQUIRED = {
    "task_type": 3,
    "task_lat_ms": 3,
    "task_met": 3,
    "task_active": 3,
}
TRACE_REQUIRED = {
    "pos_x": 2,
    "pos_y": 2,
    "speed": 2,
    "mask": 2,
    "rsu_xy": 2,
    "times": 1,
    "dt": 0,
    "maxN": 0,
    "T": 0,
    "window": 0,
    "sumo_seed": 0,
}


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def inspect_tos_package(
    root: str | Path,
    *,
    deep: bool = True,
    clock: Callable[[], datetime] = utc_now,
) -> TosValidationReport:
    """Inspect a TOS package without mutating it or a registry."""

    package = Path(root).resolve()
    findings: list[TosValidationFinding] = []
    if not package.is_dir():
        findings.append(
            _finding(
                "TOS_PACKAGE_NOT_FOUND",
                TosFindingSeverity.ERROR,
                "The selected TOS Data package directory does not exist.",
                blocks=True,
                capabilities=["evaluation_summary_import", "instrumented_historical_replay"],
            )
        )
        return _report(
            package,
            rows=0,
            findings=findings,
            fingerprint=None,
            commit=None,
            engine_versions=[],
            clock=clock,
        )

    for relative in ("README.md", "DATA_DICTIONARY.md", "evals/eval_results_master.csv"):
        path = safe_package_path(package, relative)
        if not path.is_file():
            findings.append(
                _finding(
                    "TOS_REQUIRED_FILE_MISSING",
                    TosFindingSeverity.ERROR,
                    f"Required package file is missing: {relative}",
                    file=relative,
                    blocks=True,
                    capabilities=["evaluation_summary_import"],
                )
            )

    rows = []
    engine_versions: list[str] = []
    if not any(item.code == "TOS_REQUIRED_FILE_MISSING" for item in findings):
        try:
            headers = evaluation_headers(package)
            extra = sorted(set(headers) - set(EXPECTED_EVALUATION_COLUMNS))
            if extra:
                findings.append(
                    _finding(
                        "TOS_EVALUATION_COLUMNS_ADDITIONAL",
                        TosFindingSeverity.INFO,
                        "Additional evaluation columns are preserved outside the current adapter: "
                        + ", ".join(extra),
                        file="evals/eval_results_master.csv",
                    )
                )
            rows = read_evaluation_runs(package)
            engine_versions = sorted({row.engine_version for row in rows})
        except TosPackageError as exc:
            findings.append(
                _finding(
                    "TOS_EVALUATION_MASTER_INVALID",
                    TosFindingSeverity.ERROR,
                    str(exc),
                    file="evals/eval_results_master.csv",
                    blocks=True,
                    capabilities=["evaluation_summary_import"],
                )
            )

    duplicate_run_ids = sorted(
        run_id for run_id, count in Counter(row.run_id for row in rows).items() if count > 1
    )
    if duplicate_run_ids:
        findings.append(
            _finding(
                "TOS_RUN_ID_DUPLICATE",
                TosFindingSeverity.ERROR,
                "Evaluation master contains duplicate run identifiers: "
                + ", ".join(duplicate_run_ids),
                file="evals/eval_results_master.csv",
                blocks=True,
                capabilities=["evaluation_summary_import"],
            )
        )

    if not rows and not any(item.blocks_import for item in findings):
        findings.append(
            _finding(
                "TOS_EVALUATION_ROWS_EMPTY",
                TosFindingSeverity.ERROR,
                "The evaluation master contains no runs.",
                file="evals/eval_results_master.csv",
                blocks=True,
                capabilities=["evaluation_summary_import"],
            )
        )
    unsupported_versions = [
        version for version in engine_versions if version != TOS_EXPECTED_ENGINE_VERSION
    ]
    if unsupported_versions:
        findings.append(
            _finding(
                "TOS_ENGINE_VERSION_UNSUPPORTED",
                TosFindingSeverity.ERROR,
                "Evaluation rows include unsupported engine versions: "
                + ", ".join(unsupported_versions),
                file="evals/eval_results_master.csv",
                field="engine_version",
                blocks=True,
                capabilities=["evaluation_summary_import"],
            )
        )

    for row in rows:
        trace = safe_package_path(package, Path("traces") / row.trace)
        if not trace.is_file():
            findings.append(
                _finding(
                    "TOS_TRACE_DECLARED_MISSING",
                    TosFindingSeverity.WARNING,
                    f"Evaluation row references a missing trace: {row.trace}",
                    file=row.source_file,
                    field="trace",
                    row=row.source_row,
                    capabilities=["instrumented_historical_replay"],
                )
            )

    if deep:
        _inspect_npz_contracts(package, rows, findings)

    findings.extend(
        [
            _finding(
                "TOS_RSU_SEMANTICS_UNRESOLVED",
                TosFindingSeverity.WARNING,
                "rsu_load, rsu_busy_ms, and rsu_max_concurrent are preserved but not mapped to "
                "queue length, utilisation, or capacity.",
                capabilities=["infrastructure_metric_mapping", "R2"],
            ),
            _finding(
                "TOS_TASK_OUTCOME_SEMANTICS",
                TosFindingSeverity.INFO,
                "Source completion and task_met represent deadline success per arrival; they are "
                "not silently converted to TrafficTwin's generic completed-task field.",
                capabilities=["canonical_task_conversion"],
            ),
            _finding(
                "TOS_TRIP_EVIDENCE_UNAVAILABLE",
                TosFindingSeverity.INFO,
                "The package contains no trip or journey-time records.",
                capabilities=["trip_metrics", "journey_time"],
            ),
            _finding(
                "TOS_EXECUTION_CONTRACT_UNAVAILABLE",
                TosFindingSeverity.INFO,
                "The data package does not provide a tested headless execution contract.",
                capabilities=["direct_launch", "asynchronous_launch"],
            ),
        ]
    )

    try:
        fingerprint = package_fingerprint(package)
    except TosPackageError as exc:
        fingerprint = None
        findings.append(
            _finding(
                "TOS_PACKAGE_FINGERPRINT_UNAVAILABLE",
                TosFindingSeverity.ERROR,
                str(exc),
                blocks=True,
                capabilities=["evaluation_summary_import", "provenance"],
            )
        )
    commit = package_git_commit(package)
    if commit is None:
        findings.append(
            _finding(
                "TOS_PACKAGE_COMMIT_UNAVAILABLE",
                TosFindingSeverity.WARNING,
                "The package Git commit could not be resolved; fingerprint provenance remains.",
                capabilities=["provenance"],
            )
        )
    return _report(
        package,
        rows=len(rows),
        findings=findings,
        fingerprint=fingerprint,
        commit=commit,
        engine_versions=engine_versions,
        clock=clock,
    )


def validate_tos_package(
    root: str | Path,
    *,
    deep: bool = True,
    clock: Callable[[], datetime] = utc_now,
) -> TosValidationReport:
    """Alias for the complete read-only package inspection."""

    return inspect_tos_package(root, deep=deep, clock=clock)


def _inspect_npz_contracts(
    package: Path,
    rows: list[TosEvaluationRun],
    findings: list[TosValidationFinding],
) -> None:
    patterns = (
        ("instrumented/perstep/*_perstep.npz", PERSTEP_REQUIRED, "TOS_PERSTEP"),
        ("instrumented/pertask/*_pertask.npz", PERTASK_REQUIRED, "TOS_PERTASK"),
        ("traces/*.npz", TRACE_REQUIRED, "TOS_TRACE"),
    )
    for pattern, required, prefix in patterns:
        for path in sorted(package.glob(pattern)):
            relative = path.relative_to(package).as_posix()
            try:
                safe_path = safe_package_path(package, relative)
                headers = read_npz_headers(safe_path)
                _check_headers(headers, required, relative, prefix, findings)
            except TosPackageError as exc:
                findings.append(
                    _finding(
                        f"{prefix}_INVALID",
                        TosFindingSeverity.WARNING,
                        str(exc),
                        file=relative,
                        capabilities=["instrumented_historical_replay"],
                    )
                )

    by_instrumented_key: dict[str, TosEvaluationRun] = {}
    for row in rows:
        try:
            by_instrumented_key[instrumented_key_for_run(row)] = row
        except TosPackageError:
            continue
    for path in sorted((package / "instrumented/json").glob("*.json")):
        relative = path.relative_to(package).as_posix()
        try:
            summary = read_summary(safe_package_path(package, relative))
        except TosPackageError as exc:
            findings.append(
                _finding(
                    "TOS_INSTRUMENTED_SUMMARY_INVALID",
                    TosFindingSeverity.WARNING,
                    str(exc),
                    file=relative,
                    capabilities=["instrumented_historical_replay"],
                )
            )
            continue
        matched_row = by_instrumented_key.get(path.stem)
        if matched_row is None:
            findings.append(
                _finding(
                    "TOS_INSTRUMENTED_SUMMARY_UNMATCHED",
                    TosFindingSeverity.WARNING,
                    "Instrumented summary has no matching evaluation-master row.",
                    file=relative,
                    capabilities=["evaluation_reconciliation"],
                )
            )
            continue
        _compare_summary(matched_row, summary, relative, findings)


def _check_headers(
    headers: list[NpzArrayHeader],
    required: dict[str, int],
    relative: str,
    prefix: str,
    findings: list[TosValidationFinding],
) -> None:
    by_name = {header.name: header for header in headers}
    missing = sorted(set(required) - set(by_name))
    if missing:
        findings.append(
            _finding(
                f"{prefix}_ARRAY_MISSING",
                TosFindingSeverity.WARNING,
                "Required arrays are missing: " + ", ".join(missing),
                file=relative,
                capabilities=["instrumented_historical_replay"],
            )
        )
    for name, dimensions in required.items():
        header = by_name.get(name)
        if header is not None and len(header.shape) != dimensions:
            findings.append(
                _finding(
                    f"{prefix}_SHAPE_INVALID",
                    TosFindingSeverity.WARNING,
                    f"{name} has {len(header.shape)} dimensions; expected {dimensions}.",
                    file=relative,
                    field=name,
                    capabilities=["instrumented_historical_replay"],
                )
            )
    non_scalar = [header.shape for header in headers if header.name in required and header.shape]
    if prefix == "TOS_PERTASK" and non_scalar and len({tuple(shape) for shape in non_scalar}) != 1:
        findings.append(
            _finding(
                "TOS_PERTASK_SHAPE_MISMATCH",
                TosFindingSeverity.WARNING,
                "Per-task arrays do not share the same shape.",
                file=relative,
                capabilities=["per_task_showcase_inspection"],
            )
        )


def _compare_summary(
    row: TosEvaluationRun,
    summary: TosSummary,
    relative: str,
    findings: list[TosValidationFinding],
) -> None:
    fields = (
        "completion",
        "t1_completion",
        "t2_completion",
        "t3_completion",
        "avg_energy_j_per_task",
        "avg_latency_ms_per_task",
        "p_local",
        "p_v2i",
        "p_v2v",
        "fleet_ev_share",
    )
    mismatches = [
        field
        for field in fields
        if not math.isclose(
            float(getattr(row, field)),
            float(getattr(summary, field)),
            rel_tol=0,
            abs_tol=1e-9,
        )
    ]
    if mismatches:
        findings.append(
            _finding(
                "TOS_SUMMARY_RECONCILIATION_MISMATCH",
                TosFindingSeverity.WARNING,
                "Instrumented summary differs from its evaluation row: " + ", ".join(mismatches),
                file=relative,
                capabilities=["evaluation_reconciliation"],
            )
        )


def _inventory(package: Path, rows: int) -> TosPackageInventory:
    return TosPackageInventory(
        evaluation_rows=rows,
        training_csv_files=len(list(package.glob("training/*.csv"))),
        training_summary_files=len(list(package.glob("training/*_greedy_eval.json"))),
        perstep_files=len(list(package.glob("instrumented/perstep/*_perstep.npz"))),
        pertask_files=len(list(package.glob("instrumented/pertask/*_pertask.npz"))),
        instrumented_summary_files=len(list(package.glob("instrumented/json/*.json"))),
        trace_files=len(list(package.glob("traces/*.npz"))),
        training_record_files=len(list(package.glob("records/TRAINING_*.md"))),
    )


def _report(
    package: Path,
    *,
    rows: int,
    findings: list[TosValidationFinding],
    fingerprint: str | None,
    commit: str | None,
    engine_versions: list[str],
    clock: Callable[[], datetime],
) -> TosValidationReport:
    severity_order = {
        TosFindingSeverity.ERROR: 0,
        TosFindingSeverity.WARNING: 1,
        TosFindingSeverity.INFO: 2,
    }
    ordered = sorted(
        findings,
        key=lambda item: (
            severity_order[item.severity],
            item.code,
            item.file or "",
            item.row or 0,
            item.field or "",
        ),
    )
    may_import = (
        rows > 0 and fingerprint is not None and not any(item.blocks_import for item in ordered)
    )
    if not may_import:
        status = TosValidationStatus.REJECTED
    elif any(item.severity is TosFindingSeverity.WARNING for item in ordered):
        status = TosValidationStatus.ACCEPTED_WITH_WARNINGS
    else:
        status = TosValidationStatus.ACCEPTED
    inventory = _inventory(package, rows)
    replay_invalid = any(
        item.code.startswith(("TOS_PERSTEP", "TOS_TRACE", "TOS_INSTRUMENTED_SUMMARY"))
        for item in ordered
    )
    pertask_invalid = any(item.code.startswith("TOS_PERTASK") for item in ordered)
    capabilities = TosIntegrationCapabilities(
        evaluation_summary_import=may_import,
        instrumented_historical_replay=(
            inventory.perstep_files > 0 and inventory.trace_files > 0 and not replay_invalid
        ),
        per_task_showcase_inspection=(inventory.pertask_files > 0 and not pertask_invalid),
    )
    return TosValidationReport(
        status=status,
        may_import_summaries=may_import,
        package_fingerprint=fingerprint,
        package_commit=commit,
        engine_versions=engine_versions,
        inventory=inventory,
        findings=ordered,
        capabilities=capabilities,
        inspected_at=clock(),
    )


def _finding(
    code: str,
    severity: TosFindingSeverity,
    message: str,
    *,
    file: str | None = None,
    field: str | None = None,
    row: int | None = None,
    blocks: bool = False,
    capabilities: list[str] | None = None,
) -> TosValidationFinding:
    return TosValidationFinding(
        code=code,
        severity=severity,
        message=message,
        file=file,
        field=field,
        row=row,
        blocks_import=blocks,
        affected_capabilities=capabilities or [],
    )

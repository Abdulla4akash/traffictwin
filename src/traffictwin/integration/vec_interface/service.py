"""Thin orchestration helpers over accepted VEC library services."""

from __future__ import annotations

import csv
import io
import json
import shutil
import subprocess
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import BaseModel, ValidationError

from traffictwin.integration.vec_interface.models import (
    VecAdmissionComparison,
    VecArtifactInspection,
    VecInterfaceAvailability,
    VecInterfaceSnapshot,
    VecMetricDelta,
    VecOperationName,
    VecOperationStatus,
    VecRepositorySnapshot,
)
from traffictwin.integration.vec_preprocessing import (
    PINNED_VEC_ENV_COMMIT,
    VecFcdPreprocessReceipt,
    VecFcdPreprocessRequest,
)
from traffictwin.integration.vec_reproduction import VecReproductionReport
from traffictwin.integration.vec_runner import (
    PINNED_TOS_DATA_COMMIT,
    VecExecutionReceipt,
    VecRunRequest,
)
from traffictwin.integration.vec_science import VecScientificAdmissionReport
from traffictwin.metrics.results import MetricStatus


class VecInterfaceError(ValueError):
    """Raised when a VEC-10 request or artifact is outside the thin interface contract."""


VecRequestT = TypeVar("VecRequestT", bound=BaseModel)


def inspect_vec_interface(vec_repo: Path, tos_data_repo: Path) -> VecInterfaceSnapshot:
    """Inspect pinned source readiness using read-only Git commands."""

    vec = _repository_snapshot(vec_repo, "vec_env", PINNED_VEC_ENV_COMMIT)
    tos = _repository_snapshot(tos_data_repo, "tos-data", PINNED_TOS_DATA_COMMIT)
    vec_ready = vec.ready_for_exact_blob_access
    both_ready = vec_ready and tos.ready_for_exact_blob_access
    return VecInterfaceSnapshot(
        repositories=(vec, tos),
        operations=(
            _operation("snapshot", True, "read-only repository state inspection is available"),
            _operation("validate", True, "typed request preflight is available"),
            _operation(
                "preprocess",
                vec_ready,
                "requires clean vec_env with the audited commit available",
            ),
            VecOperationStatus(
                operation="run",
                availability=(
                    VecInterfaceAvailability.CONDITIONAL
                    if both_ready
                    else VecInterfaceAvailability.BLOCKED
                ),
                reason=(
                    "requires an accepted request-specific VEC-07 runtime preflight"
                    if both_ready
                    else "both audited repositories must be ready for exact Git-blob access"
                ),
            ),
            VecOperationStatus(
                operation="monitor_current_process",
                availability=VecInterfaceAvailability.CONDITIONAL,
                reason="available only while this process owns a foreground preprocess or run",
            ),
            _operation("inspect", True, "typed portable receipts and reports can be inspected"),
            _operation("compare", True, "accepted VEC-09 scalar metrics can be compared"),
            _operation("export", True, "accepted VEC-09 reports export to JSON, CSV, or Markdown"),
        ),
    )


def load_preprocess_request(path: Path) -> VecFcdPreprocessRequest:
    return _load_model(path, VecFcdPreprocessRequest)


def load_run_request(path: Path) -> VecRunRequest:
    return _load_model(path, VecRunRequest)


def load_scientific_admission(path: Path) -> VecScientificAdmissionReport:
    """Load a direct or acceptance-wrapper VEC-09 report."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VecInterfaceError(f"could not read VEC-09 report: {exc}") from exc
    if not isinstance(payload, dict):
        raise VecInterfaceError("VEC-09 report must be a JSON object")
    candidate = payload.get("admission", payload)
    try:
        return VecScientificAdmissionReport.model_validate(candidate)
    except ValidationError as exc:
        raise VecInterfaceError(f"invalid VEC-09 report: {exc}") from exc


def inspect_vec_artifact(path: Path) -> VecArtifactInspection:
    """Parse one closed portable VEC artifact and return a bounded summary."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VecInterfaceError(f"could not read VEC artifact: {exc}") from exc
    if not isinstance(payload, dict):
        raise VecInterfaceError("VEC artifact must be a JSON object")
    candidate = payload.get("admission", payload)
    capability_id = candidate.get("capability_id") if isinstance(candidate, dict) else None
    try:
        if capability_id == "VEC-06":
            value = VecFcdPreprocessReceipt.model_validate(candidate)
            return VecArtifactInspection(
                capability_id=value.capability_id,
                artifact_type="fcd_preprocess_receipt",
                status=value.status,
                artifact_fingerprint=value.fingerprint(),
                summary={
                    "input_id": value.request.input_id,
                    "published": True,
                    "output_count": len(value.outputs),
                },
            )
        if capability_id == "VEC-07":
            execution = VecExecutionReceipt.model_validate(candidate)
            return VecArtifactInspection(
                capability_id=execution.capability_id,
                artifact_type="execution_receipt",
                status=execution.status.value,
                artifact_fingerprint=execution.fingerprint(),
                summary={
                    "run_id": execution.request.run_id,
                    "published": execution.published,
                    "elapsed_seconds": execution.elapsed_seconds,
                    "output_count": len(execution.outputs),
                },
            )
        if capability_id == "VEC-08":
            reproduction = VecReproductionReport.model_validate(candidate)
            return VecArtifactInspection(
                capability_id=reproduction.capability_id,
                artifact_type="reproduction_report",
                status=reproduction.grade.value,
                artifact_fingerprint=reproduction.fingerprint(),
                summary={
                    "case_id": reproduction.request.case_id,
                    "grade": reproduction.grade.value,
                    "exact_checks": reproduction.summary.exact,
                    "mismatches": reproduction.summary.mismatch,
                },
            )
        science = VecScientificAdmissionReport.model_validate(candidate)
        return VecArtifactInspection(
            capability_id="VEC-09",
            artifact_type="scientific_admission_report",
            status=science.status,
            artifact_fingerprint=science.fingerprint(),
            summary={
                "run_label": science.run_label,
                "scenario": science.scenario,
                "metric_count": len(science.metric_decisions),
                "rule_count": len(science.rule_readiness),
            },
        )
    except ValidationError as exc:
        raise VecInterfaceError(
            f"unsupported or invalid VEC artifact: {exc.error_count()} validation errors"
        ) from exc


def compare_vec_admissions(
    baseline: VecScientificAdmissionReport,
    variation: VecScientificAdmissionReport,
) -> VecAdmissionComparison:
    """Compare only compatible available scalar VEC-09 metric values."""

    left = baseline.evidence_pack.metric_collection.by_key()
    right = variation.evidence_pack.metric_collection.by_key()
    deltas: list[VecMetricDelta] = []
    incompatible: list[str] = []
    for key in sorted(set(left) | set(right)):
        before = left.get(key)
        after = right.get(key)
        if (
            before is None
            or after is None
            or before.status is not MetricStatus.AVAILABLE
            or after.status is not MetricStatus.AVAILABLE
            or before.unit != after.unit
            or before.scope != after.scope
            or not isinstance(before.value, (int, float))
            or isinstance(before.value, bool)
            or not isinstance(after.value, (int, float))
            or isinstance(after.value, bool)
        ):
            incompatible.append(key)
            continue
        deltas.append(
            VecMetricDelta(
                metric_key=key,
                unit=before.unit or "",
                scope=before.scope,
                baseline=before.value,
                variation=after.value,
                variation_minus_baseline=float(after.value) - float(before.value),
            )
        )
    return VecAdmissionComparison(
        baseline_run_label=baseline.run_label,
        variation_run_label=variation.run_label,
        baseline_report_fingerprint=baseline.fingerprint(),
        variation_report_fingerprint=variation.fingerprint(),
        comparable_metrics=tuple(deltas),
        unavailable_or_incompatible_metrics=tuple(incompatible),
    )


def export_vec_admission(
    report: VecScientificAdmissionReport,
    output_format: Literal["json", "csv", "markdown"],
) -> str:
    """Render an accepted VEC-09 report without recomputing scientific values."""

    if output_format == "json":
        return report.model_dump_json(indent=2) + "\n"
    metrics = report.evidence_pack.metric_collection.results
    if output_format == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("metric_key", "status", "value", "unit", "scope", "reason"))
        for metric in metrics:
            value = metric.value if isinstance(metric.value, (int, float, str)) else ""
            writer.writerow(
                (
                    metric.metric_key,
                    metric.status.value,
                    value,
                    metric.unit or "",
                    metric.scope,
                    "; ".join(metric.missing_evidence),
                )
            )
        return stream.getvalue()
    if output_format != "markdown":
        raise VecInterfaceError("VEC export format must be json, csv, or markdown")
    lines = [
        f"# VEC scientific admission — {report.run_label}",
        "",
        f"Scenario: `{report.scenario}`",
        "",
        "Deadline success is not physical completion. No threshold or finding was evaluated.",
        "",
        "| Metric | Status | Value | Unit |",
        "|---|---|---:|---|",
    ]
    for metric in metrics:
        value = metric.value if isinstance(metric.value, (int, float, str)) else "grouped"
        lines.append(
            f"| `{metric.metric_key}` | {metric.status.value} | {value} | {metric.unit or ''} |"
        )
    lines.extend(("", "## Rule readiness", ""))
    for rule in report.rule_readiness:
        lines.append(f"- **{rule.rule_id}**: {rule.status.value} — {rule.rationale}")
    return "\n".join(lines) + "\n"


def _repository_snapshot(
    path: Path,
    repository: Literal["vec_env", "tos-data"],
    audited_commit: str,
) -> VecRepositorySnapshot:
    git = shutil.which("git")
    if git is None:
        raise VecInterfaceError("git executable not found")
    root = path.resolve(strict=True)
    head = _git(git, root, "rev-parse", "HEAD").strip()
    origin = _git(git, root, "rev-parse", "refs/remotes/origin/main").strip()
    clean = not _git(git, root, "status", "--porcelain=v1", "--untracked-files=all")
    available = (
        subprocess.run(  # noqa: S603 - fixed read-only Git argv
            [git, "-C", str(root), "cat-file", "-e", f"{audited_commit}^{{commit}}"],
            check=False,
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )
    return VecRepositorySnapshot(
        repository=repository,
        audited_commit=audited_commit,
        worktree_head=head,
        origin_main=origin,
        clean=clean,
        audited_commit_available=available,
        ready_for_exact_blob_access=clean and available and origin == audited_commit,
    )


def _git(git: str, root: Path, *args: str) -> str:
    try:
        return subprocess.run(  # noqa: S603 - fixed read-only Git argv
            [git, "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        raise VecInterfaceError(f"could not inspect {root.name}: {exc.stderr.strip()}") from exc


def _operation(operation: VecOperationName, ready: bool, reason: str) -> VecOperationStatus:
    return VecOperationStatus(
        operation=operation,
        availability=(
            VecInterfaceAvailability.READY if ready else VecInterfaceAvailability.BLOCKED
        ),
        reason=reason,
    )


def _load_model(path: Path, model: type[VecRequestT]) -> VecRequestT:
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise VecInterfaceError(f"invalid {model.__name__}: {exc}") from exc

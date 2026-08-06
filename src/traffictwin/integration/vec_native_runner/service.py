"""Bounded read-only replay and joins for future-native VEC runner sidecars."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from traffictwin.domain.enums import Decision
from traffictwin.integration.vec_dispatch import (
    VecDispatchDecision,
    VecDispatchDisposition,
    VecDispatchError,
    VecDispatchRequest,
    dispatch_vec_batch,
)
from traffictwin.integration.vec_native_runner.models import (
    VecNativeFileRole,
    VecNativeRunnerManifest,
    VecNativeRunnerReport,
)
from traffictwin.integration.vec_runner import VecExecutionReceipt, VecTerminalStatus
from traffictwin.integration.vec_task_lifecycle import (
    VecTaskLifecycleError,
    VecTaskLifecycleEvent,
    VecTaskLifecycleEventKind,
    VecTaskNodeKind,
    validate_vec_task_lifecycle,
)

MAX_NATIVE_MANIFEST_BYTES = 1_000_000
MAX_NATIVE_FILE_BYTES = 256_000_000
MAX_NATIVE_TOTAL_BYTES = 512_000_000
MAX_NATIVE_JSONL_RECORDS = 1_000_000
MAX_NATIVE_JSONL_LINE_BYTES = 1_000_000

_ModelT = TypeVar("_ModelT", bound=BaseModel)


class VecNativeRunnerError(ValueError):
    """Typed fail-closed sidecar refusal with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def validate_vec_native_sidecar(
    sidecar_root: str | Path,
    runner_receipt: VecExecutionReceipt,
    *,
    manifest_file: str = "native-manifest.json",
) -> VecNativeRunnerReport:
    """Validate exact sidecar bytes, replay both contracts and join native task paths."""

    root = Path(sidecar_root)
    if root.is_symlink() or not root.resolve().is_dir():
        raise VecNativeRunnerError(
            "NATIVE_ROOT_INVALID", "sidecar root must be a direct readable directory"
        )
    resolved_root = root.resolve()
    manifest_path = _safe_file(resolved_root, _safe_relative(manifest_file, suffix=".json"))
    manifest_bytes = _bounded_read(manifest_path, MAX_NATIVE_MANIFEST_BYTES)
    try:
        manifest = VecNativeRunnerManifest.model_validate_json(manifest_bytes)
    except ValidationError as exc:
        raise VecNativeRunnerError(
            "NATIVE_MANIFEST_INVALID", "native sidecar manifest failed its strict contract"
        ) from exc
    _validate_runner_binding(manifest, runner_receipt)

    contents: dict[VecNativeFileRole, bytes] = {}
    bytes_read = len(manifest_bytes)
    for binding in manifest.files:
        path = _safe_file(resolved_root, binding.path)
        payload = _bounded_read(path, MAX_NATIVE_FILE_BYTES)
        if (
            len(payload) != binding.size_bytes
            or hashlib.sha256(payload).hexdigest() != binding.sha256
        ):
            raise VecNativeRunnerError(
                "NATIVE_FILE_IDENTITY_MISMATCH",
                f"{binding.role.value} bytes do not match the manifest",
            )
        bytes_read += len(payload)
        if bytes_read > MAX_NATIVE_TOTAL_BYTES:
            raise VecNativeRunnerError(
                "NATIVE_TOTAL_SIZE_INVALID", "combined sidecar bytes exceed the safety bound"
            )
        contents[binding.role] = payload

    events = _parse_jsonl(
        contents[VecNativeFileRole.LIFECYCLE_EVENTS],
        VecTaskLifecycleEvent,
        VecNativeFileRole.LIFECYCLE_EVENTS,
    )
    requests = _parse_jsonl(
        contents[VecNativeFileRole.DISPATCH_REQUESTS],
        VecDispatchRequest,
        VecNativeFileRole.DISPATCH_REQUESTS,
    )
    decisions = _parse_jsonl(
        contents[VecNativeFileRole.DISPATCH_DECISIONS],
        VecDispatchDecision,
        VecNativeFileRole.DISPATCH_DECISIONS,
    )
    try:
        lifecycle_report = validate_vec_task_lifecycle(events)
    except VecTaskLifecycleError as exc:
        raise VecNativeRunnerError("NATIVE_LIFECYCLE_INVALID", str(exc)) from exc
    if lifecycle_report.run_id != manifest.run_id:
        raise VecNativeRunnerError(
            "NATIVE_LIFECYCLE_RUN_MISMATCH", "lifecycle run does not match the manifest"
        )
    try:
        dispatch_report = dispatch_vec_batch(requests, manifest.dispatch_policy)
    except (VecDispatchError, ValidationError) as exc:
        raise VecNativeRunnerError("NATIVE_DISPATCH_INVALID", str(exc)) from exc
    ordered_decisions = tuple(sorted(decisions, key=lambda item: item.decision_order))
    if ordered_decisions != dispatch_report.decisions:
        raise VecNativeRunnerError(
            "NATIVE_DISPATCH_REPLAY_MISMATCH",
            "recorded dispatch decisions do not equal deterministic replay",
        )

    selected_count, unavailable_count = _join_lifecycle_and_dispatch(
        events,
        requests,
        ordered_decisions,
    )
    return VecNativeRunnerReport(
        run_id=manifest.run_id,
        manifest_fingerprint=manifest.fingerprint(),
        runner_receipt_fingerprint=runner_receipt.fingerprint(),
        producer_id=manifest.producer_id,
        producer_version=manifest.producer_version,
        producer_kind=manifest.producer_kind,
        semantics_status=manifest.semantics_status,
        bytes_read=bytes_read,
        lifecycle_report=lifecycle_report,
        dispatch_report=dispatch_report,
        v2i_task_count=len(requests),
        selected_path_count=selected_count,
        unavailable_rejection_count=unavailable_count,
    )


def _validate_runner_binding(
    manifest: VecNativeRunnerManifest,
    receipt: VecExecutionReceipt,
) -> None:
    if receipt.status is not VecTerminalStatus.COMPLETED or not receipt.published:
        raise VecNativeRunnerError(
            "NATIVE_RUNNER_RECEIPT_NOT_COMPLETED",
            "native sidecars require a successful published runner receipt",
        )
    if (
        manifest.run_id != receipt.request.run_id
        or manifest.runner_request_fingerprint != receipt.request_fingerprint
        or manifest.runner_output_fingerprint != receipt.output_fingerprint
        or manifest.runner_receipt_fingerprint != receipt.fingerprint()
    ):
        raise VecNativeRunnerError(
            "NATIVE_RUNNER_BINDING_MISMATCH",
            "manifest does not exact-bind the supplied runner receipt",
        )


def _join_lifecycle_and_dispatch(
    events: tuple[VecTaskLifecycleEvent, ...],
    requests: tuple[VecDispatchRequest, ...],
    decisions: tuple[VecDispatchDecision, ...],
) -> tuple[int, int]:
    by_task: dict[str, list[VecTaskLifecycleEvent]] = defaultdict(list)
    for event in events:
        by_task[event.task_id].append(event)
    v2i_task_ids = {
        event.task_id
        for event in events
        if event.kind is VecTaskLifecycleEventKind.ACTION_SELECTED and event.action is Decision.V2I
    }
    request_by_task = {request.task_id: request for request in requests}
    decision_by_task = {decision.task_id: decision for decision in decisions}
    if (
        set(request_by_task) != v2i_task_ids
        or set(decision_by_task) != v2i_task_ids
        or not v2i_task_ids
    ):
        raise VecNativeRunnerError(
            "NATIVE_V2I_TASK_SET_MISMATCH",
            "V2I lifecycle tasks must exactly match dispatch requests and decisions",
        )

    selected_count = 0
    unavailable_count = 0
    for task_id in sorted(v2i_task_ids):
        task_events = sorted(by_task[task_id], key=lambda item: item.sequence_index)
        request = request_by_task[task_id]
        decision = decision_by_task[task_id]
        ingress = _one(task_events, VecTaskLifecycleEventKind.INGRESS_ASSIGNED)
        if _node(ingress) != (VecTaskNodeKind.RSU, request.ingress_rsu_id):
            raise VecNativeRunnerError(
                "NATIVE_INGRESS_JOIN_MISMATCH",
                f"task {task_id!r} lifecycle ingress does not match dispatch request",
            )
        if decision.disposition is VecDispatchDisposition.NO_EXECUTION_TARGET:
            rejected = _one(task_events, VecTaskLifecycleEventKind.REJECTED)
            if _node(rejected) != (VecTaskNodeKind.RSU, request.ingress_rsu_id):
                raise VecNativeRunnerError(
                    "NATIVE_UNAVAILABLE_REJECTION_MISMATCH",
                    f"task {task_id!r} unavailable dispatch lacks ingress rejection",
                )
            unavailable_count += 1
            continue

        selected_id = decision.selected_rsu_id
        if selected_id is None:
            raise AssertionError("validated selected decision has no RSU")
        forwarded = [
            event for event in task_events if event.kind is VecTaskLifecycleEventKind.FORWARDED
        ]
        retained = [
            event for event in task_events if event.kind is VecTaskLifecycleEventKind.RETAINED
        ]
        if decision.forwarded:
            if (
                not forwarded
                or retained
                or _source(forwarded[0]) != (VecTaskNodeKind.RSU, request.ingress_rsu_id)
                or _node(forwarded[-1]) != (VecTaskNodeKind.RSU, selected_id)
            ):
                raise VecNativeRunnerError(
                    "NATIVE_FORWARD_PATH_MISMATCH",
                    f"task {task_id!r} forwarding path does not reach the selected RSU",
                )
        elif (
            forwarded
            or len(retained) != 1
            or _node(retained[0]) != (VecTaskNodeKind.RSU, selected_id)
        ):
            raise VecNativeRunnerError(
                "NATIVE_RETAINED_PATH_MISMATCH",
                f"task {task_id!r} retained path does not match the selected ingress RSU",
            )
        for event in task_events:
            if event.kind in {
                VecTaskLifecycleEventKind.EXECUTION_STARTED,
                VecTaskLifecycleEventKind.EXECUTION_COMPLETED,
                VecTaskLifecycleEventKind.DROPPED,
            } and _node(event) != (VecTaskNodeKind.RSU, selected_id):
                raise VecNativeRunnerError(
                    "NATIVE_EXECUTION_NODE_MISMATCH",
                    f"task {task_id!r} execution-path event does not match selected RSU",
                )
            if event.kind in {
                VecTaskLifecycleEventKind.RESULT_RETURNED,
                VecTaskLifecycleEventKind.RESULT_RETURN_FAILED,
            } and _source(event) != (VecTaskNodeKind.RSU, selected_id):
                raise VecNativeRunnerError(
                    "NATIVE_RETURN_SOURCE_MISMATCH",
                    f"task {task_id!r} return source does not match selected RSU",
                )
        selected_count += 1
    return selected_count, unavailable_count


def _parse_jsonl(
    payload: bytes, model: type[_ModelT], role: VecNativeFileRole
) -> tuple[_ModelT, ...]:
    lines = payload.splitlines()
    if not lines or len(lines) > MAX_NATIVE_JSONL_RECORDS:
        raise VecNativeRunnerError(
            "NATIVE_JSONL_COUNT_INVALID", f"{role.value} has an invalid record count"
        )
    records: list[_ModelT] = []
    for line_number, line in enumerate(lines, start=1):
        if not line or len(line) > MAX_NATIVE_JSONL_LINE_BYTES:
            raise VecNativeRunnerError(
                "NATIVE_JSONL_LINE_INVALID",
                f"{role.value} line {line_number} is empty or too large",
            )
        try:
            records.append(model.model_validate_json(line))
        except ValidationError as exc:
            raise VecNativeRunnerError(
                "NATIVE_JSONL_RECORD_INVALID",
                f"{role.value} line {line_number} failed its strict model",
            ) from exc
    return tuple(records)


def _one(
    events: list[VecTaskLifecycleEvent], kind: VecTaskLifecycleEventKind
) -> VecTaskLifecycleEvent:
    matching = [event for event in events if event.kind is kind]
    if len(matching) != 1:
        raise VecNativeRunnerError(
            "NATIVE_REQUIRED_EVENT_MISSING",
            f"task requires exactly one {kind.value} event",
        )
    return matching[0]


def _node(event: VecTaskLifecycleEvent) -> tuple[VecTaskNodeKind | None, str | None]:
    return event.node_kind, event.node_id


def _source(event: VecTaskLifecycleEvent) -> tuple[VecTaskNodeKind | None, str | None]:
    return event.source_node_kind, event.source_node_id


def _safe_relative(value: str, *, suffix: str) -> str:
    if len(value) > 256 or "\\" in value:
        raise VecNativeRunnerError(
            "NATIVE_PATH_INVALID", "sidecar path must be a bounded POSIX relative path"
        )
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.suffix.lower() != suffix
    ):
        raise VecNativeRunnerError("NATIVE_PATH_INVALID", "sidecar path is unsafe")
    return path.as_posix()


def _safe_file(root: Path, relative: str) -> Path:
    current = root
    for part in PurePosixPath(relative).parts:
        current /= part
        if current.is_symlink():
            raise VecNativeRunnerError(
                "NATIVE_SYMLINK_REFUSED", "symbolic-link sidecar paths are not accepted"
            )
    try:
        resolved = (root / relative).resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise VecNativeRunnerError(
            "NATIVE_FILE_INVALID", "sidecar file is missing or escapes its root"
        ) from exc
    if not resolved.is_file():
        raise VecNativeRunnerError("NATIVE_FILE_INVALID", "sidecar input must be a regular file")
    return resolved


def _bounded_read(path: Path, limit: int) -> bytes:
    with path.open("rb") as stream:
        payload = stream.read(limit + 1)
    if not payload or len(payload) > limit:
        raise VecNativeRunnerError(
            "NATIVE_FILE_SIZE_INVALID", f"{path.name} exceeds its declared safety bound"
        )
    return payload

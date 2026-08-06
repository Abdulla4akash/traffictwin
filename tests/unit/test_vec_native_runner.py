"""Digest, replay and lifecycle/dispatch join tests for native VEC sidecars."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import BaseModel

from traffictwin.integration.vec_dispatch import (
    VecDispatchCandidate,
    VecDispatchDecision,
    VecDispatchPolicy,
    VecDispatchRequest,
    dispatch_vec_batch,
)
from traffictwin.integration.vec_native_runner import (
    VecNativeFileBinding,
    VecNativeFileRole,
    VecNativeProducerKind,
    VecNativeRunnerError,
    VecNativeRunnerManifest,
    VecNativeSemanticsStatus,
    validate_vec_native_sidecar,
    vec_native_runner_contract,
)
from traffictwin.integration.vec_runner import (
    VecExecutionReceipt,
    VecRunnerFileEvidence,
    VecRunRequest,
    VecRuntimeEvidence,
    VecTerminalStatus,
)
from traffictwin.integration.vec_runner.models import output_fingerprint
from traffictwin.integration.vec_task_lifecycle import (
    VecTaskLifecycleEvent,
    VecTaskLifecycleEventKind,
    VecTaskNodeKind,
    build_two_rsu_handcheck_case,
)


def _runner_receipt(run_id: str) -> VecExecutionReceipt:
    request = VecRunRequest(
        run_id=run_id,
        trace_file="trace.npz",
        trace_sha256="a" * 64,
        actor_id="baseline_model_c_17",
        max_steps=2,
    )
    outputs = [
        VecRunnerFileEvidence(
            path="run.json",
            sha256="b" * 64,
            size_bytes=2,
            media_type="application/json",
            read_only=True,
        )
    ]
    return VecExecutionReceipt(
        status=VecTerminalStatus.COMPLETED,
        request=request,
        request_fingerprint=request.fingerprint(),
        preflight_fingerprint="c" * 64,
        argv=[],
        started_at_utc="2026-08-06T00:00:00Z",
        finished_at_utc="2026-08-06T00:00:01Z",
        elapsed_seconds=1.0,
        exit_code=0,
        timed_out=False,
        cancellation_requested=False,
        runtime=VecRuntimeEvidence(
            python="3.12.0",
            numpy="2.0.0",
            jax="0.4.30",
            jaxlib="0.4.30",
            jax_backend="cpu",
            jax_device_count=1,
            platform="test",
            machine="test",
            processor="test",
            environment_sha256="d" * 64,
        ),
        repositories=[],
        inputs_before=[],
        inputs_after=[],
        logs=[],
        stdout_excerpt="",
        stderr_excerpt="",
        outputs=outputs,
        findings=[],
        output_fingerprint=output_fingerprint(outputs),
        external_repositories_modified=False,
        raw_inputs_modified=False,
        published=True,
    )


def _request(task_id: str) -> VecDispatchRequest:
    return VecDispatchRequest(
        snapshot_id="snapshot-native-1",
        task_id=task_id,
        decision_order=0,
        ingress_rsu_id="rsu-a-strong-full",
        task_execution_slots=1,
        max_telemetry_age_ms=100,
        candidates=(
            VecDispatchCandidate(
                rsu_id="rsu-a-strong-full",
                link_quality_milliunits=900,
                execution_slot_limit=1,
                occupied_execution_slots=1,
                reserved_execution_slots=0,
                telemetry_age_ms=0,
                forwarding_ms=0,
                forwarding_energy_millijoules=0,
                predicted_queue_wait_ms=0,
                predicted_compute_ms=10,
                predicted_return_ms=5,
            ),
            VecDispatchCandidate(
                rsu_id="rsu-b-weaker-idle",
                link_quality_milliunits=600,
                execution_slot_limit=1,
                occupied_execution_slots=0,
                reserved_execution_slots=0,
                telemetry_age_ms=0,
                forwarding_ms=4,
                forwarding_energy_millijoules=400,
                predicted_queue_wait_ms=2,
                predicted_compute_ms=10,
                predicted_return_ms=5,
            ),
        ),
    )


def _jsonl(records: tuple[BaseModel, ...]) -> bytes:
    return b"".join(record.model_dump_json().encode() + b"\n" for record in records)


def _write_bundle(
    root: Path,
    receipt: VecExecutionReceipt,
    events: tuple[VecTaskLifecycleEvent, ...],
    requests: tuple[VecDispatchRequest, ...],
    decisions: tuple[VecDispatchDecision, ...],
    policy: VecDispatchPolicy,
) -> VecNativeRunnerManifest:
    payloads = {
        VecNativeFileRole.LIFECYCLE_EVENTS: ("lifecycle.jsonl", _jsonl(events)),
        VecNativeFileRole.DISPATCH_REQUESTS: ("dispatch-requests.jsonl", _jsonl(requests)),
        VecNativeFileRole.DISPATCH_DECISIONS: ("dispatch-decisions.jsonl", _jsonl(decisions)),
    }
    bindings = []
    for role, (name, payload) in payloads.items():
        (root / name).write_bytes(payload)
        bindings.append(
            VecNativeFileBinding(
                role=role,
                path=name,
                sha256=hashlib.sha256(payload).hexdigest(),
                size_bytes=len(payload),
            )
        )
    manifest = VecNativeRunnerManifest(
        run_id=receipt.request.run_id,
        producer_id="synthetic-test-producer",
        producer_version="1.0",
        producer_kind=VecNativeProducerKind.SYNTHETIC_FIXTURE,
        semantics_status=VecNativeSemanticsStatus.PROVISIONAL_DECLARED,
        dispatch_policy=policy,
        runner_request_fingerprint=receipt.request_fingerprint,
        runner_output_fingerprint=receipt.output_fingerprint,
        runner_receipt_fingerprint=receipt.fingerprint(),
        files=tuple(bindings),
    )
    (root / "native-manifest.json").write_text(
        manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def _selected_bundle(
    root: Path,
) -> tuple[VecExecutionReceipt, tuple[VecTaskLifecycleEvent, ...], VecDispatchRequest]:
    case = build_two_rsu_handcheck_case()
    receipt = _runner_receipt(case.run_id)
    request = _request(case.task_id)
    report = dispatch_vec_batch((request,), VecDispatchPolicy.LEAST_LOADED)
    _write_bundle(
        root,
        receipt,
        case.events,
        (request,),
        report.decisions,
        VecDispatchPolicy.LEAST_LOADED,
    )
    return receipt, case.events, request


def _rejected_events(run_id: str, task_id: str) -> tuple[VecTaskLifecycleEvent, ...]:
    origin = (VecTaskNodeKind.LOCAL_VEHICLE, "vehicle-reference-1")
    ingress = (VecTaskNodeKind.RSU, "rsu-a-strong-full")
    return (
        VecTaskLifecycleEvent(
            run_id=run_id,
            task_id=task_id,
            sequence_index=0,
            occurred_at_ms=0,
            kind=VecTaskLifecycleEventKind.OFFERED,
            node_kind=origin[0],
            node_id=origin[1],
        ),
        VecTaskLifecycleEvent(
            run_id=run_id,
            task_id=task_id,
            sequence_index=1,
            occurred_at_ms=0,
            kind=VecTaskLifecycleEventKind.ACTION_SELECTED,
            action="v2i",
        ),
        VecTaskLifecycleEvent(
            run_id=run_id,
            task_id=task_id,
            sequence_index=2,
            occurred_at_ms=0,
            kind=VecTaskLifecycleEventKind.INGRESS_ASSIGNED,
            node_kind=ingress[0],
            node_id=ingress[1],
        ),
        VecTaskLifecycleEvent(
            run_id=run_id,
            task_id=task_id,
            sequence_index=3,
            occurred_at_ms=2,
            kind=VecTaskLifecycleEventKind.REJECTED,
            node_kind=ingress[0],
            node_id=ingress[1],
            reason_code="NO_EXECUTION_TARGET",
        ),
        VecTaskLifecycleEvent(
            run_id=run_id,
            task_id=task_id,
            sequence_index=4,
            occurred_at_ms=2,
            kind=VecTaskLifecycleEventKind.DEADLINE_ASSESSED,
            deadline_met=False,
        ),
    )


def test_selected_native_sidecar_exact_binds_replays_and_joins(tmp_path: Path) -> None:
    receipt, _events, _request_value = _selected_bundle(tmp_path)

    report = validate_vec_native_sidecar(tmp_path, receipt)

    assert report.run_id == receipt.request.run_id
    assert report.runner_receipt_fingerprint == receipt.fingerprint()
    assert report.lifecycle_report.offered_count == 1
    assert report.lifecycle_report.returned_count == 1
    assert report.dispatch_report.selected_count == 1
    assert report.dispatch_report.forwarded_count == 1
    assert report.v2i_task_count == 1
    assert report.selected_path_count == 1
    assert report.unavailable_rejection_count == 0
    assert report.all_v2i_tasks_joined is True
    assert report.producer_authenticated is False
    assert report.current_pinned_evaluator_emits_sidecars is False
    assert report.scientific_evidence is False


def test_unavailable_dispatch_requires_explicit_lifecycle_rejection(tmp_path: Path) -> None:
    run_id = "synthetic-native-rejection"
    task_id = "task-rejected-1"
    receipt = _runner_receipt(run_id)
    events = _rejected_events(run_id, task_id)
    request = _request(task_id)
    dispatch = dispatch_vec_batch((request,), VecDispatchPolicy.STRONGEST_LINK_NO_FORWARDING)
    _write_bundle(
        tmp_path,
        receipt,
        events,
        (request,),
        dispatch.decisions,
        VecDispatchPolicy.STRONGEST_LINK_NO_FORWARDING,
    )

    report = validate_vec_native_sidecar(tmp_path, receipt)

    assert report.dispatch_report.unavailable_count == 1
    assert report.unavailable_rejection_count == 1
    assert report.selected_path_count == 0


def test_selected_dispatch_allows_explicit_return_failure(tmp_path: Path) -> None:
    case = build_two_rsu_handcheck_case()
    events = list(case.events)
    events[7] = events[7].model_copy(
        update={
            "kind": VecTaskLifecycleEventKind.RESULT_RETURN_FAILED,
            "reason_code": "RETURN_LINK_LOST",
        }
    )
    events[8] = events[8].model_copy(update={"deadline_met": False})
    receipt = _runner_receipt(case.run_id)
    request = _request(case.task_id)
    dispatch = dispatch_vec_batch((request,), VecDispatchPolicy.LEAST_LOADED)
    _write_bundle(
        tmp_path,
        receipt,
        tuple(events),
        (request,),
        dispatch.decisions,
        VecDispatchPolicy.LEAST_LOADED,
    )

    report = validate_vec_native_sidecar(tmp_path, receipt)

    assert report.lifecycle_report.return_failed_count == 1
    assert report.lifecycle_report.returned_count == 0
    assert report.selected_path_count == 1


def test_manifest_rejects_file_identity_drift(tmp_path: Path) -> None:
    receipt, _events, _request_value = _selected_bundle(tmp_path)
    path = tmp_path / "lifecycle.jsonl"
    payload = path.read_bytes()
    path.write_bytes(bytes([payload[0] ^ 1]) + payload[1:])

    with pytest.raises(VecNativeRunnerError, match="NATIVE_FILE_IDENTITY_MISMATCH"):
        validate_vec_native_sidecar(tmp_path, receipt)


def test_manifest_must_exact_bind_completed_runner_receipt(tmp_path: Path) -> None:
    receipt, _events, _request_value = _selected_bundle(tmp_path)
    manifest = VecNativeRunnerManifest.model_validate_json(
        (tmp_path / "native-manifest.json").read_bytes()
    )
    changed = manifest.model_copy(update={"runner_request_fingerprint": "e" * 64})
    (tmp_path / "native-manifest.json").write_text(
        changed.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )

    with pytest.raises(VecNativeRunnerError, match="NATIVE_RUNNER_BINDING_MISMATCH"):
        validate_vec_native_sidecar(tmp_path, receipt)

    failed = receipt.model_copy(update={"status": VecTerminalStatus.FAILED, "published": False})
    with pytest.raises(VecNativeRunnerError, match="NATIVE_RUNNER_RECEIPT_NOT_COMPLETED"):
        validate_vec_native_sidecar(tmp_path, failed)


def test_recorded_dispatch_must_equal_deterministic_replay(tmp_path: Path) -> None:
    receipt, events, request = _selected_bundle(tmp_path)
    dispatch = dispatch_vec_batch((request,), VecDispatchPolicy.LEAST_LOADED)
    changed = dispatch.decisions[0].model_copy(
        update={"selected_forwarding_energy_millijoules": 401}
    )
    _write_bundle(
        tmp_path,
        receipt,
        events,
        (request,),
        (changed,),
        VecDispatchPolicy.LEAST_LOADED,
    )

    with pytest.raises(VecNativeRunnerError, match="NATIVE_DISPATCH_REPLAY_MISMATCH"):
        validate_vec_native_sidecar(tmp_path, receipt)


def test_v2i_task_sets_must_match_dispatch_artifacts(tmp_path: Path) -> None:
    receipt, events, request = _selected_bundle(tmp_path)
    changed_events = tuple(event.model_copy(update={"task_id": "task-other"}) for event in events)
    dispatch = dispatch_vec_batch((request,), VecDispatchPolicy.LEAST_LOADED)
    _write_bundle(
        tmp_path,
        receipt,
        changed_events,
        (request,),
        dispatch.decisions,
        VecDispatchPolicy.LEAST_LOADED,
    )

    with pytest.raises(VecNativeRunnerError, match="NATIVE_V2I_TASK_SET_MISMATCH"):
        validate_vec_native_sidecar(tmp_path, receipt)


def test_lifecycle_forward_path_must_reach_selected_execution_rsu(tmp_path: Path) -> None:
    receipt, events, request = _selected_bundle(tmp_path)
    changed_events = list(events)
    changed_events[4] = changed_events[4].model_copy(update={"node_id": "rsu-c-other"})
    changed_events[5] = changed_events[5].model_copy(update={"node_id": "rsu-c-other"})
    changed_events[6] = changed_events[6].model_copy(update={"node_id": "rsu-c-other"})
    changed_events[7] = changed_events[7].model_copy(update={"source_node_id": "rsu-c-other"})
    dispatch = dispatch_vec_batch((request,), VecDispatchPolicy.LEAST_LOADED)
    _write_bundle(
        tmp_path,
        receipt,
        tuple(changed_events),
        (request,),
        dispatch.decisions,
        VecDispatchPolicy.LEAST_LOADED,
    )

    with pytest.raises(VecNativeRunnerError, match="NATIVE_FORWARD_PATH_MISMATCH"):
        validate_vec_native_sidecar(tmp_path, receipt)


def test_symlink_and_unsafe_manifest_paths_are_refused(tmp_path: Path) -> None:
    receipt, _events, _request_value = _selected_bundle(tmp_path)
    decision_path = tmp_path / "dispatch-decisions.jsonl"
    target = tmp_path / "decision-target.jsonl"
    target.write_bytes(decision_path.read_bytes())
    decision_path.unlink()
    decision_path.symlink_to(target)

    with pytest.raises(VecNativeRunnerError, match="NATIVE_SYMLINK_REFUSED"):
        validate_vec_native_sidecar(tmp_path, receipt)
    with pytest.raises(VecNativeRunnerError, match="NATIVE_PATH_INVALID"):
        validate_vec_native_sidecar(tmp_path, receipt, manifest_file="../native-manifest.json")


def test_contract_refuses_legacy_inference_and_scientific_claims() -> None:
    contract = vec_native_runner_contract()

    assert contract.runner_receipt_binding_required is True
    assert contract.lifecycle_replay_required is True
    assert contract.dispatcher_replay_required is True
    assert contract.current_pinned_evaluator_emits_sidecars is False
    assert contract.legacy_array_inference_allowed is False
    assert contract.producer_authenticated is False
    assert contract.scientific_evidence is False
    assert contract.fingerprint() == vec_native_runner_contract().fingerprint()

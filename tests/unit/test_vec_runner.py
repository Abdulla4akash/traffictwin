from __future__ import annotations

import hashlib
import io
import threading
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from traffictwin.integration.vec_runner import (
    PINNED_ACTORS,
    PINNED_EVALUATOR_FILES,
    PINNED_TOS_DATA_COMMIT,
    PINNED_VEC_ENV_COMMIT,
    VecRunnerError,
    VecRunnerPreflightStatus,
    VecRunRequest,
    VecTerminalStatus,
    preflight_vec_run,
    run_vec_evaluator,
    service,
    vec_runner_contract,
)
from traffictwin.integration.vec_runner.models import (
    PINNED_REVIEWED_TRACES,
    VecRunnerFileEvidence,
    VecRuntimeEvidence,
)

TRACE_HASH = "a2612865f5e1ef6d066975d6430693225f5d16060f139176548c8ae020e428be"
INC_TRACE_HASH = "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"
EV_TRACE_HASH = "70d6d12f3004b08c8a17e450df04ea70e74723c7a25149d3f5e1629903d01208"


def test_reviewed_allowlist_holds_exactly_the_three_admitted_gate_a_traces() -> None:
    assert PINNED_REVIEWED_TRACES[TRACE_HASH] == "traces/trace_we_fullrsu.npz"
    assert PINNED_REVIEWED_TRACES[INC_TRACE_HASH] == "traces/trace_inc_fullrsu.npz"
    assert PINNED_REVIEWED_TRACES[EV_TRACE_HASH] == "traces/trace_ev_fullrsu.npz"
    assert len(PINNED_REVIEWED_TRACES) == 3


def _request(**changes: object) -> VecRunRequest:
    payload: dict[str, object] = {
        "run_id": "unit-run",
        "trace_file": "trace.npz",
        "trace_sha256": TRACE_HASH,
        "actor_id": "ukfleettrain_mappo_model_c_17",
        "max_steps": 2,
    }
    payload.update(changes)
    return VecRunRequest.model_validate(payload)


def _actor_bytes() -> bytes:
    output = io.BytesIO()
    arrays: dict[str, object] = {
        "Dense_0.bias": np.zeros(64, dtype=np.float32),
        "Dense_0.kernel": np.zeros((17, 64), dtype=np.float32),
        "Dense_1.bias": np.zeros(64, dtype=np.float32),
        "Dense_1.kernel": np.zeros((64, 64), dtype=np.float32),
        "Dense_2.bias": np.zeros(3, dtype=np.float32),
        "Dense_2.kernel": np.zeros((64, 3), dtype=np.float32),
    }
    np.savez(output, **arrays)  # type: ignore[arg-type]
    return output.getvalue()


def _file(path: str, payload: bytes = b"x") -> VecRunnerFileEvidence:
    return service._file_evidence(path, payload, read_only=True)


def _repository_state(name: str, *, clean: bool = True) -> service._RepositoryState:
    if name == "vec_env":
        commit = PINNED_VEC_ENV_COMMIT
        blobs = {
            "eval/eval_sumo_stage1_mc.py": b"print('fixture')\n",
            "jaxmarl/env/vec_jax.py": b"# fixture\n",
        }
    else:
        commit = PINNED_TOS_DATA_COMMIT
        actor_path = PINNED_ACTORS["ukfleettrain_mappo_model_c_17"][0]
        blobs = {actor_path: _actor_bytes()}
    return service._RepositoryState(
        name=name,  # type: ignore[arg-type]
        audited_commit=commit,
        head="1" * 40,
        origin_main=commit,
        clean=clean,
        blobs=blobs,
        files=tuple(_file(f"source/{name}/{path}", blob) for path, blob in blobs.items()),
    )


def _runtime() -> VecRuntimeEvidence:
    return VecRuntimeEvidence(
        python="3.12.0",
        numpy="2.0.0",
        jax="0.4.30",
        jaxlib="0.4.30",
        jax_backend="cpu",
        jax_device_count=1,
        platform="test",
        machine="test",
        processor="test",
        environment_sha256="2" * 64,
    )


def _input_state(root: Path) -> service._InputState:
    trace = root / "trace.npz"
    if not trace.exists():
        trace.write_bytes(b"trace")
    evidence = (_file("inputs/trace.npz", b"trace"),)
    return service._InputState(root.resolve(), trace.resolve(), None, evidence, 10, 2)


@pytest.fixture
def admitted_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    input_root = tmp_path / "inputs"
    input_root.mkdir()

    def inspect_repository(
        _repo: Path, name: str, _commit: str, _files: dict[str, str]
    ) -> service._RepositoryState:
        return _repository_state(name)

    monkeypatch.setattr(service, "_inspect_repository", inspect_repository)
    monkeypatch.setattr(
        service, "_inspect_inputs", lambda _root, _request: _input_state(input_root)
    )
    monkeypatch.setattr(service, "_inspect_runtime", _runtime)
    return input_root


def test_request_and_contract_are_closed_path_safe_and_fingerprinted() -> None:
    request = _request()
    contract = vec_runner_contract()

    assert request.fingerprint() == request.fingerprint()
    assert contract.audited_commits == {
        "vec_env": PINNED_VEC_ENV_COMMIT,
        "tos-data": PINNED_TOS_DATA_COMMIT,
    }
    assert contract.source_files == PINNED_EVALUATOR_FILES
    assert "--cap-scalar" not in contract.allowed_flags
    assert "--out-json" in contract.allowed_flags
    assert contract.fingerprint() == contract.fingerprint()

    for unsafe in ("../trace.npz", "/tmp/trace.npz", "folder\\trace.npz"):  # noqa: S108
        with pytest.raises(ValidationError):
            _request(trace_file=unsafe)
    with pytest.raises(ValidationError):
        _request(fleet="unknown")
    with pytest.raises(ValidationError):
        _request(preprocessing_receipt_file="receipt.json")


def test_actor_validator_enforces_exact_audited_architecture() -> None:
    service._validate_actor(_actor_bytes())

    malformed = io.BytesIO()
    np.savez(malformed, unexpected=np.zeros(1, dtype=np.float32))
    with pytest.raises(VecRunnerError, match="actor keys"):
        service._validate_actor(malformed.getvalue())


def test_input_inspection_rejects_unreviewed_trace_without_vec06_receipt(tmp_path: Path) -> None:
    trace = tmp_path / "trace.npz"
    trace.write_bytes(b"not-a-reviewed-trace")
    request = _request(trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest())

    with pytest.raises(VecRunnerError, match="neither reviewed nor backed"):
        service._inspect_inputs(tmp_path, request)

    target = tmp_path / "target.npz"
    target.write_bytes(b"x")
    trace.unlink()
    trace.symlink_to(target)
    request = _request(trace_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    with pytest.raises(VecRunnerError, match="symbolic-link"):
        service._inspect_inputs(tmp_path, request)


def test_preflight_is_read_only_and_accepts_only_complete_evidence(
    admitted_runtime: Path,
) -> None:
    report = preflight_vec_run(
        admitted_runtime,
        admitted_runtime,
        admitted_runtime,
        _request(),
    )

    assert report.status is VecRunnerPreflightStatus.ACCEPTED
    assert report.read_only is True
    assert report.mutations_performed is False
    assert report.trace_steps == 10
    assert report.trace_slots == 2
    assert [finding.code for finding in report.findings] == [
        "VEC_PINNED_SOURCES_CONFIRMED",
        "VEC_TRACE_CONTRACT_CONFIRMED",
        "VEC_ACTOR_ARCHITECTURE_CONFIRMED",
        "VEC_CPU_RUNTIME_CONFIRMED",
    ]


def test_preflight_distinguishes_dirty_source_from_missing_runtime(
    admitted_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        service,
        "_inspect_repository",
        lambda _repo, name, _commit, _files: _repository_state(name, clean=False),
    )
    dirty = preflight_vec_run(admitted_runtime, admitted_runtime, admitted_runtime, _request())
    assert dirty.status is VecRunnerPreflightStatus.REJECTED
    assert {finding.code for finding in dirty.findings} == {"VEC_SOURCE_DIRTY"}

    monkeypatch.setattr(
        service,
        "_inspect_repository",
        lambda _repo, name, _commit, _files: _repository_state(name),
    )
    monkeypatch.setattr(
        service,
        "_inspect_runtime",
        lambda: (_ for _ in ()).throw(VecRunnerError("missing runtime")),
    )
    unavailable = preflight_vec_run(
        admitted_runtime, admitted_runtime, admitted_runtime, _request()
    )
    assert unavailable.status is VecRunnerPreflightStatus.UNAVAILABLE
    assert [finding.code for finding in unavailable.findings] == ["VEC_RUNTIME_UNAVAILABLE"]


class _FakeProcess:
    def __init__(self, argv: list[str], **_kwargs: object) -> None:
        self.argv = argv
        self.pid = 999_999
        self.returncode: int | None = None
        for flag, content in (
            ("--out-json", b"{}"),
            ("--per-step-out", b"step"),
            ("--per-task-out", b"task"),
        ):
            Path(argv[argv.index(flag) + 1]).write_bytes(content)

    def poll(self) -> int | None:
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def communicate(self, timeout: int) -> tuple[str, str]:
        del timeout
        return "fixture stdout", ""


def test_success_is_atomic_new_only_and_receipted(
    admitted_runtime: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("traffictwin.integration.vec_runner.service.subprocess.Popen", _FakeProcess)
    monkeypatch.setattr(service, "_validate_outputs", lambda *_args: None)
    destination = tmp_path / "published"

    receipt = run_vec_evaluator(
        admitted_runtime,
        admitted_runtime,
        admitted_runtime,
        destination,
        _request(),
    )

    assert receipt.status is VecTerminalStatus.COMPLETED
    assert receipt.published is True
    assert receipt.external_repositories_modified is False
    assert receipt.raw_inputs_modified is False
    assert receipt.inputs_before == receipt.inputs_after
    assert receipt.stdout_excerpt == "fixture stdout"
    assert receipt.stderr_excerpt == ""
    assert [item.path for item in receipt.outputs] == ["per-step.npz", "per-task.npz", "run.json"]
    assert (destination / "execution_receipt.json").is_file()
    with pytest.raises(VecRunnerError, match="must not already exist"):
        run_vec_evaluator(
            admitted_runtime,
            admitted_runtime,
            admitted_runtime,
            destination,
            _request(),
        )


def test_malformed_output_never_publishes(
    admitted_runtime: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("traffictwin.integration.vec_runner.service.subprocess.Popen", _FakeProcess)
    monkeypatch.setattr(
        service,
        "_validate_outputs",
        lambda *_args: (_ for _ in ()).throw(VecRunnerError("malformed output")),
    )
    destination = tmp_path / "rejected"

    with pytest.raises(VecRunnerError) as raised:
        run_vec_evaluator(
            admitted_runtime,
            admitted_runtime,
            admitted_runtime,
            destination,
            _request(),
        )

    assert raised.value.receipt is not None
    assert raised.value.receipt.status is VecTerminalStatus.FAILED
    assert raised.value.receipt.published is False
    assert raised.value.receipt.stdout_excerpt == "fixture stdout"
    assert not destination.exists()


def test_source_drift_after_execution_is_recorded_and_never_published(
    admitted_runtime: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"vec_env": 0, "tos-data": 0}

    def changing_repository(
        _repo: Path, name: str, _commit: str, _files: dict[str, str]
    ) -> service._RepositoryState:
        calls[name] += 1
        return _repository_state(name, clean=calls[name] <= 2)

    monkeypatch.setattr(service, "_inspect_repository", changing_repository)
    monkeypatch.setattr("traffictwin.integration.vec_runner.service.subprocess.Popen", _FakeProcess)
    monkeypatch.setattr(service, "_validate_outputs", lambda *_args: None)
    destination = tmp_path / "drifted"

    with pytest.raises(VecRunnerError) as raised:
        run_vec_evaluator(
            admitted_runtime,
            admitted_runtime,
            admitted_runtime,
            destination,
            _request(),
        )

    assert raised.value.receipt is not None
    assert raised.value.receipt.status is VecTerminalStatus.FAILED
    assert raised.value.receipt.external_repositories_modified is True
    assert not destination.exists()


class _WaitingProcess(_FakeProcess):
    def poll(self) -> int | None:
        return self.returncode


def test_cancellation_is_terminal_and_never_publishes(
    admitted_runtime: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = threading.Event()
    event.set()
    monkeypatch.setattr(
        "traffictwin.integration.vec_runner.service.subprocess.Popen", _WaitingProcess
    )
    monkeypatch.setattr(
        service,
        "_terminate_process_group",
        lambda process: setattr(process, "returncode", -15),
    )

    with pytest.raises(VecRunnerError) as raised:
        run_vec_evaluator(
            admitted_runtime,
            admitted_runtime,
            admitted_runtime,
            tmp_path / "cancelled",
            _request(),
            cancellation_event=event,
        )

    assert raised.value.receipt is not None
    assert raised.value.receipt.status is VecTerminalStatus.CANCELLED
    assert raised.value.receipt.cancellation_requested is True
    assert not (tmp_path / "cancelled").exists()


def test_timeout_is_terminal_and_never_publishes(
    admitted_runtime: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = iter((100.0, 100.0, 102.0, 103.0))
    monkeypatch.setattr(
        "traffictwin.integration.vec_runner.service.time.monotonic", lambda: next(clock)
    )
    monkeypatch.setattr(
        "traffictwin.integration.vec_runner.service.subprocess.Popen", _WaitingProcess
    )
    monkeypatch.setattr(
        service,
        "_terminate_process_group",
        lambda process: setattr(process, "returncode", -15),
    )

    with pytest.raises(VecRunnerError) as raised:
        run_vec_evaluator(
            admitted_runtime,
            admitted_runtime,
            admitted_runtime,
            tmp_path / "timed-out",
            _request(timeout_seconds=1),
        )

    assert raised.value.receipt is not None
    assert raised.value.receipt.status is VecTerminalStatus.TIMED_OUT
    assert raised.value.receipt.timed_out is True
    assert not (tmp_path / "timed-out").exists()


def test_destination_cannot_overlap_inputs(
    admitted_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("traffictwin.integration.vec_runner.service.subprocess.Popen", _FakeProcess)
    monkeypatch.setattr(service, "_validate_outputs", lambda *_args: None)

    with pytest.raises(VecRunnerError, match="must not overlap"):
        run_vec_evaluator(
            admitted_runtime,
            admitted_runtime,
            admitted_runtime,
            admitted_runtime / "outputs",
            _request(),
        )

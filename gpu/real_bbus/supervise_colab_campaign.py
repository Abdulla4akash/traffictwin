# ruff: noqa: S603
"""Run and recover a checkpointed B-BUS campaign through the Colab CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gpu.real_bbus.monitor_colab_checkpoints import (
    MODEL_SEEDS,
    _remote_names,
    mirror_once,
    validate_download,
)


def _event(message: str) -> None:
    print(f"[{datetime.now(UTC).isoformat()}] {message}", flush=True)


def _run(command: list[str], *, timeout: float = 900.0) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.stdout.strip():
        _event(completed.stdout.strip())
    if completed.returncode != 0 and completed.stderr.strip():
        _event(completed.stderr.strip())
    return completed


def _stop(colab: Path, session: str) -> None:
    stopped = _run([str(colab), "stop", "--session", session], timeout=120.0)
    if stopped.returncode != 0:
        _event(f"session stop was not confirmed for {session}")


def _progress(local_root: Path) -> dict[int, int]:
    progress: dict[int, int] = {}
    for seed in MODEL_SEEDS:
        checkpoint = local_root / f"model-seed-{seed}.checkpoint.zip"
        status = Path(str(checkpoint) + ".json")
        if checkpoint.is_file() and status.is_file():
            value = validate_download(checkpoint, status)
            progress[seed] = int(value["next_update"])
    return progress


def _validated_returned_result(local_root: Path) -> dict[str, object] | None:
    """Return an already downloaded result without allocating another GPU."""

    status_path = local_root / "supervisor_result.json"
    if not status_path.is_file():
        return None
    value = json.loads(status_path.read_text(encoding="utf-8"))
    required = {
        "status",
        "attempt",
        "result",
        "result_bytes",
        "result_sha256",
        "initial_checkpoint_progress",
        "final_checkpoint_progress",
    }
    if set(value) != required or value.get("status") != "returned":
        raise ValueError("existing supervisor result is not a returned campaign record")
    result = Path(str(value["result"])).resolve()
    if result.parent != local_root.resolve() or not result.is_file():
        raise ValueError("existing supervisor result points outside the local run root")
    if result.stat().st_size != value["result_bytes"]:
        raise ValueError("existing returned campaign byte count differs")
    digest = hashlib.sha256(result.read_bytes()).hexdigest()
    if digest != value["result_sha256"]:
        raise ValueError("existing returned campaign digest differs")
    with zipfile.ZipFile(result) as archive:
        if archive.testzip() is not None:
            raise ValueError("existing returned campaign ZIP failed CRC verification")
    return value


def _upload_bootstrap(*, colab: Path, session: str, pack: Path, local_root: Path) -> None:
    uploads = [(pack, f"/content/{pack.name}")]
    for seed in MODEL_SEEDS:
        checkpoint = local_root / f"model-seed-{seed}.checkpoint.zip"
        status = Path(str(checkpoint) + ".json")
        if checkpoint.is_file() and status.is_file():
            validate_download(checkpoint, status)
            uploads.extend(
                [
                    (checkpoint, f"/content/{checkpoint.name}"),
                    (status, f"/content/{status.name}"),
                ]
            )
    for local, remote in uploads:
        uploaded = _run(
            [
                str(colab),
                "upload",
                "--session",
                session,
                str(local),
                remote,
            ],
            timeout=900.0,
        )
        if uploaded.returncode != 0:
            raise RuntimeError(f"upload failed: {local.name}")


def _download_result(
    *,
    colab: Path,
    session: str,
    remote_result: str,
    local_root: Path,
) -> Path | None:
    remote = Path(remote_result)
    names = _remote_names(colab, session, remote.parent.as_posix())
    if names is None or remote.name not in names:
        return None
    local = local_root / remote.name
    temporary = local.with_suffix(local.suffix + ".download")
    downloaded = _run(
        [
            str(colab),
            "download",
            "--session",
            session,
            remote.as_posix(),
            str(temporary),
        ],
        timeout=1800.0,
    )
    if downloaded.returncode != 0:
        temporary.unlink(missing_ok=True)
        return None
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            temporary.unlink(missing_ok=True)
            raise ValueError("returned campaign ZIP failed CRC verification")
    os.replace(temporary, local)
    return local


def supervise(
    *,
    colab: Path,
    pack: Path,
    entrypoint: Path,
    local_root: Path,
    session_prefix: str,
    remote_output: str,
    remote_result: str,
    poll_seconds: float,
    max_attempts: int,
) -> dict[str, object]:
    local_root.mkdir(parents=True, exist_ok=True)
    returned = _validated_returned_result(local_root)
    if returned is not None:
        _event("existing validated campaign result reused; no Colab session created")
        return returned
    initial_progress = _progress(local_root)
    stagnant_attempts = 0
    for attempt in range(1, max_attempts + 1):
        session = f"{session_prefix}-a{attempt}"
        before = _progress(local_root)
        _event(f"attempt={attempt} session={session} checkpoint_progress={before}")
        created = _run(
            [str(colab), "new", "--session", session, "--gpu", "G4"],
            timeout=300.0,
        )
        if created.returncode != 0:
            raise RuntimeError(f"could not create G4 session {session}")
        execution: subprocess.Popen[str] | None = None
        try:
            _upload_bootstrap(
                colab=colab,
                session=session,
                pack=pack,
                local_root=local_root,
            )
            attempt_log = local_root / f"{session}.exec.log"
            with attempt_log.open("a", encoding="utf-8") as log:
                remote_output_seen = False
                consecutive_missing_output = 0
                execution = subprocess.Popen(
                    [
                        str(colab),
                        "exec",
                        "--session",
                        session,
                        "--file",
                        str(entrypoint),
                        "--timeout",
                        "43200",
                    ],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                while execution.poll() is None:
                    try:
                        mirrored = mirror_once(
                            colab=colab,
                            session=session,
                            remote_output=remote_output,
                            local_root=local_root,
                        )
                    except ValueError as exc:
                        _event(
                            "checkpoint transfer validation failed without stopping "
                            f"the live training session: {exc}"
                        )
                        mirrored = {"downloaded": [], "available": True}
                    if mirrored["available"]:
                        remote_output_seen = True
                        consecutive_missing_output = 0
                    elif remote_output_seen:
                        consecutive_missing_output += 1
                        _event(
                            "remote campaign output missing after it was observed: "
                            f"consecutive_checks={consecutive_missing_output}"
                        )
                        if consecutive_missing_output >= 3:
                            raise RuntimeError(
                                "remote campaign output disappeared for three checks"
                            )
                    for item in mirrored["downloaded"]:
                        _event(
                            f"mirrored seed={item['seed']} "
                            f"next_update={item['next_update']} bytes={item['bytes']}"
                        )
                    result = _download_result(
                        colab=colab,
                        session=session,
                        remote_result=remote_result,
                        local_root=local_root,
                    )
                    if result is not None:
                        execution.wait(timeout=120.0)
                        digest = hashlib.sha256(result.read_bytes()).hexdigest()
                        _event(f"campaign result returned: {result} sha256={digest}")
                        return {
                            "status": "returned",
                            "attempt": attempt,
                            "result": str(result),
                            "result_bytes": result.stat().st_size,
                            "result_sha256": digest,
                            "initial_checkpoint_progress": initial_progress,
                            "final_checkpoint_progress": _progress(local_root),
                        }
                    time.sleep(poll_seconds)
            result = _download_result(
                colab=colab,
                session=session,
                remote_result=remote_result,
                local_root=local_root,
            )
            if result is not None:
                digest = hashlib.sha256(result.read_bytes()).hexdigest()
                return {
                    "status": "returned",
                    "attempt": attempt,
                    "result": str(result),
                    "result_bytes": result.stat().st_size,
                    "result_sha256": digest,
                    "initial_checkpoint_progress": initial_progress,
                    "final_checkpoint_progress": _progress(local_root),
                }
        except RuntimeError as exc:
            _event(f"attempt ended: {type(exc).__name__}: {exc}")
        finally:
            if execution is not None and execution.poll() is None:
                execution.terminate()
                try:
                    execution.wait(timeout=10.0)
                except subprocess.TimeoutExpired:
                    execution.kill()
            _stop(colab, session)
        after = _progress(local_root)
        if after == before:
            stagnant_attempts += 1
        else:
            stagnant_attempts = 0
        if stagnant_attempts >= 2:
            raise RuntimeError("two consecutive attempts ended without any new durable checkpoint")
    raise RuntimeError(f"campaign did not return within {max_attempts} G4 attempts")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--entrypoint", type=Path, required=True)
    parser.add_argument("--local-root", type=Path, required=True)
    parser.add_argument("--session-prefix", required=True)
    parser.add_argument("--remote-output", required=True)
    parser.add_argument("--remote-result", required=True)
    parser.add_argument("--colab", type=Path, default=Path.home() / ".local/bin/colab")
    parser.add_argument("--poll-seconds", type=float, default=30.0)
    parser.add_argument("--max-attempts", type=int, default=5)
    args = parser.parse_args(argv)
    if args.poll_seconds <= 0 or args.max_attempts < 1:
        parser.error("poll seconds and max attempts must be positive")
    try:
        result = supervise(
            colab=args.colab.resolve(),
            pack=args.pack.resolve(),
            entrypoint=args.entrypoint.resolve(),
            local_root=args.local_root.resolve(),
            session_prefix=args.session_prefix,
            remote_output=args.remote_output,
            remote_result=args.remote_result,
            poll_seconds=args.poll_seconds,
            max_attempts=args.max_attempts,
        )
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    result_path = args.local_root.resolve() / "supervisor_result.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ruff: noqa: S603
"""Mirror atomic B-BUS checkpoints from a named Colab CLI session."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any

MODEL_SEEDS = (30, 31, 32, 33, 34)
CHECKPOINT_SCHEMA = "bbus-update-checkpoint-1.0"
STATUS_SCHEMA = "bbus-update-checkpoint-status-1.0"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_download(checkpoint: Path, status_path: Path) -> dict[str, Any]:
    """Validate a downloaded checkpoint against both of its hash layers."""

    status = json.loads(status_path.read_text(encoding="utf-8"))
    expected_status_keys = {
        "schema_version",
        "checkpoint_filename",
        "checkpoint_bytes",
        "checkpoint_sha256",
        "next_update",
        "total_env_steps",
    }
    if set(status) != expected_status_keys or status["schema_version"] != STATUS_SCHEMA:
        raise ValueError("checkpoint status schema or keys differ")
    if status["checkpoint_filename"] != checkpoint.name:
        raise ValueError("checkpoint status names a different archive")
    if status["checkpoint_bytes"] != checkpoint.stat().st_size:
        raise ValueError("checkpoint byte count differs from its status")
    if status["checkpoint_sha256"] != _sha256(checkpoint):
        raise ValueError("checkpoint digest differs from its status")
    with zipfile.ZipFile(checkpoint) as archive:
        expected_names = {"device.msgpack", "host.npz", "curve.csv", "manifest.json"}
        if set(archive.namelist()) != expected_names or archive.testzip() is not None:
            raise ValueError("checkpoint ZIP inventory or CRC differs")
        values = {name: archive.read(name) for name in expected_names}
    manifest = json.loads(values["manifest.json"])
    if manifest.get("schema_version") != CHECKPOINT_SCHEMA:
        raise ValueError("checkpoint manifest schema differs")
    if manifest.get("next_update") != status["next_update"]:
        raise ValueError("checkpoint update differs from its status")
    if manifest.get("total_env_steps") != status["total_env_steps"]:
        raise ValueError("checkpoint environment steps differ from its status")
    for name in ("device.msgpack", "host.npz", "curve.csv"):
        value = values[name]
        observed = {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
        if manifest.get("components", {}).get(name) != observed:
            raise ValueError(f"checkpoint component changed: {name}")
    return status


def _colab(
    colab: Path, arguments: list[str], *, timeout: float = 120.0
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(colab), *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _remote_names(colab: Path, session: str, remote_dir: str) -> set[str] | None:
    listed = _colab(colab, ["ls", "--session", session, remote_dir])
    if listed.returncode != 0:
        return None
    return {line.strip().removesuffix("/") for line in listed.stdout.splitlines() if line.strip()}


def _download(
    colab: Path, session: str, remote: str, local: Path
) -> subprocess.CompletedProcess[str]:
    return _colab(
        colab,
        ["download", "--session", session, remote, str(local)],
        timeout=600.0,
    )


def mirror_once(
    *,
    colab: Path,
    session: str,
    remote_output: str,
    local_root: Path,
) -> dict[str, Any]:
    """Mirror every newer seed checkpoint available in one live session."""

    names = _remote_names(colab, session, remote_output)
    if names is None:
        status = _colab(colab, ["status", "--session", session])
        if status.returncode != 0:
            raise RuntimeError("Colab session is unavailable")
        return {"downloaded": [], "available": False}
    local_root.mkdir(parents=True, exist_ok=True)
    downloaded: list[dict[str, Any]] = []
    for seed in MODEL_SEEDS:
        archive_name = f"model-seed-{seed}.checkpoint.zip"
        status_name = archive_name + ".json"
        if archive_name not in names or status_name not in names:
            continue
        temporary_status = local_root / (status_name + ".download")
        remote_status = f"{remote_output.rstrip('/')}/{status_name}"
        status_result = _download(colab, session, remote_status, temporary_status)
        if status_result.returncode != 0:
            temporary_status.unlink(missing_ok=True)
            continue
        candidate = json.loads(temporary_status.read_text(encoding="utf-8"))
        local_archive = local_root / archive_name
        local_status = local_root / status_name
        if (
            local_archive.is_file()
            and local_status.is_file()
            and candidate.get("checkpoint_sha256") == _sha256(local_archive)
        ):
            temporary_status.unlink()
            continue
        temporary_archive = local_root / (archive_name + ".download")
        remote_archive = f"{remote_output.rstrip('/')}/{archive_name}"
        archive_result = _download(colab, session, remote_archive, temporary_archive)
        if archive_result.returncode != 0:
            temporary_archive.unlink(missing_ok=True)
            temporary_status.unlink(missing_ok=True)
            continue
        observed = validate_download(temporary_archive, temporary_status)
        os.replace(temporary_archive, local_archive)
        os.replace(temporary_status, local_status)
        downloaded.append(
            {
                "seed": seed,
                "next_update": observed["next_update"],
                "bytes": observed["checkpoint_bytes"],
                "sha256": observed["checkpoint_sha256"],
            }
        )
    return {"downloaded": downloaded, "available": True}


def monitor(
    *,
    colab: Path,
    session: str,
    remote_output: str,
    local_root: Path,
    poll_seconds: float,
    once: bool,
) -> int:
    while True:
        try:
            result = mirror_once(
                colab=colab,
                session=session,
                remote_output=remote_output,
                local_root=local_root,
            )
        except Exception as exc:
            print(f"mirror stopped: {type(exc).__name__}: {exc}", flush=True)
            return 2
        for item in result["downloaded"]:
            print(
                f"mirrored seed={item['seed']} next_update={item['next_update']} "
                f"bytes={item['bytes']} sha256={item['sha256']}",
                flush=True,
            )
        if once:
            return 0
        time.sleep(poll_seconds)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    parser.add_argument("--remote-output", required=True)
    parser.add_argument("--local-root", type=Path, required=True)
    parser.add_argument(
        "--colab", type=Path, default=Path.home() / ".local/bin/colab"
    )
    parser.add_argument("--poll-seconds", type=float, default=30.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    if args.poll_seconds <= 0:
        parser.error("--poll-seconds must be positive")
    return monitor(
        colab=args.colab,
        session=args.session,
        remote_output=args.remote_output,
        local_root=args.local_root,
        poll_seconds=args.poll_seconds,
        once=args.once,
    )


if __name__ == "__main__":
    raise SystemExit(main())

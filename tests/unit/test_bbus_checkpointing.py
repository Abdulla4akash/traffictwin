from __future__ import annotations

import hashlib
import io
import json
import stat
import zipfile
from pathlib import Path

import numpy as np
import pytest
from gpu.real_bbus.checkpoint_source import (
    METHOD_VERSION,
    UPSTREAM_TRAIN_SHA256,
    _replace_once,
    checkpointed_train_text,
)
from gpu.real_bbus.monitor_colab_checkpoints import validate_download
from gpu.real_bbus.review_homecoming import _checked_members
from gpu.real_bbus.run_campaign import (
    CHECKPOINT_EVERY_UPDATES,
    CHECKPOINT_SCHEMA_VERSION,
    CHECKPOINT_STATUS_SCHEMA_VERSION,
    CHECKPOINT_TRANSFORM_VERSION,
)
from gpu.real_bbus.supervise_colab_campaign import (
    _validated_returned_result,
    supervise,
)


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _checkpoint_pair(root: Path) -> tuple[Path, Path]:
    device = b"full mutable JAX state"
    host_buffer = io.BytesIO()
    np.savez_compressed(host_buffer, next_update=np.int64(1))
    host = host_buffer.getvalue()
    curve = (
        b"update,env_step,mean_return,mean_completion,p_local,p_v2i,p_v2v,"
        b"avg_energy_j,avg_latency_ms,type_1_completion,type_2_completion,"
        b"type_3_completion,elapsed_s,sps\n"
        b"0,3200,1,1,1,0,0,1,1,1,1,1,1,1\n"
    )
    values = {"device.msgpack": device, "host.npz": host, "curve.csv": curve}
    manifest = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "next_update": 1,
        "total_env_steps": 3200,
        "settings": {},
        "components": {
            name: {"bytes": len(value), "sha256": _digest(value)} for name, value in values.items()
        },
    }
    values["manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    checkpoint = root / "model-seed-30.checkpoint.zip"
    with zipfile.ZipFile(checkpoint, "w") as archive:
        for name, value in values.items():
            archive.writestr(name, value)
    status = {
        "schema_version": CHECKPOINT_STATUS_SCHEMA_VERSION,
        "checkpoint_filename": checkpoint.name,
        "checkpoint_bytes": checkpoint.stat().st_size,
        "checkpoint_sha256": _digest(checkpoint.read_bytes()),
        "next_update": 1,
        "total_env_steps": 3200,
    }
    status_path = Path(str(checkpoint) + ".json")
    status_path.write_text(json.dumps(status), encoding="utf-8")
    return checkpoint, status_path


def test_checkpoint_execution_constants_are_frozen() -> None:
    assert CHECKPOINT_TRANSFORM_VERSION == METHOD_VERSION
    assert CHECKPOINT_EVERY_UPDATES == 50
    assert len(UPSTREAM_TRAIN_SHA256) == 64


def test_checkpoint_transform_is_fail_closed_on_source_identity() -> None:
    with pytest.raises(ValueError, match="differs"):
        checkpointed_train_text("print('not the permitted trainer')\n")
    with pytest.raises(ValueError, match="layout changed"):
        _replace_once("a a", "a", "b", label="ambiguous")


def test_checkpoint_download_has_archive_component_and_sidecar_hash_layers(
    tmp_path: Path,
) -> None:
    checkpoint, status = _checkpoint_pair(tmp_path)
    observed = validate_download(checkpoint, status)
    assert observed["next_update"] == 1
    checkpoint.write_bytes(checkpoint.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="byte count"):
        validate_download(checkpoint, status)


def test_checkpoint_download_accepts_atomic_temporary_suffix(tmp_path: Path) -> None:
    checkpoint, status = _checkpoint_pair(tmp_path)
    temporary_checkpoint = Path(str(checkpoint) + ".download")
    checkpoint.rename(temporary_checkpoint)
    temporary_status = Path(str(status) + ".download")
    status.rename(temporary_status)
    assert validate_download(temporary_checkpoint, temporary_status)["next_update"] == 1


def test_supervisor_reuses_a_validated_terminal_result_without_colab(tmp_path: Path) -> None:
    result = tmp_path / "results.zip"
    with zipfile.ZipFile(result, "w") as archive:
        archive.writestr("results/complete.txt", "complete\n")
    status = {
        "status": "returned",
        "attempt": 5,
        "result": str(result),
        "result_bytes": result.stat().st_size,
        "result_sha256": _digest(result.read_bytes()),
        "initial_checkpoint_progress": {},
        "final_checkpoint_progress": {},
    }
    (tmp_path / "supervisor_result.json").write_text(json.dumps(status), encoding="utf-8")

    assert _validated_returned_result(tmp_path) == status
    observed = supervise(
        colab=tmp_path / "missing-colab",
        pack=tmp_path / "missing-pack.zip",
        entrypoint=tmp_path / "missing-entrypoint.py",
        local_root=tmp_path,
        session_prefix="must-not-launch",
        remote_output="/content/results",
        remote_result="/content/results.zip",
        poll_seconds=1,
        max_attempts=1,
    )
    assert observed == status


def test_supervisor_refuses_a_tampered_terminal_result(tmp_path: Path) -> None:
    result = tmp_path / "results.zip"
    with zipfile.ZipFile(result, "w") as archive:
        archive.writestr("results/complete.txt", "complete\n")
    status = {
        "status": "returned",
        "attempt": 1,
        "result": str(result),
        "result_bytes": result.stat().st_size,
        "result_sha256": "0" * 64,
        "initial_checkpoint_progress": {},
        "final_checkpoint_progress": {},
    }
    (tmp_path / "supervisor_result.json").write_text(json.dumps(status), encoding="utf-8")
    with pytest.raises(ValueError, match="digest differs"):
        _validated_returned_result(tmp_path)


def test_homecoming_zip_guard_refuses_traversal_and_symlinks(tmp_path: Path) -> None:
    traversal = tmp_path / "traversal.zip"
    with zipfile.ZipFile(traversal, "w") as archive:
        archive.writestr("root/../escape.txt", "bad\n")
    with (
        zipfile.ZipFile(traversal) as archive,
        pytest.raises(ValueError, match="escapes"),
    ):
        _checked_members(archive, "root")

    symlink = tmp_path / "symlink.zip"
    info = zipfile.ZipInfo("root/link")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(symlink, "w") as archive:
        archive.writestr(info, "target")
    with (
        zipfile.ZipFile(symlink) as archive,
        pytest.raises(ValueError, match="symbolic link"),
    ):
        _checked_members(archive, "root")

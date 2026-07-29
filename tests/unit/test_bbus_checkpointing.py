from __future__ import annotations

import hashlib
import io
import json
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
from gpu.real_bbus.run_campaign import (
    CHECKPOINT_EVERY_UPDATES,
    CHECKPOINT_SCHEMA_VERSION,
    CHECKPOINT_STATUS_SCHEMA_VERSION,
    CHECKPOINT_TRANSFORM_VERSION,
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
            name: {"bytes": len(value), "sha256": _digest(value)}
            for name, value in values.items()
        },
    }
    values["manifest.json"] = (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode()
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

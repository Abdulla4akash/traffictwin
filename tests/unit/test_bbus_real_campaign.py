from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest
from gpu.real_bbus.build_colab_packs import (
    APPROVAL_PATH,
    APPROVAL_SHA256,
    ARM_BINDINGS,
    NO_DEPS_REQUIREMENTS,
    REQUIREMENTS,
    _deterministic_zip,
)
from gpu.real_bbus.prepare_source import PATCHED_TRAIN_SHA256, _patch_train_text
from gpu.real_bbus.run_campaign import (
    CAPACITY_PER_SLOT,
    EFFECTIVE_TIMESTEPS,
    EXPECTED_ARM_PROTOCOLS,
    EXPECTED_UPDATES,
    JAX_PLATFORM,
    MODEL_SEEDS,
    NUM_ENVS,
    REQUESTED_TIMESTEPS,
    ROLLOUT_LEN,
    _validate_evaluation,
    _validate_trace,
    campaign_jobs,
    sha256_file,
)


def test_campaign_is_two_separate_five_seed_held_out_designs() -> None:
    assert tuple(job.model_seed for job in campaign_jobs()) == MODEL_SEEDS == (30, 31, 32, 33, 34)
    assert CAPACITY_PER_SLOT == (2.5, 0.75)
    assert REQUESTED_TIMESTEPS == 5_000_000
    assert NUM_ENVS == 64
    assert ROLLOUT_LEN == 50
    assert EXPECTED_UPDATES == 1562
    assert EFFECTIVE_TIMESTEPS == 4_998_400
    assert set(ARM_BINDINGS) == set(EXPECTED_ARM_PROTOCOLS) == {"corridor", "sparse64"}
    assert ARM_BINDINGS["corridor"]["vec06_compatible"] is True
    assert ARM_BINDINGS["sparse64"]["vec06_compatible"] is False
    assert JAX_PLATFORM == "cuda"


def test_pack_builder_direct_entrypoint_is_importable() -> None:
    completed = subprocess.run(
        [sys.executable, "gpu/real_bbus/build_colab_packs.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_legacy_jaxmarl_metadata_is_installed_without_dependencies() -> None:
    assert "jaxmarl" not in REQUIREMENTS
    assert NO_DEPS_REQUIREMENTS == "jaxmarl==0.0.4\n"


def test_owner_receipt_and_both_protocol_bytes_match_pack_bindings() -> None:
    assert sha256_file(Path(APPROVAL_PATH)) == APPROVAL_SHA256
    for arm, design in ARM_BINDINGS.items():
        assert sha256_file(Path(design["protocol_path"])) == design["protocol_sha256"]
        assert design["protocol_sha256"] == EXPECTED_ARM_PROTOCOLS[arm]["protocol_sha256"]


def test_tree_map_compatibility_patch_is_the_only_required_source_shape() -> None:
    source = "def main():\n    import jax\n    import jax.numpy as jnp\n    return jnp, jax\n"
    patched = _patch_train_text(source)
    assert 'if not hasattr(jax, "tree_map")' in patched
    assert len(PATCHED_TRAIN_SHA256) == 64
    with pytest.raises(ValueError, match="layout changed"):
        _patch_train_text("import jax\n")


def test_trace_allowlist_and_stats_are_checked(tmp_path: Path) -> None:
    path = tmp_path / "trace.npz"
    mask = np.asarray([[True, False], [True, True]])
    arrays = {
        "pos_x": np.asarray([[0, 0], [1, 2]], dtype=np.float32),
        "pos_y": np.asarray([[0, 0], [1, 2]], dtype=np.float32),
        "speed": np.ones((2, 2), dtype=np.float32),
        "mask": mask,
        "rsu_xy": np.asarray([[0, 0]], dtype=np.float32),
        "times": np.arange(2, dtype=np.float32),
        "dt": np.float32(1),
        "maxN": np.int32(2),
        "T": np.int32(2),
        "window": np.asarray("dawn-20260728"),
        "sumo_seed": np.int32(42),
    }
    np.savez_compressed(path, **arrays)
    expected = {
        "sha256": sha256_file(path),
        "T": 2,
        "maxN": 2,
        "vehicle_seconds": 3,
        "rsu_count": 1,
        "window": "dawn-20260728",
    }
    assert _validate_trace(path, expected) == expected
    expected["vehicle_seconds"] = 4
    with pytest.raises(ValueError, match="binding mismatch"):
        _validate_trace(path, expected)


def test_held_out_evaluation_binds_capacity_seed_and_metrics() -> None:
    value = {
        "trace": "peak_trace.npz",
        "model": "C",
        "T": 10,
        "maxN": 4,
        "rsu_max_concurrent": 3,
        "fleet": "synthetic",
        "fleet_seed": 30,
        "obs_variant": "onehot17",
        "completion": 0.8,
        "avg_energy_j_per_task": 1.2,
        "avg_latency_ms_per_task": 45.0,
        "p_local": 0.5,
        "p_v2i": 0.25,
        "p_v2v": 0.25,
        "total_tasks": 100,
    }
    _validate_evaluation(value, peak={"T": 10, "maxN": 4}, capacity=0.75, seed=30)
    value["fleet_seed"] = 31
    with pytest.raises(ValueError, match="fleet_seed"):
        _validate_evaluation(value, peak={"T": 10, "maxN": 4}, capacity=0.75, seed=30)


def test_pack_zip_is_deterministic(tmp_path: Path) -> None:
    root = tmp_path / "pack"
    root.mkdir()
    (root / "a.txt").write_text("a\n")
    (root / "sub").mkdir()
    (root / "sub/b.txt").write_text("b\n")
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    _deterministic_zip(root, first)
    _deterministic_zip(root, second)
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert archive.testzip() is None
        assert archive.namelist() == ["pack/a.txt", "pack/sub/b.txt"]

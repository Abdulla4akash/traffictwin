from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jax
import numpy as np
import pytest
from gpu.colab.bcap_synthetic_smoke import (
    CAPACITY_AWARE_VARIANT,
    METHOD_VERSION,
    ORIGINAL_VARIANT,
    SmokeConfig,
    _synthetic_batch,
    run_experiment,
)


def _tiny_config() -> SmokeConfig:
    return SmokeConfig(
        model_seeds=(100,),
        evaluation_seeds=(9000,),
        updates=2,
        batch_size=32,
        evaluation_batch_size=64,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_synthetic_observation_contract_exposes_capacity_only_in_treatment() -> None:
    low = _synthetic_batch(jax.random.PRNGKey(7), 16, capacity_override=0.75)
    high = _synthetic_batch(jax.random.PRNGKey(7), 16, capacity_override=2.5)

    assert low.original_obs.shape == (16, 17)
    assert low.capacity_aware_obs.shape == (16, 19)
    assert low.rewards_by_action.shape == (16, 3)
    np.testing.assert_array_equal(np.asarray(low.original_obs), np.asarray(high.original_obs))
    assert not np.array_equal(
        np.asarray(low.capacity_aware_obs), np.asarray(high.capacity_aware_obs)
    )
    assert np.all(np.asarray(low.capacity_per_slot) == 0.75)
    assert np.all(np.asarray(high.capacity_per_slot) == 2.5)


def test_tiny_smoke_writes_labeled_checkpoint_shaped_outputs(tmp_path: Path) -> None:
    output = tmp_path / "bcap-smoke"
    result = run_experiment(_tiny_config(), output)

    design = json.loads((output / "design_manifest.json").read_text(encoding="utf-8"))
    execution = json.loads((output / "execution_manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    inventory = json.loads((output / "output_inventory.json").read_text(encoding="utf-8"))

    assert result["output_dir"] == str(output.resolve())
    assert design["method_version"] == METHOD_VERSION
    assert design["status"] == "synthetic_engineering_diagnostic_only"
    assert design["scientific_evidence"] is False
    assert design["actor_admission_eligible"] is False
    assert design["external_assets_included"] is False
    assert design["producer_assets_used"] is False
    assert design["bus_assets_used"] is False
    assert execution["scientific_evidence"] is False
    assert summary["scientific_evidence"] is False
    assert summary["model_seed_requirement_met"] is False
    assert sorted(summary["variants"]) == [CAPACITY_AWARE_VARIANT, ORIGINAL_VARIANT]

    original = np.load(output / f"{ORIGINAL_VARIANT}__model-seed-100__actor_params.npz")
    aware = np.load(output / f"{CAPACITY_AWARE_VARIANT}__model-seed-100__actor_params.npz")
    assert original["Dense_0.kernel"].shape == (17, 64)
    assert aware["Dense_0.kernel"].shape == (19, 64)
    assert original["Dense_2.kernel"].shape == (64, 3)
    assert aware["Dense_2.kernel"].shape == (64, 3)

    inventory_by_path = {item["path"]: item for item in inventory["files"]}
    assert "summary.json" in inventory_by_path
    assert inventory_by_path["summary.json"]["sha256"] == _sha256(output / "summary.json")
    assert (
        inventory_by_path["summary.json"]["size_bytes"] == (output / "summary.json").stat().st_size
    )


def test_smoke_refuses_to_overwrite_nonempty_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "owner-file.txt"
    marker.write_text("preserve me", encoding="utf-8")

    with pytest.raises(ValueError, match="never overwritten"):
        run_experiment(_tiny_config(), output)

    assert marker.read_text(encoding="utf-8") == "preserve me"


def test_colab_notebook_is_gpu_gated_and_has_no_external_asset_input_code() -> None:
    notebook_path = Path("gpu/colab/bcap_synthetic_smoke.ipynb")
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    code_sources = [
        "".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"
    ]
    all_code = "\n".join(code_sources)

    assert notebook["nbformat"] == 4
    assert notebook["metadata"]["accelerator"] == "GPU"
    assert 'REPOSITORY_URL = "https://github.com/Abdulla4akash/traffictwin.git"' in all_code
    assert "require_gpu=True" in all_code
    assert "drive.mount" not in all_code
    assert "files.upload" not in all_code
    assert "vec_env" not in all_code
    assert "tos-data" not in all_code

    for index, source in enumerate(code_sources):
        if source.lstrip().startswith("%pip"):
            continue
        compile(source, f"{notebook_path}:cell-{index}", "exec")

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jax
import numpy as np
import pytest
from gpu.colab.bbus_synthetic_trace_smoke import (
    BUS_LIKE,
    DOMAINS,
    GENERAL_TRAFFIC,
    METHOD_VERSION,
    TraceSmokeConfig,
    _synthetic_trace,
    run_experiment,
)


def _tiny_config() -> TraceSmokeConfig:
    return TraceSmokeConfig(
        model_seeds=(200,),
        evaluation_seeds=(9100,),
        updates=2,
        batch_size=32,
        training_trace_size=64,
        evaluation_trace_size=64,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_synthetic_domains_are_deterministic_distinct_and_seventeen_wide() -> None:
    key = jax.random.PRNGKey(19)
    bus_first = _synthetic_trace(key, 128, BUS_LIKE)
    bus_second = _synthetic_trace(key, 128, BUS_LIKE)
    traffic = _synthetic_trace(key, 128, GENERAL_TRAFFIC)

    assert bus_first.observations.shape == (128, 17)
    assert bus_first.rewards_by_action.shape == (128, 3)
    np.testing.assert_array_equal(
        np.asarray(bus_first.observations), np.asarray(bus_second.observations)
    )
    assert not np.array_equal(
        np.asarray(bus_first.observations), np.asarray(traffic.observations)
    )
    assert float(np.mean(np.asarray(bus_first.dwell))) > float(
        np.mean(np.asarray(traffic.dwell))
    )


def test_tiny_smoke_writes_labeled_trace_matrix_and_checkpoints(tmp_path: Path) -> None:
    output = tmp_path / "bbus-smoke"
    result = run_experiment(_tiny_config(), output)

    design = json.loads((output / "design_manifest.json").read_text(encoding="utf-8"))
    execution = json.loads((output / "execution_manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    inventory = json.loads((output / "output_inventory.json").read_text(encoding="utf-8"))

    assert result["output_dir"] == str(output.resolve())
    assert design["method_version"] == METHOD_VERSION
    assert design["scientific_evidence"] is False
    assert design["actor_admission_eligible"] is False
    assert design["external_assets_included"] is False
    assert design["producer_assets_used"] is False
    assert design["bus_assets_used"] is False
    assert design["real_motion_used"] is False
    assert execution["scientific_evidence"] is False
    assert summary["model_seed_requirement_met"] is False
    assert tuple(summary["training_domains"]) == DOMAINS

    bundle = np.load(output / "synthetic_training_trace_bundle.npz")
    for domain in DOMAINS:
        assert bundle[f"{domain}.observations"].shape == (64, 17)
        assert bundle[f"{domain}.rewards_by_action"].shape == (64, 3)
        actor = np.load(output / f"train-{domain}__model-seed-200__actor_params.npz")
        assert actor["Dense_0.kernel"].shape == (17, 64)
        assert actor["Dense_2.kernel"].shape == (64, 3)
        matrix = summary["training_domains"][domain]["evaluation_matrix"]
        assert sorted(matrix) == sorted(DOMAINS)

    by_path = {item["path"]: item for item in inventory["files"]}
    assert by_path["summary.json"]["sha256"] == _sha256(output / "summary.json")


def test_smoke_refuses_to_overwrite_nonempty_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "owner-file.txt"
    marker.write_text("preserve me", encoding="utf-8")

    with pytest.raises(ValueError, match="never overwritten"):
        run_experiment(_tiny_config(), output)

    assert marker.read_text(encoding="utf-8") == "preserve me"


def test_colab_notebook_is_gpu_gated_and_has_no_real_asset_input_code() -> None:
    notebook_path = Path("gpu/colab/bbus_synthetic_trace_smoke.ipynb")
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    code_sources = [
        "".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"
    ]
    all_code = "\n".join(code_sources)

    assert notebook["nbformat"] == 4
    assert notebook["metadata"]["accelerator"] == "GPU"
    assert 'REPOSITORY_URL = "https://github.com/Abdulla4akash/traffictwin.git"' in all_code
    assert "TraceSmokeConfig" in all_code
    assert "require_gpu=True" in all_code
    assert "drive.mount" not in all_code
    assert "files.upload" not in all_code
    assert "vec_env" not in all_code
    assert "tos-data" not in all_code
    assert "diss_mat" not in all_code

    for index, source in enumerate(code_sources):
        if source.lstrip().startswith("%pip"):
            continue
        compile(source, f"{notebook_path}:cell-{index}", "exec")

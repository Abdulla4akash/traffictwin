from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest
from scripts.run_e1_multidraw_physical_campaign import (
    _common_stream_check,
    _format_argv,
    _physical_manifest_view,
    _write_checksums,
    run_campaign,
)


def _manifest() -> dict[str, Any]:
    return {
        "manifest_id": "test-campaign",
        "backend_decision": {"status": "selected", "backend": "fixture"},
        "inputs": {
            "actor": {"path": "checkpoints/actor.npz"},
            "trace": {
                "path": "traces/trace.npz",
                "padded_fleet_width": 2488,
                "has_enter_channel": False,
            },
        },
        "cap_grid": [
            {"label": "0p75", "ratio_cli": "0.75", "resolved_tasks_per_rsu": 1866},
            {"label": "2p5", "ratio_cli": "2.5", "resolved_tasks_per_rsu": 6220},
            {"label": "40x", "ratio_cli": "40.0", "resolved_tasks_per_rsu": 99520},
        ],
        "controlled_configuration": {
            "fleet": {"preset": "uk2030"},
            "arrival_lambda": 1.5,
            "compute": {
                "rsu_service_multiplier": 1.0,
                "scaling": "off",
                "mean_multiplier_expected": 1.0,
            },
            "placement": {"mode": "off", "backhaul_ms": 0.0},
            "rsu_admission": "reject",
            "substep_queue": "sequential",
            "vehicle_queue": "conserved",
        },
        "execution": {
            "argv_template": [
                "{PYTHON}",
                "{VEC_ENV}/eval/eval_sumo_stage1_mc.py",
                "--trace",
                "{TOS_DATA}/traces/trace.npz",
                "--actor",
                "{TOS_DATA}/checkpoints/actor.npz",
                "--max-steps",
                "{MAX_STEPS}",
                "--fleet-seed",
                "{FLEET_SEED}",
                "--rsu-cap-per-veh",
                "{CAP_RATIO}",
                "--out-json",
                "{RUN_DIR}/summary.json",
            ]
        },
    }


def test_physical_view_resolves_exact_cap_and_seed() -> None:
    view = _physical_manifest_view(_manifest(), fleet_seed=3, cap_label="40x", max_steps=3600)
    assert view["scope"]["max_steps"] == 3600
    assert view["configuration"]["fleet_seed"] == 3
    assert view["configuration"]["cap"]["resolved_value"] == 99520
    assert view["configuration"]["rsu_admission"] == "reject"


def test_command_changes_only_predeclared_cell_fields(tmp_path: Path) -> None:
    argv = _format_argv(
        _manifest(),
        python=Path("/runtime/python"),
        vec_env=Path("/vec"),
        tos_data=Path("/tos"),
        run_dir=tmp_path,
        fleet_seed=4,
        cap_label="0p75",
        max_steps=10,
    )
    assert argv[argv.index("--fleet-seed") + 1] == "4"
    assert argv[argv.index("--rsu-cap-per-veh") + 1] == "0.75"
    assert argv[argv.index("--max-steps") + 1] == "10"
    assert argv[argv.index("--out-json") + 1] == str(tmp_path / "summary.json")


def test_common_stream_check_refuses_task_type_drift() -> None:
    base = {
        "run": {
            "observed": {"n_offered": 5},
            "array_sha256": {"per_task": {"task_active": "same-active", "task_type": "same-type"}},
        }
    }
    changed = {
        "run": {
            "observed": {"n_offered": 5},
            "array_sha256": {
                "per_task": {"task_active": "same-active", "task_type": "different-type"}
            },
        }
    }
    report = _common_stream_check([base, changed])
    assert report["passed"] is False
    assert report["checks"]["task_type_identical"] is False


def test_checksum_writer_refuses_overwrite(tmp_path: Path) -> None:
    (tmp_path / "summary.json").write_text("{}\n", encoding="utf-8")
    _write_checksums(tmp_path)
    with pytest.raises(FileExistsError):
        _write_checksums(tmp_path)


def test_campaign_runner_refuses_pending_backend_decision(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"backend_decision": {"status": "pending_colab_gpu_smoke"}}),
        encoding="utf-8",
    )
    args = argparse.Namespace(manifest=manifest)
    with pytest.raises(RuntimeError, match="Colab backend comparison"):
        run_campaign(args)

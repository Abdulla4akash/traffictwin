import json
from pathlib import Path
import shutil

import numpy as np
import pytest

from analysis import paired_interval


def test_primary_interval_rejects_pilot_pooled_as_fifth_draw():
    with pytest.raises(AssertionError):
        paired_interval([1, 2, 3, 4, 5])


def test_uncertainty_retains_inconclusive_mixed_draws():
    r = paired_interval([-2, -1, 1, 2])
    assert r["mean_pp"] == 0
    assert r["family95_low_pp"] < r["ci95_low_pp"] < 0 < r["ci95_high_pp"] < r["family95_high_pp"]


def test_reversing_contrast_reverses_interval_endpoints():
    a, b = paired_interval([.1, .5, 1.1, .7]), paired_interval([-.1, -.5, -1.1, -.7])
    assert a["mean_pp"] == -b["mean_pp"]
    assert a["ci95_low_pp"] == -b["ci95_high_pp"]
    assert a["family95_high_pp"] == -b["family95_low_pp"]


@pytest.mark.parametrize("drop_pre_drain", [False, True])
def test_work_conservation_detects_removed_admission(tmp_path, drop_pre_drain):
    import workload_checks
    root = Path(__file__).resolve().parent
    pilot = root.parent / "generalisation-pilot-2026-09-07"
    manifest = json.loads((pilot / "manifest.json").read_text())
    source = pilot / "preflight/fresh/attempt_001"
    for name in ("summary.json", "per_step.npz"):
        shutil.copyfile(source/name, tmp_path/name)
    if drop_pre_drain:
        with np.load(tmp_path/"per_step.npz") as z:
            step = {name:z[name] for name in z.files if name != "rsu_pre_drain_busy_ms"}
        np.savez_compressed(tmp_path/"per_step.npz", **step)
    with np.load(source/"per_task.npz") as z:
        arrays = dict(z)
    where = np.flatnonzero(arrays["task_v2i_admitted"])
    assert len(where) > 100
    arrays["task_v2i_admitted"].flat[where[:100]] = False
    np.savez_compressed(tmp_path/"per_task.npz", **arrays)
    with pytest.raises(RuntimeError, match="Reconstructed .* RSU service-work total differs|Reconstructed RSU queue endpoint differs|Reconstructed pre-drain work differs"):
        workload_checks.validate(tmp_path, manifest, manifest["cells"][0], 300)

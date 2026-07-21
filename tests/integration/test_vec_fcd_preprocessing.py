from __future__ import annotations

import hashlib
import json
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from traffictwin.integration.vec_preprocessing import (
    VecFcdPreprocessingError,
    VecFcdPreprocessRequest,
    preprocess_vec_fcd,
)

ROOT = Path(__file__).parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "vec_fcd" / "synthetic_micro"
VEC_REPO = (ROOT.parent / "external" / "vec_env").resolve()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request() -> VecFcdPreprocessRequest:
    return VecFcdPreprocessRequest(
        input_id="synthetic-micro",
        scenario_day="synthetic-day",
        window_label="t100-t103",
        fcd_file="fcd.xml",
        network_file="network.net.xml",
        fcd_sha256=_sha256(FIXTURE / "fcd.xml"),
        network_sha256=_sha256(FIXTURE / "network.net.xml"),
        sumo_seed=7,
    )


def _source_status() -> tuple[str, str]:
    git = shutil.which("git")
    assert git is not None
    head = subprocess.run(  # noqa: S603 - resolved executable and fixed test argv
        [git, "-C", str(VEC_REPO), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(  # noqa: S603 - resolved executable and fixed test argv
        [git, "-C", str(VEC_REPO), "status", "--porcelain=v1", "--untracked-files=all"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return head, status


def test_pinned_pipeline_is_deterministic_atomic_and_non_mutating(tmp_path: Path) -> None:
    if not VEC_REPO.is_dir():
        pytest.skip("the private external vec_env clone is not available")
    before_inputs = {
        path.name: (_sha256(path), path.stat().st_mtime_ns) for path in FIXTURE.glob("*.xml")
    }
    source_before = _source_status()

    first = preprocess_vec_fcd(FIXTURE, VEC_REPO, tmp_path / "first", _request())
    second = preprocess_vec_fcd(FIXTURE, VEC_REPO, tmp_path / "second", _request())

    assert first == second
    assert first.fingerprint() == second.fingerprint()
    assert (
        first.deterministic_output_fingerprint
        == "899e568cac31d72bbbcf2cd7e60ea654653f28bb25ffb1fbc60b0a97790e5437"
    )
    assert first.external_repositories_modified is False
    assert first.raw_inputs_modified is False
    assert first.inputs_before == first.inputs_after
    assert [item.path for item in first.outputs] == [
        "logs/build_trace.stderr.txt",
        "logs/build_trace.stdout.txt",
        "logs/place_rsus.stderr.txt",
        "logs/place_rsus.stdout.txt",
        "occupancy.csv",
        "rsu_placement.csv",
        "trace.npz",
    ]
    assert (tmp_path / "first" / "occupancy.csv").read_text(encoding="utf-8").splitlines() == [
        "sumo_vehicle_id,slot,t_enter,t_exit",
        "synthetic-vehicle-0,0,0,1",
        "synthetic-vehicle-1,1,1,3",
        "synthetic-vehicle-2,0,3,3",
    ]
    assert (tmp_path / "first" / "rsu_placement.csv").read_text(encoding="utf-8").splitlines() == [
        "rsu_index,x_m,y_m,radius_m,strategy",
        "0,125,125,500,greedy_urban_cover",
    ]
    stored = json.loads(
        (tmp_path / "first" / "preprocessing_receipt.json").read_text(encoding="utf-8")
    )
    assert stored == first.model_dump(mode="json")
    for path in (tmp_path / "first").rglob("*"):
        if path.is_file():
            assert not path.stat().st_mode & stat.S_IWUSR
    assert {
        path.name: (_sha256(path), path.stat().st_mtime_ns) for path in FIXTURE.glob("*.xml")
    } == before_inputs
    assert _source_status() == source_before


def test_execution_refuses_existing_and_overlapping_destinations(tmp_path: Path) -> None:
    if not VEC_REPO.is_dir():
        pytest.skip("the private external vec_env clone is not available")
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(VecFcdPreprocessingError, match="must not already exist"):
        preprocess_vec_fcd(FIXTURE, VEC_REPO, existing, _request())
    with pytest.raises(VecFcdPreprocessingError, match="must not overlap the input root"):
        preprocess_vec_fcd(FIXTURE, VEC_REPO, FIXTURE / "generated", _request())

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from traffictwin.integration.vec_preprocessing import (
    VecFcdPreprocessRequest,
    preprocess_vec_fcd,
)
from traffictwin.integration.vec_runner import (
    VecRunnerPreflightStatus,
    VecRunRequest,
    VecTerminalStatus,
    preflight_vec_run,
    run_vec_evaluator,
)

ROOT = Path(__file__).parents[2]
VEC_REPO = (ROOT.parent / "external" / "vec_env").resolve()
TOS_REPO = (ROOT.parent / "external" / "tos-data").resolve()
TRACE = TOS_REPO / "traces" / "trace_we_fullrsu.npz"
TRACE_SHA256 = "a2612865f5e1ef6d066975d6430693225f5d16060f139176548c8ae020e428be"
FCD_FIXTURE = ROOT / "tests" / "fixtures" / "vec_fcd" / "synthetic_micro"


def _repository_state(repo: Path) -> tuple[str, str, str]:
    git = shutil.which("git")
    assert git is not None
    results = []
    for args in (
        ("rev-parse", "HEAD"),
        ("rev-parse", "refs/remotes/origin/main"),
        ("status", "--porcelain=v1", "--untracked-files=all"),
    ):
        results.append(
            subprocess.run(  # noqa: S603 - resolved Git and fixed read-only argv
                [git, "-C", str(repo), *args],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    return results[0], results[1], results[2]


def test_real_pinned_two_step_run_is_isolated_validated_and_non_mutating(tmp_path: Path) -> None:
    if not VEC_REPO.is_dir() or not TOS_REPO.is_dir() or not TRACE.is_file():
        pytest.skip("the reviewed external VEC repositories are not available")
    if hashlib.sha256(TRACE.read_bytes()).hexdigest() != TRACE_SHA256:
        pytest.skip("the reviewed trace is not available at the audited identity")
    source_before = (_repository_state(VEC_REPO), _repository_state(TOS_REPO))
    trace_before = (TRACE_SHA256, TRACE.stat().st_mtime_ns)
    request = VecRunRequest(
        run_id="integration-two-step",
        trace_file="traces/trace_we_fullrsu.npz",
        trace_sha256=TRACE_SHA256,
        actor_id="ukfleettrain_mappo_model_c_17",
        evaluator_seed=0,
        fleet="uk2030",
        fleet_seed=0,
        max_steps=2,
    )

    receipt = run_vec_evaluator(
        TOS_REPO,
        VEC_REPO,
        TOS_REPO,
        tmp_path / "published",
        request,
    )

    assert receipt.status is VecTerminalStatus.COMPLETED
    assert receipt.exit_code == 0
    assert receipt.published is True
    assert receipt.scientific_admission is False
    assert receipt.external_repositories_modified is False
    assert receipt.raw_inputs_modified is False
    assert receipt.inputs_before == receipt.inputs_after
    assert [item.path for item in receipt.outputs] == ["per-step.npz", "per-task.npz", "run.json"]
    assert [item.path for item in receipt.logs] == ["logs/stderr.txt", "logs/stdout.txt"]
    summary = json.loads((tmp_path / "published" / "run.json").read_text(encoding="utf-8"))
    assert summary["T"] == 2
    assert summary["maxN"] == 139
    stored = json.loads(
        (tmp_path / "published" / "execution_receipt.json").read_text(encoding="utf-8")
    )
    assert stored == receipt.model_dump(mode="json")
    for path in (tmp_path / "published").rglob("*"):
        if path.is_file():
            assert not path.stat().st_mode & stat.S_IWUSR
    assert (_repository_state(VEC_REPO), _repository_state(TOS_REPO)) == source_before
    assert (
        hashlib.sha256(TRACE.read_bytes()).hexdigest(),
        TRACE.stat().st_mtime_ns,
    ) == trace_before


def test_real_vec06_receipt_trace_is_admitted_by_vec07(tmp_path: Path) -> None:
    if not VEC_REPO.is_dir() or not TOS_REPO.is_dir():
        pytest.skip("the reviewed external VEC repositories are not available")
    fcd = FCD_FIXTURE / "fcd.xml"
    network = FCD_FIXTURE / "network.net.xml"
    vec06_request = VecFcdPreprocessRequest(
        input_id="synthetic-micro",
        scenario_day="synthetic-day",
        window_label="t100-t103",
        fcd_file="fcd.xml",
        network_file="network.net.xml",
        fcd_sha256=hashlib.sha256(fcd.read_bytes()).hexdigest(),
        network_sha256=hashlib.sha256(network.read_bytes()).hexdigest(),
        sumo_seed=7,
    )
    vec06_output = tmp_path / "vec06"
    preprocess_vec_fcd(FCD_FIXTURE, VEC_REPO, vec06_output, vec06_request)
    trace = vec06_output / "trace.npz"
    receipt = vec06_output / "preprocessing_receipt.json"
    request = VecRunRequest(
        run_id="vec06-admission",
        trace_file="trace.npz",
        trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest(),
        preprocessing_receipt_file="preprocessing_receipt.json",
        preprocessing_receipt_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest(),
        actor_id="ukfleettrain_mappo_model_c_17",
        max_steps=2,
    )

    report = preflight_vec_run(vec06_output, VEC_REPO, TOS_REPO, request)

    assert report.status is VecRunnerPreflightStatus.ACCEPTED
    assert [item.path for item in report.inputs] == [
        "inputs/trace.npz",
        "inputs/preprocessing_receipt.json",
    ]

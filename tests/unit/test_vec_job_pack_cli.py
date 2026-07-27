"""Coverage for the job-pack command line.

Every checkout here is a handful of tiny files in ``tmp_path`` and every receipt
is synthetic. Nothing in this module touches an external repository, a live
campaign directory, a registry, or the network — there is no executor to
exercise, which is the property the contract exists to preserve.

The assertions that matter are the refusals: a pack must not be exportable from
a checkout at the wrong commit, a half-returned campaign must not exit 0, and no
output of either subcommand may read as an admission.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from traffictwin.integration.vec_campaign.job_pack import (
    AUDITED_REPOSITORY_COMMITS,
    DEFAULT_REQUIRED_OUTPUT_NAMES,
    VecJobPackInputRole,
)
from traffictwin.integration.vec_campaign.models import (
    VecCampaignApproval,
    VecCampaignArm,
    VecCampaignBudget,
    VecCampaignDesign,
    VecCampaignPhase,
)
from traffictwin.integration.vec_fresh_admission.models import VecPairingSeedSource
from traffictwin.integration.vec_runner.models import (
    PINNED_ACTORS,
    PINNED_EVALUATOR_FILES,
    VecExecutionReceipt,
    VecFleet,
    VecRunnerFileEvidence,
    VecRuntimeEvidence,
    VecTerminalStatus,
    output_fingerprint,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "vec_job_pack.py"

INC_TRACE_SHA = "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"
INC_TRACE_FILE = "traces/trace_inc_fullrsu.npz"
ACTOR_ID = "ukfleettrain_mappo_model_c_17"
CREATED_AT = "2026-07-27T18:00:00+00:00"


def _module() -> ModuleType:
    """Load the command line by path; ``scripts/`` is not an importable package."""

    spec = importlib.util.spec_from_file_location("vec_job_pack_cli_under_test", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CLI = _module()


def _design(*, seeds: list[int] | None = None) -> VecCampaignDesign:
    return VecCampaignDesign(
        experiment_id="vec-csf-cli-unit",
        research_question="Does reduced per-vehicle RSU task capacity degrade deadline success?",
        run_id_prefix="csfcli",
        phase=VecCampaignPhase.PILOT,
        approval=VecCampaignApproval(
            predeclaration_path="predeclaration.md",
            predeclaration_sha256="e" * 64,
            approved_by="A. Owner",
            approved_role="repository owner",
            approved_at_utc="2026-07-27T12:00:00+00:00",
        ),
        trace_file=INC_TRACE_FILE,
        trace_sha256=INC_TRACE_SHA,
        actor_id=ACTOR_ID,
        fleet=VecFleet.UK_2030,
        evaluator_seed=0,
        max_steps=3_600,
        timeout_seconds=7_200,
        baseline_arm=VecCampaignArm(label="cap-2.5", rsu_capacity_per_vehicle=2.5),
        variation_arms=[VecCampaignArm(label="cap-1.0", rsu_capacity_per_vehicle=1.0)],
        pairing_seed_source=VecPairingSeedSource.FLEET_SEED,
        fleet_seeds=seeds if seeds is not None else [0, 1, 2],
        primary_metric_key="tos.task.deadline_success.rate",
        budget=VecCampaignBudget(max_cells=12, max_total_output_bytes=1_000_000_000),
    )


def _checkouts(tmp_path: Path) -> dict[str, Path]:
    """Create tiny stand-ins for the two audited checkouts."""

    tos_root = tmp_path / "tos-data"
    vec_root = tmp_path / "vec_env"
    actor_path, _ = PINNED_ACTORS[ACTOR_ID]
    for root, relative, body in (
        (tos_root, INC_TRACE_FILE, b"trace-bytes"),
        (tos_root, actor_path, b"actor-bytes"),
        *[(vec_root, path, b"source-bytes") for path in sorted(PINNED_EVALUATOR_FILES)],
    ):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    return {"tos-data": tos_root, "vec_env": vec_root}


def _design_module(tmp_path: Path) -> Path:
    """Write a self-contained module exposing a design factory and an instance.

    A campaign script names its design the same way: a module-level factory the
    command line resolves without the script being an importable package.
    """

    path = tmp_path / "campaign_design_fixture.py"
    path.write_text(
        "from traffictwin.integration.vec_campaign.models import VecCampaignDesign\n"
        "\n"
        f"_PAYLOAD = {_design().model_dump_json()!r}\n"
        "\n"
        "DESIGN = VecCampaignDesign.model_validate_json(_PAYLOAD)\n"
        "\n"
        "\n"
        "def build_design():\n"
        "    return VecCampaignDesign.model_validate_json(_PAYLOAD)\n"
        "\n"
        "\n"
        "NOT_A_DESIGN = 17\n",
        encoding="utf-8",
    )
    return path


def _stub_commit_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Accept any checkout: the commit check has its own dedicated tests."""

    monkeypatch.setattr(
        CLI,
        "verify_checkout_commit",
        lambda root, repository: AUDITED_REPOSITORY_COMMITS[repository],
    )


def _runtime() -> VecRuntimeEvidence:
    return VecRuntimeEvidence(
        python="3.12.4",
        numpy="1.26.4",
        jax="0.4.30",
        jaxlib="0.4.30",
        jax_backend="cpu",
        jax_device_count=1,
        platform="test",
        machine="test",
        processor="test",
        environment_sha256="d" * 64,
    )


def _receipt(
    design: VecCampaignDesign,
    arm_label: str,
    fleet_seed: int,
    *,
    status: VecTerminalStatus = VecTerminalStatus.COMPLETED,
) -> VecExecutionReceipt:
    arm = next(item for item in design.arms() if item.label == arm_label)
    request = design.cell_request(arm, fleet_seed)
    completed = status is VecTerminalStatus.COMPLETED
    outputs = (
        [
            VecRunnerFileEvidence(
                path=name,
                sha256=f"{index}" * 64,
                size_bytes=1_000 + index,
                media_type="application/octet-stream",
                read_only=True,
            )
            for index, name in enumerate(DEFAULT_REQUIRED_OUTPUT_NAMES)
        ]
        if completed
        else []
    )
    return VecExecutionReceipt(
        status=status,
        request=request,
        request_fingerprint=request.fingerprint(),
        preflight_fingerprint="c" * 64,
        argv=[],
        started_at_utc="2026-07-27T18:00:00+00:00",
        finished_at_utc="2026-07-27T18:30:00+00:00",
        elapsed_seconds=1_800.0,
        exit_code=0 if completed else 1,
        timed_out=False,
        cancellation_requested=False,
        runtime=_runtime(),
        repositories=[],
        inputs_before=[],
        inputs_after=[],
        logs=[],
        stdout_excerpt="",
        stderr_excerpt="",
        outputs=outputs,
        findings=[],
        output_fingerprint=output_fingerprint(outputs) if outputs else None,
        external_repositories_modified=False,
        raw_inputs_modified=False,
        published=completed,
    )


def _write_results(
    directory: Path,
    receipts: list[VecExecutionReceipt],
    *,
    receipt_name: str = "execution_receipt.json",
) -> Path:
    """Lay returned receipts out the way a campaign directory lays them out."""

    for receipt in receipts:
        cell_directory = directory / receipt.request.run_id
        cell_directory.mkdir(parents=True, exist_ok=True)
        (cell_directory / receipt_name).write_text(
            receipt.model_dump_json(indent=2), encoding="utf-8"
        )
    return directory


def _export_argv(
    roots: dict[str, Path],
    *,
    design_ref: str,
    output: Path,
    extra: list[str] | None = None,
) -> list[str]:
    return [
        "export",
        design_ref,
        str(output),
        "--pack-id",
        "csf-cli-pack",
        "--created-at-utc",
        CREATED_AT,
        "--tos-data-root",
        str(roots["tos-data"]),
        "--vec-env-root",
        str(roots["vec_env"]),
        *(extra or []),
    ]


# --- design resolution -------------------------------------------------------


def test_design_reference_resolves_a_factory_in_a_file_module(tmp_path: Path) -> None:
    module_path = _design_module(tmp_path)

    design = CLI.load_design(f"{module_path}:build_design")

    assert design.fingerprint() == _design().fingerprint()


def test_design_reference_resolves_a_module_level_design_instance(tmp_path: Path) -> None:
    module_path = _design_module(tmp_path)

    design = CLI.load_design(f"{module_path}:DESIGN")

    assert design.experiment_id == "vec-csf-cli-unit"


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        ("no_separator", "MODULE:ATTRIBUTE"),
        (":build_design", "MODULE:ATTRIBUTE"),
        ("module.py:", "MODULE:ATTRIBUTE"),
    ],
)
def test_malformed_design_reference_is_refused(reference: str, expected: str) -> None:
    with pytest.raises(CLI.JobPackCommandError, match=expected):
        CLI.load_design(reference)


def test_missing_design_attribute_is_refused(tmp_path: Path) -> None:
    module_path = _design_module(tmp_path)

    with pytest.raises(CLI.JobPackCommandError, match="defines no attribute"):
        CLI.load_design(f"{module_path}:absent_design")


def test_attribute_that_is_not_a_design_is_refused(tmp_path: Path) -> None:
    module_path = _design_module(tmp_path)

    with pytest.raises(CLI.JobPackCommandError, match="not a VecCampaignDesign"):
        CLI.load_design(f"{module_path}:NOT_A_DESIGN")


def test_missing_design_module_is_refused(tmp_path: Path) -> None:
    with pytest.raises(CLI.JobPackCommandError, match="design module not found"):
        CLI.load_design(f"{tmp_path / 'absent.py'}:build_design")


# --- manifest resolution -----------------------------------------------------


def test_manifest_declares_the_pinned_inputs_with_measured_sizes(tmp_path: Path) -> None:
    roots = _checkouts(tmp_path)
    design = _design()

    refs = CLI.resolve_manifest(design, roots=roots)

    by_role = {
        ref.role: ref for ref in refs if ref.role is not VecJobPackInputRole.EVALUATOR_SOURCE
    }
    assert by_role[VecJobPackInputRole.TRACE].sha256 == INC_TRACE_SHA
    assert by_role[VecJobPackInputRole.TRACE].path == INC_TRACE_FILE
    assert by_role[VecJobPackInputRole.ACTOR].sha256 == PINNED_ACTORS[ACTOR_ID][1]
    sources = {ref.path for ref in refs if ref.role is VecJobPackInputRole.EVALUATOR_SOURCE}
    assert sources == set(PINNED_EVALUATOR_FILES)
    # Sizes are measured off the checkout; hashes are the audited pins, never a
    # local re-hash promoted to an identity.
    assert by_role[VecJobPackInputRole.TRACE].size_bytes == len(b"trace-bytes")
    assert all(ref.audited_commit == AUDITED_REPOSITORY_COMMITS[ref.repository] for ref in refs)


def test_manifest_refuses_an_input_missing_from_the_checkout(tmp_path: Path) -> None:
    roots = _checkouts(tmp_path)
    (roots["tos-data"] / INC_TRACE_FILE).unlink()

    with pytest.raises(CLI.JobPackCommandError, match="declared trace input is missing"):
        CLI.resolve_manifest(_design(), roots=roots)


def test_manifest_refuses_an_actor_that_is_not_pinned(tmp_path: Path) -> None:
    roots = _checkouts(tmp_path)
    design = _design().model_copy(update={"actor_id": "not_a_pinned_actor"})

    with pytest.raises(CLI.JobPackCommandError, match="is not a pinned checkpoint"):
        CLI.resolve_manifest(design, roots=roots)


def test_hash_verification_is_opt_in_and_refuses_a_checkout_that_does_not_match(
    tmp_path: Path,
) -> None:
    roots = _checkouts(tmp_path)

    # Default: sizes only, so the stand-in checkout is accepted.
    assert CLI.resolve_manifest(_design(), roots=roots)

    with pytest.raises(CLI.JobPackCommandError, match="not the audited"):
        CLI.resolve_manifest(_design(), roots=roots, verify_hashes=True)


# --- checkout commit ---------------------------------------------------------


def test_checkout_commit_check_refuses_a_directory_that_is_not_a_checkout(
    tmp_path: Path,
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()

    with pytest.raises(CLI.JobPackCommandError, match="not a readable git checkout"):
        CLI.verify_checkout_commit(plain, "tos-data")


def test_checkout_commit_check_refuses_the_wrong_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "tos-data"
    root.mkdir()

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="0" * 40 + "\n", stderr="")

    monkeypatch.setattr(CLI.subprocess, "run", fake_run)

    with pytest.raises(CLI.JobPackCommandError, match="re-pinning is an approval decision"):
        CLI.verify_checkout_commit(root, "tos-data")


def test_checkout_commit_check_accepts_the_audited_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "tos-data"
    root.mkdir()
    expected = AUDITED_REPOSITORY_COMMITS["tos-data"]

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=expected + "\n", stderr="")

    monkeypatch.setattr(CLI.subprocess, "run", fake_run)

    assert CLI.verify_checkout_commit(root, "tos-data") == expected


def test_checkout_commit_check_reaches_git_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The only git subcommand this script may run is a local rev-parse."""

    root = tmp_path / "tos-data"
    root.mkdir()
    seen: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(argv)
        return subprocess.CompletedProcess(
            args=argv,
            returncode=0,
            stdout=AUDITED_REPOSITORY_COMMITS["tos-data"] + "\n",
            stderr="",
        )

    monkeypatch.setattr(CLI.subprocess, "run", fake_run)
    CLI.verify_checkout_commit(root, "tos-data")

    assert len(seen) == 1
    executable, *rest = seen[0]
    assert Path(executable).name == "git"
    assert rest == ["-C", str(root), "rev-parse", "HEAD"]
    assert not any(word in rest for word in ("fetch", "pull", "clone", "remote", "push"))


# --- export ------------------------------------------------------------------


def test_export_writes_a_pack_that_matches_the_design(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_commit_check(monkeypatch)
    roots = _checkouts(tmp_path)
    module_path = _design_module(tmp_path)
    output = tmp_path / "packs" / "pack.json"

    code = CLI.main(_export_argv(roots, design_ref=f"{module_path}:build_design", output=output))

    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    design = _design()
    assert payload["design_fingerprint"] == design.fingerprint()
    assert payload["pack_id"] == "csf-cli-pack"
    assert payload["created_at_utc"] == CREATED_AT
    assert len(payload["cells"]) == len(design.arms()) * len(design.fleet_seeds)
    assert payload["external_repository_bytes_included"] is False
    assert payload["executor_included"] is False
    assert payload["credentials_included"] is False
    stdout = capsys.readouterr().out
    assert "carries no external repository bytes, no executor, and no credentials." in stdout


def test_export_is_byte_reproducible_from_the_same_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_commit_check(monkeypatch)
    roots = _checkouts(tmp_path)
    module_path = _design_module(tmp_path)
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    CLI.main(_export_argv(roots, design_ref=f"{module_path}:DESIGN", output=first))
    CLI.main(_export_argv(roots, design_ref=f"{module_path}:DESIGN", output=second))

    assert first.read_bytes() == second.read_bytes()


def test_export_refuses_to_overwrite_without_the_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_commit_check(monkeypatch)
    roots = _checkouts(tmp_path)
    module_path = _design_module(tmp_path)
    output = tmp_path / "pack.json"
    output.write_text("existing", encoding="utf-8")

    code = CLI.main(_export_argv(roots, design_ref=f"{module_path}:DESIGN", output=output))

    assert code == 1
    assert "already exists" in capsys.readouterr().err
    assert output.read_text(encoding="utf-8") == "existing"


def test_export_refuses_a_checkout_at_the_wrong_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    roots = _checkouts(tmp_path)
    module_path = _design_module(tmp_path)
    output = tmp_path / "pack.json"

    code = CLI.main(_export_argv(roots, design_ref=f"{module_path}:DESIGN", output=output))

    assert code == 1
    assert "not a readable git checkout" in capsys.readouterr().err
    assert not output.exists()


def test_export_passes_a_library_refusal_through_verbatim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_commit_check(monkeypatch)
    roots = _checkouts(tmp_path)
    module_path = _design_module(tmp_path)
    output = tmp_path / "pack.json"

    code = CLI.main(
        _export_argv(
            roots,
            design_ref=f"{module_path}:DESIGN",
            output=output,
            extra=["--pack-id", "not a valid pack id"],
        )
    )

    assert code == 1
    # The library's own wording, not a friendlier paraphrase of it.
    assert "job pack could not be exported" in capsys.readouterr().err


# --- verify ------------------------------------------------------------------


def _exported_pack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _stub_commit_check(monkeypatch)
    roots = _checkouts(tmp_path)
    module_path = _design_module(tmp_path)
    output = tmp_path / "pack.json"
    assert CLI.main(_export_argv(roots, design_ref=f"{module_path}:DESIGN", output=output)) == 0
    return output


def test_verify_accepts_a_complete_intact_return(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pack_path = _exported_pack(tmp_path, monkeypatch)
    design = _design()
    results = _write_results(
        tmp_path / "returned",
        [_receipt(design, arm.label, seed) for arm in design.arms() for seed in design.fleet_seeds],
    )

    code = CLI.main(["verify", str(pack_path), str(results)])

    assert code == 0
    stdout = capsys.readouterr().out
    assert "status: verified" in stdout
    assert "a verified import is not a scientific admission" in stdout


def test_verify_exits_non_zero_on_a_partial_return(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pack_path = _exported_pack(tmp_path, monkeypatch)
    design = _design()
    every = [
        _receipt(design, arm.label, seed) for arm in design.arms() for seed in design.fleet_seeds
    ]
    results = _write_results(tmp_path / "returned", every[:-1])

    code = CLI.main(["verify", str(pack_path), str(results)])

    assert code == 1
    stdout = capsys.readouterr().out
    assert "status: partial" in stdout
    assert every[-1].request.run_id in stdout


def test_verify_refuses_a_receipt_this_pack_never_declared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pack_path = _exported_pack(tmp_path, monkeypatch)
    design = _design()
    other = _design(seeds=[7, 8, 9])
    results = _write_results(
        tmp_path / "returned",
        [
            *[
                _receipt(design, arm.label, seed)
                for arm in design.arms()
                for seed in design.fleet_seeds
            ],
            _receipt(other, "cap-2.5", 9),
        ],
    )

    code = CLI.main(["verify", str(pack_path), str(results)])

    assert code == 1
    stdout = capsys.readouterr().out
    assert "status: refused" in stdout
    assert "not a declared cell of this pack" in stdout


def test_verify_refuses_an_unreadable_returned_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pack_path = _exported_pack(tmp_path, monkeypatch)
    results = tmp_path / "returned"
    (results / "capcli-cap-2.5-fs0").mkdir(parents=True)
    (results / "capcli-cap-2.5-fs0" / "execution_receipt.json").write_text(
        "{not json", encoding="utf-8"
    )

    code = CLI.main(["verify", str(pack_path), str(results)])

    assert code == 1
    assert "not readable JSON" in capsys.readouterr().err


def test_verify_refuses_a_directory_with_no_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pack_path = _exported_pack(tmp_path, monkeypatch)
    results = tmp_path / "returned"
    results.mkdir()

    code = CLI.main(["verify", str(pack_path), str(results)])

    assert code == 1
    assert "no execution_receipt.json files found" in capsys.readouterr().err


def test_verify_refuses_a_pack_file_that_is_not_a_pack(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pack_path = tmp_path / "pack.json"
    pack_path.write_text(json.dumps({"schema_version": "1.0"}), encoding="utf-8")
    results = tmp_path / "returned"
    results.mkdir()

    code = CLI.main(["verify", str(pack_path), str(results)])

    assert code == 1
    assert "not a valid job pack" in capsys.readouterr().err


def test_verify_report_records_that_no_admission_was_granted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack_path = _exported_pack(tmp_path, monkeypatch)
    design = _design()
    results = _write_results(
        tmp_path / "returned",
        [_receipt(design, arm.label, seed) for arm in design.arms() for seed in design.fleet_seeds],
    )
    report = tmp_path / "reports" / "verification.json"

    code = CLI.main(["verify", str(pack_path), str(results), "--report-json", str(report)])

    assert code == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["admission_granted"] is False
    assert payload["scientific_admission"] is False
    assert payload["registry_write_performed"] is False


def test_verify_reports_a_failed_remote_cell_as_unfulfilled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pack_path = _exported_pack(tmp_path, monkeypatch)
    design = _design()
    receipts = [
        _receipt(design, arm.label, seed) for arm in design.arms() for seed in design.fleet_seeds
    ]
    failed = _receipt(design, "cap-1.0", design.fleet_seeds[-1], status=VecTerminalStatus.FAILED)
    results = _write_results(
        tmp_path / "returned",
        [item for item in receipts if item.request.run_id != failed.request.run_id] + [failed],
    )

    code = CLI.main(["verify", str(pack_path), str(results)])

    assert code == 1
    stdout = capsys.readouterr().out
    assert "status: partial" in stdout
    assert failed.request.run_id in stdout

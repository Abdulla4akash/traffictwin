"""Offline campaign verification: agreement, every disagreement, and read-only-ness.

Every fixture here is synthetic and built under ``tmp_path``. Nothing in this
module reads a committed campaign directory, opens a real registry, or imports a
`scripts/capacity_*.py` design constructor — a verifier's tests must not be able
to disturb the artifacts a real campaign is writing.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

from traffictwin.domain.enums import ExecutionMode, ExperimentStatus, RunStatus
from traffictwin.domain.experiment import Experiment
from traffictwin.domain.run import Run
from traffictwin.integration.vec_campaign.models import (
    VecCampaignApproval,
    VecCampaignArm,
    VecCampaignBudget,
    VecCampaignCell,
    VecCampaignCellState,
    VecCampaignDesign,
    VecCampaignPhase,
    VecCampaignReceipt,
    VecCampaignStatus,
)
from traffictwin.integration.vec_campaign.service import STANDING_CAMPAIGN_LIMITATIONS
from traffictwin.integration.vec_campaign.verify import (
    CAMPAIGN_RECEIPT_FILE,
    CELL_RECEIPT_FILE,
    CampaignVerificationError,
    CampaignVerificationReport,
    VerificationCheck,
    VerificationSeverity,
    load_campaign_receipt,
    load_design_from_module,
    render_verification_markdown,
    verify_campaign,
)
from traffictwin.integration.vec_fresh_admission.models import VecPairingSeedSource
from traffictwin.integration.vec_runner.models import (
    VecExecutionReceipt,
    VecFleet,
    VecRunnerFileEvidence,
    VecRunRequest,
    VecRuntimeEvidence,
    VecTerminalStatus,
    output_fingerprint,
)
from traffictwin.storage.registry import Registry

NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
INC_TRACE_SHA = "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"
INC_TRACE_FILE = "traces/trace_inc_fullrsu.npz"
PREDECLARATION_TEXT = "# Synthetic predeclaration\n\nfixed design\n"
OUTPUT_PAYLOADS = {
    "per-step.npz": b"per-step-bytes",
    "per-task.npz": b"per-task-bytes",
    "run.json": b'{"synthetic": true}',
}
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "verify_campaign.py"


def _cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_campaign_under_test", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CLI = _cli()


# --------------------------------------------------------------------------- #
# Synthetic campaign fixtures
# --------------------------------------------------------------------------- #


def _predeclaration(root: Path, text: str = PREDECLARATION_TEXT) -> str:
    path = root / "predeclaration.md"
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode()).hexdigest()


def _design(
    digest: str,
    *,
    seeds: list[int] | None = None,
    experiment_id: str = "vec-verify-unit",
    baseline_capacity: float = 2.5,
) -> VecCampaignDesign:
    return VecCampaignDesign(
        experiment_id=experiment_id,
        research_question="Does reduced per-vehicle RSU task capacity degrade deadline success?",
        run_id_prefix="capverify",
        phase=VecCampaignPhase.PILOT,
        approval=VecCampaignApproval(
            predeclaration_path="predeclaration.md",
            predeclaration_sha256=digest,
            approved_by="A. Owner",
            approved_role="repository owner",
            approved_at_utc="2026-07-27T12:00:00+00:00",
        ),
        trace_file=INC_TRACE_FILE,
        trace_sha256=INC_TRACE_SHA,
        actor_id="ukfleettrain_mappo_model_c_17",
        fleet=VecFleet.UK_2030,
        evaluator_seed=0,
        max_steps=3600,
        timeout_seconds=7200,
        baseline_arm=VecCampaignArm(label="cap-2.5", rsu_capacity_per_vehicle=baseline_capacity),
        variation_arms=[VecCampaignArm(label="cap-0.75", rsu_capacity_per_vehicle=0.75)],
        pairing_seed_source=VecPairingSeedSource.FLEET_SEED,
        fleet_seeds=seeds if seeds is not None else [0, 1, 2],
        primary_metric_key="tos.task.deadline_success.rate",
        budget=VecCampaignBudget(max_cells=12, max_total_output_bytes=1_000_000_000),
    )


def _execution_receipt(
    request: VecRunRequest, *, status: VecTerminalStatus = VecTerminalStatus.COMPLETED
) -> VecExecutionReceipt:
    outputs = [
        VecRunnerFileEvidence(
            path=name,
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
            media_type="application/octet-stream",
            read_only=True,
        )
        for name, payload in sorted(OUTPUT_PAYLOADS.items())
    ]
    return VecExecutionReceipt(
        status=status,
        request=request,
        request_fingerprint=request.fingerprint(),
        preflight_fingerprint="c" * 64,
        argv=[],
        started_at_utc="2026-07-27T00:00:00+00:00",
        finished_at_utc="2026-07-27T00:00:01+00:00",
        elapsed_seconds=1.0,
        exit_code=0,
        timed_out=False,
        cancellation_requested=False,
        runtime=VecRuntimeEvidence(
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
        ),
        repositories=[],
        inputs_before=[],
        inputs_after=[],
        logs=[],
        stdout_excerpt="",
        stderr_excerpt="",
        outputs=outputs,
        findings=[],
        output_fingerprint=output_fingerprint(outputs),
        external_repositories_modified=False,
        raw_inputs_modified=False,
        published=True,
    )


def _build_campaign(
    root: Path,
    design: VecCampaignDesign,
    *,
    registry: Registry | None = None,
) -> VecCampaignReceipt:
    """Write a complete, self-consistent, fully admitted synthetic campaign."""

    campaign_dir = root / "campaign"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    cells: list[VecCampaignCell] = []
    total_bytes = 0
    for seed in design.fleet_seeds:
        for arm in design.arms():
            request = design.cell_request(arm, seed)
            directory_name = f"{arm.label}-fs{seed}"
            cell_dir = campaign_dir / directory_name
            cell_dir.mkdir(parents=True, exist_ok=True)
            for name, payload in OUTPUT_PAYLOADS.items():
                (cell_dir / name).write_bytes(payload)
            receipt = _execution_receipt(request)
            (cell_dir / CELL_RECEIPT_FILE).write_text(receipt.model_dump_json(), encoding="utf-8")
            fingerprint = receipt.fingerprint()
            registry_run_id = f"vec:fresh:{fingerprint[:16]}"
            cell_bytes = sum(item.size_bytes for item in receipt.outputs)
            total_bytes += cell_bytes
            cells.append(
                VecCampaignCell(
                    arm_label=arm.label,
                    fleet_seed=seed,
                    run_id=request.run_id,
                    request_fingerprint=request.fingerprint(),
                    state=VecCampaignCellState.ADMITTED,
                    output_directory_name=directory_name,
                    elapsed_seconds=1.0,
                    output_bytes=cell_bytes,
                    receipt_fingerprint=fingerprint,
                    registry_run_id=registry_run_id,
                    admission_stable_fingerprint="e" * 64,
                    detail="executed in 1.000s and admitted",
                )
            )
            if registry is not None:
                _admit(registry, design, arm.label, seed, registry_run_id)

    campaign_receipt = VecCampaignReceipt(
        status=VecCampaignStatus.COMPLETED,
        design_fingerprint=design.fingerprint(),
        experiment_id=design.experiment_id,
        phase=design.phase,
        approval=design.approval,
        predeclaration_verified_unchanged=True,
        experiment_registered=True,
        cells=cells,
        planned_cell_count=len(cells),
        admitted_cell_count=len(cells),
        reused_cell_count=0,
        failed_cell_count=0,
        skipped_cell_count=0,
        total_output_bytes=total_bytes,
        total_elapsed_seconds=float(len(cells)),
        started_at_utc="2026-07-27T00:00:00+00:00",
        finished_at_utc="2026-07-27T01:00:00+00:00",
        limitations=list(STANDING_CAMPAIGN_LIMITATIONS),
    )
    (campaign_dir / CAMPAIGN_RECEIPT_FILE).write_text(
        campaign_receipt.canonical_json(), encoding="utf-8"
    )
    return campaign_receipt


def _registry(root: Path, design: VecCampaignDesign) -> Registry:
    registry = Registry(root / "registry.sqlite")
    registry.initialize()
    registry.add_experiment(
        Experiment(
            experiment_id=design.experiment_id,
            research_question=design.research_question,
            baseline_seed_id=design.baseline_arm.label,
            variation_seed_ids=[arm.label for arm in design.variation_arms],
            algorithms=[design.actor_id],
            common_random_seed_set=list(design.fleet_seeds),
            planned_replicates=len(design.fleet_seeds),
            status=ExperimentStatus.PLANNED,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    return registry


def _admit(
    registry: Registry,
    design: VecCampaignDesign,
    arm_label: str,
    fleet_seed: int,
    registry_run_id: str,
) -> None:
    registry.add_run(
        Run(
            run_id=registry_run_id,
            experiment_id=design.experiment_id,
            seed_id=arm_label,
            algorithm=design.actor_id,
            random_seed=fleet_seed,
            execution_mode=ExecutionMode.EXPORT_ONLY,
            status=RunStatus.REGISTERED,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    registry.store_metric_collection(
        run_id=registry_run_id,
        metric_version="1.0",
        source_fingerprint=None,
        payload_json=json.dumps({"run_id": registry_run_id, "results": []}),
    )


def _codes(report: CampaignVerificationReport) -> set[str]:
    return {finding.code for finding in report.findings}


# --------------------------------------------------------------------------- #
# The agreeing case
# --------------------------------------------------------------------------- #


def test_consistent_campaign_verifies_with_no_findings(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    registry = _registry(tmp_path, design)
    _build_campaign(tmp_path, design, registry=registry)

    report = verify_campaign(
        design,
        tmp_path / "campaign",
        registry_path=tmp_path / "registry.sqlite",
        predeclaration_root=tmp_path,
    )

    assert report.passed is True
    assert report.findings == []
    assert report.cells_examined == 6
    assert report.executed_cells_examined == 6
    assert report.admitted_cells_examined == 6
    assert report.output_files_hashed == 18
    assert report.checks_not_run == []
    assert report.design_fingerprint_expected == report.design_fingerprint_recorded


def test_report_carries_the_read_only_literals_and_limitations(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    _build_campaign(tmp_path, design)

    report = verify_campaign(design, tmp_path / "campaign", predeclaration_root=tmp_path)

    assert report.repairs_performed is False
    assert report.writes_performed is False
    assert len(report.limitations) >= 4
    assert any("not a scientific finding" in item for item in report.limitations)


def test_verification_writes_nothing_into_the_campaign_directory(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    registry = _registry(tmp_path, design)
    _build_campaign(tmp_path, design, registry=registry)
    campaign_dir = tmp_path / "campaign"

    def snapshot() -> dict[str, tuple[int, str]]:
        return {
            str(path.relative_to(campaign_dir)): (
                path.stat().st_size,
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
            for path in sorted(campaign_dir.rglob("*"))
            if path.is_file()
        }

    before = snapshot()
    predeclaration_before = (tmp_path / "predeclaration.md").read_bytes()

    verify_campaign(
        design,
        campaign_dir,
        registry_path=tmp_path / "registry.sqlite",
        predeclaration_root=tmp_path,
    )

    assert snapshot() == before
    assert (tmp_path / "predeclaration.md").read_bytes() == predeclaration_before
    assert len(Registry(tmp_path / "registry.sqlite").list_runs()) == 6


# --------------------------------------------------------------------------- #
# Design, grid, and approval disagreements
# --------------------------------------------------------------------------- #


def test_design_fingerprint_mismatch_fails(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    _build_campaign(tmp_path, design)
    other = _design(digest, baseline_capacity=3.0)

    report = verify_campaign(other, tmp_path / "campaign", predeclaration_root=tmp_path)

    assert report.passed is False
    assert "DESIGN_FINGERPRINT_MISMATCH" in _codes(report)
    assert all(
        finding.severity is VerificationSeverity.FAILURE
        for finding in report.findings
        if finding.code == "DESIGN_FINGERPRINT_MISMATCH"
    )


def test_experiment_id_mismatch_fails(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    _build_campaign(tmp_path, design)
    other = _design(digest, experiment_id="vec-verify-other")

    report = verify_campaign(other, tmp_path / "campaign", predeclaration_root=tmp_path)

    assert report.passed is False
    assert "EXPERIMENT_ID_MISMATCH" in _codes(report)


def test_cell_missing_from_receipt_fails(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest, seeds=[0, 1, 2])
    _build_campaign(tmp_path, design)
    wider = _design(digest, seeds=[0, 1, 2, 3])

    report = verify_campaign(wider, tmp_path / "campaign", predeclaration_root=tmp_path)

    assert report.passed is False
    codes = _codes(report)
    assert "CELL_MISSING_FROM_RECEIPT" in codes
    assert "DESIGN_FINGERPRINT_MISMATCH" in codes


def test_cell_not_in_design_fails(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest, seeds=[0, 1, 2, 3])
    _build_campaign(tmp_path, design)
    narrower = _design(digest, seeds=[0, 1, 2])

    report = verify_campaign(narrower, tmp_path / "campaign", predeclaration_root=tmp_path)

    assert report.passed is False
    assert "CELL_NOT_IN_DESIGN" in _codes(report)


def test_missing_predeclaration_warns_and_does_not_silently_pass(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    _build_campaign(tmp_path, design)
    (tmp_path / "predeclaration.md").unlink()

    report = verify_campaign(design, tmp_path / "campaign", predeclaration_root=tmp_path)

    finding = next(f for f in report.findings if f.code == "PREDECLARATION_MISSING")
    assert finding.severity is VerificationSeverity.WARNING
    assert finding.check is VerificationCheck.APPROVAL
    assert report.passed is True


def test_predeclaration_edited_after_approval_fails(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    _build_campaign(tmp_path, design)
    (tmp_path / "predeclaration.md").write_text("# edited after approval\n", encoding="utf-8")

    report = verify_campaign(design, tmp_path / "campaign", predeclaration_root=tmp_path)

    assert report.passed is False
    finding = next(f for f in report.findings if f.code == "PREDECLARATION_DIGEST_MISMATCH")
    assert finding.expected == digest
    assert finding.observed != digest


# --------------------------------------------------------------------------- #
# Cell receipt and output disagreements
# --------------------------------------------------------------------------- #


def test_tampered_output_payload_fails_on_hash(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    _build_campaign(tmp_path, design)
    (tmp_path / "campaign" / "cap-0.75-fs1" / "run.json").write_bytes(b'{"synthetic": false}')

    report = verify_campaign(design, tmp_path / "campaign", predeclaration_root=tmp_path)

    assert report.passed is False
    codes = _codes(report)
    assert "OUTPUT_FILE_HASH_MISMATCH" in codes
    assert "OUTPUT_FILE_SIZE_MISMATCH" in codes
    finding = next(f for f in report.findings if f.code == "OUTPUT_FILE_HASH_MISMATCH")
    assert finding.subject == "cap-0.75-fs1/run.json"


def test_deleted_output_payload_warns_and_is_not_hashed(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    _build_campaign(tmp_path, design)
    (tmp_path / "campaign" / "cap-2.5-fs0" / "per-task.npz").unlink()

    report = verify_campaign(design, tmp_path / "campaign", predeclaration_root=tmp_path)

    finding = next(f for f in report.findings if f.code == "OUTPUT_FILE_MISSING")
    assert finding.severity is VerificationSeverity.WARNING
    assert report.output_files_hashed == 17


def test_skipping_output_hashes_is_recorded_not_implied(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    _build_campaign(tmp_path, design)
    (tmp_path / "campaign" / "cap-0.75-fs1" / "run.json").write_bytes(b"tampered")

    report = verify_campaign(
        design, tmp_path / "campaign", predeclaration_root=tmp_path, hash_outputs=False
    )

    assert VerificationCheck.OUTPUT_HASHES in report.checks_not_run
    assert VerificationCheck.OUTPUT_HASHES not in report.checks_run
    assert report.output_files_hashed == 0
    assert "OUTPUT_FILE_HASH_MISMATCH" not in _codes(report)


def test_swapped_cell_receipt_fails_on_request_fingerprint(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    _build_campaign(tmp_path, design)
    source = tmp_path / "campaign" / "cap-2.5-fs0" / CELL_RECEIPT_FILE
    target = tmp_path / "campaign" / "cap-0.75-fs0" / CELL_RECEIPT_FILE
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    report = verify_campaign(design, tmp_path / "campaign", predeclaration_root=tmp_path)

    assert report.passed is False
    codes = _codes(report)
    assert "RECEIPT_REQUEST_FINGERPRINT_MISMATCH" in codes
    assert "RECEIPT_RUN_ID_MISMATCH" in codes
    assert "CELL_RECEIPT_FINGERPRINT_MISMATCH" in codes


def test_missing_cell_directory_warns_without_claiming_agreement(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    _build_campaign(tmp_path, design)
    cell_dir = tmp_path / "campaign" / "cap-2.5-fs2"
    for path in cell_dir.iterdir():
        path.unlink()
    cell_dir.rmdir()

    report = verify_campaign(design, tmp_path / "campaign", predeclaration_root=tmp_path)

    finding = next(f for f in report.findings if f.code == "CELL_DIRECTORY_MISSING")
    assert finding.severity is VerificationSeverity.WARNING
    assert finding.subject == "cap-2.5-fs2"


def test_unparseable_cell_receipt_fails(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    _build_campaign(tmp_path, design)
    (tmp_path / "campaign" / "cap-2.5-fs1" / CELL_RECEIPT_FILE).write_text("{}", encoding="utf-8")

    report = verify_campaign(design, tmp_path / "campaign", predeclaration_root=tmp_path)

    assert report.passed is False
    assert "CELL_RECEIPT_INVALID" in _codes(report)


# --------------------------------------------------------------------------- #
# Registry admission
# --------------------------------------------------------------------------- #


def test_registry_checks_are_reported_as_not_run_when_no_registry_given(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    _build_campaign(tmp_path, design)

    report = verify_campaign(design, tmp_path / "campaign", predeclaration_root=tmp_path)

    assert VerificationCheck.REGISTRY_ADMISSION in report.checks_not_run
    assert report.passed is True


def test_admitted_cell_absent_from_registry_fails(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    registry = _registry(tmp_path, design)
    receipt = _build_campaign(tmp_path, design, registry=None)
    for cell in receipt.cells[:-1]:
        assert cell.registry_run_id is not None
        _admit(registry, design, cell.arm_label, cell.fleet_seed, cell.registry_run_id)

    report = verify_campaign(
        design,
        tmp_path / "campaign",
        registry_path=tmp_path / "registry.sqlite",
        predeclaration_root=tmp_path,
    )

    assert report.passed is False
    codes = _codes(report)
    assert "REGISTRY_RUN_MISSING" in codes
    assert "METRIC_COLLECTION_MISSING" in codes


def test_registry_run_attached_to_wrong_arm_fails(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    registry = _registry(tmp_path, design)
    receipt = _build_campaign(tmp_path, design, registry=None)
    for index, cell in enumerate(receipt.cells):
        assert cell.registry_run_id is not None
        arm_label = "cap-0.75" if index == 0 else cell.arm_label
        _admit(registry, design, arm_label, cell.fleet_seed, cell.registry_run_id)

    report = verify_campaign(
        design,
        tmp_path / "campaign",
        registry_path=tmp_path / "registry.sqlite",
        predeclaration_root=tmp_path,
    )

    assert report.passed is False
    assert "REGISTRY_RUN_ARM_MISMATCH" in _codes(report)


def test_unregistered_experiment_plan_fails(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    registry = Registry(tmp_path / "registry.sqlite")
    registry.initialize()
    receipt = _build_campaign(tmp_path, design, registry=None)
    for cell in receipt.cells:
        assert cell.registry_run_id is not None
        _admit(registry, design, cell.arm_label, cell.fleet_seed, cell.registry_run_id)

    report = verify_campaign(
        design,
        tmp_path / "campaign",
        registry_path=tmp_path / "registry.sqlite",
        predeclaration_root=tmp_path,
    )

    assert report.passed is False
    assert "REGISTRY_EXPERIMENT_MISSING" in _codes(report)


def test_unreachable_registry_warns_once_rather_than_per_cell(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    _build_campaign(tmp_path, design)

    report = verify_campaign(
        design,
        tmp_path / "campaign",
        registry_path=tmp_path / "absent-registry.sqlite",
        predeclaration_root=tmp_path,
    )

    warnings = [f for f in report.findings if f.code == "REGISTRY_UNREADABLE"]
    assert len(warnings) == 1
    assert warnings[0].severity is VerificationSeverity.WARNING
    assert VerificationCheck.REGISTRY_ADMISSION in report.checks_not_run


# --------------------------------------------------------------------------- #
# Loading, rendering, and unverifiable inputs
# --------------------------------------------------------------------------- #


def test_load_design_from_module_reads_a_constructor(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    module = tmp_path / "synthetic_campaign.py"
    module.write_text(
        "from tests.unit.test_vec_campaign_verify import _design\n\n\n"
        "def synthetic_design():\n"
        f"    return _design({digest!r})\n",
        encoding="utf-8",
    )

    design = load_design_from_module(module, "synthetic_design")

    assert design.experiment_id == "vec-verify-unit"
    assert design.fingerprint() == _design(digest).fingerprint()


def test_load_design_rejects_a_missing_module_or_attribute(tmp_path: Path) -> None:
    module = tmp_path / "empty_campaign.py"
    module.write_text("VALUE = 3\n", encoding="utf-8")

    with pytest.raises(CampaignVerificationError, match="missing or unsafe"):
        load_design_from_module(tmp_path / "absent.py", "design")
    with pytest.raises(CampaignVerificationError, match="no attribute"):
        load_design_from_module(module, "design")
    with pytest.raises(CampaignVerificationError, match="not a VecCampaignDesign"):
        load_design_from_module(module, "VALUE")


def test_missing_campaign_receipt_is_unverifiable_not_a_failure(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    (tmp_path / "campaign").mkdir()

    with pytest.raises(CampaignVerificationError, match="campaign receipt is missing"):
        verify_campaign(design, tmp_path / "campaign")
    with pytest.raises(CampaignVerificationError):
        load_campaign_receipt(tmp_path / "campaign")


def test_markdown_exhibit_states_the_verdict_and_every_finding(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    _build_campaign(tmp_path, design)
    (tmp_path / "campaign" / "cap-0.75-fs1" / "run.json").write_bytes(b'{"synthetic": false}')

    report = verify_campaign(design, tmp_path / "campaign", predeclaration_root=tmp_path)
    markdown = render_verification_markdown(report)

    assert markdown.startswith("# Campaign verification — vec-verify-unit (FAIL)")
    assert "OUTPUT_FILE_HASH_MISMATCH" in markdown
    assert "## Limitations" in markdown
    assert markdown == render_verification_markdown(report)


def test_markdown_exhibit_reports_a_clean_pass_without_a_findings_table(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    _build_campaign(tmp_path, design)

    markdown = render_verification_markdown(
        verify_campaign(design, tmp_path / "campaign", predeclaration_root=tmp_path)
    )

    assert "(PASS)" in markdown
    assert "No finding: every recorded artifact agreed with the supplied design." in markdown
    assert "| Severity |" not in markdown


# --------------------------------------------------------------------------- #
# The command line: exit codes and its refusal to overwrite
# --------------------------------------------------------------------------- #


def _design_module(root: Path, digest: str) -> Path:
    module = root / "synthetic_campaign.py"
    module.write_text(
        "from tests.unit.test_vec_campaign_verify import _design\n\n\n"
        "def synthetic_design():\n"
        f"    return _design({digest!r})\n",
        encoding="utf-8",
    )
    return module


def _argv(root: Path, module: Path, *extra: str) -> list[str]:
    return [
        "--design-module",
        str(module),
        "--design-attr",
        "synthetic_design",
        "--campaign-dir",
        str(root / "campaign"),
        "--predeclaration-root",
        str(root),
        *extra,
    ]


def test_cli_exits_zero_on_a_consistent_campaign(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    _build_campaign(tmp_path, design)
    module = _design_module(tmp_path, digest)

    assert CLI.main(_argv(tmp_path, module)) == CLI.EXIT_PASS


def test_cli_exits_one_when_a_check_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    _build_campaign(tmp_path, design)
    module = _design_module(tmp_path, digest)
    (tmp_path / "campaign" / "cap-0.75-fs1" / "run.json").write_bytes(b'{"synthetic": false}')

    assert CLI.main(_argv(tmp_path, module)) == CLI.EXIT_FAIL
    assert "OUTPUT_FILE_HASH_MISMATCH" in capsys.readouterr().out


def test_cli_exits_two_when_verification_cannot_be_performed(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    module = _design_module(tmp_path, digest)
    (tmp_path / "campaign").mkdir()

    assert CLI.main(_argv(tmp_path, module)) == CLI.EXIT_UNVERIFIABLE


def test_cli_writes_exhibits_only_where_named_and_never_clobbers(tmp_path: Path) -> None:
    digest = _predeclaration(tmp_path)
    design = _design(digest)
    _build_campaign(tmp_path, design)
    module = _design_module(tmp_path, digest)
    markdown_out = tmp_path / "out" / "verification.md"
    json_out = tmp_path / "out" / "verification.json"

    assert (
        CLI.main(
            _argv(
                tmp_path, module, "--markdown-out", str(markdown_out), "--json-out", str(json_out)
            )
        )
        == CLI.EXIT_PASS
    )
    assert "(PASS)" in markdown_out.read_text(encoding="utf-8")
    assert json.loads(json_out.read_text(encoding="utf-8"))["passed"] is True

    markdown_out.write_text("owner's own notes\n", encoding="utf-8")
    assert (
        CLI.main(_argv(tmp_path, module, "--markdown-out", str(markdown_out)))
        == CLI.EXIT_UNVERIFIABLE
    )
    assert markdown_out.read_text(encoding="utf-8") == "owner's own notes\n"

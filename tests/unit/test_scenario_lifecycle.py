"""Scenario lifecycle integration: exact binding, replay and adversarial gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from traffictwin.experiments import (
    ObjectiveDirection,
    PairedStudyConfig,
    evaluate_paired_statistical_study,
)
from traffictwin.integration.vec_campaign.analysis import (
    STANDING_ANALYSIS_LIMITATIONS,
    VecArmDescriptives,
    VecCampaignAnalysis,
    VecCampaignComparison,
)
from traffictwin.integration.vec_campaign.models import (
    VecCampaignApproval,
    VecCampaignCell,
    VecCampaignCellState,
    VecCampaignDesign,
    VecCampaignReceipt,
    VecCampaignStatus,
)
from traffictwin.platform.outcome_predictor import LoadedFit, load_outcome_predictor_fit
from traffictwin.platform.scenario_lifecycle import (
    ScenarioAdmissionRecord,
    ScenarioExecutionDeviation,
    ScenarioLifecycleConfig,
    ScenarioLifecycleError,
    ScenarioLifecycleService,
)
from traffictwin.platform.scenario_registry import ScenarioRegistryError
from traffictwin.platform.whatif_composer import (
    ComposerDraft,
    ComposerForm,
    NaturalLanguageTranslation,
    compose_scenario,
)

ROOT = Path(__file__).resolve().parents[2]
FIT_PATH = ROOT / "docs" / "platform" / "outcome_predictor_fit.json"
NOW = "2026-08-02T10:00:00+00:00"
LATER = "2026-08-02T10:05:00+00:00"


def _admission_authority(record: ScenarioAdmissionRecord, raw: bytes) -> bool:
    """Synthetic external owner policy used only by this test module."""

    return (
        record.decided_by == "A. Owner"
        and record.decided_role == "repository owner"
        and bool(hashlib.sha256(raw).hexdigest())
    )


@pytest.fixture(scope="module")
def loaded() -> LoadedFit:
    return load_outcome_predictor_fit(FIT_PATH)


def _draft(
    loaded: LoadedFit,
    *,
    capacity: float = 0.75,
    translation: NaturalLanguageTranslation | None = None,
) -> ComposerDraft:
    form = ComposerForm(trace="inc", capacity=capacity, fleet_seeds=(30, 31, 32))
    return compose_scenario(form, loaded, generated_at_utc=NOW, translation=translation)


def _service(tmp_path: Path) -> tuple[ScenarioLifecycleService, Path, ScenarioLifecycleConfig]:
    authority = tmp_path / "authority"
    authority.mkdir(parents=True)
    config = ScenarioLifecycleConfig(
        log_path=(tmp_path / "scenario-lifecycle.jsonl").resolve(),
        authority_root=authority.resolve(),
    )
    return (
        ScenarioLifecycleService(config, admission_authority_validator=_admission_authority),
        authority,
        config,
    )


def _write_model(path: Path, model: BaseModel) -> Path:
    payload = model.model_dump(mode="json")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _approved_design(authority: Path, draft: ComposerDraft) -> tuple[VecCampaignDesign, Path]:
    predeclaration = authority / "approved-predeclaration.md"
    predeclaration.write_text("# Reviewed scenario predeclaration\n", encoding="utf-8")
    approval = VecCampaignApproval(
        predeclaration_path=predeclaration.name,
        predeclaration_sha256=_sha(predeclaration),
        approved_by="A. Owner",
        approved_role="repository owner",
        approved_at_utc=NOW,
    )
    source = draft.design_draft
    design = VecCampaignDesign(
        schema_version="1.0",
        method_version=source["schema_mirrors"],
        experiment_id=source["experiment_id"],
        research_question=source["research_question"],
        run_id_prefix=source["run_id_prefix"],
        phase=source["phase"],
        approval=approval,
        trace_file=source["trace_file"],
        trace_sha256=source["trace_sha256"],
        actor_id=source["actor_id"],
        fleet=source["fleet"],
        evaluator_seed=source["evaluator_seed"],
        max_steps=source["max_steps"],
        timeout_seconds=source["timeout_seconds"],
        baseline_arm=source["baseline_arm"],
        variation_arms=source["variation_arms"],
        pairing_seed_source=source["pairing_seed_source"],
        fleet_seeds=source["fleet_seeds"],
        primary_metric_key=source["primary_metric_key"],
        budget=source["budget"],
    )
    return design, _write_model(authority / "approved-design.json", design)


def _receipt(design: VecCampaignDesign) -> VecCampaignReceipt:
    cells: list[VecCampaignCell] = []
    for arm in design.arms():
        for seed in design.fleet_seeds:
            request = design.cell_request(arm, seed)
            cells.append(
                VecCampaignCell(
                    arm_label=arm.label,
                    fleet_seed=seed,
                    run_id=request.run_id,
                    request_fingerprint=request.fingerprint(),
                    state=VecCampaignCellState.ADMITTED,
                    output_directory_name=f"{arm.label}-fs{seed}",
                    elapsed_seconds=1.0,
                    output_bytes=10,
                    receipt_fingerprint=hashlib.sha256(request.run_id.encode()).hexdigest(),
                    registry_run_id=f"registry-{arm.label}-fs{seed}",
                    admission_stable_fingerprint=hashlib.sha256(
                        f"admission:{request.run_id}".encode()
                    ).hexdigest(),
                    detail="synthetic admitted test cell",
                )
            )
    return VecCampaignReceipt(
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
        total_output_bytes=10 * len(cells),
        total_elapsed_seconds=float(len(cells)),
        started_at_utc=NOW,
        finished_at_utc=LATER,
        limitations=["Synthetic lifecycle fixture; no scientific result."],
    )


def _analysis(design: VecCampaignDesign) -> VecCampaignAnalysis:
    config = PairedStudyConfig(
        experiment_id=design.experiment_id,
        baseline_seed_id=design.baseline_arm.label,
        variation_seed_id=design.variation_arms[0].label,
        algorithm=design.actor_id,
        metric_key=design.primary_metric_key,
        objective=ObjectiveDirection.MAXIMISE,
        expected_random_seeds=design.fleet_seeds,
    )
    study = evaluate_paired_statistical_study([], config)
    return VecCampaignAnalysis(
        experiment_id=design.experiment_id,
        design_fingerprint=design.fingerprint(),
        campaign_status="completed",
        primary_metric_key=design.primary_metric_key,
        baseline_label=design.baseline_arm.label,
        admitted_collection_count=0,
        comparisons=[
            VecCampaignComparison(
                variation_label=design.variation_arms[0].label,
                study_status=study.status.value,
                admitted_pair_count=0,
                study=study,
            )
        ],
        primary_descriptives=[
            VecArmDescriptives(
                arm_label=design.baseline_arm.label,
                metric_key=design.primary_metric_key,
                seed_values={"30": 0.5},
                mean=0.5,
                minimum=0.5,
                maximum=0.5,
            )
        ],
        generated_at_utc=LATER,
        limitations=list(STANDING_ANALYSIS_LIMITATIONS),
    )


def _register(service: ScenarioLifecycleService, draft: ComposerDraft) -> tuple[str, str]:
    receipt = service.register_draft(draft, revision=1)
    return receipt.scenario_id, receipt.event_digest


def _approve_and_execute(
    service: ScenarioLifecycleService,
    authority: Path,
    draft: ComposerDraft,
) -> tuple[str, VecCampaignDesign, Path, Path, str]:
    scenario_id, genesis = _register(service, draft)
    design, design_path = _approved_design(authority, draft)
    approved = service.bind_approval(scenario_id, genesis, design_path)
    receipt_path = _write_model(authority / "execution-receipt.json", _receipt(design))
    executed = service.import_execution_receipt(scenario_id, approved.event_digest, receipt_path)
    return scenario_id, design, design_path, receipt_path, executed.event_digest


def test_template_registration_is_exact_idempotent_and_path_free(
    loaded: LoadedFit, tmp_path: Path
) -> None:
    service, authority, config = _service(tmp_path)
    draft = _draft(loaded)
    first = service.register_draft(draft, revision=1)
    retry = service.register_draft(draft, revision=1)
    view = service.get_view(first.scenario_id)

    assert retry.idempotent_replay
    assert retry.event_digest == first.event_digest
    assert view.draft_mode == "template"
    assert view.timeline.scenario.evidence is False
    assert view.timeline.scenario.prediction is True
    assert view.timeline.scenario.revision == 1
    assert (
        view.timeline.scenario.draft_predeclaration_digest
        == hashlib.sha256(draft.predeclaration_markdown.encode()).hexdigest()
    )
    raw_log = config.log_path.read_text(encoding="utf-8")
    assert str(authority) not in raw_log
    assert draft.predeclaration_markdown not in raw_log


def test_deepseek_registration_carries_only_the_translation_digests(
    loaded: LoadedFit, tmp_path: Path
) -> None:
    service, _, config = _service(tmp_path)
    form = ComposerForm(trace="inc", capacity=0.75, fleet_seeds=(30, 31, 32))
    hidden_input = "owner sentence that must never enter the lifecycle log"
    hidden_response = '{"trace":"inc","capacity":0.75}'
    translation = NaturalLanguageTranslation(
        prompt_template_digest="1" * 64,
        input_digest=hashlib.sha256(hidden_input.encode()).hexdigest(),
        response_digest=hashlib.sha256(hidden_response.encode()).hexdigest(),
        form=form,
    )
    draft = _draft(loaded, translation=translation)
    receipt = service.register_draft(draft, revision=1)
    view = service.get_view(receipt.scenario_id)

    assert view.draft_mode == "deepseek_json_form"
    assert view.llm_prompt_template_digest == "1" * 64
    assert view.llm_input_digest == translation.input_digest
    assert view.llm_response_digest == translation.response_digest
    log = config.log_path.read_text(encoding="utf-8")
    assert hidden_input not in log
    assert hidden_response not in log
    assert "credential" not in log.lower()

    prose_bearing = draft.model_copy(
        update={"drafted_by": {**draft.drafted_by, "submitted_prose": hidden_input}}
    )
    with pytest.raises(ScenarioLifecycleError) as extra:
        service.register_draft(prose_bearing, revision=1)
    assert extra.value.code == "DRAFT_PROVENANCE_INVALID"


def test_revision_lineage_requires_one_changed_child(loaded: LoadedFit, tmp_path: Path) -> None:
    service, _, _ = _service(tmp_path)
    first_draft = _draft(loaded)
    first = service.register_draft(first_draft, revision=1)
    changed = _draft(loaded, capacity=1.0)
    second = service.register_draft(changed, revision=2, parent_scenario_id=first.scenario_id)
    assert service.get_view(second.scenario_id).parent_scenario_id == first.scenario_id

    with pytest.raises(ScenarioLifecycleError) as unchanged:
        service.register_draft(first_draft, revision=2, parent_scenario_id=first.scenario_id)
    assert unchanged.value.code == "REVISION_CONFLICT"
    with pytest.raises(ScenarioLifecycleError) as sibling:
        service.register_draft(
            _draft(loaded, capacity=1.25),
            revision=2,
            parent_scenario_id=first.scenario_id,
        )
    assert sibling.value.code == "REVISION_CONFLICT"
    with pytest.raises(ScenarioLifecycleError) as missing:
        service.register_draft(changed, revision=3)
    assert missing.value.code == "REVISION_REQUIRED"


def test_approval_execution_retries_and_replay_are_deterministic(
    loaded: LoadedFit, tmp_path: Path
) -> None:
    service, authority, config = _service(tmp_path)
    draft = _draft(loaded)
    scenario_id, genesis = _register(service, draft)
    design, design_path = _approved_design(authority, draft)
    approved = service.bind_approval(scenario_id, genesis, design_path)
    assert service.bind_approval(scenario_id, genesis, design_path).idempotent_replay
    receipt_path = _write_model(authority / "execution-receipt.json", _receipt(design))
    executed = service.import_execution_receipt(scenario_id, approved.event_digest, receipt_path)
    assert service.import_execution_receipt(
        scenario_id, approved.event_digest, receipt_path
    ).idempotent_replay

    before = service.get_view(scenario_id)
    replayed = ScenarioLifecycleService(config).get_view(scenario_id)
    assert replayed == before
    assert replayed.timeline.head_digest == executed.event_digest
    assert replayed.timeline.approved and replayed.timeline.executed
    assert replayed.timeline.admission_status is None
    assert replayed.timeline.scenario.evidence is False


def test_complete_import_chain_keeps_deviation_and_standing_separate(
    loaded: LoadedFit, tmp_path: Path
) -> None:
    service, authority, config = _service(tmp_path)
    scenario_id, design, _, receipt_path, execution_head = _approve_and_execute(
        service, authority, _draft(loaded)
    )
    deviation = ScenarioExecutionDeviation(
        scenario_id=scenario_id,
        approved_design_fingerprint=design.fingerprint(),
        source_receipt_digest=_sha(receipt_path),
        deviation_code="CELL_RETRIED",
        summary="One synthetic cell was retried and remains displayed.",
        intended_digest="2" * 64,
        observed_digest="3" * 64,
        recorded_at_utc=LATER,
        scientific_settings_changed=False,
        metric_based_selection_occurred=False,
    )
    deviation_path = _write_model(authority / "deviation.json", deviation)
    deviated = service.import_deviation(scenario_id, execution_head, deviation_path)
    analysis_path = _write_model(authority / "analysis.json", _analysis(design))
    analysed = service.import_analysis(scenario_id, deviated.event_digest, analysis_path)
    admission = ScenarioAdmissionRecord(
        scenario_id=scenario_id,
        approved_design_fingerprint=design.fingerprint(),
        source_receipt_digest=_sha(receipt_path),
        analysis_artifact_digest=_sha(analysis_path),
        status="admitted",
        decision_origin="explicit_human_owner_direction",
        decided_by="A. Owner",
        decided_role="repository owner",
        decided_at_utc=LATER,
        limitations=("Synthetic lifecycle fixture; no external evidence was created.",),
    )
    admission_path = _write_model(authority / "admission.json", admission)
    without_authority = ScenarioLifecycleService(config)
    with pytest.raises(ScenarioLifecycleError) as missing_authority:
        without_authority.import_admission(scenario_id, analysed.event_digest, admission_path)
    assert missing_authority.value.code == "ADMISSION_AUTHORITY_MISSING"
    admitted = service.import_admission(scenario_id, analysed.event_digest, admission_path)

    view = service.get_view(scenario_id)
    assert view.timeline.head_digest == admitted.event_digest
    assert view.timeline.deviations == ("CELL_RETRIED",)
    assert view.timeline.analysed
    assert view.timeline.admission_status == "admitted"
    assert view.timeline.scenario.evidence is False
    assert service.admitted_views() == (view,)
    assert (
        ScenarioLifecycleService(
            config, admission_authority_validator=_admission_authority
        ).get_view(scenario_id)
        == view
    )


def test_stale_prior_and_changed_approved_design_refuse(loaded: LoadedFit, tmp_path: Path) -> None:
    service, authority, _ = _service(tmp_path)
    draft = _draft(loaded)
    scenario_id, genesis = _register(service, draft)
    design, design_path = _approved_design(authority, draft)
    approved = service.bind_approval(scenario_id, genesis, design_path)
    receipt_path = _write_model(authority / "execution-receipt.json", _receipt(design))
    with pytest.raises(ScenarioRegistryError) as stale:
        service.import_execution_receipt(scenario_id, genesis, receipt_path)
    assert stale.value.code == "PRIOR_EVENT_MISMATCH"

    other_service, other_authority, _ = _service(tmp_path / "other")
    other_draft = _draft(loaded)
    other_id, other_genesis = _register(other_service, other_draft)
    changed, changed_path = _approved_design(other_authority, other_draft)
    changed = changed.model_copy(update={"max_steps": changed.max_steps - 1})
    _write_model(changed_path, changed)
    with pytest.raises(ScenarioLifecycleError) as mismatch:
        other_service.bind_approval(other_id, other_genesis, changed_path)
    assert mismatch.value.code == "APPROVAL_DIGEST_MISMATCH"
    assert approved.event_type == "approval_bound"


def test_changed_predeclaration_and_mismatched_execution_refuse(
    loaded: LoadedFit, tmp_path: Path
) -> None:
    service, authority, _ = _service(tmp_path)
    draft = _draft(loaded)
    scenario_id, genesis = _register(service, draft)
    design, design_path = _approved_design(authority, draft)
    (authority / design.approval.predeclaration_path).write_text(
        "# changed after approval\n", encoding="utf-8"
    )
    with pytest.raises(ScenarioLifecycleError) as changed:
        service.bind_approval(scenario_id, genesis, design_path)
    assert changed.value.code == "APPROVAL_DIGEST_MISMATCH"

    service2, authority2, _ = _service(tmp_path / "receipt")
    scenario2, genesis2 = _register(service2, draft)
    design2, design_path2 = _approved_design(authority2, draft)
    approved = service2.bind_approval(scenario2, genesis2, design_path2)
    receipt = _receipt(design2).model_copy(update={"design_fingerprint": "9" * 64})
    receipt_path = _write_model(authority2 / "wrong-receipt.json", receipt)
    with pytest.raises(ScenarioLifecycleError) as mismatch:
        service2.import_execution_receipt(scenario2, approved.event_digest, receipt_path)
    assert mismatch.value.code == "EXECUTION_RECEIPT_MISMATCH"


def test_deviation_analysis_and_admission_mismatches_refuse(
    loaded: LoadedFit, tmp_path: Path
) -> None:
    service, authority, _ = _service(tmp_path)
    scenario_id, design, _, receipt_path, head = _approve_and_execute(
        service, authority, _draft(loaded)
    )
    bad_deviation = ScenarioExecutionDeviation(
        scenario_id=scenario_id,
        approved_design_fingerprint=design.fingerprint(),
        source_receipt_digest="8" * 64,
        deviation_code="WRONG_SOURCE",
        summary="Synthetic mismatch.",
        intended_digest="1" * 64,
        observed_digest="2" * 64,
        recorded_at_utc=LATER,
        scientific_settings_changed=False,
        metric_based_selection_occurred=False,
    )
    with pytest.raises(ScenarioLifecycleError) as deviation:
        service.import_deviation(
            scenario_id,
            head,
            _write_model(authority / "bad-deviation.json", bad_deviation),
        )
    assert deviation.value.code == "DEVIATION_RECEIPT_MISMATCH"

    bad_analysis = _analysis(design).model_copy(update={"design_fingerprint": "7" * 64})
    with pytest.raises(ScenarioLifecycleError) as analysis:
        service.import_analysis(
            scenario_id,
            head,
            _write_model(authority / "bad-analysis.json", bad_analysis),
        )
    assert analysis.value.code == "ANALYSIS_RECEIPT_MISMATCH"

    bad_admission = ScenarioAdmissionRecord(
        scenario_id=scenario_id,
        approved_design_fingerprint=design.fingerprint(),
        source_receipt_digest="6" * 64,
        status="admitted",
        decision_origin="explicit_human_owner_direction",
        decided_by="A. Owner",
        decided_role="repository owner",
        decided_at_utc=LATER,
        limitations=("Synthetic mismatch fixture.",),
    )
    with pytest.raises(ScenarioLifecycleError) as admission:
        service.import_admission(
            scenario_id,
            head,
            _write_model(authority / "bad-admission.json", bad_admission),
        )
    assert admission.value.code == "ADMISSION_RECEIPT_MISMATCH"
    assert _sha(receipt_path) != "6" * 64


def test_agent_admission_private_artifacts_and_symlinks_refuse(
    loaded: LoadedFit, tmp_path: Path
) -> None:
    with pytest.raises(ValidationError):
        ScenarioAdmissionRecord(
            scenario_id="1" * 16,
            approved_design_fingerprint="2" * 64,
            source_receipt_digest="3" * 64,
            status="admitted",
            decision_origin="explicit_human_owner_direction",
            decided_by="Codex agent",
            decided_role="auto approver",
            decided_at_utc=NOW,
            limitations=("invalid",),
        )

    service, authority, _ = _service(tmp_path)
    scenario_id, genesis = _register(service, _draft(loaded))
    private = authority / "private.json"
    private.write_text('{"note":"read /Users/private/archive"}', encoding="utf-8")
    with pytest.raises(ScenarioLifecycleError) as private_error:
        service.bind_approval(scenario_id, genesis, private)
    assert private_error.value.code == "PRIVATE_CONTENT_DETECTED"

    target = authority / "target.json"
    target.write_text("{}", encoding="utf-8")
    link = authority / "linked.json"
    link.symlink_to(target)
    with pytest.raises(ScenarioLifecycleError) as unsafe:
        service.bind_approval(scenario_id, genesis, link)
    assert unsafe.value.code == "ARTIFACT_UNSAFE"


def test_mutated_authority_artifact_breaks_replay_closed(loaded: LoadedFit, tmp_path: Path) -> None:
    service, authority, config = _service(tmp_path)
    _, _, _, receipt_path, _ = _approve_and_execute(service, authority, _draft(loaded))
    receipt_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ScenarioRegistryError) as replay:
        ScenarioLifecycleService(config)
    assert replay.value.code == "EXTERNAL_PROOF_INVALID"


def test_no_execution_or_artifact_writer_surface_exists() -> None:
    source = (ROOT / "src" / "traffictwin" / "platform" / "scenario_lifecycle.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "def run(",
        "def launch(",
        "def execute(",
        "subprocess",
        "urlopen",
        "write_admission",
        "create_approval",
    ):
        assert forbidden not in source

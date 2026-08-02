"""Benchmark execution packaging and synthetic-worker boundary tests."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest
from pydantic import ValidationError

from traffictwin.platform.benchmark_execution import (
    MAX_SYNTHETIC_ATTEMPTS,
    ActorPluginManifest,
    BenchmarkExecutionError,
    BenchmarkJobReceipt,
    CheckpointIdentity,
    ManifestBundle,
    PlannedJobPack,
    PlannedJobReturn,
    ReceiptLedger,
    RewardComponents,
    SyntheticDryRunPack,
    adapt_action,
    adapt_observation,
    adapt_reward,
    build_manifest_bundle,
    build_planned_job_pack,
    build_resource_plan,
    build_resume_plan,
    build_synthetic_dry_run_pack,
    export_planned_job_pack,
    freeze_synthetic_analysis_inputs,
    ingest_receipt,
    inventory_checkpoints,
    render_planned_job_pack,
    render_resource_plan,
    run_synthetic_job,
    run_synthetic_pack,
    validate_planned_checkpoint_inventory,
    validate_planned_job_return,
    validate_synthetic_dispatch,
)
from traffictwin.platform.benchmark_protocol import (
    ACTION_TRACKS,
    CAPACITY_REPRESENTATIONS,
    EVALUATION_ONLY_ALGORITHMS,
    REQUIRED_ENDPOINT_SET,
    REWARD_TRACKS,
    TRAINING_ALGORITHMS,
    BenchmarkProtocol,
    BenchmarkProtocolError,
    CapacityRepresentationKind,
    SignedPredeclaration,
    build_owner_selected_protocol,
    freeze_predeclaration,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "benchmark_execution.py"


def _cli_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("benchmark_execution_cli_under_test", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cli_main = cast(Callable[[Sequence[str] | None], int], _cli_module().main)


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _package() -> tuple[BenchmarkProtocol, ManifestBundle, PlannedJobPack, SyntheticDryRunPack]:
    protocol = build_owner_selected_protocol()
    manifests = build_manifest_bundle(protocol)
    planned = build_planned_job_pack(protocol, manifests)
    dry = build_synthetic_dry_run_pack(protocol, manifests)
    return protocol, manifests, planned, dry


def _signature() -> SignedPredeclaration:
    protocol = build_owner_selected_protocol()
    artifact = freeze_predeclaration(protocol)
    return SignedPredeclaration(
        protocol_digest=protocol.digest(),
        final_markdown_sha256=artifact.markdown_sha256,
        signer_role="human_owner",
        signature_digest=hashlib.sha256(b"synthetic signature fixture").hexdigest(),
        signed_at_utc=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
        scope_and_budget_unchanged=True,
        policy_validated=True,
    )


def _failed_receipt(
    completed: BenchmarkJobReceipt, *, attempt: int, status: str = "failed"
) -> BenchmarkJobReceipt:
    payload = completed.model_dump(mode="python")
    payload.update(
        {
            "attempt": attempt,
            "status": status,
            "adapter_trace_digest": None,
            "result_digest": None,
            "metrics": None,
            "checkpoints": (),
            "deviations": ("synthetic injected failure retained",),
        }
    )
    return BenchmarkJobReceipt.model_validate(payload)


def test_all_declared_families_have_digest_pinned_contract_only_manifests() -> None:
    protocol = build_owner_selected_protocol()
    bundle = build_manifest_bundle(protocol)
    assert tuple(item.family for item in bundle.actors) == (
        TRAINING_ALGORITHMS + EVALUATION_ONLY_ALGORITHMS
    )
    assert len({item.digest() for item in bundle.actors}) == 7
    assert all(item.binding_state == "contract_only" for item in bundle.actors)
    assert all(item.real_implementation_bound is False for item in bundle.actors)
    assert all(item.scientific_execution_allowed is False for item in bundle.actors)
    assert bundle.runtime.training_allowed is False
    assert bundle.runtime.network_allowed is False
    assert bundle.adapter_suite.scientific_validation is False


def test_manifest_bundle_refuses_missing_family_and_private_contract_text() -> None:
    protocol = build_owner_selected_protocol()
    bundle = build_manifest_bundle(protocol)
    with pytest.raises(ValidationError, match="MANIFEST_FAMILY_MISMATCH"):
        type(bundle).model_validate(
            {**bundle.model_dump(mode="python"), "actors": bundle.actors[:-1]}
        )
    private = bundle.actors[0].model_dump(mode="python")
    private["checkpoint_selection_rule"] = "/Users/private/checkpoint"
    actors = (ActorPluginManifest.model_validate(private),) + bundle.actors[1:]
    with pytest.raises(ValidationError, match="PRIVATE_CONTENT_DETECTED"):
        type(bundle).model_validate({**bundle.model_dump(mode="python"), "actors": actors})


def test_observation_adapters_cover_all_six_frozen_capacity_representations() -> None:
    protocol = build_owner_selected_protocol()
    kwargs: dict[CapacityRepresentationKind, dict[str, tuple[float, ...]]] = {
        "capacity_blind": {},
        "global_scalar": {"provisioned_values": (1.25,)},
        "per_rsu_vector": {"provisioned_values": (1.25,) * 10},
        "local_observable": {"provisioned_values": (1.25,)},
        "provisioned_remaining": {
            "provisioned_values": (1.25,) * 10,
            "remaining_values": (0.75,) * 10,
        },
        "local_utilisation_queue": {
            "utilisation_values": (0.5,),
            "queue_values": (1.0,),
        },
    }
    outputs = tuple(
        adapt_observation(protocol, item, base_values=(1.0, 2.0), **kwargs[item.kind])
        for item in protocol.capacity_representations
    )
    assert tuple(item.capacity_dimensions for item in outputs) == (0, 1, 10, 1, 20, 2)
    assert outputs[0].visible_before_action is False
    assert all(item.synthetic_contract_check and not item.evidence for item in outputs)


def test_observation_action_and_reward_adversarial_inputs_refuse() -> None:
    protocol = build_owner_selected_protocol()
    representation = protocol.capacity_representations[1]
    changed = representation.model_copy(update={"training_max_value": 3.0})
    with pytest.raises(BenchmarkExecutionError) as observation:
        adapt_observation(protocol, changed, base_values=(1.0,), provisioned_values=(1.0,))
    assert observation.value.code == "OBSERVATION_CONTRACT_MISMATCH"
    with pytest.raises(BenchmarkExecutionError, match="ACTION_INFEASIBLE"):
        adapt_action(
            "local_v2i_v2v_feasibility_masked",
            action_index=1,
            feasible_actions=(True, False, True),
        )
    with pytest.raises(BenchmarkExecutionError, match="ACTION_OUT_OF_RANGE"):
        adapt_action("local_v2i_v2v_unmasked", action_index=4, feasible_actions=(True, True, True))


def test_action_and_reward_adapters_cover_every_declared_track() -> None:
    actions = tuple(
        adapt_action(track, action_index=2, feasible_actions=(True, True, True))
        for track in ACTION_TRACKS
    )
    components = RewardComponents(
        deadline_completion=0.75,
        latency_penalty=0.2,
        energy_penalty=0.1,
        failure_penalty=0.25,
        fairness_penalty=0.1,
    )
    rewards = tuple(adapt_reward(track, components) for track in REWARD_TRACKS)
    assert {item.action for item in actions} == {"v2v"}
    assert actions[1].feasibility_checked is True
    assert tuple(item.reward_track for item in rewards) == REWARD_TRACKS
    assert all(item.literature_validated is False and item.evidence is False for item in rewards)


def test_planned_pack_is_exactly_240_cells_2400_matched_jobs_and_deterministic() -> None:
    protocol, manifests, pack, _ = _package()
    repeated = build_planned_job_pack(protocol, manifests)
    assert pack.digest() == repeated.digest()
    assert len(pack.jobs) == 2400
    assert len({item.cell_id for item in pack.jobs}) == 240
    assert {item.training_seed for item in pack.jobs} == set(protocol.seeds.training)
    assert {item.matched_interactions for item in pack.jobs} == {5_000_000}
    assert all(not item.dispatch_authorised and not item.evidence for item in pack.jobs)
    assert all(item.scope_status == "proposed_unsigned" for item in pack.jobs)


def test_planned_pack_refuses_changed_seed_budget_and_job_identity() -> None:
    _, _, pack, _ = _package()
    original = pack.jobs[0]
    for update, reason in (
        ({"training_seed": 2200}, "SEED_NAMESPACE_CONTAMINATED"),
        ({"matched_interactions": 4_999_999}, "MATCHED_BUDGET_MISMATCH"),
        ({"actor_manifest_digest": "0" * 64}, "ACTOR_MANIFEST_MISMATCH"),
    ):
        payload = original.model_dump(mode="python")
        payload.update(update)
        del payload["job_id"]
        changed = type(original).model_validate({"job_id": _digest(payload), **payload})
        jobs = (changed,) + pack.jobs[1:]
        with pytest.raises(ValidationError, match=reason):
            PlannedJobPack.model_validate({**pack.model_dump(mode="python"), "jobs": jobs})


def test_ndjson_render_binds_header_and_all_jobs() -> None:
    _, _, pack, _ = _package()
    content = render_planned_job_pack(pack)
    lines = content.decode("utf-8").splitlines()
    header = json.loads(lines[0])
    assert len(lines) == 2401
    assert header["pack_digest"] == pack.digest()
    assert header["dispatch_authorised"] is False
    assert json.loads(lines[1])["job_id"] == pack.jobs[0].job_id
    assert content == render_planned_job_pack(pack)


def test_local_export_is_atomic_path_free_and_never_overwrites(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    _, _, pack, _ = _package()
    receipt = export_planned_job_pack(pack, tmp_path, "planned.ndjson")
    target = tmp_path / "planned.ndjson"
    assert target.read_bytes() == render_planned_job_pack(pack)
    assert target.stat().st_mode & 0o777 == 0o600
    assert tuple(tmp_path.iterdir()) == (target,)
    assert receipt.path_included is False
    assert str(tmp_path) not in receipt.model_dump_json()
    with pytest.raises(BenchmarkExecutionError, match="EXPORT_EXISTS"):
        export_planned_job_pack(pack, tmp_path, "planned.ndjson")
    with pytest.raises(BenchmarkExecutionError, match="EXPORT_PATH_UNSAFE"):
        export_planned_job_pack(pack, tmp_path, "../escape.ndjson")


def test_export_refuses_group_writable_or_symlink_root(tmp_path: Path) -> None:
    _, _, pack, _ = _package()
    unsafe = tmp_path / "unsafe"
    unsafe.mkdir(mode=0o770)
    unsafe.chmod(0o770)
    with pytest.raises(BenchmarkExecutionError, match="EXPORT_PERMISSIONS_UNSAFE"):
        export_planned_job_pack(pack, unsafe, "planned.ndjson")
    target = tmp_path / "target"
    target.mkdir(mode=0o700)
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(BenchmarkExecutionError, match="EXPORT_ROOT_UNSAFE"):
        export_planned_job_pack(pack, link, "planned.ndjson")


def test_synthetic_pack_uses_all_families_only_three_engineering_seeds_and_tiny_budget() -> None:
    protocol, _, _, dry = _package()
    assert len(dry.jobs) == 21
    assert {item.algorithm for item in dry.jobs} == set(
        TRAINING_ALGORITHMS + EVALUATION_ONLY_ALGORITHMS
    )
    assert {item.engineering_seed for item in dry.jobs} == set(protocol.seeds.engineering)
    forbidden = set(protocol.seeds.training + protocol.seeds.tuning + protocol.seeds.evaluation)
    assert not {item.engineering_seed for item in dry.jobs}.intersection(forbidden)
    assert {item.step_budget for item in dry.jobs} == {4}
    assert {item.capacity_representation for item in dry.jobs} == set(CAPACITY_REPRESENTATIONS)
    assert all(not item.scientific_campaign and not item.evidence for item in dry.jobs)


def test_synthetic_worker_is_deterministic_endpoint_complete_and_not_evidence() -> None:
    protocol, manifests, _, dry = _package()
    first = run_synthetic_job(protocol, manifests, dry, dry.jobs[0])
    repeated = run_synthetic_job(protocol, manifests, dry, dry.jobs[0])
    assert first == repeated
    assert first.status == "completed"
    assert first.metrics is not None
    assert first.metrics.completion_count + first.metrics.failure_count == 4
    assert first.checkpoints[0].milestone == "synthetic_terminal"
    assert first.scientific_campaign is False
    assert first.evidence is False
    assert first.admission_created is False
    receipts = run_synthetic_pack(protocol, manifests, dry)
    assert len(receipts) == 21
    assert len({item.result_digest for item in receipts}) == 21


def test_dispatch_rechecks_job_manifest_seed_budget_and_attempt() -> None:
    protocol, manifests, _, dry = _package()
    job = dry.jobs[0]
    validate_synthetic_dispatch(protocol, manifests, dry, job, attempt=1)
    with pytest.raises(BenchmarkExecutionError, match="ATTEMPT_BUDGET_EXCEEDED"):
        validate_synthetic_dispatch(
            protocol, manifests, dry, job, attempt=MAX_SYNTHETIC_ATTEMPTS + 1
        )
    changed_seed = job.model_copy(update={"engineering_seed": protocol.seeds.training[0]})
    with pytest.raises(BenchmarkExecutionError, match="JOB_DIGEST_MISMATCH"):
        validate_synthetic_dispatch(protocol, manifests, dry, changed_seed, attempt=1)
    changed_budget = job.model_copy(update={"step_budget": 5})
    with pytest.raises(BenchmarkExecutionError, match="JOB_DIGEST_MISMATCH"):
        validate_synthetic_dispatch(protocol, manifests, dry, changed_budget, attempt=1)


def test_receipt_ingestion_is_idempotent_and_rejects_mutation() -> None:
    protocol, manifests, _, dry = _package()
    receipt = run_synthetic_job(protocol, manifests, dry, dry.jobs[0])
    ledger = ReceiptLedger()
    accepted = ingest_receipt(protocol, manifests, dry, receipt, ledger)
    retried = ingest_receipt(protocol, manifests, dry, receipt, ledger)
    assert accepted.idempotent_retry is False
    assert retried.idempotent_retry is True
    assert len(ledger.receipts) == 1
    assert receipt.metrics is not None
    changed_metrics = receipt.metrics.model_copy(update={"mean_latency_ms": 999.0})
    changed = receipt.model_copy(update={"metrics": changed_metrics})
    with pytest.raises(BenchmarkExecutionError, match="RESULT_DIGEST_MISMATCH"):
        ingest_receipt(protocol, manifests, dry, changed, ReceiptLedger())
    changed_checkpoint = receipt.model_copy(
        update={
            "checkpoints": (
                receipt.checkpoints[0].model_copy(update={"checkpoint_digest": "0" * 64}),
            )
        }
    )
    with pytest.raises(BenchmarkExecutionError, match="CHECKPOINT_DIGEST_MISMATCH"):
        ingest_receipt(protocol, manifests, dry, changed_checkpoint, ReceiptLedger())


def test_failed_receipts_retry_in_sequence_and_completed_jobs_do_not_retry() -> None:
    protocol, manifests, _, dry = _package()
    completed = run_synthetic_job(protocol, manifests, dry, dry.jobs[0])
    ledger = ReceiptLedger()
    failed = _failed_receipt(completed, attempt=1)
    ingest_receipt(protocol, manifests, dry, failed, ledger)
    retry = run_synthetic_job(protocol, manifests, dry, dry.jobs[0], attempt=2)
    ingest_receipt(protocol, manifests, dry, retry, ledger)
    with pytest.raises(BenchmarkExecutionError, match="ATTEMPT_SEQUENCE_INVALID"):
        ingest_receipt(
            protocol,
            manifests,
            dry,
            run_synthetic_job(protocol, manifests, dry, dry.jobs[0], attempt=3),
            ledger,
        )
    assert build_resume_plan(dry, ledger).completed_job_ids == (dry.jobs[0].job_id,)


def test_resume_plan_separates_pending_retryable_completed_and_exhausted() -> None:
    protocol, manifests, _, dry = _package()
    ledger = ReceiptLedger()
    first_complete = run_synthetic_job(protocol, manifests, dry, dry.jobs[0])
    ingest_receipt(protocol, manifests, dry, first_complete, ledger)
    second_complete = run_synthetic_job(protocol, manifests, dry, dry.jobs[1])
    ingest_receipt(protocol, manifests, dry, _failed_receipt(second_complete, attempt=1), ledger)
    third_complete = run_synthetic_job(protocol, manifests, dry, dry.jobs[2])
    for attempt in range(1, 4):
        ingest_receipt(
            protocol,
            manifests,
            dry,
            _failed_receipt(third_complete, attempt=attempt),
            ledger,
        )
    resume = build_resume_plan(dry, ledger)
    assert resume.completed_job_ids == (dry.jobs[0].job_id,)
    assert resume.retryable_job_ids == (dry.jobs[1].job_id,)
    assert resume.exhausted_job_ids == (dry.jobs[2].job_id,)
    assert len(resume.pending_job_ids) == 18
    assert resume.dispatch_started is False


def test_checkpoint_inventory_and_analysis_freeze_require_all_compatible_returns() -> None:
    protocol, manifests, _, dry = _package()
    ledger = ReceiptLedger()
    with pytest.raises(BenchmarkExecutionError, match="ANALYSIS_INPUT_INCOMPLETE"):
        freeze_synthetic_analysis_inputs(protocol, manifests, dry, ledger)
    receipts = run_synthetic_pack(protocol, manifests, dry)
    ingest_receipt(protocol, manifests, dry, _failed_receipt(receipts[0], attempt=1), ledger)
    ingest_receipt(
        protocol,
        manifests,
        dry,
        run_synthetic_job(protocol, manifests, dry, dry.jobs[0], attempt=2),
        ledger,
    )
    for receipt in receipts[1:]:
        ingest_receipt(protocol, manifests, dry, receipt, ledger)
    inventory = inventory_checkpoints(dry, ledger)
    frozen = freeze_synthetic_analysis_inputs(protocol, manifests, dry, ledger)
    assert inventory.completed_jobs == 21
    assert inventory.synthetic_terminal_checkpoints == 21
    assert inventory.scientific_checkpoint_inventory_complete is False
    assert frozen.complete_jobs == 21
    assert len(frozen.receipt_digests) == 22
    assert len(frozen.result_digests) == 21
    assert frozen.synthetic_dry_run is True
    assert frozen.confirmatory is False
    assert frozen.evidence is False
    assert frozen.admission_created is False
    assert "deterministic synthetic fixture; no actor or training" in frozen.deviations
    assert "synthetic injected failure retained" in frozen.deviations


def test_planned_checkpoint_inventory_requires_frozen_terminal_rule() -> None:
    _, _, pack, _ = _package()
    checkpoints = tuple(
        CheckpointIdentity(milestone=milestone, checkpoint_digest=_digest({"m": milestone}))
        for milestone in ("25", "50", "75", "100")
    )
    inventory = validate_planned_checkpoint_inventory(pack.jobs[0], checkpoints)
    assert inventory.terminal_checkpoint_digest == checkpoints[-1].checkpoint_digest
    assert inventory.contract_inventory_complete is True
    assert inventory.implementation_verified is False
    with pytest.raises(BenchmarkExecutionError, match="CHECKPOINT_INVENTORY_MISMATCH"):
        validate_planned_checkpoint_inventory(pack.jobs[0], checkpoints[:-1])


def test_planned_return_requires_exact_signed_scope_budget_seed_endpoints_and_digest() -> None:
    protocol, _, pack, _ = _package()
    job = pack.jobs[0]
    artifact = freeze_predeclaration(protocol)
    signature = _signature()
    checkpoints = tuple(
        CheckpointIdentity(milestone=milestone, checkpoint_digest=_digest({"m": milestone}))
        for milestone in ("25", "50", "75", "100")
    )
    payload: dict[str, object] = {
        "job_id": job.job_id,
        "planned_job_pack_digest": pack.digest(),
        "protocol_digest": protocol.digest(),
        "signed_predeclaration_digest": artifact.markdown_sha256,
        "signature_digest": signature.signature_digest,
        "actor_manifest_digest": job.actor_manifest_digest,
        "runtime_manifest_digest": job.runtime_manifest_digest,
        "adapter_suite_digest": job.adapter_suite_digest,
        "training_seed": job.training_seed,
        "interactions_consumed": job.matched_interactions,
        "endpoint_names": REQUIRED_ENDPOINT_SET,
        "checkpoints": checkpoints,
        "deviations": (),
        "status": "completed",
        "receipt_is_evidence": False,
        "admission_created": False,
    }
    unsealed = PlannedJobReturn.model_validate({**payload, "result_digest": "0" * 64})
    returned = unsealed.model_copy(
        update={"result_digest": _digest(unsealed.result_identity_payload())}
    )
    compatible = validate_planned_job_return(protocol, pack, job, artifact, signature, returned)
    assert compatible.compatible is True
    assert compatible.receipt_is_evidence is False
    changed = returned.model_copy(update={"training_seed": protocol.seeds.tuning[0]})
    with pytest.raises(BenchmarkExecutionError, match="RETURN_CONTRACT_MISMATCH"):
        validate_planned_job_return(protocol, pack, job, artifact, signature, changed)
    unsigned = signature.model_copy(update={"final_markdown_sha256": "0" * 64})
    with pytest.raises(BenchmarkProtocolError, match="PREDECLARATION_DIGEST_MISMATCH"):
        validate_planned_job_return(protocol, pack, job, artifact, unsigned, returned)


def test_provider_neutral_resource_plan_is_estimate_only_and_non_submitting() -> None:
    protocol, _, pack, _ = _package()
    plan = build_resource_plan(protocol, pack)
    assert plan.planned_training_jobs == 2400
    assert plan.total_training_interactions == 12_000_000_000
    assert plan.provider_labels == ("gcp_batch", "aws_batch")
    assert plan.estimate_only is True
    assert plan.authority is False
    assert plan.allocation_created is False
    assert plan.submission_created is False
    payload = json.loads(render_resource_plan(plan))
    assert payload["maximum_cost_gbp_estimate"] == 5000.0


def test_cli_exports_each_local_artifact_without_path_or_authority(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    tmp_path.chmod(0o700)
    for command, filename in (
        ("export-job-pack", "jobs.ndjson"),
        ("export-resource-plan", "resources.json"),
        ("synthetic-dry-run", "receipts.ndjson"),
    ):
        assert cli_main([command, "--output-root", str(tmp_path), "--filename", filename]) == 0
        output = capsys.readouterr().out
        assert str(tmp_path) not in output
        assert json.loads(output)["dispatch_created"] is False
        assert (tmp_path / filename).is_file()


def test_source_has_no_actor_loader_training_cloud_or_network_execution_surface() -> None:
    source = (REPO_ROOT / "src/traffictwin/platform/benchmark_execution.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "import requests",
        "import httpx",
        "import boto3",
        "google.cloud",
        "subprocess.Popen",
        "shell=True",
        "torch.optim",
        "optimizer.step",
        "importlib.import_module",
        "exec(",
    ):
        assert forbidden not in source

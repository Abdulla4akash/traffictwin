"""Unit coverage for the CSF job-pack export/import contract.

Every payload here is synthetic and every function under test is pure. Nothing
opens a connection, submits a job, reads a registry, or touches an external
repository — there is no executor to exercise, which is the point of the module.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from traffictwin.integration.vec_campaign.job_pack import (
    DEFAULT_REQUIRED_OUTPUT_NAMES,
    JobPackError,
    VecJobPack,
    VecJobPackImportStatus,
    VecJobPackInputRef,
    VecJobPackInputRole,
    build_job_pack,
    verify_job_pack_import,
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
    PINNED_TOS_DATA_COMMIT,
    PINNED_VEC_ENV_COMMIT,
    VecExecutionReceipt,
    VecFleet,
    VecRunnerFileEvidence,
    VecRuntimeEvidence,
    VecTerminalStatus,
    output_fingerprint,
)

INC_TRACE_SHA = "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"
INC_TRACE_FILE = "traces/trace_inc_fullrsu.npz"
ACTOR_ID = "ukfleettrain_mappo_model_c_17"
CREATED_AT = "2026-07-27T18:00:00+00:00"


def _design(*, seeds: list[int] | None = None) -> VecCampaignDesign:
    return VecCampaignDesign(
        experiment_id="vec-csf-unit",
        research_question="Does reduced per-vehicle RSU task capacity degrade deadline success?",
        run_id_prefix="csfunit",
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


def _manifest(
    *,
    trace_sha: str = INC_TRACE_SHA,
    trace_path: str = INC_TRACE_FILE,
    include_sources: bool = True,
    actor_sha: str | None = None,
) -> list[VecJobPackInputRef]:
    actor_path, pinned_actor_sha = PINNED_ACTORS[ACTOR_ID]
    refs = [
        VecJobPackInputRef(
            repository="tos-data",
            audited_commit=PINNED_TOS_DATA_COMMIT,
            path=trace_path,
            sha256=trace_sha,
            size_bytes=4_096,
            role=VecJobPackInputRole.TRACE,
        ),
        VecJobPackInputRef(
            repository="vec_env",
            audited_commit=PINNED_VEC_ENV_COMMIT,
            path=actor_path,
            sha256=actor_sha or pinned_actor_sha,
            size_bytes=2_048,
            role=VecJobPackInputRole.ACTOR,
        ),
    ]
    if include_sources:
        refs.extend(
            VecJobPackInputRef(
                repository="vec_env",
                audited_commit=PINNED_VEC_ENV_COMMIT,
                path=path,
                sha256=sha,
                size_bytes=1_024,
                role=VecJobPackInputRole.EVALUATOR_SOURCE,
            )
            for path, sha in sorted(PINNED_EVALUATOR_FILES.items())
        )
    return refs


def _pack(
    *,
    design: VecCampaignDesign | None = None,
    pack_id: str = "csf-unit-pack",
    created_at_utc: str = CREATED_AT,
    inputs: list[VecJobPackInputRef] | None = None,
) -> VecJobPack:
    return build_job_pack(
        design=design if design is not None else _design(),
        pack_id=pack_id,
        created_at_utc=created_at_utc,
        inputs=inputs if inputs is not None else _manifest(),
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
    output_names: tuple[str, ...] = DEFAULT_REQUIRED_OUTPUT_NAMES,
) -> VecExecutionReceipt:
    """Return the receipt a remote site would return for one declared cell."""

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
            for index, name in enumerate(output_names)
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


def _full_return(design: VecCampaignDesign) -> list[VecExecutionReceipt]:
    return [
        _receipt(design, arm.label, seed) for arm in design.arms() for seed in design.fleet_seeds
    ]


# --- export -----------------------------------------------------------------


def test_pack_declares_every_arm_seed_cell_with_its_local_request_fingerprint() -> None:
    design = _design()
    pack = _pack(design=design)

    assert len(pack.cells) == len(design.arms()) * len(design.fleet_seeds)
    assert [cell.run_id for cell in pack.cells] == [
        design.cell_run_id(arm.label, seed) for arm in design.arms() for seed in design.fleet_seeds
    ]
    for cell in pack.cells:
        arm = next(item for item in design.arms() if item.label == cell.arm_label)
        expected = design.cell_request(arm, cell.fleet_seed)
        assert cell.request_fingerprint == expected.fingerprint()
        assert cell.rsu_capacity_per_vehicle == arm.rsu_capacity_per_vehicle


def test_pack_is_byte_reproducible_because_no_clock_is_read() -> None:
    first = _pack()
    second = _pack()

    assert first.canonical_json() == second.canonical_json()
    assert first.fingerprint() == second.fingerprint()


def test_pack_carries_identities_and_never_repository_bytes() -> None:
    pack = _pack()

    assert pack.external_repository_bytes_included is False
    assert pack.executor_included is False
    assert pack.credentials_included is False
    assert pack.audited_commits() == {
        "tos-data": PINNED_TOS_DATA_COMMIT,
        "vec_env": PINNED_VEC_ENV_COMMIT,
    }
    payload = json.loads(pack.canonical_json())
    for ref in payload["inputs"]:
        assert set(ref) == {
            "repository",
            "audited_commit",
            "path",
            "sha256",
            "size_bytes",
            "role",
        }


def test_pack_records_the_no_admission_limitation() -> None:
    pack = _pack()

    joined = " ".join(pack.limitations).lower()
    assert "not a scientific admission" in joined
    assert "adr-061" in joined
    assert "not an executor" in joined


def test_pack_refuses_a_manifest_missing_the_pinned_evaluator_sources() -> None:
    with pytest.raises(JobPackError, match="pinned evaluator source"):
        _pack(inputs=_manifest(include_sources=False))


def test_pack_refuses_a_trace_that_is_not_the_designs_reviewed_identity() -> None:
    with pytest.raises(JobPackError, match="reviewed trace identity"):
        _pack(inputs=_manifest(trace_sha="f" * 64))


def test_pack_refuses_an_actor_that_is_not_the_pinned_checkpoint() -> None:
    with pytest.raises(JobPackError, match="pinned checkpoint"):
        _pack(inputs=_manifest(actor_sha="b" * 64))


def test_manifest_refuses_a_commit_that_is_not_the_audited_one() -> None:
    with pytest.raises(ValidationError, match="audited commit"):
        VecJobPackInputRef(
            repository="tos-data",
            audited_commit="0" * 40,
            path=INC_TRACE_FILE,
            sha256=INC_TRACE_SHA,
            size_bytes=1,
            role=VecJobPackInputRole.TRACE,
        )


def test_manifest_refuses_an_escaping_path() -> None:
    with pytest.raises(ValidationError, match="safe relative paths"):
        VecJobPackInputRef(
            repository="tos-data",
            audited_commit=PINNED_TOS_DATA_COMMIT,
            path="../traces/trace_inc_fullrsu.npz",
            sha256=INC_TRACE_SHA,
            size_bytes=1,
            role=VecJobPackInputRole.TRACE,
        )


def test_pack_refuses_a_design_fingerprint_that_does_not_match_the_design() -> None:
    pack = _pack()
    payload = json.loads(pack.canonical_json())
    payload["design_fingerprint"] = "a" * 64

    with pytest.raises(ValidationError, match="design_fingerprint does not match"):
        VecJobPack.model_validate_json(json.dumps(payload))


def test_pack_refuses_a_cell_list_that_is_not_the_declared_grid() -> None:
    pack = _pack()
    payload = json.loads(pack.canonical_json())
    payload["cells"] = payload["cells"][:-1]

    with pytest.raises(ValidationError, match="arms crossed with its fleet seeds"):
        VecJobPack.model_validate_json(json.dumps(payload))


def test_build_refuses_an_empty_manifest() -> None:
    with pytest.raises(JobPackError, match="at least one input"):
        build_job_pack(
            design=_design(), pack_id="csf-unit-pack", created_at_utc=CREATED_AT, inputs=[]
        )


# --- import -----------------------------------------------------------------


def test_a_complete_intact_return_verifies() -> None:
    design = _design()
    pack = _pack(design=design)

    result = verify_job_pack_import(pack, _full_return(design))

    assert result.status is VecJobPackImportStatus.VERIFIED
    assert result.findings == []
    assert result.fulfilled_cell_count == result.declared_cell_count == 6
    assert result.unfulfilled_run_ids == []
    assert all(cell.output_file_count == 3 for cell in result.cells)


def test_a_verified_import_is_still_not_an_admission() -> None:
    design = _design()
    result = verify_job_pack_import(_pack(design=design), _full_return(design))

    assert result.status is VecJobPackImportStatus.VERIFIED
    assert result.admission_granted is False
    assert result.scientific_admission is False
    assert result.registry_write_performed is False
    assert "not a scientific admission" in " ".join(result.limitations).lower()


def test_receipts_may_be_supplied_as_plain_dicts() -> None:
    design = _design()
    pack = _pack(design=design)
    payloads = [json.loads(item.model_dump_json()) for item in _full_return(design)]

    result = verify_job_pack_import(pack, payloads)

    assert result.status is VecJobPackImportStatus.VERIFIED


def test_a_missing_cell_is_partial_and_named_rather_than_ignored() -> None:
    design = _design()
    pack = _pack(design=design)
    returned = _full_return(design)[:-1]

    result = verify_job_pack_import(pack, returned)

    assert result.status is VecJobPackImportStatus.PARTIAL
    assert result.fulfilled_cell_count == 5
    assert result.unfulfilled_run_ids == [design.cell_run_id("cap-1.0", 2)]
    assert result.findings == []


def test_a_receipt_outside_the_declared_cells_refuses_the_import() -> None:
    design = _design()
    pack = _pack(design=design)
    other = _design(seeds=[7, 8, 9])
    returned = [*_full_return(design), _receipt(other, "cap-2.5", 7)]

    result = verify_job_pack_import(pack, returned)

    assert result.status is VecJobPackImportStatus.REFUSED
    assert any("not a declared cell of this pack" in finding for finding in result.findings)


def test_a_duplicated_cell_refuses_the_import() -> None:
    design = _design()
    pack = _pack(design=design)
    returned = [*_full_return(design), _receipt(design, "cap-2.5", 0)]

    result = verify_job_pack_import(pack, returned)

    assert result.status is VecJobPackImportStatus.REFUSED
    assert any("returned more than once" in finding for finding in result.findings)


def test_a_mismatched_returned_design_fingerprint_refuses_the_import() -> None:
    design = _design()
    pack = _pack(design=design)

    result = verify_job_pack_import(
        pack, _full_return(design), returned_design_fingerprint="a" * 64
    )

    assert result.status is VecJobPackImportStatus.REFUSED
    assert any("does not match the pack" in finding for finding in result.findings)


def test_a_failed_remote_run_is_reported_not_counted() -> None:
    design = _design()
    pack = _pack(design=design)
    returned = _full_return(design)[:-1]
    returned.append(_receipt(design, "cap-1.0", 2, status=VecTerminalStatus.FAILED))

    result = verify_job_pack_import(pack, returned)

    assert result.status is VecJobPackImportStatus.PARTIAL
    assert result.returned_receipt_count == 6
    assert result.fulfilled_cell_count == 5
    failed = next(cell for cell in result.cells if cell.run_id.endswith("cap-1.0-fs2"))
    assert failed.fulfilled is False
    assert failed.receipt_status is VecTerminalStatus.FAILED
    assert "failed" in failed.detail


def test_a_missing_required_output_file_refuses_the_import() -> None:
    design = _design()
    pack = _pack(design=design)
    returned = _full_return(design)[:-1]
    returned.append(_receipt(design, "cap-1.0", 2, output_names=("run.json",)))

    result = verify_job_pack_import(pack, returned)

    assert result.status is VecJobPackImportStatus.REFUSED
    assert any("missing required output files" in finding for finding in result.findings)
    assert any("per-task.npz" in finding for finding in result.findings)


def test_output_hashes_are_recomputed_rather_than_trusted() -> None:
    design = _design()
    pack = _pack(design=design)
    returned = _full_return(design)
    # A receipt object handed around in-process can be edited after it validated;
    # the importer re-derives the fingerprint instead of believing the recorded one.
    returned[0].outputs.append(
        VecRunnerFileEvidence(
            path="smuggled.npz",
            sha256="9" * 64,
            size_bytes=10,
            media_type="application/octet-stream",
            read_only=True,
        )
    )

    result = verify_job_pack_import(pack, returned)

    assert result.status is VecJobPackImportStatus.REFUSED
    assert any("does not recompute" in finding for finding in result.findings)


def test_an_unreadable_receipt_is_a_finding_not_an_exception() -> None:
    design = _design()
    pack = _pack(design=design)
    payloads: list[Any] = [json.loads(item.model_dump_json()) for item in _full_return(design)]
    payloads[0]["outputs"][0]["sha256"] = "not-a-hash"

    result = verify_job_pack_import(pack, payloads)

    assert result.status is VecJobPackImportStatus.REFUSED
    assert any("not a readable execution receipt" in finding for finding in result.findings)
    assert result.unfulfilled_run_ids == [design.cell_run_id("cap-2.5", 0)]


def test_an_empty_return_fulfils_nothing() -> None:
    design = _design()
    pack = _pack(design=design)

    result = verify_job_pack_import(pack, [])

    assert result.status is VecJobPackImportStatus.PARTIAL
    assert result.returned_receipt_count == 0
    assert result.fulfilled_cell_count == 0
    assert len(result.unfulfilled_run_ids) == 6

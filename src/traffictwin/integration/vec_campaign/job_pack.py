"""The import-first contract for running an approved campaign on remote compute.

University compute (CSF3) is requested but not granted, and the day it arrives
the temptation will be to write an executor first and think about provenance
afterwards. This module is the opposite order: the *contract* exists now, the
executor does not exist at all, and nothing downstream may read a returned
result that this module has not verified against the pack that asked for it.

Two directions, both pure:

**Export.** :func:`build_job_pack` turns one already-approved
:class:`~traffictwin.integration.vec_campaign.models.VecCampaignDesign` into a
:class:`VecJobPack`: the design itself, its fingerprint, the exact cells the
remote site is asked to run (each with the request fingerprint the local runner
would have produced), and an input manifest that names every input by
repository, audited commit, path, and SHA-256. The manifest carries
*identities*, never bytes — a pack tells a remote site what to check out and
what it must hash to; the audited repositories themselves never travel, because
a copied checkout is a checkout nobody audited.

**Import.** :func:`verify_job_pack_import` takes the returned execution receipts
and answers one question: are these the runs this pack asked for, and are they
intact? Design fingerprint match, every receipt's request fingerprint drawn from
the pack's declared cells, no duplicate and no unexpected cell, per-file output
hashes present, and the recorded output fingerprint recomputing to the same
value. Cells the remote site did not return are named rather than ignored.

**A verified import is not an admission.** ``admission_granted``,
``scientific_admission``, and ``registry_write_performed`` are type-level
``False`` here and there is no code path that can set them. Scientific admission
remains the existing ADR-061 fresh-run path, run locally against the returned
artifacts by a person who decided to run it. This module establishes only that
the artifacts are the ones that were asked for — which is a precondition for
that decision, not the decision.

There is no SSH, no network call, no scheduler, no submission, no file transfer,
and no clock: ``created_at_utc`` is supplied by the caller so a pack is
byte-reproducible from its inputs.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from traffictwin.integration.vec_campaign.models import (
    VecCampaignArm,
    VecCampaignDesign,
    VecCampaignModel,
)
from traffictwin.integration.vec_runner.models import (
    PINNED_ACTORS,
    PINNED_EVALUATOR_FILES,
    PINNED_REVIEWED_TRACES,
    PINNED_TOS_DATA_COMMIT,
    PINNED_VEC_ENV_COMMIT,
    VecExecutionReceipt,
    VecTerminalStatus,
    output_fingerprint,
)

VEC_JOB_PACK_SCHEMA_VERSION: Literal["1.0"] = "1.0"
VEC_JOB_PACK_METHOD_VERSION: Literal["vec-csf-job-pack-1.0"] = "vec-csf-job-pack-1.0"

#: Commit each audited repository must be checked out at for a pack to be valid.
#: The runner's pins are the single source of truth; when a re-pin is approved
#: these constants move and every newly built pack follows them.
AUDITED_REPOSITORY_COMMITS: dict[str, str] = {
    "vec_env": PINNED_VEC_ENV_COMMIT,
    "tos-data": PINNED_TOS_DATA_COMMIT,
}

#: Payload files the local runner publishes for a completed run. A pack requires
#: them by default so a remote site returning a partial payload is caught here
#: rather than three steps downstream.
DEFAULT_REQUIRED_OUTPUT_NAMES: tuple[str, ...] = (
    "per-step.npz",
    "per-task.npz",
    "run.json",
)

STANDING_JOB_PACK_LIMITATIONS: tuple[str, ...] = (
    "A job pack is a contract, not an executor. This module submits nothing, "
    "transfers nothing, and opens no connection; a person moves the pack and a "
    "person moves the results back.",
    "The manifest carries input identities, never input bytes. Audited "
    "repositories are never copied into a pack; the remote site checks out the "
    "named commit and must reproduce the recorded SHA-256 for every file.",
    "A verified import is not a scientific admission. Admission remains the "
    "ADR-061 fresh-run path, run locally against the returned artifacts by a "
    "person; verification only establishes that the artifacts are the ones this "
    "pack asked for.",
    "Verification is a provenance and integrity check, not a scientific one. It "
    "cannot tell whether the remote environment reproduced local numerics; that "
    "is the separate VEC-08 reconciliation question.",
)


class JobPackError(ValueError):
    """Raised when a job pack cannot be built, or a returned payload cannot be read."""


class VecJobPackInputRole(StrEnum):
    """Why one declared input is in the manifest."""

    TRACE = "trace"
    ACTOR = "actor"
    EVALUATOR_SOURCE = "evaluator_source"


class VecJobPackImportStatus(StrEnum):
    """Terminal state of one import verification."""

    VERIFIED = "verified"
    PARTIAL = "partial"
    REFUSED = "refused"


class VecJobPackInputRef(VecCampaignModel):
    """One declared input, named by identity rather than carried as bytes."""

    repository: Literal["vec_env", "tos-data"]
    audited_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    path: str = Field(min_length=1, max_length=256)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    role: VecJobPackInputRole

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if "\\" in value:
            raise ValueError("manifest paths must be POSIX relative paths")
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or not path.parts
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ValueError("manifest paths must be safe relative paths")
        return path.as_posix()

    @model_validator(mode="after")
    def validate_audited_commit(self) -> VecJobPackInputRef:
        expected = AUDITED_REPOSITORY_COMMITS[self.repository]
        if self.audited_commit != expected:
            raise ValueError(
                f"{self.repository} inputs must declare the audited commit {expected}; "
                "re-pinning is an approval decision, not a pack argument"
            )
        return self


class VecJobPackCell(VecCampaignModel):
    """One cell the remote site is asked to run, with its local request identity."""

    arm_label: str
    fleet_seed: int = Field(ge=0)
    run_id: str = Field(min_length=1, max_length=200)
    rsu_capacity_per_vehicle: float = Field(gt=0.0, le=1_000.0)
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class VecJobPack(VecCampaignModel):
    """One approved campaign design exported for execution elsewhere."""

    schema_version: Literal["1.0"] = VEC_JOB_PACK_SCHEMA_VERSION
    method_version: Literal["vec-csf-job-pack-1.0"] = VEC_JOB_PACK_METHOD_VERSION
    pack_id: str = Field(min_length=1, max_length=96)
    created_at_utc: str = Field(min_length=1, max_length=64)
    design: VecCampaignDesign
    design_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    inputs: list[VecJobPackInputRef] = Field(min_length=1, max_length=64)
    cells: list[VecJobPackCell] = Field(min_length=1)
    required_output_names: list[str] = Field(min_length=1, max_length=32)
    limitations: list[str] = Field(min_length=1, max_length=16)
    external_repository_bytes_included: Literal[False] = False
    executor_included: Literal[False] = False
    credentials_included: Literal[False] = False

    @field_validator("pack_id")
    @classmethod
    def validate_pack_id(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", value):
            raise ValueError("pack_id must be 1-96 ASCII letters, numbers, '.', '_' or '-'")
        return value

    @model_validator(mode="after")
    def validate_pack(self) -> VecJobPack:
        if self.design_fingerprint != self.design.fingerprint():
            raise ValueError("design_fingerprint does not match the exported design")
        expected = _expected_cells(self.design)
        if [cell.model_dump(mode="json") for cell in self.cells] != [
            cell.model_dump(mode="json") for cell in expected
        ]:
            raise ValueError(
                "declared cells must be exactly the design's arms crossed with its fleet seeds"
            )
        _validate_manifest(self.design, self.inputs)
        if len(set(self.required_output_names)) != len(self.required_output_names):
            raise ValueError("required_output_names must not repeat a name")
        return self

    def audited_commits(self) -> dict[str, str]:
        """Return the commit each declared repository must be checked out at."""

        return {ref.repository: ref.audited_commit for ref in self.inputs}

    def declared_request_fingerprints(self) -> dict[str, VecJobPackCell]:
        """Return the declared cells keyed by their request fingerprint."""

        return {cell.request_fingerprint: cell for cell in self.cells}


class VecJobPackCellVerification(VecCampaignModel):
    """What the returned payload did or did not establish for one declared cell."""

    arm_label: str
    fleet_seed: int = Field(ge=0)
    run_id: str
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    fulfilled: bool
    receipt_status: VecTerminalStatus | None = None
    output_file_count: int | None = Field(default=None, ge=0)
    output_bytes: int | None = Field(default=None, ge=0)
    detail: str = Field(min_length=1, max_length=1_000)


class VecJobPackImportVerification(VecCampaignModel):
    """Complete typed outcome of verifying one returned receipt set against a pack."""

    schema_version: Literal["1.0"] = VEC_JOB_PACK_SCHEMA_VERSION
    method_version: Literal["vec-csf-job-pack-1.0"] = VEC_JOB_PACK_METHOD_VERSION
    status: VecJobPackImportStatus
    pack_id: str
    pack_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    design_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    experiment_id: str
    declared_cell_count: int = Field(ge=1)
    returned_receipt_count: int = Field(ge=0)
    fulfilled_cell_count: int = Field(ge=0)
    unfulfilled_run_ids: list[str]
    cells: list[VecJobPackCellVerification]
    findings: list[str] = Field(max_length=256)
    limitations: list[str] = Field(min_length=1, max_length=16)
    admission_granted: Literal[False] = False
    scientific_admission: Literal[False] = False
    registry_write_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_outcome(self) -> VecJobPackImportVerification:
        fulfilled = [cell for cell in self.cells if cell.fulfilled]
        if len(fulfilled) != self.fulfilled_cell_count:
            raise ValueError("fulfilled cell count does not match the recorded cells")
        if len(self.cells) != self.declared_cell_count:
            raise ValueError("every declared cell must have a recorded verification")
        unfulfilled = sorted(cell.run_id for cell in self.cells if not cell.fulfilled)
        if sorted(self.unfulfilled_run_ids) != unfulfilled:
            raise ValueError("unfulfilled run ids do not match the recorded cells")
        if self.status is VecJobPackImportStatus.VERIFIED:
            if self.findings:
                raise ValueError("a verified import cannot carry findings")
            if self.fulfilled_cell_count != self.declared_cell_count:
                raise ValueError("a verified import must fulfil every declared cell")
        if self.status is VecJobPackImportStatus.PARTIAL and not self.unfulfilled_run_ids:
            raise ValueError("a partial import must name at least one unfulfilled cell")
        return self


def build_job_pack(
    *,
    design: VecCampaignDesign,
    pack_id: str,
    created_at_utc: str,
    inputs: Sequence[VecJobPackInputRef],
    required_output_names: Sequence[str] = DEFAULT_REQUIRED_OUTPUT_NAMES,
) -> VecJobPack:
    """Export one approved campaign design as a fingerprinted job pack.

    The design is exported as approved; this function never edits it, never
    relaxes it, and never invents an input. ``created_at_utc`` is the caller's
    value rather than a read clock, so the same arguments always produce the
    same pack bytes.
    """

    if not inputs:
        raise JobPackError("a job pack must declare at least one input")
    if not required_output_names:
        raise JobPackError("a job pack must require at least one output file")
    try:
        return VecJobPack(
            pack_id=pack_id,
            created_at_utc=created_at_utc,
            design=design,
            design_fingerprint=design.fingerprint(),
            inputs=sorted(inputs, key=lambda ref: (ref.repository, ref.path)),
            cells=_expected_cells(design),
            required_output_names=sorted(required_output_names),
            limitations=list(STANDING_JOB_PACK_LIMITATIONS),
        )
    except ValueError as exc:
        raise JobPackError(f"job pack could not be exported: {exc}") from exc


def verify_job_pack_import(
    pack: VecJobPack,
    receipts: Sequence[VecExecutionReceipt | Mapping[str, Any]],
    *,
    returned_design_fingerprint: str | None = None,
) -> VecJobPackImportVerification:
    """Verify a returned receipt set against the pack that asked for it.

    Answers whether these are the runs this pack declared and whether they came
    back intact. It is **not** an admission: the returned artifacts still go
    through the local ADR-061 fresh-run admission path before any registry write
    or scientific reading, and nothing here can shortcut that.

    ``returned_design_fingerprint`` is the design fingerprint the remote site
    reported alongside its results, when it reported one; a mismatch refuses the
    import outright.
    """

    findings: list[str] = []
    if returned_design_fingerprint is not None and (
        returned_design_fingerprint != pack.design_fingerprint
    ):
        findings.append(
            "returned design fingerprint "
            f"{returned_design_fingerprint} does not match the pack's "
            f"{pack.design_fingerprint}"
        )

    parsed: list[VecExecutionReceipt] = []
    for index, item in enumerate(receipts):
        receipt_or_error = _coerce_receipt(item)
        if isinstance(receipt_or_error, str):
            findings.append(
                f"returned receipt {index} is not a readable execution receipt: {receipt_or_error}"
            )
            continue
        parsed.append(receipt_or_error)

    declared = pack.declared_request_fingerprints()
    matched: dict[str, VecExecutionReceipt] = {}
    for receipt in parsed:
        fingerprint = receipt.request_fingerprint
        cell = declared.get(fingerprint)
        if cell is None:
            findings.append(
                f"receipt for run {receipt.request.run_id!r} carries request fingerprint "
                f"{fingerprint} which is not a declared cell of this pack"
            )
            continue
        if fingerprint in matched:
            findings.append(f"cell {cell.run_id} was returned more than once")
            continue
        matched[fingerprint] = receipt

    verifications: list[VecJobPackCellVerification] = []
    for cell in pack.cells:
        cell_receipt = matched.get(cell.request_fingerprint)
        if cell_receipt is None:
            verifications.append(
                VecJobPackCellVerification(
                    arm_label=cell.arm_label,
                    fleet_seed=cell.fleet_seed,
                    run_id=cell.run_id,
                    request_fingerprint=cell.request_fingerprint,
                    fulfilled=False,
                    detail="no receipt for this declared cell was returned",
                )
            )
            continue
        verifications.append(_verify_cell(pack, cell, cell_receipt, findings))

    fulfilled = sum(1 for item in verifications if item.fulfilled)
    unfulfilled = sorted(item.run_id for item in verifications if not item.fulfilled)
    if findings:
        status = VecJobPackImportStatus.REFUSED
    elif unfulfilled:
        status = VecJobPackImportStatus.PARTIAL
    else:
        status = VecJobPackImportStatus.VERIFIED

    return VecJobPackImportVerification(
        status=status,
        pack_id=pack.pack_id,
        pack_fingerprint=pack.fingerprint(),
        design_fingerprint=pack.design_fingerprint,
        experiment_id=pack.design.experiment_id,
        declared_cell_count=len(pack.cells),
        returned_receipt_count=len(parsed),
        fulfilled_cell_count=fulfilled,
        unfulfilled_run_ids=unfulfilled,
        cells=verifications,
        findings=findings,
        limitations=list(STANDING_JOB_PACK_LIMITATIONS),
    )


def _verify_cell(
    pack: VecJobPack,
    cell: VecJobPackCell,
    receipt: VecExecutionReceipt,
    findings: list[str],
) -> VecJobPackCellVerification:
    """Check one returned receipt against its declared cell."""

    cell_findings: list[str] = []
    if receipt.status is not VecTerminalStatus.COMPLETED:
        detail = f"returned as {receipt.status.value}; no outputs to verify"
        return VecJobPackCellVerification(
            arm_label=cell.arm_label,
            fleet_seed=cell.fleet_seed,
            run_id=cell.run_id,
            request_fingerprint=cell.request_fingerprint,
            fulfilled=False,
            receipt_status=receipt.status,
            detail=detail,
        )

    paths = [item.path for item in receipt.outputs]
    if len(set(paths)) != len(paths):
        cell_findings.append(f"cell {cell.run_id} returned duplicate output paths")
    missing = [name for name in pack.required_output_names if name not in set(paths)]
    if missing:
        cell_findings.append(
            f"cell {cell.run_id} is missing required output files: {', '.join(sorted(missing))}"
        )
    recomputed = output_fingerprint(receipt.outputs)
    if receipt.output_fingerprint != recomputed:
        cell_findings.append(
            f"cell {cell.run_id} output fingerprint {receipt.output_fingerprint} does not "
            f"recompute from its recorded per-file hashes"
        )
    if receipt.external_repositories_modified or receipt.raw_inputs_modified:
        cell_findings.append(f"cell {cell.run_id} reports modified audited sources or raw inputs")

    findings.extend(cell_findings)
    total_bytes = sum(item.size_bytes for item in receipt.outputs)
    detail = (
        "; ".join(cell_findings)
        if cell_findings
        else f"{len(receipt.outputs)} output files verified against their recorded hashes"
    )
    return VecJobPackCellVerification(
        arm_label=cell.arm_label,
        fleet_seed=cell.fleet_seed,
        run_id=cell.run_id,
        request_fingerprint=cell.request_fingerprint,
        fulfilled=not cell_findings,
        receipt_status=receipt.status,
        output_file_count=len(receipt.outputs),
        output_bytes=total_bytes,
        detail=detail,
    )


def _coerce_receipt(
    payload: VecExecutionReceipt | Mapping[str, Any],
) -> VecExecutionReceipt | str:
    """Return a parsed receipt, or the reason it could not be read.

    An unreadable receipt is a finding, not an exception: an import verifier that
    dies on the first malformed payload tells the reader less than one that
    refuses the whole set and names what was wrong with it.
    """

    if isinstance(payload, VecExecutionReceipt):
        return payload
    try:
        return VecExecutionReceipt.model_validate_json(json.dumps(payload))
    except (TypeError, ValueError) as exc:
        return str(exc).replace("\n", " ")[:400]


def _expected_cells(design: VecCampaignDesign) -> list[VecJobPackCell]:
    """Return the design's declared cells in deterministic order."""

    cells: list[VecJobPackCell] = []
    for arm in design.arms():
        for fleet_seed in design.fleet_seeds:
            cells.append(_cell_for(design, arm, fleet_seed))
    return cells


def _cell_for(design: VecCampaignDesign, arm: VecCampaignArm, fleet_seed: int) -> VecJobPackCell:
    request = design.cell_request(arm, fleet_seed)
    return VecJobPackCell(
        arm_label=arm.label,
        fleet_seed=fleet_seed,
        run_id=request.run_id,
        rsu_capacity_per_vehicle=arm.rsu_capacity_per_vehicle,
        request_fingerprint=request.fingerprint(),
    )


def _validate_manifest(design: VecCampaignDesign, inputs: Sequence[VecJobPackInputRef]) -> None:
    """Refuse a manifest that does not name exactly the inputs this design needs."""

    paths = [ref.path for ref in inputs]
    if len(set(paths)) != len(paths):
        raise ValueError("the input manifest must not declare the same path twice")

    traces = [ref for ref in inputs if ref.role is VecJobPackInputRole.TRACE]
    if len(traces) != 1:
        raise ValueError("the input manifest must declare exactly one trace")
    trace = traces[0]
    if trace.sha256 != design.trace_sha256 or trace.path != design.trace_file:
        raise ValueError("the declared trace does not match the design's reviewed trace identity")
    if PINNED_REVIEWED_TRACES.get(trace.sha256) != trace.path:
        raise ValueError("the declared trace is not the reviewed path for that hash")

    actors = [ref for ref in inputs if ref.role is VecJobPackInputRole.ACTOR]
    if len(actors) != 1:
        raise ValueError("the input manifest must declare exactly one actor checkpoint")
    actor = actors[0]
    actor_path, actor_sha = PINNED_ACTORS[design.actor_id]
    if actor.path != actor_path or actor.sha256 != actor_sha:
        raise ValueError("the declared actor does not match the pinned checkpoint for this design")

    sources = {
        ref.path: ref.sha256 for ref in inputs if ref.role is VecJobPackInputRole.EVALUATOR_SOURCE
    }
    for path, sha in PINNED_EVALUATOR_FILES.items():
        if sources.get(path) != sha:
            raise ValueError(
                f"the input manifest must declare the pinned evaluator source {path} "
                "with its audited hash"
            )

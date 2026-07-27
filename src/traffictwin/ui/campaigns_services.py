"""Read-only loading of campaign receipt files for the Campaigns browser.

The page-independent half of the Campaigns screen. A campaign receipt is the
terminal record one campaign invocation wrote when it stopped: the design
identity it ran under, the recorded approval, one row per declared cell, and the
resources the run consumed. This layer reads exactly one such file, named by the
person using the page, and turns it into display rows.

**It never goes looking.** There is no default path, no directory scan, no glob,
and no recent-files list. A campaign directory is opened only when someone types
its receipt's path, which is the property that keeps this page away from a
campaign that is executing right now.

**A receipt is not a live view.** It is written once, at the end, and says what
happened — including "halted". Nothing here polls, refreshes, or reports current
state, and the page says so rather than leaving the reader to assume.

**Receipts only.** No registry is opened, no analysis is computed, and no
scientific number is read: a receipt carries states, elapsed times, and byte
counts, and those are the only quantities this module surfaces. Phase and
approval fields are passed through verbatim.

**Recorded gap.** ``VecCampaignReceipt`` carries the *usage* of a campaign's
budget but not the declared ceilings — ``max_cells`` and
``max_total_output_bytes`` live in the design document, which a receipt does not
embed. This module reports usage and states that the ceilings are not in the
file, rather than presenting usage as if it were a percentage of something.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from traffictwin.integration.vec_campaign.models import (
    VEC_CAMPAIGN_METHOD_VERSION,
    VecCampaignCellState,
    VecCampaignReceipt,
)

#: Bounded read. A 200-cell receipt is a few hundred kilobytes; anything past
#: this is not a receipt and is refused without being parsed.
MAX_RECEIPT_BYTES = 8 * 1024 * 1024

BUDGET_CEILINGS_UNAVAILABLE_REASON = (
    "A receipt records what a campaign consumed, not the ceilings it was allowed. "
    "`max_cells` and `max_total_output_bytes` are declared in the design document, "
    "which the receipt does not embed, so usage is shown without a percentage."
)

NOT_LIVE_STATEMENT = (
    "A receipt is written when a campaign stops. This page reads that file and "
    "nothing else: it does not poll, refresh, or report whether anything is "
    "running now."
)

#: Cell states grouped for the summary, matching the receipt's own counters.
_ADMITTED_STATES = (VecCampaignCellState.ADMITTED,)
_REUSED_STATES = (VecCampaignCellState.REUSED,)
_FAILED_STATES = (
    VecCampaignCellState.EXECUTION_FAILED,
    VecCampaignCellState.ADMISSION_REFUSED,
)
_SKIPPED_STATES = (
    VecCampaignCellState.SKIPPED_BUDGET,
    VecCampaignCellState.SKIPPED_HALTED,
)


@dataclass(frozen=True)
class CampaignsError:
    """User-facing campaigns error with optional technical detail.

    Returned as a value, never raised: a mistyped path is an ordinary thing for
    a person to do and deserves a sentence, not a traceback.
    """

    message: str
    detail: str | None = None


@dataclass(frozen=True)
class LabelledValue:
    """One labelled field for a display table."""

    label: str
    value: str


@dataclass(frozen=True)
class CampaignCellRow:
    """One declared cell's recorded outcome."""

    arm_label: str
    fleet_seed: int
    run_id: str
    state: str
    elapsed_seconds: float | None
    output_bytes: int | None
    detail: str


@dataclass(frozen=True)
class CampaignArmSummary:
    """One arm's cell outcomes, counted from the recorded cells."""

    arm_label: str
    cell_count: int
    admitted: int
    reused: int
    failed: int
    skipped: int


@dataclass(frozen=True)
class CampaignBudgetUsage:
    """What the campaign consumed, with the ceilings honestly absent."""

    planned_cell_count: int
    recorded_cell_count: int
    admitted_cell_count: int
    reused_cell_count: int
    failed_cell_count: int
    skipped_cell_count: int
    total_output_bytes: int
    total_elapsed_seconds: float
    declared_ceilings_available: Literal[False] = False
    ceilings_unavailable_reason: str = BUDGET_CEILINGS_UNAVAILABLE_REASON


@dataclass(frozen=True)
class CampaignReceiptView:
    """One loaded receipt beside the path it was read from."""

    source_path: Path
    receipt: VecCampaignReceipt


def load_campaign_receipt(receipt_path: str | None) -> CampaignReceiptView | CampaignsError:
    """Load exactly the receipt file the caller named, or say why it could not.

    Nothing is scanned, defaulted, or inferred: an empty path returns the
    "nothing supplied" state rather than picking a file, and a directory is
    refused rather than searched.
    """

    if receipt_path is None or not receipt_path.strip():
        return CampaignsError(
            "No receipt file has been supplied. Enter the path to one campaign "
            "receipt JSON file; this page never searches for campaigns on its own."
        )
    path = Path(receipt_path.strip()).expanduser()
    if path.is_dir():
        return CampaignsError(
            "That path is a directory. Name the receipt JSON file itself — this "
            "page does not list or scan directories.",
            detail=str(path),
        )
    if not path.is_file():
        return CampaignsError(
            "No file exists at that path, so no receipt could be read.",
            detail=str(path),
        )
    try:
        size = path.stat().st_size
    except OSError as exc:
        return CampaignsError("The file could not be inspected.", detail=str(exc)[:300])
    if size > MAX_RECEIPT_BYTES:
        return CampaignsError(
            "That file is larger than a campaign receipt can be, so it was not opened.",
            detail=f"{size} bytes exceeds the {MAX_RECEIPT_BYTES}-byte bound",
        )
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return CampaignsError("The file could not be read as UTF-8 text.", detail=str(exc)[:300])

    mismatch = _artifact_mismatch(text)
    if mismatch is not None:
        return mismatch
    try:
        # The campaign models are strict and finite, so a receipt validates from
        # its persisted JSON exactly as it was written.
        receipt = VecCampaignReceipt.model_validate_json(text)
    except ValidationError as exc:
        return CampaignsError(
            "That file is not a valid campaign receipt, so nothing is displayed from it.",
            detail=str(exc)[:600],
        )
    return CampaignReceiptView(source_path=path, receipt=receipt)


def _artifact_mismatch(text: str) -> CampaignsError | None:
    """Name the artifact when a readable JSON file is simply the wrong kind.

    A campaign directory holds several JSON artifacts. Telling someone they
    opened the analysis rather than the receipt is more use than handing them a
    validation dump.
    """

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return CampaignsError(
            "That file is not valid JSON, so it is not a campaign receipt.",
            detail=str(exc)[:300],
        )
    if not isinstance(payload, dict):
        return CampaignsError(
            "That file does not contain a JSON object, so it is not a campaign receipt."
        )
    method = payload.get("method_version")
    if method is None:
        return CampaignsError(
            "That JSON file declares no method version, so it cannot be identified as a "
            "campaign receipt."
        )
    if method != VEC_CAMPAIGN_METHOD_VERSION:
        return CampaignsError(
            f"That file is a `{method}` artifact, not a campaign receipt "
            f"(`{VEC_CAMPAIGN_METHOD_VERSION}`).",
            detail="Campaign directories hold several artifacts; this page reads receipts only.",
        )
    return None


def identity_rows(receipt: VecCampaignReceipt) -> list[LabelledValue]:
    """Return the design identity the receipt records, verbatim."""

    return [
        LabelledValue("Experiment id", receipt.experiment_id),
        LabelledValue("Phase", receipt.phase.value),
        LabelledValue("Campaign status", receipt.status.value),
        LabelledValue("Design fingerprint", receipt.design_fingerprint),
        LabelledValue("Method version", receipt.method_version),
        LabelledValue("Schema version", receipt.schema_version),
        LabelledValue("Experiment registered", str(receipt.experiment_registered)),
        LabelledValue("Started (UTC)", receipt.started_at_utc),
        LabelledValue("Finished (UTC)", receipt.finished_at_utc),
    ]


def approval_rows(receipt: VecCampaignReceipt) -> list[LabelledValue]:
    """Return the recorded approval provenance, verbatim.

    ``held_out_authorised`` is displayed as recorded. This page states what the
    file says; it does not judge whether the approval was appropriate, and it
    never fills a blank in.
    """

    approval = receipt.approval
    return [
        LabelledValue("Predeclaration path", approval.predeclaration_path),
        LabelledValue("Predeclaration SHA-256", approval.predeclaration_sha256),
        LabelledValue("Approved by", approval.approved_by),
        LabelledValue("Approved role", approval.approved_role),
        LabelledValue("Approved at (UTC)", approval.approved_at_utc),
        LabelledValue("Held-out cohort authorised", str(approval.held_out_authorised)),
        LabelledValue(
            "Predeclaration verified unchanged at execution",
            str(receipt.predeclaration_verified_unchanged),
        ),
    ]


def cell_rows(receipt: VecCampaignReceipt) -> list[CampaignCellRow]:
    """Return one row per declared cell, in the receipt's recorded order."""

    return [
        CampaignCellRow(
            arm_label=cell.arm_label,
            fleet_seed=cell.fleet_seed,
            run_id=cell.run_id,
            state=cell.state.value,
            elapsed_seconds=cell.elapsed_seconds,
            output_bytes=cell.output_bytes,
            detail=cell.detail,
        )
        for cell in receipt.cells
    ]


def arm_summaries(receipt: VecCampaignReceipt) -> list[CampaignArmSummary]:
    """Return per-arm cell outcomes, arms in first-recorded order."""

    order: list[str] = []
    grouped: dict[str, list[VecCampaignCellState]] = {}
    for cell in receipt.cells:
        if cell.arm_label not in grouped:
            order.append(cell.arm_label)
            grouped[cell.arm_label] = []
        grouped[cell.arm_label].append(cell.state)
    return [
        CampaignArmSummary(
            arm_label=label,
            cell_count=len(grouped[label]),
            admitted=sum(1 for state in grouped[label] if state in _ADMITTED_STATES),
            reused=sum(1 for state in grouped[label] if state in _REUSED_STATES),
            failed=sum(1 for state in grouped[label] if state in _FAILED_STATES),
            skipped=sum(1 for state in grouped[label] if state in _SKIPPED_STATES),
        )
        for label in order
    ]


def declared_seeds(receipt: VecCampaignReceipt) -> list[int]:
    """Return the distinct fleet seeds the recorded cells name, sorted."""

    return sorted({cell.fleet_seed for cell in receipt.cells})


def budget_usage(receipt: VecCampaignReceipt) -> CampaignBudgetUsage:
    """Return what the campaign consumed, with the ceilings honestly absent."""

    return CampaignBudgetUsage(
        planned_cell_count=receipt.planned_cell_count,
        recorded_cell_count=len(receipt.cells),
        admitted_cell_count=receipt.admitted_cell_count,
        reused_cell_count=receipt.reused_cell_count,
        failed_cell_count=receipt.failed_cell_count,
        skipped_cell_count=receipt.skipped_cell_count,
        total_output_bytes=receipt.total_output_bytes,
        total_elapsed_seconds=receipt.total_elapsed_seconds,
    )


def phase_badges(receipt: VecCampaignReceipt) -> list[str]:
    """Return the phase, status, and authorisation badges for one receipt.

    Held-out authorisation gets its own badge in both directions: a campaign
    that consumed the reserved cohort should be visible at a glance, and one
    that did not should not be left ambiguous.
    """

    authorisation = (
        "HELD-OUT AUTHORISED" if receipt.approval.held_out_authorised else "HELD-OUT NOT AUTHORISED"
    )
    return [
        f"PHASE: {receipt.phase.value.upper()}",
        f"STATUS: {receipt.status.value.upper()}",
        authorisation,
        "RECEIPT RECORD",
    ]

"""Confirmatory-mode rendering of one held-out campaign's single contrast.

The exploratory harness in
:mod:`traffictwin.integration.vec_campaign.analysis` types itself
``confirmatory: False`` — correctly, because nothing about running that code
makes a result confirmatory. What makes a result confirmatory is the paperwork
around it: a predeclaration signed before the evidence existed, an approval that
binds those exact document bytes, the reserved held-out cohort explicitly
authorised, and a campaign that completed every declared cell.

This module is the renderer that refuses to produce a confirmatory report until
every one of those conditions is verified, and then presents **exactly one**
contrast — the design's primary endpoint, its baseline arm against its single
variation arm — as the confirmatory result. Every other number in the output is
labelled descriptive context, because a confirmatory protocol with one primary
endpoint has exactly one confirmatory number.

It fails closed. Each refusal is a typed error carrying a stable code, and there
is no flag, override, or partial mode that renders anyway.

The module reads models and the analysis artifact only: it never imports the
campaign service, never opens a registry, never touches live campaign data, and
computes no statistic of its own. Every reported value is one STA-01 already
recorded.

**A null or reversed primary result is a result.** The layout does not change
with the outcome: the same sections, in the same order, with the same
prominence, whether the estimate is positive, negative, zero, or unavailable.
The predeclaration's publishable-null commitment is only worth anything if the
null renders exactly like everything else.

Label ceiling: ``owner_approved_candidate``. This report never claims supervisor
approval, scientific validation, causality, or a significance verdict beyond the
numbers STA-01 itself produced.
"""

from __future__ import annotations

import re
from typing import Literal

from traffictwin.integration.vec_campaign.analysis import (
    VecArmDescriptives,
    VecCampaignAnalysis,
    VecCampaignComparison,
)
from traffictwin.integration.vec_campaign.models import (
    VecCampaignDesign,
    VecCampaignPhase,
    VecCampaignReceipt,
    VecCampaignStatus,
)

VEC_CONFIRMATORY_REPORT_METHOD_VERSION: Literal["vec-campaign-confirmatory-report-1.0"] = (
    "vec-campaign-confirmatory-report-1.0"
)

_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")

STANDING_CONFIRMATORY_LIMITATIONS = (
    "Label ceiling `owner_approved_candidate`. This is not supervisor approval, "
    "not scientific validation, and not a causal claim.",
    "Exactly one contrast is confirmatory: the predeclared primary endpoint, "
    "baseline against the single variation arm. Every other number in this "
    "report is descriptive context and carries no confirmatory standing.",
    "The estimate, interval, and randomisation p-value are STA-01's own outputs, "
    "reproduced verbatim. This report adds no threshold, no verdict, and no "
    "significance language of its own.",
    "A null or reversed primary result is reported with the same prominence as "
    "any other, per the predeclaration's publishable-null commitment.",
    "Deadline success is never physical completion; reconstructed evaluator "
    "behaviour is never an observed journey; the result describes one audited "
    "policy on one reviewed trace with one fleet preset.",
)


class ConfirmatoryReportError(ValueError):
    """Raised when confirmatory rendering is refused.

    The message always begins with a stable upper-case code so a caller can
    branch on the reason without parsing prose.
    """


def render_confirmatory_report(
    design: VecCampaignDesign,
    receipt: VecCampaignReceipt,
    analysis: VecCampaignAnalysis,
    *,
    predeclaration_sha256: str,
) -> str:
    """Render the confirmatory record for one held-out campaign, or refuse.

    ``predeclaration_sha256`` is the digest of the signed document the caller
    believes authorised this campaign. It is passed in rather than read from the
    design so that the design cannot vouch for itself: the caller states which
    document it means, and this function refuses if the approval names a
    different one.

    Refuses unless every one of these holds:

    * the design's phase is the held-out cohort;
    * its approval sets ``held_out_authorised``;
    * its approval digest equals ``predeclaration_sha256``;
    * the receipt's approval and identity match the design's, and its
      ``design_fingerprint`` equals the design's own fingerprint;
    * the receipt records that the predeclaration bytes were verified unchanged
      at execution time;
    * the receipt's status is ``completed`` with zero failed and zero skipped
      cells;
    * the analysis binds to the same design fingerprint, experiment, campaign
      status, primary endpoint, and baseline arm;
    * the design declares exactly one variation arm, and the analysis carries
      exactly its one matching comparison.

    The last condition is what makes "exactly one contrast" true by
    construction rather than by selection: a design with two variation arms has
    no single predeclared contrast, so this renderer refuses it rather than
    choosing one.

    An STA-01 study that could not be evaluated is **not** a refusal. It renders
    in the same layout with its status shown and its values marked unavailable —
    hiding an unevaluable primary endpoint would be the one outcome the
    publishable-null commitment cannot tolerate.
    """

    _require_digest(predeclaration_sha256)
    _require_held_out_authorisation(design, predeclaration_sha256)
    _require_receipt_binding(design, receipt)
    _require_complete_campaign(receipt)
    _require_analysis_binding(design, receipt, analysis)
    comparison = _require_single_contrast(design, analysis)
    return _render(design, receipt, analysis, comparison)


def _require_digest(predeclaration_sha256: str) -> None:
    if not _DIGEST_RE.fullmatch(predeclaration_sha256):
        raise ConfirmatoryReportError(
            "PREDECLARATION_DIGEST_MALFORMED: the supplied predeclaration digest is not "
            "64 lowercase hexadecimal characters"
        )


def _require_held_out_authorisation(design: VecCampaignDesign, digest: str) -> None:
    if design.phase is not VecCampaignPhase.HELD_OUT:
        raise ConfirmatoryReportError(
            "NOT_HELD_OUT_PHASE: a confirmatory report requires the held-out cohort; this "
            f"design declares phase `{design.phase.value}`"
        )
    if not design.approval.held_out_authorised:
        raise ConfirmatoryReportError(
            "HELD_OUT_NOT_AUTHORISED: the approval does not authorise the reserved held-out seeds"
        )
    if design.approval.predeclaration_sha256 != digest:
        raise ConfirmatoryReportError(
            "PREDECLARATION_DIGEST_MISMATCH: the approval binds a different predeclaration "
            "document than the one supplied"
        )


def _require_receipt_binding(design: VecCampaignDesign, receipt: VecCampaignReceipt) -> None:
    if receipt.design_fingerprint != design.fingerprint():
        raise ConfirmatoryReportError(
            "RECEIPT_DESIGN_MISMATCH: the receipt does not belong to this design"
        )
    if receipt.experiment_id != design.experiment_id or receipt.phase is not design.phase:
        raise ConfirmatoryReportError(
            "RECEIPT_IDENTITY_MISMATCH: the receipt's experiment or phase differs from the design's"
        )
    if receipt.approval != design.approval:
        raise ConfirmatoryReportError(
            "RECEIPT_APPROVAL_MISMATCH: the receipt records a different approval than the "
            "design carries"
        )
    if not receipt.predeclaration_verified_unchanged:
        raise ConfirmatoryReportError(
            "PREDECLARATION_NOT_VERIFIED: the campaign did not verify the predeclaration "
            "bytes were unchanged at execution, so this report cannot stand behind the digest "
            "it would cite"
        )


def _require_complete_campaign(receipt: VecCampaignReceipt) -> None:
    if receipt.status is not VecCampaignStatus.COMPLETED:
        raise ConfirmatoryReportError(
            f"CAMPAIGN_NOT_COMPLETED: the campaign status is `{receipt.status.value}`"
        )
    if receipt.failed_cell_count:
        raise ConfirmatoryReportError(
            f"CAMPAIGN_HAS_FAILED_CELLS: {receipt.failed_cell_count} declared cells failed"
        )
    if receipt.skipped_cell_count:
        raise ConfirmatoryReportError(
            f"CAMPAIGN_HAS_SKIPPED_CELLS: {receipt.skipped_cell_count} declared cells were "
            "skipped, so the declared matrix is incomplete"
        )


def _require_analysis_binding(
    design: VecCampaignDesign,
    receipt: VecCampaignReceipt,
    analysis: VecCampaignAnalysis,
) -> None:
    if analysis.design_fingerprint != design.fingerprint():
        raise ConfirmatoryReportError(
            "ANALYSIS_DESIGN_MISMATCH: the analysis does not belong to this design"
        )
    if analysis.experiment_id != design.experiment_id:
        raise ConfirmatoryReportError(
            "ANALYSIS_EXPERIMENT_MISMATCH: the analysis names a different experiment"
        )
    # The analysis artifact carries no receipt fingerprint, so this is the
    # strongest analysis-to-receipt binding the recorded models support: the
    # design fingerprint both share, plus the campaign status the analysis
    # copied from the receipt it was run against.
    if analysis.campaign_status != receipt.status.value:
        raise ConfirmatoryReportError(
            "ANALYSIS_RECEIPT_MISMATCH: the analysis records campaign status "
            f"`{analysis.campaign_status}` against a receipt reporting "
            f"`{receipt.status.value}`"
        )
    if analysis.primary_metric_key != design.primary_metric_key:
        raise ConfirmatoryReportError(
            "PRIMARY_METRIC_MISMATCH: the analysis evaluated a different primary endpoint "
            "than the design predeclared"
        )
    if analysis.baseline_label != design.baseline_arm.label:
        raise ConfirmatoryReportError(
            "BASELINE_ARM_MISMATCH: the analysis used a different baseline arm than the "
            "design predeclared"
        )


def _require_single_contrast(
    design: VecCampaignDesign, analysis: VecCampaignAnalysis
) -> VecCampaignComparison:
    if len(design.variation_arms) != 1:
        raise ConfirmatoryReportError(
            "NOT_A_SINGLE_CONTRAST: a confirmatory report presents one predeclared contrast, "
            f"but the design declares {len(design.variation_arms)} variation arms; choosing "
            "one here would be selection after the evidence"
        )
    variation_label = design.variation_arms[0].label
    if len(analysis.comparisons) != 1:
        raise ConfirmatoryReportError(
            "NOT_A_SINGLE_CONTRAST: the analysis carries "
            f"{len(analysis.comparisons)} comparisons for a one-arm design"
        )
    comparison = analysis.comparisons[0]
    if comparison.variation_label != variation_label:
        raise ConfirmatoryReportError(
            "CONTRAST_ARM_MISMATCH: the analysis compared arm "
            f"`{comparison.variation_label}` against a design declaring `{variation_label}`"
        )
    return comparison


def _render(
    design: VecCampaignDesign,
    receipt: VecCampaignReceipt,
    analysis: VecCampaignAnalysis,
    comparison: VecCampaignComparison,
) -> str:
    baseline = design.baseline_arm.label
    variation = design.variation_arms[0].label
    lines = [
        f"# Confirmatory result — `{design.experiment_id}`",
        "",
        "**One predeclared contrast, reported under a signed protocol on the reserved "
        "held-out cohort.** Every number outside the confirmatory section below is "
        "descriptive context and carries no confirmatory standing.",
        "",
        f"- Method: `{VEC_CONFIRMATORY_REPORT_METHOD_VERSION}`",
        f"- Research status: `{analysis.research_status}` — not supervisor approval, not "
        "scientific validation.",
        "",
        "## Signed predeclaration and design identity",
        "",
        f"- Predeclaration: `{design.approval.predeclaration_path}`",
        f"- Predeclaration SHA-256: `{design.approval.predeclaration_sha256}`",
        f"- Verified unchanged at execution: {receipt.predeclaration_verified_unchanged}",
        f"- Approved by: {design.approval.approved_by} ({design.approval.approved_role}), "
        f"{design.approval.approved_at_utc}",
        f"- Held-out cohort authorised: {design.approval.held_out_authorised}",
        f"- Design fingerprint: `{design.fingerprint()}`",
        f"- Phase: `{design.phase.value}`",
        f"- Predeclared research question: {design.research_question}",
        "",
        "The campaign-analysis artifact this report reads is itself typed "
        "`confirmatory: false`, and that is correct: running the harness is not what makes "
        "a result confirmatory. The signed predeclaration, the bound digest, the authorised "
        "held-out cohort, and the completed declared matrix are — and this report renders "
        "only after verifying all four.",
        "",
        "## The confirmatory result",
        "",
        f"Predeclared primary endpoint `{design.primary_metric_key}`, arm `{variation}` "
        f"against baseline arm `{baseline}`, paired on the declared seed cohort.",
        "",
        "| Quantity | Value |",
        "|---|---|",
        f"| STA-01 study status | `{comparison.study_status}` |",
        f"| Admitted pairs | {comparison.admitted_pair_count} |",
        f"| Estimate (variation − baseline) | {_number(comparison.mean_paired_difference)} |",
        f"| Bootstrap interval | {_interval(comparison)} |",
        f"| Randomisation p-value | {_number(comparison.randomisation_p_value, places=4)} |",
        f"| Effect direction | {_direction(comparison.mean_paired_difference)} |",
        "",
        "Direction is the sign of the estimate and nothing more. Whether that direction is "
        "desirable is a reading of the endpoint, which this report does not make. The "
        "interval and p-value are STA-01's own outputs, reproduced verbatim; no threshold "
        "is applied to them here.",
        "",
        "## Descriptive context (not the confirmatory result)",
        "",
        f"Every value below is descriptive. The predeclared contrast is the one above; "
        f"nothing here is a second result, and the design's {len(design.arms())} arms are "
        "reported for completeness only.",
        "",
        f"### Primary endpoint per arm — descriptive (`{design.primary_metric_key}`)",
        "",
        *_descriptive_table(analysis.primary_descriptives),
        "",
        "### Secondary metrics per arm — descriptive, never promoted",
        "",
        *(
            _descriptive_table(analysis.secondary_descriptives)
            if analysis.secondary_descriptives
            else ["No secondary metric was recorded for this campaign."]
        ),
        "",
        "## Campaign execution evidence",
        "",
        f"- Campaign status: `{receipt.status.value}`",
        f"- Declared cells: {receipt.planned_cell_count} "
        f"(admitted {receipt.admitted_cell_count}, reused {receipt.reused_cell_count}, "
        f"failed {receipt.failed_cell_count}, skipped {receipt.skipped_cell_count})",
        f"- Admitted metric collections analysed: {analysis.admitted_collection_count}",
        f"- Trace: `{design.trace_file}` (`{design.trace_sha256}`)",
        f"- Actor: `{design.actor_id}`, fleet preset `{design.fleet.value}`, evaluator seed "
        f"{design.evaluator_seed}",
        f"- Declared fleet-seed cohort size: {len(design.fleet_seeds)}",
        f"- Analysis generated at: {analysis.generated_at_utc}",
        "",
        "## What this report does not claim",
        "",
        "- It does not claim supervisor approval, ethics approval, or scientific validation.",
        "- It does not claim causality: the contrast isolates one declared evaluator "
        "control, not a mechanism.",
        "- It does not declare a result significant, meaningful, or practically important; "
        "the only inferential numbers are STA-01's, printed as it produced them.",
        "- It does not generalise beyond this trace, this actor, this fleet preset, and this "
        "declared seed cohort.",
        "",
        "## Limitations",
        "",
        *[f"- {item}" for item in STANDING_CONFIRMATORY_LIMITATIONS],
        "",
        "## Predeclared limitations carried from the analysis",
        "",
        *[f"- {item}" for item in analysis.limitations],
        "",
    ]
    return "\n".join(lines)


def _descriptive_table(rows: list[VecArmDescriptives]) -> list[str]:
    if not rows:
        return ["No descriptive values were recorded."]
    lines = [
        "| Arm | Metric | Seeds | Mean | Min | Max |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| `{row.arm_label}` | `{row.metric_key}` | {len(row.seed_values)} "
            f"| {row.mean:.6f} | {row.minimum:.6f} | {row.maximum:.6f} |"
        )
    return lines


def _number(value: float | None, *, places: int = 6) -> str:
    if value is None:
        return "unavailable"
    return f"{value:.{places}f}"


def _interval(comparison: VecCampaignComparison) -> str:
    lower = comparison.bootstrap_lower
    upper = comparison.bootstrap_upper
    if lower is None or upper is None:
        return "unavailable"
    return f"[{lower:.6f}, {upper:.6f}]"


def _direction(difference: float | None) -> str:
    """Describe the estimate's sign without grading it.

    A zero or unavailable estimate gets a sentence of the same shape and the
    same place in the table as any other, because the null must not read as an
    absence of result.
    """

    if difference is None:
        return "unavailable — the study did not produce an estimate"
    if difference > 0:
        return "variation above baseline"
    if difference < 0:
        return "variation below baseline"
    return "no difference in the estimate"

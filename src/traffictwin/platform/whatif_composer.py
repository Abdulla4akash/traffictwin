"""What-if scenario composer (platform P-1 tier 2, decision from 30 July).

Implements ``docs/platform/whatif_composer_design.md``: the predict-then-verify
front end. A structured form produces (1) an instant tier-1 prediction from the
committed outcome-predictor fit — or that predictor's typed refusal, embedded
verbatim — and (2) a one-action escalation: a campaign-design draft in the
house schema plus a predeclaration draft in the house format, prediction, band
and verdict rule pre-filled, sign-off EMPTY.

The guardrails are structural, not politeness:

- **Draft-only** — this module never imports or references the campaign
  executor; execution happens through the unmodified human-run instrument,
  whose byte-bound approval (typed approver + predeclaration digest,
  placeholders refused) no draft can satisfy.
- **Seed protection** — the spent held-out seeds {10-14} refuse outright, and
  the COMPLETE registered seed ledger (pilot, grid, deep, drafted cohorts) is
  checked for collisions; a draft proposes fresh seeds and a human fixes them
  at signing. The instrument's ``held_out_authorised`` gate is a backstop,
  not the whole rule.
- **Cite-only-admitted-and-committed** — the result-card renderer answers
  only from analyses in the admitted experiment registry with their pinned
  design fingerprints, refuses NON_ADMITTED records, and verifies that every
  decimal number it emits appears textually in the cited file; an invented
  number is a typed failure, not a card.
- **No silent envelope escape** — a scenario the predictor refuses is still
  draftable (that is the point of tier 2); the draft carries
  ``prediction_available: false`` and the refusal, never an invented
  expectation. Unavailable means unavailable: ``metrics_unavailable`` reasons
  propagate into the predeclaration and no value is substituted from another
  actor.
- **Budget honesty** — drafted designs embed the observed per-cell runtime
  with its provenance and hardware context; the figures are planning
  estimates, not quotas, guarantees, or permission to launch.
- **Citation and standing** — producer-derived prediction, draft and summary
  artifacts carry the mandatory producer/SUMO citation bundle
  (``docs/producer_citation_requirements.md``).

The LLM socket is DORMANT (P-D1): natural language routes to a typed refusal
until a funded ``ANTHROPIC_API_KEY`` exists — the owner's Max subscriptions
are coding tools, not runtime API. The template path below produces the
complete artifacts; the socket is an enhancement, never a dependency.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal, NoReturn

from pydantic import model_validator

from traffictwin.integration.vec_campaign.models import (
    MAX_CAMPAIGN_CELLS,
    VecCampaignArm,
    VecCampaignBudget,
)
from traffictwin.platform.outcome_predictor import (
    EXPERIMENT_REGISTRY,
    MEASURED_FLEET_PRESET,
    PRODUCER_CITATION_BUNDLE,
    PRODUCER_CITATION_REFERENCE,
    TRAINED_ACTOR,
    LoadedFit,
    PredictionRecord,
    PredictionRefusal,
    PredictorModel,
    VecScenario,
    predict,
)

COMPOSER_METHOD_VERSION: Literal["vec-whatif-composer-1.0"] = "vec-whatif-composer-1.0"
COMPOSER_DESIGN_REFERENCE: Literal["docs/platform/whatif_composer_design.md"] = (
    "docs/platform/whatif_composer_design.md"
)

#: The reference capacity every measured campaign used as its baseline arm.
BASELINE_REFERENCE_CAPACITY = 2.5

#: The spent confirmatory cohort; no draft may name these, ever (design §2).
HELD_OUT_SEEDS = frozenset({10, 11, 12, 13, 14})

#: The complete registered seed ledger (reviewed design §2): the drafter
#: refuses collisions with EVERY registered cohort, not one hard-coded set.
#: A draft proposes fresh seeds; a human fixes them at signing.
REGISTERED_SEED_COHORTS: dict[str, frozenset[int]] = {
    "capacity-study held-out cohort (SPENT — never reusable)": HELD_OUT_SEEDS,
    "pilot and crossover-baseline exploratory cohort": frozenset({0, 1, 2}),
    "grid and baseline-invariance cohort": frozenset({50, 51, 52}),
    "deep-sweep cohort": frozenset({60, 61, 62}),
    "proposed in the actor-crossover study draft": frozenset({20, 21, 22, 23, 24}),
}

#: Where an owner may later DELIBERATELY place a reviewed draft (design §4).
#: The composer itself writes only to an explicit owner-selected path.
DRAFTS_DIRECTORY = Path("docs") / "evaluation" / "drafts"

DRAFT_BANNER = (
    "DRAFT — UNSIGNED. This document was drafted by the what-if composer and "
    "approves nothing. Execution requires the campaign instrument's byte-bound "
    "approval: a typed human approver and this document's final SHA-256, which "
    "no composer output can supply."
)

_PREDICTION_BANNER = "PREDICTION — NOT EVIDENCE"

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,80}$")
_CARD_DECIMAL_RE = re.compile(r"\d+\.\d+(?:[eE][+-]?\d+)?")


class WhatifComposerError(RuntimeError):
    """Typed composer refusal; drafting fails closed, never silently."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class TraceExecutionSpec(PredictorModel):
    """Pinned execution facts for one reviewed trace, with cost provenance."""

    trace_file: str
    trace_sha256: str
    max_steps: int
    per_cell_seconds: float
    per_cell_seconds_provenance: str
    per_cell_output_bytes: int


#: Reviewed-trace execution facts. Hashes are the runner's pinned allowlist
#: values; costs are the measured probe/run figures, provenance stated —
#: budget honesty (design §2) forbids silent estimates.
TRACE_EXECUTION_SPECS: dict[str, TraceExecutionSpec] = {
    "we": TraceExecutionSpec(
        trace_file="traces/trace_we_fullrsu.npz",
        trace_sha256="a2612865f5e1ef6d066975d6430693225f5d16060f139176548c8ae020e428be",
        max_steps=32_400,
        per_cell_seconds=225.7,
        per_cell_seconds_provenance="measured full-protocol run, 26 July 2026",
        per_cell_output_bytes=35_000_000,
    ),
    "ev": TraceExecutionSpec(
        trace_file="traces/trace_ev_fullrsu.npz",
        trace_sha256="70d6d12f3004b08c8a17e450df04ea70e74723c7a25149d3f5e1629903d01208",
        max_steps=23_400,
        per_cell_seconds=265.9,
        per_cell_seconds_provenance="measured timing probe, 28 July 2026",
        per_cell_output_bytes=28_000_000,
    ),
    "wd_am": TraceExecutionSpec(
        trace_file="traces/trace_wd_am_fullrsu.npz",
        trace_sha256="5e36a7cb8b49afa9929574c9627216b7479a28ee0cbd83cc81ff852e647fd7ee",
        max_steps=10_800,
        per_cell_seconds=266.0,
        per_cell_seconds_provenance=(
            "ESTIMATE from the ev-class low-density band (215 slots; not separately probed)"
        ),
        per_cell_output_bytes=35_000_000,
    ),
    "wd_pm": TraceExecutionSpec(
        trace_file="traces/trace_wd_pm_fullrsu.npz",
        trace_sha256="848ba3cf278515f6a628bfb575892373454fae60ea6edf717da3b7683051ba9f",
        max_steps=25_200,
        per_cell_seconds=266.0,
        per_cell_seconds_provenance=(
            "ESTIMATE from the ev-class low-density band (163 slots; not separately probed)"
        ),
        per_cell_output_bytes=35_000_000,
    ),
    "inc": TraceExecutionSpec(
        trace_file="traces/trace_inc_fullrsu.npz",
        trace_sha256="e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056",
        max_steps=3_600,
        per_cell_seconds=3_555.96,
        per_cell_seconds_provenance="measured full-length timing probe, 26-27 July 2026",
        per_cell_output_bytes=100_000_000,
    ),
}


class ComposerForm(PredictorModel):
    """The structured scenario form. NL never bypasses this schema (P-D1)."""

    trace: str
    capacity: float | None = None
    reduce_factor: float | None = None
    actor: str = TRAINED_ACTOR
    fleet_preset: str = MEASURED_FLEET_PRESET
    fleet_size: int | None = None
    fleet_seeds: tuple[int, ...] = (30, 31, 32)
    comparison_capacity: float | None = None
    question: str | None = None

    @model_validator(mode="after")
    def validate_form(self) -> ComposerForm:
        if (self.capacity is None) == (self.reduce_factor is None):
            raise ValueError(
                "give exactly one of capacity or reduce_factor ('reduce xN' divides "
                f"the {BASELINE_REFERENCE_CAPACITY:g} reference capacity by N)"
            )
        if self.reduce_factor is not None and self.reduce_factor <= 1.0:
            raise ValueError("reduce_factor must be greater than 1")
        return self

    @property
    def requested_capacity(self) -> float:
        if self.capacity is not None:
            return self.capacity
        assert self.reduce_factor is not None
        return BASELINE_REFERENCE_CAPACITY / self.reduce_factor

    @property
    def baseline_capacity(self) -> float:
        if self.comparison_capacity is not None:
            return self.comparison_capacity
        return BASELINE_REFERENCE_CAPACITY


class DraftCost(PredictorModel):
    """The observed price of the drafted campaign, shown before signing.

    Planning estimates, not quotas, guarantees, or permission to launch —
    the reviewed design's budget-honesty wording, carried verbatim.
    """

    cells: int
    per_cell_seconds: float
    per_cell_seconds_provenance: str
    runtime_context: str
    total_seconds: float
    total_hours: float
    max_total_output_bytes: int
    estimate_note: str


class ComposerDraft(PredictorModel):
    """One composed scenario: tier-1 answer plus the tier-2 escalation pair."""

    record_type: Literal["whatif_scenario_draft"] = "whatif_scenario_draft"
    method_version: Literal["vec-whatif-composer-1.0"] = COMPOSER_METHOD_VERSION
    design_reference: Literal["docs/platform/whatif_composer_design.md"] = COMPOSER_DESIGN_REFERENCE
    status: Literal["DRAFT_UNSIGNED"] = "DRAFT_UNSIGNED"
    generated_at_utc: str
    slug: str
    form: ComposerForm
    prediction_available: bool
    prediction: PredictionRecord | None
    prediction_refusal: PredictionRefusal | None
    fit_digest: str
    design_draft: dict[str, object]
    predeclaration_markdown: str
    cost: DraftCost
    drafted_by: dict[str, str]


def compose_from_natural_language(text: str) -> NoReturn:
    """The LLM socket. Dormant until a funded key exists (P-D1) — refuses."""

    del text
    raise WhatifComposerError(
        "LLM_SOCKET_DORMANT",
        "the natural-language socket activates only when a funded ANTHROPIC_API_KEY "
        "exists (owner decision P-D1: form-first; the owner's Max subscriptions are "
        "coding tools, not runtime API). The structured form produces the identical "
        "artifacts — the socket is an enhancement, never a dependency.",
    )


def llm_socket_status() -> dict[str, object]:
    """Report the socket's dormancy honestly; nothing here probes a key."""

    return {
        "available": False,
        "mode": "template",
        "reason": (
            "dormant until the owner funds an ANTHROPIC_API_KEY AND explicitly "
            "configures activation (P-D1); key presence alone must never silently "
            "enable an external transfer. The form path produces the complete "
            "draft artifacts."
        ),
    }


def compose_scenario(
    form: ComposerForm,
    loaded: LoadedFit,
    *,
    generated_at_utc: str,
) -> ComposerDraft:
    """Form in; prediction (or its refusal) plus the escalation drafts out."""

    spec = TRACE_EXECUTION_SPECS.get(form.trace)
    if spec is None:
        raise WhatifComposerError(
            "COMPOSER_TRACE_UNKNOWN",
            f"trace '{form.trace}' is not a reviewed trace; the reviewed set is "
            f"{sorted(TRACE_EXECUTION_SPECS)} — admitting a new trace is a "
            "reviewed-allowlist extension, not a composer option",
        )
    named_held_out = sorted(set(form.fleet_seeds) & HELD_OUT_SEEDS)
    if named_held_out:
        raise WhatifComposerError(
            "COMPOSER_HELD_OUT_REFUSED",
            f"drafted designs may not name the spent held-out seeds {named_held_out}; "
            "the reserved confirmatory cohort {10-14} was consumed by the signed "
            "capacity confirmatory and its reuse requires the instrument's "
            "held_out_authorised approval, which no draft can grant",
        )
    collisions = {
        cohort: sorted(set(form.fleet_seeds) & seeds)
        for cohort, seeds in REGISTERED_SEED_COHORTS.items()
        if set(form.fleet_seeds) & seeds
    }
    if collisions:
        fresh = suggest_fresh_seeds(len(form.fleet_seeds))
        raise WhatifComposerError(
            "COMPOSER_SEED_COLLISION",
            f"the proposed seeds collide with registered cohorts {collisions}; a draft "
            f"proposes fresh seeds (for example {fresh}) and a human fixes them at "
            "signing — the complete registered ledger is checked, not one hard-coded set",
        )
    if len(form.fleet_seeds) < 3:
        raise WhatifComposerError(
            "COMPOSER_SEEDS_INSUFFICIENT",
            "the campaign schema requires at least three fleet seeds "
            "(fewer cannot support the predeclared paired analysis)",
        )
    if len(set(form.fleet_seeds)) != len(form.fleet_seeds):
        raise WhatifComposerError(
            "COMPOSER_SEEDS_DUPLICATED", "fleet seeds must not contain duplicates"
        )
    requested = form.requested_capacity
    baseline = form.baseline_capacity
    if requested == baseline:
        raise WhatifComposerError(
            "COMPOSER_ARMS_IDENTICAL",
            f"the requested capacity {requested:g} equals the comparison arm "
            f"{baseline:g}; arms must be distinct cells — pick a different "
            "comparison_capacity",
        )

    scenario = VecScenario(
        trace=form.trace,
        capacity=requested,
        actor=form.actor,
        fleet_preset=form.fleet_preset,
        fleet_size=form.fleet_size,
    )
    outcome = predict(scenario, loaded)
    prediction: PredictionRecord | None = None
    refusal: PredictionRefusal | None = None
    if isinstance(outcome, PredictionRecord):
        prediction = outcome
    else:
        refusal = outcome

    slug = _slug(form, generated_at_utc)
    cost = _draft_cost(form, spec)
    design_draft = _design_draft(form, spec, slug, cost, generated_at_utc)
    predeclaration = _predeclaration_markdown(
        form, spec, prediction, refusal, cost, generated_at_utc
    )
    return ComposerDraft(
        generated_at_utc=generated_at_utc,
        slug=slug,
        form=form,
        prediction_available=prediction is not None,
        prediction=prediction,
        prediction_refusal=refusal,
        fit_digest=loaded.digest,
        design_draft=design_draft,
        predeclaration_markdown=predeclaration,
        cost=cost,
        drafted_by={"mode": "template", "method_version": COMPOSER_METHOD_VERSION},
    )


def suggest_fresh_seeds(count: int) -> tuple[int, ...]:
    """The lowest seeds colliding with no registered cohort, starting at 30."""

    registered = frozenset().union(*REGISTERED_SEED_COHORTS.values())
    fresh: list[int] = []
    candidate = 30
    while len(fresh) < count:
        if candidate not in registered:
            fresh.append(candidate)
        candidate += 1
    return tuple(fresh)


def _slug(form: ComposerForm, generated_at_utc: str) -> str:
    capacity_text = f"{form.requested_capacity:g}".replace(".", "p")
    date_text = generated_at_utc[:10].replace("-", "")
    slug = f"whatif_{form.trace}_cap{capacity_text}_{date_text}"
    if not _SLUG_RE.fullmatch(slug):
        raise WhatifComposerError("COMPOSER_SLUG_INVALID", f"draft slug '{slug}' is not usable")
    return slug


def _draft_cost(form: ComposerForm, spec: TraceExecutionSpec) -> DraftCost:
    cells = 2 * len(form.fleet_seeds)
    total_seconds = cells * spec.per_cell_seconds
    return DraftCost(
        cells=cells,
        per_cell_seconds=spec.per_cell_seconds,
        per_cell_seconds_provenance=spec.per_cell_seconds_provenance,
        runtime_context=(
            "observed on the owner's local Apple-silicon machine, single evaluator "
            "process at ~390% CPU with no competing heavy load"
        ),
        total_seconds=total_seconds,
        total_hours=total_seconds / 3600.0,
        max_total_output_bytes=3 * cells * spec.per_cell_output_bytes,
        estimate_note=("planning estimates, not quotas, guarantees, or permission to launch"),
    )


def _design_draft(
    form: ComposerForm,
    spec: TraceExecutionSpec,
    slug: str,
    cost: DraftCost,
    generated_at_utc: str,
) -> dict[str, object]:
    """The campaign design in the house schema, approval explicitly UNSIGNED.

    Every field the schema can validate without an approval is validated here
    (arms, budget, cell count, run-id shape, pinned trace identity). A real
    ``VecCampaignDesign`` cannot be constructed from this draft until a human
    supplies the byte-bound approval — that gate belongs to the instrument.
    """

    requested = form.requested_capacity
    baseline_arm = VecCampaignArm(
        label=f"cap-{form.baseline_capacity:g}",
        rsu_capacity_per_vehicle=form.baseline_capacity,
    )
    variation_arm = VecCampaignArm(label=f"cap-{requested:g}", rsu_capacity_per_vehicle=requested)
    budget = VecCampaignBudget(
        max_cells=min(cost.cells, MAX_CAMPAIGN_CELLS),
        max_total_output_bytes=cost.max_total_output_bytes,
        halt_on_failure=True,
    )
    experiment_id = f"vec-{slug.replace('_', '-')}"
    run_id_prefix = slug.replace("_", "-")[:40]
    return {
        "record_type": "vec_campaign_design_draft",
        "status": "DRAFT_UNSIGNED",
        "banner": DRAFT_BANNER,
        "schema_mirrors": "vec-bounded-campaign-1.0",
        "generated_at_utc": generated_at_utc,
        "experiment_id": experiment_id,
        "research_question": form.question
        or (
            f"What does capacity {requested:g} measure on the '{form.trace}' trace "
            f"for actor {form.actor}, against the cap-{form.baseline_capacity:g} "
            "comparison arm?"
        ),
        "run_id_prefix": run_id_prefix,
        "phase": "pilot",
        "approval": {
            "status": "UNSIGNED",
            "note": (
                "the campaign instrument requires a typed human approver and the "
                "final predeclaration SHA-256; placeholder identities are refused "
                "at the model boundary, so this draft cannot be executed as-is"
            ),
        },
        "trace_file": spec.trace_file,
        "trace_sha256": spec.trace_sha256,
        "actor_id": form.actor,
        "fleet": MEASURED_FLEET_PRESET,
        "evaluator_seed": 0,
        "max_steps": spec.max_steps,
        "timeout_seconds": 7_200,
        "baseline_arm": baseline_arm.model_dump(mode="json"),
        "variation_arms": [variation_arm.model_dump(mode="json")],
        "pairing_seed_source": "fleet_seed",
        "fleet_seeds": sorted(form.fleet_seeds),
        "primary_metric_key": "tos.task.deadline_success.rate",
        "budget": budget.model_dump(mode="json"),
        "cost": cost.model_dump(mode="json"),
    }


def _prediction_section(
    prediction: PredictionRecord | None, refusal: PredictionRefusal | None
) -> list[str]:
    if prediction is not None:
        lines = [
            f"**{_PREDICTION_BANNER}** (regime `{prediction.regime}`, fit digest "
            f"`{prediction.fit_digest[:16]}…`). The verdict rule below binds to these "
            "intervals, fixed before any new cell exists:",
            "",
            "| metric | predicted point | interval low | interval high |",
            "|---|---:|---:|---:|",
        ]
        for metric in prediction.metrics:
            lines.append(
                f"| {metric.metric} | {metric.point!r} | {metric.interval_low!r} "
                f"| {metric.interval_high!r} |"
            )
        if prediction.metrics_unavailable:
            lines.append("")
            lines.append(
                "**Unavailable means unavailable** — these metrics carry no predicted "
                "value, the verdict rule does not apply to them, and no value is "
                "invented or substituted from another actor:"
            )
            for name, reason in sorted(prediction.metrics_unavailable.items()):
                lines.append(f"- {name}: {reason}")
        lines.extend(
            [
                "",
                "**Verdict rule (fixed in advance):** for each predicted metric, the "
                "measured per-arm mean over the campaign's admitted seeds falls inside "
                "the interval above → prediction HELD for that metric; outside → "
                "REFUTED; cells missing → NOT EVALUABLE. No other reading is licensed.",
            ]
        )
        return lines
    assert refusal is not None
    return [
        "**No tier-1 prediction exists for this scenario — that is the point of "
        "this campaign.** The predictor refused:",
        "",
        f"- code: `{refusal.code}`",
        f"- detail: {refusal.detail}",
        f"- the campaign that closes the gap: {refusal.closing_campaign}",
        "",
        "This document carries `prediction_available: false`. It predeclares a "
        "MEASUREMENT, not a verification; no expected value is invented for it.",
    ]


def _predeclaration_markdown(
    form: ComposerForm,
    spec: TraceExecutionSpec,
    prediction: PredictionRecord | None,
    refusal: PredictionRefusal | None,
    cost: DraftCost,
    generated_at_utc: str,
) -> str:
    requested = form.requested_capacity
    seeds_text = ", ".join(str(seed) for seed in sorted(form.fleet_seeds))
    question = form.question or (
        f"What does capacity {requested:g} measure on the '{form.trace}' trace for "
        f"actor {form.actor}, against the cap-{form.baseline_capacity:g} comparison arm?"
    )
    lines = [
        f"# What-if campaign — {form.trace} at capacity {requested:g} — "
        "Predeclaration (DRAFT — UNSIGNED)",
        "",
        f"**{DRAFT_BANNER}**",
        "",
        f"Drafted {generated_at_utc} by the what-if composer "
        f"({COMPOSER_METHOD_VERSION}, template path; LLM socket dormant per P-D1). "
        f"Design reference: {COMPOSER_DESIGN_REFERENCE}.",
        "",
        "## 1. Question and hypothesis",
        "",
        question,
        "",
        "## 2. What the evaluator control actually means",
        "",
        "`rsu_capacity_per_vehicle` scales the evaluator's per-vehicle RSU task "
        "capacity; it is an evaluator control, not a physical road claim. The "
        "capacity-squeeze pilot's predeclaration §2 is the controlling statement and "
        "is inherited unchanged.",
        "",
        "## 3. Fixed factors",
        "",
        f"- trace: `{spec.trace_file}` (sha256 `{spec.trace_sha256}`, reviewed allowlist)",
        f"- actor: `{form.actor}`; fleet preset `{MEASURED_FLEET_PRESET}`; evaluator_seed 0",
        f"- max_steps {spec.max_steps}; timeout 7200 s per cell",
        "",
        "## 4. Arms and pairing",
        "",
        f"- baseline arm: cap-{form.baseline_capacity:g}",
        f"- variation arm: cap-{requested:g}",
        f"- pairing: fleet_seed; PROPOSED seeds {{{seeds_text}}} — checked against the "
        "complete registered seed ledger (held-out {10-14} and every used cohort "
        "excluded); the signer fixes the final seeds",
        "",
        "## 5. Endpoints",
        "",
        "Primary: `tos.task.deadline_success.rate`. Secondary: `task.latency.mean_ms`, "
        "`task.offload.rate` (verbatim STA-01 diagnostics, exploratory).",
        "",
        "## 6. Scope and compute budget",
        "",
        f"- cells: {cost.cells} ({2} arms x {len(form.fleet_seeds)} seeds)",
        f"- observed per-cell runtime: {cost.per_cell_seconds:g} s "
        f"({cost.per_cell_seconds_provenance})",
        f"- runtime context: {cost.runtime_context}",
        f"- arithmetic total: {cost.total_seconds:g} s ~= {cost.total_hours:.1f} h serial",
        f"- output budget: {cost.max_total_output_bytes} bytes, halt on failure",
        f"- these figures are {cost.estimate_note}",
        "",
        "## 7. Analysis plan, fixed before results",
        "",
        "The unmodified campaign instrument's predeclared STA-01 comparison per "
        "variation arm against the baseline arm, plus per-arm descriptives; "
        "exploratory, no significance claim; analysis rendered by the committed "
        "`vec_campaign` analysis path only.",
        "",
        "## 8. Prediction and verdict rule",
        "",
        *_prediction_section(prediction, refusal),
        "",
        "## 9. Interpretation limits binding on any output",
        "",
        "- Exploratory `owner_approved_candidate` evidence at most; no confirmatory or "
        "significance claim; deadline success is never physical completion; results "
        "describe one audited policy on one reviewed trace with one fleet preset.",
        "- A prediction is never evidence; the tier-1 record beside this draft stays "
        "`evidence: false` whatever the campaign measures.",
        "",
        "## 10. Citation and standing",
        "",
        "Every number here derives from producer code/data and carries the mandatory "
        f"citation set in `{PRODUCER_CITATION_REFERENCE}`:",
        "",
        *(f"- {key}: `{value}`" for key, value in sorted(PRODUCER_CITATION_BUNDLE.items())),
        "",
        "## 11. Sign-off (EMPTY — a human must complete this)",
        "",
        "| field | value |",
        "|---|---|",
        "| approved_by | |",
        "| approved_role | |",
        "| approved_at_utc | |",
        "| predeclaration_sha256 (of the FINAL bytes) | |",
        "| held_out_authorised | false |",
        "",
        "The campaign instrument refuses placeholder identities and re-hashes this "
        "document at run time; approval binds the exact final bytes. Seeds are a "
        "PROPOSAL: the signer fixes them, and the complete registered seed ledger "
        "must be re-checked at signing.",
        "",
    ]
    return "\n".join(lines)


def write_draft(draft: ComposerDraft, destination_directory: Path) -> tuple[Path, Path]:
    """Write the dated draft pair to an EXPLICIT owner-selected directory.

    The reviewed design (§4) forbids the composer from dirtying the
    repository on its own: generation never commits or approves anything,
    and an owner may later deliberately move a reviewed draft under
    ``docs/evaluation/drafts/`` (`DRAFTS_DIRECTORY`).
    """

    directory = destination_directory
    directory.mkdir(parents=True, exist_ok=True)
    design_path = directory / f"{draft.slug}_design_draft.json"
    predeclaration_path = directory / f"{draft.slug}_predeclaration_draft.md"
    design_path.write_text(
        json.dumps(draft.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    predeclaration_path.write_text(draft.predeclaration_markdown, encoding="utf-8")
    return design_path, predeclaration_path


# --- rendering ---------------------------------------------------------------


def render_prediction_card(outcome: PredictionRecord | PredictionRefusal) -> str:
    """The tier-1 card: banner first, refusals rendered as the gap they name."""

    if isinstance(outcome, PredictionRecord):
        lines = [
            f"**{_PREDICTION_BANNER}**",
            f"scenario: trace `{outcome.scenario.trace}`, capacity "
            f"{outcome.scenario.capacity!r}, actor `{outcome.scenario.actor}`",
            f"regime: `{outcome.regime}`; fit digest `{outcome.fit_digest[:16]}…`",
            "",
        ]
        for metric in outcome.metrics:
            lines.append(
                f"- {metric.metric}: {metric.point!r} "
                f"[{metric.interval_low!r}, {metric.interval_high!r}] "
                f"(seeds {metric.seed_support})"
            )
        for name, reason in sorted(outcome.metrics_unavailable.items()):
            lines.append(f"- {name}: unavailable — {reason}")
        lines.append("")
        lines.append(
            f"producer-derived; citation set: `{PRODUCER_CITATION_REFERENCE}` "
            f"(engine `{PRODUCER_CITATION_BUNDLE['engine_version']}`, author "
            f"{PRODUCER_CITATION_BUNDLE['author']})"
        )
        return "\n".join(lines)
    return "\n".join(
        [
            "**PREDICTION REFUSED — the gap is the answer**",
            f"- code: `{outcome.code}`",
            f"- detail: {outcome.detail}",
            f"- the campaign that would close it: {outcome.closing_campaign}",
            "- escalate: draft that campaign with the composer (tier 2).",
        ]
    )


def render_result_card(analysis_path: Path) -> str:
    """The measurement card — cite-only-admitted-and-committed (reviewed §2).

    The analysis must belong to the admitted experiment registry with its
    pinned design fingerprint, be a completed campaign, and carry no
    NON_ADMITTED marker; every decimal number in the card is then verified
    against the file's own bytes, not trusted.
    """

    try:
        raw = analysis_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WhatifComposerError(
            "ANALYSIS_UNREADABLE", f"analysis {analysis_path.name} could not be read"
        ) from exc
    if "NON_ADMITTED" in raw:
        raise WhatifComposerError(
            "NON_ADMITTED_SOURCE_REFUSED",
            f"{analysis_path.name} carries a NON_ADMITTED marker; such records may be "
            "inventoried but are never rendered as measurement answers",
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WhatifComposerError(
            "ANALYSIS_INVALID", f"analysis {analysis_path.name} is not JSON"
        ) from exc
    if not isinstance(payload, dict) or "primary_descriptives" not in payload:
        raise WhatifComposerError(
            "ANALYSIS_INVALID",
            f"analysis {analysis_path.name} carries no primary descriptives",
        )
    experiment_id = str(payload.get("experiment_id"))
    registered = EXPERIMENT_REGISTRY.get(experiment_id)
    if registered is None:
        raise WhatifComposerError(
            "ANALYSIS_NOT_REGISTERED",
            f"experiment '{experiment_id}' is not in the admitted registry; the "
            "renderer answers only from admitted, registered analyses",
        )
    if str(payload.get("design_fingerprint")) != registered.design_fingerprint:
        raise WhatifComposerError(
            "ANALYSIS_FINGERPRINT_MISMATCH",
            f"{analysis_path.name} does not carry the registered design fingerprint "
            f"for '{experiment_id}'",
        )
    if str(payload.get("campaign_status")) != "completed":
        raise WhatifComposerError(
            "ANALYSIS_NOT_COMPLETED",
            f"{analysis_path.name} is not a completed campaign analysis",
        )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    lines = [
        "**MEASURED — committed campaign analysis**",
        f"source: `{analysis_path.name}` (sha256 `{digest}`)",
        f"experiment: `{experiment_id}` (registered design fingerprint "
        f"`{registered.design_fingerprint[:16]}…`); campaign status: "
        f"`{payload.get('campaign_status')}`; research status: "
        f"`{payload.get('research_status')}`",
        f"citation set: `{PRODUCER_CITATION_REFERENCE}`",
        "",
    ]
    for row in payload.get("primary_descriptives", []) + payload.get("secondary_descriptives", []):
        lines.append(
            f"- {row['arm_label']} {row['metric_key']}: mean {row['mean']!r} "
            f"(min {row['minimum']!r}, max {row['maximum']!r}, "
            f"seeds {len(row['seed_values'])})"
        )
    for comparison in payload.get("comparisons", []):
        difference = comparison.get("mean_paired_difference")
        if difference is not None:
            lines.append(
                f"- {comparison['variation_label']} vs baseline mean paired "
                f"difference: {difference!r}"
            )
    card = "\n".join(lines)
    verify_card_numbers(card, raw)
    return card


def verify_card_numbers(card: str, analysis_text: str) -> None:
    """Every decimal number in the card must appear in the analysis bytes."""

    allowed = set(_CARD_DECIMAL_RE.findall(analysis_text))
    for token in _CARD_DECIMAL_RE.findall(card):
        if token not in allowed:
            raise WhatifComposerError(
                "CARD_NUMBER_NOT_IN_ANALYSIS",
                f"the rendered card carries '{token}', which does not appear in the "
                "cited analysis; cards cite only committed numbers",
            )


def render_honesty_exhibit(
    prediction: PredictionRecord | PredictionRefusal, analysis_path: Path
) -> str:
    """Prediction beside measurement — the platform's honesty exhibit."""

    return "\n".join(
        [
            render_prediction_card(prediction),
            "",
            "---",
            "",
            render_result_card(analysis_path),
        ]
    )

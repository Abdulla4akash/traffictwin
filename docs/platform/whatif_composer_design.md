# Design — What-if scenario composer (platform P-1, tier 2)

**Status: PROPOSED design, `owner_approved_candidate` ceiling. The predict-then-verify
front end: instant predictions from the
[outcome predictor](outcome_predictor_design.md), one-action escalation to a real
predeclared campaign. The agent (template or LLM) DRAFTS AND NEVER APPROVES; no LLM
output is ever evidence.**

## 1. The loop

1. **Compose** — structured form: trace, capacity (or "reduce ×N"), actor, seeds,
   optional comparison arm. Form-first is the baseline; a natural-language box appears
   only when a funded `ANTHROPIC_API_KEY` is present (P-D1) and only *fills the same
   form* — NL never bypasses the structured schema.
2. **Predict** — tier-1 answer rendered immediately, intervals shown, `PREDICTION — NOT
   EVIDENCE` banner. A refusal renders the gap it names.
3. **Escalate** — "Draft the campaign that would verify/measure this": the composer
   emits (a) a campaign design in the house schema (arms, seeds, trace, budgets — the
   `capacity_grid_campaign.py` construction pattern) and (b) a predeclaration document in
   the house format with prediction, band, and verdict rule pre-filled from tier 1 and
   the sign-off table EMPTY.
4. **Sign** — a human. The existing campaign instrument's byte-bound approval (typed
   approver + predeclaration digest, placeholder identities refused) is the gate; the
   composer cannot fill it — enforced by the instrument, not composer politeness.
5. **Execute** — the unmodified `vec_campaign` path: detached launch, admission,
   analysis. The composer only *watches* (receipt polling, read-only).
6. **Report** — a summary card citing ONLY numbers present in the committed campaign
   analysis (each with its source path + digest), stored beside the tier-1 prediction it
   tests. Prediction vs measurement is the platform's honesty exhibit.

## 2. Guardrails (each with a test)

- **Draft-only**: no composer code path calls `execute_campaign`; execution requires the
  human-run launcher. Test asserts the import doesn't exist.
- **Seed protection**: drafted designs may not name held-out {10–14}; the drafter
  refuses, and the instrument's `held_out_authorised` gate backstops it.
- **Cite-only-committed**: the summary renderer takes a committed analysis file, and
  every number in the card must appear in it (renderer verifies, not trusts).
- **No silent envelope escape**: a scenario the predictor refuses can still be drafted —
  that is the point — but the draft carries `prediction_available: false` and the
  refusal, never an invented expectation.
- **Budget honesty**: drafted designs embed measured per-cell cost (59 min `inc`,
  ~4.4 min `ev`-class) so a signer sees the price before signing.

## 3. The LLM socket (dormant until funded)

Claude via the Anthropic API. Scope: parse NL → form fields; propose the
predeclaration's prose sections; explain a refusal. Hard bounds: temperature-0 JSON
extraction against the form schema, output validated by the same pydantic models as the
form, no tool use, no filesystem, transcripts stored with the draft (`drafted_by:
{model, prompt_digest}`) so provenance is inspectable. If the key is absent the
template path produces the identical artifacts minus prose polish — the socket is an
enhancement, never a dependency.

## 4. Placement

New module `whatif_composer.py` + a Streamlit page (see
[dashboard design](dashboard_design.md)); no lead-owned surface touched. Drafts land in
`docs/evaluation/drafts/` named and dated, clearly bannered DRAFT/UNSIGNED — mirroring
how every real predeclaration in this project already started.

## 5. Testing

Unit: schema round-trip, drafter refusals, digest stamping, cite-verification failure
modes. Integration: the worked example — the 3.3× `inc` scenario drafted end-to-end and
diffed against the *actual* signed pilot predeclaration structure; prediction card
rendered against the committed pilot analysis. UI: AppTest per house pattern, a11y
label checks.

## 6. Out of scope for v1

Multi-scenario batch composition; non-capacity knobs (fleet size needs the density-gap
campaign first; fleet mix needs the fleet-composition campaign); auto-refit of the
predictor on completion (manual refit keeps the fit artifact reviewable).

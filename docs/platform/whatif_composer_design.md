# Design — What-if scenario composer (platform P-1, tier 2)

**Status: REVIEWED PROPOSED design, `owner_approved_candidate` ceiling; not implemented.
It depends on the [outcome predictor](outcome_predictor_design.md) completing its
actor-specific envelope and publication-provenance review gates. This is a
predict-then-draft front end, not one-action execution. The template or LLM DRAFTS AND
NEVER APPROVES; no LLM output is ever evidence.**

## 1. The loop

1. **Compose** — structured form: trace, capacity (or "reduce ×N"), actor, fleet preset,
   optional fleet size, proposed fresh seeds, and optional comparison arm. Form-first is
   the baseline; a natural-language box appears
   only when a funded `ANTHROPIC_API_KEY` is present (P-D1) and only *fills the same
   form* — NL never bypasses the structured schema.
2. **Predict** — tier-1 answer rendered immediately, intervals shown, `PREDICTION — NOT
   EVIDENCE` banner. A refusal renders the gap it names.
3. **Draft** — "Draft the campaign that would verify/measure this": the composer
   emits (a) a campaign design in the house schema (arms, seeds, trace, budgets — the
   `capacity_grid_campaign.py` construction pattern) and (b) a predeclaration document in
   the house format with prediction, band, and verdict rule pre-filled from tier 1 and
   the sign-off table EMPTY. A prediction refusal can still produce a measuring draft,
   but unavailable metrics stay unavailable and are never invented.
4. **Sign** — a human. The existing campaign instrument's byte-bound approval (typed
   approver + predeclaration digest, placeholder identities refused) is the gate; the
   composer cannot fill it — enforced by the instrument, not composer politeness.
5. **Execute outside the composer** — after a separate explicit owner decision, a human
   uses the unmodified `vec_campaign` path for launch, admission and analysis. The
   composer cannot launch, spend compute, set approval fields, or turn a draft into an
   authorised campaign. Read-only receipt polling may be added only after execution exists.
6. **Report** — a summary card citing ONLY numbers present in the committed campaign
   analysis (each with its source path + digest), stored beside the tier-1 prediction it
   tests. Prediction vs measurement is the platform's honesty exhibit.

## 2. Guardrails (each with a test)

- **Draft-only**: no composer code path calls `execute_campaign`; execution requires the
  human-run launcher. Test asserts the import doesn't exist.
- **Seed protection**: capacity-study held-out seeds {10–14} are spent and may never be
  reused. The drafter also checks the complete registered seed ledger — pilot, crossover,
  grid, bus and training cohorts — and refuses collisions rather than treating only one
  hard-coded set as protected. A draft proposes fresh seeds but a human fixes them at
  signing; the instrument's `held_out_authorised` field is a backstop, not the whole rule.
- **Cite-only-admitted-and-committed**: the summary renderer takes a repository-relative,
  committed analysis selected through the admitted experiment registry, verifies its Git
  identity and content digest, and proves every displayed number appears in that artifact.
  `NON_ADMITTED`, execution-deviated and private diagnostic records may be inventoried but
  never rendered as measurement answers.
- **No silent envelope escape**: a scenario the predictor refuses can still be drafted —
  that is the point — but the draft carries `prediction_available: false` and the
  refusal, never an invented expectation.
- **Unavailable means unavailable**: partial prediction records propagate
  `metrics_unavailable`; a composer cannot turn a missing p50/tail-ceiling value into zero,
  omit its reason, or substitute a trained-actor parameter for the baseline actor.
- **Budget honesty**: drafted designs embed the observed local per-cell runtime (~59 min
  `inc`, ~4.4 min `ev`-class), hardware/runtime context, cell count and arithmetic total.
  These are planning estimates, not quotas, guarantees, or permission to launch.
- **Citation and standing**: producer-derived prediction, draft and summary artifacts carry
  the mandatory
  [producer/SUMO citation bundle](../producer_citation_requirements.md).
  Protocol-confirmed, post-hoc, exploratory, descriptive and execution-deviated sources
  remain visibly separate; prediction/LLM text remains `evidence: false` even beside an
  admitted measurement.

## 3. The LLM socket (dormant until funded)

Claude via the Anthropic API. Scope: parse NL → form fields; propose the
predeclaration's prose sections; explain a refusal. Hard bounds: temperature-0 JSON
extraction against the form schema, output validated by the same pydantic models as the
form, no tool use, and no filesystem. The API key is read from the environment and never
displayed, logged or stored. Only the bounded scenario fields and owner-entered prose may
leave the machine: no raw/private data, producer repository bytes, campaign files,
credentials, participant material, private paths or identities are sent. Inputs are
screened and size-bounded before any request; returned prose remains untrusted and typed
`evidence: false`.

The draft stores `drafted_by: {provider, model, prompt_template_digest}` plus a digest of
the validated structured input, not an unredacted secret-bearing transcript by default.
Runtime activation requires explicit configuration as well as a funded key; key presence
alone must not silently enable an external transfer. If the key/config is absent, fails,
or is refused, the local template path produces the same structured artifact without prose
polish — the socket is an enhancement, never a dependency.

## 4. Placement

New module `whatif_composer.py` plus a later Streamlit page (see
[dashboard design](dashboard_design.md)); the backend slice does not touch shared
navigation. The library/CLI may write only to an explicit owner-selected draft path after
confirmation. The UI offers a download of the deterministic DRAFT/UNSIGNED artifacts and
does not dirty the repository, workspace or registry during participant tasks. An owner may
later review and deliberately place a draft under `docs/evaluation/drafts/`; generation
does not commit or approve it.

## 5. Testing

Unit: schema round-trip, every predictor refusal/unavailable-metric path, complete
registered-seed collision checks (including spent {10–14}), digest stamping, private-path
screening, citation fields, and cite-verification failure modes. A static/import test proves
the module has no execution launcher dependency. Integration: the worked example — the
3.3× `inc` scenario drafted end-to-end and structurally compared with the actual signed
pilot predeclaration; a summary card is rendered only from the committed admitted analysis.
External-API tests use an injected fake and assert no secret/private field crosses the
boundary. UI AppTests belong to the dashboard slice and include a11y labels and a
no-repository-write assertion.

## 6. Out of scope for v1

Multi-scenario batch composition; non-capacity knobs (fleet size needs the density-gap
campaign first; fleet mix needs the fleet-composition campaign); auto-refit of the
predictor on completion (manual refit keeps the fit artifact reviewable).

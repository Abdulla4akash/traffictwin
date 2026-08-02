# Design — What-if scenario composer (platform P-1, tier 2)

**Status: IMPLEMENTED. Phase 142 delivered the reviewed form-first composer and Phase 170
activated bounded DeepSeek natural-language form extraction after the owner supplied a funded
key. Maximum policy ceiling: `owner_approved_candidate`. This remains a predict-then-draft front
end, not one-action execution. The template or LLM DRAFTS AND NEVER APPROVES; no LLM output is
ever evidence.**

## 1. The loop

1. **Compose** — structured form: trace, capacity (or "reduce ×N"), actor, fleet preset,
   optional fleet size, proposed fresh seeds, and optional comparison arm. Form-first is
   the baseline. The optional natural-language box requires a funded `DEEPSEEK_API_KEY`
   plus visible per-request consent and only *fills the same form* — NL never bypasses
   the structured schema.
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

## 3. The DeepSeek socket (implemented in Phase 170)

The adapter uses DeepSeek's official OpenAI-compatible `POST /chat/completions` JSON-output
interface with `deepseek-v4-flash`, thinking disabled, temperature zero, a 256-token output cap and
a 20-second timeout. It performs one task only: bounded natural-language → `ComposerForm`. The
unchanged local outcome predictor calculates the prediction after the returned form passes strict
Pydantic validation. DeepSeek cannot supply predicted values, evidence, approval or execution.

The user must tick a visible consent control for each request. Key presence alone never sends
anything. Input is trimmed, limited to 1,000 characters and screened before transport for private
paths, credentials, secret-like values, raw BODS material, participant material and identities.
Only the owner-entered scenario text and a fixed form-extraction instruction leave the machine; no
repository file, evidence artifact, campaign record or fit data is included. The API key is read
from the process environment, placed only in the authorization header and never displayed, logged,
hashed into an artifact or placed in request content.

The response must contain exactly one cleanly finished choice with non-empty JSON content. The
existing strict form refuses extra keys, invalid dimensions and inconsistent capacity expressions;
an additional allowlist pins trace, actor and fleet. The translation receipt stores provider/model,
prompt/input/response digests and token counts, never the prose transcript. It is structurally
`evidence: false`, `approval: false` and `execution: false`. The resulting draft records those
digests in `drafted_by` and retains an empty sign-off.

Provider authentication, billing, rate, timeout, truncation, empty-content, malformed-response,
private-input and schema failures are typed refusals. The local structured form remains available
after every refusal. The official references are the
[DeepSeek JSON-output guide](https://api-docs.deepseek.com/guides/json_mode/) and
[chat-completions API](https://api-docs.deepseek.com/api/create-chat-completion/).

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
boundary. They cover explicit consent, configuration status, request shape, response validation,
allowlists, receipt binding and adversarial inputs. UI AppTests pin the visible consent boundary,
a11y labels and the no-repository-write invariant. Phase 170 also completed one minimal live
connectivity check using owner-entered scenario prose only; it returned the validated `inc` / 0.75
form and created no prediction evidence, approval, execution or repository artifact.

## 6. Out of scope for v1

Multi-scenario batch composition; non-capacity knobs (fleet size needs the density-gap
campaign first; fleet mix needs the fleet-composition campaign); auto-refit of the
predictor on completion (manual refit keeps the fit artifact reviewable).

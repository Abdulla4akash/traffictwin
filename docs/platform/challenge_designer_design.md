# Challenge Designer — deterministic candidate what-if scenarios (V1)

Status: implemented (additive route `challenge-designer`, Platform group,
after What-If Challenge). The Challenge Designer answers one bounded
product question: *"What scenario should I test next if I want to expose
meaningful differences between competing strategies rather than
producing an obvious result?"* It complements — and never duplicates —
the two existing challenge capabilities:

* the **challenge seed library** (`ui/portfolio_explorer.py`, seven
  curated `ChallengeSeedDefinition`s bridged to Studio by
  `ui/challenge_whatif_bridge.py`), and
* the **What-If Challenge planner** (`analyst/challenge.py`), which
  converts a deterministic recommendation into a single controlled
  comparison plan.

The Designer generates *candidate* scenarios from the registered
capability surface itself, in three modes, with deterministic validation
deciding every status. Candidates are design proposals, never evidence.

## 1. Architecture

```
registered capability inventory (WHATIF_CONTROL_SPEC + SyntheticPolicyProfile)
        ↓ design_candidates()            — deterministic templates, 3 modes
        ↓ [optional] propose_candidates_with_llm()  — LLM may PROPOSE only
        ↓ validate_external_proposal()   — deterministic validation DECIDES
ChallengeCandidateSet (≤ 3 distinct ChallengeScenarioProposal)
        ↓ human selects one
        ↓ candidate_to_whatif_draft()    — pure; existing bridge draft contract
ChallengeWhatIfDraft → existing pending-draft handoff → Studio review → user generates
```

No LLM proposal becomes a candidate without passing the same validation
as a deterministic template, and no candidate becomes a What-If pair
without the user applying the draft in Studio and generating explicitly.

## 2. Challenge families (representable only)

`TASK_PRESSURE`, `TASK_MIX_SHIFT`, `TRAFFIC_DEMAND_PRESSURE`,
`INCIDENT_PRESSURE` (the honest representable counterpart of demand
concentration: pressure at the registered incident location),
`INFRASTRUCTURE_CAPACITY_PRESSURE`, `MODEL_INFRASTRUCTURE_INTERACTION`.

Families the prompt vocabulary suggests but the contract cannot express
are **not** exposed as generators: placement/load management, admission,
queue capacity, fleet capability mix and task ordering are refusal
vocabulary (`HYPOTHESIS_NOT_REPRESENTABLE` with the registered
limitation text), never approximated with a different parameter.

## 3. Modes

* **MAKE_HARDER** — one bounded, single-mechanism pressure step per
  candidate (task arrival, traffic demand, service capacity). Never
  "maximise everything": magnitudes take `HARDER_STEP_FRACTION` (0.25)
  of the remaining headroom toward a bound and never reach it. The
  fraction is a reviewable product design constant, not a scientific
  threshold; every value is editable in Studio.
* **TEST_HYPOTHESIS** — bounded hypothesis vocabulary plus an ordered
  free-text phrase matcher (specific unrepresentable mechanisms are
  recognised before generic pressure words). Unmatched text is a typed
  `INSUFFICIENT_CONTEXT` with the vocabulary listed.
* **SURPRISE_ME** — a fixed, deterministic mechanism-diverse trio
  (interaction, localised incident, task-mix shift).

An optional prior Next Investigation category only **reorders** the
candidate families (Section 14 of the task direction); it never adds,
removes or upgrades a candidate. An `INSUFFICIENT_EVIDENCE` context adds
the note that candidates *distinguish competing explanations* and prove
none.

## 4. Validation pipeline (deterministic; the LLM cannot override it)

1. schema (closed `ExternalChallengeProposal`, extra fields refused)
2. supported-field check (`SUPPORTED_CANDIDATE_FIELDS` only;
   `LLM_UNKNOWN_PARAMETER` otherwise)
3. bounds (`is_value_representable`; registered profiles only;
   `LLM_BOUNDS_VIOLATION`)
4. cross-field consistency (task-mix shares sum to 1; incident values
   require an enabled incident)
5. winner-claim guard (`LLM_WINNER_CLAIM_REFUSED`) and evidence/number
   guard (`LLM_EVIDENCE_FABRICATED`)
6. structural triviality (bound-saturated values, broad same-direction
   escalation → `VALID_BUT_TRIVIAL`)
7. novelty (mechanism fingerprint over family + changed fields +
   baseline; duplicates collapse, template look-alikes →
   `VALID_BUT_REDUNDANT`)

Statuses: `VALID_CHALLENGE`, `VALID_BUT_TRIVIAL`, `VALID_BUT_REDUNDANT`,
`PARTIALLY_REPRESENTABLE` (unsupported ideas shown separately, never
transferred), plus refusals (`UNSUPPORTED`-class typed errors,
`INSUFFICIENT_CONTEXT`).

## 5. Triviality and prediction reuse

Outcome-level triviality is only assessable **after execution** — by the
existing rule R3 (scenario-triviality) over winner-map evidence — so the
Designer applies structural checks at design time and says so
(`triviality_basis`). TrafficTwin has no deterministic predictor for
unexecuted scenarios, so every candidate carries
`prediction_status = PREDICTION_UNAVAILABLE` with
`OUTSIDE_SUPPORTED_ENVELOPE` named; LLM intuition is never used as a
prediction.

## 6. LLM boundary

The optional DeepSeek proposer receives only the compact capability
schema (`CandidateProposalRequest`: bounds, registered profiles, the
baseline values, the known-unrepresentable list, the instruction). The
payload is screened by the shared `screen_prose_payload` privacy gate
and contains no credentials, paths, BODS bytes or repository content.
Responses parse through the shared transport helpers and every proposal
passes the full deterministic validation above. Without a key the
proposer raises `LLM_NOT_CONFIGURED` and the deterministic modes remain
the complete product.

## 7. Evidence boundary

Candidates derived from the synthetic baseline carry the fixed standing
`synthetic what-if proposal (derived scenario; not an observation)`.
A scenario derived from historical or live-transit evidence would be a
what-if proposal too — derivation never inherits observation standing.
No E3/research execution path exists in this module (source-scan
pinned); `execution_authority`, `approval`, `llm_evidence` and
`creates_new_evidence` are type-level `False`.

## 8. Known limitations / deferred

* No placement, admission, queue-capacity, fleet-tier or ordering
  dimension exists in the What-If contract; the matching hypotheses are
  honest refusals until such a dimension is registered.
* The LLM proposer is API-level in V1; the page renders deterministic
  candidates only (LLM UI wiring deferred).
* Guided Demo integration ("create your own challenge") deferred.

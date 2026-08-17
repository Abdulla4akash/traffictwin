# Recommendation Agent — bounded decision support with a candidate ledger (V1)

Status: implemented (additive route `recommendation-agent`, Platform
group, beside What-If Challenge). Fourth stage of the bounded agentic
chain: Analyst → Next Investigation → What-If Challenge → **Recommendation
Agent**. See `recommendation_agent_design.md` for the Next Investigation
selector this layer consumes.

## 1. Question and architecture

The agent answers one narrow decision-support question: *given the
selected TrafficTwin evidence, what should the analyst investigate next —
the model/policy, the infrastructure/resource configuration, both,
nothing, or is there insufficient evidence to recommend anything?*

```
existing evidence
      ↓ existing deterministic services (bundles, metrics, lenses, rules)
AnalystEvidencePacket → AnalystClassification → RecommendationEvidencePacket
      ↓ pure deterministic decision engine (no thresholds, no new metrics)
RecommendationDecision  (direction + ranked candidate ledger + retraining gate)
      ↓ optional, consent-gated, per request
DeepSeek prose rendering (explains; cannot decide)
      ↓
human decides what to do
```

The forbidden architecture (raw CSV → LLM → "retrain MAPPO") does not
exist anywhere in this path; ADR-005 order is preserved unchanged. The
three chain inputs are fingerprint-bound: a mismatched pairing is a
typed `PROVENANCE_INCOMPLETE` refusal, never a silent re-derivation.

## 2. Direction vocabulary and mapping

`RecommendationDirection` is the five-way answer required by the product
question, derived from the merged Next Investigation category — never
re-decided from raw evidence:

| Direction | Underlying category |
|---|---|
| `MODEL_INVESTIGATION` | `INVESTIGATE_MODEL_OR_TRAINING` |
| `INFRASTRUCTURE_INVESTIGATION` | `INVESTIGATE_RSU_LOAD_MANAGEMENT`, `INVESTIGATE_INFRASTRUCTURE_CAPACITY` |
| `JOINT_INVESTIGATION` | `MIXED_INVESTIGATION` |
| `NO_INTERVENTION_SIGNAL` | `NO_ACTIONABLE_PROBLEM_DETECTED` |
| `INSUFFICIENT_EVIDENCE` | `INSUFFICIENT_EVIDENCE`, and `INVESTIGATE_SCENARIO_OR_CONTROL` (a material candidate exists but the sides are indistinguishable; the supported next step is a controlled comparison) |

## 3. Candidate roster and ledger

A fixed nine-candidate roster is assessed on every decision; nothing is
hidden when excluded. Eligibility restates existing rule statuses only:

| Candidate | Track | Deterministic basis |
|---|---|---|
| `INVESTIGATE_RSU_LOAD_MANAGEMENT` | infrastructure | R4 triggered |
| `INVESTIGATE_CAPACITY_OR_SERVICE_PROVISION` | infrastructure | R2 triggered |
| `INSPECT_ADMISSION_OR_REJECTION_EVIDENCE` | infrastructure | never evaluable from run bundles — admission/rejection lifecycle counts exist only in admitted Resource Strategy studies; the ledger says so and points there |
| `INSPECT_POLICY_DECISION_DISTRIBUTION` | model | R1 triggered |
| `COMPARE_POLICY_WITH_BASELINES` | model | a model-side rule triggered (registered profiles are the comparators) |
| `INVESTIGATE_TRAINING_CONDITIONS` | model | R5 triggered |
| `INVESTIGATE_RETRAINING` | model | strict typed gate (below); always ranked last |
| `RUN_CONTROLLED_SCENARIO_COMPARISON` | scenario | a side-less rule (R3/R6/R7/R8) triggered, readiness gate passed |
| `NO_INTERVENTION` | none | no rule triggered with the primary pair evaluated |

Statuses are typed (`RECOMMENDED` / `SUPPORTED_ALTERNATIVE` /
`ELIGIBLE_LAST_RESORT` / `NOT_RECOMMENDED` / `NOT_EVALUABLE`), and every
excluded candidate carries typed exclusion codes in the Decision Safety
presentation style (`ranked_candidate_ids` + `exclusions`), plus its
required and unavailable evidence. Decision Safety's `assess()` itself is
deliberately not called: its `DecisionOption` contract requires
metric-valued, policy-bound options, and investigation candidates carry
no primary metric value — fabricating one is forbidden.

Ranking is threshold-free and order-independent: primary-track eligible
candidates first in fixed roster order (R4-before-R2 restates the
recorded load-management-before-capacity direction; inspection before
comparison before training on the model side), then other eligible
tracks in roster order, retraining always last. Under
`JOINT_INVESTIGATION` the between-track ordering is declared to carry no
evidential weight (a pinned limitation line).

## 4. The retraining gate

`INVESTIGATE_RETRAINING` is a last resort behind six typed requirements,
each restating existing facts with its evidence line:

1. `readiness_gate_passed` — R0/overall readiness did not refuse.
2. `model_side_behaviour_implicated` — R1 or R5 triggered ("a poor
   outcome alone never implicates the model").
3. `infrastructure_explanation_excluded` — R2 and R4 both evaluated and
   did not trigger (saturation alone therefore never yields retraining).
4. `compatible_policy_comparator_present` — a compatible comparison in
   which a `policy.*` seed parameter changed; the changed entries name
   both actor identities.
5. `policy_identity_isolated` — no non-`policy.*` parameter differs
   between the arms, so the comparison is not confounded by scenario,
   workload, demand or infrastructure changes.
6. `evidence_standing_known` — no `UNKNOWN` standing.

Even a fully satisfied gate yields `ELIGIBLE_LAST_RESORT`, ranked last,
with a pinned note that this is an investigation proposal, not a claim
that retraining will help. Unsatisfied requirements are the "why not
retrain?" answer, verbatim.

## 5. Bounded questions

`decision_questions.py` maps a fixed roster of analyst questions ("What
should I investigate next?", "Should I retrain the model?", "Why aren't
you recommending retraining?", "Does this look like an infrastructure
problem?", "Does this look like a model/policy problem?", "Would load
redistribution be worth testing?", "What evidence is missing before we
decide?") onto deterministic queries over the decision. Free text is
matched by an ordered keyword table; an unmatched question is a typed
`UNRECOGNISED_QUESTION` refusal listing the supported questions. This is
not a chatbot, and free text has no path to the LLM.

## 6. LLM boundary

Same shared DeepSeek socket and guard vocabulary as the rest of the
chain (`analyst/prose.py` + `guard_bounded_investigation_output`). The
request is the canonical JSON of `DecisionProseRequest`, built only from
the decision; the response must be exactly `{decision_explanation,
why_not_explanation, evidence_gap_explanation}`. Additional guards:
`LLM_DECISION_MUTATED` (prose names a direction the engine did not
choose) and `LLM_CANDIDATE_PROMOTED` (prose presents an excluded
candidate inside the decision explanation; excluded candidates are
discussable only in the why-not field, and not-evaluable ones also in
the evidence-gap field). `DecisionProse` has no direction, ranking,
status or numeric field, so the deterministic result is structurally
immutable; every refusal falls back to the complete deterministic
presentation, and the page is fully functional with no API key.

## 7. Prepare a What-If

The decision page reuses the merged challenge planner
(`plan_challenge`) for the underlying recommendation and presents its
readiness honestly: representable challenges hand off to the What-If
Challenge page, whose existing bounded-input → `build_challenge_prefill`
→ pending-draft → Studio apply-once contract stays the sole path to a
prefill; `NOT_REPRESENTABLE` (for example RSU load management, which has
no registered What-If dimension) is stated, never papered over. Nothing
is executed from any of these surfaces.

## 8. Non-goals and limitations

Not a chatbot, not an autonomous controller, not an experiment runner,
not a retrainer, not an autoscaler, not an evidence admission system.
It launches no SUMO/VEC/E3/campaign work, modifies no model, RSU,
road, signal, or Kubernetes object, and contacts no live provider.
Type-level pins: `advisory_only: True`, `creates_new_evidence: False`,
`execution_authority: False`, `causal_claim_supported: False`, and per
candidate `executable: False`.

- The retraining gate can pass only on a policy-identity-isolated
  compatible comparison; on the shipped demo bundles it never passes
  (their comparisons change workload/demand alongside the policy), and
  the confounds are named verbatim in the refusal.
- Admission/placement candidates are honest pointers: run bundles carry
  no admission/rejection or placement metrics, so those investigations
  are `NOT_EVALUABLE` from this evidence path by construction.
- The five-way direction is a presentation vocabulary over the merged
  seven-way selector; it never re-decides the winner.

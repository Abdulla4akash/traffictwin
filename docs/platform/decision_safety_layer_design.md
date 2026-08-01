# Design — Decision-safety layer (post-v1 D-1)

**Status: IMPLEMENTED as a deterministic backend guardrail in Phase 151 and reconciled in Phase
161. Assessments and notices are source/ruleset bound and all carry `recommendation: false`,
`evidence: false` and `causal: false`; there is no ranking, execution or deployment surface. The
current conservative rules are local engineering defaults, not a scientific or policy approval;
future domain thresholds and display order remain owner decisions.
Maximum policy ceiling: `owner_approved_candidate`. This is a guardrail and refusal layer,
not an optimiser, autonomous decision-maker, policy recommendation service or production
control system. Every generated assessment is `evidence: false`.**

## 1. Purpose

Meeting 3 included a decision layer after analytics and prediction. TrafficTwin's central
finding shows why that layer must not simply minimise a familiar metric: mean latency can
improve under degraded capacity while deadline attainment stays flat, actions remain
invariant, and the change occurs within already-failed tasks. The first decision feature
should therefore detect unsafe interpretation and refuse unsupported comparisons, not
select an "optimal" configuration.

## 2. Supported question

Given a digest-pinned prediction, scenario or evidence selection, the layer answers:

> Is there enough compatible, correctly scoped information to present this option as a
> bounded decision-support comparison, and which cautions must accompany it?

It does not answer what an operator should deploy. It does not calculate social value,
safety, equity, emissions or real-world service impact from absent data.

## 3. Inputs

Inputs must be typed outputs from the [outcome predictor](outcome_predictor_design.md),
[experiment evidence matrix](experiment_evidence_matrix_design.md),
[scenario/run registry](scenario_run_registry_design.md), or a committed admitted analysis.
Each input supplies its digest, standing, actor/trace/capacity envelope, support,
uncertainty status, companion metrics, execution deviations and citation bundle.

Free text, arbitrary external URLs, private paths and raw simulator/BODS payloads are not
decision inputs. An LLM cannot originate facts or resolve a refusal.

## 4. Versioned guardrails

Initial deterministic rules:

1. **Envelope rule:** refuse extrapolation, actor/capacity mismatch or incompatible design.
2. **Standing rule:** keep predictions, forecasts, proposed work and non-admitted results
   separate from admitted evidence.
3. **Proxy-inversion rule:** when a headline QoS metric improves, require deadline,
   completion/failure and action-change companions before interpretation.
4. **Support rule:** expose seed/date/cell support and refuse claims whose required support
   is missing.
5. **Uncertainty rule:** distinguish interval unavailable from a zero-width interval and
   retain exact small-sample limits.
6. **Deviation rule:** propagate execution/provenance deviations without downgrading them to
   optional notes.
7. **Causality rule:** refuse causal or individual-experience wording unless a separately
   authorised design supports it; no current input does.
8. **Actionability rule:** never translate a model output into an execution instruction.

Rules are code- and configuration-versioned. Changing a threshold or required companion
metric creates a new ruleset digest and requires owner review.

## 5. Output contract

`DecisionSupportAssessment` contains:

- `status`: `presentable_with_cautions` or `refused`;
- input and ruleset digests;
- compatible option records and exact exclusions;
- required companion metrics and observed support;
- ordered `SafetyNotice` records with machine code and plain-language text;
- `recommendation: false`, `evidence: false`, `causal: false`;
- policy ceiling and citation bundle.

There is no ranking, winning option, automatic default or green/red deployment signal.
The dashboard may render comparisons in a neutral input order or an owner-selected fixed
order, never an inferred preference.

## 6. Required current safety notice

Any view of the confirmed capacity result must state that the lower-capacity arm reduced
mean latency by 8,310.9 ms with bootstrap interval [−9,097.5, −7,524.3] ms across five
same-direction seeds, while the exact two-sided sign-test floor is p=0.0625, deadline
attainment was effectively flat, actions were invariant and the latency change occurred in
already-failed tasks. It must not call that an individual vehicle improvement or a reason to
degrade capacity.

This notice is emitted only when the pinned source/design digests match. Otherwise the
layer refuses rather than reproducing stale headline numbers.

## 7. Typed refusals

At minimum: `INPUT_DIGEST_MISMATCH`, `OUTSIDE_MEASURED_ENVELOPE`,
`ACTOR_CAPACITY_NOT_MEASURED`, `INCOMPATIBLE_EVIDENCE`, `NON_ADMITTED_INPUT`,
`COMPANION_METRIC_MISSING`, `SUPPORT_INSUFFICIENT`, `UNCERTAINTY_UNAVAILABLE`,
`EXECUTION_DEVIATION_UNACKNOWLEDGED`, `CAUSAL_WORDING_FORBIDDEN`,
`RECOMMENDATION_REQUEST_FORBIDDEN` and `PRIVATE_CONTENT_DETECTED`.

## 8. Verification and acceptance

Decision-table tests cover every rule and pairwise interactions. Adversarial tests attempt
to rank options, label lower latency as better, suppress flat deadline/action invariance,
promote Sparse-64, treat p=0.0625 as conventionally significant, extrapolate outside an
actor's capacity range, or pass LLM prose as evidence. Golden wording tests bind notices to
source digests.

Acceptance requires deterministic assessments, complete provenance, no mutable approval or
execution surface, correct refusals under missing companion metrics and accessible notices
that do not rely on colour alone.

## 9. Owner decisions and stop conditions

The owner must approve the ruleset, fixed display order, minimum companion metrics and any
future domain-specific constraints. Stop if a requested feature ranks interventions,
automatically executes one, claims real-world safety/benefit, uses participant data, or
requires an ethical/policy judgement that has not been supplied by the owner.

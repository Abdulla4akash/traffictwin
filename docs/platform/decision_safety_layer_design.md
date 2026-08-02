# Design — Decision-safety layer (post-v1 D-1)

**Status: IMPLEMENTED as Decision-Safety Ruleset v2 in Phase 167, superseding the blanket
presentation prohibitions in the Phase-151 v1 implementation. V2 supports broad bounded decision
use: compatible in-envelope ranking, metric-specific winners, evidence-backed advisory
recommendations, owner-preselected defaults, reviewable instruction drafts and design-supported
scoped cause statements. It creates no evidence and has no execution authority. Maximum policy
ceiling: `owner_approved_candidate`; this is not supervisor, ethics, publication, production or
real-road approval.**

## 1. Purpose

TrafficTwin's capacity result shows why a decision layer must distinguish a metric-specific result
from an overall-service result: mean latency can improve under degraded capacity while deadline
attainment stays flat, actions remain invariant and the change occurs inside already-failed tasks.
That does not make all ranking or advice invalid. It means useful ranking must be scoped to a
compatible, predeclared endpoint and an overall-service claim must carry the service endpoint and
its companion metrics.

## 2. Supported decisions

Given a digest-pinned study policy and typed options, v2 may produce:

- deterministic rankings and tied winners for one declared metric;
- an evidence-backed advisory within that measured comparison;
- an owner-preselected default, if it remains eligible;
- scoped cause status: `none`, `simulation_internal` or `real_world`, bounded by a supporting
  admitted design and policy; and
- reviewable execution-instruction drafts that are explicitly non-executable and carry no
  execution authority.

The layer never silently expands an endpoint, actor, trace, capacity, evidence standing or cause
scope. It does not execute a draft, create evidence, grant approval or make absent safety, equity,
emissions or real-service outcomes true.

## 3. Inputs

`DecisionSafetyPolicy` is a study-specific, owner-approved contract containing its source and
comparison-contract digests, predeclared support threshold, required overall-service companions,
enabled decision surfaces, maximum cause scope, optional owner default and fixed display order.
Its cause-design allowlist binds each reviewed design digest to its greatest supported scope. There
is no universal scientific support threshold.

`DecisionOption` binds its source and comparison digests, compatibility group, standing, actor,
trace, capacity, envelope, budget match, predeclaration, support, uncertainty, metric definition,
metric value/direction, companion fields, deviations, optional cause-design digest and optional
instruction draft. Free-form paths, raw BODS/simulator payloads and secrets are not inputs.

## 4. Versioned guardrails

1. **Measured-envelope rule:** exclude extrapolation and actor/capacity cells not measured for the
   exact actor/trace contract.
2. **Compatibility and standing rule:** refuse mismatched comparison digests, compatibility groups
   or evidence standings. `NON_ADMITTED` material remains descriptive context, not a decision input.
3. **Matched predeclaration rule:** ranking requires every included cell to be predeclared and to
   use the matched budget.
4. **Metric/service rule:** a winner is a winner for the declared metric only. An overall-service
   claim additionally requires a service endpoint and all policy-declared companions.
5. **Support and uncertainty rule:** every included option meets the policy's predeclared support
   count and carries a non-unavailable interval status. Missing is never zero.
6. **Deviation rule:** every execution/provenance deviation remains visible; an undisclosed
   deviation refuses the assessment.
7. **Scoped-cause rule:** cause wording requires an admitted design digest present in the policy's
   cause-design allowlist at the exact requested scope, and a policy ceiling at least that broad.
8. **Bounded-actionability rule:** advice may be emitted when enabled and evidence-backed; an owner
   default may be carried; instruction drafts remain `executable: false` and
   `execution_authority: false`.

Any policy or rule change changes the deterministic ruleset digest.

## 5. Output contract

`DecisionSupportAssessment` includes exact policy/ruleset/input digests, display order, compatible
and excluded option ids, notices, optional ranking and tied winners, advisory text, owner default,
and instruction drafts. Its semantics are explicit:

- `recommendation` may be true only for a compliant evidence-backed advisory;
- `evidence_backed` says whether the inputs are admitted evidence;
- `creates_new_evidence` is always false;
- `causal_scope` reports the greatest supported scope and defaults to `none`; and
- `execution_authority` is always false.

This replaces v1's ambiguous blanket `evidence: false`: the assessment may be backed by evidence,
but generating it never creates new evidence.

The fixed order is: standing/scope/deviation; eligibility; metric-specific result; uncertainty and
support; companion metrics; ranking/advice/default/drafts; citations.

## 6. Required current safety notice

Any view of the confirmed capacity result states exactly that lowering RSU capacity from 2.5 to
0.75 reduced mean latency by 8,310.9 ms; the bootstrap interval is
[−9,097.5, −7,524.3] ms; all five held-out seeds moved in the same direction; the exact two-sided
sign-test floor is p=0.0625; conventional statistical significance is not claimed; deadline
attainment remained effectively flat; actions/offloading decisions were invariant; and the change
occurred within already-failed tasks rather than being an improvement experienced by an individual
vehicle. It is labelled metric-specific, not an overall-service ranking.

The notice renders only while its reviewed source digest matches.

## 7. Typed refusals

The implementation includes `INPUT_DIGEST_MISMATCH`, `OUTSIDE_MEASURED_ENVELOPE`,
`ACTOR_CAPACITY_NOT_MEASURED`, `INCOMPATIBLE_COMPARISON_CONTRACT`, `INCOMPATIBLE_EVIDENCE`,
`NON_ADMITTED_INPUT`, `RANKING_NOT_PREDECLARED_OR_MATCHED`, `RANKING_NOT_ALLOWED`,
`OVERALL_SERVICE_SUPPORT_MISSING`, `SUPPORT_INSUFFICIENT`, `UNCERTAINTY_UNAVAILABLE`,
`EXECUTION_DEVIATION_UNACKNOWLEDGED`, `CAUSAL_SCOPE_UNSUPPORTED`,
`ADVISORY_RECOMMENDATION_UNSUPPORTED`, `OWNER_DEFAULT_UNAVAILABLE`,
`EXECUTION_DRAFT_NOT_ALLOWED`, `UNSUPPORTED_GENERALISATION` and `PRIVATE_CONTENT_DETECTED`.

## 8. Verification and acceptance

Decision-table and adversarial tests cover permitted ranking/advice/default/draft paths, ties,
metric-versus-service semantics, digest/standing/group incompatibility, measured-envelope escapes,
study-specific support and mandatory uncertainty, deviations, cause-scope escalation, private
content, unsupported global superlatives and the source-digest-bound capacity notice.

Acceptance requires deterministic results, exact provenance, no standing promotion, no hidden
deviation, no execution surface and no generated evidence or authority.

## 9. Owner decisions and remaining boundaries

On 2 August 2026 the owner approved Ruleset v2 and selected maximum bounded coverage. The ruleset,
required companion contract and display order above are selected. Thresholds are study-specific and
must be frozen in each input policy rather than imposed universally. A future real-world cause
statement still needs an admitted design that actually supports that scope; an instruction draft
still needs a separate execution surface with its own valid authority before anything can happen.

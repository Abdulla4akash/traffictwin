# Design — Mechanism and policy observatory (post-v1 O-1)

**Status: IMPLEMENTED as a read-only backend bundle in Phase 150, source-pinned in Phase 161 and
updated with the owner's public-view and Sparse-64 admission decisions in Phase 166.
Delivered contracts include `StudyCard`, `MechanismCard`, `PolicyContractCard`, action-invariance,
`CoherenceCheck`, complete source bindings and deterministic templates. Reviewed source digests
must match before fixed scientific values render. No UI or scientific recalculation is included;
The public display contains every citation-complete admitted study, while the earlier non-admitted
Sparse-64 return remains in an explicit appendix.
Maximum policy ceiling: `owner_approved_candidate`. The observatory is read-only and
evidence-bound. It does not diagnose causality, recommend a policy, execute an experiment,
or upgrade any result's standing.**

## 1. Purpose

Meeting 3 asked what the actor observes, why capacity was excluded, whether the policy
changes, what mechanism explains the counter-intuitive result and how many experiments
support it. The repository contains those answers across protocol-confirmed analyses,
post-hoc mechanism work and descriptive records. This slice makes their separation and
relationships inspectable in one place.

The headline remains narrow: standard VEC QoS metrics can improve when the system is
degraded. Capacity is the experimental instrument, not the whole contribution. The
observatory must make the accompanying limits at least as visible as the latency delta.

## 2. Required views

### 2.1 Observation and action contract

Show, per compatible actor checkpoint:

- observation variables, dimensions and whether RSU capacity is present;
- action space, reward definition and checkpoint/design fingerprint;
- measured capacity envelope by trace/actor;
- compatibility/refusal status for any comparison.

This view answers what information a policy could condition on; it does not infer what the
network internally learned.

### 2.2 Action-invariance view

Show paired action/offloading summaries across capacity arms with support and equality
checks. The confirmed held-out result has invariant actions across arms; that fact must sit
beside the latency comparison rather than in a footnote. Missing action logs report
`unavailable`, not "unchanged".

### 2.3 Mechanism view

Expose the capacity-scaled latency ceiling analysis, failed-task composition, tail
distribution and persistent-minority concentration as separate cards. Each card carries
its evidence role (`protocol_confirmed`, `post_hoc`, `exploratory` or `descriptive`), source
digests, support and limitations. A visual relationship between cards is allowed; a causal
arrow is not.

### 2.4 Outcome-coherence view

Display latency, deadline attainment, completion, failures and action changes together.
For the confirmed five-seed capacity study, the view must preserve all of these facts:

- mean latency changed by −8,310.9 ms with bootstrap interval
  [−9,097.5, −7,524.3] ms;
- all five paired seeds moved in that direction;
- the exact two-sided sign-test floor is p=0.0625, so conventional significance is not
  claimed;
- deadline attainment was effectively flat; and
- the reduction occurred inside already-failed tasks, not as an improvement experienced by
  an individual vehicle.

These values are display regression fixtures only when their committed source digests and
design fingerprint match. They must not be copied into a generic fallback response.

## 3. Architecture and contracts

The observatory consumes committed, digest-pinned safe analysis records through an adapter
layer. It does not recalculate scientific endpoints in the UI. A builder emits an immutable
`ObservatoryBundle` containing:

- `StudyCard` records with design, trace, actor, capacity, seed and standing;
- `MechanismCard` records with statistic, interval/support, role and limitations;
- `PolicyContractCard` records with observation/action/reward/checkpoint metadata;
- `CoherenceCheck` records stating whether required companion metrics are present;
- a citation bundle meeting
  [producer citation requirements](../producer_citation_requirements.md).

The renderer accepts only a validated bundle digest. Any natural-language summary is
template-based initially and can cite only fields in the bundle.

## 4. Evidence separation

- Protocol-confirmed results are never pooled with post-hoc or exploratory results.
- The earlier 147-repeat Sparse-64 result is `NON_ADMITTED` and may appear only in a separately
  labelled descriptive appendix. The clean rerun is owner-admitted descriptive evidence with its
  execution deviation displayed and remains incompatible with and unpooled from corridor VEC.
- Execution deviations remain first-class warnings.
- "Supported", "not supported", "not tested" and "incompatible" are distinct states.
- No card uses `ground_truth`, `causal`, `validated_policy`, `optimal` or
  `production_ready` language.
- Current written producer permission is acknowledged only through the repository's
  citation requirements; private permission text is never requested or displayed.

## 5. Query and refusal behaviour

Filters may select trace, actor, capacity, metric and evidence role, but the service refuses
filters that would silently combine incompatible checkpoints or standings. A comparison
returns the exact included records plus excluded-record reasons.

Typed refusals include `SOURCE_DIGEST_MISMATCH`, `DESIGN_FINGERPRINT_MISMATCH`,
`INCOMPATIBLE_ACTORS`, `EVIDENCE_ROLE_MIXED`, `REQUIRED_COMPANION_METRIC_MISSING`,
`ACTION_LOG_UNAVAILABLE`, `NON_ADMITTED_PROMOTION`, `CITATION_BUNDLE_MISSING` and
`PRIVATE_CONTENT_DETECTED`.

## 6. Verification and acceptance

Golden tests pin the five-seed headline card, sign-test wording, action-invariance companion
card and flat-deadline warning to their source digests. Negative tests attempt to promote
Sparse-64, omit execution deviations, mix post-hoc and confirmed roles, compare incompatible
actors, fabricate significance from unanimous five-seed direction, or render latency
without failure/deadline context.

Acceptance requires a complete provenance walk from every displayed number, zero scientific
formula duplication in the renderer, correct citations, explicit support/exclusions, and
accessible presentation of role and refusal information without relying on colour alone.

## 7. Deliverables

One backend bundle builder, schema, deterministic templates, unit/golden tests and an
optional read-only dashboard page after the v1 dashboard is complete. No source analysis,
campaign code, actor, evidence record or manuscript is modified by this slice.

## 8. Owner decisions and stop conditions

On 2 August 2026 the owner selected maximum public coverage for citation-complete admitted studies,
kept the `NON_ADMITTED` appendix explicit, and fixed this order: standing/scope/deviation; primary
endpoint; uncertainty; companion metrics; mechanisms; limitations; citations. The bundle stores
and digest-binds that order. Stop if a requested view needs new
post-hoc computation, unpublished private artifacts, stronger permission wording, new
experiment execution or a recommendation about operational policy.

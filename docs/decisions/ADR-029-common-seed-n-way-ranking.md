# ADR-029 — Common-Seed N-Way Policy Ranking

Status: accepted and implemented
Date: 20 July 2026
Capability: `STA-02`

## Context

TrafficTwin's version 1.0 winner map already ranks policy means independently inside every
scenario-seed family and exposes deterministic ties and regret. It is intentionally descriptive:
it can accept unequal observation counts, does not audit a predeclared common-seed design, and
does not quantify uncertainty. `STA-02` must add N-way uncertainty and missingness without creating
a second, contradictory ranking definition or ranking incompatible evidence.

The registered experiment protocol is factorial over scenario conditions, policies, and common
random seeds. Comparing scenario conditions and policies in one undifferentiated league table
would conflate intervention and policy effects. N-way policy ranking therefore remains independent
inside each declared scenario family, matching the existing winner-map boundary.

## Decision

TrafficTwin implements `NWayRankingStudy` schema and method version 1.0 as an extension of the
existing `WinnerMapReport`. A strict `NWayRankingConfig` predeclares one experiment, one or more
scenario-family identifiers, at least two policy/algorithm labels, one checkpoint, one finite
scalar metric, objective direction, common random-seed set, absolute tie tolerance, confidence
level, bootstrap repetitions, and deterministic resampling seed.

For each scenario family, the exact pairing unit is `random_seed`. One complete N-way observation
contains exactly one compatible metric endpoint for every selected policy. Missing, unavailable,
partial, non-finite, duplicate, unplanned, context-invalid, provenance-incomplete, or
semantic-contract-incomplete endpoints never become zero. A random seed with any absent endpoint
is reported as incomplete and does not enter any policy's mean. A seed with cross-policy
compatibility differences is explicitly excluded. Complete seeds must also share one common
metric/environment/semantic signature across the family; TrafficTwin does not select a convenient
subgroup.

The descriptive ranking is delegated to the existing winner-map implementation using only the
admitted complete cohort. It therefore retains the existing objective-aware ordering, standard
competition ranks, winners, and original-unit regret. Two policy means tie when their absolute
difference is no greater than the predeclared `tie_tolerance` (default `1e-12`). This numerical
tie is not an equivalence claim, and overlapping confidence intervals never create a tie.

At least three complete compatible common seeds are required for uncertainty. With adequate
support, version 1.0 performs a joint paired percentile bootstrap:

1. resample complete random-seed rows with replacement;
2. retain all selected policies together in every resampled row;
3. calculate each policy mean and the ordinary winner-map rank using the predeclared objective and
   tie tolerance;
4. publish linear-interpolated percentile intervals for policy means, the empirical frequency of
   every rank, the frequency of top rank including ties, and percentile rank bounds.

The default is 10,000 repetitions, with the same 1,000–100,000 bound as `STA-01`. Each scenario
family receives a deterministic seed derived from the configured seed and family identifier, so
input order and the presence of another family cannot change its result. The procedure uses a
local random generator and never ambient random state.

No null-hypothesis test is performed by this ranking service. Consequently its
multiple-comparison policy is explicitly
`not_applicable_joint_descriptive_ranking_no_hypothesis_tests`; users needing a predeclared
baseline-versus-variation test use `STA-01`. Interval overlap is not a test, non-overlap is not an
automatic decision rule, and rank frequency is not a probability that a policy is universally
best.

Every result embeds the filtered `WinnerMapReport`, complete N-way observations, per-family
missing/duplicate/incompatible seed inventory, endpoint exclusions, input and collection
fingerprints, method/config fingerprints, bootstrap parameters, source mode, assumptions,
warnings, and limitations. The service reads completed `MetricCollection` artifacts only, does not
read raw rows, does not mutate evidence, and makes no causal or external-validity claim.

## Consequences

- Existing winner-map consumers retain their schema and ranking semantics.
- N-way means are comparable because every policy uses the same complete random-seed rows.
- Missingness can reduce support without silently changing another policy's denominator.
- A thin family can retain descriptive complete observations but its uncertainty is unavailable.
- Incompatible contracts are excluded and never receive a rank.
- Bootstrap rank frequencies express empirical resampling stability, not equivalence, causal
  superiority, deployment advice, or post-hoc model selection.
- `STA-03` equivalence, `STA-04` regression gates, and `STA-05` power remain separate capabilities.

## Rejected Alternatives

- **A new independent ranking engine:** could drift from the existing winner-map objective, tie,
  and regret semantics.
- **Rank policies with unequal available seeds:** changes denominators across policies and breaks
  the registered common-seed design.
- **Mean-impute missing runs:** fabricates evidence.
- **Rank scenario-policy combinations together:** conflates scenario and policy effects.
- **Declare ties from overlapping intervals:** interval overlap is neither equivalence nor a
  justified tie procedure.
- **Independent per-policy bootstrap:** discards the common-seed dependence used by the design.
- **Post-hoc pairwise tests between every rank:** adds undeclared multiplicity and duplicates
  `STA-01`.
- **Choose the largest compatible subgroup:** makes the estimand data-dependent and can hide
  environment or semantic changes.

## Acceptance Evidence

- Constructed-data tests cover maximise/minimise order, exact ties, objective-aware regret,
  complete-case denominators, missing expected seeds, unavailable metrics, duplicate endpoints,
  environment and semantic incompatibility, insufficient support, family-specific seeds,
  deterministic bootstrap results, input-order invariance, input immutability, and strict config
  validation.
- Golden output pins the embedded winner map, observations, audit, mean/rank uncertainty,
  provenance, assumptions, and limitations.
- CLI and Streamlit tests prove registered experiment plans supply the configuration and the UI
  only renders typed library results.
- Capability manifests, generated schemas/contract, architecture, methods, usage, limitations,
  reproducibility, and project records reconcile in the same increment.

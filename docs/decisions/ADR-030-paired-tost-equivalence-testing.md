# ADR-030 — Predeclared Paired TOST Equivalence Testing

Status: accepted and implemented
Date: 20 July 2026
Capability: `STA-03`

## Context

TrafficTwin's `STA-01` study already defines the compatible common-seed pairing boundary and
publishes the original-unit variation-minus-baseline mean. A non-significant difference test does
not show that two conditions are practically equivalent: it can also result from a noisy or thin
study. `STA-03` therefore needs a separate predeclared equivalence hypothesis, a defensible
practical margin, and an explicit decision rule over the same admitted pairs.

No universal equivalence margin is defensible for all completion, latency, energy, fairness, and
spatial metrics. Selecting a margin after seeing the paired differences would also invalidate its
interpretation. The implementation must require the caller to state the margin, its basis, and its
justification before evaluation, without inventing a dissertation threshold.

## Decision

TrafficTwin implements `EquivalenceStudy` schema and method version 1.0. A strict
`EquivalenceStudyConfig` predeclares the complete STA-01 selection (experiment, baseline and
variation seed families, policy, checkpoint, metric, objective, and common random-seed set) plus:

- a finite positive symmetric absolute margin in the metric's original unit;
- a margin basis of `practical_threshold`, `literature`, or `provisional_design`;
- a non-empty written justification and, for a literature basis, a required reference;
- one-sided alpha, default `0.05`, fixed before the result is inspected; and
- the single-comparison multiplicity policy.

The service first evaluates the ordinary `STA-01` pairing contract using the same completed
`MetricCollection` inputs. It copies the exact pairing audit and retained observations into the
equivalence artifact and records the source paired-study fingerprint. It performs no equivalence
calculation unless the paired study is available. Missing, unavailable, partial, duplicate,
unmatched, non-finite, provenance-incomplete, semantically incompatible, or cross-signature
evidence therefore remains excluded exactly as in `STA-01`; it is never replaced by zero.

Version 1.0 uses a paired-mean two one-sided tests procedure (`paired_mean_tost_v1`) over the
variation-minus-baseline differences. For symmetric margin `m > 0`, mean difference `d`, sample
standard error `se`, and `n - 1` degrees of freedom, it tests:

1. lower null `H0: d <= -m` against `H1: d > -m`; and
2. upper null `H0: d >= +m` against `H1: d < +m`.

Equivalence is demonstrated only when **both** one-sided p-values are strictly below the
predeclared alpha. The artifact also reports the corresponding `100 × (1 - 2 alpha)%` Student-t
confidence interval. Both interval endpoints must lie strictly inside `(-m, +m)`; code verifies
that this interval rule reconciles with the two-test decision. Student-t probabilities and the
critical value use a deterministic regularised-incomplete-beta implementation pinned by the
method version and checked against known reference quantiles.

At least three compatible common-seed pairs and a finite positive paired-difference sample
standard deviation are required. A zero-variance sample is reported as `degenerate` because the
Student-t standard error and test statistics are undefined; TrafficTwin does not manufacture
infinite statistics or limiting p-values. A failed TOST decision is labelled
`equivalence_not_demonstrated`, not `different` or `not equivalent`, because the procedure has not
established a practically important difference.

The method assumes the paired differences are independent across random seeds and approximately
normal for Student-t inference. The margin is symmetric and absolute in version 1.0. Objective
direction affects only descriptive labels in the inherited pairing artifact; it does not reverse
the difference, margin, hypotheses, or equivalence decision.

Every artifact records the config and fingerprint, margin provenance, source paired-study and
method-contract fingerprints, exact observations/audit, mean and standard error, both hypotheses,
p-values, interval, assumptions, warnings, limitations, and immutable input fingerprints. The UI
and CLI only collect this plan and render the typed result.

## Consequences

- TrafficTwin can make a positive equivalence claim only from a predeclared margin and two
  successful one-sided tests.
- An ordinary difference-test p-value is neither an input to nor a substitute for the equivalence
  decision.
- The exact STA-01 common-seed cohort and exclusions are reused, preventing pairing drift between
  difference and equivalence studies.
- Users must justify the margin in the metric's unit; the repository supplies no universal
  dissertation margin.
- Small, incompatible, or zero-variance studies retain evidence and a typed unavailable reason
  instead of producing a false decision.
- `STA-04` regression gates and `STA-05` power analysis remain separate capabilities.

## Rejected Alternatives

- **Treat a non-significant STA-01 test as equivalence:** confuses absence of evidence with evidence
  that the effect lies inside a practical region.
- **Choose the margin from the observed effect or confidence interval:** makes the claim
  result-dependent.
- **Hard-code one percentage margin for every metric:** ignores units, baselines, and practical
  meaning.
- **Use independent-sample TOST:** discards the registered common-seed design.
- **Use interval overlap between policies:** does not test a predeclared equivalence region.
- **Silently use normal critical values for small samples:** understates uncertainty.
- **Declare failed TOST as proof of difference:** TOST failure can reflect inadequate precision.
- **Allow zero sample variance to yield infinite test statistics:** creates non-finite artifacts and
  conceals a violated Student-t calculation boundary.

## Acceptance Evidence

- Constructed-data tests cover known equivalent, boundary, clearly outside-margin, and ordinary
  non-significant-but-not-equivalent behavior; Student-t reference probabilities; strict interval
  boundaries; margin-basis validation; insufficient, degenerate, and incompatible cohorts; input
  immutability; and fingerprint/order stability.
- Golden output pins the margin declaration, inherited pairing audit, hypotheses, p-values,
  confidence interval, conclusion, provenance, assumptions, and limitations.
- CLI and Streamlit tests prove registered plans feed the library service and expose the margin
  basis/justification without UI-side statistical logic.
- Capability manifests, generated schemas/contract, architecture, usage, limitations,
  reproducibility, and implementation records reconcile in the same increment.

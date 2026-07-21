# ADR-032 — Paired Common-Seed Normal-Approximation Power Planning

Status: accepted and implemented
Date: 20 July 2026
Capability: `STA-05`

## Context

TrafficTwin's `STA-01` comparison preserves exact common-random-seed pairs and estimates the mean
variation-minus-baseline difference in the metric's original unit. The v0.5 design also requires a
power helper that estimates the required number of common-seed replicates from a declared effect,
variance, alpha, target power, and method assumptions. It must label small-sample and synthetic
inputs and remain a planning aid rather than a guarantee.

No single observed TrafficTwin study can supply a universally defensible target effect or
prospective paired-difference variance. Automatically using the observed effect to calculate
post-hoc power would add no independent evidence beyond the completed test and could encourage
result-dependent planning. Exact power for the existing sign-flip randomisation procedure also
depends on a complete alternative distribution, not only an effect and variance. Version 1.0
therefore needs a bounded method whose assumptions follow directly from the required inputs.

## Decision

TrafficTwin implements `PowerAnalysis` schema and method version 1.0 as a prospective two-sided
paired-mean normal-approximation planner. A strict `PowerAnalysisConfig` declares:

- the metric key and original unit;
- the signed target variation-minus-baseline mean effect;
- the prospective variance of paired differences in the original unit squared;
- two-sided alpha and target power;
- separate target-effect and variance bases, written justifications, and literature references
  where literature is claimed;
- pilot sample size whenever either input is pilot-derived;
- an explicit synthetic flag whenever either input basis is synthetic; and
- a bounded search interval of at least 3 and at most 1,000,000 common-seed pairs.

For target-effect magnitude `|delta|`, paired-difference standard deviation `sigma`, pair count
`n`, and two-sided standard-normal critical value `z_(1-alpha/2)`, version 1.0 evaluates:

```text
lambda(n) = sqrt(n) * |delta| / sigma
power(n)  = Phi(-z_(1-alpha/2) - lambda(n))
          + Phi( lambda(n) - z_(1-alpha/2))
```

The service uses Python's deterministic standard-library normal distribution implementation and a
bounded integer binary search. It returns the smallest `n` whose power is at least the target and,
when `n` exceeds the lower bound, records that `n - 1` remains below target. Required total policy
runs are `2n`: one compatible baseline and one compatible variation run for every common seed.

A zero target effect, non-positive variance, or target not reached by the declared maximum yields a
typed `unavailable` result with a stable reason code. Configuration errors such as non-finite
numbers, missing bases, absent literature references, or an unlabelled synthetic basis are rejected
before evaluation. No missing pair, variance, effect, or failed calculation is replaced by zero.

Every result is labelled `planning_aid_not_a_guarantee`. Pilot inputs below 30 pairs,
recommendations below 30 planned pairs, synthetic inputs, and provisional inputs receive additional
machine-readable labels and warnings. The artifact records the complete plan and fingerprint,
method-contract fingerprint, bases, pilot size, result, achieved and preceding approximate power,
assumptions, limitations, and a timestamp-normalised fingerprint.

The normal method assumes independent common-seed pairs, a fixed known prospective variance, an
approximately normal paired-mean sampling distribution, complete compatible baseline/variation
runs, and one two-sided comparison without multiplicity adjustment. TrafficTwin never chooses the
effect or variance, validates their substantive basis, or calls planned power achieved power.

## Consequences

- Researchers can calculate and export a reproducible minimum common-seed plan before generating
  confirmatory runs.
- Signed effects remain in provenance, while two-sided power correctly uses effect magnitude.
- Small pilot samples and synthetic/provisional calibration cannot silently appear as externally
  validated sample-size evidence.
- The result is compatible with the `STA-01` paired experimental unit but is not exact power for
  its sign-flip randomisation test.
- The planner does not add simulator launch support, generate runs, or repair missing/incompatible
  completed evidence.
- More specialised sign-flip, TOST, N-way, multiplicity-adjusted, attrition, sequential, adaptive,
  cluster, or simulation-based planners require separate method contracts.

## Rejected Alternatives

- **Observed post-hoc power from a completed STA-01 effect:** restates the completed test under an
  assumed alternative and encourages result-dependent interpretation.
- **Automatically copy the observed mean and variance from any stored study:** makes the plan
  depend on inspected results and conceals the researcher's responsibility for prospective inputs.
- **Claim exact sign-flip-test power from effect and variance alone:** the alternative distribution
  is under-specified.
- **Use a normal closed-form sample-size expression without verifying integer power:** can return a
  non-minimal boundary because two-sided power includes both rejection tails.
- **Silently use a Student-t or noncentral-t label:** would misrepresent a normal-approximation
  calculation and its fixed-variance assumption.
- **Treat zero variance as infinite power:** conceals a degenerate planning assumption and creates
  an unsupported finite sample-size claim.
- **Inflate for attrition with an undocumented percentage:** fabricates a missingness model not
  declared by the caller.

## Acceptance Evidence

- Reference tests pin normal quantiles and known sample-size/power outputs; boundary tests prove
  minimality, effect-sign symmetry, monotonicity, and declared maximum behavior.
- Validation tests cover zero effect/variance, non-finite and out-of-range inputs, basis/reference,
  pilot-size, synthetic-label, justification, determinism, timestamp normalisation, and input
  immutability.
- Golden JSON pins the complete labelled planning artifact. JSON, Markdown, and CSV reconcile.
- CLI, service, capability, synthetic demo, generated contract, and Streamlit AppTest coverage keep
  interfaces thin over the library calculation.
- Architecture, usage, limitations, reproducibility, traceability, implementation status, and the
  canonical v0.5 specification are reconciled in the same increment.

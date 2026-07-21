# ADR-028 — Common-Seed Paired Statistical Study

Status: accepted and implemented
Date: 20 July 2026
Capability: `STA-01`

## Context

TrafficTwin already stores deterministic per-run `MetricCollection` artifacts and registers an
experiment's baseline seed, variation seeds, policies, checkpoints, and common random-seed set.
The existing aggregation layer reports only descriptive means and paired differences. `STA-01`
requires a predeclared estimand, pairing audit, deterministic uncertainty interval,
randomisation/permutation test, and effect sizes that respect the common-seed design.

An unpaired test or automatically primary Cliff's delta would discard the designed pairing.
Parametric inference would add distributional assumptions that are not justified for the small,
bounded dissertation studies. A statistical procedure must also refuse to combine different
metric versions, units, environments, checkpoints, semantic contracts, or ambiguous duplicate
pairing keys.

## Decision

TrafficTwin implements `StatisticalStudy` schema and method version 1.0 over completed
`MetricCollection` objects. The analysis plan is a strict `PairedStudyConfig` declared before
evaluation. It fixes one experiment, baseline seed, variation seed, policy/algorithm, checkpoint,
scalar metric, objective direction, common random-seed set, 95% by default interval level,
resampling repetitions, and an explicit resampling seed. It is a single-comparison service, so
multiple-comparison correction is explicitly not applicable rather than silently omitted.

The pairing key is exact `random_seed`. Each retained observation is variation minus baseline.
The primary estimand is the arithmetic mean of those paired differences in the metric's original
unit. Objective direction affects only the visible favourable/unfavourable interpretation; it does
not reverse or otherwise alter the estimate.

Version 1.0 uses:

1. **Paired percentile bootstrap interval.** Resample complete paired differences with replacement,
   compute their mean, and take deterministic linear-interpolated percentile endpoints. The
   algorithm uses Python's local Mersenne Twister instance with the recorded seed; it never reads
   ambient random state. Default repetitions are 10,000 and the accepted range is 1,000–100,000.
2. **Two-sided paired sign-flip randomisation test.** Test the sharp zero-effect/exchangeable-sign
   null using the absolute mean paired difference. Enumerate all `2^n` sign assignments exactly for
   at most 16 pairs. Above 16, use the recorded seed and 10,000 default Monte Carlo assignments
   with the `(extreme + 1) / (repetitions + 1)` correction. No one-sided alternative is selected
   after observing the result.
3. **Paired effect sizes.** Report the original-unit mean difference as primary. Also report
   Cohen's `dz = mean(difference) / sample_sd(difference)` when the paired-difference standard
   deviation is non-zero, and matched-pairs rank-biserial correlation over non-zero absolute-rank
   differences. These secondary standardised measures carry their assumptions. Cliff's delta is
   not calculated automatically because it is an unpaired dominance measure.

At least three compatible pairs are required for inference. Thinner studies retain their exact
observations and audit but are `insufficient`, with interval/test/effect components unavailable.
Unavailable, partial, non-scalar, non-finite, unplanned-seed, unmatched, duplicate-key, or
pair-incompatible observations are retained as exclusions. A study with multiple otherwise
eligible compatibility signatures is `incompatible`; TrafficTwin does not choose a convenient
subgroup.

Compatibility requires exact experiment, seed role, policy, checkpoint, random seed, collection
and metric implementation versions, unit, synthetic label, environment identity/version or
commit, and source fingerprint. Energy, fairness, custom-plugin, target-RSU, and spatial-grid
metrics additionally require their exact semantic-contract and admitted-group fingerprints.

Every input collection receives a timestamp-normalised fingerprint. The study records the complete
config and fingerprint, eligible pair values and source IDs/fingerprints, exclusions, planned and
missing seeds, method versions/seeds/repetitions, assumptions, warnings, and limitations. The
artifact fingerprint normalises only the study generation timestamp. The service reads no raw
rows, changes no stored collection, and performs no causal attribution.

## Consequences

- Common-seed experiment comparisons now retain the designed pairing in their estimate,
  resampling, test, and effect sizes.
- Exact small-sample sign-flip results are reproducible without an external statistics runtime;
  larger studies remain bounded and seed-reproducible.
- The interval describes bootstrap uncertainty under the empirical paired sample; the p-value is
  conditional on sign exchangeability. Neither proves practical importance, causality, external
  validity, equivalence, or adequate power.
- Missing pairs reduce the admitted sample and remain visible. Statistical methods cannot repair
  incompatible provenance or semantic contracts.
- `STA-02` N-way ranking, `STA-03` equivalence, `STA-04` regression gates, and `STA-05` power remain
  separate capabilities.
- Current SUMO and TOS adapters remain capability-unavailable until they provide a registered,
  compatible common-seed experiment boundary.

## Rejected Alternatives

- **Unpaired t-test or Mann–Whitney test:** discards the common-seed pairing.
- **Ordinary nonparametric bootstrap over two separate groups:** breaks paired dependence.
- **Cliff's delta as the primary effect:** describes unpaired dominance, not paired change.
- **Post-hoc one-sided tests or seed removal:** permits result-dependent analysis choices.
- **Normal-theory confidence intervals by default:** adds an unnecessary small-sample normality
  assumption.
- **Silently choose one duplicate or compatibility subgroup:** makes the included estimand depend
  on input ordering.
- **Interpret non-significance as equivalence:** equivalence requires the separate predeclared
  margin and method in `STA-03`.

## Acceptance Evidence

- Constructed-data tests cover known null/effect behavior, exact and Monte Carlo sign-flip modes,
  bootstrap determinism, paired effect sizes, objectives, insufficient support, missing/unmatched
  seeds, duplicate keys, unavailable/non-scalar inputs, semantic/environment incompatibility,
  timestamp/order stability, input immutability, and strict config bounds.
- Golden output pins the complete study plan, pairing audit, estimate, interval, test, effects,
  provenance, assumptions, and limitations.
- CLI and Streamlit tests prove that registered experiment plans feed the typed library service and
  expose every inclusion/exclusion without UI-side scientific calculation.
- Generated schemas/contract, capability manifests, architecture, usage, limitations,
  reproducibility, and implementation records are reconciled in the same increment.

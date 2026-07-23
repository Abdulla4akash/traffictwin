# Deterministic observed-versus-simulated comparison

Status: **candidate library evidence — `MAN-10` remains `planned`**

`traffictwin.integration.manchester.comparison` performs a pure, deterministic comparison of
compatible observed and SUMO interval evidence. It does not read files, clocks, networks, or
databases; run SUMO; infer mappings; fill missing values; fuse sources; or produce causal or model-
quality claims.

It consumes explicit fingerprints from the [snapshot service](manchester_snapshot_service.md),
[projection service](manchester_projection_service.md), and
[map-matching contract](manchester_map_matching.md). Those references preserve lineage but do not
authenticate external evidence by themselves; upstream accepted artifacts and their verification
gates remain necessary.

## Versioned comparison contract

`ManchesterComparisonMetricContract` binds every v1 methodological choice before comparison:

- evidence class (`synthetic_development` or `production`);
- exactly one observed source, with `source_fusion="none"`;
- one labelled geographic scope and its SHA-256 fingerprint;
- one labelled time basis and its SHA-256 fingerprint;
- one exact interval duration with `exact_interval_no_resampling`;
- one measure and its fixed unit (`vehicle_count`/`vehicles_per_interval` or
  `average_speed_mps`/`m/s`);
- the exact pairing key: site/edge, start, end, direction, and vehicle class;
- equal-interval weighting, unpaired-row exclusion, identical-duplicate collapse, conflicting-
  duplicate refusal, and per-side all-input-row coverage denominators;
- minimum observed and simulated coverage thresholds at 0.001 precision;
- `simulated_minus_observed`, no unit conversion, `ROUND_HALF_EVEN`, output quantum `0.001`, and
  paired-interval metric denominators; and
- a descriptive, non-causal interpretation policy.

The contract refuses DfT raw-count speed: `dft_raw_count` can select `vehicle_count` only.
Synthetic-development contracts require `synthetic_utc_road`; production contracts cannot select
that source.

## Content-bound typed inputs

`ComparisonIntervalContent` contains the exact scientific interval, source scope, and time basis.
`ObservedComparisonInterval` and `SimulatedComparisonInterval` embed that content together with:

- its recomputed content fingerprint;
- the upstream source-row fingerprint;
- a recomputed binding fingerprint over content plus provenance;
- the synthetic/real declaration; and
- source-specific snapshot/projection/mapping or network/calibration/run fingerprints.

The public builders calculate the binding fields. Model reload verifies them, so changing embedded
content while retaining an old content or provenance binding fails before comparison. Numerically
equal Decimal values such as `10` and `10.0` have the same duplicate semantics even if their source
representations and full fingerprints differ.

This is tamper-evident self-consistency, not a signature: an actor that deliberately constructs an
entirely new internally consistent artifact has created new evidence and still needs the upstream
acceptance and publication gates.

## Pairing and exclusions

Every row is canonically sorted and becomes exactly one paired contribution or one typed exclusion.
Rows are screened against the contract before pairing:

- wrong observed source → `source_mismatch`;
- wrong measure or unit → `measure_mismatch` / `unit_mismatch`;
- wrong scope or time basis → `scope_mismatch` / `time_basis_mismatch`;
- wrong duration → `interval_duration_mismatch`; and
- wrong upstream lineage → `lineage_fingerprint_mismatch`.

Exact-key rows then pair. A one-sided key becomes
`unmatched_no_simulated_counterpart` or `unmatched_no_observed_counterpart`. Numerically and
semantically identical duplicates collapse with every surplus row recorded as
`duplicate_identical_row`; disagreeing duplicates are all excluded as
`conflicting_duplicate_rows`. There is no arbitration, resampling, unit conversion, source fusion,
or missing-as-zero path. Both input and exclusion models structurally fix the zero-fill declaration
to `False`.

`ObservedSimulationComparison` publishes both denominators and both paired-coverage values:

```text
paired_observed_coverage  = paired_intervals / all_observed_input_rows
paired_simulated_coverage = paired_intervals / all_simulated_input_rows
```

The published ratios use fixed Decimal arithmetic and are rounded to `0.001`. Threshold admission
compares the exact unrounded fraction, so a value displayed as `0.667` cannot pass a `0.667`
minimum when its true ratio is `2/3`.

## Metric admission

MAE/RMSE is available only when all three conditions hold:

1. at least one compatible pair exists;
2. both contract coverage thresholds pass; and
3. the contract is admitted.

Typed unavailable reasons are `no_paired_intervals`, `coverage_below_contract_minimum`, and
`contract_not_admitted`. `APPROVED_PRODUCTION_CONTRACT_FINGERPRINTS` is intentionally empty, so
real goodness-of-fit remains unavailable. Adding an entry requires a reviewed, predeclared
production study design. Synthetic contracts calculate values only to verify software behavior.

MAE and RMSE use the exact embedded observed and simulated values under an explicit Decimal context
(precision 28, `ROUND_HALF_EVEN`) and round only the final result to `0.001`. Displayed signed
differences use the fixed direction and quantum. Ambient process Decimal precision cannot change
canonical JSON or fingerprints.

## Reload derivation

The result embeds canonical sorted tuples of every observed and simulated input. Its model validator
runs the same pure derivation over those inputs and requires exact equality for:

- evidence class and synthetic state;
- contract admission;
- input ordering and full input-set fingerprints;
- screening, duplicate handling, pairs, and exclusions including every reason;
- signed and absolute differences;
- input counts, exclusion counts, both denominators, both coverage values, and coverage status; and
- metric status, reason, sample size, unit, and value.

Consequently, coherent pair/metric rewrites, synthetic relabelling, exclusion-reason relabelling,
input addition/removal/reordering, content changes under old bindings, and summary-field mutations
all fail `model_validate_json`.

## Interpretation boundary

Every result fixes `non_causal_descriptive_only=True` and the following interpretation:

> Paired differences are descriptive software evidence; they do not establish model quality,
> realism, or the origin of any difference.

No deterministic output claims a model is better, accurate, valid, improved, or causal.

## Verification

`tests/unit/test_manchester_comparison.py` uses only labelled synthetic fixtures except for typed
fail-closed production-boundary tests. It covers exact pairing, two-sided coverage, threshold
unavailability including rounded-display boundary refusal, missingness, numeric duplicate
normalization, conflicting duplicates, cross-source/
scope/time-basis/duration refusal, DfT-speed refusal, direction/class/boundary mismatch, invalid
values, empty denominators, production self-approval refusal, evidence-class mismatch, golden
MAE/RMSE, ambient Decimal-context invariance, input-order invariance, canonical reload, coherent
mutation refusal, input-binding mutation refusal, inventory mutation refusal, and wording limits.

## Remaining blockers

- The production contract registry is empty and no reviewed real comparison design exists.
- Real observed and simulated inputs still depend on accepted MAN-01–MAN-09 artifacts.
- No real comparison has been run, and no UI action or capability status is enabled by this module.
- Package exports, generated schemas, and shared capability documentation are lead-owned integration
  steps after review.

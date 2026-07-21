# ADR-031 — Versioned Golden-Contract Regression Gates

Status: accepted and implemented
Date: 20 July 2026
Capability: `STA-04`

## Context

TrafficTwin already produces deterministic run-level `MetricCollection` artifacts and paired
`StatisticalStudy` artifacts. Continuous integration needs a bounded way to compare a newly
computed artifact with an intentionally accepted reference without comparing formatted prose,
silently accepting missing evidence, or treating every numerical change as a regression.

A golden output file alone is insufficient. It does not state which fields are scientifically
meaningful, how much numerical movement is acceptable, whether the source input must be identical,
or whether the reference has actually been approved. Conversely, a general JSON diff would make
timestamps, identifiers, ordering, and explanatory metadata part of a scientific decision by
accident.

## Decision

TrafficTwin implements `RegressionGoldenContract` and `RegressionGateReport` schema/method version
1.0. Version 1.0 supports two typed subject kinds:

- a completed `MetricCollection`, including metrics computed from a newly validated bundle or a
  stored registered collection; and
- a completed STA-01 `StatisticalStudy` JSON artifact.

The gate consumes these typed artifacts only. It does not read raw rows, recompute metrics, rerun a
study, choose tolerances, update a golden file, or mutate registry/source state.

Every golden contract declares a stable contract identifier and semantic version, a description,
an approval state, one subject kind, one typed compatibility context, a source-identity policy,
and one or more unique scalar assertions. A candidate contract may be generated for review, but a
gate over a candidate is `unavailable`; only an explicitly approved contract can pass or fail.
Approval records a non-empty approver label and note so generated output cannot silently become its
own accepted baseline.

Each assertion records the expected finite scalar value, unit, absolute tolerance, and relative
tolerance. Both tolerances are finite and non-negative, including explicit zero when exact equality
is required. For expected value `e` and actual value `a`, version 1.0 computes:

```text
absolute_error = abs(a - e)
allowed_error = max(absolute_tolerance, relative_tolerance * abs(e))
pass iff absolute_error <= allowed_error
```

The relative component therefore contributes zero at an expected value of zero; a non-zero
absolute tolerance must be declared if movement around zero is allowed. Boundary equality passes.
TrafficTwin records both error components and the final allowed error in every check.

Metric assertions use exact metric keys. The subject context requires one internally consistent
run context, the declared metric-collection version, experiment, seed family, policy, checkpoint, synthetic
label, environment identity/version-or-commit, and a non-empty source input fingerprint. Every
asserted metric must be an available finite scalar with exactly matching unit and implementation
version. Partial, unavailable, invalid, missing, non-scalar, or non-finite values are unavailable,
not zero and not a numerical failure. Metrics not named by the contract are ignored and counted;
the gate makes no claim about them.

Paired-study assertions are restricted to a published allow-list of stable scalar fields: eligible
pair count, paired mean/standard deviation/standard error, bootstrap bounds, randomisation p-value,
Cohen's dz, and matched-pairs rank-biserial correlation. The context requires an available STA-01
study, matching schema/method/config fingerprints, metric unit, synthetic label, and compatibility
signature. A selected component that is unavailable remains unavailable.

The source-identity policy is explicit:

- `exact` requires the current metric input fingerprint or complete paired-study input-fingerprint
  map to equal the accepted source identity; this is the default for fixture/reproducibility CI;
- `compatible_context` permits different source inputs only after all typed context and semantic
  compatibility checks pass; this supports declared benchmark thresholds across repeated runs.

Context or source-identity mismatch is `unavailable`, because the contract does not define a valid
comparison for that subject. An available scalar outside tolerance is `failed`. The overall gate
is `unavailable` if any required assertion or compatibility check is unavailable, otherwise
`failed` if any assertion fails, otherwise `passed`. This precedence prevents partial evidence
from being hidden by another obvious numerical failure.

Every report records the complete golden contract and fingerprint, subject and source
fingerprints, typed blocking findings, all checks, counts, ignored-field count, warnings,
limitations, and a timestamp-normalised deterministic artifact fingerprint. JSON is the primary CI
format; Markdown and CSV are reconciled human/audit views. CLI exit codes are `0` for pass, `1` for
fail, and `2` for unavailable. Interface code only loads typed inputs, collects contract metadata,
delegates to the core service, and renders its output.

## Consequences

- CI can distinguish a true tolerated pass, a complete numerical regression, and an invalid or
  incomplete comparison.
- Golden acceptance is deliberate and versioned; the evaluator never rewrites its own reference.
- Absolute and relative tolerances are visible per assertion and use one deterministic rule.
- Exact-source fixture regression and compatible-context benchmark regression are separate,
  explicit policies.
- Run timestamps, generated identifiers, prose, warnings, and unselected fields cannot
  accidentally decide the gate.
- Version 1.0 does not gate STA-02 rankings, STA-03 equivalence conclusions, diagnostic reports,
  rendered reports, arrays, grouped values, or arbitrary JSON paths. Those require separate stable
  projections and compatibility decisions.

## Rejected Alternatives

- **Byte-compare complete JSON:** makes timestamps and non-decision metadata fail CI and supplies no
  tolerance semantics.
- **Diff rendered Markdown/HTML/PDF:** presentation changes are not scientific regression evidence.
- **Treat missing or unavailable actual values as failures or zero:** conflates absent evidence with
  a measured regression.
- **Use only a relative tolerance:** has undefined or misleading behavior around an expected zero.
- **Add absolute and relative tolerances together:** silently widens the declared larger tolerance;
  version 1.0 uses their maximum as an explicit either-condition rule.
- **Let the gate generate and immediately approve its golden:** converts the current output into an
  automatic pass without independent acceptance.
- **Infer a tolerance from historical variation:** chooses an unrequested research threshold and
  belongs to a separately declared method.
- **Allow arbitrary JSONPath assertions:** exposes unstable/internal fields and makes unit and
  availability semantics ambiguous.
- **Return only a boolean:** hides incompatibility and violates the unavailable-is-not-zero policy.

## Acceptance Evidence

- Constructed tests cover exact pass, absolute and relative pass boundaries, numerical failure,
  zero expectations, missing/unavailable/non-finite/non-scalar metrics, unit/version/context/source
  mismatch, candidate contracts, compatible-context policy, study-field admission, component
  unavailability, input immutability, and deterministic fingerprints.
- Golden tests pin both a passing and failing report projection.
- CLI tests cover candidate generation, approved metric and paired-study evaluation, JSON/Markdown/
  CSV exports, and the distinct pass/fail/unavailable exit codes.
- Registry-backed UI-service and Streamlit tests verify that the interface delegates to the typed
  service and renders uploaded contract results without implementing tolerance arithmetic.
- Capability manifests, generated schemas/contract, demo artifacts, architecture, usage,
  limitations, reproducibility, and implementation records reconcile in the same increment.

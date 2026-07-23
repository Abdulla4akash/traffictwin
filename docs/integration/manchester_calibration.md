# Deterministic calibration-candidate evaluation (MAN-09 candidate)

Status: **candidate library evidence — `MAN-09` remains `planned`**

`traffictwin.integration.manchester.calibration` performs a pure, deterministic evaluation of
caller-supplied, already-completed calibration candidates against compatible observed interval
evidence. It does not read files, clocks, networks, or databases; launch SUMO or any subprocess;
invent candidate outputs; edit raw observations, map matches, networks, or SUMO results; fill
missing values; fuse sources; or accept a baseline.

It consumes explicit fingerprints in the shapes defined by the
[snapshot service](manchester_snapshot_service.md),
[projection service](manchester_projection_service.md),
[map-matching contract](manchester_map_matching.md), and
[controlled SUMO execution](sumo_controlled_execution.md), and it mirrors the hardened
content-binding and reload-derivation design of the
[MAN-10 comparison module](manchester_comparison.md). Those references preserve lineage but do
not authenticate external evidence by themselves; upstream accepted artifacts and their
verification gates remain necessary.

## Calibration contract

`ManchesterCalibrationContract` fixes every methodological choice before any number exists:

- `contract_version` and `evidence_class` (`synthetic_development` or `production`);
- exactly one observed source with `source_fusion="none"` and a structural scope kind:
  WebTRIS evidence is `strategic_road_site` scoped, DfT raw counts are `urban_zone` scoped, and
  synthetic fixtures live in `synthetic_zone` — no other combination is representable;
- one labelled scope, time basis, accepted-source, projection, mapping, and SUMO network, each
  bound by a SHA-256 fingerprint;
- one exact interval duration with `exact_interval_no_resampling`;
- one measure with its fixed unit and `unit_conversion="none"` — count and speed evidence can
  never share one objective, and a DfT raw-count contract can select `vehicle_count` only;
- one objective (`mean_absolute_error` or `root_mean_square_error`) over the fixed residual
  direction `simulated_minus_observed`, with equal-interval weighting, unpaired-row exclusion,
  identical-duplicate collapse, conflicting-duplicate refusal, per-side all-input-row
  denominators, and minimum observed/simulated coverage at `0.001` precision;
- the exact parameter space: named `CalibrationParameterBound` entries with units, finite
  bounded lower/upper bounds, and a strictly increasing permitted candidate grid inside those
  bounds — parameter names and grid values are constrained typed data, never expressions or
  commands;
- `demand_synthesis="none_supplied_candidate_evidence_only"`: the evaluator never converts a
  raw count into a vehicle-generation rate, and no DfT AADF value is representable in this
  module at all, so AADF can never become hourly demand;
- deterministic precision (`ROUND_HALF_EVEN`, quantum `0.001`), the fixed tie-break
  `objective_value_then_candidate_binding_fingerprint`, and the descriptive
  candidate-review-only interpretation policy.

## Candidates are evidence, not executions

`CalibrationCandidateInput` carries a label, one exact parameter assignment (sorted unique
names), the SUMO-run fingerprint of the completed run that produced it, and its typed simulated
intervals. Parameter assignments must name exactly the contract-declared parameters, lie inside
the bounds, and sit on the permitted grid; violations are typed errors
(`PARAMETER_CONTRACT_MISMATCH`, `PARAMETER_OUT_OF_BOUNDS`, `PARAMETER_NOT_IN_PERMITTED_GRID`).
Observed and simulated inputs embed their exact scientific content
(`CalibrationIntervalContent`) with recomputed content and content-plus-provenance binding
fingerprints, so changing embedded content while retaining an old binding fails before
evaluation. Numerically equal Decimal values such as `10` and `10.0` are identical duplicates,
never conflicts.

## Screening, pairing, and reconciliation

Each candidate is evaluated independently against the same canonical observed inputs — sources
and scopes are never merged across candidates or rows:

- wrong source → `source_mismatch`; wrong measure/unit → `measure_mismatch` / `unit_mismatch`;
- wrong scope kind, scope, or time basis → `scope_mismatch` / `time_basis_mismatch`;
- wrong duration → `interval_duration_mismatch`;
- wrong source/projection/mapping fingerprint (observed) or wrong network/run fingerprint
  (simulated) → `lineage_fingerprint_mismatch`;
- one-sided keys → `unmatched_no_simulated_counterpart` / `unmatched_no_observed_counterpart`
  — a missing observation is never zero (`filled_with_zero` and `missing_filled_with_zero` are
  structurally `False`);
- identical duplicates collapse with surplus rows recorded; disagreeing duplicates are all
  excluded without arbitration.

Every evaluation reconciles completely: observed input rows equal paired intervals plus that
candidate's observed exclusions, and likewise for its simulated side. Both coverage ratios,
both denominators, all exclusion reasons, and every signed/absolute residual
(`simulated_minus_observed`) are published.

## Objective admission and ranking

A candidate objective is available only when the contract is admitted, at least one pair
exists, and both coverage minima pass; otherwise it is typed unavailable
(`contract_not_admitted`, `no_paired_intervals`, `coverage_below_contract_minimum`) — an
insufficient-coverage candidate never yields a score. Published coverage is quantised to `0.001`,
but admission compares the exact unrounded fraction; display rounding can never promote a candidate
that is actually below its threshold.
`APPROVED_PRODUCTION_CALIBRATION_CONTRACT_FINGERPRINTS` is a **frozen empty set**: production
objectives and ranking fail closed today, real evidence cannot self-declare approval, and
synthetic and production evidence can never mix or borrow each other's admission path
(`MIXED_EVIDENCE`, `CONTRACT_EVIDENCE_CLASS_MISMATCH`).

Available candidates are ranked deterministically by objective value and then by the candidate
binding fingerprint (a hash over label, parameters, run fingerprint, and the simulated input
set). Every candidate is published, not only the winner. The top-ranked candidate is only
`candidate_selected_for_analyst_review`; `automatic_acceptance=False` and
`baseline_available=False` are literals, so nothing here creates or accepts a
`ManchesterSumoBaseline`.

## Determinism and reload derivation

All arithmetic — residuals, coverage ratios, objective sums, division, square root, and
quantisation — runs inside an explicit `localcontext()` (precision 28, `ROUND_HALF_EVEN`),
so the ambient process Decimal context cannot change canonical JSON or fingerprints (tested).
Inputs, pairs, exclusions, and evaluations are canonically sorted; results are invariant under
input and candidate ordering.

`ManchesterCalibrationReport` embeds the canonical typed observed inputs and, per candidate,
the exact parameter assignment, run fingerprint, and simulated inputs. Its validator re-runs
the same pure derivation over those embedded inputs and requires exact equality for admission,
screening, duplicate handling, pairs, exclusion reasons, residuals, counts, denominators, both
coverages, objective status/value, ranking, tie-breaks, selection, synthetic state, and every
fingerprint. Coherent objective/ranking rewrites, synthetic relabelling, exclusion-reason
relabelling, candidate or input addition/removal/reordering, parameter/residual/coverage
mutations, and content edits under old bindings all fail `model_validate_json`. This
self-consistency is tamper evidence, not cryptographic authenticity: a rebuilt internally
consistent artifact is new evidence and still needs the upstream acceptance gates.

## Interpretation boundary

Every report fixes `non_causal_descriptive_only=True` and the interpretation:

> Candidate objective values are descriptive software evidence for analyst review; they do not
> establish realism, model quality, or the origin of any difference, and no candidate is
> accepted automatically.

No deterministic output claims a candidate is better, accurate, improved, causal, or a valid
model, and no output asserts Manchester validity.

## Test evidence

`tests/unit/test_manchester_calibration.py` (29 tests, all offline, labelled synthetic fixtures
plus typed fail-closed production-boundary fixtures): golden MAE (`1.667`/`0.333`) and RMSE
(`1.732`) values with ranking and selection; fixed residual direction; deterministic
fingerprint tie-break; ambient Decimal-context invariance of canonical JSON and fingerprints;
below/above-bounds and off-grid parameter refusal; duplicate parameter, invalid grid, and
duplicate candidate-label refusal; missing observed/simulated intervals as exclusions (never
zero); numeric-duplicate collapse versus conflicting-duplicate refusal; cross-scope/time-basis/
duration and cross-network/mapping/run lineage refusal; cross-source refusal without fusion;
count/speed separation; structural DfT-speed impossibility; insufficient-coverage,
rounded-display boundary refusal, and
empty-denominator typed unavailability; frozen-empty production registry with unavailable
production objectives; production self-approval forgery rejection; mixed and mismatched
evidence-class refusal; coherent objective/ranking rewrite rejection; a broad reload-mutation
battery (inputs, parameters, synthetic flags, exclusion reasons, residuals, coverage, counts,
ranking, selection, binding fingerprints, acceptance literals); old-binding content mutation
rejection; input/candidate order invariance; canonical JSON round trip; empty-input refusal;
and forbidden-wording absence.

Validation commands (run at handoff): the focused pytest file; the full
`tests/unit/test_manchester_*.py` suite; `ruff check`/`ruff format --check` and `mypy --strict`
on the two owned Python files; `git diff --check`; and documentation link validation — all
passing.

## Residual blockers

- `APPROVED_PRODUCTION_CALIBRATION_CONTRACT_FINGERPRINTS` is intentionally empty: a
  lead-reviewed, predeclared calibration study design must register a contract fingerprint
  before any real objective or ranking can exist.
- Real inputs depend on the still-planned upstream capabilities (`MAN-01`…`MAN-08`) and on an
  accepted network binding, map matching, and temporal profile; no real calibration has been
  evaluated and no SUMO run was launched.
- Analyst review, ambiguity confirmation, uncertainty reporting, and baseline
  acceptance/refusal (design §14 steps 5–8) are outside this module and remain unimplemented.
- `MAN-09` remains `planned`; the lead-reviewed package exports, generated schemas, and docs index
  expose this candidate without changing capability truth.

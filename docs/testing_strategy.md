# Testing Strategy

TrafficTwin uses a test pyramid: focused unit tests at the base, integration tests for the pipeline, golden tests for deterministic outputs, and UI smoke tests where reliable.

## Current Snapshot

The current exact results live in the dated
[v0.7 housekeeping completion record](quality/v07_housekeeping_completion_20260803.md). That record
includes the full suite and coverage, locked dependencies, Ruff, strict mypy, deterministic
generated references, local documentation links, fixtures, source/wheel build, isolated wheel
installation, release and standalone-demo smokes, Git integrity and the Python 3.11/3.12 CI matrix.
Counts from OPS-05 and other earlier increments remain historical evidence, not current gate
results.

Coverage is a useful signal, not the only quality measure. Streamlit page rendering and CLI
workflows are partly covered through service tests, AppTest-style tests, and smoke commands rather
than exhaustive browser automation.

OPS-04 adds focused unit, golden, integration, and CLI coverage for all raw disclosure modes,
imported/public permission gates, permitted public embedding, inventory reconciliation, exact
byte determinism, fixed ZIP representation, path redaction, CFF/RO-Crate structure, checksum and
tamper failure, capability truth, and atomic create/verify behavior.

OPS-05 adds protocol, unit, golden, integration, and CLI coverage for the closed adapter catalogue,
distinct SUMO/TOS semantics and conversion profiles, complete capability truth, exact marker
selection, deterministic path-free inspections, source non-mutation, unknown rights, rejected
packages, explicit mismatch, no match, ambiguity, and symbolic-link refusal.

## Unit Tests

Located under `tests/unit/`.

Coverage includes:

- scenario seed validation;
- YAML seed IO;
- capability manifest behavior;
- registry operations and status transitions;
- manifest validation;
- bundle loader safety;
- validation codes;
- metric catalogue and calculators;
- comparison and aggregation;
- EvidencePack generation;
- rule configuration, registry, models, engine, and R0-R8 behavior, including exact temporal
  baseline/event boundaries, direction-aware degradation, gaps, recovery states, R7 operational
  group admission, R8 energy contract/support/population admission, declarative three-valued
  evaluation, and fingerprints;
- nearest-flip R5/R7/R8 exact boundaries, ordinary-engine verification, target-RSU reduction,
  unchanged discrete pair/group/task support, ties, deterministic fingerprints, input/config
  immutability, and explicit unsupported/disabled/triggered/insufficient states;
- threshold-sweep R5/R7/R8 grid generation, source-threshold insertion, every-status retention,
  fixed support/dimension config, stability, sampled transition intervals, exact-flip embedding,
  explicit point-config export, input/config immutability, and unsupported/invalid states;
- cross-rule R1/R2 conflict, R1/R4 corroboration, and explicit R0 blocker suppression; exact
  status/evidence-overlap gates; equal/unequal precedence; original-result retention; unresolved
  blockers; unclassified pairs; ordering/timestamp-stable fingerprints; validation; and input
  immutability;
- adversarial declarative-YAML admission covering unsafe tags/aliases/anchors, duplicate keys,
  multiple/oversized documents, extra fields, reserved IDs, non-finite values, unit/metadata
  mismatches, null/thin/misaligned groups, and duplicate registrations;
- provenance trace models, graph validation, source-row preview, query service, serialisation, and
  Markdown export;
- PRO-01 complete two-side eligibility ledgers, every admitted direct arithmetic formula,
  changing denominators, signed-delta reconciliation, percentile lineage-only/null weights,
  incompatibility/unavailable states, mandatory JSON/CSV warning, and deterministic fingerprint;
- PRO-02 root-centred bounds, exact omissions, stable node/edge/graph/view identities,
  timestamp independence, safe and structure-only disclosure, recursive POSIX/Windows/home/file-
  URI redaction, DOT/XML injection escaping, GraphML parsing, and invalid limit/mode rejection;
- SUMO manifest, XML-safety, checksum, version, trip-state, canonical mapping, summary semantics,
  metric, and source-contract behavior;
- manifest-inference bounds, deterministic methods, confirmation, edits, unit requirements,
  stale-source rejection, and ambiguity behavior.
- declared CSV/gzip/Parquet defaults and decoding, duplicate columns, unsupported Parquet schemas,
  malformed compressed input, decoded-size bounds, and evidence invalidation.
- deterministic batch path/glob resolution, overlap deduplication, preflight limits, mixed
  validation, per-candidate import isolation, conflicts, idempotency, and summary rendering.
- streaming config bounds, stable chunk order/source rows, ordinary-limit bypass, oversized-row
  rejection, exact cross-chunk duplicate/reference checks, and multi-size ordinary equivalence.
- fixed-window configuration, exact half-open boundary assignment, aligned-envelope inference,
  partial include/exclude behavior, empty/unavailable intervals, request bounds, deterministic
  output, and partition invariants across widths/origins.
- linear percentile empty/singleton/interpolation/bounds behavior; exact latency P99 values and
  metadata; and configured minimum-sample unavailability across P50/P95/P99.
- strict task-energy contract validation and stable fingerprinting; exact observed/completed/EDP
  values; missing, partial, negative, and no-contract handling; and comparison compatibility.
- operational-fairness policy/fingerprints; exact group rates, gaps, and Jain values; unstable or
  missing tiers; incomplete RSU load evidence; group count/support/coverage gates; all-zero Jain;
  fixed-window reuse; comparison compatibility; and complete accepted-row ledgers.
- strict task-to-RSU and vehicle-grid manifest contracts; exact target/grid grouped values;
  missing/unknown targets; coordinate coverage; partial latency/speed groups; fixed-window reuse;
  and complete accepted-row ledgers without inferred assignment.
- strict custom-metric contract alignment/fingerprints; duplicate/core-key and mixed-version
  rejection; complete/drop input policies; deep-copy isolation; exact scalar/grouped outputs;
  declared unavailability; exception, nondeterminism, and invalid-output isolation; windows;
  contract-compatible comparison; SUMO canonical-trip execution; and embedded-contract row
  provenance.
- EXP-01 deterministic Cartesian order and timestamp-stable fingerprints; strict base/path/value
  admission; axis, point, response, and complete-row limits; derived schema validation; base
  immutability; protected/symbolic destination rejection; transactional overwrite; local ordinary
  validation/metric reuse; explicit non-numeric unavailability; seed/external modes; YAML/CSV;
  and explicit no-launch artifacts.

## Integration Tests

Located under `tests/integration/`.

They check:

- bundle import;
- directory and ZIP validation;
- bundle to metrics;
- bundle to diagnostics;
- evidence to diagnostics;
- bundle to provenance;
- diagnostic fixture to EvidencePack-only provenance;
- UI service/demo flows;
- SUMO registry idempotency and CLI contract/validation/metric/import workflows;
- confirmed manifest application through the ordinary bundle validator and CLI/UI workflows.
- gzip/Parquet CLI and UI-service analysis plus exact-raw-identity registry behavior.
- batch CLI/UI-service validation and import with partial-result and idempotent-rerun behavior.
- streaming CLI/UI-service validation and metadata import plus directory/ZIP equivalence.
- fixed-window CLI JSON/file output, source-row traces, complete window contribution ledgers,
  UI-service output, and Temporal Metrics AppTest rendering.
- P99 comparison deltas and exposure through whole-run/window/report/Run Overview/provenance
  surfaces.
- task-energy CLI output and Run Overview Energy Evidence rendering over a generated contract-
  compatible bundle.
- operational-fairness CLI output, capability/source-boundary behavior, and Fairness Evidence
  Streamlit rendering over a generated evidence-complete bundle.
- spatial/per-RSU CLI output, capability/SUMO/TOS boundary behavior, and Spatial & RSU Evidence
  Streamlit rendering over a generated contracted bundle.
- machine-readable custom-metric API CLI output and About-page disclosure of the explicit local,
  no-upload, non-sandbox trust boundary.
- cross-rule contract and evaluation CLI output, embedding in a complete DiagnosticReport, and
  Diagnostics & Evidence AppTest rendering with every original result retained.
- parameter-sweep contract/materialisation CLI output plus UI-service and Parameter Sweep AppTest
  execution through the typed library boundary.

## Golden Tests

Located under `tests/golden/` with expected JSON under `tests/golden/expected/`.

Golden files verify exact projections for:

- baseline metrics;
- variation metrics;
- comparison output;
- validation reports;
- diagnostic reports;
- provenance trace projections and Markdown export;
- exact accepted-row mean-latency difference decomposition, including an excluded variation row;
- exact small-graph DOT and GraphML IDs, ordering, labels, data keys, values, and styling;
- stable manifest-inference suggestions and deliberate ambiguity projections.
- canonical, metric, ZIP, and row-provenance equivalence for CSV, gzip-CSV, and Parquet.
- a stable mixed accepted/rejected batch summary projection.
- streaming summary and exact CSV/gzip-CSV/Parquet canonical/report/metric equivalence across
  multiple chunk sizes.
- fixed-window contract/value projections and exact CSV/gzip-CSV/Parquet equivalence.
- exact baseline and variation task-latency P99 projections.
- exact synthetic task-energy family values, coverage, units, and contract provenance.
- exact synthetic operational-fairness grouped/scalar values, support, coverage, policy, and
  group-set provenance.
- exact synthetic per-RSU task and vehicle-grid values, support, coverage, geometry, and contract/
  group-set provenance.
- exact custom-metric registry contract/fingerprint and deterministic result projection.
- exact mixed cross-rule relationship, suppression, unclassified, provenance, and retention
  projection.
- exact EXP-01 two-point JSON/CSV responses, metric values, statuses, axis assignments, and
  request/base/point/seed/bundle/result fingerprints.

Do not update golden files merely to pass tests. Recompute expected values from fixture rows and document the intended behavior change.

## Streamlit Tests

Located under `tests/ui/` and relevant integration tests.

The approach is to test:

- formatting;
- labels;
- chart-data preparation;
- service models;
- state defaults;
- page guards against rejected bundles.

Full browser automation is not required for the current documentation pass.

## CLI Smoke Tests

Representative smoke commands:

```bash
traffictwin validate-seed examples/seeds/arena_gridlock.yaml
traffictwin bundle validate tests/fixtures/bundles/baseline_valid
traffictwin bundle batch-validate 'tests/fixtures/bundles/*' --format json
traffictwin metrics compute tests/fixtures/bundles/baseline_valid
traffictwin metrics windows tests/fixtures/bundles/baseline_valid --width-s 60 --format json
traffictwin compare tests/fixtures/bundles/baseline_valid tests/fixtures/bundles/variation_valid
traffictwin evidence build tests/fixtures/bundles/baseline_valid --output evidence-baseline.json
traffictwin diagnose bundle tests/fixtures/bundles/baseline_valid
traffictwin diagnose evaluate tests/fixtures/diagnostics/cases.json
traffictwin diagnose evaluate tests/fixtures/diagnostics/cases.json --extended
traffictwin diagnose cross-rule-contract --format json
traffictwin diagnose cross-rule tests/fixtures/bundles/baseline_valid --format json
traffictwin provenance metric tests/fixtures/bundles/baseline_valid task.completion.rate
traffictwin provenance contributors tests/fixtures/bundles/baseline_valid \
  task.latency.mean_ms --format csv
traffictwin provenance difference-contributors tests/fixtures/bundles/baseline_valid \
  tests/fixtures/bundles/variation_valid task.completion.rate --format json
traffictwin provenance graph-contract --format json
traffictwin provenance completeness-contract --format json
traffictwin provenance completeness tests/fixtures/bundles/baseline_valid \
  --report-type run --format csv
traffictwin provenance comparison-completeness tests/fixtures/bundles/baseline_valid \
  tests/fixtures/bundles/variation_valid --format json
traffictwin provenance export tests/fixtures/bundles/baseline_valid \
  --root-type metric --root-id task.completion.rate --format graphml \
  --max-nodes 80 --max-edges 160 --redaction structure_only
traffictwin provenance source tests/fixtures/bundles/baseline_valid tasks.csv 2
traffictwin integration sumo contract --format json
traffictwin integration sumo validate tests/fixtures/sumo/square_public
traffictwin integration sumo metrics tests/fixtures/sumo/square_public
traffictwin experiment parameter-sweep-contract
traffictwin experiment parameter-sweep --request examples/parameter_sweep_request.yaml \
  --output build/demand-capacity-sweep
```

## ZIP Security Tests

Bundle loader tests cover safe ZIP behavior:

- reject absolute paths;
- reject path traversal;
- reject symlinks;
- extract in controlled temporary directories;
- clean up after validation.

## Invariants

Tests and code enforce or exercise:

- completed tasks do not exceed generated tasks;
- decision shares are explicit and deterministic;
- rejected bundles do not produce ordinary metrics;
- unavailable metrics have no numeric value;
- JSON contains no `NaN` or infinity;
- rules cite existing evidence keys;
- rules do not mutate EvidencePacks;
- nearest-flip analysis changes neither its EvidencePack nor source RuleSetConfig and returns only
  candidates verified as triggered by the ordinary rule engine;
- threshold sensitivity changes neither EvidencePack nor source RuleSetConfig, retains the entire
  evaluated grid, and exports only exact retained points against the matching complete config;
- cross-rule reasoning retains and fingerprints every input RuleResult, mutates neither the result
  sequence nor the EvidencePack, applies only declared exact-overlap relationships, and never
  changes status, confidence, precedence, evidence, findings, or recommendations;
- provenance traces do not mutate metric or rule outputs;
- provenance exports contain no absolute local paths;
- bounded graph exports retain the root, never exceed declared limits, reconcile exact omitted
  counts, parse as GraphML, escape DOT/XML text, and do not export volatile trace timestamps;
- source-row preview rejects path traversal;
- repeated imports are idempotent;
- batch overlap is deduplicated and one rejected/conflicting candidate cannot roll back or relabel
  successful neighbours;
- directory and ZIP bundles produce equivalent results.
- aligned half-open windows partition every admitted canonical anchor exactly once for inferred
  ranges; exact shared-boundary records enter the later window;
- empty windows remain visible/unavailable, and excluded partial windows remain visible without a
  metric collection;
- generated standalone bundles validate through the existing Phase 2 path;
- standalone reports contain no unescaped HTML or absolute local paths;
- REP-01 table/figure pairs share one projection fingerprint; LaTeX special characters are
  escaped; absolute local paths are redacted without damaging URLs; SVG parses and embeds no
  script/remote asset; invariant PDF parses; and a special-character fragment compiles in a real
  minimal LaTeX document;
- REP-01 preserves unavailable/status/source-mode semantics, is byte-deterministic, refuses
  invalid/duplicate/symbolic targets and unapproved overwrite, and never recalculates source
  artifacts;
- REP-02 validates closed path-free targets and bounded author/note/decision content, verifies
  stored targets, preserves exact/unbound matching and ascending pagination, fingerprints ordered
  history, and rejects direct SQLite update/delete;
- REP-02 report tests prove analyst text is escaped and visibly separate in Markdown/HTML/PDF while
  computed sections and typed claim references remain unchanged; incomplete oversized history is
  refused rather than silently truncated;
- REP-03 tests prove every report claim has a matching prose-free snapshot; rendering, report
  identity, timestamps, warnings, and annotations do not change the scientific fingerprint;
  compatible typed changes publish exact JSON Pointer paths and all five classifications;
- REP-03 incompatibility, unavailable evidence, duplicate identity, input/section/claim/change
  bounds, exact golden JSON, CLI JSON/Markdown, and Reports UI/service paths are covered;
- REP-04 contract/selection/reconciliation/retention/path/escape/inventory/overflow tests, exact
  golden projection, four-format CLI, Reports UI/service, byte-deterministic one-page A4 PDF, and
  Poppler-rendered visual inspection are covered;
- REP-05 covers all six categories, fixed ranking/ties, category/limit filtering, query and
  inventory bounds, exact count/fingerprint reconciliation, read-only database byte identity,
  pre-match query/source path redaction, direct-report symlink/size handling, CLI JSON/text, Search
  UI/service, and generic-versus-source-specific capability boundaries;
- OPS-01 covers empty and known unversioned adoption, every formal v1-v4 starting schema, exact
  payload preservation, immutable/checksummed contiguous history, read-only status byte identity,
  byte-idempotent no-op migration, injected full-plan rollback, object/column drift, unknown/
  malformed/future/downgrade refusal, Registry/ProtocolTracker delegation, CLI text/JSON, and
  capability boundaries;
- OPS-02 covers exact cold/warm validation and downstream metric equivalence, unchanged raw/cache
  bytes, all six strict Parquet schemas, directory/ZIP parity, every key component, mapping/raw
  invalidation, stale/incompatible/corrupt/symlink rejection, explicit raw/cache separation,
  generated-fixture benchmark evidence, and injected write failure with no partial publication;
- OPS-03 covers core/optional dependency separation, complete adapter-capability truth, healthy
  workspace/current-registry diagnosis, duplicate target reconciliation, corrupt and permission-
  limited registry refusal, unsafe workspace declarations, cache miss/stale states, exact raw/
  cache/registry immutability, contract golden output, CLI JSON/text, and blocked exit behavior;
- demo workspace reset requires explicit confirmation.
- contribution-ledger accepted-row counts reconcile exactly;
- constrained narrative sentences cite existing finding IDs and evidence keys;
- withdrawn mock participant records do not enter aggregates;
- PDF output parses and contains the required deterministic sections.
- parameter sweeps never mutate the base snapshot, exceed declared admission limits, silently
  replace unavailable responses with zero, write through protected/symbolic destinations, or
  represent an external coordination artifact as executed.

## Fixture Policy

Synthetic fixtures are hand-auditable or have deterministic, documented generation provenance.
They live under `tests/fixtures/` and are clearly labelled synthetic. The public SUMO fixture is
larger because it preserves complete official scenario output; its exact generator command, SUMO
tag/commit, licence, hashes, and expected inventory are documented alongside it. Future private or
real-world schema fixtures must be sanitised and documented before committing.

Standalone generated workspaces are created under temporary paths during tests. They are not committed
as fixtures; the generator configuration and deterministic tests provide reproducibility.

## Standalone Product Tests

Standalone tests cover:

- deterministic synthetic generation for fixed seeds;
- different seeds changing generated records;
- generated bundles passing the existing validator;
- expected R1/R2/R3 diagnostic behavior through EvidencePacks;
- demo workspace initialise/reset/status safety;
- Typer CLI smoke tests for demo, report, and provenance commands;
- HTML escaping and no absolute path leakage in reports.

## TOS Integration Tests

The optional read-only TOS integration is tested with a tiny package generated at test time. This
preserves the supplied schema and representative contracts without copying Randy's raw files into
TrafficTwin. Tests cover:

- evaluation CSV and JSON-summary reconciliation;
- supported engine/version gating;
- NPZ member path, symlink, pickle, decompressed-size, key, and shape safety;
- source-summary metric and partial EvidencePack construction;
- deterministic R0-R8 behavior over incomplete evidence, including explicit R7/R8 insufficiency;
- bounded replay and per-arrival inspection;
- confirmed-unit labels, time/slot action joins, and RSU concurrency-pressure calculation;
- versioned source-contract serialization and launch-blocker reporting;
- aggregate provenance to the source summary row;
- registry persistence, conflict checks, and idempotent imports;
- Typer and Streamlit service/AppTest workflows.

An optional local smoke pass validates the separately checked-out package and confirms its Git
worktree remains unchanged. Raw TOS files are not test fixtures and are not committed.

## SUMO Output Adapter Tests

The import-only `ING-01` adapter is tested against
`tests/fixtures/sumo/square_public`, generated with SUMO 1.27.1 from the official square scenario.
Tests cover:

- exact fixture checksums and package fingerprint without raw-file mutation;
- completed, departed-incomplete, and never-departed trip semantics;
- typed summary parsing without relabelling occupancy as canonical traffic flow;
- malformed/unsafe XML, invalid values, duplicate identities, time order, checksum, path, manifest,
  and version rejection;
- deterministic canonical trip metrics and unavailable traffic metrics;
- machine-readable capability contract with launch and FCD disabled;
- registry idempotency, CLI flows, UI services, and Streamlit page rendering.

This is compatibility evidence for the declared public SUMO output contract. It is not evidence of
Manchester realism or Randy/VEC compatibility.

## Manifest Inference Tests

`tests/fixtures/manifest_inference/value_patterns` and `ambiguous` are small synthetic fixtures.
Tests cover exact-header/alias/distinctive-value evidence, stable complete/draft fingerprints,
published sampling bounds, explicit confirmation, edits/exclusions/unmapping, header-evidenced and
user-selected units, stale-source rejection, duplicate headers/source reuse, tied file kinds,
ordinary bundle validation after apply, CLI commands, UI services, and Streamlit rendering.

Golden projections assert both stable useful suggestions and the absence of an automatic selection
for ambiguity. They test the algorithm contract, not compatibility with an unobserved external
schema.

## Diagnostic Evaluation Limit

The synthetic fault-injection precision/recall values are implementation checks over labelled
synthetic cases. They are not evidence that R0-R5 are externally valid for Manchester, SUMO, or
Randy/VEC runs. R6 has separate deterministic synthetic grid/gap/recovery tests; these likewise do
not validate its provisional thresholds externally. R7 and R8 likewise have separate grouped and
contract-gated admission/boundary tests; neither establishes external validity. DIA-05 and DIA-06
golden/boundary/grid tests establish deterministic sensitivity behavior only, not threshold
validity or calibration. DIA-07 relationship tests establish only the declared deterministic
policy, not causal compatibility, probabilistic confidence, or external validity.

## Statistical-Study Verification

STA-01 constructed-data tests cover known positive and null paired differences, exact and
Monte-Carlo sign-flip modes, seeded bootstrap repeatability, original-unit/standardised effect
sizes, maximise/minimise interpretation, minimum support, missing/unmatched/unavailable/non-scalar
observations, duplicate keys, semantic/environment incompatibility, timestamp/input-order
stability, input immutability, and strict configuration bounds. Golden output pins a representative
known effect. CLI, registry-plan services, and Streamlit AppTest verify that interfaces delegate to
the library and retain exclusions. These tests validate method implementation, not policy or
external validity.

STA-02 constructed-data tests cover known maximise/minimise order, numerical ties and regret,
identical complete-seed denominators, missing/unavailable/duplicate endpoints, semantic and
environment incompatibility, family-signature refusal, insufficient support, deterministic
family-specific joint resampling, input-order stability, immutability, config bounds, and typed
exports. Golden output pins a representative rank/uncertainty projection. CLI, registered-plan
service, capability, and Streamlit AppTest coverage verify thin-interface delegation. These tests
do not establish equivalence, causal policy superiority, or external validity.

STA-03 constructed-data tests pin Student-t reference CDF/quantiles, a known equivalent sample,
strict margin-boundary and outside-margin failures, and an ordinary non-significant difference
that does not demonstrate equivalence. They also cover margin basis/justification/reference and
alpha validation, inherited STA-01 missing/unavailable/semantic/signature audit behavior,
insufficient support, zero-variance degeneracy, timestamp/input-order stability, input
immutability, deterministic JSON/Markdown/CSV, and artifact fingerprints. Golden, CLI,
registered-plan service, capability, synthetic-demo, and Streamlit AppTest coverage verify the
typed interface path. These tests validate method implementation only; they do not defend a real
metric margin, normality, external validity, or deployment equivalence.

STA-04 tests cover exact and inclusive absolute boundaries, the larger relative boundary, expected
zero, numerical failure, candidate/approved lifecycle, exact and compatible source policies,
internal/context mismatch, and missing/unavailable/non-scalar/non-finite/unit/implementation
evidence. Paired-study tests cover the published field allow-list and unavailable components.
Mutation/timestamp checks verify immutability and deterministic fingerprints. Golden projection,
three distinct CLI exit codes, JSON/Markdown/CSV, strict bounded parsing, registry/UI services,
synthetic demo artifacts, capability flags, and Streamlit AppTest exercise the complete typed path.
These tests validate implementation behavior; they do not justify a real tolerance or golden.

STA-05 tests pin a standard-normal critical value and known minimum pair counts, verify that the
reported integer meets target while the preceding integer does not, and cover effect-sign
symmetry plus effect, power, and alpha monotonicity. Validation covers zero effect, zero variance,
an exceeded search ceiling, finite/bounded inputs, justifications, literature references, pilot
size, synthetic labels, small/provisional qualifiers, input immutability, timestamp-normalised
fingerprints, and JSON/Markdown/CSV reconciliation. Golden, CLI exit, UI service, capability,
synthetic-demo, generated-contract, and Streamlit AppTest paths verify the thin interfaces. These
tests validate the normal-approximation implementation only; they do not defend a real target
effect/variance, guarantee achieved power, or establish exact sign-flip/TOST/N-way power.

PRO-01 tests iterate every compatible arithmetic registry entry and require its signed accepted-row
sum to equal the existing ordinary metric delta. Separate tests pin percentile lineage-only output,
incompatibility as unavailable rather than zero, both-side counts/fingerprints, JSON/CSV integrity
language, deterministic fingerprints, the generated contract, CLI formats, UI service delegation,
capability boundaries, and explicitly synthetic demo exports. They validate calculation lineage,
not causal attribution or scientific influence.

PRO-02 tests hold the existing trace DAG fixed and verify only its projection/export semantics.
They cover deterministic root neighbourhood selection, hard/default bounds, exact truncation,
timestamp-independent graph identity, limit-specific view fingerprints, safe ID preservation,
unsafe ID aliases, stable edge IDs, both disclosure profiles, local-path removal, DOT escaping,
GraphML parsing, exact golden files, CLI output, UI delegation/AppTest, capabilities, and synthetic
demo artifacts. They do not treat renderer coordinates, graph shape, or proximity as causal or
scientific evidence.

## Browser And PDF Verification

`scripts/ui_browser_audit.py` captures all 35 v0.7 routes at desktop and mobile viewports in light
and dark themes. It fails on bounded structural regressions: exact primary heading, main landmark
count, rendered Streamlit exceptions, unnamed visible controls, missing image alt attributes,
application-owned duplicate DOM IDs, and horizontal overflow. Streamlit Glide grid IDs are counted
separately. It is not a WCAG conformance audit.

PDF tests parse generated bytes. Release verification also renders the PDF pages with Poppler and
requires visual inspection for overflow, clipping, and layout defects.

The current verified repository snapshot is linked above rather than duplicated here, so a later
increment cannot leave this strategy document advertising an obsolete count. Historical browser,
Tectonic and phase-specific evidence remains in the dated audit and phase records that produced it.

Related documents:

- [Reproducibility guide](reproducibility.md)
- [Fault-injection methodology](fault_injection_methodology.md)
- [Developer guide](developer_guide.md)
- [Provenance model](provenance_model.md)
- [Standalone demo](standalone_demo.md)
- [General external-source contract](integration/external_source_contract.md)
- [Synthetic data model](synthetic_data_model.md)

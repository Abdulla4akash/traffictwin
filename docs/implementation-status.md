# TrafficTwin Implementation Status

Canonical design status: v0.5 is the approved repository design target. It incorporates the full
39-capability expansion covering import formats and SUMO outputs, temporal/grouped metrics,
statistics, R6-R8 and declarative rules, sensitivity, difference provenance, robustness tooling,
research exports, migrations, caching, doctor, and external-source contracts. All 39 catalogue
capabilities are implemented within their documented evidence-bounded v1 scope: `ING-01` through
`ING-05`, `MET-01` through `MET-06`, `DIA-01` through `DIA-07`, `STA-01` through `STA-05`,
`PRO-01` through `PRO-03`, `EXP-01` through `EXP-03`, `REP-01` through `REP-05`, and `OPS-01`
through `OPS-05`. Evidence-blocked source-specific extensions remain visibly unavailable. The
import-only SUMO output adapter has public-fixture acceptance evidence; accepted-row
difference provenance, bounded path-safe provenance graphs, and explicit report-claim provenance
completeness are implemented. The inference wizard has
confirmation-gated code, golden tests, CLI/UI workflows, and synthetic ambiguity evidence.
Inclusion in the design alone does not mark any other capability implemented.

Historical design status: v0.4 remains preserved as the original rationale and
supervisor-meeting traceability record.

Phase 0 status: approved and committed.

Phase 1 status: implemented and committed.

Phase 2 status: implemented and quality-gate checked.

Phase 3 status: implemented and quality-gate checked.

Phase 4 status: implemented and quality-gate checked.

Phase 5 status: implemented and quality-gate checked.

Phase 6 status: the evidenced read-only TOS Data boundary and `vec_env` source audit are
implemented. Evaluation summaries can be imported; instrumented arrays support unit-aware replay,
task/action inspection, and RSU active-task/backlog inspection; a versioned source contract records
field semantics, controls, execution evidence, and blockers. Full canonical conversion, canonical
RSU metrics, and launch remain blocked for the TOS/VEC package. A separate public SUMO 1.27 output
adapter now supports bounded tripinfo canonicalisation and source-specific summary inspection.

Documentation pass status: completed and quality-gate checked.

Complete product documentation status: implemented. `docs/full_product_guide.md` provides one
task-oriented entry point for installation, concepts, capability boundaries, 38 concrete use
cases, the complete UI surface, a CLI cookbook, input/output interpretation, dissertation use,
deployment, quality assurance, safety, troubleshooting, limitations, and goal-based workflows.

Registry compatibility maintenance: all registry and protocol-tracker schema access now delegates
to five ordered transactional migrations. Empty databases and known unversioned additive schemas
upgrade without payload rewrites; tampered, unknown, future, or downgrade states fail visibly.

Canonical-cache operations: accepted ordinary generic bundles can now publish six typed Parquet
canonical tables to an explicit content-addressed cache outside raw evidence. Every hit reopens and
fingerprints raw files, validates the current manifest mapping, verifies checksums/schemas/typed
rows/report/evidence/counts, and returns the exact cold result. Stale, incompatible, corrupt, and
symlinked entries are never used, deleted, or overwritten.

Replay-filter maintenance: vehicle, RSU, task-class, and incident controls now use stable session
keys, report their available option counts, clearly disable absent evidence, and apply selections
to the matching counts, corridor annotations, charts, and canonical vehicle rows.

Replay-source maintenance: Replay now lists validated top-level bundles with distinct-vehicle and
incident-record counts, resets bundle-specific clock/filter state on source changes, and prefers the
incident-capable synthetic stressed-demand bundle when the standalone demo would otherwise open on
its incident-free baseline. Vehicle and incident selections have AppTest and live-browser coverage.

Vehicle-filter interaction maintenance: the Vehicle control now uses a direct button grid with
deterministic Previous/Next wraparound, Clear, an explicit active-selection message, and visible
current-window metric cards. It avoids reliance on a long dropdown and provides immediate evidence
that vehicle observations were filtered.

Productisation Provenance Explorer status: implemented. The explorer is read-only and traces
metrics, diagnostic rule results, source rows, run metadata, metric definitions, validation
findings, EvidencePacks, DiagnosticReports, and bundle fingerprints where existing Phase 1-5
artifacts provide the links.

Standalone Product status: implemented. TrafficTwin can now create a deterministic synthetic demo
workspace, generate standard run bundles, import them through the existing registry path, compute
metrics, build EvidencePacks, evaluate diagnostics, prepare provenance traces, export
Markdown/HTML/PDF reports, and launch Streamlit without Randy/VEC, SUMO, live data, or external
services.

Product Polish & Research UX status: implemented. The Streamlit UI now includes Scenario Builder,
Experiment Planner, Experiment Manager, Reports, Search, Settings, About, improved Replay controls,
shared badges/cards, Guided Demo, and a clearer mobile-accessible Home dashboard. This is workflow
polish only; it adds no new metrics, diagnostic rules, simulator adapters, live data, launchers, ML
algorithms, or LLM behavior.

TOS Results Workbench status: implemented. The optional read-only integration now includes an
evaluation matrix, exact fleet-seed paired campaign comparison, processed-FCD logical replay,
source-specific RSU pressure/backlog summaries, full showcase task aggregation, bounded training
histories, conservative generalisation labels, a reproducibility audit, deterministic research
reports, and a self-contained aggregate atlas. These features do not change canonical metrics,
diagnostic rules, direct-launch capability, or external-integration blockers.

Independent Research Tools status: implemented and quality-gate checked. The
standalone/import-first product now includes a dedicated Triviality view, first-class experiment
EvidencePacks, R4 load-imbalance and R5 training-validation drift candidates, winner maps, a
transparent synthetic portfolio prototype, S5/S6 synthetic scenarios, incident/event authoring,
manual protocol tracking, and draft participant-evaluation materials. None of these features
enable direct launch or turn synthetic output into real-world evidence.

Advanced Research Tools status: implemented and quality-gate checked. The project now includes an
expanded severity/seed fault matrix, portfolio variability and dominance reports, checksummed
three-scenario case-study packs, complete accepted-row metric contribution ledgers, A4 PDF export,
browser screenshot/accessibility regression tooling, a non-geographic vehicle corridor replay,
synthetic-mock participant-result analysis, and a constrained non-LLM findings renderer.

v0.5 `ING-01` SUMO output adapter status: implemented. A versioned import-only adapter validates
immutable SUMO 1.27 `tripinfo.xml` and `summary.xml`, preserves raw checksums, canonicalises safe
trip fields, retains summary steps as source-specific evidence, computes deterministic trip
metrics, imports idempotently, and exposes CLI and Streamlit workflows. FCD and SUMO launch remain
explicitly unavailable. Acceptance uses the legally reusable official Eclipse SUMO square
scenario with embedded licence notices and pinned provenance.

`ING-01` quality gates: Ruff formatting/linting passed; strict mypy passed across 288 files; 274
tests passed; coverage reached 80%; the generated Pydantic schemas, CLI help, validation-code
catalogue, and SUMO source contract were regenerated; the dependency lock remained current.

v0.5 `ING-02` manifest inference status: implemented. A versioned bounded engine suggests generic
CSV file kinds, canonical fields, and header-evidenced units through exact headers, documented
aliases, and limited task vocabularies. Drafts are structurally non-executable. Explicit acceptance
or edits produce a fingerprinted `CanonicalisationManifest`; applying it to a complete metadata
template creates an ordinary confirmed `BundleManifest` for normal validation. Ambiguity, missing
units, changed source bytes, unsafe CSVs, duplicate source use, and unresolved required fields are
rejected. CLI and Streamlit workflows expose review/edit/download steps without importing or
analysing the source.

`ING-02` quality gates: Ruff formatting/linting passed; strict mypy passed across 294 files; 293
tests passed; coverage remained 80%; generated Pydantic schemas, CLI help, validation codes, and
the machine-readable inference contract were regenerated; documentation links and JSON parsed;
the dependency lock remained current.

v0.5 `ING-03` declared tabular format status: implemented. Ordinary bundle manifests explicitly
declare plain CSV, gzip-compressed CSV, or flat scalar Parquet while reusing the existing required
columns, column maps, units, raw checksums, canonical records, evidence availability, deterministic
metrics, registry import, CLI, Streamlit, and row-level provenance paths. Unsupported Parquet
types, duplicate columns, malformed input, and decoded tables over 10,000,000 bytes are rejected
with stable findings. Raw bundle identity remains the exact relative-path/raw-byte fingerprint;
golden tests establish canonical and metric equivalence without collapsing immutable evidence.

`ING-03` quality gates: Ruff formatting/linting passed; strict mypy passed across 296 source files;
305 tests passed; coverage remained 80%; directory/ZIP, raw-identity, CLI, UI-service, and
row-provenance tests passed; generated Pydantic schemas, CLI help, and validation codes were
regenerated; documentation JSON parsed; the dependency lock remained current.

v0.5 `ING-04` batch bundle import status: implemented. Explicit literal paths and globs are
expanded, resolved, deduplicated, bounded, and processed in deterministic order. Typed summaries
preserve input issues, consolidated counts, and per-bundle outcomes. Each accepted candidate uses
the ordinary single-bundle registry transaction, so invalid, conflicting, or locally failed
candidates cannot roll back or relabel valid neighbours. Existing raw identity, idempotency, and
identifier-conflict behavior is unchanged. CLI text/JSON/CSV output and Streamlit validation/import
controls use the same service; batch registration deliberately does not auto-compute metrics or
diagnostics.

`ING-04` acceptance evidence includes unit, integration, golden, and UI-service coverage plus a
published local fixture benchmark recording 9,609 source bytes, five candidates, 0.035070-second
median runtime, 1,092,623-byte maximum traced memory, and exact sequential-validation equivalence.
Ruff formatting/linting passed; strict mypy passed across 301 source files; 324 tests passed;
coverage remained 80%; generated Pydantic schemas and CLI help were regenerated; documentation
JSON parsed; the dependency lock remained current; the Streamlit batch page rendered and validated
mixed input under AppTest; a live headless Streamlit health check returned `ok`.

v0.5 `ING-05` chunked/streaming canonicalisation status: implemented. The opt-in validator reads
declared CSV, gzip-CSV, and flat scalar Parquet in ordered row/byte-bounded chunks while preserving
logical source rows, raw fingerprints, canonical conversion, evidence availability, and finding
order. Temporary disk-backed SQLite state performs exact duplicate-task and vehicle/RSU-reference
checks across chunk and file boundaries. Ordinary ingestion and its 10,000,000-byte table limit
remain unchanged. CLI, Streamlit, and Python APIs expose validation and metadata import; collected
mode exists for exact downstream equivalence but is explicitly not memory-bounded.

`ING-05` acceptance evidence includes unit, integration, golden, ZIP, CLI, UI-service, and
Streamlit AppTest coverage. A generated 75,000-task, 5,030,354-byte fixture produced exact
canonical-digest, count, validation, and evidence equivalence at 257, 1,024, and 4,096-row chunk
settings. Measured runtimes were 5.106264, 5.193257, and 5.273125 seconds versus 2.155129 seconds
ordinary; peak Python-traced memory was 2,113,760, 3,827,155, and 15,015,813 bytes versus
159,406,849 bytes ordinary. These are local implementation measurements, not city-scale or full
process-RSS claims. Ruff format/lint passed; strict mypy passed across 312 checked files; all 350
tests passed; coverage reached 80.90%; generated schemas, CLI help, and validation codes were
regenerated; documentation JSON parsed; the dependency lock remained current; Streamlit AppTest
covered the controls and the live headless health endpoint returned `ok`.

v0.5 `MET-01` time-windowed metrics status: implemented. A versioned
`WindowedMetricConfig` resolves fixed aligned half-open `[start,end)` windows over an explicit
range or the inferred aligned timestamp envelope. Tasks use arrival cohorts, trips use departure
cohorts, and infrastructure/vehicle/traffic/incident records use observation timestamps. Partial
edges are visibly included or excluded, empty windows remain visible with ordinary unavailable
metrics, and coverage means requested-range overlap rather than sampling completeness. The three
comparison definitions remain pairwise-only.

`MET-01` preserves the ordinary metric calculator, availability/reason codes, raw fingerprint,
and computation metadata while adding grid/effective bounds, coverage, partial status, source
counts, and anchor-policy provenance. All 60 current task, infrastructure, traffic, trip, energy,
fairness, and contracted spatial/per-RSU definitions declare window applicability after the later
MET-03/MET-05 extensions. CLI and Streamlit workflows expose the typed artifact;
window-specific trace and complete accepted-row ledgers use exact filtered canonical evidence.
Unit/property-style, integration, golden, format-equivalence, collected-streaming-equivalence,
UI-service, and Streamlit AppTest coverage exercise boundaries and gaps. `ADR-016` records the
semantics and [time-windowed metrics](time_windowed_metrics.md) documents usage and limitations.
R6 and recovery diagnosis were deliberately not part of the `MET-01` increment; the later
`DIA-01` section records their implementation over typed temporal evidence. Event-aligned window
recomputation remains separate. `MET-01` full quality gates passed: Ruff format/check across 318 Python files,
strict mypy across 312 source files, all 379 tests, 81% coverage, generated schemas/catalogues/CLI
help, dependency-lock validation, and source/wheel builds.

v0.5 `MET-02` complete latency percentile family status: implemented. Canonical task latency now
exposes P50, P95, and P99 through the ordinary metric collection, fixed windows, default experiment
aggregation, comparisons, reports, Run Overview, and generic provenance. All three use sorted
linear rank-`n-1` interpolation with method version `linear-rank-n-minus-1-v1` and carry the
percentile fraction, method, valid sample count, and configured minimum in metadata.

Zero latency observations remain unavailable with `NO_LATENCY_VALUES`; a default singleton equals
its sole value and carries a warning; a configured unmet `minimum_sample_size` makes percentiles
unavailable with `INSUFFICIENT_SAMPLE_SIZE` while leaving the defined mean available. Golden
baseline/variation projections prove exact P99 values, and `ADR-017` records the method and
interpretation limits. The capability manifest marks this family true only for generic canonical
bundles and false for the current SUMO/TOS contracts. Full quality gates passed: Ruff
format/check across 319 Python files, strict mypy across 313 checked files, all 385 tests in the
coverage run, 81% coverage, regenerated schemas/catalogue/CLI help, dependency-lock validation,
and source/wheel builds.

v0.5 `MET-03` contract-gated task-energy metric family status: implemented for generic and
generated-synthetic bundles that explicitly satisfy `TaskEnergyContract` v1.0. The ordinary and
fixed-window engines expose mean energy per observed task, mean energy per completed task, and
mean completed-task energy-delay product. Every result carries the exact eligibility policy,
eligible/population counts, coverage, joule/millisecond units, contract version, and semantic
fingerprint. Missing values are excluded rather than treated as zero; negative values reject the
bundle; empty eligible sets remain unavailable; partial completed-task coverage is visibly
partial; and comparisons require matching fingerprints.

Generated synthetic bundles declare the contract because their deterministic generator owns the
field semantics. Existing bundles without the declaration remain unavailable. Current SUMO and
TOS contracts explicitly report the canonical family unavailable; TOS aggregate joules per
arrival remains under its separate source-specific key. The family is exposed through the metric
catalogue, default aggregation, reports, CLI, Run Overview Energy Evidence cards, evidence packs,
whole-run/window provenance, and complete contribution ledgers. `ADR-018` records the decision.
Full quality gates passed: Ruff format/check across 323 Python files, strict mypy across 323 checked
files, all 394 tests in the coverage run, 82% coverage, regenerated schemas/catalogue/CLI help and
validation codes, dependency-lock validation, and source/wheel builds.

v0.5 `MET-04` evidence-gated operational fairness status: implemented for canonical generic and
generated-synthetic bundles with sufficient exact group evidence. The family now owns stable
vehicle-tier completion rates, their maximum disparity and Jain index, plus mean
capacity-normalised load by exact RSU, its maximum disparity and Jain index. These are operational
group-balance measures only; TrafficTwin neither stores nor infers protected, demographic,
socioeconomic, or personal attributes.

`OperationalFairnessPolicy` v1.0 requires at least two groups, at least two eligible observations
in every observed group, and complete in-scope coverage. Missing or unstable vehicle tiers,
non-positive capacity, negative/missing active-task values, under-supported groups, and all-zero
Jain inputs remain explicitly unavailable. Every result records the policy and exact group-set
fingerprints, support counts, coverage, and interpretation boundary. Pairwise scalar comparisons
require both fingerprints to match; whole-run and fixed-window calculations share the same rules.
Current SUMO and TOS contracts keep the family unavailable rather than relabelling source-specific
summary evidence. CLI, reports, aggregation, comparison, complete accepted-row provenance, the
Fairness Evidence UI page, and generated references expose the family. `ADR-019` records the
decision. R7 and its closed declarative dependency are implemented separately under ADR-023.

`MET-04` full quality gates passed: Ruff format/check across 329 Python files, strict mypy across
329 checked files, all 406 tests in the coverage run, 82% coverage, regenerated schemas/catalogue/
CLI help and validation codes, dependency-lock validation, documentation JSON parsing, and source/
wheel builds.

v0.5 `MET-05` contract-gated spatial and per-RSU breakdown status: implemented for canonical
generic and generated-synthetic bundles with explicit `TaskRsuTargetContract` and/or
`VehicleSpatialGridContract` evidence. Exact V2I execution targets now support task counts,
completion rates, and completed-observed deadline-miss rates by target RSU. Existing per-RSU
infrastructure summaries and strict capacity-normalised load groups supply the load views. A
separate named source-frame grid supplies vehicle observation counts, distinct vehicle counts, and
mean eligible speed by cell.

Per-RSU outcomes require complete non-empty V2I target coverage and exact in-scope canonical RSU
joins. Grid outputs require complete finite x/y coverage, explicit metre units, fixed origin/cell
geometry, and a named coordinate frame. Missing deadline or speed support remains partial/null.
Every output carries contract/group-set fingerprints, support, coverage, and interpretation
metadata. No nearest-RSU assignment, task-position interpolation, CRS/geographic inference, or
causal attribution is performed. Current SUMO and TOS contracts remain unavailable. The family is
exposed through whole-run/window engines, CLI, reports, complete accepted-row provenance, generated
references, capabilities, and the Spatial & RSU Evidence UI. `ADR-020` records the metric decision;
R7 now consumes only its exact target-RSU completion metric, while geographic task-outcome mapping
remains future work.

`MET-05` full quality gates passed: Ruff format/check across 335 Python files, strict mypy across
335 checked files, all 418 tests in the coverage run, 82.35% coverage, regenerated schemas/
catalogue/CLI help and validation codes, dependency-lock validation, documentation JSON parsing,
source/wheel builds, and clean diff-whitespace checks.

v0.5 `MET-06` trusted local custom metric plugin API status: implemented as an explicit
in-process library registry. Each extension declares a strict `PluginMetricContract` containing a
namespaced key, plugin/implementation versions, ordinary metric definition, exact canonical
tables/fields, complete-or-drop row policy, minimum eligible support, unit/scope, closed output
shape/type, unavailable behavior, optional canonical window anchor, and declared-input-row
provenance mapping. Invalid contracts, duplicate/core keys, mixed plugin versions, unknown fields,
and inconsistent declarations are rejected before evaluation.

The engine supplies only deep-copied declared canonical inputs, invokes each callable twice with
fresh copies, compares canonical JSON outputs, validates finite JSON-safe scalar/grouped values,
and wraps valid outputs in ordinary `MetricValue` records. Admission failures, exceptions,
unequal repeated results, invalid output, and deliberately unavailable plugin results use distinct
stable reason codes and cannot stop core or neighbouring plugins. Embedded contracts and
fingerprints support later provenance without a live registry; complete contribution ledgers list
every declared candidate/admitted input row. Scalar comparisons require equal contract
fingerprints, and windowed plugins reuse the existing half-open table filter with a declared
canonical anchor.

The API has Python whole-run/bundle/window/evidence/provenance integration and is also accepted by
the SUMO canonical-trip metric path. TOS remains unsupported because the read-only workbench does
not expose an ordinary canonical run bundle. The CLI and generated reference expose the static
trust boundary, while About states that there is no upload, dynamic module import, or sandbox.
`ADR-021` records the decision. The global core catalogue remains 63 definitions/60
window-applicable definitions; a registry extends only the computation to which it is explicitly
passed.

`MET-06` full quality gates passed: Ruff format/check across 339 Python files, strict mypy across
339 checked files, all 433 tests in the coverage run, 82.58% coverage, regenerated schemas/
catalogue/CLI help and plugin API contract, dependency-lock validation, clean diff-whitespace
checks, and source/wheel builds.

v0.5 `DIA-01` temporal degradation and recovery diagnosis status: implemented. An optional typed
`TemporalEvidence` projection attaches an existing complete `WindowedMetricSeries` to the ordinary
`EvidencePack` boundary. It retains every window ordinal, eligibility state, metric direction,
declared event context, source-series fingerprint, and its own deterministic fingerprint. Missing,
excluded, partial, low-coverage, non-scalar, unavailable, and incompatible windows are never
converted to zero and break consecutive evidence runs.

Deterministic R6 v1.0 uses an exact consecutive baseline, a direction-aware adverse delta in the
metric's own unit, a required sustained-window count, and bounded post-event recovery states. An
event is optional and researcher-declared; when supplied, it maps to the containing half-open
effective window and is never inferred from the series. R6 introduced ruleset `1.1`; the current
R7 advanced the ruleset to `1.2`; the current R8-enabled default is `1.3`. Default
thresholds are provisional synthetic-development values, and the result remains a diagnostic
hypothesis rather than a statistical drift test or causal incident attribution.

The generic canonical-bundle path exposes the feature through Python, CLI, generated contracts,
the Temporal Metrics UI, diagnostic reports, capabilities, and exact window/source lineage. The
current SUMO and TOS source-specific paths report it unavailable because they do not expose the
required compatible canonical window contract. `ADR-022` records the decision.

`DIA-01` full quality gates passed: Ruff format/check across 345 Python files, strict mypy across
345 checked files, all 448 tests in the coverage run, 82.75% coverage, regenerated schemas/
catalogue/CLI help and temporal diagnosis contract, dependency-lock validation, documentation JSON
parsing, clean diff-whitespace checks, and source/wheel builds.

v0.5 `DIA-02` operational outcome-disparity R7 and `DIA-04` declarative YAML authoring status:
implemented. A strict bounded trusted-local grammar compiles flat threshold/boolean definitions
into ordinary deterministic `RuleResult` objects over existing EvidencePack metrics. Admission
rejects unknown fields, unsafe YAML features, non-finite values, arbitrary code/imports/formulas,
dynamic keys, excessive documents/predicates, reserved core IDs, and inconsistent group metadata.
Three-valued `all`/`any` evaluation preserves missing evidence and records a stable complete-
definition fingerprint.

R7 v1.0 proves the same compiler with one explicit dimension: operational vehicle-tier completion
gap or exact execution-target RSU completion range. Both require exact compatible contracts, full
coverage, at least two groups, and per-group support. The default absolute ratio gap of `0.20` and
support of two are provisional synthetic-development configuration. Results retain alternatives,
conditional replication steps, categorical confidence, limitations, configuration, evidence
citations, and row-level provenance. They do not establish protected-attribute fairness,
discrimination, statistical significance, geography, causality, or acceptable overall performance.

The default ruleset is `1.2`. Library, CLI contract/validate/evaluate/R7 commands, generated
schemas/contracts/definitions, default reports, provenance, source capabilities, and the interactive
Fairness Evidence UI expose the implementation. Generic/synthetic sources are supported only when
their exact group contract is satisfied; current SUMO/TOS R7 capability remains false and their
partial EvidencePacks produce explicit insufficiency. `ADR-023` records the decision.

`DIA-02`/`DIA-04` full quality gates passed: Ruff format/check across 351 Python files, strict mypy
across 345 checked files, all 471 tests in the coverage run, 82.88% coverage, deterministic
regeneration of schemas/catalogues/CLI help/declarative contracts/R7 definitions, parsing of all 40
generated and golden JSON documents, dependency-lock validation, clean diff-whitespace checks, and
source/wheel builds.

v0.5 `DIA-03` R8 completed-task energy-anomaly diagnosis status: implemented. R8 v1.0 consumes
only `task.energy.per_completed_j` and `task.completed.count` from the EvidencePack boundary. It
admits the energy boundary only when the metric is available, finite, non-negative, `J/task`, under
the exact canonical v1.0 task-energy contract, completely covered, and consistent with its
completed-task denominator. Missing, partial, non-finite, mixed-unit, contract-incompatible, or
denominator-inconsistent evidence remains explicitly insufficient.

The inclusive provisional synthetic-development boundary is `1.50 J/task` with at least 10
completed tasks. A supported value at or above the boundary triggers; a high value with thin
support is conflicting; an admitted lower value does not trigger. R8 is not a statistical anomaly
test, hardware benchmark, causal diagnosis, external standard, or energy-saving recommendation.
The default ruleset is now `1.3` and includes R0–R8.

Library, CLI, generated contract/schema/catalogue/help, diagnostic reports, exact metric and
source-row provenance, generic capability, and the interactive Energy Evidence UI expose R8. The
current SUMO/TOS adapters report `energy_anomaly_diagnosis: false`; source-specific TOS aggregate
joules per arrival is never relabelled as completed-task energy. `ADR-024` records the decision.

`DIA-03` full quality gates passed: Ruff format/check across 356 Python files, strict mypy across
350 checked files, all 489 tests in the coverage run, 82.95% coverage, deterministic regeneration
of schemas/catalogues/CLI help and the R8 contract, parsing of all 42 generated and golden JSON
documents, dependency-lock validation, source/wheel builds, and the release smoke verifier.

v0.5 `DIA-05` verified single-boundary nearest-flip status: implemented for R5, R7, and R8.
`NearestFlipAnalysis` evaluates only the selected rule against the supplied EvidencePack and exact
ruleset configuration, requires the source status to be `not_triggered`, retains all discrete
pair/group/task support requirements, and lowers only the supported inclusive severity threshold
to the admitted observed value. The ordinary rule engine must verify the candidate as `triggered`
before it is returned.

The artifact records stable availability/reason states, source and candidate configurations,
units, direction, boundary inclusion, absolute delta, every unchanged discrete constraint, ties,
evidence/result/config fingerprints, source mode, and limitations. R0-R4, R6, and arbitrary
declarative rules are visibly unsupported in v1.0 because no defensible cross-unit or compound
configuration distance has been adopted. Triggered, conflicting, insufficient, invalid, disabled,
or thin-support source results are not converted into a favourable flip.

Library and CLI workflows accept bundles or saved EvidencePacks and optional complete
`RuleSetConfig` JSON. Generic/synthetic capability is conditional on eligible evidence; SUMO/TOS
manifests report `nearest_flip_analysis: false`. `ADR-025` records the implemented decision.

`DIA-05` full quality gates passed: Ruff format/check and strict mypy across 360 Python files, all
502 tests in the coverage run, 83.13% coverage, deterministic regeneration of schemas/catalogues/
CLI help and the nearest-flip contract, parsing of all 44 generated and golden JSON documents,
dependency-lock validation, source/wheel builds, and the release smoke verifier.

v0.5 `DIA-06` deterministic interactive threshold-sensitivity status: implemented for the same
contracted R5, R7, and R8 severity axes. `ThresholdSensitivityReport` retains the complete bounded
inclusive linear grid, every ordinary rule status and point configuration/result fingerprint,
source-threshold insertion, status/trigger stability, and adjacent sampled trigger-membership
intervals. A sampled interval is visibly distinct from the embedded exact DIA-05 nearest flip.

The Streamlit **Threshold Sensitivity** page delegates all evaluation to the library service,
labels provisional defaults, shows fixed support/dimension settings, and supports explicit
complete `RuleSetConfig` JSON import/export. Imported config remains in session state and exported
point configs are allowed only for exact retained grid points whose source config still matches.
The page does not change registry records, repository/package defaults, source bundles, raw
evidence, or rule configuration merely because a control changes.

R0-R4, R6, and arbitrary declarative rules remain explicit unsupported for the sweep contract.
Generic/synthetic capability is conditional on eligible evidence; current SUMO/TOS manifests
report `threshold_sensitivity_sweep: false`. `ADR-026` records the grid, retention, boundary,
fingerprint, and persistence decisions.

`DIA-06` full quality gates passed: Ruff format/check and strict mypy across 365 Python files, all
515 tests in the coverage run, 83.26% statement coverage, byte-identical generated-reference
regeneration across two consecutive runs, parsing of all 46 generated and golden JSON documents,
dependency-lock validation, source/wheel builds, the release smoke verifier, and the desktop/mobile
browser semantic audit with zero findings.

v0.5 `DIA-07` deterministic cross-rule reasoning status: implemented as a typed additive policy
over completed RuleResults. Version 1 records R1/R2 conflict only when both trigger and share exact
`task.generated.count` lineage; R1/R4 corroboration only when both trigger and share exact
`infra.utilisation.mean`; and R0 presentation suppression only for targets explicitly named in
`blocked_rules`. R0 readiness has precedence 100 and all ordinary rules have equal precedence 50.

`CrossRuleReasoningReport` retains every original result ID and timestamp-normalised fingerprint,
records source/target status, exact overlap, precedence, presentation effect, policy and provenance
fingerprints, suppressed/unclassified/unresolved IDs, warnings, and limitations. Suppression never
deletes or changes a target result, conflict selects no winner, corroboration does not raise
confidence, and no probability, causal attribution, ranking, or new recommendation is calculated.
R3, R5-R8, undeclared pairs, and arbitrary declarative rules remain explicitly unclassified rather
than inferred.

Every ordinary DiagnosticReport embeds the artifact; the constrained renderer and research report
only restate it. `diagnose cross-rule-contract` and `diagnose cross-rule` expose the contract and
artifact, while **Diagnostics & Evidence** renders the typed relationships immediately before all
retained original results. Generic/synthetic capability is conditional; current SUMO/TOS manifests
report `cross_rule_reasoning: false`. `ADR-027` records the decision.

`DIA-07` full quality gates passed: Ruff format/check across 369 files, strict mypy across 363
source files, all 528 tests in the coverage run, 83.66% statement coverage, byte-identical
generated-reference regeneration across two consecutive runs, parsing of all 48 generated and
golden JSON documents, dependency-lock validation, source/wheel builds, the release smoke verifier,
109-document local-link validation, and the desktop/mobile browser semantic audit with zero
findings.

v0.5 `STA-01` experiment-level statistical comparison status: implemented as a strict
baseline-versus-variation analysis over registered common-random-seed plans and completed
`MetricCollection` artifacts. `PairedStudyConfig` predeclares one scalar metric, objective,
algorithm/checkpoint, exact seed set, interval level, repetition counts, and resampling seed.
Eligible observations are always variation minus baseline and require exact metric, unit,
environment, source, synthetic-label, and applicable semantic-contract compatibility.

The deterministic method reports the original-unit mean paired difference, paired percentile-
bootstrap interval, exact two-sided sign-flip test through 16 pairs (seeded Monte Carlo above that),
Cohen's dz when defined, and matched-pairs rank-biserial correlation. At least three pairs are
required. Missing, unmatched, unavailable, non-scalar, duplicate, or incompatible evidence remains
in the pairing audit; no subgroup is silently selected and Cliff's delta is not misapplied as the
paired primary effect.

The `StatisticalStudy` artifact records the full plan and fingerprint, every admitted pair and
source collection fingerprint, every exclusion, method contract/version/seeds, compatibility
signature, assumptions, warnings, limitations, and a timestamp-normalised fingerprint. The CLI
provides method-contract and JSON/Markdown/CSV study exports. The Streamlit **Statistical Study**
page validates the registered experiment plan and delegates every calculation to the library.
Current SUMO/TOS manifests keep this capability unavailable. ADR-028 records the method decision.

`STA-01` acceptance evidence includes constructed known-effect/null distributions, exact and Monte
Carlo randomisation modes, bootstrap and input-order determinism, paired effect sizes, objective
interpretation, missing/duplicate/incompatible inputs, immutability, golden output, CLI, UI
services, and Streamlit AppTest.

`STA-01` full quality gates passed: Ruff format/check across 377 Python files; strict mypy across
371 source files; all 558 tests in the coverage run; 83.91% statement coverage; byte-identical
regeneration of all 18 generated reference files across two consecutive runs; parsing of all 50
generated/golden JSON documents; dependency-lock validation; source/wheel builds; release smoke;
110-document local-link validation; `git diff --check`; and the desktop/mobile browser semantic
audit, including the new Statistical Study page, with zero findings.

v0.5 `STA-02` N-way comparison and ranking status: implemented as a strict common-seed policy
ranking independently inside each selected registered scenario family. `NWayRankingConfig`
predeclares the experiment, scenario families, at least two policies, checkpoint, scalar metric,
objective, expected seed set, numerical tie tolerance, interval level, bootstrap repetitions, and
resampling seed.

Every admitted random-seed row contains exactly one compatible endpoint for every selected policy.
Missing, unavailable, non-finite, provenance-incomplete, duplicate, or incompatible endpoints
exclude that seed from every policy denominator and remain in the typed audit. Complete rows also
must share one family-wide metric/environment/semantic signature; no compatible subgroup is
silently selected. At least three complete rows are required for uncertainty.

The descriptive mean, objective-aware standard competition ranks, numerical ties, winners, and
regret are delegated to the existing `WinnerMapReport`. The N-way extension jointly resamples
complete seed rows and reports percentile mean intervals, rank frequencies, top-rank frequency,
and rank bounds. Each family derives its own deterministic seed. It performs no hypothesis test,
does not infer ties from interval overlap, and makes no equivalence, causal, deployment, or
external-validity claim.

`NWayRankingStudy` records the complete config/method/source fingerprints, embedded filtered winner
map, observations and source lineage, family audits, uncertainty, assumptions, warnings, and
limitations. CLI method-contract and JSON/Markdown/CSV workflows plus the existing **Statistical
Study** page validate the registered plan and render only typed results. Generic/synthetic
capabilities advertise support; SUMO/TOS remain explicitly unavailable. ADR-029 records the
method and [the N-way guide](n_way_ranking.md) documents use and interpretation.

`STA-02` acceptance evidence includes constructed known-order, minimise, tie, missingness,
duplicate, unavailable, semantic/environment incompatibility, thin-support, determinism,
input-order/immutability, golden, CLI, service, and Streamlit AppTest coverage.

`STA-02` full quality gates passed: Ruff format/check and strict mypy across all 383 Python files;
all 576 tests in the coverage run; 84.16% statement coverage; byte-identical regeneration of all
19 generated reference files; parsing of all 52 generated/golden JSON documents; dependency-lock
validation; source/wheel builds; release smoke; 134-document local-link validation; `git diff
--check`; and the desktop/mobile browser semantic audit, including the Statistical Study page,
with zero findings.

v0.5 `STA-03` equivalence-testing status: implemented as a strict paired-mean TOST over the exact
compatible common-random-seed cohort admitted by `STA-01`. `EquivalenceStudyConfig` predeclares
the registered baseline/variation selection, policy, checkpoint, metric, objective, seed set,
finite positive symmetric absolute margin, margin basis, written justification, optional required
literature reference, and one-sided alpha.

The service delegates pairing and compatibility to `evaluate_paired_statistical_study`, then
copies the exact observations, exclusions, signatures, input fingerprints, and source-study
fingerprint into `EquivalenceStudy`. At least three pairs and positive finite paired-difference
sample variance are required. Missing, duplicate, unavailable, incompatible, and zero-variance
cohorts retain typed insufficient, incompatible, or degenerate outcomes; nothing is imputed.

Version 1.0 tests the lower and upper practical-margin nulls with paired Student-t statistics.
Equivalence is demonstrated only when both one-sided p-values are strictly below alpha and the
corresponding `1 - 2 alpha` interval lies strictly inside the margin. Failed TOST is labelled
`equivalence_not_demonstrated`, never proof of difference. Student-t probabilities and quantiles
use a deterministic regularised-incomplete-beta implementation pinned against known references.

CLI method-contract and JSON/Markdown/CSV workflows, a third **Statistical Study** mode, capability
flags, generated schema/contract, and explicitly synthetic demo exports are implemented. Current
SUMO/TOS adapters remain unavailable. ADR-030 records the method and
[the equivalence guide](equivalence_testing.md) documents use and interpretation.

`STA-03` acceptance evidence covers known equivalence, a margin-boundary and outside-margin
effect, ordinary non-significant-but-not-equivalent behavior, Student-t references, strict config
and margin provenance, inherited missing/duplicate/incompatible audits, insufficient and
zero-variance support, determinism, immutability, golden output, CLI, service, capability, demo,
and Streamlit AppTest paths.

`STA-03` full quality gates passed: Ruff format/check and strict mypy across all 389 Python files;
all 603 tests in the coverage run; 84.31% statement coverage; byte-identical regeneration of all
20 generated reference files; parsing of all 54 generated/golden JSON documents; dependency-lock
validation; source/wheel builds; release smoke; 136-document local-link validation; and `git diff
--check`. The desktop/mobile browser semantic audit, including the Statistical Study page, passed
with zero findings.

v0.5 `STA-04` regression-gate status: implemented for completed run-level `MetricCollection`
artifacts, including ordinary validated-bundle computation and registered collections, plus
completed STA-01 `StatisticalStudy` JSON artifacts. `RegressionGoldenContract` schema version 1.0
records a stable ID/version/description, candidate or approved status, approver/note, exact or
compatible-context source policy, typed compatibility context, created-from subject fingerprint,
and one or more unique finite scalar assertions.

Each assertion records expected value, unit, metric implementation version where applicable, and
finite non-negative absolute and relative tolerances. Method version 1.0 admits an assertion when
`abs(actual - expected) <= max(absolute_tolerance, relative_tolerance × abs(expected))`, including
boundary equality. A relative tolerance contributes zero when expected is zero. TrafficTwin does
not infer or widen tolerances.

Metric gates require internally consistent run context, a non-empty input fingerprint, exact
metric key, available finite scalar status, and matching collection/unit/implementation versions.
Paired-study gates require available STA-01 status and matching schema/method/config,
compatibility-signature, unit, and synthetic context; only the nine published stable scalar fields
are admitted. Exact-source gates match the source fingerprint or full study input map;
compatible-context gates permit new sources only after typed context checks and carry a warning.

Candidate goldens and missing, unavailable, partial, invalid, non-finite, non-scalar,
unit/version/context/source-incompatible evidence produce `unavailable`. Complete scalars outside
tolerance produce `failed`; only a complete all-pass assertion set produces `passed`. Unavailable
has overall precedence so incomplete evidence cannot be hidden. JSON is the primary CI artifact;
Markdown/CSV reconcile with it, and exit codes are pass `0`, fail `1`, unavailable `2`.

CLI method/golden/gate commands, the fourth **Statistical Study** mode with uploaded immutable
goldens, capability flags, generated schema/contract/help, explicitly synthetic demo golden/gate,
and Python/service exports are implemented. SUMO/TOS source-specific manifests remain unavailable.
ADR-031 records the method and [the regression-gate guide](regression_gates.md) documents review,
CI use, source policies, and interpretation.

`STA-04` acceptance evidence covers exact and inclusive boundaries, larger relative tolerance,
zero expected values, numerical failure, candidate approval blocking, context/source policy,
missing/unavailable/non-scalar/non-finite/unit/version handling, paired-study field admission and
component unavailability, input immutability, timestamp-normalised fingerprints, golden projection,
three exit codes, Markdown/CSV, registry/UI services, demo, capability, and Streamlit AppTest paths.

`STA-04` full quality gates passed: Ruff format/check and strict mypy across all 395 Python files;
all 631 tests in the coverage run; 84.39% statement coverage; byte-identical regeneration of all
21 generated reference files; parsing of all 56 generated/golden JSON documents; dependency-lock
validation; source/wheel builds; release smoke; 138-document and 925-local-link validation; and
`git diff --check`. The desktop/mobile browser semantic audit, including the Statistical Study
page, passed with zero findings.

v0.5 `STA-05` power-analysis status: implemented as a prospective two-sided paired-mean normal-
approximation planning helper. `PowerAnalysisConfig` predeclares the metric and original unit,
signed variation-minus-baseline target effect, prospective paired-difference variance, alpha,
target power, separate effect/variance bases, written justifications, required literature
references, pilot size when applicable, explicit synthetic state, and a bounded common-seed search.

Method version 1.0 treats the planning variance as fixed and known, evaluates both normal rejection
tails, and uses deterministic binary search to return the smallest integer common-seed count whose
approximate power meets the target. The artifact records achieved power, the preceding count/power
when applicable, and twice the pair count as total baseline-plus-variation policy runs. The signed
effect remains in provenance while two-sided power uses its magnitude.

Every artifact is labelled `planning_aid_not_a_guarantee`. Pilot or planned counts below 30,
synthetic inputs, and provisional inputs receive additional typed labels and warnings. A zero
target effect, non-positive variance, or target not reached by the declared maximum produces a
typed unavailable reason. Invalid non-finite/bounded inputs, missing references/pilot sizes, and
unlabelled synthetic bases are rejected; nothing is imputed or represented as a false zero.

The implementation deliberately does not calculate observed post-hoc power, automatically copy an
effect/variance from completed results, claim exact power for STA-01 sign flips or STA-03 TOST,
model N-way/multiplicity/attrition/sequential designs, launch simulations, or guarantee achieved
power. ADR-032 records the method and [the power-analysis guide](power_analysis.md) documents use,
interpretation, provenance, and limitations.

CLI method/analysis commands, the fifth **Statistical Study** mode, generic capability support,
SUMO/TOS unavailability, generated schema/contract/help, Python/service exports, and explicitly
synthetic demo JSON/Markdown/CSV are implemented. Acceptance evidence covers known normal
quantiles/sample size, minimum-bound verification, sign symmetry, effect/power/alpha monotonicity,
zero-effect/variance/ceiling unavailability, input bases/references/pilot/synthetic validation,
labels, determinism, immutability, timestamp-normalised fingerprints, golden output, CLI exits and
formats, service, capability, demo, and Streamlit AppTest paths.

`STA-05` full quality gates passed: Ruff format/check and strict mypy across all 401 Python files;
all 663 tests in the coverage run; 84.53% statement coverage; byte-identical regeneration of all
22 generated reference files; parsing of all 58 generated/golden JSON documents; dependency-lock
validation; source/wheel builds; release smoke; 140-document and 950-local-link validation; and
`git diff --check`. The desktop/mobile browser semantic audit, including the Statistical Study
page, passed with zero findings.

v0.5 `PRO-01` difference-provenance status: implemented as a separate typed extension of the
complete accepted-canonical-row eligibility ledgers. It delegates compatibility and the ordinary
variation-minus-baseline delta to the existing metric comparison service, then retains every
baseline and variation candidate row, inclusion decision, source locator, canonical value, input
fingerprint, synthetic label, side summary, finding, reason code, grouping, and limitation.

A closed v1.0 arithmetic registry covers direct scalar counts, sums, means, and rates whose run
values can be reconstructed from accepted-row terms. Baseline terms receive a negative sign and
variation terms a positive sign; every arithmetic report verifies the signed sum against the
ordinary delta at `1e-12` relative/absolute tolerance. Percentiles, extrema, distinct counts,
state-machine episode metrics, grouped/fairness/spatial aggregates, and plugins without an admitted
formula expose eligible lineage without weights when a scalar comparison is available. Mapping-
valued or incompatible comparisons remain typed unavailable, never false zero or implicit
flattening.

Every JSON report and CSV row carries a mandatory non-causality statement. The artifact and ADR-033
use contributor, eligible lineage, and arithmetic contribution terminology; reconciliation never
claims a row, vehicle, RSU, incident, or variation caused the observed difference. Generic
imported/synthetic capability is true; current SUMO/TOS contracts remain false.

Library/query APIs, `provenance difference-contract` and `difference-contributors`, the **What-if
Compare** difference-provenance view, JSON/CSV downloads, generated schema/contract/help, exact
golden projection, and explicitly synthetic demo exports are implemented. Acceptance evidence
covers every comparable admitted formula, changing denominators, percentile lineage-only behavior,
incompatibility, deterministic fingerprints, exports, CLI, service, capability, and demo paths.

`PRO-01` full quality gates passed: Ruff format/check across all 404 Python files; strict mypy
across all 404 checked files; all 682 tests in the coverage run; 85% statement coverage;
byte-identical regeneration of all 23 generated reference files; parsing of all 60 generated and
golden JSON documents; dependency-lock validation; source/wheel builds; release smoke;
141-document and 980-local-link validation; and `git diff --check`. The desktop/mobile browser
semantic audit, including the new Comparison page, passed with zero findings.

v0.5 `PRO-02` provenance-graph export/view status: implemented as a separate bounded projection of
the existing `ProvenanceTrace` DAG. It does not read source paths, recalculate metrics, evaluate
rules, or invent relations. Deterministic root-centred undirected breadth-first selection retains
the root and nearby incoming/outgoing context while every retained edge keeps its original
direction. Defaults are 120 nodes/240 edges and public hard maxima are 500/2,000; every view
publishes exact total, retained, omitted, and truncation state.

Safe trace node IDs remain unchanged; path-bearing IDs receive deterministic aliases. Exported
edges receive stable hash-based IDs, and graph identity excludes volatile trace/node timestamps and
does not change with view limits. The default `safe` profile recursively redacts POSIX, Windows,
home-relative, and file-URI local paths. `structure_only` additionally removes descriptions,
attributes, source references, and edge descriptions. Neither profile is presented as complete
anonymisation, and renderer layout is not treated as deterministic evidence.

The library emits escaped deterministic DOT and typed GraphML, with parser and exact golden
coverage. `provenance graph-contract` publishes the method boundary; `provenance export` accepts
DOT/GraphML, limits, and disclosure profile. Direct metric/rule/run/TOS trace commands accept the
two graph formats with safe defaults. The **Provenance Explorer** renders the same typed bounded
view with limits, omission/redaction summaries, node inspection, and DOT/GraphML downloads. The
synthetic demo exports completion-metric graphs. Generic and TOS trace capabilities advertise
support; the current SUMO contract remains false because it has no provenance-trace entry point.

ADR-034, the graph-export guide, generated Pydantic schemas/CLI help/contract, capability manifests,
security/reproducibility/limitations guidance, architecture, traceability, demo instructions, and
tests describe the same v1.0 boundary.

`PRO-02` full quality gates passed: Ruff format/check across all 407 Python files; strict mypy
across all 407 checked files; all 694 tests in the coverage run; 85% statement coverage;
byte-identical regeneration of all 24 generated JSON references; parsing of all 63 generated,
documentation, and golden JSON documents; dependency-lock validation; source/wheel builds;
release smoke; 134-document and 1,003-local-link validation; and `git diff --check`. The
desktop/mobile browser semantic audit, including the Provenance Explorer graph view, passed with
zero findings.

v0.5 `PRO-03` provenance-completeness status: implemented over exact typed claim inventories
shared by deterministic report builders and provenance queries. Supported `run` and `diagnostics`
templates include selected metric results and all rule results; `comparison` includes every
selected typed metric comparison; `full` rebases run and optional comparison claims to unique
report-local IDs. Unavailable results remain in the denominator. Presentation/narrative,
identity/reproduction metadata, validation/evidence inventory, and comparison context are visible
named exclusions rather than silently ignored text.

Each claim is classified `source_row_complete`, `aggregate_only`, or `unavailable`. Complete means
an available result with non-empty, reconciled accepted-canonical-row ledgers and valid logical
source locators. Rules additionally require all cited metric dependencies complete and no missing
evidence; comparisons require complete ledgers on both sides under PRO-01. Directed trace depth is
published separately so one sampled source-row node cannot stand in for complete population
coverage. The unweighted score counts only complete claims; aggregate-only/unavailable receive
zero. A zero denominator publishes null and `no_claims`, never a perfect score.

The library publishes typed models, timestamp-independent fingerprints, a machine-readable method
contract, and complete JSON/CSV inventories. CLI commands cover run-like and comparison reports.
The Provenance Explorer and Comparison pages show all claims with counts, denominator/exclusion
rules, and downloads through thin services. Synthetic demo initialization exports run and
comparison artifacts. Generic/import-first capability is true; current SUMO and TOS manifests are
false because they do not expose this exact typed report-claim query.

Acceptance evidence includes exact baseline/partial/comparison/full reconciliation, unavailable-
retention and no-claims tests, timestamp-stability checks, an all-claim golden projection, CLI/CSV,
UI service/AppTest, capability, report-builder, and demo coverage. ADR-035 and the provenance-
completeness guide publish the exact method and interpretation boundary.

`PRO-03` full quality gates passed: Ruff format/check across all 411 Python files; strict mypy
across all 411 checked files; all 714 tests in the coverage run; 85% statement coverage;
byte-identical regeneration of all 25 generated JSON references; parsing of all 65 generated,
documentation, and golden JSON documents; dependency-lock validation; source/wheel builds;
release smoke; 146-document and 1,022-local-link validation; and `git diff --check`. The
desktop/mobile browser semantic audit, including the PRO-03 Provenance Explorer and Comparison
views, passed with zero findings.

v0.5 `EXP-01` parameter-sweep-composer status: implemented over one strict
`SyntheticScenarioConfig` or `ScenarioSeed` base and a closed scalar parameter catalogue. The
complete Cartesian grid is rejected above four axes, 16 values per axis, or 256 points; local
response selection is limited to 16 known core metrics. Per-path value bounds and a 2,000,000
complete local declared-row limit prevent extreme values from bypassing the grid bound. Every
derived config/seed passes its
ordinary schema before output replacement, and request/base/point/seed/bundle/result fingerprints
retain full parameter provenance.

`seed_snapshots` writes parent-linked derived seeds. `local_synthetic_bundles` runs only the
labelled TrafficTwin deterministic synthetic generator, ordinary bundle validation, and ordinary
core metric engine. `external_run_requests` writes coordination artifacts with
`execution_status=not_executed`, `direct_launch_supported=false`, and null launcher/command. It
does not run Randy, VEC/TOS, SUMO, training, or another external simulator. All modes remain
`synthetic_evaluation=true`.

Local response CSV rows repeat every axis assignment plus metric status/value/unit/reasons and
seed/bundle fingerprints. Only finite numeric core-metric values enter the numeric response;
mapping/non-numeric values remain explicitly unavailable, while missing/invalid evidence is never
zero-filled. Seed-only/external modes have an explicit empty response surface. Transactional
materialisation replaces only the exact declared destination and only with explicit overwrite;
empty, symbolic-link, current/home/root, and current/home ancestor destinations are rejected
before expansion; the base and raw inputs are not mutated.

The public library contract, `experiment parameter-sweep-contract` and `parameter-sweep` CLI,
thin Parameter Sweep page, request/result JSON, response CSV, example request, generated schemas,
and ADR-036 expose the same boundary. Acceptance evidence covers Cartesian determinism, limits,
invalid-point rejection before writes, base immutability, local bundle validation/metrics,
value/row-budget rejection, non-numeric unavailability, unexecuted external artifacts,
overwrite/symlink/YAML behavior, CLI, UI
service/AppTest, capability state, and exact JSON/CSV goldens.

`EXP-01` full quality gates passed: Ruff format/check and strict mypy across all 417 Python files;
all 734 tests in the coverage run; 85% statement coverage; byte-identical regeneration of all 26
generated JSON references; parsing of all 67 generated, documentation, and golden JSON documents;
dependency-lock validation; source/wheel builds; release smoke; 148-document and 1,064-link
validation; `git diff --check`; and a desktop/mobile browser semantic audit that now includes the
Parameter Sweep page and reported zero findings.

v0.5 `EXP-02` scenario-mutation-operator status: implemented for one ordinary-valid parent bundle
explicitly labelled synthetic/evaluation and one closed mutation per derived copy. Version 1
supports deterministic seeded row dropout over any declared table, bounded common-delta timestamp
jitter over declared seconds fields, and exact RSU infrastructure-row removal. Target mutation is
limited to uncompressed CSV; gzip/Parquet targets, arbitrary predicates/expressions, multiple
operators in one request, imported real-evidence labels, and confirmation-gated inferred manifests
remain explicitly unsupported.

Every request records a complete parent-line change ledger with before/after row fingerprints and
exact jitter field values, plus changed-file checksums and row counts. Request, plan, parent bundle,
derived bundle, and result fingerprints are deterministic and generation-time independent. The
derived seed links to its parent; the derived manifest uses `synthetic_mutation` and synthetic
execution labels with recomputed checksums. RSU removal retains task rows and target IDs unchanged,
so ordinary validation/availability exposes missing target evidence rather than inventing
rerouting, rescheduling, retraining, or policy behavior.

Materialisation reads directory/ZIP parents without mutation, rejects symbolic links plus protected
or parent-overlapping destinations, builds a bounded temporary sibling copy, validates the derived bundle through the
ordinary import-first path, verifies its planned fingerprint, and only then replaces the exact
destination with rollback-preserving explicit overwrite. Hard limits cover request size, source files/bytes, target
rows, changed-row ledger size, and jitter magnitude.

The public library contract, `experiment mutation-contract` and `mutate-scenario` CLI, thin
Scenario Mutations page/services, request/result JSON, example request, generated schema/contract,
guide, and ADR-037 expose the same boundary. Acceptance evidence covers all three operators,
determinism, exact changes, timestamp invariants, parent immutability, ZIP equivalence, admission
and workload limits, protected/symbolic paths, source/destination separation, failed-publication
rollback, CLI, UI service/AppTest, source-specific capability denial, ordinary validation, and an
exact golden manifest projection.

`EXP-02` full quality gates passed: Ruff format/check and strict mypy across all 423 Python files;
all 752 tests in the coverage run; 85% statement coverage; 92% coverage for the mutation core;
byte-identical regeneration of all 27 generated JSON references; parsing of all 69 generated,
documentation, and golden JSON documents; dependency-lock validation; source/wheel builds; release
smoke; 149-document and 1,064-link validation; `git diff --check`; a real CLI-to-validation-to-
metrics smoke run; a two-step parent-linked mutation-chain smoke run; and a desktop/mobile browser
semantic audit including Scenario Mutations with zero findings.

v0.5 `EXP-03` measurement-noise-and-dropout status: implemented as an optional layer inside the
existing deterministic standalone synthetic generator. Version 1.0 admits only a separately seeded
bounded-uniform model over generated vehicle source-frame position/speed, traffic speed/count, and
infrastructure utilisation/queue measurements. Per-table exact hash-ranked row dropout is limited
to infrastructure, vehicle, and traffic observation streams, capped at 0.95, and always retains at
least one generated row.

Every field and row choice derives from SHA-256 over versioned method inputs rather than global
random state. Noise axes are independent; dropout precedes noise; configured bounds and physical-
domain clamps are enforced. Tasks, trips, incidents, timestamps, decisions, completion, latency,
routing, targets, and energy remain the clean generator outcomes. The feature is explicitly a
synthetic software-robustness fixture, not a calibrated sensor/network/traffic model or external
simulation.

The full strict configuration, field bounds/units/counts/error extrema, exact dropout reconciliation
and selection identities, mandatory warnings/limitations, and fixed synthetic/not-calibrated/raw-
unchanged flags are embedded in `manifest.yaml`. Semantic validation rejects missing, extra,
duplicate, inconsistent, or re-fingerprinted altered audits. Bundle/run IDs include the impairment
configuration fingerprint; a disabled model preserves previous bytes and identities.

The library, `synthetic measurement-contract` and `synthetic generate-config` CLI, Scenario Builder
controls/services, runnable YAML example, generated schemas/contract/help, golden known result,
guide, and ADR-038 expose the same boundary. Synthetic output publication is now transactional and
rejects protected or symbolic-link destinations. Acceptance evidence covers determinism, axis
isolation, seeds, bounds, clamps, exact retain-one dropout, untouched outcome tables, stream
admission, semantic/fingerprint tampering, disabled compatibility, capabilities, safe overwrite,
CLI, UI service/AppTest, ordinary validation/metrics, and an exact golden audit projection.

`EXP-03` full quality gates passed: Ruff format/check across all 429 Python files; strict mypy
across all 423 configured source/test files; all 771 tests in the coverage run; 86% statement
coverage, including 93% for the measurement domain contract and 96% for the impairment engine;
byte-identical regeneration of all 28 generated JSON references; parsing of all 71 generated,
documentation, and golden JSON documents; dependency-lock validation; source/wheel builds; release
smoke; 151-document and 1,089-link validation; `git diff --check`; and a real
configuration-to-generation-to-validation-to-63-metric CLI smoke run. The desktop/mobile browser
semantic audit included Scenario Builder with zero findings, and a separate interactive browser
check confirmed that the `EXP-03` enable control plus noise and dropout inputs are editable.

v0.5 `REP-01` LaTeX-research-export status: implemented as a renderer-only boundary over existing
typed metric, comparison, STA-01 statistical-study, and diagnostic artifacts. Each projector
creates one bounded `ResearchExportProjection`; its canonical SHA-256 fingerprint is embedded in
the escaped `.tex` table and optional SVG/PDF figure so the paired outputs remain reconcilable.
The exporter performs no metric, comparison, statistical, confidence, diagnosis, or prose
calculation.

LaTeX fragments use standard LaTeX2e table constructs and escape every special character. SVG is
self-contained and script-free; PDF uses invariant ReportLab output. Numeric figures use signed
linear bars with a visible non-favourability warning. Rule figures preserve exact categorical
statuses without probability conversion. The versioned limits are 200 rows, 8 columns, 160
characters per cell, and 64 figure entries, with visible truncation warnings.

Every rendering states synthetic, imported/non-synthetic, or unresolved source mode. Absolute
POSIX and Windows paths are reduced to basename-only local-path markers while web URLs remain
intact. Diagnostic projections use the stable EvidencePack identity rather than the evaluation-
clock-dependent report ID. Exact-file publication validates `.tex`/`.svg`/`.pdf` suffixes, stages
sibling files, requires explicit overwrite, refuses duplicate and symbolic-link targets, and
returns path-free checksummed receipts.

The public library, `report latex-contract`, `latex-metrics`, `latex-comparison`, `latex-study`, and
`latex-rules` commands, Reports-page UI/service, generated schemas/contract/help, exact LaTeX/SVG
goldens, usage guide, and ADR-039 expose the same boundary. Focused acceptance evidence currently
covers all four projectors, escaping/redaction, bounds and invalid states, byte-deterministic
SVG/PDF, a real minimal Tectonic compile, checksums/overwrite/symlink safety, CLI workflows, and
Streamlit service/AppTest controls.

`REP-01` full quality gates passed: Ruff format/check across all 434 Python files; strict mypy
across all 428 configured source/test files; all 789 tests in the coverage run; 86% statement
coverage, including 92% for the LaTeX/static-figure export core; byte-identical regeneration of
all 29 generated JSON references across two consecutive runs; dependency-lock validation;
source/wheel builds; release smoke; a real minimal Tectonic compile; CLI export smoke checks; and
`git diff --check`. The desktop/mobile browser semantic audit included Reports and passed with zero
findings; an interactive browser check also generated a comparison table and PDF successfully.

v0.5 `REP-02` analyst-annotation status: implemented as a separate append-only audit stream over a
closed typed artifact-reference catalogue. Registry-resident targets are checked before append;
generated diagnostic/comparison/study/research-report targets remain explicit detached references
and do not fabricate stored artifacts. Optional exact SHA-256 target fingerprints coexist with
unbound identity-level notes.

SQLite assigns monotonic sequences and database triggers reject `UPDATE` and `DELETE`. Content-
bound annotation IDs cover target, author label, exact note, human decision label, and UTC time.
History reads are ascending, bounded, paginated, and fingerprinted. Reports declare allowed
annotation targets, include both general and matching exact-version notes, and refuse rather than
silently truncate an oversized history. Attached annotations remain outside computed sections,
typed claim references, metrics, rules, provenance, availability, and scientific fingerprints.

The public contract/models, registry API, `registry annotation-contract`, `annotation-add`, and
`annotation-list` commands, optional annotated report CLI, Reports-page UI/service, distinct
escaped Markdown/HTML/PDF rendering, generated schemas/help/contract, ordered golden history,
usage guide, and ADR-040 expose the same boundary. Acceptance evidence covers validation,
stored/detached targets, matching, ordering/pagination, update/delete guards, content identity,
claim neutrality, renderer safety, CLI workflows, and Streamlit service/AppTest controls.

`REP-02` full quality gates passed: Ruff format/check across all 440 Python files; strict mypy
across all 434 configured source/test files; all 800 tests in the coverage run; 86% statement
coverage, including 94% for the annotation contract and 85% for report attachment; byte-identical
regeneration of all 30 generated JSON references across two consecutive runs; parsing of all 72
generated/golden JSON documents; dependency-lock validation; source/wheel builds; release smoke;
156-document and 1,132-local-link validation; and `git diff --check`. The desktop/mobile browser
semantic audit included Reports and passed with zero findings.

v0.5 `REP-03` structured-report-diff status: implemented as a deterministic compatibility-gated
comparison over typed `ResearchReport` payloads before rendering. Run, diagnostics, comparison,
and full report builders now publish one `ReportClaimSnapshot` beside every scientific claim
reference. Metric snapshots preserve typed status/value/unit/scope/version/dimensions; rule
snapshots preserve categorical machine status/confidence, evidence keys, typed observations,
missing-evidence keys, and scalar metadata without hypothesis/recommendation/finding prose;
comparison snapshots preserve their existing typed values, deltas, direction, status, unit, and
reason codes.

The comparator requires matching payload schema, report type, synthetic/imported source mode,
claim-denominator definition, supported type, and complete reference/snapshot inventories.
Incompatible pairs return a typed unavailable artifact with stable codes. Compatible pairs use
report-independent claim keys and canonical recursive JSON Pointer changes to classify claims and
sections as unchanged, added, removed, changed, or unavailable. Matching narrative-only sections
are unavailable with `NO_TYPED_CLAIMS`; their bodies are not compared. Scientific fingerprints
exclude titles, timestamps, source display references, warnings, section bodies, claim labels,
exclusions, commands, annotation targets, and analyst annotations.

The public contract/models/comparator/parser/fingerprints, structured `.json` report output,
`report diff-contract` and `report diff` commands, complete JSON plus non-causal Markdown exports,
Reports-page UI/service, generated schemas/help/contract, exact golden diff, usage guide, and
ADR-041 expose the same boundary. Acceptance evidence covers builder inventory, renderer/prose/
annotation exclusion, real typed metric changes, all five classifications, unavailable evidence,
incompatible types/source modes, duplicate and byte bounds, CLI workflows, and Streamlit
service/AppTest controls.

`REP-03` full quality gates passed: Ruff format/check across all 445 Python files; strict mypy
across all 439 configured source/test files; all 812 tests in the coverage run; 86% statement
coverage, including 87% for the structured-diff engine and 100% for typed claim projection;
byte-identical regeneration of all 31 generated JSON references across two consecutive runs;
parsing of all 74 generated/golden JSON documents; dependency-lock validation; source/wheel
builds; release smoke; 158-document and 1,151-local-link validation; and `git diff --check`. The
desktop/mobile browser semantic audit included Reports and passed with zero findings.

v0.5 `REP-04` one-page-executive-summary status: implemented as a deterministic renderer
projection over one saved compatible typed `ResearchReport`. The existing REP-03 admission gate
requires supported schema/type/source mode/denominator and a complete claim inventory before the
summary can be built. Exact total, available, unavailable, and per-kind claim counts are published
with the number outside the five-highlight bound.

The closed quota policy selects at most two triggered rules, two available directional
comparisons, one unavailable claim, and one remaining rule before filling unused slots from
available metrics, remaining comparisons/rules, and other claims; earlier choices consume the
shared five-slot capacity and all ties use scientific claim keys. Selected claims preserve machine
status, availability, bounded typed display, units, reason codes, IDs, and exact scientific-payload
fingerprints. The projector does not rank importance or desirability and performs no metric,
diagnostic, comparison, causal, or LLM calculation.

Every output includes three mandatory interpretation warnings plus every source warning, all exact
top-level limitations, source mode, complete-payload/scientific fingerprints, a relative source
report link, and one relative claim link per highlight. Absolute source display paths are redacted.
Analyst annotations are excluded. Inputs beyond 100 warnings or limitations are refused rather
than shortened. JSON, Markdown, self-contained print HTML, and invariant A4 PDF use the same typed
projection. PDF page count is verified after layout and any multi-page result is refused instead
of removing caveats.

The public models/contract/projection/renderers, `report executive-contract` and `report executive`
commands, Reports-page UI/service, generated schema/help/contract, exact golden projection, usage
guide, and ADR-042 expose the same boundary. Acceptance covers selection, reconciliation,
retention, escaping, path redaction, links, incomplete inventory, deterministic fingerprint/PDF,
explicit overflow refusal, all four CLI formats, complete UI downloads, Streamlit controls, and a
Poppler-rendered visual inspection of the final one-page A4 layout.

`REP-04` full quality gates passed: Ruff format/check across all 451 Python files; strict mypy
across all 445 configured source/test files; all 824 tests in the coverage run; 86% statement
coverage, including 92% for the executive projection and 95% for the one-page PDF renderer;
byte-identical regeneration of all 32 generated JSON references across two consecutive runs;
parsing of all 76 generated/golden JSON documents; dependency-lock validation; source/wheel
builds; release smoke; 160-document and 1,169-local-link validation; and `git diff --check`. The
desktop/mobile browser semantic audit included Reports and passed with zero findings. A baseline
PDF was additionally rendered through Poppler, confirmed as A4/page 1 of 1, and visually inspected
with no clipping, overlap, footer, hierarchy, or legibility defects.

v0.5 `REP-05` full-text-registry-search status: implemented as a deterministic on-demand lexical
projection over six closed categories: findings, append-only annotations, report metadata/text,
runs, experiments, and evidence references. Existing SQLite state is opened with `mode=ro` and
immutable mode, and `PRAGMA query_only=ON`; the engine never initialises, migrates, updates, creates
SQLite sidecar state, or persists an FTS index.
Report inspection is restricted to sorted direct non-symlink files under `workspace/reports`, with
closed text formats, PDF metadata-only handling, byte/file/document ceilings, and visible skips.

Unicode NFKC case-folded unique terms use AND matching. A published integer-only score weights
typed references, titles, metadata, and text; exact/prefix/contained phrases and exact/prefix/
substring terms use fixed multipliers. Stable score/category/title/reference ties produce the same
rank and fingerprint for unchanged inputs. Absolute POSIX, Windows, home-relative, and file-URI
paths are redacted before matching and snippet construction, so local path terms cannot affect
results or leak through output. Rank is lexical relevance only, not scientific importance,
confidence, severity, causality, or approval.

The public models/contract/search/fingerprint, `registry search-contract` and `registry search`
commands, Search-page category/limit/count/result controls, thin UI service, generated schemas/help/
contract, usage guide, and ADR-043 expose the same boundary. Acceptance evidence covers all six
categories, exact deterministic ordering, category restriction, query/result/report/candidate
bounds, count reconciliation, malformed requests, database byte identity, path redaction before
matching, symlink/oversize refusal, CLI JSON/text, capability manifests, and UI service/controls.

`REP-05` full quality gates passed: Ruff format/check across all 455 Python files; strict mypy
across all 449 configured source/test files; all 841 tests in the regression suite; 86% statement
coverage, including 92% for the registry-search engine; byte-identical regeneration of all 33
generated JSON references across two consecutive runs; parsing of all 77 generated/golden JSON
documents; dependency-lock validation; source/wheel builds; release smoke; 162-document and
1,183-local-link validation; and `git diff --check`. The desktop/mobile browser semantic audit now
includes Search and passed with zero findings; its REP-05 desktop capture was visually inspected
with clear scope, query, category, limit, and empty-result guidance and no clipping or overlap.

v0.5 `OPS-01` registry-schema-migration status: implemented as five contiguous SQLite versions
covering core registry objects, import/analysis artifacts, experiment protocol tracking,
experiment EvidencePacks, and append-only analyst annotations. `PRAGMA user_version` is
authoritative and every applied migration receives one immutable name/checksum/timestamp ledger
row. `Registry.initialize()` and `ProtocolTracker.initialize()` now use this single schema owner;
the former independent additive scripts have been removed.

One `BEGIN IMMEDIATE` transaction contains the complete pending ordered plan, ledger records,
version advances, per-version object/type/column validation, and final SQLite `quick_check`. Any
failure rolls back the whole invocation. Empty databases, formal versions 1–4, and recognised
unversioned repository-era additive shapes are admitted. Existing payload columns remain
byte-identical; unknown objects, malformed known tables, ledger gaps/drift, future versions, and
downgrades fail closed.

The public models/contract/status/migrate functions, `registry migration-contract`, `registry
migration-status`, `registry migrate`, updated `registry init`/`inspect`, capability manifest,
generated schema/help/contract, usage guide, and ADR-044 expose the same boundary. Acceptance
evidence covers every historical starting version, unversioned adoption, row preservation,
read-only status byte identity, byte-idempotent no-op migration, injected full-plan rollback,
immutable ledger enforcement, checksum sensitivity, malformed/unknown/future refusal, CLI JSON/
text behavior, and ordinary registry/protocol compatibility.

`OPS-01` full quality gates passed: Ruff format/check across all 459 Python files; strict mypy
across all 453 configured source/test files; all 860 tests; 86% statement coverage, including 92%
for the registry-migration engine; byte-identical regeneration of all 34 generated JSON references
across two consecutive runs; parsing of all 79 generated/golden JSON documents; source/wheel
builds; dependency-lock validation; release smoke; 164-document and 1,199-local-link validation;
and `git diff --check`. OPS-01 changes no Streamlit page; the existing desktop/mobile semantic
audit remains green with zero findings.

## Repository Assessment

Workspace root inspected: repository parent workspace

TrafficTwin project root: `diss/`

Git repository: initialised inside `diss/` on branch `main`.

Canonical product specification: `docs/traffictwin-design-v0_5.md`

The historical v0.4 design and `../XITS/` notes remain unchanged as research material. They are
not active implementation blockers for the current implementation or approved v0.5 design target.

## Existing Contents

| Path | Type | Assessment |
|---|---|---|
| `AGENTS.md` | Agent instruction document | Concise active implementation guidance. Points agents to the canonical product specification. |
| `docs/traffictwin-design-v0_5.md` | Canonical design specification | No-timeline design target containing all 39 approved capability additions, their boundaries, dependencies, acceptance gates, and open decisions. |
| `docs/traffictwin-design-v0_4.md` | Historical design proposal | Complete attached TrafficTwin v0.4 design copy, preserved exactly for rationale and meeting traceability. |
| `pyproject.toml` | Packaging and tool configuration | Python 3.11+ package metadata, runtime dependencies, dev extras, pytest, Ruff, mypy. |
| `README.md` | Quick start | Minimal install and CLI examples with current-scope disclaimer. |
| `docs/full_product_guide.md` | Complete product guide | Consolidated installation, use cases, UI/CLI usage, output interpretation, deployment, research boundaries, and troubleshooting. |
| `src/traffictwin/` | Python package | Phase 1 domain models, seed I/O, capabilities, registry, and CLI. |
| `examples/seeds/arena_gridlock.yaml` | Example seed | Valid synthetic Phase 1 seed. |
| `tests/fixtures/bundles/` | Synthetic run bundles | Baseline, variation, partial, invalid-manifest, and invalid-row fixtures. |
| `docs/run_bundle_spec.md` | Contract documentation | Run-bundle format, manifest, units, ZIP safety, partial bundles, idempotency. |
| `docs/data_contract.md` | Canonical data documentation | Phase 2 in-memory canonical record contract. |
| `docs/validation_codes.md` | Validation documentation | Stable validation code catalogue and severity policy. |
| `tests/` | Test suite | Unit, golden, and integration tests. |
| `docs/metrics_catalogue.md` | Metrics documentation | Phase 3 metric definitions, formulas, availability, and percentile policy. |
| `docs/evidence_pack_spec.md` | Evidence documentation | Versioned evidence-pack contract for future deterministic rules. |
| `docs/comparison_methodology.md` | Comparison documentation | Pairwise comparison and descriptive aggregation policy. |
| `docs/user_guide.md` | User guide | Phase 5 launch and workflow instructions. |
| `docs/diagnostic_rules.md` | Rules documentation | R0-R8 logic, thresholds, evidence requirements, and limitations. |
| `docs/energy_diagnosis.md` | R8 guide | Exact energy admission, thresholds, UI/CLI/Python usage, provenance, and interpretation limits. |
| `docs/nearest_flip_analysis.md` | DIA-05 guide | Supported rule families, exact boundary verification, constraints, CLI/Python usage, provenance, and limits. |
| `docs/threshold_sensitivity_explorer.md` | DIA-06 guide | Complete-grid semantics, stability, sampled/exact boundaries, UI/Python usage, config exchange, provenance, and limits. |
| `docs/cross_rule_reasoning.md` | DIA-07 guide | Bounded conflict/corroboration/suppression policy, precedence, retention, UI/CLI/Python usage, provenance, and limits. |
| `docs/statistical_studies.md` | STA-01 guide | Common-seed compatibility, estimand, bootstrap, sign-flip test, paired effects, UI/CLI/Python usage, provenance, and interpretation limits. |
| `docs/n_way_ranking.md` | STA-02 guide | Per-family complete-seed cohorts, winner-map extension, ties/missingness/incompatibility, joint-bootstrap uncertainty, UI/CLI/Python usage, provenance, and interpretation limits. |
| `docs/equivalence_testing.md` | STA-03 guide | Predeclared original-unit margins, inherited STA-01 pairing, paired TOST, conclusions/unavailable states, UI/CLI/Python usage, reporting, provenance, and interpretation limits. |
| `docs/regression_gates.md` | STA-04 guide | Golden approval lifecycle, typed metric/study contexts, exact/compatible source policies, scalar tolerances, CI outcomes, UI/CLI/Python use, provenance, and limits. |
| `docs/power_analysis.md` | STA-05 guide | Prospective effect/variance bases, paired normal approximation, smallest pair-count rule, labels/unavailable states, UI/CLI/Python use, provenance, and limits. |
| `docs/difference_provenance.md` | PRO-01 guide | Compatible accepted-row comparison lineage, closed arithmetic formulas, lineage-only behavior, UI/CLI/Python use, JSON/CSV integrity language, and limits. |
| `docs/provenance_graph_exports.md` | PRO-02 guide | Bounded root-centred graph projection, stable IDs, path-safe/structure-only disclosure, DOT/GraphML, CLI/UI/Python use, and limitations. |
| `docs/provenance_completeness.md` | PRO-03 guide | Typed report-claim denominator, exclusions, classification/depth rules, null policy, CLI/UI/Python use, and interpretation limits. |
| `docs/latex_research_exports.md` | REP-01 guide | Typed artifact families, CLI/UI/Python use, compilation, shared fingerprints, bounds, path safety, source labels, and interpretation limits. |
| `docs/parameter_sweeps.md` | EXP-01 guide | Bounded grid/mode contract, closed paths, CLI/UI/Python usage, response/provenance semantics, and no-launch limits. |
| `docs/declarative_rules.md` | Declarative-rule guide | Closed grammar, trust boundary, YAML example, CLI/Python use, three-valued semantics, and limits. |
| `docs/fairness_diagnosis.md` | R7 guide | Dimension/evidence contracts, thresholds, UI/CLI/Python use cases, provenance, and interpretation limits. |
| `docs/diagnostic_report_spec.md` | Report documentation | Versioned DiagnosticReport schema and evidence-key policy. |
| `docs/fault_injection_methodology.md` | Evaluation documentation | Synthetic fault-injection cases and engineering evaluation limits. |
| `docs/ui_design.md` | UI design | Streamlit page structure and presentation policy. |
| `docs/demo_script.md` | Demo script | Keystone synthetic demonstration steps and expected states. |
| `docs/integration/` | Integration discovery documentation | Phase 6A artifact inventory, schema mapping, execution contract, gap analysis, and implementation decision. |
| `docs/index.md` | Documentation index | Organised guide to all current documentation. |
| `docs/system_overview.md` | System overview | Problem, platform vision, protected vertical slice, workflow, and integration boundary. |
| `docs/developer_guide.md` | Developer guide | Setup, package structure, extension points, and contribution rules. |
| `docs/cli_reference.md` | CLI reference | Current Typer commands only, with examples and exit behavior. |
| `docs/api_reference.md` | API reference | Principal public Python interfaces. |
| `docs/reproducibility.md` | Reproducibility guide | Deterministic design choices, fingerprints, commands, fixture provenance. |
| `docs/testing_strategy.md` | Testing strategy | Test pyramid, invariants, fixture policy, and coverage interpretation. |
| `docs/viva_guide.md` | Viva guide | Concise answers to likely supervisor/examiner questions. |
| `docs/decisions/` | ADRs | Concise architecture decision records for major project decisions. |
| `src/traffictwin/provenance/` | Provenance package | Read-only trace graph, query service, source-row previews, and JSON/Markdown export. |
| `docs/provenance_explorer.md` | Provenance documentation | User and CLI workflow for trace inspection. |
| `docs/provenance_model.md` | Provenance model documentation | Compact trace model, complete on-demand accepted-row ledgers, and aggregate limitations. |
| `src/traffictwin/synthetic/` | Synthetic generator | Deterministic standalone scenario, bundle, and experiment generation. |
| `src/traffictwin/demo/` | Demo workspace | Safe workspace initialisation, reset, status, and Streamlit launch helpers. |
| `src/traffictwin/reporting/` | Report export | Deterministic Markdown, standalone HTML, and A4 PDF research reports. |
| `.github/workflows/ci.yml` | CI workflow | Python 3.11/3.12 quality gates and standalone smoke checks. |
| `src/traffictwin/integration/tos/` | TOS Data integration | Versioned source contract, read-only validation/import, unit-aware replay, task/action and RSU-state inspection, partial evidence, and provenance. |
| `docs/integration/tos_data_adapter.md` | Integration guide | Supported TOS boundary, semantics, CLI, security, and limitations. |
| `src/traffictwin/integration/sumo/` | SUMO output adapter | Versioned XML contract, validation, canonical trip mapping, summary evidence, deterministic metrics, and idempotent import. |
| `tests/fixtures/sumo/square_public/` | Public SUMO fixture | Licensed Eclipse SUMO 1.27.1 square-scenario tripinfo/summary outputs with source metadata and checksums. |
| `docs/integration/sumo_output_adapter.md` | SUMO integration guide | Source manifest, mapping rules, CLI/UI usage, security, fixture provenance, and limitations. |

## Relevant Assets Found

- Randy's external `TOS Data` package is present outside `diss/` at `external/tos-data`.
- Randy's external `vec_env` source is present outside `diss/` at `external/vec_env`; TrafficTwin
  records inspected source commit `e98441196270b8fd4cc0eede892df4a0053b2185` as semantics evidence,
  not as the asserted producer of every run.
- The external package includes evaluation summary CSV, training curves, greedy-evaluation JSON, instrumented per-step NPZ files, instrumented per-task NPZ files, Manchester trace NPZ files, and training-record documentation.
- The source repository includes an evaluator and CSF-specific scripts, but actor checkpoints, the
  instrumented-array writer, raw SUMO XML/config, and a locally verified path-independent runtime
  are unavailable.
- TrafficTwin synthetic run artifacts and the public licensed SUMO acceptance fixture are present
  under `tests/fixtures/`; Randy's private package remains outside the repository.
- A read-only external TOS Data results integration is implemented; it cannot execute the source
  environment.
- Streamlit UI is implemented for synthetic fixtures and imported historical bundles.
- Deterministic diagnostic rules R0-R8 are implemented over EvidencePacks; R6 additionally
  requires typed temporal evidence, R7 exact operational groups, and R8 exact completed-task
  energy.
- No full Randy/VEC canonical converter, direct launcher, FCD mapping, or canonical row storage for
  TOS runs is implemented. The bounded public SUMO tripinfo/summary adapter is separate.
- Python 3.12 is available locally and was used for validation. The package declares Python 3.11+ support.

## Design Specification Status

Current and historical design paths:

- `./docs/traffictwin-design-v0_5.md`: canonical future design target.
- `./docs/traffictwin-design-v0_4.md`: preserved historical proposal and traceability source.
- `./traffictwin-design-v0_4.md`: not used.

The v0.4 design file was copied byte-for-byte from the supplied attachment before `AGENTS.md` was
replaced with concise instructions. The v0.5 design was subsequently approved as the canonical
repository target without changing the implementation status of its planned capabilities.

## Implemented In Phase 0

- Repository assessment.
- Initial implementation status, assumption register, open questions, and architecture proposal.
- Canonical design specification relocation.
- Concise `AGENTS.md`.
- Python `.gitignore`.
- Initial Git commit.

## Implemented In Phase 1

- `src/` package layout.
- `ScenarioSeed`, `Experiment`, and `Run` domain models.
- Supporting enums and nested seed configuration models.
- Explicit seed schema version handling with supported version `1.0`.
- Strict Pydantic v2 validation using `extra="forbid"`.
- Seed YAML load, validation, deterministic dump, and normalisation.
- Valid example seed and invalid seed fixtures.
- Three-valued capability manifest: `true`, `false`, `unknown`.
- Export/import-only default manifest for `generic_csv`.
- SQLite metadata registry for seeds, experiments, and runs.
- Duplicate-ID rejection.
- Creation and update timestamps.
- Basic status transitions with invalid-transition rejection.
- Minimal Typer CLI:
  - `validate-seed`
  - `normalise-seed`
  - `capabilities`
  - `registry init`
  - `registry inspect`
- Focused unit tests.

## Implemented In Phase 2

- Versioned `manifest.yaml` model.
- Directory and safe ZIP bundle loading.
- Manifest-driven generic CSV adapter.
- Canonical in-memory records for tasks, infrastructure, vehicles, traffic observations, trips, and incidents.
- Schema, file, unit, row, and reconciliation validation.
- Machine-readable validation report with JSON export.
- Evidence availability summary.
- Minimal R0-compatible insufficient-evidence summary.
- Synthetic baseline, variation, partial, invalid-manifest, and invalid-row bundles.
- Registry bundle-import metadata and idempotent import behavior.
- CLI commands:
  - `bundle validate`
  - `bundle inspect`
  - `bundle import`
  - `bundle report`
- Run-bundle, data-contract, and validation-code documentation.
- Unit, golden, and integration tests.

## Implemented In Phase 3

- Stable metric-definition catalogue.
- Metric result models with available, unavailable, partial, and invalid statuses.
- Deterministic metric engine over Phase 2 canonical records.
- Task metrics:
  - generated and completed counts;
  - completion and incomplete rates;
  - completion by class;
  - deadline-miss rate over completed observed tasks;
  - latency count, mean, P50, P95, and P99;
  - decision counts and shares;
  - offload rate;
  - drop metrics as unavailable when evidence is absent;
  - contract-gated task energy per observed task, energy per completed task, and energy-delay
    product, with explicit unavailable/partial coverage and compatible-comparison semantics.
- Infrastructure metrics:
  - per-RSU summary;
  - observed RSU count;
  - queue mean and max;
  - utilisation mean and P95;
  - configurable saturation episode count and duration;
  - capacity-normalised load balance as unavailable without capacity and active-task evidence.
- Traffic metrics:
  - observation count;
  - total and mean counts;
  - mean, P50, P95, and minimum speed;
  - time coverage;
  - sensor count.
- Trip metrics:
  - record, completed, and incomplete counts;
  - completion rate;
  - duration count, mean, P50, P95, min, and max.
- Versioned evidence-pack model and builder.
- Baseline-versus-variation comparison model and deterministic seed-parameter diff.
- Experiment-level descriptive aggregation and paired random-seed differences.
- Additive SQLite tables for metric collection JSON and evidence-pack JSON references.
- CLI commands:
  - `metrics compute`
  - `metrics report`
  - `compare`
  - `evidence build`
  - `experiment summarise`
- Golden expected metric and comparison outputs for synthetic fixtures.

## Implemented In Phase 4

- Streamlit application shell at `src/traffictwin/ui/app.py`.
- UI state defaults and logical replay clock.
- UI service layer over Phase 1-3 library functions.
- Home / Project Status page.
- Scenario Studio with YAML preview, seed validation, export, and disabled direct-launch control.
- Bundle Import & Validation page.
- Operations View in historical replay mode.
- Run Overview page.
- Infrastructure & Congestion page.
- What-if Compare page.
- Journey-Time Lens page.
- Evidence & Diagnostic Readiness page, later updated in Phase 5.
- Reusable UI components for badges, cards, validation, provenance, unavailable states, and selectors.
- Plotly chart preparation for traffic, infrastructure, task events, trip durations, and metric availability.
- UI tests for formatting, state, chart data, service models, page guards, and AppTest startup.
- Demo documentation and UI design notes.

## Implemented In Phase 5

- Versioned diagnostic rule configuration.
- Rule result models with triggered, not-triggered, insufficient-evidence, conflicting-evidence, and invalid statuses.
- Deterministic R0 data-readiness rule.
- Deterministic R1 under-offloading candidate rule.
- Deterministic R2 infrastructure-bottleneck candidate rule.
- Deterministic R3 scenario-triviality candidate rule.
- Rule registry and catalogue.
- Rule engine with independent execution, disabled-rule support, evidence-key validation, and exception isolation.
- Versioned DiagnosticReport model with readiness, provenance, warnings, and conflict observations.
- Synthetic fault-injection fixture set with development and held-out labels.
- Fault-injection evaluation utility reporting precision, recall, support count, and confusion table.
- CLI commands:
  - `diagnose bundle`
  - `diagnose evidence`
  - `diagnose report`
  - `diagnose evaluate`
- UI page updated to Evidence & Diagnostic Hypotheses with rule results, alternatives, missing evidence, confidence basis, thresholds, and JSON download.
- Golden diagnostic expected outputs.
- Unit, golden, integration, and UI tests.

## Implemented In Productisation Provenance Explorer Phase

- Versioned provenance trace models:
  - `ProvenanceNode`;
  - `ProvenanceEdge`;
  - `ProvenanceTrace`;
  - `SourceRowPreview`.
- Internal deterministic trace graph with edge endpoint validation.
- Metric trace builder from `MetricCollection`, metric catalogue, canonical tables, validation
  findings, source rows, manifest, run, seed, experiment, environment, and fingerprint.
- Diagnostic-rule trace builder from `DiagnosticReport`, findings, evidence keys, metric results,
  metric definitions, canonical evidence, and unavailable links.
- EvidencePack-only diagnostic trace support with canonical/source-row links explicitly unavailable.
- Safe declared CSV, gzip-CSV, and Parquet source-row preview using the existing bundle loader and
  bundle-relative paths.
- Provenance query service for bundle-backed traces.
- JSON and deterministic Markdown export.
- Typer commands:
  - `provenance metric`
  - `provenance rule`
  - `provenance run`
  - `provenance source`
  - `provenance export`
- Streamlit `Provenance Explorer` page.
- Golden provenance trace projections and Markdown output.
- Documentation:
  - `docs/provenance_explorer.md`
  - `docs/provenance_model.md`
  - `docs/viva_traceability_demo.md`

Phase 3 metric objects do not materialise per-row contribution lists. The additive contribution
query now reconstructs a complete accepted-candidate-row ledger on demand from the validated bundle
and applies the metric engine's field-level eligibility predicates. It does not assign fabricated
per-row causal weights.

## Implemented In Phase 6

- Initial repository and workspace discovery for Randy/VEC and SUMO artifacts.
- Updated discovery after Randy granted GitLab access to the external `TOS Data` package.
- Confirmation that real Randy/VEC result artifacts are now present outside `diss/` in `external/tos-data`.
- Inspection of the separately granted `vec_env` repository and its reproducibility, environment,
  evaluator, trace-builder, configuration, and SLURM source.
- Confirmation that the external package is not a standard TrafficTwin run bundle.
- Confirmation that raw SUMO XML/config, checkpoint files, and the instrumented NPZ writer are not
  supplied; the evaluator/SLURM scripts are not yet safe TrafficTwin launch contracts.
- Documentation of the distinction between summary metrics, instrumented NPZ source arrays, trace NPZ files, and TrafficTwin canonical records.
- Integration discovery documents:
  - `docs/integration/randy_artifact_inventory.md`
  - `docs/integration/randy_schema_mapping.md`
  - `docs/integration/randy_execution_contract.md`
  - `docs/integration/randy_gap_analysis.md`
  - `docs/integration/phase6_decision.md`
- Capability decision:
  - `direct_launch=false`
  - `asynchronous_launch=false`
  - source controls are documented separately, while the read-only adapter keeps them disabled
- Read-only `traffictwin.integration.tos` package:
  - versioned source models and stable run/experiment identifiers;
  - safe evaluation CSV, JSON, and NPZ header readers;
  - complete package validation and instrumented-summary reconciliation;
  - source-summary MetricCollections with a separate implementation version;
  - partial EvidencePacks consumed by the deterministic rule engine (currently R0-R8);
  - idempotent SQLite registration of experiments, runs, metrics, and evidence;
  - bounded historical replay joined by timestamp and time-local vehicle slot;
  - confirmed simulation-second, network-metre, and m/s replay units;
  - bounded per-task showcase inspection with joined actions and `deadline_met` semantics;
  - confirmed RSU in-flight task count, compute backlog, concurrency capacity, and pressure
    inspection without relabelling them as canonical utilisation/queue metrics;
  - versioned machine-readable `vec_env` source contract and CLI output;
  - aggregate metric/rule provenance to exact evaluation CSV rows;
  - `traffictwin integration tos ...` CLI group;
  - Streamlit `TOS Data Import` page.
- Runtime tests generate a synthetic-schema package; no Randy artifact is committed.
- Full canonical conversion remains stopped until physical completion/identity and compatible
  canonical infrastructure evidence, exact producer provenance, and fixture permissions are
  resolved.

## Implemented In Documentation Pass

- Rewritten root README as the project entry point.
- Documentation index.
- System overview.
- Revised architecture document with Mermaid diagrams.
- Developer guide.
- Expanded user guide.
- CLI reference derived from actual commands.
- API reference for principal public interfaces.
- Reproducibility guide.
- Testing strategy.
- Revised demo script and executable demo checklist.
- Viva guide.
- Dissertation mapping.
- Traceability matrix.
- Glossary.
- Limitations and future work.
- Security and privacy.
- ADR index and ten concise ADRs.
- Screenshot manual-capture checklist.
- Generated reference artifacts under `docs/reference/generated/`.
- Cross-links added to data, validation, metrics, evidence, comparison, and diagnostic contract documents.

## Quality Gates

Commands run successfully:

```bash
.venv/bin/ruff format .
.venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/python -m pytest
.venv/bin/python -m pytest --cov=traffictwin --cov-report=term-missing
.venv/bin/python scripts/generate_reference_docs.py
.venv/bin/traffictwin validate-seed examples/seeds/arena_gridlock.yaml
.venv/bin/traffictwin normalise-seed examples/seeds/arena_gridlock.yaml build/traffictwin_arena_gridlock.normalised.yaml
.venv/bin/traffictwin capabilities
.venv/bin/traffictwin registry init build/traffictwin_phase1_registry.sqlite
.venv/bin/traffictwin registry inspect build/traffictwin_phase1_registry.sqlite
.venv/bin/traffictwin bundle validate tests/fixtures/bundles/baseline_valid
.venv/bin/traffictwin bundle validate <baseline.zip>
.venv/bin/traffictwin bundle validate tests/fixtures/bundles/partial_valid
.venv/bin/traffictwin bundle validate tests/fixtures/bundles/invalid_manifest
.venv/bin/traffictwin bundle import tests/fixtures/bundles/baseline_valid --registry <tmp-registry>
.venv/bin/traffictwin bundle report tests/fixtures/bundles/partial_valid --format json
.venv/bin/traffictwin metrics compute tests/fixtures/bundles/baseline_valid
.venv/bin/traffictwin metrics compute tests/fixtures/bundles/variation_valid
.venv/bin/traffictwin metrics compute tests/fixtures/bundles/partial_valid
.venv/bin/traffictwin metrics report <baseline.zip> --format json
.venv/bin/traffictwin compare tests/fixtures/bundles/baseline_valid tests/fixtures/bundles/variation_valid
.venv/bin/traffictwin evidence build tests/fixtures/bundles/baseline_valid --output <tmp-evidence>
.venv/bin/traffictwin experiment summarise --registry <tmp-registry> --experiment-id exp-gridlock-001
.venv/bin/traffictwin diagnose bundle tests/fixtures/bundles/baseline_valid
.venv/bin/traffictwin diagnose bundle tests/fixtures/bundles/invalid_rows
.venv/bin/traffictwin diagnose evidence <tmp-evidence>
.venv/bin/traffictwin diagnose report tests/fixtures/bundles/baseline_valid --format json
.venv/bin/traffictwin diagnose evaluate tests/fixtures/diagnostics/cases.json
.venv/bin/traffictwin provenance metric tests/fixtures/bundles/baseline_valid task.completion.rate
.venv/bin/traffictwin provenance rule tests/fixtures/bundles/variation_valid R2
.venv/bin/traffictwin provenance source tests/fixtures/bundles/baseline_valid tasks.csv 2
.venv/bin/traffictwin provenance export tests/fixtures/bundles/baseline_valid --root-type metric --root-id task.completion.rate --format json
streamlit run src/traffictwin/ui/app.py --server.headless true --server.port <tmp-port>
http://127.0.0.1:<tmp-port>/_stcore/health
find <workspace-root> ... <artifact discovery searches>
```

Results:

- Ruff format: clean after formatting.
- Ruff check: all checks passed.
- mypy: no issues found.
- pytest after Phase 4: 85 passed.
- pytest after Phase 5: 119 passed.
- coverage after Phase 4: 71%.
- coverage after Phase 5: 76%.
- CLI seed validation: passed.
- CLI seed normalisation: passed.
- CLI capability manifest: direct and asynchronous launch are `false`; unconfirmed Randy controls are `unknown`.
- Registry smoke: registry created by one process and inspected by another.
- Bundle CLI smoke: valid directory, valid ZIP, partial bundle, rejected bundle, idempotent import, and JSON report passed.
- Metrics CLI smoke: baseline, variation, partial, ZIP report, and rejected-manifest failure passed.
- Comparison CLI smoke: baseline versus variation bundle comparison passed.
- Evidence CLI smoke: evidence-pack JSON generation passed.
- Diagnostic CLI smoke: baseline, R1 fixture, R2 fixture, R3 fixture, mixed fault, insufficient evidence, saved EvidencePack, and rejected bundle behavior passed.
- Fault-injection evaluation: precision/recall returned without `NaN` or infinity.
- Original Phase 6A discovery: no real Randy/VEC or SUMO artifacts were present before Randy's GitLab package was cloned.
- Updated Phase 6 discovery: `external/tos-data` contains real Randy/VEC result artifacts. The
  conservative read-only integration is covered by generated synthetic-schema tests; real fixture
  permission is still required before committing a source-derived sample.
- Updated Phase 6A documentation validation: Ruff format check passed; Ruff check passed; mypy passed; 168 tests passed; coverage remained 77%.
- Documentation pass quality gates: Ruff format/check passed; mypy passed; generated reference JSON regenerated and parsed; Markdown links checked; API imports checked; fixture paths checked; Mermaid fences checked; unsupported-claim scan completed; 119 tests passed; coverage remained 76%; synthetic CLI demo flow passed; Streamlit health check returned `200 ok`.
- Provenance Explorer quality gates: Ruff format/check passed; mypy passed; 147 tests passed; coverage reached 77%; generated reference JSON regenerated; Markdown links checked; provenance CLI metric/rule/source/export smoke checks passed; Streamlit AppTest rendered the Provenance Explorer; Streamlit headless server started; exported provenance JSON contained no absolute local paths; provenance Markdown contained no causal-proof wording.
- Experiment summary CLI smoke: registry-backed summary over stored metric collections passed.
- Streamlit smoke: headless server started and health endpoint responded.
- Streamlit AppTest: Home and all core pages rendered with synthetic defaults without uncaught exceptions.
- JSON finite check: metric JSON contained no `NaN` or infinity.
- Fixture raw-file hashes were unchanged after validation/import smoke checks.

## Blocked

- Full TOS/VEC canonical conversion remains blocked by absent physical-completion,
  persistent-identity, per-vehicle tier/target/link evidence, source raw SUMO/trip data, and
  sanitised TOS fixture permission.
- Direct launch is blocked by missing checkpoints/instrumented writer, source-specific paths, and
  an unverified local runtime despite the discovered evaluator CLI.
- Live or near-live modes are blocked until real feed details exist.
- External canonical energy remains blocked until a source provides per-task rows satisfying the
  v1.0 semantic contract. Drop-cause, queue-clearance, and capacity-normalised metrics remain
  blocked until source fields and units exist.

## Not Started

- Additional external-source families, FCD mapping, VEC canonical conversion, and sensor adapters
  beyond the two reviewed OPS-05 reference contracts.
- LLM rendering.
- XAI.

## Evidence Required Next

- Definitions for `rsu_busy_ms`, `rsu_load`, and `rsu_max_concurrent`; confirmed trace units; and
  clarification of eventual completion remain required for canonical conversion.
- Permission to commit a small sanitised real-schema fixture.
- Access to the separate `vec_env` reproduction documentation if direct execution or stronger capability mapping is required.
- Confirmation of supported scenario controls.
- Environment invocation contract, if direct launch is expected.

## Current File Tree Summary

```text
diss/
    AGENTS.md
    README.md
    pyproject.toml
    .gitignore
    docs/
        traffictwin-design-v0_5.md
        traffictwin-design-v0_4.md
        implementation-status.md
        open-questions.md
        assumption-register.md
        architecture.md
    examples/
        seeds/
            arena_gridlock.yaml
    src/
        traffictwin/
            __init__.py
            cli.py
            config/
                __init__.py
                capabilities.py
                seed_io.py
            domain/
                __init__.py
                enums.py
                experiment.py
                run.py
                scenario.py
            storage/
                __init__.py
                registry.py
            adapters/
                __init__.py
                base.py
                generic_csv.py
            canonical/
                __init__.py
                records.py
                tables.py
            evidence/
                __init__.py
                availability.py
                builder.py
                insufficient.py
                pack.py
            diagnostics/
                __init__.py
                builder.py
                report.py
                serialization.py
            experiments/
                __init__.py
                aggregation.py
                comparison.py
                grouping.py
            ingestion/
                __init__.py
                bundle.py
                canonicalise.py
                hashes.py
                loader.py
                manifest.py
            metrics/
                __init__.py
                aggregation.py
                availability.py
                catalogue.py
                comparison.py
                definitions.py
                engine.py
                engine_config.py
                infrastructure.py
                results.py
                statistics.py
                task.py
                traffic.py
                trips.py
            rules/
                __init__.py
                base.py
                catalogue.py
                config.py
                conflicts.py
                engine.py
                evaluation.py
                models.py
                registry.py
                r0_insufficient_evidence.py
                r1_under_offloading.py
                r2_infrastructure_bottleneck.py
                r3_scenario_triviality.py
            validation/
                __init__.py
                codes.py
                findings.py
                files.py
                manifest.py
                reconciliation.py
                report.py
                rows.py
    tests/
        fixtures/
            bundles/
                baseline_valid/
                variation_valid/
                partial_valid/
                invalid_manifest/
                invalid_rows/
            seeds/
                invalid_class_mix.yaml
                invalid_schema_version.yaml
            diagnostics/
                cases.json
        golden/
            test_baseline_bundle.py
            test_validation_reports.py
        integration/
            test_bundle_import.py
            test_zip_import.py
        unit/
            test_bundle_loader.py
            test_capabilities.py
            test_manifest.py
            test_registry.py
            test_scenario.py
            test_seed_io.py
```

## Dependency Decisions

Runtime dependencies used in Phase 1:

- `pydantic>=2`: strict schemas and validation.
- `PyYAML>=6`: seed YAML load/dump.
- `typer>=0.12`: minimal CLI.

Development dependencies:

- `pytest`
- `pytest-cov`
- `ruff`
- `mypy`
- `types-PyYAML`

Runtime dependencies added in Phase 4:

- `streamlit`
- `plotly`

Deferred:

- `pandas`, `polars`, `duckdb`: wait until data-size evidence. Streamlit installs pandas and pyarrow transitively, but TrafficTwin code does not import them directly.
- `pre-commit`: practical later, not required for Phase 1.
- ORM: avoided; Phase 1 uses standard library `sqlite3`.

## Phase 6 Outcome And Next Gate

Phase 6 inspected the supplied TOS results and `vec_env` source, then implemented the safe
read-only boundary. The next external increment requires:

1. exact producer commit and instrumented writer;
2. one approved checkpoint and small expected output;
3. permission for a sanitised matched fixture;
4. any additional physical-completion, identity, target/link, and raw trip/SUMO evidence;
5. a path-independent evaluator smoke run before any launcher decision.

Until then, canonical conversion and direct launch remain stopped. LLM rendering, XAI, real
portfolio calibration, and training orchestration remain outside this integration boundary.

## Implemented In Standalone Product Phase

- `SyntheticScenarioConfig` and documented synthetic policy profiles.
- Deterministic generated bundles for baseline, stressed demand, under-offloading,
  infrastructure bottleneck, mixed fault, partial evidence, and trivial multi-algorithm cases.
- `traffictwin synthetic presets`, `synthetic generate-preset`,
  `synthetic experiment-generate-preset`, and `synthetic verify`.
- `traffictwin demo initialise`, `demo reset`, `demo status`, and `demo launch`.
- Reproducible demo workspace with SQLite registry, generated seeds, bundles, exports, reports,
  logs, and manifest.
- Multi-seed low-pressure experiment evidence for the existing R3 rule.
- Deterministic report export commands for run, comparison, diagnostics, and full reports.
- Streamlit Home standalone demo status section.
- Release metadata helper, changelog, release guide, and GitHub Actions CI workflow.

## Implemented In Product Polish & Research UX

- `Guided Demo` page with eight standalone-synthetic stages and four read-only imported-TOS stages.
- Mobile-visible Home actions that use safe Streamlit navigation callbacks rather than requiring
  the collapsed sidebar.
- `Scenario Builder` page over `SyntheticScenarioConfig`.
- `Experiment Planner` over registered `ScenarioSeed` records, with research-question metadata,
  baseline/variation selection, policy labels, common random seeds, bounded design preview, seed
  differences, YAML export, and transactional registration as status `planned`.
- Versioned Experiment Protocol Exporter with exhaustive deterministic run slots, embedded seed
  snapshots/fingerprints, suggested run/bundle identifiers, YAML/CSV export, and read-only bundle
  matching (`exact`, `compatible`, `mismatch`, or `unmatched`).
- Experiment planning creates no `Run` records and exposes no simulator launch control.
- Improved replay controls: play, pause, resume, restart, timestamp jump, scrubber, speed presets,
  step controls, and deterministic filters.
- `Experiment Manager` page over registry/workspace metadata.
- `Reports` page for deterministic report inventory, downloads, and explicit regeneration.
- `Search` page for local metadata search.
- `Settings` page for session-scoped preferences.
- `About` page for version, schema, metric, diagnostic, provenance, Python, commit, and licence
  metadata.
- Shared section headers, report cards, metadata cards, status badges, and lightweight UI theme.
- Homepage dashboard improvements for workspace, reports, comparisons, provenance exports, quick
  actions, and recent artifacts.
- Original Product Polish quality gates: Ruff format/check passed; mypy passed; 168 tests passed;
  coverage 77%; demo workspace smoke passed; comparison/report/provenance smoke checks passed;
  Streamlit health check returned `ok`; package build passed.
- Guided-workflow quality gates: Ruff format/check and strict mypy passed; 210 tests passed;
  coverage 78%; standalone and real-package TOS AppTests passed; phone-sized Home, standalone, and
  imported-TOS interactions were browser-verified.
- Experiment Planner quality gates: Ruff format/check and strict mypy passed; 221 tests passed;
  coverage 79%; generated references and fixtures were unchanged; release smoke, synthetic
  workspace verification, package build, Streamlit AppTest, and phone-sized browser validation
  passed.

The protocol exporter preserves the same boundary: it coordinates planned external work but does
not schedule it, infer environment details, import matched bundles, or change registry state.
- Experiment Protocol Exporter quality gates: Ruff format/check and strict mypy passed; 229 tests
  passed; coverage remained 79%; generated schemas/CLI help were refreshed; protocol CLI and
  Streamlit AppTest workflows passed.

## Standalone Product Remaining Limits

- Synthetic generation is not calibrated simulation.
- Synthetic policy profiles are not real trained algorithms.
- Registry-run report shortcuts are not the primary report path; bundle paths are supported first.
- Read-only TOS result inspection is available with source-evidenced units and RSU meanings; its
  full canonical conversion remains blocked by missing outcome/identity evidence, raw outputs,
  producer/runtime artifacts, and sanitised fixture permission. Public SUMO tripinfo/summary
  ingestion is independently implemented.
- Direct launch, near-live, and true-live support remain unavailable.

## Implemented In Read-Only TOS Integration Increment

- Optional `tos` dependency extra for bounded NumPy archive inspection.
- Strict evaluation-master parsing, supported-engine gating, package inventory, Git commit, and
  deterministic package fingerprint.
- Deep per-step, per-task, and trace NPZ key/shape validation plus JSON-summary reconciliation.
- Source-summary MetricCollections with a distinct implementation version and explicit unavailable
  results for unsupported canonical metrics.
- Partial EvidencePacks evaluated by the deterministic rule engine (currently R0-R8).
- Idempotent SQLite registration of 10 source experiment groups and 300 source runs in the supplied
  package, without storing canonical rows or absolute source paths.
- Unit-aware historical replay, time-indexed recycled vehicle slots, confirmed source-specific RSU
  pressure/backlog views, and bounded per-arrival task/action samples.
- Aggregate metric/rule provenance to exact evaluation CSV rows, package commit/fingerprint, run,
  experiment grouping, actor, and engine version.
- Versioned `tos_source_contract()`, `contract`/`rsu-series` CLI commands, and updated Streamlit
  `TOS Data Import` page.
- Quality gates: Ruff format/check passed; mypy passed; 185 tests passed; coverage 78%. External
  package validation, idempotent 300-run import, CLI, unit-aware replay, task/action and RSU-state
  inspection, diagnostics, provenance, AppTest, generated references, and source immutability
  checks passed.

## Implemented In TOS Results Workbench Increment

- Stable source-analysis catalogue for deadline success by class, all-arrival latency, per-arrival
  energy, decision shares, and offload share.
- Campaign/cell/fleet evaluation matrices with deterministic descriptive statistics.
- Exact baseline/variation pairing by common fleet seed with compatibility and unmatched-seed
  findings.
- Conservative in-domain/held-out/unknown matrix sourced from package documentation.
- Bounded training-history reader with unavailable warm-up handling and separate greedy summaries.
- Processed-FCD trace profiles, exact source RSU pressure/backlog summaries, and exact full-showcase
  task outcome aggregation.
- Reproducibility audit for package coverage, actor/training matching, and blocked producer assets.
- Deterministic imported-simulation report, JSON research pack, and self-contained aggregate atlas.
- Focused Streamlit pages: `TOS Results`, `TOS Mobility & RSU Replay`, and `TOS Training & Audit`.
- Twelve new/extended TOS CLI smoke workflows and generated reference documentation.
- Quality gates: Ruff format/check passed; strict mypy passed; 197 tests passed; coverage 78%.
  Real-package matrix, comparison, training, replay, task, RSU, audit, report, atlas, path-safety,
  JSON-finiteness, UI AppTest, and source immutability checks passed.

## Implemented In Release, Supervisor, And Evaluation Increment

- Versioned machine-readable TOS integration gates for producer provenance, checkpoint, writer,
  canonical outcome/identity, R1/R2 evidence, trip output, permissions, and evaluator smoke.
- Checksummed private supervisor/viva pack with manifest, reports, atlas, evaluation plan, viva
  notes, screenshot checklist, audit, and readiness JSON.
- Permission-gated public TOS atlas staging; unknown permission is never treated as granted.
- Synthetic-only static dashboard built from existing standalone MetricCollections and
  DiagnosticReports, with a Netlify build definition and finite embedded JSON.
- Standalone Streamlit Docker image definition with an initialised synthetic workspace and health
  check.
- Complete `uv.lock` dependency graph and release/deployment CLI commands.
- Dissertation evaluation plan separating software evidence, synthetic verification, imported TOS
  description, blocked evaluation, and interpretation limits.
- Quality gates: Ruff format/check passed; strict mypy passed; 206 tests passed; coverage 78%.
  Readiness, private supervisor-pack, publication-gate, synthetic static-site, CLI, and UI-service
  tests passed in addition to the complete prior suite.

External canonical conversion, real R1/R2 evaluation, journey-time integration, and direct launch
remain blocked. This increment records those boundaries; it does not simulate the missing evidence.

## Implemented In Independent Research Tools Increment

- First-class deterministic experiment EvidencePacks over stored metric collections, including
  policy dispersion, always-local regret, pressure context, and explicitly paired
  training-validation gaps.
- Strict pair-set validation for R5: experiment, policy, checkpoint, metric contract, role-specific
  environment provenance, unique run IDs, and unique common random seeds are checked before any
  gap is aggregated.
- Deterministic R4 load-imbalance and R5 training-validation drift candidate rules with explicit
  unavailable/conflicting states and provisional synthetic thresholds.
- Dedicated Streamlit `Triviality` page with selectable metric/objective, explicit R5 run pairs,
  R3/R5 evidence, winner-map, portfolio, held-out study, and JSON exports.
- Deterministic per-seed winner maps with ranks, ties, and regret for an explicit objective;
  incompatible units, versions, environments, or checkpoints exclude the affected seed family.
- Ordered, auditable synthetic portfolio rules plus a fixed development/held-out evaluation across
  five seed families, three policy profiles, and three random-seed replicates per profile.
- Synthetic S5 stadium-event/RSU-siting and S6 road-clearing/lane-closure presets.
- Incident/event authoring for type, location, severity, start, duration, lanes closed, demand
  multiplier, and vehicle references, with full generic-CSV/canonical round-trip and a linked
  incident-seeded what-if variant export.
- SQLite-backed manual protocol slot tracking with validated lifecycle transitions and CLI/UI
  controls; it launches nothing.
- Additive storage for experiment-level EvidencePack JSON.
- Draft ethics, participant task, survey, interview, consent/privacy, and anonymised-result
  materials under `docs/evaluation/`; these are not submitted or approved.
- New CLI workflows for experiment evidence, winner maps, portfolio and held-out-study evaluation,
  and manual protocol tracking.
- Quality gates: Ruff format/check passed; strict mypy passed; 244 tests passed; generated
  references refreshed; all 62 fresh-workspace bundles validated; experiment evidence,
  winner-map, portfolio, held-out study, and UI smokes passed; source and wheel builds passed.

Remaining external limits are unchanged: the portfolio rules and S5/S6 output are synthetic
workflow demonstrations, R4/R5 require real calibration and evidence, participant work requires
institutional approval, and Randy/VEC/SUMO direct launch remains unavailable.

## Implemented In Advanced Research Tools Increment

- Expanded R0-R5 synthetic fault-injection matrix across three severities and three random seeds,
  with confusion counts, false-positive rate, specificity, development/held-out summaries,
  severity robustness, failure IDs, and a transparent KPI baseline.
- Portfolio selected-score/regret variability, constituent variability, failure cases, pairwise
  dominance, and deterministic CSV/Markdown report renderers.
- Checksummed synthetic baseline, incident/demand, and reduced-infrastructure case-study pack.
- Complete accepted-canonical-row metric contribution ledgers with JSON/CSV CLI and UI export.
- A4 ReportLab PDF output using the normal report builders, page headers/footers, and page numbers.
- Constrained deterministic prose rendering that cites finding IDs/evidence keys and copies only
  computed hypotheses, findings, conditional actions, prerequisites, verification, and limits.
- Synthetic/source coordinate-plane replay with explicit non-geographic labelling and unavailable
  state when coordinates are absent.
- `synthetic_mock` participant result validation and descriptive analysis with withdrawn-record
  exclusion; no participant or ethics claim.
- Playwright screenshot and semantic accessibility regression script covering five desktop pages
  and mobile Home. Browser verification fixed duplicate Streamlit navigation, duplicate grid DOM
  IDs, and an accidental second main heading.
- Quality gates: Ruff passed; strict mypy passed; 261 tests passed; two-page PDF rendered and
  visually inspected; automated desktop/mobile browser audit passed with zero findings.

The new evidence remains synthetic or mock. Real participant evaluation, real selector
calibration, external rule validation, canonical Randy conversion, and direct launch are still
outside the implemented evidence boundary.

## v0.5 `OPS-02` Canonical-table Caching Status

Implemented for accepted ordinary generic directory and ZIP bundles. The cache-aware validator
reopens and fingerprints raw evidence before every lookup, then derives a content-addressed key
from raw bytes, adapter/validator versions, complete manifest mapping, canonical Pydantic/Arrow
schema, and cache format. It stores six strict Parquet tables plus checksummed validation metadata
outside the raw bundle. Verified warm reuse reconstructs the exact cold `BundleValidationResult`;
downstream deterministic metrics are identical.

Publication uses a private temporary directory, fsync, complete reread/equality verification, and
an atomic rename. A losing concurrent writer reuses the verified winning entry and removes its own
unpublished temporary directory. Existing valid entries are byte-idempotent. Stale, incompatible,
corrupt, unexpected, or symlinked entries are classified and never used, repaired, deleted, or
overwritten.
Rejected results are not cached. The ordinary non-cache and memory-bounded streaming paths remain
unchanged. SUMO and TOS source-specific adapters explicitly report caching unsupported.

Acceptance covers exact cold/warm result and metric equivalence, raw preservation, cache
byte-idempotency, all six table schemas including empty tables, directory/ZIP parity, every key
component, stale/incompatible/corrupt/symlink rejection, explicit raw/cache separation, and injected
write failure with no partial publication, plus concurrent-winner reuse without a temporary leak.
The generated 20,000-task benchmark recorded a 2.841765-second cold validate/publish path, five
verified warm hits with a 0.684838-second median,
exact result equality, unchanged raw hashes, and a changed-raw miss/new key. Peak memory is
Python-traced only and the measurement is local implementation evidence, not a city-scale or
deployment claim. The final OPS-02 gates passed: Ruff format/check across 464 Python files; strict
mypy across 457 configured files; all 877 tests with 86% statement coverage and 84% cache-engine
coverage; 35 generated JSON references byte-stable across consecutive regeneration; and all 81
generated/golden JSON documents parsed. The dependency lock, isolated source/wheel build, release
smoke, and all 1,217 checked local documentation links also passed.

## v0.5 `OPS-03` TrafficTwin Doctor Status

Implemented as an always-read-only typed library service and root `traffictwin doctor` command.
The default diagnosis records Python, the active TrafficTwin release, all core distributions,
optional Python distributions, optional external command locations, the built-in generic/SUMO/TOS
integration boundary, unknown TOS permissions, and complete capability summaries. Expected absent
optional tools and blocked direct/asynchronous launch remain visible without making the guaranteed
generic import-first runtime unhealthy.

Requested `--workspace` diagnosis parses a bounded non-symlinked v1.0 marker, required directory
layout, contained scenario declarations, and contained registry declaration. Registry diagnosis
uses the OPS-01 immutable read-only SQLite URI, deduplicating the same workspace/explicit target.
The `--bundle`/`--cache-root` pair uses the OPS-02 read-only raw re-fingerprint and exact entry
verifier. Local read/traverse and write access is reported through advisory probes; write access is
never exercised.

The four check states are `pass`, `warning`, `blocked`, and `unavailable`. Overall `healthy`,
`degraded`, and `blocked` states depend only on requested required checks. The CLI exits non-zero
only for `blocked`. The report and contract are strict, fingerprinted, available as JSON or text,
and explicitly record `read_only=true` and `mutations_performed=false`. There is no v1 installer,
migration, cache repair, workspace generation, permission change, external command execution,
network access, simulator launch, or scientific calculation.

Acceptance covers healthy runtime/workspace/current-registry states, absent optional dependencies,
corrupt-registry copies, stale cache, cache miss, permission-limited registry, unsafe workspace
paths, incomplete cache options, duplicate registry reconciliation, CLI exit/format behavior, and
golden contract stability. Input hashes and modification times remain unchanged, and a missing
cache root remains uncreated. See ADR-046 and `docs/doctor.md`.

`OPS-03` full quality gates passed: Ruff format/check across all 468 Python files; strict mypy
across all 461 configured source/test files; all 891 tests with 86% statement coverage and 87%
doctor coverage; byte-identical regeneration of all 36 generated JSON references; parsing of all
83 generated/golden JSON documents; dependency-lock validation; isolated source/wheel builds;
release smoke; 162-document and 1,236-local-link validation; and `git diff --check`. OPS-03 adds no
Streamlit page; the existing desktop/mobile semantic audit remains green with zero findings.

## v0.5 `OPS-04` RO-Crate Archival Export Status

Implemented for one accepted ordinary generic directory or ZIP bundle. A strict caller request
owns publication date/scope, citation details, persistent identifier, licence statements, and raw
permission. Three reconciled raw modes are available: `embed`, `reference`, and `exclude`.
Imported raw embedding and public imported references require explicit confirmed permission,
written basis, and a raw-evidence licence; public unknown/denied material must be excluded.

The builder reuses the ordinary validation, metric, EvidencePack, rule, provenance, and report
services with fixed caller-owned time. It emits attached RO-Crate 1.3 metadata, archive-specific
CFF 1.2.0 citation, the strict TrafficTwin research-object manifest, exact checksums, software and
method fingerprints, reports, and policy. Raw bytes are preserved unchanged when embedded;
derived local paths are redacted, and row-level samples require embed. Sorted stored ZIP members,
fixed timestamps/modes, a final raw re-read, in-memory verification, fsync, and atomic replacement
make identical inputs/request/runtime/method versions byte-identical.

The offline verifier enforces archive bounds/safety, fixed ZIP representation, CFF structure,
manifest/inventory reconciliation, the RO-Crate graph, exact sizes/hashes, and public-permission
policy. Unit, golden, integration, and CLI acceptance covers all raw modes, source/scope permission
gates, permitted public embed, byte determinism, path redaction, tampering, citation/graph content,
capability truth, and publish/verify behavior. SUMO/TOS remain explicitly unsupported for this v1
complete-artifact pipeline. See ADR-047 and `docs/research_objects.md`.

`OPS-04` full quality gates passed: Ruff format/check across all 472 Python files; strict mypy
across all 465 configured source/test files; all 905 tests with 86% statement coverage and 86%
research-object coverage; byte-identical regeneration of all 37 generated JSON references;
parsing of all 85 generated/golden JSON documents; dependency-lock validation; isolated
source/wheel build, install, and archive CLI smoke; release smoke; 171-document and
1,263-local-link validation; and `git diff --check`. The isolated wheel check also moved the
unconditionally imported `pypdf` package from development-only to runtime dependencies. OPS-04
adds no Streamlit page; existing UI behavior is unchanged.

## v0.5 `OPS-05` Generalised External-source Contract Status

Implemented as a strict runtime-checkable `ExternalSourceAdapter` protocol with `discover`,
`contract`, `validate`, and `inspect` operations. A closed deterministic v1 registry contains the
reviewed `sumo_results_v1` and `tos_data_read_only` references. Generic TrafficTwin bundles keep
their ordinary first-party workflow and expose OPS-05 capability truth without being relabelled as
an external source.

Discovery checks exact direct safe relative markers only. No match remains unknown, multiple
matches require explicit source ownership, and a symbolic-link root or marker blocks before deep
parsing. Inspection delegates to the existing source validator and publishes a path-free portable
summary containing validator/report identity, findings, source fingerprint, declared import state,
output counts, observed provenance, complete capability truth, conversion boundary, blockers, and
required evidence. It performs no launch, registry write, repair, mapping inference, conversion,
dynamic module discovery, or uploaded-code execution.

The reference implementations remain deliberately different. SUMO is `partial_canonical` only for
its exact compatible trip projection; summary snapshots and FCD remain source-specific or
unavailable. TOS is `aggregate_summary`: evaluation rows, source metrics, and replay views stay
source-labelled, with no canonical task, persistent vehicle, RSU, trip, or generic-bundle claim.
TOS licence and public redistribution permission remain `unknown`. Conversion labels are
non-ordinal and interface membership does not establish cross-source metric compatibility.

Unit, integration, golden, and CLI acceptance covers runtime protocol conformance, catalogue and
contract stability, distinct conversion/semantic profiles, capability manifests, public SUMO and
synthetic-schema TOS discovery/inspection, deterministic path-free output, raw non-mutation,
rejected packages, missing/ambiguous/explicitly mismatched adapters, symbolic-link refusal, unknown
rights, and generated references. See ADR-048 and
`docs/integration/external_source_contract.md`.

`OPS-05` full quality gates passed: Ruff format/check across all 480 Python files; strict mypy
across all 473 configured source/test files; all 919 tests with 86% statement coverage and 95%
external-source package coverage; byte-identical regeneration of all 38 generated JSON references;
parsing of all 87 generated/golden JSON documents; dependency-lock validation; isolated source and
wheel build/install plus external-contract CLI smoke; release smoke; 152-document and
1,292-local-link validation; and `git diff --check`. OPS-05 adds no UI page and makes no external
launch, schema-equivalence, metric-comparability, or publication-rights claim.

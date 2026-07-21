# Glossary

TrafficTwin: Import-first research software prototype for traffic and vehicular edge-computing what-if analysis.

OffloadLens: The VEC analysis module within TrafficTwin, focused on tasks, offloading decisions, latency, RSU pressure, and VEC diagnostics.

VEC: Vehicular edge computing; computation involving vehicles and roadside or nearby compute resources.

V2I: Vehicle-to-infrastructure offloading decision, represented internally as `v2i`.

V2V: Vehicle-to-vehicle offloading decision, represented internally as `v2v`.

RSU: Roadside unit; infrastructure element that may receive offloaded tasks.

Scenario seed: Versioned YAML scenario configuration represented by `ScenarioSeed`.

Scenario mutation: One deterministic, bounded EXP-02 operator applied to a copied valid bundle
explicitly labelled synthetic/evaluation. It is an experiment fixture transformation, not a claim
about real fault severity or simulator behavior.

Mutation ledger: The complete bounded list of changed source rows and files in an EXP-02 result,
including before/after fingerprints and field changes. Admitted ledgers are never truncated.

Run bundle: Directory or ZIP containing `manifest.yaml`, `seed.yaml`, and optional declared CSV files.

Canonical record: Internal Pydantic record with standard fields and source provenance.

Canonical chunk: Ordered provisional group of canonical records with source-file, logical-row, and
decoded-byte metadata, consumed synchronously during streaming validation.

Streaming canonicalisation: Opt-in row/byte-bounded generic parsing with exact temporary
disk-backed global checks; it does not mean live data.

EvidencePack: Versioned structured evidence object produced from validation and metrics; the only supported input to diagnostic rules.

Temporal evidence: Optional typed EvidencePack projection of one scalar `WindowedMetricSeries`.
It retains every ordinal and eligibility state, the metric direction, source fingerprint, and an
optional researcher-declared event.

Sustained degradation: R6 candidate episode consisting of the configured number of consecutive
eligible windows whose direction-aware adverse delta from an exact baseline reaches the declared
absolute threshold. It is not statistical drift or proven causality.

Recovery state: Bounded R6 classification after a declared event: recovered, not recovered within
the horizon, inconclusive because of gaps, insufficient horizon, or not applicable without an
event.

Declarative rule: A trusted-local static YAML definition admitted by TrafficTwin's closed bounded
threshold/boolean grammar and compiled into an ordinary deterministic `RuleResult`. It cannot
contain arbitrary code, imports, formulas, dynamic keys, or nested rules and is not a sandbox.

Declarative definition fingerprint: SHA-256 identity of the complete validated rule definition,
including predicates, thresholds, evidence contracts, findings text, follow-ups, and limitations.

Operational outcome disparity: R7 candidate pattern where supported completion-rate group values
span at least the configured absolute gap over exactly one selected vehicle-tier or execution-
target RSU dimension. It is not protected-attribute fairness, significance, geography, or cause.

DiagnosticReport: Versioned output from deterministic rule evaluation over an EvidencePack.

ResearchExportProjection: Bounded REP-01 renderer input containing copied table rows, figure
entries, source mode, warnings, and a canonical fingerprint from one already-computed typed
artifact. It contains no new metric, statistical, or diagnostic calculation.

LaTeX research fragment: Escaped `.tex` table fragment rendered from a
`ResearchExportProjection`. It is intended for `\input` inside a researcher-owned document and is
not a complete dissertation template.

Static research figure: Self-contained SVG or invariant PDF rendered from the same REP-01
projection as its table. Signed bars do not imply favourability; rule categories are not
probabilities.

AnalystArtifactReference: Path-free REP-02 target containing a closed artifact kind, identifier,
and optional exact SHA-256 artifact fingerprint.

AnalystAnnotation: Immutable sequenced author label, exact note, human decision label, timestamp,
and typed target stored separately from computed evidence. It is commentary, not a TrafficTwin
finding, approval, authenticated signature, or recommendation.

AnalystAnnotationHistory: Bounded ascending page from the append-only registry stream with an
explicit continuation state and exact ordered-page fingerprint.

ReportClaimSnapshot: Prose-free REP-03 representation of one typed metric, rule, or comparison
claim, retaining availability, machine status, exact value, unit, reason codes, and closed typed
details without renderer text.

StructuredReportDiff: Compatibility-gated deterministic comparison of two typed report payloads,
classifying sections and claims as unchanged, added, removed, changed, or unavailable at canonical
JSON Pointer paths. It is descriptive and non-causal.

Nearest flip: The exact verified one-parameter configuration boundary that changes an eligible
non-triggered R5, R7, or R8 result to triggered while discrete support remains unchanged. It is
descriptive sensitivity, not a recommended or calibrated threshold.

NearestFlipAnalysis: Versioned DIA-05 artifact containing source/candidate configs and statuses,
constraints, unit/delta, ties, EvidencePack/result fingerprints, limitations, and explicit
unsupported/not-applicable reasons.

ThresholdSensitivityReport: Versioned DIA-06 artifact retaining a complete bounded R5/R7/R8
threshold grid, ordinary statuses, fixed config, stability, sampled transition intervals, exact
DIA-05 output when admissible, provenance, and explicit non-persistence limitations.

Cross-rule reasoning: The bounded DIA-07 pass over completed diagnostic results. It records only
declared conflict, corroboration, or presentation-suppression relationships with exact evidence
overlap and precedence; it does not infer causes, probabilities, rankings, or confidence changes.

CrossRuleReasoningReport: Versioned additive artifact that retains and fingerprints every original
`RuleResult`, records typed declared relationships, and makes suppressed, unclassified, or
unresolved result IDs explicit.

Presentation suppression: A DIA-07 display/actionability effect caused only by an explicit R0
`blocked_rules` target. The target result remains present and unchanged; suppression is not
deletion, invalidation, or a confidence adjustment.

Sampled flip interval: Two adjacent threshold-grid points whose triggered membership differs. It
brackets a sampled transition and is not an exact, calibrated, or recommended boundary.

Historical replay: Timestamp-driven replay over imported or synthetic records, not live data.

Fixed window: An aligned half-open interval `[start,end)` used to filter canonical records before
the ordinary metric engine. Exact end-boundary records enter the next interval.

Window coverage: The fraction of a grid window overlapped by the requested analysis range. It
does not measure sensor uptime, sampling completeness, or confidence.

Cohort outcome: A later result attributed to the interval in which its record began. Windowed
task metrics use task arrival cohorts and trip metrics use trip departure cohorts.

Sample P99 latency: The deterministic 99th percentile of valid task latencies using sorted linear
rank-`n-1` interpolation. It is a descriptive sample statistic, not a maximum or confidence bound.

Task-energy contract: A strict manifest declaration that one canonical `energy_j` value represents
per-task total energy in joules and fixes eligibility for per-task, completed-task, and
energy-delay metrics. A column name or unit alone is insufficient.

Energy-delay product: Per eligible completed task, total energy in joules multiplied by latency in
milliseconds. TrafficTwin reports the mean in `J*ms/task` only under a compatible energy contract.

Completed-task energy anomaly: R8 candidate pattern where the fully covered mean task energy for
completed tasks reaches an inclusive provisional `J/task` threshold with sufficient completed-task
support under the exact v1.0 task-energy contract. It is not a statistical anomaly, causal finding,
hardware benchmark, external standard, or optimisation recommendation.

Operational fairness: Descriptive balance or disparity across supplied compute/resource groups,
currently stable vehicle tiers or exact RSU IDs. It is not protected-attribute, demographic, or
causal fairness.

Operational-fairness policy: The versioned admission contract requiring at least two groups, two
eligible observations in every observed group, and complete in-scope coverage. Results carry both
policy and exact group-set fingerprints.

Jain index: `(sum(x)^2)/(n*sum(x^2))` over admitted group means. Larger values indicate greater
numeric equality within that set, but do not establish good outcomes; an all-zero set is undefined.

Task-to-RSU target contract: A strict declaration that `target_id` on a canonical V2I task is its
observed executing RSU and must join exactly, with complete coverage, to canonical `rsu_id`.

Vehicle spatial-grid contract: A strict declaration of vehicle position meaning, a named source
coordinate frame, metre units, fixed origin/cell dimensions, floor assignment, and complete x/y
coverage.

Source-frame cell: A deterministic grid bin in the declared source coordinate plane. It is not a
latitude/longitude or geographic area unless separate CRS evidence establishes that meaning.

Custom metric plugin: A reviewed local deterministic Python callable registered explicitly with a
strict contract. It receives only declared deep-copied canonical inputs and is not uploaded,
automatically discovered, or sandboxed.

Plugin contract fingerprint: SHA-256 identity of the complete custom metric definition, inputs,
availability, output, version, trust, window, unavailable, and provenance contract. Equal
fingerprints are required for scalar comparison.

Evaluated-input repeatability: Equality of two canonical plugin outputs produced from fresh copies
of the same admitted input. It is evidence for that run, not proof of global purity or validity.

Synthetic fixture: Small hand-auditable test/demo data created for engineering verification.

Measurement impairment: An optional EXP-03 deterministic transformation of selected generated
observation fields/rows under explicit bounds and a separate seed. It is a software-robustness
fixture, not a calibrated real sensor or packet-loss model.

Measurement audit: The strict manifest artifact binding an EXP-03 configuration to every enabled
field's units/bounds/error extrema and each dropout table's exact before/dropped/retained counts and
selection identity.

Import-first: Architecture where completed bundles are always supported and direct launch is optional only when evidenced by an adapter.

Task completion rate: Completed valid task records divided by generated valid task records.

Saturation episode: Maximal contiguous per-RSU sequence where utilisation is at or above the configured saturation threshold.

Diagnostic hypothesis: Evidence-based candidate explanation requiring verification; not a proven root cause.

Capability manifest: Three-valued adapter capability declaration using `true`, `false`, and `unknown`.

Provenance: Metadata and trace links connecting outputs to seed, run, environment, source files, random seed, versions, algorithms, metric definitions, validation findings, and source rows where available.

ProvenanceTrace: Versioned read-only trace graph containing typed nodes and edges from a metric, rule result, source row, or run back through the deterministic TrafficTwin pipeline.

Source-row preview: Bounded-output read-only inspection of a declared CSV, gzip-CSV, or Parquet row that shows decoded values, canonical mapping, declared format/units, and validation findings without mutating the source file.

Fingerprint: Deterministic hash used to identify bundle/evidence/report content for reproducibility checks.

Golden test: Test comparing deterministic output against a reviewed expected fixture.

Common-seed pair: Baseline and variation observations with the same predeclared random seed and
compatible experiment, metric, environment, unit, source, and semantic contracts.

Paired estimand: The predeclared quantity estimated from matched experimental units. STA-01 uses
the mean variation-minus-baseline scalar metric difference in the original unit.

Paired sign-flip test: A two-sided randomisation test that changes paired-difference signs under a
sharp zero-effect/exchangeable-sign null. It is exact through 16 pairs and deterministically sampled
above that in STA-01.

Matched-pairs rank-biserial correlation: A paired effect size comparing positive and negative
absolute-rank sums over non-zero differences; ties remain separately counted.

Prospective power analysis: A planning calculation performed before confirmatory results using a
declared target effect, variance, alpha, target power, and method assumptions. It is not evidence
that a completed study was adequately powered.

Paired-difference variance: The prospective variance of variation-minus-baseline differences
across common-seed pairs in the metric's unit squared. It is not a run-level variance, standard
deviation, or standard error.

Planning-aid label: The mandatory STA-05 qualification that a required pair count is an estimate
under declared assumptions, not a guarantee of significance, complete runs, or external validity.

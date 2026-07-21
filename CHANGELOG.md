# Changelog

## v0.1.0 - Standalone Prototype

Prepared the TrafficTwin repository as a self-contained research-software prototype.

Added:

- deterministic standalone synthetic scenario and run generator;
- reproducible demo workspace commands;
- multi-seed synthetic low-pressure experiment for R3 evidence;
- deterministic Markdown and standalone HTML report export;
- standalone Streamlit launcher command;
- release metadata and package-build guidance;
- GitHub Actions CI workflow;
- standalone demo, synthetic model, report export, and release documentation.

Notes:

- Licence not yet specified.
- Full Randy/VEC, SUMO, live data, LLM, XAI, and simulator launch support remain out of scope.

## Unreleased

Implemented v0.5 `OPS-05`, the generalised external-source contract:

- a strict runtime-checkable `discover`/`contract`/`validate`/`inspect` protocol, closed reviewed
  adapter registry, exact direct-marker discovery, and explicit no-match/ambiguity/symlink refusal;
- portable path-free validation/provenance inspections, complete three-valued capabilities,
  confirmed/inferred/unknown/unsupported semantics, non-ordinal conversion profiles, typed blockers,
  and required evidence;
- distinct public SUMO `partial_canonical` trip and private TOS `aggregate_summary` reference
  implementations without canonical, metric, permission, or scientific-equivalence invention;
- thin `traffictwin integration external` contract/discover/inspect commands, generated schema and
  contract, exact golden, unit/integration/CLI safety and non-mutation tests, ADR-048, and complete
  user/architecture/status documentation.

Implemented v0.5 `OPS-04`, permission-aware deterministic RO-Crate archival export:

- attached RO-Crate 1.3 ZIPs with archive-specific CFF 1.2.0 citation, strict TrafficTwin
  inventory, checksums, typed validation/metrics/evidence/diagnostics/provenance/reports, and
  software/method fingerprints;
- explicit raw `embed`, `reference`, and disclosure-minimising `exclude` modes with imported/public
  permission and licence gates, no inferred rights, and no raw-byte rewriting;
- fixed caller-owned timestamps, sorted stored ZIP members, path redaction, final raw re-read,
  bounded in-memory verification, and atomic publication;
- repository `CITATION.cff`, library/CLI create-contract-verify workflows, capability truth,
  generated schema/contract/help, golden/integration/unit tests, usage guide, and ADR-047.
- corrected packaged CLI runtime metadata by making its unconditionally imported `pypdf`
  dependency a core dependency rather than development-only.

Design:

- added the canonical no-timeline TrafficTwin v0.5 specification;
- incorporated all 39 approved catalogue capabilities across ingestion, metrics, diagnostics,
  statistics, provenance, experiments, reporting, and research operations;
- kept every new capability explicitly planned, partial, or evidence-blocked until its code,
  tests, documentation, provenance, and acceptance gates exist;
- preserved v0.4 as the historical rationale and supervisor-meeting traceability record.

Implemented v0.5 `REP-01`, deterministic LaTeX tables and static research figures:

- one bounded typed projection over existing metric, comparison, STA-01 study, and diagnostic
  artifacts, with no reporting-layer scientific calculation;
- escaped package-free `.tex` fragments and optional self-contained SVG/invariant PDF figures;
- shared projection fingerprints, deterministic ordering, explicit source mode, visible
  availability/warnings/units/methods/statuses, and absolute-path redaction;
- signed-linear numeric figures with no favourability inference and categorical rule figures with
  no probability conversion;
- exact-file staging, explicit overwrite, symbolic-link refusal, and path-free checksummed receipts;
- public contract, CLI commands, Reports UI/service, generated schemas/help/contract, exact
  goldens, real minimal-document compile coverage, usage guide, and ADR-039.

Implemented v0.5 `REP-02`, append-only analyst annotations:

- closed path-free typed targets with optional exact artifact fingerprints and stored-target
  verification;
- bounded author/note/decision records with UTC time, monotonic SQLite sequence, content-bound ID,
  pagination, and ordered-history fingerprints;
- database triggers that reject annotation update/delete and correction-by-later-append semantics;
- report target declarations plus complete-or-refuse matching history outside computed sections,
  claim references, metrics, rules, provenance, availability, and scientific fingerprints;
- distinct escaped Markdown, standalone HTML, and deterministic PDF annotation presentation;
- public models/contract, registry API, CLI commands, Reports UI/service, generated schemas/help/
  contract, golden history, usage guide, and ADR-040.

Implemented v0.5 `REP-03`, typed structured report diffing:

- prose-free typed claim snapshots for run, diagnostics, comparison, and full reports;
- strict schema/type/source-mode/denominator/inventory compatibility with typed unavailable codes;
- deterministic unchanged/added/removed/changed/unavailable section and claim classifications;
- canonical JSON Pointer field changes, scientific and complete-result fingerprints, and explicit
  exclusions for rendering, timestamps, warnings, labels, commands, and analyst annotations;
- bounded strict JSON parsing plus complete JSON and non-causal Markdown exports;
- structured `.json` report output, public library/contract, CLI commands, Reports UI/service,
  generated schemas/help/contract, exact golden output, usage guide, and ADR-041.

Implemented v0.5 `REP-04`, deterministic one-page executive summaries:

- strict projection from one compatible saved typed report with no scientific recomputation;
- complete total/available/unavailable/per-kind and bounded-omission disclosure;
- closed five-slot quota selection over existing rules, comparisons, unavailable evidence, and
  metrics, with exact claim identities and fingerprints;
- retain-all-or-refuse mandatory/source warnings and exact report limitations;
- relative fingerprinted source/claim provenance links, absolute-path redaction, and escaped
  Markdown/HTML/PDF rendering;
- invariant exactly-one-page A4 verification with explicit overflow refusal instead of caveat
  deletion;
- JSON/Markdown/HTML/PDF library, CLI, Reports UI/service, generated schema/help/contract, exact
  golden projection, usage guide, visual PDF QA, and ADR-042.

Implemented v0.5 `REP-05`, deterministic read-only registry search:

- six closed labelled categories for findings, append-only annotations, report metadata/text,
  runs, experiments, and evidence references;
- on-demand bounded projection with SQLite `mode=ro`/`query_only` and no persistent FTS/index or
  registry mutation;
- Unicode NFKC case-folded lexical AND matching, published integer field/phrase/token weights,
  stable ties, complete counts, bounded snippets, and exact result fingerprints;
- absolute POSIX/Windows/home/file-URI path redaction before matching, including query redaction;
- direct non-symlink report admission, text/file/candidate ceilings, PDF metadata-only handling,
  and visible skips/refusals;
- public models/contract, CLI commands, Search UI/service, generated schemas/help/contract,
  category/ranking/read-only/privacy tests, usage guide, browser QA, and ADR-043.

Implemented v0.5 `OPS-01`, versioned transactional registry migrations:

- five contiguous SQLite schema versions for core registry, import/analysis, protocol,
  experiment-evidence, and annotation objects;
- authoritative `PRAGMA user_version` plus immutable name/checksum/timestamp migration history;
- complete pending plan, ledger updates, version advances, boundary validation, and `quick_check`
  inside one `BEGIN IMMEDIATE` transaction with full-invocation rollback;
- empty, formal v1-v4, and known unversioned repository-era schema admission without stored-payload
  rewriting;
- fail-closed unknown/malformed/tampered/future/downgrade behavior and byte-idempotent completed
  targets;
- one schema owner shared by Registry and ProtocolTracker, read-only status inspection, public
  models/contract, CLI commands, capabilities, generated schemas/help/contract, historical upgrade
  and injected-failure tests, usage guide, and ADR-044.

Implemented v0.5 `OPS-02`, content-addressed canonical-table caching:

- six strict Apache Parquet canonical tables plus checksummed typed validation metadata, stored
  outside raw directory/ZIP evidence;
- exact keying by raw fingerprint, adapter and validator versions, complete manifest mapping,
  canonical Pydantic/Arrow schema, and cache format;
- mandatory raw reopen/fingerprint before every hit, strict checksum/schema/row/report/evidence/
  count verification, and exact cold/warm `BundleValidationResult` equivalence;
- temporary write, full reread/equality verification, fsync, atomic publication, valid-entry byte
  idempotency, and no partial entry after injected write failure;
- visible miss/written/hit/stale/incompatible/corrupt/unavailable/write-failed states, with bad or
  symlinked entries never used, automatically deleted, or overwritten;
- generic-only capability boundary, public models/contract, CLI/library workflows, generated
  schema/help/contract, exact golden, usage/benchmark documentation, and ADR-045.

Implemented v0.5 `OPS-03`, read-only environment and workspace diagnosis:

- one root `traffictwin doctor` command with human-readable and strict JSON reports plus a
  separately fingerprinted method contract;
- explicit pass, warning, blocked, and unavailable checks with required-versus-optional semantics
  and healthy/degraded/blocked aggregation;
- Python/core/optional dependency, discovered-command, integration, and complete adapter-capability
  reporting without running commands, launching simulators, or making network requests;
- bounded standalone-workspace structure and path containment checks, immutable OPS-01 registry
  inspection, and immutable OPS-02 selected-cache inspection;
- advisory read/write permission evidence, exact target reconciliation, visible remediation, and
  report assertions that the operation is read-only and performed no mutation;
- healthy, corrupt, stale-cache, cache-miss, permission-limited, and unsafe-declaration coverage,
  CLI exit behavior, generated schemas/help/contract, exact golden, usage guide, and ADR-046.

Implemented v0.5 `STA-01`, common-seed paired statistical studies:

- strict predeclared one-metric baseline-versus-variation plans over registered experiments;
- exact random-seed pairing with complete missing, duplicate, unavailable, and incompatibility audit;
- original-unit mean paired effect, deterministic percentile bootstrap interval, and two-sided
  exact/seeded-Monte-Carlo sign-flip test;
- paired Cohen's dz and matched-pairs rank-biserial effects, with Cliff's delta explicitly excluded
  from the paired primary design;
- versioned method contract, complete fingerprints/provenance, JSON/Markdown/CSV exports, CLI, and
  thin Streamlit page;
- known-distribution, determinism, immutability, golden, CLI, service, and UI acceptance tests plus
  ADR-028;
- the STA-01 artifact itself performs no N-way ranking, equivalence, regression gate, power
  analysis, causal, or external-validity claim.

Implemented v0.5 `STA-02`, N-way common-seed policy ranking:

- strict predeclared multi-policy plans over registered scenario families and common random seeds;
- one complete compatible seed-row denominator for every selected policy, with missing,
  unavailable, duplicate, and incompatible evidence retained in typed audits;
- ordinary winner-map objective, standard competition rank, numerical ties, winners, and regret
  reused rather than reimplemented;
- deterministic joint paired-seed bootstrap intervals, rank distributions, top-rank frequency,
  and family-specific derived seeds;
- versioned method/config/source fingerprints, JSON/Markdown/CSV exports, CLI, capability flags,
  and the existing thin Statistical Study page;
- constructed, golden, compatibility, determinism, CLI, service, and UI evidence plus ADR-029;
- no interval-based equivalence, post-hoc pairwise test, imputation, subgroup selection, causal,
  or external-validity claim.

Implemented v0.5 `STA-03`, predeclared paired equivalence testing:

- strict symmetric absolute margins in the metric's original unit with mandatory practical,
  literature, or explicitly provisional basis and written justification;
- unchanged STA-01 exact common-seed cohort, exclusion audit, semantic compatibility, and source
  fingerprints rather than a second pairing implementation;
- paired-mean Student-t TOST with both one-sided hypotheses/p-values and the reconciled
  `100 × (1 - 2 alpha)%` interval;
- bounded `equivalence_demonstrated` and `equivalence_not_demonstrated` conclusions, with explicit
  insufficient, incompatible, and zero-variance unavailable states;
- deterministic Student-t probability/quantile implementation pinned against known references;
- versioned JSON/Markdown/CSV artifacts, method contract, capability flags, CLI, synthetic demo,
  and a third mode on the thin Statistical Study page;
- known-equivalent, boundary, outside-margin, non-significant-but-not-equivalent, golden, CLI,
  service, and Streamlit acceptance evidence plus ADR-030;
- no universal margin, post-hoc margin choice, unpaired inference, non-inferiority, causality,
  external-validity, regression-gate, or power claim.

Implemented v0.5 `STA-04`, versioned golden-contract regression gates:

- completed `MetricCollection` and STA-01 `StatisticalStudy` subjects with strict typed contexts;
- candidate-versus-approved golden lifecycle with explicit approver and acceptance note;
- per-scalar finite expected values, units, implementation versions, and absolute/relative
  tolerances using the inclusive `max(absolute, relative × |expected|)` decision rule;
- exact-source fixture and compatible-context repeated-run policies, with mismatch or missing
  evidence retained as unavailable rather than numerical failure or zero;
- complete pass/fail/unavailable assertion audit, deterministic fingerprints, JSON/Markdown/CSV,
  and distinct CI exit codes `0`, `1`, and `2`;
- golden generation/evaluation CLI, fourth Statistical Study UI mode, synthetic demo golden/gate,
  generated contract/schema/help, constructed/golden/service/Streamlit tests, and ADR-031.

Implemented v0.5 `STA-05`, prospective paired common-seed power planning:

- strict predeclared target effect, paired-difference variance, two-sided alpha, target power,
  original unit, evidence bases, written justifications, references, and bounded replicate search;
- deterministic two-sided paired-mean normal-approximation power with the smallest qualifying
  integer, achieved power, `n - 1` power, and baseline-plus-variation run count;
- typed unavailable states for zero effect, non-positive variance, and an exceeded declared search
  ceiling, without imputation or false zero output;
- mandatory planning-aid qualification plus machine-readable small-pilot, small-planned-sample,
  synthetic, and provisional labels and warnings;
- JSON/Markdown/CSV artifact and method contract, capability flags, CLI, fifth Statistical Study
  UI mode, explicitly synthetic demo export, generated schemas/help/contract, and ADR-032;
- normal-reference, minimality, monotonicity, validation, determinism, golden, CLI, service,
  capability, demo, and Streamlit acceptance evidence;
- no retrospective observed power, automatic extraction from completed results, sign-flip/TOST/
  N-way power, attrition model, simulator execution, causal, or external-validity claim.

Implemented v0.5 `PRO-01`, accepted-row difference provenance:

- both complete baseline/variation canonical-row eligibility ledgers retained behind the existing
  ordinary metric-comparison compatibility contract;
- a closed direct scalar count/sum/mean/rate formula registry with independent run denominators,
  negative baseline terms, positive variation terms, and exact delta reconciliation;
- percentile, extrema, distinct, episode, grouped, fairness/spatial, and uncontracted-plugin
  lineage without fabricated row weights; mapping-valued differences remain unavailable;
- deterministic typed artifact/fingerprint, source fingerprints, synthetic labels, exclusions,
  reason codes, limitations, and mandatory JSON/CSV non-causality language;
- public contract and contributor CLI commands, What-if Compare view, generic capability flag,
  explicitly synthetic demo exports, generated schema/help/contract, golden projection, and
  ADR-033;
- no row-ID pairing, implicit mapping flattening, feature-importance, influence, causal, or
  external-validity claim.

Implemented v0.5 `PRO-02`, deterministic bounded provenance graph export and view:

- a typed `ProvenanceGraphView` projected from the existing DAG without recalculating lineage;
- deterministic root-centred breadth-first selection with default/hard node and edge limits,
  retained root/direction, and exact omission counts;
- stable safe node IDs, stable hash-based edge IDs, timestamp-independent graph identity, and
  exact bounded-view fingerprints;
- default recursive local-path redaction plus a structure-only profile that removes descriptions,
  attributes, and source references without claiming anonymity;
- deterministic escaped Graphviz DOT and parser-tested typed GraphML with exact golden fixtures;
- `provenance graph-contract`, extended CLI graph exports, Streamlit graph/node inspection,
  DOT/GraphML downloads, synthetic demo outputs, generated schema/help/contract, and ADR-034;
- no graph database, source-path traversal, Graphviz runtime requirement for generation,
  deterministic-layout claim or causal attribution.

Implemented v0.5 `PRO-03`, explicit report-claim provenance completeness:

- shared typed metric/rule/comparison claim inventories for run, diagnostics, comparison, and full
  deterministic report templates, with unique report-local IDs;
- an explicit denominator that retains unavailable claims plus named presentation, metadata,
  validation/evidence-inventory, and comparison-context exclusions;
- mutually exclusive source-row-complete, aggregate-only, and unavailable classifications using
  directed trace depth, complete non-empty accepted-canonical-row ledgers, strict rule
  dependencies, and complete two-side PRO-01 comparison lineage;
- an unweighted source-row-complete fraction, transparent aggregate-or-better fraction, no partial
  credit, and null/no-claims behavior for an empty denominator;
- timestamp-independent artifact/claim fingerprints, full JSON/CSV inventories, public method
  contract, CLI commands, Provenance Explorer and Comparison views, synthetic demo exports,
  generated schema/help/contract, golden projection, and ADR-035;
- no prose parsing, rejected-raw-row completeness claim, truth/quality/causal interpretation,
  source-specific TOS/SUMO claim, or LLM calculation.

Implemented v0.5 `EXP-01`, bounded deterministic parameter-sweep composition:

- one strict synthetic-config or scenario-seed base plus a closed scalar parameter catalogue;
- hard limits of four axes, 16 unique finite values per axis, 256 complete Cartesian points, and
  16 selected core response metrics, with no silent truncation;
- deterministic parent-linked seed snapshots and request/base/point/seed/bundle/result
  fingerprints carrying every ordered parameter assignment;
- labelled local synthetic-bundle mode delegated to the existing generator, validator, and core
  metric engine, with finite numeric response rows and explicit unavailable/non-numeric states;
- external request mode fixed to `not_executed`, false direct-launch support, null launcher and
  command, and ordinary import-first return of any later completed output;
- transactional exact-destination materialisation, explicit overwrite, unchanged base/raw inputs,
  and `synthetic_evaluation=true` in every mode;
- public method contract, JSON/CSV/YAML artifacts, CLI, thin Parameter Sweep page, example request,
  generated schemas/help/contract, deterministic goldens, and ADR-036;
- no Randy/VEC/TOS/SUMO/training launch, orchestration queue, arbitrary-path mutation, zero-filled
  missing response, optimisation, causality, calibration, simulator-fidelity, or external-validity
  claim.

Implemented v0.5 `EXP-02`, deterministic scenario-mutation operators:

- admission restricted to ordinarily valid bundles explicitly labelled synthetic/evaluation,
  with imported/raw and inferred/canonicalised manifests rejected;
- exactly one closed row-dropout, timestamp-jitter, or exact-ID RSU-removal operator per request,
  over a copied declared uncompressed CSV target;
- SHA-256-plus-seed row choice/delta semantics, bounded timestamps, exact row/file change ledgers,
  stable parent/plan/result fingerprints, and no process-global randomness;
- immutable parent files, byte-identical non-target files, no invented rerouting or target-ID
  changes, ordinary validation of the derived bundle, and transactional exact-destination output;
- strict file/byte/row/change/request bounds, protected/symlink destination refusal, and explicit
  overwrite only;
- public contract, YAML request, JSON mutation manifest, CLI, thin Scenario Mutations page,
  example, generated schema/contract, deterministic golden, and ADR-037;
- explicit synthetic/evaluation, unchanged-raw-source, no-external-launch, and no-calibration or
  causal/fidelity claim labels.

Implemented v0.5 `EXP-03`, deterministic synthetic measurement noise and dropout:

- one closed separately seeded bounded-uniform model over generated vehicle position/speed,
  traffic speed/count, and infrastructure utilisation/queue measurements;
- exact SHA-256-ranked per-table observation dropout with a 0.95 cap and at least one retained row;
- independent field hashes, configured error bounds, domain clamps, and unchanged task/trip/
  incident/timestamp/outcome/routing evidence;
- strict configuration/field/dropout semantic reconciliation, complete manifest audit and
  fingerprints, synthetic/not-calibrated/raw-unchanged declarations, and impairment-qualified
  bundle/run IDs;
- transactional protected-path-aware generated-bundle publication and disabled-path byte
  compatibility;
- public contract, complete YAML example, CLI, working Scenario Builder controls, generated
  schemas/help/contract, deterministic golden, usage guide, and ADR-038;
- no real sensor/network/packet-loss calibration, correlated error model, external simulator
  launch, policy response, causal claim, or external-validity claim.

Implemented v0.5 `ING-01`, the import-only Eclipse SUMO output adapter:

- versioned `sumo-source.yaml` provenance/licence/checksum contract for SUMO 1.27.x;
- safe immutable `tripinfo.xml` and `summary.xml` validation with stable codes;
- completed/incomplete canonical trip mapping and source-only never-departed records;
- typed summary-step evidence without mislabelling occupancy as interval traffic count;
- deterministic trip metrics, idempotent registry import, CLI commands, and Streamlit workflow;
- official licensed Eclipse SUMO square-scenario acceptance fixture and ADR-011;
- FCD, person/container canonicalisation, and direct/asynchronous launch remain unavailable.

Implemented v0.5 `ING-02`, the confirmation-gated manifest inference wizard:

- versioned deterministic file/field suggestions from exact headers, documented aliases, and
  bounded distinctive task value patterns;
- published file/column/row/value limits, complete source hashes, and stale-draft rejection;
- explicit ambiguity, missing-unit, duplicate-header/source-use, and unsupported-edit rejection;
- non-executable inference drafts plus checksummed, user-confirmed canonicalisation artifacts;
- bundle-manifest template application with embedded confirmation provenance;
- Typer infer/confirm/files/apply commands and an editable Streamlit workflow;
- synthetic value-pattern and deliberate-ambiguity fixtures, golden projections, and ADR-012.

Implemented v0.5 `ING-03`, declared Parquet and gzip-CSV input:

- explicit backward-compatible `format` and optional CSV `compression` manifest fields;
- one generic decoder feeding the existing mapping, unit, canonical, metric, and evidence paths;
- immutable raw checksums and exact-byte bundle identity documented by ADR-013;
- flat scalar Parquet admission, duplicate-column rejection, and a decoded-table safety bound;
- gzip/Parquet CLI, UI-service, ZIP, registry-idempotency, and row-provenance coverage;
- golden canonical and metric equivalence against the baseline CSV bundle.

Implemented v0.5 `ING-04`, failure-isolated batch bundle import:

- bounded explicit path/glob expansion with deterministic sorting and overlap deduplication;
- typed consolidated input issues/counts and ordered per-bundle validation/import outcomes;
- unchanged single-bundle fingerprint, idempotency, conflict, and registry transaction semantics;
- continued processing after an invalid, conflicting, or locally failed neighbour;
- text/JSON/CSV CLI exports and Streamlit batch controls with JSON download;
- unit, integration, golden, UI-service, and local runtime/memory/equivalence evidence plus ADR-014.

Implemented v0.5 `ING-05`, memory-bounded streaming canonicalisation:

- explicit row/decoded-byte chunking for declared CSV, gzip-CSV, and flat scalar Parquet;
- stable logical source rows and output equivalence across chunk boundaries;
- exact disk-backed duplicate-task and vehicle/RSU-reference reconciliation;
- unchanged raw fingerprints, ordinary importer limits, and registry idempotency/conflicts;
- typed summary/consumer APIs, CLI validation/import, and Streamlit controls;
- unit, integration, golden, ZIP, CLI, UI, generated-fixture runtime/memory/equivalence evidence,
  and ADR-015.

Implemented v0.5 `MET-01`, deterministic fixed-window metrics:

- aligned half-open `[start,end)` windows with explicit or inferred ranges, versioned table
  anchors, include/exclude partial edges, visible unavailable gaps, and bounded request size;
- all 50 definitions present at acceptance reuse the ordinary engine (later MET-03/MET-04 additions
  bring the current window-applicable total to 54) and carry
  window scope, effective bounds, requested-range coverage, availability, fingerprint, and
  warnings; pairwise comparison definitions remain excluded;
- CLI, Temporal Metrics UI, JSON download, per-window provenance traces, and complete accepted-row
  contribution ledgers;
- unit/property-style, integration, golden, CSV/gzip/Parquet, collected-streaming, UI-service, and
  Streamlit AppTest evidence plus ADR-016.

Implemented v0.5 `MET-02`, the complete task-latency percentile family:

- retained P50/P95 and added P99 with sorted linear rank-`n-1` interpolation;
- versioned method, percentile fraction, valid sample count, and configured minimum travel with
  every available or unavailable latency percentile;
- explicit zero-observation, singleton, and unmet-minimum behavior without zero substitution;
- whole-run, fixed-window, aggregation, comparison, report, Run Overview, and provenance surfaces;
- exact unit and golden projections plus ADR-017.

Implemented v0.5 `MET-03`, the contract-gated task-energy metric family:

- strict manifest semantics for one per-task total-energy value in joules, including completed-task
  and energy-delay eligibility plus a stable source-independent contract fingerprint;
- deterministic mean energy per observed task, mean energy per completed task, and mean
  energy-delay product with explicit eligible/population counts and coverage;
- unavailable results without the contract, partial completed-task results when coverage is
  incomplete, negative-energy validation, and no zero substitution;
- cross-source comparison only for identical semantic fingerprints;
- whole-run/window/aggregation/comparison/report/Run Overview/CLI/provenance support for contracted
  generic and labelled synthetic bundles, while SUMO/TOS canonical energy remains unavailable;
- exact golden values, generated contracts, and ADR-018.

Implemented v0.5 `MET-04`, the evidence-gated operational fairness family:

- strict fingerprinted policy requiring two exact groups, support of two per group, and complete
  coverage without dropping missing/thin groups;
- stable vehicle-tier completion grouping, maximum gap, and Jain index;
- exact-RSU mean capacity-normalised load grouping, maximum gap, and Jain index;
- explicit non-protected interpretation, all-zero Jain unavailability, and policy/group-set-
  compatible scalar comparisons;
- whole-run/window/aggregation/comparison/report/CLI/provenance and Fairness Evidence UI support;
- current SUMO/TOS contracts remain unavailable rather than relabelling source summaries;
- exact unit/golden/source-boundary evidence and ADR-019.

Implemented v0.5 `MET-05`, contract-gated spatial and per-RSU breakdowns:

- independent strict task-target and vehicle-grid contracts with stable fingerprints;
- exact V2I task count, completion, and completed-observed deadline misses by execution-target RSU;
- vehicle observation count, distinct vehicles, and mean speed by fixed source-frame grid cell;
- complete target/join and coordinate coverage requirements, with partial/null latency or speed
  support and no zero substitution;
- no nearest-RSU assignment, task-position interpolation, geography/CRS inference, or causality;
- whole-run/window/report/CLI/provenance and Spatial & RSU Evidence UI support;
- current SUMO/TOS contracts remain explicitly unavailable;
- exact unit/golden/source-boundary evidence and ADR-020.

Implemented v0.5 `MET-06`, the trusted local custom metric plugin API:

- explicit in-process registration with strict versioned definition, input, availability, output,
  time-anchor, unavailable, trust, determinism, and provenance contracts;
- rejection of malformed definitions, core/duplicate keys, mixed plugin versions, unknown fields,
  and inconsistent table/field/anchor declarations before evaluation;
- bounded deep-copied canonical input views and two-run canonical-output repeatability checks;
- stable isolated unavailable reasons for admission, execution, nondeterminism, invalid output, and
  plugin-declared missing evidence without suppressing core or neighbouring metrics;
- whole-run, fixed-window, SUMO canonical-trip, evidence, comparison, and embedded-contract
  provenance integration with complete declared-input row ledgers;
- machine-readable CLI/generated API contract and About-page trust-boundary disclosure;
- unit, integration, golden, UI, comparison, window, provenance, and capability evidence plus
  ADR-021; uploaded/dynamic code loading and sandbox claims remain excluded.

Implemented v0.5 `DIA-01`, deterministic R6 temporal degradation and recovery diagnosis:

- typed `TemporalEvidence` attached to the existing EvidencePack boundary from one compatible
  fixed-window metric series;
- complete visible grid admission with distinct excluded, low-coverage, unavailable, partial,
  invalid, non-numeric, and incompatible window states;
- objective-direction-aware absolute adverse deltas, exact consecutive baselines, sustained-window
  detection, optional researcher-declared event alignment, and bounded recovery classifications;
- conservative insufficiency when baseline gaps, observation gaps, short horizons, absent direction,
  or incompatible contracts prevent a supported conclusion;
- ruleset `1.1`, R6 v1.0, temporal CLI/UI workflows, fingerprints, generated contract, golden
  evidence, and ADR-022;
- explicit limitations: provisional synthetic thresholds, no inferred event, no missing-to-zero,
  no causal attribution, and no statistical drift/change-point claim.

Implemented v0.5 `DIA-02` and `DIA-04`, R7 operational outcome-disparity diagnosis and declarative
YAML rule authoring:

- closed bounded trusted-local static YAML grammar over already-computed EvidencePack metrics;
- flat finite numeric threshold/mapping-gap and exact boolean predicates with unit, metadata,
  group-count, and group-support admission;
- rejection of arbitrary code/imports/formulas/templates/dynamic keys/nested rules, unsafe YAML,
  extra fields, non-finite values, excessive documents/predicates, and core/duplicate IDs;
- deterministic three-valued `all`/`any` compilation into ordinary evidence-citing `RuleResult`
  artifacts with complete-definition fingerprints;
- built-in R7 v1.0 over one selected vehicle-tier or exact target-RSU completion dimension with
  provisional configurable gap/support thresholds, alternatives, insufficiency, and explicit
  non-protected/non-geographic/non-causal limits;
- ruleset `1.2`, CLI contract/validate/evaluate/fairness commands, interactive Fairness Evidence
  controls, generated contracts/definitions/schemas, source capabilities, and row-level provenance;
- adversarial unit, integration, UI, source-boundary, provenance, and golden evidence plus ADR-023;
  current SUMO/TOS R7 capability remains unavailable.

Implemented v0.5 `DIA-03`, deterministic R8 completed-task energy anomaly diagnosis:

- strict admission of only available, finite, non-negative `task.energy.per_completed_j` evidence
  with unit `J/task`, complete v1.0 energy-contract metadata, and exact contract fingerprint;
- cross-check of eligible/population counts, full coverage, and the available whole-number
  `task.completed.count` before any threshold conclusion;
- inclusive provisional mean-energy threshold plus minimum completed-task support, with thin high
  energy classified as conflicting and missing/partial/incompatible evidence as insufficient;
- ruleset `1.3`, R8 v1.0, dedicated CLI and Energy Evidence UI controls, source capabilities,
  row-level provenance, generated machine-readable contract, and deterministic golden result;
- explicit limitations: no statistical anomaly test, uncertainty estimate, hardware benchmark,
  causal attribution, external standard, optimisation recommendation, or SUMO/TOS support;
- unit, integration, CLI, UI, source-boundary, provenance, and golden evidence plus ADR-024.

Implemented v0.5 `DIA-05`, verified single-boundary nearest-flip analysis:

- typed v1.0 analysis/contract/candidate/constraint artifacts over the existing EvidencePack and
  RuleSetConfig boundaries;
- exact inclusive one-axis flips for eligible non-triggered R5, R7, and R8 severity thresholds;
- unchanged visible pair/group/task support constraints and explicit unsupported/not-applicable
  states for compound, disabled, thin, insufficient, conflicting, invalid, or triggered cases;
- mandatory ordinary rule-engine re-evaluation of every returned candidate over the same evidence;
- source/candidate config and result fingerprints, units, deltas, ties, provenance, deterministic
  artifact fingerprint, JSON/text CLI export, and generated machine-readable contract;
- generic/synthetic conditional capability with SUMO/TOS false; no interactive sweep, config
  persistence, cross-unit distance, calibration, optimisation, or recommendation claim;
- unit, integration, CLI, source-boundary, immutability, determinism, and golden evidence plus
  ADR-025.

Implemented v0.5 `DIA-06`, deterministic interactive threshold sensitivity:

- typed v1.0 request/axis/point/stability/boundary/report/contract artifacts over the existing
  EvidencePack, RuleSetConfig, and ordinary rule engine;
- bounded inclusive linear R5/R7/R8 grids with exact endpoints, source-threshold insertion, fixed
  support/dimension settings, and every ordinary status retained;
- status distributions, trigger fraction, monotonic-prefix check, sampled adjacent transition
  intervals, and embedded exact DIA-05 output when admissible;
- a thin Streamlit Threshold Sensitivity page with neutral chart/table, provisional-default labels,
  provenance/limitations, complete report download, and explicit complete-config session
  import/export without registry/source/default mutation;
- generic/synthetic conditional capability with SUMO/TOS false; no compound/R6/declarative sweep,
  calibration, optimisation, significance, causality, external-validity, or recommendation claim;
- unit, golden, UI-service, AppTest, source-capability, immutability, determinism, and generated
  contract/schema evidence plus ADR-026.

Implemented v0.5 `DIA-07`, deterministic cross-rule reasoning:

- typed v1.0 policy, relationship, report, and contract artifacts over completed retained
  RuleResults;
- explicit R1/R2 conflict with exact shared task-count lineage, R1/R4 contextual corroboration
  with exact shared mean-utilisation lineage, and R0 readiness suppression only through declared
  `blocked_rules` metadata;
- readiness precedence 100, equal ordinary-rule precedence 50, unchanged statuses/confidence, no
  winner selection, and no deletion or rewriting of suppressed targets;
- per-result/relationship/policy/evidence fingerprints, overlap keys, presentation effects,
  suppressed/unclassified/unresolved IDs, provenance, warnings, and limitations;
- embedded DiagnosticReport output, constrained renderer/research-report restatement, CLI contract
  and analysis commands, Diagnostics & Evidence UI display/download, and generated static contract;
- generic/synthetic conditional capability with SUMO/TOS false; no probability, relationship
  strength, causal attribution, automatic recommendation, or inferred undeclared pairs;
- unit, golden, CLI, AppTest, capability, immutability, determinism, and generated schema/contract
  evidence plus ADR-027.

Added an evidence-gated, read-only integration for Randy's separately supplied TOS Data result
package:

- evaluation-summary schema validation and idempotent registry import;
- source-provided task metric collections and partial EvidencePacks;
- safe NPZ key/shape validation, bounded replay, and per-arrival inspection;
- aggregate metric/rule provenance to the exact source CSV row and package fingerprint;
- descriptive campaign matrices, common-seed paired comparisons, training/audit views, and
  research-safe aggregate reports;
- machine-readable external-integration and publication-permission gates;
- checksummed private supervisor/viva packs;
- a synthetic-only static research dashboard deployed at
  <https://traffictwin-research-demo.netlify.app>;
- a standalone Streamlit container definition and reproducible dependency lock;
- Typer commands and a Streamlit `TOS Data Import` workflow.

The integration deliberately does not convert unresolved RSU fields to canonical infrastructure
metrics, launch the environment, or claim SUMO/live-data support.

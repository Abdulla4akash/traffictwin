# Reproducibility Guide

TrafficTwin is designed so that every reported number comes from deterministic code over explicit inputs.

## Environment Setup

```bash
uv sync --locked --extra dev --extra vec-runner
```

The package supports Python 3.11+. CI verifies Python 3.11 and 3.12 from the committed lock.

The complete dependency graph is committed in `uv.lock`:

```bash
uv lock --check
```

The latest exact test, coverage, generated-reference, link, build, installation, demo, fixture and
CI results are recorded once in the dated
[v0.7 housekeeping completion record](quality/v07_housekeeping_completion_20260803.md). Historical
phase counts remain in their dated records; they are not current acceptance criteria. These are
software-verification figures, not performance or external-validity claims. See
[testing strategy](testing_strategy.md) for the gate design.

## Deterministic Design Choices

OPS-04 research-object export fixes derived timestamps to the caller-declared publication date,
sorts stored ZIP members, fixes ZIP timestamps and modes, binds raw/request/software/method
fingerprints, re-reads raw evidence before publication, verifies the complete crate in memory, and
then publishes atomically. For the same source bytes, request, runtime, and method versions, the
ZIP bytes and archive SHA-256 are identical. Run `traffictwin archive verify ARCHIVE` to check a
crate offline; see [RO-Crate research objects](research_objects.md).

OPS-05 external-source discovery uses a closed sorted adapter registry and exact direct markers.
Portable inspection excludes wall-clock validation timestamps and absolute source paths while
binding adapter contract, source fingerprint, finding/output counts, provenance states, conversion,
and blockers. It delegates to existing source validators and never mutates the source or registry.
See the [general external-source contract](integration/external_source_contract.md).

- Scenario seeds are versioned YAML.
- Run bundles carry manifest, run, environment, file, unit, and provenance metadata.
- Validation runs before metrics.
- Metrics consume canonical records, not raw CSV/gzip/Parquet bytes.
- Custom metric registries are constructed explicitly, fingerprint every complete contract, embed
  that contract in results, and verify two canonical outputs for each evaluated input. Ambient
  plugin discovery is excluded so environment state cannot silently change the catalogue.
- Fixed-window metrics use versioned table anchors, decimal grid calculation, half-open membership,
  and the same ordinary calculator for every included slice.
- Temporal evidence fingerprints the source window series and complete projection, retains every
  ordinal/eligibility state, and maps only an explicitly declared event.
- Diagnostic rules consume EvidencePack objects, not raw data.
- Rules do not recompute metrics.
- Provenance traces consume existing validation, metric, EvidencePack, and DiagnosticReport objects;
  they do not recalculate results.
- PRO-03 uses report-builder-owned typed claim inventories, complete accepted-row ledgers, and
  timestamp-normalised evidence fingerprints; rendered wording cannot change its denominator.
- EXP-01 fixes axis/value order, complete Cartesian expansion, closed path/version bounds, and
  request/base/point/seed/bundle/result fingerprints. Result identity normalises generation time;
  selected random seeds remain explicit inputs.
- EXP-02 fixes source admission, operator/table identity, row order, SHA-256-plus-seed choices,
  bounded common timestamp deltas, exact row/file ledgers, and parent/plan/result fingerprints.
  The parent and every non-target source file remain unchanged; the derived bundle is ordinarily
  validated before transactional publication.
- REP-01 projects completed typed artifacts into one bounded canonical model. LaTeX and optional
  SVG/PDF output embed the same projection fingerprint; diagnostic identity uses the stable
  EvidencePack ID rather than the clock-derived report ID. SVG/PDF geometry and metadata are fixed.
- REP-02 sequences exact authored content in a separate append-only table. Annotation identity
  binds target, author, note, decision label, and UTC timestamp; ordered page fingerprints bind
  pagination state and history. Database triggers reject update/delete, and report attachment does
  not alter computed sections, claims, provenance, or scientific fingerprints.
- REP-03 fingerprints payload schema, report type, source mode, claim denominator, ordered section
  structure, report-independent claim keys, and exact typed snapshots. It excludes IDs, timestamps,
  display paths, rendered bodies, warnings, labels, commands, and annotations. Recursive changes
  use sorted canonical JSON keys and stable JSON Pointer paths.
- REP-04 binds the admitted source payload/scientific fingerprints, closed selection policy,
  complete availability and omitted counts, selected claim snapshots, all warnings/limitations,
  and relative provenance links. The projector uses no current clock. ReportLab invariant mode and
  an exact one-page `pypdf` check make accepted PDF bytes deterministic.
- REP-05 binds the sanitised query/terms, selected categories, candidate/match/omission/skip/
  redaction counts, fixed integer score/tie order, bounded snippets, and ordered hits. It rebuilds
  the projection from current read-only SQLite/report sources and uses no clock or persistent index.
- OPS-01 binds every SQLite schema version to one ordered migration name and embedded-SQL checksum.
  The immutable ledger, authoritative `user_version`, object/column inventory, and `quick_check`
  must reconcile before commit. A failed plan rolls back as a unit and existing scientific payload
  columns are not re-serialised.
- OPS-02 re-fingerprints raw files on every lookup and binds the entry to raw, adapter, validator,
  manifest-mapping, canonical Pydantic/Arrow schema, and cache-format identity. Every Parquet and
  validation payload is checksummed and strictly revalidated; a warm result equals its cold result,
  and a bad entry is never used or overwritten.
- OPS-03 emits a complete typed snapshot of runtime, dependency, integration, capability, and only
  the explicitly selected local targets. It delegates SQLite/cache evidence to immutable OPS-01/
  OPS-02 inspectors, executes no discovered command, performs no repair, and records
  `read_only=true` and `mutations_performed=false`. Report fingerprints bind the observed
  environment; the separately generated method contract remains byte-stable.
- Golden tests use fixed clocks or stable projections.
- JSON fingerprints normalise generated timestamps where implemented.

## Versions And Provenance

Current schema/config versions:

- Seed schema: `1.0`
- Run-bundle manifest schema: `1.0`
- File schema: `1.0`
- Metric version: `1.0`
- Percentile method: `linear-rank-n-minus-1-v1`
- Task-energy contract/family: `1.0`
- Operational-fairness policy/family: `1.0`
- Task-to-RSU target and vehicle spatial-grid contracts/family: `1.0`
- Trusted custom metric plugin API/contract: `1.0`
- EvidencePack schema: `1.0`
- DiagnosticReport schema: `1.0`
- ProvenanceTrace schema: `1.0`
- ProvenanceCompletenessReport/contract schema: `1.0`
- ResearchExportProjection/LaTeX export contract: `1.0`
- LaTeX/static-figure renderers: `latex-fragment-v1` / `static-figure-v1`
- WindowedMetricSeries/anchor policy: `1.0`
- TemporalEvidence/R6 method: `1.0`
- Declarative-rule schema/grammar: `1.0`
- R7 rule: `1.0`
- R8 rule: `1.0`
- NearestFlipAnalysis/contract: `1.0`
- ThresholdSensitivityReport/contract/grid method: `1.0` / `inclusive_linear_v1`
- CrossRuleReasoningReport/policy: `1.0` / `1.0`
- StatisticalStudy/paired method contract: `1.0` / `1.0`
- RuleSet schema/ruleset: `1.0` / `1.3`
- RegistrySearchResult/contract: `1.0` / `registry-search-v1`
- Registry schema/migration contract: `5` / `registry-migrations-v1`

Run provenance includes run ID, experiment ID, seed ID, algorithm, checkpoint, random seed, environment name, environment version or commit where supplied, and source bundle fingerprint.

## Fingerprints

Bundle fingerprints are built from exact relative source paths and raw-file SHA-256 values during
validation. Recompressing or converting an equivalent table therefore changes raw bundle identity;
canonical and metric equivalence is tested separately. EvidencePack, DiagnosticReport,
and ProvenanceTrace fingerprints are based on canonical JSON with volatile generated timestamps
normalised.

These fingerprints support reproducibility checks. They are not cryptographic signatures for adversarial security.

Operational-fairness outputs additionally carry the SHA-256 policy fingerprint and a separate
fingerprint of the exact sorted group IDs/dimension. A scalar cross-run delta is available only
when both match. This prevents a numerically convenient comparison from silently changing either
the admission rules or the group population.

Spatial/per-RSU outputs likewise preserve the relevant contract fingerprint and exact sorted
target/cell-set fingerprint. The grid fingerprint includes frame identity, units, origin, cell
geometry, and assignment method. Changing any of those produces a different reproducibility
contract rather than silently moving observations between cells.

Custom metric results embed the complete validated contract and its SHA-256 fingerprint. The
registry report fingerprints the sorted contract inventory. Repeated evaluation compares
canonical JSON including status, value, dimensions, missing evidence, warnings, and plugin output
metadata; scalar cross-run comparison requires equal contract fingerprints.

Temporal diagnosis records the `WindowedMetricSeries` fingerprint, typed temporal-evidence
fingerprint, exact metric/unit/version/direction, window configuration, optional event mapping,
and R6 configuration. Declarative rules record the canonical complete-definition fingerprint,
grammar/schema versions, predicate completeness, cited evidence keys, units, and metadata checks.
R6 records its configuration and exact baseline/episode/recovery ordinals. R7 additionally records
its explicit dimension, outcome-gap threshold, and minimum group support. R8 records its energy
boundary, completed-task support, observed energy, exact semantic-contract fingerprint, complete
coverage, and reconciled denominator counts. Nearest-flip artifacts record the EvidencePack,
source/candidate rule-result and source-bundle fingerprints, exact source/candidate configs,
observed boundary, unchanged discrete constraints, unit/delta, and verified status. Their artifact
fingerprint normalises only the analysis timestamp. Threshold-sensitivity reports additionally
record the complete requested/evaluated grid, exact point configs and normalised result
fingerprints, source-threshold insertion, status-sequence fingerprint, stability, sampled
intervals, and embedded DIA-05 fingerprint. Their fingerprint normalises the report and embedded
nearest-flip analysis timestamps only. Generated timestamps are
normalised in the temporal fingerprints; source values and eligibility states are not.

PRO-03 report fingerprints normalise only generation time. Per-claim fingerprints retain artifact
status, source fingerprint, trace completeness, complete ledger/dependencies, required evidence,
reasons, trace depth, and classification while excluding volatile trace IDs/timestamps. Changing
the selected report template or any claim evidence therefore changes the artifact identity.

Cross-rule reports record the exact policy inventory/fingerprint, ordered relationship evidence,
the source DiagnosticReport ID and RuleResult-sequence fingerprint, every normalised RuleResult
fingerprint, and explicit suppressed/unclassified/unresolved IDs. Their artifact fingerprint
normalises the cross-rule generation timestamp; the input result sequence is retained unchanged.

REP-01 projection fingerprints retain artifact family, stable source ID, title/caption, bounded
columns/rows/figure entries, source mode, and warnings. Both outputs embed the first 12 characters;
receipts publish full SHA-256 output checksums. Absolute paths are redacted before fingerprinted
rendering, while ordinary web URLs are preserved. A changed source value, method/status, warning,
or mode therefore changes the projection and both renderings.

REP-02 annotation IDs retain the exact path-free typed target, optional target fingerprint,
declared author label, note, human decision label, and UTC creation timestamp. Registry sequence is
separate ordering evidence. A history fingerprint retains ordered entries, target scope,
pagination boundary, limit, and continuation state. Author labels are not authenticated identities.

REP-03 scientific report fingerprints bind only the compatible typed comparison surface. Section
fingerprints bind ordered scientific claim keys and their canonical payloads; the complete result
fingerprint binds both report fingerprints, compatibility codes, classifications, paths, exact
values, exclusions, and warnings. Rewording prose or adding an annotation cannot change those
scientific fingerprints.

REP-04 projection fingerprints bind the full bounded summary, including source warning order and
every limitation. Claim link fingerprints bind exact scientific snapshot payloads. Repeated
projection and PDF rendering from the same saved typed report are byte-identical; overflow is a
deterministic refusal and cannot silently change the caveat set.

STA-01 statistical studies record the complete `PairedStudyConfig` and fingerprint, exact
expected/admitted random seeds, every endpoint and timestamp-normalised collection fingerprint,
every exclusion, compatibility-signature and source-sequence fingerprints, schema/method contract,
interval/test repetitions, and local resampling seeds. Whole paired differences are resampled; the
process never reads ambient random state. Exact sign enumeration is used through 16 pairs and the
artifact fingerprint normalises only `generated_at`.

STA-02 N-way studies record the complete `NWayRankingConfig`, filtered embedded winner map, exact
complete multi-policy rows, every endpoint/source/collection fingerprint, family missingness and
exclusions, compatibility signatures, bootstrap settings, and family-specific derived seeds.
Complete random-seed rows are resampled jointly with a local generator. The artifact fingerprint
normalises the study and embedded winner-map generation timestamps only; input order does not
change the result.

STA-03 equivalence studies record the complete `EquivalenceStudyConfig`, original-unit margin,
basis/justification/reference, alpha, exact inherited STA-01 observations/audit/input fingerprints,
source paired-study and method-contract fingerprints, both hypotheses/statistics/p-values, and the
reconciled Student-t interval. Student-t CDF and quantile evaluation is deterministic and pinned by
method version/reference tests. The artifact fingerprint normalises only `generated_at`; input
order and source computation timestamps do not change the result.

STA-04 golden contracts fingerprint their approval metadata, typed subject context, exact or
compatible-context source policy, expected values, units/versions, and explicit absolute/relative
tolerances. Metric and paired-study subjects use timestamp-normalised artifact fingerprints; exact
source policy separately pins the input fingerprint or complete study input map. Gate reports
record every check/blocker and normalise only `generated_at`. Candidate goldens cannot pass, inputs
are verified unchanged, and the evaluator never updates a golden or registry row.

STA-05 power plans record the complete strict `PowerAnalysisConfig` and fingerprint, signed target
effect, paired-difference variance, alpha, target power, bases/justifications/references, pilot
size, synthetic state, search bounds, normal critical value, smallest qualifying pair count,
achieved and preceding approximate power, and labels. The standard-library normal calculation and
integer binary search have no ambient random state. The artifact records the method-contract
fingerprint and normalises only `generated_at`; evaluation verifies the input config remains
unchanged. Synthetic, small-sample, and provisional qualifiers are part of the typed result.

PRO-01 reports fingerprint the complete baseline/variation accepted-row ledgers, comparison-side
summaries, immutable input fingerprints, synthetic labels, ordinary values/delta, formula mode,
signed row terms where admitted, compatibility audit, and mandatory non-causality language. Row
order is deterministic by side and the existing single-run ledger order. Arithmetic reports are
emitted only when `math.fsum` of signed terms reconciles to the ordinary comparison delta at the
published tolerance; lineage-only metrics retain null weights. No clock or random state enters the
artifact.

PRO-02 derives graph identity from the complete sanitised node/edge content, root, schema, and
disclosure profile. It excludes volatile trace IDs and trace/node timestamps, so evidence-
equivalent traces retain one graph ID. Each bounded `ProvenanceGraphView` has its own canonical
fingerprint and exact limits/omissions. DOT and GraphML ordering is fixed; renderer layout is not
part of the reproducibility claim. Recursive local-path redaction prevents machine paths from
changing or leaking through output text.

## Directory/ZIP Equivalence

The loader supports directory and ZIP bundles. Tests check equivalent validation/canonicalisation for ZIP and directory fixtures. ZIP loading rejects path traversal, absolute paths, and symlink entries.

## Tabular-Format Equivalence

Golden tests convert every declared baseline CSV table to deterministic gzip-CSV and Parquet,
verify identical canonical semantic projections and deterministic metric projections, and retain
representation-specific raw paths/checksums/fingerprints. This proves computational equivalence
without relabelling distinct immutable evidence as one bundle.

## Batch Equivalence And Ordering

Batch bundle ingestion expands only explicit references, resolves and deduplicates paths, and
sorts candidates lexicographically before ordinary validation/import. Overlapping globs therefore
cannot cause a second import attempt within one request. Every accepted import uses the existing
single-bundle transaction and fingerprint rules.

The checked benchmark compares every batch validation projection with an independent sequential
`validate_bundle` call and records fixture bytes, runtime, and peak traced memory:

```bash
uv run python scripts/benchmark_batch_ingestion.py 'tests/fixtures/bundles/*' --repeat 5
```

See [batch ingestion benchmark](evaluation/batch_ingestion_benchmark.md). The result is local
implementation evidence, not a large-dataset or simulator throughput claim.

## Synthetic Fixture Provenance

Repository fixtures under `tests/fixtures/` are synthetic and hand-auditable. They are suitable for:

- testing validation behavior;
- testing metric formulas;
- testing comparison output;
- testing diagnostic rule implementation;
- testing provenance trace construction and source-row preview.

They are not real Manchester, Randy/VEC, or SUMO results.

`tests/fixtures/manifest_inference` contains two additional synthetic software fixtures. The
value-pattern fixture proves stable exact/alias/distinctive-vocabulary suggestions and confirmed
bundle validation. The ambiguity fixture deliberately supports several file kinds equally and
must retain no selected kind. Reproduce both drafts with:

```bash
uv run traffictwin manifest infer tests/fixtures/manifest_inference/value_patterns --format json
uv run traffictwin manifest infer tests/fixtures/manifest_inference/ambiguous --format json
```

Draft fingerprints include the versioned candidate output and complete source fingerprint.
Confirmation re-runs inference, so changed CSV bytes cannot reuse an older draft.

The separate `tests/fixtures/sumo/square_public` package is also synthetic simulation evidence, but
it is not hand-authored. It preserves complete SUMO 1.27.1 outputs generated from the official
Eclipse SUMO square scenario. Its adjacent README and `sumo-source.yaml` record the exact command,
tag/commit, licence, retrieval metadata, immutable hashes, and random seed. Reproduce adapter
validation and metrics with:

```bash
uv run traffictwin integration sumo validate tests/fixtures/sumo/square_public
uv run traffictwin integration sumo metrics tests/fixtures/sumo/square_public
```

## Reproduce A Measurement-Robustness Fixture

```bash
traffictwin synthetic measurement-contract \
  --output build/measurement-impairment-contract.json
traffictwin synthetic generate-config \
  --config examples/synthetic_measurement_imperfections.yaml \
  --output build/measurement-robustness
traffictwin bundle validate build/measurement-robustness
```

Record the scenario seed, measurement seed, complete configuration fingerprint, audit fingerprint,
bundle fingerprint, package version, and source commit. Identical inputs reproduce identical rows
and audit; changing an unrelated noise axis does not change an already-enabled field. This verifies
deterministic software behavior, not a calibrated real sensor or dropout distribution.

## Quality Gates

```bash
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run python -m pytest --cov=traffictwin --cov-report=term-missing
uv run python scripts/generate_reference_docs.py
git diff --exit-code -- docs/reference/generated
uv run python scripts/check_markdown_links.py
uv run traffictwin demo initialise .demo --force
uv run traffictwin synthetic verify .demo
uv run traffictwin report full .demo/bundles/stressed_demand \
  --comparison-baseline .demo/bundles/baseline \
  --output .demo/reports/stressed_full.html
uv run traffictwin release stage-demo-site .demo --output public
git diff --exit-code -- tests/fixtures examples
```

The exact current snapshot is recorded in [testing strategy](testing_strategy.md) after the complete
quality-gate run. Historical counts are not acceptance criteria for later increments.

Pytest configuration explicitly adds the repository root to its import path, so `uv run python -m
pytest` resolves the repository's test helpers consistently.

## Reproduce The Baseline-Versus-Variation Demo

Standalone workspace:

```bash
traffictwin demo initialise .demo
traffictwin compare .demo/bundles/baseline .demo/bundles/stressed_demand
traffictwin diagnose bundle .demo/bundles/under_offloading
traffictwin diagnose evidence .demo/exports/trivial_multi_algorithm_evidence.json
```

Repository fixture path:

```bash
traffictwin bundle validate tests/fixtures/bundles/baseline_valid
traffictwin bundle validate tests/fixtures/bundles/variation_valid
traffictwin bundle batch-validate 'tests/fixtures/bundles/*' --format json
traffictwin bundle stream-validate tests/fixtures/bundles/baseline_valid \
  --chunk-rows 2 --max-chunk-bytes 1024 --format json
traffictwin metrics compute tests/fixtures/bundles/baseline_valid
traffictwin metrics compute tests/fixtures/bundles/variation_valid
traffictwin compare tests/fixtures/bundles/baseline_valid tests/fixtures/bundles/variation_valid
```

For UI:

```bash
streamlit run src/traffictwin/ui/app.py
```

Then follow [demo_checklist.md](demo_checklist.md).

For the generated large-fixture parser benchmark:

```bash
uv run python scripts/benchmark_streaming_ingestion.py \
  --rows 75000 --chunk-rows 257,1024,4096
```

The script checks canonical digests, validation, evidence, and counts against ordinary ingestion
for every chunk size and reports runtime plus Python `tracemalloc` peak. See the
[recorded streaming benchmark](evaluation/streaming_ingestion_benchmark.md); it is not full RSS or
a city-scale performance claim.

The public static demonstration is reproduced from the same workspace:

```bash
traffictwin release stage-demo-site .demo --output public
```

`public/site-manifest.json` records synthetic/live/external-integration flags and page hashes.

## Regenerate Evidence And Diagnostics

```bash
traffictwin evidence build tests/fixtures/bundles/baseline_valid --output evidence-baseline.json
traffictwin diagnose evidence evidence-baseline.json
traffictwin diagnose report tests/fixtures/bundles/baseline_valid --format json
```

## Regenerate Provenance Traces

```bash
traffictwin provenance metric tests/fixtures/bundles/baseline_valid task.completion.rate
traffictwin provenance rule tests/fixtures/bundles/variation_valid R2 --format json
traffictwin provenance source tests/fixtures/bundles/baseline_valid tasks.csv 2
traffictwin provenance difference-contributors tests/fixtures/bundles/baseline_valid \
  tests/fixtures/bundles/variation_valid task.latency.mean_ms \
  --format json --output difference-provenance.json
traffictwin provenance export tests/fixtures/bundles/baseline_valid \
  --root-type metric \
  --root-id task.completion.rate \
  --format markdown \
  --output provenance-task-completion.md
traffictwin provenance export tests/fixtures/bundles/baseline_valid \
  --root-type metric \
  --root-id task.completion.rate \
  --format graphml \
  --redaction structure_only \
  --max-nodes 120 --max-edges 240 \
  --output provenance-task-completion.graphml
```

## Confirm Fixture Immutability

Before and after a run:

```bash
git status --short tests/fixtures examples/seeds
```

No fixture files should be modified by validation, metrics, evidence, diagnostics, provenance, CLI,
or UI workflows.

## Known Sources Of Non-Determinism

- Real current time appears in non-golden CLI/UI report generation unless a fixed clock is injected.
- Window values are deterministic for a fixed bundle, metric/window configurations, and clock.
  CSV, gzip-CSV, Parquet, and collected-streaming tests compare stable window projections; their
  raw fingerprints remain representation-specific by design.
- SQLite timestamps are generated at write time.
- Streamlit reruns are UI state events, not research computations.
- Future external simulators may introduce runtime and stochastic variability; they must record seeds and environment versions.

## External Integration Limitations

Phase 6A inspected Randy's separately supplied TOS Data result package and established reproducible
contracts for evaluation summaries, JSON reconciliation, NPZ key/shape validation, bounded
historical replay, and per-arrival samples. The package remains external to this repository.

Install the optional reader and validate a local checkout with:

```bash
python -m pip install -e ".[dev,tos]"
traffictwin integration tos validate ../external/tos-data --format json > tos-validation.json
traffictwin integration tos import ../external/tos-data \
  --registry data/registry/traffictwin-tos.sqlite
```

Reproducibility is tied to the source package Git commit, deterministic package fingerprint,
source row, engine version, actor reference, fleet seed, TrafficTwin source-metric version, and a
separate `vec_env` semantics commit. Source inspection now confirms trace units, task/action
semantics, RSU active-task/backlog meanings, and the evaluator CLI. Exact producer commits,
checkpoints, the instrumented writer, local runtime verification, persistent identity, physical
completion, and source-package raw SUMO/trip outputs remain unavailable. Full Randy/VEC canonical
conversion and direct execution therefore cannot yet be reproduced. The independent public SUMO
1.27 tripinfo/summary adapter is reproducible through its committed fixture, but does not resolve
those source-package gaps.

Related documents:

- [Testing strategy](testing_strategy.md)
- [Run bundle specification](run_bundle_spec.md)
- [EvidencePack specification](evidence_pack_spec.md)
- [Provenance model](provenance_model.md)
- [Integration decision](integration/phase6_decision.md)

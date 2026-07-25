# CLI Reference

The CLI is implemented with Typer in [src/traffictwin/cli.py](../src/traffictwin/cli.py). This reference covers existing commands only.

Generated help output is available at [reference/generated/cli_help.json](reference/generated/cli_help.json).

## General Behavior

```bash
traffictwin --help
```

Most commands print human-readable summaries. Commands with `--format json` print machine-readable JSON. Validation or processing failures return non-zero exit codes.

## Seed Commands

### `traffictwin validate-seed PATH`

Purpose: validate a scenario seed YAML file.

Arguments:

- `PATH`: readable YAML file.

Output:

- `valid seed: <seed_id>` on success.
- validation error text on stderr and exit code `1` on failure.

Example:

```bash
traffictwin validate-seed examples/seeds/arena_gridlock.yaml
```

### `traffictwin normalise-seed SOURCE DESTINATION`

Purpose: validate a seed and write deterministic YAML.

Arguments:

- `SOURCE`: readable seed YAML.
- `DESTINATION`: output YAML path.

Example:

```bash
mkdir -p build
traffictwin normalise-seed examples/seeds/arena_gridlock.yaml build/arena_gridlock.normalised.yaml
```

Common errors:

- unsupported schema version;
- invalid class mix;
- unknown fields.

## Capability Command

### `traffictwin capabilities`

Purpose: print the default export/import-only capability manifest.

Example:

```bash
traffictwin capabilities
```

Expected status:

- `direct_launch: false`
- `asynchronous_launch: false`
- `streaming_canonicalisation: true`
- `time_windowed_metrics: true`
- `latency_percentile_family: true`
- `energy_metric_family: true` for the generic adapter, conditional on an explicit compatible
  `manifest.energy_contract`
- `fairness_metric_family: true` for the generic adapter, conditional on exact operational groups,
  complete coverage, and the fixed minimum-support policy
- `spatial_rsu_metric_family: true` for the generic adapter, conditional on explicit task-target
  and/or vehicle coordinate-frame contracts plus their complete-coverage rules
- `custom_metric_plugin_api: true` for explicit reviewed in-process registration; this does not
  enable uploaded code, arbitrary module loading, or sandboxed execution

- `temporal_degradation_diagnosis: true` for compatible generic canonical bundles; SUMO and TOS
  source-specific contracts remain `false`
- `declarative_rule_authoring: true` for the closed trusted-local static YAML grammar; this does
  not enable arbitrary code, uploaded rules, or a sandbox
- `fairness_disparity_diagnosis: true` for compatible generic operational group evidence; SUMO
  and TOS source-specific contracts remain `false`
- `energy_anomaly_diagnosis: true` for exact compatible generic completed-task energy evidence;
  SUMO and TOS source-specific contracts remain `false`
- `nearest_flip_analysis: true` for eligible generic R5/R7/R8 EvidencePacks; SUMO and TOS
  source-specific contracts remain `false`
- `threshold_sensitivity_sweep: true` for the bounded generic R5/R7/R8 library/UI grid; SUMO and
  TOS source-specific contracts remain `false`
- `cross_rule_reasoning: true` for bounded generic/synthetic R0/R1/R2/R4 RuleResult
  relationships; SUMO and TOS source-specific contracts remain `false`
- `paired_statistical_study: true` for compatible registered generic/synthetic common-seed
  experiments; SUMO and TOS source-specific contracts remain `false`
- `n_way_policy_ranking: true` for compatible registered generic/synthetic repeated-policy
  experiments; SUMO and TOS source-specific contracts remain `false`
- `parameter_sweep_composer: true` for bounded generic seed and local synthetic composition; this
  does not enable external simulator launch
- `measurement_noise_dropout_models: true` only for the bounded generated-observation EXP-03
  synthetic fixture; SUMO and TOS source-specific contracts remain `false`
- `full_text_registry_search: true` for the local read-only generic registry/report projection;
  SUMO and TOS source-specific contracts remain `false`
- `registry_schema_migrations: true` for the local generic SQLite registry; SUMO and TOS
  source-specific contracts remain `false`
- `environment_doctor: true` for the generic runtime; source-specific SUMO/TOS manifests remain
  `false` because the doctor is a global operational service rather than an adapter capability
- `ro_crate_archival_export: true` for accepted ordinary generic bundles; source-specific SUMO/TOS
  manifests remain `false` for the complete OPS-04 v1 artifact pipeline
- `generalised_external_source_contract: true` for generic capability discovery and both reviewed
  SUMO/TOS reference contracts; this does not make their data or metrics equivalent
- unconfirmed Randy/SUMO controls: `unknown`

## Doctor Command

### `traffictwin doctor [--workspace PATH] [--registry FILE] [--bundle PATH --cache-root DIRECTORY] [--format text|json] [--contract]`

Purpose: inspect Python/core and optional dependencies, optional command locations, built-in
integration/capability truth, and selected workspace/registry/cache targets without changing them.

Examples:

```bash
traffictwin doctor
traffictwin doctor --workspace .traffictwin-demo
traffictwin doctor --registry data/registry/traffictwin.sqlite --format json
traffictwin doctor --bundle data/runs/run-001 --cache-root .traffictwin-cache
traffictwin doctor --contract --format json
```

`--bundle` and `--cache-root` must be supplied together. The workspace parser is bounded and
contained, registry inspection is immutable/read-only, and cache inspection never publishes or
repairs an entry. The command executes no discovered external command. It exits `0` for `healthy`
or `degraded` and `1` for `blocked`. See [TrafficTwin doctor](doctor.md).

## Archive Commands

### `traffictwin archive contract [--format text|json]`

Print the versioned OPS-04 method, permission, limit, redaction, and deterministic-publication
contract.

### `traffictwin archive create BUNDLE DESTINATION --publication-date YYYY-MM-DD [OPTIONS]`

Create a verified attached RO-Crate ZIP. `DESTINATION` must end in `.zip`; existing files are
refused unless `--overwrite` is explicit.

Important options:

- `--raw-evidence embed|reference|exclude` (default `reference`);
- `--publication-scope private|public` (default `private`);
- `--permission-status unknown|confirmed|denied|not_required`;
- `--permission-basis TEXT` and `--raw-evidence-licence TEXT`;
- `--licence-statement TEXT`, `--persistent-identifier TEXT`, `--title`, and `--description`;
- `--format text|json`.

```bash
traffictwin archive create path/to/bundle build/run-ro-crate.zip \
  --publication-date 2026-07-21 \
  --raw-evidence reference
```

Imported raw embed and public imported reference require confirmed permission, a basis, and a raw
licence. Public unknown/denied external evidence must use `exclude`.

### `traffictwin archive verify ARCHIVE [--format text|json]`

Verify bounds, safe deterministic ZIP structure, CFF, TrafficTwin inventory, checksums, RO-Crate
file entities, and public permission policy without extraction or mutation. Invalid archives exit
`1`. See [RO-Crate research objects](research_objects.md).

## Registry Commands

### `traffictwin registry init PATH`

Purpose: create a current SQLite metadata registry through the ordered migration runner, or
upgrade a supported existing registry.

Example:

```bash
traffictwin registry init data/registry/traffictwin.sqlite
```

### `traffictwin registry inspect PATH`

Purpose: migrate a supported registry to the current schema, then print its schema version and
record counts.

Example:

```bash
traffictwin registry inspect data/registry/traffictwin.sqlite
```

### `traffictwin registry migration-contract [--format text|json]`

Purpose: publish the five ordered versions, immutable checksums, transaction/ledger/legacy/
integrity policies, exclusions, limitations, and exact OPS-01 contract fingerprint.

### `traffictwin registry migration-status PATH [--format text|json]`

Purpose: inspect an existing registry through immutable read-only SQLite. Reports empty,
legacy-unversioned, upgrade-available, or current state; authoritative/applied/pending versions;
ledger validity; `quick_check`; and schema/status fingerprints. It never migrates.

### `traffictwin registry migrate PATH [--target-version 1..5] [--format text|json]`

Purpose: apply the complete pending ordered plan in one `BEGIN IMMEDIATE` transaction. Any failure
rolls back all changes from that invocation. Existing payload columns are preserved and a completed
target is a no-op. Back up valuable registries first. See
[registry schema migrations](registry_migrations.md).

Common errors:

- path does not exist for `inspect`;
- path not writable for `init`.
- unknown or malformed legacy schema objects;
- future version, downgrade request, or migration-ledger mismatch;
- SQLite lock, permission, corruption, or integrity-check failure.

### `traffictwin registry search-contract [--format text|json]`

Purpose: publish REP-05 categories, lexical matching/ranking/tie rules, bounds, read-only guarantee,
redaction policy, exclusions, limitations, and stable contract fingerprint.

### `traffictwin registry search QUERY --registry REGISTRY [--workspace WORKSPACE] [--category CATEGORY]... [--limit N] [--format text|json]`

Purpose: search findings, append-only annotations, bounded report metadata/text, runs,
experiments, and evidence references. Repeated `--category` options restrict the six labelled
categories. Every normalised term must match. Results are deterministically ranked, path-redacted,
bounded to 1–200, and fingerprinted. The command opens SQLite read-only and never persists an
index. See [full-text registry search](registry_search.md).

## Bundle Commands

### `traffictwin bundle validate PATH`

Purpose: validate a directory or ZIP run bundle.

Example:

```bash
traffictwin bundle validate tests/fixtures/bundles/baseline_valid
```

Output includes bundle ID, run ID, import status, `may_import`, and finding count. Rejected bundles return exit code `1`.

### `traffictwin bundle inspect PATH`

Purpose: inspect a bundle without mutating a registry.

Example:

```bash
traffictwin bundle inspect tests/fixtures/bundles/partial_valid
```

Output includes declared file count and available/unavailable evidence categories.

### `traffictwin bundle import PATH --registry REGISTRY`

Purpose: validate and register an accepted or warning-level bundle.

Example:

```bash
traffictwin bundle import tests/fixtures/bundles/baseline_valid --registry data/registry/traffictwin.sqlite
```

Exit behavior:

- accepted/imported: `0`;
- idempotent re-import of same bundle: `0`;
- rejected bundle or conflicting run ID: `1`.

### `traffictwin bundle cache-contract [--format text|json]`

Purpose: publish the OPS-02 key components, adapter/validator/schema identities, Parquet format,
safety limits, raw-separation rule, invalidation policy, and contract fingerprint.

### `traffictwin bundle cache-status PATH --cache-root DIRECTORY [--format text|json]`

Purpose: reopen and fingerprint raw evidence and inspect the exact expected cache entry without
writing. A normal absent entry is `miss` with exit code `0`. Stale, incompatible, corrupt, or
unavailable state returns `1`. The cache directory must be outside a raw directory bundle.

### `traffictwin bundle cache-validate PATH --cache-root DIRECTORY [--format text|json]`

Purpose: return an exact verified warm result, or perform ordinary cold validation and atomically
publish six typed Parquet canonical tables for an accepted generic bundle.

```bash
traffictwin bundle cache-validate data/runs/run-001 \
  --cache-root .traffictwin-cache \
  --format json
```

A successful cold run reports `written`; a successful warm run reports `hit`. Rejected validation,
failed publication, or a stale/incompatible/corrupt entry returns `1`. Bad entries are bypassed but
never automatically deleted or overwritten. See
[canonical-table caching](canonical_table_caching.md).

### `traffictwin bundle batch-validate INPUTS... [--format text|json|csv] [--output FILE]`

Purpose: deterministically expand, deduplicate, order, and validate an explicit path/glob set.

```bash
traffictwin bundle batch-validate 'data/runs/run-*' --format json --output build/validation.json
```

Quote globs so TrafficTwin performs expansion. An unmatched glob is reported as an input issue;
matched neighbours still run. A complete batch returns `0`; a partial or failed batch returns `1`.

### `traffictwin bundle batch-import INPUTS... --registry REGISTRY [--format text|json|csv] [--output FILE]`

Purpose: validate every resolved candidate and independently register accepted bundles.

```bash
traffictwin bundle batch-import 'data/runs/*.zip' data/runs/manual \
  --registry data/registry/traffictwin.sqlite --format json
```

Each candidate retains ordinary created, idempotent, rejected, and conflict behavior. A partial
batch returns `1` even when valid neighbours were committed; inspect the consolidated/per-bundle
counts. JSON includes input issues, while CSV is one row per resolved candidate. Limits are 64
input references and 256 unique candidates. See the
[batch import guide](integration/batch_bundle_import.md).

### `traffictwin bundle stream-validate PATH [--chunk-rows N] [--max-chunk-bytes N] [--max-table-bytes N] [--max-bundle-bytes N] [--format text|json] [--output FILE]`

Purpose: validate and canonicalise one large generic directory/ZIP bundle through bounded chunks
without retaining all canonical rows.

```bash
traffictwin bundle stream-validate data/runs/large-run \
  --chunk-rows 1000 --max-chunk-bytes 4000000 --format json
```

The result includes source/canonical counts and maximum observed chunk bounds. A rejected bundle
returns `1`. The ordinary 10,000,000-byte table limit is unchanged.

### `traffictwin bundle stream-import PATH --registry REGISTRY [streaming options]`

Purpose: stream-validate one bundle and register accepted metadata through the ordinary
idempotency/conflict transaction.

```bash
traffictwin bundle stream-import data/runs/large-run \
  --registry data/registry/traffictwin.sqlite --chunk-rows 1000
```

This does not automatically materialise canonical rows or compute/store metrics, EvidencePacks, or
diagnostics. See the [streaming guide](integration/streaming_canonicalisation.md).

### `traffictwin bundle report PATH --format json`

Purpose: print the full validation report JSON.

Example:

```bash
traffictwin bundle report tests/fixtures/bundles/partial_valid --format json
```

Only JSON output is supported.

## Metrics Commands

### `traffictwin metrics plugin-api [--format json|text]`

Purpose: describe the versioned trusted-local custom metric boundary, supported canonical tables,
two-run repeatability check, failure-isolation behavior, and explicit absence of uploaded/dynamic
code loading or sandbox claims.

```bash
traffictwin metrics plugin-api --format json
```

This command reports the API contract; it deliberately does not accept a Python file or module
path. Custom functions are registered explicitly by reviewed application/library code. See
[Custom metric plugins](custom_metric_plugins.md).

### `traffictwin metrics compute PATH`

Purpose: compute deterministic metrics for a validated bundle and print a concise summary.

Example:

```bash
traffictwin metrics compute tests/fixtures/bundles/baseline_valid
```

Rejected bundles return exit code `1`.

### `traffictwin metrics report PATH --format json [--registry REGISTRY]`

Purpose: print complete `MetricCollection` JSON. If `--registry` is provided, store the collection in SQLite.

Example:

```bash
traffictwin metrics report tests/fixtures/bundles/variation_valid --format json
```

Only JSON output is supported.

### `traffictwin metrics windows PATH --width-s SECONDS [OPTIONS]`

Purpose: compute every declared window-applicable metric over aligned half-open fixed windows.

```bash
traffictwin metrics windows tests/fixtures/bundles/baseline_valid \
  --width-s 60 --format json --output build/windows.json
```

Options include `--origin-s`, paired `--start-s`/`--end-s`,
`--partial-windows include|exclude`, `--max-windows`, and `--format text|json`. Without an explicit
range, TrafficTwin uses the smallest complete aligned envelope containing canonical timestamps.
Empty windows stay visible with unavailable metrics. Coverage is requested-range overlap, not
sensor completeness. Rejected evidence, invalid configuration, or an over-bound request returns
exit code `1`. See [Time-windowed metrics](time_windowed_metrics.md).

## Comparison Command

### `traffictwin compare BASELINE VARIATION [--registry REGISTRY] [--format text|json]`

Purpose: compare two bundles or two registered metric collections.

Examples:

```bash
traffictwin compare tests/fixtures/bundles/baseline_valid tests/fixtures/bundles/variation_valid
traffictwin compare run-baseline-001 run-variation-001 --registry data/registry/traffictwin.sqlite --format json
```

If the arguments are paths, metrics are computed from bundles. If paths do not exist, `--registry` is required and arguments are treated as run IDs for stored metric collections.

## Evidence Commands

### `traffictwin evidence build PATH [--output FILE] [--registry REGISTRY]`

Purpose: build a versioned EvidencePack JSON document.

Examples:

```bash
traffictwin evidence build tests/fixtures/bundles/baseline_valid
traffictwin evidence build tests/fixtures/bundles/baseline_valid --output evidence-baseline.json
```

Rejected bundles return exit code `1`.

## Experiment Commands

### `traffictwin experiment summarise --registry REGISTRY --experiment-id ID [--format text|json]`

Purpose: aggregate stored metric collections for an experiment.

Example:

```bash
traffictwin experiment summarise --registry data/registry/traffictwin.sqlite --experiment-id exp-gridlock-001
```

The command summarises metric collections already stored in the registry. It does not import bundles automatically.

### `traffictwin experiment protocol --registry REGISTRY --experiment-id ID [--format yaml|csv] [--output FILE]`

Purpose: export a registered experiment and its referenced seed snapshots as an exhaustive,
deterministic coordination protocol.

Examples:

```bash
traffictwin experiment protocol --registry .demo/registry.sqlite \
  --experiment-id exp-planned-study --format yaml --output protocol.yaml
traffictwin experiment protocol --registry .demo/registry.sqlite \
  --experiment-id exp-planned-study --format csv --output run-sheet.csv
```

When `--output` is omitted, the document is printed to standard output. Only `yaml` and `csv` are
accepted. Missing experiments, missing referenced seeds, invalid plans, and unsupported formats
return exit code `1`. The command creates no `Run` records and launches nothing.

### `traffictwin experiment match-bundle PATH --registry REGISTRY --experiment-id ID [--format text|json]`

Purpose: validate a completed directory/ZIP bundle, then compare its manifest metadata with the
registered experiment protocol.

```bash
traffictwin experiment match-bundle .demo/bundles/baseline \
  --registry .demo/registry.sqlite --experiment-id exp-planned-study --format json
```

The result is `exact`, `compatible`, `mismatch`, or `unmatched`. `exact` and `compatible` return
exit code `0`; rejected bundles, conflicts, and no match return `1`. The command does not import the
bundle or mutate the registry.

### `traffictwin experiment parameter-sweep-contract [--output FILE]`

Purpose: publish the EXP-01 modes, closed parameter paths, grid/metric bounds, response policy,
provenance contract, and explicit no-launch limitations as JSON.

### `traffictwin experiment parameter-sweep --request FILE --output DIRECTORY [--overwrite]`

Purpose: validate a complete strict request and materialise seed snapshots, labelled local
synthetic bundles plus ordinary core-metric responses, or explicitly unexecuted external request
artifacts.

```bash
traffictwin experiment parameter-sweep \
  --request examples/parameter_sweep_request.yaml \
  --output build/demand-capacity-sweep
```

The destination must not exist unless `--overwrite` is explicit. Empty, symbolic-link,
current/home/root, and current/home ancestor destinations are rejected before expansion. Local mode writes
`sweep_result.json`, `response_surface.csv`, request/seed snapshots, and one validated synthetic
bundle per point. External mode writes no bundle and every request retains
`execution_status=not_executed`, false direct-launch support, and null command/launcher. Invalid or
oversized grids return exit code `1` before replacing the destination.

### `traffictwin experiment mutation-contract [--output FILE]`

Purpose: publish the EXP-02 source-admission rules, three closed operators, table/size/change
bounds, deterministic provenance contract, output layout, and explicit no-launch/no-rerouting
limitations as JSON.

### `traffictwin experiment mutate-scenario --bundle PATH --request FILE --output DIRECTORY [--overwrite]`

Purpose: apply exactly one validated deterministic mutation to a copied, ordinarily valid bundle
that is explicitly labelled synthetic/evaluation.

```bash
traffictwin experiment mutate-scenario \
  --bundle .demo/bundles/baseline \
  --request examples/scenario_mutation_request.yaml \
  --output build/mutated-baseline
```

The request chooses `row_dropout`, `timestamp_jitter`, or `rsu_removal`. The first two require a
declared uncompressed CSV table and derive per-row behavior from SHA-256 plus the declared seed.
RSU removal targets one exact ID, removes matching infrastructure rows, and never rewrites task
targets or invents routing. The output contains `bundle/`, `request.yaml`, and
`mutation_manifest.json`; the manifest retains the full bounded row/file ledger and fingerprints.
Imported/raw bundles, inferred/canonicalised manifests, unsupported encodings, symlinks, protected
destinations, or validation failures return exit code `1` without publishing a partial result.
Replacement requires `--overwrite`. No external simulator is launched.

### `traffictwin experiment study-contract [--format text|json]`

Purpose: publish the complete versioned STA-01 method, compatibility, assumption, unavailable, and
limitation contract without reading a registry.

### `traffictwin experiment statistical-study --registry REGISTRY --experiment-id ID --baseline-seed ID --variation-seed ID --algorithm NAME`

Purpose: evaluate one registered common-seed baseline-versus-variation study over stored completed
metric collections. Optional controls include `--checkpoint`, `--metric`, `--objective`,
`--confidence-level`, both repetition counts, `--resampling-seed`, `--format json|markdown|csv`,
and `--output`.

The selection must exactly match the registered experiment and common-seed plan. JSON and Markdown
contain the full result; CSV is the pair/exclusion audit. Available studies exit `0`. Insufficient
or incompatible studies still emit the typed artifact and exit `1`. The command recomputes no
metric, mutates no registry row, launches nothing, and proves neither causality nor equivalence.
See [common-seed paired statistical studies](statistical_studies.md).

### `traffictwin experiment n-way-contract [--format text|json]`

Purpose: publish the complete STA-02 comparison scope, winner-map extension, compatibility,
missingness, joint-bootstrap, unavailable, assumption, and limitation contract without reading a
registry.

### `traffictwin experiment n-way-ranking --registry REGISTRY --experiment-id ID`

Purpose: rank compatible registered policies independently inside every planned scenario family
over identical complete common random seeds. By default all registered policies are selected;
repeat `--algorithm NAME` to use a declared subset. Controls include `--checkpoint`, `--metric`,
`--objective`, `--confidence-level`, `--bootstrap-repetitions`, `--resampling-seed`,
`--tie-tolerance`, `--format json|markdown|csv`, and `--output`.

Available or partially available multi-family studies exit `0`. Entirely insufficient or
incompatible studies still emit the complete typed audit and exit `1`. The command does not infer
missing values, choose a compatibility subgroup, run pairwise tests, establish equivalence, or
mutate registry evidence. See [N-way policy ranking](n_way_ranking.md).

### `traffictwin experiment equivalence-contract [--format text|json]`

Purpose: publish the complete STA-03 evidence boundary, paired-mean TOST hypotheses, margin
contract, alpha bounds, decision rule, assumptions, unavailable behavior, and limitations without
reading a registry.

### `traffictwin experiment equivalence-study --registry REGISTRY --experiment-id ID`

Purpose: evaluate one registered baseline-versus-variation equivalence claim over the exact
STA-01 common-seed cohort. Required selection options are `--baseline-seed`, `--variation-seed`,
and `--algorithm`. The plan also requires `--equivalence-margin`, `--margin-basis
practical_threshold|literature|provisional_design`, and `--margin-justification`; a literature
basis additionally requires `--margin-reference`. Other controls are `--checkpoint`, `--metric`,
`--objective`, `--alpha`, `--format json|markdown|csv`, and `--output`.

An available study exits `0` whether equivalence is demonstrated or not. Insufficient,
incompatible, or zero-variance degenerate studies still emit the typed artifact and exit `1`.
The command does not choose or validate the practical margin, infer missing values, use ordinary
non-significance as equivalence, prove difference after failed TOST, or mutate registry evidence.
See [paired equivalence testing](equivalence_testing.md).

### `traffictwin experiment regression-contract [--format text|json]`

Purpose: publish the complete STA-04 subject, approval, source-identity, scalar selector, tolerance,
outcome-precedence, unavailable, limitation, and CI exit-code boundary without reading a subject.

### `traffictwin experiment regression-golden SUBJECT --contract-id ID --contract-version VERSION`

Purpose: generate a reviewable versioned golden from one completed metric collection (a validated
bundle path or registered run ID) or paired STA-01 study JSON. Repeat `--tolerance
SELECTOR=ABSOLUTE,RELATIVE` for each scalar. Use `--subject-kind paired_statistical_study` for study
JSON. `--source-identity-policy exact|compatible_context` is explicit.

The default is `candidate`. An approved golden additionally requires `--approval-status approved`,
`--approved-by`, and `--approval-note`. The command emits JSON to stdout or `--output`. It never
changes the subject, registry, source bundle, or an existing golden.

### `traffictwin experiment regression-gate SUBJECT --golden FILE`

Purpose: evaluate the golden's typed subject. Use `--registry` when `SUBJECT` is a registered run
ID; bundle paths are ordinarily validated and computed, while paired-study subjects are parsed as
bounded strict JSON. Formats are `json`, `markdown`, and `csv`, with optional `--output`.

Exit `0` means every assertion passed, `1` means a complete scalar exceeded tolerance, and `2`
means approval, subject, source, context, unit/version, or required value was unavailable. CI should
act on the exit code and machine JSON rather than grep prose. See
[versioned regression gates](regression_gates.md).

### `traffictwin experiment power-contract [--format text|json]`

Purpose: publish the complete STA-05 pairing, estimand, normal-approximation method, input/bound,
small/synthetic label, unavailable, assumption, unsupported-scope, and limitation contract without
reading a registry or completed result.

### `traffictwin experiment power-analysis --metric KEY --unit UNIT`

Purpose: estimate the minimum common-seed pair count for one prospective two-sided comparison.
Required planning options are `--target-effect`, `--paired-difference-variance`, `--effect-basis`,
`--effect-justification`, `--variance-basis`, and `--variance-justification`. Literature bases
require the matching reference; pilot bases require `--pilot-sample-size`; synthetic bases require
`--synthetic`. Other controls are `--alpha`, `--target-power`, `--maximum-replicates`, `--format
json|markdown|csv`, and `--output`.

An available plan exits `0`. Zero effect, non-positive variance, an exceeded search ceiling, or an
invalid plan emits or explains a typed unavailable result and exits `2`. The command does not
derive inputs from observed results, calculate retrospective/achieved power, inflate for attrition,
run a simulator, or guarantee significance. See [paired common-seed power analysis](power_analysis.md).

### `traffictwin experiment evidence --registry REGISTRY --experiment-id ID`

Purpose: build a reusable experiment-level EvidencePack from stored metric collections. Use
`--metric`, `--objective maximise|minimise`, `--output`, and `--store` as needed. R5 evidence is
created only from explicit pairs. Repeat `--training-run` and `--validation-run` the same number of
times; entries are paired by position. Pairs must have compatible experiment, policy, checkpoint,
random seed, metric version, unit, and role-specific environment provenance. Incompatible or
duplicate pair inputs return exit code `1`.

### `traffictwin experiment winner-map --registry REGISTRY --experiment-id ID`

Purpose: rank observed policies independently for each seed family and report winners, ties, and
regret for an explicit scalar metric and objective.

### `traffictwin experiment portfolio --registry REGISTRY --experiment-id ID`

Purpose: evaluate the transparent synthetic portfolio rules against the experiment winner map.
The report is descriptive and is not a trained-policy claim.

### `traffictwin experiment portfolio-study --registry REGISTRY --experiment-id ID`

Purpose: evaluate a fixed transparent selector over explicit, disjoint development and held-out
seed families, and compare every observed constituent on the held-out set. Repeat
`--development-seed` and `--held-out-seed` for custom splits. The synthetic portfolio-study
experiment uses its documented three-family development and S5/S6 held-out split when neither
option is supplied.

### `traffictwin experiment track-init --registry REGISTRY --experiment-id ID`

Purpose: register every deterministic protocol slot for manual, import-first tracking.

### `traffictwin experiment track-list --registry REGISTRY --protocol-id ID`

Purpose: list status counts and slots in text or JSON.

### `traffictwin experiment track-update --registry REGISTRY --protocol-id ID --slot-id ID --status STATUS`

Purpose: apply one valid manual lifecycle transition. Optional `--run-id`, `--bundle-id`, and
`--note` record observed coordination metadata. The command does not execute a run.

## Diagnostic Commands

### `traffictwin diagnose temporal BUNDLE --width-s SECONDS [OPTIONS]`

Purpose: compute a fixed-window artifact, project one eligible scalar metric into typed temporal
evidence, attach it to an EvidencePack, and evaluate deterministic R6 through the ordinary ruleset.

```bash
traffictwin diagnose temporal tests/fixtures/bundles/baseline_valid \
  --width-s 10 \
  --metric-key task.deadline_miss.completed_observed_rate \
  --event-time-s 20 --event-label incident \
  --format json --output build/temporal-diagnosis.json
```

Window options include `--origin-s`, paired `--start-s`/`--end-s`,
`--partial-windows include|exclude`, and `--minimum-window-coverage`. The standard 10,000-window
admission bound applies. R6 options expose the exact baseline count, minimum evaluable count,
absolute adverse delta, sustained count, recovery tolerance, and recovery horizon. Defaults are
provisional synthetic-development settings. Missing/partial/unavailable windows break consecutive
runs and are never zero. The optional event is declared by the researcher and is never inferred.
See [Temporal diagnosis](temporal_diagnosis.md).

### `traffictwin diagnose rule-contract [--format text|json]`

Purpose: print the v1.0 declarative-rule grammar, size/predicate bounds, trust/evidence boundary,
and excluded arbitrary-code features.

### `traffictwin diagnose rule-validate RULE_YAML [--format text|json]`

Purpose: parse, strictly validate, and fingerprint one trusted local static YAML definition
without evaluating it. Local IDs must begin `LOCAL_`; core `R0`–`R8` IDs are reserved. Unsafe or
ambiguous YAML and unsupported language features return exit code `1`.

### `traffictwin diagnose rule-evaluate RULE_YAML EVIDENCE_OR_BUNDLE [OPTIONS]`

Purpose: compile one admitted local definition and evaluate it over the ordinary EvidencePack
metric boundary. Use `--format text|json` and optional `--output FILE`. The second input is a
validated bundle or saved EvidencePack JSON, not arbitrary metric JSON.

### `traffictwin diagnose fairness PATH [OPTIONS]`

Purpose: evaluate only R7 for exactly one `vehicle_tier_completion` or `target_rsu_completion`
dimension. Options expose the provisional `--minimum-outcome-gap`, exact
`--minimum-group-support`, text/JSON format, and output file. Missing, thin, partial, or
incompatible group evidence produces insufficiency rather than zero.

```bash
traffictwin diagnose fairness path/to/bundle \
  --dimension vehicle_tier_completion \
  --minimum-outcome-gap 0.20 \
  --minimum-group-support 2 \
  --format json
```

See [declarative rules](declarative_rules.md) and [R7 diagnosis](fairness_diagnosis.md).

### `traffictwin diagnose energy PATH [OPTIONS]`

Purpose: evaluate only R8 over exact completed-task energy and denominator evidence. Options expose
the provisional `--minimum-energy-per-completed-task-j`, `--minimum-completed-tasks`, text/JSON
format, and output file. Missing, partial, mixed-unit, contract-incompatible, or inconsistent
evidence produces insufficiency; a high value with thin support is conflicting.

```bash
traffictwin diagnose energy path/to/bundle \
  --minimum-energy-per-completed-task-j 1.50 \
  --minimum-completed-tasks 10 \
  --format json
```

See [R8 completed-task energy diagnosis](energy_diagnosis.md).

### `traffictwin diagnose nearest-flip PATH RULE_ID [OPTIONS]`

Purpose: compute the exact verified single-boundary sensitivity result for an eligible
`not_triggered` R5, R7, or R8 result. `PATH` may be a bundle/ZIP or saved EvidencePack. Optional
`--rule-config FILE` reads a complete `RuleSetConfig` JSON; `--format text|json` and
`--output FILE` control rendering only.

```bash
traffictwin diagnose nearest-flip path/to/bundle R8 --format json
```

The analysis never lowers pair/group/task support, persists a candidate, or calls unsupported
compound rules. R0-R4, R6, and arbitrary declarative rules return an explicit unsupported
artifact. See [nearest-flip analysis](nearest_flip_analysis.md).

### `traffictwin diagnose bundle PATH`

Purpose: validate a bundle, compute metrics, build an EvidencePack, and evaluate deterministic rules.

Example:

```bash
traffictwin diagnose bundle tests/fixtures/bundles/baseline_valid
```

Rejected bundles suppress ordinary hypotheses and return exit code `1`.

### `traffictwin diagnose cross-rule-contract [--format text|json]`

Purpose: publish the closed DIA-07 policy, precedence tiers, exact overlap requirements, retention
guarantee, and confidence boundary.

```bash
traffictwin diagnose cross-rule-contract --format json
```

### `traffictwin diagnose cross-rule PATH [--format text|json] [--output FILE]`

Purpose: evaluate ordinary rules for a bundle or saved EvidencePack and emit only the additive
typed `CrossRuleReasoningReport`.

```bash
traffictwin diagnose cross-rule tests/fixtures/bundles/baseline_valid --format json
```

The command never ranks root causes, changes confidence, or removes a suppressed result. See
[deterministic cross-rule reasoning](cross_rule_reasoning.md).

### `traffictwin diagnose evidence EVIDENCE_JSON`

Purpose: evaluate deterministic rules over a saved EvidencePack JSON file.

Example:

```bash
traffictwin evidence build tests/fixtures/bundles/baseline_valid --output evidence-baseline.json
traffictwin diagnose evidence evidence-baseline.json
```

### `traffictwin diagnose report PATH --format json`

Purpose: emit a complete machine-readable DiagnosticReport for a bundle or EvidencePack JSON.

Example:

```bash
traffictwin diagnose report tests/fixtures/bundles/baseline_valid --format json
```

Only JSON output is supported. The payload embeds the typed `cross_rule_analysis` artifact and all
unchanged original RuleResults.

### `traffictwin diagnose evaluate FIXTURE_SET`

Purpose: evaluate labelled synthetic diagnostic fixtures.

Example:

```bash
traffictwin diagnose evaluate tests/fixtures/diagnostics/cases.json
```

This is implementation verification over synthetic cases, not external diagnostic validation.
Use `--extended` to expand the cases across three severity levels and three random seeds. The
report adds true/false positives and negatives, precision, recall, false-positive rate,
specificity, split summaries, severity robustness, failure IDs, and a transparent KPI baseline.

### `traffictwin diagnose render PATH [--format markdown|json] [--output FILE]`

Purpose: restate only already-computed diagnostic findings. Every finding sentence cites its
finding ID and evidence keys, and actions remain conditional. The renderer performs no metric
calculation, diagnosis, or LLM call.

## Provenance Commands

### `traffictwin provenance metric PATH METRIC_KEY [--format text|json|markdown|dot|graphml]`

Purpose: trace one metric result back to its metric definition, required canonical evidence,
source-row samples where available, validation context, run metadata, and fingerprint.

Example:

```bash
traffictwin provenance metric tests/fixtures/bundles/baseline_valid task.completion.rate
```

Rejected bundles return exit code `1` for metric traces because metrics are unavailable.

### `traffictwin provenance contributors PATH METRIC_KEY [--format json|csv] [--output FILE]`

Purpose: export every accepted canonical candidate row for a metric, including source file/row,
canonical values, inclusion state, and deterministic inclusion reason. This is a complete input
ledger, not a claim of per-row causal weight.

### `traffictwin provenance difference-contract [--format text|json]`

Purpose: publish the closed PRO-01 compatibility, arithmetic-formula, lineage-only,
reconciliation, unavailable, and non-causality boundary.

### `traffictwin provenance difference-contributors BASELINE VARIATION METRIC_KEY [--format json|csv] [--output FILE]`

Purpose: export both complete accepted-row ledgers for an ordinary compatible metric comparison.
Admitted direct count/sum/mean/rate formulas include signed terms that reconcile to
`variation - baseline`; percentiles and other non-decomposable scalar metrics expose eligible
lineage with null weights. JSON and every CSV row carry the mandatory non-causality statement. See
[difference provenance](difference_provenance.md).

### `traffictwin provenance graph-contract [--format text|json]`

Purpose: publish the PRO-02 DOT/GraphML formats, default/hard bounds, traversal, stable-ID,
redaction, path-safety, determinism, and limitation contract.

### `traffictwin provenance completeness-contract [--format text|json]`

Purpose: publish the PRO-03 supported report templates, explicit typed-claim denominator, named
exclusion policy, mutually exclusive classification rules, directed trace-depth rules,
unweighted numerator, unavailable behavior, and null zero-denominator policy.

### `traffictwin provenance completeness PATH [--report-type run|diagnostics|full] [--comparison-baseline PATH] [--format json|csv|text] [--output FILE]`

Purpose: inventory every typed metric/rule/comparison claim in a run-like report template and
classify it as source-row complete, aggregate-only, or unavailable. Unavailable claims remain in
the denominator. Use `--comparison-baseline` with `full` to include its comparison claims. CSV has
one row per denominator claim.

### `traffictwin provenance comparison-completeness BASELINE VARIATION [--format json|csv|text] [--output FILE]`

Purpose: score the exact typed comparison-report claims using complete accepted-row ledgers on
both sides. Unavailable/incompatible comparisons remain visible and contribute zero. See
[provenance completeness](provenance_completeness.md).

### `traffictwin provenance export PATH --root-type metric|rule|run [--root-id ID] [--format json|markdown|dot|graphml] [--max-nodes N] [--max-edges N] [--redaction safe|structure_only] [--output FILE]`

Purpose: export an existing trace. DOT and GraphML use deterministic bounded graph projection;
the default is 120 nodes/240 edges with hard maxima of 500/2,000. The root is retained and exact
omitted counts are embedded. `safe` recursively redacts local paths; `structure_only` also removes
descriptions, attributes, and source references. JSON and Markdown remain the existing full trace
formats, so graph-only limit/redaction options do not rewrite those schemas.

Example:

```bash
traffictwin provenance export tests/fixtures/bundles/baseline_valid \
  --root-type metric --root-id task.completion.rate \
  --format graphml --max-nodes 80 --max-edges 160 \
  --redaction structure_only --output completion.graphml
```

See [provenance graph exports](provenance_graph_exports.md).

### `traffictwin provenance window-metric PATH METRIC_KEY --width-s SECONDS [OPTIONS]`

Purpose: trace one metric in one zero-based window ordinal through the ordinary metric definition,
filtered canonical rows, and accepted source rows. Window options match `metrics windows`; use
`--window-ordinal`, and choose `--format text|json|markdown`.

### `traffictwin provenance window-contributors PATH METRIC_KEY --width-s SECONDS [OPTIONS]`

Purpose: export the complete accepted canonical candidate-row ledger for one included fixed
window as JSON. The artifact includes the window contract and the ordinary eligibility report.
Use `--output FILE` for a reproducible export. Excluded partial windows fail because no metric was
computed; this state is not silently replaced with an empty ledger.

### `traffictwin provenance rule PATH RULE_ID [--format text|json|markdown|dot|graphml]`

Purpose: trace one DiagnosticReport rule result back through findings, evidence keys, metric
results, metric definitions, and source evidence where the accepted bundle provides it.

Example:

```bash
traffictwin provenance rule tests/fixtures/bundles/variation_valid R2 --format json
```

### `traffictwin provenance run PATH [--format text|json|markdown|dot|graphml]`

Purpose: trace bundle, manifest, run, seed, environment, validation, metric, evidence, and
diagnostic context for a bundle.

Example:

```bash
traffictwin provenance run tests/fixtures/bundles/baseline_valid
```

### `traffictwin provenance source PATH FILE ROW [--context-rows N] [--format text|json]`

Purpose: inspect one read-only declared CSV, gzip-CSV, or Parquet source row inside a directory or
ZIP bundle. Paths must be
bundle-relative.

Example:

```bash
traffictwin provenance source tests/fixtures/bundles/baseline_valid tasks.csv 2
```

The `provenance export` command documented above supports `metric`, `rule`, and `run` roots.
Provenance commands are read-only and do not mutate imported files or registry contents.

Related documents:

- [User guide](user_guide.md)
- [Provenance Explorer](provenance_explorer.md)
- [Reproducibility guide](reproducibility.md)
- [Generated CLI help](reference/generated/cli_help.json)
- [Standalone demo](standalone_demo.md)

## Manifest Inference Commands

These commands suggest mappings for generic CSV inputs without allowing a draft into analysis.

### `traffictwin manifest contract [--format text|json|yaml]`

Shows the versioned limits, method precedence, required/supported fields, aliases, distinctive
value vocabularies, unit/confirmation policy, score semantics, and unsupported behavior.

### `traffictwin manifest infer SOURCE [--format text|json|yaml] [--output PATH]`

Profiles bounded CSV headers/values, fingerprints complete files, and emits a
`ManifestInferenceDraft`. Text output summarises file status; JSON/YAML contains the complete
candidate evidence. The draft always has `analysis_ready: false`.

### `traffictwin manifest confirm DRAFT SOURCE --confirmed-by LABEL --output PATH [OPTIONS]`

Rechecks the source fingerprint and creates `CanonicalisationManifest` only after explicit
acceptance or edits.

Options:

- `--accept-suggestions` explicitly accepts all unambiguous defaults;
- `--kind FILE=KIND` selects/changes a file kind;
- `--map FILE:FIELD=COLUMN` selects/changes a source column;
- `--unmap FILE:FIELD` removes a proposed optional mapping;
- `--unit FILE:FIELD=UNIT` supplies or changes a unit;
- `--exclude FILE` records an excluded CSV;
- `--overwrite` replaces an existing output deliberately.

Unresolved required mappings, ambiguity, stale bytes, duplicate source use, unsupported units, and
two files assigned to the same current manifest kind return exit code `1`.

### `traffictwin manifest files CONFIRMED [--format yaml|json]`

Renders confirmed `files:` declarations for inspection/manual use. It performs no import.

### `traffictwin manifest apply CONFIRMED TEMPLATE --output PATH [--overwrite]`

Applies confirmed declarations to a complete `BundleManifest` metadata template and embeds
confirmation provenance. It does not invent bundle/run/environment/seed metadata or validate data
rows.

```bash
traffictwin manifest infer tests/fixtures/manifest_inference/value_patterns \
  --format yaml --output mapping-draft.yaml
traffictwin manifest confirm mapping-draft.yaml \
  tests/fixtures/manifest_inference/value_patterns \
  --accept-suggestions --confirmed-by "analyst-role" \
  --output canonicalisation.yaml
traffictwin manifest apply canonicalisation.yaml \
  tests/fixtures/manifest_inference/value_patterns/manifest-template.yaml \
  --output manifest.yaml
```

See [Manifest Inference Wizard](integration/manifest_inference_wizard.md).

## General External-source Commands

These OPS-05 commands discover and inspect reviewed completed-result adapters without launching,
repairing, converting, or registering the source.

### `traffictwin integration external contract [--adapter ID] [--format text|json]`

Print the shared interface policy and both reference contracts, or select
`sumo_results_v1`/`tos_data_read_only`. The JSON includes field semantics, complete capability
truth, provenance requirements, conversion outputs, blockers, and limits.

### `traffictwin integration external discover PATH [--format text|json]`

Check exact direct markers only. Exactly one match exits `0`; no match, ambiguity, or unsafe
symbolic-link discovery is returned visibly and exits `1`. A marker match is not validation.

### `traffictwin integration external inspect PATH [--adapter ID] [--deep|--shallow] [--format text|json]`

Select the sole discovered adapter or a caller-confirmed matching adapter, invoke its existing
read-only validator, and emit a deterministic path-free inspection. Rejected/unavailable validation
exits `1`; accepted or accepted-with-warnings exits `0` within that adapter's declared import scope.

```bash
traffictwin integration external contract --format json
traffictwin integration external discover path/to/source
traffictwin integration external inspect path/to/source --deep --format json
```

See the [general external-source contract](integration/external_source_contract.md).

## SUMO Output Commands

These commands read an existing SUMO result directory containing `sumo-source.yaml`,
`tripinfo.xml`, and `summary.xml`. They do not require SUMO to be installed and never launch it.

### `traffictwin integration sumo contract [--format text|json]`

Shows the supported SUMO versions, explicit XML mappings, import-only capability manifest,
interpretation limits, and unavailable features.

### `traffictwin integration sumo validate PATH [--format text|json]`

Checks source/licence metadata, immutable checksums, safe XML, trip IDs/timing, and monotonic summary
steps. JSON returns the full typed result including canonical trips and source-specific summaries.

### `traffictwin integration sumo metrics PATH [--format text|json]`

Computes existing deterministic trip metrics from accepted canonical trips. It does not calculate
a canonical traffic count from summary occupancy.

### `traffictwin integration sumo import PATH --registry REGISTRY`

Registers accepted run metadata and its metric collection. Repeating an identical import is
idempotent; changed content under the same bundle/run ID is rejected.

```bash
traffictwin integration sumo validate tests/fixtures/sumo/square_public
traffictwin integration sumo metrics tests/fixtures/sumo/square_public
traffictwin integration sumo import tests/fixtures/sumo/square_public \
  --registry .demo/registry.sqlite
```

See [Eclipse SUMO Output Adapter](integration/sumo_output_adapter.md).

## TOS Data Integration Commands

These commands require the optional NumPy dependency:

```bash
python -m pip install -e ".[dev,tos]"
```

They read a separately supplied TOS Data package. They do not launch the source environment,
promote source-specific RSU fields to canonical metrics, or create a standard run bundle.

### `traffictwin integration tos contract [--format text|json]`

Purpose: show the versioned, source-evidenced field/unit/control contract, evaluator command
template, unavailable outputs, and direct-launch blockers. The command needs no data-package path
and never executes the evaluator.

### `traffictwin integration tos inspect PATH [--deep|--shallow] [--format text|json]`

Purpose: inventory the package, compute its fingerprint, check the evaluation master, and report
the evidenced capability boundary without registry mutation. `--deep` additionally checks NPZ
contracts and reconciles JSON summaries. The command reports a rejected status in output but use
`validate` when an exit code is required.

### `traffictwin integration tos validate PATH [--format text|json]`

Purpose: perform deep package validation. Exit code is non-zero when evaluation-summary import is
unsafe. The report distinguishes confirmed source semantics from canonical metric availability.

### `traffictwin integration tos runs PATH [--limit N]`

Purpose: list source evaluation runs and whether a matching instrumented run is available. When
available, the output includes the instrumented key accepted by `replay`, `rsu-series`, and
`task-sample`.

### `traffictwin integration tos import PATH --registry REGISTRY`

Purpose: idempotently register experiments, runs, source-summary metric collections, and partial
EvidencePacks. It stores no canonical task/infrastructure rows and no absolute source path.

### `traffictwin integration tos metrics PATH RUN_ID [--format text|json]`

Purpose: show source-provided deadline success, class deadline success, mean latency, action shares,
and offload share for one evaluation row. TrafficTwin physical-completion metrics and other
unsupported catalogue metrics remain present as unavailable.

### `traffictwin integration tos replay PATH RUN_KEY [--index N] [--max-vehicles N] [--format text|json]`

Purpose: inspect one deterministic historical frame from matched per-step and trace arrays. Vehicle
references are time-indexed source slots; positions use metres and speed uses metres per second.
RSU state includes active in-flight tasks, remaining compute backlog, and concurrency pressure.

### `traffictwin integration tos rsu-series PATH RUN_KEY [--stride N] [--limit N] [--format text|json]`

Purpose: inspect a bounded source-specific RSU history. Each row reports active in-flight tasks,
remaining compute backlog in milliseconds, maximum concurrent tasks, and concurrency pressure.
The command explicitly labels pressure as not CPU utilisation.

### `traffictwin integration tos task-sample PATH RUN_KEY [--limit N] [--format text|json]`

Purpose: inspect a bounded sample from an available per-arrival NPZ. The output preserves source
indices, simulation arrival time, joined local/V2I/V2V decision, task class, latency, and
deadline-success status; it does not create canonical task IDs.

### `traffictwin integration tos diagnose PATH RUN_ID [--format text|json]`

Purpose: evaluate the existing R0-R8 engine over the partial source-summary EvidencePack. Missing
canonical evidence produces insufficient results rather than guessed hypotheses.

### `traffictwin integration tos provenance PATH RUN_ID [--root-type metric|rule] [--root-id ID] [--format text|json|markdown]`

Purpose: export aggregate provenance to the evaluation-master row, package commit/fingerprint, run,
experiment grouping, actor, and engine version. Canonical/source-row links that cannot be supported
are explicit unavailable nodes.

### `traffictwin integration tos matrix PATH [--measure KEY] [--fleet FLEET] [--format text|json]`

Purpose: aggregate one registered source-analysis measure by campaign and scenario cell. Output
includes fleet-seed values, `n`, mean, sample SD, minimum, maximum, and P50.

### `traffictwin integration tos compare-campaigns PATH BASELINE VARIATION [--measure KEY] [--fleet FLEET] [--format text|json]`

Purpose: compute variation-minus-baseline observations paired by common cell and fleet seed. It
reports unmatched seeds and compatibility findings and never emits infinity for zero baselines.

### `traffictwin integration tos generalisation PATH [--format text|json]`

Purpose: show source-evidenced `in_domain`, `held_out`, and `unknown` campaign/cell labels. The
command does not infer labels from performance values.

### `traffictwin integration tos training-runs PATH [--limit N] [--format text|json]`

Purpose: list training CSV histories, warm-up unavailable counts, final source completion, and
available greedy/machine-record references. Machine-record contents are not printed.

### `traffictwin integration tos training PATH TRAINING_ID [--max-points N] [--format text|json]`

Purpose: load one deterministically downsampled training curve and optional greedy summary. Source
`nan` warm-up fields become JSON `null`.

### `traffictwin integration tos trace-summary PATH TRACE [--format text|json]`

Purpose: summarise processed FCD active-slot counts, speeds, bounds, and a bounded time profile. It
does not calculate trip or journey-time metrics.

### `traffictwin integration tos rsu-summary PATH RUN_KEY [--format text|json]`

Purpose: calculate exact descriptive summaries of source in-flight count, concurrency pressure,
and remaining compute backlog by RSU. These remain source inspection values.

### `traffictwin integration tos task-summary PATH RUN_KEY [--format text|json]`

Purpose: aggregate all active entries in one supplied per-task showcase by class and joined
decision, subject to an uncompressed-size safety limit.

### `traffictwin integration tos audit PATH [--format text|json]`

Purpose: report artifact coverage, actor/training-history matching, package provenance, and blocked
reproducibility dependencies. This is an engineering audit, not scientific validation.

### `traffictwin integration tos report PATH --output FILE [--variation CAMPAIGN]`

Purpose: write deterministic Markdown or standalone HTML using existing report renderers.

### `traffictwin integration tos atlas PATH --output FILE`

Purpose: write a standalone interactive HTML atlas with precomputed aggregate values, no remote
assets, no absolute source paths, and an explicit publication-permission notice.

### `traffictwin integration tos results-pack PATH --output DIRECTORY [--variation CAMPAIGN]`

Purpose: write report, matrix, paired comparison, audit, and atlas artifacts. The destination must
be empty; refusal to overwrite returns exit code `1`.

### `traffictwin integration tos readiness PATH [--format text|json]`

Purpose: report the exact evidence and permission gates for canonical conversion, R1/R2 use,
journey-time integration, direct launch, fixtures, and public TOS publication. Optional
`--confirm-fixture-permission` and `--confirm-publication-permission` flags are explicit human
attestations; they do not satisfy unrelated technical gates.

### `traffictwin integration tos supervisor-pack PATH --output DIRECTORY [--variation CAMPAIGN]`

Purpose: create a checksummed private pack containing reports, atlas, matrix, comparison, audit,
readiness JSON, evaluation plan, viva notes, and screenshot checklist. The destination must be empty.

### `traffictwin integration tos stage-public-atlas PATH --output DIRECTORY --confirm-publication-permission`

Purpose: stage `index.html` for public hosting. Without the confirmation flag the command exits `1`
and writes nothing. The flag must not be used without actual source-data permission.

Example:

```bash
traffictwin integration tos validate ../external/tos-data
traffictwin integration tos contract --format json
traffictwin integration tos runs ../external/tos-data --limit 5
traffictwin integration tos import ../external/tos-data \
  --registry data/registry/traffictwin-tos.sqlite
traffictwin integration tos metrics ../external/tos-data \
  tos:baseline:wd_am:uk2030:fs0 --format json
traffictwin integration tos rsu-series ../external/tos-data \
  baseline_uk2030_wd_am_fs0 --stride 10 --limit 100
traffictwin integration tos provenance ../external/tos-data \
  tos:baseline:wd_am:uk2030:fs0 \
  --root-id tos.task.deadline_success.rate --format markdown
traffictwin integration tos matrix ../external/tos-data
traffictwin integration tos compare-campaigns ../external/tos-data \
  baseline ukfleettrain_mappo
traffictwin integration tos audit ../external/tos-data
traffictwin integration tos readiness ../external/tos-data --format json
traffictwin integration tos results-pack ../external/tos-data \
  --output /tmp/traffictwin-tos-results
traffictwin integration tos supervisor-pack ../external/tos-data \
  --output /tmp/traffictwin-supervisor-pack
```

## Standalone Synthetic Commands

### `traffictwin synthetic presets`

Purpose: list supported standalone synthetic presets.

### `traffictwin synthetic measurement-contract [--output PATH]`

Purpose: print or write the closed EXP-03 bounded generated-observation noise/dropout contract.
It explicitly reports synthetic-only, not-calibrated, and no-direct-launch boundaries.

### `traffictwin synthetic generate-config --config FILE --output PATH [--overwrite]`

Purpose: load one complete strict `SyntheticScenarioConfig` YAML/JSON file, generate a transactional
ordinary bundle, and validate it. If measurement imperfections are enabled, output includes the
audit fingerprint and exact dropped-row count.

Example:

```bash
traffictwin synthetic generate-config \
  --config examples/synthetic_measurement_imperfections.yaml \
  --output build/measurement-robustness
```

The command refuses invalid models and existing destinations without explicit overwrite. It never
launches SUMO, Randy/VEC/TOS, training, or another simulator.

### `traffictwin synthetic generate-preset NAME --output PATH [--seed N] [--overwrite]`

Purpose: generate one deterministic standard TrafficTwin run bundle.

Example:

```bash
traffictwin synthetic generate-preset baseline --output /tmp/tt-baseline --overwrite
```

### `traffictwin synthetic experiment-generate-preset trivial_multi_algorithm --seeds 1,2,3 --output PATH [--overwrite]`

Purpose: generate a low-pressure multi-policy synthetic experiment used to exercise existing R3
evidence.

### `traffictwin synthetic verify PATH`

Purpose: validate one generated bundle or all generated bundles under a workspace. The command exits
non-zero if a discovered bundle is rejected or not labelled synthetic.

### `traffictwin synthetic case-study-pack --output PATH [--overwrite]`

Purpose: generate a checksummed synthetic baseline, incident/demand, and
reduced-infrastructure case-study pack with metrics, diagnostics, and comparisons. It launches no
simulator.

## Standalone Demo Commands

### `traffictwin demo initialise PATH [--force]`

Purpose: create a reproducible standalone workspace, validate generated bundles, import accepted
runs, compute metrics, build EvidencePacks, evaluate diagnostics, write provenance exports, and
prepare deterministic reports.

### `traffictwin demo reset PATH --yes`

Purpose: regenerate a marked standalone demo workspace. The command refuses unconfirmed resets and
does not operate on unmarked arbitrary directories.

### `traffictwin demo status PATH`

Purpose: show workspace validity, registry path, generated scenarios, imported runs, reports,
comparisons, diagnostics status, and the synthetic disclaimer.

### `traffictwin demo launch PATH [--dry-run]`

Purpose: initialise the workspace if absent and start Streamlit with explicit workspace environment
variables. `--dry-run` prints the command without starting the server.

## Report Commands

### `traffictwin report run PATH --output REPORT [--registry REGISTRY]`

Purpose: export a deterministic single-run report. `.json` preserves the complete typed structured
payload for REP-03, `.html` is standalone HTML, `.pdf` is A4 PDF, and other suffixes are Markdown.
An explicit registry adds matching REP-02 history in a separate non-computed section.

### `traffictwin report compare BASELINE VARIATION --output REPORT [--registry REGISTRY]`

Purpose: export a deterministic comparison report over two accepted bundles.

### `traffictwin report diagnostics PATH --output REPORT [--registry REGISTRY]`

Purpose: export a deterministic diagnostic report summary for one accepted bundle.

### `traffictwin report full PATH --output REPORT [--comparison-baseline BASELINE] [--registry REGISTRY]`

Purpose: export a full Markdown, standalone HTML, or A4 PDF report, optionally including comparison
context.

### `traffictwin report diff-contract [--format text|json]`

Purpose: show REP-03 supported report types, classifications, compatibility reasons, exclusions,
bounds, non-causal policy, and deterministic contract fingerprint.

### `traffictwin report diff BASELINE_REPORT_JSON VARIATION_REPORT_JSON --output DIFF`

Purpose: compare two saved compatible structured report payloads through prose-free typed claim
snapshots. `.json` is the complete machine-readable result; `.md`/`.markdown` is a visibly
non-causal presentation. Incompatible inputs still produce a typed `unavailable` result. Rendered
prose, annotations, timestamps, warnings, labels, and reproduction commands are never scientific
diff inputs. See [structured report diffing](structured_report_diffing.md).

### `traffictwin report executive-contract [--format text|json]`

Purpose: show REP-04 supported report types/formats, five-highlight bound, exact selection policy,
retain-all-or-refuse warning/limitation policy, fail-closed PDF rule, and contract fingerprint.

### `traffictwin report executive SOURCE_REPORT_JSON --output SUMMARY`

Purpose: project one compatible saved typed report into a bounded supervisor summary. `.json` is
the exact machine projection, `.md`/`.markdown` is Markdown, `.html` is self-contained print HTML,
and `.pdf` is an invariant A4 artifact accepted only when all warnings and limitations fit on one
page. The command performs no scientific recomputation and excludes analyst annotations. See
[one-page executive summary](executive_summary.md).

### `traffictwin report latex-contract`

Purpose: print the REP-01 version, four supported typed artifact families, SVG/PDF formats,
renderer bounds, scientific boundary, path policy, and contract fingerprint.

### `traffictwin report latex-metrics PATH --output TABLE [--figure FIGURE] [--overwrite]`

Purpose: validate a bundle, compute its ordinary `MetricCollection`, and render that completed
artifact as an escaped `.tex` fragment plus optional deterministic `.svg` or `.pdf` figure.

### `traffictwin report latex-comparison BASELINE VARIATION --output TABLE [--figure FIGURE] [--overwrite]`

Purpose: render an ordinary compatible/incompatible `ComparisonReport` without reimplementing
comparison logic. Unavailable comparisons remain table rows rather than becoming zero.

### `traffictwin report latex-study STUDY_JSON --output TABLE [--figure FIGURE] [--overwrite]`

Purpose: strictly parse and render one saved STA-01 `StatisticalStudy` JSON artifact. The command
does not infer a study from arbitrary JSON or re-run a statistical method.

### `traffictwin report latex-rules PATH --output TABLE [--figure FIGURE] [--overwrite]`

Purpose: render exact deterministic rule statuses/confidence categories for a validated bundle.
The figure is categorical and does not convert status or confidence to probability.

All five export commands derive table and figure from one fingerprinted bounded projection. The
table requires `.tex`; a figure requires `.svg` or `.pdf`; existing files require `--overwrite`.
Receipts show filenames, SHA-256 checksums, sizes, and the shared projection fingerprint. See
[LaTeX research tables and static figures](latex_research_exports.md).

## Analyst-Annotation Commands

### `traffictwin registry annotation-contract [--format text|json]`

Purpose: show REP-02 target/decision catalogues, bounds, append-only policy, scientific boundary,
and stable contract fingerprint.

### `traffictwin registry annotation-add --registry REGISTRY --target-kind KIND --target-id ID --author AUTHOR --note NOTE [--decision-label LABEL] [--target-fingerprint SHA256]`

Purpose: append one exact analyst-authored entry. Stored target kinds must exist; generated report,
study, comparison, and diagnostic references are explicit detached targets. No update/delete
command exists.

### `traffictwin registry annotation-list --registry REGISTRY [--target-kind KIND --target-id ID] [--target-fingerprint SHA256] [--after-sequence N] [--limit N] [--format text|json]`

Purpose: read an ascending bounded page with `has_more` and an exact history fingerprint. See
[analyst annotations](analyst_annotations.md).

## Mock Participant-Evaluation Commands

### `traffictwin participant-evaluation analyse-mock PATH [--format json|csv] [--output FILE]`

Purpose: analyse only a JSON dataset carrying `dataset_mode: synthetic_mock`. Withdrawn records
are excluded. Outputs are descriptive software-fixture summaries, not participant evidence or
ethics approval.

## Manchester Baseline-Network Commands

Design Gate-D step 1 (network binding) only. `MAN-09` remains `planned`; a built network is
geometry and is never calibration, validation, live traffic, or VEC execution. See
[ADR-059](decisions/ADR-059-greater-manchester-baseline-network.md) and the
[baseline network guide](integration/manchester_baseline_network.md).

Show the approved scope, required-area inclusion, CRS, and DfT coverage semantics:

```bash
traffictwin integration manchester network scope
traffictwin integration manchester network scope --format json
```

Acquire the pinned OpenStreetMap extract. Network access requires an explicit `--confirm`; the
host, path, media types, and byte bounds are frozen and no URL is accepted. Use `--from-file` to
import an operator-supplied local extract with no network access at all:

```bash
traffictwin integration manchester network acquire <workspace> --confirm
traffictwin integration manchester network acquire <workspace> --confirm --from-file <path>
```

Build one candidate with the frozen `netconvert` 1.27.1 recipe. The builder takes no arguments,
flags, or tool paths from the caller and never uses a shell:

```bash
traffictwin integration manchester network build <workspace> \
    --extract <path> --network-id <id>
```

List, re-verify, and report honest status:

```bash
traffictwin integration manchester network list <workspace>
traffictwin integration manchester network verify <workspace> --network-id <id>
traffictwin integration manchester network status [<workspace>]
```

`verify` re-checks both the raw digest and the canonical semantic identity; a mutated network file
or binding record fails with `NETWORK_MUTATED` or `NETWORK_IDENTITY_MUTATED` and a non-zero exit.
`status` lists what remains unavailable, including every map-matching blocker and the fact that DfT
calibration evidence covers Manchester local authority only.

Known refusals: `OSM_PBF_DECODE_UNAVAILABLE` (the reviewed `netconvert` build reads OSM XML only and
no approved PBF decoder is installed), `SUMO_VERSION_DRIFT`, `SUMO_TOOLCHAIN_UNAVAILABLE`,
`CHECKSUM_IDENTITY_DRIFT`, and `NETWORK_VALIDATION_REJECTED`.

## Release And Deployment Commands

### `traffictwin release status [--format text|json]`

Purpose: show package version, licence status, production status, and the supported, gated, or
unsupported deployment modes.

### `traffictwin release stage-demo-site WORKSPACE --output DIRECTORY [--force]`

Purpose: stage a Netlify-compatible static dashboard from an initialised standalone workspace. The
command accepts synthetic bundles only and reads existing metric and diagnostic outputs. `--force`
can replace only a directory carrying a valid TrafficTwin static-site marker.

Example:

```bash
traffictwin demo initialise .netlify-demo
traffictwin release stage-demo-site .netlify-demo --output public
```

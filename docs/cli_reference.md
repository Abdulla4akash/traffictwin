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
- unconfirmed Randy/SUMO controls: `unknown`

## Registry Commands

### `traffictwin registry init PATH`

Purpose: create a SQLite metadata registry if it does not exist.

Example:

```bash
traffictwin registry init data/registry/traffictwin.sqlite
```

### `traffictwin registry inspect PATH`

Purpose: print registry counts for seeds, experiments, runs, bundle imports, metrics, and evidence packs.

Example:

```bash
traffictwin registry inspect data/registry/traffictwin.sqlite
```

Common errors:

- path does not exist for `inspect`;
- path not writable for `init`.

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

### `traffictwin bundle report PATH --format json`

Purpose: print the full validation report JSON.

Example:

```bash
traffictwin bundle report tests/fixtures/bundles/partial_valid --format json
```

Only JSON output is supported.

## Metrics Commands

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

## Diagnostic Commands

### `traffictwin diagnose bundle PATH`

Purpose: validate a bundle, compute metrics, build an EvidencePack, and evaluate deterministic rules.

Example:

```bash
traffictwin diagnose bundle tests/fixtures/bundles/baseline_valid
```

Rejected bundles suppress ordinary hypotheses and return exit code `1`.

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

Only JSON output is supported.

### `traffictwin diagnose evaluate FIXTURE_SET`

Purpose: evaluate labelled synthetic diagnostic fixtures.

Example:

```bash
traffictwin diagnose evaluate tests/fixtures/diagnostics/cases.json
```

This is implementation verification over synthetic cases, not external diagnostic validation.

## Provenance Commands

### `traffictwin provenance metric PATH METRIC_KEY [--format text|json|markdown]`

Purpose: trace one metric result back to its metric definition, required canonical evidence,
source-row samples where available, validation context, run metadata, and fingerprint.

Example:

```bash
traffictwin provenance metric tests/fixtures/bundles/baseline_valid task.completion.rate
```

Rejected bundles return exit code `1` for metric traces because metrics are unavailable.

### `traffictwin provenance rule PATH RULE_ID [--format text|json|markdown]`

Purpose: trace one DiagnosticReport rule result back through findings, evidence keys, metric
results, metric definitions, and source evidence where the accepted bundle provides it.

Example:

```bash
traffictwin provenance rule tests/fixtures/bundles/variation_valid R2 --format json
```

### `traffictwin provenance run PATH [--format text|json|markdown]`

Purpose: trace bundle, manifest, run, seed, environment, validation, metric, evidence, and
diagnostic context for a bundle.

Example:

```bash
traffictwin provenance run tests/fixtures/bundles/baseline_valid
```

### `traffictwin provenance source PATH FILE ROW [--context-rows N] [--format text|json]`

Purpose: inspect one read-only CSV source row inside a directory or ZIP bundle. Paths must be
bundle-relative.

Example:

```bash
traffictwin provenance source tests/fixtures/bundles/baseline_valid tasks.csv 2
```

### `traffictwin provenance export PATH --root-type TYPE --root-id ID [--format json|markdown] [--output FILE]`

Purpose: export a complete `ProvenanceTrace` document. Supported root types are `metric`, `rule`,
and `run`.

Example:

```bash
traffictwin provenance export tests/fixtures/bundles/baseline_valid \
  --root-type metric \
  --root-id task.completion.rate \
  --format markdown \
  --output provenance-task-completion.md
```

Provenance commands are read-only and do not mutate imported files or registry contents.

Related documents:

- [User guide](user_guide.md)
- [Provenance Explorer](provenance_explorer.md)
- [Reproducibility guide](reproducibility.md)
- [Generated CLI help](reference/generated/cli_help.json)
- [Standalone demo](standalone_demo.md)

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

Purpose: evaluate the existing R0-R3 engine over the partial source-summary EvidencePack. Missing
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

### `traffictwin report run PATH --output REPORT`

Purpose: export a deterministic single-run report. `.html` outputs are standalone HTML; other
suffixes are Markdown.

### `traffictwin report compare BASELINE VARIATION --output REPORT`

Purpose: export a deterministic comparison report over two accepted bundles.

### `traffictwin report diagnostics PATH --output REPORT`

Purpose: export a deterministic diagnostic report summary for one accepted bundle.

### `traffictwin report full PATH --output REPORT [--comparison-baseline BASELINE]`

Purpose: export a full Markdown or standalone HTML report, optionally including comparison context.

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

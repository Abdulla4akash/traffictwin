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

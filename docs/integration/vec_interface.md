# VEC-10 CLI and UI Interface

VEC-10 exposes the accepted VEC-01 and VEC-03–VEC-09 services through a thin typed interface. It
does not add a second launcher, metric calculator, join implementation, or scientific decision
layer. Every operation delegates to the existing tested library contract.

## Capability boundary

The interface supports:

- read-only snapshot inspection of the pinned `vec_env` and `tos-data` repositories;
- request-specific VEC-06 and VEC-07 preflight validation;
- foreground FCD/network preprocessing and evaluator execution after accepted preflight;
- monitoring only the operation owned by the current CLI or Streamlit process;
- strict receipt/report inspection;
- descriptive comparison of compatible available scalar VEC-09 metrics; and
- JSON, CSV, or Markdown export of an accepted VEC-09 report.

It provides no arbitrary command/flag input, persistent queue, detached process recovery, SLURM,
remote execution, actor training, dependency installation, source mutation, or general SUMO
launcher. The ordinary generic and SUMO adapters still report direct launch as unsupported. The
VEC workbench reports evaluator execution as conditional until the exact request, repositories,
inputs, actor, and local JAX runtime pass VEC-07 preflight.

## CLI

Inspect the contract and source readiness:

```bash
uv run traffictwin integration vec contract --format json
uv run traffictwin integration vec snapshot \
  --vec-repo ../external/vec_env \
  --tos-data-repo ../external/tos-data
```

Validate a complete request JSON without creating outputs:

```bash
uv run traffictwin integration vec validate \
  --kind run \
  --request run-request.json \
  --input-root ../external/tos-data \
  --vec-repo ../external/vec_env \
  --tos-data-repo ../external/tos-data
```

Execute only after the same request-specific preflight passes:

```bash
uv run traffictwin integration vec run \
  --request run-request.json \
  --input-root ../external/tos-data \
  --vec-repo ../external/vec_env \
  --tos-data-repo ../external/tos-data \
  --output ./vec-output/new-run
```

`execute-and-import` runs the complete one-click preset workflow (preflight, execution,
revalidation, immutability verification, idempotent registry import) and `import-result`
re-validates and re-imports one published preset result; both are closed to the two
repository-defined presets and documented in the
[one-click guide](vec_one_click_execution.md).

`preprocess` has the parallel VEC-06 shape with `--request`, `--input-root`, `--vec-repo`, and a
new `--output` directory. Both commands print validating, foreground-running, and terminal states.
They cannot attach to a different process or recover a detached job.

Inspect, compare, and export portable evidence:

```bash
uv run traffictwin integration vec inspect \
  docs/reference/generated/vec_scientific_admission_report.json

uv run traffictwin integration vec compare baseline.json variation.json \
  --output comparison.json

uv run traffictwin integration vec export admission.json \
  --format csv --output metrics.csv
```

Comparison includes only available scalar metrics with matching keys, units, and scopes. Grouped,
missing, unavailable, or incompatible values are listed separately. Differences are descriptive
variation-minus-baseline values and are never causal or diagnostic.

## UI

Open **VEC Reproduction Workbench** in the Workflow section. Section 2 provides the
one-click controlled execution over closed presets (ADR-052); the remaining stages are:

1. inspect both pinned repositories and their operation availability;
2. select a preprocess or run request JSON, input root, and new output directory;
3. validate the request, after which the matching execution button is enabled only for an
   accepted preflight; and
4. inspect receipts/reports or compare/export accepted VEC-09 evidence.

The UI does not construct request values or commands. Long operations run in the Streamlit process
and display a foreground status. Restarting the app does not preserve a job queue.

## Acceptance evidence

- Library: `src/traffictwin/integration/vec_interface/`
- CLI: `traffictwin integration vec ...`
- UI: `src/traffictwin/ui/pages/vec_workbench.py`
- Contract: `docs/reference/generated/vec_interface_contract.json`
- Verification: `docs/reference/generated/vec_interface_verification.json`
- Verifier: `scripts/verify_vec_interface.py`
- Tests: `tests/unit/test_vec_interface.py` and `tests/integration/test_vec_interface.py`

The verification exercises real pinned repository state and the accepted VEC-09 report, confirms
16 compatible scalar metrics in an exact self-comparison, validates all export formats, publishes
no private paths, and proves both external repository states remain unchanged.

VEC-10 does not itself satisfy VEC-11 publication permission packaging or VEC-12 end-to-end
research artifact reconciliation; both are separately accepted downstream capabilities.

# Controlled One-Click SUMO Execution and Automatic Import

Status: implemented and real-runtime accepted (`sumo-execute-and-import-1.0`, ADR-053) against
the official Eclipse SUMO 1.27.1 arm64 macOS package. The capability
`controlled_sumo_execution` remains conditional on request-specific preflight; generic
`direct_launch` remains false everywhere.

One explicit action preflights the closed synthetic preset, runs SUMO in the foreground with a
fixed argv, verifies the pinned inputs stayed byte-identical, atomically publishes a read-only
result directory, validates it through the existing import-only SUMO adapter, and imports it
idempotently into the configured registry. This is not a general-purpose SUMO launcher.

Library: `traffictwin.integration.sumo_execution`
Contract: `docs/reference/generated/sumo_execution_contract.json`

## The closed preset

`synthetic_square_smoke` is the only executable scenario: an original TrafficTwin-authored
synthetic network (one edge tracing a 100 m square perimeter between two dead-end junctions),
six deterministic vehicles, seed 42, 120 simulated seconds. Its three input files live in the
repository with pinned SHA-256 hashes; the configuration may reference only those admitted
files. It is explicitly **synthetic**: not Manchester traffic, not Randy/VEC evidence, not
real-world validation, and not derived from Eclipse SUMO scenario files. Requests bind the
preset, the resolved executable identity and exact version, seed, begin/end, timeout, and the
new output and registry destinations; nothing else is representable.

## Runtime requirement

Preflight discovers only the PATH-resolved `sumo` entry, resolves a normal package-manager symlink
to its regular target, and requires a reported `1.27.x` version (the adapter's validated
contract). Its exact name, version, and streaming SHA-256 are rechecked immediately before
execution. Without a supported runtime the UI and CLI show the exact reason and refuse to execute
— no fake process is substituted. To enable real execution, install Eclipse SUMO yourself, for
example:

```bash
brew install sumo
```

TrafficTwin never installs software.

## UI: click-by-click

1. Open **SUMO Output Import**.
2. In **Controlled one-click SUMO run**, review the preset's factual workload (window,
   vehicles, seed) and the discovered SUMO readiness.
3. Enter a **new** output directory; the registry path is the page's configured active registry.
4. Tick the explicit synthetic-run confirmation.
5. Click **Validate, Run and Import** — the single final action, disabled while the runtime is
   unsupported or any input is missing.
6. Inspect the foreground status, stage table, receipt/output/import fingerprints, output
   inventory, and limitations. **Imported controlled SUMO execution records** lists registered
   runs from the registry and therefore survives Streamlit restarts; the ordinary import view
   and Run Overview analyse the imported run like any other accepted SUMO result.

## CLI

```bash
uv run traffictwin integration sumo execute-and-import \
  --preset synthetic_square_smoke \
  --output ./local-evidence/sumo-smoke \
  --registry .demo/registry.sqlite
```

The command prints preset workload, runtime readiness, and the preflight/execution/validation/
import stages, and returns non-zero for every non-imported terminal state. A published result
can be revalidated and re-imported idempotently:

```bash
uv run traffictwin integration sumo import-result \
  --result-dir ./local-evidence/sumo-smoke \
  --registry .demo/registry.sqlite
```

## What automatic import means

On success the runner writes the adapter's exact `sumo-source.yaml` (preset identity, discovered
SUMO version, synthetic status, unspecified-repository-licence restriction with
`redistribution_allowed: false`, and raw output checksums) plus a typed execution receipt. The
directory is then validated by the **existing** SUMO adapter and imported by the **existing**
importer — no second parser or metric engine. Import identity is
`sumo-exec-<output fingerprint[:16]>`; re-import is idempotent by stable fingerprint, conflicts
fail visibly, and the typed `SumoExecutionImportRecord` is persisted beside the receipt.
`summary.running` stays network occupancy; no FCD, task, RSU, offloading, energy, or VEC
quantity is invented.

## Safety boundary

- Fixed allowlisted argv, `shell=False`, controlled environment, private staged workspace,
  bounded logs, timeout, and process-group cancellation.
- Inputs are staged copies; the originals are re-hashed afterwards and any drift aborts
  publication.
- Outputs are checked for presence, bounds, safe XML, and expected roots before the adapter's
  full validation; publication is atomic, read-only, and never overwrites.
- Failed, timed-out, cancelled, rejected, malformed, partial, or input-mutating executions
  import nothing.
- No arbitrary executables, shell text, `sumo-gui`, scripts, flags, environment variables,
  URLs, dynamic modules, remote execution, queues, SLURM, installation, Git operations, live
  feeds, or Randy/VEC controls.

## Related documents

- [Eclipse SUMO output adapter](sumo_output_adapter.md)
- [One-click VEC execution](vec_one_click_execution.md) (the sibling pattern)
- [ADR-053](../decisions/ADR-053-controlled-one-click-sumo-execution.md)

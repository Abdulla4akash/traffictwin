# TrafficTwin Doctor

`traffictwin doctor` is a read-only operational diagnosis for the TrafficTwin runtime and any
workspace, registry, or canonical cache targets you explicitly select. It reports missing optional
components and unsupported capabilities without pretending that they are core installation
failures.

## Quick Start

Inspect the active runtime:

```bash
traffictwin doctor
```

Inspect a standalone workspace and its declared registry:

```bash
traffictwin doctor --workspace .traffictwin-demo
```

Inspect a registry directly:

```bash
traffictwin doctor --registry .traffictwin-demo/registry.sqlite
```

Inspect the cache identity for one raw bundle. Both options are required together:

```bash
traffictwin doctor \
  --bundle tests/fixtures/bundles/baseline_valid \
  --cache-root .traffictwin-cache
```

Use JSON for automation:

```bash
traffictwin doctor --workspace .traffictwin-demo --format json
```

Inspect the versioned contract without running a diagnosis:

```bash
traffictwin doctor --contract --format json
```

## Status Semantics

| Check state | Meaning |
|---|---|
| `pass` | The observed evidence satisfies that exact check. |
| `warning` | Inspection succeeded, but the selected workflow needs operator attention. |
| `blocked` | The selected workflow cannot safely proceed under the observed state. |
| `unavailable` | Optional component/evidence was absent; it is not treated as zero or pass. |

The report's overall state uses only checks required by the invocation:

- `healthy`: all requested required checks passed;
- `degraded`: no requested required check is blocked, but at least one has a warning;
- `blocked`: a requested required check is blocked or unavailable.

The CLI exits `0` for `healthy` and `degraded`, and `1` for `blocked`. A missing optional command,
unknown TOS permission, or deliberately unsupported launcher remains visible but does not break the
guaranteed generic import-first workflow.

## What It Checks

### Runtime and dependencies

- Python is at least 3.11;
- TrafficTwin and every core distribution are installed;
- optional `numpy`, `playwright`, and `pypdf` distributions are visible;
- optional `sumo`, `tectonic`, and Graphviz `dot` commands can be located.

Command discovery uses path lookup only. Doctor never executes those commands. Finding `sumo`
does not enable or imply a TrafficTwin SUMO launcher.

### Optional integrations and capabilities

The report keeps three adapter manifests separate:

- `generic_csv`: guaranteed import-first TrafficTwin functionality;
- `sumo_results_v1`: evidenced import-only SUMO results support;
- `tos_data_read_only`: source-specific TOS analysis with unknown/unsupported semantics retained.

Each summary lists every supported, unsupported, and unknown capability. Direct and asynchronous
launch remain blocked. Unknown TOS fixture/publication permission remains unavailable rather than
granted.

### Workspace

With `--workspace`, doctor checks the bounded standalone marker, schema, required directories,
declared scenario paths, and registry path. Declared paths must remain under the workspace. It does
not regenerate the demo, create directories, validate every bundle, or render reports.

### Registry

Registry diagnosis uses the OPS-01 immutable read-only SQLite inspection path. It reports current,
upgradeable, legacy, empty, future, corrupt, and integrity-failure states without applying a
migration. When `--workspace` and `--registry` identify the same file, the file is inspected once
and both sources are recorded.

### Permissions

Doctor reports current read/traverse and write access for selected local targets. It never tests
write access by creating or editing a file. `os.access` is a point-in-time advisory check: ACLs,
sandbox policy, ownership changes, locks, disk space, and later access can still differ.

### Canonical cache

`--bundle` plus `--cache-root` re-fingerprints the raw bundle and uses the OPS-02 read-only verifier.
The report carries the exact cache state and key. A missing cache root remains absent; a stale,
incompatible, or corrupt entry remains untouched for explicit operator investigation.

## Reading Common Results

- `dependency.optional.numpy = unavailable`: ordinary TrafficTwin remains usable; only optional
  TOS NPZ workflows are unavailable.
- `registry...integrity = blocked`: work on a copy and follow the migration/recovery guide. Doctor
  intentionally does not repair it.
- `cache.integrity = warning` with `miss`: run normal cold validation or `bundle cache-validate` if
  you intentionally want to publish a cache entry.
- `cache.integrity = warning` with `stale`, `incompatible`, or `corrupt`: inspect the exact reported
  entry. Doctor never deletes or overwrites it.
- `permission...write = warning`: read-only inspection can work, but workflows that intentionally
  write to that target may fail.
- `capability.direct-launch = blocked`: expected import-first product boundary, not evidence of a
  damaged installation.

## Non-Mutation Guarantee and Limits

OPS-03 v1 has no repair mode. It does not install dependencies, initialise or migrate registries,
create workspaces, warm/repair caches, change permissions, launch simulators, run compilers,
execute browsers, or make network calls.

Operational reports include local versions and selected paths. Review them before public sharing.
They do not establish scientific validity, external integration correctness, data permission, or
future access.

The machine-readable contract is generated at
[doctor contract](reference/generated/doctor_contract.json), and the governing decision is
[ADR-046](decisions/ADR-046-read-only-environment-doctor.md).

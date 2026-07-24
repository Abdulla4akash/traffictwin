# v0.7 Workspace Isolation And v0.6 Compatibility Copies

This document describes the implemented **foundation** for `REL-01` from the
[TrafficTwin v0.7 design](traffictwin-design-v0_7.md#24-compatibility-migration-and-rollback).
The capability remains `planned`: this slice proves workspace separation and a non-active,
byte-exact registry copy, not a completed cross-release migration or v0.7 release.

## What the foundation provides

- a new-only workspace marked as `traffictwin_v0_7`;
- distinct `workspace-v0.7` and `traffictwin-cache-v0.7` namespaces;
- separate active registry, Manchester, run, export, cache, compatibility, and quarantine paths;
- read-only immutable inspection of one closed registry at the frozen v0.6 schema version;
- a preview containing source schema/hash/size, target paths, free-space requirements, actions,
  blockers, and the fact that no backup is needed for a new-only copy;
- atomic publication of a byte-exact copy under `compatibility/v0.6/<hash-prefix>/`;
- a receipt reconciling the source-before, source-after, copied-registry, and active-registry
  hashes; and
- fail-closed refusal of symlinks, SQLite WAL/journal sidecars, incompatible schema versions,
  existing destinations, path escapes, insufficient space, or verification failure.

## What it deliberately does not provide

- no mutation of a v0.6 registry or workspace;
- no in-place schema upgrade or downgrade;
- no automatic activation of a copied registry;
- no copying of bundles, raw inputs, accepted outputs, exports, Manchester data, or secrets;
- no claim that a registry alone proves which package version produced it;
- no reinterpretation or scientific revalidation of stored JSON payloads; and
- no claim that `REL-01` or the v0.7 release is accepted.

## Library usage

Create and inspect an isolated candidate workspace:

```python
from traffictwin.release import initialise_v07_workspace, inspect_v07_workspace

created = initialise_v07_workspace("workspace-v0.7")
inspection = inspect_v07_workspace(created.path)
assert inspection.manifest.workspace_namespace == "workspace-v0.7"
```

Preview a non-mutating compatibility copy:

```python
from traffictwin.release import preview_v06_registry_copy

preview = preview_v06_registry_copy(
    "/path/to/closed-v0.6-registry.sqlite",
    "workspace-v0.7",
)
assert preview.operation == "copy_only_not_migration"
assert preview.automatic_activation is False
```

Only after reviewing the preview, publish the copy:

```python
from traffictwin.release import copy_v06_registry

result = copy_v06_registry(
    "/path/to/closed-v0.6-registry.sqlite",
    "workspace-v0.7",
)
print(result.registry_path)
print(result.receipt_path)
```

The source SQLite application must be stopped or otherwise closed and checkpointed first. The
operation refuses `-wal`, `-shm`, and `-journal` sidecars rather than guessing whether copying the
main file would capture a consistent database.

## CLI usage

The same foundation is available through bounded CLI commands; each prints
`capability_status: planned` because no command accepts `REL-01`:

```bash
traffictwin release v07-workspace-init workspace-v0.7
traffictwin release v07-workspace-inspect workspace-v0.7 [--format json]
traffictwin release v06-copy-preview /path/to/closed-v0.6-registry.sqlite workspace-v0.7
traffictwin release v06-copy /path/to/closed-v0.6-registry.sqlite workspace-v0.7
traffictwin release v06-attest /path/to/registry.sqlite --operator "Name" --output attestation.json
traffictwin release v06-migrate-preview /path/to/registry.sqlite workspace-v0.7 --attestation attestation.json
traffictwin release v06-migrate /path/to/registry.sqlite workspace-v0.7 --attestation attestation.json
traffictwin release v06-rollback workspace-v0.7 --receipt workspace-v0.7/compatibility/backups/mig-*/migration-receipt.json
```

`v06-attest` records the ADR-058 operator clean-checkout statement against exact registry
bytes. `v06-migrate` activates an attested source only after publishing a durable byte-exact
backup of the previous active registry together with its reconciling receipt in one atomic
rename, before the active registry is swapped; the frozen v0.6 schema equals the current v0.7
schema, so no schema transformation occurs and any other source version (or a source living
inside the workspace) is refused. The migration identity is derived only from the source
registry, so a retry after any interruption resumes deterministically — an already-activated
registry is acknowledged idempotently and a published-but-not-activated backup completes its
swap — and the previous registry is never orphaned. `v06-rollback` restores the backup
idempotently while the active registry matches either the activated or the pre-migration state.
Activation transfers operational bytes only: scientific admission stays unavailable and
`REL-01` remains planned.

`v07-workspace-init` is new-only, `v07-workspace-inspect` and `v06-copy-preview` are read-only,
and `v06-copy` publishes only the non-active byte-exact snapshot described above. See
[workspace setup and side-by-side operation](workspace_setup.md) for the surrounding workflow.

## Evidence and remaining acceptance work

The machine-readable contract is frozen by
[`v07_workspace_contract.json`](reference/generated/v07_workspace_contract.json). Focused
tests cover new-only creation, exact layout and namespace validation, tamper and symlink refusal,
read-only preview, byte identity, receipt reconciliation, repeat-copy refusal, sidecar refusal,
source-inside-target refusal, failure cleanup, and timezone-safe timestamps.

A scripted side-by-side check (`scripts/side_by_side_check.py`) now creates a clean detached
checkout of the immutable `v0.6.0` tag, installs it from its own lockfile, initialises and
validates its synthetic demo workspace with its own CLI, and serves it beside the current v0.7
checkout on separate ports and workspaces. The 24 July 2026 run
([evidence](integration/evidence/side_by_side_check.json)) confirmed both servers respond
concurrently, every workspace/registry path is distinct, and neither side changed the other's
registry bytes; the temporary checkout is removed afterwards and the tag is never modified.

`REL-01` remains planned until later work adds and accepts
package/release version alignment, cross-schema migration if a schema ever diverges, and final
documentation and capability reconciliation. The attested same-schema activation slice above
implements preview, backup, interruption quarantine, activation, and rollback for
ADR-058-attested sources only; an unattested registry still cannot claim v0.6.0 provenance, and
the scripted coexistence run is automated evidence rather than formal Gate-F release
acceptance.

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

## Evidence and remaining acceptance work

The machine-readable contract is frozen by
[`v07_workspace_contract.json`](reference/generated/v07_workspace_contract.json). Focused
tests cover new-only creation, exact layout and namespace validation, tamper and symlink refusal,
read-only preview, byte identity, receipt reconciliation, repeat-copy refusal, sidecar refusal,
source-inside-target refusal, failure cleanup, and timezone-safe timestamps.

`REL-01` remains planned until later work adds and accepts complete workspace preview/migration,
backup, interruption quarantine, activation, rollback, downgrade refusal, CLI integration,
side-by-side clean-checkout tests, package/release version alignment, and final documentation and
capability reconciliation.

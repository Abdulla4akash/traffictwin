# ADR-046: Read-only Environment Doctor

- Status: accepted
- Date: 2026-07-21
- Capability: `OPS-03`

## Context

TrafficTwin now has multiple local interfaces, typed source adapters, optional development tools,
versioned registries, standalone workspaces, and a content-addressed canonical cache. Operators
need one command that distinguishes a broken required installation from a missing optional tool,
an unsupported capability, an unhealthy selected artifact, or an unknown permission.

The diagnostic command must not become an implicit installer or repair tool. In particular,
opening a historical registry through the normal `Registry.inspect()` path could migrate it, and a
cache validation command could publish derived Parquet. Those mutations are inappropriate for a
default health check.

## Decision

Implement `traffictwin.doctor` and the root `traffictwin doctor` command under these rules:

1. Emit strict typed checks with stable IDs, one of `pass`, `warning`, `blocked`, or `unavailable`,
   a required/optional flag, observed evidence, and an optional remediation. Unavailable never
   becomes zero or pass.
2. Derive `healthy`, `degraded`, or `blocked` only from checks required by the requested invocation.
   Expected unsupported capabilities and absent optional tools remain visible without making the
   guaranteed generic import-first path unhealthy.
3. Report Python, TrafficTwin, all required distributions, optional `numpy`, `playwright`, and
   `pypdf` distributions, and optional `sumo`, `tectonic`, and `dot` commands. Read package metadata
   and command locations only; execute no external command and make no network call.
4. Publish complete capability summaries from the existing `generic_csv`, `sumo_results_v1`, and
   `tos_data_read_only` manifests. Keep direct/asynchronous launch and incomplete TOS canonical
   conversion visibly blocked. A discovered `sumo` executable never enables launch.
5. When `--workspace` is supplied, parse only a non-symlinked `workspace.yaml` of at most 1,000,000
   bytes, require the known marker/schema, inspect the required directory layout, and ensure every
   declared bundle/registry path remains within the workspace. Do not validate every bundle or
   generate missing workspace content.
6. Inspect explicit and workspace registries through OPS-01's immutable read-only SQLite URI. Do
   not call `Registry.initialize()`, apply a migration, create a journal, or repair corruption.
   Deduplicate the same registry selected through both sources.
7. Inspect a `--bundle` and `--cache-root` pair through OPS-02's read-only raw re-fingerprint and
   cache verifier. Do not create a missing cache root or publish, delete, repair, or overwrite an
   entry. A miss or rejected stale/incompatible/corrupt entry is a warning because raw validation
   remains a separate possible workflow.
8. Probe current read/traverse and write access with `os.access`. Write access is reported but
   never exercised. These observations are advisory and do not replace ACL, ownership, or future
   access checks.
9. Keep TOS sanitised-fixture and aggregate-publication permissions `unavailable` unless evidence
   is supplied through the separate permission-gated workflow. Doctor does not persist or infer
   permission.
10. Exit zero for `healthy` and `degraded`; exit one for `blocked`. This lets optional absence and a
    cache miss remain inspectable while making corrupt or unreadable requested targets fail in CI.

The report records `read_only=true` and `mutations_performed=false`. OPS-03 v1 has no repair mode.

## Consequences

- A default invocation can be healthy while honestly listing absent optional commands, unknown
  permissions, and unsupported launch capabilities.
- A supplied corrupt registry, unsafe workspace declaration, unreadable required path, invalid
  cache target pair, or unusable requested bundle blocks the invocation.
- A current registry, healthy standalone workspace, and verified cache hit pass without byte or
  modification-time changes.
- Environment reports contain local versions and selected local paths. They are operational
  artifacts, not scientific evidence, and should be reviewed before public sharing.
- The command does not prove simulator correctness, scientific validity, external-source
  permission, future filesystem access, or every platform-specific rendering path.

## Acceptance Evidence

Unit, integration, and golden tests cover:

- a healthy default runtime and complete public contract;
- a healthy workspace/current registry with duplicate-target reconciliation;
- a missing optional dependency that leaves the core installation healthy;
- a corrupt registry copy classified as blocked through immutable inspection;
- a content-addressed stale cache classified as degraded;
- a cache miss that does not create the requested root;
- a permission-limited registry that is not opened;
- unsafe workspace declarations and incomplete cache options;
- hashes and modification times proving that inspected fixtures remain unchanged;
- root CLI JSON/text output, exit behavior, and invalid-format rejection before inspection.

## Rejected Alternatives

- Automatically install missing packages: rejected because doctor is diagnostic and offline.
- Run `sumo --version`, compilers, browsers, or Graphviz: rejected because discovery does not
  require executing external processes.
- Call normal registry inspection: rejected because it deliberately applies pending migrations.
- Warm or repair the cache: rejected because that would hide the observed state and mutate derived
  storage.
- Treat every unsupported adapter feature as an unhealthy installation: rejected because
  unsupported source semantics are deliberate capability truth, not core failure.
- Accept a workspace registry path outside the workspace: rejected as an unsafe trust-boundary
  expansion.
- Add `--fix`: rejected for v1; any future mutation mode needs a separate explicit contract.

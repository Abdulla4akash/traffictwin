# Workspace Setup And Side-By-Side Operation

TrafficTwin uses more than one kind of local workspace. They have different markers, different
truth labels, and different safety rules. This guide explains how to tell them apart, how to run
two applications side by side without sharing state, and which diagnostics inspect each kind
without changing it.

For the current start/reuse/connection sequence, including the rule that an existing real
workspace path must be supplied rather than discovered, use the
[v0.7 local usage runbook](v07_usage.md).

## Workspace kinds

| Kind | Marker | Contents | Truth label |
|---|---|---|---|
| Standalone demo workspace (conventionally `.demo/`) | `workspace.yaml` | Generated synthetic bundles, registry, reports | Synthetic software fixtures only: not Manchester, not Randy/VEC, not observed evidence |
| v0.6 research workspace | `workspace.yaml` plus your own registry/bundles | Imported accepted evidence produced with the immutable `v0.6.0` release | Evidence-bounded v0.6 truth; treat as valuable and read-only from v0.7 |
| Isolated v0.7 workspace (conventionally `workspace-v0.7/`) | `workspace-v0.7.json` strict manifest | Separate registry, Manchester source areas, caches, compatibility copies | v0.7 foundation; every `MAN-*`, `UX-*`, `REL-01` capability remains planned |

Key rules:

- The synthetic demo workspace never contains Manchester evidence; its data is deterministic
  generated fixtures and every page labels it synthetic.
- A valuable v0.6 workspace is never migrated, upgraded, or written in place. v0.7 may only read
  it, and may publish a byte-exact, non-active copy under its own `compatibility/v0.6/` area.
- The v0.7 workspace is created new-only under a distinct namespace (`workspace-v0.7`,
  `traffictwin-cache-v0.7`) so it can never collide with a v0.6 registry or cache.
- Manchester acquisition, scenes, and snapshots require the isolated v0.7 workspace; they are
  refused in unmarked directories.

## Creating each workspace

Synthetic demo workspace:

```bash
traffictwin demo initialise .demo
traffictwin demo status .demo
```

Isolated v0.7 workspace (new-only; the target must not exist):

```bash
traffictwin release v07-durable-preview /owner-selected/private-parent/workspace-v0.7
traffictwin release v07-durable-create /owner-selected/private-parent/workspace-v0.7 \
  --expected-plan "replace-with-confirmed-plan-fingerprint"
traffictwin release v07-workspace-inspect /owner-selected/private-parent/workspace-v0.7
```

The durable workflow requires a current-user-owned parent with mode `0700`, previews without
mutation, requires exact digest confirmation, creates an empty-registry backup with an isolated
restore drill, and publishes atomically. See
[durable v0.7 workspace creation](v07_durable_workspace.md). It does not populate Manchester
sources or create mapping, calibration, baseline or comparison evidence. Do not run an
initialiser merely to make Manchester layers appear. To connect existing evidence, obtain the
exact existing path from the owner and run only `v07-workspace-inspect` before launch.

## Side-by-side operation

Run the synthetic/v0.6 demonstration and the v0.7 Manchester operations application as two
separate processes with different ports and different workspace environment values. Neither
process reads or writes the other's workspace.

Terminal 1 — synthetic demonstration on port 8601:

```bash
traffictwin demo launch .demo --port 8601
```

Terminal 2 — v0.7 Manchester operations on port 8602 against the isolated workspace:

```bash
TRAFFICTWIN_WORKSPACE_PATH="$PWD/workspace-v0.7" \
TRAFFICTWIN_REGISTRY_PATH="$PWD/workspace-v0.7/registry/traffictwin.sqlite" \
uv run streamlit run src/traffictwin/ui/app.py --server.port 8602
```

Notes:

- `traffictwin demo launch` initialises the demo workspace if needed and sets the workspace
  environment variables for its own process only.
- The v0.7 process must point at a strictly marked workspace; Manchester pages fail closed in an
  unmarked directory. New durable workspaces should use the preview-confirmed workflow above.
- For an existing real workspace, use only an exact owner-supplied path and validate it read-only.
  Do not scan ignored/private directories to infer one.
- `demo launch` is for `workspace.yaml` standalone demos only; launch a v0.7 workspace directly
  with both environment variables shown above.
- Port values are local operational choices; nothing in either process claims public hosting.
- To demonstrate the immutable `v0.6.0` release itself, use a separate clean checkout of the
  `v0.6.0` tag with its own workspace; do not point it at the v0.7 workspace.

## Diagnostics (read-only)

- `traffictwin demo status <path>` — validates the standalone demo marker and inventory.
- `traffictwin doctor --workspace <path>` — bounded read-only structural diagnosis of a
  standalone (`workspace.yaml`) workspace, its registry, and environment; it never initialises,
  migrates, or repairs anything.
- `traffictwin release v07-workspace-inspect <path> [--format json]` — verifies the strict v0.7
  manifest, required layout, and active-registry schema without changing any file.
- `traffictwin release v06-copy-preview <registry> <workspace>` — read-only preview of a
  byte-exact, non-active v0.6 registry copy, including free-space and blocker reporting.

## Compatibility copies (v0.6 → v0.7, read-only source)

```bash
traffictwin release v06-copy-preview /path/to/closed-v0.6-registry.sqlite workspace-v0.7
traffictwin release v06-copy /path/to/closed-v0.6-registry.sqlite workspace-v0.7
```

The source application must be stopped and the SQLite database checkpointed; WAL/journal
sidecars are refused rather than guessed about. The copy is published under
`workspace-v0.7/compatibility/v0.6/<hash-prefix>/` with a reconciling receipt and never becomes
the active v0.7 registry. Attested same-schema **activation** (with durable backup, crash-safe
resume, and receipt-gated rollback) is implemented for ADR-058-attested sources via
`release v06-attest`, `release v06-migrate`, and `release v06-rollback`; cross-release schema
migration remains separate unimplemented `REL-01` work. See
[v0.7 workspace isolation and v0.6 compatibility copies](v07_release_compatibility.md) and the
[operator v0.6 attestation procedure](integration/v06_attestation_procedure.md).

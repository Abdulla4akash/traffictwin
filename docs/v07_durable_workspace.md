# Durable v0.7 Workspace Creation

TrafficTwin can create a new, owner-selected v0.7 workspace with stronger local-operational
assurances than the original structural initialiser. The workflow is preview-confirmed, atomic,
owner-only, and creates a byte-exact empty-registry backup that is restored and inspected in an
isolated drill before publication.

This is the bounded `NEXT-01` / `REL-01` foundation. It does not discover an existing workspace,
fetch a source, import evidence, activate a historical store, or change the formal `planned`
capability status.

## Prepare a private parent

Choose a durable parent outside the repository. The parent must already exist, be owned by the
current user, have mode `0700`, and must not be a symlink. Keep the exact path local rather than
putting it in a committed script or report.

```bash
TRAFFICTWIN_DURABLE_PARENT=/owner-selected/private-parent
mkdir -p "$TRAFFICTWIN_DURABLE_PARENT"
chmod 700 "$TRAFFICTWIN_DURABLE_PARENT"
TRAFFICTWIN_DURABLE_WORKSPACE="$TRAFFICTWIN_DURABLE_PARENT/workspace-v0.7"
```

The target itself must not exist. The workflow refuses repository descendants, unsafe parents,
symlinks, target collisions, insufficient free space, and unresolved staging remnants.

## Preview without mutation

```bash
uv run traffictwin release v07-durable-preview \
  "$TRAFFICTWIN_DURABLE_WORKSPACE" --format json
```

The preview does not create the target. Its output is path-free and contains an opaque workspace
handle, required v0.7 layout, parent/target safety facts, available space, blockers, and a
`plan_fingerprint`. Review that output and continue only when `activatable` is `true`.

The confirmation digest deliberately excludes changing free-space telemetry, while still binding
the target identity, workspace contract, safety state, and planned actions.

## Create after exact confirmation

Copy the exact `plan_fingerprint` from the preview into a local task-specific variable:

```bash
TRAFFICTWIN_DURABLE_PLAN="replace-with-the-64-character-plan-fingerprint"
uv run traffictwin release v07-durable-create \
  "$TRAFFICTWIN_DURABLE_WORKSPACE" \
  --expected-plan "$TRAFFICTWIN_DURABLE_PLAN" \
  --format json
```

Creation uses private sibling staging and an atomic rename. Before publication it:

1. creates the existing strict `workspace-v0.7.json` layout and empty active registry;
2. applies owner-only `0700` directory and `0600` file permissions;
3. copies the empty active registry to
   `registry/baseline-backup/traffictwin.sqlite`;
4. restores that backup into an isolated temporary location and verifies its schema and digest;
5. reopens the staged workspace through the normal v0.7 inspector; and
6. writes a path-free `registry/durable-workspace-receipt.json` before atomic publication.

The terminal receipt reports the opaque handle and digests, confirms the restore and permission
checks, and explicitly records that no accepted source data, acquisition, or historical-store
activation occurred. It does not persist the private absolute path.

## Retry and failure behaviour

Repeating `v07-durable-create` immediately with the same target and plan fingerprint performs an
exact reconciliation. It succeeds only while the manifest, still-empty active registry, baseline
backup, permissions, receipt, and workspace identity remain exactly as created, and returns
`exact_retry: true`. After the workspace begins normal use, inspect it with
`v07-workspace-inspect`; the creation retry is not a general health check.

A pre-publication failure removes only the workflow-owned staging directory. A failure injected
after the atomic publication can be reconciled by the exact retry. The command never deletes or
repairs an existing unmanaged target. An orphan staging handle is reported as a blocker for manual
owner investigation rather than silently removed.

Common refusal codes include:

| Code | Meaning |
|---|---|
| `TARGET_EXISTS` | Preview target already exists; use the inspector for a known workspace. |
| `REPOSITORY_TARGET_FORBIDDEN` | Durable local state was placed inside the repository. |
| `PARENT_PERMISSIONS_UNSAFE` | Parent is not current-user-owned mode `0700`. |
| `PLAN_MISMATCH` | The exact current preview was not confirmed. |
| `PLAN_BLOCKED` | Free-space or orphan-staging blockers remain. |
| `EXISTING_TARGET_UNMANAGED` | Create retry found something other than its exact managed output. |
| `REGISTRY_MISMATCH` | The active registry changed, so creation retry is no longer appropriate. |

## Continue safely

Inspect the new container read-only before connecting any application:

```bash
uv run traffictwin release v07-workspace-inspect \
  "$TRAFFICTWIN_DURABLE_WORKSPACE" --format json
```

A valid empty container is not Manchester evidence. Source configuration and the
[foreground port-8502 run profile](v07_real_workspace_run.md) are separate operations;
credentials remain process-only, and source access retains its own authority, licence, privacy,
and retention requirements.

See also [v0.7 local usage](v07_usage.md),
[workspace setup](workspace_setup.md), and
[v0.7 workspace compatibility](v07_release_compatibility.md).

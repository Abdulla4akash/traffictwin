# Local Real-Workspace Run Profile

TrafficTwin provides a fixed foreground launch profile for one exact durable v0.7 workspace. It
binds Streamlit only to `127.0.0.1:8502`, leaving the conventional synthetic demo on port 8501,
and reuses the existing process-lifetime BODS and National Highways workers.

This is the bounded `NEXT-02` implementation. It is local operation, not public hosting, a daemon,
a provider SLA, city-road telemetry, capability acceptance, or a v0.7 release.

## Configure the current shell

Supply the exact durable workspace path locally. Do not search for a workspace or commit its path.
Credentials and the BODS request scope remain process environment values:

```bash
TRAFFICTWIN_REAL_WORKSPACE=/exact/owner-supplied/durable-workspace
export BODS_API_KEY
export TRAFFICTWIN_BODS_BOUNDING_BOX
export NATIONAL_HIGHWAYS_API_KEY
```

The BODS box must contain four ordered comma-separated coordinates. BODS defaults to a 60-second
interval and National Highways to 300 seconds. Their existing bounded override variables remain:

```bash
export TRAFFICTWIN_BODS_AUTO_REFRESH_SECONDS=60
export TRAFFICTWIN_NATIONAL_HIGHWAYS_AUTO_REFRESH_SECONDS=300
```

Use `off` to disable one worker. A missing credential produces `not_configured`; it is not
reported as a provider outage. The local UI may still launch with a disabled or unconfigured
worker, while an invalid interval or box refuses the run plan.

## Run the mutation-free preflight

```bash
uv run traffictwin release v07-real-preflight \
  "$TRAFFICTWIN_REAL_WORKSPACE" --format json
```

The preflight makes no provider request and writes no workspace or control file. It verifies:

- the durable-workspace receipt, opaque identity, manifest and active-registry contract;
- loopback-only port 8502 availability and separation from the expected demo port 8501;
- credential presence only, never credential values;
- exact 60/300-second defaults or valid source-specific interval overrides;
- a valid fingerprinted BODS request box without returning its coordinates;
- existing hot-control canonicality and the latest terminal state fingerprint;
- non-mutating availability of existing source lock files;
- canonicality and private permissions of any cached BODS/National Highways scenes; and
- exact source acquisition, scene, control and freshness contract versions.

Its JSON is path-free and secret-free. `policy_blockers` preserve the separate BODS retention,
public-row and complete-Bee decisions and the National Highways strategic-road-only, SLA and
public-hosting limits. These truth labels do not pretend the configured source is unavailable for
authorised private local use.

The run is blocked when port 8502 is occupied, the workspace identity changed, a control/scene/
lock path is unsafe, an existing source lock is busy, or configured scope/interval values are
invalid.

## Confirm and launch

Copy the exact `plan_fingerprint` into a task-specific local variable. A dry run rechecks the
entire current plan but starts no process:

```bash
TRAFFICTWIN_REAL_RUN_PLAN="replace-with-the-64-character-plan-fingerprint"
uv run traffictwin release v07-real-launch \
  "$TRAFFICTWIN_REAL_WORKSPACE" \
  --expected-plan "$TRAFFICTWIN_REAL_RUN_PLAN" \
  --dry-run --format json
```

Launch the confirmed profile by omitting `--dry-run`:

```bash
uv run traffictwin release v07-real-launch \
  "$TRAFFICTWIN_REAL_WORKSPACE" \
  --expected-plan "$TRAFFICTWIN_REAL_RUN_PLAN"
```

The launcher overwrites only the child process's `TRAFFICTWIN_WORKSPACE_PATH` and
`TRAFFICTWIN_REGISTRY_PATH` with the exact verified workspace values. It invokes a fixed argv with
no shell, binds to `127.0.0.1:8502`, disables Streamlit usage-stat collection, and stays in the
foreground. Open <http://localhost:8502>. Stop this exact process with `Ctrl-C`; its process-local
worker threads end with Streamlit. The terminal launch receipt is printed after the foreground
process exits.

The first configured Streamlit session starts each enabled worker independently. BODS uses its
one-minute default and explicit box; National Highways uses its five-minute default and fixed
three-product acquisition. Both retain their existing locks, rate guards, private raw storage,
aggregate hot control histories, manual fallbacks and stale-on-failure behaviour. A failure in one
worker does not stop or relabel the other.

## Troubleshooting

| Status or blocker | Safe response |
|---|---|
| `PORT_8502_UNAVAILABLE` | Reuse the exact healthy port-8502 process or stop it deliberately; do not use a broad process kill. |
| `not_configured` | Set the named key and, for BODS, the explicit request box; restart after configuration changes. |
| `disabled` | Remove `off` or set a supported interval, then rerun preflight. |
| `*_INTERVAL_INVALID` / `BODS_AUTO_REFRESH_SCOPE_INVALID` | Correct the local value and obtain a fresh plan fingerprint. |
| `*_CONTROL_INVALID` / `*_SCENE_INVALID` | Stop. Preserve the last accepted evidence and investigate the private local artifact; do not auto-repair it. |
| `*_LOCK_BUSY` | Reuse or stop the exact process already owning the source refresh. |
| `REAL_RUN_PLAN_MISMATCH` | Rerun preflight and review the changed plan rather than bypassing confirmation. |
| `REAL_WORKSPACE_HANDLE_MISMATCH` | The durable workspace moved; return to the owner-selected path or create a new workspace explicitly. |

See [durable v0.7 workspace creation](v07_durable_workspace.md),
[v0.7 local usage](v07_usage.md), and
[Manchester source refresh](integration/manchester_source_refresh.md).

# TrafficTwin v0.7 local usage

This is the current operator runbook for the v0.7 development tree. It covers two deliberately
different local modes:

1. a populated standalone demonstration containing deterministic synthetic fixtures; and
2. an existing isolated v0.7 workspace that may contain accepted Manchester artifacts.

The modes are not interchangeable. A synthetic demo is useful for exploring the product, but it
contains no Manchester evidence. A structurally valid v0.7 workspace is only a safe container; its
marker does not prove that any source artifact, mapping, calibration, baseline or comparison has
been accepted.

The immutable public release remains `v0.6.0`. These instructions do not create a `v0.7.0`
release, accept a capability or authorise source acquisition.

## 1. Start from the repository root

```bash
cd /path/to/diss-integration
uv sync
uv lock --check
```

Do not create a demo or v0.7 workspace inside a valuable existing workspace. Prefer an explicit
owner-selected directory outside the repository for durable local state, or a fresh temporary
directory for a disposable demonstration.

## 2. Reuse a running synthetic demo

Before starting another server on the usual local port, check whether one is already healthy:

```bash
lsof -nP -iTCP:8501 -sTCP:LISTEN
curl --fail --silent --show-error http://127.0.0.1:8501/_stcore/health
```

If the health endpoint prints `ok`, open <http://localhost:8501> and keep the existing process.
Starting a second process on the same port adds no data and will fail with an address-in-use error.

If the exact existing demo path is known, inspect it without changing it:

```bash
uv run traffictwin demo status /exact/path/to/demo
```

An acceptable standalone status reports `valid_workspace: True` and `synthetic: true`. Scenario,
run, report and comparison counts describe that workspace only; they are not Manchester or
scientific evidence counts.

If the known demo directory still exists but the server stopped, restart it explicitly:

```bash
uv run traffictwin demo launch /exact/path/to/demo --port 8501
```

The launch command runs Streamlit in the foreground. Keep that terminal open, and stop this exact
process with `Ctrl-C` when finished.

## 3. Create a fresh disposable synthetic demo

Use this only when there is no usable known demo. It writes outside the repository and keeps the
synthetic boundary obvious:

```bash
TRAFFICTWIN_DEMO_ROOT="$(mktemp -d)"
TRAFFICTWIN_DEMO_PATH="$TRAFFICTWIN_DEMO_ROOT/demo"
uv run traffictwin demo initialise "$TRAFFICTWIN_DEMO_PATH"
uv run traffictwin demo status "$TRAFFICTWIN_DEMO_PATH"
uv run traffictwin demo launch "$TRAFFICTWIN_DEMO_PATH" --port 8501
```

Use `--dry-run` to preview the fixed Streamlit command without starting it:

```bash
uv run traffictwin demo launch "$TRAFFICTWIN_DEMO_PATH" --port 8501 --dry-run
```

Do not use `demo reset --yes` during ordinary use. Reset deliberately replaces a marked demo
workspace and is appropriate only when the operator explicitly wants regeneration.

## 4. What to use in the synthetic UI

The populated demo supports the normal import-first workflow:

- **Home** and **Guided Demo** for task-oriented navigation;
- **Bundle Import & Validation** for strict bundle checks;
- **Run Overview**, **Operations View**, **Infrastructure**, **Journey Time** and the evidence
  pages for deterministic synthetic analysis;
- **What-if Compare**, **Statistical Study**, **Reports** and **Provenance Explorer** for
  comparisons, exports and lineage; and
- the **Platform** pages for inventory, forecasts, draft-only composition, analytics quality,
  evidence-matrix, observatory, decision-safety and synthetic Decision Audit views.

Keep the visible labels intact when presenting results:

- `synthetic` means a software fixture, not an observed road or VEC result;
- a prediction or forecast is not evidence;
- a composer output is a draft, not approval or execution;
- a dry run or local SUMO smoke is software evidence only; and
- unavailable or empty Manchester layers must remain unavailable or empty, never be filled with
  synthetic data or relabelled as Manchester.

## 5. Connect an existing v0.7 workspace

Only connect a real workspace after the owner supplies its exact existing path. Do not search
ignored directories, inspect private workspaces to guess a path, or assume a conventional
`workspace-v0.7` directory exists.

Set the supplied path and validate its strict marker read-only:

```bash
TRAFFICTWIN_V07_WORKSPACE=/absolute/owner-supplied/workspace
uv run traffictwin release v07-workspace-inspect \
  "$TRAFFICTWIN_V07_WORKSPACE" --format json
```

Continue only when the command exits successfully. It verifies the non-symlinked directory,
`workspace-v0.7.json`, exact required layout, active registry and supported registry schema without
changing them. Do not treat `valid: true` as a claim that Manchester artifacts are present or
accepted.

Keep the synthetic demo available on port 8501 and start the real-workspace process on a different
port:

```bash
TRAFFICTWIN_WORKSPACE_PATH="$TRAFFICTWIN_V07_WORKSPACE" \
TRAFFICTWIN_REGISTRY_PATH="$TRAFFICTWIN_V07_WORKSPACE/registry/traffictwin.sqlite" \
uv run streamlit run src/traffictwin/ui/app.py --server.port 8502
```

Then open <http://localhost:8502>. This process is foreground-only and local. The environment
variables apply to this command; they do not rewrite the workspace marker.

Important distinctions:

- Do not run `traffictwin demo launch` against a v0.7 workspace. That launcher requires the
  standalone `workspace.yaml` layout and points at `registry.sqlite`, not the v0.7 registry path.
- Do not run `release v07-workspace-init` against an existing workspace. Initialisation is
  new-only, and a freshly created empty workspace would not make Manchester layers appear.
- A Manchester page must continue to show each source's actual accepted, stale, historical,
  unavailable or excluded state. Missing data is not zero.
- The workspace marker does not resolve the open DfT/WebTRIS time semantics, BODS longitudinal
  privacy decisions, Bee Network scope, mapping review, calibration, baseline or comparison gates.

If the owner specifically wants the real workspace on port 8501, first stop the exact synthetic
server with `Ctrl-C`, confirm the port is free, and then use the same direct Streamlit command with
`--server.port 8501`. Do not use a broad process-kill command.

## 6. Data and credential safety

This runbook intentionally contains no acquisition command and no credential procedure. Source
fetches, provider accounts, credentials and BODS/National Highways operations require separate
explicit authority and their source-specific guides.

During ordinary viewing:

- do not print process environments or credentials;
- do not open raw quarantine bytes merely to populate a page;
- do not copy private absolute paths into reports, screenshots or commits;
- do not publish row-level BODS positions or longitudinal identifiers;
- do not turn a provider silence into a timezone default; and
- do not commit owner-local workspace artifacts.

## 7. Troubleshooting

| Symptom | Safe response |
|---|---|
| Port 8501 is already in use | Check `/_stcore/health`; reuse the healthy app or choose another port. |
| `demo status` says the workspace is invalid | Stop. Confirm the exact demo path; do not initialise over the directory. |
| `v07-workspace-inspect` refuses the path | Stop. Ask for the exact owner-supplied path or repair authority; do not guess or bypass the marker. |
| Manchester layers are unavailable or show zero accepted artifacts | Preserve that state. A valid container is not populated evidence. |
| The UI shows the wrong registry after changing paths | Stop the exact Streamlit process and relaunch with both workspace variables set together. |
| A page asks for approval, calibration or review input | Use the prepared decision artifact and obtain the responsible human decision; do not invent a default. |

## 8. Related documentation

- [Standalone demo](standalone_demo.md)
- [Workspace setup and side-by-side operation](workspace_setup.md)
- [Complete product and usage guide](full_product_guide.md)
- [Manchester Operations UI boundary](integration/manchester_operations_ui.md)
- [Current v0.7 progress and blockers](current_progress_v0_7.md)
- [External decision pack](v07_external_decision_pack.md)
- [Security and privacy](security_and_privacy.md)

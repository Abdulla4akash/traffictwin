# Demo Quick Start (v0.7)

This is the fastest way to see TrafficTwin end-to-end from a clean checkout without any Manchester, Randy, or provider credential.

## One documented launch command

From the repository root after `uv sync` (or `pip install -e ".[dev]"`):

```bash
# Option A — let Home create a demo workspace in the browser (no prior workspace)
streamlit run src/traffictwin/ui/app.py

# Option B — one CLI command that initialises and launches a demo workspace
uv run traffictwin demo launch .traffictwin-demo
# or with an explicit port for side-by-side use
uv run traffictwin demo launch .traffictwin-demo --port 8503
```

Option A is the P0 vertical slice: open `http://localhost:8501`, land on **Home**, press **Create demo workspace**, and follow **Start Guided Demo**. Option B does the same initialisation outside the browser and is what `demo_checklist.md` uses.

Verify without changing anything:

```bash
uv run traffictwin doctor
uv run traffictwin demo status .traffictwin-demo
```

## What the demo workspace contains

* Deterministic synthetic bundles under `.traffictwin-demo/bundles/` (`baseline`, `stressed_demand`, `under_offloading`, …).
* A SQLite registry at `.traffictwin-demo/registry.sqlite` with 62 imported runs, scenario seeds, experiments, and comparisons.
* Reports, exports, provenance, and comparison artifacts under `.traffictwin-demo/reports/` and `.traffictwin-demo/exports/`.

Every artifact carries `synthetic: true` and a deterministic created instant. Nothing is Manchester, Randy/VEC, or live.

## End-to-end browser journey

1. **Home** — after in-browser creation the page reads the session workspace and shows
   `Visible local layers: 0` (Manchester scenes are absent in demo), `Registered runs: 62`,
   `Comparisons: 3` without requiring a process restart; the same counts are shown immediately
   by `traffictwin demo launch .traffictwin-demo` (which sets `TRAFFICTWIN_WORKSPACE_PATH`).
   Verify counts directly: `uv run traffictwin demo status .traffictwin-demo`
   (expect `valid_workspace True, 62/3`). When no accepted Manchester scene is available,
   Home shows a static Greater Manchester boundary context map (offline ONS December 2025
   BGC, E47000001/E08000003, OGL-3.0) with the explicit statement “Static geographic
   context — no live or observed traffic scene is loaded.” The top actions now expose
   **Create what-if comparison** (What-If Studio, synthetic/deterministic/local, not Manchester
   observation or live forecast) as the primary V2-S1 entry alongside **Explore Manchester**,
   **Start Guided Demo**, and **Open latest run**; **Create scenario** remains below. Missing
   observations are not filled with synthetic or stale values.
2. **What-If Studio (V2-S1)** — **Home → Create what-if comparison** or **Build & run → What-If
   Studio**. Choose a baseline preset, define a variation from the closed intervention set, review
   the deterministic changed-parameter ledger, click **Generate comparison**. The pair is staged,
   validated, published, and registered transactionally; on success `selected_baseline_run`/
   `selected_variation_run` are set and Compare is pre-filled. All surfaces state
   SYNTHETIC/DETERMINISTIC/LOCAL and “This studio generates a deterministic synthetic baseline and
   intervention through TrafficTwin’s local generator. It does not run SUMO, VEC, a provider feed or
   an admitted research campaign.” Do not confuse with **Platform → What-If Composer**, which
   predicts from a bounded surrogate fit and drafts unsigned campaigns without approval or execution.
   See `docs/user_guide.md#what-if-studio-v2-s1`.
3. **Bundle Import** — press **Open example baseline** or **Open example variation** to select a committed fixture without typing a path; or use the text input for any local bundle. Validation is deterministic. Remains the fallback when What-If Studio is skipped.
4. **Run Overview / Infrastructure / Energy / Fairness / Journey Time** — inspect deterministic metrics; unavailable metrics stay `UNAVAILABLE` with reason codes.
5. **Comparison** — baseline vs variation, arithmetic deltas, seeded alignment check, downloadable evidence. Works with a What-If generated pair (`selected_baseline_run`/`selected_variation_run`) or the committed demo fixtures.
6. **Guided Demo — Standalone synthetic** — 9 stages from experiment plan → validate → metrics → **Build a what-if experiment** (What-If Studio) → compare → replay → diagnose → trace → report. The What-If stage is the preferred V2-S1 path; skipping it and using Bundle Import keeps Compare reachable. Action stages (`register_experiment_plan`, `regenerate_report`) auto-advance; review stages wait for **Reviewed — continue**.
7. **Reports** — inventory, deterministic regeneration, comparison/difference provenance, export.
8. **Provenance Explorer** — traces metric → canonical record → source row; bounded graph.
9. **Manchester Operations** — in a demo workspace it will always show "No accepted Manchester scene" — that is expected. Manchester evidence requires a separately activated real workspace with accepted snapshots.

Cross-page state: the selected bundle/run survives navigation between groups. A seeded `selected_bundle_path` remains authoritative on every page.

## Demo vs real workspace

| Dimension | Demo (this guide) | Real Manchester workspace |
|---|---|---|
| Path example | `.traffictwin-demo` | owner-supplied absolute path outside repo |
| Initialiser | `traffictwin demo launch` or Home button | `preview_durable_v07_workspace` + `create_durable_v07_workspace` digest flow |
| Content | synthetic fixtures only | accepted Manchester snapshots, map-layers, preflight |
| Provider use | none | BODS / National Highways via transient env keys only |
| Claim | `SYNTHETIC` / `DETERMINISTIC` badges | source-separated `historical` / `near_live` / `live_vehicle` / `stale` / `unavailable` |
| v0.7 marker | `workspace.yaml` (`traffictwin_standalone_demo`) | `workspace-v0.7.json` |

For real-workspace activation see [`docs/v07_usage.md`](v07_usage.md), [`docs/v07_durable_workspace.md`](v07_durable_workspace.md), and [`docs/v07_real_workspace_run.md`](v07_real_workspace_run.md).

## Unavailable functions remain unavailable

* Continuous city-road flow, measured speed/congestion, traffic-signal phase, parking/pedestrian/cyclist telemetry — not covered by any accepted source.
* Provider acquisition beyond the three bounded National Highways products and the explicit BODS live-bus action — requires credentials, policy, and acceptance review.
* Observation-to-SUMO baseline, calibration, comparison acceptance, SUMO-to-VEC lineage — blocked by awaiting human map-review, scientific calibration, and provider/schema decisions. See [`docs/implementation-status.md`](implementation-status.md) and [`docs/open-questions.md`](open-questions.md).

## Troubleshooting (clean checkout)

| Symptom | Response |
|---|---|
| `streamlit run` shows no workspace | Use Home's **Create demo workspace** button, or run `uv run traffictwin demo launch .traffictwin-demo` |
| Button says path not empty | Choose an empty/new directory, or relocate the existing non-workspace content |
| Port busy | Check `curl http://127.0.0.1:8501/_stcore/health`; reuse it or launch on 8503 |
| Bundle path not found | Press the Quick-start fixture buttons on Bundle Import, or `git status --short tests/fixtures` |
| Manchester map empty in demo | Expected — demo workspaces show a static Greater Manchester boundary context map (offline ONS December 2025 BGC) with “Static geographic context — no live or observed traffic scene is loaded.” No accepted Manchester scene is present by design |
| Real workspace inspect fails | Stop; request the exact owner path; use `traffictwin release v07-workspace-inspect` |

## Sources & design

* Design: [`docs/traffictwin-design-v0_7.md`](traffictwin-design-v0_7.md)
* Formal truth: [`docs/implementation-status.md`](implementation-status.md)
* Progress: [`docs/current_progress_v0_7.md`](current_progress_v0_7.md)
* Execution record for this slice: [`docs/product_completion_execution_2026-08-08.md`](product_completion_execution_2026-08-08.md)

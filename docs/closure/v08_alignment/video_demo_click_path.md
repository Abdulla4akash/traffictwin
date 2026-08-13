# Video Demo Click Path — Seven-Minute Package (Lane 11)

**Campaign:** `v08-requirements-closure` · **Lane:** `11` · **Worker:** `muse-11`
**Base SHA:** `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6` · **Prepared base:** `1185286b6dc651347b54039031ca9c28c639c38a`
**Duration inside video:** 5:15–6:15 (60 s) — 6 steps, mean ~10 s per step
**Standing:** IMPLEMENTATION-VERIFIED FACT — every locator verified at exact base; no step introduces a non-existent file
**Constraint:** Only reachable prepared-base routes and frozen dependency artifacts; do not claim that a video has been recorded or submitted.

> Honesty labels: IMPLEMENTATION-VERIFIED FACT (locator existence), RESEARCH-EVIDENCE FACT (campaign JSONs), SOURCE-DERIVED FACT (baseline hashes), INFERENCE, PROVISIONAL WORDING, EXTERNAL DECISION REQUIRED. Every evidence shot has a standing and a limitation (see `video_evidence_checklist.md`).

## Preconditions (spoken at demo start)

- Local workspace exists (empty acceptable); no credential required.
- `BODS_API_KEY` / `NATIONAL_HIGHWAYS_API_KEY` absent → honest `not_ready_credential_missing` blockers, no live retrieval.
- Deterministic offline demo: replays committed SHAs only; private raw bytes never committed.

## Click path — 6 steps (resolves to exact product/dependency artifacts)

| Step | Clock | Human entry | Exact locator (repo-relative) | Route / CLI | Service / Artifact behind it | Action | Expected output (deterministic) |
|------|-------|-------------|-------------------------------|-------------|------------------------------|--------|---------------------------------|
| 1 | ~5:15 | Manchester Evidence Hub (inventory, readiness, blockers) | `src/traffictwin/ui/pages/manchester_evidence_hub.py` via `src/traffictwin/ui/navigation_v07.py` (`UiPage.MANCHESTER_EVIDENCE_HUB`, `url_path="manchester-evidence-hub"`) | `/manchester-evidence-hub` | `src/traffictwin/ui/manchester_evidence_hub.py` + `docs/closure/v08_alignment/manchester_demo/current_view_artifact.json` | Open Hub; capture readiness table | Table lists S01–S11 with typed readiness `ACCEPTED_AVAILABLE / NOT_READY / UNAVAILABLE / DEFERRED`; fingerprint derived from typed state (deterministic); DESIGN-ONLY rows remain blocked |
| 2 | ~5:25 | Manchester Operations — strategic context (National Highways) | `src/traffictwin/ui/pages/manchester_operations.py` via `src/traffictwin/ui/app_pages/manchester.py` → `src/traffictwin/ui/page_runtime.py:run_manchester_page_script` → `pages/manchester_operations.render()` | `/manchester` | `src/traffictwin/integration/manchester/national_highways_live.py` + receipt `docs/integration/evidence/national_highways_operational_acceptance_20260724.json` (SHA `5329b1…`) | Inspect National Highways card | Honest `not_ready_credential_missing` blocker when key absent, no live call; label `REAL EXTERNAL NON-MANCHESTER DATA — strategic-road only`, never Manchester city-road |
| 3 | ~5:35 | Manchester Operations — historic baselines | `src/traffictwin/ui/pages/manchester_operations.py` (same chain) | `/manchester` | `src/traffictwin/integration/manchester/dft_acquisition.py` + `src/traffictwin/integration/manchester/boundary_reference.py` | Review DfT historic + ONS boundary layers | DfT catalogue offline (committed receipts `c0a59f…` / `f33cfe…`); ONS boundary static; both labelled historical/static, never live |
| 4 | ~5:45 | Strategy matrix — existing strategies | `docs/closure/v08_alignment/strategy_matrix.json` (frozen lane 05 artifact) | File view (repo) | E2b `fe2ed4e9bd9043b19b96a5f179390db629b01ccb` at `refs/harness/read-only/e2b` | Open matrix | Three arms rendered; JSQ labelled least-busy (argmin rsu_busy_ms, common-target per substep); zero-backhaul badge visible |
| 5 | ~5:52 | Improved strategy contract + figure data | `docs/closure/v08_alignment/improved_dynamic_strategy_contract.json` + `docs/closure/v08_alignment/improved_strategy_figure_data.csv` | File view | E2d `80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761` at `refs/harness/read-only/e2d` | Highlight identity / reservation rule + CSV row | Fingerprint `af128cf08` shown; per_task_dla defined as per-candidate argmin with immediate reservation; CSV single figure row audible |
| 6 | ~6:02 | Reproducibility artifact — command | `src/traffictwin/cli.py` (`traffictwin doctor`) | CLI `traffictwin doctor` | `src/traffictwin/doctor.py` + `docs/closure/v08_alignment/improved_strategy_evidence_index.json` | Run `traffictwin doctor` (read-only) | Doctor exits 0, reports workspace typed state; no network; evidence index SHAs echo (`f77afb23…`, `0e3f27cd…`, `93c97059…`, `e188ce07…`) |

**Validator checks for each step:** locator file exists at `bd4570fd` (or prepared base for frozen lanes), route present in `src/traffictwin/ui/navigation_v07.py` where claimed, artifact SHA prefix matches committed file if local.

## What the demo explicitly does NOT do

- No full page-set tour (only the 4 locators above, reused honestly).
- No live retrieval — deterministic placeholders only.
- No stakeholder approval implied.
- No physical scaling demonstration — service remains fixed 1×.

## Timing within the 60 s window

Steps are read in order; cursor moves are the only animation; no step exceeds 12 s, total 60 s. Overrun fails validation.

## Provenance

- Frozen baseline SHAs as in script.
- Manchester demo SHAs recomputed from `manchester_demo/*.json` committed files.
- Strategy / improved artifacts at exact frozen lane SHAs declared in the frozen-dependency manifest (controller-only `.harness` provenance, excluded from committed locator resolution).

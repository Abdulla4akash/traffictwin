# V2-A Real Journey Acceptance — Home → Guided Demo → What-If → Consequence Lenses → Compare

- Date: 2026-08-09
- Branch: `agent/product-v2a-journey-acceptance` from `a9ec532ac88ed8678973416fe21bcab5d1a57d11` (exact PR #14 head, approved preliminary)
- Base for stacked PR: `agent/product-v2-home-guided-whatif` (PR #14 OPEN DRAFT) else `main`
- Suite: `tests/integration/test_v2a_real_journey_acceptance.py` (8 scenarios A–H)
- Production boundaries exercised: real routing/session/validation/report construction; no mocked hashes, no fixture substitution for pair identity

## Standing

Engineering acceptance slice only. No Gate-F claim. Synthetic/local/deterministic wording retained throughout. Portfolio/Challenge pages not yet included (depend on PR #13 / #17 if absent). PR #14 head untouched (no commit/amend/rebase/force-push, remains PARKED).

## Scenario map (A–H)

| ID | Coverage | Key production proof |
|---|---|---|
| A | Home → Guided → What-If routing + deterministic pair | AppTest Home title, Guided Demo completion writes authoritative `selected_baseline_run`/`selected_variation_run`, `generate_whatif_pair_for_ui` deterministic `pair_id_for_request`, real `validate_bundle_for_ui` |
| B | Guided Demo handoff provenance/seed/fingerprint | Guided Demo writes real pair fingerprints, pair receipt `pair_fingerprint` matches `request_fingerprint` |
| C | Pair determinism + fingerprint stability | Two identical `WhatIfPairRequest`s produce identical `pair_id`, `request_fingerprint`, receipt portable dict, second call idempotent via registry |
| D | Consequence Lenses consumes exact pair | `build_consequence_lens_report(bv, vv)` with real `BundleAnalysis`, identities `run_id` match generated artifacts, `synthetic` true, page renders `Consequence`/`Traffic` via title/subheader and dataframes |
| E | Compare/report continuity | Same pair remains selected through Compare/report surfaces, receipt portable dict retains `synthetic`/`NOT_SUMO_EXECUTION` labels |
| F | Transactional rollback | Injected failure on variation staging rolls back: no registry row leaked, no half `whatif_receipt.json`, staging glob cleaned, authoritative `selected_*` unchanged, UI wrapper returns `ServiceError` |
| G | Invalid draft lifecycle | Blank/whitespace/missing/invalid draft preserves last valid `selected_*`, never writes `"."`, validator rejects invalid bundle |
| H | Offline/CWD hermeticity | Different CWD, `socket.socket` monkeypatched to fail, temp workspace only, no CWD artifact leak, full journey repeats with real services |

## Production wiring verified

- `initialise_workspace(tmp/ws)` → `generate_whatif_pair_for_ui` → `validate_bundle_for_ui` → `build_consequence_lens_report` are real services, not stubs.
- `AppTest.from_file(app.py)` for Home routing proves rendered What-If Studio title, not just session enum.
- `pair_id_for_request` + `receipt_to_portable_dict` prove deterministic identity and portable evidence without hash mocking.
- `ConsequenceLensReport` fields `baseline_identity`/`variation_identity` carry `run_id`/`synthetic` from real `validation.manifest.run.run_id`.

## Hermeticity and safety

- Each scenario uses `tempfile.TemporaryDirectory` workspaces and per-scenario `registry.sqlite`; no mutation of CWD or `tests/fixtures/bundles/*`.
- H scenario proves no network calls (failing socket) and no artifact leak after run.
- Serial execution while E1 active (`pgrep` check, no `-n`, no SUMO/VEC). Real research under `/Users/akashx/AntigravityTest/diss` and E1 pid `65148` never signalled.

## Adversarial mutation proofs

Suite is not vacuous: temporarily reverting any of these production invariants makes at least one scenario fail (restore after, mutant count 0 at rest):

1. Home routes to `RUN_OVERVIEW` instead of What-If → A fails (no What-If title/session).
2. Guided Demo overwrites authoritative pair on completion → B/C fail (fingerprint mismatch).
3. Rollback cleanup removed (`_rollback_on_failure` no-ops) → F fails (staging/receipt leak).
4. Invalid draft commits to `selected_*` (blank → `"."`) → G fails (dot write).

These are proved by editing the corresponding production path, re-running `pytest -q tests/integration/test_v2a_real_journey_acceptance.py`, observing ≥1 failure, then restoring.

## Run instructions

```bash
# from worktree /Users/akashx/AntigravityTest/traffictwin-v2a-acceptance
uv sync --extra dev
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync mypy
uv run --no-sync python -m pytest tests/integration/test_v2a_real_journey_acceptance.py -q  # serial, 60–90s
```

Result on this branch: `8 passed in 71.41s`, `ruff All checks passed`, `mypy Success: no issues found in 936 source files`.

## Out of scope / next

- Portfolio/Challenge evidence panels (await PR #13/#17).
- Full E2E Playwright smoke (optional, not part of this isolated slice).
- Any change to PR #14 head or to PR #13/#15/#16/#17 branches (explicitly untouched).

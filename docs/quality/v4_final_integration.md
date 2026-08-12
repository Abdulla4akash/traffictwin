# V4 Final Integration Receipt — Twelve-Lane Product Integration

Integrator: Fable (final integration pass).
Scope: integrate all twelve frozen V4 worker lanes into one candidate branch,
resolve shared registration/CLI/docs centrally, resolve genuine cross-lane
integration defects, run the combined validation, and hand off to a fresh
independent exact-head integration review. Worker PRs remain unmerged; no
worker branch was modified.

## Identity

- Integration base main (start): `bfea996f080a1d505910acc13355c04e01942f0c`
- Final incorporated main: `bfea996f080a1d505910acc13355c04e01942f0c`
  (main did not move during integration; re-verified before handoff)
- Integration branch: `integration/product-v4-twelve-lane-final-v1`
- Integration worktree: fresh, created from the exact base (never a worker tree)

## Frozen lane ledger

All twelve PR heads were verified OPEN + DRAFT + unmerged at the exact
approved SHAs before integration began, and integrated as exact SHAs
(`git merge --no-ff <sha>`), never as branch names.

| Lane | Feature | PR | Frozen SHA | Integrated | Conflict |
|---|---|---|---|---|---|
| 1 | Study Workspace | #36 | `13f6d87dce1676300a128be55c78f43ffe6890db` | yes | none |
| 2 | Evidence Admission Inbox | #33 | `726edc29969099fc6f44d93dc034e39e027a9ba2` | yes | none |
| 3 | Metric Contract Registry | #32 | `3d4e9bcb93aeaf15bdfb8cb4d76d5b00ed6bb8f1` | yes | none |
| 4 | Calibration Workbench | #31 | `92024dc3c08b7f8eb550499c9492cdeccd8dddda` | yes | none |
| 5 | Baseline Registry | #41 | `883320d01eaeda955fb130419c9249482fd0113b` | yes | none |
| 6 | Study Accrual Monitor | #34 | `cbdfc16d59f30a149ee053fcd289c7440995ee8b` | yes | none |
| 7 | Reproducibility Replay | #39 | `345cc82f65a2933e763d063f27d79944df01be09` | yes | none |
| 8 | Contract Drafting Assistant | #37 | `46cb799d8f6295814961a41a3be7d7aabb61eae3` | yes | none |
| 9 | Event-to-Scenario Bridge | #40 | `bb4fa2fb49c72f2f2db84aec90b9f7bbd96fddca` | yes | none |
| 10 | Trade-Off Explorer | #38 | `4983008bb3bb72c1441e7d32d9bfc05612af00a9` | yes | none |
| 11 | Workspace Activation | #35 | `29e13a98c875700a58855f8eb2b401ee4d412baa` | yes | none |
| 12 | Streamlit/Pytest Isolation | #42 | `69f221aee27ade44e1b0fc60d1c45c6837980b1a` | yes | none |

PR #34's body contains stale text calling `bf2fa49...` current; the
authoritative ledger SHA `cbdfc16...` was used, per campaign instruction.

- Merge order: 12, 3, 5, 2, 4, 6, 8, 9, 10, 7, 11, 1 (platform guard first,
  registries before consumers; order proved uncontentious — zero textual
  conflicts anywhere because the twelve lanes' file sets are fully disjoint).
- Surviving contribution: every lane's full file delta is byte-identical
  between its frozen SHA and the combined tree (verified per lane with
  `git diff <frozen-sha> HEAD -- <lane files>`), and no conflict markers
  exist in the tree.
- All twelve lanes share merge base `7b1b0b5` (V3 five-lane main); main had
  moved only by two research-docs commits since, so no product-code drift
  existed between base and live main.

## Shared UI registration (Fable-owned)

Eleven product lanes registered from their `docs/quality/v4_registration`
manifests (the manifests, not PR prose, were the handoff); Lane 12 is test
infrastructure and has no page.

- `src/traffictwin/ui/labels.py`: 11 new `UiPage` entries (manifest
  `enum_name`/`label`) + `PAGE_DESCRIPTIONS` from manifest descriptions.
- `src/traffictwin/ui/navigation_v07.py`: 11 `V07PageSpec` rows using manifest
  URL/script, appended at the end of each page's manifest group.
- `src/traffictwin/ui/navigation.py`: legacy `PAGE_GROUPS` coverage
  (Build & run→Workflow; Results/Compare & test/Evidence & reports→Analysis;
  Workspace Activation→Project) so the legacy radio router still lists every
  `UiPage` (54 total).
- `src/traffictwin/ui/page_runtime.py`: 11 `PAGE_RENDERERS` entries importing
  the manifest renderers (`event_scenario_bridge.render()` adapted via
  lambda; all others take the config argument directly).
- The 11 lane `app_pages` wrappers were converted from direct
  `render(load_ui_config())` calls to the repository convention
  `run_page_script(UiPage.X)` so every registered page cold-renders through
  the central runtime path (`_active_ui_page`, pending-redirect handling,
  guided assistant, shared sidebar description). Same renderer, same config
  source, exceptions still propagate.
- `tests/ui/test_navigation_v07.py`: expected route/group table extended by
  the 11 new rows.
- Duplicate checks: no duplicate enum values, labels, URLs, scripts, or
  renderer mappings; `validate_v07_page_specs()` passes; all scripts exist;
  all renderers import.

Registration decisions requiring judgment (recorded, reviewable):

1. **Lane 11 group.** The manifest declares group `"Settings"`, which exists
   in neither router. Mapped to `Advanced` (v0.7 — where the Settings page
   lives, immediately after it) and `Project` (legacy). No other manifest
   deviated from a real group.
2. **Icon normalization.** Manifests mixed three icon spellings
   (`:material/x:`, `material-x`, bare `x`). All normalized to the
   repository's `:material/x:` form, preserving each manifest's glyph
   (hub, fact_check, contract, tune, flag, monitoring, replay, description,
   alt_route, compare_arrows, settings). Duplicate glyphs across pages
   already exist in the repo and were accepted.

## Central CLI registration (Fable-owned)

Five CLI manifests found; five sub-apps wired once each into
`src/traffictwin/cli.py` with `app.add_typer(...)`, names and help straight
from the manifests. No command collisions with existing root commands or
groups; no import-time side effects (verified by import smoke and root
`--help`).

| Command | Module |
|---|---|
| `baseline` | `traffictwin.baseline_registry.cli:app` |
| `evidence-admission` | `traffictwin.evidence_admission.cli:app` |
| `metric-contract` | `traffictwin.metric_contract_registry.cli:app` |
| `replay` | `traffictwin.reproducibility_replay.cli:app` |
| `workspace` | `traffictwin.workspace_activation.cli:app` |

Root `--help` lists all five; each subcommand `--help` exits 0.

## Docs (Fable-owned)

- `README.md`: 12 feature-matrix rows (11 features + isolation guard).
- `docs/user_guide.md`: one section per V4 page (capability + boundary
  statement each), plus the privacy-policy compatibility note below.
- `docs/ui_conventions.md`: no change needed (contains no page inventory).

## Cross-lane decision 1 — field-name privacy policy (Phase 9)

Conflict: Data Contract Workbench drift/observation **CSV** exports collapsed
secret-looking field names to `[REDACTED_SECRET_FIELD]`, while Lane 8's
approved Contract Drafting Assistant preserves exact field names everywhere
and flags sensitive names `PRIVACY_REVIEW_REQUIRED`.

Decided product policy — **preserve identity, flag explicitly, redact values
only**:

1. Schema field names are identity: verbatim on every export surface; two
   distinct fields never collapse to one identifier.
2. Sensitive-looking names get explicit review semantics: drafting keeps its
   approved `PRIVACY_REVIEW_REQUIRED` findings; workbench CSVs gained an
   explicit `privacy_review` column carrying the same flag string instead of
   rewriting the name. Each feature keeps its reviewed detector (workbench:
   credential-substring set; drafting: token-aware personal-data matcher whose
   no-flag cases are pinned by frozen tests) — the shared policy is the
   semantics, not one merged token list.
3. Raw values never enter portable exports (`redact_value` unchanged);
   CSV formula-injection protection unchanged.
4. Compatibility rule (documented in the user guide): stored contracts and
   fingerprints are untouched — redaction was presentation-only; CSVs from
   earlier versions may contain the retired placeholder and lack the new
   column; re-export to obtain per-field identity.

Basis, not preference-for-newer: the placeholder violated per-field identity
in the one report whose rows are per-field findings, while the adjacent JSON
export of the same report always carried exact names (so it protected
nothing); Lane 8's exact-head-approved contract had already decided identity
preservation for the same domain; and the campaign's own consistency
requirements (two fields must not collapse) exclude the placeholder.

Changes: `src/traffictwin/data_contract/exports.py` (both CSVs),
`redact_field_name` removed from `fingerprint.py` (its only consumer was the
rejected behavior; `is_secret_field_name`, `redact_value`, `sanitise_for_csv`
remain), old redaction test rewritten to pin the new policy, and a
cross-feature regression suite added:
`tests/integration/test_field_name_privacy_policy.py` (6 tests spanning both
features: distinct-sensitive-fields stay distinct, benign traffic fields
unflagged, observation CSV flags without leaking, formula safety survives,
value redaction unchanged, one shared vocabulary across all four surfaces).

## Cross-lane decision 2 — production fork-after-AppTest SIGSEGV (Phase 10)

Reproduced before changing anything: 5× loop of the SUMO-page accessibility
tests → runs 1 and 5 each emitted **seven** hidden
`Fatal Python error: Segmentation fault` on stderr while pytest reported
`8 passed`, exit 0. Traceback: `subprocess.py:_execute_child` (fork) ←
`sumo_execution/service.py::_probe_version` ← `sumo_runtime_status()` ←
`sumo_import.render` under Streamlit AppTest, with SUMO 1.27 installed on
PATH. This is the production occurrence of the macOS fork-after-AppTest class
Lane 12 fixed in test support.

Fix (production-safe, no `tests/support` import): `_probe_version` now
captures through a narrow `os.posix_spawn` helper
(`_spawn_capture_output`) in the same module — exact argv, no shell,
inherited cwd/env, captured stdout/stderr, `subprocess.TimeoutExpired` after
kill+reap on timeout, no zombies, no fd leaks on reachable paths
(pipe/devnull cleanup in `finally`), `subprocess.run` fallback only where
`posix_spawn` does not exist (non-POSIX).

Regression: `tests/unit/test_sumo_probe_fork_safety.py` — 6 tests including
an AppTest-tainted child process that calls the production probe 10× and
asserts parseable output with zero crash markers; plus fd-leak and timeout
semantics tests. Post-fix evidence: 8/8 repeated SUMO-page accessibility runs
clean, and 3/3 full accessibility runs (442 tests each) with **zero** crash
markers.

Related, deliberately untouched: `manchester/network_build.py` and
`manchester/network_decode.py` contain the same `subprocess.run` probe
pattern but are reachable only from operator CLI commands, never from an
AppTest-rendered page — recorded as NON-BLOCKING backlog, not changed.

## Cross-lane decision 3 — Lane 1 wrapper-form tests

Genuine integration conflict: two frozen Lane 1 tests pinned the *source
text* of `app_pages/study_workspace.py` in its pre-registration form
(explicitly asserting `run_page_script` absent) and tested exception
propagation by monkeypatching the pages module attribute. Central
registration converts every wrapper to `run_page_script(UiPage.X)`, which
those assertions contradict while their *intent* (no swallowed renderer
exception, no fallback `UiConfig()`) is fully preserved by the central path.
Resolution on the integration branch only: the two tests now assert the same
guarantees against the registered form (source check for the registered
wrapper + `PAGE_RENDERERS` monkeypatch for propagation). Lane 1 suite after
the change: 107 passed. No lane branch was touched; no guarantee was
weakened.

## Lane 12 combined-invocation observation (pre-existing, NOT integration)

Running Lane 12's three test files in **one** pytest invocation
(`test_streamlit_isolation_guard.py test_streamlit_isolation_subprocess.py
test_apptest_cold_start_hardening.py`) fails 11 cold-start tests with
`returncode=-11` children: the first two files run AppTest in-process, after
which the cold-start tests' own raw `subprocess.run` children hit the same
macOS fork-after-AppTest crash. Verified **identical** (11 failed, 44
passed) at the frozen head `69f221a` in its own worktree — a boundary of the
lane's guarantee (its guard isolates Streamlit state; it does not make raw
`subprocess.run` fork-safe), not something integration introduced. Each file
passes standalone on the integration tree (15, 5, 35). Classified
CURRENT-BASELINE / invocation-pattern interaction; carried as non-blocking
backlog (candidate future hardening: spawn those probes via the lane's own
`posix_spawn_run`).

## Test ledger (exact commands, integration tree, all serial)

Phase 1 research-safety `pgrep` sweeps before work, before Phase 10, before
the broad group, and at handoff: no research processes at any point; nothing
was signalled, killed, reniced, attached, or launched; no SUMO/VEC/E-series
workload was started.

| Command | Result | Exit |
|---|---|---|
| `uv run pytest -q tests/ui/test_navigation_v07.py` | 66 passed | 0 |
| `uv run pytest -q tests/ui/test_accessibility.py` (run 1) | 442 passed, 0 crash markers | 0 |
| `uv run pytest -q tests/ui/test_accessibility.py` (run 2) | 442 passed, 0 crash markers | 0 |
| `uv run pytest -q tests/ui/test_accessibility.py` (run 3) | 442 passed, 0 crash markers | 0 |
| Lane 1 `tests/ui/test_study_workspace.py tests/unit/test_study_workspace.py` | 107 passed | 0 |
| Lane 2 `tests/test_evidence_admission.py tests/test_evidence_admission_hardening.py tests/ui/test_evidence_admission.py` | 61 passed | 0 |
| Lane 3 `tests/ui/test_metric_contract_registry.py tests/unit/test_metric_contract_registry.py` | 40 passed | 0 |
| Lane 4 `tests/integration/test_calibration_workbench_flow.py tests/ui/test_calibration_workbench.py tests/unit/test_calibration_workbench.py` | 37 passed | 0 |
| Lane 5 `tests/ui/test_baseline_registry.py tests/unit/test_baseline_registry.py` | 50 passed | 0 |
| Lane 6 `tests/integration/test_study_accrual_integration.py tests/ui/test_study_accrual.py tests/unit/test_study_accrual_service.py` | 48 passed | 0 |
| Lane 7 `tests/ui/test_reproducibility_replay_page.py tests/unit/test_reproducibility_replay.py tests/unit/test_reproducibility_replay_cli.py` | 46 passed | 0 |
| Lane 8 `tests/contract_drafting/test_contract_drafting_service.py tests/ui/test_contract_drafting.py` | 51 passed | 0 |
| Lane 9 `tests/ui/test_event_scenario_bridge_page.py tests/unit/test_event_scenario_bridge.py` | 43 passed | 0 |
| Lane 10 `tests/integration/test_tradeoff_explorer_flow.py tests/unit/test_tradeoff_explorer.py tests/unit/ui/test_tradeoff_explorer_page.py` | 39 passed | 0 |
| Lane 11 `tests/ui/test_workspace_activation.py` | 27 passed | 0 |
| Lane 12 `tests/unit/test_streamlit_isolation_guard.py` | 15 passed | 0 |
| Lane 12 `tests/unit/test_streamlit_isolation_subprocess.py` | 5 passed | 0 |
| Lane 12 `tests/unit/test_apptest_cold_start_hardening.py` | 35 passed | 0 |
| Privacy policy + both feature suites (`tests/integration/test_field_name_privacy_policy.py tests/unit/data_contract tests/contract_drafting`) | 112 passed | 0 |
| Fork-safety + SUMO execution (`tests/unit/test_sumo_probe_fork_safety.py tests/unit/test_sumo_execution.py`) | 40 passed | 0 |
| Cross-lane smokes (`tests/integration/test_v4_cross_lane_smokes.py`) | 9 passed | 0 |
| `uv run pytest -q tests/ui` | 983 passed, 0 crash markers | 0 |
| `uv run pytest -q tests/unit/ui` | 254 passed, 0 crash markers | 0 |
| `uv run pytest -q tests/ui tests/unit/ui` | 1237 passed, 0 crash markers | 0 |
| `uv run pytest -q` (unrestricted) | 2 collection errors (`test_bbus_synthetic_trace_smoke.py`, `test_bcap_synthetic_smoke.py`: `No module named 'jax'`) | 2 |
| `uv run pytest -q --ignore=tests/unit/test_bbus_synthetic_trace_smoke.py --ignore=tests/unit/test_bcap_synthetic_smoke.py` (widest practical) | 5752 passed, 1 failed, 10 skipped, 1 warning, 0 crash markers | 1 |

Widest-run classification (every non-pass accounted for):

- **JAX collection errors — ENVIRONMENT/PRECONDITION.** Both files come from
  current main (not from any lane) and import `jax`, which belongs to the
  `vec-runner` research extra and is absent from the established product
  environment by design. Proven on main itself: the same collection in the
  main repository's own venv at `bfea996` fails identically
  (`--collect-only` → 2 errors, exit 2). Research infrastructure was NOT
  installed to green the gate.
- **`test_manchester_artifact_integrity.py::test_durable_build_location_is_accepted`
  — ENVIRONMENT/PRECONDITION.** The test feeds `Path.cwd()/data/...` to
  `refuse_ephemeral_dependency`, and this integration worktree lives under
  `/tmp/`, which that checker refuses by design (the sibling test asserts
  exactly that refusal for `/tmp` paths). Integration changed nothing here:
  `git diff bfea996..HEAD -- src/traffictwin/integration/manchester/
  tests/unit/test_manchester_artifact_integrity.py` is empty, and the
  identical test file passes 7/7 on current main at its durable checkout on
  the same machine. Any durable checkout of this branch will pass it.
- **10 skipped — RESEARCH-ONLY / ENVIRONMENT PRECONDITIONS.** 8 VEC skips
  (external reviewed repositories / private `vec_env` clone / fresh-run env
  var absent — research boundaries this campaign must not touch) and 2 cold
  AppTest controls that require the explicit `--run-cold-apptest` flag.
- **1 warning — pre-existing** `zipfile` duplicate-name warning from a main
  study-capsule test, untouched by integration.
- **0 hidden crash markers** across the entire widest run — the Phase 10 fix
  holds under the full combined suite.
- Notably the Lane 12 cold-start tests pass inside the widest single-process
  run; the 11-failure interaction appears only under the specific
  guard-suites-first invocation documented above, on both the frozen head
  and the integration tree.

No skipped/deselected/error counts appeared in any green run above unless
stated (pytest -q reports only non-zero categories; every row above is the
verbatim summary line).

## Cross-lane integration smokes (Phase 12)

`tests/integration/test_v4_cross_lane_smokes.py` (9 passed): twelve-lane
single-interpreter import with no cycles; five CLI groups present; page
registry covers Study Workspace plus all V4 pages; legacy Resource Strategy
arms validate with `metric_declarations` defaulting to absent; Trade-Off
fail-closed (arm with unavailable metric infeasible and excluded from
frontier); Contract Drafting handoff `draft_only=True / freeze_executed=False
/ human_review_required=True`; Event Bridge manifest declares
`bridge-unexecuted` with "no simulation or VEC was launched"; replay contract
is a closed non-empty allowlist with fingerprint; Baseline Registry candidate
registration leaves `active_baselines` empty; accrual report deterministic
over a frozen plan (no cached-state shortcut). Workspace Activation's
no-action-on-render guarantee is exercised by its 27 lane UI tests plus its
cold render inside the 442-test accessibility gate.

## Canonical gates (Phase 15)

| Gate | Result |
|---|---|
| `uv run ruff format --check .` | 1195 files already formatted (exit 0) |
| `uv run ruff check .` | All checks passed! (exit 0) |
| `uv run mypy` | Success: no issues found in 1109 source files (exit 0) |
| `uv lock --check` | Resolved 91 packages; lock up to date (exit 0) |
| `git diff --check` | clean (exit 0) |

Canonical repository mypy (no feature-scoped or `mypy src` runs). One
integration-only edit was needed to keep canonical mypy green in the combined
tree: Lane 3's `ui/pages/metric_contract_registry.py` carried
`# type: ignore[attr-defined]` on `UiPage.METRIC_CONTRACT_REGISTRY` for the
pre-registration state its `_HAS_ENUM` guard anticipated; central
registration created that member, making the ignore unused. The ignore
comment was removed on the integration branch (the guard itself is
untouched). This is the post-registration step the lane's own defensive code
was written for.

## Non-blocking items carried (not "cleaned up")

- Lane 1 caption regression test does not distinguish declared vs derived
  when values coincide (product behavior independently probed correct).
- Lane 2 queue-derivation duplication between page/service helpers (drift
  risk only; no divergence surfaced in integration).
- Lane 6 PR #34 stale body text (ledger SHA authoritative; body not edited).
- Lane 12 helper latent issues from its review (unreachable-path read-fd
  leak, small-chunk double-`waitpid` clobber, stale doc wording, weakened
  helper return typing, weak secret canary) — none became reachable/blocking
  in the combined tree.
- Lane 12 combined-invocation cold-start interaction (see section above).
- Manchester CLI-only subprocess probes (same fork pattern, not
  AppTest-reachable).

## Final identity

- Main re-verified unmoved at handoff:
  `bfea996f080a1d505910acc13355c04e01942f0c`.
- Final integration head: the pushed tip of
  `integration/product-v4-twelve-lane-final-v1` — the exact review target is
  the draft integration PR's `headRefOid` (a receipt cannot contain its own
  commit's SHA).
- Integration PR: draft, base `main`, head
  `integration/product-v4-twelve-lane-final-v1`; number recorded in the PR
  itself and the campaign handoff report.
- Verdict at handoff: READY FOR INDEPENDENT EXACT-HEAD INTEGRATION REVIEW.
  Do not merge until a fresh reviewer returns explicit
  `APPROVE exact SHA <integration head>` and the head is unchanged.

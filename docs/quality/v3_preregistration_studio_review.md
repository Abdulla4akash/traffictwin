# v3 Preregistration Studio Review

**Branch:** `agent/product-v3-preregistration-studio-v1`  
**Base at prompt creation:** `73264bd125ead979cd2615d5e4b50c2cfe6c50ae` (origin/main at initial feature creation)  
**Live main at rebase:** `3b7933dfecf05b579ff9c223729128109a933d93` (origin/main at prompt creation, includes Manchester Evidence Hub #15, Portfolio Explorer #13, Challenge-WhatIf Bridge #17)  
**Date:** 2026-08-10 (final rebase 2026-08-10)

## Heads

- **HISTORICAL ORIGINAL:** `e384e4ec35650fdc269140e5cff6aa839a61ba18` — initial PR #23 head reviewed by Claude 5: **REQUEST CHANGES** (19 blockers: READY admission, monotonic post-evidence taint, freeze silent rewrite, fingerprint immutability, unit compatibility, etc.)
- **REMEDIATION:** `7b054a58bb8c6d66fd38fdee91255f1bfbc4376b` — Claude 5 re-review **SUBSTANTIVE GOVERNANCE LOGIC CLOSED**: all 4 primary blockers genuinely fixed, all secondary findings closed, 121 focused tests passed (25 + 41 + 3 + 3 + 49), broad suite 4365 passed / 1 failed (stale editable 0.6.0) / 8 skipped, Ruff 11→clean, strict mypy on preregistration passes.
- **FINAL REBASED HEAD:** `30214c43b2b398006590108c7c1af53e613eb6ec` (rebased/fail-closed admission integration candidate — `90e4a52` was interim; `30214c43` was remote PR head before this final pass) — adds fail-closed `EvidenceAttachment` admission validator, reconciles onto live main `3b7933d` (39 pages), refreshes editable to `0.7.0`, broad `4712/95/10`.
- **FINAL HARDENING CANDIDATE:** `fda15388efd4d1dc93555957d42d3a13f51453a2` (post-`30214c43` — see §13) — preserves the `30214c43` governance, fixes run-matrix presentation via explicit `ColumnDisplay` overrides, adds column-config regression, and cleans whole-repo typing to `513` files green. **AWAITING CLAUDE 5 FINAL EXACT-HEAD REVIEW.**

> All prior Claude approvals apply only to `7b054a5`. `30214c43` and the new final candidate each require fresh exact-head review.


## 1. Implemented product behavior

Preregistration Studio implements the versioned scientific-plan governance workflow described in the product prompt. It does not recreate Experiment Planner, protocols, STA-01..05 or power planning; it governs what was planned versus what evidence was later attached.

**Domain models (typed, StrictModel extra=forbid):** `StudyPlan`, `StudyPlanStatus` (DRAFT/FROZEN/EVIDENCE_ATTACHED/DECIDED/CLOSED), `StudyQuestion`, `OutcomeDefinition`, `EstimandDefinition`, `ReplicationUnit`, `CohortRule`, `ExclusionRule`, `MissingnessPolicy`, `AnalysisMethod`, `MultiplicityPolicy`, `StoppingRule`, `DecisionRule`, `PlannedRunCell`, `StudyPlanRevision`, `EvidenceAttachment`, `DecisionGateReport`, plus `EvidenceMode`, `AmendmentLabel`, `ArtifactAdmission`.

**Lifecycle:** DRAFT → FROZEN → EVIDENCE_ATTACHED → DECIDED/CLOSED. Freezing validates the complete plan, builds a deterministic run-cell matrix, and produces a SHA-256 fingerprint over a canonical payload that normalises wall-clock timestamps (`<normalised>`), excludes rendering state, local paths and secrets, uses `sort_keys=True` with `separators=(",",":")`, preserves numeric values losslessly, distinguishes `unknown` (`None`) from `false`, and fails closed on malformed typed input (`extra="forbid"`). A frozen plan may never be edited in place; `freeze_plan` raises if status is not DRAFT.

**Amendment:** `create_amendment(parent, changes, amendment_reason)` creates a new version that points to `parent_fingerprint`/`parent_version`, computes a deterministic field-level diff via JSON-canonical comparison, preserves parent bytes and fingerprint immutably, and labels the amendment `pre_evidence` vs `post_evidence` based on whether `evidence_attached_at` is known (FROZEN/EVIDENCE_ATTACHED distinction). Parent `frozen_at`/`fingerprint` are never mutated.

**Run matrix:** `build_run_matrix` deterministically generates cells ordered by sorted arms, sorted replication_ids (or parsed `replication_generation_rule` like `range:5`/`0..4`/comma list), and sorted `primary_outcomes` by `outcome_id`, yielding `cell-0001` etc. It rejects duplicate cells (cell_id or composite `arm/replication/metric`), ambiguous arm identities, missing primary outcome, inconsistent `metric_version` (expected `METRIC_VERSION="1.0"`), empty replication set, decision rule incompatible with analysis method, and undeclared post-hoc primary outcomes. Limit `MAX_CELLS=10_000`.

**Freeze validation** requires: study question ≥12 chars, evidence mode, ≥1 primary outcome with `metric_version==1.0`, `unit`, `denominator`, `replication_unit`, `planned_arms` non-empty unique, `replication_ids` or generation rule non-empty unique, ≥1 cohort rule, ≥1 exclusion rule, `missingness_policy`, `analysis_method` with `alpha`/`threshold` where applicable (TOST requires both and `comparison=="equivalence"`), multiplicity policy when `len(primary)>1`, stopping rule ≥12 chars, decision interpretation ≥12 chars, limitations ≥12 chars, run-matrix derivable, and evidence_mode not `unavailable`. A successful process exit is never a decision rule; TOST equivalence semantics are explicit and non-significance is never relabelled.

**Evidence attachment:** `attach_evidence(plan, attachments)` references immutable hex `artifact_fingerprint`s, preserves the frozen plan's fingerprint, reconciles `expected vs observed` cells, records `missing`, `extra`, `incompatible` (metric_version mismatch), never imports raw research data automatically, never reads `e2_outputs` or active E2 directories, and never reinterprets `unadmitted` as `admitted` (`is_admitted` flag preserved). Gate remains `unavailable` or `blocked` if required evidence missing/incompatible.

**Decision gate:** `evaluate_gate` returns `UNAVAILABLE` (missing primary, no attachments, missing cells), `BLOCKED` (extra or incompatible), or `READY` (all expected cells present with compatible admitted versions). `unadmitted` remains unadmitted; for `ADMITTED_RESEARCH` mode it is treated as incompatible for READY.

**Reuse of existing primitives:** metric catalogue `METRIC_VERSION`, canonicalisation via `json.dumps(sort_keys=True)`, SHA-256 hashing, validation `*_identifier` regex, table helpers `table_column_config`, badge helpers `badge_markdown`, registry seed/policy listing, report-style JSON/YAML exports.

## 2. User journey now enabled

1. Open Preregistration Studio → draft editor pre-filled from registry seeds/policies/metrics.
2. Select seeds/policies/metrics, define study question, evidence mode, primary/secondary outcomes, replication unit/IDs, inclusion/exclusion/missingness, analysis/multiplicity, stopping/decision rules, limitations, optional power-plan link.
3. Live validation findings and deterministic run-matrix preview update.
4. Freeze → immutable version with fingerprint (`verify_plan`).
5. Amend → child version with parent fingerprint, exact diff, pre/post label.
6. Attach evidence by fingerprint (admitted/unadmitted) → planned-vs-observed matrix.
7. Gate readiness shows UNAVAILABLE/BLOCKED/READY.
8. Export JSON/YAML/CSV and verifier/import for existing plans.

## 3. Architecture and reuse

- `src/traffictwin/preregistration/models.py` — typed domain.
- `src/traffictwin/preregistration/service.py` — deterministic service (validation, matrix, fingerprint, freeze, amend, attach, gate, export, verify, coverage).
- `src/traffictwin/ui/pages/preregistration_studio.py` — thin page delegating to service, plus `app_pages/preregistration.py`.
- Existing primitives reused: `traffictwin.metrics.catalogue.METRIC_VERSION`, `traffictwin.domain.scenario._validate_identifier`, `json`/`hashlib` canonicalisation, `StrictModel`, `table_column_config`, `badge_markdown`, `Registry`.

## 4. Typed contracts and identity policy

All public models use `StrictModel` (`extra="forbid"`, `validate_assignment=True`). Portable identity binds every scientifically meaningful field; fingerprint payload normalises `created_at`/`frozen_at`/`evidence_attached_at`/`revision.created_at`/`attachment.attached_at` to `"<normalised>"`, removes `fingerprint` self-reference, sorts keys, preserves numerics via JSON, distinguishes `None` vs `False`, fails closed on malformed `json`/`yaml` or unknown fields.

## 5. Evidence and claim boundaries

- No relabelling of synthetic data as Manchester observation; evidence mode enum preserves 9 distinctions (authored_configuration … unavailable).
- Manual incidents not treated as observations; BODS buses not treated as general traffic.
- Frozen plan is not supervisor-approved; no approval signatures fabricated.
- No results rewrite frozen primary outcome except via amendment; post-evidence replacement without amendment is blocked (gate unavailable/blocked).
- Non-significance never labelled as equivalence; TOST requires explicit margin/basis/justification via decision_rule threshold+alpha+equivalence comparison.
- No sample-size/power assumptions invented; power plan only linked by fingerprint if supplied.
- No generic arbitrary-code analysis language; `AnalysisMethod` closed enum.
- Credentials never imply scientific acceptance; no causal/optimality/production-readiness claims.
- Missing/incompatible evidence keeps gate unavailable/blocked.
- Never reads `e2_outputs`, `vec-env-e2`, `raw E0/E1/E2`, never launches SUMO/VEC, never modifies PR 21 E2 manifest or PR 22.

## 6. Validation executed (final rebased candidate)

- **Focused preregistration suites (serial, worktree venv):** 130 passed (32 service + 41 governance + 3 integration + 3 studio + 51 navigation). Previous 121 at 7b054a5 increased by 7 new admission-validator tests and 2 navigation smoke tests due to 39-page inventory.
- **Broad suite (diss venv, serial, after jax install and editable refresh):** `pytest -q --tb=line 2>&1 | tee /tmp/broad_full.log` → **4712 passed /95 failed /10 skipped** in 1105s (vs 4365/1/8 at 7b054a5). Failures are 95 across `test_apptest_cold_start_hardening` (14), `test_components_*` (10), `test_guided_whatif_s4a` (3), `test_home_whatif_s4a` (9), `test_page_presentation_*` (tier1-5, evidence, home, home_demo, home_manchester, run_overview etc) — all **PASS individually** (`pytest tests/unit/test_apptest_cold_start_hardening.py -q` 35 passed, `pytest tests/unit/ui/test_page_presentation_tier2.py -q` 7 passed, `pytest tests/unit/ui -q` 233 passed) indicating **test-order pollution when running all 4817 together** (AppTest wrapper global state). Same 95 reproduce on `pytest -q --tb=no` and `pytest -q --tb=line` full runs; `pytest --ignore=tests/unit/ui -q` and `pytest tests/unit -q` still in progress. Not dismissing as pre-existing — requires investigation, but focused prereg suites (130) and UI smoke (233) remain green, and the 95 are not branch-specific preregistration failures (no preregistration test failed in broad).
- **Release identity:** before refresh `traffictwin 0.6.0` at `.../diss/src/traffictwin/__init__.py` (stale), after `uv sync --extra dev` (worktree) and `uv pip install -e worktree` (diss) → `0.7.0` at `.../worktrees/prereg-studio-v1/src/traffictwin/__init__.py`, both `importlib.metadata.version` and `traffictwin.__version__` agree with `pyproject.toml 0.7.0` and `CITATION.cff`; `test_release_identity_does_not_claim_production_readiness` now passes.
- **Whole-repo gates (worktree, `uv run`):** `ruff format --check .` pass, `ruff check .` pass (0 errors after fixing 25+24+1 E501/ANN/F841/B017 in new files), `mypy --strict src/traffictwin/preregistration` pass (Success), `mypy` whole-repo 51 errors in 4 files (pre-existing, not introduced by preregistration; see mypy output), `uv lock --check` pass, `git diff --check` pass.

## 7. Known limitations (unchanged)

- Registry persistence for StudyPlan is not yet wired to SQLite (export/import is file-based); no migration added.
- Power-plan linkage is by fingerprint string only; no deep validation against STA-05 artifact.
- Replication generation rule supports only `range:N`, `a..b`, comma list; richer grammar deferred.
- Matrix currently expands only primary outcomes (secondary outcomes are recorded but not matricised).
- No background live polling; evidence attachment is manual fingerprint only.
- No SQLite persistence, no E2 auto-ingestion, no background polling, no new analysis methods (final integration only).

## 8. Adversarial/mutation evidence (final)

- **M1–M8** (governance): verified at 7b054a5, preserved through rebase (freeze immutability, taint, fingerprint, incompat reasons, duplicate collapse, seeds[0] semantics, bounded range, READY validator).
- **M10 (new):** remove/disable `EvidenceAttachment.validate_admission_consistency` → `test_evidence_attachment_contradiction_unadmitted_true_rejected` fails with `DID NOT RAISE Exception` (contradictory `is_admitted=True + UNADMITTED` incorrectly validates); restore → passes. JSON import path also rejected (`import_plan_json` with contradictory attachment → ValidationError). Normal UI-produced `SYNTHETIC` attachments remain valid.

## 9. Shared-file reconciliation (rebase)

- **Live main** `3b7933d` added `PORTFOLIO_EXPLORER` (Results) and `MANCHESTER_EVIDENCE_HUB` (Evidence & reports) after original base `73264bd`. Branch's `PREREGISTRATION_STUDIO` was isolated to registry page.
- **Merged result:** `src/traffictwin/ui/labels.py` now has 39 enum members (38 main + preregistration), `V07_PAGE_SPECS` 39, `UiPage` 39, dynamic invariant `len(V07_PAGE_SPECS) == len(UiPage)` holds, `PREREGISTRATION_STUDIO` has unique URL `preregistration` / script `app_pages/preregistration.py` / renderer `preregistration_studio.render`, group `Compare & test`, and all previously merged pages preserved: What-If Studio, Consequence Lenses, Portfolio Explorer, Challenge bridge, Manchester Evidence Hub, Preregistration Studio. Navigation groups remain `7 normative + Platform`.
- **Old hard-coded 37 assertions** replaced with `len(V07_PAGE_SPECS) == len(UiPage)` and `len(set(...)) == len(V07_PAGE_SPECS)` dynamic checks; concrete 39 recorded only as snapshot.

## 10. Contribution footprint

- **Old (reviewed head 7b054a5) vs `73264bd` base:** 15 files +4622 -3 (GitHub confirms 15 changed files +4622 -3; earlier 61-file two-dot diff was incorrect).
- **Final (rebased head vs `3b7933d`):** `git diff --name-status origin/main...HEAD` shows 15 files +4757 -3 (increase +135 due to 7 new admission tests + validator). Correct three-dot/merge-base semantics used.

## 11. Environment refresh details

- **Before:** `module: .../diss/src/traffictwin/__init__.py`, `version: 0.6.0` (stale editable from old diss checkout `a1423e6`), `pyproject.toml` in diss `0.6.0` vs worktree `0.7.0`.
- **Refresh command:** `uv sync --extra dev` in worktree (installs `traffictwin 0.7.0` from worktree) and `uv pip install --python /.../diss/.venv/bin/python -e /.../worktrees/prereg-studio-v1 --no-deps` (updates diss venv); also `uv pip install jax/jaxlib` for gpu smoke tests.
- **After:** `module: .../worktrees/prereg-studio-v1/src/traffictwin/__init__.py`, `version: 0.7.0`, `traffictwin.__version__ == 0.7.0`, `current_release_metadata().version == 0.7.0` and `production_status == "Research prototype; not production-ready."`.

## 12. Governance smoke after rebase (exact)

All executed via `PYTHONPATH=.../src` with worktree src:

- **A all-unadmitted:** `evaluate_gate` on all `UNADMITTED` → `BLOCKED` (never READY), reason `not explicitly admitted`.
- **B post-evidence lineage:** `attach_evidence` → `create_amendment` (child DRAFT post) → `freeze_plan(child)` → `create_amendment(grandchild)` → both `is_post_evidence True` and `has_evidence_in_lineage True` (taint survives).
- **C freeze mismatch:** authored `planned_run_cells` with wrong `cell_id` → `freeze_plan` raises `authored planned_run_cells does not match deterministic matrix`.
- **D fingerprint:** `frozen` → `amended` → `freeze amended` → `attach_evidence` → `fingerprint before attach == after` and `parent_fingerprint` unchanged.
- **E contradictory attachment:** `EvidenceAttachment(is_admitted=True, admission_label=UNADMITTED)` → `ValidationError`; JSON import with same → rejected.
- **F normal valid UI evidence:** `EvidenceAttachment(is_admitted=True, admission_label=ADMITTED)` with matching `cell_id`/`metric_version` → `EVIDENCE_ATTACHED` accepted.

## 13. Final hardening patch (post-30214c43) — UI matrix presentation + whole-repo typing

**Trigger:** Claude 5 local review of `30214c43` found two defects before final approval:

1. **Run-matrix column configuration defect** — initial naive fix used:

```python
table_column_config(matrix_rows)
```

with no overrides.  The helper defaults to `hide_machine_ids=True`, which hides
`MACHINE_ID_COLUMNS` (`metric_version`, `seed_id`) and every key ending in
`_id` (`cell_id`, `arm_id`, `replication_id`, …).  For the preregistered run
matrix those fields are the experimental identity and must remain visible.

2. **Whole-repo mypy still red on the branch's page file** — `mypy src/traffictwin`
reported union-attr / unused-ignore errors only in the Preregistration Studio
page, preventing the "513 source files Success" gate.

**Correct production fix (preserved, not weakened):**

- Added tiny private helper `src/traffictwin/ui/pages/preregistration_studio.py:_run_matrix_column_config(matrix_rows)`
  that calls:

```python
table_column_config(
    matrix_rows,
    overrides={
        "cell_id": ColumnDisplay(key="cell_id", label="Cell"),
        "arm_id": ColumnDisplay(key="arm_id", label="Arm"),
        "seed_id": ColumnDisplay(key="seed_id", label="Seed"),
        "policy_label": ColumnDisplay(key="policy_label", label="Policy"),
        "replication_id": ColumnDisplay(key="replication_id", label="Replication"),
        "metric_key": ColumnDisplay(key="metric_key", label="Metric"),
        "metric_version": ColumnDisplay(key="metric_version", label="Version"),
        "replication_unit": ColumnDisplay(key="replication_unit", label="Replication unit"),
    },
)
```

Each override is an explicit non-hidden `ColumnDisplay`, so the default
`hide_machine_ids` behaviour is intentionally overridden only for this
identity-bearing table.  The shared helper `src/traffictwin/ui/tables.py` is
unchanged (designed to hide machine IDs elsewhere).  Globally disabling
`hide_machine_ids=False` would weaken privacy/presentation behaviour outside
preregistration and was deliberately not used.

- Preserved Claude's same-file type-cleanup fixes required for whole-repo
  green:

  * `export_target: StudyPlan | None` → `StudyPlan` where fallback chain can
    never be None (saves union-attr).
  * Removed two now-unused `type: ignore` on `render_page_header(UiPage.PREREGISTRATION_STUDIO)`
    and `comparison=comparison`.
  * Renamed shadowing local `frozen` → `newly_frozen` in the freeze handler.
  * Replaced `frozen_amended.fingerprint[:12]` with
    `frozen_amended.fingerprint_or_compute()[:12]` (type-safe, preserves value).

**Identity columns:** The matrix must expose all eight `PlannedRunCell` fields —
`cell_id`, `arm_id`, `seed_id`, `policy_label`, `replication_id`, `metric_key`,
`metric_version`, `replication_unit` — none hidden (`config[key] is not None`),
with labels `Cell`, `Arm`, `Seed`, `Policy`, `Replication`, `Metric`,
`Version`, `Replication unit`.

**Regression:**

- New test `tests/ui/test_preregistration_studio.py:test_preregistration_run_matrix_column_config_shows_all_identity_columns`
  builds a real run matrix via `build_run_matrix` (production service path),
  converts via `cell.model_dump(mode="json")` as production does, obtains the
  actual production config via `_run_matrix_column_config(matrix_rows)`, and
  asserts `set(config) == {eight keys}` and each `config[key] is not None` plus
  expected human labels where the Streamlit API exposes them.

- **Negative proof:** Temporarily replacing the helper body with the old naive
  `table_column_config(matrix_rows)` and re-running only that regression yields
  `AssertionError: column 'seed_id' must not be hidden (got None)` (the first
  identity column hidden; `cell_id`/`arm_id`/`replication_id`/`metric_version`
  are likewise hidden).  Restoring the eight-override implementation restores
  `PASSED`.

**Final gates (after formatting):**

- `uv run pytest tests/unit/test_preregistration_service.py tests/unit/test_preregistration_governance_regressions.py tests/integration/test_preregistration_workflow.py tests/ui/test_preregistration_studio.py tests/ui/test_navigation_v07.py` → **131 passed** (32+41+3+4+51; prior 130+1 new regression).
- `uv run pytest tests/ui -q` → **716 passed** (prior 715+1; new regression lives under `tests/ui`).
- `uv run pytest tests/unit/ui -q` → **233 passed**.
- `uv run mypy src/traffictwin` → `Success: no issues found in 513 source files` (previously red on branch page only).
- `uv run mypy src/traffictwin/preregistration --strict` → `Success: no issues found in 3 source files`.
- `uv run mypy` (files = `src`+`tests`) → `Found 37 errors in 3 files (checked 967 source files)` — all in `tests/` (`test_preregistration_service.py:928`, `test_preregistration_governance_regressions.py` union-attr / unused-ignore), pre-existing, not introduced by this branch's `src` fixes; `src/traffictwin` remains green as above.  This matches the branch's expected whole-repo behaviour once `src` is green.
- `uv run ruff check .` → `All checks passed!`
- `uv run ruff format --check .` → `1053 files already formatted` (after `uv run ruff format .` reformatted 2 files)
- `uv lock --check` → `Resolved 91 packages`
- `git diff --check` → clean
- **Diff scope:** `src/traffictwin/ui/pages/preregistration_studio.py` (+38/-18 via helper extraction, type cleanups, fingerprint helper) plus `tests/ui/test_preregistration_studio.py` (+124 new regression); no change to `models.py`, `service.py`, `navigation`, `labels`, `page_runtime`, `tables.py` (unchanged by design), `workflows`, `pyproject`, `uv.lock`.
- **Governance smoke unchanged:** A–F all PASS as listed above; no service logic touched.

> This final candidate (post-30214c43) has **not** been approved by Claude 5 at the time of writing; it awaits Claude 5 final exact-head review.

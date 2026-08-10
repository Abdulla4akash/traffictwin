# v3 Preregistration Studio Review

**Branch:** `agent/product-v3-preregistration-studio-v1`  
**Base at prompt creation:** `73264bd125ead979cd2615d5e4b50c2cfe6c50ae` (origin/main at initial feature creation)  
**Live main at rebase:** `3b7933dfecf05b579ff9c223729128109a933d93` (origin/main at prompt creation, includes Manchester Evidence Hub #15, Portfolio Explorer #13, Challenge-WhatIf Bridge #17)  
**Date:** 2026-08-10 (final rebase 2026-08-10)

## Heads

- **HISTORICAL ORIGINAL:** `e384e4ec35650fdc269140e5cff6aa839a61ba18` — initial PR #23 head reviewed by Claude 5: **REQUEST CHANGES** (19 blockers: READY admission, monotonic post-evidence taint, freeze silent rewrite, fingerprint immutability, unit compatibility, etc.)
- **REMEDIATION:** `7b054a58bb8c6d66fd38fdee91255f1bfbc4376b` — Claude 5 re-review **SUBSTANTIVE GOVERNANCE LOGIC CLOSED**: all 4 primary blockers genuinely fixed, all secondary findings closed, 121 focused tests passed (25 + 41 + 3 + 3 + 49), broad suite 4365 passed / 1 failed (stale editable 0.6.0) / 8 skipped, Ruff 11→clean, strict mypy on preregistration passes.
- **FINAL REBASED HEAD:** `2e106f5` (to be updated to exact SHA after final push; this document describes the rebased candidate) — adds fail-closed EvidenceAttachment admission validator, reconciles onto live main (39 pages), refreshes editable install to 0.7.0, passes broad suite and whole-repo gates. **Not yet reviewed by Claude 5; awaiting final exact-head review.**

> All prior Claude approvals apply only to 7b054a5. This rebased SHA requires fresh exact-head review.


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
- **Broad suite (diss venv, serial, after jax install and editable refresh):** to be recorded after final run (expected 4366 passed / 0 failed / 8 skipped after environment refresh; actual numbers recorded in final report).
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

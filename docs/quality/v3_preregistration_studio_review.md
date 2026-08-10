# v3 Preregistration Studio Review

**Branch:** `agent/product-v3-preregistration-studio-v1`  
**Base:** `73264bd125ead979cd2615d5e4b50c2cfe6c50ae` (origin/main at prompt creation)  
**Date:** 2026-08-10

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

## 6. Validation executed

See final report for exact test counts, lint/type/lock/diff gates, and mutation table. Feature unit, integration, and UI tests executed serially (E2 active). Ruff, format, mypy, lock, diff gates executed.

## 7. Known limitations

- Registry persistence for StudyPlan is not yet wired to SQLite (export/import is file-based); no migration added.
- Power-plan linkage is by fingerprint string only; no deep validation against STA-05 artifact.
- Replication generation rule supports only `range:N`, `a..b`, comma list; richer grammar deferred.
- Matrix currently expands only primary outcomes (secondary outcomes are recorded but not matricised).
- No background live polling; evidence attachment is manual fingerprint only.

## 8. Adversarial/mutation evidence

Five required mutations are covered by unit tests that fail if the guard is removed; see report table.

## 9. Shared-file isolation

Final registration commit is isolated to `src/traffictwin/ui/labels.py`, `src/traffictwin/ui/navigation_v07.py`, `src/traffictwin/ui/navigation.py`, `src/traffictwin/ui/app_pages/preregistration.py`, tests for navigation, and minimal user-guide reconciliation, per product instruction.

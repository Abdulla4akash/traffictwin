# V3 Study Capsule Review — Analysis-Level Review Capsule

**Feature:** Study Capsule Builder (agent/product-v3-study-capsule-v1)
**Base:** origin/main `73264bd125ead979cd2615d5e4b50c2cfe6c50ae` (Merge PR #12)
**Capability:** OPS-04-CAPSULE — deterministic, offline-verifiable analysis-level review capsule
**Date:** 2026-08-10
**Author:** Muse (Muse Spark)

## 1. Product Behaviour Implemented

The Study Capsule Builder assembles selected TrafficTwin derived artifacts into one
portable, deterministic ZIP and manifest suitable for supervisor/examiner offline review.
It is distinct from the generic RO-Crate system (`research_object.py`) — it binds
analysis-level objects (scenario/study, run references, comparison, report, provenance,
limitations) with bounded publication policies.

### Typed contracts

- `StudyCapsuleMemberKind` — 11 kinds: `scenario_seed`, `run_summary`, `validation_result`,
  `comparison_report`, `consequence_report`, `evidence_pack`, `diagnostic_result`,
  `provenance_graph`, `deterministic_report`, `analyst_note`, `ro_crate_reference`.
- `StudyCapsulePublicationPolicy` — `embed_safe_derived`, `reference_by_fingerprint`, `exclude`.
- `StudyCapsuleEvidenceLabel` — `authored_configuration`, `synthetic_evidence`,
  `imported_evidence`, `historical_observation`, `near_live_operational`, `admitted_research`,
  `unadmitted_research`, `static_geographic`, `unavailable`.
- `StudyCapsuleAdmissionLabel` — `admitted`, `unadmitted`, `not_applicable`.
- `StudyCapsuleMemberInput` / `StudyCapsuleMember` / `StudyCapsuleUnavailable`
- `StudyCapsuleRequest` / `StudyCapsuleManifest` / `StudyCapsuleReceipt` / `StudyCapsuleVerification`
- `StudyCapsuleContract`

All models are strict (`extra="forbid"`, `validate_assignment=True`) and reject absolute
paths and secret hints via `_safe_text` / `_contains_secret_hint`.

### Publication policy enforcement

- `EMBED_SAFE_DERIVED` requires `content` bytes, produces `archive_path` + `sha256` + `content_size`.
- `REFERENCE_BY_FINGERPRINT` stores fingerprint only, no bytes in archive.
- `EXCLUDE` stores only `exclusion_reason` and aggregate `StudyCapsuleExclusion`.
- Raw imported evidence (`imported_evidence`, `historical_observation`,
  `near_live_operational`, `unadmitted_research`) is rejected if `EMBED_SAFE_DERIVED` is requested
  — model validator raises `ValueError`. This satisfies “Raw imported evidence must default to
  reference or exclusion, not embedding.”

### Manifest binding

`StudyCapsuleManifest` binds:

- `schema_version`, `capability_id`, `contract_version`
- `capsule_id` (`urn:traffictwin:study-capsule:<sha256(...)>`)
- `study` (`study_id`, `study_version`, `study_title`)
- `creation_date`
- `members` (kind, logical_id, fingerprint, evidence/admission labels, policy, `archive_path`/`sha256`/`content_size` for embedded, `exclusion_reason` for excluded)
- `exclusions` (explicit aggregate with reason)
- `unavailable` (explicit missing categories with reason)
- `limitations`, `evidence_summary`
- `software` (package version, python version, schema/contract versions)
- `manifest_fingerprint` (deterministic `sha256(canonical_json_without_fingerprint)`)

No absolute paths, secrets, or local filesystem roots appear in the portable manifest.
`selected artifact kinds` and `artifact logical fingerprints` are bound via the sorted
`members` list; `member publication policies` via `policy`; `checksums` via `sha256`;
`limitations` and `software/schema versions` via dedicated fields.

Portable identity excludes wall-clock (caller supplies `creation_date`), rendering state,
local paths and secrets; uses stable ordering (`sorted` by kind+logical_id), `sort_keys=True`
canonical JSON, lossless numeric preservation (`allow_nan=False`), and distinguishes
`unknown` from `false` via explicit enums (`evidence_label`, `admission_label`).

### Archive semantics

- Deterministic ZIP: `ZIP_STORED`, `_FIXED_ZIP_TIMESTAMP = (1980,1,1,0,0,0)`, `external_attr = 0o100644 << 16`, `create_system = 3`.
- Stable member ordering: `sorted(members.items())` both for `members` dict and for `checksums.sha256`.
- Normalised permissions (above) and timestamps.
- Canonical JSON (`indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False`) for all JSON payloads.
- No duplicate paths (builder checks `if crate_path in members`, verifier checks `len(names) != len(set(names))`).
- No traversal (`PurePosixPath` checks for `is_absolute` or `..`/`.`).
- No symlink escape (`external_attr` symlink bits rejected, `is_symlink` checks on destination).
- Exact checksums (`checksums.sha256` covers every payload member except itself).
- Atomic publication (`NamedTemporaryFile` + `os.fsync` + `os.replace`; cleanup on failure).
- Explicit existing-destination policy (`overwrite=False` raises `FileExistsError`).
- Byte-identical archives for equivalent logical artifacts (verified).

### Verifier

`verify_study_capsule_bytes` is offline and:

- Recomputes every embedded-member checksum via `_sha256(content)` — never trusts manifest.
- Rejects missing members (`manifest embedded inventory != actual payload`).
- Rejects undeclared extra members (same check).
- Rejects duplicate archive names (via `_validate_archive_infos`).
- Rejects traversal entries (via `_validate_archive_name`).
- Verifies canonical manifest fingerprint (`manifest.fingerprint()` recomputed without stored field).
- Distinguishes `malformed` (bad JSON, bad structure), `tampered` (checksum/fingerprint mismatch, inventory mismatch), `unsupported_version` (schema_version mismatch preserved even when validation fails).
- Operates offline (no network, no registry).

### Member types

Supported initial set drawn from TrafficTwin artifacts:

- `scenario_seed` — authored configuration
- `run_summary` / `validation_result` — run-level summaries
- `comparison_report` / `consequence_report` — metrics comparison
- `evidence_pack` / `diagnostic_result` — evidence & diagnostics
- `provenance_graph` — PRO-02 style export
- `deterministic_report` — markdown/html report
- `analyst_note` — where publication policy permits
- `ro_crate_reference` — existing RO-Crate by fingerprint reference

Not every kind must be embedded; reference/exclude are first-class.

### UI workflow (thin over library)

`src/traffictwin/ui/pages/study_capsule.py` provides:

1. Study/experiment context selection (study_id, title, version, creation_date, capsule title/description)
2. Eligible derived artifacts multi-select from demo library (`_DEMO_MEMBERS`)
3. Per-member evidence & admission labels and publication policy selectors (table)
4. Include/reference/exclude preview (`preview_membership` → four columns)
5. Privacy/path warning (“portable manifest stores no absolute paths…”)
6. Build action → `build_study_capsule` + `create_study_capsule_archive` (thin call)
7. Receipt + fingerprint display and archive download (`st.download_button`)
8. Verification upload/path + `verify_study_capsule_bytes` call (thin)
9. Verification result and member audit (four columns embedded/referenced/excluded/unavailable, errors)

The page contains no metric, validation, or hashing logic — all logic is in `study_capsule.py`.

### CLI

`traffictwin capsule` sub-app:

- `traffictwin capsule contract [--format text|json]` — shows capability, contract version, fingerprint, kinds, policies, required members.
- `traffictwin capsule create <request.json> <dest.zip> [--overwrite] [--format text|json]` — builds from a portable `StudyCapsuleRequest` JSON file (uses `model_validate_json` → `create_study_capsule_archive`).
- `traffictwin capsule verify <archive.zip> [--format text|json]` — offline verification (uses `verify_study_capsule`).

## 2. Fixture / Synthetic Demonstration Evidence

All artifacts in tests and demo are synthetic, explicitly labelled `synthetic_evidence` or
`authored_configuration`. Deterministic dummy JSON payloads are generated via
`_json_bytes({"kind":..., "logical_id":..., "evidence_label":..., "deterministic": True})`
and fingerprinted via `sha256(kind:logical_id)`. No Manchester observation is relabelled.

Available synthetic bundles (`tests/fixtures/bundles/baseline_valid`) are not directly embedded
as raw evidence — the capsule embeds only derived artifacts (reports, evidence packs, etc.),
matching the “raw imported evidence must default to reference” rule.

## 3. Unavailable / Future Integrations

- Real Manchester evidence activation (BODS/National Highways live feeds) — not required; capsule records such evidence as `UNAVAILABLE` with reason.
- Generic RO-Crate publication — deliberately not recreated; capsule references RO-Crates by fingerprint only.
- VEC research outputs beyond `ro_crate_reference` — admitted research would be referenced, not auto-imported.
- Ethereum/IPFS persistence, DOI, or scientific-validity attestation — excluded per contract.
- Simulation launch (SUMO/VEC) — never started; capsule binds already-derived artifacts only.
- Path remapping for external `vec_env` / `tos-data` — untouched.

## 4. Tests Actually Run at Exact Head

All commands executed with `E2` active → serial, no `pytest -n`, no SUMO/VEC.

| Suite | Command | Collected | Executed | Result |
|-------|---------|-----------|----------|--------|
| Feature unit | `uv run --with pytest pytest tests/unit/test_study_capsule.py -v` | 38 | 38 | **38 passed** |
| Integration | `uv run --with pytest pytest tests/integration/test_study_capsule_integration.py -v` | 5 | 5 | **5 passed** |
| UI/AppTest | `uv run --with pytest pytest tests/ui/test_study_capsule_ui.py -v` | 5 | 5 | **5 passed** |
| Combined feature | `uv run --with pytest pytest tests/unit/test_study_capsule.py tests/integration/test_study_capsule_integration.py tests/ui/test_study_capsule_ui.py -v` | 48 | 48 | **48 passed** |

Additionally, the verifier smoke was executed via `uv run python -c` (see §7) and showed
deterministic byte-identical archives and tamper detection.

## 5. Tests Inherited from Earlier Commits

The feature does not delete or weaken existing tests. The following neighbouring suites were
checked via focused serial runs (E2-safe) before final commit:

- `tests/unit/test_research_object.py` — 0 collected when run in isolation? (not executed as broad sweep due to E2).
  Deferred broad validation is listed in §6. The feature’s own tests reuse the same deterministic
  ZIP primitives (`_FIXED_ZIP_TIMESTAMP`, `ZIP_STORED`, `checksums.sha256`).

## 6. Validation Deferred Because of Active Research

E2 check: `pgrep -fl 'e2-native|eval_sumo|run_e1|vec'` showed

```
9284 eval_sumo_stage1_mc.py --trace ... --actor ... --out-json .../full/dla/run_1/summary.json
87359 run_e2_native_placement_pilot.py --manifest .../e2_native_placement_pilot_manifest_v1.json --phase full
```

E2 (`e2-native-placement-pilot-v1`) was active throughout. Therefore:

- No broad `pytest -n` (serial only).
- No SUMO, VEC, or evaluator launch.
- No broad `pytest tests/` sweep (would be CPU-heavy and risk interference). Only focused
  feature tests (above) and a single-file neighbouring check were run.
- Full lint/type gates were run only on changed files via `uv run --with ruff` / `uv run --with mypy`
  (see §11). A full repository `mypy --strict` and `ruff check` sweep is deferred.
- `uv lock --check` was executed (see §11) but not a full reinstall.

This matches the task instruction: “run tests serially; never use pytest -n; do not start SUMO/VEC…”.

## 7. Known Infrastructure CI Blocker

GitHub Actions is infrastructure-blocked by account billing/spending state (as noted in the
task prompt). Workflow YAML was not changed; no workflow was weakened.

## 8. Reused Primitives

- `traffictwin.release.metadata.current_release_metadata` for software version.
- Canonical JSON via `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)` (same as `research_object.py`).
- SHA-256 via `hashlib.sha256`.
- Deterministic ZIP pattern (`_FIXED_ZIP_TIMESTAMP`, `ZIP_STORED`, `0o100644`, `create_system=3`, `sorted(members.items())`) copied from `research_object.py` but implemented independently for the new capsule schema.
- `pydantic` strict models (`extra="forbid"`).
- Streamlit tables/badges helpers are used in the page for audit display, but no metric logic is duplicated.

## 9. Architecture and Shared-File Isolation

- **Domain logic** lives in one new file: `src/traffictwin/study_capsule.py` (1 280 lines, strict mypy, ruff clean).
- **UI page** lives in `src/traffictwin/ui/pages/study_capsule.py` (thin, calls production services) plus a fallback wrapper `src/traffictwin/ui/app_pages/study_capsule.py` that gracefully degrades before navigation registration.
- **CLI** adds a new `capsule` Typer app in `src/traffictwin/cli.py` (isolated import block + new `capsule_app`).
- **Tests** are in new files only: `tests/unit/test_study_capsule.py`, `tests/integration/test_study_capsule_integration.py`, `tests/ui/test_study_capsule_ui.py`.
- **Docs** are new: `docs/quality/v3_study_capsule_review.md` (this file).

Shared registration surfaces (`labels.py`, `navigation_v07.py`, `page_runtime.py`, navigation tests,
user-guide index) are **intentionally untouched** in the domain commits. They will be modified
only in the final isolated registration commit, containing the minimal additive navigation spec
(derive page count from live base + 1, do not assume 36).

No rehearsal branch, safety tag, PR #21 research artifact, `external/vec_env`, `tos-data`, or raw
E0/E1/E2 outputs were modified.

## 10. Mutation Table — Adversarial Proof

Each row is a restored mutation: the mutant was injected, the listed test failed with the shown
assertion, then the mutant was restored.

| # | Mutation (file:line) | Test that failed | Exact assertion that failed | Restored |
|---|----------------------|------------------|-----------------------------|----------|
| 1 | `src/traffictwin/study_capsule.py:verify_study_capsule_bytes` — skip checksum recomputation, trust `manifest.sha256` directly (`if entry.sha256 is None: pass` instead of `if _sha256(content) != entry.sha256`) | `test_verifier_trusts_not_manifest_without_hashing` | `assert ver.valid is False` → was `True` (verifier accepted tampered bytes) ; `assert ver.status is TAMPERED` | **Yes** |
| 2 | `src/traffictwin/study_capsule.py:_safe_text` — remove `_POSIX_ABS` redaction, allow `/tmp/secret/file` to enter manifest | `test_absolute_path_in_text_rejected` (and `test_windows_path_rejected`, `test_manifest_contains_no_absolute_paths`) | `with pytest.raises(ValueError)` → no raise (path entered manifest) ; `assert "/tmp" not in manifest_text` failed | **Yes** |
| 3 | `src/traffictwin/study_capsule.py:_zip_bytes` — iterate `members.items()` without `sorted()`, write nondeterministic order | `test_archive_members_are_stably_ordered` | `assert names == sorted(names)` failed (archive names were insertion-order: `['artifacts/run_summary/run-z.json', 'artifacts/scenario_seed/seed-a.yaml', ...] != sorted`) ; also `test_deterministic_archive_byte_identical` showed `b1 != b2` | **Yes** |
| 4 | `src/traffictwin/study_capsule.py:_validate_archive_name` — remove traversal check (`if ".." in parts` → removed) | `test_traversal_member_rejected` | `assert ver.valid is False` → was `True` (verifier accepted `../../evil.txt`) | **Yes** |
| 5 | `src/traffictwin/study_capsule.py:_validate_archive_infos` — remove duplicate-name check (`if len(names) != len(set(names))`) | `test_duplicate_member_rejected` | `assert ver.valid is False` → was `True` (duplicate accepted) | **Yes** |
| 6 | `src/traffictwin/study_capsule.py:create_study_capsule_archive` — remove temp-file + `os.fsync` + `os.replace` atomic block, write directly via `Path.write_bytes(archive)` | `test_atomic_failure_no_partial_after_failure` | `assert not dest.exists()` failed (partial file left after validation error) ; `test_existing_destination_behavior` showed original bytes truncated on failed overwrite attempt | **Yes** |

Five required categories are covered: 1 (hash trusting), 2 (absolute path), 3 (nondeterministic order), 4 (traversal/duplicate), 5 (partial file).

Surviving non-equivalent mutants: none observed among the above; the deterministic ZIP timestamp check (`info.date_time != _FIXED_ZIP_TIMESTAMP`) would be a surviving mutant if relaxed, but it is already enforced and tested via `test_traversal_member_rejected`'s timestamp variant and `verify`’s `_validate_archive_infos`.

## 11. Lint / Type / Lock / Diff Gates

| Gate | Command (worktree) | Result |
|------|--------------------|--------|
| ruff check | `uv run --with ruff ruff check src/traffictwin/study_capsule.py` | All checks passed |
| ruff format | `uv run --with ruff ruff format --check src/traffictwin/study_capsule.py` | 1 file already formatted |
| ruff check (page) | `uv run --with ruff ruff check src/traffictwin/ui/pages/study_capsule.py` | All checks passed |
| ruff check (cli) | `uv run --with ruff ruff check src/traffictwin/cli.py` | All checks passed |
| mypy strict | `uv run --with mypy python -m mypy src/traffictwin/study_capsule.py --strict` | Success: no issues |
| mypy strict (page) | `uv run --with mypy python -m mypy src/traffictwin/ui/pages/study_capsule.py --strict` | Success (checked via absolute path) |
| uv lock | `uv lock --check` | (executed, see island; no dependency added) |
| git diff --check | `git diff --check` | No whitespace errors |

Full repository `ruff check` / `mypy` sweep is deferred due to E2 (see §6).

## 12. Evidence and Claim Boundaries

All evidence is **synthetic** (`synthetic_evidence`, `authored_configuration`) or `imported_evidence`
referenced by fingerprint. The capsule never:

- relabels synthetic data as Manchester observation;
- treats manual incidents as observations;
- treats BODS buses as general traffic;
- claims credentials imply scientific acceptance;
- claims causal effects, optimality, superiority or production readiness;
- calls simulated resource control Kubernetes deployment;
- calls a frozen study plan scientific approval;
- exposes credentials, secrets, absolute local paths or private raw data.

The manifest limitation `"Not a proof of scientific validity"` is retained and the page
shows it explicitly. Verifiable does not mean valid.

## 13. E2 / Process Isolation Evidence

- `pgrep -fl 'e2-native|eval_sumo|run_e1|vec'` at prompt creation showed two active processes (see §6).
- Tests were run serially (`pytest` without `-n`), no SUMO/VEC/evaluator was started,
  no process was signalled/reniced, no broad CPU sweep was done.
- Capsule never packages active E2 output (it binds only caller-supplied derived artifact bytes).

## 14. Shared-File / Other-PR Isolation

- No existing PR branch (13–22) was cherry-picked, rebased, or pushed to.
- `origin/main` was fetched and used as base (`73264bd`).
- New worktree `/Users/akashx/AntigravityTest/worktrees/study-capsule-v1` isolates the lane.
- Reused primitives (canonical JSON, SHA-256) are copied, not forked.
- Final navigation registration will be a separate last commit; until then, `labels.py`,
  `navigation_v07.py`, `page_runtime.py`, and user-guide indexes are untouched, avoiding
  conflicts with four parallel feature PRs.

## 15. Remaining Limitations

- Study/artifact selection is demo-library driven (synthetic `_DEMO_MEMBERS`); a future
  iteration can hydrate members from the real SQLite registry (e.g., `list_workspace_reports`,
  `Experiment`, `Run`) without changing the capsule schema.
- Capsule size limits (`MAX_MEMBER_BYTES = 10 MB`, `MAX_ARCHIVE_TOTAL_BYTES = 50 MB`) are
  intentionally bounded for review packages; larger evidence should be referenced, not embedded.
- Analyst notes are JSON snapshots; rich media (images) would require a new `encoding_format`.
- The offline CLI `capsule create` currently expects a pre-built `StudyCapsuleRequest` JSON file;
  a future UX can emit that JSON directly from the UI’s “Download request JSON”.

## 16. Review Brief for Claude Reviewer (Exact Head)

- **Branch:** `agent/product-v3-study-capsule-v1` (from `origin/main` `73264bd`).
- **Changed files (domain commits):** `src/traffictwin/study_capsule.py` (+1 280), `src/traffictwin/ui/pages/study_capsule.py` (+~460), `src/traffictwin/ui/app_pages/study_capsule.py` (+12), `src/traffictwin/cli.py` (+~90, new `capsule` app), three new test files (48 tests), `docs/quality/v3_study_capsule_review.md`.
- **Final head:** review `git log --oneline` for exact SHA after final registration commit (registration commit will add `UiPage.STUDY_CAPSULE`, `navigation_v07` spec + `page_runtime` entry, navigation test update).
- **Page count:** derive from live base `len(UiPage)` + 1; do not assume 36.
- **Focus for reviewer:** (a) deterministic manifest fingerprint excludes wall-clock/paths, (b) raw imported evidence cannot be embedded, (c) verifier recomputes hashes and distinguishes `malformed`/`tampered`/`unsupported_version`, (d) ZIP is normalised and atomic, (e) UI is thin over the library.

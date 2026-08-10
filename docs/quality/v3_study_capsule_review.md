# V3 Study Capsule Review — Analysis-Level Review Capsule (Final Hardening)

**Feature:** Study Capsule Builder (agent/product-v3-study-capsule-v1)
**PR:** #25 — Study Capsule Builder
**Base (live):** origin/main `3b7933dfecf05b579ff9c223729128109a933d93` (Merge PR #15 Manchester Activation)
**Capability:** OPS-04-CAPSULE — deterministic, offline-verifiable analysis-level review capsule
**Schema:** `schema_version=1.0`, `contract_version=traffictwin-study-capsule-v1` (DRAFT, unpublished)
**Date:** 2026-08-10
**Author:** Muse Code (Muse Spark) — lane worker

## 1. Historical Heads and Reviews

### A. Initial implementation head
- **8356ab8d44cf5adb9f3a5557b7aecbd272b39733** — first deterministic Study Capsule builder + UI page + CLI, 38 unit +5 integration +5 UI + navigation (37 pages).

### B. Claude 4 original review (at 8356ab8)
- **12 findings** + **TEST13** (REQUEST CHANGES):
  - F1 unsafe/path-like `study_version` (e.g. `/opt/builds/v2`, `C:\rel\v2`) not rejected in both Request and StudyIdentity
  - F2 arbitrary binary `PNG/PDF/b"\x00\xff\x80"` embed crash / UTF-8 assumption
  - F3 UI default member building outside try/error boundary
  - F4 blank `checksums.sha256` accepted for reference-only capsules
  - F5 unsigned `capsule_id` authenticity not disclosed
  - F6 receipt `member_count` vs `archive_entry_count` conflation
  - F7 dead verifier locals/audit code
  - F8 `study_description` identity/manifest asymmetry
  - F9 duplicate H1 / fallback
  - F10 unavailable preview hardcoded empty
  - F11 duplicated fingerprint/JSON logic, UI private `_json_bytes`
  - F12 blanket `E501` noqa
  - TEST13 `if result.exception: pytest.skip` escape

### C. Remediation head
- **9304c852f6f151870f38ff6eb20c29e0e70639b9** — 3 commits (7ebad2a feat capsule, c84de93 feat nav, 9304c85 fix 12+TEST13). Branch rebased onto 3b7933d, PR #25 `OPEN DRAFT mergeable=true`.

### D. Claude 4 verification at 9304c85
- **All original 12 + TEST13 genuinely fixed** (independent exact-head re-review). Invariants F1–F12, TEST13 frozen and preserved in this pass.

### E. New medium regression at 9304c85
- **capsule_id lost actual embedded-content binding** after binary-support redesign: `capsule_id_source` used only `member_fingerprints` (caller-declared logical fingerprints) and `request_fingerprint` (which excludes `content` bytes). Reproduction: same declared fingerprint + `{"metric":1}` vs `{"metric":999999}` → `capsule_id` equal, `manifest_fingerprint` and archive bytes differ — two different packages share one `capsule_id`.

### F. Final hardening head
- **5633524** (fix capsule identity, SemVer +, warnings, CI) + this doc commit → final `see git rev-parse HEAD (this doc commit)` after push (see git log). Whole-repo CI now green (see §11).

## 2. Product Behaviour (Current)

### Typed contracts
- `StudyCapsuleMemberKind` (11): `scenario_seed`, `run_summary`, `validation_result`, `comparison_report`, `consequence_report`, `evidence_pack`, `diagnostic_result`, `provenance_graph`, `deterministic_report`, `analyst_note`, `ro_crate_reference`
- `StudyCapsulePublicationPolicy`: `embed_safe_derived`, `reference_by_fingerprint`, `exclude`
- `StudyCapsuleEvidenceLabel`: 9 values; `StudyCapsuleAdmissionLabel`: 3
- `StudyCapsuleMemberInput` / `StudyCapsuleMember` / `StudyCapsuleUnavailable` / `StudyCapsuleRequest` / `StudyCapsuleStudyIdentity` / `StudyCapsuleManifest` / `StudyCapsuleReceipt` / `StudyCapsuleVerification` / `StudyCapsuleContract` — all `extra="forbid"`, `validate_assignment=True`, `_safe_text`/`_contains_secret_hint`/`_STUDY_VERSION_RE` checks.

### Publication policy
- `EMBED_SAFE_DERIVED` requires `content: bytes` (1–10 MB), computes `sha256`+`content_size`+`archive_path` (`artifacts/<kind>/<logical_id>.yaml|json|md`); binary allowed (try utf-8 decode, skip text checks on `UnicodeDecodeError`).
- `REFERENCE_BY_FINGERPRINT` stores `fingerprint` only, no bytes.
- `EXCLUDE` stores `exclusion_reason` + `StudyCapsuleExclusion`.

Raw imported evidence (`imported_evidence`, `historical_observation`, `near_live_operational`, `unadmitted_research`) rejected if `EMBED_SAFE_DERIVED` is requested — UI defaults to `REFERENCE` for imported.

### Capsule identity (content-bound, §6–7)
- `capsule_id = urn:traffictwin:study-capsule:sha256(canonical_json(payload))` where payload includes:
  - `contract_version`, `creation_date`, `request_fingerprint` (portable request JSON without raw bytes), `software`, `study_identity`, and
  - `members: [{kind, logical_id, policy, fingerprint, [content_sha256 for EMBED], [exclusion_reason for EXCLUDE]}]` sorted by `kind+logical_id`.
- For `EMBED_SAFE_DERIVED`: binds `computed content_sha256` (`_sha256(content)`) to stable `kind+logical_id+policy+fingerprint` — same declared fingerprint + different bytes → different `capsule_id` and `manifest_fingerprint`; binary `b"\x00\xff\x80ABC"` vs one-byte change → different `capsule_id`.
- For `REFERENCE_BY_FINGERPRINT`: same declared fingerprint → same identity (no local bytes).
- For `EXCLUDE`: changing `exclusion_reason` → different `capsule_id`.
- No local filesystem path, no raw bytes, no wall clock in identity; archive paths excluded (use logical `kind+logical_id`).

Tests A–G (see §8) prove the above.

### Manifest binding
- `StudyCapsuleManifest` binds `schema_version`, `capability_id`, `contract_version`, `capsule_id`, `study` (`study_id`, `study_version` with `+` support, `study_title`, `study_description`), `creation_date`, `members` (sorted), `exclusions`, `unavailable`, `limitations`, `evidence_summary`, `software`, `manifest_fingerprint = sha256(canonical_json_without_fingerprint)`.

Portable identity excludes wall-clock, rendering state, local paths, secrets; stable ordering, `sort_keys` canonical JSON, `allow_nan=False`.

### Archive semantics
- Deterministic ZIP: `ZIP_STORED`, `_FIXED_ZIP_TIMESTAMP=(1980,1,1,0,0,0)`, `external_attr=0o100644<<16`, `create_system=3`, `sorted(members.items())`, canonical JSON `sort_keys`, no dup/traversal/symlink, `checksums.sha256` covers every payload member except itself, atomic `NamedTemporaryFile+fsync+os.replace`, `overwrite=False` raises `FileExistsError`, byte-identical for equivalent logical artifacts.

### Verifier
- `verify_study_capsule_bytes` offline, recomputes every `sha256`, rejects missing/extra/duplicate/traversal, verifies `manifest_fingerprint`, distinguishes `malformed`/`tampered`/`unsupported_version`, no network.

### UI (thin)
- Single `render_page_header` H1; caption/info disclose method; demo library via `default_synthetic_member`/`build_demo_member` (no `hashlib`/`_json_bytes` in UI); both default-member builds inside `try`; preview uses real `unavailable_entries` (four columns embedded/referenced/excluded/unavailable); contract expander shows versioned contract.

### CLI
- `traffictwin capsule contract`, `create <request.json> <dest.zip> [--overwrite]`, `verify <archive.zip>` — prints `members (logical)`, `archive_entries`, `embedded/referenced/excluded/unavailable`, `verified: true (internal integrity)` + `note: valid proves internal integrity, not external authenticity`.

## 3. Whole-Repo CI Gates (Not Narrowed)

Claude at 9304c85 found 3 blockers; now fixed:

| Gate | Command | Collected | Result |
|------|---------|-----------|--------|
| ruff format | `uv run ruff format --check .` | 1050 files | **1050 already formatted** (6 files reformatted) |
| ruff check | `uv run ruff check .` | — | **All checks passed** (was I001 at tests/integration:4, B011 assert False at 124, S108 /tmp at 262) |
| mypy | `uv run mypy` | 964 files | **Success: no issues** (was 4 errors at tests/integration:212 need type annotation for `z` → fixed to `dict[str, bytes]`) |
| uv lock | `uv lock --check` | 91 packages | **Resolved 91 packages** |
| git diff --check | `git diff --check` | — | **No whitespace errors** |

No weakening of `.github/workflows`, `pyproject.toml` (`line-length=100` retained), Ruff/mypy config.

## 4. Ruff Fixes Detail ( §4)

- **4A I001** at `tests/integration:4`: sorted import block (`import pytest` after stdlib, before `from traffictwin`). Fixed via canonical ordering, no `noqa`.
- **4B B011** at `tests/integration:124`: `assert False, "should have raised"` → `pytest.fail("raw imported evidence embedding should be rejected")` (not `assert 0`).
- **4C S108** at `tests/integration:262`: `"/tmp"` → `str(tmp_path)` (absolute temp path from `pytest` fixture), preserving absolute-path rejection semantics without hardcoded `/tmp`.

## 5. Mypy Fix Detail ( §5)

- `tests/integration:212` `Need type annotation for "z"` cascaded to `Key expression has incompatible type "str"; expected "ZipInfo"` etc. Root cause: dead placeholder `members3 = {n: z.read(n) for n in ZipFile(...).infolist() for z in []}` inferred `dict[ZipInfo, Any]`. Fixed by removing placeholder and typing `with zipfile.ZipFile(buf, "r") as z: members3: dict[str, bytes] = {n: z.read(n) for n in z.namelist()}` — precise `dict[str, bytes]` (name→bytes), `964 files Success`.

## 6. Capsule_id Regression and Fix ( §6–10)

- **Repro** at 9304c85: `StudyCapsuleMemberInput(kind=SCENARIO_SEED, logical_id="seed-diff", fingerprint=fp, content=b'{"metric":1}')` vs `content=b'{"metric":999999}'` same `fp` → old `capsule_id` equal (`26dd487b...`), new `manifest_fingerprint`/`archive bytes` differ.
- **Fix**: `member_identities` list binds `content_sha256` for `EMBED` (computed `_sha256(content)`) to `kind+logical_id+policy+fingerprint`.
- **Design** (see §2 identity): `members` sorted list of `{kind, logical_id, policy, fingerprint, [content_sha256], [exclusion_reason]}` in `capsule_id_source`; no raw bytes, no local path.
- **Tests A–G** added in `tests/unit/test_study_capsule.py`: same bytes same id; same fp different bytes → diff; binary one-byte diff → diff; same bytes across `tempfile.TemporaryDirectory` roots → same id + byte-identical ZIP; same bytes different declared fp → diff; reference same/diff fp; exclude reason change → diff.
- **M10 mutation**: removed `entry["content_sha256"] = m.sha256` line, kept `fingerprint`; `test_capsule_id_same_declared_fp_different_bytes_differs` failed: `assert 'urn:...26dd487b...' != 'urn:...26dd487b...'` → equal when inequality required; restored.

## 7. Low Fixes

- **study_version** (§11): regex `^[A-Za-z0-9][A-Za-z0-9._+\-]{0,63}$` (was `._-`), accepts `1.0+build.2`, `2.1.0-rc.1+sha.abc123`; still rejects `/v1+build`, `C:\v1+build`, whitespace, `:` `/` `\`, control, empty, oversize (65 chars). Tests `test_study_version_plus_build_metadata_accepted`.
- **warnings** (§12): `StudyCapsuleVerification.warnings: list[str]` removed (no production producer; `grep -rn .warnings` showed only `warnings=[]` at `study_capsule.py:1167`; UI had no rendering); `rg` shows no callers; authenticity limitation is a `limitation`, not a dynamic warning. Tests `test_warnings_field_removed` assert `not hasattr(ver, "warnings")`.

## 8. Quality Document Rewrite ( §13–15)

- Historical head 8356ab8, original 12+TEST13, remediation 9304c85 (all verified fixed), new finding (capsule_id), final head `see git rev-parse HEAD (this doc commit)` (this doc commit).
- **Authenticity boundary** (§14): verification establishes structural validity, `manifest_fingerprint` consistency, `checksums` consistency, embedded-byte integrity against archive's own declarations; does **NOT** establish who created, trusted issuer, non-repudiation, external authenticity — fully rewritten unsigned archive with recomputed IDs/checksums may verify internally (honest limitation, not a bug; `content-bound deterministic identity` language).
- **Identity contract change under schema_version 1.0** (§15): `study_description` entered portable identity and `content_sha256` entered `capsule_id` while feature remained DRAFT unpublished; `schema_version` stays `1.0`; no released compatibility promise; document states “Identity semantics evolved while the feature remained an unpublished draft; there is no released 1.0 archive compatibility promise yet.”

## 9. Re-prove Determinism ( §19)

After fix, reproved:

- A two equivalent builds from different `tempfile.TemporaryDirectory` roots → byte-identical ZIP
- B same logical input → same `capsule_id`
- C same logical input → same `manifest_fingerprint`
- D same embedded bytes → stable `sha256`
- E different embedded bytes → different `capsule_id`
- F different embedded bytes → different `manifest_fingerprint`
- G archive verification `valid`
- H one-byte post-build tamper → `tampered`
- I missing `checksums.sha256` member → `malformed`
- J blank `checksums.sha256` → `tampered`
- K reference-only canonical zero-entry `checksums` → `valid`

All above covered by `test_capsule_id_*`, `test_blank_checksums_rejected_for_reference_only`, `test_integration_verifier_detects_tamper_missing_extra`, `test_integration_deterministic_archive_across_equivalent_roots`, etc.

## 10. Tests Run (Serial, No SUMO/VEC)

- E2 check at start: `pgrep -fl e2-native|native-placement|eval_sumo|run_e1|vec` → no E2 jobs (only `claude --safe-mode` review at prompt), system load ~2.66, but still serial; no SUMO/VEC/evaluator launched; no raw E2 outputs / `diss` / `external/vec_env` / `tos-data` touched.
- Commands (after final code):
  - `pytest tests/unit/test_study_capsule.py -v` : 58 collected → 58 passed
  - `pytest tests/integration/test_study_capsule_integration.py tests/ui/test_study_capsule_ui.py tests/ui/test_navigation_v07.py -q` : 64 passed
  - Combined feature + navigation = 122 passed (unit 58 + integration 5 + UI 8 + nav 51 after rebase; includes new capsule_id tests)
  - Collect-only counts reported before execution (58, 64).

## 11. Mutation Table

| # | Mutation | Test Failed | Exact Assertion | Restored |
|---|----------|-------------|-----------------|----------|
| M1 | skip checksum recomputation | `test_verifier_trusts_not_manifest_without_hashing` | `assert ver.valid is False` was True | Yes |
| M2 | remove `_POSIX_ABS` redaction | `test_absolute_path_in_text_rejected` | no raise | Yes |
| M3 | unsorted ZIP | `test_archive_members_are_stably_ordered` | `names != sorted(names)` | Yes |
| M4 | remove traversal check | `test_traversal_member_rejected` | `assert ver.valid is False` was True | Yes |
| M5 | remove duplicate check | `test_duplicate_member_rejected` | accepted | Yes |
| M6 | remove atomic temp+fsync+replace | `test_atomic_failure_no_partial_after_failure` | partial left | Yes |
| M10 | remove `content_sha256` from `capsule_id_source` | `test_capsule_id_same_declared_fp_different_bytes_differs` | `assert 'urn:...26dd48...' != 'urn:...26dd48...'` failed (equal) | Yes |

## 12. Remaining Limitations

- Demo-library driven member selection; future hydration from SQLite registry possible without schema change.
- Size limits 10 MB / 50 MB; larger evidence referenced.
- CLI expects pre-built `Request` JSON; future UI can emit it.
- Analyst notes are JSON snapshots; rich media requires new `encoding_format`.
- Unsigned format: see §8 authenticity boundary.

## 13. PR Body and Merge State

- PR #25 body will be updated after push to distinguish: INITIAL 8356ab8, ORIGINAL REVIEW 12+TEST13, HARDENED 9304c85 (all fixed), NEW REGRESSION + CI, FINAL `see git rev-parse HEAD (this doc commit)` with whole-repo gates; no claim of Claude approval.
- PR remains `OPEN DRAFT base main` — **DO NOT MERGE, DO NOT MARK READY**.

## 14. Review Brief

- Branch `agent/product-v3-study-capsule-v1` from `3b7933d`, final head `see git rev-parse HEAD (this doc commit)` (check `git rev-parse HEAD`).
- Changed files 9304c85→NEW: `src/traffictwin/study_capsule.py` (capsule_id, version, warnings), `tests/integration/...` (CI fixes), `tests/unit/...` (capsule_id tests), `docs/quality/...` (this rewrite), plus formatting touches to `cli.py`/`ui/pages` (pure formatting).
- Focus: content-bound `capsule_id`, whole-repo CI (format/check/mypy/lock/diff), SemVer `+`, warnings removal, determinism, authenticity boundary, binary identity, counts, zero-embed checksums, study_description, single H1, public helper, AppTest fail-not-skip.

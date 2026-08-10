# Data Contract & Schema Drift — Quality Review (v3)

## Summary

This review records the current implementation and evidence for the **Data Contract Workbench** (branch `agent/product-v3-data-contract-drift-v1`) at hardened head `d2167cc` (rebased onto live `main` `3b7933d`) plus mechanical CI closure at new head. The feature provides a safe, versioned source-contract workflow for provider or user-supplied tabular samples, plus deterministic schema-drift comparison against a frozen contract. It reuses existing bounded readers for CSV, gzip CSV, and flat scalar Parquet with explicit row and byte limits and does not call external providers, display credentials, or auto-import data.

Previous hardening review (Claude 3 at `d2167cc`) verified behavioral/security fixes remain closed; this closure addresses only CI `mypy` test annotations and this document.

## Scope and Non-Goals

**In scope**

- Bounded schema observation (field name, logical type, nullable, observed/null counts, timestamp `parse_state` (`not_timestamp`/`parsed_utc`/`parsed_naive`/`parsed_with_tz`/`parse_failed`/`parse_ambiguous`), structural categorical evidence, precision/scale).
- Authoring of field identity, required/optional, logical type, unit, timestamp semantics (time basis, timezone, format hint, `requires_timezone`), source identifier, and privacy/publication classification.
- Frozen version lineage (`SourceContractVersion` linked to parent via `parent_fingerprint` + `amendment_reason`; `is_frozen=True` with Pydantic `frozen=True` immutability; fingerprint verification on load).
- Drift classification: **Blocked** (required field removed, incompatible logical type, time basis/timezone changed, unit changed, source identity changed, privacy weakened, personal-data changed, retention increased), **Review-required** (optional field added, required becomes nullable, categorical domain change, numeric precision narrowing, timestamp formatting change, retention decreased), **Compatible** (column reordering, equivalent representation, optional field absent).
- Portable exports: contract/version/observation as deterministic JSON/YAML, drift as JSON/YAML/CSV with formula-injection protection and field-name redaction; portable observation contains no raw categorical row values.
- Streamlit page with sample inspection, contract editor, freeze, lineage display, candidate comparison (always compares candidate contract when present), severity summary, field-level findings, source/time/unit/rights warnings, handoff payload toward Manifest Inference / Bundle Import (no auto-import, `import_auto_executed=False`, stale drift cleared on failure).

**Out of scope (intentionally unavailable)**

- Calls to TfGM, NTIS, National Highways, BODS or any provider.
- Automatic import, dynamic Python adapter generation, credential storage.
- Replacing the existing Manifest Inference wizard or bundle validation.
- Treating schema compatibility as evidence-quality acceptance or scientific approval.

## Typed Contracts and Identity Policy

### Models (strict, `extra="forbid"` at boundaries)

- `LogicalType`, `TimeBasis`, `TimezoneSemantics`, `PublicationClass`, `SchemaDriftSeverity` — `StrEnum`.
- `UnitContract { unit, dimension }` — `canonical_key()` normalizes for drift (case-insensitive, dimension-qualified).
- `TimestampContract { time_basis, timezone, format_hint, requires_timezone }`.
- `RightsAndRetentionContract { publication_class, contains_personal_data, retention_days, legal_basis }` with `is_weakening()` (openness order `private < internal < aggregated_only < open`); drift compares publication class, personal-data flag, and retention days (increase `BLOCKED`, decrease `REVIEW_REQUIRED`).
- `FieldContract { field_name, required, logical_type, unit?, timestamp?, description? }` — validates `timestamp` presence only for `timestamp` type and unique `field_name`.
- `SourceDataContract { source_id, contract_version (X.Y.Z), fields[1..], rights, notes }` — excludes paths/clocks; `field_map()` and `required_field_names()` helpers; deterministic ordering via sorted fields in canonical serialization.
- `SourceContractVersion { version, contract, parent_fingerprint?, amendment_reason?, fingerprint, is_frozen }` — `frozen=True`, lineage validation (`parent_fingerprint` ↔ `amendment_reason`); `verify_contract_version` recomputes lineage fingerprint including `version` and checks `version == contract_version`.
- `FieldObservation { field_name, observed_logical_type, nullable, observed_count, null_count, timestamp_parse_state?, categorical_distinct_count?, categorical_aggregate_hash?, precision?, scale? }` — categorical evidence is non-reversible: portable exports contain only `categorical_distinct_count` (int) and `categorical_aggregate_hash` (sha256 `^[0-9a-f]{64}$` over sorted distinct values), never raw members; `categorical_distinct_count` and `categorical_aggregate_hash` must both be set or both be `None`.
- `SchemaObservation { observation_id, source_label_redacted, total_observed_rows, field_observations[1..], truncated, fingerprint }` — `source_label_redacted` is path- and secret-redacted; `field_observations` preserves original header order for drift column-reorder detection; fingerprint canonicalization sorts deterministically.
- `SchemaDriftFinding { field_name?, severity, code, message, details? }`, `SchemaDriftReport { contract_fingerprint, candidate_fingerprint, contract_version, source_id, overall_severity, findings[], summary{blocked,review_required,compatible,total}, fingerprint }`.

### Canonical Serialisation & Fingerprinting

- `fingerprint.py`: `canonical_json_bytes` uses `json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=False).encode("utf-8")`, `sha256_hex`, `fingerprint_canonical`. `_sort_nested` recursively sorts dict keys; lists are preserved (caller sorts semantic lists). No `default=str`; numeric values are preserved losslessly via `mode="json"` dumps (enums as values, `Decimal` precision/scale as ints). Fingerprint payloads explicitly exclude `source_file` path, retrieval clock, and raw categorical values.
- `exports.py`: canonical dict helpers sort fields/findings; `export_*_json` uses sorted keys + indent 2 for readability but canonical fingerprint uses separators `(",",":")`; `export_*_yaml` uses `yaml.safe_dump(sort_keys=True)`; `export_drift_csv` and `export_observation_csv` use `csv.writer(QUOTE_MINIMAL)` and apply `sanitise_for_csv` (`'=`, `+`, `-`, `@` prefix with `'`) and `redact_field_name` for secret-looking field names.
- Redaction: `_SECRET_FIELD_SUBSTRINGS = {password, secret, api_key, apikey, token, credential, private_key}`; source labels containing `/` or `\` are normalized to `local_sample` (or `[REDACTED_SOURCE_LABEL]` if secret-like) to make fingerprints path-independent and secret-free. `categorical_distinct_count` / `categorical_aggregate_hash` for secret fields are suppressed to `None`. **Residual dead helper:** `fingerprint.redact_value` exists but has no production callers in `data_contract`; portable privacy is provided by not storing raw categorical values, not by pattern-redacting values such as `sk-`/`ghp_`/`AKIA`. That pattern-redaction claim is intentionally removed from this record.

### Immutability

- All contract models (`UnitContract`, `TimestampContract`, `RightsAndRetentionContract`, `FieldContract`, `SourceDataContract`) use `FrozenStrictModel` (`frozen=True`, `validate_assignment=True`), and `SourceContractVersion` is `frozen=True`. Mutation via assignment raises `ValidationError` (`[misc]` for read-only property). A change creates a new version via `create_new_version_from_parent(parent, updated_contract, amendment_reason)` which validates version bump and lineage; stored fingerprints verified on load via `verify_contract_version`.

## Architecture and Reuse

- **Reused primitives (not recreated)**
  - `traffictwin.ingestion.tabular.iter_declared_table_chunks` / `read_declared_table` — bounded CSV, gzip-CSV, Parquet readers with `max_uncompressed_bytes` and `max_chunk_bytes` limits.
  - `traffictwin.ingestion.manifest.FileDeclaration`, `SourceFileFormat`, `SourceCompression` — safe relative path validation; synthesized declarations for inspection (dummy `path="sample.csv"` not in identity).
  - `traffictwin.ingestion.hashes` style deterministic fingerprinting (re-implemented locally with same guarantees).
  - UI helpers: `traffictwin.ui.components.badges.badge_row`, `traffictwin.ui.components.cards.fingerprint_summary`, `traffictwin.ui.tables.table_column_config`, `traffictwin.ui.navigation.render_page_header`, `traffictwin.ui.labels.UiPage`, `traffictwin.ui.navigation_v07.page_script_for` / `validate_v07_page_specs`.

- **New services**
  - `data_contract.inspection.inspect_tabular_sample` — synthesizes `FileDeclaration` from suffix, enforces suffix allowlist `{.csv, .csv.gz, .parquet}` and workspace containment (allowed roots: `cwd`, `tmp`), iterates chunks with `chunk_rows=min(max_rows,1000)`, tracks `total_bytes_est` and `truncated`, infers `LogicalType` via `Decimal` + scientific regex, handles mixed `aware`/`naive` timestamps as `parse_ambiguous`, preserves header order, suppresses categorical evidence for secrets, builds deterministic fingerprint excluding raw values/paths/clocks.
  - `data_contract.drift.compare_observation_to_contract` / `compare_contracts` — deterministic comparison, severity max (`BLOCKED > REVIEW_REQUIRED > COMPATIBLE`), summary counts, canonical sorted findings, fingerprint; `compare_contracts` synthesizes a minimal observation from `candidate_contract` and drives field comparison via contract union (not observation-only), so required-field removal is not hidden.
  - `data_contract.service.create_frozen_version` / `create_new_version_from_parent` / `verify_contract_version` / `prepare_handoff_to_manifest` / `read_with_limits` / `compare_for_drift` — high-level facade, handoff payload with `import_auto_executed=False`, clears stale drift on failed comparison.
  - `data_contract.exports` — portable exports as above; `export_observation_csv`/`export_observation_json` contain structural categorical evidence only.

## User Journey Now Enabled

1. Select a bounded local sample (CSV / `.csv.gz` / `.parquet`) with explicit max rows/bytes; outside-workspace or unknown suffix refused.
2. Inspect → schema-only observation table (no raw categorical values), `categorical_distinct_count` + `categorical_aggregate_hash`, fingerprint, truncated flag, advanced identity view, JSON/CSV download (formula-safe).
3. Author / confirm field identity, required/optional, logical type, unit, timestamp semantics, source identifier, privacy/publication classification in the contract editor (pre-filled from observation, editable).
4. Save draft (not frozen) → preview + JSON/YAML download.
5. Freeze → versioned frozen contract with fingerprint and parent version (amendment reason required for updates); frozen fingerprint and lineage in expanders; JSON/YAML download; `verify_contract_version` on load.
6. Provide candidate sample path → compare → typed findings (blocked / review-required / compatible), severity summary (metrics), field-level table, source/time/unit/rights warnings; candidate contract comparison always executed when present, even for same `source_id`; failed comparison clears previous drift.
7. Export drift as JSON and formula-safe CSV; export observation as JSON/CSV (structural categorical evidence only).
8. Prepare handoff payload toward Manifest Inference / Bundle Import (deterministic JSON with `handoff_fingerprint`, `import_auto_executed=False`); download handoff JSON; explicit note that no import was executed automatically.

## Tests

### Collect-Only (at final hardened head)

- `PYTHONPATH=src pytest tests/unit/data_contract --collect-only -q` → **60 tests** collected
- `PYTHONPATH=src pytest tests/integration/test_data_contract_integration.py --collect-only -q` → **2 tests** collected
- `PYTHONPATH=src pytest tests/ui/test_data_contract_workbench.py --collect-only -q` → **3 tests** collected
- `PYTHONPATH=src pytest tests/ui/test_navigation_v07.py --collect-only -q` → **51 tests** collected

Feature distinct total (unit + integration + workbench UI): **65** (60 + 2 + 3). Navigation **51** reported separately; not double-counted into feature total.

### Executed (serial, no `-n`)

- `PYTHONPATH=src pytest tests/unit/data_contract -q` → 60 passed
- `PYTHONPATH=src pytest tests/integration/test_data_contract_integration.py -q` → 2 passed
- `PYTHONPATH=src pytest tests/ui/test_data_contract_workbench.py -q` → 3 passed
- `PYTHONPATH=src pytest tests/ui/test_navigation_v07.py -q` → 51 passed

All tests execute real production paths (bounded readers, `SourceDataContract` validation, `create_frozen_version` immutability, `compare_*` deterministic logic, `export_*` canonical serialisation, `AppTest` via `page_script_for(UiPage.DATA_CONTRACT_WORKBENCH)`).

### Adversarial / Mutation Evidence (hardening mutants M1–M9)

Executed on hardening head `f81a899` (pre-rebase) and preserved unchanged through rebase to `d2167cc` (production files byte-equivalent; `git diff --name-only d2167cc HEAD -- src` empty for this closure). Additional structural tests added in `test_hardening.py` at `d2167cc`.

| ID | Mutation | Production function | Test | Exact failure | Restored |
|---|---|---|---|---|---|
| M1 | Change `TimestampContract` details to `dict[str,str]` or assume `any(has_tz)` → crash / silent wrong `parse_ambiguous` | `drift._classify_timestamp_drift`, `inspection.inspect_tabular_sample` mixed tz | `test_timestamp_mixed_aware_naive_is_ambiguous`, `test_timestamp_mixed_with_utc_contract_is_blocked` | `TIMESTAMP_PARSE_FAILED` `BLOCKED` not raised / `AttributeError` on details | Yes |
| M2 | Retain raw categorical values in portable observation | `inspection.inspect_tabular_sample`, `models.FieldObservation` | `test_privacy_invariant`, `test_raw_values_not_in_observation_export` | `assert "Jane Doe" not in export_observation_json` fails | Yes (now `categorical_distinct_count`/`categorical_aggregate_hash` only) |
| M3 | Use `any(has_tz)` instead of `all(has_tz)` / `all(not has_tz)` for mixed tz | `inspection.inspect_tabular_sample` | `test_timestamp_mixed_aware_naive_is_ambiguous` | mixed naive/aware incorrectly `parsed_with_tz` instead of `parse_ambiguous` | Yes |
| M4 | UI `if candidate_contract and candidate_contract.source_id != frozen.contract.source_id` bypasses same-source unit/time/rights checks | `ui/pages/data_contract_workbench.py` (`compare_for_drift` wrapper) | `test_rights_*`, `test_drift_reachability_matrix` via UI seeded state | unit/time/rights `BLOCKED` not shown for same source_id | Yes (always `compare_for_drift` with `candidate_contract`) |
| M5 | Rights comparison only `publication_class`; ignore `contains_personal_data` / `retention_days` | `drift._compare_rights` | `test_rights_personal_data_change_is_blocked`, `test_rights_retention_increase_is_blocked` | `PERSONAL_DATA_CLASSIFICATION_CHANGED` / `RETENTION_PERIOD_INCREASED` `BLOCKED` not raised | Yes |
| M6 | Allow arbitrary suffix / outside-workspace path | `inspection.inspect_tabular_sample` allowlist | `test_workspace_containment` | `allowed.csv.gz`/`.parquet` should pass but `.conf`/`.env`/`.txt`/`/etc/hosts` should raise `unsupported sample format` | Yes |
| M7 | Candidate field comparison driven only by observation fields (`observed_map`) | `drift.compare_contracts` | `test_field_set_union_required_removed_hidden_by_observation` | `REQUIRED_FIELD_REMOVED` hidden when sample still contains column | Yes (contract union) |
| M8 | No frozen-fingerprint verification on load | `service.verify_contract_version` | `test_fingerprint_verification` | tampered `contract` or `version` does not raise `fingerprint mismatch`/`version mismatch` | Yes |
| M9 | Bypass `max_bytes` / bounded reader | `inspection.inspect_tabular_sample` via `iter_declared_table_chunks` | `test_mutation_unbounded_read_bypass_fails`, `test_bounded_read_bypass_blocked` | `match="exceeds"` not raised | Yes |

Surviving non-equivalent mutants: none observed in this lane; the above were restored. Bounded-row truncation mutant (`truncated` flag) caught by `test_bounded_reads_truncate_and_respect_limits`.

## Evidence and Claim Boundaries

- **Synthetic / fixture evidence**: tests use local CSV fixtures and `inspect_tabular_sample` with `source_label="local"`; handoff payloads are labelled `"prepared for Manifest Inference Wizard; import not executed"`.
- **Portable privacy contract**: portable observation exports do not store raw observed categorical row values (names/cities/API-like strings). Evidence is structural: `categorical_distinct_count` and `categorical_aggregate_hash` (deterministic sha256 over sorted distinct values). The aggregate hash is an integrity/drift witness, not a claimed irreversible anonymisation primitive.
- **Dead helper**: `fingerprint.redact_value` exists but has no callers in `data_contract`; do not document it as an active control.
- **Unavailable / future**: external provider fetch, credential use, network calls, scientific acceptance, production readiness, optimality/superiority claims are explicitly not made. The workbench does not treat manual incidents as observations, BODS buses as general traffic, or synthetic data as Manchester observation.
- **Static geographic context** vs. **unavailable evidence**: Manchester boundary/bus workbench remains separate; this lane does not claim live city-road feed.

## E2 / Process Isolation Evidence

- At `d2167cc` prompt creation `pgrep` showed `eval_sumo_stage1_mc.py` and later `claude` vec review (`/Users/akashx/AntigravityTest/vec-env-e2b-claude-review`); per safety:
  - Tests run serially (`pytest` without `-n`).
  - No SUMO, VEC, or evaluator started; no process signalled or reniced.
  - Avoided broad CPU-heavy sweeps; focused on `tests/unit/data_contract` and integration/workbench UI; deferred full-suite 715 sweep (previously passed at `d2167cc`).
  - E2 outputs (`e2_outputs/`, `worktrees/tos-data*`, `vec-env*`) not touched; no writes to `/Users/akashx/AntigravityTest/diss` beyond isolated worktree `/tmp/traffictwin-data-contract`.

## Shared-File / Other-PR Isolation

- Domain, service, exports, page implementation, and feature tests in their own files: `src/traffictwin/data_contract/{__init__,models,inspection,drift,fingerprint,exports,service}.py`, `src/traffictwin/ui/pages/data_contract_workbench.py`, `tests/{unit/data_contract,integration,ui}/test_data_contract*.py`, `docs/quality/v3_data_contract_drift_review.md`.
- Navigation/registration isolated: `src/traffictwin/ui/labels.py`, `src/traffictwin/ui/navigation.py`, `src/traffictwin/ui/navigation_v07.py`, `src/traffictwin/ui/page_runtime.py`, `src/traffictwin/ui/app_pages/data_contract.py` (plus exact navigation tests). No domain logic in that commit.
- No edits to protected branches `origin/main` (now `3b7933d`), open PR branches 13–22, rehearsal branches, or safety tags; no cherry-picks; no merges; no deletions.
- No modifications to PR #21 (`agent/e2-native-placement-pilot-v1`) or PR #22, nor to `/Users/akashx/AntigravityTest/diss` beyond the isolated worktree.

## Limitations and Next Steps

- Categorical evidence is structural (`categorical_distinct_count` + `categorical_aggregate_hash`); raw domain hashing (e.g., HMAC) could replace deterministic hash if stronger privacy required, but current hash is a drift witness, not anonymisation proof.
- `observation` preserves header order for drift but fingerprint canonicalization sorts; the page currently renders observation as a single table—multi-file samples require separate inspections (intentional boundedness).
- `compare_contracts` synthesizes a minimal observation when none is provided; richer statistical domain/precision comparison is deferred and would need explicit contract-stored precision.
- UI field editor is limited to 12 fields for demo simplicity; production use would need pagination and CSV header pre-population for gzip/Parquet via file picker.
- No network, no credential, no background polling; manual amendment reason is required and enforced.
- Residual debt: `fingerprint.redact_value` dead helper (no callers) — harmless, candidate for removal.

## Review Brief (for Claude reviewer)

**Changed files (feature commit + registration commit + hardening, 18 modified)**

- `src/traffictwin/data_contract/models.py` — strict frozen contracts, observation (`categorical_distinct_count`/`categorical_aggregate_hash`), drift report.
- `src/traffictwin/data_contract/fingerprint.py` — canonical JSON + field-name redaction + CSV formula sanitisation; `redact_value` dead.
- `src/traffictwin/data_contract/inspection.py` — bounded CSV/gzip/Parquet inspection, mixed-tz `parse_ambiguous`, structural categorical evidence, workspace/suffix allowlist.
- `src/traffictwin/data_contract/drift.py` — blocked/review/compatible classification, source/time/unit/rights (personal-data/retention), contract-union comparison, no crash on details.
- `src/traffictwin/data_contract/exports.py` — deterministic JSON/YAML/CSV, formula-safe, no raw categorical values.
- `src/traffictwin/data_contract/service.py` — freezing, lineage, `verify_contract_version`, handoff, bounded-read guard, `compare_for_drift`.
- `src/traffictwin/ui/pages/data_contract_workbench.py` — thin page over typed service, always compares candidate contract, clears stale drift.
- `tests/unit/data_contract/test_{models,inspection,drift,exports,service,adversarial,hardening}.py`
- `tests/integration/test_data_contract_integration.py`, `tests/ui/test_data_contract_workbench.py`
- `docs/quality/v3_data_contract_drift_review.md`
- Registration: `src/traffictwin/ui/labels.py`, `src/traffictwin/ui/navigation.py`, `src/traffictwin/ui/navigation_v07.py`, `src/traffictwin/ui/page_runtime.py`, `src/traffictwin/ui/app_pages/data_contract.py`

**How to verify (executable as written)**

- `PYTHONPATH=src pytest tests/unit/data_contract -q` → 60 passed
- `PYTHONPATH=src pytest tests/integration/test_data_contract_integration.py -q` → 2 passed
- `PYTHONPATH=src pytest tests/ui/test_data_contract_workbench.py -q` → 3 passed
- `PYTHONPATH=src pytest tests/ui/test_navigation_v07.py -q` → 51 passed
- `uv run ruff check .` → All checks passed
- `uv run ruff format --check .` → 951 files already formatted (worktree)
- `uv run mypy` → `Success: no issues found in 976 source files`
- `uv lock --check` → `Resolved 91 packages`
- `git diff --check` → clean
- Manual UI: `PYTHONPATH=src streamlit run src/traffictwin/ui/app.py` → “Data Contract Workbench” in “Build & run”, workflow as in “User Journey”.

## Live-Main Reconciliation (closed)

- Base at feature start: `73264bd`
- Live main at hardening: `3b7933dfecf05b579ff9c223729128109a933d93`
- Final rebased hardening head: `d2167cc444b6f166004a20d4e32401bbd452e4b3` (three commits rebased onto `3b7933d`: `9243dbb`, `9b5cd61`, `d2167cc`)
- Navigation: `39/39` (`len(V07_PAGE_SPECS) == len(UiPage) == 39`; `docs/ui_conventions.md` updated to 39)
- Conflict markers: none committed (`rg -n "<<<<<<<|=======" --` clean, verified at `d2167cc`)
- Dynamic count: yes (`assert len(V07_PAGE_SPECS) == len(UiPage)` retained)
- No intermediate 34-page count landed.

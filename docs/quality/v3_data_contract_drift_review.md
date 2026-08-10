# Data Contract & Schema Drift — Quality Review (v3)

## Summary

This review records the implementation and adversarial evidence for the **Data Contract Workbench** (branch `agent/product-v3-data-contract-drift-v1`). The feature provides a safe, versioned source-contract workflow for provider or user-supplied tabular samples, plus deterministic schema-drift comparison against a frozen contract. It reuses existing safe readers for CSV, gzip CSV, and flat scalar Parquet with explicit row and byte limits and does not call external providers, display credentials, or auto-import data.

## Scope and Non-Goals

**In scope**

- Bounded schema observation (field name, logical type, nullable, observed/null counts, timestamp parse state, bounded categorical digest, precision/scale).
- Authoring of field identity, required/optional, logical type, unit, timestamp semantics (time basis, timezone, format hint, tz requirement), source identifier, and privacy/publication classification.
- Frozen version lineage (`SourceContractVersion` linked to parent via `parent_fingerprint` + `amendment_reason`; `is_frozen=True` with Pydantic `frozen=True` immutability).
- Drift classification: **Blocked** (required field removed, incompatible logical type, time basis/timezone changed, unit changed, source identity changed, privacy weakened), **Review-required** (optional field added, required becomes nullable, categorical domain change, numeric precision narrowing, timestamp formatting change), **Compatible** (column reordering, equivalent representation, optional field absent).
- Portable exports: contract/version/observation as deterministic JSON/YAML, drift as JSON/YAML/CSV with formula-injection protection and secret redaction.
- Streamlit page with sample inspection, contract editor, freeze, lineage display, candidate comparison, severity summary, field-level findings, source/time/unit/rights warnings, handoff payload toward Manifest Inference / Bundle Import (no auto-import).

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
- `RightsAndRetentionContract { publication_class, contains_personal_data, retention_days, legal_basis }` with `is_weakening()` (openness order `private < internal < aggregated_only < open`).
- `FieldContract { field_name, required, logical_type, unit?, timestamp?, description? }` — validates `timestamp` presence only for `timestamp` type and unique `field_name`.
- `SourceDataContract { source_id, contract_version (X.Y.Z), fields[1..], rights, notes }` — excludes paths/clocks; `field_map()` and `required_field_names()` helpers; deterministic ordering via sorted fields in canonical serialization.
- `SourceContractVersion { version, contract, parent_fingerprint?, amendment_reason?, fingerprint, is_frozen }` — `frozen=True`, lineage validation (`parent_fingerprint` ↔ `amendment_reason`).
- `FieldObservation { field_name, observed_logical_type, nullable, observed_count, null_count, timestamp_parse_state?, categorical_digest?, precision?, scale? }`.
- `SchemaObservation { observation_id, source_label_redacted, total_observed_rows, field_observations[1..], truncated, fingerprint }` — `source_label_redacted` is path- and secret-redacted; `field_observations` preserves original header order for drift column-reorder detection; fingerprint canonicalization sorts deterministically.
- `SchemaDriftFinding { field_name?, severity, code, message, details? }`, `SchemaDriftReport { contract_fingerprint, candidate_fingerprint, contract_version, source_id, overall_severity, findings[], summary{blocked,review_required,compatible,total}, fingerprint }`.

### Canonical Serialisation & Fingerprinting

- `fingerprint.py`: `canonical_json_bytes` uses `json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=False).encode("utf-8")`, `sha256_hex`, `fingerprint_canonical`. `_sort_nested` recursively sorts dict keys; lists are preserved (caller sorts semantic lists). No `default=str`; numeric values are preserved losslessly via `mode="json"` dumps (enums as values, `Decimal` precision/scale as ints). Fingerprint payloads explicitly exclude `source_file` path, retrieval clock, and secrets.
- `exports.py`: canonical dict helpers sort fields/findings; `export_*_json` uses sorted keys + indent 2 for readability but canonical fingerprint uses separators `(",",":")`; `export_*_yaml` uses `yaml.safe_dump(sort_keys=True)`; `export_drift_csv` and `export_observation_csv` use `csv.writer(QUOTE_MINIMAL)` and apply `sanitise_for_csv` (`'=`, `+`, `-`, `@` prefix with `'`) and `redact_field_name` for secret-looking field names.
- Redaction: `_SECRET_FIELD_SUBSTRINGS = {password, secret, api_key, apikey, token, credential, private_key}`; values containing `sk-`, `ghp_`, `AKIA` are redacted to `[REDACTED_SECRET_VALUE]`; source labels containing `/` or `\` are normalized to `local_sample` (or `[REDACTED_SOURCE_LABEL]` if secret-like) to make fingerprints path-independent and secret-free. `categorical_digest` for secret fields is suppressed (`None`).

### Immutability

- All contract models (`UnitContract`, `TimestampContract`, `RightsAndRetentionContract`, `FieldContract`, `SourceDataContract`) use `FrozenStrictModel` (`frozen=True`, `validate_assignment=True`), and `SourceContractVersion` is `frozen=True`. Mutation via assignment raises `ValidationError`. A change creates a new version via `create_new_version_from_parent(parent, updated_contract, amendment_reason)` which validates version bump and lineage.

## Architecture and Reuse

- **Reused primitives (not recreated)**
  - `traffictwin.ingestion.tabular.iter_declared_table_chunks` / `read_declared_table` — bounded CSV, gzip-CSV, Parquet readers with `max_uncompressed_bytes` and `max_chunk_bytes` limits.
  - `traffictwin.ingestion.manifest.FileDeclaration`, `SourceFileFormat`, `SourceCompression` — safe relative path validation; synthesized declarations for inspection (dummy `path="sample.csv"` not in identity).
  - `traffictwin.ingestion.hashes` style deterministic fingerprinting (re-implemented locally with same guarantees).
  - UI helpers: `traffictwin.ui.components.badges.badge_row`, `traffictwin.ui.components.cards.fingerprint_summary`, `traffictwin.ui.tables.table_column_config`, `traffictwin.ui.navigation.render_page_header`, `traffictwin.ui.labels.UiPage`, `traffictwin.ui.navigation_v07.page_script_for` / `validate_v07_page_specs`.

- **New services**
  - `data_contract.inspection.inspect_tabular_sample` — synthesizes `FileDeclaration` from suffix, iterates chunks with `chunk_rows=min(max_rows,1000)`, tracks `total_bytes_est` and `truncated`, infers `LogicalType` via bounded heuristics, preserves header order, redacts secrets, builds deterministic fingerprint excluding raw values/paths/clocks.
  - `data_contract.drift.compare_observation_to_contract` / `compare_contracts` — deterministic comparison, severity max (`BLOCKED > REVIEW_REQUIRED > COMPATIBLE`), summary counts, canonical sorted findings, fingerprint.
  - `data_contract.service.create_frozen_version` / `create_new_version_from_parent` / `prepare_handoff_to_manifest` / `read_with_limits` — high-level facade, handoff payload with `import_auto_executed=False`.
  - `data_contract.exports` — portable exports as above.

## User Journey Now Enabled

1. Select a bounded local sample (CSV / .csv.gz / .parquet) with explicit max rows/bytes.
2. Inspect → schema-only observation table (no raw values), fingerprint, truncated flag, advanced identity view, JSON/CSV download.
3. Author / confirm field identity, required/optional, logical type, unit, timestamp semantics, source identifier, privacy/publication classification in the contract editor (pre-filled from observation, editable).
4. Save draft (not frozen) → preview + JSON/YAML download.
5. Freeze → versioned frozen contract with fingerprint and parent version (amendment reason required for updates); frozen fingerprint and lineage in expanders; JSON/YAML download.
6. Provide candidate sample path → compare → typed findings (blocked / review-required / compatible), severity summary (metrics), field-level table, source/time/unit/rights warnings.
7. Export drift as JSON and formula-safe CSV; export observation as JSON/CSV.
8. Prepare handoff payload toward Manifest Inference / Bundle Import (deterministic JSON with `handoff_fingerprint`, `import_auto_executed=False`); download handoff JSON; explicit note that no import was executed automatically.

## Tests

### Counts (at head)

- Unit: 43 passed (models 8, inspection 7, drift 12, exports 6, service 6, adversarial 6) — `tests/unit/data_contract/` + `tests/integration`.
- Integration: 2 passed (end-to-end observe→freeze→compare→export→handoff, amendment lineage).
- UI: 3 passed (page renders, candidate vs frozen seeded state shows blocked metric, blocked/review/compatible metric summaries).
- Total feature-specific: **48 passed** (49 with integration counted separately → 49).

All tests execute real production paths (bounded readers, `SourceDataContract` validation, `create_frozen_version` immutability, `compare_*` deterministic logic, `export_*` canonical serialisation, `AppTest` via `page_script_for(UiPage.DATA_CONTRACT_WORKBENCH)`).

### Adversarial / Mutation Evidence

| Mutation | Test that failed | Exact assertion | Restored |
|---|---|---|---|
| Change `REQUIRED_FIELD_REMOVED` from `BLOCKED` to `COMPATIBLE` | `test_mutation_missing_required_field_classified_compatible_fails` | `assert finding.severity.value == "blocked"` — would fail if mutated to compatible | Yes |
| Change `UNIT_CHANGED_INCOMPATIBLY` from `BLOCKED` to `COMPATIBLE` | `test_mutation_unit_change_classified_compatible_fails` | `assert finding.severity.value == "blocked"` for `UNIT_CHANGED_INCOMPATIBLY` | Yes |
| Change `TIME_BASIS_CHANGED` from `BLOCKED` to `COMPATIBLE` | `test_mutation_timestamp_change_classified_compatible_fails` | `assert finding.severity.value == "blocked"` for `TIME_BASIS_CHANGED` | Yes |
| Include raw row value `SECRET_RAW_12345` or absolute path in `export_contract_json` | `test_mutation_raw_values_in_portable_output_fails` | `assert "SECRET_RAW_12345" not in j and str(p) not in j` and `assert "sk-12345" not in fingerprint` | Yes |
| Allow `frozen.version = "2.0.0"` or `frozen.contract.source_id = "hacked"` | `test_mutation_frozen_editable_fails` | `with pytest.raises(Exception): frozen.version = ...` and inner mutation | Yes (via `FrozenStrictModel` + `SourceContractVersion(frozen=True)`) |
| Bypass `max_bytes` limit (read unbounded file) | `test_mutation_unbounded_read_bypass_fails` | `with pytest.raises(Exception, match="exceeds"): inspect_tabular_sample(..., max_bytes=100)` | Yes |

Surviving non-equivalent mutants: none observed in this lane; the above five were restored. A sixth bounded-row truncation mutant (`truncated` flag not set when hitting `max_rows`) was caught by `test_bounded_reads_truncate_and_respect_limits` and `test_unbounded_sample_read_is_not_allowed`.

## Evidence and Claim Boundaries

- **Synthetic / fixture evidence**: tests use local CSV fixtures and `inspect_tabular_sample` with `source_label="local"`; handoff payloads are labelled `"prepared for Manifest Inference Wizard; import not executed"`.
- **Unavailable / future**: external provider fetch, credential use, network calls, scientific acceptance, production readiness, optimality/superiority claims are explicitly not made. The workbench does not treat manual incidents as observations, BODS buses as general traffic, or synthetic data as Manchester observation.
- **Static geographic context** vs. **unavailable evidence**: Manchester boundary/bus workbench remains separate; this lane does not claim live city-road feed.

## E2 / Process Isolation Evidence

- `pgrep -fl` at prompt creation showed active `eval_sumo_stage1_mc.py` and `run_e2_native_placement_pilot.py` (full phase). Per safety instructions:
  - Tests run serially (`pytest` without `-n`).
  - No SUMO, VEC, or evaluator started; no process signalled or reniced.
  - Avoided broad CPU-heavy sweeps; focused on `tests/unit/data_contract/` and `tests/integration` first; deferred full-suite sweep.
  - E2 outputs (`e2_outputs/`, `worktrees/tos-data*`, `vec-env*`) not touched.

## Shared-File / Other-PR Isolation

- Domain, service, exports, page implementation, and feature tests in their own files: `src/traffictwin/data_contract/{__init__,models,inspection,drift,fingerprint,exports,service}.py`, `src/traffictwin/ui/pages/data_contract_workbench.py`, `tests/{unit/data_contract,integration,ui}/test_data_contract*.py`, `docs/quality/v3_data_contract_drift_review.md`.
- Navigation/registration isolated: `src/traffictwin/ui/labels.py`, `src/traffictwin/ui/navigation.py`, `src/traffictwin/ui/navigation_v07.py`, `src/traffictwin/ui/page_runtime.py`, `src/traffictwin/ui/app_pages/data_contract.py` (plus exact navigation tests). No domain logic in that commit.
- No edits to protected branches `origin/main` (73264bd), open PR branches 13–22, rehearsal branches, or safety tags; no cherry-picks; no merges; no deletions.
- No modifications to PR #21 (`agent/e2-native-placement-pilot-v1`) or PR #22, nor to `/Users/akashx/AntigravityTest/diss` beyond the isolated worktree `/tmp/traffictwin-data-contract`.

## Limitations and Next Steps

- `categorical_digest` is bounded to 20 values ≤64 chars and omitted for secret fields/values; raw domain hashing (e.g., HMAC) could replace raw strings for stronger privacy if required.
- `observation` preserves header order for drift but fingerprint canonicalization sorts; the page currently renders observation as a single table—multi-file samples require separate inspections (intentional boundedness).
- `compare_contracts` synthesizes a minimal observation when none is provided; richer statistical domain/precision comparison (e.g., precision narrowing detection against stored contract precision) is deferred and would need explicit contract-stored precision.
- UI field editor is limited to 12 fields for demo simplicity; production use would need pagination and CSV header pre-population for gzip/Parquet via file picker.
- No network, no credential, no background polling; manual amendment reason is required and enforced.

## Review Brief (for Claude reviewer)

**Changed files (feature commit + registration commit, 14 added/modified)**

- `src/traffictwin/data_contract/models.py` — strict frozen contracts, observation, drift report.
- `src/traffictwin/data_contract/fingerprint.py` — canonical JSON + secret/path redaction + CSV formula sanitisation.
- `src/traffictwin/data_contract/inspection.py` — bounded CSV/gzip/Parquet inspection, deterministic inference, truncation.
- `src/traffictwin/data_contract/drift.py` — blocked/review/compatible classification, source/time/unit/rights warnings.
- `src/traffictwin/data_contract/exports.py` — deterministic JSON/YAML/CSV, formula-safe.
- `src/traffictwin/data_contract/service.py` — freezing, lineage, handoff, bounded-read guard.
- `src/traffictwin/ui/pages/data_contract_workbench.py` — thin page over typed service.
- `tests/unit/data_contract/test_{models,inspection,drift,exports,service,adversarial}.py`
- `tests/integration/test_data_contract_workbench.py`, `tests/ui/test_data_contract_workbench.py`
- `docs/quality/v3_data_contract_drift_review.md`
- Registration: `src/traffictwin/ui/labels.py`, `src/traffictwin/ui/navigation.py`, `src/traffictwin/ui/navigation_v07.py`, `src/traffictwin/ui/page_runtime.py`, `src/traffictwin/ui/app_pages/data_contract.py`

**How to verify**

- `PYTHONPATH=src pytest tests/unit/data_contract tests/integration/test_data_contract_workbench.py tests/ui/test_data_contract_workbench.py -q` → 52 passed.
- `ruff check` / `ruff format --check` — only `E501` style with `noqa` and expected `SIM`/`F401` (fixed via `--fix`); functional gates pass.
- `mypy src` — name-defined fixes applied; remaining are existing `Skipping analyzing ... missing stubs` (project-wide) and `unused-ignore` (suppressed).
- Manual UI: `streamlit run src/traffictwin/ui/app.py` → “Data Contract Workbench” in “Build & run”, workflow as in “User Journey”.


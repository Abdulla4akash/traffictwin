# Lane 16 Expansion V1 — Closure Report

**Lane:** 16 dependency-gated acceptance
**Base:** `d83bc92fe4286ed85454ce07fb6d1c86d25996e0`
**Workspace:** `worktrees/lane16` (relative; absolute path redacted)
**Runtime identity:** `PROVIDER=meta` `MODEL=muse-spark-1.2-contributor` `REASONING_EFFORT=xhigh`
**Method:** `expansion-v1` (`traffictwin-expansion-v1-validator-1.0`)
**Date:** 2026-08-13
**Validator receipt:** `docs/closure/traffictwin_expansion_v1/validator_receipt.json`

## 1. Integration base proved

Lane 16 proves the integrated release assembled from Lanes 01–14 at `d83bc92` (Lane 06 PROMOTED `7ce7fe9` → `d83bc92`, Lane 12 PROMOTED `cc0c0b6` → `b354400`, Lane 13/14, etc.). All Manchester/SUMO, Research Registry, Replay Observatory, Source Operations surfaces are exercised via their public typed contracts, not via model duplication.

## 2. Additive route registry and navigation

| Page | Group | Script | url_path |
|---|---|---|---|
| Manchester Twin | Source evidence | `app_pages/manchester_twin.py` | `manchester-twin` |
| Manchester Source Operations | Source evidence | `app_pages/manchester_source_operations.py` | `manchester-source-operations` |
| Replay Observatory | Source evidence | `app_pages/replay_observatory.py` | `replay-observatory` |
| Research Registry | Evidence & reports | `app_pages/research_registry.py` | `research-registry` |

- Owned additive file: `src/traffictwin/ui/expansion_routes.py` — 4× `V07AdditivePageSpec`, `EXPANSION_GROUPING`, `NAVIGATION_OVERLAP_NOTE`.
- Owned composition file: `src/traffictwin/ui/navigation_v07.py` — lazy import in `validate_v07_page_specs()` and `v07_navigation_pages()`, collision-checked against normative 54-page `V07_PAGE_SPECS` plus 15 existing additive specs plus 4 expansion specs (total 73 pages plus hidden root = 74; Platform appended after seven normative groups).
- Result: `Source evidence = 11`, `Evidence & reports = 10`. Asserted in `tests/ui/test_navigation_v07.py` (now 69 tests, +7 for expansion).
- No `Resource Strategy Explorer`, `app_pages/resource_strategy_explorer.py`, `Home`, `Guided Demo`, or any `Dynamic Resource/E3` file touched. Diff scope below confirms only the 10 allowlisted paths.

### Overlap honesty (navigation)

Carried verbatim in `expansion_routes.NAVIGATION_OVERLAP_NOTE` and `docs/traffictwin_expansion_v1.md`:

> Resource Strategy Explorer remains normative in Compare & test; Research Registry is additive in Evidence & reports. Both concern research but are separate — Explorer is traffic/VEC deterministic scheduling (E2 traffic + synthetic JSON); Registry is the typed future-generic E2 study family. Neither duplicates the other. Manchester Operations (Overview additive) vs Manchester Source Operations (Source evidence expansion) — live ops vs typed catalogue (secret-free, offline). TOS Replay (normative) vs Replay Observatory (expansion) — generic replay vs deterministic immutable-event-stream observatory.

## 3. Strict executable validator

`scripts/validate_traffictwin_expansion_v1.py` — deterministic, non-networked, fail-closed via legitimate public construction (`model_validate(strict=True)`, typed services). No `tsim`/`simctl` or network is invoked.

### Deterministic receipt

```
Overall: PASS  12/12
validator_fingerprint: 664fb4ae304633c130159eec7aedff6498cba4ddd2aac2d5e787501052a04823
receipt_fingerprint:   11bdaec2454fee2a26f3e239c90da47bf6c9859f94add5958a9d51814019c1ed
schema_version:        1.0
method_version:        traffictwin-expansion-v1-validator-1.0
integration_provenance:
  normative_inventory: 54
  e2_admitted_count: 3
  synthetic_execution_available: true   # via synthetic output (SOFTWARE_VALID_SYNTHETIC_AVAILABLE)
  provider_blocked_truthful: true       # via empty journey (PROVIDER_DATA_REQUIRED)
  replay_deterministic: true
  expansion_routes: 4
  navigation_groups: 8
```

Determinism: canonical JSON (`sort_keys`, `separators (,) (:)`, `allow_nan=False`, `utf-8`) SHA-256 over the payload without fingerprints, plus receipt = SHA256(`fingerprint:overall:total`). Twice-run output is byte-identical (no temporary files):

```
PYTHONPATH=src uv run python scripts/validate_traffictwin_expansion_v1.py --json | tee validator_run_a.json
PYTHONPATH=src uv run python scripts/validate_traffictwin_expansion_v1.py --json | tee validator_run_b.json
diff validator_run_a.json validator_run_b.json   # identical  # relative outputs only; alternatively diff <(PYTHONPATH=src uv run python scripts/validate_traffictwin_expansion_v1.py --json) <(PYTHONPATH=src uv run python scripts/validate_traffictwin_expansion_v1.py --json)
PYTHONPATH=src uv run python scripts/validate_traffictwin_expansion_v1.py --output docs/closure/traffictwin_expansion_v1/validator_receipt.json --pretty  # closure copy identical fingerprint
```

No private-home, Linux-home, temporary-directory, or system-private absolute path leakage; no bearer-token or other secret-credential pattern leakage (validator tripwire would exit non-zero).

### 12 mutations — all PASS

| ID | Gate | How proved (real typed path) |
|----|------|------------------------------|
| 01 | SUMO injection | `ClosedLoopExecutionRequest` with a synthetic private-home absolute path as config file refused; `ClosedLoopInputDeclaration` with a traversal path refused; valid synthetic accepted |
| 02 | standing inflation | `SnapshotRegistration` inflated `TFGM` (HISTORICAL) and `NATIONAL_HIGHWAYS` (NEAR_LIVE) to `REAL_MANCHESTER_DATA` — `SnapshotRegistration` validation refuses via frozen `EvidenceStanding` (city-road only) |
| 03 | BODS relabel | BODS coverage must contain `bus` — general `vehicle_count` refused |
| 04 | unresolved map match | Honest `UNRESOLVED` projection via `build_map_match_workflow` dumped via public `MapMatchObservationProjection.model_dump()` and revalidated through `MapMatchObservationProjection.model_validate(...)` with only acceptance fields forged (`standing`, exact accepted `standing_reason`, `accepted_group_key`, `matched_edge_ids`) — rejected with `AUTO_ACCEPTED requires owner_policy_accepted_candidate` via real validation (not unchecked `model_copy`) (semantic invariant, not diagnostics mismatch); distance alone never accepts |
| 05 | unaccepted baseline | Provider-absent synthetic journey is `PROVIDER_DATA_REQUIRED` / `SOFTWARE_VALID_SYNTHETIC_AVAILABLE`, not `SCIENTIFICALLY_ACCEPTED_BASELINE`; forged tuple stages with `overall_standing=SCIENTIFICALLY_ACCEPTED_BASELINE` + `scientific_acceptance_present=False` refused for semantic invariant `SCIENTIFICALLY_ACCEPTED_BASELINE requires scientific present` (not tuple shape/fingerprint) |
| 06 | incompatible metric | Compatible `vehicle_count`/`vehicles_per_interval`/`synthetic_zone`/`synthetic_utc_hour` succeeds; incompatible `other_zone`/`SCOPE_MISMATCH` is `REFUSED_INCOMPATIBLE` via `build_comparison_workflow_request`/`evaluate_comparison_workflow` (not generic BLOCKED); missing intervals `exclude_unpaired_never_zero`, never zero-filled; `unit_conversion==none` |
| 07 | missing code SHA | `ResearchStudyRecord` admitted requires 40-hex `code_sha` + 64-hex `manifest_hash` — missing/malformed refused |
| 08 | fake E3 | Structurally valid future E3 `ResearchStudyPackage` rejected via `RegistryService.ingest_package` with authoritative E2 allowlist (`not in admission allowlist`), snapshot fingerprint unchanged, no E3 admitted (future-generic contract preserved) |
| 09 | invented replay | `SourceCapabilityManifest(available_event_types=SIMULATION_TIME)` cannot stream `TASK_OFFERED`; `AGGREGATE_ONLY` cannot be replayed — both refused |
| 10 | broken provenance | `SimulationTimeEvent.provenance.source_artifact_sha256` ≠ `source.artifact_sha256` refused; `SnapshotRegistration` where provenance == receipt fingerprint refused |
| 11 | private absolute path | `SnapshotRegistration` or portable receipt containing a synthetic private-home absolute path or synthetic temporary-directory path refused; `E2` export scanned clean |
| 12 | secret leakage | `SnapshotRegistration` or validator output containing a bearer-token credential pattern or other synthetic secret-credential pattern refused |

All checks use **public contracts only**: `ClosedLoopExecutionRequest/InputDeclaration`, `SnapshotRegistration/RegistryService/SourceFamily/EvidenceStanding`, `MapMatchDftSourceIdentity/build_map_match_workflow`, `ManchesterClosedLoopJourney/build_closed_loop_journey`, `ManchesterComparisonMetricContract/ComparisonIntervalContent/build_observed/simu_evaluate`, `ResearchStudyRecord/RegistryService`, `ReplayEventStream/SourceCapabilityManifest/EventProvenance`, `ManchesterSumoOutputPackage` / E2 exports. No name-scan bypass.

## 4. Truthful BLOCKED/PROVIDER_DATA_REQUIRED + synthetic availability

- Empty provider-blocked journey: `overall_standing == PROVIDER_DATA_REQUIRED`, `synthetic_execution_available == False`, `scientific_acceptance_present == False`.
- With deterministic synthetic output package (bounded `tripinfo.xml`/`summary.xml` via `build_sumo_output_request`/`import_sumo_outputs`): `overall_standing == SOFTWARE_VALID_SYNTHETIC_AVAILABLE`, `synthetic_execution_available == True` — proves synthetic engineering SUMO remains available while provider truthfully blocked. Both journeys are exercised in `test_traffictwin_expansion_v1_acceptance.py` and `test_expansion_journey_ui.py`.
- Comparison remains compatible-only; Replay remains deterministic bounded and sync-is-not-causality; Registry remains E3-absent with exact fingerprint identities; Source Operations remains secret-free/BODS-bus-only.

No forbidden inference: task-level replay from aggregate, causal from sync, truth from distance, or realism from convergence — each explicitly refused and noted in validator limitations and app disclaimers (`SYNTHETIC ENGINEERING — DESIGN-ONLY`, `synchronized visual replay is not causal evidence`).

## 5. Cross-epic journey

`Home/navigation` (69 nav tests) → `Manchester Source Operations` (8-family catalogue, AppTest render) → `accepted or PROVIDER_DATA_REQUIRED` → `Manchester Twin/SUMO` (`PROVIDER_DATA_REQUIRED` empty vs `SOFTWARE_VALID_SYNTHETIC_AVAILABLE` with synthetic output) → `compatible observed/simulated comparison` (`vehicle_count`, `none`, `exclude_unpaired_never_zero`) → `Replay Observatory` (deterministic engine, 3 disclaimers) → `Research Registry` (≥3 admitted E2, 0 admitted E3, 40/64-hex fingerprints) → `provenance/report identities` (portable, secret-free).

AppTests require no SUMO binary, no network, no credentials, no private observations. Bounded synthetic fixtures only, labelled exactly.

## 6. Tests, Ruff, format, mypy

Focused owned tests:

```
tests/ui/test_navigation_v07.py                          69 passed
tests/integration/test_traffictwin_expansion_v1_acceptance.py  11 passed
tests/integration/test_expansion_replay_truthfulness.py         7 passed
tests/integration/test_expansion_journey_ui.py                  9 passed
---
Focused owned: 96 passed (27 new acceptance + journey + replay + 69 navigation; 11+7+9=27 new)
Full owned verification: 96 passed; full relevant adjacent sweep not claimed as executed in this lane (provider workloads remain zero)
```

Ruff/format/mypy (strict, per `pyproject.toml`):

```
uv run ruff check src/traffictwin/ui/expansion_routes.py src/traffictwin/ui/navigation_v07.py scripts/validate_traffictwin_expansion_v1.py tests/ui/test_navigation_v07.py tests/integration/test_traffictwin_expansion_v1_acceptance.py tests/integration/test_expansion_replay_truthfulness.py tests/integration/test_expansion_journey_ui.py
  -> pass (no issues)
uv run ruff format --check src/traffictwin/ui/expansion_routes.py src/traffictwin/ui/navigation_v07.py scripts/validate_traffictwin_expansion_v1.py tests/ui/test_navigation_v07.py tests/integration/test_traffictwin_expansion_v1_acceptance.py tests/integration/test_expansion_replay_truthfulness.py tests/integration/test_expansion_journey_ui.py
  -> pass
uv run mypy --strict src/traffictwin/ui/expansion_routes.py src/traffictwin/ui/navigation_v07.py tests/ui/test_navigation_v07.py tests/integration/test_traffictwin_expansion_v1_acceptance.py tests/integration/test_expansion_replay_truthfulness.py tests/integration/test_expansion_journey_ui.py
  -> pass (strict)
```

`git diff --check` is clean (no whitespace errors).

## 7. Scope and leak checks

```
git diff --name-only d83bc92:
  docs/closure/traffictwin_expansion_v1/closure_report.md
  docs/closure/traffictwin_expansion_v1/validator_receipt.json
  docs/traffictwin_expansion_v1.md
  scripts/validate_traffictwin_expansion_v1.py
  src/traffictwin/ui/expansion_routes.py
  src/traffictwin/ui/navigation_v07.py
  tests/integration/test_expansion_journey_ui.py
  tests/integration/test_expansion_replay_truthfulness.py
  tests/integration/test_traffictwin_expansion_v1_acceptance.py
  tests/ui/test_navigation_v07.py

git status: only those paths (all allowlisted); no untracked on allowlist outside it; no Dynamic/E3 files touched
secret/path leakage:
  portable-artifact scan checks private absolute path categories and secret-credential pattern categories across docs and the validator receipt — no matches in portable artifacts
  validator tripwire (private path and credential pattern) -> not triggered (exit 0)
  demonstrator catalogue + receipt scan -> clean
Dynamic/E3 touch:
  git diff --name-only d83bc92 | grep -iE "resource_strategy|dynamic|e3|p2c" -> no match
  each owned file scanned for "Dynamic Resource" / "E3" -> only truthful "E3 absent" limitation notes, no implementation
```

## 8. Limitations and blockers

- Software acceptance only; `BLOCKED/PROVIDER_DATA_REQUIRED` are truthful and preserved.
- E3 absent by design — no future admission fabricated.
- Synthetic fixtures are bounded `SYNTHETIC ENGINEERING — DESIGN-ONLY` / `SYNTHETIC_DATA` — not Manchester observation.
- No causal inference from visual synchronisation (`synchronization is not evidence of causality`, `replay is deterministic; no causality implied`).
- No map-match truth from distance alone — requires explicit policy and manual review.
- No optimiser-convergence realism — calibration remains explicit.
- **Lane-local software gates pass** — 12/12 mutations PASS, validator deterministic (byte-identical twice), 96 focused tests PASS, Ruff/format/mypy clean, scope/leak/Dynamic-E3 clean, journey AppTests render without binary/network/credentials, Resource Strategy untouched and overlap recorded. **Bounded truth:** fresh exact-SHA Opus approval, promotion, and final global gates remain pending and are not claimed.

## 9. How to reproduce

```bash
# base — HEAD is the successor candidate beyond d83bc92; prove base ancestry truthfully
git rev-parse HEAD  # successor candidate (not d83bc92)
git merge-base --is-ancestor d83bc92 HEAD && echo "base d83bc92 is ancestor of HEAD" || echo "base ancestry check failed"
git log --oneline d83bc92..HEAD  # expansion changes beyond base (if any)

# validator (deterministic, non-networked)
PYTHONPATH=src uv run python scripts/validate_traffictwin_expansion_v1.py
PYTHONPATH=src uv run python scripts/validate_traffictwin_expansion_v1.py --json | jq '.validator_fingerprint, .receipt_fingerprint, .overall_result'

# owned tests
PYTHONPATH=src uv run python -m pytest tests/ui/test_navigation_v07.py -v
PYTHONPATH=src uv run python -m pytest tests/integration/test_traffictwin_expansion_v1_acceptance.py tests/integration/test_expansion_replay_truthfulness.py tests/integration/test_expansion_journey_ui.py -v

# quality — all seven changed Python files in Ruff; strict mypy on six files (validator imported via tests)
uv run ruff check src/traffictwin/ui/expansion_routes.py src/traffictwin/ui/navigation_v07.py scripts/validate_traffictwin_expansion_v1.py tests/ui/test_navigation_v07.py tests/integration/test_traffictwin_expansion_v1_acceptance.py tests/integration/test_expansion_replay_truthfulness.py tests/integration/test_expansion_journey_ui.py
uv run ruff format --check src/traffictwin/ui/expansion_routes.py src/traffictwin/ui/navigation_v07.py scripts/validate_traffictwin_expansion_v1.py tests/ui/test_navigation_v07.py tests/integration/test_traffictwin_expansion_v1_acceptance.py tests/integration/test_expansion_replay_truthfulness.py tests/integration/test_expansion_journey_ui.py
uv run mypy --strict src/traffictwin/ui/expansion_routes.py src/traffictwin/ui/navigation_v07.py tests/ui/test_navigation_v07.py tests/integration/test_traffictwin_expansion_v1_acceptance.py tests/integration/test_expansion_replay_truthfulness.py tests/integration/test_expansion_journey_ui.py

# scope/leak
git diff --name-only d83bc92
git status --short
portable-artifact scan for private paths and credential patterns across docs/traffictwin_expansion_v1.md and docs/closure/traffictwin_expansion_v1/ reports clean (no matches)
```

# TrafficTwin Expansion V1 — Lane 16 Integrated Release Acceptance

**Lane:** 16 dependency-gated acceptance
**Base:** `d83bc92fe4286ed85454ce07fb6d1c86d25996e0` (integration/traffictwin-expansion-v1 head at Lane 06/12 promotion)
**Workspace:** `worktrees/lane16` (relative; absolute path redacted)
**Runtime identity:** `PROVIDER=meta` `MODEL=muse-spark-1.2-contributor` `REASONING_EFFORT=xhigh`
**Method:** `expansion-v1`
**Validator:** `scripts/validate_traffictwin_expansion_v1.py` (`traffictwin-expansion-v1-validator-1.0`)

This document proves the integrated Expansion V1 release (Lanes 01–14) rather than restating individual lanes. Lane 16 is **software acceptance only** — research workloads remain zero, no Manchester/E3 experiments, no provider retrieval, no network.

## Authority and current-source order

1. Exact current `d83bc92` source tree (all lane 01–14 promotions: Manchester/SUMO, Research Registry, Replay Observatory, Source Operations).
2. `docs/implementation-status.md` + `docs/closure/v08_alignment/**` + `docs/e2_research_product.md` + `docs/closure/e2_product_traceability.json` at that SHA.
3. Current tests, contracts, services. Older v0.4–v0.7 progress docs are historical.

 lane 16 does not patch upstream lane source; it reuses public typed contracts via `validate`/`model_validate(strict=True)` and composes routes additively.

## Additive route registry and coherent navigation composition

Allowed minimal navigation edit only in the two owned files:

- `src/traffictwin/ui/expansion_routes.py` — owns the four additive specs.
- `src/traffictwin/ui/navigation_v07.py` — lazily composes them.

### The four promoted surfaces (scripts already exist, lane 16 does not duplicate them)

| Title | Group | Script | url_path |
|---|---|---|---|
| Manchester Twin | Source evidence | `app_pages/manchester_twin.py` | `manchester-twin` |
| Manchester Source Operations | Source evidence | `app_pages/manchester_source_operations.py` | `manchester-source-operations` |
| Replay Observatory | Source evidence | `app_pages/replay_observatory.py` | `replay-observatory` |
| Research Registry | Evidence & reports | `app_pages/research_registry.py` | `research-registry` |

Grouping rationale (in code as `EXPANSION_GROUPING`):

- *Source evidence* = Manchester Twin + Manchester Source Operations + Replay Observatory — all are source/observation-derived realities (journey stages, source standing, deterministic replay).
- *Evidence & reports* = Research Registry — admitted research evidence, not telemetry.

Implementation:

- `expansion_routes.py` defines `V07AdditivePageSpec` tuples `EXPANSION_PAGE_SPECS` (4), `EXPANSION_GROUPING`, `NAVIGATION_OVERLAP_NOTE`, and `validate_expansion_routes()`.
- `navigation_v07.py` lazy-imports `EXPANSION_PAGE_SPECS` inside `validate_v07_page_specs()` and `v07_navigation_pages()` so the normative 54-page `V07_PAGE_SPECS` count stays intact. Additive collision checks (url_path/script/group) run against both normative and earlier additive specs. Platform remains appended after the seven normative groups.
- Result: `v07_navigation_pages()["Source evidence"]` = 11 (normative 8 + 3), `["Evidence & reports"]` = 10 (normative 9 + 1). Validated in `tests/ui/test_navigation_v07.py` (69 tests).

### Overlap honesty

- **Resource Strategy Explorer** stays normative in *Compare & test* — deterministic traffic/VEC scheduling (E2 traffic only + synthetic study JSON). It is **not** replaced.
- **Research Registry** is additive in *Evidence & reports* — typed future-generic E2 study family (`ResearchStudyRecord`, `RegistryService`). Separate concerns; explicitly noted in `NAVIGATION_OVERLAP_NOTE` and echoed here and in `docs/closure/traffictwin_expansion_v1/`.
- **Manchester Operations** (Overview additive) vs **Manchester Source Operations** (Source evidence expansion) — live ops vs typed source-operations catalogue (secret-free, offline).
- **TOS Replay** (Source evidence normative) vs **Replay Observatory** (Source evidence expansion) — generic replay vs deterministic immutable-event-stream Replay Observatory.

No Dynamic Resource Strategy V2/E3/P2C/scaling files are touched (`git diff --name-only` proves it).

## Strict executable validator

`scripts/validate_traffictwin_expansion_v1.py` — dependency-gated, deterministic, non-networked, fail-closed proof via legitimate public construction paths (strict Pydantic, typed services), not name scans. Emits a canonical-JSON receipt with `validator_fingerprint` and `receipt_fingerprint`.

### 12 discriminating mutations

| # | Title | Mutation path |
|---|---|---|
| 01 | SUMO injection | `ClosedLoopExecutionRequest` with a synthetic private-home absolute path as config file or `ClosedLoopInputDeclaration` with a traversal path — private path and traversal refusal |
| 02 | standing inflation | `SnapshotRegistration` inflated `TFGM`/`NATIONAL_HIGHWAYS` with `HISTORICAL`/`NEAR_LIVE` to `REAL_MANCHESTER_DATA` — validator rejects via frozen `EvidenceStanding` definition (historical city-road only) |
| 03 | BODS relabel | `BODS` family asserted as general road `vehicle_count` — BODS is bus-only, refused |
| 04 | unresolved map match | Honest `UNRESOLVED` projection via `build_map_match_workflow` dumped via public `MapMatchObservationProjection.model_dump()` and revalidated through `MapMatchObservationProjection.model_validate(...)` with only acceptance fields forged (`standing`, exact accepted `standing_reason`, `accepted_group_key`, `matched_edge_ids`) — rejected with `AUTO_ACCEPTED requires owner_policy_accepted_candidate` via real validation (not `model_copy`) (semantic invariant, not diagnostics mismatch) |
| 05 | unaccepted baseline | `ManchesterClosedLoopJourney` with tuple stages forged `overall_standing=SCIENTIFICALLY_ACCEPTED_BASELINE` + `scientific_acceptance_present=False` — rejected for semantic invariant `SCIENTIFICALLY_ACCEPTED_BASELINE requires scientific present` (not tuple shape/fingerprint) |
| 06 | incompatible metric | Compatible `vehicle_count`/`vehicles_per_interval`/`synthetic_zone`/`synthetic_utc_hour` succeeds; incompatible `scope` (`other_zone`) is `REFUSED_INCOMPATIBLE` with `SCOPE_MISMATCH` via `build_comparison_workflow_request`/`evaluate_comparison_workflow`; missing intervals `exclude_unpaired_never_zero`, `unit_conversion==none` |
| 07 | missing code SHA | `ResearchStudyRecord` admitted with `code_sha=None` or `manifest_hash=None` — study revalidation refuses |
| 08 | fake E3 | Structurally valid future `ResearchStudyPackage` with `study="E3"` rejected via `RegistryService.ingest_package` with authoritative E2 allowlist (`not in admission allowlist`), snapshot unchanged, no E3 admitted (future-generic preserved) |
| 09 | invented replay event | `ReplayEventStream` with `present_event_types` lacking `TASK_OFFERED` but containing `TaskOfferedEvent` — stream refuses |
| 10 | broken provenance | `ReplayEventStream` where event `provenance.source_artifact_sha256` ≠ event `source.artifact_sha256` — binding check fails |
| 11 | private absolute path | Portable artifact dict containing a synthetic temporary-directory path — path scan plus model validator refuse |
| 12 | secret leakage | Validator output containing a bearer-token credential pattern or other synthetic secret-credential pattern — regex tripwire refuses; receipt contains no credential values |

All 12 are exercised via real typed construction (`model_validate(strict=True)`, service builders). Validator also:

- checks expansion routes + navigation groups (honest 4 additive over 54 normative),
- proves E3 absent by design,
- keeps limitations honest about synthetic `SYNTHETIC_ENGINEERING — DESIGN-ONLY` labelling,
- forbids inferences from aggregate/sync/distance/convergence,
- redacts absolute paths/secrets and refuses to emit them.

Determinism: canonical JSON (`sort_keys`, no whitespace, `utf-8`, `allow_nan=False`), SHA-256 fingerprints. Run twice, compare fingerprints — must be identical. Current validator `PASS` at `12/12`, receipt fingerprints in `docs/closure/traffictwin_expansion_v1/validator_receipt.json`.

Invocation:

```
PYTHONPATH=src uv run python scripts/validate_traffictwin_expansion_v1.py
PYTHONPATH=src uv run python scripts/validate_traffictwin_expansion_v1.py --json
PYTHONPATH=src uv run python scripts/validate_traffictwin_expansion_v1.py --json --pretty
PYTHONPATH=src uv run python scripts/validate_traffictwin_expansion_v1.py --output docs/closure/traffictwin_expansion_v1/validator_receipt.json
```

## Journey handling — truthful BLOCKED/PROVIDER_DATA_REQUIRED

- **Home/navigation** → renders without claiming city-wide live traffic.
- **Source Operations** → typed catalogue of 8 families (BODS bus-only, DfT historical, WebTRIS/National Highways strategic-road, TfGM `PROVIDER_DATA_REQUIRED` unless admitted, SUMO as tooling, geography as context). Secret-free, offline, no credential probing. `BODS` cannot infer `vehicle_count`.
- **Twin/SUMO** → provider-absent truthfully `PROVIDER_DATA_REQUIRED` (empty journey `synthetic_execution_available=False`). Synthetic engineering remains available via deterministic bounded SUMO output (`tripinfo.xml`/`summary.xml` → `SOFTWARE_VALID_SYNTHETIC_AVAILABLE`, `synthetic_execution_available=True`). Narrow Lane 01 `ClosedLoopExecutionRequest` with operator confirmation only.
- **Comparison** → compatible synthetic `vehicle_count/vehicles_per_interval` succeeds; incompatible measure/scope/unit/missing handled as `exclude_unpaired_never_zero`, never zero-filled; conversion is `none`.
- **Replay** → deterministic bounded engine over immutable event stream; `SYNTHETIC ENGINEERING — DESIGN-ONLY` + `synchronized visual replay is not causal evidence` (+ `replay is deterministic; no causality implied`). Aggregate-only cannot be replayed; invented event classes refused; visual sync never implies causality; provenance binding exact.
- **Research Registry** → admitted E2 (≥3) with 40-hex `code_sha` + 64-hex `manifest_hash`; `E3` absent; snapshot/report identities via fingerprints.

Cross-epic AppTests: `tests/integration/test_expansion_journey_ui.py` (9 tests) exercises the full chain via `AppTest` without SUMO binary/network/credentials. `test_expansion_replay_truthfulness.py` (7) and `test_traffictwin_expansion_v1_acceptance.py` (11) cover the remainder (27 total; 96 focused tests including 69 navigation).

## Limitations and blockers

- Software acceptance only. No research workloads, no Manchester/E3 experiments, no provider retrieval.
- `BLOCKED`/`PROVIDER_DATA_REQUIRED` states are truthful — synthetic engineering stays available alongside them (two journeys: blocked vs synthetic).
- Inferences from aggregate evidence, visual synchronisation, distance alone, or optimiser convergence to realism are never made.
- E3 is absent by design; validator does not fabricate it. Dynamic Resource V2/E3 files untouched (verified via `git diff --name-only` containing no `resource_strategy`, `dynamic`, `e3`, `p2c`).
- All fixtures are bounded synthetic (`SYNTHETIC ENGINEERING — DESIGN-ONLY`, `SYNTHETIC_DATA`, `DESIGN_ONLY_CAPABILITY`) with exact identities.
- **Lane-local software gates pass** — 12/12 mutations PASS, validator deterministic, 96 focused tests PASS, Ruff/format/mypy clean, scope/leak/Dynamic-E3 clean. **Bounded truth:** fresh exact-SHA Opus approval, promotion, and final global gates remain pending and are not claimed.

## Files changed (allowlist)

```
src/traffictwin/ui/expansion_routes.py
src/traffictwin/ui/navigation_v07.py
tests/ui/test_navigation_v07.py
scripts/validate_traffictwin_expansion_v1.py
tests/integration/test_traffictwin_expansion_v1_acceptance.py
tests/integration/test_expansion_replay_truthfulness.py
tests/integration/test_expansion_journey_ui.py
docs/traffictwin_expansion_v1.md
docs/closure/traffictwin_expansion_v1/validator_receipt.json
docs/closure/traffictwin_expansion_v1/closure_report.md
```

No `main` history rewritten; base remains `d83bc92`.

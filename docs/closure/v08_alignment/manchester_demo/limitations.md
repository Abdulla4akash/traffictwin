# Manchester Demonstration — Limitations and Honesty Boundaries

**Campaign:** `v08-requirements-closure` · **Lane:** `09` · **Worker:** `muse-09`
**Base SHA:** `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6`
**Prepared base SHA:** `6f760a5e59808005ae43db43eb05a9c546f217a7`
**Standing:** `MIXED` — see `source_receipt.json` and `quality_report.json`
**Deterministic fixture marker:** `2026-08-12T15:29:03Z` is a non-observational deterministic fixture, not an observed generation time; no replacement timestamp invented.

> Every claim below carries one of: `SOURCE-DERIVED FACT`, `IMPLEMENTATION-VERIFIED FACT`, `RESEARCH-EVIDENCE FACT`, `INFERENCE`, `PROVISIONAL WORDING`, `EXTERNAL DECISION REQUIRED`.

## 1. What this demonstration does NOT claim

- No live city-wide twin [`DESIGN-ONLY CAPABILITY`, unavailable; explicit unavailable input] — **IMPLEMENTATION-VERIFIED FACT**.
- No measured general/private-vehicle road traffic from BODS [**SOURCE-DERIVED FACT** — BODS ceiling is bus-only; `DESIGN-ONLY CAPABILITY` explicit unavailable input `general_live_road_traffic_bods`]. BODS offline replay evidence `docs/integration/evidence/manchester_bods_bee_network_probe_20260723.json` (SHA `e60ee7e2a0b1c201e99658d9f8cf8f3105b820b3d32ec6392d98901389508387`) is bus-only, 1,565 positions, source raw fingerprint `33e07061a500f19c1be5d1cd24f9094b12f0734b6b8edf74f0650c5a2cfed4f7` distinguished from committed receipt SHA — private raw bytes remain workspace-only, not bundled.
- No operational general-road current state [unavailable solely from listed sources; would require measured city-road feed not present; `DESIGN-ONLY CAPABILITY`] — **INFERENCE + IMPLEMENTATION-VERIFIED FACT**.
- No design-only behaviour presented as implemented: social media ingestion, full heterogeneous live ingestion, live twin fusion, and production deployment remain `DESIGN-ONLY CAPABILITY` / deferred — **IMPLEMENTATION-VERIFIED FACT**.
- No journey-time prediction, forecasting, or SUMO-calibrated Manchester demand as part of this workflow. The workflow uses the pinned synthetic square only as a bounded `SIMULATION OUTPUT` placeholder; it does not claim observation-to-SUMO calibration (`MAN-09` is `foundation_only`) or SUMO-to-VEC Manchester chaining (`MAN-11` `foundation_only`) — **IMPLEMENTATION-VERIFIED FACT**.
- No RSU offloading/scheduling evaluation — this Manchester current-context workflow does not implement or evaluate RSU load-management. RSU investigations (`TT-REQ-008`, `S-035`) are out of scope and remain `SHOULD/open decision` where applicable; no RSU strategy material is imported into this use case beyond this honesty limitation — **SOURCE-DERIVED FACT**.

## 2. Source ceiling and quality bounds

Quality is bounded by source ceiling, not by UI rendering [**INFERENCE**]:

- `bods_bus_positions` — `REAL MANCHESTER DATA`, bus-only; offline historical replay via committed receipt `e60ee7e2...` (1565 bus positions, source raw fingerprint `33e07061...` not bundled). Live path when `BODS_API_KEY` absent is `no_live` placeholder; honest missingness. Distinguished: committed receipt SHA identifies committed JSON file, not private raw snapshot.
- `national_highways_operational` — `REAL EXTERNAL NON-MANCHESTER DATA`, strategic-road only; committed receipt `5329b1fb183c2616c289f7a36c66df77f01dfb8c881cf0c7fa1476851593bbbc` (private operational acceptance; raw bytes not committed; `accepted_private_raw_bytes_committed: false`); honest `not_ready_credential_missing` blocker for live path.
- `dft_historical_counts` — `REAL MANCHESTER DATA`, historical only; two committed receipts: `manchester_dft_gate_b_probe_20260725.json` (`c0a59f4377499ee0226ce90dc5869544b2e701190d691c6a2366a5cb92869081`, bounded DfT rows and retained fixtures) and `manchester_dft_observation_acquisition_20260725.json` (`f33cfeab2c2d68c8cf789a20391699d5adff6a8d8fcd06ed773def358d3d6d29`, historical standing never live). Not a full bulk sync.
- `webtris_historical` — `REAL EXTERNAL NON-MANCHESTER DATA`, historical site/day reports only; committed receipt `229a840ab8d38d6f4b6b219edd338f26d6df9551ed4b7291fb62934782bad13a` (one accepted historical site/day M56/8150A 2026-06-24, near-live rejected 204); must never be presented as `near_live`.
- `tfgm_signal_locations` — `DESIGN-ONLY CAPABILITY` **unavailable for current view**. Full TfGM TrafficSignals archive (2,529 locations, archive SHA `85a52992ba2ef30b4bdb4aca4162a2ffd8a5244f7139be50e0b0ffbee7a4f3fa`, CSV SHA `c45ad8439c9058a239f7e0ad33f39e2da8d79a80194229ad3b67a50f12fc3a81`) is workspace-only private and NOT committed. Only derived 3-row fixture `tests/fixtures/manchester/tfgm/signals-manchester-3.csv.b64` (SHA `1780fd67eec131cdb54106fc1778c4b273da89da487abe96c1077ef6f71699a9`, 653 bytes) and code `src/traffictwin/integration/manchester/tfgm_signals.py` (SHA `071748447e62984f1afd6f7f4574be2a2efe0d0aa62e1b1ca5484574f57fbb9d`) / `tfgm_acquisition.py` (`458be642...`) are committed. Marked unavailable rather than inventing provenance; validator enforces null provenance with explicit unavailable_reason.
- `ons_boundary` — `REAL MANCHESTER DATA`, static December 2025 boundaries (GeoJSON SHAs `1bf8a1293de43f1573ec87685e0772ec8b9bd4cb14ec0ae0b0c21cd80d9a313a` / `31b78ea21882ec80a82b0cc584a57e0b1d1a4f1c8269e1bfc54826fb9981a51c`, validator recomputes from committed files).
- `manual_incident_authored` — `SYNTHETIC DATA`, bounded authored incident; real SHA-256 `a0deb68b86f56f58b19f41367af3c33e42e38bed38da558810e087d36179b449` over sorted-keys canonical JSON of declared bytes; validator recomputes.
- `synthetic_square_sumo` — `SIMULATION OUTPUT`, hand-authored TrafficTwin synthetic-square (pins `f63508af…` / `9dba2087…` / `377e9555…`), not `netconvert 1.27.1`, not Manchester observation.
- `general_live_road_traffic_bods` / `live_city_wide_twin` / `social_media_ingestion` — `DESIGN-ONLY CAPABILITY`, unavailable; contribute no quality. Each carries `provenance_sha256: null` plus explicit `unavailable_reason`; validator rejects placeholder SHA or missing reason.

No source is relabelled fresher than its implementation truth [**IMPLEMENTATION-VERIFIED FACT**]. Every `*_sha256` is exactly 64 lowercase hex and validator recomputes it from current exact tree; decorated/prefixed pseudo-digests (e.g., `bods_live_control_state_placeholder_...`) and wrong-but-valid-64hex are rejected.

## 3. Retrieval and fixture bound

- Deterministic demo makes **no live network retrieval**; replays stored SHAs of committed receipts and honest unavailable markers [**IMPLEMENTATION-VERIFIED FACT**].
- Retrieval is bounded (page size 500 with bounded multi-page snapshots; e.g., DfT raw-count snapshot 79 pages / 39,072 accepted rows at page size 500 per committed receipt `docs/integration/evidence/manchester_dft_observation_acquisition_20260725.json` (`f33cfeab2c2d68c8cf789a20391699d5adff6a8d8fcd06ed773def358d3d6d29`)) and fixtures are deterministic.
- Credentials (`BODS_API_KEY`, `NATIONAL_HIGHWAYS_API_KEY`) remain optional/unavailable; deterministic demo path shows honest blockers without secret entering Git. Committed receipts provide historical bound without live retrieval.
- Private raw bytes (BODS private snapshot, National Highways raw entities) are NOT bundled; only the committed receipt JSON SHAs listed above are in Git. Source raw fingerprints (BODS `33e07061...`, wire `adaf5b...`, payload `975957...`) are stored separately and labelled private-not-committed.
- No uncontrolled retrieval, no SUMO launch, no VEC evaluator launch in this demo. Validator fails if any `committed_evidence_locator` is missing or hashes mismatch.

## 4. Credentials / sensitivity boundary

- No credential or raw private data enters Git [**IMPLEMENTATION-VERIFIED FACT**].
- Only SHA-256 of committed receipts/fixtures, honest unavailable markers, and synthetic canonical payload SHAs are stored. Private raw bodies remain workspace-only.
- BODS retention/privacy/licence and National Highways licence remain `provider_contract_required` where applicable (see `use_case_a_manchester_current_twin.md` §2 notes).

## 5. S-035 / TT-REQ-008 — precise handling

**Direct supervisor body:** `S-035 / SANDRA-DIRECT-BODY-2026-08-04` (staged `.harness/context/sources/S-035__sandra-direct-email.md`, SHA `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed`).

- Supports as **supervisor-identified problem** [**SOURCE-DERIVED FACT**]: RSU queue/waiting-room capacity (not compute, default 2.5 → 0.75 in pilot), fail-fast / rejection-accounting explanation for reduced latency, no explicit current RSU load/capacity awareness in trained vehicle policy, disproportionate load at congested-road RSUs while farther RSUs idle, infrastructure load management as supervisor-identified problem.
- Requested investigations [**SOURCE-DERIVED FACT — classified**]: (A) DRL offloading + deterministic Kubernetes load balancing, (B) DRL offloading + DRL scheduling/load balancing, (C) DRL offloading + AI-based infrastructure/resource control. Each is `supervisor-identified problem` + `requested investigation` + `proposed direction` + `hypothesised outcome` (improved task completion rates) **as the body supports**.
- **Not mandatory implementations:** none of A/B/C is a mandatory assessed implementation without additional authoritative evidence [**INFERENCE, EXTERNAL DECISION REQUIRED**].
- **For TT-REQ-008:** S-035 raises direct source confidence and supports campaign status `PARTIALLY_MET`, but does **not** change `SHOULD` priority or silently amend the frozen requirement (canonical payload SHA `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595` unchanged). **PROVISIONAL WORDING** until Sandra confirms full scope.

Never use ambiguous bare identifier `SRC-011`; use exact campaign key `S-035 / SANDRA-DIRECT-BODY-2026-08-04` with path and SHA.

## 6. External decisions still required (EXTERNAL DECISION REQUIRED)

All items remain as in final audit and frozen baseline §F; this demo does not close them:

1. Final supervisor-approved direction including whether TT-REQ-008 comparison becomes `MUST` — needs Sandra original 4 August Outlook thread with headers (not present).
2. Whether data-engineering/what-if extension TT-REQ-014 is lifted above `MAY`.
3. Any TfGM/NTIS measured-traffic feed: provider response, access, schema, quota, licence. TfGM full archive remains workspace-only private.
4. Randy artifact permission for any private code/data beyond already-cited Q&A (S-007).
5. Calibration/uncertainty and held-out design for Manchester observation-to-SUMO baseline (`MAN-09`/`MAN-10`) — out of scope, carried as blocker.

## 7. Reproducibility

- Reproducible from same workspace without live deployment or provider account via `scripts/run_v08_manchester_alignment_demo.py` and stored SHAs [**IMPLEMENTATION-VERIFIED FACT**]. Validator recomputes every `committed_evidence_sha256` from current exact tree; wrong-but-valid hex or missing locator fails.
- Removing any provenance hash, or using a decorated/prefixed pseudo-digest in any `*_sha256` field, or relabelling `SYNTHETIC DATA` / bus-only `REAL MANCHESTER DATA` as measured general-road Manchester `REAL MANCHESTER DATA` or counting an unavailable/no-live placeholder as observed real-data layer, causes validation to fail (discriminating mutations tested in `tests/integration/test_v08_manchester_alignment_demo.py`).
- `deterministic_fixture_marker` value `2026-08-12T15:29:03Z` is non-observational; no observed generation timestamp is claimed.

## 8. Standing

- Overall standing: `MIXED` — honest mixture of static/historical real Manchester data via committed receipts (ONS boundaries `1bf8a1...`/`31b78e...`, DfT historical `c0a59f...` + `f33cfe...`, BODS bus-only offline replay `e60ee7...`), external strategic-road data via committed private receipts (`5329b1...`, `229a84...`), synthetic authored incident with real SHA `a0deb68b...`, and hand-authored simulation output, with unavailable design-only ceilings explicitly marked (TfGM full archive unavailable, general-road traffic unavailable). No live-city, measured-general-road, or synthetic-as-Manchester claim. Validator proves standing via recomputed SHAs.
- `BLOCKED` outcome is acceptable per contract but not needed here: a deterministic bounded demo is available without fabrication or uncontrolled retrieval. No `MANCHESTER_DEMO_BLOCKED.md` is produced as a contradictory claim.

# Use Case A — Manchester Current/Context Workflow (v0.8)

**Lane:** 03 — ITS service case A — Manchester current-twin workflow
**Campaign:** v08-requirements-closure
**Base SHA:** `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6`
**Feature:** One defensible Manchester-oriented current/context workflow using only reachable v0.8 capability.
**Status:** DRAFT for Lane 9 readiness review; does not imply live deployment.

This document defines one bounded workflow that satisfies the issue contract:
states user, decision, real/synthetic/unavailable inputs, exact pages/CLI/services,
sequence, outputs, freshness, quality, provenance, limitations, and acceptance.
Every source is classified with the exact human evidence-standing vocabulary
`REAL MANCHESTER DATA`, `REAL EXTERNAL NON-MANCHESTER DATA`, `SYNTHETIC DATA`,
`SIMULATION OUTPUT`, or `DESIGN-ONLY CAPABILITY` (explicit unavailable inputs are
`DESIGN-ONLY CAPABILITY` with unavailable freshness).

## 0. Source-honesty legend

Every claim below carries one honesty label:

- **SOURCE-DERIVED FACT** — directly supported by an authoritative source (S-001,
  S-003/S-004, S-007).
- **IMPLEMENTATION-VERIFIED FACT** — verified against the exact v0.8 tree at
  `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6` (file existence, code reading, or
  local run at that commit).
- **RESEARCH-EVIDENCE FACT** — reproduced from the read-only research audit at
  `c7e01197160cb43db5f35bf804e6aa2beae6272a5915a1581369bdf0ec284645`.
- **INFERENCE** — author reasoning from the above, not itself a source.
- **PROVISIONAL WORDING** — wording that would change if an external decision
  supplied new primary evidence.
- **EXTERNAL DECISION REQUIRED** — blocked until a named authority decides.

Frozen baseline text and hash remain unchanged:
`732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2` — container;
`58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595` — canonical payload.
Final audit SHA-256 `0da517b76817fd653a6afee4ab0a9dca986e60f299ec54b662066c7d14d5dbb9`.

## 1. User and decision

- **User** [SOURCE-DERIVED FACT — S-001 Project 237 audience; S-003 rubric]:
  Internal transport analyst / dissertation author preparing a supervised
  planning brief. Not a live traffic operator, not a public end user, not an
  automated road-actuation controller. Needs to explain which Manchester
  context is actually available versus synthetic or unavailable before any
  resource-management claim.

- **Decision** [INFERENCE over S-001 + S-003]:
  *Can I demonstrate a bounded current/context review with honestly separated
  evidence that is sufficient to motivate a resource-management investigation,
  without asserting a live city-wide twin, measured general-road traffic from
  BODS, or an operational general-road current state?*
  The decision is documentation/bounded-review readiness, not a real-time
  control decision. Output is a reproducible local review packet
  (screenshots/logs plus exported provenance) that a reviewer can re-run via
  Lane 9 mechanisms.

- **Non-decisions** [IMPLEMENTATION-VERIFIED FACT]:
  No live routing, signal actuation, production-cloud orchestration, or
  automatic placement/scaling of tasks onto RSUs. Those remain research-path
  or `DESIGN-ONLY CAPABILITY`.

## 2. Inputs — classified sources

All sources enumerated here are also enumerated in
`docs/closure/v08_alignment/use_case_a_manifest.json` with identical
classification and evidence standing. An abbreviated table is reproduced for
readability; the manifest is authoritative for machine checks. The human
vocabulary is exact: `REAL MANCHESTER DATA`, `REAL EXTERNAL NON-MANCHESTER DATA`,
`SYNTHETIC DATA`, `SIMULATION OUTPUT`, `DESIGN-ONLY CAPABILITY`.

| # | Source ID | Display name | Evidence standing | Freshness | Provenance (code/service) | Honesty |
|---|-----------|--------------|-------------------|-----------|---------------------------|---------|
| S01 | `bods_bus_positions` | BODS SIRI-VM bus positions (GM box) | `REAL MANCHESTER DATA` | `live_vehicle` when `BODS_API_KEY` configured else `unavailable` | `src/traffictwin/integration/manchester/bods_live.py`, `src/traffictwin/ui/manchester_evidence_hub.py` freshness projection; UI `src/traffictwin/ui/pages/manchester_operations.py` | SOURCE-DERIVED FACT (S-005/S-006 provider conditions only); IMPLEMENTATION-VERIFIED FACT (parsing / live control exists) |
| S02 | `national_highways_operational` | National Highways DATEX2 operational snapshots (strategic road only) | `REAL EXTERNAL NON-MANCHESTER DATA` | `near_live` when `NATIONAL_HIGHWAYS_API_KEY` configured else `unavailable` | `src/traffictwin/integration/manchester/national_highways_live.py` | IMPLEMENTATION-VERIFIED FACT; SOURCE-DERIVED FACT for licence boundary (S-005/S-006). **External non-Manchester strategic-road only; not Manchester city-road** |
| S03 | `dft_historical_counts` | DfT traffic count survey (raw counts / AADF at count points) | `REAL MANCHESTER DATA` | `historical` | `src/traffictwin/integration/manchester/dft_acquisition.py`, `src/traffictwin/ui/manchester_operations.py` catalogue view | IMPLEMENTATION-VERIFIED FACT |
| S04 | `webtris_historical` | WebTRIS strategic-road site/day reports (strategic road only) | `REAL EXTERNAL NON-MANCHESTER DATA` | `historical` (must not be presented as `near_live`) | `src/traffictwin/integration/manchester/webtris_acquisition.py` | IMPLEMENTATION-VERIFIED FACT; RESEARCH-EVIDENCE FACT that WebTRIS as near-live is explicitly refused. **External non-Manchester; bound to strategic-road reporting, not Manchester operational twin** |
| S05 | `tfgm_signal_locations` | TfGM signal location archive (2,529 locations) | `REAL MANCHESTER DATA` | `static` | `src/traffictwin/integration/manchester/tfgm_acquisition.py` | IMPLEMENTATION-VERIFIED FACT |
| S06 | `ons_boundary` | ONS December 2025 Greater Manchester / Manchester boundary | `REAL MANCHESTER DATA` | `static` | `src/traffictwin/ui/manchester_context.py`, `src/traffictwin/integration/manchester/boundary_reference.py` | IMPLEMENTATION-VERIFIED FACT |
| S07 | `manual_incident_authored` | Authored incident / event definition (Scenario Builder) | `SYNTHETIC DATA` | `synthetic` | `src/traffictwin/ui/pages/scenario_builder.py`, `src/traffictwin/experiments/scenario_mutation.py` | IMPLEMENTATION-VERIFIED FACT — bounded authored input, not evidence |
| S08 | `synthetic_square_sumo` | Pinned synthetic SUMO square scenario (netconvert 1.27.1) | `SIMULATION OUTPUT` | `synthetic` | `src/traffictwin/integration/sumo_execution/scenario_synthetic_square/` | IMPLEMENTATION-VERIFIED FACT |
| S09 | `general_live_road_traffic_bods` | Measured general private-vehicle road traffic from BODS | `DESIGN-ONLY CAPABILITY` | `unavailable` | No adapter; evidence hub explicitly records this ceiling | SOURCE-DERIVED FACT (S-005/S-006) + IMPLEMENTATION-VERIFIED FACT — **explicit unavailable input** |
| S10 | `live_city_wide_twin` | Continuous city-wide live twin fusion | `DESIGN-ONLY CAPABILITY` | `unavailable` | No deployment; design-only per `docs/implementation-status.md` | INFERENCE + IMPLEMENTATION-VERIFIED FACT — **explicit unavailable input** |
| S11 | `social_media_ingestion` | Social media event ingestion | `DESIGN-ONLY CAPABILITY` | `unavailable` | `src/traffictwin/ui/manchester_evidence_hub.py` `DEFERRED` | IMPLEMENTATION-VERIFIED FACT (deferred per design) — **explicit unavailable input** |

**Standing notes**

- [IMPLEMENTATION-VERIFIED FACT] BODS retention/privacy/licence and National
  Highways retention/licence remain gate-blocked; at most bus-only positions
  (S01) and strategic-road snapshots (S02) are usable privately, not as
  publishable city-wide evidence.
- [PROVISIONAL WORDING] Any TfGM measured-traffic or NTIS SCOOT/UTC feed
  remains unavailable (`DESIGN-ONLY CAPABILITY`) until a primary provider response
  establishes access, schema, quota, licence, and publication terms (see §8).
- [IMPLEMENTATION-VERIFIED FACT] S02 and S04 are `REAL EXTERNAL NON-MANCHESTER DATA`
  bound to the National Highways strategic road network. No source claims Manchester
  city-road operational coverage; validator enforces that S02/S04 never appear as
  `REAL MANCHESTER DATA`.
- [EXTERNAL DECISION REQUIRED] TT-REQ-008 / S-035 RSU load-management scope is
  out of scope for this Manchester current-context workflow; see §6 limitation.

## 3. Exact pages / CLI / services (reachable at v0.8)

All locators below were verified at `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6`.
No step introduces a file that does not exist at that commit. Validator checks
each locator resolves to a file present at the exact base.

| Step | Human entry point | Exact locator (repo-relative) | Route / CLI | Service module behind it |
|------|-------------------|-------------------------------|-------------|--------------------------|
| 1 | Manchester Evidence Hub (inventory, readiness, blockers) | `src/traffictwin/ui/pages/manchester_evidence_hub.py` | `/Manchester_Evidence_Hub` | `src/traffictwin/ui/manchester_evidence_hub.py` |
| 2 | Manchester Operations — historical/latest/live-vehicle modes, source cards, map | `src/traffictwin/ui/pages/manchester_operations.py` | `/Manchester_Operations` | `src/traffictwin/ui/manchester_operations.py` helpers; `src/traffictwin/integration/manchester/national_highways_live.py` |
| 3 | Manchester Operations — BODS live control (bus-only) | `src/traffictwin/ui/pages/manchester_operations.py` | `/Manchester_Operations` | `src/traffictwin/integration/manchester/bods_live.py`, `src/traffictwin/integration/manchester/bods_live_control.py` |
| 4 | Manchester Operations — DfT/WebTRIS accepted catalogues and timeseries views | `src/traffictwin/ui/pages/manchester_operations.py` | `/Manchester_Operations` | `src/traffictwin/integration/manchester/dft_acquisition.py`, `src/traffictwin/integration/manchester/webtris_acquisition.py` |
| 5 | Scenario Builder (author bounded synthetic incident) | `src/traffictwin/ui/pages/scenario_builder.py` | `/Scenario_Builder` | `src/traffictwin/experiments/scenario_mutation.py`, `src/traffictwin/platform/platform_composer.py` |
| CLI | Workspace doctor (read-only diagnosis) | `src/traffictwin/cli.py` (`traffictwin doctor`) | CLI `traffictwin doctor` | `src/traffictwin/doctor.py` |
| CLI | Bundle / evidence-pack helpers (import-first path, optional) | `src/traffictwin/cli.py` (`traffictwin bundle`, `traffictwin evidence`) | CLI `traffictwin bundle` | `src/traffictwin/ingestion/` |

Reachability is not evidence validity [SOURCE-DERIVED FACT — audit §2].
Each step remains honest about what it does not claim. Credentials are always
optional; hub renders deterministic blockers when absent and no live retrieval
is assumed in the deterministic demo path.

## 4. Sequence (one defensible workflow)

**Precondition** [IMPLEMENTATION-VERIFIED FACT]:
Local durable workspace exists (created via product's workspace bootstrap;
no production datastore). No credential is required to open the Hub in
read-only mode; BODS/National Highways live controls are gated behind
`BODS_API_KEY` / `NATIONAL_HIGHWAYS_API_KEY` and show explicit
`not_ready_credential_missing` when absent. This is the expected reviewer
posture with no external probe. The deterministic demo path makes **no live
network retrieval**; it replays stored SHAs and placeholder states.

1. **Inventory** — Open *Manchester Evidence Hub*
   (`src/traffictwin/ui/pages/manchester_evidence_hub.py`). Record the typed
   readiness for S01–S11: `software_support_typed`, `acquisition_typed`,
   `local_evidence_typed`, `freshness_state`, `blockers`, `limitations`,
   `next_action`. Expected: S01/S02 show `NOT_READY` without keys;
   S09/S10/S11 show `UNAVAILABLE`/`DEFERRED`/`BLOCKED` with explicit reasons;
   S03/S04 show `NOT_ACCEPTED` without accepted snapshots; S05/S06 show
   `ACCEPTED_AVAILABLE` (static). Output is a screen-visible readiness table
   plus a deterministic fingerprint derived only from typed state. No live call.

2. **Strategic context (bounded, credential-optional)** — Open *Manchester Operations*
   (`src/traffictwin/ui/pages/manchester_operations.py`). In `historical_replay`
   or `latest_available` mode, inspect S06 boundary and S05 signal layer
   (static). The National Highways card (S02, `REAL EXTERNAL NON-MANCHESTER DATA`)
   is shown as **strategic-road only**, with source health and attribution;
   when `NATIONAL_HIGHWAYS_API_KEY` is absent the card shows an honest
   `not_ready_credential_missing` blocker and no live retrieval is attempted
   in the deterministic demo. No Manchester city-road operational traffic is
   presented as available.

3. **Bus-only live context (bounded, credential-optional)** — In the same Operations page,
   inspect S01 BODS layer (`REAL MANCHESTER DATA`, bus-only). When `BODS_API_KEY`
   is absent the demo shows a deterministic `no_live` placeholder with
   staleness/outage legend; when configured locally, refresh yields a
   `live_vehicle` scene with per-bus markers, staleness labelling, and
   aggregate history — explicitly labelled *bus-only, NOT general
   private-vehicle traffic*. The deterministic demo contract does **not**
   perform live retrieval; validator and tests assert without credentials.
   Never treat S01 as S09 (`DESIGN-ONLY CAPABILITY`).

4. **Historical baselines (offline-first, no provider call)** — Without contacting providers,
   open the accepted DfT (S03, `REAL MANCHESTER DATA`) and WebTRIS (S04,
   `REAL EXTERNAL NON-MANCHESTER DATA`) catalogue views inside
   Manchester Operations. With fixtures/absent snapshots, the catalogues show
   either a bounded site/day chart or a `not_accepted` / `no_accepted`
   message. This preserves *historical-only* standing; WebTRIS is never shown
   as near-live (historical strategic-road reporting only). Provenance records snapshot SHA-256
   and acceptance path.

5. **Bounded synthetic what-if (deterministic, no live data)** — Open *Scenario Builder*
   (`src/traffictwin/ui/pages/scenario_builder.py`). Author one bounded
   synthetic incident (S07, `SYNTHETIC DATA`) over the pinned synthetic
   scenario (S08, `SIMULATION OUTPUT`). The product writes a labelled
   synthetic bundle with explicit provenance (row counts, file ledger, bundle
   SHA). Metrics/diagnostics over that bundle are deterministic and labelled
   `SYNTHETIC DATA` / `SIMULATION OUTPUT`; they are never presented as
   Manchester observation. The workflow stops at inspectable decision-support
   output (diagnostic table / export); no automatic actuation. No credentials,
   no external call.

Each step logs its input snapshot IDs / SHA-256 / timestamps and the step
output fingerprint; the sequence can be replayed from the same workspace
without new external calls. The deterministic demo path remains bounded and
credential-free for validators.

## 5. Outputs

- **Primary output** [IMPLEMENTATION-VERIFIED FACT]:
  A locally reproducible *Manchester Current Context Review packet*:
  evidence-hub fingerprint, Operations scene SHAs (or honest `no_live` /
  `not_accepted` placeholders), authored synthetic bundle ID, and a
  one-page reviewer summary stating which sources were `REAL MANCHESTER DATA`,
  `REAL EXTERNAL NON-MANCHESTER DATA`, `SYNTHETIC DATA`, `SIMULATION OUTPUT`,
  or `DESIGN-ONLY CAPABILITY` (explicit unavailable).

- **Provenance** [IMPLEMENTATION-VERIFIED FACT]:
  Every source that was touched carries its derivation chain: snapshot
  SHA-256, catalogue path, acceptance decision, parser version, and
  `source_health` state. Synthetic bundles carry the scenario-mutation
  ledger (`src/traffictwin/experiments/scenario_mutation.py`) or composer
  revision; simulation outputs carry netconvert 1.27.1 / synthetic-square
  fixture identity. Placeholders carry explicit `unavailable` provenance.

- **Quality** [INFERENCE]:
  Quality is bounded by source ceiling, not by UI rendering. S01 (`REAL MANCHESTER DATA`)
  is bus-only with staleness/error classification; S02/S04 (`REAL EXTERNAL NON-MANCHESTER DATA`)
  are strategic-road only; S03 (`REAL MANCHESTER DATA`) and S04 are historical;
  S07 (`SYNTHETIC DATA`) / S08 (`SIMULATION OUTPUT`) are synthetic with
  explicit labelling; S09/S10/S11 (`DESIGN-ONLY CAPABILITY`) are unavailable
  and contribute no quality.

- **Freshness** [IMPLEMENTATION-VERIFIED FACT]:
  Declared per source in §2. No source is relabelled fresher than its
  implementation truth: BODS cannot be promoted to general traffic
  freshness; WebTRIS historical cannot be promoted to near-live; DfT cannot be promoted
  to live.

- **Observable artifacts** [IMPLEMENTATION-VERIFIED FACT]:
  Evidence-hub fingerprint, scene SHAs or placeholders, synthetic-bundle ledger SHA,
  and one-page summary with honest classification — all verifiable without live
  deployment or provider account.

## 6. Limitations — what this workflow does NOT claim

- No live city-wide twin [`DESIGN-ONLY CAPABILITY`, unavailable; explicit unavailable input].
- No measured general/private-vehicle road traffic from BODS [SOURCE-DERIVED
  FACT — BODS ceiling is bus-only; `DESIGN-ONLY CAPABILITY` explicit unavailable input].
- No operational general-road current state [unavailable solely from the
  sources listed; would require a measured city-road feed that is not present;
  `DESIGN-ONLY CAPABILITY`].
- No design-only behavior represented as implemented: social media ingestion,
  full heterogeneous live ingestion, live twin fusion, and production
  deployment remain `DESIGN-ONLY CAPABILITY` / deferred.
- No journey-time prediction, forecasting, or SUMO-calibrated Manchester
  demand as part of this workflow. The workflow uses the pinned synthetic
  square only as a bounded `SIMULATION OUTPUT` placeholder; it does not claim
  observation-to-SUMO calibration (MAN-09 is `foundation_only`) or
  SUMO-to-VEC Manchester chaining (MAN-11 `foundation_only`).
- No RSU offloading/scheduling evaluation — this Manchester current-context
  workflow does not implement or evaluate RSU load-management. RSU investigations
  (TT-REQ-008, S-035) are out of scope and remain `SHOULD/open decision` where
  applicable; no RSU strategy material is imported into this use case beyond
  this honesty limitation.

## 7. Source-honesty scope note (narrow)

[EXTERNAL DECISION REQUIRED] TT-REQ-008 (SHOULD, Open decision YES) and the
S-035 direct Sandra body (SHA-256 `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed`)
concern RSU load-management and are **not part of this Manchester
current-context workflow**. This workflow records only that they are out of
scope, that TT-REQ-008 priority remains `SHOULD` and does not silently amend the
frozen baseline, and that no particular RSU controller (deterministic, learned,
or AI-based) is mandated here. No detailed RSU strategy investigation is
imported; the limitation preserves source honesty for Lane 9 reviewers without
re-scoping Use Case A.

## 8. Acceptance criteria and Lane 9 readiness

This workflow is accepted iff all of:

1. Every step in §4 resolves to an entry-point locator present at
   `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6` — mechanically checked by
   `scripts/validate_v08_use_case_a.py` and `tests/unit/test_validate_v08_use_case_a.py`,
   including discriminating checks that an unreachable locator and an unsupported
   evidence standing fail.
2. Every source in §2/manifest carries a correct human evidence standing
   (`REAL MANCHESTER DATA` / `REAL EXTERNAL NON-MANCHESTER DATA` / `SYNTHETIC DATA` /
   `SIMULATION OUTPUT` / `DESIGN-ONLY CAPABILITY`), freshness, and provenance;
   unavailable stays unavailable (S09/S10/S11 never reclassified as real);
   external non-Manchester (S02/S04) never presented as `REAL MANCHESTER DATA`.
3. No prohibited claim appears (live city-wide twin, BODS road traffic as general
   traffic, operational general-road current state, or design-only as implemented;
   external strategic-road not claimed as Manchester city-road).
4. Credentials remain optional/unavailable; no live retrieval is assumed in the
   deterministic demo path and Lane 9 replay.
5. Lane 9 (reproducibility/replay) can re-derive the packet from the same
   workspace using only the typed states and stored SHAs, without assuming a
   live deployment or provider account — satisfying the contract's
   "can drive Lane 9 readiness without implying a live deployment" clause.

The accompanying files provide machine evidence:

- `docs/closure/v08_alignment/use_case_a_manifest.json` — canonical source
  list with human evidence standing, step locators (with routes), and workflow binding.
- `docs/closure/v08_alignment/use_case_a_demo_contract.json` — deterministic
  offline-first demo inputs, sequence bindings, expected outputs, and red-lines.
- `scripts/validate_v08_use_case_a.py` — deterministic validator enforcing
  §2/§3/§4/§6 and red-lines; returns non-zero on any violation including
  unreachable entry point and unsupported evidence standing.
- `tests/unit/test_validate_v08_use_case_a.py` — focused unit coverage
  including discriminating mutations (unavailable→real, broken locator,
  unsupported evidence standing) that must fail and then pass on restore.

## 9. External decisions still required

All `EXTERNAL DECISION REQUIRED` items remain as in the final audit and
frozen baseline §F; this workflow does not close them:

1. Final supervisor-approved direction including whether TT-REQ-008 comparison
   becomes MUST — needs Sandra's original 4 August Outlook thread with headers.
2. Whether the data-engineering/what-if extension (TT-REQ-014, MAY) is to be
   lifted above MAY by a later Sandra instruction — not inferrable from
   owner choice or repository features.
3. Any TfGM/NTIS measured-traffic feed: provider response, access, schema,
   quota, time/DST, retention, licence, publication, and cost terms.
4. Randy artifact permission: primary written grant for any private code/data
   use beyond already-cited Q&A (S-007).
5. Calibration/uncertainty and held-out design for a Manchester
   observation-to-SUMO baseline (MAN-09/MAN-10) and Gate-D readiness — out of
   scope for this workflow but carried as blockers in the hub.

Unresolved decisions do not block honest reporting of the current/context
workflow; they bound what cannot yet be claimed.

---
*Honesty statement*: This document was drafted only from the staged sources in
`.harness/context/sources/` verified against `source_map.json`, the exact
v0.8 tree at `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6`, and the local
Manchester integration code. No Outlook header, `diss` filesystem, `vec_env`,
`tos-data`, or research branch content was invented or inferred as available.

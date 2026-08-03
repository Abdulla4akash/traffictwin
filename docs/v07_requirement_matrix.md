# v0.7 Requirement Matrix

A requirement-level audit of the normative MUST/SHALL/acceptance conditions in the
[v0.7 design](traffictwin-design-v0_7.md), built independently of existing status claims and
reconciled on 3 August 2026 against `main` at
`49be6a2db8a69409a1b92fb02e954db7cf1441f6`. State legend:

- **IT** — implemented and tested (cited code + test).
- **INA** — implemented but not accepted (works, gate/acceptance still open).
- **SM** — safe engineering work still missing (no external decision needed).
- **BX** — blocked by an identified external decision.
- **OOS** — intentionally out of scope for v0.7.

No row is marked `accepted`; all 15 capability rows remain `planned` under the completion rule
(§22.5). This matrix is a working audit aid, not an acceptance authority.

## §3 Non-negotiable constraints

| # | Constraint (design §3) | State | Evidence |
|---|---|---|---|
| 1 | Observation time is not retrieval time | IT | `integration/manchester/freshness.py`; `models.py` observation envelope; `test_manchester_freshness.py` |
| 2 | Freshness is source-specific via versioned policy | IT | `freshness.py` `SourceFreshnessPolicy`; `test_manchester_freshness.py` |
| 3 | Transit positions are not road-flow | IT | `bods.py` emits `LiveTransitVehicleObservation`; `test_manchester_bods.py`; UI labels "buses/transit" |
| 4 | Infrastructure is not telemetry | IT | `tfgm.py`/`tfgm_scene.py` infrastructure-only; `test_manchester_tfgm*.py` |
| 5 | Road domain is explicit (WebTRIS/NH strategic only) | IT | `webtris.py`, `national_highways.py`; `test_manchester_national_highways*.py`; assumption register rows 236, 241–245 |
| 6 | Survey counts retain their denominator | IT | `dft.py`/`dft_survey_view.py`; `test_manchester_dft*.py` |
| 7 | No direct observation-to-demand shortcut | IT | `calibration.py` refuses raw→demand; `temporal_profile.py` no missing-as-zero; `map_matching.py` preflight blockers |
| 8 | No source silently merged | IT | `map_layers.py` no cross-source totals; `projection.py`; `test_manchester_map_layers.py` |
| 9 | No page fetches arbitrary data | INA | `ui/pages/manchester_operations.py` reads local scenes; explicit source forms only. Accepted at Gate C, not release |
| 10 | No arbitrary URL/query execution | IT | `transport.py` allowlisted host/path, bounded; `test_manchester_transport.py` |
| 11 | Credentials are private | IT | `national_highways.py` transient header; `models.py` secret redaction; `test_manchester_transport.py` redaction tests |
| 12 | Raw evidence is immutable | IT | `snapshots.py` immutable raw + hashes; `test_manchester_snapshot_service*.py` |
| 13 | Interface is progressive | INA | Tier 1/2A/2B pages move machine detail to Advanced; `test_page_presentation_tier1.py`; final UX acceptance open |
| 14 | UI stays thin and native | INA | pages call services; `.streamlit/config.toml` native theme; UX acceptance open |
| 15 | No AI-authored science | IT | deterministic metrics/rules; `rendering/findings.py` template-only; assumption register row 174 |

## §20 Capability acceptance boundaries

| ID | Capability | State | Evidence / why not accepted |
|---|---|---|---|
| MAN-01 | Snapshot/source contract | INA | Gate A accepted; Gate-B snapshot service tested (`snapshots.py`); source-wide licence/retention/provider acceptance open (BX for licence facts) |
| MAN-02 | DfT adapter | INA/BX | Real acquisition + parser + replay tested; raw-count hour timezone **BX** (provider enquiry) |
| MAN-03 | WebTRIS adapter | INA/BX | Real site/day/quality tested; timezone **BX**; near-live correctly refused |
| MAN-04 | TfGM reference layer | INA | Real 2,529-row archive tested; final licence/release reconciliation open |
| MAN-05 | BODS live transit | INA/BX | Real acquisition + Bee scope tested; general reuse/publication and API registration documented; identifier privacy/retention + `BNVB` + full coverage **BX** |
| MAN-06 | Randy bridge | INA | Permission-safe panel tested; full workflow acceptance open |
| MAN-07 | Projection/freshness | INA/BX | Time-basis, freshness, spatial admission tested; DfT/WebTRIS canonical time **BX** (timezone) |
| MAN-08 | Manchester Operations | INA | Modes, maps, source cards, stale fallback tested; broad acceptance + manual accessibility open |
| MAN-09 | Observation-to-SUMO baseline | INA/BX | Complete Greater Manchester network foundation, map-matching, exact-artifact one-row review, calibration evaluator and temporal profile are tested; 174 named-person decisions, nine no-candidate treatments, viable demand/run evidence and scientific contracts remain external/human work |
| MAN-10 | Observed-vs-simulated comparison | BX | Engine + contract model tested; production contract registry empty pending supervisor decision |
| MAN-11 | SUMO-to-VEC workflow | BX | Lineage graph tested; needs accepted baseline (downstream of MAN-09) |
| UX-01 | Task navigation | INA | 34-page map, both routers, cross-page-state evidence (`test_cross_page_state.py`); manual + cutover open |
| UX-02 | Map-led home | INA | Focused home tested; human usability acceptance open |
| UX-03 | Responsive/accessible | INA/BX | Native theme, width migration, 140-snapshot audit; manual accessibility pass **BX** (human) |
| REL-01 | v0.6/v0.7 isolation | INA | Workspace isolation, copy, ADR-058 attestation, attested activation/backup/rollback and coexistence tested; package/CITATION aligned at `0.7.0`; licence/publication, final tag and real-workspace reconciliation open |

## §22 Testing/acceptance conditions (selected normative)

| Condition | State | Evidence |
|---|---|---|
| mph→m/s and coordinate golden values | IT | `test_manchester_webtris*.py`, `test_manchester_spatial*.py` |
| UTC/BST, DST missing/repeated hours, date-only | IT | `freshness.py`; `temporal_profile.py` day-type; `test_manchester_freshness.py` |
| Raw byte/hash immutability, atomic accept/quarantine | IT | `snapshots.py`; `test_manchester_snapshot_service*.py` |
| Credential/private-value log redaction | IT | `test_manchester_transport.py` redaction cases |
| Goodness-of-fit unavailable until MAN-10 contract | IT | `comparison.py` empty registry; `test_manchester_comparison.py` |
| Every geographic layer disabled until CRS admission | IT | `spatial.py`; `map_layers.py`; `test_manchester_spatial*.py` |
| No `use_container_width` in v0.7 UI | IT | grep-clean; UX-03 migration |
| 34-row inventory, unique URLs, no duplicate/unmapped | IT | `navigation_v07.py`; `test_navigation_v07.py` |
| Cross-page state survives reruns | IT | `test_cross_page_state.py` (added this session) |
| v0.6/v0.7 separate ports/workspaces, no collision | IT | `scripts/side_by_side_check.py` + evidence json |
| v0.7 reads/copies v0.6 registry without mutation | IT | `compatibility.py` copy; `test_release_compatibility_v07.py` |
| Migration transactional, backed up, rollback-tested | IT | `migration.py`; `test_release_migration_v07.py` incl. path-traversal refusal |
| Manual keyboard/contrast/landmark semantics | BX | `manual_accessibility_checklist.md` prepared; human execution required |
| Clean v0.6.0 checkout installs/starts independently | IT | `side_by_side_check.py` installs from v0.6.0 lockfile |
| Real-source case where required (per adapter) | INA/BX | narrow real probes recorded; broad acceptance + licence facts BX |

## Open external decisions (BX summary)

| Decision | Blocks | Prepared artifact |
|---|---|---|
| DfT/WebTRIS timezone, BODS identifier/privacy residual | MAN-02/03/05/07 canonical time, Gate B | `provider_enquiry_drafts.md` |
| Named-person review of 174 rows and treatment for nine no-candidate sites | MAN-09, Gate D | `integration/manchester_match_review.md`; `integration/manchester_gate_d_decision_support_20260802.md` |
| Calibration, uncertainty, demand and baseline decisions | MAN-09/10/11, Gates D/E | `evaluation/supervisor_contract_decision_form.md`; `integration/manchester_gate_d_decision_support_20260802.md` |
| Map-matching/calibration/comparison contracts | MAN-09/10 production registries | `supervisor_contract_decision_form.md` |
| First real v0.6 attestation | REL-01 real activation | `v06_attestation_procedure.md` |
| Manual accessibility + participant study | UX-03 / RQ16 | `manual_accessibility_checklist.md` |

## SM items found by this audit and fixed

An independent adversarial review of the 18 post-`v0.7.0-alpha.4` commits surfaced these safe
(no external decision) gaps, all now fixed with adversarial tests:

| Gap | Severity | Fix commit |
|---|---|---|
| Rollback receipt path-traversal overwrites active registry | HIGH | `0060056` |
| Migration activated-but-no-receipt window orphaned the previous registry | HIGH | `3e48085` |
| Temporal-profile reload accepted fabricated/overlapping exclusions | MEDIUM | `281aa87` |
| `v06-copy`/`v06-migrate`/`v06-rollback` raised uncaught tracebacks | MEDIUM | `e69ea55` |
| Comparison page showed unknown provenance as definite IMPORTED | MEDIUM | `c84385b` |
| Side-by-side evidence booleans hardcoded; no process-liveness check | LOW | `1b2908b` |
| `workspace_setup.md` still called activation/rollback unimplemented | LOW | `1b2908b` |
| Attestation loader refusal branches untested | LOW | `888e35e` |

The table above records the safe implementation gaps found and fixed at that audit checkpoint. A
later housekeeping pass corrected release/document drift, two broken local links, the stale
workspace-contract limitation and missing CI wheel-install/link gates; see the
[3 August housekeeping record](quality/v07_housekeeping_completion_20260803.md). No known safe
housekeeping item remains after that pass, but this is not a claim that the product-completion
work or any formal acceptance gate is complete.

Accepted (documented, not a defect within the trust model): attestation `attested_at` has no
upper bound (operator-controlled statement, not cryptographic authenticity); a true power-loss
before the migration backup rename can leave a dot-prefixed staging directory in the workspace
root (cosmetic; no registry impact). No unfixed SM gap remains at the audit's close.

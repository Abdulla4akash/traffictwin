# Seven-Minute Video Script — v08 Requirements Closure (Lane 11)

**Campaign:** `v08-requirements-closure` · **Lane:** `11` · **Worker:** `muse-11`
**Base SHA:** `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6` · **Prepared base:** `1185286b6dc651347b54039031ca9c28c639c38a`
**Feature:** Seven-minute video package (complements report, not recorded submission)
**Total duration:** 420 seconds (7:00) — exactly 8 segments, no gap or overlap
**Word budget:** 826 words total (~118 wpm, 7.0 min spoken) — validated by `scripts/validate_v08_video_package.py`

> Source-honesty labels used throughout: **SOURCE-DERIVED FACT**, **IMPLEMENTATION-VERIFIED FACT**, **RESEARCH-EVIDENCE FACT**, **INFERENCE**, **PROVISIONAL WORDING**, **EXTERNAL DECISION REQUIRED**. Violating label discipline is a contract defect.

## Honesty and boundary statement

- **SOURCE-DERIVED FACT** — Frozen baseline `732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2` (payload `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595`), final audit `0da517b76817fd653a6afee4ab0a9dca986e60f299ec54b662066c7d14d5dbb9`, S-001 brief, S-035 direct body `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed`.
- **IMPLEMENTATION-VERIFIED FACT** — file existence / behaviour at `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6`.
- **RESEARCH-EVIDENCE FACT** — committed E2/E2b/E2c/E2d campaign records (read-only refs, not rerun).
- **INFERENCE** — author reasoning, not a source.
- **PROVISIONAL WORDING** — wording that changes if an external decision supplies new primary evidence.
- **EXTERNAL DECISION REQUIRED** — blocked until Sandra / University / TfGM decides.

**Narration boundaries preventing overclaim (must be spoken or on-screen):**
- No claim that a video has been recorded or submitted — this is a preparation package only; recording is future work (TT-REQ-007 PARTIALLY_MET).
- No live-city or operational Manchester twin claim — Manchester view is bounded mixed standing with explicit unavailable inputs.
- No task-level inference — per-task counts are accounting, not independent replicates.
- No stakeholder approval claim — requirements remain PARTIALLY_MET pending ED-001..ED-007.
- No physical / scaling overclaim — service is fixed 1×, zero-backhaul idealisation, provisional queue ceiling.

**Prohibited phrases absent:** validator confirms no spaced overclaim phrase appears outside this line.

---

## Segment table (420 s exact, 8 segments)

| # | Segment | Start | End | Duration (s) | Words | WPM implied | Honesty |
|---|---------|-------|-----|--------------|-------|-------------|---------|
| 1 | Requirements — Negotiated Version 1 baseline | 0:00 | 0:30 | 30 | 63 | 126 | SOURCE-DERIVED FACT |
| 2 | Services — two bounded ITS services | 0:30 | 1:15 | 45 | 92 | 122 | SOURCE-DERIVED FACT + IMPLEMENTATION-VERIFIED FACT |
| 3 | Manchester / data engineering — bounded current-context view | 1:15 | 2:15 | 60 | 110 | 110 | IMPLEMENTATION-VERIFIED FACT |
| 4 | Existing strategies — strategy matrix | 2:15 | 3:10 | 55 | 110 | 120 | IMPLEMENTATION-VERIFIED FACT + RESEARCH-EVIDENCE FACT |
| 5 | Improved strategy — per-task least-busy placement | 3:10 | 4:10 | 60 | 108 | 108 | RESEARCH-EVIDENCE FACT |
| 6 | Evidence — one improved result with uncertainty and reproducibility | 4:10 | 5:15 | 65 | 141 | 130 | RESEARCH-EVIDENCE FACT |
| 7 | Short demo — click path (reachable artifacts only) | 5:15 | 6:15 | 60 | 114 | 114 | IMPLEMENTATION-VERIFIED FACT |
| 8 | Contribution / limits / conclusion | 6:15 | 7:00 | 45 | 88 | 117 | INFERENCE + EXTERNAL DECISION REQUIRED |

**Word budget check:** total 826, per-segment 63–141, all within 40–180. Timing check: 30+45+60+55+60+65+60+45 = 420.

---

### Segment 1 — Requirements — Negotiated Version 1 baseline (0:00–0:30, 30 s, ~63 words)

**Standing:** SOURCE-DERIVED FACT — baseline payload `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595`, whole-file `732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2`.

**Narration (63 words):**
> TrafficTwin is assessed against Negotiated Version 1, frozen at payload hash 58d9b0e7. Fourteen requirements: eleven MUST, two SHOULD, one MAY. Three MUST are trigger-conditional. Current status is PARTIALLY ALIGNED: three MUST are VERIFIED_MET, seven PARTIALLY_MET, one NOT_APPLICABLE, one SHOULD PARTIALLY_MET under the direct supervisor body S-035. No silent amendment. Remaining gaps are P0 core and P1 substantive, each bound to an external decision.

**On-screen:** `requirements_baseline_v1.json` payload hash card + `requirements_status_v08.json` MUST arithmetic 3+7+1.
**Limitation spoken:** PARTIALLY_MET means closure blocked pending Sandra / ethics / TfGM decisions; do not treat preparation as full alignment.
**Boundary:** No FULLY-ALIGNED claim.

---

### Segment 2 — Services — two bounded ITS services (0:30–1:15, 45 s, ~92 words)

**Standing:** SOURCE-DERIVED FACT (S-001 scope) + IMPLEMENTATION-VERIFIED FACT (code paths at bd4570fd).

**Narration (92 words):**
> We exercise the methodology with two bounded services, not a live operator product. Service A is a Manchester current-context review: an analyst demonstrates what is actually available — historic counts, bus positions when keyed, strategic-road snapshots — versus synthetic or unavailable inputs, without claiming a live city twin. Service B is deadline-aware VEC offloading: vehicles emit tasks, the frozen MAPPO actor chooses offload intent, infrastructure admits and places V2I tasks against backlog deadlines and a waiting-room ceiling. Both are bounded, offline-first demonstrations, exercised through committed fixtures and a single synthetic smoke scenario.

**On-screen:** Use-case A/B manifests + navigation locators.
**Limitation spoken:** Service definitions are provisional pending ED-001 confirmation of final RQs and whether VEC variants qualify as distinct services.

---

### Segment 3 — Manchester / data engineering — bounded current-context view (1:15–2:15, 60 s, ~110 words)

**Standing:** IMPLEMENTATION-VERIFIED FACT (bounded adapters at bd4570fd) — MIXED standing.

**Narration (110 words):**
> Manchester is shown as a MIXED bounded demonstration, not a live deployment. One honest view suffices: the Manchester Evidence Hub at slash manchester-evidence-hub plus Manchester Operations at slash manchester. With no credentials, both render honest blockers: bus positions and strategic-road snapshots show not-ready-credential-missing and no retrieval is attempted; the deterministic demo replays committed receipts only. Historic DfT counts and the static ONS boundary are accepted available; TfGM signal locations are static; general live road traffic from BODS and a continuous city-wide live twin are explicitly DESIGN-ONLY CAPABILITY and remain blocked. The view separates REAL MANCHESTER DATA from REAL EXTERNAL NON-MANCHESTER DATA — strategic-road only, never presented as Manchester city-road traffic.

**On-screen (one honest Manchester/current-data view):** `manchester_demo/current_view_artifact.json` MIXED packet — Hub readiness table, blocked unavailable rows, fingerprint from typed state.
**Limitation spoken:** Does not prove measured TfGM or NTIS feed delivery; no network retrieval in demo.
**Boundary:** No measured general-road traffic claim.

---

### Segment 4 — Existing strategies — strategy matrix (2:15–3:10, 55 s, ~110 words)

**Standing:** IMPLEMENTATION-VERIFIED FACT + RESEARCH-EVIDENCE FACT — matrix at `strategy_matrix.json`.

**Narration (110 words):**
> Existing strategies are compared through the frozen matrix, not by ad-hoc narrative. Three arms share one frozen actor and one incident-hour trace, differing only in infrastructure authority. Off uses strongest-link execution with no load balancing. JSQ without gate picks the least-busy RSU by remaining service work, argmin of rsu-busy-ms, common-target per substep, without a deadline gate — least-busy, not canonical queue-length. Ingress DLA keeps strongest-link execution and adds the backlog deadline gate. Direction A deterministic load balancing and directions B and C learning-based load balancing from the direct body S-035 are requested investigations, not mandatory implementations until authority confirms scope. Zero backhaul is a controlled idealisation, not a deployment claim.

**On-screen (one strategy matrix):** `strategy_matrix.json` — three arms, admission vs placement separation, information, authority, limits.
**Limitation spoken:** Matrix is bounded to one trace, one cap, one actor, fixed service; no universal superiority claim.

---

### Segment 5 — Improved strategy — per-task least-busy placement (3:10–4:10, 60 s, ~108 words)

**Standing:** IMPLEMENTATION-VERIFIED FACT + RESEARCH-EVIDENCE FACT — contract `improved_dynamic_strategy_contract.json` (per_task_dla).

**Narration (108 words):**
> The improved proposal is per-task sequential least-busy feasible placement, called per_task_dla in the E2d robustness study. After the actor's intent, infrastructure selects the feasible RSU with least remaining service work, recomputed for every candidate with immediate reservation of admitted service and lowest-index tie break. Deadline gate and waiting-room ceiling apply at the selected target. It is deterministic, not learned, and does not observe policy load. The bound is explicit: four matched fleet draws, seeds one to four, one incident hour, evaluator seed zero, 2.5× queue ceiling, fixed 1× service, zero backhaul. Naming follows the frozen E2d manifest f77afb231, not an invented label, and canonical JSQ is explicitly denied.

**On-screen (one improved result hook):** contract identity block + order/reservation diagram (no overclaim).
**Limitation spoken:** No Kubernetes deployment, no compute scaling, no staleness sensitivity in this bound.
**Boundary:** Not claimed as general Kubernetes or DRL scheduling solution without S-035 direction confirmation.

---

### Segment 6 — Evidence — one improved result with uncertainty and reproducibility (4:10–5:15, 65 s, ~141 words)

**Standing:** RESEARCH-EVIDENCE FACT — E2d per-task robustness comparison, one improved result shown.

**Narration (141 words):**
> One reproducible result is shown, with its limitation stated. At E2d matched fleet seed two, figure fig3_e2d_per_task_minus_ingress_seed2 gives per_task_dla minus ingress_dla offered attainment plus zero point zero zero five eight seven, paired difference plus 0.00587 versus the ingress_dla baseline, descriptive per draw. Across seeds one to four the paired differences are 0.00464, 0.00587, 0.00507, 0.00551, mean 0.00527, two-sided Student-t 95 percent interval 0.00442 to 0.00612, which excludes zero within the bounded four-draw replication and is the predeclared primary interval e2d_primary_interval. Admitted latency and forwarding share are reported alongside attainment as a trade-off, not a headline alone. Replication unit is fleet draw, not per-task count. Every row carries manifest SHA f77afb231, actor SHA 93c97059, and trace SHA e188ce. Reproducibility is via the committed comparison JSON and validation report at the frozen E2d head 80e8ae55, not via a live re-run in the video.

**On-screen (one improved result + reproducibility artifact):** single-row figure `per_task_dla minus ingress_dla` `fig3_e2d_per_task_minus_ingress_seed2` (seed 2 +0.00587, range 0.00464..0.00587, mean 0.00527, 95% interval 0.00442–0.00612) + artifact card with SHAs, manifest path, validation path.
**Limitation spoken:** Bounded four-draw replication; interval e2d_primary_interval 0.00442–0.00612 excludes zero within bound; cannot generalise beyond E2d hour/cap/service/actor; replication unit is fleet draw.
**Boundary:** No task-level significance inferred from per-task N.

---

### Segment 7 — Short demo — click path (5:15–6:15, 60 s, ~114 words)

**Standing:** IMPLEMENTATION-VERIFIED FACT — all locators verified at bd4570fd and prepared base.

**Narration (114 words):**
> The sixty-second demo follows an exact click path with no invented pages. One: open Manchester Evidence Hub at slash manchester-evidence-hub, verify readiness table shows blocked DESIGN-ONLY rows and deterministic fingerprint. Two: open Manchester Operations at slash manchester, inspect strategic-road National Highways card — blocked without key or labelled REAL EXTERNAL NON-MANCHESTER DATA when keyed. Three: open the bounded DfT historic catalogue and ONS boundary layer. Four: open the strategy matrix JSON and highlight the three arms. Five: open the per_task_dla contract and figure data CSV. Six: run traffictwin doctor and bundle diagnostics in read-only mode. All steps are offline-first with no live retrieval unless credentials are locally configured, and no step tours all pages.

**On-screen:** step counter + locator + route overlay matching `video_demo_click_path.md`.
**Limitation spoken:** Deterministic path makes no live network retrieval; private raw bytes stay workspace-only.

---

### Segment 8 — Contribution / limits / conclusion (6:15–7:00, 45 s, ~88 words)

**Standing:** INFERENCE (contribution) + EXTERNAL DECISION REQUIRED (limits) — no stakeholder approval claim.

**Narration (88 words):**
> Contribution is bounded: one reproducible infrastructure placement rule, one honest Manchester current-context packet, and a strategy comparison that distinguishes admission from placement. Limits are explicit: P0 gaps in service reconciliation, strategy assessment, and adequate QoS evaluation; P1 gaps in RQ confirmation, profiling reconciliation, video recording, three-arm RSU comparison, and RSU ceiling probe; seven external decisions remain open before final submission. No feature count, page rendering, or repository merge creates a negotiated requirement. Any future confirmation requires a new primary source ID and SHA with a new baseline hash.

**On-screen:** limitations register rows P0/P1 + external decisions ED-001..ED-007; closing hash banner.
**Boundary:** No submitted dissertation or assessed approval claim; overall status remains PARTIALLY ALIGNED.

---

## Word / timing budget validation table

Validated by `scripts/validate_v08_video_package.py`:

- Total 826 words, total 420 s.
- Each narration boundary present.
- No forbidden phrase.
- One Manchester view, one matrix, one improved result, one reproducibility artifact each present.

## External decisions referenced

ED-001 (TT-REQ-001/002), ED-002 (TT-REQ-008 / S-035 A/B/C), ED-003 (TT-REQ-004/005), ED-004 (TT-REQ-011), ED-005 (TT-REQ-013 ethics), ED-006 (TT-REQ-014 MAY), ED-007 (TT-REQ-012 TfGM). Each is EXTERNAL DECISION REQUIRED.

## Provenance

- Frozen baseline: `732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2` / `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595`
- Audit: `0da517b76817fd653a6afee4ab0a9dca986e60f299ec54b662066c7d14d5dbb9`
- S-035: `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed`

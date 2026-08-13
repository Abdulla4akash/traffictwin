# Video Storyboard — Seven-Minute Package (Lane 11)

**Campaign:** `v08-requirements-closure` · **Lane:** `11` · **Worker:** `muse-11`
**Base SHA:** `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6` · **Prepared base:** `1185286b6dc651347b54039031ca9c28c639c38a`
**Duration:** 420 seconds — 8 segments, no overlap or gap — validated by `scripts/validate_v08_video_package.py`
**Standing vocabulary:** SOURCE-DERIVED FACT, IMPLEMENTATION-VERIFIED FACT, RESEARCH-EVIDENCE FACT, INFERENCE, PROVISIONAL WORDING, EXTERNAL DECISION REQUIRED

**Honesty boundaries (on every relevant shot):** No recorded/submitted video claim, no live-city claim, no task-level inference, no stakeholder approval, no physical/scaling overclaim. See evidence checklist for per-shot standing/limitation.

**Required package elements shown:** one honest Manchester/current-data view or explicit blocked standing (Segment 3), one strategy matrix (Segment 4), one improved result (Segment 6), one reproducibility artifact (Segment 6). No full page-set tour.

---

| # | Segment | Start | End | Duration | Visual / Shot | Narration cue | Evidence standing | Limitation on shot |
|---|---------|-------|-----|----------|---------------|---------------|-------------------|---------------------|
| 1 | Requirements — Negotiated Version 1 | 0:00 | 0:30 | 30 s | Title card + code view of `requirements_baseline_v1.json` header with whole-file SHA `732075260b` panel; small inset `requirements_status_v08.json` MUST 3+7+1 row highlighted; baseline hash banner. No person footage. | Script Segment 1 (63 words) spoken over hash cards. | SOURCE-DERIVED FACT — frozen quotations / counts | PARTIALLY_ALIGNED only; do not imply FULLY-ALIGNED; gap P0/P1 rows visible in footer; PROVISIONAL WORDING if external decision changes counts |
| 2 | Services — two bounded ITS services | 0:30 | 1:15 | 45 s | Split screen: left `use_case_a_manchester_current_twin.md` manifest table (S01–S11 classified); right `use_case_b_vec_dynamic_service.md` flow (actor intent → admission → placement). Overlaid locator badges `src/traffictwin/ui/pages/manchester_evidence_hub.py` and `tos/contract.py`. | Script Segment 2 (95 words). | SOURCE-DERIVED FACT (S-001 service scope) + IMPLEMENTATION-VERIFIED FACT (reachable locators) | Services are bounded demos pending ED-001; not live operator product; VEC variants not yet reconciled as distinct services |
| 3 | Manchester / data engineering — bounded current-context view | 1:15 | 2:15 | 60 s | **One honest Manchester/current-data view** — capture of `manchester_demo/current_view_artifact.json` MIXED packet: Hub readiness table with colored blocker badges (green ACCEPTED, amber NOT_READY, red UNAVAILABLE/DEFERRED); Manchester Operations National Highways card showing honest `not_ready_credential_missing` blocker in demo; DfT historic catalogue + ONS GeoJSON thumbnail. Overlay labels REAL MANCHESTER DATA vs REAL EXTERNAL NON-MANCHESTER DATA. | Script Segment 3 (128 words). | IMPLEMENTATION-VERIFIED FACT — adapters verified at bd4570fd; MIXED standing | No live retrieval in deterministic demo; private raw bytes not committed; TfGM measured feeds remain unavailable; strategic-road never presented as Manchester city-road |
| 4 | Existing strategies — strategy matrix | 2:15 | 3:10 | 55 s | **One strategy matrix** — rendered `strategy_matrix.json` matrix card: three arms (off, jsq_without_gate, ingress_dla) with columns information / authority / admission / placement / cost / limits; zero-backhaul badge. No animation beyond highlight. | Script Segment 4 (115 words). | IMPLEMENTATION-VERIFIED FACT + RESEARCH-EVIDENCE FACT — E2b at `fe2ed4e9bd9043b19b96a5f179390db629b01ccb` | Bounded to one incident hour, one actor, one cap 2.5×/6220, fixed 1× service, zero backhaul, frozen actor without RSU load observation |
| 5 | Improved strategy — per-task least-busy placement | 3:10 | 4:10 | 60 s | **One improved strategy** — `improved_dynamic_strategy_contract.md` identity block (per_task_dla), order/reservation diagram (recompute argmin per candidate), deadline-gate formula overlay; fingerprint `af128cf08` banner. S-035 direction labels A/B/C shown as requested investigations inset. | Script Segment 5 (128 words). | IMPLEMENTATION-VERIFIED FACT (deterministic rule) + RESEARCH-EVIDENCE FACT (E2d bound) | E2d bound: seeds 1–4 only, no general controller superiority; not Kubernetes deployment nor DRL scheduling implementation |
| 6 | Evidence — one improved result with uncertainty + reproducibility | 4:10 | 5:15 | 65 s | **One improved result + one reproducibility artifact** — single forest/point card: `per_task_dla minus dla` at seed 2 (+0.02 offered), seed range −0.02..+0.02 inset; trade-off row (admitted latency, forwarding share); footnote replication_unit = fleet_draw. Right artifact card: manifest SHA `f77afb231`, validation SHA `0e3f27cd`, actor SHA `93c97059`, trace SHA `e188ce07`, raw checksums. | Script Segment 6 (135 words). | RESEARCH-EVIDENCE FACT — E2d `80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761` | One-draw descriptive, no interval without pre-declared plan; per-task N not replicates; bounded trace/cap/service; evaluator outcome not physical return |
| 7 | Short demo — click path (60 s) | 5:15 | 6:15 | 60 s | Screen-record mock (offline): 6 steps in `video_demo_click_path.md` with cursor overlay — Hub → Manchester Operations → DfT catalogue → strategy_matrix.json → per_task_dla contract/CSV → `traffictwin doctor` CLI output. Each step shows locator badge and route. Timer bar across bottom. | Script Segment 7 (126 words). | IMPLEMENTATION-VERIFIED FACT — locators verified at bd4570fd | No live network retrieval; no credential entered; no new live data fetched; rehearsal, not recorded submission |
| 8 | Contribution / limits / conclusion | 6:15 | 7:00 | 45 s | Closing card: contribution bullets (placement rule + honest packet + separation of admission/placement) left; limitations_register P0/P1 table and ED-001..ED-007 chips right; bottom hash banner with frozen SHAs `58d9b0e7…`, `7320752…`, `0da517b7…`, `08e0fedf…`. | Script Segment 8 (92 words). | INFERENCE (contribution) + EXTERNAL DECISION REQUIRED (limits) | PARTIALLY_ALIGNED remains; no FULLY-ALIGNED claim; new primary source requires new ID/SHA and new baseline hash |

---

## Timing proof (validated)

Segments: 0:00–0:30 (30) + 0:30–1:15 (45) + 1:15–2:15 (60) + 2:15–3:10 (55) + 3:10–4:10 (60) + 4:10–5:15 (65) + 5:15–6:15 (60) + 6:15–7:00 (45) = 420 s. No overlap, no gap. Start of first is 0:00, end of last is 7:00. Validator recomputes from script storyboard headings.

## Visual constraints honoured

- No full page-set tour — only listed locators appear.
- No live-city footage — Hub blockers remain visible.
- Rounded overlay colours are muted; no decorative headings beyond table.

## Provenance

See script provenance block.

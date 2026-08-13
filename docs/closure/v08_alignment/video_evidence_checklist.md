# Video Evidence Checklist — Seven-Minute Package (Lane 11)

**Campaign:** `v08-requirements-closure` · **Lane:** `11` · **Worker:** `muse-11`
**Base SHA:** `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6` · **Prepared base:** `1185286b6dc651347b54039031ca9c28c639c38a`
**Standing vocabulary:** SOURCE-DERIVED FACT, IMPLEMENTATION-VERIFIED FACT, RESEARCH-EVIDENCE FACT, INFERENCE, PROVISIONAL WORDING, EXTERNAL DECISION REQUIRED
**Validator:** `scripts/validate_v08_video_package.py` — every shot has a standing and a non-empty limitation; word/timing validated separately.

> Every row below is required. Removing any row or leaving standing/limitation empty fails validation (mutation: remove one evidence standing → validator must fail).

## Shot checklist (one row per evidence shot, 10 rows total)

| Shot ID | Segment (time) | Visual / Artifact shown | Artifact locator / SHA (exact) | Standing | Limitation (must be non-empty) |
|---------|----------------|-------------------------|-------------------------------|----------|--------------------------------|
| SHOT-01 | 1 — 0:00–0:30 | Baseline hash card | `docs/closure/v08_alignment/requirements_baseline_v1.json` payload `58d9b0e7…` / whole `73207526…` | SOURCE-DERIVED FACT | PARTIALLY_ALIGNED only; not FULLY-ALIGNED; gaps P0/P1 remain open — PROVISIONAL WORDING if external decision arrives |
| SHOT-02 | 1 — 0:00–0:30 | Status arithmetic card | `docs/closure/v08_alignment/requirements_status_v08.json` MUST 3+7+1 row | SOURCE-DERIVED FACT + IMPLEMENTATION-VERIFIED FACT | 3+7+0 is invalid arithmetic; NOT_APPLICABLE not counted as MET |
| SHOT-03 | 2 — 0:30–1:15 | Use-case A/B manifest table | `docs/closure/v08_alignment/use_case_a_manifest.json` + `use_case_b_manifest.json` | IMPLEMENTATION-VERIFIED FACT | Services are bounded demos pending ED-001; VEC distinct-service reconciliation remains P0 |
| SHOT-04 | 3 — 1:15–2:15 | **Honest Manchester/current-data view — MIXED packet** | `docs/closure/v08_alignment/manchester_demo/current_view_artifact.json` (MIXED, fixture `2026-08-12T15:29:03Z`) | IMPLEMENTATION-VERIFIED FACT — MIXED bounded demonstration | No live retrieval in deterministic demo; TfGM measured feeds unavailable; strategic-road never shown as Manchester city-road; credentials absent → honest blocker |
| SHOT-05 | 4 — 2:15–3:10 | **Strategy matrix** | `docs/closure/v08_alignment/strategy_matrix.json` (lane 05 frozen `c2ae9537…` in prepared base) | IMPLEMENTATION-VERIFIED FACT + RESEARCH-EVIDENCE FACT — E2b `fe2ed4e9bd9043b19b96a5f179390db629b01ccb` | One incident hour, one actor/cap/service/backhaul bound; JSQ is least-busy common-target, not canonical JSQ |
| SHOT-06 | 5 — 3:10–4:10 | **Improved strategy contract** | `docs/closure/v08_alignment/improved_dynamic_strategy_contract.json` fingerprint `af128cf08…` + E2d manifest `f77afb231…` | IMPLEMENTATION-VERIFIED FACT + RESEARCH-EVIDENCE FACT — E2d `80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761` | Bounded to seeds 1–4 only; deterministic placement not learning; no Kubernetes deployment claim; S-035 A/B/C are requested investigations not mandatory implementations |
| SHOT-07 | 6 — 4:10–5:15 | **One improved result** (per_task_dla vs dla, seed 2) | `docs/closure/v08_alignment/improved_strategy_results.json` row `fig_e2d_per_task_minus_dla_seed2` + `improved_strategy_evidence_index.json` | RESEARCH-EVIDENCE FACT — read-only E2d, fleet draw replication | One-draw descriptive only; range −0.02..+0.02 across seeds 1–4; no CI without pre-declared plan; per-task N not independent replicates |
| SHOT-08 | 6 — 4:10–5:15 | **Reproducibility artifact** | `docs/closure/v08_alignment/improved_strategy_evidence_index.json` SHAs + validation `0e3f27cd…` / raw checksums `eb5de7ce…` at `refs/harness/read-only/e2d` | RESEARCH-EVIDENCE FACT | Reproducible via committed JSONs and read-only head; not rerun live in video; evaluator outcome not physical result return |
| SHOT-09 | 7 — 5:15–6:15 | Click-path Hub + Operations captures | `src/traffictwin/ui/pages/manchester_evidence_hub.py` (`/manchester-evidence-hub`) + `src/traffictwin/ui/pages/manchester_operations.py` (`/manchester`) | IMPLEMENTATION-VERIFIED FACT | No live retrieval; blockers remain visible; not a full page-set tour |
| SHOT-10 | 8 — 6:15–7:00 | Limits / external decisions card | `docs/closure/v08_alignment/limitations_register.md` P0/P1 rows + ED-001..ED-007 chips | INFERENCE (contribution) + EXTERNAL DECISION REQUIRED (limits) | No stakeholder approval; overall PARTIALLY-ALIGNED; new source requires new ID/SHA and new baseline hash |

---

## Word / timing budget (validated)

Total words 880, total duration 420 s, per-segment durations 30,45,60,55,60,65,60,45 validated from `video_7min_script.md` table + storyboard timings. No overlap or gap.

## Required package elements

- One honest Manchester/current-data view or explicit blocked standing — SHOT-04.
- One strategy matrix — SHOT-05.
- One improved result — SHOT-07.
- One reproducibility artifact — SHOT-08.
All present; validator checks labels are non-empty.

## Forbidden claims absent

Checker in validator scans all four docs for overclaim phrases (spaced variants). Occurrence outside the enumeration line fails. Hyphenated negation forms (FULLY-ALIGNED, recorded-and-submitted, etc.) are not matched.

## Classification discipline

Every artifact above distinguishes SOURCE-DERIVED FACT, IMPLEMENTATION-VERIFIED FACT, RESEARCH-EVIDENCE FACT, INFERENCE, PROVISIONAL WORDING, EXTERNAL DECISION REQUIRED where applicable — standing column is the explicit per-shot label; PROVISIONAL WORDING and EXTERNAL DECISION REQUIRED appear in limitations where blocked.

## Mutation note

Discriminating mutation: remove any one standing cell (make empty) or add timing overlap/gap in script — validator must exit 1.

## Provenance

Frozen SHAs: payload `58d9b0e7…`, whole `73207526…`, audit `0da517b7…`, S-035 `08e0fedf…`, actor `93c97059…`, trace `e188ce07…`, prepared base `1185286b…`.

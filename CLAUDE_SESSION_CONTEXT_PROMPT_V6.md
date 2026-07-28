# Claude session context prompt v6 — TrafficTwin, night of 28→29 July 2026

Supersedes V5. V3/V4/V5 are historical; **this file carries the current state**.

Paste the block in §11 into a fresh Claude session started from
`~/AntigravityTest/diss-integration`.

---

## 1. READ THIS FIRST — three campaigns are running unattended right now

They were launched detached (`start_new_session` + `caffeinate` + pid file) and **survive
session/harness death**. Do not relaunch anything without checking these first.

| Campaign | pid file | What it is | State at 22:46Z 28 Jul |
|---|---|---|---|
| **inc-deep** | `data/vec-fresh/capacity-deep-inc/launcher.pid` (49660) | The ceiling-law prediction test | 1/12 cells, `cap-0.5-fs60` in flight |
| **inc-baseline** (crossover) | `data/vec-fresh/crossover-inc-baseline/chain.pid` (49935) | Waits for inc-deep, then runs | queued |
| **onset sweep** | `data/vec-fresh/onset-chain.pid` (50064) | Waits for crossover, then runs 3 legs | queued |

**Check them with:**
```bash
ps -p $(cat data/vec-fresh/capacity-deep-inc/launcher.pid)      # alive?
ls -1d data/vec-fresh/capacity-deep-inc/cap-*   | wc -l          # completed cells
ls -1d data/vec-fresh/capacity-deep-inc/.cap-*                   # in-flight (DOT-PREFIXED)
```
**In-flight cells live in dot-prefixed temp dirs**, so a `ls cap-*` count reads 0 until the
first cell completes. That is not a hang.

**On completion:** `uv run python scripts/capacity_grid_campaign.py <leg> analyze`, then write
a results record. Legs: `inc-deep`, `inc-baseline`, `we-deep`, `wd-am-deep`, `wd-pm-deep`.

**⚠ TIMEOUT RISK — the most important operational fact in this file.** Cells have a 7,200 s
timeout and campaigns are `halt_on_failure=True`. `inc` normally runs ~3,556 s (49% of the
ceiling). **Cell 1 of inc-deep took 4,825 s (67%) because heavy local analysis competed for
CPU.** Do **not** run test suites, array analyses, or network streaming while cells are
timed. A breach fails the cell and halts the campaign.

---

## 2. THE HEADLINE RESULT OF THIS SESSION — the capacity mechanism in closed form

Analysis-only over the 12 admitted pilot cells (Phase 118,
`docs/evaluation/pilot_dynamics_analysis_20260728.md`):

> **The tail-latency ceiling is linear in per-vehicle capacity.**
> p95 latency of *missed* tasks ÷ capacity = **39,959 ms, σ = 166, relative spread 0.41%**,
> across **all 36** (cell × task-class) pairs. I.e. `L(c) ≈ 40 s × c` — 100 s at cap-2.5,
> 60 s at cap-1.5, 40 s at cap-1.0, 30 s at cap-0.75.

**This closes the confirmed finding as a formula, not a narrative.** ~99% of latency mass sits
at the ceiling ⇒ mean latency is linear in capacity (predicted arm ratio 3.33, confirmatory
measured 3.24 — the 3% gap is the non-ceiling population). Every deadline sits **60–300×
below** the ceiling at every capacity ⇒ a task at the ceiling misses at cap-2.5 and still
misses at cap-0.75. **The −8,310.9 ms effect and the flat deadline null were never in
tension.**

Two structural findings beneath it:

- **The policy is bimodal, not probabilistic.** Counting only steps where a slot carries tasks
  (`veh_k > 0`): seed 0 has **1,413 slots that NEVER offload / 988 that ALWAYS do / only 87
  that ever mix** (seeds 1–2: 1393/992/103 and 1384/1018/86), **identical at all four
  capacities**. The "0.4026 offload rate" is a fixed partition of vehicles, not a
  per-situation rate; only ~3.5% ever switch behaviour.
- **Failure is concentrated by identity, not workload.** Failure-rate Gini 0.616–0.627, worst
  decile carries 34–36% of all failures — while **task-count Gini is 0.028**. "79%
  attainment" is near-perfect service for most vehicles and near-total failure for a
  persistent minority.

Also measured: implied deadlines read empirically from met-task latency (**T1 100 ms, T2
500 ms, T3 100 ms**); three qualitatively different failure modes (T1 misses are 3.7×
near-misses barely moved by the squeeze; T2 misses sit at the ceiling and fall 71%); and
saturation is **immediate**, not gradual (capacity ratio reached ~10% into the run, offload
share flat 0.398–0.407 throughout).

### The running test of it

`inc-deep` tests whether the law survives **extrapolation** 7.5× below its fitted floor.
Predeclaration `docs/evaluation/ceiling_law_prediction_predeclaration.md`, digest
`78dcd3ce…`, frozen before any cell ran:

| Arm | Predicted ceiling |
|---|---|
| cap-0.5 | 19,980 ms |
| cap-0.25 | 9,990 ms |
| cap-0.1 | 3,996 ms |

Pass band **±5%** (the pilot's own spread was 0.41%, so this is deliberately generous).
Outcomes: **HELD / REFUTED / BOUNDED** (holds at 0.5 but fails deeper = locates a lower
limit, a distinct finding). Also predeclared: the offload partition stays identical, p50 stays
~44 ms, and **cap-0.1 is the one arm where deadline attainment could finally move** (its
3,996 ms ceiling is only 8× the T2 deadline, against 200–1,000× at pilot capacities).

Cells run **seed-major**, so after 4 cells you have all arms at seed 60 → a preliminary read
before the full 12.

---

## 3. Observation chain restored — queue item 1, DONE (Phase 113)

All three artifacts the 27-July continuity audit called dead-but-regenerable are back, and
**regenerability held exactly**.

- **Subnetwork**: `scripts/clip_study_subnetwork.py` → 285,794 study edges of 804,611 in
  31.46 s; edge ids 100% preserved; all 150 committed Option-A counted edges present. Lives at
  `data/network-build/gm-study-manchester-la-20260728/` with `clip_receipt.json`.
- **Edge index**: rebuilt over the **parent** (the matching frame is the parent, *not* the
  clip — clipping would drop candidates outside the LA box). 804,611 real edges, geometry
  fingerprint `4019252e…`.
- **305-row v1.1 match artifact**: `scripts/regenerate_match_artifact.py` reproduces the
  25-July split **byte-for-byte** — v1.0 106/178/21, v1.1 131/165/9, 106 strict + 25 override
  acceptances, 51 override edges, 1,339 refused. Match Review page loads **174 queued, all
  pending**. Artifact at `<workspace>/manchester/match_results_v11_20260728.json`.
- **DfT had to be re-acquired** (only single-record `page[size]=1` probes survived). Both
  datasets returned the **same raw-fingerprint prefix** as the 25-July originals (342 rows/1
  page; 39,072 rows/79 pages) → the DfT historical archive is byte-stable.
- **New methodological finding:** the 25-July `reconciliation_fingerprint` `ae3ecff1…` is
  computed by **no committed code**, so it can never be verified. Lesson recorded: *a digest
  is only evidence if the code that computes it is committed beside it.*

---

## 4. Demand §2 diagnosis — queue item 2, DONE, and it REFUTES the hypothesis (Phases 114, 120)

`scripts/run_demand_diagnosis.py` reproduced the alpha.7 envelope faithfully (43,200 trips;
43,200 pool routes at 88,163,681 B vs recorded 88,163,497; 91.72% achievement vs 91.32%; zero
overflow; same two dominant shortfall edges).

- **Fringe bias is not real.** Boundary entry is **0.06%** of pool routes and 0.38% of demand
  — *below* the 1.88% unweighted base rate despite `--fringe-factor 5`. Broader
  `sumolib`-style definition (4.03% of edges) published so it can't be called definitional.
- **Long routes are real**: demand median 8.17 km / 134 edges (that 134 reproduces the
  truncated survivor's median exactly).
- **The binding constraint is neither.** Six of 150 counted edges hold **72.8%** of the
  shortfall, and Phase 120 explains why with two distinct causes:
  1. **Exactly 4 counted edges forbid passenger vehicles** (`allow="bus bicycle"` on A6/A56/
     A665) and they are **exactly** the 4 zero-coverage edges — 1:1, no false pos/neg. The
     pool is `--vehicle-class passenger`, so their 19,091 vehicles are unmet **by
     construction at any pool size**. A modelling mismatch: DfT counts buses too.
  2. **Two M56 edges at the clip boundary** hold 61.4% of the shortfall — the 1st and 2nd
     southernmost of all 150 counted edges, one with a **single** upstream edge within 8 hops
     against a typical 208.
- **Therefore all three predeclared variants target non-binding mechanisms.** V1 changes a
  0.06% population; V2 shortens routes that already can't reach distant edges; V3 doubles a
  coverage of zero. **Per §2's own rule the variant order is returned to the owner** — three
  options tabled in `docs/evaluation/demand_diagnosis_results_20260728.md` §6, **none taken**.
- **Closed the +3,152 B2 note:** the committed Option-A artifact is **150 edges / 1,800 cells
  / 2,027,275 vehicles** vs the record's 149 / 1,788 / 2,024,123. The 11 measured-zero cells
  match exactly, but no single edge totals 3,152, so **the committed artifact is not
  byte-exactly what alpha.7 consumed**. Quantified, not resolved.

---

## 5. Bus track — evening peak captured, MAN-05 defect named (Phases 115–117, 119)

**Owner opened an evening-peak window at 17:13 BST.** The pre-existing runner died after 2
snapshots on a MAN-05 `PARSE_REJECTED` (it catches only `BodsLiveControlError`, so
`BodsAcquisitionError` propagated). New `scripts/bus_attended_session.py` records the
fail-closed refusal in a ledger and **continues the window**; parser, promotion rule and
evidence boundary all untouched; ends after 8 *consecutive* refusals.

**Result: 83 accepted / 2 refused of 85** — the longest clean rush-hour window to date. Both
refusals absorbed; without the new runner it would have ended at 19.

| Session | Active | Concurrency max/median | Median speed |
|---|---|---|---|
| Night | 41 | — | 6.290 m/s |
| Dawn | 1,162 | — | 4.441 m/s |
| Morning peak | 1,433 | 1,216 / 1,192 | 3.518 m/s |
| **Evening peak** | **1,481** (52-snapshot matched; 1,522 full) | **1,250 / 1,215** | 3.610 m/s |

- **"Active" scales with session length** — always compare on a length-matched window. 1,522
  is NOT comparable with 1,433; **1,481 is**.
- **Buses at peak move 44% slower than at night.** Hourly resolution gives six monotone
  points and dissolves an anomaly: hour-for-hour the evening crest (1,462 veh, 3.369 m/s) is
  both denser *and* slower than the morning peak (1,429, 3.518) — the session average had
  mixed crest with recovery.
- **MAN-05 defect fully diagnosed** (`man05_refusal_diagnosis_20260728.json`): **all five** of
  28 Jul's refusals are one cross-operator `VehicleRef` collision — 1 group / 2 activities /
  always different operators / **zero conflicts under `(OperatorRef, VehicleRef,
  RecordedAtTime)`**. BNGN in all five, ANWE in four; three of four colliding refs sit in the
  overlapping 3000 series. Density-dependent: fired at 1,588–1,620 activities, never at the
  41-vehicle night probe. **One-line fix; MAN-05 is lead-owned and untouched.**
- `implied_speed_mps_max` 66.79 m/s again exceeds the proposed 32 m/s B1 ceiling (morning
  64.7) — two independent windows now support keep-32-and-drop-and-count. A recommendation,
  **not** a taken G2 decision.

---

## 6. The density gap — decision NOT taken, and a Colab route prepared

**The gap:** capacity is exactly inert at 139/163/175/215 slots and binds at 2,488, so onset
is bracketed in **(215, 2488]** and nothing we hold sits inside. The observed bus fleet peaks
at ~1,216–1,250 — inside the band.

**Locally unfillable.** `VecRunRequest` has **no fleet-size control** (only `fleet`,
`fleet_seed`, `rsu_capacity_per_vehicle`, `max_steps`; `trace_slots` is an *output*). So
density needs either a **derived trace** (would change what the allowlist means — every prior
extension admitted an *audited* artifact with a Gate-A hash, and B-BUS precedent deliberately
kept derived traces **outside** VEC-06) or a **runner interface change** (lead-owned). Both
recorded in `docs/evaluation/density_gap_options_20260728.md`, **neither taken**.

**Two routes queued instead:**
1. **Local onset sweep** (chained): `we-deep`, `wd-am-deep`, `wd-pm-deep` at capacities
   0.5/0.25/0.1. Hypothesis frozen: **onset capacity scales with density** (`ev` at 175 slots
   binds only at 0.1; `inc` at 2,488 responds from 2.5 — ~25× onset over ~14× density).
   Low-density traces are *minutes* per run, so 36 cells ≈ 1.8 h.
2. **B-DENSITY Colab pack** — `gpu/colab/bdensity_smoke.py`,
   `gpu/colab/BDENSITY_HANDOFF.md`, `docs/evaluation/bdensity_predeclaration_20260728.md`.
   **Prepared, NOT launched — the GPU track is Codex's lane.** On the synthetic environment
   density is a *parameter you construct*, and it uses **no producer data**, so it is
   permitted where the local campaigns are not.

**Why Colab cannot take the local campaigns:** Randy's permission covers **code** for Colab
and CSF with citation; **data blobs (traces, occupancy, checkpoints-as-data) are an open
ask**, and the record says this work *"remains local/CSF-only until the data half is
explicitly covered."* Every capacity campaign reads `trace_inc_fullrsu.npz`. **CSF is exempt
from that gate and is the sanctioned route** — and the real win there is parallelism: 60
queued cells are independent, so ~26 h sequential becomes ~1 h.

---

## 7. Gotchas learned this session — read before touching anything

1. **Verify design fingerprints byte-exactly after ANY edit to `capacity_grid_campaign.py`.**
   Bitten three times historically. Current known-good:
   `we b4da3a5b · ev efa83a78 · wd-am 2844fde2 · wd-pm 635a2cbe · ev-deep 72774544 ·
   ev-baseline 2f4e371b · inc-deep 5331e520 · inc-baseline 4784f5fc ·
   we-deep 0759b31f · wd-am-deep 1897f9f4 · wd-pm-deep 1d1c6ce6`.
   Moving an **in-flight** one breaks that campaign's own resume.
2. **Heavy local work steals cores from timed cells** and pushes them toward the 7,200 s
   timeout. Cell 1 hit 67% of the ceiling because of it.
3. **Foreground Bash wait-loops get killed by the harness** (happened twice). Use a
   persistent `Monitor`, never a `sleep`/`until` wait. **Detached jobs survived every kill.**
4. **`randomTrips --validate` rewrites its output**, so a closing-tag check alone can reuse
   the *wrong* artifact. `run_demand_diagnosis.py` now requires a `.done` marker written by
   the writer itself.
5. **Bus sessions must be selected by explicit UTC stamp ranges, not hour prefix** — a prefix
   truncated dawn to 43 snapshots and swallowed `065742Z`, the lone promotion from the
   aborted 07:57 BST attempt. Snapshot-id stamp is `name.split("-")[1]`.
6. **Bus speed must be per-segment** (`measure_session_progression`); median-displacement ÷
   median-interval is *not* a median speed.
7. Quarantine manifest file is **`quarantine-manifest.json`**, not `snapshot-manifest.json`.
   BODS wire bytes are **gzip**; the manifest sha covers the **stored** bytes, verify before
   decompressing.
8. In-flight campaign cells are **dot-prefixed** temp dirs.

---

## 8. Owner decision queue (nothing below is takeable by the agent)

1. **Ethics send — critical path**, longest lead time.
2. Three sends: Sandra, Randy (incl. the **data-off-machine permission**, which gates Colab
   *and* publication of data-derived aggregates), CSF.
3. **Demand variant order** — §2 refuted the hypothesis; three options tabled, none taken.
4. **B1 / G1–G5** bus signing; the 32 m/s ceiling recommendation.
5. **Density gap**: derived-trace ADR (option A) or runner change (option B) — or accept the
   two queued indirect routes.
6. **B-DENSITY**: route to Codex or decline.
7. R1 tos-data re-pin (trivial: one docs-only upstream commit `6e56393`).
8. Codex review + fast-forward (`CODEX_INTEGRATION_HANDOFF.md`); **`main` untouched**.
9. **Gate state to pass to Codex:** `mypy src tests` is red with **51 errors, all in
   `gpu/real_bcap|breward|bmask|bdomain`**; 12 are missing `flax`/`jax` stubs that a
   `pyproject` override would clear. `ruff` has 3 errors in
   `gpu/colab/bbus_synthetic_trace_smoke.ipynb`. This session cleared its own 9.

---

## 9. Boundaries (absolute)

Never fetch `../external` clones. Byte-frozen
`capacity_confirmatory_candidate_b_latency_primary.md`. Held-out seeds **{10–14} are spent**.
Registries and `data/vec-fresh` are read-only except through the campaign instrument.
Attended-only BODS, launched **detached**. Detached pattern for anything over an hour.
`/tmp` is volatile — preserve to `data/`. Buses are never general traffic. **Never fabricate
approvals**; approval provenance is *relayed delegation, never an owner-typed signature*.
**Never claim a provider mutated a dated file** — N1 is withdrawn.
`~/AntigravityTest/diss` is the owner's checkout; `cd` back to the worktree after touching it.

---

## 10. Where things live

- Register: `docs/experiments_and_findings_20260728.md` (rows 9e–9h, 18b, 18c, 22 are new)
- Dissertation evidence map: `~/Downloads/diss_mat/EVIDENCE_MAP.md` — **refreshed 28 Jul; the
  withdrawn Geofabrik-mutation claim was removed from it (it was listed as a headline
  number)**
- Phase claims: `AGENTS.md` §v0.7 Work Coordination, Phases **113–120**
- Memory: `traffictwin-governance.md`

---

## 11. THE PROMPT TO PASTE INTO A FRESH SESSION

```text
You are continuing as the owner-directed primary research/integration agent for TrafficTwin.

Read IN THIS ORDER, completely:
  1. memory file traffictwin-governance.md
  2. CLAUDE_SESSION_CONTEXT_PROMPT_V6.md at the repo root (V3/V4/V5 are historical)
  3. docs/experiments_and_findings_20260728.md — the consolidated register
  4. AGENTS.md §"v0.7 Work Coordination", highest phase numbers first (currently 113-120)

Then: git status, git pull --ff-only. Multiple agents push claude/complete-v0.7 (Codex is
active on the GPU/B-BUS track) — re-verify HEAD before EVERY edit, never force or rebase.

BEFORE ANYTHING ELSE, check the three detached campaigns described in V6 §1. They survive
session death. Do not relaunch without checking. If any has completed, run its `analyze` and
write the results record. THE FIRST ONE THAT LANDS IS THE IMPORTANT ONE: inc-deep tests a
pre-registered prediction of the tail-latency ceiling law (V6 §2) — predicted ceilings
19,980 / 9,990 / 3,996 ms at capacities 0.5 / 0.25 / 0.1, pass band ±5%, verdict HELD /
REFUTED / BOUNDED fixed in advance. Report whichever way it falls; a refutation is the more
interesting result.

DO NOT run test suites, array analyses, or network streaming while campaign cells are timed —
cells have a 7,200 s timeout with halt_on_failure, and contention already pushed one cell to
67% of that ceiling.

STANDING DELEGATION: "take reasonable choices and keep working" — ship autonomously with
honest recorded provenance; present owner decisions, never take them. Approval provenance is
relayed delegation, NEVER an owner-typed signature. Label ceiling owner_approved_candidate
everywhere. XAI framing is DROPPED. Full research-directions-v2 scope by 4 September.

Verify design fingerprints byte-exactly after ANY edit to shared campaign code — the
known-good list is in V6 §7, and moving an in-flight one breaks that campaign's resume.

Give me a concise status, then work the queue.
```

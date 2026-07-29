# Claude session context prompt v7 — TrafficTwin, night of 29→30 July 2026

Supersedes V6. V3–V6 are historical; **this file carries the current state.**
Paste the block in §12 into a fresh session started from `~/AntigravityTest/diss-integration`.

---

## 1. READ THIS FIRST — what is running unattended right now

| Work | Where | State at 00:18 BST 30 Jul |
|---|---|---|
| **inc-baseline (crossover)** | local, chain pid 49935, `data/vec-fresh/crossover-inc-baseline/` | **5/12 cells** (all seed-0 arms + cap-2.5-fs1 done; cap-1.5-fs1 in flight). ~1.7 h/cell → done **~12:00–13:00 BST 30 Jul** |
| **onset sweep** (we-deep / wd-am-deep / wd-pm-deep) | local, chain pid 50064 | queued behind crossover; 36 cells, ~2–4 h |
| **B-BUS sparse64, attempt ~5** | Colab G4 `bbus-sparse64rr-20260729-a5` (endpoint `usw4a0`) | **Codex's lane — do not touch.** Two prior sessions died mid-run (~3.1 h and ~6.8 h) |

Check locally: `ls -1d data/vec-fresh/crossover-inc-baseline/cap-* | wc -l`; in-flight cells are
**dot-prefixed**. Chain health: `ps -p 49935 50064`. Cells have a 7,200 s timeout with
`halt_on_failure` — worst observed 87.1% of ceiling under daytime load — so **do not run heavy
local work while a cell is timed**.

**When the crossover completes:**
1. `uv run python scripts/capacity_grid_campaign.py inc-baseline analyze`
2. `uv run python scripts/analyse_actor_crossover.py` — committed, digest-guarded, already
   exercised end-to-end on the ev pair. It applies the frozen crossover rule AND the decidable
   prediction (3) (relative latency-slope contrast ≤ 5%).
3. Write the results record; register row + phase claim.

**When the onset legs complete:** per-leg `analyze`, then
`uv run python scripts/verify_onset_scaling_prediction.py verify` (committed; INCOMPLETE until
all three legs have a campaign analysis; selftest reproduces the published ev onset).

## 2. What 29 July established (all pushed; register rows 9i–9k, 15b)

1. **Ceiling-law prediction test: HELD, 27/27 pairs** at 7.5× below the fitted floor
   (`ceiling_law_prediction_results_20260729.md`). The residual **sags** monotonically as
   capacity falls (T2 mean error +1.08% → +1.73% → +3.42%), same structure on all 3 seeds → the
   predeclared BOUNDED boundary sits just below cap-0.1. NOTE: class ordering is NOT
   "T2>T1>T3 everywhere" — only the T2-largest claim survives. p50 secondary was a **partial
   miss** (seed 61 runs 45.7–46.2 ms vs predicted ~44).
2. **The policy is a tier lookup** (`offload_partition_analysis_20260729.md`, row 9i):
   always-offload = **100% tier-0** in every cell examined (5 cells, 4 seeds, caps 2.5→0.1);
   never-offload contains **zero** tier-0. Confounds measured and eliminated (workload even,
   task mix identical; tier-1/2 miss a 500 ms deadline literally never). The ~79% attainment
   headline is a **fleet-composition artifact**.
3. **The confirmed −8,310.9 ms describes no vehicle** (same record §6): across a 25× squeeze the
   never-offload 60% of the fleet is **bit-identical** on every statistic (39.6 ms both ends,
   both seeds) while always-offload falls ~25,600→~1,070 ms. The ceiling law is an **RSU-queue**
   property (~92% of missed tasks are offloaded ones).
4. **RSU association claim WITHDRAWN same day** (row 9j, banner on
   `rsu_association_analysis_20260729.md`): counting `veh_best_rsu` per vehicle-step is the
   wrong unit (env `n_v2i` 2,191,339 vs 1,139,481) and attributed 22,939 sends to RSU 8 whose
   `rsu_busy_ms` is exactly 0.00 throughout. **What stands:** four RSUs at 95.8–97.9% of bound
   carry 99.1% of load, same four across caps/seeds; association is `argmax(all_v2i_q)` (source,
   line 747) with no load term. **Cause of idleness: undetermined.** Placement reading restored.
5. **B-DENSITY Phase 1 ran on Colab G4** (row 15b, `bdensity_phase1_results_20260729.md`): gate
   passed; the frozen design's source transform is **unnecessary** (`VEC_JAX_N_VEHICLES` +
   `VEC_JAX_RSU_MAX_CONCURRENT` are documented producer knobs — the allowance semantics, per the
   producer's own comment); `N_RSUS=2` is NOT overridable, bounding all claims. Phase 2 cost
   measured (`gpu/colab/bdensity_cost_probe.py`, manifest in `data/gpu-track/`): steady state
   5.92 s/update at N=512 → 31.08 at N=2048 (~N^1.2); full grid ≈ **99 GPU-h ≈ several× the
   whole Colab balance** → CSF work, not Colab.

## 3. THE REFRAMED HEADLINE (owner-agreed 29 Jul, in-session)

The owner's "worse wins" upset **already exists**: degrading the system (3.3× capacity squeeze)
**improved** the headline metric (−8,310.9 ms confirmed) at zero deadline cost — because the
squeeze only compresses already-failed tasks, the mean is ~99% tail mass, 60% of vehicles move
by exactly 0.0, and the policy never adapts (tier lookup). Together:

> **Standard VEC QoS metrics (mean latency, aggregate deadline rate) can be improved by
> degrading the system, with the improvement concentrated entirely in tasks that fail either
> way — shown by pre-registered experiment plus per-vehicle decomposition.**

Ch1 gap statement and Ch4 should be built on THIS, not on "capacity doesn't hurt deadlines".
Capacity is the *instrument*, not the finding. Honest limit: tail-vs-mean is not new in
queueing; the contribution is the rigorous demonstration in VEC offloading. One simulator, one
trace, one under-trained actor — always.

## 4. Permissions — MATERIALLY CHANGED 29 Jul

Owner states Randy granted **code + data + publication IN WRITING**. Recorded at
`docs/integration/randy_data_and_publication_permission_20260729.md` (28-Jul record carries a
superseded-in-scope banner; predeclarations bind it by path so it was not edited).
**Open action: paste the actual message text into that record** — currently second-hand.
Publication of the capacity numbers in the dissertation is now permitted **with citation**:
`docs/producer_citation_requirements.md` is the checklist (pinned commits verified; Etihad
district NOT city-wide; all confirmed capacity results are `inc`-only; SUMO + Lourenço entries
flagged "verify before use"). Colab remains budget-blocked regardless (~460 units needed vs
~196.6 known yesterday, minus whatever B-BUS attempts have burned).

## 5. Prepared but NOT launched (owner decisions)

- **Fleet-composition prediction** (`fleet_composition_prediction_predeclaration.md`,
  Phase 130): change ONLY the fleet preset `uk2030`→`synthetic` (tier-0 share 0.40→0.70), same
  actor/trace/cap-2.5/seeds {60–62}; mixture model predicts attainment **≈0.65 ± 0.03** vs
  measured 0.787. Uses the accepted `VecRunRequest.fleet` — admitted pipeline, no patch. 3
  cells. Owner choice: swap for the onset sweep (recommended; onset is marginal) or queue after.
  Sign-off explicitly records "no decision to run taken".
- **B-DENSITY Phase 2**: unaffordable on Colab; route to CSF (exempt + free) with the corrected
  env-var method. B-DENSITY is otherwise Codex's lane.

## 6. Colab CLI — hard-won operational facts

- Auth is the CLI's own token (`~/.config/colab-cli/token.json`) — independent of browser.
- **`colab status` reports the Jupyter kernel, not the GPU**: a training run driven by a
  detached subprocess shows IDLE while the GPU is loaded. Two B-BUS deaths are consistent with
  idle-reclamation of exactly that pattern; sessions adopted from the browser (not created by
  `colab new`) get **no keep-alive daemon**.
- Shared local state: `~/.config/colab-cli/sessions.json`. **Isolate with
  `colab --config /path/scratch.json`** (I did; Codex uses the default — never stop sessions you
  don't own; query by NAME not endpoint id).
- G4 = RTX PRO 6000 Blackwell 97 GB; `jax.default_backend()` returns `'gpu'` (the `"cuda"`
  JAX_PLATFORMS fix is for env vars, not the backend check).
- Deps for producer training on the VM: pip-install the B-CAP `EXPECTED_RUNTIME` set with
  `--no-deps` for `jaxmarl==0.0.4 gymnax brax jaxopt` (its pins conflict with jax 0.7.2), plus
  `mujoco mujoco-mjx glfw trimesh`. The `jax.tree_map` shim must be a **`.pth` file** in
  site-packages — Colab ships its own `/usr/lib/python3.12/sitecustomize.py` which shadows any
  uploaded `sitecustomize`.
- Owner's balance as of 29 Jul morning: **196.6 units, ~17.8/hr while two sessions ran**
  (per-session rate unresolved — re-read the page with exactly one session up).
- `colab run` self-cleans; always `stop` what you `new`. Costs: my whole B-DENSITY day ≈ 30 min
  GPU total; the first dead B-BUS session was allocated ~18.6 h.

## 7. Analysis gotchas added 29 Jul (on top of V6 §7, all still live)

- **Per-vehicle-step counts are NOT task counts** — the exact 9j mistake. `veh_best_rsu` is
  best-at-decision-time (−1 when `best_rsu_ok` false, i.e. saturated/out-of-range); per-task
  attribution needs the K_MAX substep admits (`rsu_inc_n`-style), which the arrays don't carry.
  Cross-check any send/task claim against env-reported `n_v2i`/`n_local`/`n_v2v` totals FIRST.
- Published σ=166 for the ceiling law is the **sample** (ddof=1) estimator.
- `slot_is_ev` is a dead end (EV share ~19–23% across tiers, no relationship).
- The evaluator runtime (association logic incl. `argmax(all_v2i_q)`) is only inspectable in an
  **in-flight** cell's `runtime/` dir — completed cells delete it.
- Fingerprint discipline unchanged: known-good list in V6 §7; verify byte-exactly after ANY edit
  to shared campaign code.

## 8. Session governance notes

- Two same-day retractions this session (coverage hypothesis; RSU association) — both caught by
  self-checks, both recorded with commits. **This is Reflection-chapter material, use it.**
- Standing delegation: "take reasonable choices and keep working"; owner decisions presented,
  never taken; `owner_approved_candidate` ceiling everywhere; XAI framing dropped; approval
  provenance is relayed delegation, never an owner-typed signature.
- Multiple agents push `claude/complete-v0.7` (Codex active on B-BUS/GPU). `git pull --ff-only`
  freely; re-verify HEAD before EVERY edit; never force/rebase.

## 9. Owner queue (nothing below is takeable by an agent)

1. **Ethics submission — critical path** (~1 week review; sessions drafted 11–22 Aug;
   deadline 4 Sep). Outstanding since 27 Jul.
2. Paste Randy's written permission text into the 29-Jul record.
3. Three sends: Sandra / Randy / CSF (CSF now doubly justified: B-DENSITY needs ~99 GPU-h).
4. Fleet-composition run: swap for onset sweep, queue after, or decline.
5. Demand variant order (§2 refuted the hypothesis; three options tabled).
6. B1/G1–G5 bus signing; R1 re-pin; Codex review + fast-forward (`main` untouched).
7. GPU-track gate debt (51 mypy errors in `gpu/real_*`, Codex's).

## 10. Where things live

- Register: `docs/experiments_and_findings_20260728.md` (rows 9i/9j/9k/15b new; 9j partially
  withdrawn — read its banner)
- This day's records: `docs/evaluation/{ceiling_law_prediction_results,offload_partition_analysis,rsu_association_analysis,bdensity_phase1_results}_20260729.md`
- Verdict/analysis code (all committed, all digest-guarded):
  `scripts/{verify_ceiling_law_prediction,verify_onset_scaling_prediction,analyse_actor_crossover,analyse_offload_partition,analyse_rsu_association}.py`
- Evidence dirs: `data/{ceiling-law-verdict,offload-partition,rsu-association}-20260729/`,
  `data/gpu-track/bdensity-*-2026072*/`
- Phase claims: AGENTS.md 122–132. Memory: `traffictwin-governance.md`.

## 11. Boundaries (absolute, unchanged)

Never fetch `../external` clones (pins verified intact 29 Jul: vec_env `068b4ea3`, tos-data
`f6c67acb`). Held-out {10–14} spent. Byte-frozen docs stay byte-frozen (density memo `00681a14`,
crossover candidate `b8f0efa2`, confirmatory candidate b). Registries and `data/vec-fresh` only
via the campaign instrument. Attended-only BODS. Detached pattern for anything >1 h. Buses are
never general traffic. Never claim provider mutation (N1 withdrawn). `~/AntigravityTest/diss` is
the owner's checkout — `cd` back after touching it. Never commit the Year-1 PDF or producer data.

## 12. THE PROMPT TO PASTE INTO A FRESH SESSION

```text
You are continuing as the owner-directed primary research/integration agent for TrafficTwin.

Read IN THIS ORDER, completely:
  1. memory file traffictwin-governance.md
  2. CLAUDE_SESSION_CONTEXT_PROMPT_V7.md at the repo root (V3-V6 are historical)
  3. docs/experiments_and_findings_20260728.md — the consolidated register
  4. AGENTS.md §"v0.7 Work Coordination", highest phase numbers first (currently 122-132)

Then: git status, git pull --ff-only. Multiple agents push claude/complete-v0.7 (Codex is
active on the B-BUS/GPU track, including a live Colab G4 session that is NOT yours) —
re-verify HEAD before EVERY edit, never force or rebase.

BEFORE ANYTHING ELSE, check the two detached local chains in V7 §1 (crossover pid 49935,
onset pid 50064). If the crossover has completed, run its analyze plus
scripts/analyse_actor_crossover.py and write the results record — it tests whether the
trained policy loses to the untrained baseline for the tier-0 40% of the fleet (the
candidate's own predictions say a crossover is UNLIKELY; report whichever way it falls).
If the onset legs have completed, run verify_onset_scaling_prediction.py.

DO NOT run heavy local work while campaign cells are timed (7,200 s timeout,
halt_on_failure, worst observed 87.1%).

STANDING DELEGATION: "take reasonable choices and keep working" — ship autonomously with
honest recorded provenance; present owner decisions, never take them. Label ceiling
owner_approved_candidate everywhere. The write-up headline is the REFRAMED one in V7 §3.
Publication is permitted with citation per docs/producer_citation_requirements.md; the
open permission action is pasting Randy's written message into the 29-Jul record.

Give me a concise status, then work the queue.
```

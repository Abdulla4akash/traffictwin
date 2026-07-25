# Research Directions — From Infrastructure to Findings

Date: 25 July 2026
Sources: supervisor meetings 1–2, Randy meetings 1–2, Randy's Year 1 report, the VEC-01
source-snapshot audit, and the accepted v0.6 capability boundary. Suggestions only — nothing
here overrides the evidence, permission, or semantic boundaries recorded in the repository docs.

## 1. What is actually being asked for

**Sandra (PI):**

- A non-obvious experimental finding — the "Morocco principle". Scenarios where the expected
  winner loses. "Local execution always wins" or "the newest algorithm always wins" is
  explicitly a poor dissertation in her words.
- A clickable what-if demo a traffic analyst could use ("buttons and a screen"; rough is fine).
  The what-if capability is the stated differentiator from Ethan's project.
- A small user evaluation (survey or interview, ethics application ~1 week, anonymised,
  business-school contacts available).
- Material usable in the group's papers (co-authorship offered).
- Still undecided by her: task-offloading focus vs journey-time prediction ("we will come up
  with something").

**Randy:**

- A resource-monitoring view over his TOS data ("Study Case 1: VEC resource monitoring") —
  implemented in the TOS Results Workbench within its semantic limits.
- Data-analysis help for training/validation; explainability framing.
- Direct feedback still open: "all the menus are cluttered so fix them"; a hinted
  "Study Case 2" for the dissertation.

**Conclusion:** the platform phase is complete. Every remaining mark comes from *using*
TrafficTwin: runs, findings, participants, one real-data scenario, and the write-up.

## 2. The constraint map (what can and cannot run)

Available today through the accepted VEC-07 runner:

| Axis | Values |
|---|---|
| Actors | exactly two: baseline Model C and UK-2030 Model C (both MAPPO, 17→64→64→3) |
| Traces | the five audited Manchester scenarios (`wd_am`, `wd_pm`, `ev`, `inc`, `we`) or any new VEC-06-preprocessed one-second FCD/network pair |
| Fleet | evaluator `--fleet` preset + `--fleet-seed` |
| Seeds | evaluator seed (integer) |
| Capacity | `--rsu-cap-per-veh` (bounded positive) |
| Steps | `--max-steps` bound |

Not available (do not plan experiments on these axes):

- Task arrival rate and task-class mix — training-side environment variables; the pinned
  evaluator does not expose them. Changing this needs a request to Randy.
- RSU count/placement as a direct override — only via trace preprocessing (VEC-06 placement
  controls, or the pinned Manchester default).
- Any new or heuristic policy — no training locally; Randy's 20-algorithm zoo (Lyapunov,
  DQN, always-local, …) is not in the supplied package.
- Mobile RSUs, signal timing, lane-closure toggles inside the evaluator — not evidenced
  in the source. (Lane closures *can* be modelled upstream in a new SUMO scene.)

Runtime reality: source wall times were 4 min – 4.3 h per run, median ~13 min; the local
CPU (jaxlib 0.4.30) full weekend run completed and matched source outputs to ≤3 ULPs.

## 3. Upset-hunting experiment designs (priority order)

All designs must be predeclared (design, cohort, thresholds, dev/held-out split) before
running, per the repository's own STA/R-rule discipline. Use the existing tooling: paired
common-seed study (STA-01), N-way ranking, TOST equivalence, regression gates,
nearest-flip and threshold-sensitivity explorers.

### 3.1 The capacity squeeze (strongest candidate)

- **Design:** sweep `--rsu-cap-per-veh` downward on the incident trace (`inc`, 2,488 peak
  vehicles in one hour) for both actors, ≥5 fleet seeds per cell.
- **Hypothesis:** a crossover capacity exists below which offloading collapses; the two
  policies degrade differently (graceful vs cliff).
- **Why it's the Morocco moment:** Randy himself named "traffic jam overwhelms the RSUs"
  as the interesting phenomenon (meeting 1). A policy that wins at capacity 2.5 and loses
  badly at 1.0 is a publishable upset.
- **Cost:** ~2 actors × 5 capacities × 5 seeds = 50 runs. Overnight locally; trivial on CSF.

### 3.2 The fleet mismatch (distribution shift, Randy's own thesis)

- **Design:** evaluate each actor on the *other's* fleet preset (baseline actor on `uk2030`,
  UK-2030 actor on the baseline fleet), common seeds, paired comparison.
- **Hypothesis:** policy advantage does not transfer across fleet distributions; the
  "wrongly trained" actor wins somewhere.
- **Why it matters:** this is the Year 1 report's central claim (DRL deteriorates under
  realistic distribution shift) demonstrated on Manchester traces instead of Berlin.

### 3.3 The scenario flip

- **Design:** both actors across all five traces with common seeds; N-way ranking per
  scenario family.
- **Hypothesis:** the winner inverts between calm (`we`) and stressed (`inc`, `ev`)
  scenarios — "the best policy depends on the day".

### 3.4 New what-if scenes (connects the science to Sandra's examples)

- **Design:** author a new SUMO scenario (stadium egress, lane closure on a key corridor),
  export one-second FCD + network, admit through VEC-06, evaluate both actors.
- **Why:** this is the literal Old Trafford / road-clearing what-if from supervisor
  meeting 2, executed end-to-end through the audited pipeline — and it is the demo story.

### 3.5 The missing baseline (one email to Randy)

The cleanest upset narrative ("a trivial policy nearly wins") needs a dumb baseline
(always-local or Lyapunov). Ask Randy for either a heuristic checkpoint or the summary
rows from his earlier algorithm comparisons. Any new artifact goes through the same
audit/permission gate as everything else. Bundle the ask with his "Study Case 2" question.

## 4. Manchester bus / open data — verdict

**The one bounded, high-value use:** scenario realism through the existing front door.

> Historical bus GPS (BODS/TfGM) + open network data → calibrate ONE SUMO corridor
> scenario (e.g. Oxford Road: real routes, bus lanes, stop dwell, real demand for a chosen
> 2-hour window) → one-second FCD → VEC-06 → traces → evaluate both actors.

This yields the claim "policies were evaluated on a real-data-calibrated Manchester urban
scenario" — directly answering the Year 1 report's realism gap and Sandra's data-fusion
vision, as one frozen, deterministic, citable bundle. Cap the scope: one corridor, one
window, historical data only.

**Traps — do not build:**

- Buses as mobile RSUs, trams as edge anchors, 5G/mmWave shadowing: the pinned environment
  has fixed per-trace RSU positions; modifying Randy's environment physics is out of scope,
  so no model could ever score these scenes. A proposal for Randy's PhD, not this project.
- Live GTFS-RT streaming or live dashboards: violates the import-first, deterministic
  architecture; near-live/live data is explicitly out of scope.
- Any new platform feature not consumed by an experiment or the demo.

## 5. Scaling on CSF (when and how)

- Per-run speed is similar to local (CPU-bound, tiny MLP). The win is SLURM array
  parallelism: wall-clock ≈ slowest single run + queue.
- Move to CSF only after a successful ~20-run local pilot, when a full factorial
  (hundreds of runs) is justified by pilot evidence.
- Pattern: install TrafficTwin + pinned clean clones on CSF; each SLURM job invokes the
  VEC-07 runner in the foreground with one typed request → full receipts preserved.
  Never run the raw evaluator outside the runner (no receipts ⇒ inadmissible); never reuse
  Randy's `eval_array.slurm` (author-specific paths, bypasses the evidence chain).
- Keep any one paired study on one platform; environments are recorded in receipts and
  float tails differ across hardware.

## 6. Marks-per-effort priority list

1. **Predeclared sweep + the finding** (§3.1–3.3). The single largest mark lever.
2. **User evaluation, executed.** Ethics application, survey, interview guide, and task
   script already exist as drafts in `docs/evaluation/`. Submit, recruit 4–6 participants
   (Randy, Ethan, students), run the what-if workbench sessions, write up.
3. **One bus-data-calibrated scenario** through VEC-06 (§4), if time remains after 1–2.
4. **Demo polish:** address Randy's menu-clutter feedback; script one clean end-to-end
   demo path (seed → what-if → run → comparison → report).
5. **Write-up:** `dissertation_mapping.md` and `dissertation_evaluation_plan.md` already
   map chapters to evidence; keep filling them as results land.

## 7. Explicitly deprioritised

- Any further platform/infrastructure capability work (the 39 v0.5 + 12 v0.6 capabilities
  are accepted; residual items are scientific/administrative, not engineering).
- Mobile-RSU / tram / live-feed integrations (§4 traps).
- New metrics or rules without a consuming, predeclared study.
- Anything that cannot appear in a dissertation chapter or the demo within the remaining
  timeline.

# Future Research Directions v2 — after the capacity finding (27 July 2026)

**Status: proposals only. Nothing in this document is approved, scheduled, or executed by
its existence.** Every direction respects the standing ceilings
(`owner_approved_candidate`; never validated/causal/supervisor-approved), the
predeclaration discipline (design before results), and the data boundaries recorded in
the integration documents. Supersedes the strategic content of the v1 research-directions
note (branch `feature-suggestions`) in the light of what is now measured.

**The anchor result** (details:
[the full narrative record](evaluation/capacity_study_detailed_findings.md)): across a
3.3× RSU capacity squeeze on the collapse-hour trace, the trained MAPPO actor's recorded
aggregate offload and no-target rates are exactly equal within each seed, deadline
attainment is flat (~79.1%), and mean latency falls 3.2×. **Update, 28 July 2026:** the
keyed comparison this paragraph called for has now been run on the admitted artifacts —
per-vehicle-slot action arrays including RSU/V2V targets are element-wise identical
across all four arms in every seed (0 mismatches in 8,956,800 cells × 9 pairs;
[evidence](integration/evidence/vec_pilot_keyed_action_comparison_20260728.json)). The
policy is **capacity-invariant at the keyed action level on this grid**, and
aggregate latency revealed the performance contrast, but aggregate summaries alone could
not distinguish unchanged decisions from changed downstream queueing consequences. Every
direction below either widens, explains, or exploits that result.

---

## Tier A — within-dissertation options (cheap, instrumented, trade-able at supervision)

### A1. Three-trace capacity grid ("is the invariance a property of the policy or the hour?")

- **Question.** Does capacity-invariance and the latency collapse replicate on the
  zero-event weekend (`we`) and the Champions-League event night (`ev`), or is it
  specific to the VSL-collapse hour (`inc`)?
- **Why it broadens.** It converts one anomalous hour into a systematic statement across
  three traffic regimes of one district — the cheapest genuine breadth available.
- **What exists.** All three traces are admitted (`we` from v0.6; `inc` ADR-062; `ev`
  ADR-065). The campaign instrument, admission chain, analysis harness, figure and table
  generators all apply unchanged.
- **What is needed.** One predeclaration (pilot-style, exploratory, fresh seeds disjoint
  from every existing cohort), owner approval, and modest compute: `we` runs ≈ 4 min/cell
  and `ev` is expected minutes-scale (first execution is a declared timing probe —
  ADR-065's open risk), so a 4-arm × 3-seed grid per trace is **hours, not days**.
- **Risks/limits.** `ev` runtime unmeasured until the probe; same single-actor,
  single-district limits as the pilot.

### A2. Actor crossover ("does the expected winner lose under squeeze?")

- Predeclared in structure ([draft](evaluation/actor_crossover_study_draft.md), candidate
  prepared); 2 actors × 2 levels × 5 fresh seeds = 20 cells ≈ two overnights local.
- New since drafting: STA-02 per-algorithm checkpoints (option G6-i) now exists, so true
  N-way ranking across the two audited actors is mechanically possible.
- Secondary payoff: does the *baseline* actor share the capacity-invariance? If yes, the
  phenomenon is not an artifact of one training run.

### A3. Stadium event-night study (the supervisor's founding example)

- The `ev` trace is Sandra's own what-if from the project's first framing; admitted and
  drafted ([skeleton](evaluation/stadium_event_study_draft.md) + prepared candidate).
  One predeclaration-signing and roughly an overnight.

### A4. The latency-tail study (analysis only, no new runs)

- The detailed findings record carries one confidence-labelled interpretation: means are
  seconds while deadlines are milliseconds, so the mean is plausibly tail-dominated and
  the squeeze truncates the tail. The per-task logs from the 12 admitted pilot cells
  already contain the answer: draw the per-arm latency distributions and quantify tail
  mass (e.g. share of latency-seconds above 1 s). Local CPU, an afternoon, and it turns
  the document's one open interpretation into a measured statement plus the
  dissertation's most explanatory figure.

### A5. Per-RSU load asymmetry (Study Case 1 analysis)

- The instrumented per-step data carries per-RSU state; the RSU Monitor surfaces it. A
  descriptive asymmetry study (which RSU saturates first, and does the squeeze equalise
  or concentrate load?) feeds both the explainability framing and the operator-facing
  Study Case 1 narrative. Local, analysis-only.

---

## Tier B — the GPU track (engineering starts now; real runs remain permission-gated)

**Venue and governance first.** Training belongs on GPU: the producer's JaxMARL path is
the `jax[cuda12]` stack (Colab-compatible; CSF3 is his documented venue). Three recorded
constraints bind every item: (1) moving the producer's code or data to a third-party
cloud requires his written permission (university GitLab + pending data-use contract) —
CSF avoids the question entirely; (2) our bus artifacts leaving the machine are
derived/pseudonymised only, never raw snapshots, and the BODS retention/republication
question (BETA-B-01) stays open; (3) results only become evidence by coming *home*
through the local admission chain — the CSF job-pack contract (export/verify, built
27 July) is the intended vehicle, and a verified import is deliberately **not** an
admission.

**Timing update.** The newer owner brief
([`CODEX_GPU_TRACK_BRIEF.md`](../CODEX_GPU_TRACK_BRIEF.md)) supersedes this document's
original *post-dissertation* sequencing only: build-out starts now, with owner Colab
compute units for synthetic stand-ins and CSF when access lands. It does not approve a
scientific run, permit producer assets on Colab, waive any predeclaration, or admit a
returned checkpoint.

### B1. Capacity-aware retraining ("give the policy eyes for the knob")

- **Question.** The source audit shows that the actor is not given the explicit RSU
  capacity/load control; the measured aggregate invariance motivates testing whether
  adding that signal changes decisions. Give it an explicit, deployment-observable RSU
  capacity/load signal and train across randomized capacity levels: does the invariance
  disappear, and does awareness buy deadline or latency performance — or does it
  destabilise training?
- **Implementation correction after source audit.** The producer's existing
  `VEC_JAX_CAP_SCALAR=1` option is **not** the pilot's RSU-capacity control. It replaces
  vehicle and V2V-target compute-tier one-hots with device service-rate scalars. The
  standard actor observation excludes `RSU_MAX_CONCURRENT`; `best_rsu_load_frac` is
  computed but not returned; and capacity is a module-import-time constant rather than a
  per-environment episode value. Trace replay exists, but no current launcher combines a
  true RSU-capacity observation with per-episode randomization over the pilot grid.
- **Training consequence.** Adding capacity and load/headroom changes the actor input
  shape. The current `--init-actor` path asserts that the saved checkpoint's input width
  already equals `OBS_SIZE`, so the 17-dimensional actor cannot be fine-tuned directly
  with that flag. From-scratch training is the primary defensible path; any input-layer
  expansion and warm start must be a separately specified and predeclared treatment.
- **Evaluation design (local, instrumented).** Three-actor comparison on identical
  seeds/levels — original, capacity-aware, baseline — via STA-02 N-way ranking per level
  (per-algorithm checkpoints) plus the descriptive slope comparison. Predeclared
  crossover-style rule for "awareness wins under squeeze".
- **Cost.** The strategic programme estimate is GPU-days, while the producer README
  reports roughly 15–30 minutes for one standard 5-million-step A100 run. Those are not
  interchangeable workloads: benchmark one corrected trace-replay seed before budgeting
  the campaign; evaluation remains hours local.
- **Hypothesis worth predeclaring.** Awareness changes decisions only below some
  capacity threshold — connecting the finding to the reward structure rather than the
  architecture.

### B2. Bus-native training (the strongest end-to-end result available to this programme)

- **Question.** Train a policy whose *native world is the real observed Manchester bus
  fleet* (via trace-replay training on the derived B1 session trace) and compare it, on
  the same bus trace and on the synthetic traces, against the two synthetic-trained
  actors. If synthetic-trained policies stumble on real motion where the bus-native one
  does not — and vice versa on synthetic traffic — the Year-1 distribution-shift thesis
  is demonstrated with genuinely observed data end to end.
- **What exists.** The complete derivation chain up to the signing gate: session-scoped
  identity policy, measured cadence (median 68 s), the trajectory library (gap ceiling,
  dwell, matched-share accounting), and the bridge into the evaluator's trace shape.
- **What is needed.** The attended peak session (data), G1–G5 signing, the derived-trace
  viability gate, then GPU training; honest labels throughout (derived scenario, never
  observed FCD; buses never general traffic; task workloads remain synthetic — only the
  *motion* is real).
- **Risk.** A ~300-vehicle peak fleet is the same order as the weekend trace's slot
  count, so numerically plausible — but nothing guarantees training converges on sparse
  schedule-structured motion; a negative result is itself the distribution-shift finding.

### B3. Reward-engineering variants (the producer's RQ3, instrumented)

- Train actors under varied deadline/energy/delay weightings and run each through the
  capacity sweep. Two published pathologies become measurable in one grid: the Year-1
  ~95%-local collapse (reward misalignment) and the capacity-invariance found here. The
  instrument's contribution: per-decision evidence distinguishes "policy changed" from
  "queueing changed" — exactly the distinction aggregate reward cannot make.

### B4. Train-×-evaluate trace matrix (systematic distribution shift)

- Train per trace regime (weekend / peaks / event / collapse), evaluate on the full
  matrix, rank with STA-02. The natural umbrella under which A2 and B2 are single cells;
  candidate joint-paper scale with the producer rather than dissertation scale.

## Codex technical suggestion — how to execute the GPU track

**Status: technical recommendation, not an approval or predeclaration.** This section
records the read-only source audit requested by the owner. It deliberately separates what
can be smoke-tested today from the scientific experiment that still has to be designed,
implemented, signed, and admitted.

### Start with the existing evidence, not the GPU

Before spending GPU time, complete A4 against the already admitted pilot outputs. Plot
ECDFs and p50/p90/p95/p99 latency; quantify the share above 1 s; separate task classes;
and relate the per-task latency/deadline arrays to the recorded per-step actions, vehicle
queues, and RSU load/headroom. Compare keyed actions across arms rather than inferring
sequence identity from equal aggregate rates. The current admitted artifacts do not
identify per-task admission/rejection and do not make physical completion or throughput
available; those outcomes require a future evaluator/metric extension and admission.

This matters because the producer environment assigns a fixed miss penalty regardless of
how far a task misses its deadline. An unavailable V2I choice is represented by a capped
latency of `10 × deadline`, while an admitted task may inherit a much larger RSU backlog.
The observed fall in raw mean latency can therefore be consistent with more capped
failures replacing extreme queued values; mean latency alone is not a safe training or
selection target. This explanation is a code-informed hypothesis. A4 can test its tail
component, but cannot settle the admission/rejection mechanism without the additional
outputs named above.

### Recommended B-CAP comparison

| Treatment | GPU training | What it isolates |
|---|---:|---|
| Frozen original actor | none | Historical reference on the measured grid |
| Random-capacity MAPPO, original 17-D observation | at least 5 seeds | Exposure to varied capacity without explicit observability |
| Random-capacity MAPPO, explicit RSU-capacity/load observation | at least 5 seeds | The effect of making the deployment control observable |
| Capacity-aware actor with revised reward | optional later treatment | Observability versus incentive/reward effects |
| Existing audited baseline actor | none | External algorithmic reference |

The random-capacity/original-observation treatment is essential. Comparing only the
frozen original against a newly trained capacity-aware actor would confound the new
observation with additional training and the randomized training distribution.

For every trained treatment:

- sample the predeclared `{2.5, 1.5, 1.0, 0.75}` capacity-per-padded-slot grid at episode
  reset, converting the selected level to `round(level × N)` concurrent tasks per RSU;
- hold trace source, fleet distribution, training budget, optimizer settings, masking,
  and randomization schedule identical between treatments;
- train at least five independent model/training seeds and treat the trained checkpoint —
  not an evaluation episode — as the statistical unit;
- evaluate every checkpoint on identical trace bytes, evaluator/task-channel seeds,
  fleet seeds, and capacity levels. Name the model, evaluator, and fleet seed roles
  separately; use fresh held-out evaluation cohorts disjoint from prior pilot and
  confirmatory cohorts rather than conflating their numeric identifiers;
- keep action masking off in the primary comparison because the original launchers and
  trace evaluator both use unmasked actor logits; masking is a separate predeclared
  factor if studied; and
- use `inc` as the targeted test and `we`/`ev` for breadth. Any trace or overlapping
  windows used during training are in-domain at evaluation, never held-out
  generalisation.

Predeclare both mechanism and performance outcomes. The mechanism set should include
keyed action-switch rate, local/V2I/V2V shares, and the actor-by-capacity slope. The
performance set should include deadline success, throughput, unavailable/rejected tasks,
latency distributions with their denominator and conditioning set explicit (all active
tasks; deadline-met versus missed; and, only after the evaluator extension, admitted
versus unavailable/rejected), p50/p90/p95/p99, tail mass, class-specific outcomes, and
queue/load state. Throughput and admission/rejection remain future instrument outputs,
not claims available from the pilot. Raw mean latency remains reportable, but never alone.

### Implementation required before B-CAP has a real command

1. Move the RSU limit from the module-level constant into JAX episode state or parameters
   so each vectorized environment can sample its own predeclared level at reset.
2. Add an explicitly named observation variant. The recommended starting design adds two
   deployment-observable values to the 17-D observation: normalized configured capacity
   per padded slot and selected-RSU load or remaining-headroom fraction. Freeze their
   units, normalization, clipping, and no-RSU semantics in the predeclaration.
3. Mirror the environment semantics in JAX and PyTorch and support the same observation
   in the trace evaluator. Do not silently reuse the existing `capscalar` name.
4. Use from-scratch MAPPO as the primary training path. If warm start is studied, define
   and test an explicit input-layer expansion/initialization rule and keep it as a
   separate arm.
5. Version the TrafficTwin evaluator/runner contract. The current path admits only two
   actor IDs and one `17-64-64-3` tensor shape, so a new checkpoint needs more than a
   `PINNED_ACTORS` row: reviewed source pins, actor-specific shape/observation identity,
   provenance, tests, and approval are required.
6. Make every training run emit a deterministic manifest containing the source commit,
   trace/config hashes, complete hyperparameters, seed, hardware/software identity, and
   output hashes alongside the curve, greedy-evaluation JSON, actor NPZ, decision-timing
   NPZ, and scheduler logs.
7. Prove the harness first with a tiny synthetic trace. Engineering smoke metrics are
   diagnostics, not scientific results, and must not be used to tune the signed design.

There is consequently **no honest one-line B-CAP launch command today**. In particular,
`slurm/launchers/run_capscalar_mappo.sh` trains the vehicle-compute-capability encoding,
not an RSU-capacity-aware policy, and must not be relabelled as B-CAP.

### What can be run now to prove the infrastructure

The producer's documented CPU smoke, from `jaxmarl/`, is:

```bash
JAX_PLATFORMS=cpu python scripts/train_mappo_vec.py \
  --total-timesteps 5000 --num-envs 2 --rollout-len 8 \
  --seed 0 --out-csv results/smoke.csv
```

The documented CSF GPU smoke, from the producer repository root after creating `logs/`,
is:

```bash
sbatch -t 0:15:00 -J smoke slurm/run_marl_csf.sh mappo 0
squeue -u "$USER"
sacct -j JOB_ID --format=JobID,State,Elapsed
```

These commands prove only the existing environment and CUDA route. They do not execute
B-CAP. The baseline full recipe is 5 million timesteps, 128 environments, rollout length
50, learning rate `3e-3`, one A100, four CPU cores, and 16 GB; retain those settings
between matched B-CAP treatments unless the predeclaration says otherwise. CSF uses the
producer's pinned Python 3.11/JAX 0.4.30 CUDA-12 environment. Colab may run synthetic
stand-ins now, but real producer code/data may enter it only after Randy's written
permission is recorded.

### Checkpoint homecoming and B-BUS

TrafficTwin's current CSF job pack exports and verifies **approved evaluation campaign**
identities; it does not submit training, transfer bytes, or admit a newly trained actor
([job-pack contract](integration/csf_job_pack_contract.md)). A returned checkpoint first
needs its training manifest and bytes verified, then a reviewed actor/evaluator pin and a
signed evaluation design. Returned evaluation artifacts pass job-pack verification where
applicable and then, separately, local ADR-061 fresh scientific admission. Neither a
training curve, a returned NPZ, nor a `verified` job-pack import is evidence by itself;
GPU-versus-CPU numerical reconciliation also remains a separate open question.

For B-BUS, build only the synthetic-fixture packaging and harness until the attended peak
session, G1–G5 signatures, and derived-trace viability gate exist. Raw BODS quarantine
snapshots never leave the machine. Train at least five bus-native seeds and compare them
with the synthetic-trained actors on common evaluations. Reusing the training bus
session for evaluation establishes in-domain behaviour only; a generalisation claim
requires a distinct session or genuinely held-out temporal material.

---

## Tier C — platform and data directions (independent of the GPU track)

### C1. Own-network experiments (unblocks with decisions E1–E5)

- The withdrawn N1 investigation established an internal source/decoded-identity recording error,
  not a Geofabrik mutation; the original network identity was reproduced. The predeclared demand
  rebuild (V0–V3, diagnosis library ready) leads to the first evaluations on **our own** DfT-count-constrained
  Manchester network rather than the producer's district — the platform's "second city
  block" without leaving Manchester. Hours-scale CPU once signed.

### C2. The methodological claim as its own artifact

- The broad contribution is not one more grid: **aggregate-reward policies can be blind
  to deployment-time resource controls, and only decision-level, provenance-complete
  instrumentation detects it.** A methods-style write-up (instrument + predeclaration
  discipline + the finding as demonstration) is the generalisable output — venue-ready
  with the producer, and the dissertation's Chapter 2/3 backbone either way.

### C3. Multi-district / multi-city generalisation

- Same instrument, different calibrated districts (subject to source/output identity separation,
  local retention and fail-closed digest checks—the corrected N1 lesson). Research
  cost is dominated by demand calibration, not by the platform.

### C4. Separated agentic-analysis layer (deliberately outside the evidence path)

- The early-meeting idea, kept excluded from evidence for trustworthiness reasons: an
  advisory layer that *reads* admitted artifacts and drafts hypotheses/recommendations,
  clearly labelled non-evidence. Only legitimate once the deterministic core is the
  authority — which is now demonstrated. A clean HCI/tooling follow-on.

### C5. Real-sensor validation

- WebTRIS/NH feeds are historical/operational only under the recorded provider limits;
  a validation study comparing simulated corridor behaviour against sensor-derived
  aggregates remains open pending provider answers (GA-DFT-1, GA-WT-1) — a data-rights
  effort more than an engineering one.

---

## Sequencing under the current owner direction

The dissertation remains constrained to 8,000 words with the 3 September submission
date. The later owner brief adds a separate target: build the full Tier A/B programme for
delivery by 4 September. The practical sequence is therefore:

1. **Now:** complete A4 first; continue only the Tier A work traded into scope; and build
   the B-CAP/B-BUS harness, manifests, predeclaration drafts, checkpoint-homecoming path,
   and synthetic dry run. This is engineering readiness, not a scientific execution.
2. **When the gates land:** put B-CAP on CSF or permitted Colab compute only after its
   corrected observation/state implementation, source review, signed predeclaration,
   venue access, and data/code permission are all recorded. Benchmark one seed before
   releasing the remaining predeclared jobs.
3. **B-BUS:** proceed only after the attended peak session, G1–G5 signing, derived-trace
   viability, and the same training/evaluation governance. C1 still waits on E1–E5
   decisions; N1 is withdrawn.
4. **Standing rule:** no scientific direction executes without its own predeclaration and
   recorded approval; no cloud boundary is crossed without permission; every return
   passes local admission; and a null anywhere is publishable by construction.

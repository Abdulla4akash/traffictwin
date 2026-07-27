# Future Research Directions v2 — after the capacity finding (27 July 2026)

**Status: proposals only. Nothing in this document is approved, scheduled, or executed by
its existence.** Every direction respects the standing ceilings
(`owner_approved_candidate`; never validated/causal/supervisor-approved), the
predeclaration discipline (design before results), and the data boundaries recorded in
the integration documents. Supersedes the strategic content of the v1 research-directions
note (branch `feature-suggestions`) in the light of what is now measured.

**The anchor result** (details:
[the full narrative record](evaluation/capacity_study_detailed_findings.md)): across a
3.3× RSU capacity squeeze on the collapse-hour trace, the trained MAPPO actor's
offloading decisions are bit-identical, deadline attainment is flat (~79.1%), and mean
latency falls 3.2×. The policy is **capacity-invariant**, and standard aggregate
evaluation could not have seen it. Every direction below either widens, explains, or
exploits that result.

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

## Tier B — the GPU track (Colab/CSF; post-dissertation or co-authorship with the
producer; every item needs the recorded permissions)

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

### B1. Capacity-aware retraining ("give the policy eyes for the knob")

- **Question.** The measured invariance means the policy cannot (effectively) see the
  capacity control. The producer's environment already exposes a **capacity-scalar
  observation variant and trace-replay training**. Retrain (or fine-tune with the
  existing warm-start flag) with capacity in the observation, across randomized capacity
  levels: does the invariance disappear, and does awareness buy deadline or latency
  performance — or does it destabilise training?
- **Evaluation design (local, instrumented).** Three-actor comparison on identical
  seeds/levels — original, capacity-aware, baseline — via STA-02 N-way ranking per level
  (per-algorithm checkpoints) plus the descriptive slope comparison. Predeclared
  crossover-style rule for "awareness wins under squeeze".
- **Cost.** Multi-agent training at the producer's documented scale (~3×10⁵ episodes) —
  GPU-days on Colab/CSF; evaluation is hours local.
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

---

## Tier C — platform and data directions (independent of the GPU track)

### C1. Own-network experiments (unblocks with decisions N1 + E1–E5)

- The Geofabrik mutation (N1) plus the predeclared demand rebuild (V0–V3, diagnosis
  library ready) lead to the first evaluations on **our own** DfT-count-constrained
  Manchester network rather than the producer's district — the platform's "second city
  block" without leaving Manchester. Hours-scale CPU once signed.

### C2. The methodological claim as its own artifact

- The broad contribution is not one more grid: **aggregate-reward policies can be blind
  to deployment-time resource controls, and only decision-level, provenance-complete
  instrumentation detects it.** A methods-style write-up (instrument + predeclaration
  discipline + the finding as demonstration) is the generalisable output — venue-ready
  with the producer, and the dissertation's Chapter 2/3 backbone either way.

### C3. Multi-district / multi-city generalisation

- Same instrument, different calibrated districts (subject to a new network pin
  discipline that assumes provider mutability from day one — the N1 lesson). Research
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

## Sequencing under the real constraint (8,000 words, 3 September)

1. **Now → submission:** Tier A only, and at most what supervision trades into scope
   (A4 is analysis-only and safest; A1 is the cheapest true breadth). Everything else is
   written up as instrumented-and-ready future work — which this document evidences.
2. **After submission:** B1/B2 as the co-authorship track with the producer (CSF once
   access lands; the job-pack contract is the transport); C1 when N1/E decisions land.
3. **Standing rule:** no direction executes without its own predeclaration and recorded
   approval; a null anywhere is publishable by construction.

# Research Directions — Fable 5 — 2026-08-11

Prompt for any agent or session working on TrafficTwin research. Supersedes the
2026-08-09 direction reports (ChatGPT Pro, Gemini Deep Think, Fable compass): those
were written BEFORE E2b/E2c completed and recommend work that is now done.

## State as of today (verify before acting, do not re-run)

- DONE: E0 (physical admission reference), E1 (admission-semantics sweep + offered-vs-admitted
  denominator critique), E2 (native placement, frozen MAPPO actor, Manchester incident trace),
  E2b (placement × admission factorial: admission gate +3.2 pp, placement −2.1 pp offered
  attainment), E2c (replication: DLA − ingress_DLA ≈ −2.1 pp, same sign on fleet seeds 0/1/2).
- Actor: frozen `mappo_modelc_17dim__envs128__lr3e-3__seed100` (17-dim obs, NO RSU-load term).
- GPU path: MIXED VERDICT from the A100 feasibility gate (2026-08-09,
  `~/AntigravityTest/a100_gate_outputs/a100-backend-feasibility-v1/`). The pinned
  jax 0.4.30 CUDA stack installs and runs (primitive gate PASSED, real A100-SXM4-40GB).
  BUT the ten-step cross-backend comparison FAILED (`decision_gate: fail`): one
  `veh_action` element FLIPS on the A100 (exact_required), float arrays differ at 1e-3
  to 1e-2 ms, and two same-command A100 runs were not byte-identical while Mac repeats
  were exact. CONSEQUENCE: evaluator/science runs stay on the Mac — Colab-run evaluation
  would fail the project's own identity gates. Colab/CSF are for TRAINING only; trained
  checkpoints come back and are evaluated locally. CSF3 SLURM scripts exist in
  `vec_env/slurm/` (incl. `run_marl_csf.sh`). CSF access applied for; Colab Pro active.
- Data permission from Randy is WRITTEN. Co-authorship offered.

## Experiments, ranked (do in this order)

### 1. E2c seed 3 — finish the CI (1 day, CPU)
Run the missing `dla` partner for fleet seed 3. Closes the predeclared 4-draw paired CI.
No new design decisions. Do this first.

### 2. Semantics sign-flip (2–3 days, CPU) — highest publication leverage
Re-run the four E2b cells under the LEGACY evaluator semantics (snapshot/clamp/
non-conserving, the E1 legacy mode). Question: does the reported arm ranking change or
reverse versus conserving semantics? If yes, the paper claim upgrades from "we critique a
metric" to "standard VEC evaluation semantics reverse experimental conclusions — measured."
Roughly 4–8 runs. Predeclare the comparison before running.

### 3. Capacity-aware MAPPO retraining — the Colab/CSF study (the substantial one)
The gate every audit imposed ("only if deterministic methods leave a residual gap") is now
SATISFIED: E2b measured the gap, and the 17-dim observation is load-blind by construction.

RQ: Can the vehicle actor learn what infrastructure placement could not fix — does
observing RSU load/headroom close the gap, measured as offered-task deadline attainment
on the held-out Manchester traces?

Four arms, ≥5 training seeds each (JaxMARL, 128 envs/GPU):
  A. Frozen 17-dim actor (control, no training).
  B. Retrained, 17-dim observation unchanged (controls for "more training helped").
  C. Retrained, observation + normalized RSU capacity + selected-RSU headroom (treatment).
  D. Optional: revised reward, separate arm — never combined with C.

HARD GATE before the grid: train ONE seed of arm B on Colab A100 and TIME it. The claimed
15–30 min/seed contradicts an earlier "GPU-days" estimate. The measured time sizes the
campaign; do not plan the grid from the claim. Note: the 17-dim checkpoint cannot be
fine-tuned into arm C (observation shape changes) — arm C trains from scratch; the RSU
limit must move from module constant into JAX episode state (touches `vec_jax.py`; change
BOTH trees or record PyTorch as out of scope).

Evaluation: drop every trained actor into the EXISTING E-series evaluator on the incident
trace (+ the weekend trace if budget allows). Paired per-seed differences, bootstrap CIs.
Either outcome publishes: "awareness closes the gap" or "it does not — fail-fast admission
stands."

Scale-up on CSF (same pipeline, joint-paper scale with Randy): train-by-regime ×
evaluate-across-traces matrix. Do NOT start it before arms A–C are analyzed.

### 4. Service-rate vs waiting-room (2–3 days, CPU, zero new code)
`--rsu-service-mult` already exists. At matched nominal resource, does real compute
(1×→3×) do what the waiting-room increase could not? Closes E1's "buffer ≠ compute"
claim from the other side.

### 5. Backhaul mini-sweep E3 (2 days, CPU) — condition boundary, NOT the headline
0/5/25 ms forwarding cost on the placement arms. Frame as a crossover condition map.
Two of three audits demote backhaul below a second traffic window; keep it bounded.

### 6. Latency-tail figure (one afternoon, analysis only, zero runs)
Per-task logs from the 12 admitted pilot cells already contain whether the capacity effect
is tail-truncation. The dissertation's most explanatory figure. Free.

## Rules (all inherited, all still binding)

- The vehicle actor stays FROZEN in every infrastructure experiment (arms above excepted).
- Deadline attainment is evaluator success, never physical task return. Never call the
  scaler "Kubernetes" (say Kubernetes-style). Never call a waiting-room change a compute
  change. One incident hour is not "Manchester".
- Matched per-seed differences are the statistical unit; millions of tasks in one run are
  NOT independent replicates.
- Predeclare every campaign before running (arms, seeds, primary outcome, stop rule).
  Independent review before any science run, per the E2b/E2c pattern.
- VERIFY prior art by DOI before citing. The QAAC (June 2026, "Anonymous, ResearchGate")
  citation from the Gemini report is unconfirmed. Babaiyan 2026 and PERFT-MAPPO 2026 are
  close prior art — check them first; they create urgency, not blockage.
- Do NOT build: learned dispatcher, real Kubernetes, LLM controller, placement × scaling ×
  staleness factorials, staleness (E5) before items 1–4 are done.

## Paper target

Workshop/short paper (IEEE VTC / VNC / ICC-GLOBECOM edge workshop):
E1 semantics + sign-flip + E2b factorial + E2c CIs + one bounded condition axis.
Working title: "Waiting Rooms Are Not Compute: Placement versus Pruning for a Frozen
MARL Actor under Conserving VEC Semantics."
The retraining study (item 3) is the second paper or the dissertation's closing chapter.

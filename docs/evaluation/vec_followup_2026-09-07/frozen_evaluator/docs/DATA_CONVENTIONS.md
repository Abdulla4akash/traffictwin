# Paper 2B — results tree (data-management conventions)

One directory per **campaign** = `(experiment set, region/row, model-variant)`:
`<set>_<region>[_<variant>]`. **No variant suffix = the frozen Paper-2A actor**
(mappo_modelc_17dim seed100). Any other policy — retrained, different obs
design, different training fleet — gets its own campaign dir, even over the
same region/cells/traces. Never mix campaigns in one directory; never reuse a
filename across campaigns.

```
results/
├── 2b0_anchor/                  # synthetic anchor, frozen 2A actor          [pending]
├── 2b1_manchester/              # DONE 2026-07-14: frozen 2A actor, 50 JSONs
├── 2b1_berlin/                  # Olympiastadion cells                       [pending]
├── 2b1_berlin_a100/             # A100 highway cells (viz-count window)      [pending]
├── 2b1_japek/                   # Jakarta-Cikampek cells                     [pending]
├── 2b2_retrain/                 # re-training remedy runs                    [pending]
└── 2b3_rsu_siting/              # RSU placement comparison (optional set)    [pending]

# examples of future variant campaigns (same traces, different policy):
#   2b2_manchester_capscalar/    — actor retrained with continuous
#                                  capability scalar instead of tier one-hot
#   2b2_manchester_ukfleettrain/ — actor retrained under the uk2030 fleet mix
```

## Variant registry
Every campaign README MUST name its actor checkpoint (full path + train
config). Registry of known variants:

| variant tag | actor checkpoint | notes |
|---|---|---|
| *(none)* | `setofexp3_modelc_17dim_final/mappo_modelc_17dim__envs128__lr3e-3__seed100_actor_params.npz` | frozen 2A baseline, 17-dim obs (tier one-hot ×2); trained in the 2A campaign (JaxMARL MAPPO, 128 envs, lr 3e-3, 25k ep, Model-C phase4_iid) |
| `capscalar` | **TRAINED 2026-07-14** — mappo+ippo × seeds 100–109 in `results/2b2_capscalar_{mappo,ippo}/` on fullport; eval actors seed100: mappo md5 f90a1d59… (popos-trained), ippo md5 b144baf0… (csf3). Full records: `2b2_manchester_capscalar_*/TRAINING.md` | obs 17→13: tier one-hots → service-rate capability scalar [0.0751, 0.4847, 1.0] (m0pa0 task mix, gpu_vehicle=1, hardcoded); **training fleet = uk2030, same as ukfleettrain** (capscalar-vs-ukfleettrain isolates the encoding; decided 2026-07-14, first 20 default-fleet jobs cancelled before start); tag `capscalar13_ukfleet2030`; eval needs `--cap-scalar`; obs-SPACE change ⇒ retrain required (§2.12) |
| `gridlocktrain` | **TRAINED+EVALUATED 2026-07-15 — NEGATIVE RESULT** (worse than baseline everywhere; inc 0.522/0.600 vs 0.709) → `results/2b2_gridlocktrain_{mappo,ippo}/` | 17-dim obs + uk2030 fleet + **gridlock-like traffic**: VEC_JAX_N_VEHICLES=120 (60 veh/RSU, 3× stress density), speeds 0–10 km/h OU σ=1 (static dense peer field); λ unchanged. Synthetic mobility ⇒ incident eval stays HELD-OUT. vs ukfleettrain isolates the traffic-condition change |
| `gridlocktrain_ft` | **TRAINED+EVALUATED 2026-07-15 — NEGATIVE RESULT, worst of all** (ft < scratch by 5–11 pp; inc 0.463/0.488; negative transfer + forgetting) → `results/2b2_gridlocktrain_ft_{mappo,ippo}/` | as `gridlocktrain` but **fine-tuned**: actor warm-started from the seed-matched ukfleettrain parent (`--init-actor`, new trainer flag; critic fresh — saved artefacts are actor-only). Same 5M budget ⇒ curves double as adaptation-speed measurements. ft-vs-scratch isolates the initialisation question for the §2.14 retraining cycle |
| `ukfleettrain` | **TRAINED 2026-07-14** — mappo+ippo × seeds 100–109 in `results/2b2_ukfleettrain_{mappo,ippo}/` on fullport; eval actors seed100: mappo md5 aca258e2… , ippo md5 cf625694… (both csf3). Full records: `2b2_manchester_ukfleettrain_*/TRAINING.md` | 2A recipe + VEC_JAX_FLEET_TIER_PROBS=0.40,0.35,0.25, EV_PROB=0.22 (uk2030); 17-dim obs unchanged |

**MANDATORY: every retraining gets a training record** — a `TRAINING.md` in its
campaign dir (and a row here) written *the day the run finishes*, containing:

- variant tag + one-line motivation (what changed and why)
- **training data source — exhaustively.** `synthetic` (native env) or
  `fcd-replay` (SUMO-trace training). For fcd-replay: the EXACT trace files
  (region, day, window, npz path + md5), and how they were sampled/windowed
  during training
- actor checkpoint full path + SHA/md5 of the `.npz`
- algo / framework / version (e.g. MAPPO, JaxMARL, jax 0.4.30)
- obs spec: dimension + feature list diff vs the 17-dim baseline
- training env config: model (C), fleet distribution used in training
  (tier_probs, ev_prob — this is now a VARIABLE, not a constant),
  stress flags (arrival λ, k-range, lanes, OU speed), N vehicles, RSUs
- budget: episodes/steps, n_envs, lr, other non-default hyperparams
- seeds trained (protocol: ≥5 like 2A) + which seed the campaign evaluates
- **training time**: wall-clock per seed + total, hardware, and the SLURM job
  IDs. **Training may be split across machines** (e.g. CSF3 gpuA A100 vs popos
  RTX 4090 Laptop queue-race, 2026-07-14): the record MUST list, per seed,
  which machine produced the used checkpoint (`<TAG>.machine.txt` written by
  the popos driver; SLURM logs for CSF3), and wall-clock statistics MUST be
  reported per machine, never pooled — different hardware, different times.
  Same-seed runs from different machines are statistically equivalent but not
  bit-identical (GPU arch changes reduction order); if both exist, the
  first-finished one is used and the duplicate archived
- final training metrics (completion / energy / T1 on the training distribution)
  + the training-curve CSV path
- eval-side note: which obs-dim flag the Model-C engine needs (`--obs-dim`),
  and whether the change is obs-SPACE (retrain was required) or
  obs-DISTRIBUTION (retrain was a choice) per the §2.12 taxonomy

## Conventions (apply to every new campaign)

1. **Result JSON naming:** `<region>_<cell>_<fleet>_fs<seed>.json`
   (regions: `manch`, `berlin`, `a100`, `japek`). The eval engine bakes
   trace name, fleet preset, achieved EV share/tier histogram and fleet seed
   into each JSON, so every file is self-describing even if misplaced.
2. **Traces on CSF3** (`~/scratch/phd-project-2b-poc/`): prefix with region,
   e.g. `berlin_trace_wd_am_fullrsu.npz`. (Manchester traces predate this rule
   and are unprefixed `trace_wd_*|trace_we|trace_ev|trace_inc` — do not reuse
   those names.)
3. **SLURM array manifests:** `manifest_<campaign>.txt`, output paths pointing
   into a per-campaign results dir on CSF3 (`fleet2030_results/` is the
   archived master of the 2b1_manchester campaign only — frozen, do not add).
4. **Sim inputs/FCD:** per-region dirs `<region>_fcd/<day>_<condition>/`
   (e.g. `manchester_fcd/2024-10-15_workingday/`), always isolated copies —
   never run SUMO inside Lourenço match-sim dirs.
5. **Each campaign dir gets:** the raw JSONs, an aggregate `summary_*.csv`
   (include an `actor` column — the engine bakes the actor filename into every
   JSON), and a `README.md` with provenance (day, window, T, maxN,
   engine/actor checkpoint, RSU rule) + headline table. See
   `2b1_manchester/README.md` as template.
5b. **Traces are shared across variants, results are not.** A variant re-run
   of Manchester reuses the same `manchester_fcd/` traces byte-identically
   (that is the point — only the policy changes); its results go in a NEW
   campaign dir. Comparing `2b1_manchester` vs `2b2_manchester_<variant>` on
   identical traces isolates the policy effect, like-for-like.
5c. **Train/eval contamination rule (fcd-replay variants).** When a variant is
   trained on SUMO FCD traces, every eval result over a trace that overlaps
   the training data (same day+window, or any sub-window of it) MUST be
   labelled **in-domain** — it is a fit score, not generalisation. Held-out
   evals (other cells, days, windows, regions) are the generalisation claims.
   The campaign README gets a train/eval matrix declaring, per cell:
   `in-domain` / `held-out (same region)` / `held-out (cross-region)`.
   Both kinds are useful — in-domain shows the remedy's ceiling, held-out
   shows whether it transfers — but they must never share a table row
   unlabelled. Suggested tags: `fcdtrain-<region><cells>`
   (e.g. `2b2_manchester_fcdtrain-manwd` = trained on Manchester WD traces).
6. **Protocol:** 5 fleet draws (`--fleet-seed 0..4`) per (cell, fleet) minimum;
   single-draw numbers are exploratory only and must be labelled as such.
7. After a campaign completes: pull JSONs local, update
   `SetofExperiments_2B.md` §1.13 + regenerate the docx, update memory.

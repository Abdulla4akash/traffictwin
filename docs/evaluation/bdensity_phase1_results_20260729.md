# B-DENSITY Phase 1 — engineering smoke run on Colab G4, and a correction to Phase 2's method

**Status: exploratory GPU-track diagnostic, `owner_approved_candidate` ceiling. Not
supervisor-approved, not confirmatory, no significance claimed. Non-admitted: nothing here is
scientific evidence, enters the registry, or is an actor-admission candidate. No producer data
of any kind was read or uploaded.**

Run under owner direction ("run the required experiments on google colab on g4 gpu as you see
fit, use the cli"), which resolved the open routing decision in the queue — B-DENSITY had been
prepared and deliberately not launched because the GPU track is the lead's lane.

## 1. What ran

`gpu/colab/bdensity_smoke.py` on a freshly allocated Colab **G4** via `colab run`, released
immediately afterwards.

| | |
|---|---|
| Accelerator | NVIDIA RTX PRO 6000 Blackwell Server Edition, 97,887 MiB, driver 580.82.07 |
| Backend | `jax.default_backend() == 'gpu'` — a real GPU, not a `--allow-cpu` dry run |
| JAX / Python | 0.7.2 / 3.12.13, `Linux-6.6.122+-x86_64-with-glibc2.35` |
| Grid | densities 128 / 1024 × capacities 2.5 / 0.25 × seeds 700 / 701, 2,000 steps |
| Manifest | `data/gpu-track/bdensity-phase1-20260729/bdensity_smoke_manifest.json` |
| Manifest sha256 | `66da4327e974f727500d58a82fb1289b91c6b99c29a3b0778420f6286bbf736d` |

The digest was printed by the script **on the VM** and re-verified byte-exactly against the
downloaded file locally, so the artifact is the one the GPU produced.

**Phase 1's gate passes:** the density axis responds at both capacities
(`{"2.5": true, "0.25": true}`), and the manifest has been inspected — which is what the
predeclaration requires before Phase 2 may start.

**No Phase-1 number is a result.** Its model treats capacity as a service rate, the opposite of
the real evaluator's backlog allowance; the script says so itself and the manifest carries the
direction warning. Phase 1 proves plumbing: the density axis, the non-GPU refusal path, and the
manifests.

## 2. The correction — Phase 2 does not need a source transform

Both the [predeclaration](bdensity_predeclaration_20260728.md) §4 and the
[handoff](../../gpu/colab/BDENSITY_HANDOFF.md) specify that Phase 2 reaches the density axis
"via a reviewed transform of a **disposable copy** of `vec_jax.py` — the same operation B-CAP
already performs for the 19-D observation". **That premise is wrong, and reading the producer
source rather than assuming is what found it.**

`../external/vec_env/jaxmarl/env/vec_jax.py` already exposes both axes as documented
environment variables:

```python
N_VEHICLES = int(os.environ.get("VEC_JAX_N_VEHICLES", str(N_VEHICLES)))          # line 60
RSU_MAX_CONCURRENT = int(os.environ.get("VEC_JAX_RSU_MAX_CONCURRENT", ...))      # line 74
```

and the producer's own comment on the second one states its purpose exactly:

> *match the eval engine's per-RSU concurrency scaling (**2.5 × fleet**, non-binding by design)*

That is the **allowance** semantics the handoff insists Phase 2 must preserve, straight from the
producer, and it matches the real evaluator's relation measured in the running campaign's own
receipt (`RSU_MAX_CONCURRENT=6220` at 2,488 slots = 2.5 × fleet). So a cell at density `N` and
capacity `c` is reached by setting

    VEC_JAX_N_VEHICLES        = N
    VEC_JAX_RSU_MAX_CONCURRENT = round(c × N)

with **no patch to producer source at all**.

**This is recorded as a deviation from the frozen design's §4, not a silent simplification.** It
is strictly the safer route: B-CAP's `prepare_source.py` rewrites nine separate source regions
under byte-exact preconditions, and every one of those is an opportunity to change semantics.
Using the producer's own documented knobs removes that surface entirely and keeps the
environment unpatched. The predeclaration's §6 boundaries are all still satisfied — no producer
data, no modification or fetch of the pinned clone, citation carried in every output. The frozen
grid, hypothesis, prediction and verdict rule are untouched.

The predeclaration is **not edited**: it is a frozen document and this record sits beside it.

## 3. Fidelity limits of the synthetic environment, measured not assumed

Reading the source also fixes the scale of what Phase 2 can claim. The producer highway is not a
miniature of the Manchester district:

| Property | Producer synthetic env | Local `inc` regime |
|---|---|---|
| RSUs | **`N_RSUS = 2`**, and *not* environment-overridable | 10 |
| Corridor | 2,000 m, `RSU_POSITIONS = (500, 1500)` | Etihad event district network |
| Episode | `EPISODE_LENGTH = 200` | 3,600 steps |
| Queue depth | `MAX_QUEUE_DEPTH = 10` | — |

At the top of the frozen grid this means 2,048 vehicles on a 2 km corridor served by **two**
RSUs. Density in this environment is therefore not comparable to concurrent slots on a replayed
trace, and no onset capacity measured here may be quoted as a property of `inc`, of the
Manchester traces, or of the Etihad district — which the predeclaration §5 already forbids, and
which the 2-RSU count makes concrete rather than a formality.

## 4. What Phase 2 still needs

Phase 1's gate is passed and the method is now correct, so the remaining work is a campaign
runner and compute, not a design question:

1. A runner in the shape of `gpu/real_bcap/run_campaign.py` — byte-verified producer sources,
   frozen predeclaration digest, non-GPU refusal, resumability, per-cell manifests — but
   **without** `prepare_source.py`, since no patch is required.
2. Dependency provisioning on the VM (`jaxmarl` and the frozen runtime set); the B-BUS track hit
   and fixed this same problem on 28 July.
3. The frozen grid: 6 densities × 3 model seeds = **18 from-scratch training jobs**, each
   evaluated at 4 capacities. Timesteps per job are deliberately unfixed by the predeclaration
   ("the compute budget is the owner's and the lead's to allocate"); B-CAP's precedent is 5M
   timesteps per job for 10 jobs.

That is a multi-hour G4 commitment, and it is the point at which this stops being a smoke test
and starts spending real budget.

## 5. Boundaries observed

- No producer trace, occupancy array, checkpoint-as-data, bus artifact, `.demo/`, quarantine
  material or `data/vec-fresh/` content was read or uploaded.
- Producer **code** use is covered by the recorded permission for Colab and CSF with citation;
  the data half remains an open ask and nothing here relies on it. The citation is carried in
  the manifest.
- The pinned external clones were read only — never fetched, never modified.
- A pre-existing **orphaned G4 assignment** (`gpu-g4-s-kkb-…`) was visible server-side with no
  local CLI record throughout. It was **not touched**: the CLI log shows nothing used it between
  08:10 and this session, and the B-BUS track was actively committing Colab work, so it is most
  likely a live browser session belonging to that track. It is flagged for the owner, not
  stopped by this agent.
- The session created here was released (`colab stop`), confirmed by `colab sessions`.

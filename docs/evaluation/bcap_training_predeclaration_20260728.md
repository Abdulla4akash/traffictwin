# B-CAP Full Training Predeclaration — Random Capacity Observability

**Status: owner-approved candidate design, frozen before full-scale outcomes.** Approval is
recorded separately and must bind the exact SHA-256 of this file. The label ceiling is
`owner_approved_candidate`: not supervisor-approved, validated, causal, or generalisable.

- Predeclared: 28 July 2026
- Permission basis: `docs/integration/randy_code_permission_20260728.md`
- Producer citation: Randy Putra; `gitlab.cs.man.ac.uk/e62992rp/vec_env` and
  `gitlab.cs.man.ac.uk/e62992rp/tos-data`; audited vec_env commit
  `068b4ea33e640f206ce6a7d04f3d6fae2ac831f4`; local clean snapshot
  `e98441196270b8fd4cc0eede892df4a0053b2185`; engine `v2_post_nrsus_fix`
- Venue: owner Colab compute, requested G4 GPU; code only, with citation; no producer data

## Question and equal-standing outcomes

The completed capacity study found that the 17-D actor cannot observe the deployment-time RSU
capacity control and is decision-invariant across the studied grid. Does randomized training plus
an explicit, deployment-observable capacity/headroom signal make a policy capacity-sensitive, and
does that sensitivity improve performance under squeeze?

All outcomes have equal standing: awareness may improve, harm, or leave performance unchanged; it
may alter decisions without improving outcomes; or it may fail to alter decisions. The last two
are publishable nulls, not failed experiments. Training reward alone never answers the question.

## Frozen implementation

The producer JAX environment is copied to a disposable GPU VM only after its four used source files
match recorded SHA-256 values. The reviewed transformation:

1. stores an `rsu_max_concurrent` scalar in episode state;
2. samples capacity-per-padded-slot from `{2.5, 1.5, 1.0, 0.75}` at reset, yielding ceilings
   `{50, 30, 20, 15}` for 20 vehicles;
3. uses that state scalar for saturation, load normalization, and RSU admission in both Model-B and
   Model-C;
4. retains the original 17-D observation for the hidden-capacity control; and
5. defines the 19-D treatment by appending configured capacity-per-slot divided by 2.5 and clipped
   to `[0,1]`, plus selected-RSU remaining headroom `1-load/capacity` clipped through the existing
   load fraction. If no RSU is in range, headroom is `0`. The existing `capscalar` variant is never
   used or relabelled.

This is JAX training code only. PyTorch parity and the trace evaluator extension remain checkpoint-
homecoming gates and are not inferred from a successful training campaign.

## Pre-run G4 platform amendment

Before any producer source was uploaded or model seed was executed, the requested G4's Blackwell
GPU rejected the producer's pinned JAX/JAXlib 0.4.30 CUDA code: a matrix-multiplication compatibility
probe failed because its `sm_90a` PTX could not target the future architecture. That disposable VM
was terminated with no experiment output. The clean replacement G4 passed the same probe under the
following exact stack, which is frozen for all ten matched jobs and enforced by the launcher:

`jax==0.7.2`, `jaxlib==0.7.2`, `numpy==2.0.2`, `flax==0.11.2`, `optax==0.2.8`,
`chex==0.1.92`, `distrax==0.1.9`, `gymnax==0.0.9`, `brax==0.14.2`,
`mujoco==3.10.0`, `mujoco-mjx==3.10.0`, `jaxopt==0.8.5`, `jaxmarl==0.0.4`,
`glfw==2.10.2`, and `trimesh==4.12.2` on an
`NVIDIA RTX PRO 6000 Blackwell Server Edition` G4. This deliberate platform deviation from the
producer's 0.4.30 environment is a standing limitation and makes the already-required CPU/GPU and
software-version reconciliation part of checkpoint homecoming. Both treatments use identical
runtime bytes, so the matched training contrast is not confounded by software version.

## Training matrix and hyperparameters

| Factor | Frozen value |
|---|---|
| Treatments | randomized capacity hidden in original 17-D observation; randomized capacity exposed in 19-D capacity/headroom observation |
| Model seeds | `{100, 101, 102, 103, 104}`, paired by identifier across treatments and distinct from seed 0 used by engineering smokes |
| Jobs | 2 treatments × 5 model seeds = 10 |
| Algorithm | from-scratch parameter-shared MAPPO; centralized critic; no warm start |
| Requested/effective budget | 5,000,000 / 4,998,400 environment steps per job |
| Vectorization | 128 environments; rollout length 50; 781 updates |
| Optimizer | Adam, learning rate `3e-3`, epsilon `1e-5`; gradient norm 0.5 |
| PPO | 4 update epochs; 4 minibatches; gamma 0.99; GAE lambda 0.95; clip 0.2; entropy 0.01; value coefficient 0.5 |
| Environment | synthetic producer highway; Model-C on; priority-scaled alpha off; default task and fleet distributions |
| Action masking | off |
| Diagnostic greedy evaluation | 20 episodes, 16 vector environments; never a scientific endpoint |

No hyperparameter, seed, budget, treatment, or stopping rule changes after the first full job starts.
A failed job halts the matrix. Infrastructure failure may be repaired and the same job resumed from
scratch; no partial model is selected.

## Checkpoint-homecoming evaluation declared now

The trained checkpoint—not an episode—is the statistical unit. All ten checkpoints return with
their source/configuration manifests and hashes. Before any performance claim they require a
reviewed actor/evaluator contract for both 17-D and 19-D shapes, CPU/GPU reconciliation, and fresh
local evaluation admission.

The evaluation uses common held-out evaluator contexts across every checkpoint and all four
capacity levels. It reports keyed action-switch rate, local/V2I/V2V shares, actor-by-capacity
slope, deadline success, explicitly conditioned latency p50/p90/p95/p99 and tail mass, class-level
outcomes, and queue/load state. Throughput and unavailable/rejected tasks are primary only if the
reviewed evaluator extension makes them explicit before evaluation begins; otherwise they remain
unavailable rather than reconstructed. Raw mean latency is never reported alone.

The primary mechanism contrast is the paired per-model-seed change in keyed action-switch rate
between capacity 2.5 and 0.75 for 19-D versus 17-D actors. The primary performance contrast is the
paired per-model-seed difference in deadline success at capacity 0.75. With five model seeds,
inference is descriptive with uncertainty and all seed-level values shown; no conventional
significance claim is made. `inc` is the targeted local trace; `we` and `ev` are breadth analyses
only after their own data/admission gates. No producer trace enters Colab.

## Boundaries and exclusions

- Producer code is cited in every returned bundle; source is executed temporarily but never
  rehosted in result archives. Producer traces, checkpoints, or data blobs never leave local/CSF.
- No bus data, raw BODS snapshots, derived bus artifacts, quarantine bytes, `.demo/`, or
  `data/vec-fresh/` material is used.
- Training curves, rewards, synthetic-highway completion and latency, and Colab greedy diagnostics
  are engineering diagnostics—not dissertation results and not a substitute for local admission.
- A returned NPZ is not actor-admissible until the separately reviewed homecoming process succeeds.
- No result may be called validated, causal, supervisor-approved, or generally representative of
  Manchester traffic.

## Approval gate

Launch requires `docs/evaluation/bcap_training_approval_20260728.json` to name this path, reproduce
its exact SHA-256, record the owner's explicit in-session direction to execute the design, and keep
`held_out_authorised` false. Any byte change after approval makes the launcher refuse.

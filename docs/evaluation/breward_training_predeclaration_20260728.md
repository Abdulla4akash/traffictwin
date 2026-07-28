# B-REWARD Full Training Predeclaration — Balanced versus Pure-QoS Reward

**Status: owner-approved candidate design, frozen before outcomes.** Approval is recorded in a
separate byte-bound receipt. The label ceiling is `owner_approved_candidate`: not validated,
causal, supervisor-approved, or generalisable.

- Predeclared: 28 July 2026
- Direction: Tier B3 in `docs/research_directions_v2.md`
- Permission: `docs/integration/randy_code_permission_20260728.md`
- Producer citation: Randy Putra; `gitlab.cs.man.ac.uk/e62992rp/vec_env` and
  `gitlab.cs.man.ac.uk/e62992rp/tos-data`; audited vec_env commit
  `068b4ea33e640f206ce6a7d04f3d6fae2ac831f4`; local clean snapshot
  `e98441196270b8fd4cc0eede892df4a0053b2185`; engine `v2_post_nrsus_fix`
- Venue: owner-managed Google Colab G4; producer code only, with citation; no producer or bus data

## Question and equal-standing outcomes

For a capacity-aware actor trained across randomized RSU ceilings, does removing the energy term
from the reward for deadline-met tasks materially change its learned decisions and synthetic-highway
diagnostics? The pure-QoS arm may improve, harm, or leave deadline, latency, energy, or action
behaviour unchanged. Any of those outcomes is acceptable; reward alone is never treated as a
performance result.

This comparison isolates the producer's existing, documented constant-alpha reward knob. It does
not introduce a new reward equation: with priority scaling disabled, `alpha=0.7` weights normalized
deadline slack at 0.7 and normalized energy at 0.3 for deadline-met tasks; `alpha=1.0` retains only
the slack term. OOM and deadline-miss penalties are identical between treatments.

## Frozen implementation and runtime

The campaign reuses the reviewed `bcap-random-capacity-observation-blackwell-v2` transformation.
It verifies the exact four producer source inputs, stores the sampled RSU ceiling in episode state,
samples capacity-per-padded-slot uniformly from `{2.5, 1.5, 1.0, 0.75}`, and exposes normalized
capacity plus selected-RSU headroom in the 19-D observation. The existing producer `capscalar`
variant is not used. The pinned external clone is never modified.

The Blackwell-compatible runtime is frozen to Python 3.12 with `jax==jaxlib==0.7.2`,
`numpy==2.0.2`, `flax==0.11.2`, `optax==0.2.8`, `chex==0.1.92`, `distrax==0.1.9`,
`gymnax==0.0.9`, `brax==0.14.2`, `mujoco==mujoco-mjx==3.10.0`, `jaxopt==0.8.5`,
`jaxmarl==0.0.4`, `glfw==2.10.2`, and `trimesh==4.12.2` on the requested
`NVIDIA RTX PRO 6000 Blackwell Server Edition` G4. The compatibility alias
`jax.tree_map = jax.tree_util.tree_map` is the same frozen API repair used by B-CAP.

## Training matrix

| Factor | Frozen value |
|---|---|
| Treatments | capacity-aware constant `alpha=0.7`; capacity-aware pure-QoS `alpha=1.0` |
| Model seeds | `{200, 201, 202, 203, 204}`, paired across treatments and fresh for this campaign |
| Jobs | 2 treatments x 5 model seeds = 10, all from scratch |
| Observation | 19-D capacity plus selected-RSU headroom variant in both treatments |
| Requested/effective budget | 5,000,000 / 4,998,400 environment steps per job |
| Vectorization | 128 environments, rollout length 50, 781 updates |
| Optimizer | Adam, learning rate `3e-3`, epsilon `1e-5`, gradient norm 0.5 |
| PPO | 4 epochs, 4 minibatches, gamma 0.99, GAE 0.95, clip 0.2, entropy 0.01, value coefficient 0.5 |
| Environment | synthetic producer highway, Model-C on, priority-scaled alpha off |
| Capacity | uniform per-episode randomization over ceilings `{50, 30, 20, 15}` |
| Action masking | off |
| Training-script greedy pass | disabled; replaced by the explicit common fixed-grid diagnostic |

No treatment, seed, optimizer setting, budget, or stopping rule changes after the campaign starts.
A failed job stops the matrix. Infrastructure repair may rerun that job from scratch; partial
checkpoints are never selected.

## Fixed-capacity diagnostic

Every returned actor is greedily evaluated on 32 synthetic episodes at each capacity-per-slot
level `{2.5, 1.5, 1.0, 0.75}`. All actors and levels use evaluator seed `42424242`, identical reset
keys, and identical per-step environment keys. Episodes run for the producer's fixed 200 steps.
The evaluator records the complete action tensor, per-level action digest, high-versus-low keyed
action-switch rate, local/V2I/V2V shares, deadline proxy, task-class deadline proxies, mean energy,
and mean latency. The checkpoint is the comparison unit; all five seed-level values are retained.

These are engineering diagnostics in the producer's synthetic training environment. They are not
held-out scientific evaluation, Manchester evidence, or checkpoint admission. The Model-C host
metrics preserve the producer training script's per-agent accounting and are labelled accordingly.

## Boundaries

- No producer data, producer checkpoints, traces, BODS material, bus-derived artifacts, quarantine
  bytes, `.demo/`, `data/vec-fresh/`, registry, or existing scientific campaign bytes enter Colab.
- Producer source executes temporarily under the recorded citation permission but is excluded from
  returned archives. Exact source and transformation hashes remain in manifests.
- A training curve, fixed-grid diagnostic, or actor NPZ is not scientific evidence and does not
  admit an actor. Homecoming still requires reviewed evaluator support, CPU/GPU reconciliation,
  a separate signed local evaluation design, and fresh admission.
- No output may be called validated, causal, supervisor-approved, or representative of Manchester.

## Approval gate

Launch requires `docs/evaluation/breward_training_approval_20260728.json` to bind this file and the
campaign/evaluator harness hashes, record the owner's explicit direction "do the next one", and
keep `held_out_authorised` false. Any byte change makes the launcher refuse.


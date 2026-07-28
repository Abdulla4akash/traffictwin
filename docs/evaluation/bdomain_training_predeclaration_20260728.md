# B-DOMAIN Full Training Predeclaration — Procedural Task-Distribution Matrix

**Status: owner-approved candidate design, frozen before outcomes.** Approval is recorded in a
separate byte-bound receipt. The label ceiling is `owner_approved_candidate`: not validated,
causal, supervisor-approved, or generalisable.

- Predeclared: 28 July 2026
- Direction: data-free precursor to Tier B4 in `docs/research_directions_v2.md`; literal trace
  training remains cloud-blocked by producer-data permission
- Permission: `docs/integration/randy_code_permission_20260728.md`
- Producer citation: Randy Putra; `gitlab.cs.man.ac.uk/e62992rp/vec_env` and
  `gitlab.cs.man.ac.uk/e62992rp/tos-data`; audited vec_env commit
  `068b4ea33e640f206ce6a7d04f3d6fae2ac831f4`; local clean snapshot
  `e98441196270b8fd4cc0eede892df4a0053b2185`; engine `v2_post_nrsus_fix`
- Venue: owner-managed Google Colab G4; producer code only, with citation; no producer or bus data

## Question and equal-standing outcomes

How much does a capacity-aware MAPPO actor depend on its procedural task-type training mixture?
Train separate actors in three producer-defined mixtures, then evaluate every actor on all three
mixtures using common numeric keys. In-domain actors may outperform, underperform, or tie
out-of-domain actors; rankings may change across task domain or RSU capacity; complete invariance
is equally publishable as a diagnostic null.

This is a workload-distribution experiment, not the real-trace B4 study. Mobility remains the
producer's synthetic highway. Only task-type sampling probabilities change; the task definitions,
vehicle motion, channel model, capacity observation, reward, optimizer, and training budget are
fixed.

## Frozen training matrix

| Training domain | Type 1 | Type 2 | Type 3 |
|---|---:|---:|---:|
| `default` | 0.20 | 0.30 | 0.50 |
| `safety_dominant` | 0.50 | 0.25 | 0.25 |
| `pilot_inspired` | 0.10 | 0.20 | 0.70 |

The producer's `uniform` `[0.33,0.33,0.34]` variant is excluded before outcomes. The compute
budget is spent on five independent checkpoints for each of three more distinct regimes rather
than weakening replication to add a fourth intermediate mixture.

| Factor | Frozen value |
|---|---|
| Model seeds | `{400, 401, 402, 403, 404}`, paired across training domains and fresh |
| Jobs | 3 domains × 5 seeds = 15, all from scratch |
| Reward | balanced constant `alpha=0.7`; priority scaling off; identical penalties |
| Observation | 19-D configured capacity plus selected-RSU headroom |
| Action masking | off during training and evaluation |
| Requested/effective budget | 5,000,000 / 4,998,400 environment steps per job |
| Vectorization | 128 environments, rollout length 50, 781 updates |
| Optimizer | Adam, learning rate `3e-3`, epsilon `1e-5`, gradient norm 0.5 |
| PPO | 4 epochs, 4 minibatches, gamma 0.99, GAE 0.95, clip 0.2, entropy 0.01, value coefficient 0.5 |
| Capacity during training | uniform per-episode randomization over ceilings `{50,30,20,15}` |

The campaign reuses the reviewed `bcap-random-capacity-observation-blackwell-v2` transformation
and exact Blackwell runtime used by B-CAP/B-REWARD/B-MASK. A failed job stops the matrix. An
infrastructure repair reruns that job from scratch; partial checkpoints are never selected.

## Frozen train × evaluate diagnostic

Every checkpoint is greedily evaluated in all three task domains at capacity-per-slot `2.5`
(ceiling 50) and `0.75` (ceiling 15). Each of the six cells uses 32 episodes of 200 steps with
evaluator seed `44444444`, identical reset-key and step-key numbers, and the exact declared
import-time task probabilities. The evaluator records complete action tensors with shape
`[3,2,32,200,20]`, per-cell action digests, realized task shares, capacity-switch rates,
cross-domain action-switch rates, action shares, completion proxies by class, energy, and latency.

The checkpoint is the comparison unit. Primary descriptive outputs are:

1. for each evaluation domain and capacity, paired actor contrasts among all training domains;
2. each actor cohort's in-domain versus out-of-domain gaps;
3. whether the descriptive training-domain ranking changes by evaluation domain or capacity; and
4. cross-domain and high-versus-low-capacity keyed action-switch rates.

No inferential, causal, Manchester, or trace-generalisation claim is authorised. Reusing the same
numeric key does not make sampled task types identical across different categorical probability
distributions; it only provides a reproducible common-random-number coupling.

## Boundaries

- No producer data, traces, checkpoints, BODS material, bus artifacts, quarantine bytes, local
  scientific campaigns, registries, or held-out cohorts enter Colab.
- Producer source runs temporarily under code-use permission and is excluded from returned
  archives. Exact hashes remain in manifests.
- Curves, actors, and diagnostics are not evidence and do not admit an actor. Homecoming still
  needs review, CPU/GPU reconciliation, a separate evaluation design, and fresh admission.
- This result cannot be relabelled as train-×-trace, bus-native, or Manchester distribution shift.

## Approval gate

Launch requires `docs/evaluation/bdomain_training_approval_20260728.json` to bind this document
and the preparation, campaign, and evaluator harness hashes; record the owner's direction "do the
next experiment"; keep `held_out_authorised` false; and keep producer-data authorization false.
Any byte change makes the launcher refuse.

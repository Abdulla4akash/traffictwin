# B-MASK Full Training Predeclaration — Learned Policy versus Runtime Feasibility

**Status: owner-approved candidate design, frozen before outcomes.** Approval is recorded in a
separate byte-bound receipt. The label ceiling is `owner_approved_candidate`: not validated,
causal, supervisor-approved, or generalisable.

- Predeclared: 28 July 2026
- Direction: separately predeclared action-masking factor identified by the B-CAP technical
  recommendation in `docs/research_directions_v2.md`; B4 remains cloud-blocked by producer-data
  permission
- Permission: `docs/integration/randy_code_permission_20260728.md`
- Producer citation: Randy Putra; `gitlab.cs.man.ac.uk/e62992rp/vec_env` and
  `gitlab.cs.man.ac.uk/e62992rp/tos-data`; audited vec_env commit
  `068b4ea33e640f206ce6a7d04f3d6fae2ac831f4`; local clean snapshot
  `e98441196270b8fd4cc0eede892df4a0053b2185`; engine `v2_post_nrsus_fix`
- Venue: owner-managed Google Colab G4; producer code only, with citation; no producer or bus data

## Question and equal-standing outcomes

For the 19-D capacity-aware actor trained over randomized RSU ceilings with the balanced
`alpha=0.7` reward, does applying the producer's feasibility mask during training alter the
learned policy, and what additional change comes from enforcing the same mask at deployment?
Masking may improve, harm, or leave completion, latency, energy, and action behaviour unchanged.
Every outcome, including a null or a training/deployment interaction, is reported.

The mask is the producer's existing `get_action_masks_arr`: local is always available; V2I is
masked when no qualifying unsaturated RSU is available; V2V is masked when link quality is below
the threshold. The masked PPO treatment applies the mask both during sampling and in the policy
loss. This campaign does not rewrite feasibility semantics.

## Frozen training matrix

| Factor | Frozen value |
|---|---|
| Treatments | capacity-aware unmasked MAPPO; capacity-aware masked MAPPO (`--use-mask`) |
| Model seeds | `{300, 301, 302, 303, 304}`, paired and fresh |
| Jobs | 2 treatments × 5 seeds = 10, all from scratch |
| Reward | constant `alpha=0.7`; priority scaling off; identical penalties |
| Observation | 19-D configured capacity plus selected-RSU headroom |
| Requested/effective budget | 5,000,000 / 4,998,400 environment steps per job |
| Vectorization | 128 environments, rollout length 50, 781 updates |
| Optimizer | Adam, learning rate `3e-3`, epsilon `1e-5`, gradient norm 0.5 |
| PPO | 4 epochs, 4 minibatches, gamma 0.99, GAE 0.95, clip 0.2, entropy 0.01, value coefficient 0.5 |
| Environment | synthetic producer highway, Model-C on |
| Capacity | uniform per-episode randomization over ceilings `{50, 30, 20, 15}` |

The campaign reuses the reviewed `bcap-random-capacity-observation-blackwell-v2` transformation
and exact B-REWARD runtime. No treatment, seed, budget, or stopping rule changes after launch. A
failed job stops the matrix; an infrastructure repair reruns that job from scratch.

## Frozen 2 × 4 diagnostic

Every checkpoint is greedily evaluated with deployment masking **off and on**, on 32 common
synthetic episodes at each capacity-per-slot level `{2.5, 1.5, 1.0, 0.75}`. Both modes, all actors,
and all levels use evaluator seed `43434343`, identical reset keys, and identical per-step keys.
The evaluator records complete action tensors with shape `[2, 4, 32, 200, 20]`, action digests,
capacity-switch rates, within-actor masking switch rates, selected-infeasible rates, mask
availability, action shares, completion proxies by class, energy, and latency.

The checkpoint is the comparison unit. Primary descriptive contrasts are:

1. masked-trained minus unmasked-trained, under the same deployment mode, paired by model seed;
2. masked-deployment minus unmasked-deployment, within the same checkpoint; and
3. the training × deployment-mask interaction.

No inferential claim is authorised. The masked-deployment invariant is zero selected-infeasible
actions; violation fails the job rather than becoming a result.

## Boundaries

- No producer data, checkpoints, traces, BODS material, bus artifacts, quarantine bytes, local
  scientific campaigns, registries, or held-out cohorts enter Colab.
- Producer source runs temporarily under code-use permission and is excluded from returned
  archives. Exact hashes remain in manifests.
- Curves, actors, and diagnostics are not evidence and do not admit an actor. Homecoming still
  needs review, CPU/GPU reconciliation, an evaluation design, and fresh scientific admission.
- B4 train-×-evaluate remains local/CSF-only until producer trace-data movement is permitted.

## Approval gate

Launch requires `docs/evaluation/bmask_training_approval_20260728.json` to bind this document and
the preparation, campaign, and evaluator harness hashes; record the owner's direction "do the
next one"; keep `held_out_authorised` false; and keep producer-data authorization false. Any byte
change makes the launcher refuse.

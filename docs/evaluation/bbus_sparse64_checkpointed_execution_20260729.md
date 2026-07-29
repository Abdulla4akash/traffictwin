# B-BUS Sparse-64 checkpointed execution record — 29 July 2026

## Status

**Running; no held-out result is available.** The owner approved an execution-only
checkpoint/resume repair and a new Sparse-64 run after two non-checkpointed Colab G4 sessions
were lost before any seed completed. The new five-seed campaign started through the Colab CLI
at approximately **10:29:54 UTC (11:29:54 BST) on 29 July 2026**. At this record's cutoff the
named G4 session was BUSY, the campaign design/progress files existed, and training logs existed
for seeds 30–34. No actor, peak evaluation, campaign summary or result archive had returned.

This is an execution record, not a scientific verdict. Returned bytes remain non-admitted and
must pass the independent homecoming review before any result is promoted.

## Frozen scientific design retained

Checkpointing changes none of the approved scientific inputs or settings:

- experiment `B-BUS-SPARSE64-DAWN-PEAK-20260728` and protocol digest
  `f366f3ba886287150eefcf64268e38df4e2a488372ed738dbbc712573c221efa`;
- private derived dawn/peak trace digests `c08a69da…` / `9125b32c…`, with the same single
  dawn-designed 64-site array and 45.01% / 46.00% exact coverage diagnostics;
- dawn-only MAPPO training, held-out peak-only evaluation, model seeds 30–34, evaluation stream
  seeds 700030–700034, capacities 2.5 and 0.75, Model C, no action masks;
- 5,000,000 requested / 4,998,400 effective environment steps per seed, 64 environments,
  rollout length 50, 1,562 updates, learning rate 0.003 and the unchanged PPO/GAE settings;
- the same permitted producer trainer, whose staged identity remains
  `d19453529babb1c1691fdc9da5188aa0e3e233e3dcf6a65ac84ada2ef25355e1`.

The derived private checkpoint trainer has digest
`1f8b46eb621c7b01fe313a6a0a8dd7cbab254c8a2c682e9cf2d2a23fc4f0f035`. The original permitted
trainer is not edited. A marker-checked transformation creates a second private script while
building the pack. Its provenance binding explicitly says `scientific_settings_changed=false`
and `checkpoint_boundary=completed_ppo_update`.

Final private pack identities:

- Sparse-64 ZIP:
  `0ef9ea359d985e25393ba2a80022fdf73265f1d0bb8fa5c34dff87cb8ce89d7b`;
- paired pack manifest:
  `fe3d09cc90a872b9fa540953b79adef6ac8ce20ca95e8933442fb3232237250a`;
- committed execution code: `78728d8` (`add durable B-BUS update checkpoints`).

## Checkpoint boundary and contents

Each seed writes one atomic replacement ZIP after every 50 completed PPO updates and after the
final update. At the frozen vectorisation this is every **160,000 environment steps**. Based on
the preserved 162–164 step/s process rates, the expected interval is roughly 16–17 minutes;
this is an estimate, not a runtime guarantee. A tiny JSON sidecar binds the latest ZIP's byte
count, sha256, next update and environment-step count. The local monitor downloads a large ZIP
only when that sidecar names a new digest.

The ZIP contains the complete next-update state:

- actor and critic parameters, optimiser states and optimiser steps;
- PRNG key, batched observation and batched environment state;
- partial-episode returns, task/completion counts, action histograms, class counts, energy and
  latency accumulators;
- all finished-episode diagnostic lists;
- raw decision timing values and their global indices;
- cumulative environment/decision steps and elapsed training time; and
- the exact CSV through the completed update.

Save is temporary-file then atomic replace. Resume verifies ZIP CRC, exact inventory, component
hashes, trainer/trace/settings identity, curve boundary, host counters and exact restored device
state values before appending at the next update. A checkpoint cannot select an actor: the
frozen terminal update remains the only training endpoint, and peak never enters resume,
stopping or selection.

## G4 equivalence smoke and numerical caveat

A four-update actual-trainer/actual-Sparse-64-trace G4 smoke compared uninterrupted execution
with an interruption after update 2 and continuation from the checkpoint. The returned smoke
record has sha256 `b0399421db3bb86047643f09267513d02763e5177cfb69906534bf30341c9049`.

- every archived state value restored exactly before resumed computation;
- all 12 scientific training-curve columns were exactly equal across all four rows;
- elapsed time, throughput and decision-wall-clock values were deliberately excluded;
- after the two further updates, actor/full device state was not bitwise equal across the two
  independent G4 processes; the maximum actor-parameter absolute difference was
  `0.005979523062705994`.

No post-hoc numerical tolerance was introduced. The last observation is retained as a material
provenance limitation: checkpoint recovery preserves the exact boundary state, but further
float32 GPU execution in a newly compiled process is not a claim of bitwise trajectory
identity. A recovered seed remains the predeclared seed and terminal-update actor, but its
execution manifest must disclose that it resumed.

## Browser-independent supervision and stale-session cleanup

The Colab API had retained one orphan G4 assignment after the earlier local session record was
cleared by a `404/401` loss. That server/local mismatch is why `colab sessions` showed `[?]`.
The exact sole orphan endpoint was unassigned; the subsequent server listing contained zero
allocations. Four bounded equivalence-smoke sessions were also explicitly stopped after use.

The live campaign is controlled by the macOS service
`com.traffictwin.bbus.sparse64.20260729`, not by a browser tab. Its supervisor:

1. creates a named G4 session through the CLI and uploads only the private derived pack plus any
   latest locally validated checkpoints;
2. starts all five frozen seed jobs concurrently;
3. mirrors atomic checkpoints to the gitignored local run directory every 30 seconds;
4. on a lost runtime, stops/unassigns the exact session and launches a new attempt from those
   checkpoints, with a five-attempt bound and a fail-closed stop after two attempts with no new
   durable progress; and
5. on completion, retrieves and CRC-checks the private result ZIP and stops/unassigns the exact
   finished session.

Closing the browser does not stop this service. Sleeping, powering off or disconnecting the Mac
can interrupt local checkpoint mirroring; the remote Colab execution may continue, but that is
not claimed as a durable guarantee. No Google Drive mount or public hosting is used.

## Interpretation boundary

There is still no Sparse-64 held-out number at this cutoff. The arm remains explicitly outside
VEC-06 because 64 sparse sites cover less than half of vehicle-seconds. Any returned result will
describe the frozen simulator, synthetic fleet/tasks and two captured windows; it will not
establish real deployment coverage, a causal rush-hour effect or an owner/supervisor verdict.

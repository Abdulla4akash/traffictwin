# B-BUS Sparse-64 GPU homecoming — results and execution deviation

## Status

**The GPU computation and local archive review are complete, but this is not a clean
one-shot held-out result.** All five model seeds reached the frozen terminal update, all five
actors and both peak-capacity evaluations returned, and the retained ZIP passed an independent
local integrity, binding and metric-recomputation review. The retained output's primary
descriptive value is **0.519215 mean held-out peak deadline completion at capacity 0.75**.

Homecoming also found a material execution deviation. After the first successful return,
`launchd` relaunched the supervisor and repeated evaluation/packaging of the same fixed terminal
actors. The log contains **148 complete returned campaigns: one intended return plus 147
unintended repeats**. No actor or scientific setting changed, and the supervisor did not inspect
metrics or select a result, but only the last archive was retained. Cross-repeat metric identity
therefore cannot be verified, and the literal requirement to evaluate each frozen actor on peak
once was not met. The retained result is consequently **execution-deviated, descriptive and
non-admitted**; it is not promoted as scientific evidence or an actor-admission verdict.

The service is stopped, the server reports no active Colab sessions, and the supervisor now has
a tested terminal-result guard that validates and reuses an existing returned archive without
allocating another GPU.

## Provenance and verified artifacts

- Experiment: `B-BUS-SPARSE64-DAWN-PEAK-20260728`.
- Frozen protocol sha256:
  `f366f3ba886287150eefcf64268e38df4e2a488372ed738dbbc712573c221efa`.
- Frozen checkpointed private pack: 28,163,173 bytes; sha256
  `0ef9ea359d985e25393ba2a80022fdf73265f1d0bb8fa5c34dff87cb8ce89d7b`.
- Retained private result archive: 50,294,048 bytes; 59 ZIP members and 58 inventoried
  payload files; sha256
  `59e0242bee5e7ad3306bf7272956595fb87168772367eaa531ae087b26379eb6`.
- Local review status:
  `RETURNED_ARCHIVE_INTEGRITY_PASS__HELD_OUT_REPEAT_DEVIATION__NON_ADMITTED`.
- Machine-readable review:
  [Sparse-64 homecoming evidence](../integration/evidence/bbus_sparse64_gpu_homecoming_20260730.json).

The review refused unsafe, duplicate, encrypted or symlink ZIP members; checked every CRC;
matched the inventory's member set, byte counts and sha256 values; reverified the frozen pack;
validated the campaign design and five run manifests; matched every terminal checkpoint to its
local mirror; checked evaluation metadata and action-share sums; and recomputed the campaign
summary exactly from the per-seed outputs.

## Exact study settings

The complete task, fleet, radio, queue, reward, MAPPO and trajectory settings are recorded in
the [paired detailed-settings record](bbus_dawn_peak_settings_and_preliminary_results_20260729.md).
The load-bearing Sparse-64 settings were:

- real captured, privacy-processed bus mobility from the 52-snapshot dawn and peak sessions;
  no raw BODS bytes, raw identifiers or session salts entered Colab;
- 961 retained dawn buses and 1,212 retained peak buses, padded to 827 and 1,000 concurrent
  slots respectively, with 3,422 dawn and 3,384 peak one-second steps;
- whole parent fleet retained, with exactly 64 dawn-selected generated analysis sites reused
  byte-for-byte at peak; exact 500 m vehicle-second coverage 45.0141% dawn and 45.9960% peak;
  this arm is explicitly outside VEC-06;
- dawn-only MAPPO training from scratch, model seeds 30–34, one shared 17→64→64→3 actor,
  centralised critic, stochastic training actions and deterministic argmax evaluation;
- 5,000,000 requested / 4,998,400 effective vectorised environment steps per seed, 64
  environments, rollout length 50, 1,562 PPO updates, learning rate 0.003, four epochs and four
  minibatches per update;
- full-state atomic checkpoint every 50 completed updates, with exact restored boundary state
  but no claim that subsequent cross-process float32 execution is bitwise identical;
- synthetic Model-C arrivals and synthetic equipment fleet; no observed computing tasks,
  deployed RSUs, passenger loads or physical completion outcomes;
- peak evaluation streams 700030–700034, fleet seeds equal to model seeds, full 3,384-second
  peak trace, and per-RSU concurrency ceilings 750 at capacity 0.75 and 2,500 at capacity 2.5;
  the same evaluation stream is paired across capacities; and
- primary endpoint fixed as the equal-weight five-seed mean peak deadline-completion at
  capacity 0.75. No post-result success threshold or significance test was introduced.

The returned runtime records Python 3.12.13, NumPy 2.0.2, JAX/JAXLIB 0.7.2, CUDA device
`cuda:0`, and an NVIDIA RTX PRO 6000 Blackwell Server Edition.

## Completion and recovery record

All seeds reached update 1,562 of 1,562 and 4,998,400 effective environment steps. Every run
manifest discloses checkpoint resume, and all five terminal checkpoint ZIPs are byte-identical
to their local mirrors. Before the first successful completion, the supervisor recorded nine
events in which remote campaign output disappeared and resumed from durable local checkpoints.
That recovery is why the training work survived runtime loss.

The successful terminal state exposed a separate orchestration bug: successful supervisor exit
was treated as restartable by `launchd`, and the supervisor had no pre-allocation terminal-result
check. Each relaunch uploaded the already-terminal checkpoints, reran the two fixed peak
evaluations for every actor and replaced the result ZIP. The log binds the retained archive to
the last of 148 returns and contains 148 distinct archive hashes. Differences in timestamps,
timing arrays and packaging are sufficient to vary an archive hash, so distinct hashes do not
prove distinct scientific metrics. Conversely, because earlier archives were overwritten, this
record does not assert that the repeated metrics were identical.

## Retained held-out peak result

### Primary capacity 0.75, per seed

| Seed | Tasks | Completion | T1 / T2 / T3 completion | Latency ms/task | Energy J/task | Local / V2I / V2V |
|---:|---:|---:|---:|---:|---:|---:|
| 30 | 4,738,678 | 0.442555 | 0.266134 / 0.561564 / 0.441693 | 1,193.351 | 0.210925 | 0.222531 / 0.777469 / 0.000000 |
| 31 | 4,736,985 | 0.504273 | 0.308810 / 0.562791 / 0.547363 | 860.462 | 0.468683 | 0.510817 / 0.002655 / 0.486528 |
| 32 | 4,735,894 | 0.618675 | 0.486290 / 0.674105 / 0.638412 | 683.117 | 0.337292 | 0.562533 / 0.432083 / 0.005384 |
| 33 | 4,737,083 | 0.427187 | 0.154897 / 0.508899 / 0.486983 | 970.555 | 0.416924 | 0.046252 / 0.165135 / 0.788613 |
| 34 | 4,738,319 | 0.603386 | 0.472833 / 0.669999 / 0.615534 | 718.177 | 0.272331 | 0.404077 / 0.368212 / 0.227710 |
| **Equal-weight mean** | **23,686,959 total** | **0.519215** | **0.337793 / 0.595472 / 0.545997** | **885.133** | **0.341231** | **0.349242 / 0.349111 / 0.301647** |

Completion sample SD across the five seeds is **0.088806** and the range is
**0.427187–0.618675**. These are between-seed descriptive statistics, not uncertainty over a
random sample of Manchester days.

### Capacity comparison

| Equal-weight mean | Capacity 0.75 | Capacity 2.5 | `2.5 - 0.75` |
|---|---:|---:|---:|
| Completion | 0.519215153 | 0.519107907 | -0.000107245 (-0.0107 percentage points) |
| T1 / T2 / T3 completion | 0.337793 / 0.595472 / 0.545997 | 0.337713 / 0.595325 / 0.545903 | -0.000080 / -0.000147 / -0.000094 |
| Latency ms/task | 885.132540 | 1,042.527281 | +157.394741 ms |
| Energy J/task | 0.341231094 | 0.341231094 | 0 |
| Local / V2I / V2V | 0.349242 / 0.349111 / 0.301647 | identical | 0 / 0 / 0 |

Seeds 31–34 are numerically identical between capacity outputs for every reported endpoint.
Only seed 30 differs: capacity 2.5 has 0.0536 percentage points lower completion and 786.974 ms
higher mean latency. The returned metrics do not expose enough queue-level detail to assign a
verified mechanism to that reversal.

## Observations and bounded interpretation

1. **The retained primary output is 51.92%, with substantial seed variation.** The 19.15
   percentage-point seed range and sharply different action strategies make a single actor an
   inadequate summary of this setup.
2. **T1 is again the weakest class.** Mean T1 completion is 33.78%, versus 59.55% for T2 and
   54.60% for T3. These are simulated task-template outcomes, not real bus-safety measurements.
3. **More configured concurrency did not improve this retained output.** Completion is nearly
   unchanged and slightly lower at capacity 2.5, while mean latency is higher because of seed
   30. This does not establish a general capacity effect or absence of one.
4. **The corridor and Sparse-64 arms must remain separate.** The corridor retained output is
   0.809841 at capacity 0.75, 0.290625 (29.06 percentage points) above Sparse-64. That is a
   descriptive contrast, not an infrastructure treatment effect: the arms also differ in
   geography, fleet size, padded population and site-placement policy.
5. **Sparse-64 does not cover the whole simulated fleet at a site.** Its 64 sites cover only
   45.01% of dawn and 46.00% of peak vehicle-seconds within 500 m. Keeping every bus in the
   motion trace is not the same as providing full infrastructure coverage.
6. **This is not a measured dawn-to-peak drop.** Actors train on dawn, but the frozen evaluator
   runs only peak. The training CSV is not endpoint-equivalent, and the sessions do not link
   vehicles across time.
7. **The one-shot execution requirement failed.** Unchanged actors and absence of metric-based
   selection bound the defect, but do not erase it. The retained numbers may support engineering
   diagnosis; they may not be represented as a clean confirmatory verdict.

## Decision boundary and remaining gates

No owner or supervisor decision is taken here. The owner/supervisor can later decide whether the
execution-deviated result is useful as non-admitted descriptive evidence or whether a new,
explicitly approved one-shot rerun is worth its compute cost. This agent does not initiate that
rerun automatically. Independent actor admission, supervisor approval, causal rush-hour claims,
general-Manchester claims and claims about real computing tasks or deployed RSUs all remain
false.

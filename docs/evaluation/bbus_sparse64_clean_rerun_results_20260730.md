# B-BUS Sparse-64 fresh rerun — result and execution record

## Status

**The fresh five-seed GPU computation, archive retrieval and independent local review are
complete.** Every seed reached update 1,562 / 4,998,400 effective environment steps. The retained
50,203,691-byte ZIP passes path, CRC, inventory, digest, frozen-pack, design, manifest,
checkpoint, evaluation-metadata and exact metric-recomputation checks. The GPU service is
stopped and no Colab session remains active.

The retained primary descriptive result is **0.501355 mean held-out peak deadline completion at
capacity 0.75**. It is not a clean one-shot scientific result. After the first valid archive was
downloaded and CRC-checked, the supervisor waited for an already-terminal foreground RPC, timed
out, and exited before persisting terminal state. `launchd` restarted it, causing one unintended
second evaluation and result return. The first archive was overwritten. Actors and scientific
settings did not change and no metric-based selection occurred, but cross-return metric identity
cannot be verified. This rerun is therefore **execution-deviated, descriptive and non-admitted**.

## Provenance and integrity

- Experiment: `B-BUS-SPARSE64-DAWN-PEAK-20260728`.
- Frozen protocol sha256:
  `f366f3ba886287150eefcf64268e38df4e2a488372ed738dbbc712573c221efa`.
- Frozen checkpointed pack: 28,163,173 bytes; sha256
  `0ef9ea359d985e25393ba2a80022fdf73265f1d0bb8fa5c34dff87cb8ce89d7b`.
- Retained private archive: 50,203,691 bytes, 59 ZIP members / 58 inventoried payloads;
  sha256 `18e774bbe656920ce16407d23c30bae41e4bdd0f8761043b8beb4945c2adf19a`.
- Review status:
  `RETURNED_ARCHIVE_INTEGRITY_PASS__HELD_OUT_REPEAT_DEVIATION__NON_ADMITTED`.
- Machine-readable review:
  [fresh-rerun homecoming evidence](../integration/evidence/bbus_sparse64_clean_rerun_gpu_homecoming_20260730.json).

The review also matched each terminal checkpoint to its local mirror and verified all five run
manifests, the 17→64 actor shape, evaluation streams, action-share sums and the recomputed
campaign summary. It records Python 3.12.13, NumPy 2.0.2, JAX/JAXLIB 0.7.2, CUDA `cuda:0`, and
an NVIDIA RTX PRO 6000 Blackwell Server Edition.

## Frozen experimental settings

The full task, fleet, radio, queue, reward, MAPPO and trajectory specification is in the
[detailed settings record](bbus_dawn_peak_settings_and_preliminary_results_20260729.md). The
load-bearing settings were unchanged:

- privacy-processed mobility from the already captured 52-snapshot dawn and peak sessions; no
  raw BODS bytes, raw identifiers or session salts entered Colab;
- 961 retained dawn buses / 1,212 retained peak buses, padded to 827 / 1,000 concurrent slots,
  over 3,422 / 3,384 one-second steps;
- the whole parent fleet and exactly 64 dawn-selected generated analysis sites, reused
  byte-for-byte at peak; 500 m vehicle-second coverage 45.0141% dawn / 45.9960% peak, explicitly
  outside VEC-06;
- dawn-only MAPPO training from scratch, model seeds 30–34, one shared 17→64→64→3 actor,
  centralised critic, stochastic training actions and deterministic argmax evaluation;
- 5,000,000 requested / 4,998,400 effective steps per seed, 64 environments, rollout length 50,
  1,562 PPO updates, learning rate 0.003, four epochs and four minibatches per update;
- a full-state atomic checkpoint every 50 completed updates, without claiming bitwise-identical
  float32 trajectories after a cross-process resume;
- peak evaluation streams 700030–700034, paired across per-RSU concurrency ceilings 750
  (capacity 0.75) and 2,500 (capacity 2.5), over the full 3,384-second peak trace; and
- primary endpoint fixed before the run as the equal-weight five-seed mean peak
  deadline-completion at capacity 0.75, with no post-result threshold or significance test.

The mobility is observed and processed, but Model-C task arrivals, compute equipment and all
task outcomes are simulated. The 64 sites are analysis placements, not observed RSUs.

## Completion and operational history

The first four GPU attempts ended at approximately one-hour boundaries and resumed from durable
checkpoints. Forensic review found that these were not demonstrated GPU failures: the installed
Colab CLI retained a one-hour runtime-proxy credential while the live endpoint offered refreshed
credentials. Monitoring consequently misclassified inaccessible output as missing and restarted
the runtime. Updating that operational credential for the same authenticated endpoint allowed
the fifth attempt to pass the former boundary and finish; it did not change code, data, actors or
scientific settings.

At completion, the terminal-state ordering defect caused **two complete archive downloads**, one
intended and one unintended repeat. The retained archive is the last return; only its hash is
available. The supervisor now atomically records a verified terminal result before any fallible
remote-process cleanup, and the homecoming review counts successful downloads even when a
terminal JSON record was not yet written. Focused tests cover the ordering guard, idempotent
reuse, tamper refusal and archive-path refusal.

## Retained held-out peak result

### Primary capacity 0.75

| Seed | Tasks | Completion | T1 / T2 / T3 | Latency ms/task | Energy J/task | Local / V2I / V2V |
|---:|---:|---:|---:|---:|---:|---:|
| 30 | 4,738,678 | 0.400527 | 0.252283 / 0.514334 / 0.391510 | 1,319.575 | 0.137797 | 0.149233 / 0.850767 / 0.000000 |
| 31 | 4,736,985 | 0.634229 | 0.418643 / 0.696176 / 0.683311 | 548.922 | 0.557011 | 0.760208 / 0.037259 / 0.202533 |
| 32 | 4,735,894 | 0.458814 | 0.298790 / 0.538049 / 0.475351 | 966.894 | 0.263692 | 0.325529 / 0.673733 / 0.000738 |
| 33 | 4,737,083 | 0.476872 | 0.171349 / 0.582394 / 0.535678 | 786.826 | 0.435136 | 0.120592 / 0.341904 / 0.537504 |
| 34 | 4,738,319 | 0.536333 | 0.433014 / 0.629187 / 0.521802 | 855.590 | 0.136309 | 0.270129 / 0.671190 / 0.058681 |
| **Equal-weight mean** | **23,686,959 total** | **0.501355** | **0.314816 / 0.592028 / 0.521530** | **895.561** | **0.305989** | **0.325138 / 0.514971 / 0.159891** |

Completion sample SD across seeds is **0.088677** and the range is
**0.400527–0.634229**. These are descriptive between-seed statistics, not uncertainty over
Manchester days.

### Capacity comparison

| Equal-weight mean | Capacity 0.75 | Capacity 2.5 | `2.5 - 0.75` |
|---|---:|---:|---:|
| Completion | 0.501354861 | 0.501232927 | -0.000121934 (-0.0122 percentage points) |
| T1 / T2 / T3 | 0.314816 / 0.592028 / 0.521530 | 0.314721 / 0.591862 / 0.521424 | -0.000095 / -0.000166 / -0.000106 |
| Latency ms/task | 895.561256 | 1,055.813607 | +160.252350 |
| Energy J/task | 0.305988869 | 0.305988869 | 0 |
| Local / V2I / V2V | 0.325138 / 0.514971 / 0.159891 | identical | 0 / 0 / 0 |

## Observations and interpretation

1. Retained completion is 50.14%, with a 23.37 percentage-point seed range and very different
   action mixtures. A single actor would not summarise this setup.
2. T1 is the weakest simulated class: 31.48% completion versus 59.20% for T2 and 52.15% for T3.
3. Raising configured concurrency from 0.75 to 2.5 did not improve this retained output;
   completion is 0.0122 percentage points lower and latency is 160.25 ms higher. The result does
   not establish a causal or general capacity effect.
4. The earlier retained Sparse-64 output was 0.519215, 1.7860 percentage points above this fresh
   retained output. Both runs violated literal one-shot evaluation and neither preserved both
   returned archives, so this is only a descriptive cross-run difference—not evidence of
   reproducibility or non-reproducibility.
5. This is dawn-trained / peak-evaluated, not a measured dawn-to-peak change. Vehicle identities
   do not link across sessions, and the training curve is not the held-out endpoint.

## Claim and decision boundary

Scientific evidence, actor admission, independent admission and supervisor approval remain
false. No causal rush-hour, general-Manchester, observed-RSU, real-computing-task or physical
completion claim is available. No owner decision is taken here, and no additional rerun is
started automatically.

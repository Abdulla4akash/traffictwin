# B-BUS Dawn-to-Peak — Detailed Settings, Available Results and Interpretation

**Status at 29 July 2026 04:00 BST:** the corridor campaign completed 5/5 seed jobs and its
returned archive passed a local byte-level integrity and binding recheck. Its metrics below are
**available, preliminary and non-admitted** pending the separately required independent
homecoming/actor review. The whole-fleet Sparse-64 campaign did not complete: the Colab
session terminated before any actor, held-out evaluation or result archive existed. The two
arms therefore do not yet have comparable result status and are never pooled.

- Corridor experiment: `B-BUS-CORRIDOR-DAWN-PEAK-20260728`
- Sparse-64 experiment: `B-BUS-SPARSE64-DAWN-PEAK-20260728`
- Frozen producer-environment source: `vec_jax.py` sha256 `4eed6b61…`; Model-C evaluator
  sha256 `f6515f6c…`; training script sha256 `d1945352…`
- Corridor returned archive: 1,412,372 compressed bytes (2,829,488 uncompressed member
  bytes); sha256 `a84b5a16…`
- Machine-readable local review:
  [corridor homecoming evidence](../integration/evidence/bbus_corridor_gpu_homecoming_preliminary_20260729.json)

This record adds detail; it does not change either approved protocol, adopt a checkpoint,
make a supervisor decision, or turn a synthetic computing workload into observed bus demand.

## 1. What is measured, derived and synthetic

| Layer | Provenance | What it means |
|---|---|---|
| Bus observations | **Captured** BODS snapshots from two attended sessions | Time-stamped vehicle positions/activity from the dawn and peak windows; no computing tasks, passenger load or onboard telemetry |
| Motion traces | **Derived** locally | Pseudonymous bus trajectories after matching, routing, interpolation, gap/dwell/speed rules and arm-specific spatial/infrastructure processing |
| Corridor/Sparse sites | **Derived analysis infrastructure** | Generated sites used by the simulator; not observed, planned or deployed RSUs |
| Task demand, compute fleet, radio fading and queues | **Synthetic** frozen simulator | Controlled VEC workload laid over the derived movement; not recorded from buses |
| Completion, latency, energy and action shares | **Simulated outcomes** | Outcomes of the frozen actor/environment under those assumptions; not physical bus-service measurements |

The most accurate short description is **real captured bus mobility with synthetic vehicular
computing demand and generated analysis infrastructure**.

## 2. Captured sessions and parent trajectory construction

Both arms inherit the same parent processing. No acquisition occurred during post-hoc
processing or GPU execution.

| Setting or result | Dawn training source | Peak held-out source |
|---|---:|---:|
| Exact window | 05:12:26–06:09:33 UTC (06:12:26–07:09:33 BST) | 07:02:23–07:58:51 UTC (08:02:23–08:58:51 BST) |
| Snapshots processed | 52 | 52 |
| Distinct in-window fixes | 41,122 | 60,123 |
| Network-matched fixes | 36,990 (89.95%) | 54,136 (90.04%) |
| Vehicles passing the 80% matched-fix floor before routing | 966 | 1,213 |
| Vehicles retained in the final parent trace | 961 | 1,212 |
| Parent maximum concurrent slots | 827 | 1,000 |
| Speed-ceiling segments dropped | 1,394 | 1,757 |
| Maximum retained implied speed | 31.986 m/s | 31.992 m/s |
| Parent vehicle-seconds | 2,174,120 | 3,170,599 |
| Interpolated share | 98.39% | 98.37% |

Frozen trajectory settings were: independent per-session HMAC pseudonyms; no cross-session
vehicle linkage; `120 s` maximum gap; `15 m` dwell radius; at least `80%` matched fixes; and a
`32 m/s` implied-speed ceiling with violating segments dropped and counted. The high
interpolated share follows from the measured roughly 66–67 second source cadence and must
travel with every interpretation. Raw BODS bytes, raw identifiers and session salts did not
enter either Colab pack.

## 3. The two infrastructure arms

| Property | Corridor/full coverage | Whole-fleet Sparse-64 |
|---|---:|---:|
| Geographic rule | Closed 750 m EPSG:27700 capsule around the frozen St Peter's Square–University landmark segment | No spatial filtering; preserves the complete parent fleet |
| Dawn / peak trace shape `[T,maxN]` | `[3422,67]` / `[3384,98]` | `[3422,827]` / `[3384,1000]` |
| Dawn / peak vehicle-seconds | 161,654 / 281,265 | 2,174,120 / 3,170,599 |
| Share of parent vehicle-seconds | 7.44% / 8.87% | 100% / 100% |
| Occupied 50 m cells | 831 / 893 | 66,291 / 72,208 parent cells |
| Analysis sites | 12 dawn and 12 peak, placed separately | Exactly 64 selected from dawn only and reused byte-for-byte at peak |
| Exact 500 m vehicle-second coverage | 100% / 100% | 45.014% / 45.996% |
| Contract status | Placement-contract compatible; no VEC-06 receipt | Explicitly outside VEC-06 |

Corridor sites were generated separately for each session by the pinned full-coverage method:
`50 m` cells, `500 m` radius, at most 64 sites and at most 2,000 occupied cells. This tests
transfer under a common **placement rule**, not one unchanged physical estate. Sparse-64
selected dawn cell centres greedily by uncovered dawn vehicle-second weight, using the
full-cell safe radius `500 - 50*sqrt(2)/2 m`; ties used the lowest integer cell coordinate.
Peak positions neither selected nor moved a sparse site.

## 4. Synthetic computing-task generator

The BODS source supplied no tasks. For every active bus and one-second simulation step,
Model C draws `k ~ Poisson(1.5)`, clips it to `[0,5]`, and samples `k` independent task slots.
Inactive padded slots receive no arrivals. Task ordering is IID because no ordering override
was set. Each payload receives multiplicative `Uniform(0.8,1.2)` noise.

| Task class | Model label | Probability | Deadline | Mean payload | Workload | Task GPU speedup cap | Maximum parallelism | Reward weight |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | safety-critical | 0.20 | 100 ms | 1.0 MB | 1,254 Mcycles | 40× | 4 | 20 |
| T2 | platooning | 0.30 | 500 ms | 0.0012 MB | 2,100 Mcycles | 5× | 4 | 3 |
| T3 | awareness/CAM | 0.50 | 100 ms | 0.001 MB | 15 Mcycles | 1× | 2 | 2 |

Important Model-C semantics:

- one representative task is shown in each bus observation at decision time;
- the actual within-second arrival slots are sampled separately and may be heterogeneous;
- the actor emits one action for that bus-second, reused for all `k` arrivals;
- the `k` tasks are processed sequentially against the evolving queue, links are computed once
  at the start of the second, and queues drain by 1,000 ms once after all five possible slots;
- vehicle queue depth is 10; RSU concurrency is controlled separately; and
- `deadline-completion` means simulated latency `<=` the class deadline. It is not a
  confirmation of physical execution, queue admission or real-world task completion.

## 5. Synthetic fleet and compute model

Every episode/evaluation seed samples an independent synthetic equipment fleet. The configured
vehicle-tier probabilities are Raspberry-Pi-like `0.50`, Jetson-like `0.40` and GPU-vehicle
`0.10`; EV probability is `0.30`. EV initial state of charge is uniform `[0.20,0.95]` on a
60 kWh battery. Non-EVs use 23 dBm V2I transmission power and EVs 20 dBm.

| Tier | CPU GHz | IPC | Cores | Utilisation | Device GPU factor | Idle / compute power |
|---|---:|---:|---:|---:|---:|---:|
| Raspberry-Pi-like | 1.5 | 1.0 | 4 | 1.00 | 1× | 3 / 7 W |
| Jetson-like | 1.5 | 1.2 | 6 | 0.90 | 9× | 5 / 15 W |
| GPU vehicle | 2.2 | 1.5 | 8 | 0.85 | 20× | 10 / 60 W |
| RSU | 2.2 | 1.5 | 12 | 0.90 | 5× | 15 / 60 W |

Compute time follows workload divided by frequency, IPC, effective cores, utilisation and the
bounded task/device GPU factor, with independent `Uniform(0.9,1.1)` multiplicative noise.
The reported energy is not total-system energy: it includes source local/transfer energy and
V2V-target compute energy, but not RSU compute energy.

## 6. Radio, latency, queue and reward settings

- Distance in trace replay is two-dimensional Euclidean distance over the projected bus/site
  coordinates. Synthetic speed and lane evolution are disabled.
- V2I: 5.9 GHz, 20 MHz, 500 m range, 9 dB noise figure, 8 dB antenna gain.
- V2V: 5.9 GHz, 10 MHz, 300 m range, 9 dB noise figure, 0 dB antenna gain.
- Both links use the TR 37.885-style deterministic loss
  `32.4 + 20 log10(distance_m) + 20 log10(frequency_GHz)`, Rician K-factor
  `N(9 dB,3.5 dB)`, 3 dB shadowing and Shannon capacity.
- SNR maps linearly to quality from 5 to 40 dB; minimum usable quality is 0.15.
- Transfer latency uses payload/capacity plus 0.1 ms propagation. Offload return payload is
  0.001 MB. Unavailable-link sentinel latency is reported as `10 × deadline`.
- Local latency is current vehicle backlog plus compute time. V2I/V2V latency adds transfer,
  current target backlog, target compute and return transfer.
- The reward uses OOM `-100`, deadline-miss multiplier `10`, baseline alpha `0.7`, energy
  normalisation denominator `0.1 J`, and **constant** alpha across task classes because
  priority scaling was disabled (`VEC_JAX_PRIORITY_ALPHA=0`).
- Action masks were not enabled. The policy could choose local, V2I or V2V even when an offload
  was unavailable; the environment then applied its failure latency/reward semantics.

## 7. MAPPO training settings

| Setting | Frozen value |
|---|---|
| Algorithm | Cooperative MAPPO; parameter-shared actor and centralised critic |
| Actor | 17 inputs → 64 tanh → 64 tanh → 3 logits (local/V2I/V2V) |
| Critic | Concatenated joint observations (`17 × maxN`) → 64 tanh → 64 tanh → scalar |
| Initialisation | From scratch; no warm-start actor |
| Training policy | Stochastic categorical actions; no action mask |
| Training trace | Random 200-second windows from dawn; automatic episode reset |
| Seeds | 30, 31, 32, 33, 34 |
| Requested / effective steps per seed | 5,000,000 / 4,998,400 vectorised environment steps |
| Vectorisation | 64 environments × rollout length 50; 1,562 updates |
| Optimisation | Adam, learning rate `0.003`, epsilon `1e-5`; 4 epochs; 4 minibatches/update |
| PPO/GAE | gamma 0.99; lambda 0.95; clip 0.2; entropy 0.01; value coefficient 0.5 |
| Gradient bound | Global norm 0.5 |
| Reward aggregation | Team-sum reward per environment step |
| Model | Model C; Poisson arrivals on; lanes/synthetic speed off |
| Post-training internal greedy pass | Disabled; the separately frozen peak evaluator performs argmax inference |
| Actor output | One actor NPZ per completed seed; input kernel shape `[17,64]` |

The training CSV's completion and class-completion columns are **diagnostics**, not the primary
endpoint. Its host accounting uses a per-bus-step boolean approximation even though Model C
can generate several tasks. Only the held-out evaluator below counts every arrival separately.

## 8. Capacity and held-out evaluation

Dawn was the only training trace. Peak was used once after each actor froze; it did not affect
site selection for Sparse-64, training, stopping, hyperparameters or checkpoint choice.

- Training capacity is 2.5 per padded trace slot, implemented as one absolute concurrency
  ceiling per RSU: corridor `round(2.5 × 67) = 168`; Sparse-64
  `round(2.5 × 827) = 2,068`.
- Peak capacities are 2.5 and 0.75 per padded peak slot, not a dynamically changing active-bus
  count. Corridor absolute ceilings are 245 and 74 per RSU; Sparse-64 would use 2,500 and 750.
- Evaluation uses deterministic argmax. Evaluation stochastic-stream seeds are
  `700030`–`700034`; fleet seeds remain `30`–`34`. Each seed uses the same stream at both
  capacities, enabling paired descriptive comparison.
- The full peak time axis is evaluated: 3,384 seconds in both arms.
- Primary endpoint: equal-weight five-seed mean held-out peak deadline-completion at capacity
  0.75. Secondary endpoints: capacity-2.5 completion, per-class completion, mean simulated
  latency/task, accounted energy/task and local/V2I/V2V task shares.
- No significance threshold or post-result success threshold was introduced.

## 9. Corridor result — available but non-admitted

Local review verified 49 archive members: the inventory plus all 48 inventoried payloads.
Every inventoried size and sha256 matched, ZIP paths were safe and unique, progress said 5/5
complete, every action-share row summed to one, all summary means recomputed exactly, and the
campaign binding/protocol hashes matched the frozen corridor pack. The recorded runtime was
Python 3.12.13, JAX/JAXLIB 0.7.2 on CUDA, with an NVIDIA RTX PRO 6000 Blackwell Server Edition.
The five sequential seed jobs ran from 21:30 to 23:26 UTC and used about 1,373–1,400 seconds
each. These checks establish returned-byte integrity, not actor admission.

### Primary capacity 0.75, per seed

| Seed | Tasks | Completion | T1 / T2 / T3 completion | Latency ms/task | Energy J/task | Local / V2I / V2V |
|---:|---:|---:|---:|---:|---:|---:|
| 30 | 420,770 | 0.756675 | 0.603917 / 0.928658 / 0.714139 | 134.200 | 0.142778 | 0.166542 / 0.777907 / 0.055551 |
| 31 | 419,859 | 0.746932 | 0.428974 / 0.863795 / 0.803636 | 152.190 | 0.610796 | 0.757638 / 0.242362 / 0.000000 |
| 32 | 420,195 | 0.852064 | 0.710149 / 0.980236 / 0.831991 | 82.479 | 0.289600 | 0.418092 / 0.467078 / 0.114830 |
| 33 | 420,153 | 0.854758 | 0.696177 / 0.978083 / 0.844101 | 83.114 | 0.297950 | 0.436767 / 0.422458 / 0.140775 |
| 34 | 421,013 | 0.838775 | 0.676205 / 0.971362 / 0.824388 | 90.241 | 0.288043 | 0.415726 / 0.497362 / 0.086912 |
| **Equal-weight mean** | **2,101,990 total** | **0.809841** | **0.623084 / 0.944427 / 0.803651** | **108.445** | **0.325833** | **0.438953 / 0.481434 / 0.079613** |
| Sample SD across seeds | — | 0.053436 | 0.115964 / 0.049726 / 0.052158 | 32.497 | 0.171924 | 0.210206 / 0.192996 / 0.054662 |

The primary completion estimate is therefore **80.9841%**, with a five-seed range of
74.6932%–85.4758%. No confidence interval or hypothesis test was predeclared.

### Capacity comparison

| Equal-weight mean | Capacity 0.75 | Capacity 2.5 | `2.5 - 0.75` |
|---|---:|---:|---:|
| Completion | 0.809840509 | 0.809671771 | -0.000168738 (-0.0169 percentage points) |
| Latency ms/task | 108.444990 | 108.655524 | +0.210534 ms |
| Energy J/task | 0.325833449 | 0.325833449 | 0 |
| Local / V2I / V2V | 0.438953 / 0.481434 / 0.079613 | identical | 0 / 0 / 0 |

Seeds 31–34 were numerically identical across capacities for every reported endpoint. Seed 30
alone changed: completion was 0.0844 percentage points lower and latency 1.053 ms higher at
2.5 than at 0.75. The evaluator does not expose enough queue telemetry to assign a verified
mechanism to that small reversal.

## 10. Observations and bounded interpretation

1. **A held-out peak result exists; a dawn-to-peak loss estimate does not.** The five actors
   achieved a descriptive 80.98% deadline-success mean on the corridor peak trace. The design
   did not run the same frozen actors on dawn, and its training CSV is not metric-equivalent,
   so this cannot be called a measured percentage retained or lost from dawn.
2. **The two declared capacity levels were practically inert here.** Four actors were exactly
   unchanged and one had a tiny reverse difference. These values do not support a claim that
   extra RSU concurrency improved this corridor result. They also do not prove capacity can
   never matter; both ceilings may be mostly non-binding under this placement/workload.
3. **Training seed matters materially.** Completion spans 10.78 percentage points, latency
   69.71 ms and action strategies differ sharply. Seed 31 is 75.76% local with no V2V and the
   highest accounted energy; seed 30 is 77.79% V2I. A single checkpoint would conceal this
   variability.
4. **T1 is the clearest weakness.** Mean T1 completion is 62.31%, below T3 at 80.37% and T2 at
   94.44%. That is a simulator result for the configured task templates, not observed safety
   performance and not evidence that a real bus system is unsafe.
5. **The result is narrow.** It covers a constructed 750 m capsule retaining only 7–9% of
   parent vehicle-seconds, two windows on one day, separately generated full-coverage site
   layouts, a synthetic fleet and task stream, and five seeds. It is not a whole-Manchester,
   causal rush-hour, same-vehicle, real-RSU, passenger-service or deployment result.
6. **No success threshold was frozen.** “Useful transfer” cannot honestly be converted into a
   pass/fail verdict after seeing 80.98%. The publishable null remains viable, especially given
   seed instability and T1 performance.

## 11. Sparse-64 execution status — no result

The whole-fleet run began at 23:48:39 UTC with five seed jobs executing concurrently. The last
preserved progress sample at 02:44 BST showed last update indices 349–353 of 0–1,561
(350–354 updates completed) and 1.120–1.133 million of 4.9984 million environment steps per
seed (roughly 22–23%). The Colab service recorded
`session_terminated` at 02:53:24 BST and now reports no active session. No completed job
manifest, actor, peak evaluation, campaign summary or archive was returned. The termination
event does not state a cause, so this record does not invent one.

Partial training curves are operational diagnostics only. They are not valid checkpoints,
cannot answer the held-out question and must not be compared with the completed corridor
metrics. A new or safely resumable Sparse-64 execution under the already approved frozen
protocol is still required.

## 12. Remaining gates

1. Preserve/review the corridor returned archive through the independent homecoming and actor
   admission process; do not promote the preliminary numbers merely because local integrity
   checks passed.
2. Re-run Sparse-64 without changing its trace, 64-site array, scientific settings, seeds or
   held-out discipline; record any execution-only scheduling change.
3. When Sparse-64 returns, publish its settings and results beside—not pooled with—the corridor
   arm, always carrying its 45.01%/46.00% coverage diagnostic.
4. Owner/supervisor decisions remain decisions to present, never decisions for an agent to
   take.

# B-BUS Dawn-to-Peak Trace-Replay Experiment — APPROVED PROTOCOL

**Status:** owner-approved candidate protocol, frozen before trajectory derivation or GPU
execution. The owner authorised the experiment in the project conversation on 28 July 2026
with `yea approved GO`, in direct response to the complete decision statement reproduced in
§1. This document records that decision; it is not a supervisor signature, actor admission,
public-hosting permission, or a scientific verdict.

- Protocol date: 28 July 2026
- Research label ceiling: `owner_approved_candidate`
- Experiment ID: `B-BUS-DAWN-PEAK-20260728`
- Training domain: the already captured dawn bus session only
- Held-out domain: the already captured rush-hour bus session only
- Acquisition in this experiment: none

## 1. Owner-authorised boundary

The exact decision presented to and approved by the owner was:

> Approve dawn→peak B-BUS Colab experiment: dawn training and peak held-out evaluation;
> 120 s gap ceiling, 15 m dwell radius, 80% matched-share floor, 32 m/s speed ceiling with
> violating segments dropped and counted; capacity 2.5 and 0.75; fleet seeds 30–34;
> derived/pseudonymised trace permitted on owner Colab, no raw BODS material uploaded.

Those values are closed. An implementation may fail closed, but it may not tune them after
seeing the derived trace or GPU result. Any changed value is a new experiment requiring a new
protocol and owner decision.

## 2. Question, contrast, and publishable null

**Question.** Can a policy trained by trace replay on derived dawn bus motion retain useful
offloading performance when evaluated on the independently captured, higher-density peak bus
window?

**Primary contrast.** For every seed, train one bus-native MAPPO actor on the dawn trace and
evaluate that frozen actor on the peak trace at 0.75 and 2.5 capacity per active slot. The
peak bytes are never made available to training, model selection, stopping, or hyperparameter
choice. The primary result is the five-seed held-out peak table, not a training curve.

**Primary metric.** Mean task deadline-completion share on held-out peak at capacity 0.75,
reported per seed and as an equal-weight five-seed mean. Capacity 2.5 completion, mean latency
per task, mean energy per task, and local/V2I/V2V decision shares are named secondary metrics.
The paired 2.5-minus-0.75 response is descriptive. No significance threshold is introduced
after the run.

**Publishable null.** Dawn-native training need not transfer to peak: flat training reward can
coexist with weak held-out completion, increased latency or energy, or an unstable action mix.
That outcome has equal standing and is never repaired by retraining on peak.

Comparison with the two previously audited actors is a later local homecoming analysis. Those
actors are not uploaded merely to make this Colab run look comparative, and a returned B-BUS
checkpoint is not added to the pinned actor set without the existing independent review and
admission steps.

## 3. Frozen source windows

| Role | Session | Exact window | Snapshots | Accepted support before trajectory work |
|---|---|---|---:|---:|
| Train | `dawn-20260728` | 05:12:26–06:09:33 UTC (06:12:26–07:09:33 BST) | 52 verified/promoted | 1,676 seen; 1,162 linked across snapshots |
| Held-out evaluate | `peak-20260728` | 07:02:23–07:58:51 UTC (08:02:23–08:58:51 BST) | 52 verified quarantines (51 promoted plus one fail-closed parser refusal) | 1,677 seen; 1,433 linked across snapshots |

The exact snapshot-ID lists are bound by
`docs/integration/evidence/bods_bus_sessions_20260728.json` and the private post-hoc receipts.
The dawn cadence fingerprint is
`03b1e0267d9539567af978b66096a1a9ddc02ad8ed1fee1df8dd1a28bd55a054`; the peak cadence
fingerprint is
`1e5ec631d989e10fc086d634ff5f5aae4cec7831d0a59faf1e9d12afff244417`.

No new request, live attendance, substituted snapshot, extension of either endpoint, or
longest/best-window selection belongs to this experiment. The whole fixed session window is
processed. The two MAN-05 `CONFLICTING_ACTIVITY` refusals remain refusals; MAN-05 is not
weakened to increase coverage.

## 4. Identity and privacy boundary

Each session is reprocessed locally under
`manchester-bods-session-identity-1.1`: `HMAC(session_salt, OperatorRef || NUL ||
VehicleRef)`. Dawn and peak use independent random salts. A salt and all raw identifiers stay
inside the local processing boundary and are absent from the Colab bundle and returned
archive. No attempt is made to link a dawn vehicle with a peak vehicle.

The upload allowlist is limited to derived arrays, occupancy spans containing only session
tokens, derived trace reports/accounting, protocol and source-chain fingerprints, campaign
code, and the approval receipt. Raw XML, raw ZIPs, quarantine manifests or member references,
`OperatorRef`, `VehicleRef`, line/journey identifiers, session salts, and private local paths
are forbidden. The owner authorised the derived/pseudonymised artifact for a private owner
Colab only; public Drive links, public notebook output, and public hosting remain
unauthorised.

## 5. Frozen trajectory construction and viability gate

The common construction order is load-bearing:

1. Verify every selected quarantine and parse only accepted vehicle observations.
2. Sort by session token and `RecordedAtTime`; refuse non-monotone or duplicate times.
3. Project WGS84 positions into the verified Greater Manchester network frame and generate
   deterministic road candidates under the existing MAN-09 retrieval/eligibility bounds:
   50 m retrieval, 30 m for an explicit edge shape, and 50 m for fallback geometry. Nearest
   eligible geometry wins; an exact-distance tie is settled by edge ID and counted. These
   are pre-result engineering bindings inherited from the existing candidate policy, not a
   new owner or supervisor decision.
4. Drop a segment before dwell/path construction when its fix interval exceeds **120 s**.
5. Treat matched endpoints within **15 m** as dwell at the entry location.
6. Otherwise follow the deterministic shortest connected road path between the two matched
   locations. No straight-line fallback is allowed; missing paths are dropped and counted.
7. Compute implied speed from matched-path length divided by elapsed seconds. Drop and count
   a segment above **32 m/s**; never retain it and never raise the ceiling.
8. Exclude a vehicle if fewer than **80%** of its fixes are matched. Interpolate each retained
   path at one-second resolution and publish observed versus interpolated seconds per vehicle.

The trace passes only if both sessions satisfy all of the following: monotone timestamps;
matched-share exclusions and every segment outcome reconcile exactly; no retained segment
exceeds 32 m/s; occupancy spans reconstruct the dense mask cell-for-cell; all VEC-06 size and
finite-value bounds pass; and the deterministic VEC-06 `greedy_urban_cover` placement with
its existing defaults (500 m radius, 50 m cells, at most 64 generated analysis sites) covers
every active derived position. These are generated analysis sites, not observed RSUs.

Failure is a recorded refusal. Peak is not substituted into training, thresholds are not
relaxed, and the trace is not thinned by selecting a favourable subwindow.

The network source is the provider-checksum-matching dated PBF
`data/network-recovery/greater-manchester-260724.osm.pbf`, 50,502,348 bytes, md5
`c73b16ec7da303c1dfd331dc914bd5bc`. Its decoded XML identity is 996,913,352 bytes / sha256
`233af3fa6dd34b1541ec022f0139a543f44355fe1748fd9d609ed653c8c9edf1`. The final rebuilt
network identity and build receipt must be attached before derivation; the withdrawn N1
provider-mutation claim is not repeated.

## 6. GPU campaign and held-out discipline

- Algorithm: the producer's trace-replay MAPPO training path, Model-C, using producer code
  under the recorded private-Colab code permission. No producer data blob is uploaded.
- Seeds: `{30, 31, 32, 33, 34}`. Each is a complete independent training/fleet draw and is
  reported separately; no best-seed selection is permitted.
- Training trace: dawn only. Requested optimisation horizon is 5,000,000 environment steps;
  the harness records the exact effective step count, update count, environment count,
  rollout length, and any memory-driven batch configuration before the first job. A GPU
  memory refusal may reduce vectorised environment count while preserving effective steps,
  but cannot change model, trace, seeds, metrics, or thresholds; the final configuration is
  common to all seeds.
- Evaluation trace: peak only, with the actor frozen. Evaluate both capacity-per-active-slot
  levels `2.5` and `0.75` under common random keys for the two levels and record all five
  seeds. Peak may not tune the actor or choose a checkpoint.
- Hardware: a Colab GPU is required and its reported device/runtime identity is recorded.
  CPU fallback is refused.
- Outputs: per-job curve, actor NPZ, evaluation JSON/NPZ, log and manifest; campaign design,
  progress, inventory and checksummed private ZIP. Existing non-empty output is never
  overwritten, and incomplete jobs may resume only when their manifest validates.

Training reward/loss and the in-dawn fit are diagnostics. The held-out peak table is the only
candidate result of this protocol, and it remains non-admitted until the returned archive is
copied locally, ZIP-tested, hashed, checked against these exact bytes and the exact trace
bundle hashes, and reviewed through the existing actor/homecoming gates.

## 7. Claim ceilings

The experiment may support a bounded statement about one day, two approximately one-hour
Manchester bus windows, the declared interpolation/matching policy, this task generator and
these five seeds. It cannot establish city-wide traffic behaviour, road-traffic speed or
volume, same-vehicle temporal change, causal rush-hour effects, cross-day generalisation,
real RSU performance, observed FCD, or buses as general traffic. Pseudonymisation is not
anonymity, and private execution is not publication permission.

## 8. Decision record

- Owner decision: approved in conversation, 28 July 2026 (`yea approved GO`), against the
  exact complete boundary in §1.
- Agent actions: record the approval; freeze inherited engineering details before derivation;
  process locally; run only the permitted private-Colab bundle; return evidence for review.
- Decisions not taken: supervisor approval, public release, actor admission, acceptance of a
  scientific claim, or any threshold/result change after observation.

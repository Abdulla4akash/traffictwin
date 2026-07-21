# Randy/VEC Source Snapshot Audit v0.6

Status: **`VEC-01` accepted with scoped downstream blockers**

This is the Gate A evidence record for the v0.6 work. It reconciles Randy's written response
against the exact Git objects, source code, arrays, XML, tables, and checkpoints that were
available on 21 July 2026. It does not claim that later integration capabilities are implemented.

The complete deterministic record, including one SHA-256 digest per admitted file, is
[`vec_source_snapshot_audit.json`](../reference/generated/vec_source_snapshot_audit.json).

## Pinned sources

| Source | Audited commit | `origin/main` | Preserved local worktree |
|---|---|---|---|
| `vec_env` | `068b4ea33e640f206ce6a7d04f3d6fae2ac831f4` | exact match | clean at `e98441196270b8fd4cc0eede892df4a0053b2185` on `akash-traffictwin-discovery` |
| `tos-data` | `f6c67acbed3360dba3a0d5c8d1fd557caa99ecff` | exact match | clean at `d27294ef5213e6a20f55632448bd20f5a76a45ab` on `main` |

Both remote references were fetched after confirming clean starting states. The audited files were
then read as `git show <commit>:<path>` objects. Neither external worktree was checked out, edited,
cleaned, committed, or pushed.

## Evidence inventory

| Source | Files | Bytes | Treatment |
|---|---:|---:|---|
| `vec_env` | 7 | 121,564 | producer, evaluator, JAX environment, RSU placement, reconstruction, fidelity, and reproduction sources |
| `tos-data` | 145 | 888,802,649 | dictionary, README, master CSV, traces, occupancy, JSON, per-step/per-task arrays, checkpoints, and tripinfo |
| Randy response screenshots | 2 | 337,598 | hashes only; private screenshots are not copied into this repository |
| **Total** | **154** | **889,261,811** | every admitted file has a SHA-256 digest in the machine record |

No `LICENSE`, `LICENCE`, `COPYING`, `NOTICE`, or `CITATION.cff` file was found in either external
repository.

The inventory includes `jaxmarl/env/vec_jax.py` because the audited evaluator imports and executes
that environment module. It was added when the VEC-07 preflight review exposed its omission from
the earlier 153-file record; a safe runner cannot claim pinned execution while omitting executable
source from the hash boundary.

## Trace and occupancy verification

The five occupancy CSVs use the observed columns
`sumo_vehicle_id,slot,t_enter,t_exit`. The producer defines both bounds as inclusive. For every
scenario the audit rebuilt a Boolean occupancy matrix from those spans and compared it with the
trace `mask` cell by cell.

| Scenario | `T` | `maxN` | RSUs | Active vehicle-seconds | Occupancy rows | Unique SUMO IDs | Exact mask |
|---|---:|---:|---:|---:|---:|---:|---|
| `wd_am` | 10,800 | 215 | 9 | 1,166,439 | 5,381 | 5,377 | yes |
| `wd_pm` | 25,200 | 163 | 10 | 2,621,666 | 12,232 | 12,232 | yes |
| `ev` | 23,400 | 175 | 12 | 1,898,428 | 9,130 | 9,129 | yes |
| `inc` | 3,600 | 2,488 | 10 | 8,747,692 | 5,307 | 3,780 | yes |
| `we` | 32,400 | 139 | 10 | 2,776,283 | 13,249 | 13,249 | yes |

All five traces have contiguous one-second `times`, `dt=1.0`, valid slot/time bounds, no
overlapping occupants in a slot, no overlapping visits for the same SUMO vehicle, and an inclusive
span total equal to the trace mask count. Repeated IDs in some files are valid non-overlapping
visits, not duplicate concurrent occupants.

## Instrumented run verification

The audited package contains 60 per-run JSON files, 60 per-step NPZ files, and six per-task NPZ
files.

All 60 per-step files passed the following checks:

- exact 18-key schema, expected shapes, and values in documented ranges;
- `times`, active counts, `T`, `maxN`, and RSU dimensions reconcile with the scenario trace;
- `veh_k`, `veh_done`, and route counts reconcile internally;
- completion, routing shares, fleet assignment, and latency reconcile with the corresponding JSON;
- `slot_tier` is in `0..2`, `slot_is_ev` is Boolean, target indices are in range, and eligible V2V
  targets are never the source slot.

The JSON latency and the sum of stored float32 per-step latency can differ by normal accumulation
rounding. The audit admits only differences within `1e-5` relative or `0.001 ms/task` absolute;
all files passed. Vehicle queue signal is present in all 60 files, while positive RSU busy/load
signal occurs in 28.

The target fields are decision-time eligibility evidence, not unconditional transfer evidence.
Across the 60 files there are:

- 48,693,467 V2I decision rows with at least one task, including 4,368 with
  `veh_best_rsu == -1`;
- 39,956,365 V2V decision rows with at least one task, including 55,658 with
  `veh_best_v2v == -1`.

Therefore `veh_action == 1/2` means the policy selected that action. A non-negative corresponding
target identifies the eligible best RSU/peer used by the evaluator; `-1` means no eligible target.
TrafficTwin must not describe a selected action with `-1` as a completed offload.

The per-task schema is exactly `task_type`, `task_lat_ms`, `task_met`, and `task_active`. None of the
six files contains per-task energy or an eventual physical-completion field. `task_met`, `done`, and
JSON `completion` concern deadline success. They must not be renamed to physical completion.

## Checkpoints and evaluator

Both actor checkpoints load safely with `allow_pickle=False`. Each contains the expected float32
`17 -> 64 -> 64 -> 3` dense actor parameters.

| Checkpoint | Observed size |
|---|---:|
| baseline Model C actor | 21,880 bytes |
| UK-2030 Model C actor | 21,869 bytes |

Randy's response described each as approximately 74 KB. The reviewed Git blobs are approximately
22 KB each, so the presence and structure claim is confirmed but the stated size is not.

The documented evaluator command, writer flags, and checkpoint paths exist. However,
`eval/eval_sumo_stage1_mc.py` prepends a fixed `~/scratch/vec-offloading-jaxmarl-fullport` import
path. `VEC-07` cannot call this as an assumed portable command: its runner must control the source
path, isolate outputs, enforce timeouts, and verify that imports resolve to the pinned commit.

## Tripinfo coverage

All four gzip XML files parse, use unique trip IDs, and have finite non-decreasing depart/arrival
times. Exact `sumo_vehicle_id` joins are possible, but coverage is not universal.

| Trace | Occupancy IDs | Matched trip IDs | Missing | Missing at trace boundary | Missing before boundary |
|---|---:|---:|---:|---:|---:|
| `wd_am` | 5,377 | 5,377 | 0 | 0 | 0 |
| `wd_pm` | 12,232 | 12,180 | 52 | 52 | 0 |
| `ev` | 9,129 | 9,094 | 35 | 35 | 0 |
| `inc` | 3,780 | 3,020 | 760 | 746 | 14 |
| `we` | 13,249 | 13,210 | 39 | 39 | 0 |

Most unmatched vehicles remain present at the trace boundary and are therefore candidates for
right-censoring. The 14 incident vehicles that disappear earlier are not assigned an invented
cause. `VEC-05` must preserve the full-day trip clock, publish eligibility and exclusions, and
compute journey metrics only over explicitly matched vehicles.

## Randy response reconciliation

| Response area | Audit decision |
|---|---|
| Writer provenance | confirmed at the pinned `vec_env` commit |
| Checkpoints and one-line command | files and command confirmed; checkpoint size differs and the evaluator import path is not portable |
| Completion evidence | confirmed as per-arrival deadline success, not eventual physical completion |
| Vehicle identity | confirmed exactly through occupancy spans and trace masks |
| Tier/EV assignment | confirmed as a fixed per-slot assignment for each run; recycled vehicles inherit the slot's assignment |
| Action targets | confirmed as eligible best targets at decision time; a selected action can still have `-1` and is not proof of transfer |
| Tripinfo | all four files confirmed; joins are exact but incomplete as quantified above |
| Arbitrary FCD | partially confirmed; the builder accepts FCD/network inputs, but writes `dt=1.0` without deriving it and defaults to Manchester-specific Drakewell RSU locations |
| Reuse | Randy's permission confirms sanitized samples and aggregates for the dissertation with both repositories cited and required labels retained |

The master evaluation CSV has 300 rows, all five cells, and only engine version
`v2_post_nrsus_fix`.

## Downstream blockers and required controls

Gate A itself is complete. These limits block only the dependent claim or capability until handled:

| ID | Affects | Required handling |
|---|---|---|
| `per_task_energy_absent` | `VEC-09` | do not publish per-task or denominator-sensitive energy metrics from these rows |
| `eventual_physical_completion_absent` | `VEC-02`, `VEC-09` | model the field as deadline success; keep eventual completion unavailable |
| `action_is_not_transfer_proof` | `VEC-04`, `VEC-09` | join targets only with eligibility-aware semantics and expose `-1` |
| `fcd_resolution_not_enforced` | `VEC-06` | independently parse and require one-second FCD timestamps before launch |
| `rsu_placement_is_manchester_specific` | `VEC-06` | require explicit validated placement or clearly select the pinned Manchester default |
| `evaluator_repo_path_hard_coded` | `VEC-07`, `VEC-08` | control import resolution and prove the pinned code ran |
| `no_repository_licence` | `VEC-12` | publish only within Randy's scoped written permission; do not infer raw/checkpoint redistribution rights |

The `_s102` rows must keep the `best-of-seeds` label, both external repositories must be cited, and
the engine label `v2_post_nrsus_fix` must accompany reused evidence.

## Reproduction

The checked audit was generated with:

```bash
uv run python scripts/audit_vec_source_snapshot.py \
  --vec-repo /path/to/vec_env \
  --tos-repo /path/to/tos-data \
  --permission-image randy-email-page-1.jpg=/private/path/to/page-1.jpg \
  --permission-image randy-email-page-2.jpg=/private/path/to/page-2.jpg \
  --output docs/reference/generated/vec_source_snapshot_audit.json
```

The private email pages are hashed and then discarded by the script; they are never written into
the repository. Rerunning against unchanged Git objects and the same two permission screenshots
must produce byte-identical JSON.

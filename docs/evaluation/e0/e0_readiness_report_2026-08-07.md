# E0 corrected-evaluator smoke: provenance and readiness

Date: 2026-08-07

Decision: **PASS for the bounded 10-step E0 validity gate**

Next-stage boundary: no E1 or full-hour run was started.

The authoritative machine records are the
[predeclared manifest](e0_manifest_v1.json) and
[deterministic validation report](e0_validation_v1.json). The manifest SHA-256 is
`8d81cf30f1ada3e9af7c799c9ebd0e01a427a67c570f583b658b11717a5eab93`; the validation report
SHA-256 is `ff095ac91765c1e59410c4b902ff47e018cf00a7c9513ca33e2983a8e18ae38d`.

## Readiness decision

The corrected strongest-link/default reference is technically ready for one full-hour execution
under the same manifest, after explicit approval. The decision is provisional rather than
canonical because the physical absolute RSU waiting-room size, a complete historical fleet/run
contract and an `enter`-instrumented incident trace remain unavailable. A full corrected reference
would still be a reference run, not E1 and not a reproduction of Randy's reported `0.6943`.

This smoke establishes bounded task and work accounting. It does not answer whether load-aware
placement improves, ties or harms task outcomes.

## Verified provenance

| Item | Selected identity | State used |
|---|---|---|
| TrafficTwin | `95e7b1e4048a11a2002473e83eb0aa1c584c9bbc` | New `agent/e0-corrected-reference-v1` branch; pre-existing untracked `year_1_report_randy_11315534.pdf` preserved and excluded |
| TrafficTwin remote main observed at predeclaration | `a462c72b81f1668eef4ea0b7f8e806be4d208b47` | Selected branch was 6 commits ahead and 271 commits behind; divergence did not block direct pinned evaluation |
| vec_env | `0f01f4d2082d3e8b735e74a873095ab8eeba37cc` | Clean worktree on `agent/traffictwin-e0-pinned-0f01f4d`; existing `akash-traffictwin-discovery` at `e98441196270b8fd4cc0eede892df4a0053b2185` preserved |
| tos-data | `a75bbdb1a956f828ee0e9b97b33506bd32d31b85` | Clean worktree on `agent/traffictwin-e0-data-a75bbd`; existing checkout at `d27294ef5213e6a20f55632448bd20f5a76a45ab` preserved |
| Evaluator | `eval/eval_sumo_stage1_mc.py`, SHA-256 `260b90ff400cb5048ae4e74fb6c407d197fbfc80d91d7b7edf0c65640b5bd669` | Unmodified audited vec_env source |
| Environment model | `jaxmarl/env/vec_jax.py`, SHA-256 `73d83d062fad030941f5236835cce8e86caacc4d44eb7a1129047e99228886ff` | Unmodified audited vec_env source |
| Actor | `checkpoints/mappo_modelc_17dim__envs128__lr3e-3__seed100_actor_params.npz`, SHA-256 `93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208` | Frozen Paper-2A 17-dimensional MAPPO actor, training seed 100 |
| Trace | `traces/trace_inc_fullrsu.npz`, SHA-256 `e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056` | Friday 2024-03-15, 20:00-21:00 local; SUMO seed 43; first 10 seconds only |

The source repos were fetched before their remote identities were selected. Separate worktrees
prevented reset or overwrite of Randy-originated checkouts. No external repository was pushed.

The relevant historical tos-data output was inventoried but excluded from corrected-baseline use:

- `instrumented/json/baseline_uk2030_inc_fs0.json` — SHA-256
  `69e9774338c4650a5465a516dd076553da37507e2a9b9d0fef18bc319d058404`;
- matching per-step NPZ — SHA-256
  `c02733a8d980c79a0c9d17463745461cc10fa44b41eba5240821651c0c7e677f`;
- matching per-task NPZ — SHA-256
  `2f738fa20e4173753942136b2e5d39a031ee7ba40a24f0d446f44e58b3541929`.

Those artifacts lack the corrected sequential/reject/conserved accounting fields. They are not
corrected-engine baselines.

## Exact execution configuration

The exact environment-variable map and argv are in `execution` within the manifest. The two runs
differed only in the repeat-specific output directory (`run_1` and `run_2`). Key settings were:

- evaluator seed 0; fleet seed 0; actor training seed 100; trace SUMO seed 43;
- 10 steps from the Manchester incident trace;
- `uk2030` fleet preset, explicitly provisional;
- sequential substep accounting with three gate iterations;
- conserved vehicle queues and physical per-task RSU rejection semantics;
- strongest-link/default placement (`rsu_lb=off`) and zero backhaul forwarding cost;
- fixed 1x RSU service with simulated scaling off;
- provisional `2.5 * 2488 = 6220` tasks per RSU admission/in-flight ceiling.

The 2.5x value is the evaluator's documented `50 / 20` training-parity ratio. It is an admission
or waiting-room ceiling, not compute power. No approved physical absolute ceiling was found.

The execution host was macOS 26.4.1 on arm64. The isolated CPU environment used Python 3.11.15,
JAX/JAXLIB 0.4.30, NumPy 1.26.4, ml-dtypes 0.5.4, opt-einsum 3.4.0 and SciPy 1.17.1, with X64
disabled. Local SUMO was 1.27.1, whereas trace provenance names SUMO 1.27.0. The evaluator replayed
the NPZ and did not invoke SUMO, so this is a compatibility smoke, not an exact canonical SUMO
reproduction.

The evaluator hard-codes a historical import location. A local adapter supplied an empty `env`
package initializer and symlinked only the pinned `vec_jax.py`; adapter initializer SHA-256 is
`5917ef0cb0cf634d1f079acd0dfd129d8b81016be12968d1977202046ee8cf5b`. The first whole-directory
symlink attempt stopped at import before `main()` and before any task simulation because an optional
JaxMARL training dependency was absent. Its log is retained with SHA-256
`c80aaa0118c95a86c7eacef85f0437d6ba4f478775398f65f3f9b2fa255a11a9`. No evaluator change was
required. The scientific configuration was predeclared first; this adapter provenance was added to
the manifest after the failed import and before either successful task-simulating run.

## Observed smoke result

Both successful runs produced the same scientific result:

| Ledger item | Observed |
|---|---:|
| Offered tasks | 36,856 |
| Admitted tasks | 35,195 |
| Deadline-met simulated outcomes | 25,227 |
| Served but deadline-missed | 9,968 |
| Local vehicle-queue rejections | 108 |
| V2V helper-queue rejections | 1,553 |
| All other rejection/unavailability codes | 0 |
| Offered-denominator deadline attainment | 0.6844747123941828 |
| Admitted-denominator deadline attainment | 0.716777951413553 |

These are simulated deadline outcomes. There are no native physical completion or result-return
events supporting stronger language.

## Conservation and numeric verdict

The validator executed 32 checks per run, with no failures:

- task conservation: `36,856 = 35,195 + 108 + 1,553`;
- V2I work in milliseconds: `122,473 = 122,473 + 0`;
- vehicle-queue work in milliseconds: `820,565.8125 = 789,046.9375 + 31,518.875`;
- per-task outcome codes 3 through 8 reconcile with all six aggregate terminal reason counters;
- per-step arrivals and active task records equal offered tasks;
- per-step deadline-met records, per-task deadline flags and outcome code 1 reconcile;
- no NaN, infinity, negative count/work/latency, impossible completion fraction, active task without
  a terminal outcome, inactive task with a terminal outcome or silent task loss was found;
- offered and admitted completion/latency denominators were independently recomputed from per-task
  records and retained separately.

## Repeat and output identities

The repeat comparison used code, not visual judgment: exact JSON equality after excluding only
`wall_s`, plus exact dtype/shape/byte SHA-256 equality for every NPZ array. Scientific summaries and
all arrays were identical. Run wall times were 12.7 s and 12.6 s, so raw summary/log hashes differ.

Raw output locator: `local-output:e0_outputs/e0-corrected-reference-v1`.

| Artifact | Run 1 SHA-256 | Run 2 SHA-256 |
|---|---|---|
| `summary.json` | `298ccbee8bae82d043a2dcd4401a72d7bce2437e0027e208db53970ca9f2aa7b` | `faa261dfa8c3a3c9532bdddb563ef2877cb60740b5537510e3dc561cb1a76e6b` |
| `per_step.npz` | `9ca62b5df68c6b39d8961b1a0376d23ba1b2a646792305fda6e5dae9447e9904` | identical |
| `per_task.npz` | `01aa251422a35f692291d8e7085044c97b6a62c11213f7a81b7805c59437643f` | identical |
| `stdout_stderr.log` | `e9fb5c131bfb4ea9148381c903c9ea3b1154afa2e01597d172421ac3426ee9e0` | `a2aeaea7013a47180f7de261e91528416ad6eda7caca97242708cbe2249a80f6` |

Raw NPZ files and logs remain outside Git. The checked-in validation JSON retains their identities
and all array-level digests.

## Blockers and missing information

1. No approved physical absolute RSU admission/waiting-room ceiling is available. The 6220-task
   ceiling is provisional fleet-scaled training parity.
2. The complete historical run/sweep contract is unavailable. `uk2030` is a documented provisional
   anchor, not proof of the exact fleet behind every reported result.
3. The incident trace has no `enter` channel. The evaluator therefore reports
   `engine_version=v2_post_nrsus_fix` and uses mask-only queue reset semantics.
4. Canonical trace provenance is SUMO 1.27.0; the local installed binary is 1.27.1.
5. The ten-second window did not activate RSU-cap, DLA-gate, V2I-unavailable or V2V-unavailable
   terminal pathways. Their counters reconciled at zero, but this smoke did not exercise them.
6. No native physical completion/result-return events are available; only simulated deadline
   attainment can be claimed.
7. A full corrected one-hour strongest-link reference has not been run, and Randy's `0.6943` has
   not been reproduced.

## Validation code and checks

The reusable validator is [scripts/validate_e0_smoke.py](../../../scripts/validate_e0_smoke.py),
with focused tests in
[tests/test_validate_e0_smoke.py](../../../tests/test_validate_e0_smoke.py). Verification before
handoff:

- focused tests: `3 passed`;
- Ruff lint and format checks: passed;
- JSON parsing for manifest and validation report: passed;
- `git diff --check`: passed.

The next authorised action is to seek explicit approval for one full-hour corrected strongest-link
reference under this manifest, ideally after the cap and fleet contract are confirmed. Do not start
E1 automatically.

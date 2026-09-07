# Manchester working-day generalisation pilot

**Completed:** both full runs and their paired validation passed. Start with
[ANALYSIS.md](ANALYSIS.md) for the result and interpretation, or
[comparison.csv](comparison.csv) for the compact table.

This exploratory pilot compares fresh per-task sequential least-busy placement
with ingress execution under the same live deadline-aware admission rule. The
primary comparison is per-task minus ingress in percentage points of all
offered tasks meeting their deadlines. One matched fleet draw is used. The
scenario was selected before inspecting either condition's outcome.

## Input and fixed settings

- Scenario: Tuesday 15 October 2024, full 08:00–11:00 Manchester morning window.
- Canonical trace: `vec_env-state-delay-run/eval/data/manchester_workingday/trace_wd_am_wdrsu.npz`.
- Trace dimensions: 10,800 one-second rows, 215 padded vehicle slots, nine RSUs.
- Frozen actor: `tos-data-full/checkpoints/mappo_modelc_17dim__envs128__lr3e-3__seed100_actor_params.npz`.
- Recorded actor training: Model C phase4_iid synthetic mobility, MAPPO, 128
  environments, learning rate 0.003, 25k episodes; onehot17 observation.
- Fleet: UK2030, fleet seed 1; evaluator seed 0. No retraining.
- RSU capacity: fixed absolute 6,220 tasks per RSU; service 1×; arrival rate 1.5.
- Forwarding cost 0 ms; fresh placement information; scaling off.
- Sequential task accounting, three reconciliation iterations, explicit
  rejection, conserved vehicle queues; per-visit queue reset enabled, SoC
  reset on entry disabled.
- Frozen evaluator commit: `908bd10f86542de94fc38af90dd56c2ccc08cf9b`.
- Runtime: CPython 3.11.15, JAX/JAXlib 0.4.30, NumPy 1.26.4, Mac arm64 CPU.

Exact paths, hashes, environment flags, tolerances, stopping rules and the
comparison are recorded in [manifest.json](manifest.json). The evaluator and
earlier experiment records are preserved.

## Input validation and interpretation

The canonical trace and source FCD match their published SHA-256 checksums.
An independent streaming reconstruction from that FCD matches all 10,800 rows
of positions, speeds, active masks, entry markers and timestamps exactly.
There are 5,381 vehicle visits, including 1,722 immediate slot handovers. A
matching occupancy table is supplied here. Every active position is within
500 metres of at least one of the nine canonical RSUs; this is geometric
coverage, not guaranteed radio admission.

The initial preparation check found that the old working-day trace uses a
different slot order. Its original occupancy table therefore cannot be used
with the canonical trace. We reconstructed a canonical occupancy table from
the FCD instead. This happened before any evaluator results were generated.
See [input_validation.json](input_validation.json) and [audit_trace.py](audit_trace.py).

This is scenario transfer within Manchester. Relative to the old incident
study, the date, duration, density, RSU layout, number of RSUs, deterministic
slot assignment and availability of vehicle-entry markers differ. Both new
arms use the same canonical inputs and queue-reset convention. Cross-scenario
differences are not attributed solely to traffic, and this is not an
independent geographical dataset. Same fleet seed with a different number of
slots does not mean the realised fleet is identical to the incident fleet.

The absolute capacity remains 6,220. Keeping the old ratio command would have
silently reduced it to 538 tasks per RSU at this smaller padded fleet width.

## Execution and validation

Two 300-step probes run first, one per condition. They must pass source/input
identity, finite-value, task accounting, queue/path and paired-input checks
before the full runs begin. Full runs use the same two conditions serially.
Each full task-record prefix must match its corresponding probe, and paired
actions, fleet, arrivals, task types and ingress selections must remain equal.
Actor logits use the predeclared absolute tolerance of 0.00001.

The runner writes `status.json` and `pilot.log`, preserves each attempt,
validates the outputs, then generates `comparison.csv` and `RESULTS.md`.
There is no within-cell checkpoint; `--resume` verifies successful cells and
restarts only incomplete cells in a new attempt directory. A source/input
change, failed check, evaluator error, low disk space or three-hour cell
timeout stops the campaign without automatically retrying it.

```sh
../vec_env-state-delay/.venv/bin/python run_pilot.py --resume
```

This command is only for resuming an interrupted campaign. The runner lock
prevents overlapping launches. The short benchmark includes compilation and
is an estimate, not a measured full-run duration.

The one-draw results are descriptive. They do not establish replicate-level
significance or equivalence. No additional scenarios or repetitions are part
of this two-run pilot.

# VEC-04 Tier, EV, Task, Action, and Target Joins

Status: implemented and accepted for all six audited runs that contain matched per-step and
per-task artifacts at `tos-data` commit `f6c67acbed3360dba3a0d5c8d1fd557caa99ecff`.

`integration.vec_task_join` requires an accepted VEC-03 identity snapshot and exact VEC-02
trace/per-step/per-task schemas. It reconciles `task_active` with `veh_k`, `task_met` with
`veh_done`, per-step arrivals/completions, latency sums, and active identity coverage.

Each streamed task row carries the exact occupancy-bounded vehicle ID, fixed per-slot operational
tier/EV assignment, latency, deadline-success state, action, and eligible target state. `-1` is
`no_eligible_target`; it is not a failure. Action is not transfer confirmation. Eventual
completion, link quality, per-task energy, and protected-attribute claims remain unavailable.

The read-only verifier admitted 46,861,416 tasks across six runs and retained 1,907 no-target tasks
as an explicit availability state. External evidence remained unchanged; the report contains no
raw vehicle IDs.

```bash
uv run python scripts/verify_vec_task_join.py \
  --tos-data-repo ../external/tos-data \
  --output docs/reference/generated/vec_task_join_verification.json
```

VEC-05 trip joins, VEC-09 scientific admission, and VEC-10 CLI/UI wiring remain separate.

# Parameter Sweep Composer

TrafficTwin `EXP-01` expands a small declared grid into reproducible seed snapshots, labelled local
synthetic bundles, or **unexecuted** external coordination requests. It is intended for controlled
software and robustness studies, not for claiming that Randy, VEC/TOS, SUMO, or a real traffic
system was executed.

## Modes

| Mode | What is written | What runs |
|---|---|---|
| `seed_snapshots` | parent-linked `ScenarioSeed` YAML per point | schema validation only |
| `local_synthetic_bundles` | seeds, complete synthetic bundles, result JSON, response CSV | TrafficTwin synthetic generator, validator, and core metric engine |
| `external_run_requests` | seeds and request JSON with suggested IDs | nothing external; every request says `not_executed` |

All modes set `synthetic_evaluation=true`. External request artifacts set
`direct_launch_supported=false` and leave `launcher` and `command` null.

## Bounds and supported fields

The complete Cartesian grid is limited to four axes, 16 unique finite scalar values per axis, and
256 points. A local response surface accepts at most 16 known core metric keys. TrafficTwin rejects
the whole request before writing output if a derived point violates its base schema.

The machine-readable contract also publishes each path's type/range or enumeration. Local mode
uses the generator's declared table sizes to reject a complete sweep estimated above 2,000,000
rows before writing. This bounds admission; it is not a runtime or memory guarantee.

The closed synthetic catalogue covers duration, sampling interval, vehicle count, task-arrival
rate, RSU count/capacity, network delay, congestion multiplier, policy profile, trip count, and
random seed. The seed catalogue covers demand/birth-rate multipliers, fleet/RSU counts, policy
label, random seed, and declared event closure/duration/demand fields. Run
`traffictwin experiment parameter-sweep-contract` for the exact machine-readable list.

Mixes and lists are intentionally absent: changing one mix share independently can violate the
sum-to-one contract, while incident/failure/placement changes require dedicated mutation
semantics.

## Request example

The repository includes [parameter_sweep_request.yaml](../examples/parameter_sweep_request.yaml).
Its essential shape is:

```yaml
schema_version: '1.0'
sweep_id: sweep-demand-capacity
title: Synthetic demand and RSU-capacity response
mode: local_synthetic_bundles
base_synthetic_config:
  # Complete strict SyntheticScenarioConfig snapshot; see the example file.
axes:
  - parameter_path: synthetic.task_arrival_rate
    values: [0.08, 0.12, 0.16]
  - parameter_path: synthetic.rsu_capacity
    values: [20.0, 35.0]
metric_keys:
  - task.completion.rate
  - infra.utilisation.mean
```

## CLI use

```bash
traffictwin experiment parameter-sweep-contract \
  --output build/parameter-sweep-contract.json

traffictwin experiment parameter-sweep \
  --request examples/parameter_sweep_request.yaml \
  --output build/demand-capacity-sweep
```

The destination must not exist unless `--overwrite` is explicit. Empty paths, symbolic links, the
current directory, the home directory, the filesystem root, and ancestors of the current/home
directory are rejected before expansion. On success the destination contains:

```text
request.yaml
sweep_result.json
response_surface.csv
seeds/<point-id>.yaml
bundles/<point-id>/...             # local mode only
external_requests/<point-id>.json  # external mode only
```

## Streamlit use

Open **Parameter Sweep**, select a synthetic preset and mode, declare one to four axes with
comma-separated scalar values, select numeric response metrics for local mode, and choose the
exact output directory. The page shows each point's assignments, seed, bundle fingerprint or
execution status, and the long-form response surface. JSON and CSV downloads come from the typed
library result.

## Python use

```python
from traffictwin.experiments import (
    ParameterSweepMode,
    ParameterSweepRequest,
    SweepAxis,
    SweepParameter,
    execute_parameter_sweep,
)
from traffictwin.synthetic.scenarios import preset_config

request = ParameterSweepRequest(
    sweep_id="sweep-demand",
    title="Synthetic demand response",
    mode=ParameterSweepMode.LOCAL_SYNTHETIC_BUNDLES,
    base_synthetic_config=preset_config("baseline"),
    axes=[
        SweepAxis(
            parameter_path=SweepParameter.SYNTHETIC_TASK_ARRIVAL_RATE,
            values=[0.08, 0.12, 0.16],
        )
    ],
    metric_keys=["task.completion.rate"],
)
result = execute_parameter_sweep(request, "build/sweep")
```

Use `expand_parameter_sweep(request)` to validate and inspect every derived snapshot without
writing files. Use `parameter_sweep_response_to_csv(result)` for the provenance-bearing table.

## Response and provenance semantics

Each point records ordered parameter assignments plus request, parent, point, seed, and—when
local—bundle fingerprints. Each response row repeats all assignments and identifies its run, seed,
bundle, metric status, numeric value, unit, and reason codes.

Only finite numeric core-metric values enter `response_value`. Mapping or other non-numeric metric
values become `unavailable` with `RESPONSE_VALUE_NON_NUMERIC`. Missing and invalid evidence stays
missing or invalid and is never replaced by zero.

Point and result fingerprints are independent of generation time. The synthetic generator's
explicit random seed remains part of the request/point identity.

## Boundaries

- The generated model is a deterministic software fixture, not calibrated simulation.
- The composer does not train, schedule, queue, or launch a policy or simulator.
- An external request is not evidence of execution or scientific validity.
- Completed external results must return as ordinary immutable bundles for validation/import.
- No response-surface relationship is automatically causal, optimal, significant, or externally
  valid.
- Raw inputs and the base snapshot are not edited in place.

See [ADR-036](decisions/ADR-036-bounded-parameter-sweep-composer.md), the
[synthetic data model](synthetic_data_model.md), and the
[experiment protocol](experiment_protocol.md).

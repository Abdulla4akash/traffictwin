# Phase 6 Discovery Decision

Decision date: 2026-07-17

## Decision

Phase 6A discovery is complete. Phase 6B adapter implementation is not approved by the available evidence.

Reason: no real Randy/VEC artifacts, SUMO artifacts, schemas, units, configuration files, invocation commands, checkpoints, metric scripts, notebooks, job scripts, logs, or output directories were found in the inspected repository or workspace.

## What Is Confirmed

- TrafficTwin's internal synthetic bundle contract is present and tested.
- The existing generic CSV adapter is manifest-driven and should remain free of Randy-specific behavior.
- The existing import-first pipeline is the correct integration target:

```text
real artifacts
    -> adapter-specific validation
    -> standard TrafficTwin run bundle
    -> existing Phase 2 validation
    -> existing canonical records
    -> existing Phase 3 metrics
    -> existing EvidencePack
    -> existing Phase 5 diagnostics
    -> existing UI
```

## What Is Not Confirmed

- Randy's CSV schema.
- SUMO output formats present in the project environment.
- Units for real task, infrastructure, traffic, vehicle, or trip outputs.
- Identifier conventions and join keys.
- Which artifacts are training outputs, validation outputs, SUMO outputs, scenario configuration, or summaries.
- A headless CLI, Python API, shell script, notebook workflow, or CSF job contract.
- Runtime and output-size expectations.
- Existing metric formulas used by Randy's scripts.
- Which ScenarioSeed controls map to real environment controls.

## Capability Decision

| Capability | Decision | Evidence |
|---|---|---|
| Direct launch | `false` | No documented/tested headless command found. |
| Asynchronous launch | `false` | No queue or job mechanism found. |
| Real run-bundle import | `unknown` | No real bundle schema found. |
| Task arrival multiplier | `unknown` | No real config or argument found. |
| Workload class mix | `unknown` | No real config or argument found. |
| Workload ordering | `unknown` | No real config or argument found. |
| Vehicle count | `unknown` | No real config or argument found. |
| Vehicle tier mix | `unknown` | No real config or argument found. |
| RSU count | `unknown` | No real config or argument found. |
| RSU capacity | `unknown` | No real config or argument found. |
| RSU placement | `unknown` | No real config or argument found. |
| RSU failure | `unknown` | No real config or argument found. |
| Action toggles | `unknown` | No real config or argument found. |
| Signal timing | `unknown` | No real SUMO scenario control found. |
| Lane closure | `unknown` | No real SUMO scenario control found. |

## Implementation Decision

Do not implement:

- `randy_vec.py`;
- SUMO FCD, tripinfo, detector, or queue adapters;
- integration manifest builders;
- real launchers;
- UI controls that enable real execution;
- compatibility metrics against Randy's formulas.

## Approval Gate For Phase 6B

Phase 6B may begin only after the supplied artifacts establish:

- at least one real or sanitised source schema;
- declared units;
- provenance fields;
- a safe mapping to one or more canonical record types;
- expected validation findings;
- sample fixtures that can be committed or referenced safely;
- and, for launcher work, a documented headless execution contract.

Until then, the recommended next increment is artifact acquisition, not code.

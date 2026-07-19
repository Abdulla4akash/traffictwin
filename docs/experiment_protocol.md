# Experiment Protocol Export

The Experiment Protocol Exporter turns a validated, registered `Experiment` into an exhaustive,
versioned run checklist. It supports coordination with a person or external environment while
TrafficTwin direct launch remains unavailable.

It is a planning artifact. Exporting a protocol does not create `Run` records, execute a policy,
schedule work, or assert that a completed bundle is scientifically valid.

## Deterministic Inputs

The exporter uses only:

- the registered `Experiment` snapshot;
- its baseline and variation `ScenarioSeed` snapshots;
- the ordered policy labels;
- the ordered common random-seed set.

For every condition, policy, and random seed, it emits one slot. A protocol is never silently
truncated. Plans above the configured 10,000-slot guard are rejected so the researcher must reduce
or deliberately partition the design.

## Protocol Document

Protocol schema version: `1.0`.

The YAML document contains:

| Field | Meaning |
|---|---|
| `protocol_id` | Stable ID derived from the experiment and input fingerprint. |
| `generated_at` | Snapshot time; defaults to the registered experiment's `updated_at`. |
| `direct_launch_supported` | Always `false` for this exporter. |
| `input_fingerprint` | SHA-256 over the experiment and sorted referenced seed snapshots. |
| `seed_snapshots` | Immutable planning inputs embedded for later audit. |
| `seed_fingerprints` | SHA-256 for each referenced seed. |
| `slots` | Exhaustive ordered run checklist. |
| `matching_fields` | Manifest fields used by the matcher. |
| `warnings` | Unresolved checkpoint or design qualifications. |
| `limitations` | Explicit execution and interpretation boundaries. |

Each slot includes the role, seed, policy label, random seed, seed fingerprint, and suggested run
and bundle IDs. Suggested IDs are coordination metadata, not evidence that an external producer
executed the correct configuration.

## Stable Ordering

Slots are ordered by:

1. baseline, followed by variations in `Experiment.variation_seed_ids` order;
2. policy labels in `Experiment.algorithms` order;
3. random seeds in `Experiment.common_random_seed_set` order.

This order produces stable `slot-0001` identifiers and byte-stable YAML/CSV for the same stored
inputs.

## Checkpoints

A checkpoint is copied into a slot only when the seed's `policy.algorithm` exactly matches the
planned policy label. If the labels differ, TrafficTwin does not guess a checkpoint and does not
require checkpoint equality during matching. The protocol records a warning for that unresolved
pair.

## Bundle Matching

The matcher first runs the normal Phase 2 bundle validator. Rejected bundles are not matched.
Accepted manifests receive one status:

| Status | Meaning |
|---|---|
| `exact` | Core metadata and both suggested run/bundle IDs match one slot. |
| `compatible` | Core metadata matches exactly one slot, but one or both producer IDs differ. |
| `mismatch` | A suggested ID identifies a slot but required metadata conflicts, or IDs point to different slots. |
| `unmatched` | No slot has the same experiment, seed, policy, random seed, and required checkpoint. |

Core fields are `experiment_id`, `seed_id`, `algorithm`, `random_seed`, and checkpoint when the
slot has an evidenced checkpoint. Environment details are not compared because the plan does not
know or invent an external environment version.

A compatible result establishes metadata alignment only. It does not prove execution correctness,
scientific comparability, or simulator provenance.

## CLI

```bash
traffictwin experiment protocol \
  --registry .demo/registry.sqlite \
  --experiment-id EXPERIMENT_ID \
  --format yaml \
  --output protocol.yaml

traffictwin experiment protocol \
  --registry .demo/registry.sqlite \
  --experiment-id EXPERIMENT_ID \
  --format csv \
  --output run-sheet.csv

traffictwin experiment match-bundle COMPLETED_BUNDLE \
  --registry .demo/registry.sqlite \
  --experiment-id EXPERIMENT_ID \
  --format json
```

`match-bundle` returns exit code `0` for `exact` or `compatible`, and `1` for rejected,
`mismatch`, or `unmatched` inputs.

## Streamlit Workflow

Experiment Planner provides:

- protocol YAML and run-sheet CSV downloads for a newly validated plan;
- stable regeneration for registered experiments;
- a read-only completed-bundle check;
- visible warnings when checkpoint alignment is unresolved.

The page retains the `NO DIRECT LAUNCH` label. Matching does not import the bundle or change the
registry.

## Limitations

- The protocol has no command, working directory, runtime, output directory, or environment
  version because no evidenced launcher supplies them.
- It does not reserve work, monitor execution, or change experiment status.
- It does not infer external checkpoint identity.
- It does not replace bundle validation, metric comparison, or provenance inspection.

## Related Documents

- [Architecture](architecture.md)
- [API reference](api_reference.md)
- [CLI reference](cli_reference.md)
- [Run bundle specification](run_bundle_spec.md)
- [Reproducibility](reproducibility.md)
- [User guide](user_guide.md)

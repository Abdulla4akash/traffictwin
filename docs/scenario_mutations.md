# Scenario Mutation Operators

TrafficTwin `EXP-02` creates a separate, validated copy of an explicitly labelled
synthetic/evaluation run bundle and applies one deterministic mutation. It records the parent
bundle fingerprint, every changed parent row, changed-file checksums, derived identifiers, and the
ordinary validation result. The parent directory or ZIP is never edited.

These mutations are controlled software-robustness fixtures. They are not models of real sensors,
traffic, network behavior, RSU failure physics, policy adaptation, or simulator execution.

## Operators

| Operator | Request | Exact behavior |
|---|---|---|
| `row_dropout` | table, fraction, seed | Drops `max(1, floor(rows × fraction))` rows selected by stable seeded SHA-256 order. |
| `timestamp_jitter` | table, maximum seconds, seed | Applies one deterministic signed delta per row to every present absolute timestamp; the common delta is clamped only to keep the earliest timestamp non-negative. |
| `rsu_removal` | exact RSU ID | Removes matching `infra_state` rows and marks the derived seed. Existing task targets are retained because TrafficTwin cannot infer rerouting. |

Timestamp jitter applies a common delta to related timestamps in one row. For example, task
arrival/completion differences and trip departure/arrival differences are preserved unless the
earliest timestamp requires the documented non-negative clamp.

RSU removal deliberately does not rewrite a V2I task's decision, target, completion, latency, or
energy. Ordinary validation and metric availability therefore expose the missing target evidence;
the mutation service never invents the response of a policy that was not rerun.

## Admission and bounds

The parent must pass ordinary bundle validation and either declare a supported synthetic/evaluation
source label or use synthetic execution mode. Confirmation-gated inferred manifests are rejected,
as are imported real-evidence labels.

Version 1 targets only one declared uncompressed CSV table per request. Other bundle files are
copied byte-for-byte before the seed and manifest are deterministically derived. A target gzip CSV
or Parquet table remains explicitly unsupported.

Hard admission limits are:

- 64 source files;
- 25,000,000 total source bytes;
- 100,000 rows in the target table;
- 20,000 exact changed-row ledger entries;
- 3,600 seconds maximum absolute timestamp jitter; and
- a 1,000,000-byte request document.

The output path must not already exist unless overwrite is explicit. Empty paths, symbolic links,
the current directory, the home directory, the filesystem root, and current/home ancestors are
rejected before materialisation. A destination cannot equal, contain, or sit inside its parent
bundle. Explicit overwrite moves the previous destination aside and restores it if final
publication fails.

## Request example

The repository includes [scenario_mutation_request.yaml](../examples/scenario_mutation_request.yaml):

```yaml
schema_version: '1.0'
mutation_id: mutation-task-dropout
title: Deterministic task-row dropout
description: Labelled robustness fixture; not real-world validation evidence.
mutation:
  operator: row_dropout
  table_kind: tasks
  drop_fraction: 0.25
  random_seed: 17
```

## CLI use

```bash
traffictwin experiment mutation-contract \
  --output build/scenario-mutation-contract.json

traffictwin experiment mutate-scenario \
  --bundle tests/fixtures/bundles/baseline_valid \
  --request examples/scenario_mutation_request.yaml \
  --output build/task-dropout-mutation
```

On success the destination contains:

```text
request.yaml
mutation_manifest.json
bundle/
  manifest.yaml
  seed.yaml
  <copied and mutated declared files>
```

`bundle/` is an ordinary TrafficTwin bundle and can be passed to `bundle validate`, `metrics
compute`, `diagnose bundle`, comparison, temporal analysis, or provenance workflows. The mutation
manifest is outside the bundle so its derived fingerprint does not form a circular dependency.

## Streamlit use

Open **Scenario Mutations**, select a synthetic/evaluation parent bundle and one operator, enter the
bounded parameters and exact output directory, then select **Build Mutated Copy**. The page shows
parent/derived fingerprints, ordinary validation status, every changed parent row, before/after
row fingerprints, changed fields for jitter, and changed-file checksums. Downloaded JSON comes
directly from the typed library artifact.

## Python use

```python
from traffictwin.experiments import (
    MutationTableKind,
    RowDropoutMutation,
    ScenarioMutationRequest,
    execute_scenario_mutation,
    plan_scenario_mutation,
)

request = ScenarioMutationRequest(
    mutation_id="mutation-task-dropout",
    title="Task dropout robustness case",
    mutation=RowDropoutMutation(
        table_kind=MutationTableKind.TASKS,
        drop_fraction=0.25,
        random_seed=17,
    ),
)
plan = plan_scenario_mutation("parent-bundle", request)
result = execute_scenario_mutation("parent-bundle", request, "build/mutation")
```

Planning reads and validates the parent but does not create a destination. Execution repeats the
admission checks, builds a temporary sibling tree, validates the derived bundle, verifies its
planned fingerprint, and only then replaces the exact destination when overwrite was requested.
The previous destination is rollback-protected until publication succeeds.

## Provenance and interpretation

Every `MutationRowChange` identifies the parent file and line, action, before fingerprint, optional
after fingerprint, and exact field values changed by jitter. `MutationFileChange` reconciles
before/after checksums and row counts for the target table, derived seed, and derived manifest.
Request, plan, parent, derived bundle, and result fingerprints are deterministic and independent of
the result-generation timestamp.

One operator is applied per request. A derived bundle may be used as another explicitly labelled
parent, producing an auditable chain rather than silently combining mutations. Robustness results
must retain every parent/mutation link and cannot be presented as causal, calibrated, optimal, or
externally valid evidence.

See [ADR-037](decisions/ADR-037-deterministic-scenario-mutation-operators.md), the
[run-bundle specification](run_bundle_spec.md), and the
[fault-injection methodology](fault_injection_methodology.md).

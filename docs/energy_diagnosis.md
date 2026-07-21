# R8 Completed-Task Energy-Anomaly Diagnosis

R8 v1.0 is a deterministic candidate rule over one exact whole-run energy indicator. It compares
already-computed mean energy per completed task with a declared boundary and checks the completed-
task denominator before it can trigger.

R8 is not a statistical anomaly detector, hardware benchmark, energy model, causal diagnosis, or
efficiency standard. Its default exists for labelled synthetic development and must not be
presented as externally calibrated.

## Evidence Boundary

R8 reads only these metrics from `EvidencePack.metric_collection`:

| Metric | Required meaning |
|---|---|
| `task.energy.per_completed_j` | Mean per-task total energy over completed tasks with eligible energy evidence. |
| `task.completed.count` | Exact completed-task denominator used to reconcile energy population metadata. |

The energy metric must be `available`, finite, non-negative, and use `J/task`. It must carry the
exact canonical v1.0 task-energy contract fingerprint, quantity `per_task_total_energy`, energy
unit `J`, completed-task eligibility policy, and complete coverage. Eligible and population counts
must match, and the population must equal the available `task.completed.count` metric in `count`.

R8 never reads task rows, recalculates energy, converts units, or treats missing values as zero.
The current TOS joules-per-arrival summary is a separate source-specific measure and is not admitted.

## Configuration and Status

| Configuration | Default | Meaning |
|---|---:|---|
| `minimum_energy_per_completed_task_j` | `1.50` | Inclusive high-energy candidate boundary in `J/task`. |
| `minimum_completed_tasks` | `10` | Minimum completed-task support required to trigger. |

The defaults are provisional synthetic-development settings. The status rules are:

- `triggered`: energy is at or above the boundary and completed support is sufficient;
- `conflicting_evidence`: energy meets the boundary but completed support is too thin;
- `not_triggered`: admitted energy is below the boundary;
- `insufficient_evidence`: required evidence is absent, partial, invalid, mixed-unit,
  contract-incompatible, incompletely covered, non-finite, or denominator-inconsistent.

At exactly `1.50 J/task`, R8 triggers if at least 10 completed tasks support the metric.

## CLI Usage

Evaluate a bundle or saved EvidencePack:

```bash
uv run traffictwin diagnose energy path/to/bundle \
  --minimum-energy-per-completed-task-j 1.50 \
  --minimum-completed-tasks 10 \
  --format json
```

Write the typed result:

```bash
uv run traffictwin diagnose energy path/to/bundle \
  --output r8-energy.json
```

Trace an R8 result to its metric and accepted source rows:

```bash
uv run traffictwin provenance rule path/to/bundle R8 --format json
```

Provenance identifies calculation lineage and eligible contributors. It does not attribute causal
energy use to a task, policy, vehicle, or RSU.

## Python Usage

```python
from traffictwin.rules.config import R8Config, RuleSetConfig
from traffictwin.rules.engine import evaluate_rules

config = RuleSetConfig(
    r8=R8Config(
        minimum_energy_per_completed_task_j=1.50,
        minimum_completed_tasks=10,
    )
)
report = evaluate_rules(evidence_pack, config)
r8 = next(result for result in report.results if result.rule_id == "R8")
```

For an R8-only evaluation, disable R0–R7 or use the CLI/UI service, which constructs the isolated
configuration and calls the same rule engine.

## UI Usage

Open **Energy Evidence** after selecting a compatible bundle. The page shows:

- observed-task energy, completed-task energy, and energy-delay product with availability;
- contract fingerprint, eligible/population counts, and coverage;
- threshold and completed-support controls;
- R8 status, observed value, categorical confidence, findings, alternatives, and limitations;
- deterministic JSON download.

Changing a UI control evaluates an explicit in-memory configuration. It does not overwrite or
persist the ruleset default.

## Appropriate Use Cases

R8 can support:

- deterministic synthetic fault-case evaluation;
- checking whether a compatible imported run crosses a predeclared energy-cost boundary;
- identifying high values that need matched common-seed comparison;
- demonstrating explicit failure for missing, partial, or mixed-unit energy;
- tracing admitted energy calculations to accepted source records.

R8 cannot establish:

- real hardware efficiency or battery impact;
- statistical abnormality relative to a population;
- a causal effect of policy, offloading, task class, RSU, or incident;
- compatibility with TOS/SUMO energy summaries that do not satisfy the canonical contract;
- an optimal or recommended threshold.

Task-class mix, workload, execution decisions, latency/resource constraints, finite variation, and
the synthetic energy model remain explicit alternative explanations. Matched repeated experiments
and future statistical capabilities are required for stronger comparisons.

## Versioning and References

R8 v1.0 is enabled in ruleset `1.3`. See:

- [ADR-024](decisions/ADR-024-contract-gated-r8-energy-anomaly.md);
- [task-energy metric decision](decisions/ADR-018-contract-gated-task-energy-metrics.md);
- [diagnostic rules](diagnostic_rules.md);
- [generated R8 contract](reference/generated/r8_energy_diagnosis_contract.json);
- [limitations](limitations_and_future_work.md).

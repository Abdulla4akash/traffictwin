# R7 Operational Outcome-Disparity Diagnosis

TrafficTwin `DIA-02` identifies a supported difference in completion outcomes across exactly one
researcher-selected operational grouping. R7 v1.0 is the reference core rule compiled through the
`DIA-04` declarative grammar and evaluated over the ordinary `EvidencePack` boundary.

R7 is not protected-attribute fairness analysis. It does not prove discrimination, statistical
significance, geography, siting or routing cause, or acceptable overall performance.

## Selectable Dimensions

| Dimension | Evidence metric | Required contract |
|---|---|---|
| `vehicle_tier_completion` | `fairness.vehicle_tier.completion_rate.max_gap` | operational-fairness policy v1.0, exact stable vehicle tiers, full task coverage |
| `target_rsu_completion` | `spatial.rsu.task.completion_rate_by_target` | exact task execution-target RSU contract v1.0, full join coverage |

R7 never merges these dimensions or chooses whichever produces a trigger. The selected metric
must be `available`, use unit `ratio`, carry the exact expected policy/contract fingerprint, have
at least two groups, and meet the configured support per group. Missing, partial, null, thin, or
incompatible evidence produces `insufficient_evidence`, not a zero gap.

## Default Configuration

| Field | Default | Meaning |
|---|---:|---|
| `dimension` | `vehicle_tier_completion` | One explicit operational grouping. |
| `minimum_outcome_gap` | `0.20` | Absolute completion-rate range that triggers R7. |
| `minimum_group_support` | `2` | Minimum admitted observations in every group. |

The `0.20` value is a provisional synthetic-development threshold. It is not literature-backed,
externally calibrated, or an ethical fairness standard. A substantive study should justify and
predeclare its threshold and support requirement.

At the threshold boundary, R7 triggers (`gap >= threshold`). A complete lower gap produces
`not_triggered`. A trigger includes alternative explanations and a conditional replication step.
The result carries the selected dimension, threshold, support requirement, and complete
declarative-definition fingerprint.

## CLI Use

Evaluate the vehicle-tier dimension for a bundle:

```bash
uv run traffictwin diagnose fairness \
  path/to/bundle \
  --dimension vehicle_tier_completion \
  --minimum-outcome-gap 0.20 \
  --minimum-group-support 2 \
  --format json \
  --output /tmp/r7-tier.json
```

Evaluate exact target-RSU completion:

```bash
uv run traffictwin diagnose fairness \
  path/to/bundle \
  --dimension target_rsu_completion \
  --minimum-outcome-gap 0.20 \
  --minimum-group-support 2 \
  --format text
```

The input may also be a saved `EvidencePack` JSON file. Use the general report command when all
enabled rules are required:

```bash
uv run traffictwin diagnose report path/to/bundle --format json
```

The default ruleset is schema `1.0`, version `1.3`, and includes R0–R8.

## UI Use

Open **Fairness Evidence** after choosing an accepted bundle. The page shows the existing grouped
metrics, then an **R7 Operational Outcome Disparity** section. Select the dimension, gap threshold,
and minimum support. Controls call the typed service; the page does not calculate the gap or rule
status. It renders:

- R7 status and categorical confidence;
- the cited finding and exact missing evidence;
- alternative explanations and limitations;
- the definition/configuration metadata;
- a downloadable `RuleResult` JSON artifact.

## Python API

```python
from traffictwin.rules.config import R7Config, RuleSetConfig
from traffictwin.rules.engine import evaluate_rules

config = RuleSetConfig(
    r7=R7Config(
        dimension="vehicle_tier_completion",
        minimum_outcome_gap=0.20,
        minimum_group_support=2,
    )
)
report = evaluate_rules(evidence_pack, config)
r7 = next(result for result in report.results if result.rule_id == "R7")
print(r7.status)
```

For a standalone R7-only workflow, disable R0–R6 in `RuleSetConfig` or use the CLI/UI service.
The two complete built-in definitions and their fingerprints are generated in
[`reference/generated/r7_rule_definitions.json`](reference/generated/r7_rule_definitions.json).

## Use Cases

R7 can support:

1. a predeclared synthetic robustness check asking whether policy outcomes differ by supplied
   compute tier;
2. an imported-run audit asking whether exact observed execution targets have different
   completion outcomes;
3. a common-seed follow-up study that tests whether an operational disparity remains stable across
   compatible repetitions;
4. an evidence-readiness check that shows why a tier/target comparison is currently unavailable.

R7 cannot support protected-class fairness claims, causal RSU attribution, post-hoc threshold
tuning presented as confirmation, or source mappings without the exact group contract.

## Provenance And External Sources

`traffictwin provenance rule path/to/bundle R7 --format json` traces the R7 result to its finding,
metric definition/result, canonical rows, source rows, rule configuration, and declarative
definition fingerprint. This establishes lineage, not causality.

Generic and labelled synthetic bundles can expose R7 only when they satisfy the operational
fairness or exact-target contracts. Current SUMO and TOS source contracts expose neither selected
group family, so `fairness_disparity_diagnosis` remains `false` for those adapters and R7 returns
explicit insufficiency if the general rule engine is run over their partial evidence.

The governing decision is
[ADR-023](decisions/ADR-023-declarative-rule-grammar-and-r7-fairness.md).

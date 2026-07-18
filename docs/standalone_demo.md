# Standalone Demo

TrafficTwin can now be demonstrated without Randy's VEC environment, SUMO, live Manchester data,
cloud services, or external APIs. The standalone demo uses deterministic synthetic run bundles that
conform to the same generic run-bundle contract used by imported historical data.

## What Is Synthetic

The standalone generator creates small CSV/YAML bundles for software demonstration. It approximates
relationships such as higher demand increasing queues, reduced capacity increasing delays, low
offload use affecting T1 tasks on low-tier vehicles, and congestion increasing trip duration.

It does not model real traffic physics, radio propagation, SUMO dynamics, Manchester sensor feeds,
or Randy's VEC environment.

## Initialise

```bash
traffictwin demo initialise .demo
traffictwin demo status .demo
```

This creates:

```text
.demo/
├── registry.sqlite
├── seeds/
├── bundles/
├── reports/
├── exports/
├── logs/
└── workspace.yaml
```

The command validates every generated bundle, imports accepted bundles into SQLite, computes metrics,
builds EvidencePacks, evaluates diagnostics, prepares comparison JSON, prepares provenance traces,
and writes deterministic report files.

Use `--force` only when you intentionally want to replace an existing workspace.

## Launch

```bash
traffictwin demo launch .demo
```

For a non-blocking command preview:

```bash
traffictwin demo launch .demo --dry-run
```

The launcher sets:

- `TRAFFICTWIN_WORKSPACE_PATH=.demo`
- `TRAFFICTWIN_REGISTRY_PATH=.demo/registry.sqlite`
- `TRAFFICTWIN_FIXTURE_PATH=.demo/bundles`

and starts `streamlit run src/traffictwin/ui/app.py`.

## Scenarios

| Scenario | Expected software behavior |
|---|---|
| `baseline` | High completion, moderate utilisation, no strong R1/R2 hypothesis. |
| `stressed_demand` | Lower completion, longer queues, longer trips. |
| `under_offloading` | R1 under-offloading candidate. |
| `infrastructure_bottleneck` | R2 infrastructure-bottleneck candidate. |
| `mixed_fault` | R1 and R2 may both be plausible. |
| `partial_evidence` | Accepted with evidence limitations; R0 and insufficient rules. |
| `trivial_multi_algorithm` | Multiple low-pressure synthetic policy profiles for R3 evidence. |

## CLI Demonstration

```bash
traffictwin bundle validate .demo/bundles/baseline
traffictwin metrics compute .demo/bundles/baseline
traffictwin diagnose bundle .demo/bundles/under_offloading
traffictwin diagnose evidence .demo/exports/trivial_multi_algorithm_evidence.json
traffictwin compare .demo/bundles/baseline .demo/bundles/stressed_demand
traffictwin provenance metric .demo/bundles/baseline task.completion.rate
traffictwin report full .demo/bundles/stressed_demand \
  --comparison-baseline .demo/bundles/baseline \
  --output .demo/reports/stressed_full.html
```

## UI Demonstration

1. Home: confirm the standalone demo status and capability manifest.
2. Bundle Import & Validation: validate `baseline` and `stressed_demand`.
3. Run Overview: inspect task completion and latency.
4. Operations View: confirm `HISTORICAL REPLAY`.
5. Infrastructure & Congestion: inspect queue and utilisation.
6. What-if Compare: compare baseline and stressed demand.
7. Journey-Time Lens: inspect synthetic trip durations.
8. Evidence & Diagnostic Hypotheses: inspect R1, R2, and R3 scenarios.
9. Provenance Explorer: trace `task.completion.rate` or rule `R2`.

## Reset

```bash
traffictwin demo reset .demo --yes
```

Reset only operates on a marked TrafficTwin standalone workspace. It will not delete arbitrary
unmarked directories.

## Limitations

- Synthetic outputs are software fixtures, not external validation.
- The generator does not impersonate real algorithms.
- Diagnostic hypotheses remain candidate explanations.
- No direct simulator launch is enabled.

Related documents:

- [Synthetic data model](synthetic_data_model.md)
- [Report export](report_export.md)
- [Demo checklist](demo_checklist.md)
- [Limitations and future work](limitations_and_future_work.md)

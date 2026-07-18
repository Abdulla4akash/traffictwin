# Demo Script

This supervisor-ready demonstration uses repository synthetic fixtures only. It does not require Randy, SUMO, external services, or live data.

## Pre-Demo Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
.venv/bin/python -m pytest
traffictwin demo initialise .demo
```

Launch:

```bash
traffictwin demo launch .demo
```

## Fixture Paths

- Baseline: `.demo/bundles/baseline`
- Stressed demand: `.demo/bundles/stressed_demand`
- Under-offloading: `.demo/bundles/under_offloading`
- Infrastructure bottleneck: `.demo/bundles/infrastructure_bottleneck`
- Mixed fault: `.demo/bundles/mixed_fault`
- Partial evidence: `.demo/bundles/partial_evidence`
- R3 experiment evidence: `.demo/exports/trivial_multi_algorithm_evidence.json`
- Legacy repository baseline: `tests/fixtures/bundles/baseline_valid`
- Legacy repository variation: `tests/fixtures/bundles/variation_valid`
- Invalid manifest: `tests/fixtures/bundles/invalid_manifest`
- Diagnostic cases: `tests/fixtures/diagnostics/cases.json`

## Script

1. Open Home / Project Status.
   - Say: "This is the standalone prototype. It is synthetic/import-first only."
   - Show the Standalone Demo section.
   - Show direct launch is unsupported and unknown capabilities stay unknown.

2. Open Scenario Studio.
   - Show seed fields and YAML preview.
   - Explain that every scenario serialises to YAML before execution/import.
   - Point out the disabled Run action.

3. Open Bundle Import & Validation.
   - Validate `.demo/bundles/baseline`.
   - Show status accepted, declared files, record counts, and evidence categories.

4. Validate `.demo/bundles/stressed_demand`.
   - Show it uses the same experiment and random seed but different seed parameters.

5. Open Run Overview.
   - Show task completion, incomplete rate, latency, offload rate, and unavailable optional metrics.
   - Explain unavailable is not zero.

6. Open Operations View.
   - Show the `HISTORICAL REPLAY` badge.
   - Move through timestamps.
   - Explain there is no wall-clock live source.

7. Open Infrastructure & Congestion.
   - Show per-RSU queue/utilisation.
   - Point out the `0.90` saturation threshold is a configurable demo threshold, not a validated research threshold.

8. Open What-if Compare.
   - Select baseline and variation.
   - Show changed seed parameters.
   - Show task, infrastructure, traffic, and trip deltas.
   - Use neutral wording: increased/decreased/unchanged.

9. Open Journey-Time Lens.
   - Show synthetic trip duration metrics.
   - Say: "These are imported synthetic trip durations, not real Manchester predictions."

10. Open Evidence & Diagnostic Hypotheses.
    - Show EvidencePack ID/fingerprint.
    - Show R0-R3 status.
    - Explain hypotheses are candidate explanations, not proven causes.
    - Use `.demo/bundles/under_offloading` to show R1.
    - Use `.demo/bundles/infrastructure_bottleneck` to show R2.
    - Use `.demo/exports/trivial_multi_algorithm_evidence.json` via CLI to show R3:

```bash
traffictwin diagnose evidence .demo/exports/trivial_multi_algorithm_evidence.json
```

    - Download DiagnosticReport JSON if needed.

11. Open Provenance Explorer.
    - Select `Metric` and `task.completion.rate`.
    - Show the metric result, metric definition, canonical `tasks` table, `tasks.csv` row samples, manifest, run, seed, environment, and fingerprint.
    - Select `Source file row`, `tasks.csv`, row `2`.
    - Show the raw CSV row and canonical `TaskRecord`.
    - Select `Diagnostic rule` and `R2`.
    - Explain that rule traces separate observed evidence, rule logic, candidate hypotheses, alternatives, and missing evidence.
    - Download trace Markdown if needed.

12. Run fault-injection evaluation in a terminal:

    ```bash
    traffictwin diagnose evaluate tests/fixtures/diagnostics/cases.json
    ```

    Explain that precision/recall here verifies deterministic implementation behavior over labelled synthetic cases only.

## Limitations Statement

Use this exact wording if challenged:

> The current prototype demonstrates the reproducible TrafficTwin workflow using synthetic fixtures and generic imported bundles. It does not yet integrate Randy's environment, SUMO outputs, Manchester sensors, live feeds, direct launch, LLM rendering, or XAI. Phase 6A documented the missing artifacts required before real adapters can be built.

## Fallback If Streamlit Fails

Run the CLI demonstration:

```bash
traffictwin bundle validate tests/fixtures/bundles/baseline_valid
traffictwin metrics compute tests/fixtures/bundles/baseline_valid
traffictwin compare tests/fixtures/bundles/baseline_valid tests/fixtures/bundles/variation_valid
traffictwin diagnose bundle tests/fixtures/bundles/baseline_valid
traffictwin provenance metric tests/fixtures/bundles/baseline_valid task.completion.rate
traffictwin provenance source tests/fixtures/bundles/baseline_valid tasks.csv 2
```

## Cleanup

Remove temporary exported JSON or registry files created during the demo:

```bash
rm -f evidence-baseline.json diagnostic-baseline.json
rm -f data/registry/demo.sqlite
```

Do not delete repository fixtures.

Related documents:

- [Demo checklist](demo_checklist.md)
- [User guide](user_guide.md)
- [Viva traceability demo](viva_traceability_demo.md)
- [Screenshot checklist](assets/screenshots/README.md)

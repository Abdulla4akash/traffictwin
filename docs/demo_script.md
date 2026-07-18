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

2. Open Scenario Builder.
   - Duplicate the baseline synthetic preset.
   - Show documented generator controls for traffic, tasks, infrastructure, policy profile, and
     evidence files.
   - Show the expected bundle/run IDs and configuration YAML.
   - Explain that generation writes a standard bundle and then uses the normal validator.

3. Open Bundle Import & Validation.
   - Validate `.demo/bundles/baseline`.
   - Show status accepted, declared files, record counts, and evidence categories.

4. Validate `.demo/bundles/stressed_demand`.
   - Show it uses the same experiment and random seed but different seed parameters.

5. Open Run Overview.
   - Show task completion, incomplete rate, latency, offload rate, and unavailable optional metrics.
   - Explain unavailable is not zero.

6. Open Replay.
   - Show the `HISTORICAL REPLAY` badge.
   - Use play, pause, restart, speed presets, timestamp jump, scrubber, and step controls.
   - Show filters for vehicle, RSU, task class, and incident where evidence exists.
   - Explain there is no wall-clock live source.

7. Open Infrastructure & Congestion.
   - Show per-RSU queue/utilisation.
   - Point out the `0.90` saturation threshold is a configurable demo threshold, not a validated research threshold.

8. Open Comparison.
   - Select baseline and variation.
   - Show changed seed parameters.
   - Show task, infrastructure, traffic, and trip deltas.
   - Use neutral wording: increased/decreased/unchanged.

9. Open Journey-Time Lens.
   - Show synthetic trip duration metrics.
   - Say: "These are imported synthetic trip durations, not real Manchester predictions."

10. Open Diagnostics & Evidence.
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

11. Open Experiment Manager.
    - Show experiments, runs, policies, bundle fingerprints, comparisons, reports, metrics, and
      evidence counts.
    - Explain that this page organises existing artifacts only.

12. Open Reports.
    - Show report inventory and download buttons.
    - Explain reports regenerate only when explicitly requested.

13. Open Search.
    - Search for `completion`, `R1`, or `baseline`.
    - Explain that search is local metadata search.

14. Open Provenance Explorer.
    - Select `Metric` and `task.completion.rate`.
    - Show the metric result, metric definition, canonical `tasks` table, `tasks.csv` row samples, manifest, run, seed, environment, and fingerprint.
    - Select `Source file row`, `tasks.csv`, row `2`.
    - Show the raw CSV row and canonical `TaskRecord`.
    - Select `Diagnostic rule` and `R2`.
    - Explain that rule traces separate observed evidence, rule logic, candidate hypotheses, alternatives, and missing evidence.
    - Download trace Markdown if needed.

15. Open Settings and About.
    - Show session-scoped preferences.
    - Show version, schema, metric, diagnostic, provenance, generator, Python, commit, and licence
      metadata.

16. Run fault-injection evaluation in a terminal:

    ```bash
    traffictwin diagnose evaluate tests/fixtures/diagnostics/cases.json
    ```

    Explain that precision/recall here verifies deterministic implementation behavior over labelled synthetic cases only.

## Limitations Statement

Use this exact wording if challenged:

> The current prototype demonstrates the reproducible TrafficTwin workflow using synthetic
> fixtures and generic imported bundles. It also has optional read-only TOS result inspection, but
> it does not execute Randy's environment, parse raw SUMO XML, use Manchester sensors/live feeds,
> or provide direct launch, LLM rendering, or XAI. The source audit documents the remaining
> canonical and execution blockers.

## Optional TOS Results Workbench Demo

Use this only when the separately supplied package is available locally and the audience is
authorised to see source-derived aggregate values.

1. Open **TOS Data Import**, inspect the package, and show the source contract and disabled launch.
2. Open **TOS Results**, select deadline success, and show the campaign/cell matrix.
3. Compare `baseline` with one variation; point out exact fleet-seed pairing and neutral deltas.
4. Show in-domain, held-out, and unknown labels without interpreting score as domain evidence.
5. Open **TOS Mobility & RSU Replay**, play the logical timeline, then load one deliberate spatial
   frame.
6. Show RSU concurrency pressure and state explicitly that it is not CPU utilisation.
7. Open **TOS Training & Audit**, show one training curve, audit blockers, and integration gates.
8. Prepare the private supervisor ZIP and point out its manifest and checksum file.
9. State that the TOS atlas is local and permission-gated; do not deploy it during the demo.

See [integration/tos_results_workbench.md](integration/tos_results_workbench.md).

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

# Demo Script

This supervisor-ready demonstration uses repository synthetic fixtures only. It does not require Randy, SUMO, external services, or live data.

## Pre-Demo Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
.venv/bin/python -m pytest
```

Launch:

```bash
streamlit run src/traffictwin/ui/app.py
```

## Fixture Paths

- Baseline: `tests/fixtures/bundles/baseline_valid`
- Variation: `tests/fixtures/bundles/variation_valid`
- Partial evidence: `tests/fixtures/bundles/partial_valid`
- Invalid manifest: `tests/fixtures/bundles/invalid_manifest`
- Diagnostic cases: `tests/fixtures/diagnostics/cases.json`

## Script

1. Open Home / Project Status.
   - Say: "This is the Phase 1-6A prototype. It is synthetic/import-first only."
   - Show direct launch is unsupported and unknown capabilities stay unknown.

2. Open Scenario Studio.
   - Show seed fields and YAML preview.
   - Explain that every scenario serialises to YAML before execution/import.
   - Point out the disabled Run action.

3. Open Bundle Import & Validation.
   - Validate `tests/fixtures/bundles/baseline_valid`.
   - Show status accepted, declared files, record counts, and evidence categories.

4. Validate `tests/fixtures/bundles/variation_valid`.
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
    - Download DiagnosticReport JSON if needed.

11. Run fault-injection evaluation in a terminal:

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
- [Screenshot checklist](assets/screenshots/README.md)

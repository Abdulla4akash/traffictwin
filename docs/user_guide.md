# User Guide

TrafficTwin Phase 4 is an import-first Streamlit prototype. It supports synthetic fixtures and imported historical bundles only.

## Launch

```bash
streamlit run src/traffictwin/ui/app.py
```

## Supported Workflow

1. Open Home / Project Status.
2. Confirm the capability manifest. Direct launch is unsupported.
3. Open Scenario Studio.
4. Draft or load a seed and export YAML.
5. Open Bundle Import & Validation.
6. Validate `tests/fixtures/bundles/baseline_valid`.
7. Import it into a registry if desired.
8. Repeat for `tests/fixtures/bundles/variation_valid`.
9. Open Run Overview for the selected bundle.
10. Open Operations View to inspect historical replay timelines.
11. Open Infrastructure & Congestion.
12. Open What-if Compare and compare baseline versus variation.
13. Open Journey-Time Lens for imported trip duration.
14. Open Evidence & Diagnostic Readiness and download the EvidencePack JSON.

## Limitations

- No direct simulator launch.
- No live or near-live Manchester data.
- No deterministic diagnostic rules R1-R3 yet.
- No LLM prose rendering.
- No SUMO or Randy/VEC adapter.
- Unavailable metrics are shown as unavailable with reason codes, never as zero.

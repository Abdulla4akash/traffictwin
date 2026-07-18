# Demo Checklist

Use this checklist immediately before a supervisor or viva demonstration.

## Pre-Demo

- [ ] Install dependencies with `python -m pip install -e ".[dev]"`.
- [ ] Run `.venv/bin/python -m pytest`.
- [ ] Confirm `git status --short` has no unintended changes.
- [ ] Confirm fixture paths exist:
  - [ ] `tests/fixtures/bundles/baseline_valid`
  - [ ] `tests/fixtures/bundles/variation_valid`
  - [ ] `tests/fixtures/bundles/partial_valid`
  - [ ] `tests/fixtures/diagnostics/cases.json`
- [ ] Or initialise a standalone workspace:

```bash
traffictwin demo initialise .demo
traffictwin demo status .demo
```

- [ ] Start Streamlit:

```bash
traffictwin demo launch .demo
```

## UI Flow

- [ ] Home shows prototype notice and capability manifest.
- [ ] Direct launch is unsupported.
- [ ] Scenario Builder renders synthetic generator controls and YAML preview.
- [ ] Scenario Builder validates before generation and does not imply simulator launch.
- [ ] Bundle Import validates baseline.
- [ ] Bundle Import validates variation.
- [ ] Experiment Manager lists experiments, runs, seeds, fingerprints, reports, and comparisons.
- [ ] Run Overview shows task metrics and unavailable optional metrics honestly.
- [ ] Replay shows `HISTORICAL REPLAY`, speed presets, scrubber, timestamp jump, and filters.
- [ ] Infrastructure page shows queue/utilisation and threshold notice.
- [ ] Comparison shows baseline/variation deltas.
- [ ] Journey-Time Lens shows synthetic/imported trip duration, not live prediction.
- [ ] Diagnostics & Evidence shows rule statuses and JSON download.
- [ ] Provenance Explorer traces `task.completion.rate` to metric definition and `tasks.csv` rows.
- [ ] Provenance Explorer source-row preview shows `tasks.csv` row `2` read-only.
- [ ] Provenance Explorer exports JSON or Markdown.
- [ ] Reports lists Markdown/HTML exports and requires explicit regeneration.
- [ ] Search finds local metadata without external services.
- [ ] Settings stores only session-scoped UI preferences.
- [ ] About shows version/schema/build/licence metadata.

## CLI Fallback

```bash
traffictwin capabilities
traffictwin bundle validate tests/fixtures/bundles/baseline_valid
traffictwin metrics compute tests/fixtures/bundles/baseline_valid
traffictwin compare tests/fixtures/bundles/baseline_valid tests/fixtures/bundles/variation_valid
traffictwin diagnose bundle tests/fixtures/bundles/baseline_valid
traffictwin provenance metric tests/fixtures/bundles/baseline_valid task.completion.rate
traffictwin provenance export tests/fixtures/bundles/baseline_valid --root-type metric --root-id task.completion.rate --format markdown
traffictwin report full .demo/bundles/stressed_demand --comparison-baseline .demo/bundles/baseline --output .demo/reports/stressed_full.html
```

## Post-Demo Cleanup

- [ ] Delete temporary registries or JSON exports.
- [ ] Confirm fixtures are unchanged:

```bash
git status --short tests/fixtures examples/seeds
```

## Required Spoken Caveats

- [ ] Synthetic fixtures are not real Manchester data.
- [ ] Historical replay is not live data.
- [ ] Diagnostic hypotheses are not proven root causes.
- [ ] Provenance supports traceability and auditability, not proof of correctness or causality.
- [ ] Read-only TOS inspection is available, but canonical Randy/SUMO integration and launch stay
  blocked by missing producer/checkpoint/writer, identity/outcome/trip evidence, and fixture
  permission.
- [ ] Direct launch is intentionally disabled.

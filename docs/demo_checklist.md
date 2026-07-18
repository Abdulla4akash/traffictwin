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
- [ ] Start Streamlit:

```bash
streamlit run src/traffictwin/ui/app.py
```

## UI Flow

- [ ] Home shows prototype notice and capability manifest.
- [ ] Direct launch is unsupported.
- [ ] Scenario Studio renders seed form and YAML preview.
- [ ] Run action is disabled or clearly unavailable.
- [ ] Bundle Import validates baseline.
- [ ] Bundle Import validates variation.
- [ ] Run Overview shows task metrics and unavailable optional metrics honestly.
- [ ] Operations View shows `HISTORICAL REPLAY`.
- [ ] Infrastructure page shows queue/utilisation and threshold notice.
- [ ] What-if Compare shows baseline/variation deltas.
- [ ] Journey-Time Lens shows synthetic/imported trip duration, not live prediction.
- [ ] Evidence & Diagnostic Hypotheses shows rule statuses and JSON download.

## CLI Fallback

```bash
traffictwin capabilities
traffictwin bundle validate tests/fixtures/bundles/baseline_valid
traffictwin metrics compute tests/fixtures/bundles/baseline_valid
traffictwin compare tests/fixtures/bundles/baseline_valid tests/fixtures/bundles/variation_valid
traffictwin diagnose bundle tests/fixtures/bundles/baseline_valid
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
- [ ] Randy/SUMO integration is blocked until real artifacts are supplied.
- [ ] Direct launch is intentionally disabled.

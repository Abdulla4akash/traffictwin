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
- [ ] Home exposes **Start Guided Demo** without requiring the sidebar.
- [ ] Guided Demo shows eight standalone stages and keeps every stage synthetic/import-first.
- [ ] **Start guided workflow** opens the first real task page without requiring a separate
  per-stage **Open ...** click.
- [ ] The persistent guide keeps task instructions, interpretation boundaries, progress, and
  Previous/Skip/Exit controls visible across page changes.
- [ ] Successful experiment registration and report regeneration advance automatically; review
  stages advance only through **Reviewed — continue**.
- [ ] A skipped stage is visibly recorded as skipped rather than completed, and an exited workflow
  can resume at its current task.
- [ ] Experiment Planner previews the baseline/variation matrix and seed differences.
- [ ] Experiment Planner exports an exhaustive protocol YAML and CSV run sheet.
- [ ] Completed-bundle matching is read-only and distinguishes exact, compatible, mismatch, and
  unmatched metadata.
- [ ] Registering an experiment plan creates no run and enables no simulator launch.
- [ ] Optional imported-TOS track reports the validated package inventory and read-only boundary.
- [ ] Direct launch is unsupported.
- [ ] Scenario Builder renders synthetic generator controls and YAML preview.
- [ ] Scenario Builder validates before generation and does not imply simulator launch.
- [ ] Bundle Import validates baseline.
- [ ] Bundle Import validates variation.
- [ ] Experiment Manager lists experiments, runs, seeds, fingerprints, reports, and comparisons.
- [ ] What-if Compare shows arithmetic completion-rate difference provenance and downloadable
  JSON/CSV with the non-causality statement.
- [ ] What-if Compare shows PRO-03 comparison completeness with all selected typed claims,
  including unavailable claims, and JSON/CSV downloads.
- [ ] Run Overview shows task metrics and unavailable optional metrics honestly.
- [ ] Replay shows `HISTORICAL REPLAY`, speed presets, scrubber, timestamp jump, and filters.
- [ ] Infrastructure page shows queue/utilisation and threshold notice.
- [ ] Comparison shows baseline/variation deltas.
- [ ] Journey-Time Lens shows synthetic/imported trip duration, not live prediction.
- [ ] Diagnostics & Evidence shows rule statuses and JSON download.
- [ ] Provenance Explorer traces `task.completion.rate` to metric definition and `tasks.csv` rows.
- [ ] Provenance Explorer source-row preview shows `tasks.csv` row `2` read-only.
- [ ] Provenance Explorer Graph tab shows bounded retained/omitted counts and a selectable node.
- [ ] Provenance Explorer exports JSON, Markdown, DOT, and GraphML; structure-only removes details.
- [ ] Provenance Explorer shows the PRO-03 run/diagnostics denominator, class counts, exclusions,
  full static claim table, and JSON/CSV downloads.
- [ ] Reports lists Markdown/HTML/PDF exports and requires explicit regeneration.
- [ ] Replay shows the non-geographic corridor plane when vehicle x/y evidence exists.
- [ ] Mock Evaluation Analysis clearly labels its fixture as mock and excludes withdrawn records.
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
traffictwin provenance export tests/fixtures/bundles/baseline_valid --root-type metric --root-id task.completion.rate --format graphml --redaction structure_only --max-nodes 80 --max-edges 160
traffictwin provenance difference-contributors tests/fixtures/bundles/baseline_valid tests/fixtures/bundles/variation_valid task.completion.rate --format json
traffictwin report full .demo/bundles/stressed_demand --comparison-baseline .demo/bundles/baseline --output .demo/reports/stressed_full.html
traffictwin experiment protocol --registry .demo/registry.sqlite --experiment-id EXPERIMENT_ID --format yaml
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
- [ ] Read-only TOS inspection and bounded SUMO tripinfo/summary import are available, but full
  Randy/VEC conversion and launch stay blocked by missing producer/checkpoint/writer,
  identity/outcome/trip evidence, and fixture permission; SUMO FCD also remains unavailable.
- [ ] Direct launch is intentionally disabled.
- [ ] Unknown TOS publication permission remains visible as an integration gate.
- [ ] The supervisor ZIP is labelled private research material.
- [ ] Any public demonstration uses only the standalone synthetic static site.

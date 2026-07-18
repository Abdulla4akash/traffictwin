# Report Export

TrafficTwin report export is deterministic template rendering over existing pipeline artifacts.
It does not use an LLM and does not calculate metrics in the reporting layer.

## Commands

```bash
traffictwin report run .demo/bundles/baseline --output .demo/reports/run.md
traffictwin report compare .demo/bundles/baseline .demo/bundles/stressed_demand \
  --output .demo/reports/comparison.md
traffictwin report diagnostics .demo/bundles/under_offloading \
  --output .demo/reports/diagnostics.md
traffictwin report full .demo/bundles/stressed_demand \
  --comparison-baseline .demo/bundles/baseline \
  --output .demo/reports/full.html
```

Outputs ending in `.html` are standalone HTML. Other outputs are Markdown.

## Contents

Reports include:

- synthetic/imported disclaimer;
- run provenance;
- scenario and environment context;
- validation summary;
- evidence availability;
- task, infrastructure, traffic, and trip metrics where available;
- comparison deltas where requested;
- diagnostic hypotheses and missing evidence;
- provenance summary;
- limitations;
- reproduction commands.

## Security And Path Policy

- Report text is deterministic and template-based.
- HTML output escapes untrusted text.
- Reports do not embed remote assets or JavaScript.
- Absolute local paths are normalised to repository-relative or basename references where practical.
- Large raw CSV tables are not embedded.

## Limitations

- Registry-run report shortcuts are not the primary supported path; bundle paths are supported first.
- Reports do not prove correctness or causality.
- Synthetic reports are demonstration artifacts only.

## TOS Imported-Simulation Exports

The optional TOS workbench exports a deterministic report and aggregate static atlas:

```bash
traffictwin integration tos results-pack "$TOS_DATA_PATH" --output tos-results
```

This output uses source-analysis models rather than canonical Phase 3 metrics. It carries a
publication-permission warning and must not be publicly deployed until source-data permission is
confirmed. See [TOS Results Workbench](integration/tos_results_workbench.md).

Related documents:

- [Standalone demo](standalone_demo.md)
- [Provenance Explorer](provenance_explorer.md)
- [Diagnostic report specification](diagnostic_report_spec.md)
- [Security and privacy](security_and_privacy.md)

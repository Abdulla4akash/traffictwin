# Completed infrastructure sensitivity evidence

Start with [RESULTS.md](RESULTS.md) for the forwarding result, or
[DISSERTATION_SECTION.md](DISSERTATION_SECTION.md) for the combined state-delay
and forwarding write-up. Three figures are supplied in both PNG and SVG.

This directory contains the completed analysis of 0, 1, 2.5, 5 and 10 ms of
fixed forwarding overhead, using the fresh-state pilot archive. Four direct
ten-step evaluator probes qualified the transformation before its application
to the full trace. Ten unit tests passed. No new full-length run was required.

## Evidence and scope

- `manifest.json`: pinned source, inputs, runtime, controls and final method.
- `qualification.json` and `qualification/`: four direct comparisons and logs.
- `analysis_validation.json`: full-data validation and results.
- `forwarding_sensitivity.csv`: overall and per-task-type deadline outcomes.
- `unit_validation.xml`: the ten successful focused checks.
- `SHA256SUMS`: checksums of the deliverables and qualification artifacts.
- `plot_environment.json`: separate plotting runtime, independent of the evaluator.

The original pilot is in the sibling `state-delay-pilot-2026-09-07` directory.
The input archives are referenced in the manifest and retain their original
validation receipts. This package uses one fleet draw. The forwarding model
adds fixed latency; it does not simulate network congestion or transfer-driven
execution arrival times. See the reports for the 104 ambiguous point latencies
whose deadline outcomes remain identifiable.

## Reproduction

The commands below assume this directory is the current working directory and
the manifest's local inputs remain available. Preserve this completed evidence
directory and use a separate copy for replay. The qualification phase requires
that the replay copy have no existing `qualification/` directory; copy the
source scripts and manifest to a new directory to generate new qualification
artifacts. Run qualification before analysis in that directory:

```sh
../vec_env-state-delay/.venv/bin/python forwarding_analysis.py qualify
../vec_env-state-delay/.venv/bin/python forwarding_analysis.py analyze
../vec_env-state-delay/.venv/bin/python -m pytest -q test_forwarding_analysis.py
```

The analysis verifies the recorded evaluator commit, source hashes, input
hashes, runtime versions and pilot archive receipts. Absolute input paths are
part of the manifest. Porting to another machine requires a separately
recorded manifest and qualification.

Figures can be regenerated independently using the saved CSV and the original
pilot's comparison table and mechanism audit:

```sh
.plot-venv/bin/python make_figures.py
```

The plotting environment uses Matplotlib 3.10.8 and NumPy 1.26.4. It is
separate from the validated evaluator environment. Report and figure files
were visually reviewed after generation.

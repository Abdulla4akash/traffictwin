# TrafficTwin empirical extension — 8 September 2026

Complete editable [manuscript](TrafficTwin_Dissertation.md), new
[PDF](TrafficTwin_Dissertation.pdf), [change/evidence report](REVISION_REPORT.md),
[claim bindings](CLAIM_SOURCE_MAP.md), [author inputs](AUTHOR_INPUTS.md),
[seven-minute storyboard](VIDEO_STORYBOARD.md), and [current validation](VALIDATION.json).
The PDF is an author-review artifact, not an approved submission. No new full
campaign, actor inference, historical recovery, upload, push or merge occurred.

## Relocatable verification

From any working directory, set `PACKAGE` to this directory in a complete
repository checkout and `DOC_PYTHON` to Python with NumPy/SciPy (the supplied
PDF requirements additionally provide document tooling). Explicit variables
below are placeholders to fill, not paths assumed to exist:

```sh
PACKAGE=/absolute/path/to/checkout/docs/dissertation/empirical_extension_2026-09-08
DOC_PYTHON=/absolute/path/to/analysis/python
"$DOC_PYTHON" "$PACKAGE/analysis/verify.py" --output /absolute/new/verification-output
```

Default checks authenticate supplied compact/source bindings, regenerate
central table inputs and type CSVs, recalculate timing summaries from 1,600
saved durations, and inspect the disabled campaign seal. It does not import
JAX, repeat a benchmark, run an evaluator, rejoin tasks or validate missing
historical arrays. Missing/mismatched package files fail explicitly.

Optional `--raw-root /explicit/september/root` reads only the eight specified
primary-morning ingress/per-task files, hashes each before aggregation and
writes new type results under the output directory. These source arrays are
not copied into this package. The prior authenticated audit/joins remain in
[gap closure](../gap_closure_2026-09-08/verification/README.md). A complete
checkout supplies compact checks; markers need separately granted September
raw access for raw reaggregation. Private GitHub links are not automatic
examiner access. Local presence and checksums are not off-machine backup.
Original E0/E1/E2 outputs remain unavailable, deletion reported by the author,
with no known backup. Other historical availability is not inferred.

## Comparator and measured benchmark

Use the existing scientific Python (JAX/JAXlib0.4.30, NumPy1.26.4, CPU,
x64 false); do not install document dependencies into it.

```sh
JAX_PLATFORMS=cpu JAX_ENABLE_X64=false "$SCI_PYTHON" "$PACKAGE/experimental/test_comparator.py"
JAX_PLATFORMS=cpu JAX_ENABLE_X64=false "$SCI_PYTHON" "$PACKAGE/experimental/test_compatibility.py"
```

The [benchmark declaration](analysis/PROTOCOL.md), [implementation](analysis/benchmark.py),
[results](analysis/results/BENCHMARK.json) and [durations](analysis/results/BENCHMARK_TIMES.csv)
are complete. The original measurement is not rerun by verification. If a
separately desired local timing reproduction is made, write it to a new folder:

```sh
JAX_PLATFORMS=cpu JAX_ENABLE_X64=false "$SCI_PYTHON" "$PACKAGE/analysis/benchmark.py" --output /absolute/new/timing-output
```

This is scheduler-only timing. Busy entry queues are imposed stress states;
exact queue clearing excludes them as reachable entries from the studied empty
initialisation. Compiler buffer figures are estimates, not peak RSS.

## Sealed, unrun confirmation

Read [protocol](confirmation/PROTOCOL.md) and [seal](confirmation/SEALED.json).
Eight joint seed pairs100/200 through107/207, four arms, 32 maximum attempts.
Three primary paired contrasts; other comparisons descriptive. The current
switch is false and `--execute` refuses to launch. The old dry-run seal is
retained only as a pre-review declaration; final analysis requires passed,
bound block controls as well as cell accounting. No new study result exists.

```sh
"$DOC_PYTHON" "$PACKAGE/confirmation/runner.py" --dry-run \
  --python "$SCI_PYTHON" --runtime-root /explicit/unchanged/runtime-checkout \
  --trace /explicit/canonical/morning-trace.npz --actor /explicit/frozen-actor.npz \
  --output-root /absolute/new/confirmation-output --receipt /absolute/new/dry-run.json
"$DOC_PYTHON" "$PACKAGE/confirmation/test_runner.py"
```

The runner queries versions and hashes explicit available trace/actor/source
inputs; it performs no evaluator dry-prefix. Only a later explicit
execution authorisation and reseal could enable `--execute` with the same
arguments. After all 32 cells and eight block controls pass, the predeclared
analysis command would be:

```sh
"$DOC_PYTHON" "$PACKAGE/confirmation/analyse.py" --root /absolute/confirmation-output --output /absolute/new/confirmation-analysis.json
```

Currently that command must fail for absence of completed block records.
A future run is a separate study, not recovery of historical outputs.

## Documents and review

`build_pdf.py` uses a separate ReportLab document environment and installed
Times New Roman/Arial fonts; it imports no scientific runtime. The current
[visual record](VISUAL_REVIEW.json) identifies every inspected rendered page
and the new PDF hash. The [separate AI critique](REVIEW.md) is distinct from
self-validation and pending human approval. A storyboard is not a recorded
video. No new DOCX is claimed or included.

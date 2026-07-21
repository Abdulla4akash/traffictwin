# Time-Windowed Metrics

TrafficTwin can compute the existing deterministic run metrics over aligned fixed windows. This
feature is useful for locating when degradation appears, inspecting gaps, and preparing typed
temporal evidence without changing any whole-run metric.

## Contract At A Glance

| Item | Implemented meaning |
|---|---|
| Boundary | half-open `[start, end)`; an exact end-boundary record enters the next window |
| Alignment | `origin + k * width`; origin defaults to `0` seconds |
| Inferred range | smallest complete aligned envelope containing all canonical anchors |
| Explicit range | `[start-s, end-s)`; intersecting edge windows are clipped |
| Partial edges | `include` or `exclude`; excluded edges remain visible |
| Empty windows | emitted with ordinary metric unavailability, never filled with zero |
| Coverage | requested-range overlap divided by grid width; not sensor completeness |
| Request bound | 10,000 windows by default |
| Applicable metrics | all 60 current core task, infrastructure, traffic, trip, energy, fairness, and contracted spatial/per-RSU metrics, plus explicitly registered plugins that declare a valid canonical anchor |
| Excluded definitions | three pairwise comparison definitions; these require two runs |

Record anchors are tasks by arrival, trips by departure, and infrastructure, vehicles, traffic,
and incidents by their timestamp. Tasks and trips therefore describe start cohorts. See
[ADR-016](decisions/ADR-016-fixed-window-metric-semantics.md) for the rationale and edge cases.

## CLI Usage

Compute 60-second windows over the inferred aligned source envelope:

```bash
traffictwin metrics windows tests/fixtures/bundles/baseline_valid \
  --width-s 60 --format text
```

Export the complete machine-readable artifact:

```bash
mkdir -p build
traffictwin metrics windows tests/fixtures/bundles/baseline_valid \
  --width-s 60 --format json --output build/baseline-windows.json
```

Use a five-second grid, origin zero, and an explicit range. The first and last windows are clipped
if the range is not aligned:

```bash
traffictwin metrics windows tests/fixtures/bundles/baseline_valid \
  --width-s 5 --origin-s 0 --start-s 2 --end-s 18 \
  --partial-windows include --format json
```

To retain the edge-window records and bounds but not calculate their metrics, use
`--partial-windows exclude`. `--start-s` and `--end-s` must be supplied together. Use
`--max-windows` to lower the admission bound for automation.

Trace one metric in one zero-based window ordinal:

```bash
traffictwin provenance window-metric tests/fixtures/bundles/baseline_valid \
  task.generated.count --width-s 5 --start-s 0 --end-s 10 \
  --window-ordinal 0 --format json
```

Export every accepted candidate row and its ordinary metric-eligibility decision:

```bash
traffictwin provenance window-contributors tests/fixtures/bundles/baseline_valid \
  task.generated.count --width-s 5 --start-s 0 --end-s 10 \
  --window-ordinal 0 --output build/window-0-contributors.json
```

An excluded partial window has no metric collection, so provenance requests for it fail visibly.

## Streamlit Usage

Start the app:

```bash
streamlit run src/traffictwin/ui/app.py
```

Open **Temporal Metrics**, select a validated bundle, set window width/alignment and optional
explicit range, then choose **Compute Windowed Metrics**. The page shows:

- included, excluded-partial, and empty-window counts;
- the resolved range and range source;
- a selectable metric table with grid/effective bounds, coverage, source count, status, value,
  and reason codes;
- a line chart only for available scalar numeric values;
- the full anchor/coverage contract and a JSON download.

The page does not calculate metrics. It renders `WindowedMetricSeries` returned by the library UI
service. The same page can project one eligible scalar metric into temporal evidence and evaluate
R6 with an optional declared event and explicit provisional thresholds.

## Python Usage

```python
from pathlib import Path

from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics import (
    PartialWindowPolicy,
    WindowedMetricConfig,
    compute_windowed_metrics_for_bundle,
)

bundle = validate_bundle(Path("tests/fixtures/bundles/baseline_valid"))
config = WindowedMetricConfig(
    width_s=60,
    alignment_origin_s=0,
    partial_window_policy=PartialWindowPolicy.INCLUDE,
)
series = compute_windowed_metrics_for_bundle(bundle, config)

first = series.slice_at(0)
if first.metrics is not None:
    completion = first.metrics.by_key()["task.completion.rate"]
    print(completion.status, completion.value)
```

For lower-level use, `compute_windowed_metrics` accepts `CanonicalTables`, `RunMetricContext`,
`EvidenceAvailability`, and the same configuration. `canonical_tables_for_window` exposes the
exact table filter. `build_window_metric_trace` and
`build_window_metric_contribution_report` provide read-only lineage.

## Reading The Artifact

`WindowedMetricSeries` contains the run/fingerprint, metric and anchor-policy versions, input
configuration, resolved range, range source, table anchors, applicable keys, warnings, and slices.
Each slice contains:

- a stable zero-based ordinal and grid index;
- grid and effective bounds;
- requested-range coverage and partial flag;
- `included` or `excluded_partial` disposition;
- source record counts for all six canonical tables;
- an ordinary `MetricCollection` scoped to `time_window`, or `null` when excluded.

An included empty slice is evidence of no admitted canonical rows in that interval. Its metrics
remain unavailable because that does not prove the real system generated zero work.

## Interpretation Limits

- Do not add means, percentiles, ratios, distinct counts, grouped objects, or Jain indices across
  windows.
- Saturation episodes/durations and traffic coverage are clipped to each window and do not
  reconstruct the whole-run result.
- Coverage is geometric overlap with the requested range, not observation completeness.
- Task outcome metrics are grouped by arrival cohort; trip outcomes are grouped by departure
  cohort. They are not completion-event series.
- Windowing alone does not make a diagnosis. `DIA-01` explicitly projects a selected series into
  typed temporal EvidencePack evidence and evaluates deterministic R6; it does not prove incident
  causality or statistical drift.
- The generic bundle adapter advertises this capability. The public SUMO and Randy/TOS result
  adapters do not yet expose the same canonical time-window contract and therefore report it
  unavailable.

For the complete R6 method, CLI, UI, recovery states, fingerprints, and limits, see
[Temporal degradation and recovery diagnosis](temporal_diagnosis.md).

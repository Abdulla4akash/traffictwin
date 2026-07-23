# DfT historical survey view (`MAN-02` / `MAN-08` candidate)

This module turns an accepted `DftRawCountParseReport` into a bounded, deterministic,
source-specific historical view. It is the filter boundary needed before a thin Manchester
Operations chart can display DfT survey-hour evidence. Its pure functions accept a parser report;
its convenience functions reopen a verified accepted local snapshot through the shared DfT
acquisition boundary. Neither path performs network access, canonical projection, aggregation, or
SUMO conversion.

`MAN-02` and `MAN-08` remain `planned`. This candidate library and its synthetic tests are software
evidence, not real-source Gate-B acceptance.

## Why this is a survey view, not a continuous time series

DfT provides a `count_date` and an `hour` label, but the accepted source audit does not establish
the timezone of that hour. TrafficTwin therefore retains:

- `count_date` exactly as a source date;
- `hour` exactly as a source local-clock label;
- `time_basis="local_clock_hour"`; and
- `observed_at_utc`, `source_timezone`, and `interval_seconds` as structurally unavailable.

Rows from different survey dates are not joined into a continuous series. No date, daylight-saving
rule, retrieval time, or first-row time is used to fabricate a UTC instant.

## Exact filtering contract

`dft_survey_filter_options(report)` derives the count-point IDs, directions, dates, hours, and
vehicle-class fields that actually have at least one value in the supplied report. A
`DftSurveyViewQuery` must:

- bind the exact parser-report fingerprint;
- contain sorted, unique, non-empty count-point, direction, date, and hour selections;
- select one exact audited vehicle-class field; and
- retain the fixed no-aggregation, preserve-null, local-clock policies.

Unknown values fail closed. An individually valid combination that has no matching row returns an
honest empty result; it does not substitute another date or emit a zero. More than 100,000 selected
rows is refused rather than truncated.

For an on-disk workflow,
`dft_survey_filter_options_from_accepted(workspace, acquisition)` and
`build_dft_survey_view_from_accepted(workspace, acquisition, query)` first reproduce the exact
raw-count parser report from an accepted snapshot. They refuse unmarked v0.7 workspaces, mutated
receipts or bytes, and count-point/AADF acquisitions. A caller-supplied in-memory report is never
trusted as a substitute for that accepted-snapshot path.

After a later process discovers a raw-count entry through
`catalogue_accepted_dft_snapshots`, the receipt-free
`dft_survey_filter_options_from_snapshot(workspace, snapshot_id)` and
`build_dft_survey_view_from_snapshot(workspace, snapshot_id, query)` entry
points reopen that exact accepted snapshot. They retain the same strict
dataset, parser, missingness, and local-clock behavior as the acquisition-bound
functions.

## Output and reconciliation

Each `DftSurveyObservation` corresponds to exactly one accepted source row and one selected source
vehicle-class field. It retains source lineage, count point, direction, date, hour, road label,
source coordinates, the selected count, and the source `all_motor_vehicles` value. Null remains
null and is counted separately.

`DftSurveyViewCounts` proves:

```text
source_records = selected_records + records_outside_selection
selected_records = values_present + values_missing
```

Results contain no measured speed, AADF value, aggregation, missing-as-zero value, UTC timestamp,
continuous-series claim, or canonical replay row. The output model protects its internal row and
query fingerprints; `validate_dft_survey_view(report, view)` additionally re-derives a persisted
view from the exact source report.

## Library usage

```python
from datetime import date

from traffictwin.integration.manchester.dft_survey_view import (
    DftSurveyViewQuery,
    build_dft_survey_view_from_snapshot,
    dft_survey_filter_options_from_snapshot,
)

# `workspace` is an isolated v0.7 workspace and `snapshot_id` comes from the
# verified local DfT catalogue.
options = dft_survey_filter_options_from_snapshot(workspace, snapshot_id)
query = DftSurveyViewQuery(
    source_report_fingerprint=options.source_report_fingerprint,
    count_point_ids=(6046,),
    directions=("N",),
    count_dates=(date(2025, 5, 20),),
    hours=(8, 9, 10),
    vehicle_class="all_motor_vehicles",
)
view = build_dft_survey_view_from_snapshot(workspace, snapshot_id, query)
```

The example demonstrates the API shape only; it does not claim that those filter values occur
together in an accepted snapshot. A UI must populate controls from `options`, keep counts and
missingness visible, and render no chart when the exact combination is empty.

## Verification

The 11-test synthetic suite covers option derivation, exact row filtering, null preservation, local-clock
truth, empty combinations, sorted/unique query enforcement, unavailable values, report-fingerprint
binding, rejected-source refusal, internal mutation, source-bound revalidation, exact total-motor
retention, bounded-output refusal, socket-disabled accepted-snapshot replay, and non-raw-dataset
refusal. No test contacts DfT or uses a real source row.

## Residual blockers

- `GA-DFT-1`: the source hour timezone remains undocumented, so UTC/canonical projection is blocked.
- The minimal audited real raw-count probe has passed, but a complete Manchester bulk and browser
  acceptance flow has not.
- No reviewed date/day-type/season policy exists for calibration or SUMO demand construction.
- Manchester Operations now consumes this boundary for one exact snapshot/count-point/date/class
  selection with direction/hour controls, grouped bars, missingness reconciliation, and a source
  row table. Browser accessibility and complete real-source acceptance remain outstanding, so this
  integration does not make either capability implemented.

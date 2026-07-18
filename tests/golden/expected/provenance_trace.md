# TrafficTwin Provenance Trace

## Trace Summary

- Trace ID: `provenance-66674e6f84f5`
- Root: `metric_result:run-baseline-001:task.completion.rate` (metric_result)
- Completeness: `partial`
- Synthetic: `true`
- Source fingerprint: `b778c4c3f27cefda66f452432fdf920ac577345ab5ed889d3b1e77a09cabf75a`

Provenance shows how TrafficTwin derived a result from available records and configured rules. It does not establish real-world causality.

## Run Context

- `run:run-baseline-001` - Run run-baseline-001 [available]

## Root Result

- `metric_result:run-baseline-001:task.completion.rate` - task.completion.rate [available]

## Lineage

- Bundle bundle-baseline-001 contains manifest.yaml (`exact`)
- Bundle bundle-baseline-001 identified by Bundle fingerprint (`exact`)
- tasks record 0 canonicalised from tasks.csv:2 (`exact`)
- tasks record 1 canonicalised from tasks.csv:3 (`exact`)
- tasks record 2 canonicalised from tasks.csv:4 (`exact`)
- Canonical tasks contains tasks record 0 (`exact`)
- Canonical tasks contains tasks record 1 (`exact`)
- Canonical tasks contains tasks record 2 (`exact`)
- DiagnosticReport diagnostic-7463589f8833 generated from Run run-baseline-001 (`exact`)
- task.completion.rate cites task.completion.rate (`exact`)
- EvidencePack evidence-run-baseline-001-b778c4c3f27c generated from Run run-baseline-001 (`exact`)
- manifest.yaml contains Run run-baseline-001 (`exact`)
- task.completion.rate computed from Canonical tasks (`exact`)
- task.completion.rate defined by task.completion.rate (`exact`)
- Run run-baseline-001 belongs to Experiment exp-gridlock-001 (`exact`)
- Run run-baseline-001 configured by Seed s1-gridlock-baseline (`exact`)
- Run run-baseline-001 contains task.completion.rate (`exact`)
- Run run-baseline-001 executed with No checkpoint declared (`exact`)
- Run run-baseline-001 executed with Environment synthetic (`exact`)
- tasks.csv:2 located in tasks.csv (`exact`)
- tasks.csv:3 located in tasks.csv (`exact`)
- tasks.csv:4 located in tasks.csv (`exact`)

## Metric Definition

- `metric_definition:task.completion.rate` - task.completion.rate [available]

## Evidence Used

- `evidence_key:task.completion.rate` - task.completion.rate [available]

## Canonical Records

- `canonical_table:tasks` - 3 eligible records

## Validation Findings


## Source Rows

- `source_row:tasks.csv:2` - tasks.csv:2 [available]
- `source_row:tasks.csv:3` - tasks.csv:3 [available]
- `source_row:tasks.csv:4` - tasks.csv:4 [available]

## Missing Links

- No unavailable references recorded.

## Limitations

- experiment: Only manifest experiment_id is available in bundle traces.
- source_rows: Aggregate traces show bounded source-row samples and exact eligible record counts.

# ADR-017: Complete Latency Percentile Family

Status: accepted

## Context

TrafficTwin v0.5 `MET-02` requires task-latency P99 while retaining P50 and P95. Percentile
estimators differ across libraries, and a P99 calculated from a small sample can be misread as a
worst-case or statistically stable tail estimate. Missing evidence must remain unavailable rather
than becoming zero.

## Decision

- Define the task-latency family as `task.latency.p50_ms`, `task.latency.p95_ms`, and
  `task.latency.p99_ms` over finite, non-missing, non-negative canonical `latency_ms` values.
- Sort values ascending and use linear interpolation at rank `(n - 1) * p`. Record the method as
  `linear-rank-n-minus-1-v1`; `MetricEngineConfig.percentile_method` admits only `linear` until a
  separate versioned estimator is implemented.
- Keep `minimum_sample_size=1` as the backward-compatible default. A singleton percentile equals
  its sole observation and carries an explicit warning.
- If there are zero valid latency observations, keep the latency count at zero and make mean and
  percentiles unavailable with `NO_LATENCY_VALUES`.
- If `0 < n < minimum_sample_size`, keep the mean available but make all three percentiles
  unavailable with `INSUFFICIENT_SAMPLE_SIZE`.
- Attach percentile fraction, method, method version, valid sample count, and configured minimum
  to available and unavailable percentile results.
- Expose P99 through the ordinary collection, fixed windows, default experiment aggregation,
  comparison, Markdown/HTML/PDF reports, Run Overview, catalogue, and generic provenance paths.
  The SUMO and TOS source adapters remain unsupported because they do not create canonical task
  latency collections under their current contracts.
- Treat sample P99 as descriptive only. It is not a maximum, confidence bound, or claim of tail
  stability.

## Consequences

- Exact P99 output is reproducible across whole-run and windowed calculations.
- Consumers can distinguish missing evidence from an intentionally configured sample threshold.
- The default retains the previously documented P50/P95 singleton behavior while making its
  limitation visible.
- Adding another estimator requires a new method version and compatibility decision; changing a
  label in configuration cannot silently change the calculation.

## Acceptance Evidence

- Statistics tests pin empty, singleton, interpolated P99, and invalid-percentile behavior.
- Task tests pin P50/P95/P99 values, metadata, singleton warnings, and configured-minimum
  unavailability.
- Golden projections pin exact baseline and variation P99 values.
- Window CLI tests pin exact P99 and the expanded applicable catalogue.
- Catalogue, capability, comparison, report, UI, provenance, generated-reference, lint, typing,
  and full-suite gates cover the public surfaces.

## Alternatives Considered

- Nearest-rank P99: rejected because it would differ from the existing documented linear method.
- Require 100 observations unconditionally: rejected because sample percentiles are defined for
  smaller samples and research protocols may set different defensible thresholds.
- Return zero when no latency exists: rejected because missing observations do not prove zero
  latency.
- Label the maximum as P99: rejected because it fabricates a different statistic.

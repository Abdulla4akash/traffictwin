# Design — Incremental analytics and data-quality monitor (post-v1 A-1)

**Status: IMPLEMENTED as an aggregate-only backend micro-batch contract in Phases 152, 161 and
165. The delivered path has digest/version work keys, durable replay of receipts and
materialisations, idempotent retry, crash-before-commit recovery, deterministic
concurrency/progression summaries, local-service-date readiness, explicit missingness, the
owner-selected 15-minute schedule, freshness/completeness/exclusion thresholds, cross-source
overlap and schema-change refusals, and immutable local report publication under indefinite
retention. The shared dashboard has not yet bound the safe report feed and no OS scheduler is
activated by the library; this is not continuous streaming or a production-monitoring claim.
Maximum policy ceiling: `owner_approved_candidate`. This is aggregate micro-batch
analytics, not a claim of continuous streaming, real-time control or production
monitoring.**

## 1. Purpose

Meeting 3 joined ingestion to analytics and future-state prediction. The scheduled runner
now produces cadence and activity aggregates, including Phase-143 concurrency and hourly
progression, but a growing archive still needs deterministic incremental materialisation
and visible quality checks. This slice processes each newly accepted aggregate exactly
once and reports what is usable, thin, late or refused.

The source feed operates at roughly minute cadence, so scheduled micro-batches are the
honest abstraction. The design does not introduce Kafka, claim sub-second latency or relax
the scheduled-runner acquisition boundary.

## 2. Dependencies and boundary

Preferred dependency: the
[historical store and feature registry](historical_store_feature_registry_design.md).
Before that exists, a prototype may consume an explicit list of digest-pinned aggregate
files, but it may not invent a parallel persistent catalogue.

Inputs are aggregate-only session activity/cadence records and public descriptive profiles.
The monitor never opens raw BODS quarantine, creates salts, joins vehicle identities across
snapshots/sessions or launches acquisition. It does not fit the
[bus predictor](bus_prediction_design.md); it produces compatible feature snapshots and
readiness reports that the predictor may consume later.

## 3. Processing model

Each accepted dataset produces one immutable `AnalyticsWorkItem`, keyed by source digest,
schema version and analytics-definition version. The worker:

1. validates the registered source and evidence boundary;
2. reserves the idempotency key transactionally;
3. computes only declared aggregate measures;
4. writes provisional materialisations and quality observations;
5. commits outputs and advances the checkpoint atomically.

If computation fails, the reservation remains retryable and no successful checkpoint is
written. A repeated identical item returns its existing receipt. Changed source bytes under
the same logical id refuse.

## 4. Materialisations

Initial measures are intentionally small:

- session and hourly concurrency summaries using per-snapshot `live_vehicle` or the
  explicitly labelled attended-session `extracted_observation_count`;
- hourly `measure_session_progression` summaries, retaining support and exclusions;
- scheduled-cadence freshness, gap and completion summaries;
- distinct eligible local service dates by day type and local hour;
- forecast-readiness cells: support dates, completeness and refusal reason;
- source/version distribution and duplicate/overlap counts.

`vehicles_linked_across_snapshots` is never substituted for concurrency. Progression is
never renamed general traffic speed. UTC timestamps are not reinterpreted as local service
hours; the declared `Europe/London` date/hour contract and DST metadata are retained.

## 5. Quality observations

Every check emits a `QualityObservation` with rule version, scope, measured value, support,
severity, first/last occurrence and source digest. Proposed rules include:

- schema/digest validity and logical-id collision;
- snapshot cadence gaps or overlap;
- incomplete session windows and missing declared hours;
- unsupported day-type/hour cells;
- progression unavailable or exclusion share above an owner-set descriptive threshold;
- impossible units/ranges and non-finite values;
- unexpected schema/source-version change;
- stale source age measured against the owner-approved schedule;
- forbidden fields, private paths or identifier-like values.

Severity is operational (`info`, `warning`, `refusal`), not scientific confidence. Drift
alerts are descriptive comparisons, not causal findings or evidence of degradation.
Thresholds that might later support a scientific claim require a separate predeclaration.

Phase 165 binds the operational policy digest to each complete report. Freshness warns at
30 minutes and refuses readiness at 60 minutes; session completeness warns below 95% and refuses
below 80%; progression exclusion share warns above 10% and refuses above 25%. Any overlapping
source window or unrecognised schema version refuses. These thresholds affect operational
readiness only and cannot establish a scientific effect.

## 6. Outputs and API

Outputs are immutable `IncrementalAnalyticsReceipt`, feature-snapshot digests, a checkpoint
and a `DataQualityReport`. The report separates accepted, warned, refused and not-observed;
missing is never shown as zero.

Minimum library surface:

- `plan_increment(source_record) -> AnalyticsWorkItem | AnalyticsRefusal`
- `apply_increment(work_item) -> IncrementalAnalyticsReceipt | AnalyticsRefusal`
- `build_quality_report(as_of_digest) -> DataQualityReport`
- `read_readiness(target, filters) -> ReadinessReport`

Dashboard consumers receive serialisable safe summaries only. They cannot request arbitrary
filesystem paths or SQL, mutate checkpoints, suppress refusals or start the runner.

`LocalQualityReportStore` publishes a report atomically under its content digest, makes exact
retries idempotent and exposes a read-only local feed. It has no deletion or external-send API.
`next_scheduled_run` and `scheduled_readiness_cells` derive strict 15-minute UTC cells and retain
the corresponding `Europe/London` offset and fold, so the repeated and skipped DST hours remain
explicit rather than being collapsed.

## 7. Evidence and alert semantics

Analytics outputs inherit the weakest standing of their inputs and transformation. A data
quality pass does not admit a source. Forecast-readiness is not forecast validity. Alerts
must say what rule fired and with what support; they may not say a model, policy or city is
unsafe, optimal or causally affected.

LLM-written explanations, if added later, must be derived only from the typed report,
remain `evidence: false`, cite their source digests and never create or clear an alert.

## 8. Typed refusals

At minimum: `SOURCE_NOT_REGISTERED`, `DIGEST_MISMATCH`, `SCHEMA_UNSUPPORTED`,
`CHECKPOINT_CONFLICT`, `DUPLICATE_LOGICAL_SOURCE`, `SESSION_OVERLAP`,
`LOCAL_TIME_METADATA_MISSING`, `PROGRESSION_AGGREGATE_MISSING`,
`RAW_SOURCE_FORBIDDEN`, `PRIVATE_CONTENT_DETECTED`, `NONFINITE_MEASURE` and
`STANDING_ESCALATION`.

## 9. Verification and acceptance

Synthetic tests cover idempotent retry, crash-before-commit recovery, deterministic
materialisations, late-arriving aggregates, duplicate and overlap refusal, DST/local-date
handling, cadence gaps, unavailable progression, minimum support, evidence inheritance and
privacy screening. Property tests should show that processing the same accepted set in
different arrival orders yields the same final aggregates where the measure is declared
order-independent.

Acceptance requires no raw-data access, one receipt per digest/version, a replay from an
empty checkpoint that reproduces all materialisation digests, explicit missingness, and a
quality report that cannot mutate source or evidence state.

## 10. Owner decisions and stop conditions

The owner selected the following policy on 2 August 2026:

| Decision | Selected policy |
|---|---|
| Processing cadence | Scheduled micro-batch every 15 minutes |
| Freshness | Warning at 30 minutes; readiness refusal at 60 minutes |
| Completeness | Warning below 95%; readiness refusal below 80% |
| Progression exclusions | Warning above 10%; refusal above 25% |
| Overlap and schema | Any overlapping source window or unrecognised schema refuses |
| Notifications | Typed local receipts and local-dashboard feed only; no external notification |
| Retention | Indefinite; no automatic deletion |

The backend policy and safe dashboard feed are implemented. Activating an OS scheduler and binding
the feed into the shared dashboard remain deployment/integration work, not missing analytics
semantics. Stop if monitoring would require raw quarantine access, participant data, cross-session
identity, an external notification account, or scientific interpretation of an operational
threshold.

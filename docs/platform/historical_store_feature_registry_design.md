# Design — Aggregate historical store and feature registry (post-v1 H-1)

**Status: PROPOSED post-v1 design; owner review pending, unimplemented and not approved for build.
The maximum policy ceiling is `owner_approved_candidate`. Building this slice requires an
owner scope decision. This document does not authorise acquisition, migration of raw BODS
material, experiment execution, cloud services, or production deployment.**

## 1. Purpose

Meeting 3 described historical storage as the bridge between ingestion, analytics,
prediction and decision support. TrafficTwin already has workspaces, receipts, registries
and committed evidence artifacts, but no single queryable catalogue with a stable feature
contract. This slice adds that catalogue without replacing the source-specific provenance
chains that make the current evidence defensible.

The store answers four narrow questions:

1. Which aggregate datasets and model artifacts exist?
2. Which exact source digests, schemas and eligibility decisions produced them?
3. Which feature definitions were used by a fit, forecast or analysis?
4. Can a consumer retrieve a compatible version without learning a private path or raw
   identifier?

It is infrastructure, not a new scientific result. Registration never changes admission
standing and never turns a forecast, draft or non-admitted result into evidence.

## 2. Position in the platform

Build only after the six committed v1 slices are complete. It consumes the aggregate-only
outputs of the [scheduled BODS runner](bods_scheduled_runner_design.md), the implemented
Phase-143 bus activity aggregates and safe committed VEC analysis artifacts. It can later
serve the [incremental analytics monitor](incremental_analytics_monitor_design.md),
[experiment evidence matrix](experiment_evidence_matrix_design.md), and
[scenario/run registry](scenario_run_registry_design.md).

The existing evidence register, source-specific receipts and admission records remain
authoritative. The historical store indexes them; it does not become a second admission
authority.

## 3. Data boundary

Eligible payload classes are deliberately narrow:

| Class | Example | Payload allowed |
|---|---|---|
| Aggregate session measurement | concurrency/progression by snapshot or hour | Aggregate values, declared local service date, support and exclusions |
| Public descriptive profile | digested DfT hourly profile | Normalised aggregate series plus source and licence metadata |
| Model artifact | predictor or bus-forecast fit | Parameters, compatibility envelope, fit/source digests and evidence flags |
| Safe analysis summary | admitted or explicitly non-admitted campaign analysis | Committed metrics, evidence role, standing, design fingerprint and citations |
| Scenario metadata | composer draft or later run receipt | Digests and typed state only; no arbitrary prompt or secret material |

Raw BODS bytes, salts, vehicle or operator identifiers, cross-session linkages,
credentials, private absolute paths and participant data are forbidden. Whole-region
Sparse-64 artifacts may be indexed only as `NON_ADMITTED` metadata; their results must
remain segregated from the admitted VEC feature namespace.

## 4. Logical architecture

The first implementation should remain local and dependency-light:

- **Payload area:** immutable, content-addressed aggregate JSON or Parquet artifacts in an
  owner-selected workspace outside the repository.
- **Catalogue:** a transactional embedded database containing logical records, digests,
  schema versions, temporal coverage and evidence standing.
- **Feature registry:** immutable definitions that give every derived feature a name,
  version, units, aggregation rule, eligibility rule and implementation digest.
- **Read service:** a typed library API first. A dashboard adapter may be added only after
  the backend contract and privacy tests pass.

DuckDB plus Parquet is one implementation candidate, not an architectural requirement.
The owner must choose the storage engine and retention location before implementation.
No network service, warehouse account or object-store spend is implied.

## 5. Core records

`HistoricalDatasetRecord`:

- `dataset_id`, `logical_source_id`, `schema_name`, `schema_version`;
- `payload_digest`, `source_digests`, `created_at_utc`;
- declared event-time interval, local-service-date coverage and timezone where applicable;
- support, exclusions and refusal counts;
- `evidence_role`, `admission_status`, `policy_ceiling` and `execution_deviation`;
- citation bundle and licence class;
- relative workspace locator or opaque handle, never an absolute path.

`FeatureDefinition`:

- stable `feature_name` and monotonically versioned definition;
- value type, units, allowed null semantics and aggregation grain;
- exact transformation identifier and implementation digest;
- required input schemas and minimum support;
- leakage boundary, evidence restrictions and deprecation relation.

`FeatureSnapshot` binds a dataset digest to feature-definition versions and records row
count, coverage, exclusions and a deterministic snapshot digest. Values are not silently
rewritten when a definition changes; a new snapshot is created.

## 6. Write and read contracts

Registration is validate-then-commit:

1. Parse and schema-check the candidate in a temporary transaction.
2. Screen keys and string values for private paths, secrets and prohibited identifiers.
3. Verify payload and source digests.
4. Check that the requested evidence standing is no stronger than the source standing.
5. Reject logical-id conflicts unless the content digest is identical.
6. Atomically publish the payload handle, catalogue row and receipt.

A failure leaves no partial catalogue row or payload alias. An exact retry is idempotent.
Reads require an explicit schema/version range and return a compatibility result; they do
not silently select the newest version or combine incompatible evidence classes.

Minimum library surface:

- `register_dataset(candidate) -> StoreReceipt | StoreRefusal`
- `register_feature(definition) -> FeatureReceipt | FeatureRefusal`
- `materialise_snapshot(request) -> FeatureSnapshot | FeatureRefusal`
- `get_dataset(dataset_id, expected_digest) -> HistoricalDatasetRecord`
- `query_catalogue(filter) -> tuple[HistoricalDatasetRecord, ...]`

## 7. Evidence, privacy and retention rules

- `evidence: false` remains false after storage or retrieval.
- Admission status is copied from an authoritative source record and cannot be edited in
  place. A later admission decision creates a new link event.
- Protocol-confirmed, post-hoc, exploratory, descriptive and execution-deviated roles are
  separate filterable fields, not prose collapsed into one confidence label.
- An aggregate with fewer supporting dates or seeds than a consumer requires is returned
  with its real support; the store never imputes support.
- Deletion and retention are owner policy decisions. Any future garbage collection must be
  receipt-driven, target exact payload digests and preserve catalogue tombstones.

## 8. Typed refusals

At minimum: `RAW_SOURCE_FORBIDDEN`, `PRIVATE_PATH_DETECTED`, `IDENTIFIER_FIELD_FORBIDDEN`,
`SCHEMA_UNSUPPORTED`, `DIGEST_MISMATCH`, `LOGICAL_ID_CONFLICT`, `FEATURE_INCOMPATIBLE`,
`STANDING_ESCALATION`, `LICENCE_METADATA_MISSING`, `PARTIAL_COMMIT` and
`SOURCE_RECORD_MISSING`.

## 9. Verification and acceptance

Tests use synthetic aggregate fixtures only and cover deterministic digests, idempotent
retry, transaction rollback, schema evolution, incompatible-feature refusal, evidence
standing monotonicity, Sparse-64 segregation, private-path/identifier screening, timezone
metadata and missing-support preservation. A migration dry run must prove that registering
existing safe artifacts changes neither their bytes nor their source records.

Acceptance requires:

- no raw/private payload in the store, repository or test fixtures;
- byte-identical query results for a pinned dataset and feature snapshot;
- no state change after any typed refusal;
- a provenance walk from a snapshot to every source digest and definition version; and
- an owner-reviewed recovery/backup procedure before the store becomes a dependency.

## 10. Owner decisions and stop conditions

The owner must choose the storage engine/location, retention period, backup policy,
licence allowlist and whether any catalogue metadata may be committed. Stop if satisfying
a consumer would require raw BODS retention, cross-session identity, participant data,
unreviewed cloud spend, or an evidence-standing upgrade. Those are new scopes, not hidden
implementation details.

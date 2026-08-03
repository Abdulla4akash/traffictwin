# Manchester Aggregate Operational History

Phase 193 implements the bounded `NEXT-03` storage contract for privacy-safe BODS and National
Highways operational trends. It does not activate long-term collection. The supplied retention
policy is a proposal until the owner records the private duration, backup cadence, disk ceiling,
deletion treatment and public-output class.

## What is stored

Each terminal source attempt can be represented by a strict aggregate-only record containing the
source and contract version, automatic/operator trigger, UTC attempt and terminal times, an
allowlisted failure code, opaque scope/receipt fingerprints, accepted/excluded/stale counts, an
optional source-time range and a one-bit clock-skew finding. Vehicle, journey and detector
identifiers, credentials, private paths, raw rows and public exports are structurally forbidden.
Unknown failure detail is reduced to `UNCLASSIFIED_SAFE_FAILURE`.

Records form a canonical JSONL hash chain under
`manchester/operational_history/journal-v1.jsonl`. The file and lock are current-user-only; append
is lock-serialised, atomically replaced, size bounded, exact-retry safe and refused after that UTC
day has become immutable. Partial lines, changed chain links, duplicate terminal receipts,
non-canonical JSON, unsafe paths and permissions fail closed. No recovery path reads source
quarantine or repairs an untrusted journal automatically.

The existing live controls remain unchanged at their 24-hour/240-entry bounds. Worker wiring is
not active in this phase: a real writer must be separately approved after the owner policy is
recorded.

## Read-only verification and preview

Verify a durable workspace without a source request or mutation:

```bash
uv run traffictwin release v07-operational-history-status \
  "$TRAFFICTWIN_REAL_WORKSPACE" --format json
```

Preview a UTC day with explicit caller-declared cadence denominators:

```bash
uv run traffictwin release v07-operational-day-preview \
  "$TRAFFICTWIN_REAL_WORKSPACE" 2026-08-02 \
  --bods-status enabled --bods-interval 60 --bods-expected 1440 \
  --national-highways-status enabled \
  --national-highways-interval 300 --national-highways-expected 288 \
  --format json
```

Use `disabled` or `not_configured` with no interval and an expected count of zero. A denominator
is never inferred from observed successes: missing cadence is measured against the explicit
configuration supplied for that day.

## UTC partitions and daylight saving

Compaction is deterministic over a verified journal sequence and always creates 24 UTC hours for
both sources. It reconciles terminal, trigger and count totals and binds every included record
fingerprint. Private day publication is new-only and requires both an exact owner-approved policy
fingerprint and a caller-supplied authority validator; the default 24-hour compaction delay must
have elapsed. Exact bytes may be retried, while changed bytes are refused.

London time is a display projection only. Every projected hour retains its UTC instant, local
date/hour, UTC offset and PEP 495 `fold`, so the repeated autumn 01:00 hour remains two distinct
buckets. Source timestamps later than the terminal receipt remain present only as an aggregate
clock-skew count.

## Historical-store boundary

`operational_day_store_schema()` and `build_operational_day_store_candidate()` form one closed
adapter for `manchester.operational.day` payloads. It accepts only a matching authoritative
aggregate-journal record with `SAFE_ANALYSIS_SUMMARY`, descriptive/not-applicable standing and
`evidence: false`. Arbitrary JSON, sparse/metadata-only sources and mismatched journal tails are
refused. Registration does not upgrade these operational descriptions into scientific evidence.

## Still blocked

- owner approval of the aggregate retention, backup, disk, deletion and public-output policy;
- wiring the two source workers to the journal and reconciling crash boundaries;
- any operating-system backup or deletion scheduler;
- a public trend export and its licence/privacy review; and
- owner activation in a real workspace.

See [durable workspace creation](../v07_durable_workspace.md),
[local real-workspace run profile](../v07_real_workspace_run.md), and the
[canonical v0.7 design](../traffictwin-design-v0_7.md).

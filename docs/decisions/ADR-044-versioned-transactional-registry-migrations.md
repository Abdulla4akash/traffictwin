# ADR-044: Versioned Transactional Registry Migrations

- Status: accepted
- Date: 2026-07-21
- Capability: `OPS-01`

## Context

TrafficTwin originally created every known SQLite table through repeated `CREATE TABLE IF NOT
EXISTS` scripts in `Registry.initialize()` and `ProtocolTracker.initialize()`. That additive path
did not identify a schema version, record which changes ran, detect missing or modified objects,
prove ordering, or define rollback. It could silently recreate a dropped table while presenting a
tampered database as healthy.

The repository now has registry state for imports, metrics, EvidencePacks, protocols, experiment
evidence, and append-only analyst annotations. Future persistence changes need one auditable
upgrade boundary before caching, doctor, and archival capabilities are built.

## Decision

Implement `traffictwin.storage.migrations` as the only registry schema owner:

1. Use SQLite `PRAGMA user_version` as the authoritative integer version and publish schema
   versions 1–5 in a fixed contiguous order.
2. Record every applied version in `registry_schema_migrations` with immutable version, name,
   embedded-SQL checksum, and application timestamp. Database triggers reject ledger updates and
   deletes.
3. Execute the complete pending ordered plan, its ledger inserts, and version changes inside one
   `BEGIN IMMEDIATE` transaction. Any statement, schema validation, ledger validation, or
   `quick_check` failure rolls back the whole plan to the exact starting version.
4. Validate required object types and columns after every version. Reject ledger gaps, changed
   names/checksums, future versions, downgrades, malformed known tables, and unknown schema
   objects before commit.
5. Support empty databases and known unversioned repository-era additive TrafficTwin schemas.
   Legacy tables may already contain objects from any of the five versions; `IF NOT EXISTS`
   statements adopt them only after their required columns are verified. Existing rows and JSON
   payload bytes are never rewritten.
6. Make `Registry.initialize()` and `ProtocolTracker.initialize()` delegate to this single runner.
   Remove their independent schema scripts.
7. Expose a read-only immutable status inspection, an explicit migration contract, and an
   explicit migrate command. Normal registry access continues to initialise or upgrade a
   supported database automatically.
8. Do not provide destructive downgrades or claim that schema integrity validates scientific JSON
   meaning. Recommend an independent backup before migrating valuable registries.

The version sequence is:

| Version | Migration | Introduced boundary |
|---:|---|---|
| 1 | `core_registry` | Migration ledger, seeds, experiments, runs |
| 2 | `import_and_analysis_artifacts` | Bundle imports, metric collections, run EvidencePacks |
| 3 | `experiment_protocol_tracking` | Protocols and manual protocol slots |
| 4 | `experiment_evidence` | Experiment EvidencePacks |
| 5 | `analyst_annotations` | Append-only annotations, index, and guards |

## Consequences

- The same binary has one inspectable current schema version and ordered migration fingerprint.
- A failure cannot leave half-created tables, partial ledger rows, or an advanced `user_version`.
- Re-running a completed migration is a byte-idempotent no-op.
- Known old registry rows remain byte-identical at the payload-column level.
- Tampering and unsupported future schemas fail visibly instead of being silently repaired.
- Initialisation takes an immediate SQLite write lock while checking/applying the plan. The current
  schema is small; a later large data migration must re-evaluate lock duration and backup policy.
- The migration ledger is operational provenance, not scientific provenance and not evidence that
  a stored payload is semantically valid.

## Rejected Alternatives

- Continue additive `CREATE IF NOT EXISTS` scripts: rejected because they have no ordered version,
  drift detection, or rollback contract.
- One transaction per migration: rejected for this small initial sequence because it can leave an
  upgrade stopped at an intermediate version. A single plan transaction gives stronger rollback.
- Alembic or another external framework: rejected because the current SQLite-only sequence is
  bounded and does not justify another runtime dependency. This can be revisited if schema breadth
  or deployment topology changes.
- Automatic downgrade: rejected because reverse transformations could destroy data and are not
  required by OPS-01.
- Automatically copying the database before every operation: rejected because storage and backup
  policy belong to the operator; the CLI states that valuable registries should be backed up.
- Accepting arbitrary extra tables: rejected because a user could accidentally point TrafficTwin
  at an unrelated SQLite database and mutate it.

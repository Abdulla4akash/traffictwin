# Registry Schema Migrations

TrafficTwin `OPS-01` provides deterministic, ordered, transactional SQLite registry upgrades. It
replaces the former repeated additive table creation with five explicit schema versions and an
immutable checksummed migration ledger.

## What Is Migrated

| Version | Name | Registry objects |
|---:|---|---|
| 1 | `core_registry` | Schema ledger, seeds, experiments, runs |
| 2 | `import_and_analysis_artifacts` | Bundle imports, metrics, run EvidencePacks |
| 3 | `experiment_protocol_tracking` | Experiment protocols and manual slots |
| 4 | `experiment_evidence` | Experiment EvidencePacks |
| 5 | `analyst_annotations` | Annotation history, target index, append-only guards |

`PRAGMA user_version` is the authoritative version. The `registry_schema_migrations` table records
the exact migration name, embedded-SQL checksum, and applied timestamp for every version. Update
and delete triggers make that history append-only.

## Safe Operating Workflow

Back up a valuable registry first. TrafficTwin makes migrations atomic but does not create an
operator backup automatically.

Inspect without changing the database:

```bash
traffictwin registry migration-status .traffictwin-demo/registry.sqlite
```

Inspect the machine-readable migration contract:

```bash
traffictwin registry migration-contract --format json
```

Apply every pending migration:

```bash
traffictwin registry migrate .traffictwin-demo/registry.sqlite
```

Request JSON suitable for an operational log:

```bash
traffictwin registry migrate .traffictwin-demo/registry.sqlite --format json
```

`traffictwin registry init PATH` creates a new current registry through the same migration runner.
Ordinary `Registry` and protocol-tracker operations also upgrade a supported older registry before
access. Use `migration-status` when a strictly read-only check is required.

## Python Use

```python
from traffictwin.storage.migrations import (
    inspect_registry_migrations,
    migrate_registry,
    registry_migration_contract,
)

contract = registry_migration_contract()
before = inspect_registry_migrations("registry.sqlite")
result = migrate_registry("registry.sqlite")
after = inspect_registry_migrations("registry.sqlite")

print(contract.current_registry_schema_version)
print(before.state, result.applied_migrations, after.state)
```

For controlled compatibility testing, the library accepts `target_version=1` through the current
version. It never accepts a target below the database's current version.

## Transaction And Failure Semantics

The runner obtains `BEGIN IMMEDIATE`, validates the starting schema and ledger, applies every
pending migration in order, validates each version boundary, runs SQLite `quick_check`, and then
commits. Any failure rolls back:

- all schema objects created by that invocation;
- all migration-ledger inserts from that invocation;
- all `PRAGMA user_version` advances from that invocation.

Previously committed rows and versions remain unchanged. Running the same completed target again
adds no ledger entries and is byte-idempotent in the acceptance tests.

## Supported Historical Boundary

The first migration contract supports:

- an empty SQLite database;
- formal TrafficTwin schema versions 1–4 created by this migration sequence;
- known unversioned repository-era additive schemas containing any recognised combination of the
  core, import, analysis, protocol, experiment-evidence, and annotation objects.

Known legacy tables must contain every required column. Existing payload columns are not rewritten
or re-serialised. An unknown table, view, index, or trigger causes a fail-closed error so an
unrelated SQLite database is not silently adopted.

## Refused States

Migration stops visibly for:

- a schema version newer than the running TrafficTwin build;
- a downgrade request;
- missing required objects or columns in a versioned registry;
- an incomplete, renamed, or checksum-mismatched ledger;
- unknown schema objects;
- a corrupt database or failed SQLite `quick_check`;
- a lock or permission failure.

Do not edit `PRAGMA user_version` or the ledger manually. Restore a verified backup or use a
separately reviewed recovery procedure if either is inconsistent.

## Interpretation Limits

A migration proves that the SQLite structure matches the embedded contract. It does not prove
that stored run, metric, evidence, report, or annotation JSON is scientifically correct. It does
not modify raw bundles, calculate metrics, reinterpret findings, or change source fingerprints.

The governing decision is
[ADR-044](decisions/ADR-044-versioned-transactional-registry-migrations.md).

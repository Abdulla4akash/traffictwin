# Canonical-table Caching

TrafficTwin `OPS-02` can reuse canonical tables for an unchanged, ordinarily valid generic run
bundle. It stores six typed Parquet tables outside the raw bundle and re-fingerprints the raw bundle
before every hit. Caching changes runtime only; the returned scientific result is exactly the cold
validation result.

## Quick Start

Choose a cache directory that is not inside the bundle:

```bash
traffictwin bundle cache-status tests/fixtures/bundles/baseline_valid \
  --cache-root .traffictwin-cache

traffictwin bundle cache-validate tests/fixtures/bundles/baseline_valid \
  --cache-root .traffictwin-cache
```

The first `cache-validate` normally reports `cache_state: written`. Running the same command again
normally reports `cache_state: hit`. Request a machine-readable receipt with `--format json`:

```bash
traffictwin bundle cache-validate BUNDLE \
  --cache-root CACHE_DIRECTORY \
  --format json
```

Inspect the versioned contract:

```bash
traffictwin bundle cache-contract --format json
```

`cache-status` is read-only. It reopens and hashes raw files and verifies a matching entry if one
exists, but it does not build a missing entry or fully validate a miss.

## Status Meanings

| State | Meaning | Cache used? |
|---|---|---:|
| `miss` | No directory exists for the complete current key. | No |
| `written` | Cold validation was accepted, verified Parquet was published atomically. | Cold result returned |
| `hit` | Raw identity, entry checksums, schemas, rows, and validation metadata all verified. | Yes |
| `stale` | An entry at the expected location has the wrong raw/mapping identity. | No |
| `incompatible` | Adapter, validator, cache format, or canonical schema differs. | No |
| `corrupt` | Inventory, checksum, size, Parquet, typed row, or summary verification failed. | No |
| `unavailable` | The bundle lacks the valid manifest/seed/fingerprint required for caching. | No |
| `write_failed` | Cold validation completed but cache publication failed. | No |

On `stale`, `incompatible`, or `corrupt`, TrafficTwin may still return an ordinary cold validation
result through the Python API. It keeps the bad status visible and never overwrites the entry. The
CLI returns non-zero because the requested cache operation did not produce a verified reusable
entry.

If another process publishes the same valid key first, the losing writer verifies and reuses that
entry, then removes only its own unpublished temporary directory.

## What Is In One Entry

The entry directory name is the SHA-256 fingerprint of:

- exact raw bundle fingerprint;
- `generic_tabular` adapter identifier and version;
- validator version;
- manifest file declarations, columns, units, checksums, and semantic contracts;
- canonical Pydantic and Arrow schema fingerprint;
- cache format version.

The directory contains:

```text
<cache-key>/
├── entry.json
├── validation.json
├── tasks.parquet
├── infrastructure.parquet
├── vehicles.parquet
├── traffic.parquet
├── trips.parquet
└── incidents.parquet
```

Empty canonical tables still have their complete typed Arrow schema. `entry.json` carries exact
checksums, sizes, rows, and record-model names. `validation.json` carries the accepted manifest,
seed, findings, evidence availability, and insufficient-evidence state. It does not contain raw
source bytes.

## Python Use

```python
from traffictwin.ingestion.bundle import inspect_bundle_cache, validate_bundle_cached

status = inspect_bundle_cache("bundle", ".traffictwin-cache")
cached = validate_bundle_cached("bundle", ".traffictwin-cache")

print(status.state)
print(cached.cache.state)
print(cached.validation.canonical.record_counts())
```

Existing metric, evidence, diagnostic, reporting, and provenance functions consume
`cached.validation` exactly as they consume `validate_bundle(...)`.

## Safe Operations

- Keep the cache outside every raw directory bundle. The library refuses overlap.
- Treat the cache as disposable derived data, not as the only copy of evidence.
- Keep raw bundles, manifests, seeds, and declared checksums under the existing preservation policy.
- Use `cache-status` before relying on a shared or copied cache.
- Do not edit `entry.json` or Parquet payloads manually.
- TrafficTwin does not delete invalid entries. If an operator chooses to quarantine or remove one,
  first identify the exact `cache_entry` path from status output and preserve it if investigation is
  required. A later accepted cold run can then publish the same key again.

## Scope and Limits

OPS-02 currently supports ordinary generic run bundles only. It does not cache:

- rejected bundle results;
- the memory-bounded streaming path;
- SUMO source-specific imports;
- TOS source-specific arrays or summaries;
- metrics, EvidencePacks, diagnostics, reports, or registry records;
- direct simulator results or live data.

Warm reuse still reads and hashes raw bytes, verifies cached checksums, reads Parquet, and validates
every canonical record. It is not an in-memory memoizer. Cache retention/eviction, multi-host locks,
remote/object storage, encryption, signatures, and shared-service permissions remain outside v1.

The governing decision is
[ADR-045](decisions/ADR-045-content-addressed-canonical-table-cache.md).

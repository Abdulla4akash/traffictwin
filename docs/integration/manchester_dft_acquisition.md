# Controlled DfT Acquisition Workflow (MAN-02 candidate)

Status: **candidate Gate B library evidence — `MAN-01` and `MAN-02` remain `planned`**

`traffictwin.integration.manchester.dft_acquisition` connects the existing MAN-01
infrastructure to the MAN-02 parser in one fixed, fail-closed order:

```text
BoundedHttpClient fetch (per page, bounded)
    → MAN-01 quarantine (complete raw set, atomic, hash-verified)
    → MAN-02 parser over the quarantined bytes
    → promote to accepted storage only on an admitted parse
```

It reuses the existing [transport boundary](manchester_transport_boundary.md),
[snapshot service](manchester_snapshot_service.md), and
[DfT adapter](manchester_dft_adapter.md) without adding a second HTTP, hashing,
or publication implementation, makes no freshness or SUMO claim, and changes no
capability state.

## Request/query contract

`DftAcquisitionRequest` is strict, frozen, and deliberately unable to express a
host, path, URL, or free-form query:

- `dataset`: `raw_counts` | `count_points` | `aadf` — mapped internally to the
  three audited endpoints on `roadtraffic.dft.gov.uk`; nothing else is
  reachable (the shared `EndpointPolicy` allowlists exactly those three path
  prefixes).
- `scope`: `DftManchesterScope` whose ONS code (`E08000003`) and
  `local_authority_id=85` are literals — callers cannot select another
  authority.
- Optional audited filters only: `filter_id` → `filter[id]`, `year` →
  `filter[year]` (refused for `count_points`, whose rows carry `aadf_year`
  only). The mandatory scope filter `filter[local_authority_id]=85` is always
  sent.
- Pagination is driven by `page[number]`/`page[size]`; query parameters are
  deterministic and sorted by the transport layer, and the exact allowlisted
  query name set is `filter[id]`, `filter[local_authority_id]`,
  `filter[year]`, `page[number]`, `page[size]`.
- Explicit bounds: `page_size` (≤500), `max_pages` (≤500, also bounded by the
  snapshot policy's member count), `max_rows` (≤200,000), and a full
  `ManchesterSnapshotPolicy` (member count / member bytes / total bytes).
- Explicit policies: `publication_class`, `prior` snapshot link,
  `accept_with_warnings` (warning-accepted parses promote only when this is
  true), and a mandatory `synthetic` declaration that flows into every
  manifest, receipt, and parser lineage reference.

Transport limits are conservative module constants (no published DfT rate
limits exist — audit blockers `GA-DFT-2`/`GA-DFT-3`): 10 s connect, 30 s read,
120 s per-request deadline, ≤2 same-host redirects, ≤3 attempts,
`application/json` only, and per-response bytes capped by the snapshot
policy's member bound.

## Quarantine-before-parse

Every exact response body is preserved in MAN-01 quarantine before the parser
sees any page. This is enforced structurally — the workflow calls the existing
`quarantine_validate_and_promote`, which publishes and verifies the quarantine
before invoking the validator — and proven by a test that intercepts the parser
and asserts all raw pages plus the quarantine manifest already exist on disk at
parse time. The parser then re-reads bytes from the quarantine directory,
re-hashing each member against the manifest.

One bounded exception is documented rather than hidden: pagination control
performs a read-only *peek* of the four audited envelope integers
(`current_page`, `per_page`, `total`, `last_page`) on each already
size-bounded body, solely to drive iteration and limits. The peek produces no
records, persists nothing, and everything it reads is re-verified from
quarantined bytes by the full MAN-02 parser before promotion.

## Failure behaviour

All failures are typed (`DftAcquisitionError` with a stable `code`, or the
existing `ManchesterSnapshotError`), publish no accepted snapshot, and never
touch an existing accepted snapshot:

| Situation | Code | Durable evidence |
|---|---|---|
| Transport failure / HTTP rejection on any page | `TRANSPORT_FAILURE` | none — acquisition incomplete, nothing published |
| First page is not page 1, pages disagree, or `per_page` differs from the request | `PAGINATION_DRIFT` | none |
| Body is not the audited envelope, or pagination totals do not reconcile | `PAGINATION_PEEK_FAILED` | none |
| Reported pages/rows/bytes exceed request bounds | `PAGE_LIMIT_EXCEEDED` / `ROW_LIMIT_EXCEEDED` / `TOTAL_BYTES_EXCEEDED` | none |
| Parser rejects the quarantined evidence (schema drift, out-of-scope, malformed rows, conflicts) | `PARSE_REJECTED` | complete quarantine retained; `quarantine_snapshot_id` set |
| Warning-accepted parse without `accept_with_warnings` | `WARNINGS_REFUSED` | complete quarantine retained |
| Quarantined bytes drift before/during replay | `QUARANTINE_INVALID` / snapshot-service `MEMBER_MUTATED` | quarantine preserved for inspection |
| Replay dataset/source/endpoint/request/licence/page inventory disagree | `DATASET_MISMATCH` / `SOURCE_CONTRACT_MISMATCH` | quarantine preserved; no parser output is relabelled |
| Same acquisition repeated | snapshot-service `DESTINATION_EXISTS` | prior quarantine/accepted snapshots unchanged |

Incomplete acquisitions deliberately publish nothing (the existing MAN-01
policy quarantines only complete acquisitions); complete-but-invalid
acquisitions are retained in quarantine and never promoted.

## Receipts

A successful run returns `DftAcquisitionResult` (strict, frozen, canonical
fingerprint): dataset and endpoint identity, the full request, snapshot ID, raw
fingerprint, complete member inventory, page/row/record counts, the parser
report status and fingerprint, quarantine and accepted receipt fingerprints,
and the synthetic flag. A rejected parser status is unrepresentable in a
result. Query secrets cannot appear anywhere (DfT is anonymous, and the shared
request-identity models refuse credential-like names); pagination-envelope URLs
are never persisted.

## Offline replay

`replay_dft_quarantine(workspace, snapshot_id, dataset, expected_synthetic=…)`
re-verifies an existing quarantine through the unmodified MAN-01
`verify_manchester_quarantine` and re-runs the MAN-02 parser over the stored
bytes with no network and no promotion, returning a `DftReplayResult` whose
parser fingerprint matches the original acquisition. A declared/actual
evidence-class disagreement is refused (`SYNTHETIC_MISMATCH`). Before parsing,
replay also proves that the caller's dataset agrees with the manifest source
ID, audited endpoint, adapter/schema/freshness versions, anonymous Manchester
query, licence/attribution, sequential page inventory, and each page envelope
number. This prevents valid quarantined bytes from being relabelled as another
DfT dataset. The three
retained official fixtures (see the [DfT adapter guide](manchester_dft_adapter.md))
pass through this validation path from locally built quarantines without any
download, pinned to their recorded SHA-256 values.

`load_accepted_dft_report(workspace, acquisition)` is the separate downstream
read boundary for promoted evidence. It first requires a valid isolated v0.7
workspace, re-validates the supplied `DftAcquisitionResult`, verifies the
accepted snapshot receipt and every member hash, and binds the manifest to the
exact dataset, request filters, page size, policy, prior link, publication
class, licence, attribution, validation state, and evidence class. It then
replays the same MAN-02 parser and requires the report fingerprint and counts
to reproduce the acquisition receipt exactly. The function performs no HTTP
request and is shared by DfT map and survey-view services, so those consumers
do not implement their own weaker accepted-snapshot readers.

For later local sessions that no longer hold the in-memory acquisition result,
`open_accepted_dft_snapshot(workspace, snapshot_id)` derives the dataset from
the verified source identity and reproduces the exact parser report using only
the accepted manifest, receipt, and immutable members. It additionally
requires the stored validation state and complete finding inventory to match
the replayed parser result. It returns a strict
`DftAcceptedSnapshotSummary` plus the verified manifest, receipt, and report;
it does not reconstruct or invent an acquisition request.

`catalogue_accepted_dft_snapshots(workspace)` discovers only DfT-prefixed
accepted directories, verifies and replays every candidate, ignores unrelated
source snapshots, refuses unsafe entries, and caps the inventory at 512. The
result contains sorted unique summaries and exact raw-count/count-point/AADF
counts. It performs no network access and creates no files, making it the
bounded discovery boundary for a later thin UI.

## Test evidence

`tests/unit/test_manchester_dft_acquisition.py` (27 tests, all offline via
`httpx.MockTransport` and injected deterministic clocks): exact allowlisted
request per endpoint; immutable Manchester identity (85/E08000003);
host/path/URL/query injection refusal; deterministic pagination, ordering, and
stable receipts across runs; result-model reconciliation; exact page-size and
pagination-math checks; quarantine-before-parse interception proof;
successful promotion with verified accepted snapshot and mapped findings;
explicit warning-admission policy in both directions; incomplete pages
publishing nothing; page/row/byte bound enforcement; HTTP failure leaving an
accepted snapshot byte-identical; schema drift quarantined but never promoted;
malformed JSON and pagination drift publishing nothing; hash-mutation
detection; synthetic/real and replay-dataset mismatch refusal; repeat-acquisition overwrite
refusal; socket-disabled replay; and official-fixture replay with pinned
hashes. The accepted-snapshot path additionally proves socket-disabled exact
report reproduction, request-drift refusal, and v0.7 workspace isolation.
Catalogue coverage includes empty and mixed-product workspaces, offline
opening by snapshot ID, unrelated-source isolation, path-shape and symlink
refusal, fixed inventory bounds, and tampered count reconciliation.

Focused validation commands (run 2026-07-22):

```bash
.venv/bin/python -m pytest tests/unit/test_manchester_dft_acquisition.py
.venv/bin/python -m pytest tests/unit/test_manchester_models.py tests/unit/test_manchester_snapshots.py \
  tests/unit/test_manchester_acquisition.py tests/unit/test_manchester_transport.py \
  tests/unit/test_manchester_xml.py tests/unit/test_manchester_archive.py \
  tests/unit/test_manchester_dft.py tests/unit/test_manchester_dft_acquisition.py
.venv/bin/ruff check src/traffictwin/integration/manchester/dft_acquisition.py tests/unit/test_manchester_dft_acquisition.py
.venv/bin/ruff format --check src/traffictwin/integration/manchester/dft_acquisition.py tests/unit/test_manchester_dft_acquisition.py
.venv/bin/mypy src/traffictwin/integration/manchester/dft_acquisition.py tests/unit/test_manchester_dft_acquisition.py
```

## Known limitations and open points

- `ManchesterQuarantineManifest` stores one `http` metadata block, so the
  manifest records the first page's response metadata; per-page HTTP metadata
  is not persisted by MAN-01 v1 (page identity, bytes, and hashes are).
- The stored request identity is page 1's (including `page[number]=1`); later
  page numbers are recoverable from the member inventory.
- `GA-DFT-1` (raw-count hour timezone) remains open; nothing here fabricates
  UTC instants.
- The [minimal real-source probe](manchester_dft_gate_b_probe.md) passes the
  three exact audited row IDs through acquisition and accepted replay. It is
  not a full Manchester bulk/load acceptance and does not by itself change
  capability truth.

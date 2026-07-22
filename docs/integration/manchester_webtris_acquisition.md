# Controlled WebTRIS Acquisition Workflow (MAN-03 candidate)

Status: **candidate Gate B library evidence — `MAN-01` and `MAN-03` remain `planned`**

`traffictwin.integration.manchester.webtris_acquisition` connects the existing MAN-01
infrastructure to the existing MAN-03 WebTRIS parser in one fixed, fail-closed order:

```text
BoundedHttpClient fetch (per response, bounded)
    → MAN-01 quarantine (complete raw set, atomic, hash-verified)
    → MAN-03 parser over re-read, re-hashed quarantined bytes
    → promote to accepted storage only when the parse is explicitly admitted
```

It reuses the existing [transport boundary](manchester_transport_boundary.md),
[snapshot service](manchester_snapshot_service.md), and
[WebTRIS adapter](manchester_webtris_adapter.md) without duplicating any HTTP, hashing,
quarantine, or promotion logic, and it changes no capability state.

## Products and request contract

`WebtrisAcquisitionRequest` is strict, frozen, and structurally unable to express a host, URL,
free path, free query, parser, executable, or arbitrary date string:

- `product`: `site` | `daily_report` | `daily_quality`, mapped internally to the audited
  endpoints on `webtris.nationalhighways.co.uk`: `/api/v1.0/sites/{site_id}`,
  `/api/v1.0/reports/daily`, and `/api/v1.0/quality/daily`. One `EndpointPolicy` allowlists
  exactly those path families and the query names `end_date`, `page`, `page_size`, `siteId`,
  `sites`, `start_date`.
- `site_id` is a typed digit string; `report_date` is a typed `date` (bounded 1990–2100) that
  the workflow itself renders as the audited `ddmmyyyy` request form; `site_name` binds the
  daily scope. Product-specific field rules are validator-enforced (the site product takes no
  scope name/date/page size; `daily_report` requires an explicit `page_size` ≤ 96;
  `daily_quality` takes none).
- Explicit bounds: `max_pages` (≤ the parser's 100-page bound and the snapshot policy member
  count), a full `ManchesterSnapshotPolicy` (member count / member bytes / total bytes, with
  per-response bytes capped by the member bound at the transport), and the conservative fixed
  transport limits (10 s connect, 30 s read, 120 s deadline, ≤2 same-host redirects, ≤3
  attempts, `application/json` only) reflecting the audit's absent rate-limit policy (`GA-WT-5`)
  and the announced 2026 service interruption.
- Explicit policies: `publication_class`, `prior` link, `synthetic` declaration, and the
  code-specific warning admission below.

## Quarantine-before-parse

Every exact response body is preserved in MAN-01 quarantine before the parser sees any page,
enforced structurally through the existing `quarantine_validate_and_promote` and proven by a
test that intercepts the parser and asserts all raw pages plus the quarantine manifest already
exist on disk at parse time. The validator then re-reads each member from the quarantine
directory and re-hashes it against the manifest before building parser lineage refs.

One bounded exception is documented: daily-report pagination peeks the audited
`Header.row_count` integer on each already-size-bounded body, solely because iteration requires
the page count (`ceil(row_count / page_size)`). The peek creates no records, and every peeked
value is revalidated from quarantined bytes by the full MAN-03 parser (which independently
requires `row_count == 96`, contiguous pages, and the complete interval set) before anything is
promoted. The single-response site and quality products perform no peek at all.

## Warning admission (code-specific, no blanket switch)

There is deliberately no `accept_with_warnings` boolean. The request carries
`admitted_warning_codes`: a bounded (≤8), sorted, unique tuple of exact finding codes. A
warning-accepted parse promotes only when **every** observed warning code is in that set;
otherwise the run fails `WARNINGS_REFUSED` naming the unapproved codes, and the complete
quarantine is retained unpromoted. A rejected parse (`PARSE_REJECTED`) can never promote. Typical
admissible example: `("MISSING_INTERVAL_MEASUREMENTS",)` for a day with source-empty intervals —
which stay `missing`, never zero.

## Evidence semantics preserved

All semantics come from the MAN-03 parser unchanged: WebTRIS records remain historical
strategic-road evidence (`evidence_status="historical"`,
`road_domain="national_highways_strategic_road"`); source timestamps stay verbatim under
ADR-055's `source_string_undeclared` basis while `GA-WT-1` is open — nothing here fabricates a
UTC instant; retrieval time appears only in retrieval metadata and never becomes observation
time or freshness; quality rows carry `interpretation="data_availability_percentage"` with
structural `False` literals for sensor-accuracy and traffic-validity claims; and a transport
failure or service interruption is a typed `TRANSPORT_FAILURE` whose message states it is never
zero traffic.

## Replay binding

`replay_webtris_quarantine(workspace, snapshot_id, WebtrisReplayRequest)` re-validates
already-quarantined bytes offline (no network — tested with sockets disabled; no promotion).
Before any byte is parsed, the caller's claim is bound to the manifest: product ↔ source ID
(`webtris_site` / `webtris_daily_report` / `webtris_daily_quality`), adapter/schema/freshness
versions, licence and attribution, host, audited endpoint path (including the site ID for the
site product), the exact stored request parameters recomputed from the claimed site/date/page
size, and the member-role inventory (a sequential `pages/page-0001..N` set for daily reports,
the exact single-role path otherwise). Mismatches fail typed (`PRODUCT_MISMATCH`,
`SOURCE_CONTRACT_MISMATCH`, `SCOPE_MISMATCH`, `SYNTHETIC_MISMATCH`) with the quarantine
untouched, so valid bytes can never be relabelled as another WebTRIS product, site, or day.
The saved acquisition and replay results repeat those bindings: product, request, source ID,
endpoint, evidence class, inventory, and count constraints validate again on reload. The
acquisition result also recomputes its raw fingerprint from the exact member inventory.

## Failure behaviour

| Situation | Code | Durable evidence |
|---|---|---|
| Transport failure / HTTP rejection / oversized response | `TRANSPORT_FAILURE` | none — incomplete, nothing published |
| Body fails the bounded row-count peek | `PAGINATION_PEEK_FAILED` | none |
| Later page disagrees with page 1 | `PAGINATION_DRIFT` | none |
| Reported pages / combined bytes exceed bounds | `PAGE_LIMIT_EXCEEDED` / `TOTAL_BYTES_EXCEEDED` | none |
| Parser rejects (schema drift, scope mismatch, malformed rows) | `PARSE_REJECTED` | complete quarantine retained |
| Warning code outside the admitted set | `WARNINGS_REFUSED` | complete quarantine retained |
| Quarantined bytes drift | `QUARANTINE_INVALID` / snapshot-service `MEMBER_MUTATED` | quarantine preserved |
| Replay claim disagrees with manifest | `PRODUCT_MISMATCH` / `SOURCE_CONTRACT_MISMATCH` / `SCOPE_MISMATCH` / `SYNTHETIC_MISMATCH` | quarantine preserved |
| Same acquisition repeated | snapshot-service `DESTINATION_EXISTS` | prior snapshots unchanged |

Existing accepted snapshots are never replaced; a post-success failing rerun leaves the accepted
directory byte-identical (tested).

## Licence note

The manifest records `licence_id="OGL"` because the WebTRIS privacy-policy statement names the
Open Government Licence without a version. In accordance with the accepted Gate-A audit, the
attribution also retains the provider statement, logo exclusion, and the
[official OGL v3.0 URI](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
This records the observed provider wording and its reviewed licence-text reference without
inventing a separate licence blocker.

## Test evidence

`tests/unit/test_manchester_webtris_acquisition.py` (18 tests, all offline via
`httpx.MockTransport` and injected deterministic clocks): exact allowlisted request and typed
query for all three products; host/path/URL/free-query/date-string injection refusal and absence
of any blanket warning switch; deterministic pagination and stable receipts across runs;
quarantine-before-parse interception proof; successful promotion with boundary labels and no
freshness fields; code-specific warning admission and refusal in both directions; page and
total-byte bounds; typed transport failure preserving accepted snapshots byte-identically;
malformed JSON, pagination drift, and schema drift; hash mutation detection and repeat-publication
refusal; replay relabelling refusal (product/site/date/synthetic) and broken page-inventory
refusal; historical/strategic-road/timezone and quality-as-availability boundaries; sockets
disabled during replay with deterministic fingerprints; and official-fixture replay for all three
products with pinned SHA-256 values and no download.

Validation commands (run 2026-07-22): the focused pytest file, the full
`tests/unit/test_manchester_*.py` suite, `ruff check`/`ruff format --check`, and strict `mypy`
over the two owned Python files, plus `git diff --check` — all passing at handoff.

## Residual blockers

- `GA-WT-1` keeps WebTRIS report timestamps out of UTC projection.
- `GA-WT-3` keeps monthly and annual report surfaces unavailable because their report-type enums
  are not formally documented.
- `GA-WT-5` records that no API rate-limit statement was found; acquisition therefore retains its
  conservative self-imposed request and retry bounds.
- The official Gate-B daily fixture closes `GA-WT-2` for the supported daily parser surface only.
- No real-network acceptance run was performed; the announced 2026 WebTRIS interruption makes
  the lead's early real-fixture capture advice in the Gate A audit stand.
- MAN-01 v1 stores one `http` metadata block per snapshot (first response); page identity, bytes,
  and hashes cover the rest of the inventory.
- `MAN-01` and `MAN-03` remain `planned`; exports, generated schemas, and documentation are now
  reconciled, but real-source acquisition acceptance still gates any capability claim.

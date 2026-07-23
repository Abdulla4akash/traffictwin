# DfT Manchester Road-Count Adapter Library (MAN-02 candidate)

Status: **candidate Gate B library evidence — `MAN-01` and `MAN-02` remain `planned`**

`traffictwin.integration.manchester.dft` is the pure, offline parsing half of the MAN-02 DfT
historical road-count adapter. It consumes exact raw bytes plus snapshot/member lineage produced
by the candidate MAN-01 quarantine/snapshot boundary
([snapshot service](manchester_snapshot_service.md),
[transport boundary](manchester_transport_boundary.md)) and emits strict typed records, findings,
and deterministic reports. It performs no network access, no snapshot publication, no freshness
labelling beyond `historical`, and no SUMO demand conversion.

## Audited source contract implemented

Exactly the Gate A contract in
[the Gate A audit](manchester-source-gate-a-audit-v0_7.md) §2 (official API documentation, the
official "Road Traffic Statistics Metadata" PDF, and live anonymous samples, all accessed
2026-07-22):

- Host `roadtraffic.dft.gov.uk`; endpoints `/api/raw-counts`, `/api/count-points`,
  `/api/average-annual-daily-flow`.
- Pagination envelope: `current_page`, `per_page`, `total`, `last_page`, `data`, plus the audited
  optional keys (`from`, `to`, `path`, page URLs, `links`). Any other envelope key is schema
  drift and rejects the member. Envelope URL values are never persisted.
- Raw-count rows: the exact audited field set — identity/time/scope fields required non-null;
  descriptive road fields, coordinates, link lengths, and the thirteen vehicle-class columns
  nullable (null = suppressed/missing, never zero).
- Count-point rows and AADF rows: the exact observed field sets, as separate record families.
  AADF rows additionally require `id`, `estimation_method`, and
  `estimation_method_detailed`. The official API documentation and the retained minimal fixture
  both carry `id`; its absence is schema drift.
- Codes: `direction_of_travel` ∈ {N, S, E, W, C}; `road_category` ∈
  {PM, PA, TM, TA, M, MB, MCU}; `road_type` ∈ {Major, Minor}.

## Evidence semantics enforced

- **Historical only.** Every record carries `evidence_status="historical"`; nothing in this
  module can produce a live or near-live label.
- **ADR-055 time bases.** `count_date` is a calendar date; `hour` is a 0–23 local clock-hour
  label with `time_basis="local_clock_hour"`; no UTC instant is ever fabricated while `GA-DFT-1`
  (undocumented timezone) is open. AADF records carry `time_basis="date_only"`.
- **No speed.** The audited schema has no measured-speed field; records carry
  `measured_speed_available: Literal[False]`, and a row containing a speed-like extra field is
  rejected as `UNEXPECTED_FIELD`. Speed is never derived from road class or limits.
- **Survey ≠ AADF.** Raw survey counts and AADF statistics are separate strict record types with
  disjoint required fields; each family's rows are structurally rejected by the other parser,
  and AADF records carry `statistical_not_survey: Literal[True]`.
- **No demand conversion.** Nothing here maps counts to SUMO vehicle generation; that remains
  MAN-09's separately gated workflow.
- **Total reconciliation.** When all components are present, `all_hgvs` must equal the sum of
  the six audited HGV columns and `all_motor_vehicles` must equal the motor-class sum
  (`two_wheeled + cars_and_taxis + buses_and_coaches + lgvs + all_hgvs`); mismatches are
  `INCONSISTENT_*_TOTAL` errors. The identity follows the audited metadata-PDF class hierarchy
  and was reconfirmed against the retained real raw-count and AADF rows. Any null component makes
  reconciliation unavailable (`COUNTS_INCOMPLETE` warning), never assumed.

## Scope enforcement

`DftManchesterScope` fixes both identifiers as literals: ONS code `E08000003` and DfT
`local_authority_id=85`. The official DfT local-authorities response binds these values to
Manchester; a caller cannot substitute another authority or provide self-authored binding text.
Rows carrying any other identifier are refused as `OUT_OF_SCOPE_RECORD` errors with exact
exclusion counts.

## Determinism and fail-closed behaviour

- Reports, records, and findings are canonically ordered; page input order never changes the
  report fingerprint (tested).
- Pagination is reconciled: exact page set 1..`last_page`, consistent `per_page`/`total`/
  `last_page`, and combined row count equal to `total`; anything else is an error finding.
- Identical duplicate rows (same identity key, identical content ignoring row locator and
  envelope `id`) collapse to one with a `DUPLICATE_ROW` warning; conflicting rows sharing an
  identity key are all excluded with a `CONFLICTING_DUPLICATE` error. Revisions therefore never
  silently overwrite within one parse; cross-snapshot revision tracking stays with the snapshot
  `supersedes` relation.
- Any error finding makes the report `rejected`; downstream consumers must check `status` before
  using `records`. Complete accounting (`rows_seen`, accepted, malformed, out-of-scope,
  conflicting, duplicates collapsed, incomplete-count records) is always published.
- Caller-side misuse (no members, duplicate members, oversized member, member bytes that do not
  match the declared snapshot SHA-256) raises typed `DftAdapterError` — broken lineage is never
  parsed.

## Lineage

Every record embeds its `DftMemberRef` (snapshot id, member path, member SHA-256, synthetic
flag). Member bytes are re-hashed against the declared snapshot hash before any parsing. A parse
run must use one snapshot and one evidence class; mixing snapshot IDs or synthetic and real
members is refused before decoding.

## Fixtures

Most tests use clearly labelled synthetic rows. Three minimal exact response bodies are retained
as base64 under `tests/fixtures/manchester/dft/`: raw count `43177`, count point `6046`, and AADF
`9219`, all for Manchester count point `6046`. They were fetched from the official unauthenticated
API on 2026-07-22 and are covered by the Crown copyright/Open Government Licence v3.0 attribution
recorded beside the fixtures. Their decoded SHA-256 values are pinned and tested. They are schema
evidence only, not representative data or dissertation results.

## Residual points after the minimal real-source probe

1. Confirm nullability across a deliberately selected bounded sample; the current nullable set is
   a conservative fail-closed contract and the three minimal rows are all complete.
2. `GA-DFT-1` (hour timezone) remains open; hour values stay local clock labels.
3. The controlled acquisition and accepted-replay path has passed the exact three-row real-source
   probe recorded in [the Gate-B probe report](manchester_dft_gate_b_probe.md), but full Manchester
   bulk/load acceptance and the common MAN-01 integrating gate remain open.

## Test evidence

`tests/unit/test_manchester_dft.py` (36 tests): valid raw-count/count-point/AADF parsing;
deterministic fingerprints and page-order independence; Manchester-scope refusal; survey/AADF
family separation; structural speed unavailability; exact HGV and motor-total reconciliation;
null/missing-field behaviour; malformed date/hour/year refusal; identical-duplicate collapse and
conflicting-duplicate rejection; unexpected row and envelope fields; pagination contract;
lineage preservation and hash-mismatch refusal; mixed-snapshot/evidence-class refusal; strict JSON
constant handling; exact official-fixture hashes and parsing; typed caller-misuse errors; no
network access during parsing (socket disabled); and explicit synthetic labels.

Focused validation commands (run 2026-07-22):

```bash
.venv/bin/python -m pytest tests/unit/test_manchester_dft.py
.venv/bin/ruff check src/traffictwin/integration/manchester/dft.py tests/unit/test_manchester_dft.py
.venv/bin/ruff format --check src/traffictwin/integration/manchester/dft.py tests/unit/test_manchester_dft.py
.venv/bin/mypy src/traffictwin/integration/manchester/dft.py tests/unit/test_manchester_dft.py
```

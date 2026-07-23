# WebTRIS Strategic-Road Adapter (MAN-03 candidate)

Status: **candidate Gate-B parsing evidence; `MAN-03` remains `planned`**

`traffictwin.integration.manchester.webtris` is a pure offline parser for immutable National
Highways WebTRIS snapshot members. It supports one active scope only: a complete one-site,
one-day `daily` report, its site reference, and its daily availability response. It performs no
network access, source acquisition, freshness calculation, UTC conversion, Manchester boundary
admission, SUMO conversion, or UI rendering.

## Frozen official contract

The Gate-A audit left the exact daily speed-bin spelling blocked as `GA-WT-2`. A bounded official
Gate-B fixture captured on 2026-07-22 closes that parser blocker for the daily report surface:

- API host `webtris.nationalhighways.co.uk`, version `v1.0`;
- site response fields `Id`, `Name`, `Description`, `Longitude`, `Latitude`, `Status`;
- daily envelope `Header` plus `Rows`, with header fields `row_count`, `start_date`, `end_date`,
  and `links`;
- report identity fields `Site Name`, `Report Date`, `Time Period Ending`, `Time Interval`;
- length bins `0 - 520 cm`, `521 - 660 cm`, `661 - 1160 cm`, `1160+ cm`;
- speed bins `0 - 10 mph`, `11 - 15 mph`, `16 - 20 mph`, `21 - 25 mph`,
  `26 - 30 mph`, `31 - 35 mph`, `36 - 40 mph`, `41 - 45 mph`, `46 - 50 mph`,
  `51 - 55 mph`, `56 - 60 mph`, `61 - 70 mph`, `71 - 80 mph`, `80+ mph`;
- `Avg mph` and `Total Volume`; and
- quality envelope `row_count` plus `Qualities`, whose rows contain `Date` and `Quality`.

Any additional, absent, or renamed row field is schema drift. Monthly and annual reports remain
unavailable because `GA-WT-3` is unresolved; the adapter does not extrapolate this daily schema to
them.

## Evidence semantics

- WebTRIS is National Highways strategic-road evidence, not city-road coverage.
- The source normally publishes about a month in arrears. Every parsed artifact is `historical`;
  retrieval time never promotes it to live or near-live.
- `Report Date` and `Time Period Ending` are preserved verbatim with
  `time_basis="source_string_undeclared"`. Their timezone is undocumented (`GA-WT-1`), so the
  model exposes no UTC timestamp.
- `Time Interval` must form the exact set `0..95` for the admitted one-day report. The nominal
  interval is 900 seconds, but irregular source clock strings are preserved rather than repaired.
- Empty strings become null/missing, never zero. A completely empty source interval remains an
  explicit record with `measurement_state="missing"` and a typed warning.
- Average speed retains original mph and adds deterministic m/s using exactly
  `mph × 0.44704`. No speed is inferred when `Avg mph` is empty.
- Daily `Quality` is the source data-availability percentage. It is structurally prevented from
  becoming a sensor-accuracy or traffic-validity claim.

## Reconciliation and source anomalies

When all four length bins are present, the adapter compares their sum with `Total Volume`. It does
the same for all fourteen speed bins when they are complete. A mismatch preserves every original
value, sets the corresponding reconciliation flag to `false`, and emits a warning. It does not
silently correct or discard source evidence.

The retained official report contains one such observation at interval `82`: the four length bins
sum to `415`, while WebTRIS publishes `Total Volume=414`. This is fixture-backed source evidence,
not a TrafficTwin calculation error. Consumers can exclude or sensitivity-test this row using the
published flag.

## Lineage and failure behaviour

Every input is re-hashed before JSON decoding. A parse run refuses changed bytes, duplicate pages,
mixed snapshot IDs, mixed synthetic/real evidence, incorrect member roles, oversized members, and
non-standard JSON constants. Multi-page input order does not affect canonical output. Reports are
rejected for incomplete interval sets, duplicate intervals, scope/date mismatches, malformed
values, or schema drift.

This module does not follow or persist pagination URLs from source envelopes. Controlled HTTP
acquisition must be implemented separately through the MAN-01 transport/quarantine boundary.

## Retained fixtures

`tests/fixtures/manchester/webtris/` contains exact base64-encoded official responses for active
site `34` (`M56/8150A`), its complete 2026-03-01 daily report, and daily quality `89`. Decoded
SHA-256 hashes, access date, OGL basis, and limitations are recorded beside the files. They are
minimal schema evidence, not representative Manchester traffic data or dissertation results.

The announced three-to-six-month 2026 WebTRIS service interruption remains an operational
limitation. A future acquisition service must preserve the last accepted snapshot and represent a
long outage as unavailable/stale rather than replacing evidence.

## Current integration and remaining acceptance work

The allowlisted WebTRIS acquisition, MAN-01 quarantine-before-parse, atomic promotion, offline
replay, source-specific freshness policy, package exports, generated schemas, and documentation
reconciliation are now implemented as candidate evidence. The daily official fixture closes
`GA-WT-2` for this exact parser surface.

Remaining work:

1. Run and record the controlled real-network Gate-B acquisition acceptance case.
2. Publish the explicit selected-site scope artifact used by the candidate MAN-07 spatial gate;
   an M56 label alone makes no Greater Manchester boundary or network-scope claim.
3. Wire service-notice/cache freshness decisions into the Manchester Operations source card while
   preserving unavailable/stale labels.
4. Keep UTC/sub-day cross-source alignment blocked until `GA-WT-1` is resolved.
5. Keep monthly/annual reports unavailable under `GA-WT-3`, and retain conservative acquisition
   bounds while `GA-WT-5` records the absence of a published rate-limit policy.

`MAN-03` therefore remains planned even though its daily offline parser has real-fixture evidence.

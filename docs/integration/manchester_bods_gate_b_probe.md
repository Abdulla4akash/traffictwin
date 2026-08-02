# BODS real-source Gate-B probe — 23 July 2026

Status: **controlled real-source vertical slice passed; complete Gate B and `MAN-05` remain
planned**

This record contains only safe metadata and aggregate counts. The API key, raw vehicle
identifiers, response body, accepted raw member, and derived position records are excluded from
Git and remain in the configured private v0.7 workspace.

## Request and evidence identity

- Source: DfT Bus Open Data Service SIRI-VM datafeed.
- Trigger: one explicit foreground operator action; no background polling.
- Request scope: `-2.7304178,53.3273147,-1.9096224,53.6857188` in WGS84. This is an operator
  request rectangle derived for Greater Manchester discovery, not an accepted administrative
  boundary and not evidence of Bee Network membership.
- Snapshot: `bods_siri_vm-20260723T223908Z-33e07061a500`.
- Raw fingerprint:
  `33e07061a500f19c1be5d1cd24f9094b12f0734b6b8edf74f0650c5a2cfed4f7`.
- Transport: HTTP 200, `text/xml`, `gzip`, one network request, no redirect.
- Preserved wire member: 254,732 bytes; bounded decoded parser payload: 2,012,972 bytes.
- Credential route: transient process argument loaded from the local macOS Keychain; only the
  redacted parameter name `api_key` is persisted.

## Result

- Activities seen and accepted: 1,565; malformed, out-of-scope, duplicate, and conflicting: 0.
- Freshness at the bound retrieval instant: 304 `live_vehicle`, 1,261 `stale`.
- Published private local scene: `manchester/scenes/live_vehicles.json`, 3,879,674 bytes, with
  separate live and stale layers.
- Raw `VehicleRef` values did not enter receipts, logs, the summary, or this record. Derived scene
  identities remain snapshot-scoped pseudonyms and public export remains unavailable.

## Observed profile variance

The official guidance describes `Bearing`, `BlockRef`, and direct `VehicleJourneyRef` as mandatory.
The central response instead contained:

- 836 accepted positions without `Bearing`;
- 25 accepted positions without `BlockRef`; and
- 1,553 accepted positions using `FramedVehicleJourneyRef/DatedVehicleJourneyRef` rather than a
  direct `VehicleJourneyRef`.

TrafficTwin does not invent the missing values. Optional output fields remain `None`, the framed
identity retains an explicit source label, and the parser report emits aggregate warning codes and
counts. This is usable current bus-position evidence with visible source-quality limitations, not
proof that every publisher conforms to the profile.

## Acceptance boundary

The probe proves the fixed authenticated transport, secret redaction, immutable raw preservation,
bounded gzip decoding, hardened XML parsing, freshness classification, privacy-safe spatial/map
projection, and atomic local scene publication against one real response. A later aggregate-only
[Bee Network scope probe](manchester_bee_network_scope.md) uses this exact accepted snapshot to
verify five operator references without exposing private rows. It does not close:

- pending `BNVB`, complete Bee Network service/fleet coverage, or `GA-BEE-2`–`GA-BEE-4`;
- `GA-BODS-4` and the legal/governance part of design §18.2 (identifier persistence,
  longitudinal use, backup/secure-erasure, and publication approval). A separate precautionary
  local control now previews 24-hour/240-family cleanup and requires exact confirmation, but it
  does not resolve those external terms;
- `GA-BODS-3` (general consumer rate limits); Phase 185 subsequently documented API account/email
  registration and closed `GA-BODS-6` as a source fact; or
- complete Gate-B, browser/accessibility, outage, longitudinal-retention, and release acceptance.

Accordingly, the live slice works locally while `MAN-01`, `MAN-05`, `MAN-07`, and `MAN-08` remain
`planned` in capability truth.

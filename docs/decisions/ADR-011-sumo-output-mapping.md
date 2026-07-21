# ADR-011: Import-Only SUMO Output Mapping

Status: accepted

## Context

TrafficTwin v0.5 `ING-01` requires an evidenced Eclipse SUMO output adapter for `tripinfo.xml` and
`summary.xml`, a legally reusable public validation scenario, immutable raw inputs, stable
validation codes, and no implied simulator-launch support. The official SUMO 1.27 documentation
and XML schemas establish the relevant field meanings, but TrafficTwin's existing canonical
traffic `count` is used as an interval count. SUMO summary `running` is an instantaneous network
occupancy and must not be silently relabelled as that count.

## Decision

- Admit a directory only when `sumo-source.yaml` declares scenario URL, SUMO version, source
  commit when known, SPDX licence, retrieval date, redistribution status, run metadata, and exact
  SHA-256 checksums for `tripinfo.xml` and `summary.xml`.
- Validate adapter version 1 against SUMO `1.27.x`. Other versions remain rejected until their
  output contract is tested.
- Map a SUMO `tripinfo` ID to both `TripRecord.trip_id` and `vehicle_id` unchanged.
- Map non-negative departure times. A completed record requires non-negative arrival, no
  vaporisation reason, and duration equal to arrival minus departure.
- Preserve departed unfinished/vaporised vehicles as incomplete canonical trips with no canonical
  arrival or duration. Keep SUMO's reported elapsed duration in `SumoTripObservation` only.
- Keep never-departed records source-only because the canonical model requires a real departure
  timestamp.
- Parse documented summary attributes into `SumoSummaryStep`. Do not map `running` into canonical
  traffic `count`; present summary steps as source-specific replay evidence.
- Treat `source_row` for mapped XML records as the one-based `tripinfo` element ordinal, not a
  physical text line number.
- Reject DTD/entity declarations, malformed XML, unsafe paths, symlinks, duplicate IDs, checksum
  drift, unsupported roots, invalid values, and non-monotonic summary time.
- Keep FCD, person/container canonicalisation, direct launch, asynchronous launch, and scenario
  controls unavailable.

## Consequences

- Existing deterministic trip metrics can run over supported canonical records.
- Summary charts remain useful without creating a false traffic-flow metric.
- The raw XML is authoritative, fingerprinted, and never rewritten.
- Registry import is idempotent by result-bundle fingerprint and stores the canonical metric
  collection only after accepted validation.
- Supporting another SUMO minor contract or FCD requires an explicit later decision and tests.

## Acceptance Evidence

- Official Eclipse SUMO `tools/game/square` scenario at tag `v1_27_1`, commit
  `7717f2379d9e314a0c81c5cec748444de06a2a91`.
- Generated `tripinfo.xml` and `summary.xml` retain Eclipse SUMO licence notices and have checksums
  recorded in `tests/fixtures/sumo/square_public/sumo-source.yaml`.
- Unit, integration, CLI, registry-idempotency, raw-immutability, XML-safety, metric, and UI-service
  tests.

## Alternatives Considered

- Map summary `running` to canonical traffic `count`: rejected because occupancy snapshots are not
  interval flow counts and `traffic.count.total` would become misleading.
- Drop all unfinished vehicles: rejected because it would inflate completion rate.
- Use reported unfinished duration as completed journey time: rejected because it is elapsed time
  at simulation termination, not arrival duration.
- Add FCD heuristically: rejected because v0.5 requires an explicit mapping and persistent-ID/unit
  decisions first.

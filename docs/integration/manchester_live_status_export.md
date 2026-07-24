# Metadata-only Manchester live-status export

Manchester Operations can locally download `manchester-live-status.json`, a deterministic
projection of the local BODS and National Highways control states. It is useful for a reviewed
private supervisor handoff or operational audit without including position or response data.

The export contains only:

- generation, last-attempt, and latest-success UTC timestamps;
- exact source state (`never_attempted`, `in_progress`, `succeeded`, or failed, with cached-success
  distinctions retained);
- aggregate BODS accepted/live/stale/synthetic record counts;
- aggregate National Highways closure/restriction/VMS record counts;
- source scope, evidence meaning, and required attribution; and
- explicit availability/refusal flags.

The schema makes raw payloads, coordinates, identifiers, credentials, the Bee Network reference
table, public position export, and public live-scene hosting unrepresentable. It also refuses claims
of complete Manchester coverage, complete Bee Network coverage, continuous city-road telemetry,
live signal phases, or an external basemap. BODS aggregate counts must reconcile exactly, source
identity and metric inventories are fixed, and all timestamps must be UTC.

This **metadata** artifact is locally downloadable; that does not accept public metadata hosting or
permission to redistribute either provider's raw data. The export says a licence/terms recheck is
required before any hosted service is proposed. The private local snapshot and scene boundaries
remain unchanged.

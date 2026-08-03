# Manchester Source Health

Phase 196 implements the bounded `NEXT-06` read-only Source Health route. It answers whether the
local BODS and National Highways workers are configured, running, degraded or stopped, using only
the verified durable-workspace preflight, accepted control summaries, process-local worker status
and aggregate operational-journal integrity.

The Overview page rerenders this local projection every 30 seconds. It does not fetch either
provider, test a credential, repair or delete a file, start or stop a worker, calculate scientific
evidence, or approve retention, licensing, identifiers, publication or public hosting. A missing
credential is `not_configured`, not a source outage. A malformed control or journal remains an
explicit invalid/degraded state.

Each source card shows its evidence role, declared scope, configured presence, request-scope state,
process state, conservative TrafficTwin interval, last accepted local attempt/success, locally next
eligible time, aggregate-history counts/integrity and exact display-safe blocker codes. The
provider quota stays `unknown`; the local interval is never presented as the provider limit. BODS
source time is `unavailable` because its accepted hot-control summary does not retain that field.

The metadata download is allowlisted. It contains no credential value, length, hash or prefix;
request-box coordinates or fingerprint; machine/workspace handle or path; raw source row; vehicle,
operator, event or detector identifier; or public-hosting permission. Primary page state is
expressed in text as well as badges, so colour is not the only signal.

Run the page only through a verified durable workspace configured by
[the local real-workspace profile](../v07_real_workspace_run.md). Use Manchester Operations for
source actions. Long-term journal activation still requires the separate owner policy described in
[aggregate operational history](manchester_operational_history.md).

See the [canonical v0.7 design](../traffictwin-design-v0_7.md#277-next-06--read-only-source-health-page).

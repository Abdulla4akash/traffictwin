# Controlled BODS refresh and aggregate history

Status: **candidate MAN-05/MAN-08 operational control — both capabilities remain `planned`**

`traffictwin.integration.manchester.bods_live_control` wraps the BODS fetch-to-scene workflow with
conservative local coordination. It prevents accidental request bursts, serialises refreshes, and
retains a small private history of already-computed aggregate summaries. A configured local
Streamlit process may invoke the same boundary automatically; ordinary UI reruns never fetch.

## Fixed policy

- One source refresh at a time, enforced by an OS-backed non-blocking local file lock that is
  released automatically if the process exits.
- At least 60 seconds between attempted source requests.
- At most 240 successful aggregate summaries and at most 24 hours of history.
- One process-local worker may request a refresh every 60 seconds while Streamlit is running.
- The worker requires a validated v0.7 workspace, environment-only `BODS_API_KEY`, and an explicit
  `TRAFFICTWIN_BODS_BOUNDING_BOX`; `off` disables it and 60–300 seconds is the accepted range.
- Manual refresh remains available and shares the same lock and minimum interval.
- No remote scheduler, automatic deletion, or retry burst.
- No API key, response body, raw position, vehicle token, `VehicleRef`, or private path in state.
- Private local state only; public export remains unavailable.

The 60-second interval is deliberately more conservative than the ten-second consumer cache noted
by the Gate-A audit because a general BODS rate-limit contract remains unavailable. It is an
engineering protection, not a statement of the provider's quota.

## State transition

Before transport, the coordinator validates the v0.7 workspace and canonical state, obtains the
single-refresh lock, checks the last-attempt interval, and atomically records `in_progress`. A
successful existing BODS workflow adds its secret-free `BodsLiveRefreshSummary` to bounded
history. A typed failure increments failure accounting and preserves the most recent successful
summary. A process interruption leaves an auditable in-progress attempt that is counted as failed
when a later allowed attempt begins.

The state file is canonical JSON at `manchester/live/bods-refresh-state.json`, mode `0600`, with a
2 MiB hard bound. Reload validation reconciles lifetime attempts/successes/failures, bounded
history size/order/uniqueness, latest-success identity, failure-code presence, and UTC timestamps.
Mutation, symlinks, non-canonical JSON, clock regression, concurrent refresh, and too-soon refresh
all fail closed before another source request.

The server worker and Manchester page's **Refresh bus positions now** fallback both use this
coordinator. The page renders the bounded aggregate history locally. One point is shown as a
status; two or more points enable a chart for
verified Bee Network buses, other/unknown buses, live positions, and stale records. The chart says
transit positions and never general road traffic.

On every local display, `project_bods_live_scene_for_display` re-evaluates each non-synthetic BODS
layer from its preserved source `RecordedAtTime`/`ValidUntilTime` at an explicit current UTC
instant. A position that was live when acquired therefore becomes **stale cached** after its
freshness window expires; the derived display scene, layer title, filter state, warning, and stale
badge all agree. The immutable stored scene is not rewritten. Synthetic scenes remain synthetic
regardless of wall-clock age.

Offline tests in `tests/unit/test_manchester_bods_live_control.py` and
`tests/unit/test_manchester_bods_auto_refresh.py` use synthetic HTTP fixtures to
prove success persistence, credential/raw-ID absence, pre-transport interval refusal, safe failure
accounting, concurrency refusal, mutation detection, side-effect-free empty state, live-to-stale
display projection, synthetic-state preservation, explicit scope validation, idempotent worker
startup, and automatic-trigger receipts.

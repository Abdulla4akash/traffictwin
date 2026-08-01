# Design — Controlled live-twin adapter (post-v1 L-1)

**Status: PROPOSED optional post-v1 design; owner review pending, unimplemented and not approved for
build. Maximum policy ceiling: `owner_approved_candidate`. "Live" means an owner-attended,
process-backed SUMO session with controlled state exchange. It does not mean a live city
replica, production traffic control, continuous sensor synchronisation or authority to run
an experiment.**

## 1. Purpose

Meeting 3 described a what-if interface backed by SUMO. The v1 composer deliberately stops
at a prediction and reviewable campaign draft; execution remains behind human approval and
the existing instrument. This optional adapter would add a tightly bounded interactive
engineering session for observing a running simulation and, if separately approved,
applying allowlisted scenario changes.

The adapter is not needed for v1. It should be considered only after the dashboard,
[scenario/run registry](scenario_run_registry_design.md) and decision guardrails are stable.

## 2. Non-negotiable boundary

- Owner-attended foreground process only; no daemon, public endpoint or unattended queue.
- Exact reviewed network/scenario, seed, tool versions and resource budget are bound before
  startup.
- No arbitrary shell, Python, TraCI command or filesystem path from a UI.
- Default mode is observe-only. Mutating commands require a separate owner-approved
  allowlist and exact scenario approval.
- Closing the UI stops or detaches according to an owner-selected fail-safe policy and emits
  a terminal receipt.
- The adapter does not modify the campaign instrument, admission chain or VEC-10 boundary.

TraCI controls traffic-simulation state. It must not be described as directly changing VEC
RSU compute capacity unless a reviewed integration model explicitly maps such a scenario to
the compute simulator. Traffic capacity, signal control and RSU compute capacity are
different variables.

## 3. Session modes

### 3.1 Observe-only (first deliverable)

Start a pinned simulation, subscribe to an allowlist of aggregate variables and emit
rate-limited `TwinSnapshot` records: simulation time, aggregate vehicle count, mean speed,
queue indicators and session health where supported. No vehicle identifiers leave the
adapter; the UI receives aggregates.

### 3.2 Controlled intervention (separate opt-in)

Only after owner approval, accept a versioned allowlist such as pause/resume, simulation
step and predeclared signal-program or demand-scenario selection. Each command carries a
scenario digest, expected current state, monotonic sequence and actor class. Commands that
change scientific treatment after a run begins invalidate experiment use and record a
deviation.

## 4. Startup, runtime and shutdown

`LiveTwinSessionSpec` binds network/scenario digests, toolchain versions, seed, mode,
allowlist, maximum simulation duration, wall-clock/runtime budget and output policy.
Startup performs the existing compatibility and provenance checks before spawning a
process. The process uses a private ephemeral control port and an argument vector, never a
shell string.

Runtime is a single state machine: `prepared -> running -> stopping -> completed/refused`.
Exactly one controller owns a session. A heartbeat timeout, protocol mismatch, unexpected
process exit or budget breach triggers fail-safe stop and a typed receipt.

The terminal `LiveTwinReceipt` records intended/observed configuration, start/end times,
tool versions, command ledger digest, aggregate-output digests, resource use, deviations and
exit status. It contains no private path, credential or raw identity.

## 5. Relationship to evidence

An interactive session is an engineering demonstration by default: `evidence: false`.
Scientific use requires a separate frozen protocol, accepted human approval, unmodified
instrument boundary and admission decision. The adapter never labels a session validated,
causal, ground truth or production-ready.

No current BODS session is fed directly into SUMO by this design. A real-time data-to-twin
bridge would require a new data contract, licence/privacy review, temporal alignment study
and owner decision.

## 6. API

Minimum backend surface:

- `prepare_session(spec) -> PreparedSession | LiveTwinRefusal`
- `start_session(prepared_digest) -> SessionHandle | LiveTwinRefusal`
- `read_snapshot(handle) -> TwinSnapshot | LiveTwinRefusal`
- `apply_command(handle, command) -> CommandReceipt | LiveTwinRefusal`
- `stop_session(handle, reason) -> LiveTwinReceipt`

The dashboard receives only opaque handles and aggregate snapshots. It cannot supply an
executable, port, path or free-form command.

## 7. Typed refusals

At minimum: `OWNER_PRESENCE_REQUIRED`, `APPROVAL_MISSING`, `DIGEST_MISMATCH`,
`TOOL_VERSION_MISMATCH`, `RESOURCE_BUDGET_MISSING`, `SESSION_ALREADY_OWNED`,
`COMMAND_NOT_ALLOWLISTED`, `STATE_SEQUENCE_MISMATCH`, `CONTROL_PROTOCOL_LOST`,
`BUDGET_EXCEEDED`, `SCIENTIFIC_USE_UNAUTHORISED` and `PRIVATE_CONTENT_DETECTED`.

## 8. Verification and acceptance

Tests use a deterministic fake control process first, then a pinned local SUMO smoke test
where available. They cover argument-vector construction, port isolation, state transitions,
single-owner locking, allowlist enforcement, stale command rejection, heartbeat loss,
budget stop, process cleanup, aggregate-only snapshots and receipts after every terminal
path. No network acquisition or experiment campaign runs in tests.

Acceptance requires observe-only mode before mutation, zero arbitrary command surface,
deterministic terminal receipts, bounded cleanup, explicit engineering-only labelling and
no change to existing evidence/admission records.

## 9. Owner decisions and stop conditions

The owner must explicitly decide whether to build this optional slice, observe-only versus
mutation scope, approved variables/commands, session budgets and fail-safe shutdown policy.
Stop if safe implementation would need unattended execution, public control access, live
BODS ingestion, an unfrozen intervention, new cloud compute, or a relaxation of VEC-10.

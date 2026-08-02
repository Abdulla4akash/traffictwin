# Design — Controlled live-twin adapter (post-v1 L-1)

**Status: IMPLEMENTED in Phase 168 as maximum-coverage backend contracts and a deterministic fake
control adapter; Phase 176 added the first concrete bounded local-SUMO/TraCI process transport over
the pinned repository-owned synthetic square scenario. Delivered modes are observe-only,
unattended closed-loop simulation and preauthorised operator-site closed loop; supporting contracts
cover authenticated public access,
local SUMO, GCP/AWS scheduling, aggregate BODS updates, plugins, streams/webhooks, command/cost
budgets and terminal receipts. One foreground local SUMO 1.27.1 engineering smoke ran for five
simulated seconds; no live BODS request, public service, cloud allocation or real-road actuation was
executed. Public/cloud/operator transports still require deployment-supplied accounts, endpoints,
credentials and operator authority. Maximum policy ceiling:
`owner_approved_candidate`; receipts create no scientific evidence or production certification.**

## 1. Purpose and coverage

The adapter provides a single typed control plane for local/fake simulation, local SUMO, scheduled
cloud simulation and operator-authorised infrastructure. It supports lifecycle, scenario,
vehicle/route policy, incidents, signals, speeds, lanes, road capacity, RSU compute capacity,
actors, observation/action/reward contracts, seed namespaces, budgets, metrics, streams/webhooks,
recommendations, defaults, instruction drafts, sweeps, replay/checkpoints, fault injection and
digest-pinned plugins.

Capability does not manufacture deployment inputs. This repository can validate a supplied cloud
or operator policy, but it does not create an account, credential, endpoint, spending authority or
site-control authority.

## 2. Session modes and backends

`LiveTwinSessionSpec` binds the complete mode, backend, access surface and budget before startup:

- `observe_only` accepts aggregate snapshots and no commands;
- `simulation_closed_loop` accepts exact allowlisted simulation/platform commands and may run
  attended or unattended on a fake, local SUMO, GCP Batch or AWS Batch adapter; and
- `operator_site_closed_loop` accepts allowlisted real-infrastructure commands only when exact
  operator authority and operator-policy digests are bound.

Backends are `local_fake`, `local_sumo`, `gcp_batch`, `aws_batch` and `operator_site`. Access is by
`local_library`, `cloud_scheduler` or `authenticated_public_api`. Public access requires TLS,
authentication, signed requests, roles, age bounds and idempotency in `PublicApiPolicy`.
`AuthenticatedControlAdapter` is the backend authorization boundary; a web framework/transport is
not started by this phase.

Unattended operation does not require per-command human approval when the exact session command
allowlist and authority policy already preauthorise it. Heartbeat, wall-clock, simulation-time,
command-count and estimated-cost limits remain mandatory.

## 3. Aggregate BODS bridge

`BodsBridgePolicy` permits unattended inputs without a separate self-imposed request rate while
requiring compliance with the upstream provider's policy, `Retry-After` and exponential backoff.
It binds terms, licence and aggregate-schema digests and a staleness ceiling. It requires
`raw_bytes_retained: false` and `identifiers_retained: false`.

`AggregateMobilityUpdate` accepts only aggregate vehicle count, speed, queue, incident and route
demand fields plus a source-receipt digest. Updates are sequenced, schema-bound and idempotent;
stale, changed or identity-bearing updates refuse. Phase 168 used synthetic updates only and
contains no downloader or credential.

## 4. Command model

`CommandGrant` binds a command kind and surface. `TwinCommand` additionally binds the session
digest, monotonic sequence, idempotency key, expected state, target, typed parameter keys, estimated
cost and whether it changes a scientific treatment. Real-infrastructure commands also bind the
session's operator-authority digest.

The allowlist includes:

- pause/resume/step and lifecycle support;
- signal programs, speed limits, lane open/close, incidents and route/demand policy;
- explicitly separate `set_road_capacity` (`road_traffic`) and
  `set_rsu_compute_capacity` (`rsu_compute`) commands;
- actor family and observation/action/reward/seed contracts;
- scenario revisions, budgets, checkpoints/restores, sweeps and fault injection;
- recommendation publication, owner-default selection and application of a digest-bound
  instruction draft; and
- digest-bound plugin invocation.

There is no arbitrary shell, executable, script, path or request-provided plugin code. Treatment
changes become immutable deviations and invalidate scientific use of the engineering receipt.

## 5. State, locking, events and shutdown

The state machine is `prepared -> running <-> paused -> stopping -> completed/refused`. An exact
spec digest has one process-local controller owner. Commands and aggregate updates are idempotent;
changed retries refuse. Heartbeat/protocol loss, wall/simulation/command/cost budget breach,
private output or stale live input triggers fail-safe termination and a terminal receipt.

`TwinSnapshot` exposes only approved aggregate fields. `EventSubscription` covers session,
snapshot, command, mobility, heartbeat and terminal events through local streams or authenticated
webhook bindings; payloads are digests rather than raw data. Delivery failures become deviations.

`LiveTwinReceipt` records command/update counts, ledger digest, estimated cost, deviations and
whether the injected process reported an external effect. It always states:

- `evidence: false`;
- `scientific_use: false`;
- `production_ready: false`; and
- `execution_authority_created: false`.

An operator adapter may report a real external effect only when deployment supplied the authority;
the fake used by tests reports no external effect except in an explicit receipt-path simulation.

## 6. Cloud and plugin contracts

`CloudExecutionPolicy` binds GCP or AWS, external account-scope digest, region allowlist, maximum
instances and cost authority. The provider must match the selected backend and the session budget
cannot exceed the supplied external authority. The model does not allocate a resource or spend.

`PluginContract` binds id, content digest, kind and command grants and forbids arbitrary
request-provided code. Plugin kinds cover traffic/vehicle-edge models, controllers, metrics and
event sinks. Actual plugin loading remains an injected adapter responsibility.

## 7. Typed refusals

Implemented refusal paths include `SESSION_ALREADY_OWNED`, `DIGEST_MISMATCH`,
`COMMAND_NOT_ALLOWLISTED`, `STATE_SEQUENCE_MISMATCH`, `IDEMPOTENCY_CONFLICT`,
`AUTHORITY_MISSING`, `AUTHENTICATION_FAILED`, `REQUEST_EXPIRED`, `CONTROL_PROTOCOL_LOST`,
`BUDGET_EXCEEDED`, `PLUGIN_NOT_ALLOWLISTED`, `BODS_BRIDGE_NOT_CONFIGURED`, `LIVE_INPUT_STALE`,
`BACKEND_MISMATCH`, `PUBLIC_API_NOT_CONFIGURED`, `SCIENTIFIC_USE_UNAUTHORISED` and
`PRIVATE_CONTENT_DETECTED`. Pydantic model refusals cover inconsistent backends, unbound public or
operator modes, command/capacity conflation, undeclared treatment change and arbitrary parameters.

## 8. Verification and acceptance

Phase-168 tests use a deterministic in-process fake. They cover every mode/policy family, process-local
single ownership, heartbeat and budget stops, snapshot privacy, separate road/RSU capacity domains,
sequenced/idempotent commands, pause/resume, treatment deviations, plugin and command allowlists,
operator authority, fake external-effect receipts, authenticated public requests, aggregate BODS
idempotency/staleness/privacy, webhook event digests, scientific-use refusal and bounded SUMO argv.

Phase 176 adds injected crash/protocol/privacy/cleanup tests and one runtime-gated loopback TraCI
smoke over the exact pinned synthetic square. That smoke launches only the locally installed SUMO
1.27.1 process, advances 0→5 simulated seconds and returns an engineering-only receipt. No test
fetches BODS, opens a public socket, contacts a cloud provider, spends money, executes a scientific
campaign or actuates infrastructure.

## 9. Owner decisions and deployment inputs

On 2 August 2026 the owner selected maximum coverage: unattended operation, closed loop, public
authenticated access, cloud orchestration and preauthorised operator-site control are enabled by
the contracts above without per-command human approval. Activation still requires concrete inputs
that code cannot invent: BODS access/licence configuration, GCP/AWS account scope and funded budget,
public authentication/TLS deployment, and operator endpoint/authority/site policy. Supplying those
inputs and choosing to start an external adapter are separate deployment actions; none occurred in
Phase 168. Phase 176 supplies only the local-SUMO process input using the already pinned repository
fixture and locally installed supported runtime; it does not reduce or satisfy any BODS, public,
cloud or operator deployment input above.

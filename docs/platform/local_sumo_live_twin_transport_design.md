# Design — Concrete local-SUMO live-twin transport

**Status: IMPLEMENTED IN PHASE 176. The transport is a bounded local engineering
adapter beneath the Phase-168 `ControlProcess` contract. It uses only the repository-owned pinned
`synthetic_square_smoke` scenario, a supported SUMO 1.27.x binary discovered on `PATH`, and the
matching local TraCI tools. It creates no scientific evidence, production readiness, deployment
authority or real-road effect.**

## 1. Purpose and boundary

Phase 168 deliberately stopped at deterministic fakes. This slice supplies the first real process
transport while retaining the existing `LiveTwinController` as the sole lifecycle, ownership,
idempotency, sequencing, heartbeat, budget, deviation and terminal-receipt authority. The process
transport implements that existing protocol; it does not fork a second session model or receipt.

Only the original TrafficTwin synthetic-square input inventory already pinned by the controlled
SUMO runner is admissible. The adapter revalidates every source byte and stages copies in a private
temporary workspace before startup. The repository inputs are never writable by SUMO and are
revalidated during health checks and shutdown. There is no caller-supplied executable, scenario,
configuration, working directory, module, flag, environment variable or port.

## 2. Read-only preparation and runtime binding

A strict path-free preparation record binds:

- the exact live-twin session-spec digest;
- the pinned preset, preset fingerprint, network digest and complete input inventory;
- the supported SUMO version and executable digest;
- the exact local command-policy digest, simulation window, seed and output bound; and
- a receipt-safe argv whose executable is represented only as `sumo`.

Preparation requires backend `local_sumo`, local-library access, mode `observe_only` or
`simulation_closed_loop`, seed 42, the exact preset/network digests, the discovered runtime version
plus the transport version, executable digest and command-policy digest in `tool_versions`, bounded
wall/simulation/command budgets, no BODS/cloud/public/operator policy, and simulation-only grants
from the implemented local command subset. This makes the existing terminal receipt's spec digest
bind the complete local transport preparation. The accepted executable is
resolved from the `sumo` PATH entry, must be a regular file, and its version/digest are checked
again immediately before launch. Matching TraCI Python tools must resolve beneath the same SUMO
installation; arbitrary import roots refuse.

## 3. Process, heartbeat and cleanup

The real launcher uses one fixed tuple argv, `shell=False`, a controlled environment, local
loopback TraCI, a new process group and a bounded combined-output collector. It starts in a staged
copy of the pinned scenario and remains foreground-owned by the controller: there is no detach,
daemon or surviving process handle. Connection failure, early exit, output overflow, input drift,
heartbeat failure or protocol exception makes health false; the controller then terminates the
process and emits its existing `refused` engineering receipt.

Shutdown is idempotent. It closes TraCI, requests process-group termination, escalates after the
fixed grace bound, drains the bounded collector, verifies input identities, and removes only the
private staged workspace. Startup failures follow the same cleanup path. No repository, registry,
evidence or workspace artifact is written.

## 4. Aggregate snapshots and privacy

TraCI may inspect synthetic vehicle ids transiently to calculate aggregates, but ids never cross
the transport boundary. A snapshot contains only simulation time, aggregate vehicle count, mean
speed, queue indicator, incident count and session health. The existing controller applies its
allowlist and private-marker guard again. No raw TraCI response, route membership, vehicle id,
position, trip, private path, stdout/stderr text or credential enters a snapshot, command receipt
or terminal receipt. Missing aggregate support is unavailable, never zero-filled as evidence.

## 5. Closed-loop command mapping

The transport maps only existing simulation-surface grants:

- `pause` and `resume` retain the controller state; SUMO advances only on explicit steps;
- `step` advances a bounded positive number of simulation steps;
- `set_signal_program` selects a program on an inventory-verified signal id;
- `set_speed_limit` applies a bounded speed to an inventory-verified edge or lane;
- `close_lane` and `open_lane` apply/clear the fixed synthetic passenger-class restriction;
- `inject_incident` and `clear_incident` apply/restore a bounded synthetic edge-speed incident;
- `set_route_demand` adds a bounded number of synthetic vehicles to an inventory-verified route;
  and
- `set_vehicle_route_policy` applies an allowlisted route policy to the current synthetic fleet
  without returning identities.

Targets and parameter keys/ranges are fixed by a strict command policy and reconciled with the
live TraCI inventory at connection. Unsupported grants refuse during preparation; changed targets,
unallowlisted programs/policies, invalid ranges and protocol failures refuse before a successful
command receipt. Treatment commands remain deviations and invalidate experiment use through the
unchanged controller. Road-capacity and RSU-compute-capacity commands are deliberately unsupported:
lane/edge traffic operations do not represent VEC compute capacity.

## 6. Verification and residuals

Deterministic injected tests cover preparation, fixed argv, runtime/input/tool binding, lifecycle,
aggregate snapshots, every command family, inventory and parameter refusals, sequence/idempotency,
single ownership, command/time/resource budgets, private output, bounded-output overflow, process
crash, heartbeat/protocol loss, connection timeout, escalation and workspace cleanup. Source scans
pin no shell, public client, cloud SDK, BODS adapter or persistence surface.

When the supported pinned runtime and matching TraCI tools are locally available, one bounded
synthetic smoke starts the real process, reads aggregates, steps, stops and inspects the existing
engineering-only receipt. That smoke is local implementation evidence only: it is not Manchester
traffic, Randy/VEC evidence, a scientific campaign, real-world validation, production certification
or authority for any external system.

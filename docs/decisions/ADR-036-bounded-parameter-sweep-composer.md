# ADR-036 — Bounded Deterministic Parameter-Sweep Composer

Status: accepted and implemented
Date: 20 July 2026
Capability: `EXP-01`

## Context

TrafficTwin can author strict scenario seeds, create labelled deterministic synthetic bundles,
validate completed bundles, and compute ordinary metrics. Researchers also need to inspect how
outcomes vary across declared parameters. A generic dotted-path editor would bypass schema
semantics, while a loop that appeared to run Randy, VEC, or SUMO would contradict the import-first
boundary. An unbounded Cartesian product could also create an accidental workload explosion.

Response-surface rows must retain the exact parameters and source bundle that produced them.
Missing, mapping-valued, or invalid metrics cannot be converted to numeric zero merely to fit a
table.

## Decision

TrafficTwin adds version 1.0 `ParameterSweepRequest`, `ParameterSweepExpansion`,
`ParameterSweepPoint`, `ExternalRunRequest`, `SweepResponseRow`, and `ParameterSweepResult`
artifacts. The composer accepts exactly one strict base: `SyntheticScenarioConfig` or
`ScenarioSeed`.

The v1 catalogue is closed. Synthetic axes include duration, sampling interval, vehicle count,
task-arrival rate, RSU count/capacity, network delay, congestion multiplier, policy profile, trip
count, and random seed. Seed axes include demand and birth-rate multipliers, fleet/RSU counts,
policy label, random seed, and declared event closure/duration/demand fields. Mix, placement,
failure-list, incident-list, arbitrary nested, and unknown fields are rejected. Every derived
snapshot is validated through its ordinary Pydantic schema before any destination is replaced.

The public bounds are four axes, 16 unique finite scalar values per axis, 256 complete Cartesian
points, and 16 selected core response metrics. Axis and value order define deterministic product
order. Request, base, point, seed, bundle, and result fingerprints record identity independently
of generation time.

Every path also has a published type/range or enumeration bound. Before local materialisation the
composer sums the exact row counts implied by the current deterministic generator configuration
(tasks, time-indexed vehicle/infrastructure/traffic rows, trips, and incidents) and rejects a
complete sweep above 2,000,000 declared rows. This is an engineering admission limit, not a memory
or performance claim.

Three modes are distinct:

- `seed_snapshots` writes derived, parent-linked seeds only;
- `local_synthetic_bundles` invokes only TrafficTwin's labelled deterministic synthetic generator,
  ordinary bundle validator, and ordinary core metric engine; and
- `external_run_requests` writes seed and coordination artifacts whose status is always
  `not_executed`, `direct_launch_supported` is false, and launcher/command are null.

The composer never runs Randy, VEC/TOS, SUMO, training, or another external simulator. Returned
external outputs must re-enter through ordinary validation and import.

Local response rows use the selected ordinary core metrics. Finite numeric available/partial
values enter `response_value`. Unavailable and invalid results retain their status/reason codes.
An otherwise available mapping, string, boolean, or non-finite result becomes an explicit
response-table unavailable/invalid state, never zero. Seed-only and external modes emit an empty
response surface and state that no local analysis occurred.

Materialisation uses a temporary sibling directory and replaces the exact requested destination
only after every point succeeds and only when overwrite was explicit. Raw inputs and the base
model are never mutated. Empty, symbolic-link, current-directory, home-directory, filesystem-root,
and current/home ancestor destinations are rejected before expansion. Every derived point is
labelled `synthetic_evaluation=true`, even when
the base is an imported/authored seed, because the grid point is controlled evaluation evidence.

## Consequences

- A researcher can produce reproducible parameter/metric tables without manual nested loops.
- A request artifact cannot be mistaken for proof that an external simulator ran.
- Closed paths exclude coupled mix fields until a separate validity-preserving operator exists.
- Complete-grid limits are checked before filesystem mutation.
- Per-value and complete local-row bounds prevent a small grid from hiding an extreme generated
  workload.
- Response CSV rows carry the full axis values plus seed and bundle fingerprints.
- External orchestration remains out of scope; the output is a coordination request, not a queue.

## Rejected Alternatives

- **Arbitrary JSONPath mutation:** bypasses typed semantics and admits unsupported fields.
- **Infer external launch commands:** no evidenced Randy/VEC/SUMO launcher contract exists.
- **Treat request creation as execution:** metadata does not prove producer behavior.
- **Unbounded grids or silent truncation:** either risks resource exhaustion or changes the
  declared design without consent.
- **Flatten mapping metrics:** invents a response dimension not declared by the researcher.
- **Replace unavailable values with zero:** violates the unavailable-is-not-zero policy.
- **Mutate the base bundle in place:** breaks raw/source immutability and parent provenance.
- **Calculate metrics in CLI or Streamlit:** duplicates the scientific implementation outside the
  tested library layer.

## Acceptance Evidence

- Unit tests pin Cartesian order, fingerprints, base immutability, bounds, duplicate/incompatible
  axes, invalid derived-point rejection, overwrite behavior, and YAML round trips.
- Local integration tests validate every generated bundle and numeric response row through the
  ordinary metric engine; mapping-valued responses remain explicitly unavailable.
- External-mode tests prove there is no bundle, launcher, command, or executed status.
- Golden JSON/CSV fixtures pin two exact response points, values, and provenance fingerprints.
- CLI tests cover the public method contract, local materialisation, and destination conflicts.
- UI service and Streamlit AppTest coverage prove the page delegates composition and calculation
  to the library and renders the no-launch boundary.
- Generated schemas, CLI help, method contract, capability manifest, architecture, status, usage,
  assumptions, open decisions, and limitations are reconciled.

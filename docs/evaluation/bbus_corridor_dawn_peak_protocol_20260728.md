# B-BUS Oxford Road Corridor Dawn-to-Peak — APPROVED SUCCESSOR PROTOCOL

**Status:** owner-approved successor, with the geographic and mechanical details frozen by
the primary research/integration agent before inspecting any corridor count or outcome.
This is a candidate experiment, not VEC-06 admission, actor admission, a supervisor signature,
publication permission, or a scientific verdict.

- Protocol date: 28 July 2026
- Experiment ID: `B-BUS-CORRIDOR-DAWN-PEAK-20260728`
- Parent experiment: `B-BUS-DAWN-PEAK-20260728`
- Train/evaluate split: captured dawn session for training; captured peak session once for
  held-out evaluation
- Acquisition or attendance: none

## 1. Owner decision and delegated technical freeze

After the parent experiment derived both whole-fleet traces and refused at full-coverage
placement, its result record presented two numbered successors. The owner answered
`cant we do both 1 and 2`. This protocol is successor 1. The owner selected the experiment;
the agent did not take that owner decision.

The fixed corridor is not selected from bus positions. It is a **750 m closed capsule** in
EPSG:27700 around the straight line between the two public landmark probes already frozen in
`network_scope.py` and ADR-059:

| Endpoint | WGS84 longitude, latitude | EPSG:27700 easting, northing |
|---|---|---|
| St Peter's Square | `-2.244600, 53.477900` | `383863.597181, 397936.133916` |
| University of Manchester, Oxford Road campus | `-2.233900, 53.466800` | `384569.687684, 396698.832727` |

An active derived position is inside iff its Euclidean distance to the closed projected line
segment is at most `750.0 m`. Endpoint discs are included. The CRS transform is
`pyproj`/PROJ with `always_xy=True`; the projected constants above are authoritative for this
experiment so a later library update cannot move the scope. The capsule is a constructed
study envelope, not an administrative boundary, an observed bus corridor, or evidence about
every Oxford Road service.

The agent froze 750 m because the resulting geometric envelope is bounded enough for the
existing 2,000-cell placement safety limit by design while including the named road spine and
nearby streets. No bus count, cell count, coverage result, or learning outcome was inspected
to choose or tune that width.

## 2. Trace transformation and accounting

The input bytes are exactly the two successful private parent motion traces named in the
aggregate parent receipt. There is no rematching, rerouting, new interpolation, altered speed
rule, vehicle selection, or time-window selection.

For each session independently:

1. evaluate every active parent vehicle-second against the frozen capsule;
2. retain in-capsule seconds and set every other source cell inactive;
3. split each pseudonymous occupancy span into maximal contiguous retained runs;
4. repack those runs deterministically into the first free dense slot, sorting by start second,
   session token and source slot; and
5. verify that the new occupancy spans reconstruct the new mask cell-for-cell.

Every source active vehicle-second is accounted as retained or excluded. The whole dawn and
peak time axes remain unchanged. An empty second is valid; an empty session, a non-finite active
value, a mask/occupancy mismatch, an unaccounted source cell, or any output containing a raw
identifier or salt is a refusal. Session tokens remain unlinkable between sessions and private.

## 3. Full-coverage placement gate

The pinned producer script `eval/place_rsus_cover.py`, sha256
`33928f4113988ee39f75ff06d99f2c01061182f9d0f17092e051a159a42840a0`, is run separately
on the dawn and peak corridor traces with its accepted values: 500 m radius, 50 m cells and
at most 64 generated analysis sites. The input must contain at most 2,000 occupied cells.
The script's exact raw-point verification must report 100% vehicle-second coverage.

This per-session placement is intentional and predeclared: the question is motion transfer
between time windows under the same placement rule, not transfer of one physical RSU estate.
Peak placement may configure only peak infrastructure; peak motion, counts, placement or
metrics may not enter training, checkpoint selection, stopping or hyperparameter choice.

Passing this gate makes the trace **VEC-06 placement-contract compatible**. It does not create
a VEC-06 receipt: the source is a derived bus scenario rather than the accepted FCD builder
path, and the rebuilt network remains reviewed but not accepted for real matching. If either
session exceeds a bound or lacks full coverage, this arm refuses; the capsule is not narrowed,
the radius/site limits are not raised and no favourable subwindow is substituted.

## 4. GPU campaign

All parent Phase-107 settings remain binding: producer trace-replay MAPPO Model-C; seeds
`30,31,32,33,34`; dawn-only training; a requested 5,000,000 environment steps; one frozen
actor per seed; one held-out peak evaluation at capacity per active slot `0.75` and `2.5`
under common random keys; GPU required and CPU fallback refused. Memory-driven vectorisation
may be reduced once, before the first seed, while preserving effective steps and every
scientific setting. The resulting common runtime configuration is recorded.

The primary metric remains equal-weight mean held-out peak deadline-completion share at 0.75.
The parent secondary metrics and publishable null remain unchanged. Training diagnostics have
no standing as the primary result. A failed or weak peak result is reported, never repaired by
training on peak or changing this scope.

## 5. Privacy and claim ceiling

Only the derived, pseudonymised allowlist from the parent protocol may enter the owner's private
Colab. Raw BODS material, raw identifiers, salts, snapshot/quarantine references, private local
paths and cross-session links remain forbidden. Public hosting is unauthorised.

Any conclusion is limited to this constructed capsule, these two one-day bus windows, this
trajectory policy, task generator, placement rule and five seeds. It cannot establish a causal
rush-hour effect, same-vehicle change, observed FCD, real-RSU performance, all Oxford Road
services, general Manchester traffic, cross-day generalisation, or actor admission.


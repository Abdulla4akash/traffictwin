# Capacity-Squeeze Pilot — Exploratory Results (27 July 2026)

**Status: exploratory `owner_approved_candidate` evidence from the predeclared pilot. No
confirmatory or significance claim is made; the pilot's predeclaration committed to publishing
this outcome with equal prominence before any run existed, and this record honours that.**

- Design: [pilot predeclaration](capacity_squeeze_pilot_predeclaration.md), approved by owner
  delegation 26 July 2026; design fingerprint
  `de474e038523e5e79e2d167364f312dc7c2ea273e610f2d26ec1cf253f41bb90`
- Execution: approval-gated campaign (ADR-063), **12/12 cells executed and admitted, zero
  failures, zero skips**, 12.47 hours total compute (cells 3,534.6–3,846.7 s), 1.17 GB of
  hash-verified outputs, every cell admitted through fresh-run admission (ADR-061)
- Analysis artifacts: `data/vec-fresh/capacity-pilot/campaign_analysis.{json,md}` (the
  markdown carries the three full STA-01 study reports as appendices)
- Scenario provenance (per the producer's sidecar, read 27 July 2026): the `inc` trace is
  **Friday 2024-03-15, 20:00–21:00 — a documented reactive-rule VSL-collapse hour** on the
  Manchester **Etihad/Co-op Live event-district network** (Lourenço-calibrated demand,
  SUMO 1.27.0, trace seed 43). All scope language below means that district, not Manchester
  generally.

## Design executed

Four capacity arms (`--rsu-cap-per-veh` 2.5 baseline / 1.5 / 1.0 / 0.75) × three common fleet
seeds {0, 1, 2}, actor `ukfleettrain_mappo_model_c_17`, fleet preset `uk2030`, full 3,600-step
trace per cell. Primary endpoint, fixed before execution: `tos.task.deadline_success.rate`
(maximise). Pairing on `fleet_seed`.

## Findings (exploratory)

**1. The hypothesised degradation cliff does not exist.** Mean deadline-success rate is flat
across the 3.3× squeeze — 0.790412 / 0.790522 / 0.790591 / 0.790737 by descending capacity —
with each *reduction* in capacity associated with a faint *rise* (+0.000110, +0.000069,
+0.000146 per adjacent step). The three predeclared paired comparisons give mean paired
differences of +0.000111 / +0.000180 / +0.000325 with bootstrap intervals [0.000000, 0.000332]
/ [0.000000, 0.000539] / [0.000000, 0.000694] and randomisation diagnostics of 1.0 / 1.0 /
0.5 (three pairs; diagnostics reported verbatim, never as acceptance). **The predeclared null
holds: on this collapse-hour trace, capacity squeeze did not reduce deadline attainment.**

**2. Mean task latency collapses monotonically, 3.2×.** 9,798.8 → 6,029.6 → 4,089.9 →
3,083.6 ms by descending capacity, with per-arm ranges that do not overlap between adjacent
arms at any seed. A tighter per-vehicle concurrency bound shortens effective queues for the
same deadline outcomes.

**3. The mechanism is visible: the policy is capacity-invariant.** Offload rates are
bit-identical across all four capacities within every seed (0.402608 / 0.406349 / 0.414181 by
seed), and the no-eligible-target rate is constant (~0.0024%). The trained actor's decisions
never respond to the capacity control; only the queueing outcomes downstream of its unchanged
choices differ.

## One-sentence framing (descriptive, non-causal)

During a modeled traffic-collapse hour in the Etihad event district, tightening per-vehicle
edge capacity 3.3× left deadline attainment unchanged (~79.1%) while cutting mean task
latency by two-thirds — because the trained offloading policy's decisions are
capacity-invariant.

## Consequences for the predeclared programme

- The confirmatory protocol's **knee rule selects nothing** (no adjacent-step drop exists);
  its predeclared fallback fork is now an owner decision at signing, recorded with these
  measured numbers in [the confirmatory draft](capacity_confirmatory_protocol_draft.md):
  confirm the null descriptively on the held-out seeds, or declare `task.latency.mean_ms`
  the confirmatory primary before any held-out data exists.
- Held-out seeds {10–14} remain untouched and structurally unauthorised.
- The pilot's numbers are exploratory context forever; they are never pooled into any
  confirmatory estimate.

## Limitations (binding)

One actor, one fleet preset, one reviewed trace (a deliberately anomalous collapse hour),
three seeds, uncorrected shared-baseline multiplicity, per-padded-vehicle concurrency
semantics for the capacity control, deadline success ≠ physical completion, and
`owner_approved_candidate` status throughout — not supervisor-approved, not validated, not
causal, not generalisable beyond the studied grid.

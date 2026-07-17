# TrafficTwin Open Questions

This register separates questions that block implementation from questions that affect later dissertation framing or optional features.

## Questions For Abdulla

Answered before Phase 1:

- `diss/` is the permanent TrafficTwin project root.
- The v0.4 design document is canonical at `diss/docs/traffictwin-design-v0_4.md`.
- Git should be initialised inside `diss/`.
- Phase 1 should proceed with package and CLI name `traffictwin`.
- Streamlit and other UI work remain out of scope until the later UI phase.

Open:

1. Should Phase 4 Streamlit pages use only bundle paths during the first UI slice, or should they require a registry workflow from the start?
2. Which Phase 3 metric subset should be most prominent in the first Run Overview page?

Resolved during Phase 3:

- Saturation threshold is held in `MetricEngineConfig` and documented as synthetic-demo configuration.
- Synthetic expected metric outputs are stored as JSON golden projections under `tests/golden/expected/`.

## Questions For Dr. Sandra Sampaio

1. Confirm the actual dissertation submission date and interim milestone dates.
2. Confirm whether TrafficTwin should lead with OffloadLens, the journey-time lens, or the dual-lens platform framing.
3. Confirm whether the C1 plus C2 framing, platform plus portfolio/selector, is appropriate for dissertation scale.
4. Confirm whether formal participant evaluation is required for dissertation evidence.
5. If formal evaluation is required, confirm survey versus semi-structured interview and whether business-school contacts may participate.
6. Confirm whether the earlier XITS note to wait for `MATERIALS COMPLETE` is also superseded for dissertation planning, not only for implementation.
7. Confirm whether Manchester is only the first case study or should constrain the implementation choices more strongly.
8. Confirm whether the digital-twin term should be qualified as replay-and-scenario digital twin in the dissertation.

## Questions For Randy

1. Can the VEC/SUMO environment be invoked headlessly through a CLI, script, or Python API?
2. If yes, what exact command or API accepts scenario seed parameters?
3. What is the expected wall-clock duration for one lightweight run and one SUMO validation run?
4. Can one complete run bundle be supplied with header rows and units?
5. Which files are exported today: task logs, RSU logs, vehicle traces, traffic observations, trip outputs, incident/event records, or something else?
6. Are per-RSU queue length, utilisation, arrivals, completions, drops, and capacity exported over time?
7. Are task arrival time, completion time, latency, deadline, deadline-met flag, decision, target, class, vehicle tier, data size, workload, energy, and drop reason exported?
8. Are trip departure and arrival times available from SUMO output?
9. Which units are used for time, speed, distance, data size, workload, energy, queue length, and utilisation?
10. Are task IDs unique across a run?
11. Are decision values represented as `local`, `v2i`, and `v2v`, or with different labels?
12. How are V2I and V2V decision targets represented?
13. Does the environment support varying demand, task birth rate, class mix, task ordering, vehicle count, vehicle tier mix, RSU count, RSU capacity, RSU placement, RSU failure, and decision toggles?
14. Are environment version, Git commit, algorithm, checkpoint, random seed, and training budget recorded in run outputs?
15. Is sensor-to-SUMO scenario generation shareable?
16. Does the VEC environment consume arbitrary FCD/network files or only prepared scenes?
17. Are there existing plotting or metric scripts that should be reused rather than reimplemented?

## Implementation Blockers

- Real adapters require sample files and schema evidence.
- Direct launch requires a documented invocation contract.
- Metrics using energy, drop causes, queue-clearance time, or capacity-normalised load require source columns and units.
- R1-R3 thresholds require synthetic calibration first and real calibration only after representative data is supplied.
- UI controls must remain unavailable or unknown until adapter capabilities are evidenced.
- Phase 2 generic CSV validation can proceed with synthetic fixtures, but real Randy compatibility remains blocked on sample files.
- Phase 3 can compute deterministic metrics on synthetic fixtures, but real-world interpretation remains blocked on Randy/SUMO evidence.

## Non-Blocking Unknowns

- Exact design of later portfolio selection.
- Later use of DuckDB or Polars.
- Optional language rendering.
- Optional XAI instrumentation.
- Near-live or true-live data sources.

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

1. Which exact thresholds should R1-R3 use for dissertation evaluation, and should they remain synthetic-demo defaults until real evidence exists?
2. Which rule outputs should be included in dissertation screenshots?
3. Should R3 experiment-level evidence be represented as a first-class aggregation EvidencePack in Phase 6?
4. What evidence is needed before R1 can use a T1-by-low-tier cross-tab rather than the current lower-confidence proxy?
5. What evidence is needed before R2 can evaluate temporal overlap between saturation windows and task misses?
6. Can a real or sanitised Randy/SUMO sample set be supplied for Phase 6B, and which files may be committed as fixtures?
7. Should Phase 6B start with Randy/VEC logs, SUMO trip/FCD outputs, or a combined standard TrafficTwin bundle once artifacts are supplied?
8. Should future metric results store full contributing canonical-record references for selected aggregates, or is bounded source-row sampling sufficient for the dissertation demo?

Resolved during Phase 3:

- Saturation threshold is held in `MetricEngineConfig` and documented as synthetic-demo configuration.
- Synthetic expected metric outputs are stored as JSON golden projections under `tests/golden/expected/`.

Resolved during Phase 4:

- The first UI supports both direct bundle paths and optional registry-backed imports.
- Run Overview prioritises task completion, incomplete rate, deadline-miss rate, latency, and offload metrics.
- The Streamlit launch command is documented rather than adding a Typer wrapper.

Resolved during Phase 5:

- The UI page is now `Evidence & Diagnostic Hypotheses`.
- Diagnostic rules are deterministic code over EvidencePacks only.
- R3 returns `insufficient_evidence` for ordinary single-run bundles.

Resolved during Phase 6A:

- No real Randy/VEC or SUMO artifacts are present in the inspected workspace.
- Phase 6B adapter implementation is blocked until schemas, units, source samples, and execution contracts are supplied.

Resolved during documentation pass:

- Documentation reference artifacts are generated from code under `docs/reference/generated/`.
- Automated screenshots are not produced; a manual screenshot checklist is documented instead.

Resolved during Provenance Explorer productisation:

- Provenance is read-only and does not recompute metrics or reinterpret rules.
- Aggregate metric traces show eligible rows and bounded samples rather than fabricated per-row
  contribution weights.
- EvidencePack-only fault-injection traces mark source-row links unavailable unless a bundle exists.

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

1. Can one complete real or sanitised output directory be supplied from a single validation run?
2. For every supplied file, what are the header rows, field meanings, units, missing-value conventions, and timestamp conventions?
3. Does the sample represent training, lightweight validation, SUMO validation, scenario configuration, or post-processed summaries?
4. Can the VEC/SUMO environment be invoked headlessly through a CLI, script, or Python API?
5. If yes, what exact command or API accepts scenario seed parameters?
6. What is the expected wall-clock duration for one lightweight run and one SUMO validation run?
7. Which files are exported today: task logs, RSU logs, vehicle traces, traffic observations, trip outputs, incident/event records, or something else?
8. Are per-RSU queue length, utilisation, arrivals, completions, drops, and capacity exported over time?
9. Are task arrival time, completion time, latency, deadline, deadline-met flag, decision, target, class, vehicle tier, data size, workload, energy, and drop reason exported?
10. Are SUMO `.sumocfg`, network, route, FCD, tripinfo, detector, queue, or summary outputs available?
11. Which units are used for time, speed, distance, data size, workload, energy, queue length, capacity, and utilisation?
12. Are task IDs unique across a run?
13. Are decision values represented as `local`, `v2i`, and `v2v`, or with different labels?
14. How are V2I and V2V decision targets represented?
15. Does the environment support varying demand, task birth rate, class mix, task ordering, vehicle count, vehicle tier mix, RSU count, RSU capacity, RSU placement, RSU failure, and decision toggles?
16. Are environment version, Git commit, algorithm, checkpoint, random seed, and training budget recorded in run outputs?
17. Is sensor-to-SUMO scenario generation shareable?
18. Does the VEC environment consume arbitrary FCD/network files or only prepared scenes?
19. Are there existing plotting or metric scripts that should be reused or reconciled rather than reimplemented?
20. Which real or sanitised artifacts may be committed to the repository as fixtures, and which must remain private?

## Implementation Blockers

- Real adapters require sample files and schema evidence.
- Direct launch requires a documented invocation contract.
- Metrics using energy, drop causes, queue-clearance time, or capacity-normalised load require source columns and units.
- R1-R3 thresholds require synthetic calibration first and real calibration only after representative data is supplied.
- R1 direct low-tier/T1 evidence requires vehicle-tier and task-class cross-tab evidence.
- R2 temporal-overlap evidence requires windowed or event-level task and infrastructure evidence in the EvidencePack.
- UI controls must remain unavailable or unknown until adapter capabilities are evidenced.
- Phase 2 generic CSV validation can proceed with synthetic fixtures, but real Randy compatibility remains blocked on sample files.
- Phase 3 can compute deterministic metrics on synthetic fixtures, but real-world interpretation remains blocked on Randy/SUMO evidence.
- Phase 6B adapter implementation is blocked on real or sanitised Randy/SUMO artifacts, units, schemas, provenance, and invocation contracts.
- Documentation is now broad enough for supervisor review, but dissertation claims still require real integration, literature verification, and any formal evaluation evidence.
- Exact row-level contribution lists for aggregate metrics remain a future design choice; current
  provenance provides aggregate-level traceability and source-row samples.

## Non-Blocking Unknowns

- Exact design of later portfolio selection.
- Later use of DuckDB or Polars.
- Optional language rendering.
- Optional XAI instrumentation.
- Near-live or true-live data sources.

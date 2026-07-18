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
6. Which files from Randy's `TOS Data` package may be committed as small sanitised fixtures?
7. Should Phase 6B start with an offline converter for one matched instrumented showcase run before broader campaign import?
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

- The original repository did not contain real Randy/VEC or SUMO artifacts.
- Randy has now supplied an external `TOS Data` package with real evaluation summaries, instrumented NPZ outputs, traces, and training records.
- Phase 6B adapter implementation remains blocked until specific field semantics, units, fixture permissions, and execution contracts are supplied.

Resolved during documentation pass:

- Documentation reference artifacts are generated from code under `docs/reference/generated/`.
- Automated screenshots are not produced; a manual screenshot checklist is documented instead.

Resolved during Provenance Explorer productisation:

- Provenance is read-only and does not recompute metrics or reinterpret rules.
- Aggregate metric traces show eligible rows and bounded samples rather than fabricated per-row
  contribution weights.
- EvidencePack-only fault-injection traces mark source-row links unavailable unless a bundle exists.

Resolved during Standalone Product phase:

- TrafficTwin can be demonstrated without Randy/VEC, SUMO, external services, or live data.
- Standalone scenarios are generated as ordinary run bundles and imported through the Phase 2
  registry path.
- Synthetic policy profiles use `synthetic-*` labels and do not impersonate real trained
  algorithms.
- Report export is deterministic Markdown/HTML and does not use an LLM.
- The one-click demo launcher initialises the workspace if absent and starts Streamlit with
  explicit workspace environment variables.

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

1. What is the exact integer encoding for `instrumented/pertask/*: task_type`?
2. Does `task_met` mean completed by deadline, physically completed, or only deadline success?
3. Does `task_lat_ms` include backlog values for deadline missers, and should missed tasks be treated as incomplete in TrafficTwin?
4. What is the denominator and intended range for `rsu_busy_ms`; can it be converted to utilisation fraction as `busy_ms / (dt * 1000)`?
5. What exactly does `rsu_load` represent: queue length, active tasks, workload, capacity use, or another quantity?
6. What units are used for trace `pos_x`, `pos_y`, `speed`, and `rsu_xy`?
7. Is vehicle slot index stable enough to use as a vehicle ID within each trace?
8. Is per-vehicle tier available in any file, array, or source code output?
9. Are action availability, link quality, V2I target, or V2V target available anywhere?
10. Are trip/journey-time outputs available outside the `TOS Data` package?
11. Are SUMO `.sumocfg`, network, route, detector, queue, FCD XML, summary, or `tripinfo` outputs available if needed?
12. Can the separate `vec_env` source repository or its `docs/REPRODUCING.md` be shared for execution-contract discovery?
13. Which exact command or API produced the existing `TOS Data` outputs?
14. Which scenario controls are genuinely configurable without editing environment code?
15. Which small files may be committed to TrafficTwin as sanitised real-schema fixtures, and which must remain private?

## Implementation Blockers

- Real adapters require sample files and schema evidence.
- Direct launch requires a documented invocation contract.
- Metrics using energy, drop causes, queue-clearance time, or capacity-normalised load require source columns and units.
- R1-R3 thresholds require synthetic calibration first and real calibration only after representative data is supplied.
- R1 direct low-tier/T1 evidence requires vehicle-tier and task-class cross-tab evidence.
- R2 temporal-overlap evidence requires windowed or event-level task and infrastructure evidence in the EvidencePack.
- UI controls must remain unavailable or unknown until adapter capabilities are evidenced.
- Phase 2 generic CSV validation can proceed with synthetic fixtures, but real Randy compatibility needs an adapter because the supplied lower-level files are NPZ/JSON, not standard bundle CSV.
- Phase 3 can compute deterministic metrics on synthetic fixtures, but real-world interpretation remains blocked on confirmed Randy/SUMO mapping and expert review.
- Phase 6B adapter implementation is blocked on remaining Randy field semantics, source units, fixture permission, and invocation contracts.
- Documentation is now broad enough for supervisor review, but dissertation claims still require real integration, literature verification, and any formal evaluation evidence.
- Exact row-level contribution lists for aggregate metrics remain a future design choice; current
  provenance provides aggregate-level traceability and source-row samples.
- Real integration remains the next blocker for moving beyond synthetic demonstration.
- A project licence still needs explicit selection before public release.
- Product Polish improves workflow but does not resolve Randy's remaining field/unit/execution-contract blockers.

## Non-Blocking Unknowns

- Exact design of later portfolio selection.
- Later use of DuckDB or Polars.
- Optional language rendering.
- Optional XAI instrumentation.
- Near-live or true-live data sources.
- Persistent multi-user settings or authentication.
- Richer UI screenshot automation.

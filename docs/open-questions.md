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
7. After Randy supplies producer/writer/checkpoint evidence and fixture permission, should the next
   increment trial one sanitised source-specific conversion?
8. Should future metric results store full contributing canonical-record references for selected aggregates, or is bounded source-row sampling sufficient for the dissertation demo?
9. May aggregate values from Randy's package be included in a publicly hosted static atlas, or
   only in private supervisor/dissertation materials?

Implemented while these questions remain open:

- a synthetic-only public static dashboard that contains no Randy-derived values;
- a private checksummed TOS supervisor pack;
- a public TOS atlas command that refuses to stage without explicit permission attestation;
- machine-readable readiness gates that keep all unrelated technical blockers intact.

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
- Evaluation summaries and instrumented NPZ schemas are sufficient for a conservative read-only
  integration without interpreting RSU fields.
- Vehicle array slots are time-local padded indices, not safe persistent vehicle IDs.
- The read-only integration now validates/imports summaries, exposes replay/task samples, and
  produces partial evidence and aggregate provenance.
- Randy later supplied `vec_env`; source inspection confirmed task/action codes, deadlines, trace
  units, RSU active-task/backlog/capacity meanings, scenario-control mechanisms, and the evaluator
  CLI.
- The source evaluator is not yet a TrafficTwin launcher because checkpoints, instrumented writer,
  portable paths, and local runtime verification are absent.

Resolved during TOS Results Workbench productisation:

- All 300 source-summary rows can be explored as a campaign/cell matrix without canonicalising
  absent task records.
- Campaign comparison pairs exact common fleet seeds and reports descriptive deltas only.
- Training warm-up non-finite values are represented as unavailable rather than JSON NaN.
- Processed FCD supports mobility-state replay but not persistent identity or trip duration.
- The static atlas can be generated offline, but public deployment remains permission-gated.

Resolved during guided-workflow polish:

- First-time and mobile users can enter the workflow through Home without opening the collapsed
  Streamlit sidebar.
- The synthetic and imported-TOS walkthroughs are separate evidence tracks and do not imply direct
  simulator launch, live data, or canonical TOS conversion.

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

Source inspection answered the earlier field, unit, control, and evaluator-interface questions.
Only the following evidence is still needed:

1. Which exact source commit/script produced the supplied per-step and per-task NPZ files, and can
   that instrumented writer be shared?
2. Can one small approved actor checkpoint and its exact producing environment commit be shared
   for a reproducibility smoke run?
3. Are eventual physical completion, per-vehicle tier, action targets/availability/link quality,
   or raw SUMO/trip outputs exported anywhere outside the supplied package?
4. Which small matched files may be committed as sanitised fixtures and shown in dissertation
   screenshots/tables?
5. Is TrafficTwin permitted to propose a separate instrumentation branch later if a required field
   exists internally but is not exported?

## Implementation Blockers

- Full canonical adapters require physical-completion/identity fields, compatible infrastructure
  evidence, exact producer provenance, and fixture permission; basic source semantics/units are no
  longer blockers.
- Direct launch requires the checkpoint, instrumented writer or agreed output contract, portable
  paths, and a tested local invocation.
- Metrics using energy, drop causes, queue-clearance time, or capacity-normalised load require source columns and units.
- R1-R3 thresholds require synthetic calibration first and real calibration only after representative data is supplied.
- R1 direct low-tier/T1 evidence requires vehicle-tier and task-class cross-tab evidence.
- R2 temporal-overlap evidence requires windowed or event-level task and infrastructure evidence in the EvidencePack.
- UI controls must remain unavailable or unknown until adapter capabilities are evidenced.
- Phase 2 generic CSV validation can proceed with synthetic fixtures, but real Randy compatibility needs an adapter because the supplied lower-level files are NPZ/JSON, not standard bundle CSV.
- Phase 3 can compute deterministic metrics on synthetic fixtures, but real-world interpretation remains blocked on confirmed Randy/SUMO mapping and expert review.
- The read-only TOS integration is implemented with source-evidenced semantics; canonical
  conversion remains blocked on absent outcome/identity/target/trip evidence, producer artifacts,
  and fixture permission.
- Documentation is now broad enough for supervisor review, but dissertation claims still require real integration, literature verification, and any formal evaluation evidence.
- Exact row-level contribution lists for aggregate metrics remain a future design choice; current
  provenance provides aggregate-level traceability and source-row samples.
- Stronger canonical integration remains the next blocker for externally grounded metric and rule
  evaluation.
- A project licence still needs explicit selection before public release.
- A synthetic demonstration can be hosted publicly without TOS data, but publishing source code or
  Randy-derived results still requires the relevant licence and permission decisions.
- Product Polish does not resolve external producer/checkpoint/writer, fixture-permission, or
  canonical-evidence blockers.
- Experiment planning is not blocked by external integration: it records a proposed design only.
  Executing planned run slots remains adapter-gated and unavailable.
- Deterministic YAML/CSV protocols now support manual coordination and later manifest matching;
  who or what executes each slot, and the actual environment/checkpoint provenance, remain external
  responsibilities until an evidenced launcher exists.

## Non-Blocking Unknowns

- Exact design of later portfolio selection.
- Later use of DuckDB or Polars.
- Optional language rendering.
- Optional XAI instrumentation.
- Near-live or true-live data sources.
- Persistent multi-user settings or authentication.
- Richer UI screenshot automation.

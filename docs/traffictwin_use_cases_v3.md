# TrafficTwin Use Cases V3 — Integrated Release

**Status:** CURRENT RELEASE USE-CASE OVERLAY  
**Release:** `337f1624e5ffe188393554b1110a35ababcce8e1`  
**Date:** 15 August 2026

This document gives the current bounded use cases for the integrated release. Historical detailed use-case records, including `docs/closure/v08_alignment/use_case_a_manchester_current_twin.md` and `docs/closure/v08_alignment/use_case_b_vec_dynamic_service.md`, remain source-bound evidence/history. They are not rewritten here.

## Use Case A — Manchester current/context and evidence readiness

### User
Internal transport analyst, dissertation author, supervisor, or examiner reviewing what Manchester-related context TrafficTwin can actually support.

### Decision
Can the user build a bounded, reproducible current/context picture from available evidence while clearly separating real Manchester data, external strategic-road context, bus-only live/recent context, synthetic inputs, simulation output, and unavailable sources?

### Inputs
Potential inputs include:

- Manchester/Greater Manchester static geography and infrastructure references;
- historical Manchester traffic observations where accepted;
- BODS bus positions when configured, explicitly bus-only;
- National Highways strategic-road operational context when configured;
- imported accepted evidence;
- synthetic/authored scenario context;
- explicit unavailable provider-dependent feeds.

### Workflow

1. Inspect evidence/source readiness and blockers.
2. Inspect bounded Manchester context with source-specific standing/freshness.
3. Keep bus-only, strategic-road, historical, static, synthetic, and unavailable states distinct.
4. Select or author a bounded scenario only after the evidence ceiling is visible.
5. Export/review provenance and limitations.

### Outputs
A reproducible context/evidence packet, not a claim of a continuous city-wide live twin.

### Prohibited interpretations

- BODS buses as general road traffic;
- National Highways strategic-road events as complete Manchester city-road telemetry;
- TfGM signal locations as phase/state/queue telemetry;
- retrieval time as observation time;
- unavailable evidence filled with zero;
- static/historical context described as live.

## Use Case B — Scenario/what-if comparison

### User
Traffic/VEC analyst exploring a bounded intervention or challenging scenario.

### Decision
What changes are visible between a baseline and a compatible variation when the evidence standing, changed parameters, denominators, exclusions, and provenance are retained?

### Inputs

- validated scenario/configuration;
- compatible baseline and variation artifacts;
- synthetic, imported, or authorised simulation outputs;
- explicit evidence standing and provenance;
- optional traffic and VEC consequence artifacts.

### Workflow

1. Select or author the baseline/scenario.
2. Record the changed-parameter ledger.
3. Generate/import compatible artifacts through an authorised mode.
4. Validate compatibility and evidence standing.
5. Compare traffic and VEC consequences using deterministic services.
6. Inspect limitations, provenance, and evidence status before reporting.
7. Export deterministic reports/receipts.

### Outputs
Evidence-labelled descriptive comparison. A difference is not automatically causal or operationally optimal.

## Use Case C — Deadline-aware VEC dynamic service and infrastructure load management

### User
VEC researcher/analyst studying task lifecycle, queue pressure, infrastructure placement/forwarding, and deadline outcomes.

### Authority boundary

- **Vehicle actor:** chooses only the mode `Local`, `V2I`, or `V2V` for the frozen baseline semantics.
- **Ingress RSU:** infrastructure/environment-resolved first RSU for offloaded work.
- **Admission:** checks per-RSU waiting-room/queue capacity.
- **Execution RSU:** infrastructure-selected target where admitted work queues/receives service.
- **Placement/load management:** deterministic infrastructure-side RSU target selection/forwarding where implemented.
- **Scaling:** compute/service-rate resource change when simulated; separate from admission and placement.

Do not credit the vehicle actor with exact RSU choice without exact evidence for a different actor/checkpoint contract.

### Lifecycle

`offered → actor mode choice → ingress → admission/rejection → execution-RSU placement → optional forwarding → queue/service → compute_completed → return → deadline assessment`

The following remain separate counters/concepts:

- `offered`
- `admitted`
- `rejected`
- `forwarded`
- `compute_completed`
- `returned`
- `deadline_success`

### Critical semantic distinctions

- waiting-room/queue capacity ≠ compute/service capacity;
- admission ≠ placement ≠ scaling;
- mode choice ≠ ingress RSU ≠ execution RSU;
- forwarded ≠ compute completed ≠ returned ≠ deadline success;
- simulated resource scaling ≠ real Kubernetes deployment.

Use **deterministic infrastructure-side RSU load management** for deterministic placement/forwarding behavior. Do not describe it as vehicle-side learned RSU selection.

### Scientific availability

The software/product surface is present in the integrated release, but E3 scientific execution remains unauthorised and unexecuted:

- `LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD`
- `E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED`
- `evidence_state = NOT_EXECUTED`
- `result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE`
- `research_workloads_launched = 0`

Therefore the use case can demonstrate contracts, lifecycle semantics, UI, validation, provenance, and release behavior, but **must not present E3 research findings**.

## Use Case D — Reproducible study, evidence admission, review, and export

### User
Researcher, supervisor, examiner, or software reviewer who needs to verify how a claim/artifact was produced and whether it is eligible for use.

### Decision
Can an artifact or study be traced, validated, compared, admitted/refused, replayed/reviewed, and exported without losing source identity or overstating evidence standing?

### Workflow

1. Select typed artifacts/study inputs.
2. Verify fingerprints, compatibility, standing, and required provenance.
3. Retain missing/incompatible/refused evidence rather than silently dropping it.
4. Run deterministic study/comparison/diagnostic services where their preconditions are satisfied.
5. Use evidence-admission/review workflows where explicit authority is required.
6. Package/export only the evidence allowed by the selected policy.
7. Preserve exact source/review/release identities in receipts.

### Outputs
Typed reports, provenance views, study artifacts, receipts, deterministic exports, and explicit refusals/unavailable states.

## Acceptance across all use cases

A use case is acceptable only when:

- the source/standing label is truthful;
- missing evidence remains explicit;
- UI does not recompute scientific outputs independently;
- provenance and exact identity remain inspectable;
- unsafe/unavailable/unauthorised operations fail closed;
- no experiment is inferred to have run merely because its software path exists;
- no product page claims real-world control authority it does not possess.

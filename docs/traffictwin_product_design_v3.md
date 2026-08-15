# TrafficTwin Product Design V3 — Integrated Release

**Document version:** 3.0  
**Date:** 15 August 2026  
**Status:** CURRENT RELEASE DESIGN OVERLAY  
**Authoritative release:** `main` at `337f1624e5ffe188393554b1110a35ababcce8e1`

This document is the current product-design overlay for the merged TrafficTwin release. It does not erase the historical v0.6/v0.7/v0.8 designs, Product Design V2 proposal, lane contracts, ADRs, or review receipts. Those remain evidence/history. Where an older document describes a campaign as proposed, active, or awaiting integration, this V3 release overlay and current Git state control the present status.

## 1. Product definition

TrafficTwin is a local, evidence-labelled traffic and vehicular-edge-computing research-software platform for reproducible digital-twin experimentation and decision support. It combines bounded traffic context, scenario authoring, imported/synthetic/simulation evidence, deterministic comparison and diagnostics, infrastructure-side resource-management views, provenance, study/review workflows, and reproducible exports.

TrafficTwin is **not** a city-wide operational traffic-control system, a live private-vehicle telemetry platform, an autonomous RSU controller, or evidence that an unexecuted research campaign produced scientific results.

## 2. Release composition

The current release composition is `337f1624e5ffe188393554b1110a35ababcce8e1`.

Reviewed/frozen component lineage includes:

- Expansion V1: `85a6d98464ba5065f578632fd97456b91fa6ab0e`.
- Lane-12 approved Dynamic content: `4d35a80407268877323fc073e3027a37fc42f63d`.
- Provenance-binding remediation: `c96b407bc9cb3915e2e3908a20b9a122b5e61f11`.
- Dynamic freeze after provenance binding: `32f8b05be58ca8be00d48566003f8d12d45a3f79`.
- Strict-mypy/composition-pin remediation: `cebe0c05d959af99cac3a9f98f3dbc30ab948966`.
- Final frozen Dynamic tip: `d9e9944e4258578c4743a524c9de6ddce1bd7dde`.
- Final integrated release: `337f1624e5ffe188393554b1110a35ababcce8e1`.

Reviewed histories are preserved without rebasing.

## 3. Design principles

1. **Evidence before claims.** Every important product result carries provenance, standing, availability, denominators/exclusions, and limitations.
2. **Thin interfaces over tested services.** Streamlit and CLI surfaces present typed library outputs rather than reimplementing scientific calculations.
3. **Deterministic identity.** Semantic artifacts use canonical content/fingerprints and avoid local-path or wall-clock contamination where identity must be portable.
4. **Fail closed.** Missing, incompatible, unauthorised, stale, or unverifiable evidence remains unavailable/blocked instead of being silently substituted.
5. **Source separation.** Manchester, external strategic-road, bus-only, synthetic, simulation, imported, and research evidence are not silently fused.
6. **Authority separation.** Authored configuration, software capability, scientific evidence, human approval, and operational control are distinct states.
7. **Reproducible review.** Exact source identity, deterministic gates, review receipts, provenance, and bounded exports support dissertation/viva auditability.

## 4. Current product surfaces

### 4.1 Manchester current/context workflow

TrafficTwin can present bounded Manchester context and evidence readiness while preserving source-specific ceilings. BODS is bus-only. National Highways operational material is strategic-road context. Static/historical Manchester evidence remains distinct from live/general road telemetry. Missing provider contracts or credentials produce explicit unavailable/not-ready states.

This is a **context and evidence-readiness workflow**, not a claim that TrafficTwin maintains a continuous city-wide live twin.

### 4.2 Scenario and what-if workflow

Users can work with bounded scenario definitions, synthetic fixtures, imported artifacts, controlled simulation outputs where authorised, comparison services, challenge/mutation tooling, and deterministic reports. Authored incidents are configuration/hypotheses, not observations.

### 4.3 VEC dynamic-resource workflow

The VEC product preserves the complete authority and accounting boundary:

- the vehicle actor chooses the offloading **mode** (`Local`, `V2I`, `V2V`);
- exact ingress/execution RSU identity is infrastructure/environment-side;
- admission checks waiting-room/queue capacity;
- deterministic infrastructure-side RSU load management may place/forward admitted work;
- service/compute capacity is distinct from queue capacity;
- forwarding, compute completion, return, and deadline success are separate lifecycle events;
- resource scaling presented as simulation remains simulated, not a Kubernetes deployment.

The product may expose resource-strategy software and provenance without implying that an unexecuted E3 campaign generated scientific results.

### 4.4 Evidence, study, review, and release workflows

The integrated product contains strong evidence/provenance, compatibility, admission, statistical/comparison, study workspace, replay/capsule, export, registry, validation, and release-quality surfaces. These support reproducible analysis and review; they do not automatically elevate evidence standing or substitute for human/scientific authority.

## 5. Current scientific truth boundary

The E3 software/product surface is merged, but the E3 scientific workload was not authorised and was not executed. Preserve the following exact state until the human owner explicitly changes policy:

- `LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD`
- `E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED`
- `evidence_state = NOT_EXECUTED`
- `result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE`
- `research_workloads_launched = 0`

Therefore the release may truthfully demonstrate E3-related software, contracts, validators, UI, acceptance, provenance, and release bindings while showing **no E3 research results available**.

## 6. Source and claim ceilings

- BODS vehicle positions are Manchester bus context, not measured general road traffic.
- TfGM signal-location data is infrastructure location, not signal phase/state/queue telemetry.
- National Highways operational data is strategic-road context, not complete Manchester city-road coverage.
- Historical observations are not live observations.
- Authored scenario inputs are not observed events.
- Simulation output is not ground truth.
- Descriptive comparisons are not causal claims.
- A software-ready research path is not an authorised experiment.
- Simulated Kubernetes-style scaling is not a real Kubernetes deployment.

## 7. Principal release use cases

The current bounded use cases are specified in `docs/traffictwin_use_cases_v3.md`:

1. Manchester current/context and evidence-readiness review.
2. Scenario/what-if comparison with evidence-labelled traffic and VEC consequences.
3. Deadline-aware VEC dynamic service and deterministic infrastructure-side RSU load management.
4. Reproducible study/evidence/review/export workflow.

Historical v0.8 Use Case A/B documents remain detailed source-bound records; V3 states how those capabilities sit inside the final integrated product.

## 8. Current architecture

See `docs/architecture_current_release.md`. In summary:

```text
Evidence / authored inputs
        ↓
Typed contracts + ingestion/adapters
        ↓
Validation + canonical models
        ↓
Metrics / experiment / VEC / comparison services
        ↓
Evidence + provenance + admission + study/review artifacts
        ↓
Thin Streamlit / CLI surfaces
        ↓
Deterministic exports / receipts / reproducible release artifacts
```

Scientific and operational authority does not flow backward from UI availability.

## 9. Multi-agent engineering design

Repository engineering uses an explicit trust-separated agent model:

- human owner = final authority;
- controller/integrator = scheduling, composition, gates, provenance;
- builder/remediator = source-changing worker (for example Muse xhigh or designated Fable 5 xhigh);
- independent reviewer = fresh read-only Opus 5 xhigh on the exact pushed SHA;
- deterministic infrastructure = Git/GitHub, worktrees, pytest, Ruff, mypy, validators, receipts, fingerprints.

A builder cannot approve its own source. Process exit code is not approval. Any source change creates a new identity and requires fresh review when review is required.

A future orchestration-runtime migration (for example a durable graph/state-machine controller) may replace shell/session plumbing, but it must not replace Git exact-SHA identity, independent review, deterministic gates, or owner authority. Such a migration is future work, not an implemented product claim.

## 10. Non-goals of the current release

- continuous city-wide private-vehicle digital twin;
- autonomous real-world traffic/RSU actuation;
- real Kubernetes deployment unless separately implemented and evidenced;
- silent fusion of heterogeneous evidence;
- fabricated provider access or unavailable source fields;
- invented participant/user-study results;
- E3 scientific execution without explicit owner authorisation;
- treating implementation, review approval, scientific admission, and deployment as synonyms.

## 11. Change policy

New design work starts from current `main`. Material changes should create a new version/overlay rather than rewriting historical receipts or source-bound records. When a new design changes scientific authority, provider semantics, human approval, or experiment execution, that authority must be explicit and separately evidenced.

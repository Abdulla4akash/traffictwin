# TrafficTwin Architecture

**Current authoritative release:** `337f1624e5ffe188393554b1110a35ababcce8e1`

The current integrated architecture is documented in:

- [`architecture_current_release.md`](architecture_current_release.md) — current high-level release architecture and trust boundaries;
- [`traffictwin_product_design_v3.md`](traffictwin_product_design_v3.md) — current product design;
- [`traffictwin_use_cases_v3.md`](traffictwin_use_cases_v3.md) — current bounded use cases;
- [`quality/final_release_status_20260815.md`](quality/final_release_status_20260815.md) — exact release identity and scientific hold state.

Older architecture/design documents remain important historical and module-level records, including the versioned v0.5/v0.6/v0.7/v0.8 specifications and the pre-final version of this file in Git history. They must not override the current release overlay when they describe a capability as merely proposed/active even though it has since been integrated.

## Current architectural invariants

- TrafficTwin is evidence-first and fail-closed.
- Streamlit/CLI are thin interfaces over tested services and typed artifacts.
- Metrics, lifecycle accounting, diagnostics, comparisons, and statistical outputs are deterministic code outputs.
- Source standing, freshness, missingness, compatibility, provenance, and authority remain explicit.
- Manchester bus, strategic-road, static/historical, synthetic, simulation, imported, and unavailable evidence are not silently fused.
- Vehicle actor mode choice is distinct from exact RSU selection.
- Deterministic infrastructure-side RSU load management is infrastructure-side placement/forwarding, downstream of actor mode choice.
- Waiting-room/queue capacity is distinct from compute/service capacity.
- Admission, placement, and scaling are distinct.
- Forwarding, compute completion, return, and deadline success are distinct lifecycle states/counters.
- Simulated resource scaling is not a real Kubernetes deployment.
- Git exact-SHA identity, deterministic gates, receipts, independent review, and owner authority form the engineering trust chain.

## E3 truth boundary

The integrated software does not imply E3 scientific execution. Current state remains:

```text
LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD
E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED
evidence_state = NOT_EXECUTED
result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE
research_workloads_launched = 0
```

No architecture, UI, test, validator, release receipt, or merged code may convert that state into research evidence without explicit new owner-authorised execution and its own evidence chain.

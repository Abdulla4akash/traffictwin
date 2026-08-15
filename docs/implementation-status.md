# TrafficTwin Implementation Status

**Current authoritative release:** `main` at `337f1624e5ffe188393554b1110a35ababcce8e1`  
**Status date:** 15 August 2026

This file records current implementation truth. Detailed historical v0.5/v0.6/v0.7/v0.8 phase tables, candidate measurements, lane receipts, and design evolution remain available in versioned documents and Git history; they must not be treated as the current release status merely because they describe an earlier active campaign.

## Current product state

The reviewed/frozen Expansion V1 and Dynamic Resource V2 product surfaces are integrated into current `main`.

Key release identities:

- Expansion V1: `85a6d98464ba5065f578632fd97456b91fa6ab0e`
- Lane-12 approved Dynamic content: `4d35a80407268877323fc073e3027a37fc42f63d`
- Provenance-binding remediation: `c96b407bc9cb3915e2e3908a20b9a122b5e61f11`
- Dynamic freeze after binding: `32f8b05be58ca8be00d48566003f8d12d45a3f79`
- Strict-mypy/composition-pin remediation: `cebe0c05d959af99cac3a9f98f3dbc30ab948966`
- Final frozen Dynamic tip: `d9e9944e4258578c4743a524c9de6ddce1bd7dde`
- Final integrated release: `337f1624e5ffe188393554b1110a35ababcce8e1`

The current product design is `docs/traffictwin_product_design_v3.md`; current bounded use cases are `docs/traffictwin_use_cases_v3.md`; current high-level architecture is `docs/architecture_current_release.md`.

## Implemented release surfaces

At a high level the integrated release contains:

- evidence-labelled Manchester context/readiness and source-separated operational/historical/static/synthetic states;
- bounded scenario authoring, what-if/comparison, mutation/challenge, deterministic analysis and reporting surfaces;
- traffic/VEC consequence and research-product workflows;
- explicit VEC lifecycle/accounting and deterministic infrastructure-side RSU load-management software boundaries;
- evidence, compatibility, provenance, admission/review, registry, replay/capsule, statistical/comparison, export and release-quality tooling;
- thin Streamlit and CLI interfaces over tested services;
- exact-source/provenance/release bindings and deterministic validation gates.

Implementation does not imply provider availability, scientific admission, human approval, or operational deployment.

## Scientific state — E3 remains unexecuted

The E3 software/product surface is implemented, but E3 scientific execution was not authorised and no E3 research workload was launched. Preserve exactly:

- `LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD`
- `E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED`
- `evidence_state = NOT_EXECUTED`
- `result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE`
- `research_workloads_launched = 0`

Therefore **no E3 research results are available**. Software readiness, green tests, merged code, UI routes, validators, or receipts must not be presented as experimental evidence.

## Current capability ceilings

The release does not establish:

- a continuous city-wide live Manchester private-vehicle twin;
- complete Manchester city-road telemetry from National Highways;
- general road traffic from BODS bus positions;
- TfGM signal-state/phase/queue telemetry from signal locations;
- autonomous real-world traffic or RSU actuation;
- a real Kubernetes deployment where only simulated resource scaling exists;
- participant/user-study results without actual authorised collection;
- scientific results for an unexecuted E3 workload.

## VEC semantic implementation boundary

Current wording and accounting must preserve:

- vehicle actor mode (`Local` / `V2I` / `V2V`) ≠ exact RSU choice;
- ingress RSU ≠ execution RSU;
- admission ≠ placement ≠ scaling;
- waiting-room/queue capacity ≠ compute/service capacity;
- forwarded ≠ compute_completed ≠ returned ≠ deadline_success;
- deterministic placement/forwarding = **deterministic infrastructure-side RSU load management**;
- simulated Kubernetes-style scaling ≠ real Kubernetes deployment.

## Engineering/release trust

New source-changing work starts from current `main` unless explicitly scoped otherwise and follows `AGENTS.md` and `CONTROLLER.md`:

- isolated source-changing work;
- focused/adversarial/static gates during remediation;
- exact pushed SHA as review identity;
- fresh independent read-only approval for promotable source;
- no self-approval by a source-changing controller/builder;
- no rebase of reviewed histories or force-push of `main`;
- bounded final integration audit for concrete new/reintroduced composition defects.

For exact final release identity and hold state, see `docs/quality/final_release_status_20260815.md`.

# TrafficTwin Final Integrated Release Status — 15 August 2026

## Authority

Authoritative branch: `main`  
Authoritative release SHA: `337f1624e5ffe188393554b1110a35ababcce8e1`

At the release boundary, `release/dynamic-v2-expansion-v1` and `main` resolve to the same final composition SHA. This record is a current-state overlay; historical lane/review receipts remain the evidence for individual approvals and remediation history.

## Reviewed/frozen lineage

| Component / stage | Exact identity | Meaning |
|---|---|---|
| Expansion V1 | `85a6d98464ba5065f578632fd97456b91fa6ab0e` | Frozen Expansion V1 integration tip |
| Lane-12 Dynamic content | `4d35a80407268877323fc073e3027a37fc42f63d` | Exact Lane-12 content approved by independent review |
| Dynamic provenance-binding remediation | `c96b407bc9cb3915e2e3908a20b9a122b5e61f11` | Approved provenance/release-binding fix |
| Dynamic freeze after binding | `32f8b05be58ca8be00d48566003f8d12d45a3f79` | Source-identical promotion of binding-approved Dynamic product |
| Strict-mypy/composition-pin remediation | `cebe0c05d959af99cac3a9f98f3dbc30ab948966` | Approved type/provenance-pin remediation |
| Final frozen Dynamic tip | `d9e9944e4258578c4743a524c9de6ddce1bd7dde` | Source-identical promotion of the approved mypy/pin remediation |
| Final integrated release | `337f1624e5ffe188393554b1110a35ababcce8e1` | Current `main` release composition |

Reviewed histories were composed without rebasing.

## Scientific execution state

Release completion does not change research authority. The E3 scientific workload remains held and unexecuted:

- `LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD`
- `E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED`
- `evidence_state = NOT_EXECUTED`
- `result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE`
- `research_workloads_launched = 0`

This is an intentional truthful product state. Software, validators, UI, provenance, and release receipts may be complete while research results remain unavailable.

## Current interpretation

The final release therefore supports two separate statements:

1. **Software/release statement:** the reviewed Dynamic Resource V2 and Expansion V1 product surfaces are integrated into current `main`.
2. **Scientific statement:** no E3 scientific workload was authorised or launched, so no E3 research results are available.

These statements must never be collapsed into “the experiment is complete.”

## Terminology safeguards

- Use **deterministic infrastructure-side RSU load management** for deterministic placement/forwarding.
- Vehicle mode choice (`Local`/`V2I`/`V2V`) is not exact RSU choice.
- Waiting-room/queue capacity is not compute/service capacity.
- Admission, placement, and scaling are distinct.
- Forwarding, compute completion, return, and deadline success are distinct.
- Simulated Kubernetes-style scaling is not a real Kubernetes deployment.
- Do not describe the software as a continuous city-wide live Manchester twin.

## Post-release engineering rule

New work should branch from current `main` and follow `AGENTS.md` + `CONTROLLER.md`. Historical campaign documents remain auditable records but do not automatically reopen completed lanes.

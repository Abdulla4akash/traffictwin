# TOS Integration Readiness Gates

TrafficTwin represents the remaining external-integration work as versioned, machine-readable gates.
This prevents an unavailable artifact or unknown permission from being treated as supported.

Generate the current report:

```bash
traffictwin integration tos readiness TOS_DATA_PATH --format json
```

## Gate States

- `ready`: inspected evidence satisfies the named gate.
- `blocked`: required evidence is absent or incompatible.
- `unknown`: a permission or provenance fact has not been confirmed.
- `not_applicable`: reserved for a gate that does not apply to the selected context.

## Current Gates

| ID | Gate | Current default | Blocks |
|---|---|---|---|
| G01 | Source summary contract | Ready | Nothing in the read-only workbench |
| G02 | Exact producer provenance | Unknown | Canonical conversion, rerun, launch |
| G03 | Approved checkpoint | Blocked | Evaluator smoke, launch |
| G04 | Instrumented writer | Blocked | Instrumented rerun, conversion, launch |
| G05 | Physical completion and persistent identity | Blocked | Canonical tasks and vehicles |
| G06 | Decision-time context | Blocked | Real R1 evaluation |
| G07 | Failure/infrastructure temporal alignment | Blocked | Real R2 evaluation |
| G08 | Raw trip output | Blocked | Journey-time integration |
| G09 | Sanitised fixture permission | Unknown | Committed real-schema fixture and public CI |
| G10 | Aggregate publication permission | Unknown | Public TOS atlas/results |
| G11 | Local evaluator smoke | Blocked | Direct launch |

Permission flags are attestations, not discovery mechanisms. For example,
`--confirm-publication-permission` changes only G10. It cannot make canonical conversion or direct
launch ready.

## Capability Policy

The read-only summary import, results workbench, historical replay, and private supervisor pack are
ready. Canonical conversion, real R1/R2 evaluation, journey-time integration, direct launch, and
public TOS publication remain unavailable until every relevant gate is ready.

## Related Documents

- [Phase 6 decision](phase6_decision.md)
- [Gap analysis](randy_gap_analysis.md)
- [Execution contract](randy_execution_contract.md)
- [Supervisor pack](../supervisor_pack.md)

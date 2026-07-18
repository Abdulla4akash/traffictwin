# Limitations And Future Work

This document separates deliberate scope boundaries from evidence gaps.

## Current Limitations

- The prototype is import-first and synthetic-demo ready.
- It does not run external simulators.
- It does not ingest live, near-live, or real Manchester data.
- It does not include real Randy/VEC or SUMO adapters.
- It stores metadata and JSON payloads in SQLite, not full canonical row datasets.
- Provenance traces aggregate metrics to eligible record samples; they do not store full per-row
  contribution weights for every aggregate.
- Streamlit is a research UI, not a production deployment surface.

## Evidence Limitations

- Included bundles are synthetic.
- Real schemas, units, runtime behavior, and output sizes are unknown.
- R1 lacks direct T1-by-low-tier cross-tab evidence in normal EvidencePacks.
- R2 lacks direct temporal overlap between saturation windows and task misses.
- R3 requires experiment-level evidence not present in ordinary single-run bundles.
- EvidencePack-only fault-injection traces cannot inspect source rows unless the source bundle is
  also available.

## Synthetic-Evaluation Limitations

Synthetic fixtures verify implementation behavior and formulas. They do not establish external validity for Manchester traffic, SUMO outputs, or Randy/VEC runs.

Fault-injection precision/recall values are implementation checks over labelled synthetic cases, not research validation.

## External Integration Blockers

Phase 6A found no real:

- Randy/VEC task logs;
- infrastructure logs;
- vehicle state files;
- SUMO configuration or output files;
- checkpoints;
- notebooks or launch scripts;
- job files;
- metric scripts;
- unit documentation.

See [integration/randy_gap_analysis.md](integration/randy_gap_analysis.md).

## Research Limitations

- No formal expert/user study is present.
- No real operator validation is present.
- Diagnostic thresholds are provisional.
- No portfolio selector or winner-map study is implemented.
- Literature claims are not encoded as repository evidence.

## Engineering Limitations

- No row-level analytical store.
- No materialised metric-to-row contribution table.
- No adapter plugin framework beyond current module boundaries.
- Limited UI test coverage for full browser interaction.
- CLI help snapshots are generated references, not hand-written tutorials.
- No licence file is present.

## Sensible Future Work

1. Acquire real or sanitised Randy/SUMO artifacts.
2. Implement the smallest evidenced adapter.
3. Generate a standard TrafficTwin run bundle from real samples.
4. Reconcile Randy's existing metric scripts against TrafficTwin formulas.
5. Extend EvidencePack only where real evidence requires it.
6. Run expert review of diagnostic hypotheses.
7. Add canonical row storage if real data volume justifies it.
8. Add materialised contributing-record references for selected aggregate metrics if supervisor or
   viva feedback requires deeper audit trails.
9. Consider direct launch only after a safe headless execution contract exists.

## Explicitly Rejected Scope For Now

- Faking Randy/SUMO integration.
- Claiming live data from imported files.
- Letting an LLM calculate metrics or invent recommendations.
- Adding SUMO formats not present in supplied artifacts.
- Implementing XAI without decision-time state evidence.
- Adding FastAPI, React, distributed queues, or cloud infrastructure without a demonstrated need.

Related documents:

- [Integration decision](integration/phase6_decision.md)
- [Security and privacy](security_and_privacy.md)
- [Viva guide](viva_guide.md)
- [Provenance Explorer](provenance_explorer.md)

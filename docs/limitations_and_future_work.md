# Limitations And Future Work

This document separates deliberate scope boundaries from evidence gaps.

## Current Limitations

- The prototype is import-first and synthetic-demo ready.
- It does not run external simulators.
- It does not ingest live, near-live, or real Manchester data.
- It includes only a read-only TOS Data result reader, not a canonical Randy/VEC or SUMO adapter.
- It stores metadata and JSON payloads in SQLite, not full canonical row datasets.
- Provenance traces aggregate metrics to eligible record samples; they do not store full per-row
  contribution weights for every aggregate.
- Streamlit is a research UI, not a production deployment surface.

## Evidence Limitations

- Included bundles are synthetic.
- TOS field meanings and trace units are source-evidenced, but exact producer provenance,
  checkpoint/writer artifacts, local runtime behavior, persistent identity, physical completion,
  and several decision-time outputs remain unavailable.
- R1 lacks direct T1-by-low-tier cross-tab evidence in normal EvidencePacks.
- R2 lacks direct temporal overlap between saturation windows and task misses.
- R3 requires experiment-level evidence not present in ordinary single-run bundles.
- EvidencePack-only fault-injection traces cannot inspect source rows unless the source bundle is
  also available.

## Synthetic-Evaluation Limitations

Synthetic fixtures verify implementation behavior and formulas. They do not establish external validity for Manchester traffic, SUMO outputs, or Randy/VEC runs.

Fault-injection precision/recall values are implementation checks over labelled synthetic cases, not research validation.

## External Integration Blockers

Phase 6 found evaluation summaries, instrumented arrays, and source code, but a full adapter is
blocked by:

- no persistent per-vehicle identifier or vehicle-tier output in the inspected arrays;
- no eventual physical-completion field compatible with canonical `TaskRecord.completed`;
- no action-target, action-availability, or link-quality output;
- no trip/journey-time or raw SUMO outputs;
- no exact producer commit, actor checkpoint, or instrumented-array writer;
- source-specific evaluator paths and no locally verified runtime;
- no permission yet to commit sanitised derived fixtures.

See [integration/randy_gap_analysis.md](integration/randy_gap_analysis.md).

## Research Limitations

- No formal expert/user study is present.
- No real operator validation is present.
- Diagnostic thresholds are provisional.
- Standalone synthetic scenarios are deterministic software fixtures, not calibrated simulations.
- Synthetic policy profiles are not real trained algorithms and should not be used for performance
  claims.
- No portfolio selector or winner-map study is implemented.
- Literature claims are not encoded as repository evidence.

## Engineering Limitations

- No row-level analytical store.
- No materialised metric-to-row contribution table.
- No adapter plugin framework beyond current module boundaries.
- Limited UI test coverage for full browser interaction.
- CLI help snapshots are generated references, not hand-written tutorials.
- Report export supports bundle paths first; richer registry-run reporting can be added later if
  needed.
- No licence file is present.

## Sensible Future Work

1. Obtain the instrumented writer/producer commit, approved checkpoint, missing output evidence,
   and sanitised-fixture permission.
2. Add only mappings compatible with the existing canonical semantics.
3. Generate a standard TrafficTwin run bundle only when identifiers and units are unambiguous.
4. Reconcile Randy's existing metric scripts against TrafficTwin formulas.
5. Extend EvidencePack only where real evidence requires it.
6. Run expert review of diagnostic hypotheses.
7. Add canonical row storage if real data volume justifies it.
8. Add materialised contributing-record references for selected aggregate metrics if supervisor or
   viva feedback requires deeper audit trails.
9. Consider direct launch only after a safe headless execution contract exists.
10. Add report themes or PDF export only if dissertation submission workflow needs them.

## Explicitly Rejected Scope For Now

- Faking Randy/SUMO integration.
- Claiming live data from imported files.
- Letting an LLM calculate metrics or invent recommendations.
- Adding SUMO formats not present in supplied artifacts.
- Implementing XAI without decision-time state evidence.
- Adding FastAPI, React, distributed queues, or cloud infrastructure without a demonstrated need.
- Treating standalone synthetic reports as real-world validation.

Related documents:

- [Standalone demo](standalone_demo.md)
- [Synthetic data model](synthetic_data_model.md)
- [Report export](report_export.md)
- [Integration decision](integration/phase6_decision.md)
- [Security and privacy](security_and_privacy.md)
- [Viva guide](viva_guide.md)
- [Provenance Explorer](provenance_explorer.md)

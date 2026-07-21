# Limitations And Future Work

This document separates deliberate scope boundaries from evidence gaps.

## Current Limitations

- The prototype is import-first and synthetic-demo ready.
- It does not run external simulators.
- It does not ingest live, near-live, or real Manchester data.
- It includes a read-only TOS Data result reader and a bounded public SUMO tripinfo/summary adapter,
  not a full Randy/VEC converter, FCD adapter, or simulator launcher.
- OPS-05 standardises discovery and disclosure for those two reviewed external adapters only. It
  does not make their schemas, conversion profiles, metrics, permissions, or scientific evidence
  equivalent and does not dynamically load third-party adapters.
- The manifest wizard covers the six existing generic CSV kinds only. It does not learn arbitrary
  schemas, infer units from numeric magnitude, or establish external semantic validity.
- Streaming bounds the generic parser chunk and uses disk-backed global checks, but does not bound
  caller retention, validation-report growth, every native-library allocation, or materialise
  downstream metrics without collected mode.
- It stores metadata and JSON payloads in SQLite, not full canonical row datasets.
- Provenance traces stay compact, while an on-demand ledger lists every accepted candidate row;
  neither assigns per-row causal weights.
- Streamlit is a research UI, not a production deployment surface.
- P99 latency is a descriptive sample percentile. Small samples, including a default singleton,
  do not establish tail stability, a worst case, or a confidence bound; consumers must inspect the
  attached sample-count and method metadata or configure a larger minimum sample size.
- Canonical energy metrics are available only for explicit v1.0 generic/synthetic task-energy
  contracts. The bundled synthetic energy model is not measured power/energy evidence, TOS exposes
  only a separate aggregate joules-per-arrival source metric, and SUMO has no compatible task
  energy. R8 can consume only the complete completed-task energy metric with the exact v1.0
  contract and a matching completed-task population. Its provisional absolute threshold is not a
  statistical anomaly test, hardware benchmark, causal attribution, external standard, or
  recommendation; no external-validity claim follows from `MET-03` or an R8 result.
- Operational fairness metrics are available only with exact stable vehicle-tier or RSU groups,
  two groups, repeated support, and complete coverage. Vehicle tier is not a protected attribute;
  load/completion equality can coexist with uniformly poor outcomes. Current SUMO/TOS contracts
  remain unavailable. R7 can consume only compatible completion evidence and its provisional
  threshold does not establish a causal conclusion, demographic fairness, or external standard.
- Per-RSU task outcomes require an explicit exact execution-target contract and complete V2I
  target-to-RSU joins. Vehicle grid summaries require a separate named metre-based source frame,
  fixed geometry, and complete finite x/y. The implementation does not infer task positions,
  nearest RSUs, routes, CRS/geography, or causal attribution; current SUMO/TOS contracts remain
  unavailable. R7 can describe an exact-target operational disparity but no geographic outcome or
  cause follows from `MET-05`.
- R6 is available only for a direction-declared scalar metric from a compatible complete
  `WindowedMetricSeries`. Its absolute thresholds are in that metric's unit and remain provisional;
  a trigger is not a statistical drift test or causal attribution. Missing/partial/low-coverage
  windows break consecutive runs. Recovery is assessed against an optional researcher-declared
  event and a bounded horizon; TrafficTwin does not infer the event.
- R7 selects one operational completion dimension and uses a provisional absolute gap threshold.
  It does not test significance, uncertainty, protected attributes, discrimination, geography,
  or cause, and it remains insufficient for thin, partial, incompatible, or missing group evidence.
- R8 uses an inclusive provisional mean-energy threshold and a minimum completed-task count. It
  remains insufficient for thin, partial, mixed-contract, wrong-unit, inconsistent-population, or
  missing evidence, and it does not estimate uncertainty or identify the source of high energy.
- Nearest-flip v1.0 supports only the exact inclusive single-boundary severity settings of R5,
  R7, and R8 after unchanged discrete support admission. R0-R4, R6, and arbitrary declarative
  rules are unsupported rather than assigned an arbitrary cross-unit distance. A returned boundary
  is selected from the observed evidence and is descriptive sensitivity, not calibration,
  optimisation, significance, or a recommended replacement default.
- DIA-06 sweeps only the same contracted R5/R7/R8 continuous axes, retains fixed discrete support,
  and reports sampled trigger intervals separately from exact DIA-05 output. It does not calibrate
  defaults, persist controls, support compound/R6/declarative grids, or establish external validity.
- DIA-07 v1 admits only R1/R2 conflict, R1/R4 contextual corroboration, and R0 explicit-blocker
  suppression. It does not infer undeclared pairs, probabilities, relationship strength, causal
  attribution, or recommendation priority. Shared evidence keys are common lineage, not proof of
  independence or cause; suppression never changes or hides an original result.
- Declarative rules support only the published flat threshold/boolean grammar. Local YAML is
  trusted configuration, not a sandbox; schema admission and deterministic execution do not prove
  that a threshold, metric, or resulting hypothesis is scientifically valid.
- STA-01 supports only one predeclared compatible baseline-versus-variation common-seed contrast.
  Its paired bootstrap, two-sided sign-flip p-value, and paired effects do not establish practical
  importance, causality, external validity, equivalence, or adequate power. At least three admitted
  pairs are required; missing/duplicate/incompatible inputs remain exclusions.
- STA-02 ranks policies independently inside a scenario family over identical complete common-seed
  rows and adds joint-bootstrap mean/rank uncertainty. Numerical ties are not equivalence, rank
  frequency is not universal superiority, and interval overlap is not a hypothesis test. At least
  three complete rows are required; incomplete/incompatible evidence is audited, not imputed.
- STA-03 implements only a symmetric absolute-margin paired-mean Student-t TOST over the unchanged
  STA-01 cohort. It assumes independent, approximately normal paired differences, requires at least
  three pairs and positive sample variance, and does not choose or scientifically validate the
  margin. `equivalence_not_demonstrated` does not prove difference. Asymmetric/relative margins,
  unpaired equivalence, multiplicity, non-inferiority, and power planning remain unsupported or
  separate future capabilities.
- STA-04 v1 gates only completed `MetricCollection` and STA-01 `StatisticalStudy` scalar
  projections. A pass covers declared assertions only; it is not equivalence, scientific validity,
  or policy quality. Candidate goldens remain unavailable; approval and tolerance justification
  are human decisions. Exact-source and compatible-context policies have different claims.
  STA-02/STA-03, grouped/array, diagnostic, rendered-report, and arbitrary JSON-path gates require
  separate stable projections and method decisions.
- STA-05 v1 is prospective two-sided paired-mean normal-approximation planning with a fixed
  researcher-declared effect and variance. It is not retrospective achieved power, exact power for
  STA-01 sign flips or STA-03 TOST, an attrition model, a guarantee, or an automatic scientific
  recommendation. Small, synthetic, and provisional labels do not validate the supplied inputs.
- PRO-01 arithmetic is limited to the closed direct scalar formula registry. Percentiles, extrema,
  distinct counts, state-machine metrics, grouped/fairness/spatial aggregates, and plugins without
  an admitted formula receive eligible lineage with no weights. Mapping-valued differences remain
  unavailable. A reconciled calculation does not identify causality, influence, significance, or
  external validity; current SUMO/TOS adapter boundaries do not support this generic two-bundle
  ledger.
- PRO-02 is a bounded projection of an existing provenance DAG, not a causal
  analysis. Truncation is explicit, renderer layout is not deterministic evidence, path-safe mode
  is not anonymisation, and structure-only mode removes details required for value-level audit.
  Generic and TOS traces can use the serializer; the current SUMO contract has no trace entry
  point.
- PRO-03 scores accepted-canonical-row lineage over the exact typed claims in one supported report
  template. It does not measure rejected raw-row coverage, truth, correctness, causal validity,
  scientific importance, or report quality. All claims have equal weight, aggregate-only claims
  receive no partial credit, and scores from different templates require their denominators.
  Current TOS/SUMO report boundaries do not expose the required typed claim inventory and remain
  unavailable.
- EXP-01 local output comes only from the labelled deterministic TrafficTwin software-fixture
  generator. External request artifacts are never executed, and neither mode establishes
  simulator fidelity, calibration, optimal parameters, causal response, statistical significance,
  or external validity. The v1 closed scalar catalogue excludes mixes, placement, failures, and
  list-valued mutations that require their own validity-preserving contracts.
- EXP-02 mutates only ordinarily valid, explicitly labelled synthetic/evaluation bundles and only
  one declared uncompressed CSV table per request. Its closed dropout, jitter, and RSU-removal
  operators are software experiment controls, not calibrated traffic/VEC faults. RSU removal does
  not infer task rerouting. Gzip-CSV/Parquet rewriting, operator composition inside one request,
  scientifically justified severity/seed matrices, and real/external mutation validity remain
  future work.
- EXP-03 applies only deterministic bounded-uniform errors and exact generated-row dropout to a
  closed set of synthetic observation fields. It does not model empirical sensor tails,
  correlation, bias, drift, occlusion, radio/packet loss, physical failure, or policy response.
  Tasks, trips, incidents, timestamps, and routing remain clean-generator outcomes. Real
  calibration, correlated models, external validity, and defensible study-specific bounds remain
  future research work.
- OPS-03 is a bounded local preflight, not a repair tool or security scanner. It checks metadata,
  structure, advisory permissions, immutable registry state, and selected cache state; it does not
  execute optional tools, validate credentials/services/network access, prove all ACL behavior,
  discover arbitrary workspaces, or establish simulator/data scientific validity.

## Evidence Limitations

- Included bundles are synthetic.
- TOS field meanings and trace units are source-evidenced, but exact producer provenance,
  checkpoint/writer artifacts, local runtime behavior, persistent identity, physical completion,
  and several decision-time outputs remain unavailable.
- R1 lacks direct T1-by-low-tier cross-tab evidence in normal EvidencePacks.
- R2 lacks direct task-to-saturation temporal-overlap evidence in its current whole-run
  EvidencePack. `DIA-01` adds a one-metric typed temporal projection and R6, but does not change R2
  or create a multi-series overlap claim.
- R3 requires experiment-level evidence not present in ordinary single-run bundles.
- R4 requires compatible capacity, active-task, utilisation, and multi-RSU evidence, and does not
  prove a siting or routing cause.
- R5 requires explicitly matched training-validation pairs and does not prove overfitting.
- EvidencePack-only fault-injection traces cannot inspect source rows unless the source bundle is
  also available.

## Synthetic-Evaluation Limitations

Synthetic fixtures verify implementation behavior and formulas. They do not establish external validity for Manchester traffic, SUMO outputs, or Randy/VEC runs.

The public SUMO square fixture establishes parser compatibility with the documented SUMO 1.27
contract only. It is synthetic simulated traffic and does not establish external validity.

Fault-injection precision/recall values are implementation checks over labelled synthetic cases, not research validation.
The expanded severity/seed matrix, KPI baseline, and robustness summaries remain synthetic
software-verification evidence.

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

- No completed formal expert/user study is present; draft unapproved materials are available.
- No real operator validation is present.
- Diagnostic thresholds are provisional.
- Standalone synthetic scenarios are deterministic software fixtures, not calibrated simulations.
- Synthetic policy profiles are not real trained algorithms and should not be used for performance
  claims.
- Winner-map tooling, paired/N-way/equivalence method implementations, and a transparent synthetic
  portfolio prototype exist, but no trained selector, real calibration, compatible real repeated
  study, or external validation exists.
- Literature claims are not encoded as repository evidence.

## Engineering Limitations

- No row-level analytical store.
- No persisted metric-to-row contribution table; complete ledgers are reconstructed on demand.
- The general external-source interface has a closed reviewed v1 registry, not a dynamic adapter
  plugin framework. New source families require code, contracts, fixtures, and acceptance review.
- The custom metric API executes explicitly registered trusted local Python in-process. It is not a
  sandbox, does not load uploaded/arbitrary modules or ambient entry points, has no timeout/process
  isolation, and two equal outputs do not prove global purity or scientific validity.
- Automated desktop/mobile screenshot and bounded semantic checks exist, but they are not a formal
  WCAG, keyboard, screen-reader, contrast, or participant evaluation.
- CLI help snapshots are generated references, not hand-written tutorials.
- Report export supports bundle paths first; richer registry-run reporting can be added later if
  needed.
- REP-01 tables/figures are bounded compact renderings of four typed artifact families. They do not
  replace full JSON, infer favourable direction/significance/probability, or solve dissertation-
  specific wide-table pagination and typography. Final LaTeX/PDF output needs visual review.
- REP-02 annotations are bounded append-only analyst commentary with declared author labels. They
  provide no authentication, signatures, permissions, rich text, attachments, collaborative
  conflict resolution, or approval authority. Generated-artifact targets are explicit references,
  not proof that a corresponding file is stored.
- REP-03 compares only typed claim snapshots in current run, diagnostics, comparison, and full
  report JSON. It does not diff rendered prose/layout, perform statistical significance or causal
  analysis, merge reports, interpret desirability, or recover snapshots from older presentation-
  only reports. Narrative-only and unavailable sections remain explicitly unavailable.
- REP-04 is a bounded deterministic index into current typed reports, not a free-text synopsis or
  importance ranking. Its five-slot quota can leave relevant claims outside the page, so it exposes
  the omitted count and source link. It does not infer desirability, significance, cause, or
  recommendation, include analyst annotations, or recover legacy presentation-only reports.
- REP-04 one-page PDF deliberately fails when all warnings and limitations do not fit. It does not
  paginate, reduce content to unreadable type, or silently omit caveats. HTML/Markdown/JSON remain
  available for the complete bounded projection.
- No licence file is present.

## Sensible Future Work

1. Obtain the instrumented writer/producer commit, approved checkpoint, missing output evidence,
   and sanitised-fixture permission.
2. Add only mappings compatible with the existing canonical semantics.
3. Generate a standard TrafficTwin run bundle only when identifiers and units are unambiguous.
4. Reconcile Randy's existing metric scripts against TrafficTwin formulas.
5. Extend EvidencePack only where real evidence requires it.
6. Run expert review of diagnostic hypotheses.
7. Obtain ethics/supervisory approval before participant recruitment, then pilot the draft study
   instruments and anonymised schema.
8. Add canonical row storage if real data volume justifies it.
9. Add materialised contributing-record references for selected aggregate metrics if supervisor or
   viva feedback requires deeper audit trails.
10. Consider direct launch only after a safe headless execution contract exists.
11. Add report themes or dissertation-specific LaTeX layout helpers only if the submission
    workflow needs them; keep all scientific values in the typed source artifacts.
12. Add a new external-source reference adapter only after its immutable fixture, field/unit/
    identity/join semantics, provenance, permission, conversion boundary, and blockers are reviewed.

## Explicitly Rejected Scope For Now

- Faking Randy/SUMO integration.
- Claiming live data from imported files.
- Letting an LLM calculate metrics or invent recommendations.
- Adding SUMO formats without an evidenced explicit mapping, permission metadata, and immutable
  acceptance fixture.
- Implementing XAI without decision-time state evidence.
- Adding FastAPI, React, distributed queues, or cloud infrastructure without a demonstrated need.
- Treating shared adapter-interface membership or conversion labels as cross-source equivalence,
  maturity, trust, or scientific validity.
- Loading uploaded/dynamic external adapter code without a later explicit security and contract
  design.
- Treating standalone synthetic reports as real-world validation.
- Treating a valid RO-Crate or checksum as proof of permission, licence validity, authorship,
  scientific truth, or causality. OPS-04 v1 supports only complete ordinary generic bundles;
  source-specific SUMO/TOS archival export remains unavailable.

Related documents:

- [Standalone demo](standalone_demo.md)
- [Synthetic data model](synthetic_data_model.md)
- [Report export](report_export.md)
- [LaTeX research tables and static figures](latex_research_exports.md)
- [Integration decision](integration/phase6_decision.md)
- [SUMO output adapter](integration/sumo_output_adapter.md)
- [Security and privacy](security_and_privacy.md)
- [Chunked and streaming canonicalisation](integration/streaming_canonicalisation.md)
- [Viva guide](viva_guide.md)
- [Provenance Explorer](provenance_explorer.md)
- [Experiment research tools](experiment_research_tools.md)
- [Common-seed paired statistical studies](statistical_studies.md)
- [Paired equivalence testing](equivalence_testing.md)
- [Versioned regression gates](regression_gates.md)
- [Paired common-seed power analysis](power_analysis.md)
- [Accepted-row difference provenance](difference_provenance.md)
- [RO-Crate research objects and citation](research_objects.md)
- [General external-source contract](integration/external_source_contract.md)
- [Draft evaluation materials](evaluation/README.md)

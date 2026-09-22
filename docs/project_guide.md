# TrafficTwin project guide

This is the repository owner's plain-language handbook for the project as it stood on 27 July
2026. It explains the vocabulary, files, scientific workflow, governance, and current state; it
does not replace the designs, decision records, or approval-bound study documents that it links.

**Post-snapshot correction (3 August 2026):** N1 was withdrawn on 28 July. No Geofabrik provider
mutation occurred; an internal record conflated compressed source bytes with decoded XML. The
network chain was rebuilt to the original canonical identity. Current release/product status is in
[current workflow](current_workflow_and_todo.md), and the correction evidence is in the
[workspace continuity audit](integration/manchester_workspace_continuity_20260727.md).

## 1. What this project is

TrafficTwin is Abdulla Al Mamun Akash's MSc dissertation project: a research-software instrument
for asking evidence-backed “what if?” questions about vehicular edge-computing task offloading.
The dissertation contribution is not a new traffic simulator. It is the disciplined chain that
turns source artifacts into inspectable, reproducible, carefully limited findings. The v0.7
product's Manchester source/workflow context is broad, while the `ev` trace's real-world identity
is specifically the Etihad/Co-op Live event district and must not be widened to Manchester in
general. (`README.md`; `docs/traffictwin-design-v0_7.md`;
`docs/dissertation_appendices/trace_provenance.md`)

In practical terms, TrafficTwin validates imported run bundles, computes deterministic metrics,
applies diagnostic rules, compares scenarios and policies, and traces displayed claims back to
source rows, receipts, and fingerprints. It provides a CLI and a Streamlit research UI. Its normal
architecture is import-first; narrowly allowlisted SUMO and VEC execution exists only behind
request-specific preflight and admission gates, while unsupported or unevidenced claims are shown
as unavailable rather than invented. (`docs/system_overview.md`; `docs/architecture.md`;
`docs/traffictwin-design-v0_6.md`; `docs/traffictwin-design-v0_7.md`)

Randy Putra's `vec_env` supplies the VEC simulator/evaluator code and runtime, while `tos-data`
supplies the audited actor checkpoints, traces, occupancy identities, task/run outputs, trip
information, and their data dictionary. TrafficTwin consumes audited, exact source identities
read-only and adds
validation, joins, controlled execution, scientific admission, statistics, provenance, and
publication-bounded packaging; it neither replaces Randy's work nor turns possession into a
licence to redistribute raw data or checkpoints. (`../external/vec_env/README.md`;
`../external/tos-data/README.md`; `../external/tos-data/DATA_DICTIONARY.md`;
`docs/dissertation_appendices/trace_provenance.md`)

## 2. The glossary

- **AADF.** Annual Average Daily Flow, a DfT annual-average traffic figure. It is context here,
  not an instantaneous hourly observation. (`docs/dissertation_appendices/abbreviations.md`)

- **Admission.** A fail-closed decision that an artifact is eligible for a particular next use.
  Fresh VEC admission, for example, requires a completed, full-length, reviewed-trace execution,
  byte re-verification, declared study identity, and compatible metrics before registry insertion.
  (`docs/integration/vec_fresh_run_admission.md`; `docs/decisions/ADR-061-vec-fresh-run-scientific-admission.md`)

- **ADR.** Architecture Decision Record: a numbered record of a decision, its evidence,
  consequences, and limits. All ADR-001 through ADR-065 are indexed as accepted, but accepting an
  ADR does not by itself accept a capability or scientific finding. (`docs/decisions/index.md`;
  `docs/dissertation_appendices/abbreviations.md`)

- **Analyst-reviewed candidate.** `analyst_reviewed_candidate` is the ceiling for evidence a
  named analyst reviewed under the append-only map-match policy. It records review, not scientific
  acceptance. (`docs/decisions/ADR-064-analyst-map-match-review-ledger.md`)

- **Approval.** A record names a human, role, time, scope, and exact predeclaration digest; tooling
  proves that those approved bytes have not changed, not that it authenticated the named person's
  intent. Held-out execution also needs explicit authorisation. (`docs/integration/vec_campaign_execution.md`;
  `docs/decisions/ADR-063-bounded-vec-campaign-execution.md`)

- **AppTest.** Streamlit's headless page harness, used to exercise UI behaviour without treating a
  rendered page as scientific evidence. (`docs/dissertation_appendices/abbreviations.md`;
  `docs/testing_strategy.md`)

- **Arm.** One controlled level in a campaign, such as RSU capacity `cap-2.5` or `cap-0.75`.
  Arms are compared only under the predeclared pairing and analysis rules. (`docs/integration/vec_campaign_execution.md`)

- **BETA-D-01 / BETA-D-02 / BETA-D-03.** These mean complete the 165-row analyst map review;
  replace the gridlocking demand candidate through a revised route-pool/demand policy and viability
  diagnostics; then accept a Manchester baseline. ADR-064 delivered software for D-01, not the
  outstanding human decisions. (`docs/traffictwin-design-v0_7_beta-goals.md`;
  `docs/implementation-status.md`)

- **BNVB.** One candidate Bee Network National Operator Code that was not observed in the accepted
  probe and remains pending; seeing it may open review but cannot activate membership automatically.
  (`docs/integration/manchester_bee_network_scope.md`; `docs/decisions/ADR-057-bee-network-membership-identifiers.md`)

- **BODS.** The UK Bus Open Data Service, supplying timetable, fares, and SIRI-VM real-time bus
  feeds. TrafficTwin treats vehicle identities and raw live locations as private, bounded evidence,
  not general road-traffic counts. (`docs/dissertation_appendices/abbreviations.md`;
  `docs/evaluation/bus_data_experiment_options.md`)

- **Bundle / run bundle.** A validated directory, or safely handled ZIP representation, of source
  tables and metadata for one run.
  Import creates registry evidence from the bundle; it does not retroactively make the simulator
  output scientifically valid. (`docs/data_contract.md`; `docs/run_bundle_spec.md`)

- **Campaign.** A bounded, approved matrix of arms and seeds. Execution is sequential,
  foreground, budgeted, resumable only when fingerprints match, and halted rather than silently
  changing a declared control after failure. (`docs/integration/vec_campaign_execution.md`;
  `docs/decisions/ADR-063-bounded-vec-campaign-execution.md`)

- **Cell.** One arm × fleet-seed execution in a campaign. Each cell has a composed run identity,
  request fingerprint, output directory, execution receipt, and terminal state. (`docs/integration/vec_campaign_execution.md`)

- **CFF / RO-Crate.** Citation File Format describes how to cite the software; RO-Crate is a
  checksummed research-object package. Correct packaging proves artifact identity, not truth,
  rights, or causality. (`CITATION.cff`; `docs/decisions/ADR-047-permission-aware-deterministic-ro-crate.md`)

- **Checkpoint / actor.** A checkpoint is the trained policy state evaluated by an actor label,
  such as the audited UK-MAPPO actor. Checkpoint identity is evidence; it is not a claim that the
  policy is optimal or generalises. (`docs/integration/vec_evaluator_runner.md`;
  `docs/evaluation/actor_crossover_study_draft.md`)

- **CI.** Continuous Integration: automated software checks run on repository changes. A green CI
  gate is software evidence, not scientific acceptance. (`docs/testing_strategy.md`;
  `docs/decisions/ADR-031-versioned-regression-gates.md`)

- **CLI / UI / API.** CLI is command-line interface, UI is user interface, and API is the typed
  programming interface. TrafficTwin keeps CLI and Streamlit pages thin over the same library
  services so presentation does not redefine evidence. (`docs/architecture.md`; `docs/cli_reference.md`)

- **Confirmatory / exploratory.** Exploratory work can reveal a pattern and shape a later question;
  confirmatory work tests a design fixed before held-out outcomes exist. The completed capacity
  pilot is permanently exploratory even though it motivated a separate confirmatory latency
  protocol. (`docs/evaluation/capacity_squeeze_pilot_predeclaration.md`;
  `docs/evaluation/capacity_pilot_results_20260727.md`;
  `docs/evaluation/capacity_confirmatory_candidate_b_latency_primary.md`)

- **CRS / EPSG / WGS84 / UTM.** A Coordinate Reference System says what map coordinates mean;
  EPSG codes identify particular systems. WGS84/EPSG:4326 is geographic longitude/latitude, while
  the reviewed SUMO network records UTM zone 30N/EPSG:32630. (`docs/integration/manchester_network_decision_worksheet.md`)

- **CSF / CSF3 / SLURM.** The Computational Shared Facility is the University of Manchester's
  shared high-performance-computing service; SLURM is its batch-job scheduler. The local capacity
  work was measured as feasible serially; repository docs say access was requested but not granted,
  while the owner pack still carries the unsent request email draft. (`docs/dissertation_appendices/abbreviations.md`;
  `docs/integration/csf_job_pack_contract.md`; `docs/owner_action_pack_20260727.md`)

- **CSV / JSON / XML / YAML.** Common text formats used for tables, structured records, SUMO/SIRI
  documents, and human-readable configuration. Parsers preserve raw identity and reject malformed,
  oversized, or structurally unsafe input rather than guessing. (`docs/data_contract.md`;
  `docs/decisions/ADR-013-declared-tabular-formats-and-raw-identity.md`;
  `docs/decisions/ADR-054-bounded-manchester-acquisition-transport-and-parsing.md`)

- **CTDE.** Centralised Training with Decentralised Execution, the MAPPO arrangement used by the
  upstream evaluator's parameter-shared actor and centralised critic. (`../external/vec_env/README.md`)

- **DDQN / DQN / DRL / IPPO / MAPPO / MARL / PPO.** DQN is Deep Q-Network and DDQN its
  value-overestimation-reducing variant; DRL is Deep Reinforcement Learning. MARL is Multi-Agent
  Reinforcement Learning, PPO is Proximal Policy Optimisation, MAPPO its multi-agent form, and IPPO
  the independent-agent variant. (`docs/dissertation_appendices/abbreviations.md`)

- **Decision codes.** `R1` is the upstream `tos-data` re-pin choice; `N1` was the Manchester
  network re-pin/recovery question and is withdrawn after the 28 July identity correction;
  `E1–E5` are the demand-rebuild signing choices, and `G1–G5` are the bus-study
  choices. `D1–D6` is overloaded between the capacity-pilot and stadium documents and must be
  qualified by file; the actor draft's `G6` reference is orphaned rather than a sixth bus choice.
  (`docs/owner_action_pack_20260727.md`; `docs/evaluation/demand_rebuild_predeclaration.md`;
  `docs/evaluation/bus_fleet_experiment_predeclaration_draft.md`;
  `docs/evaluation/stadium_event_study_draft.md`)

- **DfT.** The UK Department for Transport, whose road-count data provides historical observations.
  Survey counts and AADF are kept distinct, with unresolved local-clock alignment stated rather
  than converted by assumption. (`docs/dissertation_appendices/abbreviations.md`;
  `docs/integration/manchester_dft_adapter.md`)

- **Digest / fingerprint / SHA-256.** A digest is the cryptographic identity of exact bytes; this
  project uses SHA-256. A fingerprint is usually the SHA-256 identity of a canonicalised typed
  design or record, so semantically identical inputs have one stable identity and drift is visible.
  (`docs/architecture.md`; `docs/integration/vec_campaign_execution.md`)

- **EV.** In uppercase, electric-vehicle state in the VEC source arrays—not a demographic or
  protected attribute. It must not be confused with lowercase `ev`, the event-night trace code.
  (`docs/traffictwin-design-v0_6.md`; `docs/dissertation_appendices/trace_provenance.md`)

- **Evaluator seed.** Internal evaluator randomness fixed separately from the fleet seed. The
  capacity studies hold evaluator seed `0` constant, so it is not the replicate used for pairing.
  (`docs/evaluation/capacity_squeeze_pilot_predeclaration.md`)

- **EvidencePack.** A versioned structured handoff of validation state, evidence availability,
  metric collection, context, warnings, and provenance passed to diagnostics or reports. It omits
  raw/canonical rows, so row tracing still needs the original bundle; the boundary prevents a
  renderer from acquiring or inventing evidence. (`docs/evidence_pack_spec.md`;
  `docs/decisions/ADR-004-evidencepack-boundary.md`)

- **FCD.** Floating Car Data: time-sampled per-vehicle position and speed. In this project it is
  simulator-produced, not observed road telemetry, and VEC-06 accepts only a one-second FCD plus
  its matching network under declared controls. (`docs/dissertation_appendices/abbreviations.md`;
  `docs/integration/vec_fcd_preprocessing.md`)

- **Fleet seed.** The seed selecting a vehicle-fleet realisation. Reusing the same fleet seed
  across arms creates the common replicate used by paired statistics. (`docs/evaluation/capacity_squeeze_pilot_predeclaration.md`)

- **GA-*.** A source-prefixed Gate-A gap/blocker identifier, such as the unresolved DfT hour
  timezone. A GA code keeps missing evidence visible and blocks only claims that need it.
  (`docs/integration/manchester-source-gate-a-audit-v0_7.md`; `docs/assumption-register.md`)

- **Gates A–G.** The v0.6 VEC chain is Gate A source audit, B contract/fixtures, C imports/joins,
  D FCD preprocessing, E runner/reproduction, F scientific admission, and G interfaces/research
  publication. The separate v0.7 Manchester scheme has only A–F: source audit, immutable adapters,
  product workflow, SUMO mapping/calibration/comparison, VEC/evaluation, then compatibility/release;
  the same letter therefore means different work in the two designs. (`docs/traffictwin-design-v0_6.md`;
  `docs/traffictwin-design-v0_7.md`)

- **GEH.** A traffic-engineering goodness-of-fit statistic comparing modelled and observed flows.
  Whether it is an acceptance criterion, and its threshold, remain owner/supervisor decisions.
  (`docs/dissertation_appendices/abbreviations.md`; `docs/evaluation/supervisor_contract_decision_form.md`)

- **Grant.** In `AGENTS.md`, a grant gives a session permission to work on a bounded file set; it
  is not ownership of the whole feature, permission to widen scientific claims, or permission to
  edit another session's files. (`AGENTS.md`; `CLAUDE_SESSION_CONTEXT_PROMPT.md`)

- **GTFS-RT.** General Transit Feed Specification Realtime, an optional BODS live-feed format. Its
  exact path is sign-in-gated, so the accepted current path uses hardened SIRI-VM rather than
  assuming GTFS-RT availability. (`docs/integration/manchester-source-gate-a-audit-v0_7.md`)

- **Held-out seeds.** Replicates reserved before exploratory results and excluded from pilot
  pooling. Seeds 10–14 belong only to the capacity confirmatory study and require explicit
  held-out authorisation. (`docs/evaluation/capacity_squeeze_pilot_predeclaration.md`;
  `docs/evaluation/capacity_confirmatory_candidate_b_latency_primary.md`)

- **HMAC.** Hash-based Message Authentication Code. The bus work uses session-scoped HMAC tokens
  so a short attended session can link its own observations without publishing stable vehicle
  identities across sessions. (`docs/evaluation/bus_data_experiment_options.md`)

- **Import-first.** The guaranteed mode is analysis of artifacts produced elsewhere. Controlled
  execution is an additional, narrowly gated path and never changes that baseline promise.
  (`docs/decisions/ADR-001-import-first-architecture.md`; `docs/traffictwin-design-v0_6.md`)

- **ING / MET / DIA / EXP / PRO / REP / OPS.** Stable capability families for ingestion,
  metrics, diagnostics, experiments, provenance, reporting, and operations. Their identifiers
  name implemented software contracts, not scientific conclusions. (`docs/implementation-status.md`;
  `docs/dissertation_appendices/appendix_a_capability_catalogue.md`)

- **ITS.** Intelligent Transport Systems: sensing, communication, computation, and control applied
  to transport. (`docs/dissertation_appendices/abbreviations.md`)

- **JAX / JAXLIB.** The pinned numerical runtime used by Randy's evaluator. VEC-07 verifies the
  audited environment and dependencies before execution rather than treating any installed JAX as
  equivalent. (`docs/integration/vec_evaluator_runner.md`; `../external/vec_env/README.md`)

- **Knee rule.** The pilot's predeclared rule selected the lower capacity after the largest
  adjacent drop in deadline-success rate. Deadline success did not drop, so the rule honestly
  selected no knee. (`docs/evaluation/capacity_squeeze_pilot_predeclaration.md`;
  `docs/evaluation/capacity_pilot_results_20260727.md`)

- **Label ladder.** Permitted scientific labels include `owner_approved_candidate`,
  `analyst_reviewed_candidate`, `descriptive_non_causal`, and
  `held_out_candidate_evaluation`; each says who authorised or reviewed what, not that it is true
  everywhere. `scientifically_validated`, `ground_truth`, `publication_approved`, `causal`, and
  `production_deployment_ready` are forbidden because the evidence is bounded, partly reconstructed
  or synthetic, non-causal, and lacks the necessary supervisor/publication/production acceptance.
  (`AGENTS.md`; `docs/evaluation/capacity_squeeze_pilot_predeclaration.md`)

- **Lead / integrator.** The coordinating agent who owns cross-feature reconciliation, shared-file
  integration, status truth, and final handoff. It does not acquire the owner's scientific or
  external-communication authority. (`AGENTS.md`; `CURRENT_STATUS_CONTEXT_PROMPT.md`)

- **LLM / XAI.** Large Language Model and Explainable Artificial Intelligence. An LLM may only
  restate already computed evidence under constraints; it does not calculate TrafficTwin metrics
  or establish a diagnosis, while XAI remains a proposed framing rather than an accepted result.
  (`docs/architecture.md`; `docs/owner_action_pack_20260727.md`)

- **MAE / RMSE.** Mean Absolute Error and Root Mean Squared Error, possible observed-versus-SUMO
  comparison measures. They remain unavailable until the MAN-10 comparison contract fixes pairing,
  units, coverage, exclusions, and interpretation. (`docs/traffictwin-design-v0_7.md`;
  `docs/evaluation/supervisor_contract_decision_form.md`)

- **MAN-01 … MAN-11.** The Manchester families are: snapshot/source contract; DfT counts;
  WebTRIS; TfGM signals; BODS transit; optional Randy bridge; projection/freshness; Operations UI;
  observation-to-SUMO baseline; observed-versus-simulated comparison; and Manchester SUMO-to-VEC.
  The canonical design still labels all eleven `planned` until their complete gates pass, even
  where substantial candidate software exists. (`docs/traffictwin-design-v0_7.md`;
  `docs/traffictwin-design-v0_7_beta-goals.md`)

- **MetricCollection.** A versioned ordered metric artifact for one admitted run and its evidence
  identity; it may be stored in the registry or embedded in an EvidencePack. A statistical study
  reads collections; it does not
  re-parse simulator files or silently fill unavailable metrics. (`docs/architecture.md`;
  `docs/integration/vec_fresh_run_admission.md`)

- **Morocco principle.** A useful study must allow the expected winner or expected effect to lose;
  otherwise the scene is too trivial to teach anything. The pilot is the current example: the
  expected deadline cliff was refuted, revealing a policy that did not adapt to the capacity
  control. (`docs/traffictwin-design-v0_4.md`;
  `docs/evaluation/capacity_pilot_results_20260727.md`;
  `~/Downloads/diss_mat/EVIDENCE_MAP.md`)

- **netconvert.** SUMO's network-construction program. The Greater Manchester candidate fixed
  SUMO/netconvert 1.27.1 and reads projection information back from the output rather than assuming
  it. A later recovery initially failed because an internal record confused compressed-source and
  decoded-XML identities; the correction reproduced the original canonical network and withdrew
  the provider-mutation claim. (`docs/decisions/ADR-059-greater-manchester-baseline-network.md`;
  `docs/integration/manchester_workspace_continuity_20260727.md`)

- **NOC.** National Operator Code, used as the only acceptable basis for the proposed Bee Network
  operator allowlist. Display name or geography is not a membership test. (`docs/decisions/ADR-057-bee-network-membership-identifiers.md`)

- **npz.** A compressed NumPy archive containing arrays. Randy's trace `.npz` stores the padded,
  time-indexed simulator tensors; its hash and paired occupancy file together define the reviewed
  trace identity. (`../external/tos-data/DATA_DICTIONARY.md`;
  `docs/dissertation_appendices/trace_provenance.md`)

- **Objectives O1–O7.** The dissertation spine covers contracts, deterministic metrics/rules,
  statistical comparison, what-if analysis, research UX, Manchester evaluation, and correctness /
  reproducibility / usability. O1–O5 are recorded implemented; O6 is split between exploratory
  pilot and in-progress confirmation; O7 usability is pending ethics. (`docs/dissertation_appendices/objectives_traceability.md`)

- **Occupancy.** A table of inclusive time spans saying which real SUMO vehicle occupies each
  reusable padded trace slot. It prevents slot number from being mistaken for a permanent vehicle
  identity. (`docs/integration/vec_identity.md`; `../external/tos-data/DATA_DICTIONARY.md`)

- **ODbL / OGL.** Open Database Licence and Open Government Licence. OSM is carried under ODbL,
  while several UK public sources use OGL; source licence and publication class remain attached to
  snapshots and derivatives. (`docs/integration/manchester-source-gate-a-audit-v0_7.md`;
  `docs/integration/manchester_network_decision_worksheet.md`)

- **ONS.** Office for National Statistics, the source of standard geography codes and reviewed
  boundary context used to scope Manchester layers. (`docs/dissertation_appendices/abbreviations.md`;
  `docs/traffictwin-design-v0_7.md`)

- **OSM / Geofabrik / PBF.** OpenStreetMap is the geographic database; Geofabrik distributes
  regional OSM extracts, including compact Protocolbuffer Binary Format (PBF). The project chose a
  dated Greater Manchester extract under ODbL. N1 initially misidentified the decoded XML digest
  as the compressed source digest; re-examination proved no provider mutation and reproduced the
  original network identity.
  (`docs/decisions/ADR-059-greater-manchester-baseline-network.md`;
  `docs/integration/manchester_workspace_continuity_20260727.md`)

- **P50 / P95 / P99.** Deterministic sample percentiles; P99 is a high-tail descriptive statistic,
  not a maximum or confidence bound. (`docs/metrics_catalogue.md`)

- **Pairing.** Comparing the same fleet seed across arms so nuisance variation is removed before
  calculating a difference. Missing cells are reported and never imputed; unpaired traces such as
  `ev` versus `inc` must not be presented as paired. (`docs/statistical_studies.md`;
  `docs/evaluation/stadium_event_study_draft.md`)

- **Phase claim.** An append-only `AGENTS.md` record reserving a numbered unit of work, its exact
  files, boundaries, result, and verification. It is how concurrent sessions avoid silently
  overlapping claims. (`AGENTS.md`; `PARALLEL_FEATURES_MASTER_PROMPT_6.md`)

- **Predeclaration.** A research question, controls, endpoints, seeds, exclusions, analysis, and
  publishable null fixed before the relevant outcomes exist. Approval binds its exact bytes; a
  draft with unresolved `FILL-*` fields is not executable. (`docs/decisions/ADR-063-bounded-vec-campaign-execution.md`;
  `docs/evaluation/capacity_confirmatory_protocol_draft.md`)

- **Publishable null.** The promise to report an absent or contrary effect with equal prominence
  instead of changing the story after looking at results. It made “no deadline knee” a result,
  not a failed experiment. (`docs/dissertation_appendices/abbreviations.md`;
  `docs/evaluation/capacity_pilot_results_20260727.md`)

- **Quarantine.** The private, immutable-before-parse area holding exact acquired bytes and safe
  request metadata. Validation failure leaves quarantine intact and creates no accepted snapshot;
  a later promotion must reverify identical provenance. (`docs/integration/manchester_snapshot_service.md`;
  `docs/decisions/ADR-054-bounded-manchester-acquisition-transport-and-parsing.md`)

- **R0 … R8.** The deterministic diagnostic candidates are evidence insufficiency, under-offloading,
  infrastructure bottleneck, scenario triviality, load imbalance, training/validation drift,
  temporal degradation/recovery, operational disparity, and completed-task energy anomaly. They
  are evidence-linked hypotheses, not proven causes. (`docs/dissertation_appendices/abbreviations.md`;
  `docs/diagnostic_rules.md`)

- **Receipt.** A machine-readable record of what a bounded operation requested, checked, produced,
  hashed, and decided. Re-reading and re-hashing a receipt can prove consistency of artifacts, but
  not that the design was scientifically good or that a result reproduced numerically.
  (`docs/integration/vec_campaign_verification.md`)

- **Registry.** The local SQLite catalogue of runs, bundles, metric collections, plans, annotations,
  and evidence identities. Writes are transactional and idempotent by fingerprint; a conflicting
  existing identity refuses instead of being overwritten. (`docs/architecture.md`;
  `docs/decisions/ADR-007-sqlite-metadata-registry.md`)

- **REL-01.** The v0.7 release-isolation capability: separate workspaces, registries, caches,
  compatibility copies, migration backup/refusal, and rollback while v0.6 stays immutable. Its
  canonical capability status remains `planned`. (`docs/traffictwin-design-v0_7.md`;
  `docs/v07_release_compatibility.md`)

- **RSU.** Roadside Unit: fixed roadside communication and edge-compute infrastructure. In the
  capacity study, `rsu_capacity_per_vehicle` is the evaluator's concurrent-task bound per padded
  vehicle; it is not RSU count, bandwidth, CPU, or a hardware measurement. (`docs/dissertation_appendices/abbreviations.md`;
  `docs/evaluation/capacity_squeeze_pilot_predeclaration.md`)

- **SIRI-VM.** Service Interface for Real Time Information — Vehicle Monitoring, the XML profile
  through which BODS exposes live vehicle positions. (`docs/dissertation_appendices/abbreviations.md`)

- **Snapshot.** An immutable source acquisition with request/retrieval metadata, byte inventory,
  hashes, licence/publication class, validation findings, and a receipt. A new retrieval is new-only;
  accepted state is never replaced by a failed refresh. (`docs/integration/manchester_snapshot_service.md`)

- **STA-01 … STA-05.** The statistical methods are paired baseline-versus-variation study,
  common-seed N-way ranking, paired TOST equivalence, versioned regression gates, and prospective
  paired power planning. A method code explains how a number was produced, not whether its claim
  is accepted. (`docs/statistical_studies.md`; `docs/n_way_ranking.md`;
  `docs/equivalence_testing.md`; `docs/regression_gates.md`; `docs/power_analysis.md`)

- **Study Case 1 / Study Case 2.** Study Case 1 is resource monitoring: which RSU is overloaded
  and by how much, now exposed through the per-RSU drill-down. Study Case 2 is controlled
  VEC what-if experimentation; the capacity squeeze is its first predeclared result. (`AGENTS.md`;
  `docs/owner_action_pack_20260727.md`)

- **SUMO.** Simulation of Urban MObility, the microscopic traffic simulator that produces the
  traffic/network layer and FCD used upstream of VEC. (`docs/dissertation_appendices/abbreviations.md`)

- **T / maxN.** `T` is trace time-step count and `maxN` the padded vehicle-slot width. Padding is
  meaningful only with the active mask and occupancy spans. (`docs/dissertation_appendices/trace_provenance.md`;
  `../external/tos-data/DATA_DICTIONARY.md`)

- **TOS.** Task Offloading Simulator, Randy's vehicular-edge simulator/evaluator namespace whose
  artifacts TrafficTwin imports and analyses. (`docs/dissertation_appendices/abbreviations.md`;
  `../external/tos-data/README.md`)

- **TOST.** Two One-Sided Tests, the STA-03 practical-equivalence method. Both one-sided nulls must
  reject and the interval must lie inside a predeclared original-unit margin; ordinary
  non-significance is not equivalence. (`docs/equivalence_testing.md`)

- **Trace codes.** `we` is the admitted weekend 12:00–21:00 trace; `wd_am` is refused
  weekday morning 08:00–11:00; `wd_pm` is refused weekday afternoon/evening 14:00–21:00; `inc` is
  the admitted Friday 15 March 2024 incident/VSL-collapse hour 20:00–21:00; and `ev` is the admitted
  Champions League event night 17:30–24:00 in the Etihad/Co-op Live district. The upstream rationale
  for the first three is not restated because its sidecar commit is absent from the deliberately
  unfetched pinned clones. (`docs/dissertation_appendices/trace_provenance.md`;
  `docs/evaluation/capacity_pilot_results_20260727.md`;
  `docs/decisions/ADR-062-inc-trace-allowlist-extension.md`;
  `docs/decisions/ADR-065-ev-trace-allowlist-extension.md`)

- **tripinfo.** SUMO's per-vehicle trip-completion XML. TrafficTwin preserves the raw source and
  reports exact matched eligibility and boundary/missing exclusions rather than treating every
  trace vehicle as a completed journey. (`docs/integration/vec_trip_join.md`;
  `docs/traffictwin-design-v0_6.md`)

- **Unavailable.** A typed state saying required evidence or compatibility is absent. It is never
  represented as zero, blank, or a convenient default. (`docs/metrics_catalogue.md`;
  `docs/dissertation_appendices/abbreviations.md`)

- **UTC / BST.** Coordinated Universal Time and British Summer Time. Source time bases remain
  typed; absolute instants may display in `Europe/London`, while date-only or undocumented local
  values are never invented as UTC. (`docs/decisions/ADR-055-manchester-time-basis.md`)

- **UX-01 … UX-03.** Task-oriented navigation, map-led home/research workflow, and responsive /
  accessible visual system. Much is working as candidate evidence, but the canonical design keeps
  all three `planned` until the complete browser, version, accessibility, and release gates pass.
  (`docs/traffictwin-design-v0_7.md`; `docs/v07_navigation.md`)

- **V2I / V2V / V2X.** Vehicle-to-Infrastructure links vehicles to fixed infrastructure; V2V is
  direct Vehicle-to-Vehicle communication; V2X is the umbrella Vehicle-to-Everything term.
  (`docs/dissertation_appendices/abbreviations.md`)

- **VEC.** Vehicular Edge Computing: computation delivered near vehicles, here primarily through
  RSUs to which vehicle tasks may be offloaded. (`docs/dissertation_appendices/abbreviations.md`)

- **VEC-01 … VEC-12.** In order: source audit; source contract; occupancy identity; task/action /
  target joins; trip joins; FCD preprocessing; safe evaluator runner; reproduction check;
  evidence-strengthened metrics/rules; thin CLI/UI; sanitised dissertation pack; end-to-end
  reproducibility artifact. All are accepted only within their recorded source, permission,
  scientific, and publication limits. (`docs/traffictwin-design-v0_6.md`)

- **VMS.** Variable Message Sign. Current National Highways status evidence does not guarantee the
  literal displayed sign text, so the UI must not invent it. (`docs/integration/manchester_national_highways_operational_feeds.md`)

- **VSL.** Variable Speed Limit. The `inc` trace represents the documented reactive-rule /
  speed-limit-collapse incident hour; the label does not turn simulator evidence into observed
  road truth. (`docs/decisions/ADR-062-inc-trace-allowlist-extension.md`;
  `docs/evaluation/capacity_squeeze_pilot_predeclaration.md`)

- **WCAG.** Web Content Accessibility Guidelines. UX-03's manual Gate-C checklist targets WCAG
  2.2 AA checks that automated Streamlit tests cannot accept on a person's behalf.
  (`docs/evaluation/manual_accessibility_checklist.md`; `docs/traffictwin-design-v0_7.md`)

- **WebTRIS.** National Highways' strategic-road traffic-data service. Its exact time semantics
  remain source-declared rather than assumed. (`docs/dissertation_appendices/abbreviations.md`;
  `docs/decisions/ADR-055-manchester-time-basis.md`)

- **Worktree.** A Git checkout attached to a branch. The integration, owner, and historical Claude
  UI worktrees deliberately coexist, so branch, ignored evidence, and untracked owner files must be
  checked before any commit. (`AGENTS.md`; local Git worktree metadata)

This glossary was completed after a capitalised-acronym and house-term sweep across `docs/`, the
root coordination prompts, and the two external README/data-dictionary sources. Common file-format
and governance terms were included where they affect how repository claims should be read.

## 3. The map of files

| Local path | What it is | Storage status |
|---|---|---|
| `~/AntigravityTest/diss-integration/` | Lead/integration worktree on `claude/complete-v0.7`; this guide's authoritative working tree. | Git worktree; source/docs committed, runtime evidence ignored. (`AGENTS.md`; local `.git` worktree metadata) |
| `~/AntigravityTest/diss/` | Owner's separate checkout on `codex/traffictwin-v0.7`; do not use it as the integration commit target. | Local Git worktree. (`AGENTS.md`; local Git worktree metadata) |
| `~/AntigravityTest/diss-claude-ui/` | Historical Claude UI worktree on `claude/ui-redesign`, retained separately from the integration branch. | Local Git worktree. (`CLAUDE_SESSION_CONTEXT_PROMPT.md`; local Git worktree metadata) |
| `~/AntigravityTest/diss/year_1_report_randy_11315534.pdf` | Randy's Year-1 report retained in the owner's checkout for background. | Untracked owner file; deliberately untouched. (the PDF; local Git status, 27 July 2026) |
| `~/AntigravityTest/external/tos-data/` | Randy's traces, occupancy identities, task/run outputs, trip evidence, and dictionary. | External Git clone; read-only to TrafficTwin and deliberately unfetched. (`../external/tos-data/README.md`; `../external/tos-data/DATA_DICTIONARY.md`) |
| `~/AntigravityTest/external/vec_env/` | Randy's VEC simulator/evaluator source, runtime configuration, and reproduction tooling. | External Git clone; read-only to TrafficTwin and deliberately unfetched. (`../external/vec_env/README.md`; `docs/traffictwin-design-v0_6.md`) |
| `data/vec-fresh/smoke-envcheck/` | Short environment/preflight evidence, never scientific output. | Gitignored local runtime data. (local directory inventory, 27 July 2026; `.gitignore`) |
| `data/vec-fresh/full-protocol-run/` | Full weekend controlled-run output used in the reproduction/execution chain. | Gitignored local runtime data. (local directory inventory, 27 July 2026; `docs/integration/vec_reproduction_verification.md`; `.gitignore`) |
| `data/vec-fresh/inc-timing-probe-1/` | First full incident-trace timing-probe output associated with the recorded precision finding. | Gitignored local runtime data. (local directory inventory, 27 July 2026; `docs/evaluation/capacity_squeeze_pilot_predeclaration.md`; `.gitignore`) |
| `data/vec-fresh/capacity-pilot/` | Completed four-arm, three-seed exploratory campaign and its local analysis artifacts. | Gitignored local scientific runtime data; committed results live under `docs/evaluation/`. (`docs/evaluation/capacity_pilot_results_20260727.md`; `.gitignore`) |
| `data/vec-fresh/capacity-confirmatory/` | Live Candidate-B two-arm, five-held-out-seed campaign, including PID, log, receipts, and eventual analysis. | Gitignored local, protected while executing. (`scripts/capacity_confirmatory_campaign.py`; `.gitignore`) |
| `.demo/registry-fresh.sqlite` | Local fresh-run registry distinct from the two named campaign registries. | Gitignored local SQLite. (local directory inventory, 27 July 2026; `.gitignore`) |
| `.demo/registry-capacity-pilot.sqlite` | Pilot campaign plans, runs, and metric collections. | Gitignored local SQLite. (`scripts/capacity_pilot_campaign.py`; `.gitignore`) |
| `.demo/registry-capacity-confirmatory.sqlite` | Confirmatory campaign plans, runs, and metric collections. | Gitignored local SQLite; protected while executing. (`scripts/capacity_confirmatory_campaign.py`; `.gitignore`) |
| `~/AntigravityTest/diss/data/workspace-v0.7/` | Owner-local v0.7 evidence workspace: root quarantine/accepted snapshot areas; root registry/runs; and contract areas under `manchester/{raw,accepted,projections,mappings,calibrations,comparisons}`, plus cache, exports, and compatibility. | Gitignored because it is under the owner's `data/`. (`docs/owner_action_pack_20260727.md`; `docs/workspace_setup.md`; `docs/integration/manchester_snapshot_service.md`; local directory inventory, 27 July 2026) |
| `data/network-recovery/` | Phase-26 quarantined recovery area; currently holds the Greater Manchester OSM PBF whose chain halted at source verification. | Gitignored local recovery evidence. (`docs/integration/manchester_workspace_continuity_20260727.md`; `.gitignore`) |
| `docs/evaluation/capacity_confirmatory_candidate_b_latency_primary.md` | Operative latency-primary confirmatory predeclaration. | Committed and byte-frozen by its approval digest; never edit during/after the bound campaign. (`scripts/capacity_confirmatory_campaign.py`) |
| `~/Downloads/diss_mat/` | Owner-local dissertation skeleton, evidence map, rubrics/guidelines, sample reports, and private meeting working notes. | External private local material, not repository content; concepts may inform planning but private notes are not quoted. (`~/Downloads/diss_mat/DISSERTATION_SKELETON.md`; `~/Downloads/diss_mat/EVIDENCE_MAP.md`) |

The scientific audit records `tos-data` commit `f6c67ac…` and `vec_env` commit `068b4ea3…` as the
audited source identities, while the deliberately unfetched local clone heads observed on 27 July
were different. Claims must use the committed audit identities, not infer that today's checkout
head is the audited blob. (`docs/dissertation_appendices/trace_provenance.md`; local external-clone
`.git/HEAD` and Git object records)

## 4. How the science flows

A trace begins as a hashed `.npz` tensor paired with a hashed occupancy table. The trace supplies
time × padded-slot state; occupancy supplies the exact SUMO vehicle ID valid for each inclusive
span. VEC-06 can also create such a pair from a one-second SUMO FCD and matching network, but only
after it verifies source blobs, bounds, time spacing, projection, dependencies, and clean external
state. Refused traces (`wd_am`, `wd_pm`) cannot be made usable by a UI choice. (`docs/integration/vec_identity.md`;
`docs/integration/vec_fcd_preprocessing.md`; `docs/dissertation_appendices/trace_provenance.md`)

The VEC runner then constructs one fixed, shell-free evaluator command from a strict request. It
checks the trace allowlist and hash, checkpoint, scripts, environment, bounds, output isolation,
and timeout; it captures logs and a receipt and proves the external sources did not change. A
failed, cancelled, timed-out, mutated, truncated, or structurally invalid execution publishes no
accepted result. (`docs/integration/vec_evaluator_runner.md`; `docs/decisions/ADR-050-isolated-allowlisted-vec-evaluator-runner.md`)

Execution alone is not science. Fresh admission reopens the published directory, re-hashes the
receipt and outputs, requires full declared length and the reviewed source-run context, validates
the VEC-10 import and VEC-09 metric availability, and atomically registers the run plus its metric
collection. Trip-level metrics remain excluded where the fresh trace has no compatible trip
evidence, and every fresh admission remains explicitly reproduction-ungraded.
(`docs/integration/vec_fresh_run_admission.md`; `docs/decisions/ADR-061-vec-fresh-run-scientific-admission.md`)

The registry is the join point. A predeclared statistical study selects metric collections by
experiment, arm, metric key, and common fleet seeds; pairing is exact, missing cells are reported,
and the method emits a fingerprinted study record. Results documents and dissertation exports read
that record and its receipts, carry the label ceiling and limitations, and never promote a
descriptive association into a cause. An evidence pack is therefore the last mile of one chain,
not a manually assembled screenshot. (`docs/statistical_studies.md`; `docs/integration/vec_campaign_execution.md`;
`docs/evaluation/capacity_pilot_mechanism_report_20260727.md`)

The approval chain is separate and deliberately earlier:

```text
predeclaration → named approval of exact SHA-256 → campaign cells → admission → analysis/results
```

The predeclaration fixes question, arms, seeds, endpoints, exclusions, analysis, limits, and null.
Approval stores its exact digest and, for held-out seeds, explicit authorisation. Campaign launch
re-hashes those bytes before doing work; the analysis later refuses a receipt that does not match
the same design. Candidate B's bytes are therefore part of the experimental control, not prose to
tidy while the campaign runs. (`docs/decisions/ADR-063-bounded-vec-campaign-execution.md`;
`docs/evaluation/capacity_confirmatory_candidate_b_latency_primary.md`;
`scripts/capacity_confirmatory_campaign.py`)

The main fail-closed points are: wrong source commit/hash or dirty external state; disallowed trace;
missing/ambiguous occupancy; unsafe XML/archive/input size; checkpoint or argv drift; timeout,
cancellation, truncation, or output mutation; receipt/request/design mismatch; unapproved or
changed predeclaration; held-out use without authorisation; cell/byte budget breach; registry
identity conflict; missing paired cells; and unsupported metric/interpretation. A refusal remains
visible and blocks only the dependent claim. (`docs/traffictwin-design-v0_6.md`;
`docs/decisions/ADR-054-bounded-manchester-acquisition-transport-and-parsing.md`;
`docs/integration/vec_campaign_execution.md`; `docs/integration/vec_fresh_run_admission.md`)

## 5. Who does what

- **The repository owner, Abdulla,** chooses research direction, accepts or rejects scientific
  designs, resolves source/licensing and study decision queues, approves external communications,
  and decides what is sent to Sandra, Randy, Research IT, participants, or GitHub. Prepared emails
  and ethics documents remain drafts until the owner personally reviews/sends them.
  (`docs/owner_action_pack_20260727.md`; `AGENTS.md`)

- **Codex as lead/integrator** reconciles the repository-wide truth, allocates non-overlapping
  claims, protects shared files and live evidence, integrates completed slices, records boundaries,
  and hands the owner one coherent state. Phases 14–39 were the primary integration session's
  numbered claims; after the final below-40 claim, future primary work is reserved from Phase 80.
  (`AGENTS.md`; `PARALLEL_FEATURES_MASTER_PROMPT_6.md`)

- **The Claude session was the predecessor integration context:** its prompt originally designated
  Claude for the v0.7 phase work and its separate UI worktree remains as history. The later current-
  status prompt assigns Codex the sole lead/integrator role; neither context widens scientific or
  owner authority. (`CLAUDE_SESSION_CONTEXT_PROMPT.md`; `CURRENT_STATUS_CONTEXT_PROMPT.md`; `AGENTS.md`)

- **Parallel feature sessions** occupy Phases 40–71 in six master-prompt batches. Each phase must
  claim exact new/exclusive files, inherit the live-campaign and scientific boundaries, and leave
  shared integration decisions to the lead; Phases 72–79 are intentionally unused.
  (`PARALLEL_FEATURES_MASTER_PROMPT.md`; `PARALLEL_FEATURES_MASTER_PROMPT_2.md`;
  `PARALLEL_FEATURES_MASTER_PROMPT_3.md`; `PARALLEL_FEATURES_MASTER_PROMPT_4.md`;
  `PARALLEL_FEATURES_MASTER_PROMPT_5.md`; `PARALLEL_FEATURES_MASTER_PROMPT_6.md`; `AGENTS.md`)

Across every role, the hard boundaries are the same: do not mutate Randy's repositories; do not
touch a live campaign; do not edit digest-bound evidence; do not imply direct execution where only
import is accepted; do not widen candidate labels; do not expose credentials/private raw data; do
not claim a capability from code alone; and do not send external communications for the owner.
(`AGENTS.md`; `docs/traffictwin-design-v0_7.md`; `docs/dissertation_appendices/trace_provenance.md`)

## 6. Where things stand

**Status snapshot: 27 July 2026, 22:47:45 BST (UTC+01:00).** This is deliberately a timestamped
observation, because the detached confirmatory process continued after the guide was written.

The capacity pilot is complete: four arms × three fleet seeds, all 12 cells completed and admitted,
12.47 compute-hours and about 1.17 GB. Deadline success was essentially flat/slightly higher from
about 0.790412 to 0.790737, so the predeclared degradation knee did not occur. Mean task latency
fell from about 9,798.8 ms to 3,083.6 ms; every seed had the same descending order, although pooled
per-arm ranges overlap. Offload and no-eligible-target rates were invariant within each seed. This
is forever exploratory, `owner_approved_candidate`, descriptive and non-causal—not a significance,
generalisation, or deployment claim. (`docs/evaluation/capacity_pilot_results_20260727.md`;
`docs/evaluation/capacity_pilot_mechanism_report_20260727.md`)

The confirmatory Candidate B campaign was live at the timestamp: PID `49470` was alive, eight cell
directories containing `execution_receipt.json` existed for both arms at seeds 10–13, and the
temporary `cap-2.5-fs14` directory showed the ninth cell in progress. The top-level
`campaign_receipt.json` still recorded the earlier halted attempt (one admission conflict and nine
skips), because the detached relaunch writes the replacement campaign receipt only on return; no
confirmatory analysis or result was therefore available yet. Do not analyze, verify full payloads,
or cite an outcome until the live PID is gone and the final receipt reconciles all ten cells.
(`data/vec-fresh/capacity-confirmatory/launcher.pid`;
`data/vec-fresh/capacity-confirmatory/launch.log`;
`data/vec-fresh/capacity-confirmatory/campaign_receipt.json`;
`scripts/capacity_confirmatory_campaign.py`; local directory inspection at the timestamp)

There is also a post-execution tooling blocker: the confirmatory script calls the generic analysis
with its default `MAXIMISE` objective even though Candidate B predeclares latency to be minimised,
and the generic model hard-codes an exploratory/non-confirmatory stance plus pilot-specific
limitations. Its `analyze` subcommand must not be treated as the final confirmatory analysis until
those contracts are corrected and reviewed. (`scripts/capacity_confirmatory_campaign.py`;
`src/traffictwin/integration/vec_campaign/analysis.py`;
`docs/evaluation/capacity_confirmatory_candidate_b_latency_primary.md`)

Approval state needs careful wording. The pilot predeclaration was approved through relayed owner
delegation before its results. Candidate A is explicitly not chosen. Candidate B is the operative
latency-primary design: a relayed in-session owner delegation is recorded, its SHA-256 is
`ac9d6cb7cd24f19ba683352cd3d12d91cbd610343ac392028feb53797bbae2a8`, and the execution object has
`held_out_authorised=true`. Its conventional checkboxes remain blank and it is not an owner-typed
or supervisor signature, but the bytes are approval-bound and frozen. The generic confirmatory
protocol, actor, bus, stadium, demand, ethics, consent, participant, accessibility, and supervisor
contract documents remain drafts/unsigned unless their own text says otherwise.
(`docs/evaluation/capacity_squeeze_pilot_predeclaration.md`;
`docs/evaluation/capacity_confirmatory_candidate_a_null_descriptive.md`;
`docs/evaluation/capacity_confirmatory_candidate_b_latency_primary.md`;
`scripts/capacity_confirmatory_campaign.py`; `docs/evaluation/README.md`)

The recorded owner decision queue is:

1. Confirm the dissertation emphasis (offloading versus journey time), algorithm-combination scope,
   and explainability/trust framing with Sandra. (`docs/owner_action_pack_20260727.md`)
2. Ask Randy to confirm the baseline checkpoint and written aggregate/publication permission;
   separately choose the `tos-data` re-pin (`R1`). (`docs/owner_action_pack_20260727.md`)
3. Review the final confirmatory analysis/result only after completion. (`docs/owner_action_pack_20260727.md`)
4. Confirm and submit ethics values/materials; all current participant documents describe zero
   completed sessions. (`docs/evaluation/ethics_application_draft.md`;
   `docs/evaluation/user_evaluation_instrument_draft.md`)
5. Resolve demand choices `E1–E5`. The former network-recovery question `N1` is withdrawn; the
   internal source/decoded-identity error and its correction remain evidence to report.
   (`docs/integration/manchester_workspace_continuity_20260727.md`;
   `docs/evaluation/demand_rebuild_predeclaration.md`)
6. Resolve bus choices `G1–G5`, the actor-crossover checkpoint-method choice plus its remaining
   levels/seeds/cost/signing items, and the stadium file's context-local `D1–D6` choices.
   (`docs/evaluation/bus_fleet_experiment_predeclaration_draft.md`;
   `docs/evaluation/actor_crossover_study_draft.md`;
   `docs/evaluation/stadium_event_study_draft.md`)
7. Obtain supervisor decisions for MAN-09/MAN-10 scientific contracts and complete the human
   Gate-C accessibility checklist. (`docs/evaluation/supervisor_contract_decision_form.md`;
   `docs/evaluation/manual_accessibility_checklist.md`)

Some documents linked by this 27 July handbook are historical snapshots. The current workflow and
release records have since been reconciled; the confirmatory protocol still retains pre-pilot
boilerplate because its later annotation records completion and Candidate B's selection. For
current trace admission use ADR-065/trace provenance; for current pilot science use the dated
result/mechanism record; for capability truth use the canonical design and current status records.
(`docs/current_workflow_and_todo.md`;
`docs/evaluation/capacity_confirmatory_protocol_draft.md`;
`docs/decisions/ADR-065-ev-trace-allowlist-extension.md`;
`docs/dissertation_appendices/trace_provenance.md`; `docs/implementation-status.md`)

## 7. How to do common things

Run these from `~/AntigravityTest/diss-integration`. Do not run the gate battery, campaign verifier,
analysis, or other sustained work while the confirmatory PID is alive. (`AGENTS.md`;
`docs/integration/vec_campaign_verification.md`)

**Launch the standalone UI** (the launch command initialises a missing demo workspace):

```bash
uv run traffictwin demo launch .demo
```

Use `uv run traffictwin demo status .demo` first to inspect it, or append `--dry-run` to preview the
Streamlit command. (`docs/standalone_demo.md`)

**Run the full handoff gate battery** after the campaign is idle:

```bash
uv run python scripts/run_all_gates.py
```

It runs Ruff check/format, strict mypy, unit/UI/integration tests, and `git diff --check`
sequentially; `--list` prints the commands without running them. (`scripts/run_all_gates.py`)

**Check the live confirmatory campaign without mutating it:**

```bash
campaign_pid=$(<data/vec-fresh/capacity-confirmatory/launcher.pid)
ps -p "$campaign_pid" -o pid=,etime=,stat=,command=
find data/vec-fresh/capacity-confirmatory -maxdepth 2 \
  -name execution_receipt.json -print | sort
```

The campaign launcher has no `status` subcommand; its commands are `fingerprint`, `launch`, and
`analyze`. Do not re-run `launch` merely to ask for status. (`scripts/capacity_confirmatory_campaign.py`)

**After the PID has exited, inspect the final receipt:**

```bash
jq '{status, admitted_cell_count, failed_cell_count, skipped_cell_count}' \
  data/vec-fresh/capacity-confirmatory/campaign_receipt.json
```

Do **not** currently use `uv run python scripts/capacity_confirmatory_campaign.py analyze` as the
final confirmatory analysis: it defaults STA-01 to maximisation and emits a type-level exploratory
report, while Candidate B requires minimised latency and a separately reviewed held-out result.
After that contract is corrected, its intended machine outputs are
`data/vec-fresh/capacity-confirmatory/campaign_analysis.json` and `campaign_analysis.md`; a human
result record remains separate. (`scripts/capacity_confirmatory_campaign.py`;
`src/traffictwin/integration/vec_campaign/analysis.py`;
`docs/evaluation/capacity_confirmatory_candidate_b_latency_primary.md`)

**Offline consistency verification, only after execution finishes:**

```bash
uv run python scripts/verify_campaign.py \
  --design-module scripts/capacity_confirmatory_campaign.py \
  --design-attr confirmatory_design \
  --campaign-dir data/vec-fresh/capacity-confirmatory \
  --registry .demo/registry-capacity-confirmatory.sqlite
```

A PASS means the artifacts agree, not that the campaign succeeded or the finding is scientifically
accepted. Full output hashing is deliberately forbidden against a running campaign.
(`docs/integration/vec_campaign_verification.md`)

**Regenerate the machine-derived appendices and capacity figures:**

```bash
uv run python scripts/generate_dissertation_appendices.py
uv run python scripts/generate_quality_snapshot.py
uv run python scripts/generate_capacity_figures.py \
  data/vec-fresh/capacity-pilot/campaign_analysis.json --overwrite
uv run python scripts/generate_results_tables.py \
  data/vec-fresh/capacity-pilot/campaign_analysis.json --overwrite
```

The first writes Appendix A/B into `docs/dissertation_appendices/`; the quality command writes
`quality_snapshot.md` (collected counts are not passed tests); the figure command writes `.tex`,
`.svg`, and provenance under `docs/dissertation_appendices/figures/`. Only run the figure command
for an analysis whose labels and intended publication target have been reviewed. The results-table
command writes the arm descriptives and predeclared-comparison exports under
`docs/dissertation_appendices/tables/`. These commands intentionally point at the pilot: the
current figure generator hard-codes deadline-primary pilot semantics, and neither export should
be aimed at Candidate B until the confirmatory analysis contract above is corrected and its
labels are reviewed.
(`scripts/generate_dissertation_appendices.py`; `scripts/generate_quality_snapshot.py`;
`scripts/generate_capacity_figures.py`; `scripts/generate_results_tables.py`;
`docs/dissertation_appendices/figures/provenance.md`)

## 8. Where to read more

| Read this | Use it for |
|---|---|
| [`docs/traffictwin-design-v0_7.md`](traffictwin-design-v0_7.md) | Canonical Manchester/product scope, MAN/UX/REL capability definitions, and Gates A–F. |
| [`docs/traffictwin-design-v0_7_beta-goals.md`](traffictwin-design-v0_7_beta-goals.md) | What remains before beta, with blockers and acceptance targets. |
| [`docs/implementation-status.md`](implementation-status.md) | Detailed implemented/candidate/planned software inventory and evidence pointers. |
| [`docs/traffictwin-design-v0_6.md`](traffictwin-design-v0_6.md) | Accepted VEC-01–12 chain and its Gates A–G. |
| [`docs/dissertation_appendices/trace_provenance.md`](dissertation_appendices/trace_provenance.md) | Five trace identities, hashes, occupancy evidence, rights, and admission state. |
| [`docs/integration/vec_fresh_run_admission.md`](integration/vec_fresh_run_admission.md) | Exact fresh-execution-to-registry scientific admission rules. |
| [`docs/integration/vec_campaign_execution.md`](integration/vec_campaign_execution.md) | Approval-bound campaign design, execution, resume, budgets, and analysis. |
| [`docs/evaluation/capacity_pilot_results_20260727.md`](evaluation/capacity_pilot_results_20260727.md) | Authoritative exploratory pilot finding and corrected limitations. |
| [`docs/decisions/index.md`](decisions/index.md) | Complete ADR register; start with ADR-054 through ADR-065 for current integration/science. |
| [`docs/dissertation_appendices/objectives_traceability.md`](dissertation_appendices/objectives_traceability.md) | O1–O7 dissertation spine and artifact-to-chapter lookup. |

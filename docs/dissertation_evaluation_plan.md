# Dissertation evaluation plan — reconciled after experiment completion

**Reconciled:** 1 August 2026
**Current manuscript:** `docs/dissertation_manuscript_20260801.md`

This plan separates evidence that can be reported now from evidence that is still unavailable. It
supersedes the earlier wording that described the held-out capacity campaign as “in progress”.
The result exists; its interpretation remains bounded.

## 1. Evidence hierarchy

| Level | Included work | Dissertation treatment |
|---|---|---|
| Protocol-confirmed within project scope | Signed latency-primary capacity comparison, seeds 10–14, cap 2.5 vs 0.75 | Central quantitative result. Report all five directions, −8,310.9 ms paired mean, bootstrap interval and p=0.0625 sign-test floor. Never call it externally validated or causal. |
| Post-hoc mechanism | Keyed actions, observation audit, tail distribution, vehicle/tier partition, failure concentration, RSU load | Explains the central result. Label the analyses post-hoc and retain the partial withdrawal of the RSU causal account. |
| Predeclared exploratory robustness/falsification | Ceiling prediction, actor crossover, normal-regime onset scaling | Report successes and refutations together: 27/27 ceiling checks held; actor slope and exact onset predictions were refuted. |
| Descriptive/non-admitted | Captured bus sessions, corridor preliminary, Sparse-64 full fresh rerun | Mobility corroboration only. State generated tasks/sites, ~45% coverage, VEC-06 incompatibility and duplicate-return deviation. |
| Software evidence | Canonical contracts, deterministic metrics, provenance, campaign receipts, tests, golden outputs, UI | Establishes instrument correctness/reproducibility within tested boundaries; does not validate the scientific model. |
| Human evaluation | Prepared instrument and owner-reported ethics submission | No result available: no approval reference, participants or response dataset. |

## 2. Central evaluation to report

### 2.1 Experimental unit and intervention

- One paired evaluator seed is the confirmatory unit.
- Five held-out seeds `{10, 11, 12, 13, 14}` were run at both arms.
- Baseline configured per-vehicle RSU concurrency was 2.5; variation was 0.75.
- Trace `inc` is one modelled 20:00–21:00 collapse hour in the Etihad/Co-op Live district,
  generated with SUMO seed 43. It is not city-wide Manchester.
- The actor is the supplied `ukfleettrain_mappo_model_c_17` checkpoint in
  `v2_post_nrsus_fix` with the `uk2030` fleet preset.

### 2.2 Primary and secondary outcomes

- Primary: paired difference in mean task latency, variation minus baseline.
- Uncertainty: paired non-parametric bootstrap interval from the signed report.
- Direction check: exact two-sided sign test; at n=5 the all-same-direction floor is 0.0625.
- Secondary: overall and T1/T2/T3 source-defined deadline attainment.
- Descriptive: action/target, compatible energy and task-count summaries.

“Deadline completion” means only that a generated compute task met its source deadline. It is not
vehicle trip completion, application correctness or physical service quality.

### 2.3 Required result chain

1. Establish that four normal traces are capacity-inert at pilot arms and only `inc` binds.
2. Present the pilot as hypothesis-generating, including its precommitted deadline null.
3. Present the signed held-out primary result and complete seed direction.
4. Show exact action invariance before interpreting the latency curve.
5. Decompose median, p99, >1 s population, latency mass and vehicle partitions.
6. Show the ceiling prediction, then both refuted predictions and the withdrawn RSU explanation.
7. End the results with B-BUS as non-admitted transfer evidence, not confirmation.

## 3. Software correctness and reproducibility

Report in proportion to the research argument:

- schema validation, stable refusal/finding codes and explicit unavailable values;
- source-to-canonical-to-metric provenance;
- directory/ZIP and deterministic-output checks;
- signed design digests, campaign-cell receipts and null-publication commitment;
- pinned producer environment/trace commits and engine version;
- current collected/pass counts, lint, typing and package checks from the final verification;
- the limitation that private producer inputs prevent fully open third-party reconstruction.

The standalone synthetic bundles demonstrate software behaviour and diagnostic rules only. They
must not be counted as independent real-data validation.

## 4. Research UX and video evaluation

The report evaluates the UX by implemented evidence-boundary properties: validated imports,
unavailable states, replay labelling, provenance navigation, append-only human review and
campaign receipts. It does not claim usability from implementation.

The 6–8 minute video should complement the report by showing interaction that print cannot:

- a one-sentence metric-reversal hook;
- historical replay with its badge;
- a continuous metric-to-source provenance walk;
- the signed protocol, receipt and held-out result;
- the tail/vehicle mechanism;
- one explicit limitation and one refuted prediction.

Participant usability evidence remains unavailable until institutional approval permits the
study and actual responses are collected. Mock fixtures verify the analyser only.

## 5. B-BUS treatment

Report the captured sessions separately from the synthetic VEC overlay.

Observed mobility facts include dawn/peak retained populations (961/1,212), peak concurrency
(827/1,000), occupied cells (66,291/72,208) and session-speed summaries. The VEC successor adds
synthetic tasks, equipment and 64 generated sites. Sparse-64 coverage is about 45%, outside the
accepted 2,000-cell/64-site VEC-06 boundary.

The retained fresh-rerun cap-0.75 result is 0.501355 completion (sample SD 0.088677; range
0.400527–0.634229); cap 2.5 is 0.501233. A terminal-state ordering failure caused a second return
after the first archive was downloaded, and the first archive was overwritten. Settings did not
change, but identity cannot be checked. The output is execution-deviated, descriptive and
non-admitted. No further spend is required to report that bounded observation.

## 6. Evidence still unavailable

| Evaluation/claim | Missing evidence or decision |
|---|---|
| Physical T1 completion or deployed service outcome | The source exposes task deadlines, not physical execution/application/safety completion. |
| Canonical deployed utilisation | The accepted source does not provide CPU utilisation; concurrency pressure is not CPU usage. |
| All-Manchester or causal traffic claim | The central trace is simulated and district-bounded; buses are transit observations, not general traffic. |
| Actor-family or algorithm superiority | One trained actor and a mismatched baseline/preset comparison cannot isolate algorithm effects. |
| Cause of four-RSU load concentration | Load asymmetry is measured, but the earlier association explanation was withdrawn. |
| Contract-compatible observed-mobility VEC confirmation | Requires a separately predeclared, fully covered geography with fixed infrastructure and honest synthetic/observed labels. |
| Participant usability result | Institutional approval plus recruited participants and a real response dataset. |
| Supervisor/external validation | An explicit human review/decision; never inferred from repository state. |

## 7. Suggested final report exhibits

Keep the body focused:

1. Evidence-flow diagram: source → canonical tables → metric → signed comparison → claim state.
2. Confirmatory paired latency figure.
3. Flat deadline-attainment figure.
4. Exact action-invariance figure.
5. One compact tail/vehicle-partition table.
6. One claim-status table containing held, refuted, withdrawn and non-admitted extensions.

Put capability catalogues, complete software versions, protocol digests, detailed arm tables and
B-BUS execution chronology in appendices. Every producer-derived exhibit must carry the Putra
environment/trace and SUMO citations in `docs/producer_citation_requirements.md`.

## Related documents

- [Complete dissertation manuscript](dissertation_manuscript_20260801.md)
- [Literature and claim matrix](dissertation_literature_matrix_20260801.md)
- [Objectives traceability](dissertation_appendices/objectives_traceability.md)
- [Consolidated experiment register](experiments_and_findings_20260728.md)
- [Video storyboard](video_storyboard.md)
- [Testing strategy](testing_strategy.md)

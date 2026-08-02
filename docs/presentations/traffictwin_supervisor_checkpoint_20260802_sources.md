# TrafficTwin supervisor checkpoint — source audit

**Artifact date:** 2 August 2026
**Scope:** four-slide supervisor communication artifact
**Editable source:** `traffictwin_supervisor_checkpoint_20260802.mjs`
**Editable deck:** `traffictwin_supervisor_checkpoint_20260802.pptx`
**Visually verified rendition:** `traffictwin_supervisor_checkpoint_20260802.pdf`

This audit controls the deck's non-trivial claims. Literature provides context and method only;
project measurements provide TrafficTwin-specific numbers; repository status/contract records
provide implementation and decision standing. LLM drafting is disclosed assistance, never a
measurement, citation, approval or evidence source. Each slide repeats its controlling sources in
a `[Sources]` speaker-note block.

## Slide 1 — TrafficTwin

| Visible claim | Source class | Controlling source | Permitted reading | Prohibited promotion |
|---|---|---|---|---|
| TrafficTwin is framed as a verifiable what-if loop for traffic and edge-computing research | Project documentation plus literature context | `../current_progress_v0_7.md`; `../implementation-status.md`; Fuller et al., DOI `10.1109/ACCESS.2020.2998358`; van der Valk et al., DOI `10.1016/j.compind.2022.103716` | Communication proposition for the repository instrument | No claim of production deployment, external validation, novelty verdict or scientific evidence from the deck |
| The deck is a supervisor checkpoint | Communication metadata | `supervisor_deck_and_bibliography_design.md` | Material prepared for discussion | Not supervisor approval, endorsement or a signed decision |

## Slide 2 — one loop, two lenses

| Visible claim | Source class | Controlling source | Permitted reading | Prohibited promotion |
|---|---|---|---|---|
| Observation, canonical twin, bounded what-if and evaluation/claim state form the research loop | Project contract plus literature context | `../architecture.md`; `../experiment_protocol.md`; `../platform/scenario_lifecycle_integration_design.md`; Fuller et al., DOI `10.1109/ACCESS.2020.2998358`; Jones et al., DOI `10.1016/j.cirpj.2020.02.002` | Designed repository workflow with auditable boundaries | Not a claim that a live physical twin is connected or continuously synchronised |
| Traffic/mobility and edge-policy/QoS are distinct analytical lenses | Literature context plus project design | Wang et al., DOI `10.1016/j.trc.2023.104014`; Nguyen et al., DOI `10.1016/j.scs.2023.104847`; Shi et al., DOI `10.1109/JIOT.2016.2579198`; Mao et al., DOI `10.1109/COMST.2017.2745201`; `../platform/capacity_aware_benchmark_design.md` | A bounded two-lens analysis structure | Not proof that either lens is calibrated for real Manchester |
| LLM drafting sits outside the evidence path | Project safety contract | `../platform/decision_safety_layer_design.md`; `../reproducibility.md` | Drafting may propose or explain while signed contracts and admitted records control execution/claims | No LLM output is a source, scientific result, operator instruction or approval |

## Slide 3 — bounded evidence result

| Visible claim | Source class | Controlling source | Permitted reading | Prohibited promotion |
|---|---|---|---|---|
| Mean latency was 12,027.5 ms at capacity 2.5 and 3,716.6 ms at capacity 0.75 | Project measurement | `../evaluation/capacity_confirmatory_results_20260728.md`; `../evaluation/capacity_confirmatory_report_20260728.md` | Arm means in the signed five-seed modelled comparison | Not an observed real-road result or cross-algorithm claim |
| Paired mean was −8,310.9 ms; all five seeds had the same direction; deadline attainment was flat | Project measurement | `../evaluation/capacity_confirmatory_results_20260728.md`; `../dissertation_evaluation_plan.md` | Protocol-confirmed within the signed project design | Not causal, externally validated, statistically universal or a service-success improvement |
| There were zero action mismatches in 8,956,800 keyed decisions in each of nine pilot pairs | Project audit measurement | `../integration/evidence/vec_pilot_keyed_action_comparison_20260728.json`; `../evaluation/capacity_study_detailed_findings.md` | Exact invariance in the admitted pilot artifacts | Not proof for other checkpoints, algorithms, seeds or environments |
| p50 stayed 44.3 ms; 97.9–99.4% of latency mass exceeded one second; neither subgroup saw the fleet mean | Project post-hoc analysis | `../evaluation/offload_partition_analysis_20260729.md`; `../evaluation/capacity_study_detailed_findings.md` | Mechanism-bounding description of admitted artifacts | Not a predeclared causal mechanism or population-general result |
| Tail-aware and protocol-disciplined interpretation is necessary | Literature context | Dean and Barroso, DOI `10.1145/2408776.2408794`; Nosek et al., DOI `10.1126/science.aab2374`; Gorsane et al., DOI `10.52202/068431-0398` | Methodological context only | Literature does not manufacture or independently validate the project measurements |

## Slide 4 — standing and decisions

| Visible claim | Source class | Controlling source | Permitted reading | Prohibited promotion |
|---|---|---|---|---|
| The auditable instrument, bounded what-if lifecycle, decision-safety layer and read-only contract browsers are implemented | Repository status | `../implementation-status.md`; `../current_progress_v0_7.md` | Current repository implementation standing | Not production acceptance or a live-deployment claim |
| The evidence set contains one signed central result while deviations, refutations and unavailable states stay visible | Project evidence/status | `../dissertation_evaluation_plan.md`; `../evaluation/experiment_catalogue_20260730.md` | Bounded project evidence description | Not a claim that all hypotheses held or all gaps are resolved |
| Multi-algorithm portfolio/benchmark work is a direction after inputs exist | Unsigned project design | `../evaluation/capacity_multi_algorithm_benchmark_predeclaration_20260802.md`; `../platform/capacity_aware_benchmark_design.md` | Candidate future protocol and infrastructure direction | Not executed evidence, funded compute or an approved study |
| Gate-D review, the next confirmatory design/compute envelope and an ethics-gated usability/final-report decision are requested | Unsigned decision material | `../integration/manchester_gate_d_integration.md`; `../open-questions.md`; `../evaluation/supervisor_contract_decision_form.md`; `../dissertation_evaluation_plan.md` | Questions for the responsible humans | Not a recorded supervisor decision, named-person review, ethics approval or publication decision |

## Artifact verification

- The PPTX was generated with `@oai/artifact-tool` from the committed ES module. All visible
  elements are editable native text, shape, connector or chart objects.
- Four slide PNGs were rendered from the final PPTX at 1920 × 1080, inspected individually at full
  size and as a montage, and passed the presentation overflow test.
- The four-page PDF was produced from those verified renders, rendered back to PNG, and inspected
  as a second montage. It is a communication rendition, not an evidence record.
- DOI-bearing bibliography entries are controlled by
  `../dissertation_references_20260802.bib`; official non-DOI and private records retain their
  explicit source class in `../dissertation_literature_matrix_20260801.md`.

# Dissertation literature, metadata and claim matrix

**Prepared:** 2 August 2026
**Manuscript:** `dissertation_manuscript_20260801.md`
**Bibliography source:** `dissertation_references_20260802.bib`
**Status:** 100-reference submission-support audit; the University's required reference-manager
and IEEE-style export check remains a human submission step.

This matrix records what each source cluster can support and, just as importantly, what it cannot.
TrafficTwin experiment records remain the authority for project-specific numbers. Literature does
not upgrade an exploratory, post-hoc, descriptive or non-admitted result. LLM-assisted discovery
or drafting is never a source.

## 1. Source-class boundary

| Source class | Count | Authority and permitted use | Prohibited promotion |
|---|---:|---|---|
| DOI-bearing primary literature | 88 | DOI content negotiation was checked on 2 August 2026 against Crossref/DataCite metadata; publisher-returned title, authors, year, venue and DOI populate the BibTeX source | A correct citation does not validate TrafficTwin, its actor, simulator, metric or result |
| First-party official/standards records | 9 | JMLR, UK Government/DfT, SUMO/DLR, VLDB, National Highways, ETSI, NeurIPS and W3C records support software, data-source, standard or method context | Official availability is not a data licence, source acceptance, calibration result or deployment approval |
| Private producer records | 3 | References [15]–[17] identify the permitted private report, environment and trace commits | Private material is not independent publication, open reproduction or external validation |
| Project measurements | separate from the 100 literature records | Signed protocols, immutable evidence JSON and evaluation reports control every TrafficTwin-specific number | Project artifacts are not literature and do not become external evidence through citation |
| LLM drafting | zero bibliography entries | Disclosed assistance may help discover or edit candidate prose | It is never evidence, metadata authority, reviewer, approval or reference |

The twelve non-DOI BibTeX entries are [12], [14]–[17], [31], [40], [46], [47], [64], [85] and
[90]. Each has a stable first-party or explicitly private locator; none is disguised as a failed
DOI lookup. The other 88 entries carry unique resolvable DOI metadata.

## 2. Complete primary-source register

The register is deliberately grouped by research role. Every number maps one-to-one to key
`tt001`–`tt100` in the BibTeX source.

| References | Count | Primary-source scope | Verification route |
|---|---:|---|---|
| [1]–[4], [7]–[8], [48]–[64] | 23 | Edge/MEC/VEC architectures, communication-compute coupling, offloading and edge intelligence | IEEE/ACM/Elsevier/Springer DOI records; ETSI GS MEC 003 first-party PDF |
| [5]–[6], [65]–[79] | 17 | PPO/MAPPO, foundational and cooperative RL algorithms, evaluation benchmarks and real-world constraints | arXiv DataCite, AAAI, Nature and Springer publisher metadata |
| [9]–[12], [80]–[89] | 14 | Tail latency, preregistration, statistical inference, reproducibility, dataset/model reporting and ML technical debt | ACM, PNAS, IMS, ASA/Taylor & Francis, SAGE, OUP, ACL, Nature and first-party proceedings |
| [13]–[14], [31]–[47] | 19 | SUMO, traffic-flow models, map matching, calibration/validation and official road/BODS sources | IEEE/ACM/Elsevier/SAGE/Royal Society/Informs DOI records; DLR, VLDB, DfT and National Highways pages |
| [15]–[17] | 3 | Producer report, exact VEC environment commit and exact trace commit | Private identifiers recorded under permission; no public metadata claim |
| [18]–[30] | 13 | Digital-twin definitions, enabling technology and transport/IoV implementations | Elsevier, IEEE, Springer, SAGE, IET and Taylor & Francis publisher metadata |
| [90]–[100] | 11 | W3C provenance plus explanation, attribution, sanity, fidelity and interpretability boundaries | W3C Recommendation, ACM/Nature/ACL publisher records and arXiv DataCite |

Total: **100 distinct sources**. Bibliographic spellings and capitalisation in the manuscript are
generated from the checked BibTeX source rather than reconstructed from memory.

## 3. Claim-to-reference matrix

| Claim used in the dissertation | Supporting references | Limit carried into the dissertation |
|---|---|---|
| Edge computing brings computation closer to devices and makes latency, energy, communication and shared compute joint concerns | [1]–[4], [48]–[54], [62]–[64] | Architecture and survey literature does not show that offloading is always beneficial or that TrafficTwin models deployed capacity |
| VEC adds mobility, heterogeneous links, vehicles/RSUs and resource-management uncertainty to the offloading problem | [7], [8], [55]–[61] | Different objectives, networks and workloads do not transfer reported gains to the supplied checkpoint |
| RL/MARL labels are not sufficient experimental descriptions; actor, observation, environment, seed and evaluation protocol must be pinned | [5], [6], [65]–[79] | Benchmark competence does not establish algorithm-family superiority in this one environment |
| A digital twin needs a maintained physical/observed-to-virtual relationship; what-if simulation alone is not a live twin | [18]–[24] | Manufacturing/city definitions motivate the loop but do not certify TrafficTwin as a deployed live digital twin |
| Transport digital twins combine measured streams, simulation and decision support, while calibration, synchronisation and governance remain material challenges | [25]–[30] | Other transport twins cannot supply Manchester time semantics, mapping review, calibration or real-road authority |
| SUMO and traffic-flow models support reproducible modelled mobility, not direct observation of physical traffic | [13], [31]–[36] | Simulator theory and software citations do not validate the producer trace or generalise one collapse hour to Manchester |
| Map matching requires geometry/topology, uncertainty and explicit policy; calibration needs declared objectives and validation evidence | [37]–[47] | The literature does not choose TrafficTwin's threshold, review 174 rows, resolve source time or accept a baseline |
| Means can conceal tail populations; small samples require transparent uncertainty and exact-test resolution | [9]–[11], [80]–[84] | General statistical principles do not make n=5 externally representative or causal |
| Reproducibility requires explicit artifacts, provenance, data/model documentation and workflow discipline | [12], [85]–[90] | Reproducibility and FAIR/provenance practice establish inspectability, not truth, model validity or openness of private inputs |
| Post-hoc explanation needs method-specific validation; plausibility, reconstruction and faithfulness are distinct | [91]–[100] | Synthetic SHAP/IG-shaped fixtures are not real actor explanations, causal attributions or evidence |
| BODS SIRI-VM describes vehicle-monitoring data | [14] | Bus positions are not general road traffic, VEC tasks, radios, RSUs or application outcomes |
| The producer supplied the private environment, traces and checkpoint boundary | [15]–[17] | Permission and commit pinning do not redistribute the sources or independently validate results |

## 4. Project claims and their controlling evidence

| Dissertation claim | Evidence class | Controlling repository record | Permitted wording |
|---|---|---|---|
| Tightening capacity from 2.5 to 0.75 reduced mean latency by 8,310.9 ms while deadline attainment remained flat in five held-out seeds | Protocol-confirmed within the signed project design | `evaluation/capacity_confirmatory_results_20260728.md` and signed protocol/report | “confirmed in the held-out experiment”; never “externally validated” or “causal in real Manchester” |
| Actions were exactly invariant across pilot arm comparisons | Audited post-hoc probe over admitted artifacts | `integration/evidence/vec_pilot_keyed_action_comparison_20260728.json` | “0 mismatches in 8,956,800 compared actions”; not proof outside those artifacts |
| The mean improvement was concentrated in an already-failed, always-offloading population | Post-hoc mechanism analysis | `evaluation/latency_tail_analysis_20260728.md`; `evaluation/offload_partition_analysis_20260729.md` | “mechanism consistent with the observed artifacts”; subgroup construction and interpretation remain post-hoc |
| The inverse-capacity ceiling law predicted 27/27 new checks within ±5% | Predeclared exploratory prediction | `evaluation/ceiling_law_prediction_results_20260729.md` | “the predeclared exploratory prediction held”; not a universal VEC law |
| The trained actor remained better than baseline, but latency slopes differed | Predeclared exploratory robustness test | `evaluation/actor_crossover_results_20260730.md` | “no crossover; slope-invariance prediction refuted”; actor/preset mismatch prevents algorithm-family claims |
| Density/onset scaling matched only four of six exact checks | Predeclared exploratory falsification test | `evaluation/onset_scaling_prediction_results_20260730.md` | “prediction refuted under the frozen exact rule”; tiny numerical deviations remain disclosed |
| Sparse-64 bus runs yielded approximately 50.1% mean completion at cap 0.75 | Execution-deviated descriptive output | `evaluation/bbus_sparse64_clean_rerun_results_20260730.md` | “descriptive corroboration only”; outside VEC-06, synthetic compute/infrastructure, non-admitted |

## 5. Manuscript citation placement

| Manuscript location | Reference coverage | Purpose |
|---|---|---|
| §1.6.1 | [1]–[4], [7], [8], [48]–[64] | Edge/VEC architecture and offloading coupling |
| §1.6.2 | [5], [6], [65]–[79] | PPO/MARL method and evaluation limits |
| §1.6.3–§1.6.4 | [9]–[12], [80]–[90] | Tail interpretation, inference, preregistration, reproducibility and provenance |
| §1.6.5 | [13], [14], [18]–[47] | Digital-twin/transport scope, SUMO, observed sources, map matching and calibration |
| §2.2 and §4.3 | [91]–[100] | Explanation/attribution boundaries for implemented synthetic XAI and future work |
| §1.6.6 | [15]–[17] | Producer ownership, private-source scope and exact commits |

The reference list includes no generated prose source and no incomplete Lourenço calibration
citation. TrafficTwin measurements stay linked to their repository records, not to nearby
literature numbers.

## 6. Submission checks still requiring a person

- Import `dissertation_references_20260802.bib` into the University's required reference manager,
  select the mandated IEEE numeric style and inspect capitalisation, initials, access dates and
  line breaking in the final template.
- Confirm the private Year-1 report's year and whether private GitLab references should be
  non-clickable identifiers; until then they remain explicitly private and the year is `n.d.`.
- Confirm whether the bibliography breadth should be reduced for the final 8,000-word submission;
  all 100 sources are verified candidates, but the supervisor/marker may prefer only directly
  discussed works.
- Preserve the producer environment/trace and SUMO citations on every producer-derived figure,
  table and video frame.
- Do not add the unverified Lourenço calibration reference or make a calibration-quality claim
  until the producer supplies the exact publication metadata.

## 7. Phase-186 committed-input integrity check

The 2 August 2026
[local-input and handoff audit](quality/v07_local_input_and_handoff_audit_20260802.md) re-hashed the
committed manuscript, BibTeX source, editable deck, rendered deck and claim/source audit. It
reconfirmed 8,396 counted manuscript words, exactly 100 numbered and cited references, 100 BibTeX
records, four slides and four source-note blocks. A fresh exact scan found no duplicated manuscript
paragraph of at least 120 characters and no duplicated normalised line of at least 60 characters;
the manuscript therefore required no speculative prose edit. The human submission checks above
remain unchanged.

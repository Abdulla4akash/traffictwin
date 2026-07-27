# Appendix — Abbreviations and house terms

Two lists. The first is the general vocabulary the dissertation's background and related-work
chapters use. The second is the identifier scheme this project invented, which a reader
outside the repository has no way to decode — every one of these appears in the committed
documentation, and the count beside each family is the number of documents it appears in at
this commit.

Expansions are one line each. Where a term carries a boundary that matters scientifically, the
boundary is stated with it rather than left to a footnote elsewhere.

---

## 1. General vocabulary

| Term | Expansion |
|---|---|
| **ADR** | Architecture Decision Record — a numbered, dated record of one architectural decision and its consequences. |
| **CSF** | Computational Shared Facility — the University of Manchester's shared HPC cluster, reached through SLURM. |
| **DDQN** | Double Deep Q-Network — a DQN variant that decouples action selection from action evaluation to reduce value overestimation. |
| **DQN** | Deep Q-Network — value-based deep reinforcement learning using a neural network as the action-value function. |
| **DRL** | Deep Reinforcement Learning — reinforcement learning with neural function approximation. |
| **FCD** | Floating Car Data — per-vehicle position and speed traces sampled over time, here produced by the simulator rather than observed. |
| **IPPO** | Independent Proximal Policy Optimisation — PPO applied per agent, each treating the others as part of the environment. |
| **ITS** | Intelligent Transport Systems — the field applying sensing, communication, and control to transport networks. |
| **MAPPO** | Multi-Agent Proximal Policy Optimisation — PPO with a centralised critic and decentralised actors. |
| **MARL** | Multi-Agent Reinforcement Learning — reinforcement learning where several agents learn in a shared environment. |
| **RSU** | Roadside Unit — fixed roadside compute and communication infrastructure that vehicles offload tasks to. |
| **SUMO** | Simulation of Urban MObility — the open-source microscopic traffic simulator used for the traffic layer. |
| **TOS** | Task Offloading Simulator — the vehicular-edge simulator whose runs this platform imports and analyses. |
| **V2I** | Vehicle-to-Infrastructure — communication between a vehicle and fixed infrastructure such as an RSU. |
| **V2V** | Vehicle-to-Vehicle — direct communication between vehicles. |
| **V2X** | Vehicle-to-Everything — the umbrella term covering V2I, V2V, and related links. |
| **VEC** | Vehicular Edge Computing — edge computation serving vehicles, typically at roadside units. |

---

## 2. Data sources, standards, and external bodies

| Term | Expansion |
|---|---|
| **AADF** | Annual Average Daily Flow — a DfT annual average traffic figure. Contextual only in this project; it is never used as an instantaneous hourly observation. |
| **BODS** | Bus Open Data Service — the UK statutory service publishing bus timetable, fares, and real-time location feeds. |
| **DfT** | Department for Transport — the UK government department publishing the road traffic count data used here. |
| **GEH** | The GEH statistic (after Geoffrey E. Havers) — a traffic-engineering goodness-of-fit measure comparing modelled and observed flows. Whether it is an acceptance criterion here, and at what threshold, is an open owner decision rather than a settled one. |
| **ONS** | Office for National Statistics — source of the standard geography codes used to bound the study area. |
| **OSM** | OpenStreetMap — the open geographic database the road network is built from. |
| **SIRI-VM** | Service Interface for Real Time Information, Vehicle Monitoring — the XML profile BODS publishes live bus positions in. |
| **WebTRIS** | National Highways' traffic-data service for the strategic road network. |

---

## 3. House identifier schemes

Coined by this project. Each family is a stable identifier space, so a claim can be traced to
exactly one recorded thing.

| Family | Meaning |
|---|---|
| **VEC-01 … VEC-12** | The vehicular-edge capability identifiers — the import, metric, diagnostic, and reporting capabilities of the VEC analysis chain. Each has passed its recorded evidence gate; that does not widen any scientific, licensing, or hosting boundary. |
| **STA-01 … STA-05** | The statistical method identifiers: STA-01 paired study, and the N-way ranking, equivalence, power, and regression-gate methods beside it. A method identifier names how a number was produced, never that it was accepted. |
| **MAN-01 … MAN-11** | The Manchester integration capabilities — real observation acquisition, map matching, temporal profiling, network construction, and the live-bus work. |
| **UX-01 … UX-03** | The task-oriented product-interface capabilities. |
| **DIA-01 … DIA-07** | The diagnostic capabilities, including rule evaluation and sensitivity interpretation. |
| **REP-01 … REP-05** | The reporting and research-export capabilities. REP-01 is the deterministic LaTeX table fragment and static SVG/PDF figure export used for the dissertation figures. |
| **REL-01** | The release and reproducibility capability. |
| **R0 … R8** | The deterministic diagnostic rules. R0–R4 are the cross-rule family; R5, R7, and R8 are the sensitivity-supported rules. Rules produce hypotheses with evidence links, never proven causes. |
| **ADR-001 … ADR-065** | The decision register, indexed in `docs/decisions/index.md`. |

---

## 4. Project-internal terms

| Term | Meaning |
|---|---|
| **AppTest** | Streamlit's `AppTest` harness — runs a page headlessly so UI behaviour is asserted in tests rather than by hand. |
| **Analyst-reviewed candidate** | Evidence a human analyst has reviewed under a recorded policy. A label ceiling, not an acceptance. |
| **Descriptive non-causal** | A result that reports what was recorded without asserting why. Applied at type level so a caller cannot widen it. |
| **Fresh-run admission** | The gate a simulator run passes before its outputs may enter analysis. |
| **Gate A … Gate F** | The evidence gates: source audit through release reconciliation. A gate is accepted only on real evidence of that specific kind. |
| **Held-out cohort** | Seeds reserved before any evidence exists, consumed once by a confirmatory campaign and never reused. |
| **Import-first** | The guaranteed workflow: analyse artifacts produced elsewhere. Direct simulator launch is conditional and is never faked. |
| **Owner-approved candidate** | The repository owner has authorised a research policy to be implemented and exercised. **Not** supervisor approval, not validation, and not publication approval. |
| **Predeclaration** | A study design fixed and fingerprinted before its data exists, including the outcome that would be published if the hypothesis fails. |
| **Publishable null** | A committed undertaking to report a null result as a finding rather than reframing it after the fact. |
| **Unavailable state** | An explicit, reasoned "this is not available" surfaced to the user. Never a blank, a zero, or a silent default. |

---

## Notes on two expansions

**CSF** is not expanded anywhere in this repository; the expansion above is the standard
University of Manchester one, consistent with the SLURM wrapper the workspace notes describe.

**GEH** is a standard traffic-engineering statistic, but its role here is undecided: whether it
becomes an acceptance criterion, and at what threshold, is an open owner decision. The
expansion states the statistic, not a commitment to use it.

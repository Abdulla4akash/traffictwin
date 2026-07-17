# TrafficTwin — Design Proposal (v0.4)

**Working title (rename at will):** TrafficTwin — a modular what-if experimentation and decision-support platform for urban traffic and vehicular edge computing, demonstrated through a Manchester case study, with **OffloadLens** as its VEC analysis module
**Project:** Dynamic Resource Management for Intelligent Transportation System Applications (Project 237)
**Author:** Abdulla Al Mamun Akash · **Supervisor:** Dr. Sandra Sampaio · **Collaborating researcher:** Randy Putra
**Status:** Draft for discussion — pending supervisor approval before implementation begins
**Date:** 17 July 2026

> **Legend:** ⚠️ marks anything inferred from the meetings or standard SUMO practice but not yet confirmed against Randy's data, code, or Sandra's intent. **Appendix C** traces every major design element to the meeting statement that motivated it.

> **Changes from v0.3:** explicit research questions and consolidated contributions are added (§3); the platform is recast as a modular architecture with replaceable adapters (§4); Manchester is positioned as the first case study rather than the architectural boundary; experiments become first-class multi-run objects (§6); data validation precedes metrics and diagnosis (§6); training and evaluation controls are separated (§7); root-cause claims are softened to evidence-based diagnostic hypotheses (§10); evaluation is organised into software correctness, diagnostic/experimental validity, and expert usefulness (§11); the protected Must path is narrowed to one complete vertical slice (§13); and the submission calendar is made an explicit approval dependency.

---

## 1. Summary

### Elevator pitch

> **TrafficTwin is a modular experimentation platform that unifies roadside sensing, traffic simulation, and vehicular edge-computing analysis in one reproducible workflow for scenario design, prediction, comparison, and decision support. Users create what-if scenarios, evaluate both traffic-level and computing-level consequences, and inspect evidence-based diagnostic hypotheses. OffloadLens is the platform's specialised VEC analysis module, while Manchester provides the initial demonstration case rather than limiting the architecture.**

Sandra described the target directly: *"for Abdulla, an app — it is like a digital twin of a complex environment, of roads in Manchester."* A user — primarily a **traffic analyst**, with researchers as first evaluators and drivers as the conceptual end beneficiary — starts from the situation as it is (historical data plus the latest available state), **creates a what-if scenario** (an accident closing a lane, a signal-timing change, a post-event surge at Co-op Live, a royal motorcade requiring cleared roads, doubled demand, a weakened or reinforced edge infrastructure), runs or imports the corresponding simulation, and inspects the **predicted consequences**: how traffic flows, how long journeys take, when congestion clears — and, through the OffloadLens module, how the vehicular edge computing layer copes: which roadside units (RSUs) overload, how many safety-critical tasks miss deadlines, and whether the remedy is a better-trained model or more infrastructure. The platform then compares alternatives and issues **evidence-based recommendations** from a deterministic rules engine, optionally rendered into prose by a language model.

The what-if capability is not decoration; per Sandra it is *the* differentiator of this project within the group — the thing that distinguishes this dissertation from Ethan's algorithm work on the same environment. Two commitments carry over from earlier drafts and now have direct supervisory backing: every scenario serialises to a machine-readable **seed** (the group's own word for a parameter configuration), making import-first execution unconditional; and **all numbers come from code** — diagnosis is deterministic and testable, with any AI-assisted implementation manually verified and all research claims grounded in primary sources and experimental evidence.

The document is deliberately comprehensive — Sandra expects a contribution that reflects full-time work and a dissertation of roughly a hundred verified references — but the **build core is deliberately small**, per her equally explicit instruction: *"something small, simple, but has a huge impact."* Section 13's Must path is a single vertical slice; everything else is staged, optional, or future work.

## 2. What the supervisors actually asked for

This section exists so that the proposal can be checked against its sources line by line (full mapping in Appendix C).

**Sandra, first meeting:** a data-engineering/software contribution over traffic data — sensors, driver inputs, analysis feeds — fused into *"a complete view of traffic as it is at the moment,"* with forecasting *"just a part of it"* and **what-if scenarios** on top. Scenarios must be designed so that the obvious winner can lose (*"Morocco wins"*): trivial scenes yield trivial dissertations. Method discipline: only reputable published sources, roughly a hundred references, no AI-derived arguments, writing proceeds continuously as sections are completed, and the contribution must reflect full-time hours.

**Sandra, second meeting:** the digital-twin platform above, addressed to this author by name; the open question of whether **task offloading or journey-time prediction** powers the what-if predictions (*"I need to think if it's task offloading algorithms or… a prediction of journey time… we will come up with something"*); a proposed technical contribution — take the two or three most promising algorithms, learned and heuristic, and **combine them** or build a selector that picks the best per scenario; the **"seeds"** framing for parameterised experiment configurations, with an explicit wish for more and harder seeds (task birth rate, task mix and ordering, vehicle counts, capability mix); a **formal user evaluation** (ethics application, ~1-week review, anonymised participants, survey or interviews, Randy/Ethan/students as users, business-school contacts available); scope guidance (*small, simple, huge impact; time is constrained*); interface guidance (rough is acceptable, but *"it has to be easy to use… buttons and screen"*); and a blessing on AI-assisted code generation alongside the standing ban on AI-derived ideas.

**Randy:** a monitoring capability over his validation outputs — tasks generated and completed, vehicles, RSUs, **which RSU is overwhelmed and how badly**, especially under gridlock (his Co-op Live sensor-derived scenarios); help with **training-vs-validation data analysis** (does the policy trained in the light environment survive SUMO?); a suggestion to explore agentic AI because a bare dashboard *"sounds trivial"*; a suggestion to look at the explainability gap, softened by his own caveat — *"you must not have to give a solution… at least try to work on the gap"*; design-first process (short deck to Sandra before building); and the literature method (Semantic Scholar API + Consensus, top-tier venues, verified metadata).

## 3. Research questions, contributions, and framing

The dissertation is organised around explicit research questions rather than around a list of software features. The platform is the research instrument; implementation and evaluation provide the evidence.

### 3.1 Research questions

- **RQ1 — Platform value:** Can a unified, scenario-driven experimentation platform reduce the effort required to analyse traffic and vehicular-edge-computing experiments compared with the current CSV-based workflow?
- **RQ2 — Diagnostic value:** Can deterministic, evidence-based rules identify credible diagnostic hypotheses for degraded task-offloading performance under controlled faults?
- **RQ3 — Scenario sensitivity:** Under which traffic, workload, fleet, and infrastructure conditions do different offloading algorithms perform best?
- **RQ4 — Integrated insight:** Does presenting traffic-level and VEC-level consequences together produce more useful operational insight than either view alone?
- **RQ5 — Portfolio selection (stretch):** Can a scenario-aware selector reduce average regret relative to using one fixed offloading policy across all tested seeds?

### 3.2 Claimed contributions

This dissertation aims to contribute:

1. **A modular TrafficTwin architecture** integrating sensor data, SUMO simulation, VEC outputs, scenario authoring, and reproducible comparison.
2. **A scenario-driven experimentation workflow** in which every seed is versioned, exportable, replayable, and comparable.
3. **A deterministic diagnostic-hypothesis engine** that links computed evidence to candidate model, infrastructure, scenario, or data explanations.
4. **A reproducible experiment framework** supporting multi-seed comparison, fault injection, and training-versus-validation drift analysis.
5. **An evaluated software artifact**, assessed at software-correctness, diagnostic-quality, and expert-usefulness levels.
6. **An empirical winner-map and portfolio study** if the data and compute budget support it.

### 3.3 Research-to-evaluation chain

```text
Research questions
        ↓
Platform and diagnostic design
        ↓
Implementation as modular components
        ↓
Controlled experiments and fault injection
        ↓
Expert/researcher evaluation
        ↓
Answers, limitations, and future work
```

The dissertation needs a defensible gap. Rather than one speculative claim, this proposal carries **three contribution paths that trace to the supervisors' own words**, plus one explicitly fenced exploration. Anchor papers are denoted [R1]–[R4]; identifying and verifying them via the Semantic Scholar API (cross-checked with publisher records and the papers themselves, using Consensus only as a discovery cross-check) is Phase-0 work. Until then every gap is asserted as *plausible*, not *demonstrated*.

**C1 — The what-if decision-support platform itself** (engineering contribution, Sandra's core ask). Few systems couple mobility simulation, edge-computing evaluation, scenario authoring, and operator-facing comparison in one loop with a formal user evaluation. The contribution is the designed, built, and user-evaluated artifact plus the data model beneath it.

**C2 — Algorithm portfolio and selection** (empirical contribution, Sandra's own proposal). Across a family of seeds, no single offloading algorithm should dominate — that is precisely the "Morocco" structure she wants demonstrated. The platform's per-seed comparison data becomes training evidence for a **portfolio policy**: at minimum a transparent rule-based selector over scenario features (load intensity, tier mix, density); as a stretch, a learned selector. Hypothesis: a scenario-aware selector reduces average regret, or improves average performance, relative to committing to one fixed constituent across all tested seeds. The platform and the contribution feed each other — the What-if Compare engine *is* the instrument that reveals per-scenario winners.

**C3 — Diagnostic hypotheses for learned offloading systems** (methodological contribution). The model/infrastructure/scenario diagnostic rules (§10.1), evaluated by fault injection against known ground truth, give operators a repeatable, evidence-linked answer to "what should I investigate or change next?" — a question Randy currently answers by expert manual analysis.

**Fenced add-on — decision-level explainability instrumentation** (§10.3). Randy's suggested gap, included in the spirit he offered it: worked on, not solved, and never the dissertation's central claim. See §10.3 for exactly what AI assistance can and cannot contribute there.

**The open direction question** is Sandra's, stated in her words in §5, and the architecture is built so that her answer changes the front page, not the foundations.

## 4. Platform architecture — Sandra's vision, implemented modularly

Her description maps onto five areas, implemented as replaceable modules around a small core. The modularity is deliberate: the first Manchester case study can later be replaced by another sensor feed, SUMO network, or VEC environment without rewriting the whole platform.

```text
TrafficTwin Core
├── Data Hub
│   ├── Sensor adapter
│   ├── SUMO/FCD adapter
│   ├── VEC-log adapter
│   └── Incident/event adapter
├── Seed Designer
├── Prediction adapters
│   ├── Journey-time lens
│   └── OffloadLens
├── Experiment registry and metrics engine
├── Diagnostic-hypothesis rules engine
├── Comparison dashboard
└── Optional XAI and prose-rendering modules
```

The term *digital twin* is Sandra's and is used with her; for examiners, one defensive sentence in the dissertation will position the prototype precisely as a **replay-and-scenario digital-twin prototype** rather than a claimed live mirror of the city. ```
Roadside sensors (5-min counts/speeds) ──┐
SUMO mobility traces (FCD)  ─────────────┤
VEC task / RSU logs (Randy's env) ───────┤
Road network metadata (SUMO net,         ├──►  DATA HUB  ──►  OPERATIONS VIEW
  gov.uk downloads: lights, geometry ⚠️) ─┤   (canonical      (replay /
Event calendar (arena, stadium) ─────────┤    time+place      near-live /
Incident reports (manual form — the      ┤    model)          true-live)
  dissertation-scale stand-in for        ┘        │
  driver/pedestrian input Sandra described)       ▼
                                          SCENARIO STUDIO — "Seed Designer"
                                          traffic events · demand · signals ⚠️
                                          infrastructure · policies · ordering
                                                  │ seed (YAML)
                                                  ▼
                                          PREDICTION ENGINE (dual-path, §5)
                                          Path A: OffloadLens (VEC outcomes)
                                          Path B: Journey time (SUMO + history)
                                                  │
                                                  ▼
                                          WHAT-IF COMPARE  ──►  DECISION SUPPORT
                                          (baseline vs           (rules engine →
                                           intervention)          optional prose)
```

**Data modes for the Operations View**, honestly labelled: **historical replay** (timestamp-driven playback of sensor and SUMO data — guaranteed); **near-live** (directory/API polling for new 5-minute readings — Should); **true live** (a real municipal feed, only if Sandra or Randy can arrange access — Could). The UI is identical across modes; only the ingestion adapter changes, and the mode is always displayed on screen so no one mistakes a replay for a live feed.

## 5. The dual-path prediction engine — designing for Sandra's open decision

Sandra: *"I need to think if it's task offloading algorithms or… a prediction of journey time… whether you should do task offloading or journey time — we will come up with something."*

Rather than guess, the engine is an abstraction with two adapters, and **the prototype ships both lenses on the same scenario**:

**Path A — Offloading lens (OffloadLens module, §8).** For a given seed, the VEC environment answers the computing-system questions: which RSU will overload and for how long; how many T1 safety-critical tasks miss deadlines; how decisions split across local/V2I/V2V; whether shortfalls trace to the policy or the infrastructure. Everything from v0.2 survives here intact.

**Path B — Journey-time lens.** For the same seed, SUMO itself is the predictor: simulated trip durations, queue-clearance times, and corridor speeds under the scenario, contextualised by historical statistics from the 5-minute sensor feed (per-sensor, per-time-of-day, per-day-type averages). Deliberately **no machine-learning forecaster in v1** — calibrated simulation plus historical baselines is defensible, cheap, and answers Sandra's analyst questions ("when should I leave to arrive by 9?", "when does the post-event queue clear?", "what does a 60→20 km/h speed drop do?") at her stated 1–3-hour horizons. A learned forecaster is explicitly out of scope by decision and noted once as future work.

**The keystone demo** puts the fork in front of Sandra instead of asking her to imagine it: one Co-op Live arena-egress seed, one SUMO run, two lenses — journey times and clearance on one screen, RSU saturation and T1 misses on the next. Her direction decision then chooses which lens leads the dissertation's front page; the platform, hub, studio, compare, and rules layers are identical either way.

## 6. Canonical data model (⚠️ to confirm against Randy's files)

Adapters map whatever the environment and sensors actually export onto this model; absent ⚠️ fields degrade gracefully (first preference: a one-line logging addition in the environment).

**`seeds`** — the run request and scenario definition (ours; Appendix B): provenance (preset or parent seed plus deltas), traffic-side parameters (demand multiplier, incident/lane closure, signal timing ⚠️, event surge profile), compute-side parameters (task birth rate, task-class mix, **task ordering** — a variable Sandra specifically flagged, vehicle count, tier mix, RSU count/capacity/placement ⚠️, permitted decisions), policy and checkpoint, random seed, episodes.

**`experiments`** — one row per research comparison: `experiment_id`, research question, seed family, constituent policies/checkpoints, common random-seed set, replicate count, evaluation metrics, and status. This makes conclusions multi-run by default rather than treating one run as the experiment.

**`runs`** — one row per executed run: `run_id`, `created_at`, `seed_id`, `algorithm`, `random_seed`, `training_episodes`, `env_commit`, `config` blob.

**`tasks`** — one row per generated task:

| Field | Meaning | Basis |
|---|---|---|
| `task_id`, `vehicle_id` | identity | stated |
| `class` | T1 safety-critical / T2 platooning / T3 CAM | stated |
| `t_arrival` | generation time | stated |
| `data_size` | payload that travels on offload | stated |
| `workload_cycles` | computation required | stated |
| `deadline_ms` | ≈100 ms T1; relaxed otherwise | stated |
| `decision` | `local` / `v2i:rsu_k` / `v2v:vehicle_j` | stated |
| `t_complete`, `latency_ms`, `deadline_met` | outcome | stated |
| `transmission_time` | size × link rate at decision time | mechanism stated; per-row logging ⚠️ |
| `queue_wait`, `exec_time` | latency breakdown | ⚠️ assumed |
| `energy_j` | per-task energy | metric stated; logging ⚠️ |
| `drop_reason` | deadline / queue / link | ⚠️ assumed |

**`infra_state`** — per-RSU time series: `t`, `rsu_id`, `queue_len`, `utilisation`, `arrivals`, `active_tasks`, `drops`. Queue state exists in-env (the Lyapunov baseline needs it — stated); time-series *export* is ⚠️.

**`vehicle_state`** — SUMO FCD columns ⚠️ (`t`, `vehicle_id`, `x`, `y`, `speed`, `lane`) joined with `tier` (stated) and `propulsion` (stated), plus `cpu_util` ⚠️.

**`traffic_obs`** — the 5-minute sensor feed: `t`, `sensor_id`, `count`, `avg_speed` (stated by Randy); location metadata ⚠️.

**`trips`** — per-vehicle journey records from SUMO trip output ⚠️: depart, arrive, duration, route — the raw material of the journey-time lens.

**`incidents`** — manual reports via the in-app form (type, location, severity, vehicles involved, timestamp) — the honest stand-in for Sandra's driver/pedestrian input channel; incidents can seed what-if variants directly ("what if this had happened at 17:30 at 2× demand?").

**Data-validation layer** — runs before any metric or diagnosis: required columns present; units known; timestamps monotonic; task IDs unique; completion not before arrival; decision targets valid; metadata complete; cross-file counts reconciled. Failed validation suppresses diagnosis and produces an explicit `insufficient_data` report.

**Derived metrics** (computed once, versioned): completion rate overall/per class/per tier; latency P50/P95 vs deadline; decision shares; offload ratio; per-RSU utilisation, queue trajectories, and sustained-saturation episodes; drops by cause; energy per completed task; capacity-normalised load-balance indices across RSUs and vehicles; cross-algorithm dispersion per seed; journey-time distributions and deltas per origin–destination; queue-clearance time; corridor speed profiles.

## 7. Scenario Studio — the Seed Designer

Adopting the group's vocabulary: a **seed** is a parameter configuration that defines a job; Sandra asked for *more seeds, harder seeds, ordered differently*. The Studio is where they are made.

| Control group | Controls |
|---|---|
| Base | Preset (S1–S6 below) · variation of an existing seed · custom |
| Traffic events | Incident (location, lanes closed, duration) · signal-timing change ⚠️ (network-dependent, see §14 risks) · speed-limit/shock drop (e.g., 60→50→20 km/h) · event surge profile (arena/stadium egress) · road-clearing corridor (motorcade) |
| Demand | Multiplier ×1/×2/×4/custom · time-of-day profile from `traffic_obs` |
| Task workload | Birth rate · class mix (T1/T2/T3 shares) · **ordering** (easy-first / mixed / hard-first) |
| Fleet | Vehicle count · tier mix (weak / mixed / high-compute) · propulsion mix |
| Infrastructure | RSU count · capacity (standard/reduced/expanded) · placement ⚠️ · RSU failure toggle |
| Decisions | Permit/forbid local, V2I, V2V |
| Policy | always-local · random · heuristic · Lyapunov · DQN · DDQN · IPPO · MAPPO · **portfolio selector (§9)** (+ checkpoint) |
| Evaluation reproducibility | Random seed · checkpoint · common seed set |
| Training request (separate workflow) | Episodes · reward/config reference · training seeds; exported or queued rather than treated as ordinary validation |
| Actions | **Run** (mode-dependent, §8.2) · **Export seed** · **Import completed bundle** · **Compare against…** |

**Preset seeds** (each ships with a written hypothesis; the Morocco requirement made operational):

| ID | Preset | Why non-trivial | Hypothesised upset |
|---|---|---|---|
| S1 | Arena-egress gridlock (Co-op Live data) | Density may saturate one or both RSUs, depending on placement and demand | Blind offloading may collapse; selective V2V/V2I should be tested as a rescue mechanism |
| S2 | Weak-vehicle T1 storm | Pi-class vehicles cannot meet ≈100 ms locally | Selective offloading decisive; always-local fails exactly where safety matters |
| S3 | Data-gravity tasks ⚠️ | Included only if the environment models data location or transfer cost | Under those conditions, moving computation may outperform moving voluminous or sensitive data |
| S4 | Heterogeneous rush hour | Elevated arrivals per recent literature; sensor-derived profiles | The regime where learned adaptivity should finally beat static rules — budget permitting |
| S5 | Stadium event siting (Old Trafford — Sandra's example) | City-scale disruption planning | Journey-time lens: siting/timing choices change clearance by hours |
| S6 | Road-clearing corridor (royal-visit — Sandra's example) | Planned closures reroute everything | What-if planning value where no "algorithm" wins — the analyst does |

## 8. OffloadLens — the VEC analysis module

Everything approved in v0.2 survives as the platform's deepest module; summarised here, unchanged unless noted.

### 8.1 Views

| # | View | Question | Phase |
|---|---|---|---|
| 1 | Run Overview | How did this run go? (KPIs, arrivals vs completions) | P1 |
| 2 | Infrastructure & Congestion | Which RSU is overwhelmed, when, how badly, for how long? (Randy's priority) | P1 |
| 3 | Decisions | What is the policy actually doing? | P2 |
| 4 | What-if Compare | Did the change help? Who wins where? — including **training-vs-validation** comparison (Randy's stated ask: does the light-env policy survive SUMO?) | P2 |
| 5 | Triviality check | Can this seed produce insight at all? (cross-algorithm dispersion; flags "too easy — nothing can shine here") | P2 |
| 6 | Journey-time panel | Trip durations, clearance times, corridor speeds per seed (Path B) | P2 |
| 7 | Decision audit | Why was *this* task sent *there*? — part of the XAI add-on, §10.3 | Add-on |

### 8.2 Execution modes and the environment contract

Unchanged from v0.2 and now decisive for build order: **interactive**, **asynchronous**, **import-first (guaranteed)**, **hybrid (likely end state)**. Every Studio action serialises to a seed file; direct launch is a thin subprocess wrapper over the same file, conditional on Randy's answers to §15 Q1–Q2. The hybrid pattern mirrors Randy's own practice — iterate on the lightweight environment, reserve SUMO for validation.

## 9. The portfolio contribution — Sandra's combination idea, made concrete

Sandra: *"We can contribute in 1, 2, 3 algorithms that are more promising in complex scenes… one that is learnt-based, one that is heuristic… combine them somehow… identify them, coming up with a way to combine them, is a good contribution."*

**Stage 1 — Identify (analysis).** Run the algorithm suite across the seed families of §7; the What-if Compare and Triviality views produce a **per-seed winner map** and characterise *when* each algorithm excels (Lyapunov under which loads; MAPPO after which training budgets; heuristics where). This stage is pure platform output — the dissertation's analysis chapter writes itself from it, and it directly satisfies Sandra's demand for scenarios where the expected winner loses.

**Stage 2 — Combine (artifact).** Build a **portfolio policy**: v1 is a transparent rule-based selector over observable seed/scene features (load intensity, tier mix, density, deadline pressure) that dispatches to the best constituent; a learned selector is a stretch goal, attempted only if Stage 1's structure invites it. Evaluate the portfolio against every constituent across held-out seeds. Hypothesis: **no constituent dominates everywhere, and the portfolio dominates or ties everywhere** — the Morocco narrative, formalised into a measurable claim.

This path has three virtues: it is Sandra's own suggestion; it converts the platform from an observability tool into an instrument that *produces* a technical result; and its compute burden (many runs across seeds) is exactly what the CSF cluster and the seed/registry machinery exist for.

## 10. Decision support

### 10.1 Rules engine (deterministic core)

After each run or comparison, the metrics engine emits an **evidence pack** (compact JSON, stable keys). The rules engine — ordinary, tested code; thresholds in config; no language model — walks the playbook and returns findings (each citing evidence keys), one or more **diagnostic hypotheses** (**model / infrastructure / scenario / data / mixed / insufficient evidence**), and recommendations with expected direction of effect.

| Rule | Symptom | Diagnostic hypothesis | Recommendation |
|---|---|---|---|
| R0 Data insufficiency | Missing fields, inconsistent counts, invalid timestamps, or incomplete coverage | Evidence is insufficient for a reliable diagnosis | Suppress causal advice; report exactly what is missing or inconsistent |
| R1 Under-offloading | High T1 miss on low-tier vehicles while RSU utilisation is low | Policy leaves capacity unused — consistent with undertraining (cf. 200 vs 3×10⁵ episodes) | Retrain with larger budget / T1-rescue reward emphasis |
| R2 Infrastructure bottleneck | Sustained RSU saturation, growing queues, V2V already high | Capacity/placement limit, not policy | Add or uplift an RSU near the hotspot; re-validate |
| R3 Seed triviality | Cross-algorithm dispersion < ε and always-local within δ of best | Seed too easy to reward intelligence | Raise arrivals, skew tiers, add egress burst, harden ordering |
| R4 Load imbalance | Low Jain index across RSUs at moderate total utilisation | Placement/routing imbalance | Placement review or load-balancing reward penalty |
| R5 Sim-to-validation drift | Completion gap between light-env training and SUMO validation exceeds threshold | Policy overfit to the training environment | Validation-in-the-loop retraining; report per-metric drift (Randy's analysis ask, automated) |

Traffic-side recommendations (departure timing, alternative siting, clearance planning) are **comparison-driven**: ranked by measured deltas between seeds, requiring no new rules or ML.

### 10.2 Optional language layer

A language model may render the rules engine's JSON into readable prose — restating findings by ID, introducing nothing. Output is schema-checked against cited findings; the switch defaults to off in evaluation runs. This preserves Randy's agentic-AI demonstration while permitting the diagnostic component to be evaluated independently with the language model removed.

### 10.3 XAI add-on — included honestly, fenced deliberately

Randy's suggestion, in his own framing: *"explainable machine learning is still a gap in the research… you must not have to give a solution — at least try to work on the gap."* This tier does exactly that, no more.

**What goes in (all instrumentation, no research claim):** the **decision audit** — for sampled tasks, the decision-time state snapshot ⚠️ (queues, link rates, local capability; requires an environment hook, §15 Q7); **counterfactual replay** — what Lyapunov or always-local would have chosen on the same snapshot; a **disagreement browser** surfacing where the learned policy diverges from baselines (where the interesting behaviour lives); **behavioural fingerprints** — offload-ratio-vs-load curves per algorithm; and, as pure exploration, post-hoc attribution (SHAP/Integrated-Gradients-style) over DQN/DDQN Q-value inputs.

**Methodological boundary.** AI-assisted development may accelerate implementation, but every instrumentation component must be manually validated against Randy's environment and the selected XAI methodology. Post-hoc techniques such as SHAP or integrated gradients are not treated as meaningful merely because code runs: their fidelity, stability, and interpretation require literature-grounded evaluation. Therefore this tier is evaluated only for **diagnostic usefulness in the expert walkthrough**, positioned as instrumentation and future work, and governed by three gates: it starts only after every Must in §13 is complete; it requires the snapshot hook to exist; and it is the **first thing dropped** under pressure. It can never become the dissertation's central claim.

## 11. Evaluation — three levels

Evaluation occurs at three distinct levels so software quality, research-method quality, and human usefulness are not conflated:

```text
Level 1: Software correctness
        ↓
Level 2: Diagnostic and experimental validity
        ↓
Level 3: Expert/researcher usefulness
```

**Level 1 — Software correctness.**

*Metrics correctness:* golden-file tests on a miniature synthetic run plus property checks (completions ≤ arrivals; shares sum to 1; latency ≥ transmission time where present).

**Level 2 — Diagnostic and experimental validity.**
*Rules-engine quality by fault injection:* use several severity levels, multiple random seeds, combined faults, and held-out scenarios; calibrate thresholds on a separate development set; compare against a simple KPI-threshold baseline; score multi-label precision/recall, false-positive rate, robustness across seeds, and recommendation appropriateness. The existing 200-episode checkpoint, RSU-capacity reduction, disabled V2V, tightened T1 deadline, deliberately trivial seeds, and light-env-only checkpoints are candidate materials rather than assumed facts until inspected.

*Portfolio evaluation (C2):* compare a fixed-policy baseline, rule-based selector, and—only if justified—a learned selector across held-out seeds; report average performance, regret, variability, and failure cases rather than requiring the selector to beat every constituent everywhere.

*Case studies:* (i) arena-egress gridlock before/after +1 RSU; (ii) undertrained vs retrained on the same seed; (iii) training-vs-validation drift analysis; (iv) the keystone dual-lens demo (§5).

*Language-layer faithfulness (only if enabled):* generated prose contains no claim unbacked by a cited finding.

**Level 3 — Expert/researcher usefulness (formal if used as dissertation evidence).**

Per Sandra's process: submit the **ethics application in Phase 0** (review takes ~a week; anonymisation of stakeholders is required and will be designed in from the start); participants are Randy, Ethan, additional researchers/students, and potentially Sandra's business-school contacts; unless real traffic/network operators participate, this is reported as an expert/researcher evaluation rather than general end-user validation; instrument is a task-based session (create a seed, run/import, interpret the comparison, act on a recommendation) followed by **either a survey or a semi-structured interview** — her stated options; the choice is put to her in §15. Measures: task success, time-to-insight, comprehension of diagnoses, perceived usefulness for an analyst. Findings feed the evaluation chapter and, plausibly, the group's papers.

## 12. Technology

| Layer | Choice | Rationale |
|---|---|---|
| OS / runtime | Linux, Python 3.11+ | Environment and SUMO require Linux (stated) |
| Store | DuckDB over Parquet | Columnar analytics over many-run volumes, zero administration; downgraded to SQLite/pandas if the first sample bundle proves volumes trivial |
| Core | Installable package: `hub` / `live` / `studio` / `predict` / `offload` / `rules` / `render` / `cli`, pytest throughout | The engineering substance is a tested library; the UI is thin |
| UI | Streamlit (or Plotly Dash); map/corridor layer via pydeck/folium ⚠️ | Velocity; Sandra accepts rough-but-easy — "buttons and screen" — over polish |
| Launcher | Subprocess wrapper over Randy's environment, driven by the seed YAML | Conditional on §15 Q1–Q2; absent it, export/import carries the same file |
| Journey-time path | SUMO trip output + historical stats from `traffic_obs` | No ML forecaster in v1 by decision |
| Language layer | Any function-calling LLM API; low temperature; schema-validated output | Optional by design (§10.2) |
| Build method | AI-assisted implementation where useful; all research claims, citations, analyses, and generated code manually verified | One concise reproducibility and integrity statement replaces repeated AI-defence language |
| Config / repo | YAML seeds; GitLab beside Randy's environment; runs pinned to env commit | Reproducibility |
| Compute | Laptop-class platform; **CSF** for the Stage-1 portfolio sweeps and heavy SUMO batches | The sweeps in §9 are the genuine CSF workload |

## 13. Phasing and scope

The actual submission calendar must be inserted before approval. Until then, durations are not promises: phases end at gates, estimates are revised after P0, and the plan compresses by dropping Coulds first. Writing proceeds continuously: each phase lands dissertation sections (SUMO/CSF/technology background in P1; design and seed chapters in P2; evaluation from P3 onward), per Sandra's write-as-you-go instruction.

| Phase | Content | Gate |
|---|---|---|
| P0 | This proposal → deck → Sandra's decisions (§15); Randy's contract answers (§15); **ethics application drafted and submitted**; anchor-paper search [R1]–[R4] | Green light; direction, modes, schema fixed; ethics in review |
| P1 | Data Hub adapters (`traffic_obs`, FCD, VEC logs), registry, metrics engine; Run Overview + Infrastructure views on one real imported run | Randy sees his own gridlock run in the dashboard |
| P2 | Seed Designer (import-first minimum; launch if contract allows); What-if Compare incl. training-vs-validation; Decisions; Triviality; journey-time panel; presets S1–S6; Operations View replay mode; **keystone dual-lens demo** | Sandra sees the fork demonstrated, not described |
| P3 | Rules engine R1–R5; fault-injection evaluation; portfolio **Stage 1** sweeps on CSF; incident form | Measured diagnosis precision/recall; per-seed winner map |
| P4 | Portfolio **Stage 2** selector + evaluation; user-evaluation sessions (ethics now approved); optional language layer | Portfolio results in; user study executed |
| P5 | XAI add-on (all three gates of §10.3 permitting); polish; figures; write-up consolidation | Evaluation chapters complete |

**MoSCoW.** *Must* — one complete vertical slice: one real sensor source; one Co-op Live SUMO scenario; one VEC run bundle; canonical ingestion and data validation; experiment registry and metrics engine; Seed Designer in import-first mode; replay Operations View; one traffic lens and one OffloadLens comparison; rules R0–R3; one controlled fault family; ethics decision/application if formal participant evidence is planned; keystone dual-lens demo. *Should* — direct launch; Triviality view; S5–S6; R4 and fairness metrics; portfolio Stage 1; user-evaluation execution; near-live mode; language layer. *Could* — portfolio Stage 2 learned selector; XAI add-on; corridor map polish; async queue; advisor track-record ledger; true-live feed. *Won't (this project)* — a learned traffic forecaster (explicitly excluded by decision); changes to Randy's training code; new base DRL algorithms; city-scale deployment; real crowdsourcing or social-media ingestion at scale (the incident form and event calendar stand in); the business-school group's full platform (relationship to it is a question for Sandra, §15).

## 14. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Environment not headlessly invocable / runtimes long | Possible | Execution modes degrade by design; import-first unconditional |
| CSV/FCD schema differs from assumptions | Likely | Adapters isolate; ⚠️ fields degrade; sample bundle is §15 Q3 |
| Scenario-generation tooling not shareable, or env accepts only prepared scenes | Possible | §15 Q4–Q5; fallback: parameter variation over Randy's existing scenes |
| Geometry mismatch — the VEC corridor has no intersections, so no signal timing there | Known | Signal-timing what-ifs run on a richer SUMO network for the journey-time lens; stated openly rather than discovered late |
| Ethics approval latency blocks the user study | Possible | Application submitted in P0; study scheduled for P4 |
| Dual-path scope creep | Possible | Path B v1 is simulation+statistics only; MoSCoW enforced |
| Portfolio sweeps costly | Likely | CSF batches; lightweight-env iteration; SUMO for validation only |
| Language-layer hallucination | Possible | Renders only; schema+citation checks; off by default in evaluation |
| XAI add-on distorts the project | Guarded | Three explicit gates; first thing dropped; never the central claim |
| Effort estimates invalid before Randy's contracts and the actual calendar are known | Certain | Treat P0 as estimation discovery; re-plan after sample data, runtimes, supported controls, and submission date are confirmed |
| Direction pending | Certain until next meeting | The keystone demo and §15 questions are the ask; architecture survives either answer |

## 15. Open questions

**For Dr. Sampaio:** (1) Confirm the actual dissertation submission date and any interim milestones so the phase plan can be calibrated. (2) Direction — after the keystone demo: should the offloading lens or the journey-time lens lead the dissertation's front page? (Her stated deliberation, returned with evidence.) (3) Relationship to the business-school platform group — does this feed it, borrow from it, or stand beside it? (4) User evaluation — survey or interviews, and may we draw on the business-school contacts? (5) Could we obtain the whiteboard photograph from the second meeting to fold those scenarios into the seed presets? (6) Does the C1+C2 pairing (platform + portfolio) match her sense of a full-time-scale contribution?

**For Randy:** (1) Can the environment be invoked headlessly — CLI, Python API, or script — with seed overrides? (2) Wall-clock for one lightweight run and one SUMO validation run? (3) One complete run bundle (task log, infra log, FCD, trip output) plus header rows, to develop against. (4) Is your sensor-to-SUMO scenario-generation pipeline shareable, and (5) does the VEC environment consume arbitrary FCD/networks or only your prepared scenes? (6) Is per-RSU state exported over time or only end-of-run? (7) Can the environment dump a decision-time state snapshot per task, and at what cost? (8) Is energy logged per task? (9) Which seed parameters does the environment support varying today (birth rate, mix, **ordering**, counts, tiers, RSU config, decision toggles)? (10) Typical volumes per run and per sweep? (11) GitLab access and the commit to pin. (12) Existing checkpoint pairs (200 vs 3×10⁵; any light-env-only) for fault injection. (13) The seed catalogue Sandra referred to — the existing "standard/challenging/easy" configurations. (14) The V2V-only edge-computing paper Sandra praised, for the literature review. (15) Any plotting/metric scripts to reuse.

## 16. Dissertation and publication mapping

RQ1/RQ4 are answered by the platform and expert-evaluation results; RQ2 by controlled fault-injection experiments; RQ3 by per-seed winner maps; RQ5 only if the portfolio stretch is executed. Background (ITS and V2X; VEC task offloading; DRL and Lyapunov baselines; SUMO; CSF; the sensor data) ← literature review and infrastructure familiarisation, ~100 verified references via the Semantic Scholar API + Consensus. Design ← §4–10. Implementation ← the package and screens, with AI-assisted-build methodology stated. Evaluation ← §11 both tracks. Discussion ← per-seed winner maps, portfolio results, diagnostic-hypothesis accuracy, user-study findings. Conclusion/future work ← learned forecaster, true-live feeds, deeper XAI (citing Randy's gap papers), the business-school platform bridge. Publication-shaped pieces: the portfolio/winner-map study (Sandra's suggested contribution), the fault-injection methodology, and the platform-plus-user-study write-up; co-authorship on Randy's current paper is already on the table per meeting 2.

## 17. Immediate next steps

Condense to the 3–4-slide deck: slide 1 — Sandra's digital twin, the loop, the differentiator; slide 2 — Seed Designer + Operations View + keystone dual-lens demo (mocks); slide 3 — rules engine, portfolio contribution, two-track evaluation; slide 4 — phased plan, MoSCoW, risks, and the §15 questions. Send Randy his list the same day; draft the ethics application; run the [R1]–[R4] literature search. On approval, P1 starts immediately.

---

### Appendix A — illustrative diagnosis report (rules-engine output; prose rendering optional)

```json
{
  "run": "run_0142 (MAPPO, random_seed 7, seed S1-arena-egress)",
  "findings": [
    {"id": "F1",
     "statement": "T1 completion fell to 0.54 during 18:10–18:35 while RSU-2 utilisation held above 0.93",
     "evidence": ["metrics.t1_completion.window_1810_1835", "metrics.rsu2.util_p95"]},
    {"id": "F2",
     "statement": "V2V share was 0.06 in the same window despite 3 idle tier-3 vehicles in range",
     "evidence": ["metrics.decision_share.v2v", "metrics.idle_tier3.count"]}
  ],
  "diagnostic_hypotheses": [{
    "class": "model_under_offloading",
    "strength": "moderate",
    "rationale": "Capacity appeared available (F2) but the policy did not use it; pattern matches R1",
    "alternatives": ["poor_connectivity", "reward_misalignment"],
    "missing_evidence": ["link_quality_at_decision_time"],
    "rule": "R1"
  }],
  "recommendations": [
    {"action": "Retrain with a larger episode budget and reward emphasis on T1 rescue",
     "expected_effect": "T1 completion increases in S1", "rule": "R1"},
    {"action": "If the miss persists, evaluate an additional RSU at the arena egress",
     "expected_effect": "RSU-2 saturation duration decreases", "rule": "R2"}]
}
```

### Appendix B — illustrative seed (the Studio's unconditional export)

```yaml
seed:
  base: S1-arena-egress
  traffic:
    demand_multiplier: 2.0
    incident: {location: egress_junction, lanes_closed: 1, duration_min: 30}
    event_profile: arena_letout_2100
  workload:
    task_birth_rate: default
    class_mix: {T1: 0.4, T2: 0.3, T3: 0.3}
    ordering: hard_first        # a variable Sandra specifically asked to vary
  fleet: {count: default, tier_mix: mixed}
  infrastructure: {rsu_count: 2, capacity: standard}
  permitted_decisions: [local, v2i, v2v]
  policy: {algorithm: portfolio_v1, fallback: lyapunov}
  reproducibility: {random_seed: 7}
compare_against: run_0138       # same seed at ×1 demand, no incident
```

### Appendix C — traceability: design element → source

| Design element | Source | Statement (paraphrased) |
|---|---|---|
| Digital-twin framing; Manchester roads; "for Abdulla" | Sandra, meeting 2 | An app like a digital twin of Manchester's roads is proposed as this author's project |
| What-if as *the* differentiator vs Ethan | Sandra, meeting 2 | The what-if capability for a traffic analyst is the intended distinction of this project |
| Open direction: offloading vs journey time | Sandra, meeting 2 | She is deciding between task-offloading algorithms and journey-time prediction; "we will come up with something" |
| Portfolio/combination contribution (§9) | Sandra, meeting 2 | Identify 2–3 promising algorithms, learned and heuristic, and combining them is a good contribution |
| Seeds vocabulary; more/harder seeds; ordering, birth rate, counts | Sandra, meeting 2 | Seeds are parameter configurations; she asked for more seeds and named the variables to vary |
| Formal user evaluation; ethics app (~1 week); anonymisation; survey/interview; business-school contacts | Sandra, meeting 2 | Full user-evaluation process described, including the approval route |
| Small-simple-huge-impact scope; time constrained | Sandra, meeting 2 | Explicit scope guidance |
| Easy interface, "buttons and screen"; rough acceptable | Sandra, meeting 2 | Interface guidance |
| AI-assisted code blessed; AI ideas banned | Sandra, meetings 1–2 | Tools may generate code; arguments/ideas must be human, cited to published work |
| Incident input (severity, vehicles); 1–3 h predictions; leave-time questions | Sandra, meeting 2 | Driver/pedestrian input channel and prediction horizons described |
| Event scenarios: Old Trafford siting; royal-visit road clearing; signal, lane, speed-drop what-ifs in SUMO | Sandra, meeting 2 | Her worked examples of what-if scenarios |
| Platform vision: fused sensor/driver/analysis data, "complete view of traffic at the moment", forecasting a part | Sandra, meeting 1 | The original platform description |
| Morocco principle; triviality check (view 5, R3) | Sandra, meeting 1 | Scenarios must let the expected winner lose; trivial scenes ⇒ trivial dissertations |
| ~100 references; citation discipline; write-as-you-go; full-time-scale contribution | Sandra, meeting 1 | Dissertation method and scale expectations |
| Business-school platform question | Sandra, meeting 1 | A large group already builds a platform; relationship must be clarified |
| RSU-overload dashboard; tasks/vehicles/RSUs; model-vs-infrastructure | Randy, meeting 1 | His concrete monitoring request |
| Training-vs-validation analysis (view 4, R5) | Randy, meeting 1 | His stated ask for help analysing training and validation |
| Co-op Live sensors; 5-minute counts/speeds; FCD workflow; light-env training + SUMO validation | Randy, meeting 1 | His data and pipeline |
| 200 vs 3×10⁵ episodes finding (R1 evidence; fault-injection material) | Randy, meeting 1 | His training-budget result |
| Agentic AI as optional layer (§10.2) | Randy, meeting 1 | His suggestion, kept optional by design |
| XAI add-on, fenced (§10.3) | Randy, meeting 1 | His gap suggestion with his own caveat: work on it, need not solve it |
| Design-first; 3–4-slide deck | Randy, meeting 1 | His process advice |
| Semantic Scholar API + Consensus method | Randy, meeting 1 | His literature-review method, relaying Sandra's standards |
| Co-authorship prospects | Sandra, meetings 1–2 | Stated in both meetings |

# TrafficTwin: Auditable Evaluation of QoS Metric Reversal in Vehicular Edge Offloading

**Dissertation manuscript — submission-support draft**
**Candidate:** [name and student ID to be inserted by the owner]
**Programme:** MSc Advanced Computer Science, The University of Manchester
**Evidence cut-off:** 30 July 2026
**Prepared:** 1 August 2026

> **7 September 2026 integration note:** this manuscript retains the earlier
> latency-study framing and 30 July evidence cut-off. Use the
> [current integrated E0–E2d and follow-up results](dissertation/vec_results_integration_2026-09-07.md)
> and [evidence map](dissertation/vec_evidence_map_2026-09-07.md) for the later
> offered-task deadline-attainment programme. The new section is replacement
> material for a coordinated revision, not an appendix to add to this word count.
> The historical scientific results below have not been rewritten.

**Working report word count:** **8,396** whitespace-delimited words from Abstract through
Conclusion, including headings and excluding front matter, references and the evidence map. The
University template's counter and convention remain authoritative.

> This is a complete, evidence-bound manuscript draft, not a supervisor-approved final
> submission. The owner must apply the required University template, verify the final word-count
> rule and references, and insert personal/submission metadata. Square-bracket placeholders are
> deliberately visible rather than invented.

### Front matter to place in the University template

**Declaration of originality.** Insert the current University standard declaration verbatim from
the approved template; it is not reproduced from memory here.

**Generative-AI disclosure draft.** Generative-AI assistants, including Anthropic Claude and
OpenAI Codex/ChatGPT, were used during software development for code suggestions, review,
documentation, literature discovery and drafting/editing assistance. The author selected the
research questions, authorised experiments, reviewed source material and evidence records, and is
responsible for every submitted claim. AI-generated text and suggestions were not treated as
experimental evidence. Reconcile this wording with University policy and the candidate's complete
personal-use log before submission.

**Copyright statement.** Insert the current four-clause University boilerplate from the approved
template rather than paraphrasing it.

**Acknowledgements draft.** I thank Dr Sandra Sampaio for supervising this project and Randy
Prasetia Putra for providing the VEC environment, traces and checkpoint and for granting their use
with citation. [Add any personal acknowledgements in the candidate's own words.]

## Abstract

Vehicular edge-computing (VEC) studies often evaluate offloading policies through aggregate
quality-of-service metrics. This dissertation presents TrafficTwin, an audit-oriented instrument
that validates imported artifacts, preserves source-row provenance, binds campaigns to signed
designs and represents unavailable evidence explicitly. It uses the instrument to test a
counter-intuitive observation: reducing a roadside-unit resource can make mean latency look
better without improving service attainment.

A signed five-seed experiment on one modelled collapse hour in Manchester's Etihad/Co-op Live
district compared configured per-vehicle RSU concurrency 2.5 with 0.75. Reducing the ceiling
lowered mean latency from 12,027.5 to 3,716.6 ms. The paired difference was −8,310.9 ms with
bootstrap interval [−9,097.5, −7,524.3], and all seeds agreed in direction, while deadline
attainment remained flat. Exact audit found zero action mismatches across nine pilot arm pairs,
each comparing 8,956,800 keyed vehicle-slot decisions.

Post-hoc decomposition showed that median latency stayed 44.3 ms and 97.9–99.4% of latency mass
lay above one second. Roughly three-fifths of vehicles never offloaded and were unchanged; the
always-offloading population absorbed the queue effect, moving from roughly 26 seconds to 1.1
seconds across a deeper squeeze while still carrying nearly all missed tasks. A predeclared
ceiling prediction held 27/27, but actor-slope and onset-scaling predictions were refuted. Captured
bus mobility remained descriptive and non-admitted. The contribution is a reproducible VEC
demonstration that an aggregate QoS metric can reward resource degradation, plus the per-vehicle
audit that reveals why and defines where the claim stops.

## 1. Introduction

### 1.1 Problem

Edge computing moves computation away from a distant central cloud and towards the devices and
places where data are produced. Its appeal is strongest for interactive and mobile applications,
where communication delay and constrained device resources can make local-only or cloud-only
execution unattractive [1], [2]. Vehicular edge computing applies
that idea to moving vehicles and roadside infrastructure. A vehicle can execute a task locally or
offload it to an RSU, trading local compute time and energy against radio delay, shared queues and
edge capacity. The resulting decision is not simply “edge is faster”: it depends on the vehicle,
task, link, queue and allocation policy [3], [4].

Reinforcement learning is a plausible way to make repeated decisions in that coupled system.
Proximal policy optimisation (PPO) learns a policy from interaction while constraining the size of
updates to a surrogate objective [5]. Its multi-agent variant, MAPPO, has proved a strong
cooperative-MARL baseline on several benchmark families [6].
However, a strong learned policy and a plausible simulator do not make evaluation automatic. The
metric used to summarise the outcome decides which behaviour looks good.

This dissertation began as an integration and research-UX project. The supplied VEC environment,
traffic traces, checkpoint, Manchester data sources and a large analysis platform existed at
different levels of completeness and permission. The immediate engineering challenge was to make
their boundaries inspectable: validate imports, keep source semantics, expose missing evidence,
record lineage and execute only bounded campaigns. That instrument enabled a more interesting
scientific question. During a pilot capacity sweep, reducing a resource ceiling made mean task
latency dramatically better, yet did not improve the source-defined deadline-success rate. In a
naïve dashboard this could be read as evidence that less infrastructure performs better. In an
audit-oriented system it becomes a question: which tasks and vehicles moved, which decisions
changed, and what does the aggregate actually mean?

### 1.2 Research gap

Latency tails are not a new phenomenon. Dean and Barroso [9] showed that a small slow
population can dominate service performance at scale. Nor is careful MARL evaluation a new
requirement: Gorsane et al. [10], in a meta-analysis of 75 cooperative-MARL papers, identify
practices that impair comparison and propose a more standardised protocol. The gap addressed here
is narrower and empirical. In the audited VEC environment, can an ordinary mean-latency metric
improve when an RSU resource is reduced, while a deadline metric remains flat? If so, can the
artifact chain identify the decision, queue and population mechanism without turning post-hoc
analysis into a confirmatory claim?

Existing DRL offloading work explicitly models uncertain edge-load dynamics [7] and dynamic VEC
resource/response-time allocation [8]. Those studies demonstrate why load-aware decisions matter;
they do not provide an artifact-level audit of how an aggregate metric responds when the resource
control itself changes. TrafficTwin addresses that evaluation gap without claiming a new
offloading optimiser.

That positioning matters. The novelty claimed is not that means hide tails, that queues react to
capacity, or that RL rewards may be incomplete. It is the combination of: (1) a protocol-bound
demonstration of the reversal in a concrete VEC evaluator; (2) exact action-level and
per-vehicle decomposition showing where the aggregate improvement resides; and (3) an evidence
system that preserves the distinction between prediction, exploration, refutation and a failed
admission boundary. This is a systems-and-evaluation contribution, not a new offloading algorithm.

### 1.3 Research questions

Three evaluative questions organise the manuscript:

- **RQ1:** Under saturation, how does reducing configured per-vehicle RSU concurrency affect
  source-defined deadline attainment and mean task latency for the audited MAPPO checkpoint?
- **RQ2:** What action-, queue-, task-class- and vehicle-level mechanisms explain the aggregate
  response?
- **RQ3:** Does the qualitative response persist across actors, traffic regimes and captured bus
  mobility, and where must the evidence stop?

These questions operationalise the project's seven objectives. O1–O5 concern the canonical data
contract, deterministic metrics, statistical comparison, what-if machinery and research UX. O6
is evaluation on the supplied Manchester-district TOS traces. O7 combines software correctness
and reproducibility with a separately ethics-gated usability evaluation. The detailed mapping is
maintained in `docs/dissertation_appendices/objectives_traceability.md`; it is not repeated as a
feature catalogue here because the argument, rather than the number of platform pages, is the
unit of assessment.

### 1.4 Contributions

The work makes four bounded contributions.

First, TrafficTwin provides an import-first experimental instrument. It preserves raw-to-canonical
lineage, deterministic metric definitions, unavailable states, signed campaign designs and
machine-readable receipts. These features make a result inspectable and make unsupported claims
harder to express.

Second, the held-out capacity study confirms an initially counter-intuitive response inside its
signed protocol: a 3.33-fold reduction in configured capacity reduces mean latency by 8.31 seconds
while leaving deadline attainment flat. All five paired seeds agree in direction. This is an
internally confirmed project result, not external scientific validation.

Third, the mechanism analysis demonstrates why the aggregate is misleading. The evaluated policy
does not adapt its actions to the capacity intervention. The median and locally executing
population do not meaningfully move; nearly all latency mass and the capacity response reside in
the already-failing offloaded tail. The headline mean therefore describes neither the local nor
the offloading subgroup.

Fourth, the study reports failed predictions and non-admitted corroboration alongside successful
ones. A ceiling prediction generalised to deeper squeezes, but actor-slope invariance and exact
density-onset scaling did not. The bus successor was executed but failed its admission rule and
remains descriptive. These negative boundaries are part of the contribution because they prevent
a local effect from becoming an unsupported universal claim.

### 1.5 Scope

The central experiments use one supplied simulator implementation (`v2_post_nrsus_fix`), one
supplied trained checkpoint (`ukfleettrain_mappo_model_c_17`) and one anomalous trace, `inc`, from
a modelled 20:00–21:00 collapse hour in the Etihad/Co-op Live event district. The trace is not
city-wide Manchester and its deadlines are simulator-defined task outcomes, not journey
completion, passenger experience or physical safety. Other supplied traces are used to establish
where the intervention is inert. Captured buses are public-transport vehicles, never a proxy for
all road traffic. No participant usability result is reported because no ethics approval or
participant dataset is present at the evidence cut-off.

### 1.6 Concise literature synthesis

#### 1.6.1 Edge offloading as a coupled resource problem

Edge computing is commonly motivated by latency, bandwidth, privacy and availability constraints
that make exclusive reliance on remote clouds undesirable [1], [2]. Mobile edge-computing surveys
formalise computation offloading as a joint decision over communication and compute resources
[3], [4]. A task sent to an
edge node may avoid slow device compute, but it gains transmission, scheduling and queueing
components. Shared infrastructure also couples agents: one vehicle's decision changes the
contention experienced by others.

The wider fog, MEC and VEC literature reaches the same structural conclusion from different
architectures and optimisation methods: communication, compute, mobility, energy and queue state
must be reported together rather than collapsed into an “edge is faster” premise [48]–[64]. Those
studies motivate the variables audited here; their performance results do not transfer to this
checkpoint or trace.

This coupling creates at least three different notions of success. A policy can minimise average
latency, increase the proportion of tasks that meet a deadline, or distribute service more
equitably across vehicles. These objectives need not agree. A one-second reduction on a task that
is already tens of seconds late can dominate a mean while contributing nothing to deadline
attainment. Conversely, moving several near-deadline tasks by a few milliseconds can improve
attainment with little effect on the mean. A report containing only one number cannot reveal the
difference.

The evaluated environment defines three task classes. T1 and T3 use 100 ms deadlines; T2 uses a
500 ms deadline. The dissertation preserves those source semantics. “Completion” means that a
generated compute task met its source-defined deadline. It does not mean that a vehicle completed
a physical trip, that an application produced a usable response, or that a safety requirement was
met. That apparently simple terminological restriction is central to construct validity.

#### 1.6.2 PPO, MAPPO and evaluation

PPO alternates environment interaction with optimisation of a surrogate objective, commonly
using clipping to discourage excessively large policy updates [5]. MAPPO adapts PPO to
cooperative multi-agent settings. Yu et al. [6] show that PPO-based multi-agent
methods can be competitive across several benchmark suites, while also demonstrating that
implementation and hyperparameter choices materially affect performance. It follows that “MAPPO”
is not a sufficient experimental description. The exact checkpoint, environment version, fleet
preset, observation contract and evaluator must be pinned.

TrafficTwin evaluates a supplied checkpoint rather than training a new actor. That boundary has
two advantages. It makes the study a focused audit of a fixed policy, and it prevents training
noise from being confused with the resource intervention. It also constrains the conclusion: the
result concerns this checkpoint in this environment, not MAPPO as an algorithm family.

Foundational and cooperative deep-RL methods, MARL surveys and evaluation studies show how much
algorithm, implementation and protocol choices vary [65]–[79]. They support pinning the exact
actor/observation/environment contract and reporting variability; they do not create an
algorithm-family comparison where only one compatible trained actor exists.

Gorsane et al. [10] motivate multiple evaluation runs, transparent reporting and standardised
comparison in cooperative MARL. This project applies those principles through paired seeds,
predeclared primary outcomes, complete arm publication, exact artifact fingerprints and
machine-readable receipts. Five held-out seeds are still a small confirmatory cohort. Reporting
all five directions and the exact sign-test resolution is therefore more informative than
presenting a rounded p-value alone.

#### 1.6.3 Aggregate latency and the tail

Dean and Barroso [9] describe how rare slow components can dominate user-facing latency in
large services. The VEC setting differs from warehouse-scale computing, but the statistical
lesson transfers: a mean is sensitive to a heavy tail and does not identify which population
moved. For that reason, this study reports p50, p95, p99, deadline attainment, the proportion
above one second, latency-mass shares, task-class results and per-vehicle policy partitions.

Bootstrap, exact-test, equivalence, multiplicity and transparent significance guidance further
motivate reporting estimands, uncertainty and attainable resolution rather than a binary verdict
[80]–[84].

The phrase “mean latency improved” is treated as a mathematical statement, not automatically as a
service-quality statement. Its interpretation requires at least two further questions. Did tasks
cross a deadline that matters to the source definition? Did any representative vehicle
experience the reported average change? The central result answers “no” to both in the evaluated
artifacts. That is why the study uses “metric reversal”: the direction of the aggregate suggests
that a degraded resource setting is better, while the outcome decomposition shows no equivalent
improvement in task attainment.

#### 1.6.4 Reproducibility, predeclaration and honest provenance

Nosek et al. [11] distinguish testing predictions against new observations from generating
explanations after seeing data. The latter is valuable discovery, but it carries different
evidential weight. TrafficTwin implements that distinction locally rather than claiming an
external registration. An approved campaign binds the exact bytes and digest of its design;
execution receipts bind cells, inputs and outcomes; the result is published under a prior
commitment to publish null or contrary findings.

Pineau et al. [12] argue for reproducibility practices including code, explicit reporting and
checklists. This project extends that logic to provenance and claim state. A hash proves identity,
not truth. A deterministic pipeline proves repeatability under the same inputs, not external
validity. A source-row link shows where a number came from, not whether the source measurement is
correct. TrafficTwin represents these distinctions in both data types and user-facing language.

Work on ML technical debt, FAIR data, dataset/model documentation, reproducibility standards and
formal provenance reinforces why these artifacts must remain inspectable and role-separated
[85]–[90].

The evidence hierarchy used in this manuscript has four levels. **Protocol-confirmed** results
were tested on held-out seeds under a signed design with a pre-specified primary outcome.
**Post-hoc mechanism** results decompose completed artifacts and generate explanations but do not
inherit confirmatory status. **Predeclared exploratory** tests make sharp predictions on new
cells, yet remain exploratory because their scope, sample size or construction was not promoted
to a new confirmatory study. **Descriptive/non-admitted** results may be useful observations, but
violate an admission contract or use incompatible inputs and cannot test the central claim.

#### 1.6.5 Traffic simulation and observed buses

Digital-twin literature distinguishes a maintained observed/physical-to-virtual relationship
from an isolated simulation and identifies synchronisation, calibration, governance and decision
feedback as continuing challenges [18]–[30]. TrafficTwin therefore uses the digital-twin loop as
an architectural direction while keeping the evaluated capacity claim labelled as modelled VEC,
not a deployed or continuously synchronised Manchester twin.

The producer's five mobility traces were generated with the microscopic traffic simulator SUMO
[13]. The evaluated `inc` trace uses SUMO seed 43 and represents a
reactive-rule variable-speed-limit collapse hour in a bounded event district. Simulation permits
repeatable, vehicle-level experiments that would be difficult or unsafe on a live road network,
but it also limits external validity. The dissertation therefore says “modelled” and
“simulated” wherever needed and avoids the label “Manchester digital twin” for the experimental
claim.

The Bus Open Data Service (BODS) supplies SIRI-VM vehicle-monitoring data, including current bus
locations and related journey information [14]. TrafficTwin captured
separate dawn and morning-peak sessions and later converted their observed movement snapshots into
bounded research traces. Those positions improve the mobility provenance relative to wholly
synthetic vehicle paths. They do not observe compute tasks, RSU placement, radio conditions or
edge capacity. Any VEC task stream and infrastructure laid over them remains synthetic. The bus
study is consequently a descriptive transfer probe, not real-world validation of offloading.

Traffic-flow, map-matching and calibration sources show that model structure, candidate policy,
direction/topology, observed-data binding and validation criteria are separate decisions
[31]–[47]. They support the fail-closed Gate-D workflow, but they do not choose a threshold,
review a row, resolve provider clock semantics or accept a Manchester baseline.

#### 1.6.6 Positioning against the producer's work

The environment, trace repository and trained checkpoint were produced by Randy Prasetia Putra at
The University of Manchester. The pinned environment commit is
`068b4ea33e640f206ce6a7d04f3d6fae2ac831f4`; the audited trace commit is
`f6c67acbed3360dba3a0d5c8d1fd557caa99ecff`. Putra's private Year-1 report, *Intelligent Task
Offloading: Current State Limitations and Proposed Potential Solutions*, documents the broader
task-offloading programme and motivates concern about distribution shift and reward alignment
[15], [16], [17]. Permission to use code, data and derived publications was granted with citation. The
private report and repository contents are not redistributed.

TrafficTwin's contribution is downstream and distinct. It does not claim authorship of the
environment, traces or checkpoint. It builds an auditable analysis and execution boundary around
them, discovers and tests the capacity-metric reversal, and reports where the supplied policy and
evaluator produce that response.

## 2. Methodology

### 2.1 Research design

The study followed a staged design. First, integration work audited and pinned the source
repositories, trace fingerprints, environment version and evaluator semantics. Second, a pilot
used only non-held-out seeds to locate a capacity-sensitive regime and estimate execution cost.
Third, a signed candidate-B protocol declared latency as the primary outcome and reserved seeds
10–14 for a one-shot paired confirmation. Fourth, analysis-only probes decomposed the completed
artifacts without modifying them. Fifth, predeclared exploratory campaigns tested predictions at
deeper capacity levels, with another actor and across normal traffic regimes. Finally, two
previously captured bus sessions were processed into successor inputs; no additional acquisition
or attendance was performed for that experiment.

This order reduces researcher freedom without pretending to eliminate it. The pilot selected the
interesting trace and produced the hypothesis; it is therefore exploratory. The held-out campaign
tested the declared primary effect. The detailed mechanism was discovered post hoc. Later sharp
predictions tested consequences of that mechanism, and contrary outcomes were retained. Each
stage has a separate record in the consolidated experiment register.

### 2.2 TrafficTwin as the research instrument

TrafficTwin is an import-first Python research platform. The central architectural rule is that
data acquisition or a simulator process does not directly become a chart or claim. An input first
passes a source-specific inspection and schema boundary. Accepted fields are normalised into
canonical tables with source references. Metrics consume those tables deterministically.
Reports, comparisons and UI pages consume typed metric artifacts rather than reimplementing
scientific formulas.

Four instrument properties matter to this dissertation.

**Validation and explicit absence.** Bundles declare files, schemas and fingerprints. Partial or
malformed inputs are rejected. If a metric cannot be computed from available evidence, its value
is “unavailable”, not zero. This prevents a missing energy or utilisation field from silently
entering a comparison.

**Provenance.** Metric records link to definitions, canonical rows and source rows where the
contract permits. Campaign outputs retain source commits, trace digests, checkpoint identity,
configuration and per-cell state. This supports an auditable path from headline to input. It does
not establish source truth or causality.

**Bounded execution.** The VEC runner accepts only allowlisted requests that have passed the
source and preprocessing gates. Campaigns enumerate their cells in advance, enforce budgets and
write resumable receipts. The approval is digest-bound: changing a predeclaration after approval
invalidates the request rather than silently changing the design.

**Claim state.** Project records distinguish implementation acceptance from scientific
admission. A working parser can be accepted while a derived scientific claim remains exploratory.
Similarly, a successfully returned GPU archive can be non-admitted if the execution violated its
predeclared rule. This separation is essential in the bus case.

The same boundary governs explanation. Local-surrogate, attribution and interpretability research
distinguishes plausible presentation, arithmetic reconstruction, sensitivity and faithfulness
[91]–[100]. TrafficTwin's synthetic SHAP/Integrated-Gradients-shaped fixtures test data contracts
only; they are not explanations of the supplied actor and do not enter this evidence chain.

The platform includes statistical studies, diagnostic rules, scenario mutations, parameter
sweeps, replay, provenance, report export and human-review ledgers. Those capabilities satisfy
the broader engineering objectives, but the manuscript uses them as supporting infrastructure.
The principal evaluated instrument is the signed capacity campaign and its deterministic
post-processing chain.

### 2.3 Source artifacts and experimental unit

The producer supplied five trace regimes: zero-event weekend (`we`), event night (`ev`), the
collapse hour (`inc`), weekday morning peak (`wd_am`) and weekday evening peak (`wd_pm`). The
central `inc` trace contains 2,488 padded time slots. Normal traces contain 139–215 padded slots
under the audited preprocessing. The environment uses the `uk2030` fleet preset with the trained
`ukfleettrain_mappo_model_c_17` actor unless an exploratory comparison states otherwise.

The experimental unit for the confirmatory study is a paired evaluator seed. For each seed, the
same trace, actor and task-generation setting are evaluated at baseline capacity 2.5 and reduced
capacity 0.75. Pairing removes between-seed variation from the arm contrast. It does not make five
seeds a large sample, so raw seed directions and uncertainty are reported.

The intervention is a configured per-vehicle RSU concurrency ceiling. It is an instrument for
creating queue pressure, not a claim about a particular deployed RSU specification. Capacity
values 2.5, 1.5, 1.0 and 0.75 formed the pilot. Deeper exploratory checks used 0.5, 0.25 and 0.1.
Interpretation uses the environment's own units and equations; it does not translate them into
physical core counts.

### 2.4 Outcomes

The confirmatory primary outcome is mean task latency in milliseconds. For each seed, the paired
difference is reduced-capacity minus baseline; a negative value therefore favours the reduced
arm mathematically. The report gives the mean paired difference and a paired non-parametric
bootstrap interval. A secondary direction check uses the exact two-sided sign test. With five
non-zero pairs all in the same direction, the minimum attainable two-sided p-value is 0.0625. The
study therefore does not convert directional consistency into a conventional p<0.05 claim.

Deadline success is the fraction of tasks meeting their class deadline. It is secondary in the
latency-primary confirmatory protocol and is also reported by T1/T2/T3 class. Other descriptive
outcomes include mean energy per task where source-compatible, offload-action share and offload
target. Mechanism outcomes include latency quantiles, latency mass above one second, failure
concentration, per-vehicle action sequences, compute tier, workload and task mix.

An exact keyed action comparison aligns vehicle identity and slot before comparing decisions.
Aggregate action shares would be insufficient: two policies could have identical shares but
switch different vehicles. The probe compares both offload/local decisions and recorded targets.
The RSU observation audit separately checks whether capacity changes the inputs visible to the
actor rather than assuming that an invariant aggregate means an invariant observation.

### 2.5 Pilot and held-out protocol

The pilot evaluated three non-held-out seeds, 0–2, at four capacity arms. Before result
inspection, the record committed to publishing a null as well as a positive result. It showed
flat mean deadline attainment of approximately 79.1% across all arms, while mean latency fell
from 9,798.8 ms at capacity 2.5 to 3,083.6 ms at capacity 0.75. This motivated, but did not itself
confirm, the metric-reversal hypothesis.

The confirmatory design compared only 2.5 and 0.75 on held-out seeds 10–14. It declared mean
latency primary, retained deadline attainment as secondary, fixed the paired analysis and
specified a null-publication rule. The protocol and evidence digests were signed before the held-
out results were available. Ten cells were run: five seeds by two arms. Completed artifacts were
reviewed locally and recorded without choosing among alternative outcomes.

### 2.6 Mechanism and robustness analyses

Post-hoc analysis proceeded from broad distribution to specific population. The latency-tail
analysis measured p50, p95, p99, maximum, mean, share above one second and tail contribution to
total latency. A closed-form check inspected the evaluator's missed-task latency ceiling. The
per-vehicle policy analysis classified vehicles by whether they always offloaded, never offloaded
or switched, then compared compute tier, workload, task mix and failures. A decomposition at
capacities 2.5 and 0.1 measured latency separately for the always- and never-offloading groups.

Three later tests carried predictions frozen before their new cells were analysed. The ceiling
law predicted missed-task p95 at capacities 0.5, 0.25 and 0.1. The actor-crossover study compared
the trained checkpoint with a baseline actor and predicted both winner behaviour and similar
latency slopes. The onset-scaling test predicted the first capacity at which each normal trace
would cease to be exactly invariant. Frozen rules were applied literally; a numerically tiny miss
still counted as a failed exact prediction.

The RSU association analysis is an example of correction rather than selective polishing. Direct
load measures established that four RSUs carried 99.1% of load and operated near the concurrency
bound. An initial attempt to attribute this to association behaviour used the wrong counting unit
and contradicted busy-time evidence. That causal reading was withdrawn. The asymmetry remains
measured; its cause is undetermined.

### 2.7 Bus-session successor

The two bus sessions were captured at different times before this processing task. The dawn
session contained 1,162 active bus identifiers and the morning-peak session 1,433; after bounded
trace preparation, 961 and 1,212 buses were retained. Their peak concurrent retained populations
were 827 and 1,000. Dawn occupied 66,291 grid cells and peak occupied 72,208, far beyond the
accepted VEC-06 bound of 2,000 cells and 64 infrastructure sites.

Two successors were designed. A bounded-corridor arm attempted contract-compatible geographic
restriction. A whole-fleet Sparse-64 arm kept the wider mobility but generated only 64 analysis
sites. The latter covered 45.0141% of occupied dawn cells and 45.9960% of peak cells, so it was
explicitly outside VEC-06 admission. Compute tasks, equipment and sites were synthetic; raw BODS
payloads were not uploaded in the result pack.

The Sparse-64 GPU campaign used five seeds and a fixed held-out peak evaluation. Checkpoint
recovery preserved training across four expired one-hour CLI proxy credentials. At completion,
the result was downloaded and CRC-checked, but a terminal-state ordering defect allowed the
service to restart and perform a second return. The first archive was overwritten. No setting or
metric selection changed, but identity across returns cannot be verified and the one-return rule
was violated. The retained output is therefore descriptive and non-admitted. The defect was
repaired and tested; no rerun is needed to interpret the retained artifact at its declared low
evidence level.

### 2.8 Ethics, privacy and reproducibility

The capacity experiments use simulation artifacts and contain no participant study. BODS
processing retains bounded research snapshots and publishes aggregate descriptions; buses remain
transit vehicles and raw identifiers are excluded from public research artifacts. Producer code
and data are used under permission conditioned on citation. The private Year-1 report and raw
producer repositories are not committed or redistributed.

The owner has recorded that the ethics material covering platform pages was submitted, but the
repository contains no institutional approval reference or participant dataset at the evidence
cut-off. Consequently, no recruitment, response, usability score or qualitative participant
theme is reported. O7's usability component remains pending approval and data collection.

Reproducibility is supported through pinned commits, content fingerprints, deterministic
post-processing, campaign receipts, tests and machine-readable evidence. It is constrained by the
private source repositories and checkpoint, so an unauthorised third party cannot reconstruct
every raw input from this repository alone. The dissertation distinguishes computational
repeatability for an authorised researcher from fully open reproduction.

### 2.9 Method selection and alternatives

The import-first design was chosen over live simulator coupling because the producer runs are
expensive, private and already carry source artifacts; re-execution is permitted only through the
bounded evaluator. A typed Python library beneath Streamlit was chosen over notebook-only analysis
so metric semantics can be tested once and shared by CLI, UI and reports. Deterministic,
content-addressed evidence was chosen over LLM-generated interpretation in the scientific path
because a fluent summary cannot supply lineage or repeatability. Finally, paired seeds were chosen
over independent-arm summaries because the same evaluator randomness can be differenced directly.
These choices trade immediacy and narrative flexibility for refusal, reproducibility and audit.

## 3. Evaluation and reflection

### 3.1 Regime selection and pilot

At capacities 2.5, 1.5, 1.0 and 0.75, the four normal regimes (`we`, `ev`, `wd_am`, `wd_pm`)
were invariant at the reported precision. Their 139–215 padded slots did not generate enough
pressure for the intervention to bind. The `inc` trace, with 2,488 padded slots, did. This
contrast prevents the result from being described as a generic Manchester effect: capacity was
an active intervention only in the modelled collapse hour.

Across three pilot seeds, deadline attainment remained approximately 79.1% at every capacity.
Mean latency nevertheless decreased monotonically from 9,798.8 ms at capacity 2.5 to 3,083.6 ms
at 0.75, a 68.5% reduction. Offload shares and aggregate energy were effectively unchanged. The
pilot therefore established the phenomenon and the candidate explanation—queue clipping without
policy adaptation—but remained exploratory because the trace and contrast were selected from
pilot evidence.

### 3.2 Held-out confirmatory result

The signed comparison replicated the latency reversal. The capacity-2.5 arm had an across-seed
mean latency of 12,027.5 ms; capacity 0.75 had 3,716.6 ms, a 3.24-fold ratio. The primary paired
difference was **−8,310.9 ms**, with paired bootstrap interval
**[−9,097.5, −7,524.3]**. Every one of the five held-out seeds had a negative paired difference.
The exact two-sided sign-test p-value is **0.0625**, which is both the observed result and the
smallest possible at n=5. The interval and full seed agreement support a large, stable effect in
these evaluator seeds; the sample does not justify a population-wide asymptotic claim.

Deadline attainment remained flat, replicating the pilot null. In practical terms, removing
1.75 capacity units did not rescue more tasks or cause a visible aggregate deadline loss. It
reduced how late many already-late tasks became. RQ1 is therefore answered: under the evaluated
saturation, lower configured RSU concurrency greatly lowers mean latency but does not improve the
source-defined service outcome represented by deadline attainment.

### 3.3 Actions and observations

The exact action audit rules out adaptive policy decisions as the explanation for the pilot
curve. Each of nine pairwise capacity comparisons aligned **8,956,800** vehicle-slot decisions.
There were **zero mismatches**, including offload targets. The result is stronger than equal
action proportions: the same vehicle made the same decision at the same slot across compared
capacity arms.

This invariance is consistent with the observation contract. Vehicle-side actor inputs were
identical across capacity arms and contained no RSU-load term. The environment's RSU state did
differ in roughly 41% of cells, but that changing state was not part of the vehicle decision input
used by the evaluated actor. Capacity could therefore alter queue arithmetic without giving the
policy information from which to adapt.

That observation gap is real but not the complete mechanism. The later population analysis found
an even simpler partition: the policy's offload choice aligned exactly with compute tier in the
measured artifacts. The always-offloading group was 100% tier 0 in every analysed cell; the
never-offloading group contained no tier-0 vehicles. Workload per slot (approximately 5,263 versus
5,243 tasks) and task-class shares (20/30/50%) were nearly or exactly balanced, so neither
explained the decision split.

### 3.4 Distributional mechanism

The mean moved while the middle of the distribution did not. Pilot p50 latency was **44.3 ms** at
every capacity, changing by only −0.10% across the 3.33-fold squeeze. The fraction of tasks above
one second changed by −0.07 percentage points. In contrast, p99 fell by **69.9%**, and
**97.9–99.4%** of total latency mass lay above one second. The apparent average improvement was
therefore almost entirely a tail effect.

The missed-task ceiling followed a simple evaluator relation. Across 36 cell-by-class pairs, the
p95 of missed latency divided by capacity was approximately **39,959 ms**, with sample standard
deviation 166 ms and relative spread 0.41%. At the pilot capacities, the resulting ceilings were
roughly 60–300 times larger than the 100 ms and 500 ms deadlines. Reducing the ceiling compressed
an already-failed tail long before it approached a threshold at which large numbers of tasks
could switch from failure to success.

The vehicle partition makes the aggregate failure more concrete. Approximately three-fifths of
vehicles never offloaded. Across the deeper 25-fold squeeze from 2.5 to 0.1, their mean latency was
bit-identical at **39.6 ms**; their median, missed-task p95 and attainment were also unchanged to
recorded precision. The remaining always-offloading population carried the queue response: in two
seeds its mean fell from **25,625 to 1,061 ms** and **27,438 to 1,074 ms**. Roughly 92% of missed
tasks belonged to that offloading population.

The confirmed fleet mean of −8,310.9 ms therefore describes no vehicle group. About 60% received
exactly no latency change in the measured deep-squeeze decomposition; about 40% received an
order-of-magnitude change from extremely late to still commonly late. The aggregate averages the
two into a value experienced by neither. Failure was also concentrated: the failure Gini ranged
from 0.616 to 0.627 and the worst decile contained 34–36% of failures, despite a task-count Gini of
only 0.028. Tier-1 and tier-2 vehicles never missed the 500 ms T2 deadline in the analysed cells.

RQ2 is answered by this chain: the actor makes capacity-invariant, compute-tier-partitioned
decisions; always-offloading tier-0 vehicles enter a shared RSU queue; the configured ceiling clips
their already-failed latency; and a tail-dominated mean reports that clipping as improvement.

### 3.5 RSU asymmetry and correction

Four RSUs operated at 95.8–97.9% of the configured concurrency bound while the other four were
near zero; the busy four carried **99.1%** of measured load. The same four were saturated across a
25-fold capacity range and another seed. Source inspection shows that the environment selects a
best RSU using maximum V2I link quality and contains no load term in that expression.

It would be tempting to conclude that link-quality association caused the imbalance. The project
does not make that claim. An initial analysis counted vehicle-step assignments with an incorrect
unit and attributed sends to an RSU whose busy time was exactly zero. That interpretation was
withdrawn. Placement, reachability, reporting semantics and association may all contribute. What
stands is the load asymmetry; its cause is undetermined. This correction demonstrates why source
inspection and contradictory measures must constrain a plausible narrative.

### 3.6 Predeclared exploratory tests

The closed-form ceiling produced a successful out-of-range prediction. At capacities 0.5, 0.25
and 0.1—down to 7.5 times below the fitted pilot floor—**27/27** predeclared cell checks fell
within the ±5% tolerance. Median latency was only a partial miss against its secondary prediction,
and the tested range stopped at a predeclared bound just below 0.1. This result strengthens the
claim that the mean-latency curve is evaluator queue arithmetic in this setting. It does not make
the fitted relation a universal VEC law.

The actor-crossover result bounded generality. The trained actor beat the baseline actor on
deadline completion at all four capacities by **6.0835–6.0946 percentage points**, so no winner
crossover occurred. However, the predicted latency-slope similarity was refuted: slopes were
3,828.2 and 6,555.4 ms per capacity unit, a **52.53%** symmetric relative contrast against the
frozen 5% band. The `uk2030` fleet preset matches the trained actor's distribution but not the
baseline actor's. Policy and preset mismatch are inseparable, so this is not evidence about MAPPO
versus another algorithm.

The onset-scaling prediction was also refuted. It correctly predicted four of six exact checks,
including the load-bearing claim that `wd_am` would first bind at capacity 0.1. The two misses were
predicted-inert capacity-0.25 cells on `we` and `wd_pm`; each differed only in mean latency for one
seed, by 0.000242979 ms and 0.000024348 ms. The deviations are operationally negligible but fail
the exact-equality rule that was frozen. At capacity 0.1, all four normal regimes moved weakly in
the same direction, with completion changes of +0.0011 to +0.0043 percentage points and latency
changes of −0.024 to −0.205 ms. The correct conclusion is “exact prediction refuted on a coarse
grid”, not “density is irrelevant” and not “the tiny misses prove a material effect”.

### 3.7 Captured bus sessions

The captured mobility itself showed a credible time-of-day contrast. The retained dawn and peak
traces contained 961 and 1,212 buses, with peak concurrency 827 and 1,000. Across the wider
session records, morning-peak buses were about 44% slower than night observations (mean 3.518
versus 6.290 m/s). This is a descriptive temporal association, not a causal congestion estimate.

The fresh Sparse-64 retained result had mean held-out peak deadline completion of
**0.501355** at capacity 0.75, sample SD **0.088677**, and seed range **0.400527–0.634229**.
Class rates were T1 **0.314816**, T2 **0.592028** and T3 **0.521530**. Capacity 2.5 produced
**0.501233**. The lower-capacity arm was therefore 0.0122 percentage points higher and its mean
latency 160.252 ms lower. Aggregate action shares and energy were identical across the two arms.

This is qualitatively consistent with the central reversal, but it cannot confirm it. Only about
45% of occupied cells had Sparse-64 coverage; tasks, hardware and sites were generated; the input
exceeded VEC-06 geography; and the execution performed an unintended duplicate return. The
correct RQ3 answer is therefore mixed. The qualitative metric direction reappears under a very
different mobility input, but the bus result is descriptive corroboration outside admission. The
confirmed claim remains confined to `inc` and the audited checkpoint.

### 3.8 What the result means

The study's headline can be stated precisely: in a saturated, modelled event-district trace,
reducing configured per-vehicle RSU concurrency from 2.5 to 0.75 lowered mean task latency by
8.31 seconds across five held-out evaluator seeds, while source-defined deadline attainment
remained flat. The result is counter-intuitive only if mean latency is treated as a complete
proxy for service quality. Once the distribution and vehicle partition are visible, it is a
coherent queueing response.

Lower capacity truncates or limits how long offloaded work remains in an already-failing queue.
Because the actor does not change decisions and because the configured missed-task ceilings stay
far above class deadlines, the intervention changes lateness magnitude rather than success. The
local majority is unaffected. The offloading minority experiences a large numerical reduction but
still accounts for nearly all missed tasks. The aggregate combines those populations and reports a
large improvement that no representative vehicle receives.

This does not imply that mean latency is useless. It implies that its adequacy depends on the
decision it is meant to support. Mean latency is informative about total accumulated delay. It is
misleading if interpreted as evidence that service improved for most vehicles or that more tasks
met their requirements. A defensible VEC evaluation should jointly report attainment, quantiles,
tail mass and population-conditioned outcomes, with exact metric semantics.

### 3.9 Why this matters for learned offloading policies

A learned actor is often evaluated as if it were the sole source of performance variation. Here,
the policy is literally action-invariant under the intervention. The metric response arises
downstream in evaluator and queue logic. Without action-level comparison, an analyst could
incorrectly infer that the policy adapted well to scarcity. Without observation inspection, they
might expect adaptation that the actor was not equipped to make. Without the compute-tier
partition, they could attribute the effect to workload or task mix rather than a fixed fleet
split.

The implication is methodological: policy evaluation must cover the whole policy–environment–
metric chain. At minimum, a resource-sensitivity study should report whether the intervention is
observable to the policy, whether decisions change, how queue states change, and which population
contributes to the aggregate. A high return or favourable mean cannot by itself identify the
mechanism.

The actor-crossover study reinforces this caution. The trained checkpoint is consistently better
than the baseline on deadline completion, yet their latency slopes differ substantially. One
cannot transfer the exact capacity response from one actor to another, even within the same
environment. Because the fleet preset matches only one checkpoint's training distribution, the
comparison also shows why algorithm labels are too coarse for causal interpretation.

### 3.10 Scientific value of failed predictions

The strongest argument is not that every extension succeeded. The ceiling prediction held 27/27,
which supports the queue-arithmetic explanation. The slope-invariance prediction failed by a wide
margin, which limits actor generality. The onset-scaling prediction failed under its exact rule,
even though the numerical misses were tiny. The RSU causal narrative was partially withdrawn when
its counting unit proved wrong. The bus campaign returned usable numbers but failed admission.

Reporting these outcomes has two benefits. First, it demonstrates that the execution and
reporting process can produce an unfavourable verdict rather than merely rationalising a desired
story. Second, it clarifies the boundary of the central finding. The inverse-capacity ceiling is
robust within the audited evaluator cells; the precise onset and actor slope are not; transfer to
captured mobility is suggestive only.

This is also why a fresh bus rerun is not automatically required. Repeating the same settings may
produce a cleaner archive, but it would not repair the fundamental geography and synthetic-task
limitations. The retained result already answers the modest descriptive question. A new run would
only be justified by a separately predeclared, contract-compatible design and a research question
whose answer warrants the compute cost.

### 3.11 Contribution of TrafficTwin

TrafficTwin's contribution is best understood as epistemic infrastructure: software that makes it
easier to know what a result does and does not support. Its canonical contracts prevent source
fields from acquiring new meanings in a page. Its unavailable states stop missing metrics from
becoming zero. Its provenance DAG permits a marker or researcher to walk from a metric to the
source row. Its campaign approval binds design bytes before execution. Its evidence records retain
nulls, refutations and execution deviations.

The interface alone cannot make a finding correct. Provenance can faithfully trace a flawed
source; a signed protocol can test a poorly motivated hypothesis; deterministic code can repeat a
construct-invalid metric. The platform's value is that those weaknesses remain inspectable and
can be discussed. In this dissertation, that auditability converted an apparently favourable
mean into a population-specific mechanism and prevented a non-admitted bus return from being
presented as confirmation.

The engineering breadth—39 routed views at the recorded checkpoint, statistical tools, scenario
composition, report exports, migration and cache machinery—is secondary to this argument. It
shows a substantial implemented system, but a distinction-level dissertation should not equate
feature count with research contribution. The research contribution is the disciplined path from
source contract through experiment to bounded interpretation.

### 3.12 Validity and limitations

**Construct validity.** Deadline attainment is defined by the producer's T1/T2/T3 thresholds, and
capacity is an environment control. Neither is a direct measurement of real application utility,
human safety or infrastructure cost. Mean task latency includes a heavy failed tail. The
dissertation mitigates this by reporting exact definitions and decomposition, but it cannot turn
simulator constructs into physical outcomes.

**Internal validity.** Pairing seeds, freezing a primary outcome and preserving exact actions
strengthen attribution of the numerical response to the capacity intervention inside the
evaluator. However, the detailed tier and tail explanation is post hoc. The RSU load asymmetry's
cause remains unresolved. The actor lacks load observation, but the study does not rerun a
modified observation model and cannot claim that adding such a term would improve behaviour.

**Statistical conclusion validity.** The held-out effect is large and all five directions agree,
but n=5 limits inference. The exact two-sided sign test cannot reach p<0.05 at that sample size.
The bootstrap interval describes paired evaluator-seed uncertainty under the recorded procedure;
it is not a guarantee over traffic days, networks or trained checkpoints. Many mechanism probes
are descriptive and are labelled accordingly.

**External validity.** The central result uses one `inc` trace from one bounded district, one SUMO
seed for traffic generation, one engine version and one trained checkpoint. Four normal regimes
are inert at pilot capacities. The bus successor improves temporal mobility realism but loses VEC
admission and still synthesises tasks and infrastructure. No conclusion is made about all Greater
Manchester traffic, deployed RSUs or live service quality.

**Implementation and source validity.** The environment and data are producer-owned private
research artifacts. Commits and hashes pin what was inspected, and permission with citation is
recorded, but open readers cannot reproduce the complete chain without authorised source access.
The exact environment is complex; the withdrawn association explanation shows the risk of using
the wrong measurement unit. Independent implementation review would strengthen the result.

**Execution validity.** The admitted held-out capacity campaign completed according to its signed
design. The B-BUS campaign did not: stale remote credentials caused recoveries and a terminal
ordering defect caused a duplicate return. Settings did not change, but only the last archive
survives, so equality across returns is unknowable. It is correctly excluded from confirmatory
evidence.

**Usability and ethics.** Automated UI tests and a prepared evaluation instrument establish
software readiness, not user usefulness. The owner reports ethics submission, but approval and
participant evidence are absent. O7 is only partially achieved until an approved study is run and
reported. No synthetic survey result is substituted.

### 3.13 Implications and future work

The immediate recommendation for VEC evaluation is a minimum reporting bundle: mean and median
latency, at least one tail quantile, deadline attainment by task class, proportion and latency mass
beyond an application-relevant threshold, action changes under intervention, and per-vehicle or
per-policy partitioning. When resource controls can affect failure bookkeeping or queue ceilings,
the evaluator equation should be included alongside plots.

A stronger confirmatory extension would predeclare the vehicle-partition mechanism itself. It
would reserve new traffic traces or seeds, predict subgroup-specific effects, and test whether the
never-offload population remains invariant while the always-offload population follows the
ceiling relation. Increasing the seed cohort would improve exact-test resolution. Crossing actors
with fleet presets matched to their training distributions would separate checkpoint behaviour
from distribution mismatch.

For mobility transfer, the next defensible step is not another whole-fleet Sparse-64 run. It is a
bounded corridor or district whose occupied cells can receive complete VEC-06-compatible coverage,
with site placement fixed independently of outcomes. Observed bus positions could supply mobility,
but tasks, radios and infrastructure would still need honest synthetic labels unless measured
sources become available. A comparison should be framed as mobility-conditioned simulation, not
live VEC validation.

For the platform, the priority is consolidation. The final user evaluation should proceed only
after institutional approval, use the already prepared tasks, and report task success, time,
usefulness and qualitative limitations without over-generalising from a small convenience sample.
The dissertation video should complement this report by showing the dynamic replay, provenance
walk and experiment receipt, while devoting its opening and close to the metric-reversal argument.

## 4. Conclusion

TrafficTwin was built to make heterogeneous VEC research artifacts auditable, but its most useful
output is a warning about apparently ordinary metrics. In the signed held-out study, reducing a
configured RSU concurrency ceiling from 2.5 to 0.75 lowered mean task latency by 8,310.9 ms across
five paired seeds while deadline attainment remained flat. Exact action comparison showed that
the learned policy did not adapt. Distributional and vehicle-level analysis showed why: the local
majority was unchanged, while an always-offloading, weak-compute population carried nearly all
failures and the compressible RSU-queue tail. The fleet mean described neither group.

The result supports the project's overall claim within a deliberately narrow boundary. Standard
aggregate QoS metrics can reward resource degradation in this VEC evaluator unless they are
decomposed by outcome, tail and vehicle policy. A successful 27/27 ceiling prediction strengthens
the mechanism. Refuted actor and onset predictions limit generality. The captured-bus run is
qualitatively consistent but non-admitted and cannot promote the claim to real Manchester.

The dissertation's contribution is therefore not a better offloading policy or a universal
capacity rule. It is an auditable experiment showing when “better” mean latency is not better
service, and a reproducible method for finding the affected population before making a claim. The
remaining work is human and presentational: reference verification, approved usability
evaluation if permission arrives, supervisor review, final formatting and a video that shows the
evidence chain rather than repeating the report.

### 4.1 Outcomes against objectives

**O1—canonical contracts: achieved.** Source-specific readers, immutable snapshots and typed
canonical tables provide a validated boundary for synthetic, SUMO and audited TOS artifacts.
Ambiguity is refused or made explicit rather than guessed.

**O2—deterministic metrics, diagnostics and provenance: achieved within implemented contracts.**
The metric and rule libraries produce reproducible artifacts, while the provenance path connects
reported values to definitions and bounded source rows. The RSU correction demonstrates that
traceability supports challenge and withdrawal, not automatic correctness.

**O3—statistical comparison: achieved.** Common-seed pairing, bootstrap summaries, exact
direction checks, equivalence/ranking/power machinery and signed experiment receipts exist. The
held-out result demonstrates their use on the empirical centre of the dissertation rather than on
synthetic fixtures alone.

**O4—what-if analysis: achieved as software.** Scenario mutations, bounded sweeps and measurement-
imperfection tools are implemented behind deterministic contracts. They support future research
but were intentionally not allowed to displace the one-story word budget.

**O5—research UX: achieved as an implemented interface, not as a usability finding.** The UI
exposes unavailable states, historical replay, diagnostics, provenance, human-review ledgers and
campaign records. Whether intended users find it effective remains an unanswered human question.

**O6—Manchester TOS evaluation: achieved within a narrower, stronger scope than the initial
five-scenario catalogue implied.** Four normal regimes were inert at pilot capacities; the one
collapse hour produced the signed held-out result, detailed mechanism and bounded prediction
tests. The bus successor adds descriptive mobility evidence but is explicitly non-admitted.

**O7—correctness/reproducibility achieved; usability partially achieved.** The repository has
3,728 collected tests plus golden, fingerprint and campaign controls. The owner reports ethics
submission, but no approval or participant data exists, so the usability strand cannot be marked
complete.

### 4.2 Project achievement and approach

The project's difficulty lay less in inventing another dashboard than in maintaining semantic and
evidential integrity across heterogeneous sources, private producer artifacts, a stochastic
multi-agent evaluator, statistical studies, a large UI and expensive remote execution. The
implemented response was a typed, deterministic core beneath the interface; source-specific
admission before analysis; content-addressed provenance; and explicit claim states. That design
enabled a finding to be followed from a paired effect through actions, observations, queue tails
and vehicle groups.

Several challenges improved the work. A wide trace exposed a verification-precision defect before
the held-out campaign. Post-hoc unit cross-checks forced withdrawal of the RSU association cause.
Exact onset rules returned “refuted” for sub-microsecond differences rather than accepting a
post-hoc tolerance. Remote B-BUS supervision recovered checkpoints but also revealed credential
expiry and terminal-state ordering failures; the retained output was downgraded instead of
laundered. These are not peripheral mishaps. They show that the platform's refusal and provenance
mechanisms were exercised when evidence was inconvenient.

Scope decisions were equally important. The work did not retrain or optimise MAPPO, claim a live
digital twin, infer general traffic from buses, invent participant results, or spend further GPU
budget merely to improve the appearance of a non-admitted arm. It prioritised a defensible
mechanism over feature narration. This is why the manuscript can support a strong project-
achievement case without implying that all 39 routes are individually novel research.

### 4.3 Future work

The first scientific extension should predeclare the subgroup mechanism on new, untouched cells:
the never-offload population should remain invariant while the always-offload population follows
the queue ceiling. A larger paired-seed cohort would improve exact-test resolution. Actor studies
should cross checkpoints with fleet presets matched to their training distributions so that
policy behaviour can be separated from preset mismatch.

Observed-mobility transfer needs a bounded geography with complete VEC-06-compatible
infrastructure fixed before outcomes. Bus paths can improve mobility provenance, but compute
tasks, radios and sites must remain labelled synthetic unless they are measured. A multi-district
or multi-city study should be attempted only after one such corridor passes the source and
admission gates.

Finally, once institutional approval exists, the prepared user study should evaluate whether
researchers can import, compare and trace a result more accurately with TrafficTwin. Task success,
time and qualitative explanation should be reported with the limitations of the actual sample.
An LLM-assisted composer may draft future scenarios, but its output must remain outside the
evidence path and behind the same signed execution boundary. These extensions preserve the core
lesson: new capability is valuable only when its provenance and claim ceiling remain visible.

## References

[1] M. Satyanarayanan, “The emergence of edge computing,” Computer, vol. 50, no. 1, pp. 30–39, Jan. 2017, doi: 10.1109/mc.2017.9.

[2] W. Shi, J. Cao, Q. Zhang, Y. Li, and L. Xu, “Edge computing: Vision and challenges,” IEEE Internet of Things Journal, vol. 3, no. 5, pp. 637–646, Oct. 2016, doi: 10.1109/jiot.2016.2579198.

[3] P. Mach and Z. Becvar, “Mobile edge computing: A survey on architecture and computation offloading,” IEEE Communications Surveys & Tutorials, vol. 19, no. 3, pp. 1628–1656, 2017, doi: 10.1109/comst.2017.2682318.

[4] Y. Mao, C. You, J. Zhang, K. Huang, and K. B. Letaief, “A survey on mobile edge computing: The communication perspective,” IEEE Communications Surveys & Tutorials, vol. 19, no. 4, pp. 2322–2358, 2017, doi: 10.1109/comst.2017.2745201.

[5] J. Schulman, F. Wolski, P. Dhariwal, A. Radford, and O. Klimov, “Proximal policy optimization algorithms.” arXiv, 2017. doi: 10.48550/ARXIV.1707.06347.

[6] C. Yu et al., “The surprising effectiveness of PPO in cooperative multi-agent games,” in Advances in neural information processing systems 35, in NeurIPS 2022. Neural Information Processing Systems Foundation, Inc. (NeurIPS), 2022, pp. 24611–24624. doi: 10.52202/068431-1787.

[7] M. Tang and V. W. S. Wong, “Deep reinforcement learning for task offloading in mobile edge computing systems,” IEEE Transactions on Mobile Computing, vol. 21, no. 6, pp. 1985–1997, 2022, doi: 10.1109/tmc.2020.3036871.

[8] E. Karimi, Y. Chen, and B. Akbari, “Task offloading in vehicular edge computing networks via deep reinforcement learning,” Computer Communications, vol. 189, pp. 193–204, May 2022, doi: 10.1016/j.comcom.2022.04.006.

[9] J. Dean and L. A. Barroso, “The tail at scale,” Communications of the ACM, vol. 56, no. 2, pp. 74–80, Feb. 2013, doi: 10.1145/2408776.2408794.

[10] R. Gorsane, O. Mahjoub, R. J. D. Kock, R. Dubb, S. Singh, and A. Pretorius, “Towards a standardised performance evaluation protocol for cooperative MARL,” in Advances in neural information processing systems 35, in NeurIPS 2022. Neural Information Processing Systems Foundation, Inc. (NeurIPS), 2022, pp. 5510–5521. doi: 10.52202/068431-0398.

[11] B. A. Nosek, C. R. Ebersole, A. C. DeHaven, and D. T. Mellor, “The preregistration revolution,” Proceedings of the National Academy of Sciences, vol. 115, no. 11, pp. 2600–2606, Mar. 2018, doi: 10.1073/pnas.1708274114.

[12] J. Pineau et al., “Improving reproducibility in machine learning research,” Journal of Machine Learning Research, vol. 22, no. 164, pp. 1–20, 2021, Available: https://jmlr.org/papers/v22/20-303.html

[13] P. A. Lopez et al., “Microscopic traffic simulation using SUMO,” in 2018 21st international conference on intelligent transportation systems (ITSC), IEEE, Nov. 2018, pp. 2575–2582. doi: 10.1109/itsc.2018.8569938.

[14] Department for Transport, Technical guidance: Publishing location data using the bus open data service (SIRI-VM). UK Government, 2020. Available: https://www.gov.uk/government/publications/technical-guidance-publishing-location-data-using-the-bus-open-data-service-siri-vm

[15] R. P. Putra, “Intelligent task offloading: Current state limitations and proposed potential solutions,” The University of Manchester, n.d.

[16] R. P. Putra, “VEC environment.” Private University of Manchester GitLab repository, 2026.

[17] R. P. Putra, “TOS trace data.” Private University of Manchester GitLab repository, 2026.

[18] D. Jones, C. Snider, A. Nassehi, J. Yon, and B. Hicks, “Characterising the digital twin: A systematic literature review,” CIRP Journal of Manufacturing Science and Technology, vol. 29, pp. 36–52, May 2020, doi: 10.1016/j.cirpj.2020.02.002.

[19] A. Fuller, Z. Fan, C. Day, and C. Barlow, “Digital twin: Enabling technologies, challenges and open research,” IEEE Access, vol. 8, pp. 108952–108971, 2020, doi: 10.1109/access.2020.2998358.

[20] A. Rasheed, O. San, and T. Kvamsdal, “Digital twin: Values, challenges and enablers from a modeling perspective,” IEEE Access, vol. 8, pp. 21980–22012, 2020, doi: 10.1109/access.2020.2970143.

[21] B. R. Barricelli, E. Casiraghi, and D. Fogli, “A survey on digital twin: Definitions, characteristics, applications, and design implications,” IEEE Access, vol. 7, pp. 167653–167671, 2019, doi: 10.1109/access.2019.2953499.

[22] W. Kritzinger, M. Karner, G. Traar, J. Henjes, and W. Sihn, “Digital twin in manufacturing: A categorical literature review and classification,” IFAC-PapersOnLine, vol. 51, no. 11, pp. 1016–1022, 2018, doi: 10.1016/j.ifacol.2018.08.474.

[23] F. Tao, J. Cheng, Q. Qi, M. Zhang, H. Zhang, and F. Sui, “Digital twin-driven product design, manufacturing and service with big data,” The International Journal of Advanced Manufacturing Technology, vol. 94, no. 9–12, pp. 3563–3576, Mar. 2017, doi: 10.1007/s00170-017-0233-1.

[24] M. Batty, “Digital twins,” Environment and Planning B: Urban Analytics and City Science, vol. 45, no. 5, pp. 817–820, 2018, doi: 10.1177/2399808318796416.

[25] K. Kušić, R. Schumann, and E. Ivanjko, “A digital twin in transportation: Real-time synergy of traffic data streams and simulation for virtualizing motorway dynamics,” Advanced Engineering Informatics, vol. 55, p. 101858, Jan. 2023, doi: 10.1016/j.aei.2022.101858.

[26] A. Rudskoy, I. Ilin, and A. Prokhorov, “Digital twins in the intelligent transport systems,” Transportation Research Procedia, vol. 54, pp. 927–935, 2021, doi: 10.1016/j.trpro.2021.02.152.

[27] W. Lu, X. Fu, J. Liu, A. Hainen, F. Xia, and O. Chen, “A ‘digital twin’ traffic simulation tool for network-wide real-time traffic monitoring and management,” Journal of Intelligent Transportation Systems, pp. 1–13, Aug. 2025, doi: 10.1080/15472450.2025.2553287.

[28] Y. Wang, H. Wang, W. Wang, S. Song, and X. Fu, “Architecture, application, and prospect of digital twin for highway infrastructure,” Journal of Traffic and Transportation Engineering (English Edition), vol. 11, no. 5, pp. 835–852, Oct. 2024, doi: 10.1016/j.jtte.2024.03.003.

[29] C. Ge and S. Qin, “Digital twin intelligent transportation system (DT‐ITS)—a systematic review,” IET Intelligent Transport Systems, vol. 18, no. 12, pp. 2325–2358, Aug. 2024, doi: 10.1049/itr2.12539.

[30] J. Guo, M. Bilal, Y. Qiu, C. Qian, X. Xu, and K.-K. Raymond Choo, “Survey on digital twins for internet of vehicles: Fundamentals, challenges, and opportunities,” Digital Communications and Networks, vol. 10, no. 2, pp. 237–247, Apr. 2024, doi: 10.1016/j.dcan.2022.05.023.

[31] D. Krajzewicz, J. Erdmann, M. Behrisch, and L. Bieker-Walz, “Recent development and applications of SUMO – simulation of urban MObility,” International Journal On Advances in Systems and Measurements, vol. 5, no. 3–4, pp. 128–138, 2012, Available: https://sumo.dlr.de/docs/Publications.html

[32] M. Treiber, A. Hennecke, and D. Helbing, “Congested traffic states in empirical observations and microscopic simulations,” Physical Review E, vol. 62, no. 2, pp. 1805–1824, Aug. 2000, doi: 10.1103/physreve.62.1805.

[33] M. J. Lighthill and G. B. Whitham, “On kinematic waves II. A theory of traffic flow on long crowded roads,” Proceedings of the Royal Society of London. Series A. Mathematical and Physical Sciences, vol. 229, no. 1178, pp. 317–345, May 1955, doi: 10.1098/rspa.1955.0089.

[34] P. I. Richards, “Shock waves on the highway,” Operations Research, vol. 4, no. 1, pp. 42–51, Feb. 1956, doi: 10.1287/opre.4.1.42.

[35] C. F. Daganzo, “The cell transmission model: A dynamic representation of highway traffic consistent with the hydrodynamic theory,” Transportation Research Part B: Methodological, vol. 28, no. 4, pp. 269–287, Aug. 1994, doi: 10.1016/0191-2615(94)90002-7.

[36] K. Nagel and M. Schreckenberg, “A cellular automaton model for freeway traffic,” Journal de Physique I, vol. 2, no. 12, pp. 2221–2229, Dec. 1992, doi: 10.1051/jp1:1992277.

[37] M. A. Quddus, W. Y. Ochieng, and R. B. Noland, “Current map-matching algorithms for transport applications: State-of-the art and future research directions,” Transportation Research Part C: Emerging Technologies, vol. 15, no. 5, pp. 312–328, Oct. 2007, doi: 10.1016/j.trc.2007.05.002.

[38] P. Newson and J. Krumm, “Hidden markov map matching through noise and sparseness,” in Proceedings of the 17th ACM SIGSPATIAL international conference on advances in geographic information systems, in GIS ’09. ACM, Nov. 2009, pp. 336–343. doi: 10.1145/1653771.1653818.

[39] Y. Lou, C. Zhang, Y. Zheng, X. Xie, W. Wang, and Y. Huang, “Map-matching for low-sampling-rate GPS trajectories,” in Proceedings of the 17th ACM SIGSPATIAL international conference on advances in geographic information systems, in GIS ’09. ACM, Nov. 2009, pp. 352–361. doi: 10.1145/1653771.1653820.

[40] S. Brakatsoulas, D. Pfoser, R. Salas, and C. Wenk, “On map-matching vehicle tracking data,” in Proceedings of the 31st international conference on very large data bases, VLDB Endowment, 2005, pp. 853–864. Available: https://www.vldb.org/conf/2005/program/paper/fri/p853-brakatsoulas.pdf

[41] M. Hashemi and H. A. Karimi, “A critical review of real-time map-matching algorithms: Current issues and future directions,” Computers, Environment and Urban Systems, vol. 48, pp. 153–165, Nov. 2014, doi: 10.1016/j.compenvurbsys.2014.07.009.

[42] D. Reinke, R. Dowling, R. Hranac, and V. Alexiadis, “Development of a high-level algorithm verification and validation procedure for traffic microsimulation models,” Transportation Research Record: Journal of the Transportation Research Board, vol. 1876, no. 1, pp. 151–158, Jan. 2004, doi: 10.3141/1876-16.

[43] D. Henclewood, W. Suh, M. Rodgers, M. Hunter, and R. Fujimoto, “A case for real-time calibration of data-driven microscopic traffic simulation tools,” in Proceedings title: Proceedings of the 2012 winter simulation conference (WSC), IEEE, Dec. 2012, pp. 1–12. doi: 10.1109/wsc.2012.6465294.

[44] E. T. Cascan, J. Ivanchev, D. Eckhoff, A. Sangiovanni-Vincentelli, and A. Knoll, “Multi-objective calibration of microscopic traffic simulation for highway traffic safety,” in 2019 IEEE intelligent transportation systems conference (ITSC), IEEE, Oct. 2019, pp. 4548–4555. doi: 10.1109/itsc.2019.8917044.

[45] D. Henclewood, W. Suh, M. O. Rodgers, R. Fujimoto, and M. P. Hunter, “A calibration procedure for increasing the accuracy of microscopic traffic simulation models,” SIMULATION, vol. 93, no. 1, pp. 35–47, Oct. 2016, doi: 10.1177/0037549716673723.

[46] Department for Transport, Road traffic statistics. UK Government, 2026. Available: https://roadtraffic.dft.gov.uk/

[47] National Highways, WebTRIS traffic flow data. National Highways, 2026. Available: https://webtris.highwaysengland.co.uk/

[48] A. V. Dastjerdi and R. Buyya, “Fog computing: Helping the internet of things realize its potential,” Computer, vol. 49, no. 8, pp. 112–116, Aug. 2016, doi: 10.1109/mc.2016.245.

[49] F. Bonomi, R. Milito, J. Zhu, and S. Addepalli, “Fog computing and its role in the internet of things,” in Proceedings of the first edition of the MCC workshop on mobile cloud computing, in SIGCOMM ’12. ACM, Aug. 2012, pp. 13–16. doi: 10.1145/2342509.2342513.

[50] N. Abbas, Y. Zhang, A. Taherkordi, and T. Skeie, “Mobile edge computing: A survey,” IEEE Internet of Things Journal, vol. 5, no. 1, pp. 450–465, Feb. 2018, doi: 10.1109/jiot.2017.2750180.

[51] Y. Mao, J. Zhang, and K. B. Letaief, “Dynamic computation offloading for mobile-edge computing with energy harvesting devices,” IEEE Journal on Selected Areas in Communications, vol. 34, no. 12, pp. 3590–3605, Dec. 2016, doi: 10.1109/jsac.2016.2611964.

[52] C. You, K. Huang, H. Chae, and B.-H. Kim, “Energy-efficient resource allocation for mobile-edge computation offloading,” IEEE Transactions on Wireless Communications, vol. 16, no. 3, pp. 1397–1411, Mar. 2017, doi: 10.1109/twc.2016.2633522.

[53] X. Chen, L. Jiao, W. Li, and X. Fu, “Efficient multi-user computation offloading for mobile-edge cloud computing,” IEEE/ACM Transactions on Networking, vol. 24, no. 5, pp. 2795–2808, Oct. 2016, doi: 10.1109/tnet.2015.2487344.

[54] S. Sardellitti, G. Scutari, and S. Barbarossa, “Joint optimization of radio and computational resources for multicell mobile-edge computing,” 2014, doi: 10.48550/ARXIV.1412.8416.

[55] X. Hou, Y. Li, M. Chen, D. Wu, D. Jin, and S. Chen, “Vehicular fog computing: A viewpoint of vehicles as the infrastructures,” IEEE Transactions on Vehicular Technology, vol. 65, no. 6, pp. 3860–3873, 2016, doi: 10.1109/tvt.2016.2532863.

[56] M. A. Javed, S. Zeadally, and E. B. Hamida, “Data analytics for cooperative intelligent transport systems,” Vehicular Communications, vol. 15, pp. 63–72, Jan. 2019, doi: 10.1016/j.vehcom.2018.10.004.

[57] N. Cha, C. Wu, T. Yoshinaga, Y. Ji, and K.-L. A. Yau, “Virtual edge: Exploring computation offloading in collaborative vehicular edge computing,” IEEE Access, vol. 9, pp. 37739–37751, 2021, doi: 10.1109/access.2021.3063246.

[58] X. Gu and G. Zhang, “Energy-efficient computation offloading for vehicular edge computing networks,” Computer Communications, vol. 166, pp. 244–253, Jan. 2021, doi: 10.1016/j.comcom.2020.12.010.

[59] S. Li, G. Zhu, and S. Lin, “Computation offloading with time-varying fading channel in vehicular edge computing,” in 2018 IEEE globecom workshops (GC wkshps), IEEE, Dec. 2018, pp. 1–6. doi: 10.1109/glocomw.2018.8644140.

[60] R. Meneguette, R. De Grande, J. Ueyama, G. P. R. Filho, and E. Madeira, “Vehicular edge computing: Architecture, resource management, security, and challenges,” ACM Computing Surveys, vol. 55, no. 1, pp. 1–46, Nov. 2021, doi: 10.1145/3485129.

[61] R. A. Dziyauddin et al., “Computation offloading and content caching and delivery in vehicular edge network: A survey,” Computer Networks, vol. 197, p. 108228, Oct. 2021, doi: 10.1016/j.comnet.2021.108228.

[62] Z. Zhou, X. Chen, E. Li, L. Zeng, K. Luo, and J. Zhang, “Edge intelligence: Paving the last mile of artificial intelligence with edge computing,” Proceedings of the IEEE, vol. 107, no. 8, pp. 1738–1762, Aug. 2019, doi: 10.1109/jproc.2019.2918951.

[63] J. Chen and X. Ran, “Deep learning with edge computing: A review,” Proceedings of the IEEE, vol. 107, no. 8, pp. 1655–1674, Aug. 2019, doi: 10.1109/jproc.2019.2921977.

[64] ETSI, “Multi-access edge computing (MEC); framework and reference architecture,” European Telecommunications Standards Institute, ETSI GS MEC 003 V4.1.1, 2025. Available: https://www.etsi.org/deliver/etsi_gs/mec/001_099/003/04.01.01_60/gs_mec003v040101p.pdf

[65] C. J. C. H. Watkins and P. Dayan, “Q-learning,” Machine Learning, vol. 8, no. 3–4, pp. 279–292, May 1992, doi: 10.1007/bf00992698.

[66] V. Mnih et al., “Human-level control through deep reinforcement learning,” Nature, vol. 518, no. 7540, pp. 529–533, Feb. 2015, doi: 10.1038/nature14236.

[67] J. Schulman, S. Levine, P. Moritz, M. I. Jordan, and P. Abbeel, “Trust region policy optimization.” arXiv, 2015. doi: 10.48550/ARXIV.1502.05477.

[68] T. P. Lillicrap et al., “Continuous control with deep reinforcement learning.” arXiv, 2015. doi: 10.48550/ARXIV.1509.02971.

[69] T. Haarnoja, A. Zhou, P. Abbeel, and S. Levine, “Soft actor-critic: Off-policy maximum entropy deep reinforcement learning with a stochastic actor.” arXiv, 2018. doi: 10.48550/ARXIV.1801.01290.

[70] J. Foerster, G. Farquhar, T. Afouras, N. Nardelli, and S. Whiteson, “Counterfactual multi-agent policy gradients,” Proceedings of the AAAI Conference on Artificial Intelligence, vol. 32, no. 1, Apr. 2018, doi: 10.1609/aaai.v32i1.11794.

[71] R. Lowe, Y. Wu, A. Tamar, J. Harb, P. Abbeel, and I. Mordatch, “Multi-agent actor-critic for mixed cooperative-competitive environments.” arXiv, 2017. doi: 10.48550/ARXIV.1706.02275.

[72] P. Sunehag et al., “Value-decomposition networks for cooperative multi-agent learning.” arXiv, 2017. doi: 10.48550/ARXIV.1706.05296.

[73] T. Rashid, M. Samvelyan, C. S. de Witt, G. Farquhar, J. Foerster, and S. Whiteson, “QMIX: Monotonic value function factorisation for deep multi-agent reinforcement learning.” arXiv, 2018. doi: 10.48550/ARXIV.1803.11485.

[74] M. Hessel et al., “Rainbow: Combining improvements in deep reinforcement learning.” arXiv, 2017. doi: 10.48550/ARXIV.1710.02298.

[75] P. Hernandez-Leal, B. Kartal, and M. E. Taylor, “A survey and critique of multiagent deep reinforcement learning,” Autonomous Agents and Multi-Agent Systems, vol. 33, no. 6, pp. 750–797, Oct. 2019, doi: 10.1007/s10458-019-09421-1.

[76] G. Papoudakis, F. Christianos, L. Schäfer, and S. V. Albrecht, “Benchmarking multi-agent deep reinforcement learning algorithms in cooperative tasks.” arXiv, 2020. doi: 10.48550/ARXIV.2006.07869.

[77] P. Henderson, R. Islam, P. Bachman, J. Pineau, D. Precup, and D. Meger, “Deep reinforcement learning that matters,” Proceedings of the AAAI Conference on Artificial Intelligence, vol. 32, no. 1, Apr. 2018, doi: 10.1609/aaai.v32i1.11694.

[78] R. Agarwal, M. Schwarzer, P. S. Castro, A. Courville, and M. G. Bellemare, “Deep reinforcement learning at the edge of the statistical precipice.” arXiv, 2021. doi: 10.48550/ARXIV.2108.13264.

[79] G. Dulac-Arnold et al., “Challenges of real-world reinforcement learning: Definitions, benchmarks and analysis,” Machine Learning, vol. 110, no. 9, pp. 2419–2468, Apr. 2021, doi: 10.1007/s10994-021-05961-4.

[80] B. Efron, “Bootstrap methods: Another look at the jackknife,” The Annals of Statistics, vol. 7, no. 1, Jan. 1979, doi: 10.1214/aos/1176344552.

[81] R. L. Wasserstein and N. A. Lazar, “The ASA statement on p-values: Context, process, and purpose,” The American Statistician, vol. 70, no. 2, pp. 129–133, Apr. 2016, doi: 10.1080/00031305.2016.1154108.

[82] D. Lakens, A. M. Scheel, and P. M. Isager, “Equivalence testing for psychological research: A tutorial,” Advances in Methods and Practices in Psychological Science, vol. 1, no. 2, pp. 259–269, 2018, doi: 10.1177/2515245918770963.

[83] Y. Benjamini and Y. Hochberg, “Controlling the false discovery rate: A practical and powerful approach to multiple testing,” Journal of the Royal Statistical Society Series B: Statistical Methodology, vol. 57, no. 1, pp. 289–300, Jan. 1995, doi: 10.1111/j.2517-6161.1995.tb02031.x.

[84] R. Dror, G. Baumer, S. Shlomov, and R. Reichart, “The hitchhiker’s guide to testing statistical significance in natural language processing,” in Proceedings of the 56th annual meeting of the association for computational linguistics (volume 1: Long papers), Association for Computational Linguistics, 2018, pp. 1383–1392. doi: 10.18653/v1/p18-1128.

[85] D. Sculley et al., “Hidden technical debt in machine learning systems,” in Advances in neural information processing systems 28, Neural Information Processing Systems Foundation, 2015. Available: https://proceedings.neurips.cc/paper/2015/hash/86df7dcfd896fcaf2674f757a2463eba-Abstract.html

[86] M. D. Wilkinson et al., “The FAIR guiding principles for scientific data management and stewardship,” Scientific Data, vol. 3, no. 1, Mar. 2016, doi: 10.1038/sdata.2016.18.

[87] T. Gebru et al., “Datasheets for datasets,” Communications of the ACM, vol. 64, no. 12, pp. 86–92, Nov. 2021, doi: 10.1145/3458723.

[88] M. Mitchell et al., “Model cards for model reporting,” in Proceedings of the conference on fairness, accountability, and transparency, in FAT* ’19. ACM, Jan. 2019, pp. 220–229. doi: 10.1145/3287560.3287596.

[89] B. J. Heil, M. M. Hoffman, F. Markowetz, S.-I. Lee, C. S. Greene, and S. C. Hicks, “Reproducibility standards for machine learning in the life sciences,” Nature Methods, vol. 18, no. 10, pp. 1132–1135, Aug. 2021, doi: 10.1038/s41592-021-01256-7.

[90] T. Lebo, S. Sahoo, and D. McGuinness, PROV-o: The PROV ontology. World Wide Web Consortium, 2013. Available: https://www.w3.org/TR/prov-o/

[91] M. T. Ribeiro, S. Singh, and C. Guestrin, “‘Why should i trust you?’: Explaining the predictions of any classifier,” in Proceedings of the 22nd ACM SIGKDD international conference on knowledge discovery and data mining, in KDD ’16. ACM, Aug. 2016, pp. 1135–1144. doi: 10.1145/2939672.2939778.

[92] S. Lundberg and S.-I. Lee, “A unified approach to interpreting model predictions.” arXiv, 2017. doi: 10.48550/ARXIV.1705.07874.

[93] M. Sundararajan, A. Taly, and Q. Yan, “Axiomatic attribution for deep networks.” arXiv, 2017. doi: 10.48550/ARXIV.1703.01365.

[94] J. Adebayo, J. Gilmer, M. Muelly, I. Goodfellow, M. Hardt, and B. Kim, “Sanity checks for saliency maps.” arXiv, 2018. doi: 10.48550/ARXIV.1810.03292.

[95] Z. C. Lipton, “The mythos of model interpretability,” Communications of the ACM, vol. 61, no. 10, pp. 36–43, 2018, doi: 10.1145/3233231.

[96] R. Guidotti, A. Monreale, S. Ruggieri, F. Turini, F. Giannotti, and D. Pedreschi, “A survey of methods for explaining black box models,” ACM Computing Surveys, vol. 51, no. 5, pp. 1–42, Aug. 2018, doi: 10.1145/3236009.

[97] C. Rudin, “Stop explaining black box machine learning models for high stakes decisions and use interpretable models instead,” Nature Machine Intelligence, vol. 1, no. 5, pp. 206–215, May 2019, doi: 10.1038/s42256-019-0048-x.

[98] A. Jacovi and Y. Goldberg, “Towards faithfully interpretable NLP systems: How should we define and evaluate faithfulness?” in Proceedings of the 58th annual meeting of the association for computational linguistics, Association for Computational Linguistics, 2020, pp. 4198–4205. doi: 10.18653/v1/2020.acl-main.386.

[99] F. Doshi-Velez and B. Kim, “Towards a rigorous science of interpretable machine learning.” arXiv, 2017. doi: 10.48550/ARXIV.1702.08608.

[100] C.-K. Yeh, C.-Y. Hsieh, A. S. Suggala, D. I. Inouye, and P. Ravikumar, “On the (in)fidelity and sensitivity for explanations.” arXiv, 2019. doi: 10.48550/ARXIV.1901.09392.

## Evidence map for final typesetting

| Manuscript item | Source artifact suitable for appendix/figure generation |
|---|---|
| Held-out paired latency effect | `docs/evaluation/capacity_confirmatory_results_20260728.md` and `capacity_confirmatory_report_20260728.md` |
| Pilot arm descriptives | `docs/dissertation_appendices/tables/vec_capacity_squeeze_pilot_arm_descriptives.tex` |
| Latency by seed | `docs/dissertation_appendices/figures/capacity_latency_by_seed.svg` |
| Deadline success by seed | `docs/dissertation_appendices/figures/capacity_deadline_success_by_seed.svg` |
| Exact action invariance | `docs/dissertation_appendices/figures/capacity_offload_invariance.svg` |
| Tail mechanism | `docs/evaluation/latency_tail_analysis_20260728.md` |
| Vehicle partition | `docs/evaluation/offload_partition_analysis_20260729.md` |
| Prediction/refutation chain | `docs/evaluation/ceiling_law_prediction_results_20260729.md`, `actor_crossover_results_20260730.md`, `onset_scaling_prediction_results_20260730.md` |
| Bus descriptive transfer | `docs/evaluation/bbus_sparse64_clean_rerun_results_20260730.md` |

The final typeset dissertation should use no more figures than the argument needs. A strong core
set is: the paired confirmatory latency plot, flat deadline plot, action-invariance plot, a compact
tail/partition table, and one evidence-chain architecture figure. Every producer-derived figure
must carry the Putra environment, trace and SUMO citations required by
`docs/producer_citation_requirements.md`.

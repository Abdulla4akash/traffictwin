# Meta Muse Spark 1.2 — Publication Direction
## TrafficTwin Publishable Research Directions

**Author:** Meta Muse Spark 1.2 (Muse Spark 1.2 powered by Meta)
**Date:** 2026-08-06 (updated 2026-08-06 for v0.7 line)
**Source snapshot:** TrafficTwin v0.6.0 baseline + v0.7.0 `main` (49be6a2) — 12/12 VEC accepted (Gate G closed), 39/39 v0.5 catalogue implemented
**Canonical spec:** [traffictwin/docs/traffictwin-design-v0_6.md](/traffictwin/docs/traffictwin-design-v0_6.md) — supersedes v0.5, v0.5 remains implemented baseline
**Implementation truth:** [traffictwin/docs/implementation-status.md](/traffictwin/docs/implementation-status.md) + [traffictwin/docs/assumption-register.md](/traffictwin/docs/assumption-register.md) (234 rows) + [traffictwin/AGENTS.md](/traffictwin/AGENTS.md)
**Reading completed:** Full design (§1-16 + Appendices), README, AGENTS.md, CHANGELOG, architecture, open-questions, implementation-status, assumption-register
**Author stance:** Muse Spark 1.2 — reasoning trace preserved in §0, publication directions in §1-7, non-publishable boundaries in §8

> This file is the requested thinking artifact. It derives every direction from *existing* tested code, generated contracts, and accepted VEC audit evidence — not from email claims or inferred schemas. Any direction that would require raw checkpoint redistribution, per-task energy, eventual physical completion, confirmed transfer, anonymity, or a project licence is marked **blocked** until separate evidence/authority exists.

---

## 0. How Muse Spark 1.2 Read TrafficTwin (Reasoning Trace)

### 0.1 What the system actually is
- **Import-first research software prototype** for reproducible urban traffic / vehicular edge-computing what-if analysis. Guaranteed workflow: `seed YAML → bundle → validation → CanonicalTables → MetricCollection → EvidencePack → DiagnosticReport → ProvenanceTrace → Reports` — see [traffictwin/docs/architecture.md](/traffictwin/docs/architecture.md:42) and [traffictwin/README.md](/traffictwin/README.md:3).
- **Not** a simulator, not a live Manchester twin, not a job scheduler. Direct launch is a *conditional adapter capability*, not a default — generic/SUMO `direct_launch=false` retained; only the exact VEC evaluator path is conditional via request-specific preflight ([traffictwin/docs/traffictwin-design-v0_6.md:67-68](/traffictwin/docs/traffictwin-design-v0_6.md:67), [traffictwin/AGENTS.md:65-68](/traffictwin/AGENTS.md:65)).
- **Determinism + provenance + permission-awareness** are the three hard invariants. Every metric is computed by deterministic library code, every diagnostic hypothesis is a deterministic rule over `EvidencePack`, every archive is permission-gated and byte-identical ([traffictwin/AGENTS.md:19-22](/traffictwin/AGENTS.md:19)).

### 0.2 What counts as evidence
- **VEC-01 audit** hashed 154 files (889 MB) at pinned commits `vec_env@068b4ea3` + `tos-data@f6c67acb`, reconciled all 5 trace/occupancy pairs (17.2M cells), 60 per-step + 6 per-task + 4 tripinfo, 2 checkpoints — see [traffictwin/docs/implementation-status.md:58-78](/traffictwin/docs/implementation-status.md:58). This is the *only* trusted source for schemas, units, joins, and permission scope.
- **VEC-08** reproduced the pinned `ukfleettrain-mappo_we_uk2030_fs0` weekend protocol-seed case twice, exact for scientific arrays, 61 exact + 2 float32-reduction checks (energy `6.03e-8 J`, 9,536 latency sums ≤ `0.0039 ms`) — scoped to JAX 0.4.30 CPU, not portable ([traffictwin/docs/implementation-status.md:284-309](/traffictwin/docs/implementation-status.md:284)).
- **Gate G closed** at 1,110 tests, Ruff + strict mypy (530 files), 1,420 doc links resolved, byte-identical 27-member VEC-12 ZIP rebuilt — see [traffictwin/docs/implementation-status.md:217-223](/traffictwin/docs/implementation-status.md:217).

### 0.3 Hard boundaries that make or break publishability
From assumption-register + design §3 + AGENTS.md § “Non-Negotiable Constraints”:

| Boundary (publishable only if respected) | Why it matters to reviewers |
|---|---|
| **Pseudonymisation ≠ anonymity** — VEC-11 has 3 rounded rows, labels must say so ([traffictwin/docs/assumption-register.md:113](/traffictwin/docs/assumption-register.md:113)) | Privacy claim overclaim = desk reject |
| **Permission is narrow** — sanitised samples + aggregates only, with `vec_env`+`tos-data` citation, engine `v2_post_nrsus_fix`, `_s102_best_of_seeds` label; no checkpoint/raw redistribution, no project licence yet ([traffictwin/docs/assumption-register.md:112](/traffictwin/docs/assumption-register.md:112), [traffictwin/docs/traffictwin-design-v0_6.md:387-390](/traffictwin/docs/traffictwin-design-v0_6.md:387)) | Licence/permission inference = legal/ethics reject |
| **Per-task energy & eventual completion unavailable** — only deadline success `task_met` + aggregate energy ([traffictwin/docs/assumption-register.md:48](/traffictwin/docs/assumption-register.md:48)) | Inventing joules/task = scientific misconduct |
| **`veh_best_rsu/_v2v = -1` means no eligible target, not failure**; action ≠ transfer proof ([traffictwin/docs/assumption-register.md:47](/traffictwin/docs/assumption-register.md:47)) | Misreading VEC semantics = method reject |
| **Occupancy span = identity** only inside `t_enter ≤ t ≤ t_exit`; slot alone is time-local ([traffictwin/docs/assumption-register.md:46](/traffictwin/docs/assumption-register.md:46)) | Slot-as-vehicle = join bug |
| **No causality, no protected-attribute fairness, no link-quality** from current fields ([traffictwin/docs/assumption-register.md:34](/traffictwin/docs/assumption-register.md:34)) | Causal/fairness overclaim = review failure |
| **Checksums prove identity, not truth; RO-Crate/VEC-12 prove no new rights** ([traffictwin/docs/assumption-register.md:28](/traffictwin/docs/assumption-register.md:28), [traffictwin/docs/assumption-register.md:125](/traffictwin/docs/assumption-register.md:125)) | Conflating integrity with validity = scope error |

Any direction below that violates a row in this table is marked **not publishable** in §8.

### 0.4 What is already strong (no new experiment needed)
- 39 v0.5 capabilities with deterministic contracts, golden tests, CLI/UI, docs, provenance, reports — all `implemented` within v1 scope ([traffictwin/docs/implementation-status.md:13-16](/traffictwin/docs/implementation-status.md:13)).
- STA-01..05, PRO-01..03, EXP-01..03, REP-01..05, OPS-01..05 complete and tested.
- VEC-01..12 accepted with *explicit unavailable fields* — this precision is itself a publishable contribution (how to report negative capability).

---

## 1. Direction A — Strongest First Paper: The Import-First Reproducibility Platform

**Provisional title:** *TrafficTwin: An Import-First, Deterministic, Provenance-Complete Platform for Reproducible Urban Traffic and Vehicular Edge What-If Analysis*

**Venue family:** SoftwareX / Journal of Open Source Software (JOSS) / Empirical Software Engineering (tool) / Scientific Data (software descriptor). This is the safest first submission — it needs no new VEC experiment, only documentation of what is already built.

**Research question (RQ-A):** Can a research-data pipeline guarantee deterministic, import-first reuse, complete provenance, and permission-aware archival without requiring a live simulator, while making unsupported capabilities *visibly* unavailable rather than silently simulated?

**Why TrafficTwin enables it now:**
- **Implemented pipeline:** seed YAML → manifest-driven CSV/gzip-CSV/Parquet ingestion (ING-01..05) → half-open window metrics (MET-01, 60 metrics) → EvidencePack → R0-R8 deterministic hypotheses (DIA-01..07) → provenance (PRO-01..03) → reports/search/RO-Crate.
- **Evidence quality:** 1,110 tests, strict mypy 530 files, Ruff 546 files, 1,420 doc links, byte-identical VEC-12 ZIP, content-addressed Parquet cache with re-fingerprint-before-hit, 5-version transactional migrations.
- **Distinctive design choices:** `partial_valid` with reason codes, `unknown` capability state, path-redacted RO-Crate `embed/reference/exclude`, bounded provenance graphs, typed report-claim completeness, non-additive percentile handling.

**Contribution claims (defensible):**
1. A versioned contract pattern for making *absence* of evidence machine-readable (reason codes, not nulls).
2. Content-addressed canonical-cache with fail-closed semantics outside raw bundles (OPS-02/ADR-045) — derived tables are disposable, raw is authoritative.
3. Permission-aware deterministic RO-Crate (OPS-04/ADR-047) with explicit licence/permission basis.
4. Closed external-source interface (OPS-05/ADR-048) that refuses ordinal ranking of `partial_canonical` vs `aggregate_summary`.

**Method section already written:** `docs/architecture.md`, `docs/full_product_guide.md`, generated contracts under `docs/reference/generated/`, ADRs 011-050.

**Evaluation for the paper (no new data collection):**
- Synthetic portfolio stress test (5 families × 3 policies × 3 seeds, S5/S6 held-out already in repo) — show metric/diagnostic stability.
- Mutation + measurement-imperfection robustness (EXP-02/EXP-03) — report degradation curves.
- Performance: 20K-task cache benchmark + 75K-task streaming benchmark already documented (docs/decisions/ADR-045, ADR-015).
- Reproducibility: rerun `traffictwin synthetic verify` + `bundle validate` + `metrics compute` + `evidence build` on CI.

**What to *add* for publication (small):**
- JOSS/software paper requires archived release (Zenodo DOI) + CITATION.cff — both already present, needs version tag.
- Add a one-figure “capability truth table” showing which of the 51 capabilities are `true/false/unknown` and why visible `unknown` is a feature.
- No new Randy data needed; keep Netlify synthetic demo as the public artifact, cite VEC work as *separate* pending paper (Direction B).

**Risk if ignored:** Claiming SUMO launch, real-Manchester calibration, or per-task energy would make this paper desk-rejected. Keep §8 exclusions visible.

**Thesis mapping:** Chapters 1-3 (platform + methodology). Advises Dr. Sandra on C1+C2 framing: this paper is C1 (platform).

---

## 2. Direction B — Second Paper: Evidence-Gated Reproduction of a Closed RL/VEC Evaluator

**Provisional title:** *Reproducing a Closed Vehicular Edge Evaluator Without Trusting the Email: Evidence Gates, Occupancy-Bounded Identity, and a Scoped CPU Tolerance*

**Venue family:** ESEM / MSR / ICSE-SEIP / Journal of Systems and Software (reproducibility) / Scientific Reports. Novelty is *method*, not RL performance.

**Research questions (from spec §4.2):**
- **RQ8** — Can a pinned external evaluator be run through a safe typed contract while keeping import-only operation independent?
- **RQ9** — Can occupancy spans reconcile padded slots with persistent SUMO vehicles?
- **RQ11** — Can a useful dissertation fixture be produced within narrow permission/citation/seed constraints?

**Why publishable:**
- **VEC-01..12 closed** with auditable hashes, not claims. The 12-gate story (A→G) is itself a replicable protocol for reproducing private simulators without forking them.
- **Scoped success with honest failure:** VEC-08 passes only for one protocol-seed case on JAX 0.4.30 CPU; cross-platform/generalisation is explicitly *not* claimed — reviewers reward this precision.
- **Identity innovation:** Slot reuse observed (slot disappearance/reuse), solved by inclusive `OccupancySpan` with exact mask reconstruction (17.2M cells, zero gaps) — see [traffictwin/docs/implementation-status.md:115-118](/traffictwin/docs/implementation-status.md:115).

**Contribution claims:**
1. A 7-gate evidence-gating pattern (snapshot → contract → joins → preprocessing → runner → reproduction → publication) that keeps `import` usable when `execute` is blocked.
2. Occupancy-bounded identity as a reusable primitive for padded-simulator traces (5 trace/occupancy pairs validated, 45,299 spans).
3. Target semantics disambiguation: `veh_action` (policy choice) vs `veh_best_* = -1` (no eligible target) — prevents 1,907 misclassifications across 46.8M tasks ([traffictwin/docs/implementation-status.md:135-138](/traffictwin/docs/implementation-status.md:135)).
4. VEC-11 minimal sanitised fixture (3 rows + 26 aggregates) as a permission-minimal disclosure pattern — pseudonymised *and labelled not anonymous*.

**Evaluation:**
- Primary: VEC-08 two-run exactness + pinned-source comparison (already accepted, scripts `scripts/verify_vec_reproduction.py` bonded to `docs/reference/generated/vec_reproduction_report.json`).
- Secondary: VEC-03 coverage proof (5 pairs), VEC-04 reconciliation (46.8M tasks), VEC-05 trip join (42,881/43,767 matched, 872 boundary-censored, 14 incident-missing) — all quantified, not anecdotal.
- Negative results: per-task energy, eventual completion, transfer confirmation remain unavailable — publish the *absence table* (VEC-09: 18 admitted / 8 unavailable, R1/R2/R7 blocked).

**What to add (moderate):**
- One additional independent reproduction on a second CPU host (same JAX version) to upgrade “two runs on one host” to “two hosts” — strengthens tolerance claim without claiming GPU portability.
- Publish VEC-12 ZIP as supplementary material (27 members, checksums, offline verifier) — allows reviewers to run `verify` without extraction.
- Ethics/licence appendix: reproduce Randy’s 21 July permission text verbatim + VEC-11 manifest, state “no project licence selected”.

**What NOT to claim:** No claim that SUMO FCD/network pairing is authenticated (VEC-06 limitation), no claim that generated grid sites are real RSUs, no claim that VEC-12 proves scientific truth.

**Thesis mapping:** Chapter 4 (case study). RQ8-11 directly.

---

## 3. Direction C — Provenance, Contribution Ledgers, and Publication Governance

**Provisional title:** *From Bundle Fingerprint to One-Page Supervisor Summary: Complete, Path-Safe Provenance for Deterministic Research Data Pipelines*

**Venue family:** IPAW / TaPP (provenance) / J. Data and Information Quality / Empirical SE (provenance of ML/RL pipelines).

**Research question:** Can every derived metric, diagnostic rule, window slice, and report claim be traced to exact source rows with bounded disclosure and without recomputing science in the provenance layer?

**Enabled by:**
- **PRO-01** — closed arithmetic registry (counts/sums/means/rates) with reconciled signed terms; non-additive aggregates (percentiles, Jain, etc.) expose eligible lineage with null weights and mandatory non-causality statement — [traffictwin/docs/architecture.md:289-296](/traffictwin/docs/architecture.md:289).
- **PRO-02** — root-centred BFS, default/hard node/edge bounds, stable path-safe IDs, DOT/GraphML exports, exact truncation counts (ADR-034).
- **PRO-03** — typed report-claim completeness: denominator = explicit template claims, unavailable claims retained, named exclusions, null for zero-claim reports (ADR-035).
- **PRO-Explorer UI** — read-only traces metric → source row where available.
- **OPS-04** — RO-Crate with CFF, `embed/reference/exclude` per raw item, fixed ZIP timestamps/modes, bounded verifier.

**Contribution claims:**
1. **Reconciled difference provenance** (PRO-01) — baseline vs variation delta decomposes into per-row signed terms only for admitted additive formulas; other metrics keep lineage but refuse weight fabrication — prevents causal overclaim.
2. **Path-safe + structure-only disclosure** — deterministic redaction without extra anonymity claim.
3. **Report-claim provenance completeness** — a completeness score that *cannot* be inflated by omitting unavailable claims.
4. **Governance binding** — every RO-Crate / VEC-12 artifact binds source commits, report fingerprints, permission basis, and explicit exclusions — checksums are identity, not validity.

**Evaluation:**
- Demonstrate PRO-01 reconciliation on the 20 metric-state deltas between baseline and stressed-demand synthetic bundles (already computable).
- Demonstrate PRO-02 truncation behaviour on a 20K-task bundle with varying node limits; show retained/omitted counts.
- Demonstrate PRO-03 on three report templates (run, compare, full) — show denominator, class counts, exclusions.
- Compare before/after path redaction: show absolute host paths never leak.

**Publishability boost:** This is the most *reusable* contribution — other groups can adopt PRO-01..03 even without VEC data. Frame as “provenance for deterministic file-bundle pipelines”.

**Small add:** One figure comparing PRO-01 “reconciled arithmetic” vs “naïve row-matching” on a mean-rate metric to show why row-ID matching across runs is wrong (ADR-033).

---

## 4. Direction D — Statistical Rigor: Paired Common-Seed Studies, Equivalence, and Regression Gates

**Provisional title:** *Beyond p < 0.05: Paired Common-Seed Bootstrap, Winner Maps, TOST Equivalence, and Golden-Gate Regressions for Simulation-Based What-If Studies*

**Venue family:** ESEM / TSE / Empirical SE / Simulation (SCS). Directly leverages STA-01..05 which are already implemented, tested, and documented — no simulator needed.

**Research question:** How should small-sample, common-seed simulation experiments report effect, uncertainty, ranking, equivalence, and regression without relabelling non-significance as “no difference”?

**Enabled by:**
- **STA-01** — predeclared mean variation-minus-baseline effect, deterministic paired percentile bootstrap, exact/seeded sign-flip test, Cohen’s dz + matched-pairs rank-biserial — [traffictwin/docs/architecture.md:190-207](/traffictwin/docs/architecture.md:190).
- **STA-02** — per-family complete-seed winner map + joint paired-seed bootstrap for mean/rank uncertainty, with explicit tie/missingness handling (ADR-029).
- **STA-03** — paired TOST over STA-01 cohort with mandatory margin, basis, justification, reference (ADR-030) — refuses to infer equivalence from STA-01 non-significance.
- **STA-04** — versioned golden contracts, `max(abs, rel×|expected|)` tolerance, `candidate` vs `approved`, `pass/fail/unavailable` trichotomy (ADR-031).
- **STA-05** — prospective power planning (target effect + variance + alpha → smallest n), with small-sample/synthetic/provisional labels (ADR-032).

**Contribution claims:**
1. A *coherent chain* where STA-01 pairs → STA-03 reuses that cohort → STA-04 gates regressions → STA-05 plans next study — all bound by common-seed compatibility auditing.
2. **Winner-map discipline:** incompatible seed families excluded, not ranked with warnings — prevents mixed-unit ranking.
3. **Equivalence discipline:** zero-variance cohort returns `degenerate` with no p-value, failed TOST is `equivalence_not_demonstrated` not “different” — prevents misinterpretation.
4. **Regression-gate trichotomy:** `unavailable` (missing context) vs `failed` (out-of-tolerance) — prevents “missing = pass”.

**Evaluation (synthetic, rigorous):**
- Use the fixed 5-family × 3-policy × 3-seed synthetic portfolio (already in repo) plus held-out S5/S6 — run STA-01..03 end-to-end, report bootstrap intervals vs sign-flip p-values, report STA-03 with a predeclared margin (e.g. `task.completion.rate` absolute 0.02) vs without.
- Negative control: shuffle seed pairing → show audit correctly retains exclusions and returns `insufficient`.
- STA-04: promote a candidate golden to approved, then perturb one expected value by `1.1×` tolerance → show `failed` vs `unavailable` contrast.
- STA-05: plan n for a synthetic effect/variance, then simulate draws at that n → show empirical power vs normal approximation, with caveat that STA-05 is *approximation*, not sign-flip exact.

**Thesis mapping:** Chapter 5 (evaluation methodology). Answers open question in [traffictwin/docs/open-questions.md:1-6](/traffictwin/docs/open-questions.md:1) about R1-R5 thresholds: propose to *predeclare* them via STA.

**Risk:** Do not claim synthetic effects generalise to Manchester deployment. Label every synthetic result `synthetic=true` per STA constraints.

---

## 5. Direction E — Robustness & Sensitivity Without New Data

**Provisional title:** *How Brittle Is Your Conclusion? Deterministic Mutations, Bounded Measurement Noise, and Threshold Stability for Simulation Claims*

**Venue family:** SEAMS / ICSE-SEIP (robustness) / Reliability Engineering / Transportation Research Part C (sensitivity).

**Research question:** For a deterministic pipeline, how sensitive are metric values and diagnostic hypotheses to small, seeded perturbations in rows, timestamps, infrastructure, observations, and thresholds?

**Enabled by:**
- **EXP-02** — row-dropout / timestamp-jitter / RSU-removal over copied validated synthetic/evaluation bundles, SHA-256-derived choices, exact bounded change ledgers, transactional publication (ADR-037); at most 20K changed rows or request rejected.
- **EXP-03** — bounded-uniform noise over closed generated-observation fields + hash-ranked exact dropout, typed manifest audit, synthetic/not-calibrated labels (ADR-038).
- **DIA-05 / DIA-06** — verified nearest-flip for single-boundary R5/R7/R8 thresholds + complete-grid threshold sweep retaining every point/status (ADR-025, ADR-026).
- **EXP-01** — bounded parameter sweeps (≤4 axes, ≤16 values, ≤256 points, ≤16 response metrics) with `not_executed` for external requests.

**Contribution claims:**
1. **Deterministic, replayable perturbations** derived from SHA-256 + stable row identity + declared seed — not `numpy.random` global state — gives byte-for-byte replay.
2. **Ledger-bounded provenance:** every admitted mutation publishes the exact row/file ledger; large requests fail closed instead of truncating.
3. **Threshold stability as evidence:** DIA-06 retains *every* grid point (not just flips) and separates sampled transitions from exact DIA-05 flips — shows instability that single-threshold papers hide.

**Evaluation (already runnable):**
- Take `baseline` + `stressed_demand` synthetic bundles → apply EXP-02 dropout at 1%, 5%, 10% with 3 seeds → report metric delta distributions + R-hypothesis stability (e.g. does R5 drift detection survive 5% dropout?).
- Apply EXP-03 bounded noise (±5% of field range) to generated observation fields → report which metrics (P50 latency vs completion rate) are fragile.
- Sweep R5/R7 threshold across declared range (DIA-06) → plot full status trajectory, identify narrow instability bands where conclusion flips with ε.
- Publish the fault matrix already in repo: severity × seed variants with false-positive/specificity reports (see architecture “Advanced Research Tools”).

**What to add (small):** Calibrate one EXP-02 severity ladder to a *defensible* external reference (e.g. “1% row dropout ≈ 1% detector miss rate reported in [cite]”) — without this, EXP-02 remains a software fixture, not a real-error model (see ADR-038).

---

## 6. Direction F — Diagnostic Hypotheses as Deterministic Artifacts (Not Causal Claims)

**Provisional title:** *From Metrics to Hypotheses — Without an LLM: Closed Declarative Rules, Temporal Recovery, and Typed Cross-Rule Reasoning over EvidencePacks*

**Venue family:** SEAMS / ICAC / Transportation Research (intelligent-vehicle diagnostics) / Explainable SE.

**Research question:** Can diagnostic hypotheses be made inspectable, versioned, and sensitivity-tested while *never* using an LLM to calculate, infer, or recommend — and while marking every missing-evidence gap explicitly?

**Enabled by:**
- **R0-R8 + declarative layer** — trusted-local static YAML grammar with flat `all/any`, finite thresholds, exact booleans, closed identifier boundary, fingerprinted definitions (ADR-023); R7 = tier-gap or RSU-completion, R8 = per-completed-task energy (requires TaskEnergyContract).
- **R6 temporal** — WindowedMetricSeries → typed temporal projection with gaps preserved, declared event mapped to containing half-open window, consecutive baseline/degradation/recovery runs (ADR-022).
- **DIA-05/06/07** — nearest-flip verification, complete-grid threshold sweep (session-only), additive cross-rule policy (R1/R2 conflict, R1/R4 corroboration, R0 blocker precedence 100 vs 50).

**Contribution claims:**
1. **LLM-free guarantee** — renderer copies EvidencePack fields only; AGENTS.md forbids LLM metric/diagnostic calculation — a verifiable negative claim.
2. **Provisional-threshold discipline:** R6/R7/R8 defaults are labelled synthetic-development values; real use requires predeclared calibration (open question in [traffictwin/docs/open-questions.md:1](/traffictwin/docs/open-questions.md:1)).
3. **Typed cross-rule reasoning without confidence tampering** — DIA-07 never changes status/confidence, retains every original RuleResult, reports suppressed IDs separately.

**Evaluation:**
- Run R0-R8 on synthetic portfolio (fault-injected + clean) → report confusion matrix with `insufficient_evidence` / `unavailable` rates — show that single-run R3 correctly returns `insufficient` (experiment evidence needed).
- Demonstrate DIA-05 nearest-flip on one R5 false-positive → show exact threshold distance and ordinary-engine verification.
- Demonstrate DIA-07 on co-triggered R1+R2 vs solo R1 → show conflict activation only on shared evidence key.
- Compare TrafficTwin rule report vs LLM-summary baseline (if allowed): show LLM hallucinates cause, TrafficTwin restates evidence keys.

**Small add:** Predeclare one R6 calibration protocol (window width 60s, metric `task.completion.rate`, event = incident start) and run it on held-out S5/S6 — without this, R6 remains provisional (VEC-09 keeps R6 conditional).

---

## 7. Direction G — Synthetic Scenario Engineering & Infrastructure What-Ifs

**Provisional title:** *S5 Stadium Siting, S6 Road Clearing, and Controlled SUMO Smoke: Synthetic Fixtures as a What-If Authoring Testbed*

**Venue family:** SUMO Conference / IEEE ITSC / Transportation Research Part C (scenario engineering).

**Research question:** Can a scenario authoring layer that writes only deterministic synthetic bundles — not simulator inputs — still exercise a full what-if pipeline from authoring → validation → metrics → comparison → provenance → report?

**Enabled by:**
- **Incident/event round-trip authoring** (type, location, severity, timestamp, duration, lanes, demand multiplier, vehicle refs preserved — see [traffictwin/docs/assumption-register.md:171](/traffictwin/docs/assumption-register.md:171)).
- **S5/S6 presets** — synthetic stadium-event siting + road-clearing corridor, labelled `synthetic_fixture`, `environment.name: synthetic` — *not* calibrated Manchester models ([traffictwin/docs/assumption-register.md:159](/traffictwin/docs/assumption-register.md:159)).
- **Controlled SUMO execution (ADR-053)** — one closed synthetic preset (`synthetic_square_smoke`), fixed argv, foreground, byte-identical input verification, import-only via ING-01 — *not* generic launch.
- **Sweeps + mutations** over S5/S6 to generate variant bundles.

**Contribution claims:**
1. A clear separation: *authoring* (synthetic config) vs *launch* (conditional adapter) vs *import* (always available) — prevents conflating authored incident with simulated physics.
2. Round-trip preservation guarantee for authored fields — tested across config → seed → CSV → canonical.
3. Controlled SUMO workflow as a *reproducibility template* for others who want to wrap an official binary (Eclipse SUMO 1.27.1 square scenario) without claiming city-scale validity.

**Evaluation:**
- Author S5 variant with RSU siting change → generate bundle → import → compare against baseline → provenance-trace the infrastructure delta.
- Author S6 lane-closure variant → chain EXP-02 RSU-removal → show that TrafficTwin *does not* invent rerouting (task/target bytes unchanged) — honest limitation.
- Run controlled SUMO smoke preset end-to-end → show receipt hashes, validation report, and imported trip metrics vs plain ING-01 import.

**What NOT to claim:** S5/S6 are not SUMO, not Manchester, not traffic-engineering valid — they are *workflow fixtures* (assumption-register contradicted row).

---

## 8. What Is NOT Publishable Now (Would Be Desk-Rejected)

Every row below is a **standing blocker** referenced to the register/design. Citing it *as unavailable* is publishable; claiming it is available is not.

| Claim | Status | Evidence | Publishable alternative |
|---|---|---|---|
| Per-task energy (J/task), canonical energy provenance, R8 findings | **Unavailable** — no per-task joule field; only aggregate energy, R8 provisional `1.50 J/task` on synthetic data | [traffictwin/docs/assumption-register.md:48](/traffictwin/docs/assumption-register.md:48), [traffictwin/docs/assumption-register.md:178](/traffictwin/docs/assumption-register.md:178) | Publish the *absence* + TaskEnergyContract v1 design; propose future source contract |
| Eventual physical task completion, canonical completion metrics vs deadline success | **Unavailable** — `task_met` is deadline success only; VEC-09 admits `tos.task.deadline_success.*` separately | [traffictwin/docs/assumption-register.md:47](/traffictwin/docs/assumption-register.md:47), [traffictwin/docs/assumption-register.md:134](/traffictwin/docs/assumption-register.md:134) | Publish separately-named TOS metrics, keep canonical unavailable |
| Confirmed offload transfer / target execution / drop cause | **Unavailable** — action + `-1` = no eligible target, not failure; no transfer-confirmation field | [traffictwin/docs/assumption-register.md:47](/traffictwin/docs/assumption-register.md:47), [traffictwin/docs/assumption-register.md:132](/traffictwin/docs/assumption-register.md:132) | Report chosen-target join + no-target rate; label transfer proof unavailable |
| Canonical CPU utilisation / queue length from `rsu_load`/`rsu_busy_ms` | **Unavailable** — source meanings are active-task count + backlog ms | [traffictwin/docs/assumption-register.md:110](/traffictwin/docs/assumption-register.md:110) | Expose active-task/backlog as source-specific RSU pressure |
| Protected-attribute / demographic fairness | **Contradicted** — tier is compute tier, not protected | [traffictwin/docs/assumption-register.md:34](/traffictwin/docs/assumption-register.md:34) | Operational group-balance only, with `OperationalFairnessPolicy` fingerprints |
| Causal claims about vehicle/RSU/policy/incident | **Contradicted** — no counterfactual design | [traffictwin/docs/assumption-register.md:59](/traffictwin/docs/assumption-register.md:59) | Hypothesis language + PRO-01 non-causality statement |
| Anonymous dataset / public hosting of Randy-derived data | **Blocked** — pseudonymisation ≠ anonymity; no licence; public atlas requires `--confirm-publication-permission` | [traffictwin/docs/assumption-register.md:113](/traffictwin/docs/assumption-register.md:113), [traffictwin/deploy/README.md:36](/traffictwin/deploy/README.md:36) | Publish VEC-11 minimal pack + aggregate atlas *locally*; defer hosting until licence |
| Generic or asynchronous SUMO launch, training/fine-tuning, SLURM queue | **Unavailable** — only VEC evaluator (conditional) + controlled SUMO smoke preset | [traffictwin/docs/assumption-register.md:42](/traffictwin/docs/assumption-register.md:42), [traffictwin/docs/traffictwin-design-v0_6.md:342-351](/traffictwin/docs/traffictwin-design-v0_6.md:342) | Frame runner as *local reproduction*, not orchestration |
| Calibrated threshold for any R-rule | **Provisional** — defaults are synthetic-development values | [traffictwin/docs/open-questions.md:1](/traffictwin/docs/open-questions.md:1) | Require predeclared calibration study; do not cite defaults as validated |

---

## 9. Recommended Publication Sequence (Muse Spark 1.2 Strategy)

```
Step 1 — Direction A (platform paper) ──→ establishes the artifact, gets a DOI, cites 51 capabilities, no VEC controversy
          │
          ├─→ Direction C (provenance) ──→ can be parallelised; cites A
          │
Step 2 — Direction D (statistics) ──→ methodological companion; uses synthetic portfolio from A
          │
Step 3 — Direction B (VEC reproduction) ──→ strongest case study; cites A+C+D, carries VEC-12 ZIP as supplement
          │
Step 4 — Direction E + F (robustness + diagnoses) ──→ empirical extensions on top of B's admitted metrics
          │
Step 5 — Direction G (scenario fixtures) ──→ demo-track / SUMO-community paper; lowest priority unless SUMO venue targeted
```

**Why this order:** A is unblockable and gives you a citable platform DOI for B-G. B is the most novel but needs A’s credibility + careful permission wording. C/D are citable methods that strengthen B’s evaluation. E/F are incremental without B. G is nice-to-have for community engagement.

**For the dissertation:** Map A→Ch.2-3, B→Ch.4, D→Ch.5, C→Ch.6 appendix/method, E/F→Ch.7 evaluation, G→Ch.8 fixtures. Keep R1/R2/R7 blocked and R6 conditional visibly — examiners reward the honesty and it matches VEC-09 admission (18 admitted / 8 unavailable).

---

## 10. Next Actions Checklist (Owner + Evidence)

- [ ] **Licence decision** — choose project licence (open question [traffictwin/docs/open-questions.md:497](/traffictwin/docs/open-questions.md:497) implicit) — blocks public source/Docker release; keep `Licence not yet specified` until then.
- [ ] **Permission appendix** — copy Randy 21 July text + VEC-11 manifest verbatim into `docs/integration/vec_dissertation_pack.md` supplement — already built, just cite in paper.
- [ ] **Zenodo release** — tag v0.6.0, include VEC-12 ZIP + `CITATION.cff` — enables JOSS/SoftwareX citation.
- [ ] **Predeclare one threshold study** — pick R6 window 60s + metric `task.completion.rate` + event mapping, register config, run on held-out S5/S6, report before claiming any R6 finding — unblocks F.
- [ ] **Second-host CPU rerun** — repeat VEC-08 on a second host with JAX 0.4.30 to upgrade tolerance evidence from “2 runs, 1 host” to “2 hosts” — strengthens B without claiming GPU generality.
- [ ] **Synthetic calibration note** — for EXP-02 severity ladder, add one external citation grounding (e.g. detector miss-rate %) or keep labelled “fixture, not calibrated” — unblocks E’s external validity paragraph.
- [ ] **Dissertation framing meeting** — confirm with Dr. Sandra: OffloadLens vs journey-time lens vs dual-lens; C1+C2 scale; participant evaluation necessity ([traffictwin/docs/open-questions.md:409-419](/traffictwin/docs/open-questions.md:409)).

---

## 11. Reference Map (Where Every Claim Comes From)

| Claim | Source file |
|---|---|
| v0.6 design, 12 VEC capabilities, Gates A-G, 11 constraints | [traffictwin/docs/traffictwin-design-v0_6.md](/traffictwin/docs/traffictwin-design-v0_6.md) |
| Current truth: 39+12 implemented, Gate G closed, 1,110 tests | [traffictwin/docs/implementation-status.md](/traffictwin/docs/implementation-status.md:1) |
| Non-negotiable constraints, VEC-01..12 blockers | [traffictwin/AGENTS.md](/traffictwin/AGENTS.md:15) |
| Current scope, synthetic demo, CLI examples | [traffictwin/README.md](/traffictwin/README.md:35) |
| Architecture, dependency direction, STA/PRO/EXP layering | [traffictwin/docs/architecture.md](/traffictwin/docs/architecture.md:39) |
| Assumption register (permission, anonymity, slot identity, energy) | [traffictwin/docs/assumption-register.md](/traffictwin/docs/assumption-register.md) |
| Open questions (thresholds, licence, evaluation) | [traffictwin/docs/open-questions.md](/traffictwin/docs/open-questions.md) |
| VEC audit (154 files, 889 MB, 17.2M cells) | [traffictwin/docs/implementation-status.md:58](/traffictwin/docs/implementation-status.md:58) |
| VEC-11 pack (3 rows + 26 aggregates) | [traffictwin/docs/implementation-status.md:150](/traffictwin/docs/implementation-status.md:150) |
| VEC-12 ZIP (27 members, offline verifier) | [traffictwin/docs/implementation-status.md:176](/traffictwin/docs/implementation-status.md:176) |
| Controlled SUMO (ADR-053) | [traffictwin/docs/implementation-status.md:477](/traffictwin/docs/implementation-status.md:477) |
| One-click execute-and-import (ADR-052) | [traffictwin/docs/implementation-status.md:373](/traffictwin/docs/implementation-status.md:373) |
| Publication gate, TOS atlas permission flag | [traffictwin/deploy/README.md:36](/traffictwin/deploy/README.md:36) |
| v0.7 Manchester design (RQ12-16, evidence portfolio) | [traffictwin/docs/traffictwin-design-v0_7.md](/traffictwin/docs/traffictwin-design-v0_7.md:1) |
| v0.7 progress (0.7.0 line, NEXT-01..08, 4,160 tests) | [traffictwin/docs/current_progress_v0_7.md](/traffictwin/docs/current_progress_v0_7.md:1) |
| v0.7 implementation truth (MAN/UX/REL still planned) | [traffictwin/docs/implementation-status.md](/traffictwin/docs/implementation-status.md:3) |

---

## 12. Update — v0.7 Line Checked (2026-08-06, main@49be6a2)

**What was checked:** Remote `origin/main` at `49be6a2` (vs frozen `v0.6.0@1c50a25`), [traffictwin/docs/traffictwin-design-v0_7.md](/traffictwin/docs/traffictwin-design-v0_7.md:1), [traffictwin/docs/current_progress_v0_7.md](/traffictwin/docs/current_progress_v0_7.md:1) (Phase 198, 4,160 tests, 890 strict-mypy files), [traffictwin/docs/implementation-status.md](/traffictwin/docs/implementation-status.md:3) (all `MAN-01`–`MAN-11`, `UX-01`–`UX-03`, `REL-01` remain `planned`/`working_bounded`/`foundation_only` — not accepted).

**Implication:** v0.6 directions §1–§7 remain the only *accepted* publishable core. v0.7 adds three *working_bounded* directions that are publishable as method/audit papers without claiming accepted Manchester capability:

### 12.1 Direction H — Official-Source Audit (immediately publishable as data paper)
- **Phase 185** re-audited 7 DfT / National Highways / BODS sources in 412 tests; BODS general reuse/publication + API registration now documented ([traffictwin/docs/current_progress_v0_7.md:136](/traffictwin/docs/current_progress_v0_7.md:136)), but DfT raw-count hour timezone + WebTRIS clock basis remain open, retention / `VehicleRef` persistence remain open.
- **Paper angle:** `Scientific Data` / `Data in Brief` — bounded transport + immutable `ManchesterSourceSnapshot` contract with allowlisted hosts, bounded pages, secret redaction ([traffictwin/docs/traffictwin-design-v0_7.md:8](/traffictwin/docs/traffictwin-design-v0_7.md:8)). Publish freshness pitfalls as contribution.
- **RQ12:** Heterogeneous urban evidence integration without erasing boundaries.

### 12.2 Direction I — Durable Operational-History Programme (NEXT-01..06, systems paper)
- **Built:** `NEXT-01` durable workspace (74 tests), `NEXT-02` preflight + foreground 8502 profile (118 tests), `NEXT-03` hash-chained journal/UTC compaction, `NEXT-04` National Highways 6-state transitions, `NEXT-05` identifier-free BODS trends, `NEXT-06` Source Health page — all `working_bounded` per [traffictwin/docs/current_progress_v0_7.md:19](/traffictwin/docs/current_progress_v0_7.md:19), no real retention writer/policy activated.
- **Paper angle:** ESEM-SEIP on policy-gated, privacy-safe operational history for live sources — identifier-free, hash-chained, UTC-day partitions.

### 12.3 Direction J — Observed-to-SUMO Mapping Methodology (method, not results)
- **Built:** Reviewed Greater Manchester network, 305-site v1.1 candidates (131 policy / 165 ambiguous / 9 no-candidate), sealed 174-row human-review ledger (empty), 39,072-cell DfT profile candidate, calibration workflows — but 174 human decisions + calibration/uncertainty approval + gridlock-free demand missing ([traffictwin/docs/current_progress_v0_7.md:229](/traffictwin/docs/current_progress_v0_7.md:229)).
- **Paper angle:** Publish method + ledger design (how to keep mapping reviewable / refusal-explicit) — do not claim calibrated baseline. Maps to RQ13 in [traffictwin/docs/traffictwin-design-v0_7.md:136](/traffictwin/docs/traffictwin-design-v0_7.md:136).

**Updated sequence:** A (v0.6 platform) → H (v0.7 source audit) → C/D (methods) → B (VEC case study, cites A+C+D+H + VEC-12 ZIP) → I/J → E/F.

---

*Generated by **Meta Muse Spark 1.2** reading the repository as the oracle. No external paper, URL, or metric was invented. Every “publishable” direction above is implementable today; every “blocked” row is a reviewer trap to avoid. Doctoral authority for framing remains with Abdulla + Dr. Sandra; VEC permission remains with Randy. File written locally at `muse-spark-1.2-publication-direction.md` as requested.*

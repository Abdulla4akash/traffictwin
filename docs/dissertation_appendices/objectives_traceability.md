# Appendix — Objectives traceability (O1–O7)

The spine Chapter 1 §1.4 declares, Chapter 3 tests strand by strand, and Chapter 4 §4.1
revisits objective by objective. One row per objective: what it was, where it stands **today**,
the evidence that supports the claim with its repository path, and the dissertation section
that will cite it.

**Statuses are honest, including where that is unflattering.** An objective is not recorded as
achieved because it is nearly achieved. Two are deliberately not green: the Manchester
confirmatory campaign is *in execution* rather than complete, and the user-evaluation strand is
*pending ethics* with no participants and no data. Both stay that way here until a person can
record otherwise.

**Status vocabulary.**

| Status | Meaning |
|---|---|
| `implemented` | Built, tested, and exercised in the repository at this commit. |
| `implemented, exploratory evidence` | Built and run on real data, but the evidence carries `owner_approved_candidate` and no confirmatory or accepted status. |
| `in execution` | Running now; no result exists and none may be anticipated. |
| `pending ethics` | Cannot begin. Approval is a person's action and has not happened. |

Permitted labels throughout are `owner_approved_candidate`, `analyst_reviewed_candidate`, and
`descriptive_non_causal`. Nothing in this appendix is `scientifically_validated`,
`ground_truth`, `causal`, or supervisor-approved.

---

## The spine

| # | Objective (as declared in §1.4) | Status today | Evidence artifacts | Cited in |
|---|---|---|---|---|
| **O1** | Define a canonical, validated data contract for VEC simulation outputs (SUMO + TOS + synthetic) | `implemented` | `src/traffictwin/integration/tos/` (readers, validation, audit); `src/traffictwin/canonical/`; the ADR register `docs/decisions/index.md`, in particular ADR-054 through ADR-058; `docs/api_reference.md`; `docs/architecture.md` | §2.2, §2.3 |
| **O2** | Implement deterministic metrics and diagnostic rules (R0–R8) with complete provenance | `implemented` | `src/traffictwin/metrics/`; `src/traffictwin/diagnostics/` (`cross_rule.py` carries R0–R4, `sensitivity.py` carries R5/R7/R8); the `/provenance` route; `docs/advanced_research_tools.md` | §2.4, §3.2 |
| **O3** | Provide statistical comparison machinery for offloading policies (paired studies, N-way ranking, equivalence, power) | `implemented` | `src/traffictwin/experiments/statistical_study.py`, `n_way_ranking.py`, `equivalence_testing.py`, `power_analysis.py`; `docs/statistical_studies.md` records STA-01 through STA-05; the STA-02 per-algorithm checkpoint extension is recorded in `AGENTS.md` Phase 28 | §2.4, §3.4 |
| **O4** | Support what-if analysis (scenario mutations, parameter sweeps, measurement imperfections) | `implemented` | `src/traffictwin/experiments/scenario_mutation.py`, `parameter_sweep.py`, `portfolio.py`, `winner_map.py`; `src/traffictwin/synthetic/`; `docs/advanced_research_tools.md` | §2.4, §3.3 |
| **O5** | Deliver a research UX exposing the above with explicit unavailable and limits states | `implemented` | 34 `UiPage` values in `src/traffictwin/ui/labels.py` plus 5 additive routes (`/manchester`, `/match-review`, `/rsu-monitor`, `/bus-sessions`, `/campaigns`) in `src/traffictwin/ui/navigation_v07.py` — 39 routes at this commit; `docs/v07_navigation.md`; `docs/ui_design.md` | §2.3, §3.5 |
| **O6** | Evaluate on the Manchester TOS traces (descriptive case studies across the scenarios) | **pilot: `implemented, exploratory evidence`; confirmatory: `in execution`** | `docs/evaluation/capacity_squeeze_pilot_predeclaration.md`; `docs/evaluation/capacity_pilot_results_20260727.md`; `docs/evaluation/capacity_pilot_mechanism_report_20260727.md`; `docs/dissertation_appendices/figures/`; `docs/dissertation_appendices/trace_provenance.md` | §3.4 |
| **O7** | Evaluate correctness and reproducibility (tests, golden outputs, fingerprints) **and** usability (user evaluation, subject to ethics) | **correctness: `implemented`; usability: `pending ethics`** | Correctness: 3,454 tests collected across `tests/`; `tests/golden/`; the fingerprint machinery in `src/traffictwin/reporting/latex.py` and the campaign design fingerprints. Usability: `docs/evaluation/user_evaluation_instrument_draft.md`, `docs/evaluation/ethics_application_draft.md` — **unsigned, unsubmitted, zero participants** | §3.2, §3.5 |

---

## The two objectives that are not green, stated plainly

### O6 — the confirmatory campaign is running, not finished

The capacity-squeeze **pilot** is complete and its evidence is real, but it is exploratory
throughout: `owner_approved_candidate`, `descriptive_non_causal`, no significance claim, no
acceptance. Its headline finding is a **published null** — across a 3.3× capacity squeeze,
mean deadline-success rate did not fall — recorded before the evidence existed and honoured
after it did.

The **confirmatory** campaign on the held-out seed cohort is executing at the time of writing.
No result exists. Nothing in this appendix, the figures appendix, or the mechanism exhibit
anticipates its outcome, and the confirmatory candidate documents remain unsigned.

Chapter 3 §3.4 should therefore present the pilot as exploratory evidence with its null
honoured, and treat the confirmatory result as a separate claim that either exists by
submission or is reported as not completed.

### O7 — the user evaluation has not started

The correctness strand is genuinely met. The usability strand is not, and the reason is
external: ethics approval is a person's decision that has not been made.

What exists is preparation only — a drafted instrument, a drafted application, and a fixed
anonymised result schema. What does not exist is a single participant, a single response, or
an approval. No number may be reported for this strand, and no agent may generate one.

Chapter 3 §3.5 should present the research UX against its design intent and the recorded
accessibility checklist, and state the user evaluation as prepared-but-not-run with the
reason. Chapter 4 §4.1 should record O7 as **partially achieved**, which is the accurate
verdict and the one the rubric rewards stating.

---

## Honest scoping, carried into the appendix

Known limits at this commit, so §1.4's honest-scoping paragraph and §3.6 can cite one list:

- **Live simulator execution is not part of the guaranteed workflow.** The import-first path is
  the supported one; direct launch is conditional and is never faked.
- **Publication permission for the collaborator's data is not held.** Trace provenance is
  recorded in `docs/dissertation_appendices/trace_provenance.md`, including the rationales this
  repository cannot restate because the upstream sidecar is not reachable locally.
- **No real-world sensor validation.** Deadline success is never physical completion, and a
  reconstructed evaluator behaviour is never an observed journey.
- **Buses are never general traffic.** Bus progression speed is not road speed, and road-traffic
  volume is not derivable from the bus feed.
- **No supervisor sign-off exists on any research contract.**
  `docs/evaluation/supervisor_contract_decision_form.md` is unsigned.

---

## Provenance of this appendix

Objective wording is carried from the owner's dissertation skeleton rather than reworded, so
this table and Chapter 1 §1.4 cannot drift apart. Section numbers follow that skeleton's
structure.

Every count in the table was measured at this commit rather than copied from a working note:
34 `UiPage` values, 5 additive routes, and 3,454 tests collected across `tests/` — 2,701 in
`tests/unit`, 476 in `tests/ui`, 214 in `tests/integration`, and 63 in `tests/golden`. These
are **collected** counts; the most recent full-suite pass is recorded in `AGENTS.md`. An
earlier working evidence map quoted a 35-route UI and 3,167 tests; both were out of date and
are not reproduced here.

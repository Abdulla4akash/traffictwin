# Appendix — Objectives traceability (O1–O7)

**Reconciled:** 1 August 2026 against the completed experiment register and the manuscript
evidence cut-off.
**Authority:** `docs/dissertation_manuscript_20260801.md` for the current chapter structure and
`docs/experiments_and_findings_20260728.md` for experiment state.

This appendix records what each objective achieved and what remains outside the evidence. A
working feature is not a validated scientific result; a completed run is not admitted merely
because it returned numbers; and ethics submission is not ethics approval.

## Status vocabulary

| Status | Meaning |
|---|---|
| `implemented` | Built, tested and exercised in the repository. |
| `protocol-confirmed within project scope` | Completed on held-out cells under the signed protocol; not external validation or supervisor approval. |
| `exploratory/post-hoc` | Useful empirical evidence whose hypothesis, analysis or extension is not confirmatory. |
| `descriptive, non-admitted` | Returned output that is informative only at a descriptive level because an admission or execution rule was not met. |
| `pending external approval/data` | Prepared, but an owner, supervisor, ethics body or participant must act before evidence exists. |

No row is labelled `scientifically_validated`, `ground_truth`, `causal`, city-wide, deployed or
supervisor-approved.

## Objective spine

| # | Objective | Status at evidence cut-off | Controlling evidence | Manuscript use |
|---|---|---|---|---|
| **O1** | Define a canonical, validated data contract for VEC simulation outputs (SUMO + TOS + synthetic) | `implemented` | `src/traffictwin/integration/tos/`; `src/traffictwin/canonical/`; ADR-054–ADR-058; `docs/architecture.md` | §2.2, instrument boundary |
| **O2** | Implement deterministic metrics and diagnostic rules (R0–R8) with complete provenance | `implemented` | `src/traffictwin/metrics/`; `src/traffictwin/diagnostics/`; provenance routes and `docs/advanced_research_tools.md` | §§2.2, 3.3–3.5 |
| **O3** | Provide statistical comparison machinery for offloading policies (paired studies, N-way ranking, equivalence, power) | `implemented` | `src/traffictwin/experiments/statistical_study.py`, `n_way_ranking.py`, `equivalence_testing.py`, `power_analysis.py`; `docs/statistical_studies.md` | §§2.3–2.5, 3.2 |
| **O4** | Support what-if analysis (scenario mutations, parameter sweeps, measurement imperfections) | `implemented` | `src/traffictwin/experiments/scenario_mutation.py`, `parameter_sweep.py`, `portfolio.py`, `winner_map.py`; `src/traffictwin/synthetic/` | §2.2 and project context; not promoted as the scientific contribution |
| **O5** | Deliver a research UX exposing the above with explicit unavailable and limits states | `implemented` | 34 `UiPage` values plus 5 additive routes at the recorded checkpoint; `docs/v07_navigation.md`; `docs/ui_design.md`; video materials | §§2.2, 3.11 |
| **O6** | Evaluate on the Manchester TOS traces (descriptive case studies across scenarios) | **held-out capacity result: `protocol-confirmed within project scope`; mechanisms/robustness: `exploratory/post-hoc`; B-BUS: `descriptive, non-admitted`** | Signed confirmatory result/report; tail, partition and prediction records; consolidated experiment register; B-BUS fresh-rerun record | §§3.1–3.7 |
| **O7** | Evaluate correctness and reproducibility, and usability subject to ethics | **correctness/reproducibility: `implemented`; usability: `pending external approval/data`** | 3,728 tests collected on 1 August; `tests/golden/`; campaign fingerprints/receipts. User instrument/application materials exist; owner records submission, but no approval reference, participant or response dataset exists | §§2.8, 3.12, 4.1 |

## O6 — current result hierarchy

The capacity pilot is exploratory and generated the hypothesis. The signed held-out experiment
then tested its predeclared latency-primary contrast on seeds 10–14. It confirmed a mean paired
latency difference of **−8,310.9 ms** with paired bootstrap interval
**[−9,097.5, −7,524.3]**; all five directions agreed and the deadline null replicated. The exact
two-sided sign-test value is 0.0625, the attainable floor at n=5. “Protocol-confirmed within
project scope” is therefore accurate; “externally validated” is not.

Action, observation, tail, vehicle-partition and RSU analyses are post-hoc mechanism evidence.
The ceiling-law, actor-crossover and onset-scaling runs are separately predeclared exploratory
tests. Their outcomes must be reported together: 27/27 ceiling checks held; the actor latency-
slope prediction was refuted; the exact onset-scaling prediction was refuted four-of-six; and an
RSU causal explanation was partially withdrawn after a unit error.

The dawn/peak B-BUS successor is not a second confirmation. Its 64 generated analysis sites cover
about 45% of occupied bus cells, its tasks/infrastructure are synthetic, it is outside VEC-06,
and a duplicate-return execution deviation prevents one-shot admission. The retained result is
useful descriptive corroboration only.

## O7 — current human-evaluation boundary

The correctness strand is met at the repository level: 3,728 tests are currently collected, and
golden, fingerprint, preflight, campaign and evidence checks cover the relevant workflow. The
latest full run recorded 3,724 passed and 2 skipped, with two reproducible failures outside this
documentation slice (an N-way golden fingerprint mismatch and a Manchester evidence-export
privacy refusal). The final submission snapshot must not claim a clean suite until those separate
repository defects are resolved.

The usability strand is not met. The owner has recorded that the ethics material covering the
platform was submitted. Submission is not approval: no approval reference, recruitment record,
participant, response or analysed participant dataset is present. The manuscript therefore
reports **zero participant results** and marks O7 partially achieved. No agent-generated mock
result may be substituted for human evidence.

## Honest scope carried into the dissertation

- The central trace is a modelled one-hour collapse in the Etihad/Co-op Live event district, not
  city-wide Manchester and not observed road traffic.
- Deadline success means a generated task met a source-defined 100 ms or 500 ms threshold; it is
  never physical trip completion or safety.
- The environment, trace and checkpoint are producer artifacts used with citation. Permission is
  recorded; private repositories and the Year-1 report are not republished.
- Buses are transit vehicles, never general traffic. Bus progression speed is not road speed and
  the bus VEC overlay uses synthetic tasks/equipment/sites.
- The held-out finding is internal to one environment, trace and checkpoint. No causal deployed-
  infrastructure, algorithm-family or all-Manchester claim is available.
- No supervisor sign-off, ethics approval, external validation or final mark is inferred.

## Count provenance

`uv run pytest --collect-only -q` collected **3,728 tests in 3.58 seconds** on 1 August 2026.
This is a collection count, not a pass claim. The manuscript contains **8,110 whitespace-
delimited words from Abstract through Conclusion**, including headings and excluding front matter,
references and its evidence map, before University-template conversion. The University's own
word-count convention remains the submission authority.

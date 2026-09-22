# Week 4 Progress — Supervisor-Expectation Checklist (27 July 2026)

**Status: owner-facing progress record.** The expectations below are reconstructed from the
owner's notes of the two July 2026 supervision meetings with Dr. Sandra Sampaio (kept outside
the repository) and from Randy Putra's Year-1 report. They are the owner's reading of what was
asked, not a supervisor-endorsed document; nothing here claims supervisor approval, and every
scientific result referenced keeps its recorded `owner_approved_candidate` / exploratory
ceiling.

**Post-snapshot correction:** N1 was withdrawn on 28 July after source PBF and decoded XML
identities were correctly separated; no Geofabrik mutation occurred. The historical line below is
superseded by the correction in
[the continuity audit](integration/manchester_workspace_continuity_20260727.md).

Each item: what was asked → where it stands → the concrete next step and who can take it.

## 1. Learn and use SUMO as the realistic mobility engine

- **Status: delivered, beyond the ask.** Frozen netconvert 1.27.1 Greater Manchester network
  build (ADR-059/060), study subnetwork, count-constrained demand candidate with a measured
  gridlock diagnostic and a predeclared rebuild plan, and the full VEC trace chain running on
  SUMO-derived Manchester traces. All of it evidenced and receipted.
- **Move forward:** nothing pending on this expectation itself; the demand rebuild (E1–E5)
  and network re-pin (N1) decisions continue the story.

## 2. Get onto CSF and use university compute

- **Status: not started in practice.** All experiment compute to date is local CPU (the
  12.5 h pilot ran on the owner's machine). A CSF access request draft was prepared on 26 July;
  Randy's repository ships SLURM launchers and a CSF guide, so the execution path is known.
- **Move forward:** owner sends the CSF request (it is one of the three pending sends). Until
  then the campaign instrument stays local-only by design.

## 3. Read the literature; cite only reputable published work

- **Status: partial.** Randy's Year-1 report has been read and absorbed (its distribution-shift
  concern is the stated motivation of the predeclared bus-fleet experiment). The research
  strategy documents exist. A dissertation-grade reference list (~100 sources, per the
  meeting's guidance) does not exist yet.
- **Move forward:** build the reference list alongside the writing, sourcing via Semantic
  Scholar as Randy recommended; every argument in the dissertation traces to a published,
  citable source — never to a tool's unsupported claim.

## 4. Start writing the dissertation early, technology sections first

- **Status: groundwork only.** The dissertation skeleton exists (outside the repository), and
  the repo's dissertation mapping and evaluation plan were reconciled against accepted
  evidence on 26 July. No prose chapters are drafted yet.
- **Move forward:** the SUMO, CSF, data-source, and instrument sections can be drafted now
  directly from committed docs (ADRs, integration docs, evidence records); the experiment
  chapters wait on the confirmatory campaign.

## 5. Build the Manchester digital twin with what-if scenarios (the project's differentiator)

- **Status: substantially built.** TrafficTwin v0.7 carries the Manchester evidence core
  (DfT, BODS live buses, National Highways, boundaries), the experiment instrument
  (predeclaration → approval-gated campaign → admission → statistical study), and the
  scenario/what-if UI surfaces. The supervisor's own worked example — an event filling a
  football stadium — exists as Randy's audited `ev` trace (Champions League night in the
  Etihad district); a read-only probe on 27 July verified it reconciles perfectly and is
  admission-ready.
- **Move forward:** owner decision to admit the `ev` trace (reviewed allowlist extension,
  same pattern as `inc`), then a predeclared stadium what-if experiment — this would close
  the loop on the exact scenario named in the meeting.

## 6. Engineer scenarios where the expected winner loses (the "Morocco" principle)

- **Status: delivered — one genuine inversion measured.** The predeclared capacity-squeeze
  pilot (12/12 cells, exploratory) refuted the hypothesised degradation cliff: a 3.3×
  capacity squeeze left deadline attainment flat (~79.1%) while mean task latency *fell*
  3.2×, because the trained policy's offloading decisions are capacity-invariant. A
  non-obvious result of exactly the kind the meeting asked for, published under the
  predeclaration's own null-commitment. The actor-crossover study ("expected winner loses")
  is predeclared in structure.
- **Move forward:** owner picks the confirmatory fork — (a) confirm the null descriptively on
  held-out seeds, or (b) declare mean latency the confirmatory primary — then sign, run the
  held-out campaign, and afterwards the crossover study.

## 7. Use real Manchester data, historical and live

- **Status: strong.** DfT count points and raw counts (accepted, matched, demand-constrained),
  BODS live-bus sessions under the attended 60 s boundary (measured cadence median 68 s,
  session-scoped identity policy), National Highways operational feeds, ONS boundaries. All
  quarantined, receipted, and honestly labelled; buses are never general traffic.
- **Move forward:** the weekday-peak bus session (G1) when the owner can attend; the
  demand-rebuild execution after E1–E5 signing.

## 8. User evaluation with ethics approval

- **Status: ready to submit.** The ethics application draft carries clearly-labelled proposed
  values for all seven open fields (submission window, supervisor-mediated recruitment,
  survey-not-interview, retention, withdrawal). The meeting's guidance — about a week of
  review lead time, anonymised participants — is reflected. Nothing is submitted yet.
- **Move forward:** owner confirm-and-send now; it is the longest lead-time item on the
  critical path to the participant study (proposed sessions 11–22 August).

## 9. Contribution must reflect full-time work

- **Status: evidenced by the repository itself** — the accepted phases, ADR trail, evidence
  records, test suite, and this progress series document sustained full-time effort.
- **Move forward:** keep the weekly progress records honest and dated.

## 10. Contribute to Randy's work (co-authorship offer)

- **Status: prepared, not sent.** The baseline-request email with the Study Case 2 proposal is
  drafted; Randy's Year-1 report is read; his trace provenance sidecar is absorbed into the
  pilot's reporting. The pilot's capacity-invariance finding is a direct Year-2 echo of his
  Year-1 reward-misalignment observation — genuine shared material.
- **Move forward:** owner sends the Randy email (second of the three pending sends).

## 11. The open supervisor fork: task offloading vs journey-time prediction

- **Status: open — flagged for the supervisor.** The built programme is de-facto
  task-offloading; the bus-versus-DfT comparison primitive gives the journey-time direction a
  real hook if chosen. The meeting left this decision explicitly with the supervisor.
- **Move forward:** raise in the Monday progress email with the pilot finding attached — the
  latency result gives the journey-time angle new, measured weight.

## 12. The unharvested idea: combine the most promising algorithms

- **Status: not in the current programme.** The meeting proposed identifying the 2–3 most
  promising algorithms and combining them as a contribution. Nothing built or predeclared
  addresses it, and the current instrument (single-algorithm STA-01, N-way ranking) could
  express its evaluation but not its construction.
- **Move forward:** treat as a scoping question for the supervisor: in-scope contribution or
  recorded future work. No commitment implied by this record.

## 13. Keep the supervisor updated

- **Status: drafted.** A progress-update email for the Monday cycle was drafted 27 July; this
  document is its written counterpart.
- **Move forward:** owner sends it with items 11 and 12 as the explicit questions.

## Summary

Four items are fully or substantially delivered (1, 5, 6, 7), three are prepared and blocked
only on owner sends (2, 8, 10, 13), two are writing-stage work that can start now (3, 4), and
two are open supervisor questions to raise Monday (11, 12). The single highest-leverage next
action is the ethics submission (item 8); the single most valuable technical decision is the
confirmatory fork (item 6).

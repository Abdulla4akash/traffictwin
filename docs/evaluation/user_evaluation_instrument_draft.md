# User Evaluation Instrument Draft

**Status: PROPOSED — unsigned, unapproved, and not yet submitted.**

This is the instrument `docs/evaluation/ethics_application_draft.md` refers to, assembled so
that submission becomes an attach-and-send step rather than a writing task. It carries the
proposed values from that draft's §"Proposed values for the open fields" so the application
and the instrument cannot drift apart.

Three things this document is not, stated once here rather than implied throughout:

- **It is not approved.** No ethics committee has seen it, no supervisor has signed it, and
  no reference number exists. Every proposed value below is a proposal a person confirms or
  amends at submission.
- **It carries no results.** No participant has been recruited, no session has run, and no
  response exists. An agent never fabricates a participant response, a completion rate, a
  quotation, an approval, or a signature, and no placeholder in this document may be filled
  with an invented one.
- **It does not replace the existing instrument drafts.** `survey.md`,
  `consent_and_privacy.md`, `participant_task_script.md`, and `interview_guide.md` remain as
  they are. This document composes them against the proposed values and extends the task
  walkthrough and questionnaire to the routes those drafts predate.

Fields in `[square brackets]` are the ones only a person can supply. They stay bracketed
until submission.

---

## 1. Proposed values carried from the ethics draft

Repeated here so a reviewer reads one document. The authority is the ethics draft; if the
two ever disagree, the ethics draft wins and this file is wrong.

| Field | Proposed value | Confirmed by |
|---|---|---|
| Instrument | **Survey**, with optional free-text comments — not an interview | applicant at submission |
| Recording | **None.** Screen and audio recording stay disabled | applicant at submission |
| Session length | 30–45 minutes, task-based | applicant at submission |
| Participants | ~4–10 adult researchers or postgraduate students | applicant at submission |
| Identifiers | Random participant code only; anonymised responses | applicant at submission |
| Retention | Until degree award **plus 12 months**, University-approved encrypted storage | applicant at submission |
| Withdrawal cutoff | **14 days** after the participant's session, after which responses are anonymised and no longer attributable for deletion | applicant at submission |
| Study dates | Sessions [11–22 August 2026, to confirm] | applicant at submission |
| Ethics reference | [assigned at submission — never pre-filled] | ethics committee |

The interview guide stays in the repository as a possible follow-up application. Selecting
the survey does not delete it, and this instrument does not assume the interview will
happen.

---

## 2. Participant information sheet (skeleton)

> **Study title.** Evaluating an import-first workflow for traffic and vehicular-edge-computing
> experiments.
>
> **Who is running this study.** [Researcher name], [programme], [School], University of
> Manchester, supervised by [Supervisor name]. Contact: [researcher email] /
> [supervisor email]. Ethics reference: [assigned at submission].
>
> **Why you have been invited.** You have experience with traffic simulation, vehicular edge
> computing, or research software. We are evaluating the software's workflow — not your
> ability, knowledge, or performance.
>
> **What taking part involves.** One session of approximately 30–45 minutes. You will work
> through a short task script with the prototype in front of you, then complete a
> questionnaire of rating items and three optional free-text questions. You may skip any task
> or question and stop at any point without giving a reason.
>
> **Recording.** **There is no recording.** No screen capture and no audio or video are
> made. The observer writes short non-identifying notes only.
>
> **What data is collected.** A random participant code generated before the session; a broad
> role category and experience band; for each task whether it was completed, completed with
> assistance, or not completed, with elapsed time and an assistance count; your questionnaire
> ratings; and your optional free-text comments after names and organisation identifiers are
> removed.
>
> **What is never collected.** Your name, email address, staff or student number, IP address,
> precise employer, or any confidential project or simulator data. Please do not enter any of
> these in the free-text boxes.
>
> **How your data is stored.** In [University-approved encrypted storage service], accessible
> to the student researcher and the named supervisor only. The participant-code key is stored
> separately from the responses. Data is retained until degree award plus 12 months and then
> deleted.
>
> **Withdrawing.** You may stop during the session without giving a reason. Afterwards you
> may withdraw your responses by quoting your participant code to [researcher email] within
> **14 days** of your session — by [date to be written per session]. After that point the
> responses are anonymised and can no longer be identified as yours, so they cannot be
> removed.
>
> **Risks.** We expect none beyond the mild discomfort of using unfamiliar software. The
> software is being evaluated, not you. Anyone the researcher directly assesses is not
> recruited.
>
> **What happens to the results.** Aggregate ratings, task outcome counts, and anonymised
> quotations may appear in the dissertation and any resulting publication. With a sample this
> small, results are reported descriptively and never as population estimates.
>
> **Complaints.** [Standard University complaints wording and contact — insert at
> submission.]

---

## 3. Consent checklist

To be ticked by the participant before the session begins. The session does not start until
every non-optional statement is ticked.

- [ ] I have read and understood the participant information sheet.
- [ ] I have had the opportunity to ask questions and they have been answered.
- [ ] I understand that participation is voluntary and that I may stop at any time without
      giving a reason and without any consequence.
- [ ] I understand that no screen, audio, or video recording is made.
- [ ] I understand what data is collected, that it is identified only by a random participant
      code, and that my name and contact details are not part of the research record.
- [ ] I understand that I may withdraw my responses by quoting my participant code within 14
      days of my session, and that after anonymisation they can no longer be removed.
- [ ] I understand that anonymised quotations may be used in the dissertation and any
      resulting publication.
- [ ] I agree to take part in this study.

Participant code: `[assigned before the session]`  Date: `[  ]`

*No signature block appears in this draft. The consent format — wet signature, tick-box form,
or recorded verbal consent — is an approval decision, and an agent does not choose it or
complete it.*

---

## 4. Task walkthrough

Read the opening from `participant_task_script.md` first: the software is being evaluated,
not the participant; synthetic material is labelled synthetic; diagnostic outputs are
hypotheses rather than proven causes.

Four tasks, in this order. Each names what the observer records and what the participant is
asked to say out loud, because the questionnaire items later depend on the participant having
actually reached that surface.

### Task 1 — Guided Demo: establish what kind of data is on screen

Open the **Guided Demo** (`/guided-workflow`) and work through it far enough to answer: *is
what I am looking at synthetic, imported, or unavailable, and how do I know?*

- **Ask the participant to state:** the current data mode, and the specific element on screen
  that told them.
- **Observer records:** outcome, elapsed seconds, assistance count, and whether the
  participant named the labelling element or inferred the mode from context.

### Task 2 — RSU Monitor: which RSU is overwhelmed, and how overwhelmed

Open **RSU Monitor** (`/rsu-monitor`) over an already-imported TOS run. Identify the roadside
unit under the most pressure, and say what "pressure" is being measured.

- **Ask the participant to state:** which RSU they would look at first, the quantity they
  used to decide, and one thing the page tells them it *cannot* show.
- **Observer records:** outcome, elapsed seconds, assistance count, and whether the
  participant noticed that per-RSU energy and per-RSU processed-task counts are declared
  unavailable rather than shown.
- **Note for the observer:** the page reports in-flight tasks against recorded maximum
  concurrency. It is not CPU utilisation and not live monitoring. If the participant reads it
  as either, record that — it is a finding, not a participant error, and it must not be
  corrected before the questionnaire.

### Task 3 — Provenance: trace a displayed number to where it came from

Take one number the participant has already seen and trace it back through **Provenance
Explorer** (`/provenance`) to its source context.

- **Ask the participant to state:** what they would need to see before citing that number in
  their own work, and whether they can see it here.
- **Observer records:** outcome, elapsed seconds, assistance count, and any link the
  participant expected to find and did not.

### Task 4 — Match Review: decide, then seal

Open **Match Review** (`/match-review`), review one map-matching candidate, record a decision
with its reason, and then seal the ledger for export.

- **Ask the participant to state:** what sealing changed, and what they would do if they
  needed to revise a decision after sealing.
- **Observer records:** outcome, elapsed seconds, assistance count, and whether the
  participant understood before sealing that the sealed export is written beside the working
  ledger rather than replacing it.

### Closing

Hand over the questionnaire. Remind the participant of the 14-day withdrawal window, their
participant code, and the study contact address.

**Observer record per task:** `completed` / `completed_with_assistance` / `not_completed`,
elapsed seconds, assistance count, and one short non-identifying note. Participant names
never appear on this sheet.

---

## 5. Questionnaire

**Scale for items 1–11:** 1 = strongly disagree, 2 = disagree, 3 = neither agree nor
disagree, 4 = agree, 5 = strongly agree. Every item may be skipped; a skipped item is
recorded as skipped and never imputed.

Eleven rating items — within the 8–12 the design calls for — followed by three free-text
questions.

### Honesty of state (what the software is showing)

1. I could tell whether the data on screen was synthetic, imported, or unavailable.
2. Where something was unavailable, the interface told me *why* rather than showing a blank
   or a zero.

### Explainability (why the system behaved as it did)

3. **The provenance trail helped me understand *why* a displayed result had the value it
   did**, rather than only *what* the value was.
4. **The diagnostics distinguished what the evidence showed from what it did not**, so I
   could see which hypotheses the data actually supported.
5. **RSU Monitor let me work out which roadside unit was under pressure and how much**,
   rather than only that pressure existed somewhere.
6. When a quantity could not be attributed to an individual RSU, the interface made that
   limitation clear rather than leaving me to assume it had been measured.

### Usability

7. I could complete the tasks without needing simulator-specific knowledge.
8. It was clear at each step what I could do next.
9. I could recover when I made a mistake or opened the wrong thing.
10. The terminology was consistent enough that I did not have to re-learn a word between
    pages.
11. Compared with inspecting separate result files by hand, this workflow would reduce my
    effort.

### Free text (all optional)

- **F1.** Which part of the workflow was most useful, and why?
- **F2.** Which part was confusing, or gave you an impression that turned out to be wrong?
- **F3.** What is the single most important thing to change before you would use this for
  your own work?

*Please do not include names, organisations, or confidential project details in your answers.
Any that appear are removed before analysis.*

### Also collected

Participant code; broad role category; broad experience band. Nothing else. All three are
already fixed by `anonymised_result_schema.json` and this instrument invents none of them:
the code matches `TT-` followed by 6–12 uppercase alphanumerics, the role category is one of
`researcher` / `postgraduate_student` / `traffic_professional` / `other`, and the experience
band is one of `under_1_year` / `1_to_3_years` / `4_to_7_years` / `8_plus_years`.

The schema keys ratings as `Q1`–`Q11`, which the eleven rating items above fill directly, and
records each task with its outcome, elapsed seconds, and assistance count — the same three
values the observer sheet in §4 collects. Free-text answers enter as `coded_comments` only
after a person has coded them.

---

## 6. Analysis commitments, fixed before any data exists

Written now so the analysis cannot be chosen after seeing the responses.

- Ratings are reported as distributions — counts per point on the scale — not as means of an
  ordinal scale, and never as population estimates. With 4–10 participants, no inferential
  test is run and no significance is claimed.
- Task outcomes are reported as counts in the three recorded categories, with assistance
  counts beside them. Elapsed times are reported descriptively (median and range).
- Free-text answers are coded into themes by a person. **No LLM computes a metric, codes a
  participant response, or generates a finding.** An LLM may, if used at all, only render
  findings a person has already established.
- A result that is unflattering to the software is reported the same way as a flattering one.
  The publishable outcome includes "participants could not do this".
- Anything the sample cannot support — generalisation to traffic operators, claims about
  real-world deployment, or any statement that the workflow is validated — is out of scope
  for this instrument and stays that way regardless of what the responses say.

---

## 7. Submission checklist

Everything below is a person's action. None of it is an agent's.

- [ ] Supervisor has reviewed the ethics application draft and this instrument.
- [ ] Every proposed value in §1 confirmed or amended.
- [ ] Every `[bracketed field]` in §2 replaced, including both contact addresses, the storage
      service name, and the standard complaints wording.
- [ ] Consent format chosen and the consent record designed accordingly.
- [ ] Per-session withdrawal dates prepared for §2 and the closing script.
- [ ] Recruitment invitations sent by the supervisor or a neutral third party, not by the
      researcher directly.
- [ ] Application submitted; reference number recorded here on receipt.
- [ ] **Approval received before the first session is booked.**

---

**Related documents.** `ethics_application_draft.md` (the authority for every proposed value
above), `consent_and_privacy.md`, `participant_task_script.md`, `survey.md`,
`interview_guide.md` (held for a possible follow-up application), and
`anonymised_result_schema.json` (the fixed record shape).

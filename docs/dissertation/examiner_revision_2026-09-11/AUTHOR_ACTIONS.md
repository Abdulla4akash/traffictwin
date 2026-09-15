# Author confirmations and defence exercises

## Author confirmation — S M Abdulla Al Mamun, 15 September 2026

1. Design and decisions. The research questions and every evaluation design were mine: E1 capacity levels; the E2b ingress-with-gate control; the E2c four-draw replication; the E2d per-task placement and its reuse of E2c controls; the morning pilot and its exclusion; primary seeds 0/2/3/4; the three declared contrasts; the round-robin comparator; the eight joint fleet/evaluator blocks and rotating arm order. One exception: the 100 ms, 500 ms and 1,000 ms report-age levels were suggested by Dr Sandra Sampaio (email, 18 August 2026, `docs/correspondence/sandra_randy_vec_progress_email_thread_2026-08-18.md`, PDF page 4). I chose to run them.
2. Supplied code. Randy Prasetia Putra supplied the MAPPO actor, the vec_env environment and evaluator, and the 5 August 2026 accounting repair (vec_env commits 4cb7c06, 0f01f4d).
3. Implementation. I directed the design of every component. Codex and ChatGPT generated code, campaign runners and draft text to my specification. I reviewed that code, and in many cases modified it myself to fit the experimental design, before it was run or archived. Commits under my name in vec_env and traffictwin record those changes. I ran or authorised every campaign and decided what entered the report.
4. Verification. I completed the eight exercises below on 15 September 2026, including recomputing the block-0 per-task minus ingress effect from the offered counts, checking the Table 6 and Table 7 intervals, working through Proposition 1 and Table C1, and tracing the common-target argmin in the frozen evaluator source.
5. Open items. COMP60060 AI-use permission: pending supervisor confirmation. Examiner data access: pending.

## Author-check exercises (completed 15 September 2026)

- Explain the reversal using target timing, visible workload, reservations,
  admission and scoring; avoid relying on the label “least-busy”.
- Work through Proposition 1: define the map, why it reverses inclusion, and
  why two deadline classes suffice under its exact-arithmetic assumptions.
- Explain how inclusive-prefix subtraction can change a strict float32 gate,
  and separate mask, final offset, failure label and deadline outcome.
- Interpret one incident interval and one morning simultaneous interval; state
  the replication units, adaptive/reused controls and excluded pilot.
- Trace Table C1's adverse example and explain why its reduced dimensions and
  A-conditioned B targets limit its applicability.
- Defend cyclic pointer advancement on rejection, no advancement for unavailable
  radio, and the fair shared-input boundary. Explain what the CPU benchmark excludes and why
  the new study permits observation/action feedback under frozen weights.
- Recalculate one new paired effect from the two all-offered counts. Explain
  why eight joint-seed blocks give df=7, why the three simultaneous intervals
  form one family, and why neither tasks nor the earlier four draws add
  replications to it. Distinguish the observed action check from forced replay.
- Identify what the new results change about workload awareness versus
  spreading, and what remains conditional on this trace, actor and evaluator.

These confirmations record my statement; automated validation does not constitute supervisor approval. Award wording, student ID, signature, prescribed University copyright text and video recording remain open in SUBMISSION_GATES.md.

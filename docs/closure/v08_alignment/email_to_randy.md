# Email to Randy — Confirmation Request (DRAFT — DO NOT SEND WITHOUT REVIEW)

**Status: DRAFT / NOT EFFECTIVE — PROVISIONAL_PENDING_RANDY**
**Base: bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6**
**Packet ref: docs/closure/v08_alignment/stakeholder_confirmation_packet.md**

Subject: Request for confirmation — RSU semantics, denominators, and lifecycle fields (v08 closure)

Dear Randy,

I am writing to request explicit confirmation on six points that remain EXTERNAL DECISION REQUIRED for honest VEC reporting. The full decision packet is attached for reference and remains DRAFT / NOT EFFECTIVE until you reply. No approval or delivery is claimed.

**SOURCE-DERIVED FACT:** This request draws on your direct Q&A (S-007, SHA-256 `e8dbbdfa43995870b7e79b8de00dd5e3d73d2988a3846c5bac178bb6b3ab4ec4`) and the staged direct Sandra body (S-035, SHA-256 `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed`).

**PROVISIONAL_PENDING_RANDY — six neutral questions:**

1. **RSU waiting-room meaning (RQ-RANDY-01).** Should the project adopt exactly the per-RSU admission/in-flight waiting-room ceiling definition for all code, report, and UI labels — counting every task inside the RSU, waiting plus being served, unrelated to processing power — and move away from any per-vehicle RSU concurrency ceiling wording?

2. **Offered / admitted / rejected denominators (RQ-RANDY-02).** For deadline attainment, latency, and completion rate, which denominators should be reported — offered tasks, admitted tasks, or rejected tasks — and how should rejected tasks be accounted for to avoid fail-fast accounting effects where reduced queue capacity appears as reduced latency?

3. **Deadline after return (RQ-RANDY-03).** Should deadline compliance be evaluated after return to the requesting vehicle (including any RSU-to-RSU forwarding time), and what deadline interval and return path should be used for common reporting?

4. **Actor mode-only authority vs downstream RSU selection (RQ-RANDY-04).** Is the actor's authority limited to mode/offload decision only, with downstream RSU selection handled by the infrastructure balancer (as suggested by radio association once per second and per-task routing+admission), or does the actor retain RSU-choice authority? How should the boundary be documented?

5. **Gate vs capacity rejection (RQ-RANDY-05).** How should gate rejection be distinguished from capacity rejection (waiting-room full) in metrics and traces, and should surplus tasks be terminally rejected outside the RSU queue with no retry, fallback, or re-forwarding as the authoritative semantic?

6. **Authoritative lifecycle fields (RQ-RANDY-06).** Which lifecycle fields are authoritative for the task record (e.g., offered time, admission time, RSU assignment, queue entry, service start/end, rejection reason, return time), and which fields should be added or remain out of scope for this closure?

All questions are `PROVISIONAL_PENDING_RANDY` and do not presuppose any answer. Your confirmation on any or all points will be recorded as a new source and reflected in the decision register. The proposed amendment remains DRAFT / NOT EFFECTIVE until stakeholder confirmation is received.

Thank you for your help.

Kind regards,
Abdulla

---
*This draft has not been sent. It references the packet and the proposed amendment v2, both marked DRAFT / NOT EFFECTIVE.*

# Cumulative Findings

## 1. Queue capacity is not compute capacity

E1 enlarged only the waiting room. At fixed 1× service, larger caps reduced cap rejection and admitted more work, but created much larger admitted latency and lower admitted-task attainment. The primary offered-task contrast remained inconclusive.

## 2. Offered and admitted denominators answer different questions

Deadline-aware admission can improve the quality of admitted work by rejecting tasks that are unlikely to meet deadlines. That does not erase rejected tasks from the system objective. Reporting both denominators prevented the admission policy from looking better simply because it considered fewer tasks.

## 3. Placement and admission must be separated

E2's `dla` arm changed both execution placement and admission. E2b added the missing `ingress_dla` cell. This showed that deadline-aware admission improved offered attainment under both placement families, while the inherited placement rule remained lower than strongest-link under the same gate.

## 4. Balance is not a sufficient performance argument

E2's ordinary least-busy arm produced an almost uniform execution distribution yet lowered offered deadline attainment. E2c's gated common-target arm also forwarded heavily but executed work on only five RSUs. Balance and forwarding counts are mechanism diagnostics, not substitutes for deadline outcomes.

## 5. Implementation semantics reversed the direction

The E2c contrast was:

`common-target-per-substep least-busy - strongest-link = −2.122 pp` (four-draw mean)

The E2d contrast was:

`per-task sequential least-busy - strongest-link = +0.527 pp` (four-draw mean)

The same broad “least-busy” label concealed two materially different dispatch mechanisms. E2d used all ten RSUs with near-uniform execution shares and updated the effective workload after every admitted assignment. The inherited E2c rule selected only one target per substep and used five RSUs for actual execution.

The bounded evidence supports the statement that dispatch granularity was an important mechanism behind E2c's negative direction. It does not prove that batching was the sole possible cause, nor that per-task least-busy placement is universally superior.

## 6. Evaluation methodology is part of the contribution

The programme combined:

- rejection-aware offered-task denominators;
- task and service-work conservation;
- native ingress/selection/execution observability;
- matched task, actor-action and fleet identities;
- fleet-seed—not task-level—replication;
- predeclared estimands and stop rules;
- frozen source/artifact identities;
- raw checksum ledgers;
- independent exact-head technical review gates;
- transparent retention of inconclusive and stopped pre-run events.

## Cumulative experiment table

| Study | Question | Seeds | Intervention | Main result | Status |
|---|---|---:|---|---|---|
| E0 | Can evaluator accounting be trusted? | Validation | Accounting/conservation | Conservation established | Closed |
| E1 | Does larger waiting-room capacity help? | 5 | Queue cap | Primary inconclusive; latency/admission trade-off | Closed |
| E2 | Does least-busy placement help? | 1 | Placement | Balanced execution but lower attainment | Pilot |
| E2b | Placement or admission? | 1 | Factorial missing cell | Admission helps; inherited placement worse under same gate | Hypothesis-generating |
| E2c | Does same-gate negative result replicate? | 4 new | Common-target placement | −2.12 pp | Bounded matched result |
| E2d | Does result survive per-task dispatch? | 4 matched | Per-task placement | +0.53 pp; direction reversal | Bounded robustness result |

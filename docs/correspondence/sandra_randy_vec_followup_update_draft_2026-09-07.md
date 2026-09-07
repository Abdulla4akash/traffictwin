# Supervisor update — draft, not sent

**To:** Sandra Sampaio

**Cc:** Randy Putra

**Subject:** TrafficTwin VEC: dispatch reversal replicated in the morning scenario

Dear Sandra and Randy,

I have completed the follow-up studies on RSU information delay, fixed
forwarding overhead and another Manchester traffic scenario.

The strongest new result comes from a three-arm replication in the canonical
working-day morning scenario. I compared ingress execution, common-target
least-busy placement and sequential per-task least-busy placement, retaining
the inherited deadline-aware admission rules. Across four newly declared fleet
draws and twelve full runs, the ordering was common-target < ingress < per-task
in every draw.

Mean offered-task deadline attainment was 85.655% for common-target, 88.887%
for ingress and 92.785% for per-task placement. The paired per-task advantage
over ingress was **3.899 percentage points**, with a simultaneous 95% interval
of **[2.671, 5.126] points** across the three planned contrasts. Common-target
was **3.232 points below ingress**. This reproduces the implementation-dependent
ranking reversal in another Manchester operating scenario.

The earlier positive two-arm pilot was kept separate from the primary
analysis because it influenced the decision to continue. All arms used the
same frozen actor, canonical morning trace, nine-RSU layout, absolute
6,220-task RSU limit, queue-reset convention, 1× service and zero forwarding
overhead. All matched-input, task-accounting and workload-conservation checks
passed. Common-target concentrated admitted work on five RSUs, while per-task
placement distributed it almost evenly across all nine.

For the incident-trace state-delay pilot, I tested your suggested 100 ms,
500 ms and one-second ages. The measured changes were small, but the 100 ms
result needs careful interpretation: under the retained batched-arrival model,
the queue cleared before both the 100 ms and fresh report times. Those
conditions therefore supplied identical workload values. I have documented
this timing limitation rather than treating the equality as general robustness
to stale information.

The separate fixed-overhead analysis found that the per-task advantage remained
positive through 10 ms forwarding cost in the tested incident draw, declining
from 0.464 to 0.283 percentage points above ingress. Four direct short runs
qualified the transformation of the existing full task records. This measures
a fixed latency charge, not a physical congested backhaul network.

I have prepared an integrated dissertation results section and archived the
compact evidence, figures and validation records in the private repository.
My next writing focus is the dispatch-semantics contribution, supported by the
new replication and these bounded sensitivity findings. The evidence remains
limited to the tested Manchester scenarios and frozen policy; it does not
establish independent geographical generalisation or a Kubernetes deployment.

Best regards,

S M Abdulla Al Mamun

---

Links for review:

- [Integrated evaluation and reflection](../dissertation/vec_results_integration_2026-09-07.md)
- [Replication summary and figures](../evaluation/vec_followup_2026-09-07/generalisation-replication-2026-09-07/PUBLICATION_SUMMARY.md)
- [Private evidence archive](../evaluation/vec_followup_2026-09-07/README.md)

This message has not been sent. The links require access to the private repository.

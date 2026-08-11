# Supervisor-facing E2c summary — 10 August 2026

The E2c evidence passed all 16 smoke and eight full-cell gates. For the four new matched fleet
draws, the `dla - ingress_dla` offered-task deadline-attainment differences were seed 1
`-0.022097034972`, seed 2 `-0.020519134179`, seed 3 `-0.021447383092` and seed 4
`-0.020825491499`. All four were negative; their mean was `-0.021222260935`, and the two-sided 95%
Student-t interval with three degrees of freedom was
`[-0.022335254070, -0.020109267800]`, which excluded zero. Seed 0 was excluded from this primary
interval and remains prior pilot evidence.

Within this bounded four-new-draw Manchester incident replication, JSQ execution placement under
the inherited one-common-target-per-substep implementation produced lower offered-task deadline
attainment than strongest-link execution when both used the same deadline-aware admission gate.

The evidence is limited to four new matched provisional `uk2030` fleet draws (seeds 1–4), fixed
evaluator seed 0, one Manchester incident hour, one 2.5x waiting-room cap (6,220 tasks per RSU),
fixed 1x service and zero-cost backhaul. The frozen vehicle actor does not observe current RSU load
and does not select the execution RSU. No ordinary/free-flow traffic control was run, and deadline
attainment is a simulator outcome rather than confirmed physical task-result return. The inherited
DLA/JSQ implementation selects one common `argmin(rsu_busy_ms)` target per substep.

These results do not support a population-wide or Manchester-wide claim, physical-deployment or
Kubernetes evidence, universal JSQ harm, or general controller superiority. E2c remains closed;
fresh independent exact-head review is the next gate, and no further experiment is authorised.

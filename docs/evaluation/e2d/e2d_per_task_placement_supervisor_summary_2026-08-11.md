# Supervisor-facing E2d summary — 11 August 2026

E2d completed the four predeclared matched `per_task_dla` cells after exact no-effect and smoke
gates. The primary `per_task_dla - ingress_dla` differences were
seed 1 `+0.004636732564`, seed 2 `+0.005867285642`, seed 3 `+0.005071796666`, seed 4 `+0.005509919752`.
Their mean was `+0.005271433656` and the two-sided 95% Student-t interval with df=3 was
`[+0.004422143925, +0.006120723387]`; the predeclared decision was
`directional_advantage_for_per_task_placement_within_bounded_draws`. The secondary per-task-minus-common-target mean was
`+0.026493694591` with interval
`[+0.026210763951, +0.026776625232]`.

This bounded construct-validity study covers four matched provisional fleet draws (seeds 1–4),
fixed evaluator seed 0, one Manchester incident hour, one 2.5x/6,220-task cap, fixed 1x service,
zero-cost backhaul and a frozen actor that neither observes RSU load nor chooses execution RSUs.
The new deterministic mode recomputes the least remaining-service-work target per task in padded
vehicle-slot order; the inherited deadline gate remains a backlog-only simulator rule. There was
no ordinary-traffic control, physical task-result-return confirmation, physical/Kubernetes
deployment or task-level inference. The evidence does not establish equivalence, universal
least-busy superiority/inferiority, general controller superiority, or Manchester-wide or
population-wide performance. E2d is closed pending independent post-run review, with no automatic
follow-on authority.

# Limitations and Claim Boundaries

## Experimental scope

The placement evidence is bounded to:

- one Manchester incident hour (15 March 2024, 20:00–21:00 Europe/London);
- a provisional `uk2030` fleet;
- four new E2c/E2d fleet draws (seeds 1–4);
- evaluator seed 0;
- one waiting-room regime, 2.5× / 6,220 tasks per RSU;
- fixed 1× compute service;
- scaling off;
- zero backhaul latency;
- a backlog-only deadline-feasibility gate;
- a simulator deadline outcome, not confirmed physical task-result return;
- a frozen vehicle actor that neither observes current RSU load nor chooses an execution RSU;
- no ordinary/free-flow traffic control;
- reused, hash-verified E2c controls in E2d.

E1 examined three waiting-room caps over five fleet draws, but retained the same one incident hour, fleet family and evaluator seed.

## Claims not supported

The evidence does not establish:

- population-wide or Manchester-wide performance;
- universal least-busy or universal JSQ superiority/inferiority;
- general strongest-link inferiority/superiority;
- performance under nonzero backhaul;
- ordinary-traffic performance;
- physical deployment or Kubernetes execution;
- confirmed task-result return to physical vehicles;
- task-level statistical significance;
- causal effects outside the controlled simulator intervention;
- equivalence when a confidence interval includes zero;
- that common-target batching was the sole cause of E2c's direction.

## Interpretation of the final result

Within four matched incident draws, per-task sequential least-busy placement exceeded strongest-link execution under the same deadline-feasibility rule. This establishes a bounded directional difference for the tested simulator conditions. The reversal relative to E2c demonstrates construct sensitivity, not a universal scheduler ranking.

# Research Question

## Programme-level question

How do finite RSU queue capacity, deadline-aware admission and infrastructure-side execution placement affect offered-task deadline attainment in a vehicular edge-computing simulator when the vehicle actor and compute service are held fixed?

The programme refined that broad question through six bounded studies rather than treating one scheduler label as a single, fixed construct.

## Question progression

1. **E0 — validity:** Does every offered task reach a complete terminal accounting category, and does service work conserve?
2. **E1 — queue capacity:** Does increasing waiting-room capacity improve offered-task deadline attainment when service remains 1×?
3. **E2 — placement pilot:** Does native least-busy execution placement improve attainment relative to strongest-link execution?
4. **E2b — decomposition:** Is the observed DLA benefit due to placement, deadline-aware admission or their interaction?
5. **E2c — matched replication:** Under the same deadline gate, does the common-target least-busy deficit persist across four new fleet draws?
6. **E2d — construct validity:** Does that deficit persist when least-busy placement is recomputed sequentially per task candidate?

## Primary estimands

### E1

`offered_deadline_attainment(40x cap) - offered_deadline_attainment(0.75x cap)`

Replication unit: fleet seed, five matched draws.

### E2c

`offered_deadline_attainment(common-target dla) - offered_deadline_attainment(ingress_dla)`

Replication unit: fleet seed, four new matched draws (1–4). Seed 0 generated the hypothesis and was excluded from the primary interval.

### E2d

`offered_deadline_attainment(per_task_dla) - offered_deadline_attainment(ingress_dla)`

Replication unit: fleet seed, four matched draws (1–4). E2c controls were reused by exact identity and hash.

The secondary E2d construct-validity contrast was:

`offered_deadline_attainment(per_task_dla) - offered_deadline_attainment(common-target dla)`

## Why offered-task attainment is primary

Admission policies may improve the outcomes of admitted work by rejecting more difficult tasks. Those rejections remain system outcomes. Using `deadline_met / offered_tasks` keeps rejected and unavailable work in the primary performance denominator. Admitted-task attainment is reported as a separate diagnostic, not substituted for the primary outcome.

## Research architecture

The frozen actor chooses Local, V2I or V2V. For V2I, the radio layer identifies strongest-link ingress. Infrastructure placement may keep execution at ingress or choose another RSU. Admission then applies cap and, in gated arms, deadline feasibility. Only admitted tasks enter execution queues. These are distinct decisions and were separated experimentally.

## Claim boundary

The programme estimates differences within bounded simulator conditions. It does not establish universal scheduler rankings, physical Manchester performance, task-level statistical significance or equivalence when an interval includes zero.

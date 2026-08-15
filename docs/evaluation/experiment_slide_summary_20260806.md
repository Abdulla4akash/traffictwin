# TrafficTwin experiments — slide summary

**Status:** owner-approved candidate evidence; descriptive/non-causal; not supervisor-approved.

## Slide 1 — Historical VEC experiments

- **154 admitted cells; 17 studies** across five traffic traces.
- **Pilot:** no deadline-attainment cliff; mean modelled latency fell **9.80 → 3.08 s**.
- **Held-out test:** **−8.31 s** mean latency; **p = 0.0625**; deadline attainment nearly flat.
- **Mechanism:** actor decisions identical; 17-D actors could not observe capacity/load.
- **Tail:** median stayed **44.3 ms**; reduction came from the already-failed extreme tail.
- **Breadth:** normal-density traces were invariant; deep-squeeze effects were tiny.
- **Predictions:** ceiling regularity held; density-onset law and actor-independent slope failed.
- **Actor test:** trained actor stayed about **6.09 percentage points** ahead; no crossover.
- **RSUs:** load was highly unequal, but the cause remains unresolved.

## Slide 2 — Live traffic: BODS bus observations

- **Four attended sessions:** night, dawn, morning peak and evening peak.
- Active linked buses: **41 → 1,162 → 1,433 → 1,522**.
- Update cadence stayed stable: median **66–68 s**, p90 **75–76 s**.
- Bus progression fell from **6.29 m/s at night** to **3.52–3.61 m/s at peak**.
- Operator-scoped identity fixed cross-operator vehicle-reference collisions.
- Result is **observational**: bus progression is not general road speed or a causal congestion test.

## Slide 3 — Real-mobility hybrid bus experiments

- Real BODS bus movement; **synthetic tasks, hardware, radio, queues and RSUs**.
- Full dawn/peak traces failed the VEC-06 placement bound; the refusal was preserved.
- **Corridor, five seeds:** deadline attainment **0.809841 vs 0.809672**; non-admitted.
- **Sparse-64 first return:** **0.519215 vs 0.519108**; 147 duplicate returns; non-admitted.
- **Sparse-64 clean rerun:** **0.501355 vs 0.501233**; one duplicate return.
- Clean rerun is admitted only as **descriptive evidence with an execution deviation**.

## Slide 4 — Colab/GPU experiments

- **B-CAP:** 17-D actors stayed invariant; retrained 19-D actors reacted to capacity/headroom.
- **B-REWARD:** pure QoS gave a tiny **+0.017 pp** synthetic gain with higher energy/local use.
- **B-MASK:** zero infeasible choices across **10.24 million** masked decisions.
- **B-DOMAIN:** 15 training jobs and 90 diagnostic cells; contrasts await independent review.
- **B-BUS/IPPO smokes:** proved training pipelines only; no algorithm or real-bus verdict.
- **B-DENSITY:** GPU path worked; full grid estimated at **~99 GPU-hours**, so it was not run.
- Overall: GPU work proved responsiveness and infrastructure, **not admitted outcome benefit**.

## Slide 5 — Historical Manchester data investigations

- **Demand:** 43,200 routes and 749,267 sampled vehicles; fringe-bias hypothesis refuted.
- Six poorly reachable edges caused **72.8% of unmet demand**.
- Four were bus/bicycle-only; two were clipped M56 boundary segments.
- **Source audit:** the claimed Geofabrik mutation was withdrawn; compressed and decoded hashes had been confused.
- **Regeneration:** network, DfT counts and matching chain reproduced from committed pins.
- One historical fingerprint remained unverifiable because its computation script was not retained.

## Slide 6 — Defensible conclusion

- The capacity control changed an **admission/in-flight ceiling**, not computation power.
- Lower mean modelled latency did **not** prove faster computation, throughput or physical completion.
- Live traffic supplied real mobility evidence; VEC task outcomes remained simulated.
- Next: **lifecycle instrumentation → deterministic RSU dispatcher → learned scheduler**.
- Capacity-aware actor retraining is a **separate experiment**.

Source: [complete experiment history](complete_experiment_history_20260806.md).

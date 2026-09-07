# State-delay pilot results

Single fleet draw (seed 1), Manchester incident, 3,600 simulated seconds per condition.

| Condition | Offered-task deadline attainment | Change from fresh (pp) | Change from ingress (pp) |
|---|---:|---:|---:|
| fresh | 72.46695% | +0.00000 | +0.46367 |
| delay_100 | 72.46695% | +0.00000 | +0.46367 |
| delay_500 | 72.46856% | +0.00161 | +0.46529 |
| delay_1000 | 72.45510% | -0.01185 | +0.45183 |
| ingress | 72.00328% | -0.46367 | +0.00000 |

This is a single-draw pilot, so these are descriptive comparisons without replicate-level confidence intervals.
Placement sees delayed workload reports; admission and acknowledgements are current. Arrivals retain Model C's one-second batches. Equal reports during idle periods do not establish general resilience to communication delay.

All cells passed their recorded validation. Full metrics are in comparison.csv and each cell's summary.json.

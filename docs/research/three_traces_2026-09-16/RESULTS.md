# Three-trace generalisation results

All 120 full cells and 24 blocks passed, following 18 qualification attempts. No failures or retries. The design was proposed by Claude and authorised by the owner. These are paper-study results; no manuscript was edited.

## Scenarios and timing

| Trace | N | R | Entry channel | Elapsed hours |
|---|---:|---:|---|---:|
| we | 139 | 9 | True | 7.334 |
| wd_pm | 163 | 10 | False | 7.033 |
| ev | 175 | 12 | False | 7.029 |

Trace elapsed times include serial cells and validation and may overlap across traces. These are the preserved runner monotonic timers, which exclude host sleep. For actual UTC clock elapsed times, including the documented sleep interruptions, see [TIMING_NOTES.md](TIMING_NOTES.md).

## Deadline attainment

| Trace | Arm | Mean attainment (%) |
|---|---|---:|
| we | ingress_dla | 89.896399 |
| we | dla | 86.900305 |
| we | per_task_dla | 93.624790 |
| we | causal_round_robin | 93.111854 |
| we | dla_p2c | 93.044508 |
| wd_pm | ingress_dla | 89.153458 |
| wd_pm | dla | 85.559558 |
| wd_pm | per_task_dla | 93.512259 |
| wd_pm | causal_round_robin | 92.906656 |
| wd_pm | dla_p2c | 92.865978 |
| ev | ingress_dla | 90.998940 |
| ev | dla | 87.406410 |
| ev | per_task_dla | 94.733763 |
| ev | causal_round_robin | 94.306169 |
| ev | dla_p2c | 94.200181 |

## All declared contrasts

Percentage-point differences from eight equally weighted paired blocks; Student-t, df=7. Positive values favour the first arm. The last column adjusts for all 15 new contrasts.

| Trace | Contrast | Mean | Individual 95% | Within-trace 95% | All-15 95% |
|---|---|---:|---|---|---|
| we | per_task_dla_minus_ingress_dla | +3.728391 | [+2.959782, +4.497001] | [+2.590901, +4.865881] | [+2.312730, +5.144052] |
| we | dla_minus_ingress_dla | -2.996094 | [-3.665761, -2.326427] | [-3.987155, -2.005032] | [-4.229518, -1.762670] |
| we | per_task_dla_minus_causal_round_robin | +0.512936 | [+0.388551, +0.637322] | [+0.328855, +0.697018] | [+0.283838, +0.742035] |
| we | per_task_dla_minus_dla_p2c | +0.580283 | [+0.469742, +0.690824] | [+0.416690, +0.743876] | [+0.376683, +0.783882] |
| we | dla_p2c_minus_causal_round_robin | -0.067346 | [-0.081756, -0.052936] | [-0.088672, -0.046021] | [-0.093887, -0.040805] |
| wd_pm | per_task_dla_minus_ingress_dla | +4.358801 | [+3.298731, +5.418870] | [+2.789970, +5.927632] | [+2.406315, +6.311286] |
| wd_pm | dla_minus_ingress_dla | -3.593901 | [-4.576362, -2.611440] | [-5.047876, -2.139925] | [-5.403443, -1.784358] |
| wd_pm | per_task_dla_minus_causal_round_robin | +0.605603 | [+0.363761, +0.847445] | [+0.247693, +0.963513] | [+0.160167, +1.051039] |
| wd_pm | per_task_dla_minus_dla_p2c | +0.646281 | [+0.452701, +0.839862] | [+0.359795, +0.932767] | [+0.289736, +1.002827] |
| wd_pm | dla_p2c_minus_causal_round_robin | -0.040678 | [-0.090534, +0.009178] | [-0.114462, +0.033106] | [-0.132506, +0.051149] |
| ev | per_task_dla_minus_ingress_dla | +3.734823 | [+3.001976, +4.467670] | [+2.650259, +4.819387] | [+2.385031, +5.084615] |
| ev | dla_minus_ingress_dla | -3.592530 | [-4.311357, -2.873704] | [-4.656345, -2.528716] | [-4.916499, -2.268562] |
| ev | per_task_dla_minus_causal_round_robin | +0.427594 | [+0.333862, +0.521325] | [+0.288877, +0.566310] | [+0.254955, +0.600233] |
| ev | per_task_dla_minus_dla_p2c | +0.533581 | [+0.434139, +0.633024] | [+0.386413, +0.680749] | [+0.350424, +0.716739] |
| ev | dla_p2c_minus_causal_round_robin | -0.105988 | [-0.114649, -0.097326] | [-0.118807, -0.093168] | [-0.121941, -0.090034] |

## Limits

- The primary denominator is all offered tasks, including rejected tasks.
- PM and event use legacy mask-only entry conventions; immediate slot reuse can carry vehicle queue backlog. Weekend and morning have explicit entry resets.
- RSU counts, trace density, slot assignment and queue convention differ by scenario. The descriptive density plot cannot isolate a density effect.
- Incident E2c/E2d contribute four archived fleet draws; morning contributes eight joint-seed blocks. Incident round-robin is unavailable and is not imputed.
- No trace pooling, cross-trace tests, task-level tests, equivalence claims, seed replacements or outcome-based exclusions were used.
- Frozen actor weights do not imply identical observations, logits or actions; matched exogenous inputs and conservation are checked separately.
- Native two-choice and per-task placement differ in candidate sampling and reservation visibility; this is a comparison of complete implementations.

# Dissertation follow-up results — 15 September 2026

All 72 new full cells completed with eight matched blocks per study. The 32 historical controls were reused after identity and raw-accounting verification.

## Deadline attainment

| Condition | Policy | Mean attainment (%) |
|---|---|---:|
| baseline | ingress_dla | 88.3725 |
| baseline | dla | 84.8685 |
| baseline | per_task_dla | 92.5094 |
| baseline | causal_round_robin | 91.8789 |
| 07_two_choice | dla_p2c | 91.8605 |
| 08_half_speed | ingress_dla | 84.8356 |
| 08_half_speed | dla | 81.4397 |
| 08_half_speed | per_task_dla | 89.0510 |
| 08_half_speed | causal_round_robin | 88.2271 |
| 09_second_actor | ingress_dla | 89.5134 |
| 09_second_actor | dla | 86.0730 |
| 09_second_actor | per_task_dla | 93.0523 |
| 09_second_actor | causal_round_robin | 92.5026 |

## Declared paired contrasts

Differences are percentage points. Positive values favour the first policy. The final interval adjusts across all ten new contrasts; the CSV/JSON also retains individual and within-study intervals.

| Study | Contrast | Mean difference | Within-study 95% interval | All-ten 95% interval |
|---|---|---:|---|---|
| 07_two_choice | per_task_minus_two_choice | +0.6489 | [+0.5467, +0.7511] | [+0.5172, +0.7806] |
| 07_two_choice | two_choice_minus_ingress | +3.4880 | [+3.0075, +3.9685] | [+2.8689, +4.1071] |
| 07_two_choice | two_choice_minus_round_robin | -0.0184 | [-0.0417, +0.0049] | [-0.0484, +0.0117] |
| 08_half_speed | per_task_dla_minus_ingress_dla | +4.2153 | [+3.9994, +4.4313] | [+3.9545, +4.4762] |
| 08_half_speed | dla_minus_ingress_dla | -3.3959 | [-3.8852, -2.9066] | [-3.9871, -2.8048] |
| 08_half_speed | per_task_dla_minus_causal_round_robin | +0.8239 | [+0.7937, +0.8540] | [+0.7875, +0.8602] |
| 08_half_speed | change_in_per_task_minus_round_robin_gap | +0.1933 | [+0.0617, +0.3250] | [+0.0343, +0.3524] |
| 09_second_actor | per_task_dla_minus_ingress_dla | +3.5390 | [+3.0125, +4.0654] | [+2.8607, +4.2172] |
| 09_second_actor | dla_minus_ingress_dla | -3.4404 | [-3.8759, -3.0048] | [-4.0015, -2.8792] |
| 09_second_actor | per_task_dla_minus_causal_round_robin | +0.5497 | [+0.4580, +0.6414] | [+0.4315, +0.6679] |

## Interpretation boundaries

- These are follow-ups on the existing eight seed pairs, outside the original sealed confirmation family. They do not add independent traces or independent training seeds.
- Native two-choice samples with replacement from the substep backlog snapshot. Its comparison with causal per-task placement includes differences in reservation visibility.
- Half-speed changes RSU service capacity; the declared difference-in-differences tests whether the per-task/round-robin gap grows.
- The second actor was trained on a different fleet distribution with the same training seed. This is a bounded actor sensitivity test.
- Actor weights are frozen within each comparison; endogenous action differences are allowed and recorded.
- Intervals assume independent approximately normal block effects and remain conditional on the selected trace/model. An interval crossing zero is inconclusive, not proof of equivalence.

## Evidence

- `ANALYSIS.json`: exact block effects, all interval families and arm means.
- `CELL_RESULTS.csv`: all 72 new and 32 reused cells, with offered denominators.
- `PAIRED_EFFECTS.csv`: the ten predeclared contrasts.
- `PROTOCOL.md`, execution seal, qualification and validation receipts: design and provenance.

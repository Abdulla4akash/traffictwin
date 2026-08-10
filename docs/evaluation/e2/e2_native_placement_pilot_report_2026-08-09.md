# E2 native-placement pilot report — 9 August 2026

## Status

The bounded one-seed E2 pilot completed all declared instrumentation, review,
repeat-smoke, path, accounting, and conservation gates. This is descriptive
pilot evidence only, not confirmatory or multi-seed evidence.

## Direct arm observations

| Arm | Offered | Admitted | Deadline met | Offered attainment | Admitted attainment |
|---|---:|---:|---:|---:|---:|
| `off` | 13,076,234 | 11,661,973 | 8,939,165 | 0.683619229 | 0.766522526 |
| `jsq` | 13,076,234 | 12,140,886 | 8,835,373 | 0.675681775 | 0.727737086 |
| `dla` | 13,076,234 | 10,122,571 | 9,087,197 | 0.694939919 | 0.897716302 |

The offered denominator is all 13,076,234 offered tasks. The admitted denominator is each arm's
admitted-task count. The same offered task stream, task types, fleet assignment and vehicle-action
array were used in all arms.

| Arm | Mean latency / offered (ms) | Mean latency / admitted (ms) | Mean latency / deadline-met (ms) | Energy J / offered task |
|---|---:|---:|---:|---:|
| `off` | 17,262.118 | 12,140.312 | 46.301 | 0.468282764 |
| `jsq` | 15,923.200 | 16,980.170 | 45.244 | 0.468242424 |
| `dla` | 522.780 | 75.439 | 49.458 | 0.467996252 |

Energy uses offered tasks as its explicit denominator. Latency values use the denominators named
in their column headings; rejected offered tasks retain the evaluator's existing penalty-inclusive
latency treatment.

| Arm | Local MQD rejected | V2I cap rejected | V2I gate rejected | V2I unavailable | V2V MQD rejected | V2V unavailable |
|---|---:|---:|---:|---:|---:|---:|
| `off` | 34,124 | 834,120 | 0 | 138 | 545,879 | 0 |
| `jsq` | 34,124 | 355,207 | 0 | 138 | 545,879 | 0 |
| `dla` | 34,124 | 0 | 2,373,522 | 138 | 545,879 | 0 |

| Arm | Type-1 completion | Type-2 completion | Type-3 completion | Local share | V2I share | V2V share |
|---|---:|---:|---:|---:|---:|---:|
| `off` | 0.587190622 | 0.748448739 | 0.683284173 | 0.534968937 | 0.202840436 | 0.262190628 |
| `jsq` | 0.584710854 | 0.732988875 | 0.677678981 | 0.534968937 | 0.202840436 | 0.262190628 |
| `dla` | 0.589146220 | 0.778534672 | 0.687086396 | 0.534968937 | 0.202840436 | 0.262190628 |

## Native path and forwarding evidence

Every arm recorded 2,652,389 V2I attempts. The ingress counts were identical:
`[602163, 336491, 304428, 381844, 104157, 242968, 288519, 50591, 56306, 284922]`.

| Arm | V2I admitted | Forwarded admitted | Forwarded share of admitted V2I | Maximum execution share | Execution-share range |
|---|---:|---:|---:|---:|---:|
| `off` | 1,818,131 | 0 | 0.000000000 | 0.126485935 | 0.098660108 |
| `jsq` | 2,297,044 | 2,067,204 | 0.899940968 | 0.100238829 | 0.000457980 |
| `dla` | 278,729 | 232,729 | 0.834965145 | 0.240014494 | 0.240014494 |

Actual execution counts by RSU were:

- `off`: `[229968, 229665, 229541, 229022, 104157, 229661, 229772, 50591, 56306, 229448]`;
- `jsq`: `[229793, 229655, 230002, 229381, 229904, 230253, 230032, 229325, 229498, 229201]`;
- `dla`: `[66743, 66899, 66772, 52223, 26092, 0, 0, 0, 0, 0]`.

The imbalance diagnostic is deterministically defined as maximum minus minimum per-RSU execution
share. The complete ingress-to-execution matrices and selected-target counts are in
[`e2_native_placement_path_forwarding_summary_v1.json`](e2_native_placement_path_forwarding_summary_v1.json).
All forwarding-latency totals and means were exactly zero, as required by the locked zero-backhaul
design.


## Declared contrasts

- Placement contrast, JSQ minus off: offered-task attainment difference
  `-0.007937454`;
  direct observation: lower observed offered-task attainment.
- Admission contrast, DLA minus JSQ: offered-task attainment difference
  `+0.019258144`;
  direct observation: higher observed offered-task attainment. `dla` is JSQ
  placement plus deadline-aware admission, not deadline-aware placement alone.
- The DLA-minus-off row in the comparison JSON is a joint
  placement-plus-admission contrast.

Queue balance and deadline attainment are reported separately; a reduction in
imbalance is not treated as proof of better deadlines.

The placement contrast was mixed. JSQ admitted 478,913 more tasks, all of them V2I, and reduced
V2I cap rejection by the same count. It also lowered the execution-share range by `0.098202128`
and mean penalty-inclusive latency per offered task by 1,338.918 ms. However, admitted-task mean
latency increased by 4,839.858 ms, offered-task attainment decreased by `0.007937454`, and
admitted-task attainment decreased by `0.038785440` in this draw.

The admission contrast also represents a trade-off. DLA admitted 2,018,315 fewer tasks than JSQ,
replacing 355,207 cap rejections with 2,373,522 deadline-gate rejections. Offered-task attainment
increased by `0.019258144`, admitted-task attainment by `0.169979215`, and penalty-inclusive mean
latency per offered task fell by 15,400.420 ms. Its execution-share range increased by
`0.239556514`; this does not support describing DLA as a balancing improvement.

## Integrity, review and conservation

- Frozen E2 manifest SHA-256:
  `53bcd2e26b913b64ce0c4546da7c01cb7f9290382a036a20ce9fd28229ed02a8`.
- Reviewed TrafficTwin pre-run commit:
  `b2ce160c64a3ce6e9fef9f23cdb52c9ee1940dbb`.
- Reviewed vec_env instrumentation commit:
  `e11f4445a9cc939a79d4f419c6f48b43ce110664`.
- tos-data commit: `a75bbdb1a956f828ee0e9b97b33506bd32d31b85`.
- Independent Claude verdict: `APPROVE` after the requested changes and re-review.
- Instrumentation no-effect: exact agreement for all pre-existing scientific summaries and arrays
  in matched `off`, `jsq` and `dla` checks, excluding wall-clock and additive fields.
- Two-RSU production-path probe: 34/34 checks passed.
- Repeated smokes: both ten-step repeats passed for all three arms with byte-identical existing
  arrays within arm.
- Full arms: `off` 99/99 checks, `jsq` 98/98 and `dla` 98/98; no failed checks.
- Cross-arm identity: offered count, `task_active`, `task_type`, fleet assignment and vehicle
  actions were exact. JSQ actor logits were byte-identical to off. DLA logits had maximum absolute
  difference `2.384185791015625e-7`, below the predeclared diagnostic tolerance, while the vehicle
  action array remained byte-identical.
- V2I service work conserved in every arm: offered work equalled admitted plus
  rejected/unavailable work.
- Vehicle service work conserved in every arm: offered work equalled admitted plus rejected work.
- Every task reconciled to the unchanged outcome taxonomy; no task silently disappeared.
- All task-level path arrays reconciled exactly to the path aggregates. Rejected and unavailable
  tasks were never recorded as executed or forwarded.

Raw evidence is outside Git under
`/Users/akashx/AntigravityTest/e2_outputs/e2-native-placement-pilot-v1`. Exact arm locators and
permission-safe hashes are recorded in
[`e2_native_placement_evidence_index_v1.json`](e2_native_placement_evidence_index_v1.json). The
root checksum ledger independently verified every listed retained artifact.

## Validity and limitations

- One evaluator seed and one fleet draw; no fleet-seed confidence interval or population inference.
- Tasks are accounting records, not independent statistical replicates.
- The frozen 17-dimensional vehicle actor does not observe current RSU load.
- Zero backhaul represents ideal fibre; nonzero forwarding cost is deferred to an unauthorised later E3 gate.
- The current evaluator reports deadline success, not physical task-return completion.
- No ordinary-traffic control, scaling, P2C, learning, retraining, or Kubernetes deployment was tested.

## Exit decision

The single authorised E2 pilot is complete. No additional seed, P2C/DLA-P2C arm, nonzero-backhaul
run, E3 sensitivity, scaling experiment, prediction, learning or retraining is authorised. The
exact next gate is researcher review.

# E2 — Native Infrastructure Placement Pilot

## Purpose

Test whether infrastructure-side least-busy execution placement changed offered-task deadline attainment relative to strongest-link execution, with the 17-dimensional vehicle actor frozen.

## Design

One Manchester incident draw (fleet seed 0), 3,600 steps, 2.5× cap, fixed 1× service and zero forwarding latency. Native output-only path instrumentation distinguished ingress, selected target, actual execution and forwarding.

## Results

| Arm | Meaning | Offered attainment | Admitted attainment | Admitted tasks | V2I admitted | Forwarded |
|---|---|---:|---:|---:|---:|---:|
| `off` | Strongest-link/default | 0.683619229 | 0.766522526 | 11,661,973 | 1,818,131 | 0 |
| `jsq` | Inherited least-busy, ordinary admission | 0.675681775 | 0.727737086 | 12,140,886 | 2,297,044 | 2,067,204 |
| `dla` | Inherited least-busy + deadline-aware admission | 0.694939919 | 0.897716302 | 10,122,571 | 278,729 | 232,729 |

`jsq - off = −0.007937454` offered attainment. Execution became almost uniform across ten RSUs, yet the deadline result worsened. `dla` improved offered attainment but gate-rejected 2,373,522 V2I tasks and changed both placement and admission.

## Decision

E2 was a descriptive pilot. It showed that balance is not automatically deadline benefit, but could not identify whether DLA's improvement came from placement or admission. E2b added the missing factorial cell.

## Authoritative identities

- Final evidence commit: `c05736125a401b8176c53212b3915ec57b95fdc3`
- Manifest SHA-256: `53bcd2e26b913b64ce0c4546da7c01cb7f9290382a036a20ce9fd28229ed02a8`

## Public evidence and data

- [Arm summary](data/e2_arm_summary.csv)
- [Byte-identical path/forwarding summary](evidence/e2_native_placement_path_forwarding_summary_v1.json)
- [Public-sanitized comparison](evidence/e2_native_placement_pilot_comparison_v1_public_sanitized.json)
- [Public-sanitized validation](evidence/e2_native_placement_pilot_validation_v1_public_sanitized.json)
- [Public-sanitized manifest](evidence/e2_native_placement_pilot_manifest_v1_public_sanitized.json)

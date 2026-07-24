# Supervisor Decision Form — Gate-D Scientific Contracts

The v0.7 design (§14–15, §22.2, §25) requires **predeclared, study-specific** values for
map-matching, calibration, and comparison, and explicitly refuses software defaults. These
contracts carry scientific weight and should be agreed with the supervisor (Dr. Sandra Sampaio)
before they enter the production registries, which are intentionally empty today. Completing this
form does not accept any capability; the lead registers each agreed contract through a reviewed,
fingerprinted mechanism and reruns the affected tests.

Record decisions with a written basis (a reference, a pilot result, or an explicit engineering
rationale). "Software default" is not an acceptable basis for any of these.

## A. Map-matching policy (`MAN-09`)

| Parameter | Proposed value | Basis / reference | Cases requiring manual confirmation |
|---|---|---|---|
| Maximum site-to-edge distance (m) | | | |
| Direction tolerance (degrees) | | | |
| Road-class rule (require match? which classes equivalent?) | | | |
| Confidence categories | | | |
| Ambiguity / many-to-one handling | | | |

The deterministic synthetic harness (`src/traffictwin/integration/manchester/map_matching.py`) and
its in-page review demonstration already implement the mechanics; this form supplies the real
thresholds. Real-source matching stays blocked by
`MANCHESTER_NETWORK_LICENCE_UNAPPROVED`, `MANCHESTER_NETWORK_NOT_REVIEWED`,
`MAP_MATCH_POLICY_UNAPPROVED`, and `REAL_SOURCE_GATE_B_UNACCEPTED` until both this policy and the
network (see the OSM network worksheet) are approved.

## B. Calibration contract (`MAN-09`)

| Parameter | Proposed value | Basis / reference |
|---|---|---|
| Objective (MAE or RMSE — both implemented) | | |
| Calibrated parameters and bounds/grid | | |
| Uncertainty treatment | | |
| Development window | | |
| Held-out / out-of-window design | | |
| Minimum coverage for admission | | |

The calibration evaluator (`src/traffictwin/integration/manchester/calibration.py`) and the
day-type/season temporal-profile builder
(`src/traffictwin/integration/manchester/temporal_profile.py`) are implemented and tested; both
production registries are empty pending this contract.

## C. Comparison metric contract (`MAN-10`)

| Parameter | Proposed value | Basis / reference |
|---|---|---|
| Pairing keys (site/edge, interval) | | |
| Interval aggregation | | |
| Weighting | | |
| Missing / excluded record handling | | |
| Per-side denominators | | |
| Minimum coverage thresholds | | |
| Output precision | | |
| Interpretation wording (must stay non-causal) | | |

The comparison engine (`src/traffictwin/integration/manchester/comparison.py`) implements
MAE/RMSE and full exclusion/coverage handling; the reviewed production-contract registry
(`APPROVED_PRODUCTION_CONTRACT_FINGERPRINTS`) is empty, so goodness-of-fit values remain
unavailable until one contract is registered.

## Sign-off

| Role | Name | Date | Signature |
|---|---|---|---|
| Researcher | Abdulla Al Mamun Akash | | |
| Supervisor | Dr. Sandra Sampaio | | |

After sign-off, the lead's first task is to translate part C into one versioned
`ManchesterComparisonMetricContract` and register its fingerprint, then wire and test one real
observed-versus-simulated comparison (the shortest chain, since it does not need the SUMO network).

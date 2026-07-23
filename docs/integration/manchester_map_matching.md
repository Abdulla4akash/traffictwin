# Manchester map-matching candidate (`MAN-09`)

This library establishes the first fail-closed boundary for observation-to-SUMO map matching. It
does **not** enable real Manchester matching or create a SUMO baseline. `MAN-09` remains planned.

## Current real-source status

`current_map_matching_preflight()` reports `unavailable` with all four current blockers:

- no reviewed Manchester SUMO network;
- no approved licence for that network;
- no approved distance/direction/road-class matching policy; and
- real-source Gate-B acquisition/projection dependencies are not accepted.

Candidate generation, confidence classification, analyst acceptance, calibration, and SUMO
baseline creation remain unavailable for real evidence. Visual proximity never establishes an
edge identity, and no observation is converted directly into traffic demand.

These blockers correspond to the unresolved network and policy decisions in the
[v0.7 design](../traffictwin-design-v0_7.md#25-open-decisions-and-evidence-still-required).

## Synthetic-only harness

The module provides a deterministic harness so matching mechanics can be tested without
pretending that synthetic rules are scientifically accepted:

1. Build a fully admitted `SpatialAdmissionReport` containing only source=`synthetic` points.
2. Bind clearly synthetic WGS84 SUMO-edge fixtures to a synthetic network SHA-256 and the active
   PyProj/PROJ runtime.
3. Declare a `SyntheticMapMatchingPolicy` containing test-only distance, direction, and optional
   road-class thresholds.
4. Call `evaluate_synthetic_map_matches(request)`.
5. Inspect every point-by-edge feature row and record an explicit analyst decision with
   `record_synthetic_map_match_review(...)`.

The service transforms fixture coordinates from EPSG:4326 to EPSG:27700 for bounded planar
distance inspection. For every observation/edge pair it deterministically records:

- closest directed edge segment;
- distance in metres, rounded to 0.001 m;
- directed segment bearing and optional direction delta, rounded to 0.001 degrees;
- optional exact road-class equality;
- independent distance, direction, and road-class gate outcomes; and
- typed reasons for every outcome.

The complete Cartesian product is retained and reconciled. Candidate order is stable by point,
distance, and edge ID. No candidate is automatically selected, and the only confidence label is
`synthetic_rule_only`.

## Manual review boundary

A review must contain exactly one typed decision per observation. A selected candidate must:

- belong to the same report and observation;
- pass all declared synthetic policy gates; and
- use the typed `SYNTHETIC_FIXTURE_SELECTION` reason.

Rejections use `NO_SUITABLE_CANDIDATE` or `AMBIGUOUS_CANDIDATES`. Reviewer names and free text are
not stored. Even a complete synthetic review structurally keeps real map-match acceptance,
calibration, and baseline availability false.

## Safety and scientific limits

- Only admitted `source=synthetic` spatial results are accepted.
- Network and edge models are structurally synthetic and cannot claim Manchester review or a real
  licence.
- Input points and edges are bounded, uniquely identified, sorted, fingerprinted, and fully
  reconciled.
- Runtime projection versions are recorded and validated.
- Reports re-compute all candidate rows and counts during model validation, so stored measurements,
  gates, fingerprints, or counts cannot drift independently.
- The harness does not parse a SUMO network, access the network, infer road class/direction,
  calibrate demand, run SUMO, compare observations, or produce VEC evidence.
- Synthetic software tests do not validate Manchester geography, matching quality, calibration,
  traffic realism, or scientific confidence.

## Remaining acceptance work

Real `MAN-09` implementation still requires:

1. one reviewed Manchester SUMO network with exact bytes, construction method, CRS, boundary,
   version, licence, and publication decision;
2. accepted real-source projections from Gate B;
3. a reviewed distance/direction/road-class policy and confidence categories;
4. explicit analyst ambiguity and override rules;
5. a temporal-profile and bounded calibration contract with uncertainty and residuals; and
6. real/golden acceptance evidence plus integration through the controlled SUMO service.

Until those gates pass, the application must render the preflight blockers and keep “Prepare SUMO
baseline” disabled.

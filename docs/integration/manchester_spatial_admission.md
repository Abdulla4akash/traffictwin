# Manchester geographic spatial admission (`MAN-07` candidate)

## Purpose

`src/traffictwin/integration/manchester/spatial.py` is the deterministic gate between a
coordinate-bearing source record and a future Manchester geographic map. It records the source
and target CRS, transformation runtime, coordinate bounds, point meaning, uncertainty, scope
evidence, and a typed admission or exclusion result. It performs no network access, boundary
inference, map matching, interpolation, or proximity join.

This is candidate Gate-B evidence. It does not enable the `MAN-08` map, accept a source adapter,
resolve a geographic boundary, or change `MAN-07` from `planned`.

## Source policy

| Source | Required coordinate evidence | Required scope evidence | Geographic result |
|---|---|---|---|
| DfT | Published EPSG:27700 and WGS84 pair agreeing within 2.5 m | Audited Manchester local-authority binding `E08000003` / `85` | Admitted when both checks pass |
| TfGM signals | Published EPSG:27700 and WGS84 pair agreeing within 2.5 m | Audited Greater Manchester authority dataset | Admitted as static signal infrastructure only |
| WebTRIS | Published WGS84 point | Fingerprint of an explicitly selected strategic-road site | Admitted as a strategic-road detector, not Manchester-wide coverage |
| BODS SIRI-VM | Profile-documented WGS84 point | Fingerprint of the accepted request bounding box | Admitted in that request box as a transit-vehicle position; this establishes neither Greater Manchester scope nor Bee Network membership |
| Randy/TOS | No geographic projection in the accepted sanitised pack | Unavailable | Excluded from the geographic map |
| SUMO/VEC and analysis RSUs | Source-local/generated coordinates without a reviewed network projection binding | Unavailable | Excluded from the geographic map |
| Synthetic | Explicit WGS84 fixture contract and synthetic label | Synthetic scope artifact | Admitted only as clearly labelled synthetic evidence |

For dual-coordinate sources, the declared WGS84 coordinate remains the rendered value. The
EPSG:27700-to-EPSG:4326 transform is used only to validate agreement. The policy artifact records
the exact `pyproj` and PROJ runtime versions and `always_xy=true`.

## Decisions and reconciliation

`evaluate_spatial_admission(...)` gives every point one result. Admitted points have exact
single-point WGS84 bounds and one of two reasons:

- `direct_wgs84_admitted`; or
- `dual_coordinates_admitted` with the measured conversion error.

Excluded points retain a stable reason covering inactive/unavailable source state, missing or
unknown coordinates, absent dual evidence, coordinate disagreement, missing/wrong scope evidence,
wrong point semantics, or an absent geographic projection. Exclusions never carry target
coordinates or become map-renderable.

`evaluate_spatial_batch(...)` sorts inputs by canonical fingerprint, refuses duplicate evidence
and duplicate source records, and reconciles admitted, coordinate, scope, and source-state counts.
An empty or wholly excluded batch is explicitly `unavailable`; a mixed batch is `partial`.

## Usage

```python
from traffictwin.integration.manchester import (
    evaluate_spatial_admission,
    webtris_spatial_evidence,
)

evidence = webtris_spatial_evidence(
    accepted_site_record,
    selection_fingerprint=accepted_site_selection.fingerprint(),
)
decision = evaluate_spatial_admission(evidence)

if decision.map_rendering_available:
    longitude = decision.longitude
    latitude = decision.latitude
else:
    disabled_reason = decision.reason
```

The adapter helpers preserve the original source-record fingerprint and synthetic marker. A
synthetic fixture from an official source remains both, for example `source="dft"` and
`synthetic=true`; test evidence is never silently relabelled observed.

## Fail-closed boundaries

- A Manchester label, road name, request bounding box, or visible map proximity does not establish
  identity, service membership, equal coverage, or a cross-source join.
- BODS geographic admission does not establish Bee Network membership.
- TfGM signal points do not provide phases, timings, queues, incidents, traffic counts, or live
  state.
- DfT/WebTRIS/TfGM/BODS admission does not make their data mutually comparable or temporally
  aligned.
- Randy, SUMO, VEC, and analysis-site coordinates remain usable in clearly non-geographic views
  where their own contracts permit it; this gate does not reinterpret them as latitude/longitude.
- Source scopes are not inferred from a loose Manchester bounding box. A future boundary layer is
  a separately versioned reference artifact.

## Verification

```bash
.venv/bin/pytest -q tests/unit/test_manchester_spatial.py
.venv/bin/ruff check \
  src/traffictwin/integration/manchester/spatial.py \
  tests/unit/test_manchester_spatial.py
.venv/bin/mypy --strict \
  src/traffictwin/integration/manchester/spatial.py \
  tests/unit/test_manchester_spatial.py
```

The focused suite covers the complete policy matrix, direct and dual admission, measured
coordinate disagreement, every exclusion family, scope/geometry mismatches, synthetic lineage,
order independence, duplicate refusal, strict mutation failures, and repository fixtures for all
four public-source families.

## Evidence basis

- [TrafficTwin v0.7 design](../traffictwin-design-v0_7.md), §§9–12, 20–22 and Appendix A
- [ADR-056: Manchester map rendering and attribution](../decisions/ADR-056-manchester-map-rendering-and-attribution.md)
- [Manchester Gate-A source audit](manchester-source-gate-a-audit-v0_7.md)

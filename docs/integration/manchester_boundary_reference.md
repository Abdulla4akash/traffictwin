# Official Manchester boundary display reference

TrafficTwin packages two exact, hash-verified GeoJSON display derivatives so Manchester Operations
has official geographic context without contacting a tile service:

| Scope | Official code | ONS product | Packaged SHA-256 |
|---|---|---|---|
| Manchester local authority | `E08000003` | Local Authority Districts (December 2025) Boundaries UK BGC | `31b78ea21882ec80a82b0cc584a57e0b1d1a4f1c8269e1bfc54826fb9981a51c` |
| Greater Manchester Combined Authority | `E47000001` | Combined Authorities (December 2025) Boundaries EN BGC | `1bf8a1293de43f1573ec87685e0772ec8b9bd4cb14ec0ae0b0c21cd80d9a313a` |

The public-authoritative ONS ArcGIS items are pinned as
`54b2a8f849f743aea669488cab415c8f` and `8b6547b5908a4c90a2d63baf9543c5fb`.
The assets are server-generalised display derivatives of the BGC products, requested in EPSG:4326
with `maxAllowableOffset=0.001` and `geometryPrecision=4`. The library checks the exact asset hash,
FeatureCollection shape, CRS, official code/name, Polygon closure, finite coordinates, and a
conservative regional coordinate bound before returning renderer-ready features.

Both attribution lines are always rendered:

- `Source: Office for National Statistics licensed under the Open Government Licence v.3.0`
- `Contains OS data © Crown copyright and database right 2025`

## Interpretation boundary

These polygons are context, not evidence of roads or sensor coverage. They do not clip or admit
scientific records, map a record to a road, prove source coverage, replace the source-specific
request bounding box, or turn National Highways Strategic Road Network records into city-wide
telemetry. The external basemap remains disabled. This resolves the missing official boundary
context in the UI, not the missing city-road traffic feed.

The code and assets live in
`src/traffictwin/integration/manchester/boundary_reference.py` and
`src/traffictwin/integration/manchester/boundary_data/`. `MAN-08` remains `planned` until its full
capability and release gates are reconciled.

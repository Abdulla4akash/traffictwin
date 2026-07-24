# Manchester SUMO Network Decision Worksheet (`MAN-09`)

Map matching, calibration, and any SUMO baseline are blocked until a Manchester SUMO network is
approved with a licence, CRS, date, construction method, and deterministic regeneration recipe.
This worksheet captures the exact decisions the design (§10, §14, §25 questions 1 and 5) and the
map-matching preflight blockers require. Filling it in does not accept any capability; the lead
then produces the network under a reviewed ADR with pinned hashes before any real matching runs.

## A. Boundary and scope (design open question 1)

| Decision | Value |
|---|---|
| Study boundary: Manchester local authority (E08000003) **or** all ten Greater Manchester boroughs | |
| Boundary geometry source and version | |
| Reason for the choice | |

The chosen boundary defines the OSM extract envelope and must match the geographic scope used for
DfT (local authority) versus wider layers. It is separate from the caller-declared National
Highways operational envelope and from the ONS display polygons.

## B. Source data and extract

| Decision | Value |
|---|---|
| Source (recommended: OpenStreetMap) | |
| Exact extract provider (e.g. Geofabrik) and file | |
| Extract date to pin | |
| Licence (OSM is ODbL 1.0 — confirm acceptable) | |
| Required attribution string | © OpenStreetMap contributors, ODbL 1.0 |

## C. Construction (SUMO netconvert)

| Decision | Value |
|---|---|
| SUMO version (repository baseline: 1.27.1) | |
| `netconvert` version | |
| Exact `netconvert` options / typemap | |
| Road classes retained | |
| Simplification / cleanup steps | |

## D. Projection and CRS

| Decision | Value |
|---|---|
| Source CRS (OSM WGS84 / EPSG:4326) | EPSG:4326 |
| SUMO network CRS / projection | |
| Distance CRS for matching (repository uses EPSG:27700) | EPSG:27700 |
| Coordinate uncertainty basis | |

## E. Deterministic regeneration

| Requirement | Confirmation |
|---|---|
| Extract date, boundary polygon, and tool versions pinned | |
| Regeneration command recorded and byte-reproducible | |
| Network SHA-256 recorded before binding | |
| ODbL attribution stored in the network's source/licence record | |

## Sign-off

| Role | Name | Date |
|---|---|---|
| Researcher | Abdulla Al Mamun Akash | |
| Supervisor (if network affects scientific scope) | Dr. Sandra Sampaio | |

After approval, the lead's first task is to add a reviewed ADR pinning A–E, generate the network
with the recorded recipe, record its SHA-256, and build a real `SyntheticSumoNetworkBinding`
replacement bound to the approved network — at which point the map-matching preflight blockers
`MANCHESTER_NETWORK_LICENCE_UNAPPROVED` and `MANCHESTER_NETWORK_NOT_REVIEWED` can be lifted for the
matching policy from the supervisor decision form.

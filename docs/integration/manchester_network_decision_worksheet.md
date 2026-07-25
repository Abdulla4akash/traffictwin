# Manchester SUMO Network Decision Worksheet (`MAN-09`)

Map matching, calibration, and any SUMO baseline are blocked until a Manchester SUMO network is
approved with a licence, CRS, date, construction method, and deterministic regeneration recipe.
This worksheet captures the exact decisions the design (§10, §14, §25 questions 1 and 5) and the
map-matching preflight blockers require. Filling it in does not accept any capability; the lead
then produces the network under a reviewed ADR with pinned hashes before any real matching runs.

**Status:** sections A–E answered by the repository owner on 25 July 2026. The decisions are
implemented by [ADR-059](../decisions/ADR-059-greater-manchester-baseline-network.md) and the
[Greater Manchester baseline network foundation](manchester_baseline_network.md). Answering this
worksheet accepts **no capability**: it satisfies design Gate-D step 1 (network binding) only,
which is the first of `MAN-09`'s seven acceptance components. `MAN-09` remains `planned`.

## A. Boundary and scope (design open question 1)

| Decision | Value |
|---|---|
| Study boundary: Manchester local authority (E08000003) **or** all ten Greater Manchester boroughs | **Greater Manchester** (all ten boroughs, combined-authority code `E47000001`) is the primary baseline network scope. **Manchester local authority (`E08000003`) remains a selectable sub-area/filter**, not a second baseline network. |
| Boundary geometry source and version | Identity from ONS December 2025 boundaries already packaged in this repository: `Combined_Authorities_December_2025_Boundaries_EN_BGC` (`E47000001`) and `Local_Authority_Districts_DEC_2025_Boundaries_UK_BGC` (`E08000003`). The packaged GeoJSON is **BGC generalised (20 m), coastline clipped, 4-decimal display geometry** and is therefore used for **identity and derived-envelope context only**, never as a scientific clipping boundary. |
| Reason for the choice | The baseline must contain Manchester City Centre and the University of Manchester area, and must also carry the strategic approaches and neighbouring boroughs those areas depend on. A Manchester-local-authority-only network would cut the through-routes that reach the city centre. Greater Manchester keeps one baseline network while the local-authority filter preserves the exact scope DfT count-point evidence actually covers. |

The chosen boundary defines the OSM extract envelope and must match the geographic scope used for
DfT (local authority) versus wider layers. It is separate from the caller-declared National
Highways operational envelope and from the ONS display polygons.

**Recorded consequence.** The Greater Manchester scope is **wider than** the reviewed National
Highways operational envelope (latitude 53.30–53.70, longitude −2.60–−1.90): Greater Manchester
extends west to approximately longitude −2.7304. The two envelopes are not interchangeable and are
never reported as equal coverage.

## B. Source data and extract

| Decision | Value |
|---|---|
| Source (recommended: OpenStreetMap) | **OpenStreetMap** |
| Exact extract provider (e.g. Geofabrik) and file | **Geofabrik**, `https://download.geofabrik.de/europe/united-kingdom/england/greater-manchester-latest.osm.pbf`, with its published `.md5` companion. The provider, host, and path family are pinned in the endpoint policy; no caller-supplied URL is accepted. |
| Extract date to pin | **25 July 2026** (`osm_reference_date`). The date is recorded in the acquisition receipt and rebound on every replay. |
| Licence (OSM is ODbL 1.0 — confirm acceptable) | **ODbL 1.0 — accepted** by the repository owner on 25 July 2026. Licence URI `https://opendatacommons.org/licenses/odbl/1-0/`. Accepted raw extracts stay `private` (workspace-only, excluded from Git); derived networks are `redistributable_derived` subject to the share-alike obligation being honoured at publication review. |
| Required attribution string | © OpenStreetMap contributors, ODbL 1.0 |

## C. Construction (SUMO netconvert)

| Decision | Value |
|---|---|
| SUMO version (repository baseline: 1.27.1) | **1.27.1** — required exactly; a different observed version fails the build closed with `SUMO_VERSION_DRIFT`. |
| `netconvert` version | **Eclipse SUMO netconvert 1.27.1** (observed build features recorded in the command receipt). |
| Exact `netconvert` options / typemap | Fixed reviewed argument vector, not caller-supplied. `--osm-files <input>`, `--output-file <output>`, `--osm.bike-access false`, `--osm.sidewalks false`, `--geometry.remove`, `--ramps.guess`, `--junctions.join`, `--tls.guess-signals`, `--tls.discard-simple`, `--tls.join`, `--no-turnarounds`, `--offset.disable-normalization false`, `--proj.plain-geo false`, `--numerical-ids`, `--seed 42`, `--xml-validation never`, `--no-internal-links false`. The full frozen vector lives in `network_build.py` as `NETCONVERT_FIXED_ARGUMENTS`; the operator selects none of it. |
| Road classes retained | Motorway, trunk, primary, secondary, tertiary, unclassified, residential and their `_link` variants, via the reviewed `--keep-edges.by-vclass passenger` / typemap defaults. Service, track, footway, cycleway, and path geometry is excluded from the driveable baseline. |
| Simplification / cleanup steps | `--geometry.remove` (collapse redundant shape points), `--junctions.join` (merge cluster junctions), `--ramps.guess`, `--tls.discard-simple` and `--tls.join`. No manual post-editing; the network is exactly what the frozen recipe produces. |

## D. Projection and CRS

| Decision | Value |
|---|---|
| Source CRS (OSM WGS84 / EPSG:4326) | EPSG:4326 |
| SUMO network CRS / projection | **UTM zone 30N (EPSG:32630)**, selected by `netconvert`'s default `--proj.utm` for this longitude band and recorded verbatim from the produced `<location>` element's `projParameter`. The network's own `netOffset`, `convBoundary`, and `origBoundary` are read back and pinned; TrafficTwin never re-derives or overrides them. |
| Distance CRS for matching (repository uses EPSG:27700) | EPSG:27700 |
| Coordinate uncertainty basis | The packaged ONS display geometry is BGC-generalised to 20 m and rounded to 4 decimal degrees, so the derived extract envelope carries **at least 20 m** boundary uncertainty plus an explicitly recorded margin. This uncertainty applies to the *envelope*, not to OSM geometry itself, whose positional accuracy is not asserted by TrafficTwin. No coordinate is silently clipped or reinterpreted. |

## E. Deterministic regeneration

| Requirement | Confirmation |
|---|---|
| Extract date, boundary polygon, and tool versions pinned | **Yes.** `NetworkBuildInputManifest` pins the OSM extract SHA-256 and byte size, the reference date, the boundary scope identity, the derived envelope, and the observed SUMO/netconvert version. |
| Regeneration command recorded and byte-reproducible | **Yes for the command; semantic identity for the output.** The exact argument vector and observed tool version are recorded in `NetworkBuildCommandReceipt`. Re-running identical accepted inputs reproduces the same **semantic network identity** (`network_identity_sha256`, computed over the canonicalised node/edge/connection structure with the volatile XML header removed). Byte-level equality of the raw `.net.xml` is **not** claimed, because `netconvert` writes its own version banner and a generation comment; this is recorded honestly rather than asserted away. |
| Network SHA-256 recorded before binding | **Yes.** Both the raw `network_sha256` and the canonical `network_identity_sha256` are recorded before any binding is produced. |
| ODbL attribution stored in the network's source/licence record | **Yes.** `© OpenStreetMap contributors, ODbL 1.0` is carried on the acquisition receipt, the build receipt, and the resulting network binding. |

## Sign-off

| Role | Name | Date |
|---|---|---|
| Researcher | Abdulla Al Mamun Akash | 25 July 2026 |
| Supervisor (if network affects scientific scope) | Dr. Sandra Sampaio | *not yet obtained — see below* |

**Supervisor sign-off is not required for this slice and has not been claimed.** The network build
is infrastructure: it produces geometry, not a scientific result. Supervisor approval remains
required before the *matching policy*, *calibration objective*, and *comparison metric contract*
decisions on the [supervisor contract decision form](../evaluation/supervisor_contract_decision_form.md)
are accepted, and those remain open.

After approval, the lead's first task is to add a reviewed ADR pinning A–E, generate the network
with the recorded recipe, record its SHA-256, and build a real `SyntheticSumoNetworkBinding`
replacement bound to the approved network — at which point the map-matching preflight blockers
`MANCHESTER_NETWORK_LICENCE_UNAPPROVED` and `MANCHESTER_NETWORK_NOT_REVIEWED` can be lifted for the
matching policy from the supervisor decision form.

**Status of that follow-on task (25 July 2026).** The ADR is published as ADR-059 and the
deterministic builder exists. The two network blockers are **not yet lifted**: lifting them also
requires the approved real-source matching policy (`MAP_MATCH_POLICY_UNAPPROVED`) and accepted
Gate-B real-source evidence (`REAL_SOURCE_GATE_B_UNACCEPTED`), neither of which this slice
provides. `SyntheticSumoNetworkBinding` is therefore unchanged and still refuses real matching.

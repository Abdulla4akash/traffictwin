# ADR-059: Greater Manchester OpenStreetMap-to-SUMO Baseline Network

- Status: accepted (Gate-D step 1 decision; network binding only)
- Date: 2026-07-25
- Capability: `MAN-09` network-binding component only; exercises the `MAN-01` acquisition contract

## Context

Design §21 Gate D lists as its first step "Bind one reviewed Manchester SUMO network and licence",
and design §20 gives `MAN-09` the acceptance boundary "Network binding, map-match candidates,
manual ambiguity review, temporal profile, bounded calibration, residuals, and fail-closed
acceptance". Until a network exists, `map_matching.py` fails closed on
`MANCHESTER_NETWORK_LICENCE_UNAPPROVED` and `MANCHESTER_NETWORK_NOT_REVIEWED`, and the only network
binding in the repository is `SyntheticSumoNetworkBinding`, which is explicitly not a Manchester
claim.

Design §25 left two questions open that this ADR answers, using decisions supplied by the
repository owner on 25 July 2026 and recorded in the
[network decision worksheet](../integration/manchester_network_decision_worksheet.md):

- question 1 — is the case-study boundary Manchester local authority or all ten Greater Manchester
  boroughs?
- question 5 — which Manchester SUMO network, generation method, projection, date, and licence are
  approved?

## Decision

1. **Greater Manchester is the primary baseline network scope.** The single baseline network covers
   the ten-borough combined authority (`E47000001`). It must contain Manchester City Centre and the
   University of Manchester area, and this is enforced by required-inclusion probes rather than
   assumed.
2. **Manchester local authority is a selectable sub-area filter, not a second network.** `E08000003`
   is modelled as a filter over the one baseline network. Building a second baseline network for the
   local authority is explicitly refused.
3. **Source is OpenStreetMap via Geofabrik**, licence **ODbL 1.0 — accepted**, attribution
   `© OpenStreetMap contributors, ODbL 1.0`. Accepted raw extracts are `private` (workspace-only,
   never committed); derived networks are `redistributable_derived` subject to share-alike being
   honoured at publication review.
4. **The pinned extract is the dated file, not the `-latest` alias, and its two dates are kept
   separate.** Probing the provider on 25 July 2026 established that
   `greater-manchester-latest.osm.pbf` responds `302 Found` and redirects to a dated file, so
   pinning `-latest` would make the baseline non-reproducible by construction. The dated file is
   pinned instead and is served directly with no redirect, which is why the transport allows zero
   redirects. Design §3.1 ("observation time is not retrieval time") applies to the two dates:

   | Field | Value | Meaning |
   |---|---|---|
   | `reference_date` | 2026-07-25 | Operator decision and retrieval date |
   | `extract_data_cutoff_date` | 2026-07-24 | OSM data cutoff encoded in the provider's filename |

   **The owner's requested 25 July 2026 extract does not exist.** `greater-manchester-260725.osm.pbf`
   returns HTTP 404; the newest published extract is `greater-manchester-260724.osm.pbf`, itself
   served with `Last-Modified: Sat, 25 Jul 2026 00:29:36 GMT`. Rather than relabel a 24 July extract
   as a 25 July one, both dates are recorded and a test asserts they never collapse into one value.
5. **The ONS boundary assets provide identity and a derived envelope only.** The packaged GeoJSON is
   BGC-generalised to 20 m, coastline clipped, and rounded to 4 decimal degrees. It is **not** used
   as a scientific clipping boundary — `boundary_reference.py` already declares
   `scientific_clipping_available = False`, and this ADR does not override that. The extract
   envelope derived from it is labelled `derived_from_display_geometry` and carries an explicit
   uncertainty statement and margin.
6. **Construction uses SUMO 1.27.1 `netconvert` through one fixed reviewed argument vector.** The
   operator selects no argument, no host, no URL, no path, and no tool name. An observed version
   other than 1.27.1 fails the build closed with `SUMO_VERSION_DRIFT`.
7. **Projection is read back from the produced network, never asserted.** `netconvert` selects UTM
   zone 30N for this longitude band; the produced `<location>` element's `projParameter`,
   `netOffset`, `convBoundary`, and `origBoundary` are read verbatim and pinned into the binding.
   TrafficTwin never re-derives, overrides, or silently reprojects them. Distance work elsewhere
   continues to use EPSG:27700.
8. **Determinism is claimed at semantic identity, not byte identity.** This was measured, not
   assumed (see Consequences).

## Consequences

### Determinism, stated honestly

Two `netconvert` 1.27.1 runs over identical inputs produce `.net.xml` files whose **raw bytes
differ**. The observed differences are exactly two, both inside the leading XML comment banner:

- the generation timestamp (`generated on 2026-07-25T03:14:09... ` vs `...T03:14:15...`);
- the echoed `--output-file` value.

After removing XML comments and normalising trailing whitespace, the two outputs are
**byte-identical**, giving the same SHA-256. The build therefore records two digests:

| Digest | Meaning |
|---|---|
| `network_sha256` | Raw `.net.xml` bytes. Reproducible only within a single run; **not** stable across runs. |
| `network_identity_sha256` | Canonical form with comments removed and trailing whitespace normalised. **Stable across runs** and is the digest a rebuild is verified against. |

Claiming byte-level reproducibility here would be false, so it is not claimed. The unavoidable
nondeterminism is confined to a generation banner that carries no network semantics.

### Environment observation

In the reviewed environment `netconvert` emits `pj_obj_create: Cannot find proj.db` twice on stderr
while still exiting successfully and writing a valid UTM projection. This is captured verbatim in
the command receipt's warning list rather than suppressed. It does not alter the recorded
`projParameter`.

### What this ADR does not do

This ADR accepts **no capability**. It satisfies Gate-D step 1 only, which is the first of
`MAN-09`'s seven acceptance components. It provides:

- no map matching and no matching thresholds;
- no analyst ambiguity review;
- no temporal profile;
- no calibration objective, parameters, bounds, or uncertainty treatment;
- no residuals and no accepted `ManchesterSumoBaseline`;
- no comparison metric contract.

`MAN-09` therefore stays `planned` and practically `foundation_only`; Gate D stays
`foundation_only`. The map-matching blockers `MANCHESTER_NETWORK_LICENCE_UNAPPROVED` and
`MANCHESTER_NETWORK_NOT_REVIEWED` are **not lifted**, because lifting them additionally requires
`MAP_MATCH_POLICY_UNAPPROVED` and `REAL_SOURCE_GATE_B_UNACCEPTED` to be resolved, and neither is in
scope here. `SyntheticSumoNetworkBinding` is unchanged.

A built network is geometry. It is not calibration, not validation, not live traffic, and not VEC
execution, and must never be described as any of them.

### DfT calibration coverage

DfT count-point observations cover **Manchester local authority only**. Within the Greater
Manchester baseline this is partial coverage. Locations outside the local-authority filter are
labelled `uncovered`/`unavailable` and are **never** filled with zero, because absence of a survey
point is not absence of traffic. This is encoded structurally in `DftCalibrationCoverage` rather
than left to documentation.

### Scope relationships

Greater Manchester (west to approximately longitude −2.7304) is **wider** than the reviewed National
Highways operational envelope (longitude −2.60 to −1.90). The two are separate envelopes and are
never reported as equal coverage. Both remain separate from the ONS display polygons.

## Alternatives considered

- **Manchester local authority as the baseline network.** Rejected by the repository owner: it cuts
  the through-routes and strategic approaches that city-centre and university traffic depends on.
- **Two baseline networks (one per scope).** Rejected: two networks would need two calibrations, two
  provenance chains, and a fusion rule that no accepted contract provides. A filter over one network
  keeps a single provenance chain.
- **Using the ONS display polygon as the clip boundary.** Rejected: it is generalised display
  geometry, and `boundary_reference.py` already refuses scientific clipping. A derived envelope with
  a declared margin and uncertainty is honest; a generalised polygon presented as an exact scientific
  boundary is not.
- **Asserting byte-reproducible builds.** Rejected as factually wrong; measured and reported instead.

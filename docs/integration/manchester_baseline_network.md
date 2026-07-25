# Greater Manchester Baseline Network Foundation (`MAN-09`, Gate-D step 1)

**Status:** `foundation_only`. `MAN-09` remains `planned`; Gate D remains `foundation_only`.

This document describes the deterministic OpenStreetMap-to-SUMO baseline-network foundation added
on 25 July 2026 under [ADR-059](../decisions/ADR-059-greater-manchester-baseline-network.md).

## What this is, and what it is not

Design §21 Gate D lists as its **first** step "Bind one reviewed Manchester SUMO network and
licence", and design §20 gives `MAN-09` the acceptance boundary "Network binding, map-match
candidates, manual ambiguity review, temporal profile, bounded calibration, residuals, and
fail-closed acceptance".

This foundation delivers **only the first of those seven components**.

| Delivered | Not delivered |
|---|---|
| Bounded operator-invoked OSM extract acquisition | Map matching and matching thresholds |
| Greater Manchester baseline scope + Manchester filter | Analyst ambiguity review over real evidence |
| Deterministic `netconvert` 1.27.1 build | Temporal profile from real observations |
| Network validation and required-area inclusion | Calibration objective, bounds, uncertainty |
| Immutable manifests, receipts, checksums | Residuals and an accepted `ManchesterSumoBaseline` |
| Read-only service and bounded CLI | `ManchesterComparisonMetricContract` |

**A built network is geometry.** It is not calibration, not validation against observations, not
live traffic, and not VEC execution, and must never be described as any of those.

## Scope decision

| Decision | Value |
|---|---|
| Primary baseline scope | **Greater Manchester** combined authority (`E47000001`) |
| Sub-area filter | **Manchester local authority** (`E08000003`) — a filter, never a second network |
| Required inclusion | Manchester city centre **and** the University of Manchester area |
| Geographic CRS | `EPSG:4326` |
| Distance CRS | `EPSG:27700` |
| Network CRS | Read back from the produced network (UTM zone 30N observed) |

The packaged ONS boundary assets are **BGC-generalised display geometry**.
`boundary_reference.py` already declares `scientific_clipping_available = False`, and this
foundation does not override it. The extract envelope derived from those assets is labelled
`derived_from_display_geometry`, carries a declared 0.01° margin and 20 m boundary uncertainty, and
sets both `administrative_boundary` and `scientific_clipping_boundary` to false.

Greater Manchester extends west to approximately longitude −2.7304, which is **wider** than the
reviewed National Highways operational envelope (−2.60 to −1.90). The two are never reported as
equal coverage.

## Source identity

| Field | Value |
|---|---|
| Provider | Geofabrik |
| Host / path | `download.geofabrik.de` `/europe/united-kingdom/england/greater-manchester-260724.osm.pbf` |
| Bytes | 50,502,348 |
| SHA-256 | `38f18e98441e89f7376678eab72d1245454547ffad4df80b76a5ac1c9ccfef3e` |
| MD5 (observed = provider published) | `c73b16ec7da303c1dfd331dc914bd5bc` |
| Reference / access date | 2026-07-25 |
| Extract data-cutoff date | 2026-07-24 |
| Licence | ODbL 1.0 |
| Attribution | `© OpenStreetMap contributors, ODbL 1.0` |
| Publication class | `private` — workspace-only, never committed |

Two provider facts were established by probing on 25 July 2026 and changed the pin:

1. **`-latest` is a moving target.** It responds `302 Found` and redirects to a dated file. Pinning
   it would have made the baseline non-reproducible by construction, and the transport allows zero
   redirects, so acquisition would also have failed against the real provider. The **dated** file is
   pinned instead.
2. **The requested 25 July extract does not exist.** `greater-manchester-260725.osm.pbf` returns
   HTTP 404. The newest published extract is `260724`, itself served with
   `Last-Modified: Sat, 25 Jul 2026 00:29:36 GMT`. Rather than relabel a 24 July extract as a
   25 July one, both dates are recorded separately — design §3.1's observation-time-is-not-
   retrieval-time rule applied to a dated file.

## Deterministic build

The builder is one frozen argument vector; the operator selects none of it and no shell is used:

```text
netconvert --osm-files <input> --output-file <output>
           --osm.bike-access false --osm.sidewalks false
           --geometry.remove --ramps.guess --junctions.join
           --tls.guess-signals --tls.discard-simple --tls.join
           --no-turnarounds --numerical-ids --seed 42 --xml-validation never
```

`<input>` and `<output>` are substituted with private temporary paths at run time and **never**
appear in evidence; the receipt records the placeholder shape.

`netconvert` must report `1.27.x`; anything else refuses with `SUMO_VERSION_DRIFT`. Builds run in a
private staging directory and are renamed into place only after validation, so a failed build
leaves no accepted artifact.

### Determinism, stated honestly

Two digests are recorded for every build:

| Digest | Stability |
|---|---|
| `network_sha256` (raw `.net.xml` bytes) | **Not** stable across runs |
| `network_identity_sha256` (comments removed, trailing whitespace normalised) | **Stable** across runs |

This was measured, not assumed. Four independent `netconvert` 1.27.1 runs over identical real
Manchester OSM input produced **four different raw digests** and **one identical canonical
identity**, `75ef6fd3fb5cf64dd4cd476903861a05ecf62df0b09647a1dad9bebcfec623c9`. The difference is
confined to the generation banner's timestamp and echoed output filename, which carry no network
semantics. The binding therefore sets `byte_reproducible = false` and
`semantically_reproducible = true`; byte reproducibility is not claimed because it is not true.

## Known blocker: PBF cannot be read by the reviewed toolchain

`netconvert` 1.27.1 as built in the reviewed environment reads **OSM XML only**. Handed the pinned
`.osm.pbf` it exits 1 with `Error: invalid byte '' at position 2 of a 2-byte sequence` — it is
trying to parse the binary container as XML. Its reported build features
(`Proj GUI FMT Intl SWIG Parquet Eigen GDAL GL2PS JuPedSim`) list no PBF reader, and no approved
decoder (`osmium`, `osmconvert`, `osmosis`, `pyosmium`) is installed.

The builder therefore sniffs PBF framing and refuses with `OSM_PBF_DECODE_UNAVAILABLE`, naming the
missing decode step, rather than surfacing an opaque XML parse error. **The full Greater Manchester
baseline build is blocked on this tooling decision.** Acquisition of the pinned extract works and is
verified; only the decode-to-XML step is missing.

## Real-build evidence

Recorded in
[`evidence/manchester_baseline_network_build_20260725.json`](evidence/manchester_baseline_network_build_20260725.json).

Because of the PBF gap, the real network build used a bounded OpenStreetMap API extract of the
Manchester city-centre and University of Manchester area (bbox `-2.248,53.464,-2.230,53.480`,
14,552,830 bytes). **This is explicitly a sub-area probe and NOT the Greater Manchester baseline
network.**

| Measure | Value |
|---|---|
| Validation status | `accepted`, no findings |
| Edges / junctions / connections | 14,852 / 4,706 / 13,758 |
| Lanes / traffic lights | 15,422 / 57 |
| Projection (read from network) | `+proj=utm +zone=30 +ellps=WGS84 +datum=WGS84 +units=m +no_defs` |
| `origBoundary` | `-2.269013,53.460412,-2.216746,53.493202` |
| Manchester city centre inside | yes |
| University of Manchester inside | yes |

No raw OSM bytes are committed to Git.

## DfT calibration coverage

DfT count-point observations cover **Manchester local authority only**. Inside the Greater
Manchester baseline that is **partial** coverage:

- a location inside the Manchester filter classifies `covered`;
- a location elsewhere in Greater Manchester classifies `uncovered` and stays `unavailable`;
- `uncovered_is_zero` and `missing_filled_with_zero` are both structurally `false`.

A missing survey point is not measured silence, so uncovered is never rendered as zero traffic.
Tests confirm Wigan and Stockport sit inside Greater Manchester but outside the Manchester filter,
and that `classify_dft_coverage` returns a categorical state rather than a number.

## CLI

```text
traffictwin integration manchester network scope
traffictwin integration manchester network acquire <workspace> --confirm [--from-file <path>]
traffictwin integration manchester network build <workspace> --extract <path> --network-id <id>
traffictwin integration manchester network list <workspace>
traffictwin integration manchester network verify <workspace> --network-id <id>
traffictwin integration manchester network status [<workspace>]
```

Acquisition refuses without an explicit `--confirm`. No command accepts a URL, host, path family,
argument, flag, or tool path.

## Service boundary

`integration/manchester/network_service.py` is read-only and offline: it performs no network
access, runs no subprocess, and computes no scientific result. A later Manchester Operations page
reads accepted candidates and honest status through it. Tests assert the module references no
`subprocess`, no `httpx`, and no `BoundedHttpClient`, and exposes neither acquisition nor build.

## What stays unavailable

- Real site-to-edge map matching — `MAP_MATCH_POLICY_UNAPPROVED`, `REAL_SOURCE_GATE_B_UNACCEPTED`.
- Demand calibration — no approved objective, bounds, or uncertainty treatment.
- Observed-versus-simulated goodness-of-fit — no approved `ManchesterComparisonMetricContract`.
- The full Greater Manchester network — blocked by `OSM_PBF_DECODE_UNAVAILABLE`.

The map-matching blockers `MANCHESTER_NETWORK_LICENCE_UNAPPROVED` and
`MANCHESTER_NETWORK_NOT_REVIEWED` are **not lifted** by this foundation, because lifting them also
requires the two blockers above. `SyntheticSumoNetworkBinding` is unchanged and still refuses real
matching.

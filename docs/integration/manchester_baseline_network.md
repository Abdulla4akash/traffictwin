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

### Reproducibility is measured, not asserted

An earlier version of this document claimed builds were semantically reproducible. **That claim
was withdrawn after measuring at full scale.** It held for the small city-centre network (four
runs, identical canonical identity) but does not always hold for Greater Manchester.

Three independent Greater Manchester builds over byte-identical decoded input and identical frozen
arguments:

| Comparison | Canonical identity | Structural counts | Differing canonical lines |
|---|---|---|---|
| build 3 vs build 1 | identical | identical | 0 of 10,913,436 |
| build 3 vs build 2 | **differs** | identical | 238 of 10,913,444 (0.0022%) |
| build 1 vs build 2 | **differs** | identical | 238 of 10,913,444 |

Every differing line is a `<roundabout>` membership list. Edge, junction, connection, lane, and
traffic-light counts were identical in all three builds. So Greater Manchester builds are
**intermittently**, not systematically, non-reproducible.

A single build therefore records `semantic_reproducibility = not_verified`, because one build
cannot establish reproducibility. Only `compare_builds` over two real builds sets
`verified_identical` or `verified_varies`, and a validator refuses a status its own measurement
contradicts. The difference is deliberately **not** hidden by excluding `<roundabout>` from the
digest: defining it away would make the artifact assert a stability it does not have.

## Decode step: PBF to OSM XML

`netconvert` 1.27.1 as built in the reviewed environment reads **OSM XML only**. Handed a
`.osm.pbf` it exits 1 with `Error: invalid byte '' at position 2 of a 2-byte sequence` — it tries
to parse the binary container as XML. The repository owner approved **`osmium-tool`** as the
controlled decoder, and the builder still refuses PBF input directly with
`OSM_PBF_DECODE_UNAVAILABLE` so nobody skips the step by accident.

`osmium` is an optional audited external runtime, treated exactly like SUMO: discovered on `PATH`,
version-probed, run through a frozen argument vector with no shell, never imported into Python.
Observed runtime `osmium 1.19.1` / `libosmium 2.23.1`, GPL-3.0-or-later — executed as a separate
process, never linked, so its licence does not attach to TrafficTwin. `pyproject.toml` and
`uv.lock` are untouched.

**The decode is a format conversion and never a content selection.** It applies no tag filter, no
bounding-box clip, no simplification, and no road-class choice; deciding which ways become edges
stays entirely inside the frozen `netconvert` recipe. A decode that changed which objects survive
would move a scientific decision into a conversion step where nobody would look for it. The
receipt fixes `content_filtered`, `bounding_box_clipped`, `simplified`, and
`road_classes_selected` false, and a test asserts no filtering argument can enter the vector.

Measured on the pinned extract: 50,502,348 bytes of PBF decode to 996,913,352 bytes of XML
(≈19.7×) in under three seconds. The decoded XML is a **private workspace intermediate** and is
never committed.

## Real-build evidence

Two records exist and must not be confused:

| Record | Scope |
|---|---|
| [`manchester_baseline_network_build_20260725.json`](evidence/manchester_baseline_network_build_20260725.json) | Manchester city-centre / University **sub-area probe**. **Not** the Greater Manchester baseline. |
| [`manchester_greater_manchester_network_20260725.json`](evidence/manchester_greater_manchester_network_20260725.json) | The **full Greater Manchester baseline network**. |

The full Greater Manchester baseline network, built from the pinned extract through
`osmium` 1.19.1 and `netconvert` 1.27.1:

| Measure | Value |
|---|---|
| Validation status | `accepted`, no findings |
| Edges / junctions / connections | 2,106,404 / 468,442 / 2,545,492 |
| Lanes / traffic lights | 2,157,380 / 2,434 |
| Network size | 1,248,945,774 bytes |
| Projection (read from network) | `+proj=utm +zone=30 +ellps=WGS84 +datum=WGS84 +units=m +no_defs` |
| Network extent (from `convBoundary`) | lon −2.743629…−1.879479, lat 53.327738…53.690950 |
| Input box (`origBoundary`, **not** the extent) | −2.831812, 52.858497, 1.459963, 53.693129 |
| Manchester city centre inside | yes |
| University of Manchester inside | yes |
| Private paths embedded in the network | 0 |

Validating the 1.25 GB network streams in 1.7 s at 148 MB peak RSS; nothing is ever loaded whole.

No raw OSM bytes and no decoded XML are committed to Git.

### The extent is the network, not the input box

`netconvert` writes both `origBoundary` (everything it *read*) and `convBoundary` (what it
*built*). An OSM extract retains whole ways crossing its edge, so `origBoundary` reached longitude
**+1.46** — Norfolk — while the network stopped at −1.88. The extent is therefore computed from
`convBoundary`, offset by `netOffset` and transformed back through the network's own
`projParameter`. Reading `origBoundary` instead would have overstated coverage and let a point
250 km away pass a containment test.

The network is **not clipped** to the administrative boundary: whole ways are retained, so it
reaches slightly beyond the approved envelope. `NetworkEnvelopeReconciliation` records that
overshoot per side as a measurement, with `network_clipped_to_boundary` and
`overshoot_threshold_applied` both false, because no clipping rule or tolerance has been approved.

## DfT calibration coverage

DfT count-point observations cover **Manchester local authority only**. Inside the Greater
Manchester baseline that is **partial** coverage:

- a location inside the Manchester filter classifies `covered`;
- a location elsewhere in Greater Manchester classifies `uncovered` and stays `unavailable`;
- `uncovered_is_zero` and `missing_filled_with_zero` are both structurally `false`.

A missing survey point is not measured silence, so uncovered is never rendered as zero traffic.
Tests confirm Wigan and Stockport sit inside Greater Manchester but outside the Manchester filter,
and that `classify_dft_coverage` returns a categorical state rather than a number.

## Operator workflow and storage

Install and check the decoder (a standalone CLI, never a Python dependency):

```bash
command -v osmium && osmium --version        # expect osmium 1.19.x / libosmium 2.x
HOMEBREW_NO_AUTO_UPDATE=1 brew install osmium-tool   # if missing, on macOS
```

If `osmium` is absent, every decode fails closed with
`OSMIUM_TOOLCHAIN_UNAVAILABLE`, and `network status` reports
`decoder_available: false` with the blocker named.

Full workflow:

```bash
traffictwin integration manchester network status                     # readiness
traffictwin integration manchester network acquire <ws> --confirm     # pinned PBF
traffictwin integration manchester network decode \
    --extract <pbf> --output <osm.xml> --verify-pinned                # PBF -> XML
traffictwin integration manchester network verify-decode <osm.xml>    # offline replay
traffictwin integration manchester network build <ws> \
    --extract <osm.xml> --network-id gm-baseline-260724               # build
traffictwin integration manchester network verify <ws> --network-id …  # re-verify
traffictwin integration manchester network list <ws>                  # inspect
```

**Storage expectations.** Budget roughly **2.3 GB** of workspace per build:
~50 MB PBF + ~1.0 GB decoded XML + ~1.25 GB network. The decode refuses to
start unless free space covers 30× the PBF. All three artifact classes are
distinct: the **raw** PBF and the **decoded** XML are private workspace
intermediates and are never committed; only the **derived** network is
`redistributable_derived`, and that remains conditional on ODbL share-alike and
the final publication review.

`--verify-pinned` refuses anything but the exact ADR-059 extract identity
(SHA-256, provider MD5, dated filename), and the expectation model refuses a
request that collapses the data-cutoff and retrieval dates into one.
`verify-decode` revalidates a promoted artifact **entirely offline** — it calls
neither the provider nor the decoder — and detects both artifact and receipt
mutation. Measured on the real 997 MB artifact: replay completes in about one
second and an 8-byte append is caught.

## CLI

```text
traffictwin integration manchester network scope
traffictwin integration manchester network acquire <workspace> --confirm [--from-file <path>]
traffictwin integration manchester network decode --extract <pbf> --output <osm.xml>
traffictwin integration manchester network build <workspace> --extract <osm.xml> --network-id <id>
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
- Reproducibility of a Greater Manchester build — intermittently unstable in `<roundabout>`
  groupings, so it must be measured with `compare_builds` rather than assumed.

The map-matching blockers `MANCHESTER_NETWORK_LICENCE_UNAPPROVED` and
`MANCHESTER_NETWORK_NOT_REVIEWED` are **not lifted** by this foundation, because lifting them also
requires the two blockers above. `SyntheticSumoNetworkBinding` is unchanged and still refuses real
matching.

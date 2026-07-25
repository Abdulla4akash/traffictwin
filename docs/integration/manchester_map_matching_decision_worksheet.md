# Manchester map-matching decision worksheet (open question 6)

- Status: **owner-approved candidate policy** (25 July 2026); supervisor review still outstanding
- Raised by: Gate-D step 2 (site-to-edge map-match candidates), capability `MAN-09`
- Prepared: 25 July 2026, against the accepted Greater Manchester baseline network (ADR-059/060)
- Prepared by: measurement, not by proposal

[Open question 6](../open-questions.md) asks: *"Which map-matching distance, direction,
road-class, and confidence rules are scientifically acceptable, and which cases require manual
confirmation?"*

This worksheet was prepared to make that question answerable from evidence, and every number in it
is measured rather than proposed. **The repository owner has since answered it** as a versioned
candidate-research policy — see
[the approved policy](#owner-approved-candidate-policy-25-july-2026) below. That authorises the
complete candidate workflow; it is **not** supervisor approval, and
[the contract decision form](../evaluation/supervisor_contract_decision_form.md) remains unsigned.

## What is already built and not blocked

| Piece | State |
|---|---|
| Real directed edge geometry, with provenance per edge | Built (`network_geometry.py`) |
| Spatial index over all 804,611 real edges | Built, 9.5 s / 528 MB / sub-ms lookups |
| Observation geometry admission with fingerprints | Already existed (`spatial.py`) |
| DfT count-point parsing | Already existed (`dft.py`) |
| Candidate generation, confidence, acceptance | Policy approved 25 July 2026; implementation in progress |

## What the network actually looks like

Measured on the accepted Greater Manchester network, not assumed:

| Property | Value |
|---|---|
| `<edge>` elements | 2,106,404 |
| — junction-internal connectors (excluded) | 1,301,793 |
| — real road edges | 804,611 |
| Real edges with their own `shape` | 516,460 (64.19%) |
| Real edges whose geometry is a straight line between two junctions | 288,151 (35.81%) |
| Edges carrying a signed road number (`ref`) | 44,607 |
| Junctions | 468,442 |

Two consequences the decision should account for:

1. **A third of edges have lower-fidelity geometry.** For 288,151 edges the only available shape
   is a straight line between the two junctions, because the network stores no shape of its own.
   On a curved road the true carriageway can lie tens of metres from that line. Any distance rule
   is therefore not measuring the same thing for all edges, which is why every edge records
   `geometry_source` and the two populations are never averaged.
2. **The network includes non-motor-traffic ways.** 128,051 footways, 54,667 paths, and 20,437
   cycleways are present. They are real parts of the network and are deliberately **not** filtered
   out by the reader, because deciding which classes may carry a motor-traffic count is part of
   this question.

## Measured ambiguity: why distance alone will not do

742 sample points were taken on the geometry of **real A-road edges** (`highway.trunk` and
`highway.primary` carrying an `A…` ref) — that is, points that are certainly on a major road,
which is where a DfT count point sits. For each, every edge within a given radius was counted.

| Search radius | Mean candidates | Median | p90 | Max | Points with candidates from >1 road class |
|---|---|---|---|---|---|
| 10 m | 6.0 | 6 | 10 | 23 | 77.5% |
| 20 m | 10.4 | 8 | 20 | 47 | 89.2% |
| 30 m | 15.8 | 12 | 32 | 85 | 95.0% |
| 50 m | 29.1 | 23 | 58 | 126 | 98.0% |
| 100 m | 76.0 | 61 | 150 | 414 | 99.6% |

Even at a 10 m radius the median point already has six competing edges and three-quarters of
points draw candidates from more than one road class. Candidate counts roughly double for each
doubling of the radius.

Part of this is structural rather than error: SUMO splits a two-way road into two directed edges
and breaks each at every junction, so several returned edges are legitimately the *same* road.
Whether same-road fragments should be collapsed before an analyst sees them is itself part of this
decision.

### Nearest-edge alone mis-attributes about one point in five

For the same 742 points — each *known* to sit on an A road — the class of the single nearest edge
within 30 m was:

| Nearest edge's class | Share |
|---|---|
| `highway.primary` | 46.0% |
| `highway.trunk` | 32.2% |
| `highway.service` | 8.8% |
| `highway.residential` | 6.3% |
| `highway.path` | 2.0% |
| `highway.footway` | 1.3% |
| `highway.trunk_link` | 0.7% |

A "snap to the nearest edge" rule would attribute roughly **19%** of these points to a service
road, residential street, path, or footway. Attributing a motor-traffic count to a footway is not
a small error; it is a wrong measurement that would then propagate into calibration. This is the
concrete reason the road-class rule in open question 6 cannot be skipped or left implicit.

## What had to be decided

Each of these is a scientific choice with no defensible software default. They are listed here as
the questions; the owner's answers follow in the next section.

1. **Distance rule.** Maximum snap distance, and whether it varies by road class or by
   `geometry_source` (the straight-line third of edges arguably deserves a different tolerance).
2. **Direction rule.** Whether a count point's direction is used at all, the bearing tolerance if
   so, and what happens when direction is absent — the majority of count points may not carry one.
3. **Road-class rule.** Which classes may receive a motor-traffic count, and whether that is a
   hard filter or a ranking preference. The 19% figure above is the cost of leaving this open.
4. **Same-road fragments.** Whether directed pairs and junction-split fragments of one road are
   collapsed into a single candidate before review.
5. **Confidence categories.** What distinguishes an unambiguous match from an ambiguous one, in
   terms the above measurements can express.
6. **Manual confirmation.** Which cases must reach an analyst rather than being auto-accepted, and
   what an analyst is shown in order to decide.
7. **Failure handling.** What happens to a count point with no acceptable candidate — it must
   remain unavailable and must never be silently dropped or attributed to a nearby wrong road.

## Observation-side measurement (added 25 July 2026, after real acquisition)

The bounded DfT acquisition has now been run for Manchester local authority `85`: 342 count points
and 39,072 raw counts, both `accepted`, real, and fingerprinted
([evidence](evidence/manchester_dft_observation_acquisition_20260725.json)). Every raw-count site
resolves to a count point; none is orphaned. The same instrumentation was applied to the **305 real
count points that carry raw counts**.

| Search radius | Sites with ≥1 candidate | Mean candidates | Median | p90 | Max | Spanning >1 road class |
|---|---|---|---|---|---|---|
| 10 m | 298 / 305 | 4.5 | 3 | 9 | 24 | 58.4% |
| 20 m | 304 / 305 | 8.3 | 6 | 18 | 44 | 70.8% |
| 30 m | **305 / 305** | 13.3 | 10 | 28 | 61 | 80.0% |
| 50 m | 305 / 305 | 27.2 | 23 | 57 | 128 | 90.5% |
| 100 m | 305 / 305 | 87.4 | 71 | 179 | 460 | 98.7% |

Distance to the nearest edge of any class:

| DfT `road_type` | n | Median | p90 | Max |
|---|---|---|---|---|
| Major | 141 | 2.3 m | 5.2 m | 22.4 m |
| Minor | 164 | 1.4 m | 3.3 m | 14.3 m |

**Distance barely discriminates.** Real Manchester count points sit essentially *on* the network,
and every one of the 305 has a candidate within 30 m — so the approved eligibility distances
exclude no site, and the furthest any site sits from the network is 22.4 m. The difficulty is
ambiguity, not proximity: at 10 m the median site already has three candidate edges, and 58.4% draw
candidates from more than one road class. The road-class filter, the road-identity rule, and
analyst confirmation therefore carry the discriminating work.

### Provider coordinate self-consistency

The provider's own `easting`/`northing` and its own `latitude`/`longitude` disagree by a median of
**1.79 m** (p95 1.85 m, max 1.87 m) when the latter is reprojected to EPSG:27700 — a small
systematic offset consistent with datum handling inside the provider's conversion. It is recorded
because it is a real component of positional uncertainty. It is roughly an order of magnitude below
the approved eligibility distances, not negligible in principle.

### `Counted` versus `Estimated`

`estimation_method` and `estimation_method_detailed` exist on **AADF only**; raw counts carry no
estimation marker. Using raw counts as the calibration evidence and keeping AADF strictly
contextual therefore preserves the distinction structurally rather than by convention.

## What this worksheet does not do

It does not choose a threshold, propose one, rank the options, or imply that any row above is
preferable. It does not lift any of the four map-matching blockers. `MAN-09` remains `planned`,
Gate D remains `foundation_only`, and reading geometry is not matching.

## Owner-approved candidate policy (25 July 2026)

Policy identifier: **`manchester-dft-map-match-owner-candidate-1.0`**
Research status: **`owner_approved_candidate`**

The repository owner authorises the following as a versioned candidate-research policy. The stated
basis is conservative: DfT's own guidance warns that individual-link estimates are less robust than
regional statistics, so the policy prefers manual confirmation over automatic acceptance
throughout.

**This is not supervisor approval.** The
[contract decision form](../evaluation/supervisor_contract_decision_form.md) remains unsigned, and
a later supervisor review may accept or revise this policy without changing any raw evidence.

### Candidate search

| Decision | Value |
|---|---|
| Outer candidate-search radius | 50 m — a *retrieval* bound, not an acceptance claim |
| Eligibility, edge with its own geometry | ≤ 30 m |
| Eligibility, edge with straight junction-to-junction fallback geometry | ≤ 50 m |
| `geometry_source` recorded per candidate | Required |
| Sensitivity analysis radii | 10, 20, 30, 50, 100 m |

The wider bound for fallback geometry follows directly from the measurement above: a straight line
between two junctions can sit further from the true carriageway than the road's own shape does, so
holding both to one tolerance would penalise an edge for the network's storage choice rather than
for being the wrong road.

Grid/index resolution remains a performance parameter and must not alter the exact candidate
product — already enforced by test.

### Road classes

Hard-excluded from motor-count matching: `footway`, `path`, `cycleway`, `steps`, `bridleway`,
`corridor`, `platform`, `construction`, `proposed`.

| DfT `road_type` | Admissible SUMO/OSM classes |
|---|---|
| `Major` | `motorway`, `motorway_link`, `trunk`, `trunk_link`, `primary`, `primary_link`, `secondary`, `secondary_link` |
| `Minor` | `tertiary`, `tertiary_link`, `unclassified`, `residential`, `living_street`, `service`, `road` |

A `service` candidate always requires manual confirmation and an exact compatible road identity
where one exists. A nearby service road is never automatically treated as the counted road.

Every rejected candidate and its rejection reason is preserved in the reconciliation ledger.

### Road identity

Signed references are normalised conservatively — uppercase, ordinary spacing removed, nothing
else. An exact normalised M/A/B reference match is strong identity evidence. Fuzzy text matching is
never an automatic acceptance rule; exact normalised road-name matches may support ranking only.
Junction names are analyst context, not proof. Missing names or references never become matches,
and a road-identity conflict forces manual review.

### Same-road grouping

Opposite directed edges and junction-split fragments collapse into one analyst-facing road group
only when they share a compatible normalised signed reference *or* exact normalised road name, plus
road-class family and local topological continuity. Every underlying SUMO edge id and direction is
retained: grouping is review logic and must never erase edge-level lineage.

### Direction

Count-point reference matching first identifies an **undirected** road group; raw-count direction is
applied afterwards to the underlying directed edges. `N`/`E`/`S`/`W` use the corresponding cardinal
bearing with a maximum angular difference of **45°**. `C` means combined directions and is never
forced onto a single directed edge. Where both directed edges remain plausible, both are kept and
analyst confirmation is required. Where no direction-compatible edge exists, the result is
`direction_unresolved` — direction is never reversed or invented.

### Confidence and acceptance

| Category | Meaning |
|---|---|
| `clear_candidate` | Exactly one eligible grouped road; exact compatible signed reference or exact road name; no road-class conflict; no direction conflict; and ≤ 10 m (native geometry) or ≤ 20 m (fallback geometry) |
| `review_required` | One or more eligible groups exist but not every strict condition is met |
| `no_suitable_candidate` | No candidate survives the approved filters |
| `rejected_by_analyst` | The analyst explicitly rejects every candidate |
| `accepted_by_analyst` | The analyst selects one road group and, where applicable, the directed-edge binding |

**Automatic final acceptance is disabled in policy version 1.0.** Even a `clear_candidate` requires
analyst confirmation. Confidence is triage, not proof.

Every real observation receives exactly one terminal disposition — accepted, rejected, no suitable
candidate, or unavailable through missing evidence. No observation may disappear from
reconciliation.

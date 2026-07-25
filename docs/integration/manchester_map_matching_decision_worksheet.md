# Manchester map-matching decision worksheet (open question 6)

- Status: **awaiting owner/supervisor decision**
- Raised by: Gate-D step 2 (site-to-edge map-match candidates), capability `MAN-09`
- Prepared: 25 July 2026, against the accepted Greater Manchester baseline network (ADR-059/060)
- Prepared by: measurement, not by proposal

[Open question 6](../open-questions.md) asks: *"Which map-matching distance, direction,
road-class, and confidence rules are scientifically acceptable, and which cases require manual
confirmation?"*

This worksheet exists to make that question answerable from evidence. **It deliberately proposes
no values.** Every number below is measured from the real network; none is a recommendation. The
code refuses to generate real candidates until this is decided
(`MAP_MATCH_POLICY_UNAPPROVED`), and no threshold exists anywhere in it, not even as a default.

## What is already built and not blocked

| Piece | State |
|---|---|
| Real directed edge geometry, with provenance per edge | Built (`network_geometry.py`) |
| Spatial index over all 804,611 real edges | Built, 9.5 s / 528 MB / sub-ms lookups |
| Observation geometry admission with fingerprints | Already existed (`spatial.py`) |
| DfT count-point parsing | Already existed (`dft.py`) |
| Candidate generation, confidence, acceptance | **Blocked on this decision** |

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

## What has to be decided

Each of these is a scientific choice. None has a defensible default, and none is chosen here.

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

## What is still needed to inform the decision

The measurements above are **network-side only**. Producing the equivalent for real observations —
the distribution of distance from each real DfT count point to its plausible edges — needs a DfT
count-point snapshot, and none is held locally. That is a bounded, operator-invoked acquisition
under the existing MAN-01/MAN-02 contract and has deliberately not been run as a side effect of
this work.

Once such a snapshot exists, the same instrumentation produces the observation-side distributions
without any new decision.

## What this worksheet does not do

It does not choose a threshold, propose one, rank the options, or imply that any row above is
preferable. It does not lift any of the four map-matching blockers. `MAN-09` remains `planned`,
Gate D remains `foundation_only`, and reading geometry is not matching.

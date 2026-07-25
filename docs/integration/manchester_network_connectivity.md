# Manchester baseline-network connectivity and routability review

- Status: **owner-approved candidate review** (25 July 2026); supervisor review outstanding
- Capability: `MAN-09`, Gate-D step 1 (network binding) **review only**
- Network: `gm-baseline-260724`, identity
  `ce285f85d07fee24414cc3318cf85ea1ca0cb967e2eadb2ac7bcb3f96bde2577` (ADR-059/060)
- Evidence: [`manchester_network_connectivity_20260725.json`](evidence/manchester_network_connectivity_20260725.json)

A demand model cannot avoid one question about a network it did not build: **which parts of it can a
motor vehicle actually reach?** This review answers that and stops there. It performs no map
matching, no calibration, and no comparison, and it lifts no blocker.

## The decision this review had to make first

"Motor-eligible" is not a free choice here; the network settles it. Measured on the accepted build:

| Fact | Value |
|---|---|
| `<lane>` elements carrying exactly one of `allow`/`disallow` | 2,157,380 of 2,157,380 |
| `highway.service` lanes built as `allow="pedestrian delivery bicycle"` | 126,991 |

`netconvert` 1.27.1 builds service roads so that they admit a **delivery van** and exclude a
**private car**. So "permits a motor vehicle" and "permits a car" are different networks, and the
gap is large — 234,126 edges. Collapsing them would overstate the drivable network by every
driveway, alley, and parking aisle in Greater Manchester.

Both subgraphs are therefore computed and both are published. Neither is called *the* motor network,
because the network itself does not make that choice. `custom1` and `custom2` are excluded from the
motor classes: they are unnamed placeholders, and admitting an edge on their evidence alone would be
a guess. That exclusion is published rather than left implicit.

## Edge accounting

Every `<edge>` element increments exactly one accounting path, so the totals reconcile additively
rather than by subtraction. A reader that silently drops malformed elements forces every later count
to be recovered by arithmetic, and a subtracted count cannot tell an internal connector from a
malformed road.

| Population | Count |
|---|---|
| `<edge>` elements | 2,106,404 |
| — junction-internal connectors, excluded | 1,301,793 |
| — real road edges | 804,611 |
| — of which dangling (missing an endpoint) | 0 |
| — of which declaring no lane | 0 |
| Permits a private car | 351,813 |
| Permits a motor vehicle but not a car | 234,126 |
| Permits no motor vehicle | 218,672 |
| Permissions unreadable | 0 |

The recorded binding edge count is **checked** against the streamed count, never used to derive the
internal count; a disagreement refuses the review rather than silently rebalancing. The
independently written geometry reader produces the same 2,106,404 / 1,301,793 / 804,611 split.

An `<edge>` with no `id` fails the review closed: a nameless element cannot be audited by identity,
so calling it an internal connector would claim knowledge the file does not provide.

## Components and coverage

| Subgraph | Kind | Eligible edges | Components | Largest-component edge share | Length share | Inter-component edges |
|---|---|---|---|---|---|---|
| any motor vehicle | weak | 585,939 | 510 | 0.995539 | 0.989066 | 0 |
| any motor vehicle | strong | 585,939 | 892 | 0.994566 | 0.985358 | 404 |
| passenger car | weak | 351,813 | 131 | 0.997723 | 0.996543 | 0 |
| passenger car | strong | 351,813 | 435 | 0.996603 | 0.989789 | 323 |

Shares are unrounded to six decimal places deliberately: a coverage figure that rounded up to 1
would read as complete coverage of a network that is not complete.

A directed edge between two strongly connected components belongs to neither, so both its count and
its **length** are reported separately. Without the named length field those metres would silently
inflate the length credited to the other components.

## Isolated fragments

A size-descending list of runner-up components structurally cannot show the small end — an isolated
fragment is by definition among the smallest, so it sorts last and falls off any top-N. Fragment
totals are therefore computed over **every** fragment, and the sample is drawn from the smallest
end.

For the passenger-car weak subgraph: 87 fragment components holding 183 edges, 193 junctions, and
12,694 m, of which 24 are single-junction components. 192,940 junctions carry no car-eligible edge
at all; they are reported as untouched rather than counted as one-junction road networks.

The three largest non-largest car components hold 112, 48, and 34 edges.

## Bounded probes, and what they cannot establish

32 deterministic spread probes all routed, at 70–343 hops. That result on its own is misleading: a
probe set drawn from a subgraph whose largest component holds 99.7% of the edges will succeed every
time, and unbroken success reads as evidence that the network is routable.

So the review also runs **contrast probes** aimed deliberately outside the largest component. Of 8,
seven were correctly reported unreachable and one routed — a rank-2 strong component that is
reachable *from* the largest component without being strongly connected to it. Strong connectivity
requires both directions, so that is a correct outcome, not a contradiction.

`probe_limit_reached` is kept distinct from `unreachable`, because failing to find a path is not the
same as proving none exists.

**Bounded probes do not prove universal routability.** A probe that succeeds proves one origin
reached one destination. Proving the general claim would need the complete pairwise reachability of
the whole junction graph. The artifact carries
`proves_universal_routability: false` structurally, not only in prose, so a consumer cannot read
past it.

## Using it

```text
traffictwin integration manchester network connectivity <workspace> --network-id <id>
```

The command re-verifies the binding, streams the network once, computes both subgraphs for both
component kinds, runs the probes, and writes `connectivity.json` beside the binding through an
atomic replace, so a partial record is never left behind. Arguments are validated before the network
is touched: a run that will be rejected for its output format does no traversal and leaves no
record.

The read-only service reads that stored record and **never** computes a review, so an ordinary
Streamlit rerun cannot trigger a full-network traversal. A stored review is shown only when both its
network id and its network identity match the candidate; a matching digest under a different id is
not the same artifact and is reported stale. Absent, unreadable, symlinked, and oversized records
each keep their own state rather than collapsing into "absent" — reporting a corrupt record as
merely missing would send an operator to re-run a review instead of inspecting a file that failed to
parse.

## What this review does not do

It does not match an observation to an edge, calibrate demand, compare observed with simulated
traffic, accept the network for real matching, or lift `MANCHESTER_NETWORK_LICENCE_UNAPPROVED`,
`MANCHESTER_NETWORK_NOT_REVIEWED`, `MAP_MATCH_POLICY_UNAPPROVED`, or
`REAL_SOURCE_GATE_B_UNACCEPTED`. `MAN-09` remains `planned` and Gate D remains `foundation_only`.

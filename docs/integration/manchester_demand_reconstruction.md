# Manchester count-constrained candidate demand

- Capability: `MAN-09`, Gate-D step 5 (demand reconstruction)
- Status: **candidate demand produced** under Option A (2019/2022+ window, 78 sites, 149 bound site-directions used)
- Research status: `owner_approved_candidate` — **not** supervisor-approved
- Records: [direction binding](evidence/manchester_demand_direction_binding_20260725.json),
  [study subnetwork](evidence/manchester_study_subnetwork_20260725.json),
  [survey-date question](evidence/manchester_demand_survey_date_question_20260725.json)

The product of this stage is labelled **`count_constrained_candidate_demand`**: a set of routes
chosen so that simulated edge counts approach observed edge counts. It is **not** observed
origin-destination travel, and no artifact here describes it as such.

## The acceptance limitation, carried forward

The input is the set of rows the owner's **written policy** accepted
(`owner_policy_accepted_candidate`). **No analyst, human, or supervisor reviewed any row.**
`CountConstrainedDemandInput` fixes `analyst_accepted` and `human_accepted` false so no downstream
artifact can quietly promote it, and
[the contract decision form](../evaluation/supervisor_contract_decision_form.md) remains unsigned.

## Why `routeSampler` and not `dfrouter`

SUMO's own [routes-from-observations guidance](https://sumo.dlr.de/docs/Demand/Routes_from_Observation_Points.html)
warns that `dfrouter` can generate implausible routes in highly meshed city networks. Greater
Manchester is exactly that, so `routeSampler` is used against a fixed, documented candidate-route
pool. `dfrouter` is deliberately unused.

## Direction application

The approved policy sequences direction *after* an undirected road group is identified, so policy
v1.1 leaves `bearing_degrees` unset and this stage is where direction first exists. Each edge's
bearing is computed from its own geometry and compared against the DfT cardinal code with the
approved 45° tolerance. Four outcomes, never merged:

| Outcome | Meaning |
|---|---|
| `bound_to_single_edge` | one compatible edge; the count binds to it |
| `bound_to_collinear_fragment_group` | several compatible edges agreeing to within the same 45° — one carriageway split at junctions, so one binding target (owner ruling, 25 July 2026) |
| `several_compatible_edges_require_confirmation` | bearings genuinely diverge; still ambiguous |
| `direction_unresolved` | no compatible edge. Direction is never reversed or invented |

`C` (combined directions) is never forced onto a single directed edge.

The collinearity bound **reuses** the approved 45° tolerance applied pairwise rather than
introducing a second threshold, and the count binds to the fragment **nearest the count point**,
because a point count constrains the edge it physically sits on — binding it to every fragment
would assert identical flow across intervening junctions. The collapsed set and its measured spread
are recorded on every collinear binding, so edge-level lineage survives.

Measured effect of the ruling on real data:

| | Before | After |
|---|---|---|
| Bound site-directions | 87 / 311 (28.0%) | **241 / 311 (77.5%)** |
| Sites with ≥1 binding | 53 / 131 | **126 / 131** |
| Genuinely ambiguous | — | 9 |
| Unresolved | 61 | 61 |

Of the 163 previously deferred cases, 154 were one carriageway and only 9 diverged.

## Study subnetwork

Route generation over 804,611 Greater Manchester edges is impractical, and every observation that
could constrain demand lies inside the local authority. The subnetwork is produced by **clipping the
accepted parent**, not re-deriving from OpenStreetMap, so it is provably a subset of the reviewed
baseline: 285,794 real edges (35.5% of parent) in 33 s, all 233 bound edges present, and all edge
ids preserved so every match binding stays valid.

This is **Manchester local-authority** evidence. It must never be described as Greater
Manchester-wide. Routes generated in a clipped network necessarily start and end at its boundary
rather than at true external origins; that is a recorded limitation of a count-constrained
candidate, which is not a claim about real journeys in any case.

## The mismatch that blocked route sampling, and the window that resolved it

`routeSampler` needs **one** set of hourly edge counts. The source does not contain one.

The DfT Manchester raw counts are a **25-year archive of one-off manual surveys**, not a
synchronised network-wide count. Measured on the real acquisition:

- The most widely shared single `count_date` covers **6 of 305 sites**. No date has even ten sites,
  so a network-wide snapshot does not exist in this source.
- Sites carry between 1 and 24 distinct survey dates each; 93 sites have only one.
- Taking each site's latest survey spans **2000-04-04 to 2025-10-14**, with 72 sites last surveyed
  before 2015. That would treat 2008 traffic as contemporaneous with 2025 traffic.
- The approved temporal-profile policy fixes `fuses_across_dates: false`, so fusing them is
  explicitly forbidden rather than merely inadvisable.

Every site's latest survey does at least fall on a weekday, so a latest-survey rule introduces no
weekend contamination.

### The pandemic years are a separate hazard

**26 sites were last surveyed in 2020 (13) or 2021 (13)** — pandemic-restricted traffic rather than
normal conditions. Any window including those years mixes restricted and normal surveys in a way
calibration cannot detect: the discrepancy would be silently absorbed into `demand_scale` and
reported as a fitted parameter rather than as a data-consistency problem.

### The recency-versus-coverage trade-off

Counted over observations that already have a bound edge, so these are the counts demand could
actually use. The full bound set is 126 sites and 241 site-directions over 233 distinct edges.

| Window | Sites | Site-directions | Distinct edges | Pandemic years |
|---|---|---|---|---|
| 2025 only | 31 | 60 | 60 | no |
| 2024 and later | 48 | 93 | 93 | no |
| 2022 and later | 65 | 127 | 127 | no |
| 2019, or 2022 and later | 78 | 151 | 151 | no |
| 2019 and later | 97 | 186 | 184 | **yes** |
| all dates, 2000 and later | 126 | 241 | 233 | **yes**, 25-year span |

This interacts with the frozen 80/20 site split, which is per-site and already fixed: narrowing the
window shrinks both partitions. At 2025-only roughly 25 development and 6 held-out sites remain,
which is thin for a held-out evaluation; the wider windows keep the held-out set meaningful and pay
for it in date consistency.

### The owner's decision

The owner selected **Option A** on 25 July 2026, recorded in commit `13ae063`: each site is
represented by its **latest** survey, admitted only if that survey falls in **2019, or 2022 and
later**. The pandemic years are skipped.

The rule is encoded as a *gap*, not a floor — `site_is_in_survey_window` admits 2019 and 2022 onward
and rejects 2020 and 2021 — because a plain "from 2019" threshold would silently readmit the 26
sites whose latest survey measured pandemic-restricted traffic, and a fitted `demand_scale` would
absorb that discrepancy rather than surface it.

Reconciled against the decision record rather than assumed: **81** accepted sites fall in the window
and **78** of them carry a bound direction, matching the recorded figure. The record's **151**
site-directions were counted over all survey dates; demand can use **149**, because site `26157`'s
northbound and southbound directions bound historically but are absent from its latest survey. That
two-direction difference is a property of the window, not a loss.

Applied to the real data, the window yields **1,788 edge-hour cells** over 149 edges and 12 hourly
intervals, totalling **2,024,123 observed vehicles**, of which **11 cells are measured zeros** —
admitted as zero and flagged, never confused with a missing hour.

## What is ready and waiting

| Piece | State |
|---|---|
| Owner-policy-accepted match set | 131 rows, reproduced exactly from the accepted snapshots |
| Direction binding | settled, 241 of 311 site-directions |
| Study subnetwork | built, all 233 bound edges present |
| `routeSampler` / `randomTrips` tooling | SUMO 1.27.1, verified present |
| edgeData counts file | written: 1,788 cells, 149 edges, 12 intervals |
| Fixed route pool | 43,200 routes, seed 42, envelope recorded |
| `routeSampler` run and mismatch output | run: 746,440 vehicles, 91.32% of observed counts achieved, zero overflow |

Once the window is declared, the remaining work is mechanical: write the `edgeData` counts file for
the chosen window, generate the fixed route pool with a recorded envelope and seed, run
`routeSampler`, and preserve its `--mismatch-output` along with unmatched counts, overflow, route
coverage, and warnings.

## What stays unavailable

- Demand for Greater Manchester outside the local authority. There are no DfT observations there, so
  it stays uncovered; a missing count never becomes a zero count.
- Any claim that reconstructed routes are observed journeys.
- Calibration, comparison, and simulation, none of which this stage performs.

`MAN-09` remains `planned`; Gate D remains `foundation_only`.

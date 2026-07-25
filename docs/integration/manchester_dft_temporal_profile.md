# Manchester DfT temporal-profile candidate

- Status: **owner-approved candidate policy** (25 July 2026); supervisor review outstanding
- Evidence class: **exploratory candidate software evidence**
- Capability: `MAN-09`, Gate-D step 6 (build temporal profile)
- Policy: `manchester-dft-temporal-profile-owner-candidate-1.0`
- Evidence: [`manchester_dft_temporal_profile_20260725.json`](evidence/manchester_dft_temporal_profile_20260725.json)

This turns accepted DfT raw counts into a reviewable hourly demand profile for Manchester local
authority. It adds exactly two things to the observations — a **simulation-clock origin** and an
**accounting** — and nothing else. It does not smooth, average, interpolate, or fill.

## The grain, and what is never merged

One cell is **one site, one direction, one survey date, one clock hour**: the same grain DfT
records. Season and day type are recorded as attributes of a series and are never keys it is
aggregated over.

| Rule | Value |
|---|---|
| Series key | `count_point_id` + `direction_of_travel` + `count_date` |
| Fuses across sites / dates / seasons / directions | No, on all four |
| Measure | `all_motor_vehicles` (DfT's own column) |
| Scope | ONS `E08000003` **and** DfT local authority `85`, both enforced |

## Why there is no UTC anywhere

ADR-055 types the DfT `hour` as `local_clock_hour`: the provider documents it as a local clock range
("7 represents between 7am and 8am") with no timezone, and `GA-DFT-1` is open. A local clock hour is
never promoted to an instant here. DfT's neutral-day survey dates fall almost entirely inside BST,
so assuming Europe/London would shift every hour near a DST boundary and be indistinguishable from
correct data afterwards.

The simulation clock is a **declared mapping, not a discovered instant**: 07:00 local is simulation
second zero, and hour *h* becomes the half-open interval `[(h−7)·3600, (h−6)·3600)`. The artifact
labels it as a convention and fixes `utc_instant_available` to false structurally.

## Missing, zero, and the difference between them

| Cell state | Meaning | Carries a value? |
|---|---|---|
| `observed` | The survey recorded a measurement | Yes — including a measured **0** |
| `missing_no_row` | No row exists for this hour | Never |
| `excluded_null_value` | A row exists but states no value | Never |
| `excluded_conflicting_duplicate` | Two rows disagree; neither is preferred | Never |

A measured zero is a measurement: the road was observed to carry nothing. Dropping it would bias
every mean computed downstream, and filling a missing hour with zero would invent one. The two are
typed separately and never merge.

Every excluded **input row** gets its own ledger entry carrying `source_row_id`, `row_index`,
member path and hash, and the value it held. Cell-level entries would be indistinguishable exactly
where a reviewer most needs detail — a conflicting duplicate.

## The site-level split

Sites are partitioned by `sha256(salt : count_point_id)` bucketed over 10,000, held out below 2,000.
Hashing the **site** is what keeps every hour, direction, and date from one road on the same side;
splitting by row would let a road appear on both, and a held-out score would then be measuring
memorisation.

The realised share is near 20%, not exactly it — the published site counts are the truth. Admission
requires **at least 0.800 coverage on each side**, gated on the exact integer ratio rather than the
six-place figure the artifact publishes.

## Real evidence versus a labelled fixture

The builder works over either an accepted real snapshot or a labelled synthetic fixture and records
which in `evidence_class`. Only `open_real_raw_count_evidence` establishes *real* evidence: it goes
through the existing `open_accepted_dft_snapshot` boundary, refuses a synthetic snapshot, and binds
the raw, manifest, receipt, and parser fingerprints into the artifact. Every row must agree with
that binding on snapshot id and synthetic flag, and `records_accepted` must equal the rows offered,
so real-looking lineage cannot be pinned onto rows from anywhere else.

A stored artifact is re-derived on load: partition summaries are recomputed from the embedded
series, and each series' partition, day type, and season must follow from its own site and date. A
coherently edited artifact is refused rather than believed.

## Measured result, 25 July 2026

Built from `dft_raw_counts-20260725T063354Z-61965dc5c182` (39,072 accepted rows, real, `accepted`).

| Quantity | Value |
|---|---|
| Admission | `admitted_candidate` |
| Rows offered / admitted / excluded | 39,072 / 39,072 / 0 |
| Sites | 305 |
| Series | 3,256 |
| Cells expected / observed / missing | 39,072 / 39,072 / 0 |
| Measured zeros preserved | 166 |
| Coverage | 1.000000 |

| Partition | Sites | Series | Expected | Observed | Coverage | Meets 0.800 |
|---|---|---|---|---|---|---|
| development | 238 | 2,544 | 30,528 | 30,528 | 1.000000 | yes |
| held_out | 67 | 712 | 8,544 | 8,544 | 1.000000 | yes |

Realised held-out site share 0.2197. Hours present in the real data are exactly 7–18 with 3,256 rows
each, which confirms the declared window rather than defining it. Directions N 877 / S 860 / W 762 /
E 757; road types Major 1,716 / Minor 1,540; all weekday; seasons spring 1,275, autumn 1,066, summer
915 across 1,244 distinct survey dates.

Five guards — window exclusion, null value, conflicting duplicate, insufficient coverage, and empty
partition — did **not** fire: the real data is complete and rectangular. Each is implemented and
adversarially tested; their silence is a property of this data.

## What is refused

**AADF** is an annual statistical estimate, not a survey hour. It is refused as a profile input with
its own reason rather than fused. The `Counted`/`Estimated` marker exists only on AADF, so using raw
counts preserves that distinction structurally.

**WebTRIS** stays out while `GA-WT-1` leaves its clock basis undeclared; mixing an undeclared clock
into an hourly profile produces rows that look comparable and are not.

## Using it

```text
traffictwin integration manchester profile policy
traffictwin integration manchester profile build <workspace> --snapshot-id <id> [--output P] [--overwrite]
traffictwin integration manchester profile inspect <profile.json>
```

`build` re-verifies the snapshot before parsing and writes atomically, refusing a symlink even under
`--overwrite` and refusing a payload past the bound `inspect` admits — otherwise a build could leave
an artifact its own CLI could never read back. An existing output is never replaced without
`--overwrite`. `inspect` bounds and type-checks the file before reading it.

The read-only service summarises an already-built artifact and never computes or fetches, so an
ordinary UI rerun cannot reach a provider.

## What this is not

A temporal profile is not calibration, demand, a baseline, or a simulation input. Coverage of
1.000000 measures completeness of the observed window, not accuracy or representativeness. The 80/20
split is a partition of sites, not a validated experimental design. `MAN-09` remains `planned` and
Gate D remains `foundation_only`; the supervisor contract form is unsigned.

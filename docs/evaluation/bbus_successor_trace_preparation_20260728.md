# B-BUS Paired Successor Trace Preparation — Both Ready

**Outcome: both owner-approved successors passed their separately frozen preprocessing
checks.** The Oxford Road study corridor has exact full coverage in both windows. The
whole-fleet Sparse-64 arm preserves every parent vehicle-second and uses one dawn-designed
site array unchanged at peak. No Colab pack, GPU training, held-out policy evaluation,
checkpoint or scientific verdict exists yet.

- Corridor protocol sha256: `cd2e93f…`
- Sparse-64 protocol sha256: `f366f3b…`
- Owner approval receipt sha256: `e165619…`
- Successful private successor manifest sha256: `aef118b…`
- Aggregate machine record:
  [paired successor preparation evidence](../integration/evidence/bbus_successor_trace_preparation_20260728.json)
- Research ceiling: `owner_approved_candidate`; actor admission remains false

## Corridor arm: bounded and fully covered

The 750 m capsule around the frozen St Peter's Square--University of Manchester landmark
line was fixed before these counts were inspected. The transformation reuses the parent
one-second positions without rematching or interpolation, retains only in-capsule seconds,
splits pseudonymous occupancy spans at exits/re-entries, compacts slots deterministically,
and reconciles the result cell-for-cell.

| Measure | Dawn training | Peak held-out |
|---|---:|---:|
| Source vehicle-seconds | 2,174,120 | 3,170,599 |
| Retained corridor vehicle-seconds | **161,654 (7.44%)** | **281,265 (8.87%)** |
| Pseudonymous session tokens retained | 273 | 395 |
| Peak concurrent buses | **67** | **98** |
| Occupied 50 m cells | 831 | 893 |
| Generated analysis sites | **12** | **12** |
| Exact vehicle-second coverage at 500 m | **100%** | **100%** |

Both occupied-cell counts are below the accepted 2,000-cell safety bound. The pinned
`place_rsus_cover.py` bytes (`33928f4…`) completed independently for each session with no
stderr and exact raw-point coverage. The traces are therefore placement-contract compatible.
They are not VEC-06-admitted: this derived bus-scenario route did not produce a VEC-06 receipt,
and the rebuilt network remains reviewed but not accepted for real matching.

The corridor is deliberately narrow. Its 7--9% retained share is scope accounting, not an
argument that excluded buses are irrelevant. Conclusions from this arm cannot be restated as
whole-fleet or Greater Manchester findings.

## Sparse-64 arm: whole fleet, deliberately incomplete infrastructure

The source motion arrays remain byte-for-byte unchanged. Exactly 64 cell-centre analysis
sites were greedily selected from dawn vehicle-second weights only and the same float32 site
array (sha256 `e744e26…`) was attached to both traces. An independent check confirmed every
source field in each sparse output is array-equal to its parent and the site arrays are equal
between windows.

| Exact 500 m coverage | Dawn training | Peak held-out |
|---|---:|---:|
| Total vehicle-seconds | 2,174,120 | 3,170,599 |
| Covered | **978,660 (45.01%)** | **1,458,349 (46.00%)** |
| Uncovered | 1,195,460 | 1,712,250 |
| Peak concurrent buses retained | 827 | 1,000 |

Peak movement did not choose, move or weight a site. The similar held-out coverage is an
observed preparation diagnostic, not a selection target and not evidence of site optimality.
This arm is explicitly outside VEC-06 because roughly 54--55% of vehicle-seconds are outside
500 m of all 64 sites. Its future learning result must always travel with that coverage fact.

## Provenance and privacy checks

The runner verified the successful parent manifest plus all four source motion/occupancy
hashes, the two protocol hashes, approval receipt and pinned placement-script hash before
writing. Private output was new-only. A second local check reconstructed both corridor masks
from occupancy spans, remeasured full coverage, confirmed the sparse motion arrays against
their parents and confirmed one shared sparse site array.

The private output is 33,774,233 bytes below gitignored `data/`. It contains derived arrays
and pseudonymous occupancy only: no raw BODS material, raw identifier, salt, snapshot member,
cross-session linkage or acquisition. The Colab pack will omit occupancy because the producer
runner needs only the derived trace arrays. Public hosting remains unauthorised.

## Next gate

Build two separately identified private Colab packs and fail closed unless each binds its own
protocol and exact dawn/peak trace hashes. Run the corridor and Sparse-64 campaigns as separate
five-seed dawn-training/peak-evaluation studies. Never pool their checkpoints, metrics,
admission labels or conclusions.


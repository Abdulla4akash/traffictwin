# B-BUS Dawn-to-Peak Trace Preparation — Result and Refusal

**Outcome: both captured sessions were converted into reconciled private motion traces, but
the accepted infrastructure-placement gate refused both. No Colab pack was created and no GPU
experiment ran.** This is a successful, aggregate-only trace-preparation result followed by a
scientific preflight refusal—not a failed acquisition and not an empty result.

- Protocol: [approved dawn-to-peak design](bbus_dawn_peak_protocol_20260728.md), sha256
  `b0b35224…`
- Machine record:
  [aggregate trace-preparation evidence](../integration/evidence/bbus_dawn_peak_trace_preparation_20260728.json)
- Private successful manifest: sha256 `032696ea…` under the gitignored `data/` workspace
- Research ceiling: `owner_approved_candidate`; network still not accepted for real matching

## What was processed

The runner opened the two already captured 52-snapshot quarantine ranges—no acquisition—and
used a fresh independent salt for each. Exact repeats were deduplicated, and fixes whose own
`RecordedAtTime` fell outside the declared dawn or peak observation window were counted and
excluded rather than placed into the wrong hour. The selected in-window fixes were matched to
bus-permitted network edges, routed with the rebuilt canonical network, and then processed in
the frozen order: 120 s gap, 15 m dwell, 80% matched-fix floor, and 32 m/s drop-and-count.

| Measure | Dawn training trace | Peak held-out trace |
|---|---:|---:|
| In-window distinct fixes | 41,122 | 60,123 |
| Matched fixes | 36,990 (89.95%) | 54,136 (90.04%) |
| Vehicles meeting 80% before routing | 966 | 1,213 |
| Routable paths constructed | 29,233 | 40,921 |
| Vehicles retained in final motion trace | **961** | **1,212** |
| Peak concurrent vehicles | **827** | **1,000** |
| Speed-ceiling segments dropped | 1,394 | 1,757 |
| Maximum retained implied speed | 31.986 m/s | 31.992 m/s |
| Derived vehicle-seconds | 2,174,120 | 3,170,599 |
| Interpolated share | 98.39% | 98.37% |
| Motion trace sha256 | `38371ea6…` | `4a057319…` |

The high interpolated share is expected from the measured 66–67 s update cadence and must
travel with every result. The largest paths rejected by the speed rule (398.2 m/s dawn and
1,772.8 m/s peak) are consequences of candidate direction/tie and route detours, not measured
bus speeds. They were dropped exactly as approved; the ceiling was not raised.

## The decisive refusal

VEC-06's accepted `greedy_urban_cover` placement is bounded to 2,000 occupied 50 m cells and
at most 64 generated analysis sites at 500 m radius. The complete bus fleet spans Greater
Manchester:

| Gate | Bound | Dawn | Peak |
|---|---:|---:|---:|
| Occupied placement cells | ≤2,000 | **66,291** | **72,208** |

Both traces therefore refuse as `OCCUPIED_PLACEMENT_CELLS_EXCEEDED` before placement. No RSU
position was generated, neither trace is VEC-06-admitted, and the preparation runner correctly
withheld a Colab-ready archive. Trimming buses or raising the bound after seeing this result
would change the experiment; neither was done.

This finding is useful in its own right: a complete region-wide live bus fleet is not the same
spatial object as the compact fully covered VEC traces for which the current placement contract
was designed. Density compatibility (827/1,000 concurrent buses) did not imply geographic
placement compatibility.

## Honest next decision

Two defensible successors exist, and an agent cannot silently choose between them:

1. **Bounded geographic/corridor trace under full coverage (recommended).** Freeze a
   Manchester/corridor polygon before re-derivation, process both whole time windows inside it,
   retain the accepted full-coverage placement semantics, and record the buses excluded by the
   geographic scope. This answers a narrower but contract-compatible dawn-to-peak question.
2. **Whole-fleet sparse-infrastructure scenario.** Keep every retained bus, choose at most 64
   weighted sites, allow uncovered vehicle-seconds, and run a new explicitly non-VEC-06
   exploratory scenario. This preserves the region-wide fleet but changes the infrastructure
   question and admission path.

Raising the accepted 2,000-cell/64-site bounds to force region-wide full coverage is not
recommended: it would generate roughly city-region-scale infrastructure, change computational
complexity and physical interpretation, and disguise a scope mismatch as a limit increase.

Until the owner selects a successor, `dawn training → peak held-out` remains approved but
blocked at placement. No raw BODS byte has left the local machine, no cross-session identity
link exists, and no checkpoint or scientific verdict exists.

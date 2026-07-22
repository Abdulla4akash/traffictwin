# Manchester time basis (`MAN-07` candidate foundation)

## Purpose and boundary

`src/traffictwin/integration/manchester/time_basis.py` implements the accepted ADR-055 time rules
as deterministic library code. It creates no source records, performs no acquisition, reads no
wall clock, and does not complete `MAN-07` by itself. Projection, cross-source reconciliation, and
shared capability/UI wiring remain separate work.

The module answers one narrow question safely: **can this source time be represented as elapsed
seconds inside this exact UTC analysis window?** Only a documented UTC instant can answer yes.

## Typed source-time values

`ManchesterSourceTime` preserves the five v1 bases without collapsing them:

| Kind | Evidence | UTC projection |
|---|---|---|
| `utc_instant` | Documented source UTC instant, currently BODS | Eligible inside a declared window |
| `local_clock_hour` | DfT date plus 0–23 hour label | Unavailable while `GA-DFT-1` is open |
| `source_string_undeclared` | Verbatim WebTRIS date/time strings | Unavailable while `GA-WT-1` is open |
| `date_only` | DfT/TfGM calendar date/version | Never promoted to midnight |
| `simulation_clock` | Randy/TOS relative time | Never mixed with wall-clock evidence |

The refused values remain valid typed source evidence. A projection refusal does not discard or
rewrite them.

## UTC analysis-window contract

`ManchesterTimeBasis` requires:

- explicit UTC start, end, and anchor values;
- the anchor to equal the caller-requested window start;
- a positive-duration half-open interval `[start, end)`;
- `Europe/London` only as the display timezone; and
- explicit false values for source-anchor inference and retrieval-clock use.

`project_source_time(...)` returns `ManchesterTimeProjection`. An admitted UTC instant receives
exact decimal elapsed seconds from the anchor. End-boundary and out-of-window records are excluded.
Every incompatible source kind gets a stable reason code rather than a guessed timestamp.

## London display and DST

`resolve_london_local(...)` applies the installed IANA `Europe/London` rules and reports:

- `unique` with its one UTC candidate;
- `ambiguous` with both ordered UTC candidates, selecting neither unless the caller supplies an
  explicit fold; or
- `nonexistent` with no candidate and no fabricated instant.

For 2026, tests cover the nonexistent `2026-03-29 01:30` spring wall time and the two distinct UTC
interpretations of `2026-10-25 01:30` in autumn. `to_london_display(...)` converts an existing UTC
instant for presentation, preserving its UTC source, offset, and fold; it never rewrites stored
evidence.

Elapsed analysis time is always calculated in UTC. A two-hour UTC window remains 7,200 elapsed
seconds even when the displayed London clock skips or repeats an hour.

## Example

```python
from datetime import UTC, datetime

from traffictwin.integration.manchester.time_basis import (
    ManchesterTimeBasis,
    UtcInstantTime,
    project_source_time,
)

time_basis = ManchesterTimeBasis(
    analysis_anchor_utc=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
    window_start_utc=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
    window_end_utc=datetime(2026, 7, 22, 13, 0, tzinfo=UTC),
)
source_time = UtcInstantTime(
    observed_at_utc=datetime(2026, 7, 22, 12, 15, 30, tzinfo=UTC)
)
projection = project_source_time(source_time, time_basis)

assert projection.status == "admitted"
assert projection.timestamp_s == 930
```

Passing `DateOnlyTime`, `LocalClockHourTime`, `UndeclaredSourceStringTime`, or
`SimulationClockTime` returns an excluded result with the corresponding evidence reason.

## Verification

```bash
.venv/bin/pytest -q tests/unit/test_manchester_time_basis.py
.venv/bin/ruff check \
  src/traffictwin/integration/manchester/time_basis.py \
  tests/unit/test_manchester_time_basis.py
.venv/bin/mypy \
  src/traffictwin/integration/manchester/time_basis.py \
  tests/unit/test_manchester_time_basis.py
```

The suite covers UTC strictness, exact fractional seconds, both half-open boundaries, every
non-instant refusal reason, date-only values on DST dates, spring nonexistence, autumn ambiguity,
fold-aware display, and attempts to strengthen an excluded result into a fabricated instant.

## Evidence basis

- [ADR-055: Manchester Time Basis](../decisions/ADR-055-manchester-time-basis.md)
- [Manchester Gate-A audit](manchester-source-gate-a-audit-v0_7.md), §9
- [TrafficTwin v0.7 design](../traffictwin-design-v0_7.md), §§6, 9–11

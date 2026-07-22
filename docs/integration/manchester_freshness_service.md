# Manchester source freshness and truth-state service (`MAN-07` candidate)

## Purpose and boundary

`src/traffictwin/integration/manchester/freshness.py` provides one deterministic classification
boundary for accepted Manchester evidence. It records exactly what each audited source can claim
at a caller-supplied UTC evaluation instant. It does not acquire data, read the wall clock, infer
observation time from download time, project observations into SUMO, or complete `MAN-07`.

This distinction is deliberate: **availability is not freshness**, and a recently downloaded
historical record does not become live evidence.

## Frozen source policy

| Source family | Allowed interpretation | Explicit exclusion |
|---|---|---|
| BODS SIRI-VM | `live_vehicle` only when `RecordedAtTime` is 0–60 seconds old and evaluation is not after `ValidUntilTime`; otherwise stale, historical replay, synthetic, or unavailable | Never general road-traffic volume or private-vehicle flow |
| DfT raw counts, count points, AADF | Historical | Retrieval time cannot make survey/statistical evidence live; raw-count local-hour timezone remains blocked by `GA-DFT-1` |
| WebTRIS daily observations | Historical, or stale when a cached snapshot is used during a forced service outage | Not live Manchester city-road traffic; source time remains blocked by `GA-WT-1` |
| TfGM signals | Traffic freshness is not applicable | A versioned infrastructure reference is not an observation stream |
| Randy/TOS | Wall-clock freshness is not applicable | Simulation time is not silently aligned to UTC |
| Synthetic | Synthetic | No observed-Manchester claim |

No v1 source may emit `near_live`. Every output fixes
`road_traffic_live_available=false` and `retrieval_time_used=false` in its schema.

## Deterministic evaluation

Callers construct `FreshnessEvaluationRequest` with:

- the source and existing evidence-validation result;
- whether an accepted snapshot is available;
- an explicit use mode (`live`, `offline_replay`, or `historical`);
- an explicit UTC evaluation instant;
- BODS source timestamps only when the source is BODS;
- the synthetic marker; and
- an optional paired service override and safe notice identifier.

The request rejects non-UTC timestamps, half-specified BODS time windows, fabricated UTC validity
fields for historical/static sources, cache claims without a snapshot, and service overrides
without a notice identifier. Evaluation returns a stable request fingerprint, exact policy
fingerprint, reason code, source timestamps, and decimal observation age where applicable.

The persisted `SourceFreshnessEvaluation` validates its own state/reason/source combinations,
policy fingerprint, exact observation age, service-override flag, and live-transit flag. Mutating a
stored result into a stronger claim fails validation.

## Service overrides and unavailable evidence

A forced outage with no accepted local snapshot is `unavailable`. A cached WebTRIS or BODS
snapshot used during that outage is `stale`, never nominally live. Missing snapshots and rejected
validation results remain unavailable regardless of any freshness fields. BODS with missing or an
invalid source validity window fails closed as unavailable.

## Example

```python
from datetime import UTC, datetime, timedelta

from traffictwin.integration.manchester import (
    FreshnessEvaluationRequest,
    ManchesterValidationState,
    evaluate_source_freshness,
)

recorded = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
decision = evaluate_source_freshness(
    FreshnessEvaluationRequest(
        source="bods_siri_vm",
        evidence_validation=ManchesterValidationState.ACCEPTED,
        snapshot_available=True,
        use_mode="live",
        evaluated_at_utc=recorded + timedelta(seconds=30),
        observed_at_utc=recorded,
        valid_until_utc=recorded + timedelta(seconds=90),
        synthetic=False,
    )
)

assert decision.truth_state == "live_vehicle"
assert decision.observation_age_seconds == 30
assert decision.transit_live_available is True
assert decision.road_traffic_live_available is False
```

The evaluation instant is evidence supplied by the caller. The library never substitutes the
machine's current time.

## Verification

```bash
.venv/bin/pytest -q tests/unit/test_manchester_freshness.py
.venv/bin/ruff check \
  src/traffictwin/integration/manchester/freshness.py \
  tests/unit/test_manchester_freshness.py
.venv/bin/mypy --strict \
  src/traffictwin/integration/manchester/freshness.py \
  tests/unit/test_manchester_freshness.py
```

The focused suite covers all source families, inclusive BODS boundaries, fractional-second
staleness, future and expired observations, historical replay, existing BODS-policy parity,
service outages and cache fallback, missing/rejected evidence, UTC refusal, fabricated source
times, schema strengthening, and deterministic fingerprints.

## Evidence basis

- [ADR-055: Manchester Time Basis](../decisions/ADR-055-manchester-time-basis.md)
- [Manchester Gate-A audit](manchester-source-gate-a-audit-v0_7.md), §§4–9
- [TrafficTwin v0.7 design](../traffictwin-design-v0_7.md), §§6, 9–11 and 17

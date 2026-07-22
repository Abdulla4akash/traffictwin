# Manchester evidence-compatible road projection (`MAN-07` candidate)

## Purpose and safety boundary

`src/traffictwin/integration/manchester/projection.py` converts source-specific road records into a
strict intermediate `ManchesterRoadObservation`, then admits only evidence compatible with an
explicit `ManchesterTimeBasis`. It never uses retrieval time, guesses a timezone, fills a missing
speed, treats missing volume as zero, or extends the existing canonical schema.

The current audited sources have an important honest outcome:

- DfT raw-count rows retain their survey date and local clock-hour label, but `GA-DFT-1` prevents a
  UTC instant and therefore canonical `timestamp_s`;
- WebTRIS daily rows retain their source date/time strings, 15-minute interval, volume, mph speed,
  exact m/s conversion, and strategic-road scope, but `GA-WT-1` prevents a UTC instant; and
- a clearly labelled synthetic UTC road row can demonstrate the admission path without implying
  that either official source is currently projectable.

## Source-specific intermediate record

`ManchesterRoadObservation` retains:

- source snapshot, member, member hash, original source-record fingerprint, and source row;
- the typed source time value and a stable row identity;
- sensor/site identity and non-equivalent geographic scope;
- count, speed, original speed value/unit, interval, location label, and quality state; and
- explicit synthetic and retrieval-clock flags.

Source validators refuse semantic strengthening. DfT cannot receive a speed field. WebTRIS speed
must preserve the exact `mph × 0.44704` conversion. DfT must remain Manchester-local-authority
evidence; WebTRIS must remain strategic-approach evidence. Synthetic records cannot lose their
synthetic label.

## Projection and reconciliation

`project_road_observations(...)` sorts inputs by fingerprint, refuses duplicate source records,
projects each typed source time through the declared half-open UTC window, and gives every input
exactly one outcome:

- `ManchesterProjectedRoadRow` when the time and measurement are admissible; or
- `ManchesterProjectionExclusion` with the exact time-basis or missing-measurement reason.

The report independently records normalized-input and original-source fingerprints. Its
`input_set_fingerprint` binds both inventories to the time-basis fingerprint. Counts reconcile
inputs, rows, exclusions, missing measurements, and time-basis exclusions. Saved rows embed their
time projection and validate the canonical timestamp against it, preventing a timestamp from being
changed without invalidating the artifact.

An admitted row materializes the existing `TrafficObservationRecord` through
`to_canonical_record()`. The wrapper carries lineage separately and fixes
`canonical_schema_extended=false`.

## Current official-source result

```python
observation = dft_raw_count_observation(accepted_dft_row)
report = project_road_observations((observation,), time_basis)

assert report.status == "unavailable"
assert report.exclusions[0].reason == "undocumented_source_timezone_ga_dft_1"
assert report.exclusions[0].fabricated_timestamp is False
```

This is expected fail-closed behavior, not a failed computation. Once a reviewed source contract
resolves a timezone blocker, that source's typed time adapter can change through a versioned
decision and new acceptance fixtures; the projection engine itself does not guess.

## Verification

```bash
.venv/bin/pytest -q tests/unit/test_manchester_projection.py
.venv/bin/ruff check \
  src/traffictwin/integration/manchester/projection.py \
  tests/unit/test_manchester_projection.py
.venv/bin/mypy --strict \
  src/traffictwin/integration/manchester/projection.py \
  tests/unit/test_manchester_projection.py
```

The tests cover DfT and WebTRIS conversion, blocker-preserving exclusions, missing observations,
the UTC synthetic admission path, exact canonical output, half-open windows, partial and empty
reports, deterministic input ordering, duplicate refusal, semantic strengthening, timestamp
tampering, and complete reconciliation.

## Evidence basis

- [ADR-055: Manchester Time Basis](../decisions/ADR-055-manchester-time-basis.md)
- [Manchester Gate-A audit](manchester-source-gate-a-audit-v0_7.md), §§4–9
- [TrafficTwin v0.7 design](../traffictwin-design-v0_7.md), §§6, 9–11 and Appendix A

# Deterministic day-type/time-of-day temporal profiles (MAN-09 candidate)

Status: **candidate library evidence — `MAN-09` remains `planned`**

`traffictwin.integration.manchester.temporal_profile` builds a reviewable day-type/time-of-day
profile from caller-supplied, already-parsed source-specific observations. It is a pure
transformation: no network, filesystem discovery, wall clock, database, UI, SUMO launch, or
subprocess use, and no mutation of any upstream artifact. It mirrors the reload-derivation and
frozen-empty production-registry design of the
[calibration module](manchester_calibration.md) and the
[MAN-10 comparison module](manchester_comparison.md).

## Policy

`TemporalProfilePolicy` fixes every methodological choice before any cell exists:

- exactly one observed source (`dft_raw_count`, `webtris_daily`, or `synthetic_utc_road`) with a
  structurally bound time basis: DfT and WebTRIS evidence must declare
  `source_local_clock_undeclared` while `GA-DFT-1` and the WebTRIS timezone blocker remain open,
  and only the labelled synthetic fixture may declare `utc`;
- one measure/unit pair (`vehicle_count` in `vehicles_per_interval`, or `average_speed_mps` in
  `m/s`);
- an exact inclusive analysis window of at most 400 days;
- an exact sorted expected slot-label grid (at most 288 labels) — slot labels are opaque
  source-local strings, never fabricated instants;
- the fixed v1 ISO day-type rule (`weekday`/`saturday`/`sunday`) and a versioned season rule
  (`none` or `meteorological_month_v1`);
- caller-declared excluded dates, each with a reason label — the builder never infers a public
  holiday, event, or school term from the calendar (`holiday_inference="unavailable"`); and
- a minimum per-cell observation count.

## Builder behaviour

`build_temporal_profile(policy, observations)` partitions every offered observation exactly once:

- admitted observations contribute to their `(season, day_type, slot_label)` cell;
- typed exclusions retain the complete observation: `outside_analysis_window`,
  `unknown_slot_label`, `declared_excluded_date`, `null_value_retained` (null stays separate
  from zero), and `conflicting_duplicate_rows` (conflicts exclude every conflicting row rather
  than arbitrating); byte-identical duplicates collapse with a visible count;
- the complete expected grid is emitted: every cell derived from the window calendar and slot
  grid appears with state `available`, `insufficient_observations`, or `no_observations` — a
  missing observation never becomes zero and no interpolation exists;
- available cells publish deterministic Decimal mean (quantised to 0.001, immune to the ambient
  Decimal context), minimum, maximum, observation count, and exact contributing dates; and
- reports embed their exact inputs and re-derive the complete cell partition, admission class,
  and reconciliation counts on every reload, and the exclusion partition is re-derived too —
  admitted and excluded identities must be disjoint, non-conflicting exclusions must be
  identity-unique, and each `conflicting_duplicate_rows` group must contain at least two rows in
  at least two distinct forms — so a fabricated or overlapping exclusion is rejected on reload.

## Structural negatives

Every report fixes `calibration_use_available=False`, `sumo_demand_available=False`, and
`baseline_available=False`. `utc_projection_available` is true only for the synthetic UTC
fixture. The production policy registry
(`APPROVED_PRODUCTION_PROFILE_POLICY_FINGERPRINTS`) is intentionally empty: real DfT or WebTRIS
profiles evaluate as `not_admitted_production_unapproved` until a lead-reviewed policy —
including resolved source timezone semantics and a defensible day-type/season/exclusion design —
is registered. Profile cells are analyst-review evidence only; they are not SUMO demand, not a
baseline, and not calibration acceptance, so `MAN-09` remains planned.

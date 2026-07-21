# VEC-05 Trip and Journey-Time Integration

Status: implemented and accepted for all four audited tripinfo files and all five associated
scenario joins at `tos-data` commit `f6c67acbed3360dba3a0d5c8d1fd557caa99ecff`.

`integration.vec_trip_join` reads bounded gzip XML without changing it, rejects DTD/entities,
duplicates and invalid required values, and fingerprints both compressed and uncompressed bytes.
It joins occupancy vehicles only through exact `sumo_vehicle_id`. Trip departure/arrival values
stay on the full-day SUMO clock; trace-relative occupancy indices are never treated as the same
clock.

Matched rows retain departure, arrival, duration and route length. Missing IDs are explicit
exclusions: a final span reaching the trace boundary is right-censored; a span ending earlier is
missing-before-boundary with cause unavailable. No trip value or zero is filled.

The accepted joins cover 43,767 occupancy vehicles: 42,881 exact matches, 872 boundary-censored
vehicles, and 14 incident vehicles missing before the boundary. Only the exact matched cohort is
used for deterministic duration count/mean/P50/P95/min/max. Those definitions are compatible with
existing `trip.duration.*` methods; completion/count metrics over a different cohort remain
incompatible and unavailable pending VEC-09 admission.

```bash
uv run python scripts/verify_vec_trip_join.py \
  --tos-data-repo ../external/tos-data \
  --output docs/reference/generated/vec_trip_join_verification.json
```

The generated report publishes hashes and aggregates, not raw vehicle IDs. VEC-05 does not enable
canonical conversion, scientific rules, launch, or CLI/UI controls.

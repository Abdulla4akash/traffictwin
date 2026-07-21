# VEC-11 Sanitised Dissertation Pack

Status: implemented and accepted for the audited `_s102` weekend evidence.

The checked-in pack is
[`docs/reference/generated/vec_dissertation_pack/`](../reference/generated/vec_dissertation_pack/).
It is the smallest matched sample and aggregate set built under Randy Putra's written 21 July 2026
permission. It is suitable for repository/dissertation use within that stated permission; it is
not a general data licence and does not authorise public hosting beyond the recorded basis.

## Contents

The pack contains exactly three regular files:

- `sanitised_matched_sample_s102.csv`: three distinct matched task/trip rows, one each for local,
  V2I, and V2V action evidence;
- `aggregate_metrics_s102.csv`: all 26 VEC-09 metric states, including the 18 available values and
  the eight explicit unavailable values and blockers; and
- `manifest.json`: commits, citations, engine, permission, sanitisation, selected-seed disclosure,
  hashes, source-report fingerprints, limitations, and excluded inventory.

The sample uses sequential aliases with no retained mapping. It removes source vehicle IDs, slots,
task indices, trace/full-day clocks, source record numbers, target indices, coordinates, and paths.
Latency is rounded to 10 ms, trip duration to 10 s, and route length to 100 m. Pseudonymisation
reduces direct identification but is **not anonymity**, and the rounded rows must not be used to
reconstruct exact source values.

## Source bindings

- `vec_env`: reviewed commit `068b4ea33e640f206ce6a7d04f3d6fae2ac831f4`;
- `tos-data`: reviewed commit `f6c67acbed3360dba3a0d5c8d1fd557caa99ecff`;
- engine: `v2_post_nrsus_fix`;
- selected run: `fcd_s102_uk2030_we_fs0`;
- required disclosure: `_s102_best_of_seeds`.

The manifest fingerprints the exact accepted VEC-04 task report, VEC-05 trip report, and VEC-09
scientific-admission report. Integration tests recalculate those fingerprints from the checked-in
machine records.

## Build from pinned read-only sources

The destination must not exist. The builder reads exact Git blobs without checkout and refuses a
dirty external repository or an `origin/main` ref different from the audited commit.

```bash
uv run python scripts/build_vec_dissertation_pack.py \
  --tos-data-repo ../external/tos-data \
  --vec-env-repo ../external/vec_env \
  --scientific-report docs/reference/generated/vec_scientific_admission_report.json \
  --output /tmp/vec-dissertation-pack
```

Publication is new-only and atomic. Files are staged, flushed, marked read-only, verified, and then
renamed into place. Existing destinations, extra files, symlinks, hash/size mismatches, unexpected
columns, raw identifiers supplied to the renderer, and local paths fail closed.

## Offline verification

```python
from pathlib import Path

from traffictwin.integration.vec_publication import verify_vec_dissertation_pack

manifest = verify_vec_dissertation_pack(
    Path("docs/reference/generated/vec_dissertation_pack")
)
assert manifest.status == "accepted"
assert manifest.public_hosting_authorized is False
```

Run the capability-specific checks with:

```bash
uv run pytest -q tests/unit/test_vec_publication.py tests/integration/test_vec_publication.py
```

## Deliberately excluded

The pack contains no full raw dataset or repository, actor/checkpoint binary, source vehicle
identity or mapping, private machine/environment record, or third-party SUMO network/FCD asset.
Deadline success remains distinct from eventual physical completion, and eligible targets remain
distinct from confirmed transfers or execution targets.

## Related evidence

- [VEC source audit](randy-source-snapshot-audit-v0_6.md)
- [VEC-04 task joins](vec_task_join.md)
- [VEC-05 trip joins](vec_trip_join.md)
- [VEC-09 scientific admission](vec_scientific_admission.md)
- [Publication policy](randy_publication_policy.md)
- [Generated VEC-11 contract](../reference/generated/vec_dissertation_pack_contract.json)

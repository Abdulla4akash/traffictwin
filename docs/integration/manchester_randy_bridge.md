# Manchester Randy/TOS bridge (`MAN-06` candidate)

## Purpose and status

`src/traffictwin/integration/manchester/randy.py` gives v0.7 a read-only, fail-closed view of the
accepted v0.6 `VEC-11` dissertation pack. It is a candidate library boundary; it does not mark
`MAN-06` implemented and is not yet wired into the Manchester Operations UI or shared capability
manifest.

The bridge is deliberately narrow. It supports a non-geographic Randy/TOS case-study panel using
only material already permitted and accepted for repository/dissertation use. The public-source
Manchester workflow does not depend on it.

## Exact accepted input

`load_randy_manchester_bridge(path)` accepts only a directory that passes the existing
`verify_vec_dissertation_pack(...)` contract:

- exactly `aggregate_metrics_s102.csv`, `manifest.json`, and
  `sanitised_matched_sample_s102.csv` as regular files;
- exact member sizes and SHA-256 values;
- the accepted VEC-11 manifest schema and permission contract;
- reviewed `vec_env` commit `068b4ea33e640f206ce6a7d04f3d6fae2ac831f4`;
- reviewed `tos-data` commit `f6c67acbed3360dba3a0d5c8d1fd557caa99ecff`;
- engine `v2_post_nrsus_fix`;
- run `fcd_s102_uk2030_we_fs0` and disclosure `_s102_best_of_seeds`;
- the three-row pseudonymised/rounded sample; and
- all 26 admitted/unavailable VEC-09 metric states.

The bridge reads the members again after verification and rechecks their hashes, so a file change
between verification and projection fails closed. It performs no network call, external Git
operation, raw-trace import, simulator launch, or write.

## Output and allowed use

The deterministic `RandyManchesterBridgeReport` provides:

- the pack-manifest file hash and canonical manifest fingerprint;
- a sorted three-member inventory;
- both source citations and exact reviewed commits;
- the three sanitised sample rows;
- 18 available and eight explicitly unavailable metric states;
- the VEC-04, VEC-05, and VEC-09 binding fingerprints; and
- the complete VEC-11 permission/scientific limitations.

This is suitable for a local **non-geographic case-study** view that shows the disclosed task,
decision, latency, trip, and metric evidence. Unavailable metric values remain null with their
missing-evidence reasons; no missing value becomes zero.

## Structural refusals

The report model makes the following claims unrepresentable:

- live or fresh Manchester data;
- general Manchester telemetry;
- a geographic map layer or coordinate projection;
- canonical Manchester observations;
- raw source vehicle identity;
- eventual physical completion;
- confirmed execution/transfer targets;
- per-task energy;
- anonymity; or
- a formal licence or public-hosting authorisation.

The sanitised VEC-11 pack removed simulation clocks and coordinates. Therefore the bridge cannot
place rows on the Manchester map or run a freshness calculation. If a future accepted Randy layer
contains evidenced coordinate/projection metadata, it needs a new reviewed spatial-admission
artifact; visual proximity or a Manchester scenario label is not enough.

## Library usage

```python
from pathlib import Path

from traffictwin.integration.manchester.randy import load_randy_manchester_bridge

bridge = load_randy_manchester_bridge(
    Path("docs/reference/generated/vec_dissertation_pack")
)

assert bridge.non_geographic_replay_available is True
assert bridge.geographic_map_layer_available is False
assert bridge.live_data is False
assert bridge.public_hosting_authorized is False
```

The input path is operational only and is never written into the report or its fingerprint.

## Verification

```bash
.venv/bin/pytest -q tests/unit/test_manchester_randy.py
.venv/bin/ruff check \
  src/traffictwin/integration/manchester/randy.py \
  tests/unit/test_manchester_randy.py
.venv/bin/mypy \
  src/traffictwin/integration/manchester/randy.py \
  tests/unit/test_manchester_randy.py
```

The tests load the real accepted VEC-11 pack, check its evidence bindings and unavailable states,
prove deterministic path-free output, refuse strengthened scientific/publication claims, reject
tampering and extra files, and prove that the bridge needs neither network nor external repository
access.

## Related evidence

- [VEC-11 sanitised dissertation pack](vec_dissertation_pack.md)
- [VEC source audit](randy-source-snapshot-audit-v0_6.md)
- [VEC-09 scientific admission](vec_scientific_admission.md)
- [Randy/TOS publication policy](randy_publication_policy.md)
- [TrafficTwin v0.7 design](../traffictwin-design-v0_7.md), §9.6

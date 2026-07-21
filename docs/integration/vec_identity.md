# VEC-03 Occupancy-Bounded Vehicle Identity

Status: implemented and accepted for all five audited `tos-data` trace/occupancy pairs at commit
`f6c67acbed3360dba3a0d5c8d1fd557caa99ecff`.

## What it provides

`traffictwin.integration.vec_identity` turns the inclusive occupancy table into a strict identity
index bound to the exact trace contents. Construction succeeds only when:

- the trace passes the VEC-02 schema and value contract;
- occupancy rows have the exact audited header and valid inclusive bounds;
- slot spans do not overlap, a vehicle is not in two slots at one second, and all bounds fit the
  trace;
- every active trace `(time_index, slot)` has exactly one `sumo_vehicle_id`; and
- no inactive trace cell receives an identity.

The returned snapshot fingerprints every trace array and every admitted span. A downstream join
must present the same trace fingerprint. `resolve_vehicle_identity` returns an ID only inside the
inclusive span, while `iter_vehicle_mobility` yields timestamp, position, and speed rows with the
exact vehicle ID. It streams span-by-span instead of materialising more than 17 million joined
rows.

Slots are explicitly reusable and are not persistent vehicle identities. No neighbouring ID is
carried into a gap, and no missing identity is filled. VEC-04 may use the same exact resolver for
task/action cells; it remains responsible for the task, tier, EV, action, and target contracts.

## Usage

```python
import csv
import numpy as np

from traffictwin.integration.vec_identity import (
    build_vehicle_identity_snapshot,
    iter_vehicle_mobility,
)

with np.load("trace.npz", allow_pickle=False) as archive:
    trace = {key: archive[key] for key in archive.files}
with open("occupancy.csv", encoding="utf-8-sig", newline="") as handle:
    reader = csv.reader(handle)
    header = next(reader)
    rows = list(reader)

snapshot = build_vehicle_identity_snapshot(trace, header, rows, scenario="we")
observations = iter_vehicle_mobility(trace, snapshot, cells=[(0, 0), (1, 0)])
for observation in observations:
    print(observation.sumo_vehicle_id, observation.speed_mps)
```

Invalid evidence raises `VecIdentityError`; no partial snapshot is returned.

## Acceptance evidence

The read-only verifier loaded all ten inputs with `git show <audited-commit>:<path>`, checked the
external worktree before and after, and admitted:

| Scope | Result |
|---|---:|
| Scenario pairs | 5 |
| Occupancy spans | 45,299 |
| Active trace cells | 17,210,508 |
| Identity cells | 17,210,508 |
| Missing identities | 0 |
| Identities on inactive cells | 0 |

The permission-safe machine report records exact source hashes and per-scenario aggregates without
publishing raw vehicle IDs. Re-run it from a checkout containing the clean audited evidence clone:

```bash
uv run python scripts/verify_vec_identity.py \
  --tos-data-repo ../external/tos-data \
  --output docs/reference/generated/vec_identity_verification.json
```

Relevant artifacts:

- `src/traffictwin/integration/vec_identity/`
- `tests/unit/test_vec_identity.py`
- `scripts/verify_vec_identity.py`
- `docs/reference/generated/vec_identity_contract.json`
- `docs/reference/generated/vec_identity_verification.json`

## Boundaries

- This is a source-specific VEC identity and mobility view, not canonical bundle conversion.
- It does not claim that a slot is a vehicle, infer identity outside spans, or expose raw vehicle
  IDs in generated documentation.
- Tier/EV/task/action/target joins remain VEC-04; trip joins remain VEC-05.
- It enables no launcher, metric, rule, CLI, or UI control.

# VEC-06 FCD/Network Preprocessing

TrafficTwin can safely preprocess an arbitrary caller-supplied, one-second SUMO FCD XML and its
matching network XML with the exact trace-building scripts audited at `vec_env` commit
`068b4ea33e640f206ce6a7d04f3d6fae2ac831f4`. The workflow is a tested Python library boundary;
it does not launch SUMO or Randy's evaluator.

## What It Produces

One successful run atomically publishes a new directory containing read-only artifacts:

- `trace.npz`: the pinned builder's trace with deterministic greedy analysis-site placement;
- `occupancy.csv`: exact SUMO vehicle-ID to dense-slot visit spans;
- `rsu_placement.csv`: the generated analysis-site coordinates and placement controls;
- four path-redacted stdout/stderr files under `logs/`; and
- `preprocessing_receipt.json`: request, source, input, dependency, command, output, and limitation
  evidence.

Publication is new-only. An existing destination is rejected rather than replaced.

## Install The Optional Runtime

From the repository root:

```bash
uv sync --extra vec
```

For a normal editable installation instead:

```bash
python -m pip install -e ".[vec]"
```

The VEC extra pins `sumolib==1.27.0` and bounds NumPy and pyproj. Git and a local clone containing
the audited `vec_env` commit are also required. Preflight reports absent runtime dependencies as
`unavailable`; it does not install or modify anything.

## Prepare Inputs

Put the FCD and network XML beneath one input root. The request names them with safe paths relative
to that root and declares their SHA-256 identities. Do not point the API at compressed files,
symlinks, or unrelated XML.

Compute the hashes, for example:

```bash
shasum -a 256 /path/to/input/fcd.xml /path/to/input/network.net.xml
```

The FCD must contain finite, strictly increasing, exact one-second timesteps. Every vehicle must
have a unique ID within its timestep and finite `x`, `y`, and `speed` values. The network must
declare usable projection, offset, and boundary metadata. TrafficTwin checks that observed FCD
coordinates fit the network boundary, but the FCD format cannot cryptographically prove that the
two files were generated together; the caller remains responsible for selecting the correct pair.

## Preflight Without Writing

```python
from traffictwin.integration.vec_preprocessing import (
    VecFcdPreprocessRequest,
    preflight_vec_fcd,
)

request = VecFcdPreprocessRequest(
    input_id="manchester-weekday-am",
    scenario_day="weekday",
    window_label="am",
    fcd_file="fcd.xml",
    network_file="network.net.xml",
    fcd_sha256="<64 lowercase hexadecimal characters>",
    network_sha256="<64 lowercase hexadecimal characters>",
    sumo_seed=102,
)

report = preflight_vec_fcd(
    input_root="/path/to/input",
    vec_repo="/path/to/vec_env",
    request=request,
)
print(report.status.value)
for finding in report.findings:
    print(finding.code, finding.message)
```

Preflight is deliberately read-only. It validates input bounds and hashes, rejects unsafe XML,
checks exact timestep spacing and the coordinate envelope, verifies runtime versions, requires a
clean source worktree whose `origin/main` is the audited commit, and hashes the two source scripts
loaded from the pinned Git commit. An `accepted` result is required before execution. `rejected`
means the request or evidence is incompatible; `unavailable` means the optional runtime is absent.

## Execute And Publish

```python
from traffictwin.integration.vec_preprocessing import preprocess_vec_fcd

receipt = preprocess_vec_fcd(
    input_root="/path/to/input",
    vec_repo="/path/to/vec_env",
    output_dir="/path/to/results/manchester-weekday-am",
    request=request,
)
print(receipt.deterministic_output_fingerprint)
```

TrafficTwin loads exact reviewed source blobs through Git, stages them outside both input and source
trees, and invokes them with allowlisted argument vectors in a controlled subprocess environment.
It validates all output keys, data types, shapes, counts, time values, slot spans, placement-only
changes, and full observed-point coverage before publication. It then rechecks raw-input and source
identity, writes the receipt, makes the payload read-only, and performs one atomic rename.

If validation, execution, timeout, or publication fails, the staging directory is removed and no
partial destination is published. Catch `VecFcdPreprocessingError` to inspect a failed preflight
report when one is available.

## Placement Controls And Bounds

`VecGreedyUrbanPlacement` exposes radius, grid-cell size, maximum RSU count, and maximum occupied
grid cells. Request fields also bound source-file sizes, timesteps, concurrent vehicles, total
observations, dense trace cells, coordinate tolerance, and execution time. Defaults are deliberately
finite; increasing them must be an explicit, schema-bounded request.

The generated coordinates are deterministic grid-cell centres that cover the observed points.
They are analysis sites, not evidence of real installed RSUs. The pinned placement script's
`allow_pickle=True` is isolated to the freshly generated intermediate trace; TrafficTwin never
accepts an arbitrary NPZ at that boundary and validates NPZ outputs with pickle disabled.

## Synthetic Acceptance Evidence

The clearly labelled `tests/fixtures/vec_fcd/synthetic_micro/` pair has four one-second timesteps,
three synthetic vehicle IDs, six observations, and deliberate dense-slot reuse. Local integration
tests execute both exact pinned source blobs twice and assert identical artifacts, full coverage,
exact occupancy reconstruction, atomic new-only publication, read-only outputs, unchanged raw
inputs, and an unchanged external repository. This proves the software path for the bounded
fixture; it is not Manchester traffic evidence or a scientific result.

## Capability Boundary

VEC-06 is preprocessing only. It does not:

- launch SUMO or Randy's evaluator;
- prove traffic realism or scientific validity;
- convert the result into TrafficTwin canonical task, vehicle, trip, or metric records;
- prove the input pair's provenance beyond hashes, structure, coordinate consistency, and the
  caller's declaration;
- represent generated sites as real infrastructure; or
- authorise redistribution of Randy's raw data, actors, checkpoints, or third-party assets.

The stable public model is generated at
[`reference/generated/vec_fcd_preprocessing_contract.json`](../reference/generated/vec_fcd_preprocessing_contract.json).
The source-snapshot prerequisite is documented in
[`randy-source-snapshot-audit-v0_6.md`](randy-source-snapshot-audit-v0_6.md).

# E3a evaluator version 3

Additive research evaluator for the fixed-1x, fresh-state E3a placement
comparison. This is software, not evidence of an executed scientific cell.

`evaluator_v3.py` was copied from
`docs/dissertation/joint_confirmation_2026-09-08/experimental/evaluator_v2.py`
at main `1e01b755b8b633f43c9c7bb6fdd0d75beb6469e8`. The inherited
`ingress_dla` and `per_task_dla` arithmetic and random-key operations are
unchanged. A deterministic three-tick, eight-vehicle construct test compares
every emitted numerical array and all non-runtime summary fields against
that source. The evaluator retains incident mask-only resets when no `enter`
array is present. There is no invented visit channel.

`p2c.py` implements the normative E3 contract's fresh-state P2C branch with
the exact five-field SplitMix64 mapping. Unsigned 64-bit integers are stored
as two uint32 limbs, without enabling x64 or touching the exogenous JAX PRNG.
It filters all RSUs by strict raw-backlog deadline feasibility and current
queue occupancy, samples two distinct feasible IDs when available, and
chooses lower raw backlog with lower-ID ties. N=0 selects no target and
classifies radio unavailable, no deadline-feasible RSU, or all feasible RSUs
full, in that order. N=1 skips hashing. The ordinal is the dense position
`task_slot * padded_fleet_width + vehicle_slot`, including inactive slots.

Admitted work and occupancy are reserved immediately in float32/int32 causal
order. The P2C branch carries those exact arrays across ordering substeps;
it does not regroup the running sum into a separate scatter sum. Rejected
tasks never reserve work, execute, or forward. The copied E2 path validator
has a P2C-only branch allowing the required absent selected target on N=0.

P2C task artifacts add feasible counts, sorted sampled pairs (`[-1,-1]`
when fewer than two are feasible), dense ordinals, selected pre-admission
raw workloads (`-1` when no selection), and separate feasibility/ranking/
unique-workload inspection counts. A radio-viable V2I attempt checks all R
workloads for feasibility, then ranks 0, 1, or 2 values; repeated reads are
visible. These are logical decision-inspection counts, not measured network
messages or a claim of reduced total communication. Reconciliation passes
start from identical initial state and return the same result.

`vendor/vec_jax.py`, the E2d and state-delay helpers, and the preserved host
P2C test oracle are unchanged copies. The evaluator imports the frozen
helpers from its local vendor directory, making the package self-contained.
Only the dependency path in `round_robin.py` changed. See
`vendor/SOURCE_BINDINGS.json` for source hashes and the single vendor change.
The host oracle is used only by kernel tests, not by the simulation path.

Scientific execution, exact inputs, array scheduling, and review receipts
are controlled by the campaign protocol and launcher outside this directory.
Only kernel and tiny synthetic construct checks belong to this builder step.

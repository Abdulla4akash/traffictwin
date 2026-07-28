# B-CAP full training harness

This directory contains the code-only, fail-closed launcher for the owner-approved B-CAP
training campaign. It never reads producer traces, TrafficTwin campaign artifacts, bus data,
`.demo/`, quarantine material, or `data/vec-fresh/`.

The harness verifies four audited producer source files, transforms only a disposable uploaded
copy of `vec_jax.py`, and trains ten from-scratch MAPPO actors: five matched model seeds for a
random-capacity 17-D hidden-observation control and five for the 19-D capacity/headroom treatment.
Every job requests five million timesteps on the producer synthetic highway environment.

The campaign refuses a changed predeclaration digest, unexpected producer bytes, a non-GPU JAX
backend, an incomplete curve, or an actor with the wrong input shape. It is resumable only when
the frozen design matches. Training curves and greedy evaluations are diagnostics; returned
actors are not admitted evidence.

The signed design is
[`docs/evaluation/bcap_training_predeclaration_20260728.md`](../../docs/evaluation/bcap_training_predeclaration_20260728.md).
The separate JSON receipt binds its exact SHA-256 before launch.

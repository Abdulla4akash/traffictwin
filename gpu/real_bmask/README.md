# B-MASK full G4 campaign

This harness runs the data-free action-masking experiment declared in
`docs/evaluation/bmask_training_predeclaration_20260728.md`. It trains five paired
capacity-aware MAPPO seeds with the producer's action mask disabled and enabled,
then evaluates every actor in both deployment modes at four fixed RSU ceilings.

The harness accepts only the reviewed B-CAP disposable source transformation and a
byte-bound approval receipt. It requires the exact Colab G4 runtime, never reads
producer data or bus artifacts, and labels all curves, checkpoints, and mask-grid
outputs as non-admitted owner-approved candidate diagnostics.

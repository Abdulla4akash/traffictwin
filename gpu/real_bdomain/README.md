# B-DOMAIN full G4 campaign

This harness runs the data-free procedural distribution-shift experiment declared in
`docs/evaluation/bdomain_training_predeclaration_20260728.md`. It trains five
capacity-aware MAPPO checkpoints in each of three producer-defined task mixtures and
evaluates every checkpoint across the complete three-domain matrix at baseline and
squeezed RSU capacity.

The harness accepts only the reviewed B-CAP disposable source transformation and a
byte-bound approval receipt. It requires the exact Colab G4 runtime, never reads traces,
producer data, checkpoints, or bus artifacts, and labels all outputs as non-admitted
owner-approved candidate diagnostics.

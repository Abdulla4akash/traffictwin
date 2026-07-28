# Real B-BUS private Colab campaigns

This directory owns the fail-closed harness for the two owner-approved B-BUS
dawn-to-peak successors. `build_colab_packs.py` creates two distinct private ZIPs:
one bounded corridor/full-coverage pack and one whole-fleet Sparse-64 pack.

Each pack contains only its two derived trace NPZs, the exact allowlisted producer
code, the one JAX compatibility patch, its protocol/approval bytes, and the bound
runner. Occupancy tokens, raw BODS material, identifiers, salts, producer data and
checkpoints are absent. The runner requires a GPU, trains only on dawn for seeds
30--34, and evaluates the frozen actors once on peak at 2.5 and 0.75 capacity per
slot with common keys. Returned bytes stay non-admitted until local homecoming
verification; neither pack is authorised for public hosting.

# Synthetic VEC FCD preprocessing fixture

This is a deliberately tiny synthetic SUMO-schema fixture for `VEC-06` acceptance tests. It is
not Randy data, a Manchester trace, a measured traffic sample, or scientific evidence.

- `network.net.xml` is a minimal synthetic 1,000 m square network-coordinate envelope.
- `fcd.xml` contains four one-second timesteps and three synthetic vehicle IDs with slot reuse.

The fixture exists only to test input safety, deterministic pinned-script orchestration,
occupancy reconstruction, RSU placement, hashing, and non-mutation.

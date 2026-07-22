# TrafficTwin synthetic square smoke scenario

Original TrafficTwin-authored synthetic SUMO smoke-test scenario: one edge
tracing a 100 m square perimeter between two dead-end junctions, six
deterministic vehicles, 120 simulated seconds, evaluated with a fixed seed.

Provenance: hand-written for this repository. It is not derived from the
Eclipse SUMO `tools/game/square` scenario (whose inputs are not vendored
here), it is not Manchester traffic, it is not Randy/VEC evidence, and it is
not real-world validation. It exists only to exercise the controlled one-click
SUMO execution workflow.

These three files are the complete admitted input inventory; their SHA-256
hashes are pinned in `traffictwin.integration.sumo_execution.models`.

# B-REWARD full G4 campaign

This directory holds the fail-closed runner for the first data-free B3 reward-engineering
comparison proposed in `docs/research_directions_v2.md`. It uses the reviewed B-CAP source
transformation, trains two matched 19-D capacity-aware MAPPO treatments, and evaluates every
checkpoint on a common four-level synthetic fixed-capacity grid.

The treatments differ only in the producer environment's documented constant-alpha reward knob:
`0.7` retains the balanced QoS/energy reward and `1.0` removes the energy term for deadline-met
tasks (pure QoS). Model seeds are `200` through `204`. Each job requests five million environment
steps and starts from scratch.

All outputs are `owner_approved_candidate` training diagnostics. They are not scientific evidence,
the checkpoints are not admitted actors, and no producer data, bus data, trace, registry, or local
scientific campaign material may enter the disposable VM.


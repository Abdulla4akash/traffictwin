# Synthetic Data Model

The standalone generator lives under `src/traffictwin/synthetic/`. It creates deterministic
TrafficTwin run bundles for demonstration, testing, and viva walkthroughs.

## Configuration

`SyntheticScenarioConfig` is a versioned Pydantic model with:

- scenario ID, name, description, and experiment ID;
- random seed;
- duration and sampling interval;
- vehicle count and tier mix;
- task arrival rate and task-class mix;
- local-capacity hints by tier;
- RSU count and capacity;
- congestion multiplier;
- synthetic policy profile;
- incident schedule;
- included evidence tables;
- synthetic fault labels;
- provenance.

All generated values are deterministic for a fixed configuration and seed.

## Policy Profiles

Profiles are deliberately named as synthetic behavior profiles:

- `synthetic-always-local`
- `synthetic-always-v2i`
- `synthetic-random`
- `synthetic-selective`
- `synthetic-balanced`
- `synthetic-low-offload`

These labels do not claim to implement MAPPO, DQN, Lyapunov control, or any real trained policy.

## Generated Tables

Generated bundles may contain:

- `tasks.csv`
- `infra_state.csv`
- `vehicle_state.csv`
- `traffic_obs.csv`
- `trips.csv`
- `incidents.csv`

Every table uses the existing Phase 2 generic run-bundle contract. Units are declared in
`manifest.yaml`; missing optional files become evidence limitations rather than fabricated data.

## Supported Synthetic Faults

The generator supports only documented demonstration concepts:

- higher demand;
- reduced RSU capacity;
- low offload use;
- weak-vehicle T1 concentration;
- sustained RSU overload;
- localised saturation;
- longer trip durations;
- incomplete evidence;
- trivial low-pressure conditions.

These are implementation fixtures. They are not calibrated scientific claims.

## R3 Experiment Evidence

`generate_trivial_multi_algorithm_experiment` creates multiple synthetic policy-profile bundles
with common random seeds. `build_r3_evidence_pack_from_bundles` computes ordinary Phase 3 metrics,
uses Phase 3 aggregation, and builds the experiment-level evidence keys consumed by existing R3:

- `experiment.algorithm.count`
- `experiment.cross_algorithm_dispersion`
- `experiment.always_local_gap_from_best`
- `experiment.pressure.indicator`

This keeps R3 in the existing deterministic rule path.

## Invariants

- Same config and seed produce identical files.
- Different random seeds change record-level outcomes.
- Generated bundles pass Phase 2 validation.
- Metrics come only from Phase 3.
- Diagnostics consume only EvidencePacks.
- Provenance remains read-only.
- Synthetic labels propagate through manifests, evidence, diagnostics, UI, and reports.

Related documents:

- [Standalone demo](standalone_demo.md)
- [Run bundle specification](run_bundle_spec.md)
- [Diagnostic rules](diagnostic_rules.md)
- [Reproducibility](reproducibility.md)

# Synthetic Measurement Noise And Dropout

TrafficTwin `EXP-03` adds optional deterministic measurement imperfections inside the standalone
synthetic generator. It can perturb selected generated observation fields and remove a bounded,
seeded subset of observation rows. The generated output is an ordinary validated TrafficTwin run
bundle with a typed audit embedded in `manifest.yaml`.

This feature is for controlled software-robustness evaluation. It is not a calibrated sensor,
network, radio, traffic, SUMO, Randy/VEC, or physical-error model. It never launches an external
simulator and never changes imported raw evidence.

## Supported Model

Version 1.0 implements only `bounded_uniform` noise and exact deterministic row dropout.

| Configuration field | Generated fields | Maximum admitted value | Output clamp |
|---|---|---:|---|
| `vehicle_position_max_error_m` | `vehicle_state.x`, `vehicle_state.y` | 100 m | none; coordinates remain in the synthetic source frame |
| `vehicle_speed_max_error_mps` | `vehicle_state.speed` | 20 m/s | minimum 0 |
| `traffic_speed_max_error_mps` | `traffic_obs.average_speed` | 20 m/s | minimum 0 |
| `traffic_count_max_error` | `traffic_obs.count` | 100 | integer, minimum 0 |
| `infrastructure_utilisation_max_error` | `infra_state.utilisation` | 0.5 | interval `[0,1]` |
| `infrastructure_queue_max_error` | `infra_state.queue_length` | 100 | integer, minimum 0 |
| `row_dropout_fraction_by_table` | `infra_state`, `vehicle_state`, `traffic_obs` | 0.95 per table | at least one generated row is retained |

At least one noise bound or dropout fraction must be non-zero. A model targeting a disabled
generated stream is rejected. Noise never applies to tasks, trips, incidents, timestamps,
decisions, completion, latency, routing, target IDs, or task energy.

For each numeric field, a separate SHA-256 digest of the model seed, table, field, original
generated-row index, and clean retained row is mapped to a signed bounded value. Integer fields use
a deterministic value from the inclusive integer range. Adding a different noise field therefore
does not change an already enabled field's noise sequence.

Dropout occurs before noise. For a table with `n > 0`, the dropped count is:

```text
min(n - 1, max(1, floor(n * requested_fraction)))
```

Rows are selected by stable SHA-256 rank using the measurement seed and original clean generated
row. This is exact generated-row selection, not an independent Bernoulli missingness process.

## Configuration Example

The complete runnable example is
[synthetic_measurement_imperfections.yaml](../examples/synthetic_measurement_imperfections.yaml):

```yaml
measurement_imperfections:
  schema_version: '1.0'
  model_version: '1.0'
  distribution: bounded_uniform
  random_seed: 31
  vehicle_position_max_error_m: 3.0
  vehicle_speed_max_error_mps: 1.5
  traffic_speed_max_error_mps: 2.0
  traffic_count_max_error: 4
  infrastructure_utilisation_max_error: 0.1
  infrastructure_queue_max_error: 3
  row_dropout_fraction_by_table:
    infra_state: 0.2
    vehicle_state: 0.1
    traffic_obs: 0.2
```

The scenario random seed controls clean synthetic generation. `measurement_imperfections.random_seed`
controls only the impairment layer. Keep both seeds when reproducing a case.

## CLI Workflow

Inspect the closed machine-readable contract:

```bash
traffictwin synthetic measurement-contract
```

Generate and ordinarily validate the example:

```bash
traffictwin synthetic generate-config \
  --config examples/synthetic_measurement_imperfections.yaml \
  --output build/measurement-robustness

traffictwin bundle validate build/measurement-robustness
traffictwin metrics compute build/measurement-robustness
```

Existing destinations are refused unless `--overwrite` is explicit. Publication is transactional;
a failed regeneration leaves the prior destination intact. Empty, symbolic-link, current/home/root,
and current/home ancestor destinations are rejected.

## Streamlit Workflow

Open **Scenario Builder**, then:

1. Select or edit a synthetic scenario.
2. Enable **Synthetic measurement imperfections**.
3. Set a separate measurement seed and at least one non-zero noise or dropout control.
4. Select **Validate Preview** and inspect the `-imp-<fingerprint>` bundle/run identity.
5. Select an output directory and **Generate And Validate Bundle**.
6. Inspect the audit fingerprint, noisy-field count, dropped-row count, and ordinary validation
   status.

All controls remain synthetic-only. The page has no Randy, TOS, SUMO, training, or live-data run
action.

## Python Workflow

```python
from traffictwin.domain.measurement import (
    MeasurementTableKind,
    SyntheticMeasurementImpairmentConfig,
)
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.config import SyntheticScenarioConfig
from traffictwin.synthetic.scenarios import preset_config

payload = preset_config("baseline").model_dump(mode="python")
payload["measurement_imperfections"] = SyntheticMeasurementImpairmentConfig(
    random_seed=31,
    vehicle_position_max_error_m=3.0,
    row_dropout_fraction_by_table={MeasurementTableKind.VEHICLE_STATE: 0.1},
).model_dump(mode="python")
config = SyntheticScenarioConfig.model_validate(payload)
bundle = write_synthetic_bundle(config, "build/impaired-baseline")
```

`generate_run_data(config)` exposes the same `SyntheticMeasurementImpairmentAudit` before file
materialisation when library code needs an in-memory case.

## Audit And Provenance

An impaired manifest contains `synthetic_measurement_impairment` with:

- the complete strict configuration and its SHA-256 fingerprint;
- one audit for every enabled field, including unit, bound, eligible/perturbed rows, observed error
  extrema, and clamp policy;
- one audit for every enabled dropout table, including requested fraction, before/dropped/retained
  counts, and selection fingerprint;
- a fingerprint over the complete audit;
- fixed `synthetic_evaluation=true`, `calibrated_sensor_model=false`, and
  `raw_source_mutated=false` declarations; and
- mandatory warnings and limitations.

Manifest validation rejects missing, extra, duplicate, or semantically inconsistent field/dropout
audits even if an altered artifact is re-fingerprinted. The bundle and run IDs include the first 12
characters of the configuration fingerprint, preventing a clean and impaired run from sharing an
identity accidentally. When the model is absent, prior synthetic bundle bytes and identifiers are
unchanged.

## Useful Evaluation Cases

- Compare a clean synthetic run with one bounded measurement model to test whether observation-
  dependent metrics or diagnostic hypotheses are stable.
- Repeat one model seed exactly while changing only a declared bound to build a controlled
  sensitivity study.
- Exercise import, validation, replay, metric, reporting, and provenance behavior under known
  missing observation rows.
- Demonstrate why missing observations must remain missing evidence rather than be zero-filled.
- Build deterministic teaching or software-test fixtures for clamps, absent rows, and incomplete
  spatial/infrastructure evidence.
- Combine an explicit EXP-03 configuration with an EXP-01 local parameter sweep when every changed
  parameter remains in the sweep's closed catalogue, or analyse generated outputs with ordinary
  comparison/statistical tools.

Task outcomes remain clean-generator outcomes. A changed metric after impairment describes the
software's response to the controlled observation fixture; it does not measure a policy's physical
response to a real sensor failure. EXP-02 remains the separate post-generation copied-bundle
mutation layer.

## Interpretation Limits

- Bounded uniform errors do not establish an empirical error distribution, correlation structure,
  bias, drift, occlusion process, communication-loss process, or hardware behavior.
- Exact fraction dropout is not random independent missingness and cannot be described as a real
  packet-loss rate.
- Synthetic source-frame coordinates are not latitude/longitude or Manchester geography.
- One seed or one bound does not establish robustness, external validity, significance, or causal
  explanation.
- A defensible dissertation study must predeclare its clean/impaired comparisons, bounds, seeds,
  metrics, multiplicity/statistical method, and claim language.

See [ADR-038](decisions/ADR-038-deterministic-bounded-measurement-imperfections.md), the
[synthetic data model](synthetic_data_model.md), [reproducibility guide](reproducibility.md), and
[fault-injection methodology](fault_injection_methodology.md).

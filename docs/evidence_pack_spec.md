# Evidence Pack Specification

An evidence pack is the Phase 3 handoff object consumed by Phase 5 deterministic diagnostic rules. It contains structured evidence only. It does not contain narrative diagnoses, causal claims, recommendations, LLM prose, or XAI output.

## Schema

Current schema version: `1.0`.

Top-level fields:

- `schema_version`
- `pack_id`
- `generated_at`
- `synthetic`
- `run_context`
- `source_bundle_fingerprint`
- `validation_summary`
- `evidence_availability`
- `metric_engine_config`
- `metric_collection`
- `excluded_record_counts`
- `warnings`
- `provenance`

## Run Context

The run context records:

- run ID;
- experiment ID;
- seed ID;
- algorithm;
- checkpoint;
- random seed;
- environment name;
- environment version or commit.

## Metric Collection

The embedded metric collection contains ordered `MetricValue` objects. Each metric carries:

- metric key;
- status;
- value or `null`;
- unit;
- aggregation scope;
- required and missing evidence;
- reason codes;
- implementation version;
- run provenance;
- computation timestamp.

## Fingerprinting

`EvidencePack.fingerprint()` uses canonical JSON with generated timestamps normalised. It is intended for reproducibility checks, not as a security signature.

## Validation And Evidence

The evidence pack includes the Phase 2 validation status and evidence availability categories. Phase 5 rules use this information to suppress unsupported hypotheses.

## Diagnostic Consumption

Rules consume only the EvidencePack:

- R0 reads validation status, evidence availability, and metric statuses.
- R1 reads task-class completion, task count, offload rate, and mean utilisation.
- R2 reads saturation, queue, utilisation, and task outcome metrics.
- R3 requires experiment-level metric keys such as `experiment.algorithm.count` and `experiment.cross_algorithm_dispersion`.

Rules do not mutate the EvidencePack.

## Limitations

- Excluded row counts are zero for accepted synthetic fixtures because Phase 2 rejects bundles with invalid rows rather than computing partial metrics from rejected data.
- Canonical rows remain in memory; the evidence pack stores metric results and provenance, not raw CSV contents.
- Real Randy/SUMO evidence remains unavailable until representative bundles and units are supplied.
- R1 lacks direct T1-by-low-tier cross-tab evidence in current packs.
- R2 lacks direct task-to-saturation temporal overlap in current packs.
- R3 experiment-level evidence is available only in synthetic diagnostic fixtures at this stage.

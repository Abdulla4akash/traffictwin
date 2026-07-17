# Evidence Pack Specification

An evidence pack is the Phase 3 handoff object for future deterministic diagnostic rules. It contains structured evidence only. It does not contain narrative diagnoses, causal claims, recommendations, LLM prose, or XAI output.

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

The evidence pack includes the Phase 2 validation status and evidence availability categories. Future rules must use this information to suppress unsupported hypotheses. In Phase 3, no deterministic R1-R3 rules are implemented.

## Limitations

- Excluded row counts are zero for accepted synthetic fixtures because Phase 2 rejects bundles with invalid rows rather than computing partial metrics from rejected data.
- Canonical rows remain in memory; the evidence pack stores metric results and provenance, not raw CSV contents.
- Real Randy/SUMO evidence remains unavailable until representative bundles and units are supplied.

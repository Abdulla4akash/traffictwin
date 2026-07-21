# Eclipse SUMO Output Adapter

TrafficTwin implements v0.5 capability `ING-01` as an import-only adapter for Eclipse SUMO
`tripinfo.xml` and `summary.xml`. It validates immutable result files, creates supported canonical
trip records, computes existing deterministic trip metrics, offers a source-specific summary
view, and imports accepted run metadata and metrics idempotently into SQLite.

It does **not** launch SUMO. FCD is not mapped. A successful import establishes compatibility with
the declared XML contract, not scenario realism, Manchester validity, or compatibility with
Randy's private VEC pipeline.

## Supported Contract

Adapter version `1.0` is validated for SUMO `1.27.x`.

| Source evidence | TrafficTwin treatment |
|---|---|
| `tripinfo/@id` | `TripRecord.trip_id` and `vehicle_id`, unchanged |
| non-negative `tripinfo/@depart` | `departure_time_s` |
| completed `arrival` and `duration` | `arrival_time_s` and `duration_s` after consistency validation |
| departed unfinished/vaporised trip | incomplete canonical trip; reported elapsed duration stays source-only |
| never-departed trip | typed source observation only |
| `summary/step` | typed `SumoSummaryStep` source evidence |
| summary `running` | network occupancy only; never canonical traffic `count` |
| FCD | unavailable pending an explicit mapping contract |

`personinfo`, `containerinfo`, device-specific child output, route identity, emissions, and battery
fields remain raw unless a later contract explicitly supports them.

## Result Directory

An input directory contains:

```text
sumo-results/
├── sumo-source.yaml
├── tripinfo.xml
└── summary.xml
```

Minimal manifest shape:

```yaml
schema_version: "1.0"
adapter: sumo_results
bundle:
  bundle_id: sumo-example-seed-42
  created_at: "2026-07-19T12:00:00+00:00"
source:
  scenario_id: public-scenario-id
  scenario_url: https://example.org/scenario
  sumo_version: 1.27.1
  source_commit: null
  licence_spdx: EPL-2.0
  retrieval_date: 2026-07-19
  redistribution_allowed: true
  restrictions: []
  synthetic: true
run:
  run_id: sumo-example-seed-42
  experiment_id: sumo-example
  seed_id: sumo-example-seed-42
  algorithm: sumo-declared-model
  random_seed: 42
files:
  tripinfo:
    path: tripinfo.xml
    checksum_sha256: <64 lowercase hexadecimal characters>
  summary:
    path: summary.xml
    checksum_sha256: <64 lowercase hexadecimal characters>
```

All metadata is declarative evidence supplied with the result. TrafficTwin verifies structure and
checksums; it does not contact the source URL during import or independently grant redistribution
permission.

## Command-Line Usage

From the repository virtual environment:

```bash
.venv/bin/traffictwin integration sumo contract
.venv/bin/traffictwin integration sumo validate tests/fixtures/sumo/square_public
.venv/bin/traffictwin integration sumo metrics tests/fixtures/sumo/square_public
.venv/bin/traffictwin integration sumo import tests/fixtures/sumo/square_public \
  --registry .demo/registry.sqlite
```

Add `--format json` to `contract`, `validate`, or `metrics` for machine-readable output. Repeating
an import with the same bundle ID, run ID, and fingerprint is idempotent. A changed fingerprint or
conflicting run ID is rejected.

## Streamlit Usage

Open `SUMO Output Import`, enter the result-directory and registry paths, then inspect:

- declared source, licence, retrieval, and version metadata;
- raw XML checksums and sizes;
- validation findings;
- tripinfo/canonical/completed counts;
- downsampled presentation of the complete typed summary sequence;
- deterministic canonical trip metrics.

`Import SUMO Results` becomes effective only for an accepted result. No page control starts SUMO.

## Public Acceptance Fixture

`tests/fixtures/sumo/square_public` was generated with SUMO 1.27.1 and random seed 42 from the
official Eclipse SUMO `tools/game/square` scenario at tag `v1_27_1`. Its README records the exact
command, commit, licence, and limitations. It is labelled synthetic simulated traffic.

Current expected inventory:

- 142 valid source `tripinfo` observations;
- 127 departed canonical trips;
- 41 completed canonical trips;
- 86 incomplete canonical trips;
- 15 never-departed source-only observations;
- 1,800 typed summary steps.

These counts are fixture acceptance evidence, not performance claims.

## Security And Integrity

- Raw XML is read-only and its hash is checked before parsing.
- Paths must stay inside the source directory and may not be symlinks.
- DTD and entity declarations are rejected before standard-library XML parsing.
- XML roots, required attributes, numeric values, duplicate IDs, trip consistency, and summary
  time order have stable validation codes.
- Unknown supported-version attributes remain in raw XML and generate a warning rather than being
  silently mapped.

The decision rationale is recorded in
[ADR-011](../decisions/ADR-011-sumo-output-mapping.md). Machine-readable contract output is
generated at `docs/reference/generated/sumo_source_contract.json`.

The same source boundary is projected through the closed OPS-05 interface as
`sumo_results_v1` with conversion profile `partial_canonical`. See the
[general external-source contract](external_source_contract.md); interface membership does not
make SUMO equivalent to TOS or a complete generic bundle.

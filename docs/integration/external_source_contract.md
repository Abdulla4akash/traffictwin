# General External-source Contract

TrafficTwin `OPS-05` provides one typed, read-only interface for discovering, validating, and
describing completed external result packages. It does not make different source families
scientifically or structurally equivalent. Each adapter publishes its own semantics, capabilities,
provenance requirements, conversion boundary, blockers, and interpretation limits.

The v1 registry contains exactly two reviewed reference adapters:

| Adapter | Required discovery marker | Conversion profile | What it does not claim |
|---|---|---|---|
| `sumo_results_v1` | `sumo-source.yaml` | `partial_canonical` | Only valid departed `tripinfo` records become `TripRecord`; summary snapshots and FCD do not become canonical traffic/vehicle evidence. |
| `tos_data_read_only` | `evals/eval_results_master.csv` | `aggregate_summary` | Producer summary rows and source-specific replay views remain source-labelled; no canonical task, vehicle, RSU, trip, or ordinary-bundle conversion is claimed. |

Generic TrafficTwin run bundles remain the first-party `traffictwin bundle` workflow. They are not
wrapped as an external reference adapter merely to increase the adapter count.

## Shared interface

Every registered adapter implements four operations:

1. `discover(path)` checks exact, safe, relative markers without deep parsing.
2. `contract()` returns the versioned field semantics, capability manifest, provenance policy,
   conversion profile, blockers, and limits.
3. `validate(path, deep=False)` calls the existing source-specific read-only validator and projects
   a portable summary without discarding the source report identity.
4. `inspect(path, deep=False)` returns the same portable validation and observed provenance for the
   selected contract.

The protocol is available as
`traffictwin.integration.external.ExternalSourceAdapter`. The closed v1 registry is returned by
`external_source_adapters()`; it does not discover Python modules, import uploaded code, or load
unreviewed adapters.

## Discovery

```bash
traffictwin integration external discover path/to/source
traffictwin integration external discover path/to/source --format json
```

Discovery produces one of four states:

| State | Meaning |
|---|---|
| `one_match` | Exactly one registered adapter matched all required direct markers. |
| `no_match` | No adapter matched; TrafficTwin does not guess from filenames or extensions. |
| `ambiguous` | More than one adapter matched; pass an explicit adapter to inspection only after confirming the source type. |
| `blocked` | The source root or a discovery marker is a symbolic link or otherwise unsafe. |

Discovery is shallow. A matched marker does not mean that the package is valid, importable,
licensed, or scientifically suitable.

## Contract inspection

Show the shared catalogue:

```bash
traffictwin integration external contract
traffictwin integration external contract --format json
```

Show one reference contract:

```bash
traffictwin integration external contract \
  --adapter sumo_results_v1 \
  --format json
```

The generated machine-readable contract is
[`external_source_contract.json`](../reference/generated/external_source_contract.json).

## Source inspection

```bash
traffictwin integration external inspect path/to/source
traffictwin integration external inspect path/to/source --deep --format json
```

Normally the single discovery match selects the adapter. If a package deliberately contains both
marker families, selection is ambiguous and inspection refuses to guess. An explicit selection is
available for a known source:

```bash
traffictwin integration external inspect path/to/source \
  --adapter tos_data_read_only \
  --deep \
  --format json
```

An inspection contains:

- the selected adapter and exact contract fingerprint;
- the source-specific validation outcome, validator version, finding codes/counts, source
  fingerprint, import decision, and produced-output counts;
- observed provenance with `confirmed`, `inferred`, `unknown`, or `unsupported` status;
- the adapter conversion profile and exact unavailable outputs;
- typed blockers and the evidence required to revisit them;
- interpretation limits, `read_only: true`, and `mutations_performed: false`.

Absolute source paths and wall-clock timestamps are excluded from the portable inspection. The same
unchanged source and software contract produce the same inspection fingerprint.

## Python usage

```python
from traffictwin.integration.external import (
    discover_external_sources,
    inspect_external_source,
)

discovery = discover_external_sources("path/to/source")
print(discovery.status)
print(discovery.candidate_adapter_ids)

inspection = inspect_external_source("path/to/source", deep=True)
print(inspection.adapter_id)
print(inspection.validation.outcome)
print(inspection.conversion.level)
print(inspection.fingerprint())
```

`accepted_for_declared_import` applies only to the selected adapter's documented import boundary.
For example, accepted TOS source summaries do not imply accepted canonical task rows.

## Conversion profiles

Conversion-profile labels are non-ordinal descriptions, not grades:

- `none`: no typed TrafficTwin output;
- `source_specific`: typed source-native inspection only;
- `aggregate_summary`: producer aggregates may enter explicitly source-labelled artifacts;
- `partial_canonical`: only the listed compatible fields enter the listed canonical records;
- `canonical_bundle`: a complete declared canonical-bundle contract, not claimed by either v1
  external reference adapter.

Do not compare the labels numerically or infer scientific compatibility from them.

## Adding another source

A future adapter requires a reviewed implementation and acceptance evidence. At minimum it must:

1. use exact safe markers and fail closed on ambiguity or symbolic links;
2. preserve raw source evidence and call a deterministic, read-only source validator;
3. document every exposed field's meaning, unit, identity scope, join, evidence status, and limits;
4. provide a complete three-valued capability manifest;
5. declare required provenance, licence, permission, version, and fingerprint evidence;
6. list exact canonical, source-specific, registry, and unavailable outputs;
7. publish typed blockers with the evidence needed to revisit them;
8. add unit, integration, golden, safety, non-mutation, path-redaction, and fixture tests;
9. update the generated contract, ADR, architecture, assumption register, open questions, and
   implementation status.

Dynamic entry points and uploaded adapter code are excluded from v1. Adding an adapter is a code and
contract review, not a runtime configuration action.

## Safety and interpretation

- Discovery and inspection do not launch SUMO, Randy/VEC, or another simulator.
- They do not import into the registry, repair files, rewrite manifests, or generate conversions.
- A checksum proves byte identity, not permission, correctness, realism, or scientific validity.
- A public-looking URL does not establish a licence or redistribution permission.
- TOS package licence and publication permission remain `unknown` until the owner supplies them.
- SUMO fixture provenance applies only to the declared files and supported version boundary.
- Cross-source comparisons still require compatible metric, unit, population, method, and provenance
  contracts; this interface does not provide that compatibility by itself.

See [ADR-048](../decisions/ADR-048-generalised-external-source-contract.md), the
[SUMO adapter guide](sumo_output_adapter.md), and the [TOS adapter guide](tos_data_adapter.md).

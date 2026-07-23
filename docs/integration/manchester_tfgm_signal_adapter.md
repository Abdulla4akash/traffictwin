# TfGM Traffic-Signal Reference Adapter (MAN-04 candidate)

Status: **candidate Gate-B parsing evidence; `MAN-04` remains `planned`**

`traffictwin.integration.manchester.tfgm_signals` is a pure offline parser for the official
Greater Manchester Traffic Signal Locations CSV. It produces static infrastructure references
only. Network access, archive extraction, immutable publication, map rendering, freshness, and
spatial admission stay outside this module.

## Audited release identity

The verified source is the TfGM `TrafficSignals_OpenData.zip` fetched from the official static
download on 2026-07-22:

- dataset label: Nov 2025 data, published 14 January 2026;
- archive SHA-256: `85a52992ba2ef30b4bdb4aca4162a2ffd8a5244f7139be50e0b0ffbee7a4f3fa`;
- admitted member: `CSV-format/TrafficSignals.csv`;
- CSV SHA-256: `c45ad8439c9058a239f7e0ad33f39e2da8d79a80194229ad3b67a50f12fc3a81`;
- 2,529 unique records across all ten Greater Manchester authorities; and
- a UTF-8 BOM plus the exact fifteen-field header frozen in the Gate-A audit.

The archive URL is overwritten in place. The hashes and access date—not the URL alone—are the
release identity.

## Exact record contract

The parser admits only:

```text
FRAS_ref,Description,Type,Controller,BUS_GATE,Easting,Northing,Type_Of_Control,
Authority,HA_AGENCY_MAINTAINED,Longitude,Latitude,NIS_node,COMMENTS,KRN
```

Observed signal types are Junction, PCAT, Pedex, Pegasus, Pelican, Puffin, Sparrow, Toucan, and
Wig Wag. Control values are MOVA, RMS, SCOOT, and UTC. Authorities are exactly Bolton, Bury,
Manchester, Oldham, Rochdale, Salford, Stockport, Tameside, Trafford, and Wigan. Schema/code-list
drift is rejected rather than silently grouped into an invented category.

`FRAS_ref` remains source text so leading zeroes and slash-delimited identifiers survive. Empty
optional text remains null. `KRN` maps Yes/No to true/false and an empty source value to null,
never false. The official full release contains 18 empty KRN values, reported as a typed warning.

## Coordinate validation

Every record contains both British National Grid eastings/northings (EPSG:27700) and WGS84
longitude/latitude (EPSG:4326). The parser transforms the former with the version-bounded PyProj
runtime and requires the published pair to agree within 2.5 metres. The verified release's worst
observed discrepancy is approximately 1.83 metres; all 2,529 records pass.

The original coordinate values remain authoritative evidence and are preserved. The calculated
coordinates are used only for validation and are not written over the source values.

## Scientific limits encoded in the model

Each record carries `evidence_status="static_reference"` and
`evidence_kind="traffic_signal_location"`. The following capabilities are literal false values:

- live signal state;
- current phase;
- phase timing;
- queue measurements;
- traffic counts; and
- incident evidence.

Unknown fields are forbidden, so a downstream artifact cannot add `current_phase` or similar
claims to a validated record. The dataset does not support control-performance, congestion, or
real-time operational conclusions.

## Licence and fixture policy

The full ZIP and CSV remain workspace-only. Repository tests retain only an exact three-row
Manchester derivative with source/archive hashes and attribution. It is labelled
`redistributable_derived_sample` and cannot claim to be the complete dataset.

The OGL text inside the acquired January 2026 archive requires:

> Contains Transport for Greater Manchester data. Contains OS data © Crown copyright and database
> right 2026.

The supporting PDF and data.gov.uk page currently say 2025. TrafficTwin records the discrepancy
and uses the wording shipped inside the acquired artifact for this snapshot rather than silently
combining the two.

## Failure and lineage behaviour

The parser re-hashes bytes before decoding and refuses oversized input, a changed official hash,
missing BOM, header drift, malformed CSV, non-unique `FRAS_ref`, invalid code values, out-of-range
coordinates, and coordinate-system disagreement. Full-release claims additionally require the
exact audited CSV hash, 2,529 rows, and all ten authorities.

Output is sorted by `FRAS_ref`; source row order cannot change the record inventory. The parser
performs no network calls and does not extract arbitrary archive members.

## Verification evidence

- The three-row attributed fixture and negative suite contain no full source archive.
- The focused test suite validates schema, coordinates, identifiers, optional values, publication
  classes, hashes, strict claims, and offline behaviour.
- A local workspace-only parse of the exact full CSV admitted all 2,529 records, all ten
  authorities, zero malformed rows, and one aggregate `KRN_MISSING` warning covering 18 rows.

## Remaining acceptance work

1. Run the controlled acquisition candidate against the exact real ZIP and retain its private
   acceptance receipt without committing the archive.
2. Reconcile that real receipt with the pinned full-release identity and spatial/map manifests.
3. Pass accepted records through the candidate MAN-07 spatial gate and MAN-08 offline layer
   manifest; both services exist, but no real-source map layer or UI is accepted yet.
4. Reconcile the complete acquisition-to-map chain and capability truth after lead review.

`MAN-04` remains planned until those integration gates pass.

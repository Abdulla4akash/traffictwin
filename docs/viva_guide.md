# Viva Guide

This guide gives concise, candid answers to likely viva or supervisor questions.

## What problem does TrafficTwin solve?

It turns scattered traffic/VEC experiment artifacts into a reproducible workflow: versioned seed, validated run bundle, canonical records, deterministic metrics, evidence packs, comparisons, and diagnostic hypotheses.

## What did you personally contribute?

The repository implements the TrafficTwin research-software architecture: schemas, validation, canonicalisation, registry, metrics, evidence packs, comparison, deterministic diagnostics, provenance tracing, Streamlit UI, CLI, tests, fixtures, and documentation.

## Why import-first?

Because Randy/VEC and SUMO execution contracts are not evidenced locally. Import-first lets the system work with completed run bundles without fabricating launch capability. Direct launch can be added later behind an adapter when real commands and output contracts are known.

## Why deterministic rules rather than an LLM?

Metrics and diagnostic hypotheses need to be testable, reproducible, and auditable. An LLM may later render already-computed findings into prose, but it must not calculate metrics, invent diagnoses, or recommend unsupported actions.

## Why canonical records?

Adapters isolate source-specific schemas. Canonical records give metrics and rules a stable internal contract while preserving source file and row provenance.

## Why EvidencePacks?

EvidencePacks create a strict boundary between computed evidence and diagnostic interpretation. Rules consume EvidencePacks only, which prevents raw-data peeking or metric recomputation inside diagnostics.

## How is reproducibility preserved?

Through versioned schemas, deterministic YAML, explicit units, validation before metrics, stable metric keys, fixed-clock tests, bundle/evidence/provenance fingerprints, source row references, and golden tests.

## What does the Provenance Explorer add?

It makes the prototype auditable. A supervisor can select a displayed metric or diagnostic rule and trace it back to metric definitions, canonical records, validation findings, source files/rows, manifest metadata, seed, experiment, environment, and fingerprint. It shows traceability through the software pipeline; it does not prove real-world causality.

## What is synthetic and what is real?

All included run data and fault-injection cases are synthetic. No real Randy/VEC, SUMO, Manchester sensor, near-live, or true-live data is included.

## Is this a digital twin?

It is a replay-and-scenario digital-twin prototype, not a live city mirror. It demonstrates the software workflow needed for what-if analysis; real live integration is future work.

## Is the data live?

No. The UI supports historical replay over imported timestamps and synthetic fixtures. Near-live and true-live labels are future unsupported modes.

## Are diagnostic rules validated?

They are tested against labelled synthetic fault-injection cases, which verifies implementation behavior. External validity requires real data, expert review, and controlled evaluation.

## What would Randy integration change?

It would add evidenced adapters that map real Randy/VEC and SUMO artifacts into the existing canonical contract. The metrics, EvidencePack, diagnostics, and UI pipeline should remain the same.

## What are the biggest limitations?

No real external artifacts, no launch contract, no live data, synthetic-only diagnostic evaluation, aggregate rather than temporal-overlap evidence for some rules, and no formal user study yet.

## Why Streamlit?

It gives a fast, inspectable research UI with low infrastructure burden. The important engineering work remains in the tested library, not the UI.

## Why SQLite?

SQLite is sufficient for local metadata and reproducibility at this stage. There is no evidence yet that heavier storage is needed for row-level analytics.

## Why no pandas in the core?

The current fixtures are small and the standard library CSV module plus Pydantic are sufficient. Avoiding pandas keeps the core dependency surface smaller until larger real data justifies it.

## How would the system scale?

The next storage step would be canonical Parquet/DuckDB for large run sets, but only after real data volumes justify it. The current architecture keeps that change behind storage boundaries.

## How would you validate with real operators?

First integrate real or sanitised Randy/SUMO artifacts. Then run task-based expert sessions: create/import/compare/interrogate diagnoses, measure task success and usefulness, and collect survey or interview feedback under appropriate ethics approval.

## What would you do next?

Request one complete real or sanitised Randy/SUMO output set with schemas, units, provenance, and execution contract. Then build the smallest evidenced adapter and run the existing validation, metrics, evidence, diagnostics, and UI pipeline over that sample.

Related documents:

- [Dissertation mapping](dissertation_mapping.md)
- [Traceability matrix](traceability_matrix.md)
- [Viva traceability demo](viva_traceability_demo.md)
- [Limitations and future work](limitations_and_future_work.md)

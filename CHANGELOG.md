# Changelog

## v0.1.0 - Standalone Prototype

Prepared the TrafficTwin repository as a self-contained research-software prototype.

Added:

- deterministic standalone synthetic scenario and run generator;
- reproducible demo workspace commands;
- multi-seed synthetic low-pressure experiment for R3 evidence;
- deterministic Markdown and standalone HTML report export;
- standalone Streamlit launcher command;
- release metadata and package-build guidance;
- GitHub Actions CI workflow;
- standalone demo, synthetic model, report export, and release documentation.

Notes:

- Licence not yet specified.
- Full Randy/VEC, SUMO, live data, LLM, XAI, and simulator launch support remain out of scope.

## Unreleased

Added an evidence-gated, read-only integration for Randy's separately supplied TOS Data result
package:

- evaluation-summary schema validation and idempotent registry import;
- source-provided task metric collections and partial EvidencePacks;
- safe NPZ key/shape validation, bounded replay, and per-arrival inspection;
- aggregate metric/rule provenance to the exact source CSV row and package fingerprint;
- Typer commands and a Streamlit `TOS Data Import` workflow.

The integration deliberately does not convert unresolved RSU fields to canonical infrastructure
metrics, launch the environment, or claim SUMO/live-data support.

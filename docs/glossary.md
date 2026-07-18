# Glossary

TrafficTwin: Import-first research software prototype for traffic and vehicular edge-computing what-if analysis.

OffloadLens: The VEC analysis module within TrafficTwin, focused on tasks, offloading decisions, latency, RSU pressure, and VEC diagnostics.

VEC: Vehicular edge computing; computation involving vehicles and roadside or nearby compute resources.

V2I: Vehicle-to-infrastructure offloading decision, represented internally as `v2i`.

V2V: Vehicle-to-vehicle offloading decision, represented internally as `v2v`.

RSU: Roadside unit; infrastructure element that may receive offloaded tasks.

Scenario seed: Versioned YAML scenario configuration represented by `ScenarioSeed`.

Run bundle: Directory or ZIP containing `manifest.yaml`, `seed.yaml`, and optional declared CSV files.

Canonical record: Internal Pydantic record with standard fields and source provenance.

EvidencePack: Versioned structured evidence object produced from validation and metrics; the only supported input to diagnostic rules.

DiagnosticReport: Versioned output from deterministic rule evaluation over an EvidencePack.

Historical replay: Timestamp-driven replay over imported or synthetic records, not live data.

Synthetic fixture: Small hand-auditable test/demo data created for engineering verification.

Import-first: Architecture where completed bundles are always supported and direct launch is optional only when evidenced by an adapter.

Task completion rate: Completed valid task records divided by generated valid task records.

Saturation episode: Maximal contiguous per-RSU sequence where utilisation is at or above the configured saturation threshold.

Diagnostic hypothesis: Evidence-based candidate explanation requiring verification; not a proven root cause.

Capability manifest: Three-valued adapter capability declaration using `true`, `false`, and `unknown`.

Provenance: Metadata connecting outputs to seed, run, environment, source files, random seed, versions, and algorithms.

Fingerprint: Deterministic hash used to identify bundle/evidence/report content for reproducibility checks.

Golden test: Test comparing deterministic output against a reviewed expected fixture.

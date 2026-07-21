# ADR-038 — Deterministic Bounded Measurement Imperfections

Status: accepted and implemented
Date: 21 July 2026
Capability: `EXP-03`

## Context

TrafficTwin needs reproducible experiments that test how its analysis behaves when generated
measurements contain bounded error or missing rows. The feature must not modify raw imported
evidence, fabricate a calibrated sensor model, alter clean task outcomes, or imply that an external
simulator ran. Process-global pseudo-random state would also make a field's result depend on call
order and on which unrelated fields were enabled.

## Decision

EXP-03 version 1.0 is an optional layer inside `SyntheticScenarioConfig` and the existing
standalone generator. It accepts only the closed `bounded_uniform` distribution with a separate
non-negative measurement seed.

Noise is limited to generated observations:

- vehicle source-frame `x`, `y`, and speed;
- traffic average speed and integer count; and
- infrastructure utilisation and integer queue length.

Each enabled field derives its error independently from SHA-256 over the method version, seed,
table, field, original generated-row index, and retained clean row. Continuous errors lie within
the declared symmetric bound. Integer errors lie in the declared inclusive integer range. Speeds,
counts, and queues clamp at zero; utilisation clamps to `[0,1]`; source-frame coordinates are not
clamped.

Dropout is available only for `infra_state`, `vehicle_state`, and `traffic_obs`. For a non-empty
table it drops `min(n-1, max(1, floor(n*fraction)))` rows by stable SHA-256 rank and retains at
least one row. Dropout occurs before noise and refers to original generated-row indices. It is an
exact controlled subset, not a Bernoulli or empirical missingness model.

The model caps position error at 100 m, speed errors at 20 m/s, traffic count and infrastructure
queue errors at 100, utilisation error at 0.5, and per-table dropout at 0.95. At least one parameter
must be active, and every targeted stream must be enabled.

Tasks, trips, incidents, all timestamps, decisions, completion, latency, target IDs, routing, and
task energy are unchanged. The layer does not reschedule, reroute, retrain, or launch SUMO,
Randy/VEC/TOS, or another producer.

Every impaired bundle embeds a strict typed audit in its manifest. The audit binds the complete
configuration, field semantics, observed error extrema, row counts, dropout selections, warning/
limitation text, and fixed synthetic/not-calibrated/raw-unchanged declarations. Semantic validation
requires exactly the audits implied by the configuration before verifying configuration and audit
fingerprints. Bundle and run IDs gain a stable impairment-configuration suffix. The disabled path
retains existing bundle bytes and identifiers.

Generation is published through the ordinary synthetic bundle writer. The writer builds a
temporary sibling and replaces only the exact destination after successful generation. Existing
outputs require explicit overwrite; broad protected and symbolic-link destinations are rejected,
and a failed build preserves the prior destination.

## Consequences

- The same scenario seed, model parameters, and measurement seed reproduce identical rows and
  audits.
- Enabling an unrelated field does not move another field's deterministic sequence.
- Clean task outcomes remain a stable reference while measurement-dependent evidence may change or
  become unavailable.
- Ordinary validation, metrics, comparison, diagnostics, reporting, and provenance can consume the
  output without a second analysis path.
- The audit makes every admitted bound and missing-row count inspectable.
- Real sensor fidelity, correlated errors, drift, and empirically calibrated dropout remain
  unresolved research work.

## Rejected Alternatives

- **Mutate imported bundles or raw files:** violates raw-source identity and the import-first
  evidence boundary.
- **Use global `random` state:** field results could change with execution order or unrelated
  settings.
- **Apply noise to task outcomes or timestamps:** would invent execution behavior rather than
  measurement imperfection.
- **Use unbounded Gaussian noise by default:** no calibration, variance, tail, or clamp basis is
  evidenced.
- **Independent Bernoulli dropout:** a nominal probability would not provide an exact controlled
  missing-row count for small deterministic fixtures.
- **Drop every row:** prevents inspection and ordinary evidence handling; version 1 retains one.
- **Call the fixture a sensor/network model:** deterministic software perturbations do not establish
  physical fidelity.
- **Implement formulas in Streamlit:** would duplicate the tested library contract and weaken audit
  consistency.

## Acceptance Evidence

- Unit tests pin determinism, independent field axes, seeds, bounds, clamps, exact dropout counts,
  retain-one behavior, untouched outcome tables, stream admission, audit semantics/fingerprints,
  disabled byte compatibility, capabilities, protected paths, and transactional overwrite.
- A golden projection pins known configuration/audit/dropout fingerprints, row counts, error
  extrema, observation samples, outcome-table identity, and synthetic boundary flags.
- CLI integration covers the public contract, strict config generation, ordinary validation,
  destination conflict, and invalid-config refusal.
- UI service and Streamlit AppTest coverage exercise enabled controls, fingerprinted preview, and
  audited bundle generation.
- Generated Pydantic schemas, CLI help, the public JSON contract, architecture, project records,
  usage guidance, and limitations expose the same boundary.

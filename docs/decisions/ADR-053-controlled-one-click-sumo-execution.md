# ADR-053: Controlled One-Click SUMO Execution and Automatic Import

- Status: accepted (implementation); real runtime acceptance pending a local SUMO 1.27.x binary
- Date: 2026-07-22
- Capability: `controlled_sumo_execution` (bounded post-v0.6 extension over `ING-01`)

## Context

TrafficTwin's SUMO adapter is deliberately import-only: it validates and imports completed
`tripinfo.xml`/`summary.xml` outputs but cannot produce them. Users who want a demonstrable local
SUMO run had no safe path, and any launcher risks becoming an arbitrary-command surface or an
implied claim about Manchester traffic or Randy's missing SUMO inputs. The accepted one-click VEC
workflow (ADR-052) established the orchestration pattern to follow.

## Decision

1. Add a typed orchestration library (`traffictwin.integration.sumo_execution`) composing, in
   fixed order: registry/output admission, controlled runtime discovery, read-only preflight, a
   fixed-argv foreground SUMO run in a private staged workspace, byte-identical input
   verification, atomic read-only publication, validation through the existing SUMO adapter, and
   one idempotent import through the existing `import_sumo_results` service. No second parser,
   metric engine, or importer exists.
2. Accept exactly one closed repository-owned preset, `synthetic_square_smoke`: an original
   TrafficTwin-authored scenario (one edge tracing a 100 m square perimeter, six deterministic
   vehicles, seed 42, 120 simulated seconds) with a pinned SHA-256 inventory. The Eclipse
   `square` scenario inputs are not vendored here, and Randy's missing SUMO inputs are neither
   reconstructed nor claimed. Every artifact is literal about being synthetic, non-Manchester,
   non-Randy, and not real-world validation.
3. Discover the runtime only through PATH, resolve that entry to a regular `sumo` file (including
   a normal package-manager symlink), and require a supported `1.27.x` version (the adapter's
   validated contract). Record its streaming SHA-256 identity and re-observe the exact name,
   version, and digest immediately before execution. No executable, flag, environment variable,
   script, URL, GUI, or module can be supplied; the argv is a fixed allowlist requesting
   `tripinfo.xml` and `summary.xml` with `shell=False` and a controlled environment.
4. Generate the adapter's exact `sumo-source.yaml` on success, declaring preset identity, the
   discovered SUMO version, synthetic status, the unspecified-repository-licence restriction
   (`redistribution_allowed: false`), and raw output checksums. Import identity is
   `sumo-exec-<output fingerprint[:16]>`, making re-import idempotent by stable fingerprint and
   conflicts visible through the existing registry conventions.
5. Persist a typed `SumoExecutionImportRecord` beside the receipt in the published directory and
   surface imported runs through the registry-backed inspector, which survives Streamlit
   restarts.
6. Keep generic `direct_launch` false everywhere. The new source-specific capability
   `controlled_sumo_execution` is conditional on request-specific preflight, and with no local
   SUMO binary the workflow reports the exact missing-runtime reason, keeps execution disabled,
   and never substitutes a fake process. Installation (for example `brew install sumo`) is a
   user decision TrafficTwin never performs.
7. Failed, timed-out, cancelled, rejected, malformed, partial, or input-mutating executions
   publish nothing and import nothing.

## Consequences

- One explicit UI action or one CLI command produces a validated, registered, clearly synthetic
  local SUMO run with end-to-end fingerprints and proven input immutability.
- The feature is implemented and stub-verified everywhere, but real runtime acceptance remains
  visibly unavailable until a supported binary exists locally; capability truth follows runtime
  evidence, not possession of code.
- Adding future presets requires repository review of new pinned inputs; users cannot widen the
  surface at runtime.

## Acceptance evidence

Unit/CLI/UI tests cover preset pinning, unsupported presets, missing/symlinked/unsupported
runtimes, hash mismatches, config-reference escapes, unsafe destinations, existing-output
refusal, fixed argv, shell-free execution, no-process-after-rejected-preflight, timeout,
cancellation, non-zero exit, partial/malformed/empty outputs, input mutation, output symlink and
tamper refusal at import, streaming hashing, adapter acceptance, automatic import, idempotent
re-import, visible registry conflict, capability truth, UI gating, persistent record inspection,
and CLI exit codes — using explicitly labelled synthetic stub executables that cannot satisfy the
separate real acceptance test, which runs only against a genuine supported binary.

## Rejected alternatives

- A general SUMO launcher, `sumo-gui`, or user-supplied scenarios/flags: rejected as an
  arbitrary-command surface.
- Vendoring the Eclipse `square` scenario inputs: rejected; reusing outputs' provenance without
  the official inputs would blur attribution, and an original minimal scenario is sufficient.
- Marking `direct_launch` true or claiming acceptance without a real binary: rejected; runtime
  truth requires a genuine run.
- A second output parser/metric path for generated results: rejected; the existing adapter is
  the only validation and import authority.

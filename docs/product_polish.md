# Product Polish & Research UX

This phase improves the standalone TrafficTwin research experience without adding new scientific
capability. It does not add Randy/VEC integration, SUMO integration, live Manchester feeds, new
metrics, new diagnostic rules, predictive models, LLM features, or autonomous decision making.

## Scope

Implemented polish areas:

- Guided Demo with separate standalone-synthetic and imported-TOS evidence tracks, routed to the
  existing pages without recomputing results.
- Experiment Planner for validated baseline/variation, policy-label, and common-random-seed design
  over registered seeds. Registration stores metadata only and creates no runs.
- Scenario Builder for editing documented `SyntheticScenarioConfig` fields and generating standard
  run bundles through the existing synthetic generator.
- Experiment Manager for browsing registered experiments, runs, seeds, policies, bundle
  fingerprints, comparisons, reports, metrics, and evidence availability.
- Report Dashboard for finding, downloading, and deliberately regenerating deterministic Markdown
  or HTML reports through the existing reporting module.
- Search page for local metadata search across runs, experiments, reports, metrics, rules, and
  source files.
- Settings page for session-scoped UI preferences such as replay speed and report format.
- About page for package, generator, metric, diagnostic, provenance, Python, commit, and licence
  metadata.
- Replay controls for play, pause, resume, restart, timestamp jumps, stepping, speed presets, and
  deterministic filters.
- Shared UI components for section headers, report cards, status badges, and metadata cards.

## Research UX Principles

- The UI remains thin: validation, metrics, evidence, diagnostics, provenance, and reports are
  computed by existing library modules.
- Synthetic data remains labelled synthetic.
- Direct launch remains unavailable unless a future adapter proves support.
- Missing evidence is displayed as unavailable rather than simulated.
- Report regeneration is explicit and user-triggered.
- Search is local and deterministic; no external service is used.

## Navigation

The polished navigation groups the workflow into:

- Home
- Guided Demo
- Experiment Planner
- Scenario Builder
- Bundle Import & Validation
- Experiment Manager
- Replay
- Run Overview
- Infrastructure & Congestion
- Comparison
- Journey-Time Lens
- Diagnostics & Evidence
- Provenance Explorer
- Reports
- Search
- Settings
- About

## Replay Controls

The replay page now supports:

- speed presets: `0.25x`, `0.5x`, `1x`, `2x`, `5x`;
- play, pause, resume, restart;
- step back and step forward;
- scrubber and timestamp jump;
- filters for vehicle, RSU, task class, and incident type when evidence exists.

The controls advance a logical replay clock only. They do not create missing telemetry or simulate
new records.

## Limitations

- Scenario Builder exposes only the current synthetic generator model.
- Settings are session-scoped; there is no user account or persistent profile system.
- Search is simple substring search over local metadata.
- Visual polish is intentionally restrained and Streamlit-native.
- No screenshots are generated automatically by this phase.
- Guided Demo explains the existing pipeline; it is not a simulator, training interface, or
  substitute for external validation.

## Related Documents

- [Standalone demo](standalone_demo.md)
- [Synthetic data model](synthetic_data_model.md)
- [UI design](ui_design.md)
- [User guide](user_guide.md)
- [Architecture](architecture.md)

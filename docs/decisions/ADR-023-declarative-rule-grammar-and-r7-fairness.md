# ADR-023 — Declarative Rule Grammar and R7 Operational Fairness

Status: accepted and implemented
Date: 20 July 2026
Capabilities: `DIA-02`, `DIA-04`

## Context

`MET-04` provides contract-gated vehicle-tier completion disparity and `MET-05` optionally
provides exact execution-target RSU completion groups. `DIA-02` requires R7 to identify a supported
outcome disparity, but the design also requires R7 to be the reference proof of the `DIA-04`
declarative mechanism. Hard-coding R7 before defining that boundary would violate its dependency.

Local YAML must not become arbitrary code execution or a second metric engine. A declarative rule
may select and compare already-computed EvidencePack metrics only. Missing, partial, semantically
incompatible, thin, or non-finite evidence must remain explicit. The project has no externally
calibrated universal fairness threshold and does not contain protected attributes.

## Decision

TrafficTwin implements a versioned, flat, closed `DeclarativeRuleDefinition` grammar. A trusted
local YAML document is limited to 65,536 UTF-8 bytes and 16 predicates. It is parsed with a safe
loader that rejects custom tags, anchors/aliases, duplicate keys, and multiple documents. Pydantic models
forbid unknown fields and bound identifiers, strings, lists, metadata checks, and recommendations.

The grammar admits only:

- `all` or `any` over one flat predicate list;
- finite numeric comparisons using `lt`, `lte`, `gt`, or `gte`;
- exact boolean equality;
- an already-scalar metric value, or the closed `mapping_max_gap` reducer;
- exact expected-unit and declared scalar metadata equality checks; and
- explicit minimum mapping-group count and per-group support for grouped evidence.

It admits no imports, Python names, calls, templates, regular expressions, paths, nested rule
references, user formulas, arithmetic expressions, dynamic metric lookup, `eval`, or `exec`.
Because rules cannot reference other rules, the grammar cannot contain a dependency cycle.

Compilation produces a `DeclarativeDiagnosticRule` that reads only `EvidencePack.metric_collection`
and returns an ordinary `RuleResult`. Every result records the definition fingerprint, grammar
version, trust boundary, condition mode, and predicate counts. A metric must exist, be `available`,
match the declared unit and metadata, and have the required scalar or complete finite mapping
shape. The compiler never recalculates a metric or treats null/missing values as zero.

Three-valued combination is deterministic:

- `all`: any false predicate supports `not_triggered`; all true predicates trigger; otherwise the
  result is `insufficient_evidence`;
- `any`: any true predicate triggers; all false predicates support `not_triggered`; otherwise the
  result is `insufficient_evidence`.

Definitions loaded from user-controlled local files must use a `LOCAL_` rule identifier. An
explicit in-process registry rejects reserved core identifiers and duplicate IDs before
evaluation. Built-in definitions are parsed through the same grammar but may use the reserved R7
identifier. There is no uploaded-rule UI or ambient rule discovery.

R7 v1.0 is an ordinary core rule backed by one of two built-in declarative definitions selected in
`R7Config`:

1. `vehicle_tier_completion` compares the existing contract-gated scalar maximum completion-rate
   gap across stable operational vehicle tiers.
2. `target_rsu_completion` applies `mapping_max_gap` to exact execution-target RSU completion-rate
   groups under the `TaskRsuTargetContract`.

The selected dimension is evaluated independently; TrafficTwin does not merge dimensions or infer
a spatial target. Both require at least two groups, at least two eligible observations per group,
complete contract-gated evidence, unit `ratio`, and an absolute gap at or above the configured
`minimum_outcome_gap`. The default `0.20` threshold is a provisional synthetic-development value.

R7 describes operational outcome disparity only. Vehicle tier is not a protected or demographic
attribute. Target RSU is an observed executing-resource grouping, not evidence that an RSU or its
location caused the outcome. A non-trigger does not prove fairness or good performance, and a
trigger is not a statistical significance test.

## Consequences

- `DIA-04` supplies a bounded trusted-local extension interface and R7 proves the same compiler can
  produce a core diagnostic result.
- R7 remains inside the EvidencePack boundary and generic provenance can trace its cited metrics
  to the existing fairness/spatial contracts and accepted-row ledgers.
- Threshold/config changes produce a different definition fingerprint and remain visible in the
  DiagnosticReport configuration.
- SUMO and TOS remain unavailable for R7 because their current contracts do not supply the selected
  operational-group evidence. They may still return explicit insufficiency.
- Declarative YAML is configuration, not a sandbox. Files are trusted local inputs, even though the
  grammar prevents direct code execution.
- Nested boolean expressions, string comparisons, arbitrary reductions, cross-run rules, temporal
  operators, custom recommendations with executable actions, and persistence/automatic discovery
  remain outside v1.0.

## Rejected Alternatives

- **Hard-code R7 first:** violates the explicit `DIA-04` dependency and does not prove the grammar.
- **Use Python expressions or `eval`:** creates an arbitrary-code surface and weakens auditability.
- **Allow arbitrary JMESPath/JSONPath or formulas:** introduces a second unbounded computation
  language and dynamic evidence selection.
- **Drop null or thin mapping groups:** can manufacture a disparity or hide one.
- **Combine tier and target-RSU evidence automatically:** changes the diagnostic population and
  interpretation without a declared scope.
- **Infer protected attributes or geographic meaning:** unsupported by the canonical contracts.
- **Treat a low gap as proof of fairness:** equal groups may still have uniformly poor outcomes.

## Acceptance Evidence

- Parser/compiler tests cover safe YAML, size/list/string bounds, duplicate keys, aliases, custom
  tags, multiple documents, reserved/duplicate IDs, invalid types/units/metadata, both boolean
  modes, scalar/boolean/mapping predicates, determinism, and definition fingerprints.
- R7 tests cover both dimensions, trigger/non-trigger boundaries, insufficient/partial/thin/null
  evidence, threshold overrides, alternatives, limitations, TOS/SUMO insufficiency, and provenance.
- CLI tests cover contract, validate, evaluate, and built-in fairness workflows; golden tests pin
  the static contract, R7 definition, and RuleResult projection.
- Fairness UI/service tests prove controls delegate to typed library evaluation.
- Generated schemas, rule catalogue, capability manifests, documentation, and repository quality
  gates are reconciled in the same increment.

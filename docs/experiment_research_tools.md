# Experiment Research Tools

TrafficTwin provides deterministic, import-first tools for analysing registered experiment
results. These tools operate on stored `MetricCollection` objects and registered
`ScenarioSeed` metadata. They do not launch a simulator, train a model, or invent missing pairs.

## Experiment EvidencePack

`build_experiment_evidence_pack` creates a first-class experiment-level `EvidencePack`. It
computes:

- policy count and cross-policy dispersion for a selected scalar metric;
- the configured always-local policy's gap from the best observed policy;
- an aggregate pressure indicator from available run metrics;
- count, maximum absolute gap, mean absolute gap, and mean signed gap for explicitly supplied
  training-validation pairs.

Missing scalar observations remain unavailable. Training-validation values are included only when
the caller explicitly declares a matched pair. Every pair must carry the same experiment, policy,
checkpoint, random seed, metric key/version, and unit at both endpoints. Across a multi-pair R5
analysis, the policy, checkpoint, metric contract, training environment, and validation environment
must remain fixed, and random seeds and run IDs must not be reused. Incompatible input is rejected
instead of averaged. The resulting pack can be stored in the additive
`experiment_evidence_packs` registry table and passed to the normal deterministic rule engine.

## R4 And R5

- R4 is a load-imbalance candidate. It requires capacity-normalised Jain balance, mean
  utilisation, and at least two observed RSUs. It does not prove a placement or routing cause.
- R5 is a training-to-validation drift candidate. It requires explicit paired observations and
  does not infer pairing from filenames, labels, or ordering. It does not prove overfitting.

Both rules use provisional synthetic-development thresholds. Real threshold calibration remains
external research work.

## Winner Map

`build_winner_map` groups compatible scalar observations by seed family and policy, computes each
policy's mean, deterministic rank, regret from the best value, and ties. Objective direction is
explicitly `maximise` or `minimise`. Missing or non-scalar metrics are skipped and reported through
warnings when no usable observation remains. A seed family is excluded if its observations mix
units, metric or implementation versions, environment provenance, or checkpoints for one policy.

The winner map is descriptive. It does not establish statistical significance or generalisation.

## Prospective Common-Seed Planning

`STA-05` can plan a future paired comparison from a researcher-declared target effect,
paired-difference variance, two-sided alpha, and target power. It returns the smallest bounded
common-seed pair count under a versioned normal approximation and always labels the result a
planning aid. It does not inspect the winner map or completed study, derive observed post-hoc
power, launch runs, or prove statistical significance. See
[paired common-seed power analysis](power_analysis.md).

## Transparent Portfolio Prototype

`default_synthetic_portfolio_rules` is an ordered, inspectable rule set over declared seed
features such as load intensity, T1 share, fleet tier mix, and RSU capacity mode. Every decision
records the matched rule and rationale. `evaluate_portfolio` joins those decisions to a winner map
and reports winner/tie rate and regret only where the selected policy was observed.

The default rule set and policy names are synthetic workflow demonstrations. They are not trained
algorithms, calibrated recommendations, or evidence of portfolio performance.

`evaluate_portfolio_study` fixes that ruleset before a disjoint development/held-out split,
evaluates the selector on both partitions, and compares every observed constituent on held-out
seed families. The demo workspace supplies five synthetic seed families, three policy profiles,
and three random-seed replicates per policy: three families are development inputs and S5/S6 are
held out. This verifies the study machinery only; it is not external or statistical validation.
The report includes selected-score and regret variability, min/max results, failure seed IDs,
per-constituent variability, and a pairwise held-out dominance matrix. It can be rendered as JSON,
CSV, or Markdown.

## S5/S6 And Event Authoring

The standalone generator adds two explicitly synthetic presets:

- `s5_stadium_event_siting`: a high-demand event and RSU-siting workflow fixture;
- `s6_road_clearing_corridor`: a lane-closure and demand-response workflow fixture.

Scenario Builder can author incident/event type, location, severity, start, duration, closed-lane
count, demand multiplier, and involved synthetic vehicle references. Those fields round-trip into
the seed and canonical `IncidentRecord`. The page can also export a linked incident-seeded what-if
variant without launching anything. Event demand affects generated synthetic observations. The
generator remains a deterministic software fixture, not SUMO or a calibrated Manchester model.

## Manual Protocol Tracking

Protocol tracking records external coordination without claiming execution. A slot follows:

```text
planned -> received -> validated -> matched -> complete
       \-------------------------------------> rejected
```

The SQLite tracker stores expected and observed run/bundle identifiers, status, note, and update
time. Invalid transitions are rejected. Tracking never executes a protocol slot or changes the
direct-launch capability.

## Bounded Parameter Sweeps

`EXP-01` accepts one strict synthetic configuration or scenario seed and expands one to four
closed scalar axes into at most 256 deterministic points. Seed-only mode writes parent-linked
snapshots. Local mode invokes only the labelled TrafficTwin synthetic generator, normal bundle
validation, and normal core metrics. External mode writes requests with `not_executed`, false
direct-launch support, and no command or launcher.

Every point records ordered assignments and request/base/point/seed fingerprints; local points
also record the exact bundle fingerprint. Response CSV rows carry the full assignments, metric
status/value/unit/reasons, run, seed, and bundle. Only finite numeric core metric values enter the
numeric response. See [Parameter sweep composer](parameter_sweeps.md) and [ADR-036](decisions/ADR-036-bounded-parameter-sweep-composer.md).

## Deterministic Scenario Mutations

`EXP-02` creates a new, ordinarily validated bundle from a valid source explicitly labelled
synthetic/evaluation. One request applies one closed row-dropout, bounded timestamp-jitter, or
exact-ID RSU-removal operator to a declared uncompressed CSV table. Row selection and timestamp
deltas derive from SHA-256 plus the request seed. RSU removal retains task targets because no
routing transition is evidenced.

The parent is unchanged, non-target files are byte-identical, every admitted changed row/file is
recorded, and output is published transactionally only after validation and fingerprint checks.
No operator launches an external simulator or establishes calibrated fault severity. See
[scenario mutation operators](scenario_mutations.md) and [ADR-037](decisions/ADR-037-deterministic-scenario-mutation-operators.md).

## CLI Examples

```bash
traffictwin experiment evidence --registry .demo/registry.sqlite \
  --experiment-id exp-standalone-demo --store --output experiment-evidence.json
traffictwin experiment winner-map --registry .demo/registry.sqlite \
  --experiment-id exp-standalone-demo --output winner-map.json
traffictwin experiment portfolio --registry .demo/registry.sqlite \
  --experiment-id exp-standalone-demo --output portfolio.json
traffictwin experiment portfolio-study --registry .demo/registry.sqlite \
  --experiment-id exp-synthetic-portfolio-study --format markdown \
  --output held-out-study.md
traffictwin experiment track-init --registry .demo/registry.sqlite \
  --experiment-id exp-standalone-demo
traffictwin experiment parameter-sweep \
  --request examples/parameter_sweep_request.yaml \
  --output build/parameter-sweep
traffictwin experiment mutate-scenario \
  --bundle .demo/bundles/baseline \
  --request examples/scenario_mutation_request.yaml \
  --output build/mutated-baseline
```

## Synthetic Measurement Imperfections

`EXP-03` adds a separate measurement seed and explicit bounded noise/dropout parameters to
`SyntheticScenarioConfig`. It can perturb only generated vehicle position/speed, traffic
speed/count, and infrastructure utilisation/queue observations, or drop an exact bounded subset of
the three observation streams. Clean tasks, trips, incidents, timestamps, outcomes, and routing are
unchanged. Each output embeds the complete configuration and field/dropout audit in its manifest.

Use the example directly:

```bash
traffictwin synthetic generate-config \
  --config examples/synthetic_measurement_imperfections.yaml \
  --output build/measurement-robustness
```

This is a deterministic robustness fixture rather than calibrated sensor or packet-loss evidence.
See [Synthetic measurement noise and dropout](measurement_imperfections.md) and
[ADR-038](decisions/ADR-038-deterministic-bounded-measurement-imperfections.md).

Use `track-list` to inspect slots and `track-update` to apply one valid manual transition.

## Evaluation Materials

Draft study materials are under `docs/evaluation/`. They include a draft ethics application,
participant task script, survey, interview guide, consent/privacy notes, and an anonymised result
schema. They are planning artifacts only: they have not been submitted or approved and must not be
used to recruit participants until the responsible institution confirms the process.
The directory also contains a `synthetic_mock` JSON fixture and deterministic descriptive-analysis
tooling. Those outputs validate software behavior only and are not participant evidence.

See [Advanced research tools](advanced_research_tools.md) for the expanded fault matrix,
case-study pack, provenance ledgers, PDF output, browser audit, corridor view, mock analysis, and
constrained findings renderer.

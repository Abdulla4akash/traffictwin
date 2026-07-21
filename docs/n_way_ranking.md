# N-Way Common-Seed Policy Ranking

TrafficTwin implements v0.5 `STA-02` as a deterministic extension of the existing descriptive
winner map. It ranks two or more registered policies independently inside each selected scenario
family, uses the same complete common-random-seed rows for every policy, and adds joint-bootstrap
uncertainty without inventing missing results or ranking incompatible contracts.

The method decision is [ADR-029](decisions/ADR-029-common-seed-n-way-ranking.md). Pairwise
baseline-versus-variation estimation and sign-flip testing remain the separate
[STA-01 workflow](statistical_studies.md).

## What It Answers

For each selected scenario family, the study can answer:

- which policy has the best compatible complete-seed mean for the declared maximise/minimise
  objective;
- which policies are numerically tied under the predeclared absolute tolerance;
- each policy's standard competition rank and original-unit regret from the best mean;
- the percentile-bootstrap interval for each policy mean;
- how often each policy receives every rank, including rank 1, under joint paired-seed resampling;
- which planned seeds were complete, incomplete, incompatible, duplicate, or missing;
- why any endpoint, random seed, or whole family did not receive a rank.

It does not establish equivalence, causal superiority, deployment suitability, external validity,
or a universal probability that a policy is best.

## Analysis Plan

`NWayRankingConfig` must be fixed before inspecting the result. It declares:

- one registered experiment;
- one or more scenario-family seed IDs;
- at least two registered policy/algorithm labels;
- one checkpoint selection;
- one finite scalar metric and objective direction;
- the exact expected common-random-seed set;
- an absolute numerical tie tolerance;
- confidence level, bootstrap repetitions, and deterministic seed.

The service sorts set-like config fields before fingerprinting them. Defaults are a 95% interval,
10,000 repetitions, seed `20260720`, tolerance `1e-12`, and at least three complete compatible
seed rows. Repetition counts must be from 1,000 through 100,000.

## Cohort And Missingness

The pairing key is exact `random_seed`. One complete row contains exactly one endpoint for every
selected policy inside one scenario family. A missing, unavailable, partial, invalid, non-finite,
duplicate, or provenance-incomplete endpoint excludes that seed from every policy denominator.
TrafficTwin never zero-fills or mean-imputes the endpoint.

Within a complete seed, all policy endpoints must agree on metric-collection version, metric
implementation version, unit, synthetic label, environment name/version-or-commit, and any
applicable energy, fairness, plugin, target-RSU, or spatial semantic fingerprints. Incompatible
seeds are audited and excluded. The remaining complete rows must share one family-wide signature;
if they do not, the whole family is `incompatible` and TrafficTwin selects no subgroup.

With one or two complete rows, the filtered winner map can still show a descriptive mean/rank, but
the family is `insufficient` and every uncertainty field is unavailable. Three or more compatible
complete rows are required for an `available` ranking.

## Ranking And Ties

TrafficTwin sends only the admitted complete cohort to `build_winner_map`. This preserves one
ranking definition:

- maximise sorts larger means first; minimise sorts smaller means first;
- standard competition ranks are used (`1, 1, 3` for a two-way tie at the top);
- values within the configured absolute tolerance share a rank;
- regret is the non-negative original-unit distance from the best mean.

The tolerance handles numerical equality only. A winner-map tie is not TOST equivalence, and
confidence-interval overlap never creates or removes a tie.

## Joint Paired Bootstrap

For each repetition, the evaluator resamples complete random-seed rows with replacement and keeps
all policies together. It calculates every policy mean and applies the ordinary winner-map ranking
to that joint replicate. Outputs include:

- linear-interpolated percentile endpoints for each policy mean;
- rank-frequency distribution;
- top-rank frequency, including tied rank 1;
- percentile rank bounds.

Each scenario family receives a deterministic seed derived from the configured seed and family ID.
Adding another family or changing input order therefore cannot change an existing family's
resamples. No hypothesis test is performed, so the multiple-comparison policy is explicitly
`not_applicable_joint_descriptive_ranking_no_hypothesis_tests`.

## UI Usage

1. Register an experiment with at least two policies and a common-random-seed set.
2. Import and compute the completed `MetricCollection` for every planned policy/seed slot.
3. Open **Analysis → Statistical Study**.
4. Select **N-way policy ranking (STA-02)**.
5. Choose scenario families, policies, checkpoint, metric, objective, interval, repetitions,
   resampling seed, and tie tolerance before evaluating.
6. Inspect every family status, complete-seed count, missingness/incompatibility audit, policy
   rank, interval, and rank frequency.
7. Download JSON, Markdown, or the combined rank/observation/exclusion CSV.

The page stores the last result only in Streamlit session state. It does not persist a study,
remove seeds, change experiment plans, or alter metric evidence.

## CLI Usage

Publish the method boundary:

```bash
traffictwin experiment n-way-contract --format json
```

Rank every policy and scenario family in the registered experiment:

```bash
traffictwin experiment n-way-ranking \
  --registry .demo/registry.sqlite \
  --experiment-id exp-standalone-trivial \
  --metric task.completion.rate \
  --objective maximise \
  --bootstrap-repetitions 10000 \
  --resampling-seed 20260720 \
  --tie-tolerance 0.000000000001 \
  --format json \
  --output n-way-ranking.json
```

Repeat `--algorithm POLICY` to rank an explicit registered subset. Formats are `json`, `markdown`,
and `csv`. An entirely insufficient/incompatible result is still emitted as a typed audit artifact
and returns exit code 1; `available` and partially available multi-family results return 0.

## Python Usage

```python
from traffictwin.experiments.n_way_ranking import (
    NWayRankingConfig,
    evaluate_n_way_ranking,
)

plan = NWayRankingConfig(
    experiment_id="exp-policies",
    seed_ids=["seed-baseline", "seed-stress"],
    algorithms=["policy-a", "policy-b", "policy-c"],
    metric_key="task.completion.rate",
    objective="maximise",
    expected_random_seeds=[1, 2, 3, 4, 5],
    bootstrap_repetitions=10_000,
    resampling_seed=20_260_720,
)

study = evaluate_n_way_ranking(metric_collections, plan, seed_aliases=seed_aliases)
print(study.status)
print(study.entries[0].policy_ranks)
```

Callers should validate selections against the registered experiment, as the CLI/UI services do.
The pure evaluator accepts completed metric artifacts and explicit aliases so it can also be used
in tested library workflows.

## Artifact And Provenance

`NWayRankingStudy` contains:

- the complete config and fingerprint;
- an embedded filtered `WinnerMapReport`;
- complete multi-policy observations with run, source-input, and collection fingerprints;
- a family audit with expected/complete/missing/incomplete/incompatible/duplicate seeds and stable
  exclusion codes;
- descriptive ranks and joint-bootstrap uncertainty;
- method-contract and source-sequence fingerprints;
- assumptions, warnings, limitations, and a timestamp-normalised study fingerprint.

Raw inputs and stored metric collections are not changed. Current generic/synthetic registered
experiments advertise `n_way_policy_ranking: true`; current SUMO and TOS adapters advertise
`false` because they do not provide this registered compatible repeated-policy boundary.

## Interpretation Limits

- Rank frequency is empirical resampling stability, not Bayesian posterior probability.
- A confidence interval is not an equivalence region or deployment threshold.
- A numerical tie is not practical equivalence; `STA-03` remains separate.
- Ranking on one metric does not automatically optimise another metric.
- Missing seeds can change the eligible estimand and must be reported with the result.
- Synthetic policy-profile rankings validate code and method behavior only.
- The artifact contains deterministic lineage, not causal attribution.

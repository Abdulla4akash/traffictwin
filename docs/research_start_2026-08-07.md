# Research Start Status — 7 August 2026

TrafficTwin now has the source material, software foundation, and local SUMO
toolchain needed to begin the next research phase. This record inventories what
is available and separates possession of the materials from verified
end-to-end reproduction. It does not change any formal `MAN-*`, `UX-*`,
`REL-01`, VEC, or gate status recorded elsewhere.

## Secured research assets

The following repositories are preserved as authorised private GitHub mirrors:

| Repository | What it contains | Current/default reference | Reviewed research snapshot |
|---|---|---|---|
| [TrafficTwin](https://github.com/Abdulla4akash/traffictwin) | Deterministic experiment, evidence, comparison, provenance, diagnostic, Manchester, SUMO, and VEC-integration platform | default `main`; `codex/traffictwin-v0.7` is the active development branch | immutable v0.6 and v0.7 alpha records remain in the repository |
| [vec_env](https://github.com/Abdulla4akash/vec_env) | PhD student Randy's VEC environment, PyTorch and JAX implementations, MAPPO/IPPO training, evaluation, Manchester traces, validation, SLURM launchers, and reproduction guidance | `main` at `0f01f4d2082d3e8b735e74a873095ab8eeba37cc` | `archive/traffictwin-reviewed-20260719` at `068b4ea33e640f206ce6a7d04f3d6fae2ac831f4` |
| [tos-data](https://github.com/Abdulla4akash/tos-data) | TOS/VEC traces, evaluation outputs, instrumented task data, training records, trip information, and frozen MAPPO actors | `main` at `a75bbdb1a956f828ee0e9b97b33506bd32d31b85` | `archive/traffictwin-reviewed-20260719` at `f6c67acbed3360dba3a0d5c8d1fd557caa99ecff` |

The mirrors preserve the GitLab histories and reviewed commits without changing
the original GitLab repositories. They are private; their existence does not
authorise public redistribution or broaden any publication claim.

## Tooling and platform already available

- Eclipse SUMO **1.27.1** is installed locally. The upstream reproduction notes
  specify SUMO 1.27.0, so normal use is available while a bit-exact study must
  record and, if necessary, test the patch-version difference.
- TrafficTwin has an existing locked Python project environment, deterministic
  tests, import and comparison boundaries, provenance tooling, experiment
  planning, report generation, Manchester data integration, and controlled
  SUMO/VEC interfaces.
- The VEC source package documents Python 3.11 environments for PyTorch and JAX,
  including the pinned JAX stack used for its main MAPPO/IPPO experiments.
- Frozen actor checkpoints and the data needed for the reviewed VEC evaluation
  path are present in the private data mirror.

## What is already built

Existing TrafficTwin project records describe substantial completed foundations:

- deterministic bundle validation, metrics, comparisons, diagnostics, and
  result-to-source provenance;
- experiment registration, parameter sweeps, robustness tools, reports, and
  evidence exports;
- the evidence-gated VEC integration path, including source auditing, schema
  semantics, joins, preprocessing, controlled evaluation, reproduction checks,
  scientific admission, and private research artifacts;
- real Manchester foundations involving DfT observations, network construction,
  candidate map matching, temporal profiling, candidate demand, controlled SUMO
  execution, and comparison boundaries;
- bus-specific live-evidence foundations through BODS, while preserving the rule
  that bus locations are not general road-traffic measurements; and
- separate National Highways operational evidence and TfGM infrastructure
  evidence, each kept within its actual coverage and meaning.

Formal capability truth remains governed by
[`implementation-status.md`](implementation-status.md). In particular, existing
candidate workflows, unreviewed matches, blocked stages, or available source
packages must not be presented as supervisor approval, scientific validation,
accepted real-world calibration, or causal evidence.

## Research thread 1 — supervisor-aligned VEC experiments

The immediate purpose of this thread is to reproduce and then interrogate the
reviewed VEC work rather than treating its outputs as unquestioned facts.

The detailed analysis of Randy's queue-limit results, evaluator changes,
RSU-load observation proposal, deadline-aware dispatcher, Kubernetes baseline,
and proactive-scaling opportunity is recorded in
[`randy_email_research_analysis_2026-08-07.md`](randy_email_research_analysis_2026-08-07.md).

1. Create and verify the pinned Python/JAX/PyTorch environments.
2. Replace machine-specific CSF paths with explicit local or account-specific
   configuration without changing scientific parameters.
3. Run the VEC validation battery against the reviewed code and actors.
4. Reproduce one frozen baseline result end to end and record code, data,
   checkpoint, seed, environment, and SUMO identities.
5. Only after reproduction, run controlled comparisons for incidents, fleet
   composition, demand regimes, observation encodings, MAPPO/IPPO differences,
   and training-to-evaluation transfer.
6. Report sensitivity, failure modes, and negative results—not merely the best
   score—and keep descriptive evidence separate from causal claims.

This gives the supervisor-requested work a defensible starting point while
allowing TrafficTwin to test whether the inherited assumptions and policies
remain stable under realistic changes.

## Research thread 2 — independent live-bus and prediction research

This is a separate research contribution centred on real Greater Manchester bus
operations rather than an extension of the inherited VEC experiment alone.

Candidate research questions include:

1. How accurately can short-horizon bus position, arrival time, delay, and
   service-reliability outcomes be predicted from recent BODS trajectories?
2. Does adding historical DfT counts, National Highways operational events,
   network structure, time-of-day, weather or other permission-safe context
   improve prediction beyond a bus-only baseline?
3. Where and when do prediction errors become systematically worse—by corridor,
   service pattern, congestion regime, incident state, or evidence freshness?
4. Can calibrated SUMO counterfactuals help investigate disruption and recovery
   without misrepresenting simulation as observed reality?
5. Can an agentic research assistant help analysts assemble evidence, run
   approved deterministic tools, compare registered experiments, and explain
   model outputs with provenance—without allowing an LLM to calculate metrics,
   invent findings, or replace the prediction model?
6. Which predictive model family gives the best accuracy, calibration,
   robustness, computational cost, and interpretability trade-off: simple
   statistical baselines, gradient-boosted trees, temporal neural models,
   graph-based models, or carefully bounded hybrids?

The first comparison must include simple baselines. An LLM or agent is a
tool-using explanation and workflow layer, not the source of numerical truth.

## Immediate research-start gate

The project is ready to **start research**, but it must not yet claim that every
external experiment is locally reproducible. The first concrete milestone is:

> reproduce one reviewed VEC baseline from the pinned private code, data, actor,
> seed, environment, and SUMO identities, then register the resulting evidence
> in TrafficTwin before introducing a new experimental variable.

In parallel, the independent bus thread can begin with a bounded BODS dataset,
a clear prediction target and horizon, a leakage-safe train/validation/test
split, and at least one naive baseline. Provider credentials, raw vehicle
identifiers, private snapshots, and machine-specific paths remain outside Git.

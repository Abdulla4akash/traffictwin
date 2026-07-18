# Dissertation Evaluation Plan

This plan separates evidence that TrafficTwin can report now from evaluation that remains blocked.
It is a reporting plan, not a dissertation chapter or a claim of external validity.

## Evaluation Strands Available Now

### 1. Software Correctness and Reproducibility

Report:

- schema validation and stable finding codes;
- deterministic metric, EvidencePack, diagnostic, and provenance outputs;
- directory/ZIP equivalence;
- fixed-clock golden tests;
- package fingerprints and source-row provenance;
- test count, coverage, lint, typing, package-build, and clean-install results.

### 2. Standalone Synthetic Demonstration

Use the baseline, stressed demand, under-offloading, infrastructure bottleneck, mixed fault,
partial-evidence, and trivial multi-algorithm fixtures. State explicitly that these cases verify
software behavior and rule implementation, not real traffic or VEC validity.

### 3. Imported TOS Descriptive Analysis

Use only the source-analysis catalogue:

- deadline-success rate overall and by task class;
- mean latency across all arrivals;
- mean energy per arrival;
- local, V2I, V2V, and offload shares.

Report campaign/cell/fleet sample size, mean, sample standard deviation, minimum, maximum, and exact
common-seed paired differences. Do not silently substitute TrafficTwin canonical completion for the
source deadline-success measure.

### 4. Reproducibility and Domain Audit

Report the package fingerprint, package commit, semantics-evidence commit, artifact coverage,
training-history matching, and conservative in-domain/held-out/unknown labels. Do not claim the
semantics-evidence commit produced every supplied result.

### 5. Research UX Demonstration

Demonstrate scenario authoring, bundle validation, replay, comparisons, diagnostic readiness,
provenance, report export, TOS results exploration, and explicit unavailable states. Evaluation of
usability by participants requires supervisor confirmation and any necessary ethics process.

## Interpretation Rules

- Describe observed differences and candidate hypotheses; do not claim causes.
- Report replicate counts and unmatched seeds.
- Keep training curves separate from Manchester evaluation results.
- Treat RSU concurrency pressure as a source inspection value, not CPU utilisation.
- Do not derive trip duration from recycled FCD slots.
- Do not publish Randy-derived aggregate values without permission.
- Keep provisional diagnostic thresholds labelled as synthetic-development defaults.

## Blocked Evaluation

| Evaluation | Missing evidence |
|---|---|
| Canonical TOS completion metrics | Eventual physical completion and stable identities |
| Real R1 assessment | Vehicle tier/task-class cross-tab and decision-time context |
| Real R2 assessment | Task failures aligned to reliable infrastructure state |
| Journey-time assessment | `tripinfo` or equivalent trip records |
| Executable reproduction | Producer commit, writer, checkpoint, portable paths, runtime smoke |
| Public TOS atlas | Written publication permission |
| Public source release | Explicit licence selection |

The current state of these gates is generated with:

```bash
traffictwin integration tos readiness TOS_DATA_PATH --format json
```

## Suggested Dissertation Evidence

- architecture and deterministic evidence-flow diagrams;
- run-bundle and canonical-record contract tables;
- validation-code and metric-catalogue extracts;
- baseline-versus-stressed synthetic comparison table;
- selected TOS campaign matrix and paired-comparison table, subject to permission;
- reproducibility audit and provenance trace;
- screenshots following the private supervisor-pack checklist;
- limitations table copied from the machine-readable readiness report.

## Related Documents

- [Dissertation mapping](dissertation_mapping.md)
- [Testing strategy](testing_strategy.md)
- [Comparison methodology](comparison_methodology.md)
- [Fault-injection methodology](fault_injection_methodology.md)
- [Integration readiness gates](integration/readiness_gates.md)

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

### 6. Executed VEC Reproduction and Controlled Execution (accepted v0.6 chain)

Report from recorded evidence, not plans: the audited source snapshot (`VEC-01`), exact
identity/task/trip joins over the weekend scenario (`VEC-03`–`VEC-05`), the allowlisted
foreground runner (`VEC-07`), the local CPU full-protocol reproduction graded
**numerically equivalent** for the pinned weekend case (`VEC-08`), and the 18-metric scientific
admission of the audited `_s102` source run with eight metrics typed unavailable (`VEC-09`).
Trip-duration metrics exist over the exact-ID matched complete-trip cohort; canonical
journey-time claims beyond that cohort remain out of scope.

### 7. Predeclared Capacity Study Pipeline (owner-approved candidate, in progress)

Report the instrument and its discipline: predeclaration committed before results
([capacity pilot](evaluation/capacity_squeeze_pilot_predeclaration.md)), byte-bound approval,
disjoint pilot/held-out seeds, fresh-run admission with typed refusals
([ADR-061](decisions/ADR-061-vec-fresh-run-scientific-admission.md)), the measured
verification-precision defect the first wide-trace run exposed, and measured run costs
(`we` 225.7 s, `inc` 3,555.96 s). Pilot outputs are exploratory candidate evidence; only a
separately signed confirmatory protocol on the held-out seeds may carry a finding.

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
| Canonical TOS completion metrics | Eventual physical completion and stable identities (still absent from the audited source) |
| Real R1 assessment | Physical T1 completion and canonical infrastructure utilisation |
| Real R2 assessment | Canonical utilisation, queue trend, and confirmed execution targets |
| Journey-time beyond the matched cohort | Trip evidence outside the exact-ID matched complete-trip cohort; occupancy-censored vehicles stay excluded |
| Confirmatory capacity finding | The signed confirmatory protocol and its untouched held-out seeds `{10–14}` |
| Manchester observed-versus-simulated comparison | A non-gridlocking demand candidate, approved calibration, an accepted baseline/FCD pair |
| Participant usability evaluation | Ethics approval and supervisor confirmation; recruitment must not precede them |
| Public TOS atlas | Written publication permission |
| Public source release | Explicit licence selection |

Resolved since the original version of this table: executable reproduction was completed and
graded numerically equivalent for the pinned weekend case (`VEC-08`), and `tripinfo`-based
trip joins exist (`VEC-05`) — journey-time evidence is now bounded by cohort semantics rather
than absent records.

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

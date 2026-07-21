# VEC-09 Scientific Admission

VEC-09 is the deterministic boundary between Randy/VEC source evidence and TrafficTwin metrics or
diagnostic rules. It admits only definitions whose denominator, unit, row level, and outcome
semantics are supported by the audited evidence. It never calibrates a threshold, emits a finding,
or renames deadline success as physical task completion.

## Accepted scope

The acceptance case uses the audited `fcd_s102_uk2030_we_fs0` task evidence, the matching weekend
identity/trip join, and the accepted VEC-08 numerical-reproduction report. The `_s102` best-of-seeds
label is preserved. VEC-08 establishes the pinned evaluator path separately; it is not represented
as a reproduction of this selected `_s102` evidence row.

The service produces an ordinary `EvidencePack` containing 18 available metrics:

- existing task count, mean latency, decision-share, and offload-rate definitions;
- existing trip-duration definitions over the exact-ID matched complete-trip cohort only; and
- five explicitly TOS-specific deadline-success, operational slot-tier, and no-eligible-target
  definitions.

Eight tempting but unsupported metrics are included as typed `unavailable` results: physical task
completion count/rate, per-completed-task energy, canonical infrastructure utilisation/queue,
confirmed-target RSU completion, protected-attribute vehicle-tier fairness, and trip completion
over the occupancy cohort. Absence is therefore visible to every downstream consumer.

## Rule readiness

VEC-09 performs readiness analysis, not rule evaluation:

- R1 is blocked because physical T1 completion and canonical infrastructure utilisation are absent.
- R2 is blocked because canonical utilisation, queue trend, and confirmed execution targets are
  absent.
- R6 is conditional because a temporal deadline-success/latency study is constructible, but its
  windows, threshold, and development/held-out split must be predeclared separately.
- R7 is blocked because operational slot-tier deadline success is neither a stable vehicle
  attribute nor physical-completion fairness.

Every readiness record fixes `threshold_evaluated=false` and `finding_emitted=false`. No result in
the report is a diagnosis or a causal conclusion.

## Reproduce the acceptance record

From the repository root, with the audited `tos-data` clone clean and its `origin/main` at the
pinned commit:

```bash
uv run python scripts/verify_vec_scientific_admission.py \
  --tos-data-repo ../external/tos-data \
  --reproduction-report docs/reference/generated/vec_reproduction_report.json \
  --output docs/reference/generated/vec_scientific_admission_report.json
```

The verifier reads exact Git blobs with `git show`; it does not check out, edit, or copy raw data
into the documentation tree. Publication contains aggregate values, hashes, relative source paths,
and report fingerprints only—never raw vehicle IDs or private machine paths.

Library consumers call `build_vec_scientific_admission(...)` with already validated VEC-03,
VEC-04, VEC-05, and VEC-08 evidence. The service rebuilds the VEC-04 report from the supplied
arrays, checks the trip identity/source binding, and fails closed on any mismatch.

## Evidence and tests

- Contract: `docs/reference/generated/vec_scientific_admission_contract.json`
- Acceptance report: `docs/reference/generated/vec_scientific_admission_report.json`
- Library: `src/traffictwin/integration/vec_science/`
- Verifier: `scripts/verify_vec_scientific_admission.py`
- Synthetic golden/refusal tests: `tests/unit/test_vec_science.py`
- Published-record tests: `tests/integration/test_vec_scientific_admission.py`

VEC-09 does not enable a CLI/UI Run control, canonical VEC conversion, external execution, public
hosting, or the VEC-12 research object. VEC-10–VEC-12 have since passed their separate gates; this
VEC-09 artifact still carries none of those capabilities by itself.

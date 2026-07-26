# ADR-061: Fresh-Run Scientific Admission as a Separate Candidate Policy

- Status: accepted (owner-directed candidate research policy, 26 July 2026)
- Date: 2026-07-26
- Capability: none accepted or changed; research-instrument groundwork consumed by the
  planned VEC experiment chain. Extends nothing in [ADR-052](ADR-052-one-click-vec-execute-and-import.md);
  it composes with it.

## Context

Every planned dissertation experiment (capacity squeeze, fleet mismatch, scenario
robustness) runs the pinned evaluator through VEC-07 and compares arms with the STA-01
paired-study tooling. The independent experiment-readiness review found the chain severed in
the middle, and the code confirmed it:

- A fresh VEC-07 receipt carries `scientific_admission: false` as a type-level literal, and
  the VEC-10 one-click import stores `scientific_admission_status: "unavailable"` with zero
  metric rows. An imported execution is structural provenance only.
- The accepted VEC-09 admission binds the audited `_s102` source run: its metric stamps
  (`experiment_id=None`, `seed_id == run_label`, `random_seed=0`,
  `algorithm="audited-vec-source"`) can never satisfy STA-01 pairing, its `EvidencePack` is
  never imported into any registry, and its entry gate requires the VEC-08
  `numerically_equivalent` grade that no fresh run has.
- STA-01 consumes only registry metric collections whose per-metric run context declares a
  real experiment, arm, and pairing seed. `register_bundle_import` alone never yields
  study-visible metrics; `store_metric_collection` is the only entrance.

So long runs could complete perfectly and still be scientifically invisible — the
highest-risk failure mode named in the review ("inadmissible output").

## Decision

1. **A new, separate policy** — `vec-fresh-run-scientific-admission-1.0` in
   `traffictwin.integration.vec_fresh_admission` — admits fresh executions. No existing
   contract is relaxed: the VEC-07 receipt literal, the VEC-10 record literal, and the
   accepted VEC-09 artifact are untouched, and the new module consumes only public APIs.
2. **Honest grading instead of borrowed grading.** The admission records
   `reproduction_graded: False` as a type-level literal. Passing the audited VEC-08
   fingerprint alongside fresh arrays would have satisfied VEC-09's entry check while
   binding a grade from a different execution — exactly the fabrication the review warned
   about — so the policy refuses that route structurally rather than by convention.
3. **Same definitions, different stamp.** The 12 available metric definitions are
   intentionally identical to the accepted VEC-09 admission and a drift-guard test asserts
   value equality on shared fixtures. The eight VEC-09 unavailable metrics remain
   unavailable with the same blockers. Trip metrics are excluded: trip evidence is
   trace-level SUMO output that does not vary with the evaluated policy, and admitting it
   per-run would manufacture identical "results" across arms.
4. **Evidence discipline matches the import path.** Only a `completed` receipt with
   re-verified published bytes is admissible; identity evidence comes from exact Git blobs
   at the audited `tos-data` commit; the full VEC-04 task join revalidates every array
   before any metric exists; truncated (smoke) executions and unreviewed traces refuse with
   typed codes (`TRUNCATED_EXECUTION_REFUSED`, `UNREVIEWED_TRACE_REFUSED`).
5. **Pairing context is declared, never fabricated.** The caller names the experiment, the
   arm, and which executed seed field pairs the run; the seed value is read from the
   receipt's request and the record validates the correspondence. The strongest permitted
   label is `owner_approved_candidate`; analyst review and supervisor approval are
   type-level `False` literals.
6. **Both registry writes or neither.** Admission registers the run
   (`vec:fresh:<fp16>`, bundle `vec-fresh:<fp>`) and stores the metric collection in one
   service call, because a run row without metrics reproduces the exact gap this policy
   closes.

## Consequences

**What this unblocked.** One fresh, full-length VEC-07 execution can now become admitted
registry metrics that pair in `evaluate_paired_statistical_study` without manual
relabelling — proven end-to-end on synthetic fixtures (six admissions → registry → STA-01
`available`, three pairs). The capacity-squeeze pilot's evidence route exists.

**What it did not change.** No `VEC-*` or `MAN-*` capability moves; VEC-11/VEC-12
packaging still binds the audited source run only; publication permission is unchanged.
The remaining experiment-readiness items are separate slices: a real full-length run
(the 7,200 s runner ceiling versus the 15,306 s historical maximum is an open measured
risk), admission of further audited traces via VEC-06 receipts, CLI/UI wiring, and the
predeclared confirmatory protocol.

**Cost.** The 12 metric definitions exist twice (VEC-09 and here) by design, guarded by a
parity test; unifying them would mean editing the frozen accepted module, which was
rejected as higher-risk than duplication under a drift guard.

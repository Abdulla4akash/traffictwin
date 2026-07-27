# Fresh-Run Scientific Admission (owner-approved candidate)

Status: implemented candidate policy `vec-fresh-run-scientific-admission-1.0` (ADR-061).

This policy closes the fresh-run evidence gap identified in the v0.7 experiment-readiness
review: a completed VEC-07 execution used to remain structural evidence with zero scientific
metrics, so no locally executed run could ever reach the STA-01 paired-study tooling. The
policy computes the accepted deterministic VEC metric definitions over one re-verified fresh
execution and stores them as a registry metric collection bound to the execution receipt.

It is an **owner-approved candidate research policy**. It is not supervisor approval, not
analyst review, not VEC-08 reproduction grading, and not a change to any accepted VEC-09,
VEC-10, or capability boundary. The VEC-10 import record keeps its literal
`scientific_admission_status: "unavailable"`; this policy produces a separate artifact.

Library: `traffictwin.integration.vec_fresh_admission`

## What one admission does

1. Re-reads `execution_receipt.json` and refuses anything that is not a `completed` receipt
   with verified immutable sources.
2. Re-hashes every published output byte-for-byte against the receipt inventory.
3. Refuses a truncated execution (`TRUNCATED_EXECUTION_REFUSED`): a smoke run's arrays can
   never reconcile against the trace identity and are never scientific evidence.
4. Refuses any trace outside the pinned reviewed set (`UNREVIEWED_TRACE_REFUSED`). The set
   holds the weekend trace and, per the measured probes of ADR-062 and ADR-065, the `inc`
   incident trace and the `ev` event-night trace; `wd_am` and `wd_pm` stay refused until
   their own reviewed extensions.
5. Reads the trace and occupancy identity evidence as exact Git blobs from the audited
   `tos-data` commit — the clone must be clean with `origin/main` at that commit — and
   verifies the trace hash against the executed request.
6. Rebuilds the vehicle identity snapshot and the full VEC-04 task join, which revalidates
   every array against the trace identity before any metric exists.
7. Computes the same deterministic metric definitions as the accepted VEC-09 admission
   (12 available), stamped with the caller's declared study context; the eight VEC-09
   unavailable metrics stay unavailable with the same blockers, and trip metrics are
   deliberately excluded as trace-level evidence.
8. Registers one run (`vec:fresh:<receipt fingerprint16>`) through
   `register_bundle_import` **and** stores the metric collection through
   `store_metric_collection` — the second write is what makes the run visible to STA-01.

## Study context and pairing

Every metric carries a caller-declared `VecFreshRunStudyContext`: the experiment id, the
arm label (`seed_id`), and which executed seed field (`fleet_seed` or `evaluator_seed`)
supplies the STA-01 pairing `random_seed`. The seed value is always read from the receipt's
request, never typed in, and the record validates the correspondence. With a registered
`Experiment` plan supplying `common_random_seed_set`, admitted runs pair directly in
`evaluate_paired_statistical_study` with no manual relabelling.

## Library use

```python
from traffictwin.integration.vec_fresh_admission import (
    VecFreshRunStudyContext, VecPairingSeedSource, admit_vec_fresh_run,
)

record, outcome = admit_vec_fresh_run(
    "./local-evidence/cap-sweep/cap25-fs0",
    ".demo/registry.sqlite",
    VecFreshRunStudyContext(
        experiment_id="vec-capacity-squeeze-pilot",
        seed_id="cap-2.5",
        pairing_seed_source=VecPairingSeedSource.FLEET_SEED,
    ),
    tos_data_repo="../external/tos-data",
)
```

The pure computation (`build_fresh_run_admission`) and the registry write
(`register_fresh_run_admission`) are separately callable and separately tested.

## Scientific and publication limitations

- The execution was **not** VEC-08 reproduction-graded; numerical equivalence with the
  audited source engine is not claimed for any fresh run, and the accepted `_s102` VEC-09
  artifact is neither reused nor altered.
- Deadline success is never physical completion; action selection is never a confirmed
  transfer; aggregate energy is never per-task energy.
- `owner_approved_candidate` is the strongest permitted label. Forbidden labels
  (`scientifically_validated`, `ground_truth`, `publication_approved`, `causal`,
  `production_deployment_ready`) are structurally absent from the record.
- Admission grants no publication permission; VEC-11 packaging remains the only
  publication path, and VEC-11/VEC-12 continue to bind the audited source run only.

## Evidence and tests

- Library: `src/traffictwin/integration/vec_fresh_admission/`
- Decision record: `docs/decisions/ADR-061-vec-fresh-run-scientific-admission.md`
- Synthetic admission/refusal/STA-01-chain tests: `tests/unit/test_vec_fresh_admission.py`
- Real-artifact chain tests (skip until a published full run exists):
  `tests/integration/test_vec_fresh_admission_chain.py`, driven by
  `TRAFFICTWIN_VEC_FRESH_RESULT_DIR` and `TRAFFICTWIN_TOS_DATA_REPO`.

CLI/UI wiring, admission of further audited traces, and any capability-state change remain
separate lead-reviewed slices.

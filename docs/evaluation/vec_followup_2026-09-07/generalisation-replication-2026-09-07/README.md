# Three-arm Manchester morning replication

**Completed:** all twelve full cells and twelve preflight probes passed.
Start with the [publication summary and figures](PUBLICATION_SUMMARY.md), or
the [full results](RESULTS.md). The primary ranking reversal appeared in all
four new fleet draws; pilot seed 1 remains separate from primary inference.

This campaign implements the owner's twelve-run extension: four new fleet
draws (0, 2, 3, 4), each with ingress DLA, inherited common-target DLA and
sequential per-task DLA. The two completed seed-1 pilot runs remain in the
sibling `generalisation-pilot-2026-09-07` directory and are excluded from
primary inference.

Read [PROTOCOL.md](PROTOCOL.md) for the questions, contrasts, uncertainty
method, interpretation and stopping conditions. The protocol, analysis code,
validator, reference work stream and evaluator/input hashes were saved in
[manifest.json](manifest.json) before any new fleet-draw probes or outcomes.
This is a locally recorded prespecified plan, not a claim of external
preregistration.

## Execution

Twelve 300-step preflight probes must pass before the twelve full 10,800-step
runs start. Full runs execute serially, grouped by fleet seed. The actor,
canonical morning trace, nine-RSU layout, per-visit queue reset, absolute
6,220-task capacity, service 1×, forwarding 0 ms and scaling-off settings are
fixed. No evaluator source change or retraining is part of this campaign.

`status.json` records the current phase, seed, process, output directory and
completed cells. `replication.log` records validation milestones. Each cell
has a command record, stdout/stderr, summary, per-step/per-task archives,
independent workload validation and an output-hash-bound validation receipt.

The runner generates the primary and supplementary tables and `RESULTS.md`
automatically after all twelve full cells pass. It stops on failures and
retains attempts. It does not retry or exclude cells because of their results.
No within-cell checkpoint exists. An interrupted campaign can resume only
after completed-cell hashes are verified:

```sh
../vec_env-state-delay/.venv/bin/python run_replication.py --resume
```

The runner lock prevents an overlapping launch. The validated runtime is
CPython 3.11.15, JAX/JAXlib 0.4.30, NumPy 1.26.4, SciPy 1.17.1 on the Mac's
arm64 CPU. Exact identities are in the manifest.

## Extra validation for the common-target arm

[workload_checks.py](workload_checks.py) reconstructs RSU service work from
the frozen per-task random keys, task types, admissions and destinations.
The reference stream was qualified against the existing pilot: all saved
queue endpoints and pre-drain workloads matched exactly. All three new arms
receive checks of the reconstructed queue carry, admitted-work summary,
service-work balance and workload distribution. Common-target selections
must be shared within a substep and choose a least-workload RSU.

Five focused analysis/validation tests passed. They cover exclusion of a
fifth draw from primary intervals, inconclusive contrasts, signed intervals,
and detection of deliberately removed admitted work both with and without
pre-drain instrumentation. The retained initial test receipt records a test
expectation that was too narrow: corrupted work was rejected by the earlier
pre-drain check. The corrected tests accept that valid failure and also test
the case without pre-drain records. No experimental outcome prompted a method
or tolerance change.

The canonical trace's source reconstruction is retained in
[input_validation.json](input_validation.json). Original trace, model and
pilot archives are preserved.

## Planned result files

- `runs.csv`: attainment, counts, rejections, energy and forwarding by arm/draw.
- `paired_differences.csv`: all four new draw-level contrasts.
- `paired_intervals.csv`: individual and simultaneous paired intervals.
- `arm_summary.csv`: equally weighted means and SD across new draws.
- `rsu_workload_distribution.csv`: execution and compute workload at each RSU.
- `task_types.csv`: task-type outcomes.
- `supplementary_five_draws.csv`: ingress/per-task, with pilot seed 1 labelled.
- `analysis_validation.json` and `RESULTS.md`: recorded analysis and report.

This tests fleet variability in another scenario within Manchester. It does
not isolate the cause of cross-scenario differences or establish independent
geographical generalisation.

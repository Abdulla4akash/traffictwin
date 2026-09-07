# Common-target five-RSU mechanism audit

Read [REPORT.md](REPORT.md) for the completed audit, observations, deductions,
unavailable fields and one proposed falsification test. This is distinct from
the earlier 100 ms state-delay audit.

The input is the four completed morning common-target runs, with recorded
per-task controls used to check the execution-RSU footprint. Raw records and
the frozen service-work reference were read from
`/Users/akashx/Downloads/diss_mat/generalisation-replication-2026-09-07/`.
No simulator or campaign runner was launched. All audited original files and
the frozen evaluator source retained their recorded hashes.

Contents:

- `audit.py`: analysis source actually executed, bound in the result receipt;
- `audit_results.json`: per-draw findings, exact input hashes and field inventory;
- `per_second_targets.csv.gz`: all 43,200 seconds, including observed targets,
  reconstructed minima/ties, admissions, gate rejections and idle alternatives;
- `per_substep_summary.csv`: twenty seed-by-substep summaries;
- `worked_examples.json`: the first rejecting second from each draw;
- `verification.json`: independent reconciliation of exported per-second records;
- `SHA256SUMS`: file identity ledger for this audit package.

An observed target of `-1` means no V2I attempt was recorded in that substep.
The separately named predicted target is a source-based deduction, not an
observed destination. Reconstructed workloads are explicitly labelled.

The falsification test is proposed and **not executed**. Its purpose is to
distinguish the fixed low-index identities from the five-target-per-second
limit. It is not a new performance campaign.

This audit package is saved locally. It does not change the repository archive
or integrated results at `f17298e`, and it is not a remote backup of the raw
arrays. For reproduction, copy `audit.py` to a new sibling output directory
under the same `diss_mat` parent and use the recorded evaluator Python
environment; the analysis expects the original sibling replication directory
and frozen evaluator checkout. Do not rerun into this completed audit package.

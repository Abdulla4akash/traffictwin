# Codex task: three-trace generalisation study (five arms, eight blocks, three Manchester traces)

Purpose: evidence for a paper, not for the dissertation. No manuscript edits in this task. The owner authorises exactly the runs below; record that the design was proposed by Claude and authorised by the owner, as PROTOCOL.md did for studies 7–9.

Start from branch `research/dissertation-followups-2026-09-15-guarded` (head `5cbe568`) in a new worktree and new branch `research/dissertation-traces-2026-09-16`. Reuse `runner.py`, `validation.py`, `analyse.py`, `checks.py` and the versioned `evaluator_v2.py` unchanged in their scientific code; only add configuration for new traces and arms. Same runtime as the seal: CPython 3.11.15, JAX/JAXlib 0.4.30, NumPy 1.26.4, CPU, x64 off, the venv at `~/Downloads/diss_mat/vec_env-state-delay/.venv`.

## A. Fixed design

- Traces (three new): weekend `we` (Sun 2024-09-15, 12:00–21:00, T=32,400), PM peak `wd_pm` (Tue 2024-10-15, 14:00–21:00, T=25,200), event night `ev` (Wed 2024-09-18, 17:30–24:00, T=23,400).
- Arms (five): `ingress_dla`, `dla`, `per_task_dla`, `causal_round_robin`, `dla_p2c`. Rotate arm order by block index as before.
- Blocks: fleet/evaluator seed pairs (100,200) … (107,207). 8 blocks × 5 arms × 3 traces = 120 full cells. Nothing else.
- Controls exactly as the morning confirmation: original actor (SHA `93c9705…c208`), arrival 1.5, UK2030 fleet, `--rsu-cap-abs 6220`, service multiplier 1, zero forwarding, no scaling, sequential queue accounting with three reconciliation iterations, conserved vehicle queues. `--ignore-enter` and `--reset-soc-on-enter` set exactly as in the morning protocol; state the values in PROTOCOL.md.
- Primary outcome: 100 × deadline successes / all offered tasks. Rejected tasks stay in the denominator.

## B. Trace selection and qualification (before any full run)

B.1 Inventory every candidate file: `~/Downloads/diss_mat/vec_env-state-delay-run/eval/data/*/trace_*_{wdrsu,fullrsu}.npz` (also on `origin/main` of vec_env, e.g. `manchester_weekend/trace_we_wdrsu.npz`) and `~/Downloads/diss_mat/tos-data-full/traces/trace_*_fullrsu.npz`. For each: SHA-256, T, N, RSU count, whether the entry channel used by the 3 Aug `v3_enter_reset` fix is present, embedded window and SUMO seed.

B.2 Preference order per trace: (1) `wdrsu` variant with entry channel; (2) `fullrsu` with entry channel; (3) `fullrsu` legacy convention, documented as such in PROTOCOL.md with the same caveat the dissertation uses for the incident trace. Record the RSU count for each chosen trace; R differs across traces and that is part of the scenario, not a fault.

B.3 Confirm the morning trace identity: check whether tos-data `trace_wd_am_fullrsu.npz` equals the `trace_wd_am_wdrsu.npz` used in the confirmation (array-level). Record equal or the exact differences. Do not rerun the morning trace.

B.4 Qualification per trace with the pilot pair (fleet 1, evaluator 0): five instrumented 300-step cells (one per arm) plus one 150-step restart of `per_task_dla`; require the 83 shared scientific fields to match across arms within a trace, conservation checks to pass, and the restart to match the prefix. Any failure stops that trace; report, do not patch scientific code.

## C. Execution

- Three runner processes at once, one per trace, each serial internally, each with its own raw root under `~/Downloads/diss_mat/traffictwin-traces-raw-2026-09-16/<trace>/` and its own lock. Peak RSS per cell is expected below 3 GB; verify on the first cell of each trace and reduce to two concurrent if any exceeds 4.5 GB.
- Free-space check: 40 GB before start, 10 GB before each attempt. Per-cell timeout 3 hours. No retries, no seed substitution. Incomplete attempts retained.
- Estimated wall time: 3 to 4 hours for all 120 cells at three concurrent.

## D. Analysis fixed before outcomes

Per trace, five declared contrasts from eight equal-weight paired block differences with Student-t, df=7: per-task − ingress; common-target − ingress; per-task − round-robin; per-task − two-choice; two-choice − round-robin. Report individual 95% intervals, within-trace Bonferroni (family of 5), and one conservative family across all 15 new contrasts. Descriptive only: the per-task − ingress and per-task − round-robin margins plotted against mean active vehicles per second across all five Manchester traces, using the archived incident (E2c/E2d) and morning (eight-block) values for the two existing points; no pooling across traces, no cross-trace test. No task-level tests, no equivalence claims from non-significance. Every result reported, including inconclusive ones.

## E. Deliverables

- `PROTOCOL.md` (sealed before full outcomes, with owner/Claude attribution), `TRACE_INVENTORY.json` (B.1–B.3), qualification receipts, 120 cell receipts, 24 block receipts, `CELL_RESULTS.csv`, `PAIRED_EFFECTS.csv`, `ANALYSIS.json`, independent arithmetic audit as in `FINAL_ANALYSIS_AUDIT.json`, `RESULTS.md`, `FINDINGS.md`, a dot-plot chart in the style of `RESULTS_CHART.png` with one panel per trace, and a density plot for the descriptive axis.
- Compact packet ZIP with checksums under `~/Desktop/Dissertation/Experiments 10-12 - 2026-09-16/`; raw arrays stay local with a `RAW_INVENTORY.json`.
- Commit protocol, configuration and results to the new branch; push; open a draft PR; do not merge. Report head SHA, cell count, failures (expect 0), wall time per trace, and the 15 contrasts with all-15 intervals.

# Inspectable mechanism analysis

Read [the model and proof](MATHEMATICS.md) before the counts. The initial [protocol](PROTOCOL.md) and bounded [follow-up declarations](FOLLOWUP_PROTOCOL.md) preserve the executed sequence and numerical rules. [SOURCE_BINDINGS.json](SOURCE_BINDINGS.json) binds unchanged source and prior results to the base Git commit. [EVIDENCE_SUMMARY.json](results/EVIDENCE_SUMMARY.json) is the final 719-input ledger; `SUMMARY.json` is an earlier 697-input phase record, retained unchanged.

| Executable | Inputs / saved output | Purpose |
|---|---|---|
| `diagnostics.py` |671; `results/DIAGNOSTICS.json` | Independent rational fixed-point reference, prior scalar reference, unchanged simultaneous/causal production helpers; fixed eligibility/targets, coupled types and numerical boundaries |
| `refine_and_account.py` |10 adverse reductions +12 transfers +4 numerical follow-ups; `ADVERSE_CASE.json`, `NUMERICAL_FOLLOWUP.json` | Explain an already saved adverse case and establish the limited constructive state boundary; also re-extract existing morning outcome counts, with no raw joins |
| `adverse_production.py` |5 reductions; `ADVERSE_PRODUCTION.json/csv` | Hand-checkable coupled example and unchanged-helper agreement |
| `dimension_check.py` |12; `DIMENSION_CHECK.json` | Failed adverse-case transfers to R9/10,K5,C6220; retains small candidate vectors |
| `padding_check.py` |4; `PADDING_CHECK.json` | Fixed-target numerical example at actual padded N/R widths, active block at either end |
| `common_target_fixture.py` |1; `COMMON_TARGET_INPUT.json` | Zero-entry prefix construction with actual common argmin; stable retained mask |
| `summarise.py` |0 new inputs; `EVIDENCE_SUMMARY.json` | Arithmetic and coverage derived from saved results; source-byte binding checks |

Reproduction uses a disposable copy/checkout retaining this repository's relative structure and Git objects. The scripts deliberately refer to frozen files in the previous package; they do not import the campaign runner. Use an explicitly chosen analysis Python with JAX0.4.30, NumPy1.26.4, CPU and x64 disabled, matching the saved environment. No dependency changes to the scientific runtime were made. Run the scripts in the table order from this directory with that Python (first `python diagnostics.py --output results`, then the remaining scripts in order). Later scripts write their newly reproduced results under `results/`, so run only in the disposable copy if preserving delivered outputs. The authoritative original files stay unchanged. A different JAX/backend may change floating-point boundaries; do not discard those disagreements.

The rational implementation is independent of the production prefix algorithm. The old scalar reference and frozen causal helper are shared comparison dependencies, not additional independent evidence. Intermediate production masks are an instrumented arithmetic mirror whose returned final fields agree with the unchanged helper; they are not archived full-evaluator traces. Explicit service arrays replace actor/PRNG/environment generation. Compatibility with a task's deadline and service range, compatibility with a local queue state, selection-consistent construction and observed fleet occurrence remain distinct.

[Outcome accounting JSON](results/OUTCOME_ACCOUNTING.json) and [CSV](results/OUTCOME_ACCOUNTING.csv) derive only from the previous authenticated transition output. The 19-run raw audit, 23 joins and earlier440-case suite were not repeated. No historical arrays are needed or searched for. Compact document checks can be run with the parent `validate_document.py`; they fail on absent/mismatched sources and do not masquerade as fresh task-level validation.

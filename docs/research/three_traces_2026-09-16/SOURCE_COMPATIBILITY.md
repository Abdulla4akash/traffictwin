# Pre-execution compatibility audit

Base: `5cbe568c9260c432f3e3ae42b45dcfba7f1a8dbe`.
No evaluator process has been launched. The requested five scientific files
are unchanged. The original actor and exact requested Python/JAX/NumPy CPU
runtime passed the inherited preflight.

## Concrete conflicts with literal reuse

| Source | Existing contract | Required configuration |
|---|---|---|
| `followups_2026-09-15/validation.py:37` | N=215, R=9 | Weekend 139/9, PM 163/10, event 175/12 |
| `validation.py:60` | `enter_reset=True` | True only when selected trace has `enter`; both entry flags remain false |
| `validation.py:123` | Unconditional `tr['enter']` | Legacy mask-only carry/reset for PM and event |
| `followups_2026-09-15/checks.py:43` | P2C candidates have shape 215 and range 0–8 | Use sealed N and R for each selected trace |
| `followups_2026-09-15/runner.py` | Morning trace, 10,800 steps, 72 cells, historical matching to morning, 50/20 GiB floors | Three new traces, their full horizons, 40 cells each, within-trace pairing, requested storage thresholds |
| `followups_2026-09-15/analyse.py` | Ten old contrasts and old family sizes | Five contrasts per trace, families 1/5/15; retain the existing interval arithmetic |

The evaluator itself reads N/R from trace arrays and already implements the
legacy fallback. It does not need scientific modification. Bypassing the
validator's hard-coded dimensions or forging an entry channel would not be
valid reuse. Changing the trace to fit the validator is not authorised.

## Qualification wording

The morning `confirmation/qualify.py:compatible` compares the same arm under
the frozen and instrumented evaluator, counting original summary fields
(except wall time) and shared arrays. Its recorded count is 83. It does not
require 83 outcome fields to match between different schedulers.

The follow-up `checks.py:matched` checks 14 exogenous input fields:
times, slot tier, slot EV flag, initial SoC, transmit power, exogenous keys,
observation task type/size, vehicle arrival counts, task activity/type/size,
RSU work and local work. It records observation/logit/action differences
without requiring equality. The instrumented output has 43 per-step arrays
and 16 per-task arrays; restart equality applies to all 59 arrays.

The approved amendment in `OWNER_AMENDMENT.md` and `PROTOCOL.md` preserves
these existing scientific distinctions and the requested run budget.

## Archived descriptive comparison availability

The archived incident E2c/E2d arms are ingress, common-target and per-task.
There is no round-robin outcome in those studies. The morning eight-block
confirmation has the requested round-robin comparison. The incident
per-task-minus-round-robin coordinate must be unavailable; it cannot be
inferred from another trace or populated with zero.

## Decision

The owner explicitly approved the configuration/qualification clarification
before any evaluator attempt. Configured copies and orchestration can proceed
through qualification and exact-source review. Full execution still requires
its source-bound seal. The original protected scientific files remain unchanged.

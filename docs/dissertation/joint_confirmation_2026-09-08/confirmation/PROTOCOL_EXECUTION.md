# Execution version — joint-randomness morning confirmation

8 September 2026. Author-authorised execution, conditional on the bound
qualification receipts. This is a new study, separate from all old observations.
The original disabled [protocol](../../empirical_extension_2026-09-08/confirmation/PROTOCOL.md)
and seal remain unchanged. [EXECUTION_AMENDMENT.md](EXECUTION_AMENDMENT.md)
records the authority, qualification ceiling and implementation changes.

Eight independent joint-seed blocks retain fleet/evaluator pairs (100,200)
through (107,207), with original rotating arm order. Each block has ingress_dla,
dla, per_task_dla and causal_round_robin. The same canonical 10,800-second morning
trace, N=215, R=9, K=5, UK2030 fleet, arrival parameter 1.5, absolute RSU count
limit 6,220, service multiplier 1, zero forwarding, scaling off, conserved
vehicle queues, queue-entry reset, no SoC-entry reset and three admission
replacements apply to all cells. Float32 CPU execution uses the unchanged
CPython 3.11.15 / JAX/JAXlib 0.4.30 / NumPy 1.26.4 runtime. No actor training,
policy redesign, full-evaluator tie-break prefix or other campaign is included.

The estimand is the total scheduling intervention under frozen actor weights.
Admission may affect energy, SoC, observations, logits and actions. Selected
radio targets are endogenous. Exogenous fleet/key/task/arrival/service arrays
must agree within each block; observation/logit/action differences are reported,
not forced away. Every task remains in the offered denominator.

Primary contrasts, in percentage points: per_task_dla minus ingress_dla; dla
minus ingress_dla; per_task_dla minus causal_round_robin. Use all eight equal-
weight paired block effects, sample SD and two-sided Bonferroni simultaneous
95% Student-t intervals with df=7 and critical t(1-0.05/6,7), recomputed by SciPy.
Independent blocks and approximately normal paired effects are assumptions;
eight draws cannot strongly diagnose tails. The original precision sensitivity
remains prospective, not observed power. Report both observed ordering and
whether simultaneous intervals support positive per-task/ingress and negative
common-target/ingress contrasts. No change of test, pooling, subgroup tests,
seed substitution or significance-driven extension. If any block is incomplete,
primary confirmation is incomplete; available valid cells are descriptive.

Exactly one absolute raw-output root and study-wide lock are bound in the
execution seal. At most 32 full attempts, including failures, serially, maximum
10,800 wall seconds per attempt. Require 50 GiB initially and 20 GiB before each
attempt. An incomplete attempt is never overwritten or retried. Resume only
matching seal, configuration and output hashes; passed block receipts must bind
all four cells. Preserve command/environment, source/input identities, timestamps,
stdout/stderr, summary, step/task arrays and receipts. Process and validation
elapsed times are separate. After the first included valid block, extrapolate
remaining runtime only; results cannot alter continuation. Actual control,
source, storage, timeout or accounting failures stop the study. Unexpected
rankings and legitimate action differences do not.

Retained tolerances: discrete counts/masks/categories, inputs and source hashes
are exact; reconstruct JSON success/type numerators within 1e-6 tasks; per-queue
per-second service conservation within 0.01 ms absolute; drain within 0.001 ms
plus 1e-6 relative. Rejected latency is exactly 10 times its deadline; success
uses inclusive latency <= deadline. No tolerance was relaxed after outcomes.
Independent final admission, proposal/execution/forwarding relationships, queue
count/service enqueue, drain/carry and entry resets are validated. Recorded
input arrays are checked by dtype, shape, content hashes and within-block equality.

Qualification completed eight short runs, never exceeding 300 steps, on the
previously inspected fleet=1/evaluator=0 pair. Three old/new comparisons matched
83 shared scientific fields exactly. Four-arm input controls, pointer progression
and a 150-step fresh-process prefix restart passed. Deliberate count/input/
receipt/hash corruptions were refused. Added type-summary and launch/receipt
safeguards were checked against existing short records, with zero additional
evaluator runs. The 300-step RR run had 8,817 advances and 28 advance-then-
rejections. Short runs had no unavailable-radio, RSU-capacity or local-capacity
failures; those branches have preserved kernel evidence only. This is bounded
qualification, not physical validation or full-horizon equivalence proof.

Raw outputs remain local; an off-machine destination has not been approved.
No push, merge, upload, PDF/DOCX generation or submission is authorised.

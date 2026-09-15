# Owner-approved configuration and qualification clarification

16 September 2026, before any new evaluator attempts.

The owner first approved configuration-only changes for trace dimensions,
entry-channel presence, run counts and interval families. After the exact
restart schema and archive availability were clarified, the owner explicitly
approved this full amendment:

> Parameterise trace dimensions and entry-channel expectations, match the 14
> exogenous inputs across arms, require all 59 restart arrays to match the
> prefix, and show the absent archived incident round-robin comparison as
> unavailable. Keep the 18 short attempts, 120 full cells, scientific equations
> and tolerances unchanged.

Owner response: **“Approve this exact amendment.”**

The original `OWNER_TASK.md` is retained unchanged. `PROTOCOL.md` and
`CONFIG.json` incorporate this approved clarification before qualification and
full outcomes. Exact schema checks prevent an intersection-only comparison
from overlooking a missing array. The original protected files at the guarded
base remain byte-identical; new configured validator/check copies change only
N/R and the existing evaluator entry convention. The copied interval function
is byte/AST-equivalent. New runner orchestration applies the authorised budget,
trace isolation, provenance, storage, timeout and memory guards.

The historical 83-field same-arm compatibility check comprised 53 summary
fields, 19 original per-step arrays and 11 original per-task arrays. The
instrumented schema has 43 per-step and 16 per-task arrays, all checked on
restart. Cross-arm exogenous matching and same-arm restart equality serve
different purposes; endogenous outcomes/actions remain unconstrained.

# Recommended next work after the state-delay pilot

Recommendation: document the mechanism and the bounded pilot result, then
qualify an existing-array forwarding-cost sensitivity analysis. A new long
state-delay campaign is not the immediate priority.

## What the completed outputs show

All five full runs passed the declared checks. Per-task placement exceeded
ingress by 0.46367 percentage points with fresh information and by 0.45183
percentage points with 1-second-old workload reports. Those are descriptive
results for one fleet draw, not replicated evidence of general robustness.

The post-hoc [mechanism audit](mechanism_audit.json) excludes startup and
examines 3,599 batches × 10 RSUs = 35,990 workload-report observations per arm.

| Report age | Reports equal to live workload | Mean report error | Largest report error |
|---|---:|---:|---:|
| 100 ms | 100% | 0 ms | 0 ms |
| 500 ms | 20.42% | 12.89 ms | 38.71 ms |
| 1,000 ms | 0% | 502.51 ms | 538.64 ms |

The true RSU batch-entry workload was zero at every audited observation.
Within each batch, however, admitted tasks still accumulated workload and
waited behind earlier tasks; empty batch-entry queues do not imply an absence
of queueing or deadline failures.

The equality at 100 ms follows from the frozen model's constants and timing.
The live admission gate admits only when the target backlog is below that
task's deadline, whose maximum is 500 ms. The largest possible RSU service
time at fixed 1× service is approximately 38.8889 ms (including the 1.1 noise
factor). A causal admission therefore leaves at most approximately 538.8889
ms of workload, apart from negligible floating-point rounding. The 100 ms
report is taken after 900 ms of service from the previous batch, so the queue
has emptied by then. The observed maximum was 538.8381 ms in the fresh and
100 ms arms. This mechanism applies under the same empty initialization,
task deadlines, compute constants, live gate and once-per-second batches;
changing fleet seeds alone does not remove it.

The 500 ms and 1-second conditions did supply different workload information.
They retain immediate acknowledgements, current-batch reservations and live
admission, which define the scope of the result. This diagnostic does not
supersede the recorded validation or change the older E2d evidence. It
explains why successful implementation tests and suitability for a broader
research claim are separate assessments. Simulation-model validity is
relative to its intended question and operating domain; see
[Sargent, Verification and Validation of Simulation Models (2011)](https://www.informs-sim.org/wsc11papers/016.pdf).

## Work to do now

1. Incorporate the pilot table, workload-report diagnostic and timing diagram
   into the dissertation results/methodology. State explicitly that the 100 ms
   arm changed timestamps but supplied identical workload values under this
   model. Avoid interpreting the small single-draw outcome differences as
   equivalence or broad resilience to communication delay.
2. Preserve the completed manifest, code identity, raw archives, validations
   and this post-hoc diagnostic as distinct records.

## Best next sensitivity analysis

Test fixed forwarding overheads of **0, 1, 2.5, 5 and 10 ms**. The research
question is whether the approximately 0.46-point placement advantage survives
an execution destination different from the ingress incurring transfer time.
These are proposed controlled sensitivity values, not measured backhaul
latencies or a physical network deployment claim.

The source adds forwarding delay directly to V2I latency after its queue and
service calculation. Placement and the inherited backlog admission gate do
not read forwarding delay. This makes reuse of saved task arrays a candidate
method, subject to qualification:

- Reconstruct zero-delay deadline outcomes and aggregate counts exactly.
- Check the complete dataflow, including whether changed deadline outcomes
  can affect future policy inputs, admission, queues, service or energy.
- Compare a short direct nonzero-forwarding evaluator run with the transformed
  zero-delay records. Match task outcomes exactly and check the relevant
  latency arithmetic, actor/actions, placements and queues.
- Only if these checks pass, transform admitted forwarded-task latency and
  re-score deadlines from the original task types. Preserve rejected tasks,
  non-forwarded tasks and the offered-task denominator.

This could avoid further full-length simulations. The present turn did not
launch the forwarding study or assert that its qualification checks have
already passed. Any analysis using only the completed pilot remains a
single-draw result. If existing matched E2d archives for other fleet draws are
used later, verify their identities and the transformation separately.

## Later choices

If the priority is stronger scenario coverage, follow Sandra's other
suggestion with another traffic condition and matched ingress/per-task
controls. Verify the new input first and document topology differences; the
planning record flags nine-RSU ordinary-traffic traces versus the ten-RSU
incident trace, so this would be scenario robustness rather than an isolated
traffic-only intervention.

If the priority is broader staleness realism, define task arrival times,
status-update delivery and reservation acknowledgements at sub-second
resolution, then build a small diagnostic scenario before full experiments.
Such a timing model would require its own fresh controls. Increasing the
number of seeds in the current 100 ms arm cannot resolve that timing-model
limitation.

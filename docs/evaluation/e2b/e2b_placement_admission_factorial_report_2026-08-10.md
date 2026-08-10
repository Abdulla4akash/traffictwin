# E2b placement × admission factorial report — 10 August 2026

## Status and evidence boundary

The one authorised `ingress_dla` arm completed the predeclared review, repeated-smoke,
path, accounting and conservation gates. The completed E2 `off`, `jsq` and `dla` cells were
reused only after exact checksum verification. This is one-draw descriptive evidence, not
confirmatory or multi-seed evidence.

## Four-cell observations

| Placement | Gate off | Gate on |
|---|---:|---:|
| Strongest-link | `off` 0.683619229 | `ingress_dla` 0.715773211 |
| JSQ | `jsq` 0.675681775 | `dla` 0.694939919 |

`ingress_dla` offered 13,076,234 tasks, admitted
10,424,749, met 9,359,618 deadlines,
and admitted 580,907 V2I tasks. Its offered
attainment was 0.715773211; admitted attainment was
0.897826701.

## Declared offered-attainment contrasts

- Placement without gate, JSQ minus off: `-0.007937454`.
- Placement with gate, DLA minus ingress-DLA: `-0.020833292`.
- Admission under strongest-link, ingress-DLA minus off: `+0.032153983`.
- Admission under JSQ, DLA minus JSQ: `+0.019258144`.
- Placement × admission interaction, DLA - JSQ - ingress-DLA + off: `-0.012895838`.

For the primary placement-with-gate question, the direct observation is
lower observed value. Close values are not treated as equivalent.
The JSON comparison repeats all contrasts for admitted attainment, offered/admitted latency,
admitted tasks, admitted V2I, gate and cap rejection, execution imbalance and energy per offered task.

## Path, forwarding and conservation

`ingress_dla` selected strongest-link ingress for every V2I attempt. It forwarded
0 tasks, charged
0.0 ms total forwarding
latency, and all admitted execution lay on the ingress-to-ingress matrix diagonal. Gate-rejected
tasks retained their selected ingress, had actual execution `-1`, and were not enqueued. Task,
V2I-work and vehicle-work conservation passed.

## Limitations

- One evaluator seed and one fleet draw; no confidence interval or population inference.
- Tasks are accounting records, not independent statistical replicates.
- Three cells are immutable completed E2 outputs reused by exact hash; only ingress_dla is new.
- The ingress_dla-minus-off admission contrast retains one inherited eligibility-timing difference: off uses its step-entry coarse saturation check, while ingress_dla recomputes that check against live backlog per substep. Completed off recorded 138 unavailable V2I attempts (about 1.1e-5 per offered task); the raw admission contrast and interaction therefore are not perfectly isolated gate-only effects.
- The frozen 17-dimensional actor does not observe current RSU load.
- Zero backhaul represents ideal fibre and ingress_dla performs no forwarding.
- One Manchester incident hour, one provisional UK-2030 fleet, one cap and fixed 1x service were tested.
- Deadline success is evaluator success, not confirmed physical task return.
- No ordinary-traffic control, scaling, P2C, learning, retraining, deployment, or Kubernetes execution was tested.

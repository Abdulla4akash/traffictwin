# TrafficTwin research audit reply

## Audit complete

The requested read-only scientific and implementation audit was completed. No code was changed and no experimental campaign was launched.

- [Complete 17-section research audit](TrafficTwin_research_audit_2026-08-07.md)
- [Immediate request checklist](TrafficTwin_immediate_request_checklist_2026-08-07.txt)

The report includes the full ranked experiment matrix, missing-information register, exact questions for Sandra, Randy and Ethan, seven-day execution plan, reproducibility checklist, bus-thread decision, and source-to-claim traceability.

## Executive verdict

### Can research execution begin now?

**Yes—but begin with a corrected reference run, not a large campaign and not another neural model.**

The current `vec_env` evaluator already implements sequential queue updates, explicit capacity rejection, conserved vehicle queues, absolute or fleet-scaled RSU limits, JSQ/P2C/deadline-aware placement, backhaul delay, and static/reactive compute scaling. However, the existing TrafficTwin runner on the requested branch pins the older reviewed evaluator and exposes only the old controls, so the corrected reference must initially be run directly through current `vec_env` or through an upgraded runner.

There is also a major branch-governance issue: `codex/traffictwin-v0.7` has diverged from TrafficTwin `main` and GitHub reports it as **271 commits behind main**. The authoritative execution base must be selected before new implementation work is admitted.

### What is the first experiment?

**E0 — corrected frozen-actor reference and conservation gate.**

Use:

- the frozen 17-dimensional MAPPO actor;
- Manchester incident trace, 15 March 2024, 20:00–21:00;
- sequential substep accounting;
- conserved vehicle queues;
- physical reject semantics;
- strongest-link selection;
- fixed 1× compute;
- no load-balancing intervention.

The first objective is not to beat a baseline. It is to demonstrate:

\[
\text{offered}=\text{admitted}+\text{rejected}
\]

with explicit rejection reasons, stable input identities, work conservation, class-level completion and properly separated latency denominators.

The actor itself chooses only Local, V2I or V2V. Although the JAX environment computes an RSU load fraction, that value is not included in the actor’s current observation. This makes frozen-actor infrastructure experiments clean and scientifically useful.

### What is the first causal comparison?

**E1 — repeat the waiting-room intervention under both legacy and physical semantics.**

Start with three cap points:

- `0.75×`
- `2.5×`
- `40×`

Run each under:

1. legacy clamp/snapshot behaviour;
2. sequential physical rejection and conservation.

The central hypothesis is that low admission capacity may reduce latency among admitted tasks simply because work is rejected early. That does not mean computation became faster or that service quality over all offered tasks remained unchanged.

Sandra’s documented correction explicitly distinguishes the waiting-room ceiling from compute power. Randy’s reported `0.6943` completion and approximately `4.9 → 128.4 s` latency sweep remains a **reported result**, because its raw outputs, full command, actor identity, seeds and numerical table were not found in the repositories.

### What should the main research contribution be?

The strongest bounded contribution is:

> **A semantics-aware, conservation-checked evaluation of infrastructure-side RSU scheduling with a frozen vehicle actor, identifying when deterministic load-aware placement and compute scaling help, tie or harm under admission limits, forwarding cost and stale RSU state.**

The minimum defensible package is:

1. corrected accounting and E0 reference;
2. legacy-versus-physical waiting-room result;
3. strongest-link versus deterministic load-aware placement;
4. forwarding/backhaul sensitivity;
5. fixed/static/reactive scaling only after the first four are sound.

Stale-state sensitivity at `0`, `100`, `500` and `1000 ms` is the strongest extension. Proactive forecasting, actor retraining and a learned dispatcher should be gated behind evidence that the simpler deterministic methods leave a meaningful residual problem.

## What is already implemented—but not yet scientific evidence?

TrafficTwin has an unmerged sequential prototype chain containing:

- a provisional task-lifecycle contract;
- a synthetic two-RSU hand-check;
- strongest-link, least-loaded and predicted-earliest-completion dispatch;
- a read-only validator for future native lifecycle sidecars;
- a matched synthetic three-policy study.

These components are useful engineering foundations. Their own contracts explicitly state that they do not prove native execution, result return, deadline benefit or scheduler superiority.

The current missing bridge is an authorised native producer or adapter that records stable task identities across:

\[
\text{offered}\rightarrow\text{admitted/rejected}\rightarrow
\text{retained/forwarded}\rightarrow\text{started}\rightarrow
\text{completed/dropped}\rightarrow\text{returned/failed}\rightarrow
\text{deadline outcome}
\]

## What has actually been reproduced?

The repositories support two kinds of historical evidence:

- TrafficTwin reproduced one bounded weekend case against the **old reviewed evaluator**.
- `tos-data` contains the historical 300-row evaluation package, checkpoints, traces and training records for `v2_post_nrsus_fix`.

That package predates the 5 August physical-rejection and work-conservation changes. For example, its five UK2030 incident baseline draws range from roughly `0.7170` to `0.7414` completion, with a mean near `0.7247`; these are historical old-engine values, not corrected baselines.

The historical retraining records also show why another immediate retraining campaign would be risky: gridlock-matched training transferred badly when the synthetic two-RSU training topology did not match the ten-RSU Manchester evaluation topology.

## Information to request immediately

From **Sandra**: confirm the mandatory core deliverables, primary actor, primary denominator, essential trace set, whether physical return events are mandatory, whether stale state is core or extension, and the exact seven-day deliverable.

From **Randy**: request the complete queue-sweep evidence package—raw outputs, commands/manifests, cap grid, actor checksum, trace checksum, evaluator and fleet seeds, commits, environment, SUMO version, completion definition, latency population and drain treatment.

From **Ethan**: request his exact branch/commit, owned workstream, completed outputs, controller definitions and intended ownership split.

Operationally, request CSF3 partition access, quota, durable output location and allowed array concurrency. A historical incident run took approximately three CPU-hours, so even a three-cap × two-semantics × five-draw core is around **90 CPU-hours** if current runtime is similar.

## Work that can proceed without waiting for replies

Proceed now with:

- local `git status`, branch and untracked-output inventory at all three supplied paths;
- actor and trace checksums;
- an E0 predeclared manifest;
- SUMO/environment pinning;
- a bounded corrected-semantics smoke run;
- conservation validation;
- design of the missing forwarding/path fields;
- a separate Manchester bus-data feasibility inventory.

The bus thread should remain a parallel contingency rather than replacing the supervisor-directed VEC study immediately. Its strongest focused question is short-horizon corridor travel-time and severe-delay prediction, starting with persistence, historical median and gradient-boosting baselines—not an LLM-generated numerical forecast.

**The immediate move is E0: establish that the current engine accounts for every offered task before trying to make any controller look clever.**

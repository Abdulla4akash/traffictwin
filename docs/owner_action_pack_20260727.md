# Owner Action Pack — 27 July 2026 (current drafts refreshed 28 July)

**Status: CURRENT DRAFTS are in section A below. The original 27-July drafts are retained
in section B for provenance and must not be sent because their campaign/session state is
stale. Nothing has been sent; an agent never sends external communications.** Recipient
addresses are deliberately omitted and the owner fills them at send time.

---

## A. Current send pack — 28 July 2026

### A1. Email to Dr Sandra Sampaio

> **Subject:** Week 4→5 progress — confirmed capacity result and two scope questions
>
> Dear Dr Sampaio,
>
> A short Week-4-to-5 update: the predeclared capacity programme is now complete and has
> produced one confirmed, bounded finding.
>
> On the modelled traffic-collapse hour in the Etihad/Co-op Live event district,
> tightening per-vehicle edge capacity from 2.5 to 0.75 reduced mean task latency by
> 8.3 seconds across five reserved seeds (bootstrap interval −9.1 to −7.5 seconds), with
> all five seeds in the predeclared direction. Deadline attainment remained flat-to-rising,
> so the expected degradation cliff did not appear. At the decision level, the trained
> policy selected identical actions across capacity levels because its vehicle-side input
> carries no capacity-dependent signal.
>
> The wider sweep clarifies the boundary: all four normal traces — weekend, event night,
> and weekday AM/PM, at 139–215 maximum trace slots — were exactly unchanged across the
> standard capacity arms. Only the 2,488-slot collapse hour responded. A deep squeeze on
> the event night stayed exactly inert through cap-0.25 and first changed at cap-0.1. This
> supports a saturation-governed interpretation without claiming a universal threshold.
>
> I have also processed the three attended BODS sessions into aggregate-only records.
> Active bus support was 41 at night, 1,162 at dawn, and 1,433 at the weekday peak while
> median cadence stayed at 66–68 seconds. No bus experiment has run; its protocol still
> needs signing, map matching, a viability check, and an explicit speed-outlier rule.
>
> The concise checkpoint and figure provenance are in
> `docs/current_progress_week5.md` and
> `docs/dissertation_appendices/figures/cross_regime/provenance.md`. The confirmed result
> remains bounded to one actor and one audited district trace and is not external validation.
>
> Two questions where I would value your steer:
>
> 1. Task offloading versus journey-time prediction — you left this open; the completed
>    evidence programme is now strongly offloading-centred. Should that remain the core?
> 2. The algorithm-combination idea from our second meeting — should it be an in-scope
>    contribution, or explicitly recorded as future work?
>
> The participant-study ethics application is ready for my review and submission, and my
> CSF3 request is ready. I would be grateful for your supervisor confirmation if Research
> IT requests it.
>
> Best regards,
> Abdulla

### A2. Email to Randy

> **Subject:** Capacity-study result, baseline identity, and written permission record
>
> Hi Randy,
>
> Thank you again for the tos-data provenance sidecar and for talking through code use. I
> have kept the scope wording to the Etihad/Co-op Live event district rather than Manchester
> generally.
>
> Study Case 2 has now completed its first predeclared programme on the `inc` collapse-hour
> trace. The exploratory pilot found that a 3.3× capacity squeeze left deadline success flat
> while mean task latency fell 3.2×. A separately signed held-out run then confirmed the
> latency direction across all five reserved seeds: −8.3 seconds mean paired difference,
> interval −9.1 to −7.5 seconds. The policy's actions were bit-identical across capacity
> arms because the vehicle-side observation has no capacity-dependent signal.
>
> The cross-regime checks are equally useful: weekend, event-night, and both weekday-peak
> traces were exactly inert under the standard squeeze; only the 2,488-slot collapse hour
> responded. A small baseline-actor prediction test also held — `baseline_model_c_17` was
> exactly capacity-invariant — while its descriptive actor differences remain unranked.
>
> Three asks:
>
> 1. For any later formal actor-crossover study, can you confirm that
>    `baseline_model_c_17` and the seed-100 checkpoint identity are the intended baseline
>    provenance to cite?
> 2. My dissertation would include derived tos-data aggregates, paired differences, and
>    analysis tables with full provenance and your repositories cited. Could you confirm
>    in writing that this is permitted, and state any publication constraints you want?
> 3. Could you confirm in writing that using your training code with citation is permitted,
>    including synthetic-environment Colab runs with no tos-data uploaded? I have kept the
>    returned checkpoints private and non-admitted.
>
> I will not treat silence as permission or externally release third-party material beyond
> the conditions you confirm. Happy to walk you through the dashboard and results once the
> participant-study ethics approval is in place.
>
> Thanks again,
> Abdulla

### A3. CSF3 access request

> **Subject:** CSF3 account request — MSc dissertation (supervisor: Dr Sandra Sampaio)
>
> Hello,
>
> I am an MSc Advanced Computer Science student working on a dissertation supervised by
> Dr Sandra Sampaio in the Department of Computer Science. I would like to request a CSF3
> account for GPU-accelerated JAX multi-agent reinforcement-learning training and evaluation
> for a vehicular-edge-computing task-offloading study.
>
> The group's existing repository already includes SLURM launchers and an environment guide
> (`gitlab.cs.man.ac.uk/e62992rp/vec_env`), and my colleague Randy Putra uses CSF3 for the
> same workload family. I expect single-GPU batch jobs, tens of gigabytes of scratch space,
> and no interactive service or public endpoint.
>
> My supervisor can confirm the project. Please let me know if a supervisor authorisation
> form or additional information is required.
>
> Kind regards,
> Abdulla
> Student ID: **FILL BEFORE SEND**

### A4. Owner sequence

| Priority | Personal action | Do not delegate |
|---:|---|---|
| 1 | Review and submit `docs/evaluation/ethics_application_draft.md` | Submission, recruitment, and dates are the owner's |
| 2 | Review and send A1–A3 | Recipient/address checks and all sends are the owner's |
| 3 | Record Sandra's actual answers to the two scope questions | Do not infer a verdict from silence or meeting timing |
| 4 | Trigger Codex review of `CODEX_INTEGRATION_HANDOFF.md` and, if satisfied, the official-branch fast-forward | `main` stays untouched |
| 5 | Decide B1 G1–G5, especially the 32 m/s drop+count recommendation | No bus experiment or trace construction before signing and viability |
| 6 | Complete/decide crossover and stadium candidates; decide E1–E5 and R1 | Each remains an owner decision; N1 was withdrawn after the 28 July identity correction |

---

## B. Archived 27-July drafts — provenance only, DO NOT SEND

### Archived 1. Email to Dr Sandra Sampaio (Monday progress cycle)

> **Subject:** Week 4 progress — a confirmed finding overnight, and three scoping questions
>
> Dear Dr Sampaio,
>
> A short update ahead of our meeting, with a result that landed overnight.
>
> The platform's experiment instrument is complete and has now produced a **confirmed,
> predeclared finding**. In the exploratory pilot on the incident-hour Manchester trace,
> tightening per-vehicle edge capacity 3.3× left deadline attainment unchanged while
> cutting mean task latency by two-thirds — the expected degradation cliff did not
> appear. Following the predeclared protocol, mean latency was then declared the
> confirmatory endpoint *before* any reserved data was touched, and last night's held-out
> campaign confirmed it: across five untouched seeds, the squeeze reduced mean task
> latency by 8.3 seconds (bootstrap interval −9.1 to −7.5 s), with **all five seeds
> agreeing in the predeclared direction** and deadline attainment again flat.
>
> We can also now show the mechanism, not just the effect: the trained policy's decisions
> are bit-for-bit identical across all capacity levels (zero differences across ~9 million
> per-second decisions), because its observation space contains no capacity-dependent
> signal — the policy is blind to capacity *by observation design*, not by learned
> indifference. That is, I believe, exactly the kind of non-obvious result you asked for
> in our first meeting: the expected outcome did not happen, and the instrument shows
> precisely why.
>
> The full records are in the repository: `docs/current_progress_week4.md` (progress
> against our meeting notes) and `docs/evaluation/capacity_confirmatory_results_20260728.md`
> (the confirmed result with all limitations stated — one actor, one district trace,
> internal predeclaration discipline, not external validation).
>
> Two questions I'd value your steer on:
>
> 1. Task offloading vs journey-time prediction — you left this open; the built programme
>    is offloading-centred and the confirmed result strengthens that direction.
> 2. The algorithm-combination idea from our second meeting — in-scope contribution, or
>    recorded future work?
>
> Also in motion: I am submitting the ethics application for the user evaluation this
> week per the proposed values; Randy has agreed to use of his code with citation (his
> data-use permission for published aggregates is being confirmed in writing); a
> follow-up study training a capacity-aware variant of the policy is being prepared; and
> my CSF access request is going in — I would be grateful for your confirmation as
> supervisor when it arrives.
>
> Best regards,
> Abdulla

---

### Archived 2. Email to Randy (provenance thanks, Study Case 2, baseline, permission)

> **Subject:** tos-data provenance — thank you; Study Case 2 first result; two asks
>
> Hi Randy,
>
> Thank you for the provenance sidecar — the calendar dates, windows, and seeds answered
> exactly what I needed, and I've read your Year-1 report as well. The scope wording in all
> my reports now says Etihad/Co-op Live event district, not Manchester generally.
>
> Following your Study Case framing: Study Case 1 (VEC resource monitoring) is built into
> the platform, and Study Case 2 produced its first predeclared result this weekend on your
> `inc` trace — the reactive-rule collapse hour. Across a 3.3× per-vehicle capacity squeeze
> (12 paired runs, 3 common fleet seeds), deadline success stayed flat at ~79% while mean
> task latency fell 3.2× — and the mechanism is visible in the instrumented outputs: the
> ukfleettrain MAPPO actor's offloading decisions are bit-identical across all four capacity
> levels within each seed. The policy never responds to the capacity control; only the
> queueing outcomes change. That reads as a concrete Year-2 instance of the
> reward/behaviour-misalignment concern in your Year-1 report, and it is exploratory,
> clearly labelled, and reproducible end to end from receipts. A held-out confirmatory run
> is executing tonight.
>
> Also: the held-out confirmation completed last night — the latency effect held on all
> five reserved seeds (−8.3 s mean paired difference, interval −9.1 to −7.5), and we
> traced the mechanism: the policy's observation space carries no capacity-dependent
> signal, so its decisions are literally identical across capacity levels. That makes a
> capacity-aware observation variant the obvious next training experiment — which brings
> me to the asks.
>
> Three asks:
>
> 1. **Baseline actor.** For the predeclared actor-crossover study I plan to run
>    `baseline_model_c_17` against `ukfleettrain_mappo_model_c_17` on identical seeds and
>    capacity levels. Can you confirm that checkpoint is the right baseline for that
>    contrast (and that the seed-100 training identity in `checkpoints/` is the one to
>    cite)?
> 2. **Written permission — data.** My dissertation would include derived aggregates from
>    tos-data (per-arm metric means, paired differences, the analysis tables above) with
>    full provenance and your repos cited. Could you confirm in writing that this use is
>    fine — or tell me what constraints you'd like? Nothing derived from your data is
>    published anywhere until then.
> 3. **Written confirmation — code.** Thank you for agreeing that I can use your code
>    with citation — could you confirm that in one line by reply, so my records carry it
>    in writing? Related: is running your training code on Colab (my compute units,
>    synthetic environment only, no tos-data) within that permission?
>
> Happy to walk you through the dashboard against your own data whenever useful — that
> session would also count toward the user evaluation once ethics approval lands.
>
> Thanks again,
> Abdulla

---

### Archived 3. CSF access request (via supervisor / Research IT)

> **Subject:** CSF3 account request — MSc dissertation (supervisor: Dr Sandra Sampaio)
>
> Hello,
>
> I am an MSc Advanced Computer Science student (dissertation project supervised by
> Dr Sandra Sampaio, Department of Computer Science) and would like to request a CSF3
> account for my project.
>
> Planned use: GPU-accelerated JAX multi-agent reinforcement-learning evaluation and
> training runs for a vehicular-edge-computing task-offloading study, using the SLURM
> launchers and environment documented in the group's existing repository
> (gitlab.cs.man.ac.uk/e62992rp/vec_env — my colleague Randy Putra already uses CSF3 for
> the same workloads). Expected footprint is modest: batch jobs on single-GPU nodes,
> tens of gigabytes of scratch storage, no interactive services.
>
> My supervisor can confirm the project. Please let me know if a supervisor authorisation
> form or any additional information is needed.
>
> Kind regards,
> Abdulla
> (student ID: fill in)

---

### Archived 4. To-do — Monday 28 July 2026

| When | Action | Notes |
|---|---|---|
| 08:00–09:30 | **Attended peak bus session (G1)** | `BODS_API_KEY` in env, run `uv run python scripts/bus_cadence_probe_session.py` from the repo with the workspace at `~/AntigravityTest/diss/data/workspace-v0.7`; ~85 snapshots at 65 s; stay attended throughout. Fills B1's peak-density fields. |
| Morning | **Review the confirmatory result** | Campaign completes tonight; analysis + results record will be committed. Check `docs/evaluation/` and the campaign analysis before citing anything. |
| Morning | **Send the ethics application** | Confirm-and-send from `docs/evaluation/ethics_application_draft.md` — the seven proposed values are in-file. Longest lead time; sessions proposed 11–22 Aug. |
| Morning | **Send emails 1–3 above** | Sandra (progress + three questions), Randy (two asks), CSF request. |
| When replying | **Queued decisions, whenever convenient** | R1 tos-data re-pin (trivial, one docs-only commit); N1 network re-pin (bigger); E1–E5 demand signing; G1–G6 bus-fleet signing; ev-study predeclaration go/no-go (admission landed as ADR-065). |

---

The archived N1 action above was withdrawn on 28 July after the source PBF/decoded XML identity
error was corrected; it is not a current owner action.

*Prepared 27 July 2026 under the standing in-session delegation; every draft awaits the
owner's personal review and send.*

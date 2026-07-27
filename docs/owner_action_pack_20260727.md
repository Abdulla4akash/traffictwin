# Owner Action Pack — 27 July 2026 (drafts + to-do)

**Status: DRAFTS prepared for the owner to review, edit, and send personally. Nothing here
has been sent; an agent never sends external communications.** The recipient addresses are
deliberately omitted — the owner fills them at send time.

---

## 1. Email to Dr Sandra Sampaio (Monday progress cycle)

> **Subject:** Week 4 progress — first experimental result, and three scoping questions
>
> Dear Dr Sampaio,
>
> A short update ahead of Monday. The platform's experiment instrument is complete and
> produced its first predeclared result this weekend: on the incident-hour Manchester trace,
> tightening per-vehicle edge capacity 3.3× left deadline attainment unchanged (~79%) while
> cutting mean task latency by two-thirds — because the trained policy's offloading
> decisions turn out to be capacity-invariant. The expected degradation cliff did not
> appear; the null was predeclared as publishable, and a powered confirmatory run on
> held-out seeds is executing now with mean latency as its declared primary. A full written
> progress checklist against our meeting notes is in the repository
> (`docs/current_progress_week4.md`).
>
> Three questions I'd value your steer on:
>
> 1. Task offloading vs journey-time prediction — you left this open; the latency result
>    above gives the journey-time angle measured weight, but the built programme is
>    offloading-centred.
> 2. The algorithm-combination idea from our second meeting — in-scope contribution, or
>    recorded future work?
> 3. Framing: Randy suggested anchoring the dissertation gap in explainability/trustworthy
>    ML; the capacity result reads naturally as an explainability finding (the instrument
>    showed *why* the cliff didn't happen). Are you comfortable with that as the headline
>    framing?
>
> I am also submitting the ethics application for the user evaluation this week per the
> proposed values, and the data/baseline request to Randy is ready to go.
>
> Best regards,
> Abdulla

---

## 2. Email to Randy (provenance thanks, Study Case 2, baseline, permission)

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
> Two asks:
>
> 1. **Baseline actor.** For the predeclared actor-crossover study I plan to run
>    `baseline_model_c_17` against `ukfleettrain_mappo_model_c_17` on identical seeds and
>    capacity levels. Can you confirm that checkpoint is the right baseline for that
>    contrast (and that the seed-100 training identity in `checkpoints/` is the one to
>    cite)?
> 2. **Written permission.** My dissertation would include derived aggregates from tos-data
>    (per-arm metric means, paired differences, the analysis tables above) with full
>    provenance and your repos cited. Could you confirm in writing that this use is fine —
>    or tell me what constraints you'd like? Nothing derived from your data is published
>    anywhere until then.
>
> Happy to walk you through the dashboard against your own data whenever useful — that
> session would also count toward the user evaluation once ethics approval lands.
>
> Thanks again,
> Abdulla

---

## 3. CSF access request (via supervisor / Research IT)

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

## 4. To-do — Monday 28 July 2026

| When | Action | Notes |
|---|---|---|
| 08:00–09:30 | **Attended peak bus session (G1)** | `BODS_API_KEY` in env, run `uv run python scripts/bus_cadence_probe_session.py` from the repo with the workspace at `~/AntigravityTest/diss/data/workspace-v0.7`; ~85 snapshots at 65 s; stay attended throughout. Fills B1's peak-density fields. |
| Morning | **Review the confirmatory result** | Campaign completes tonight; analysis + results record will be committed. Check `docs/evaluation/` and the campaign analysis before citing anything. |
| Morning | **Send the ethics application** | Confirm-and-send from `docs/evaluation/ethics_application_draft.md` — the seven proposed values are in-file. Longest lead time; sessions proposed 11–22 Aug. |
| Morning | **Send emails 1–3 above** | Sandra (progress + three questions), Randy (two asks), CSF request. |
| When replying | **Queued decisions, whenever convenient** | R1 tos-data re-pin (trivial, one docs-only commit); N1 network re-pin (bigger); E1–E5 demand signing; G1–G6 bus-fleet signing; ev-study predeclaration go/no-go (admission landed as ADR-065). |

---

*Prepared 27 July 2026 under the standing in-session delegation; every draft awaits the
owner's personal review and send.*

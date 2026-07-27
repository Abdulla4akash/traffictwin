# Dissertation video narration script

The spoken text for [the storyboard](video_storyboard.md), one block per shot, in shot order.
Record narration separately against these words and lay it under the picture, as the storyboard's
audio note directs.

**This document makes no scientific claim of its own.** Every number spoken aloud appears in
exactly one place — the verbatim framing sentence in shot 12, quoted from the committed results
record and attributed on camera. Everywhere else the speaker names a record and lets the screen
carry it.

## Timing budget

Budgeted at **140 words per minute**, the rate the storyboard's separately-recorded narration
assumes. Every block but one is sized to finish inside its shot with headroom, because narration
that exactly fills a shot leaves no room to breathe and reliably overruns on the take.

| # | Shot | Length | Words | Speech | Headroom |
|---:|---|---:|---:|---:|---:|
| 1 | Hook | 0:40 | 84 | 0:36 | +0:04 |
| 2 | Home / Project Status | 0:30 | 62 | 0:26 | +0:03 |
| 3 | Guided Demo | 0:30 | 59 | 0:25 | +0:05 |
| 4 | Bundle Import | 0:35 | 72 | 0:30 | +0:04 |
| 5 | Run Overview | 0:30 | 58 | 0:24 | +0:05 |
| 6 | Replay animation | 0:40 (0:04 silent) | 65 | 0:27 | +0:08 |
| 7 | RSU Monitor | 0:35 | 72 | 0:30 | +0:04 |
| 8 | Diagnostics | 0:40 | 70 | 0:30 | +0:10 |
| 9 | Provenance DAG | 0:45 | 95 | 0:40 | +0:04 |
| 10 | Match Review | 0:40 | 69 | 0:29 | +0:10 |
| 11 | Experiment instrument | 0:30 | 65 | 0:27 | +0:02 |
| 12 | Wrap | 0:25 | 66 | 0:28 | −0:03 |

**Total spoken: 837 words ≈ 5:58 of speech under a 7:00 picture — inside the 8-minute ceiling with 2:01 to spare.** The gap is deliberate: pauses, the four silent seconds in shot 6, and the
cuts between shots.

**Shot 12 does not fit its slot, and this is a real conflict rather than an oversight.** The
storyboard allots the wrap 0:25. The framing sentence must be quoted verbatim from the results
record — that alone is about 0:20 at this rate — and it still needs an attribution phrase in
front of it and the limitation the storyboard says to end on behind it. The block is trimmed to
the minimum that keeps all three and still measures **0:28, three seconds over**.

Two ways to resolve it, both the owner's call, because the storyboard is not this document's to
edit:

- **Give shot 12 five more seconds** and take them from shot 8 or shot 10, which carry +0:10 of
  headroom each. This is the recommended fix; the total picture stays at 7:00.
- **Drop the closing limitation** and end on the quotation. Cheaper, but it loses the storyboard's
  stated intent of ending on the limitation rather than burying it, so it is the worse trade.

What must not happen is speaking shot 12 faster to make it fit, or paraphrasing the quoted
sentence to shorten it.

## Where the required caveats land

The *Required Spoken Caveats* in [the demo checklist](demo_checklist.md) are quoted **word for
word** below, at the storyboard positions that carry them. Where the storyboard paraphrases one
in its own checklist, the checklist's wording is the authority and is what appears here.

| Caveat | Shot |
|---|---:|
| Synthetic fixtures are not real Manchester data. | 2 |
| Direct launch is intentionally disabled. | 2 |
| Read-only TOS inspection … SUMO FCD also remains unavailable. | 3 |
| Historical replay is not live data. | 6 |
| Diagnostic hypotheses are not proven root causes. | 8 |
| Provenance supports traceability and auditability, not proof of correctness or causality. | 9 |
| Unknown TOS publication permission remains visible as an integration gate. | 11 |
| The supervisor ZIP is labelled private research material. | conditional — see below |
| Any public demonstration uses only the standalone synthetic static site. | conditional — see below |

The last two are conditional in the checklist and stay conditional here. Optional lines for both
are given after shot 12; speak them only when the condition holds, and re-record the shot rather
than captioning it afterwards.

---

## Shot 1 — Hook (0:00–0:40)

**[SCREEN: Manchester Operations map, talking-head overlay.]**

> Vehicular edge computing promises to offload work from cars to roadside infrastructure. The
> policies that decide what to offload are trained in simulation, on synthetic fleets. So here is
> the question this project asks: when one of those trained policies is put in front of evidence
> you can actually trace, does its behaviour hold up — and can you tell? TrafficTwin is the
> instrument I built to answer that honestly. Where buses appear in this video, they are transit
> vehicles, never general road traffic.

*84 words ≈ 0:36.* Do not preview a result.

---

## Shot 2 — Home / Project Status (0:40–1:10)

**[SCREEN: Home, capability status list.]**

> This is the honesty discipline everything else rests on. What the system cannot support is
> shown as unsupported; what nobody has established is shown as unknown — not as a blank, and not
> as a zero. Synthetic fixtures are not real Manchester data. Direct launch is intentionally
> disabled. If you do not believe these states are real, nothing later should convince you.

*62 words ≈ 0:26.* Both caveats are verbatim from the demo checklist.

---

## Shot 3 — Guided Demo and the evidence boundary (1:10–1:40)

**[SCREEN: Guided Demo, standalone synthetic track.]**

> The guided track separates three things that are easy to blur: simulation artifacts, the
> deterministic pipeline over them, and my interpretation at the end. Now the integration
> boundary. Read-only TOS inspection and bounded SUMO tripinfo/summary import are available, but
> full Randy/VEC conversion and launch stay blocked by missing producer/checkpoint/writer,
> identity/outcome/trip evidence, and fixture permission; SUMO FCD also remains unavailable.

*59 words ≈ 0:25.* The long sentence is verbatim; rehearse it. Do not enter the imported track
unless the authorised package is configured on the recording machine.

---

## Shot 4 — Bundle Import (1:40–2:15)

**[SCREEN: Bundle Import validating `.demo/bundles/baseline`, then `.demo/bundles/stressed_demand`.]**

> Two runs come in through the same import path. Validation is not a formality here — the declared
> files, their record counts, and their hashes are all checked before anything is accepted, and a
> bundle that fails is rejected rather than partly loaded. Watch the accepted status and the file
> list. In a few minutes I am going to trace a number all the way back to one row inside this
> bundle.

*72 words ≈ 0:30.* Hold the accepted status on screen long enough to read.

---

## Shot 5 — Run Overview (2:15–2:45)

**[SCREEN: Run Overview, an optional metric showing unavailable.]**

> Here is the run's metric set — and here is a metric marked unavailable. Unavailable is not zero.
> That metric could not be computed from the evidence this run actually carries, so the system
> says so and refuses to substitute a default. A dashboard that quietly showed zero here would be
> easier to read and would be lying.

*58 words ≈ 0:24.* "Unavailable is not zero" is worth landing cleanly.

---

## Shot 6 — Replay animation (2:45–3:25) — UN-REPORTED

**[SCREEN: Replay, `HISTORICAL REPLAY` badge visible for the whole shot.]**

> *(Four seconds of silence — let the animation read.)*
>
> This is a recorded window being replayed, not a live feed. Historical replay is not live data.
> The badge stays on screen for exactly that reason, and there is no wall-clock source behind it.
> I am changing the playback speed, and jumping the scrubber. A written report can print a
> snapshot of this; it cannot show you the motion, which is why the shot exists.

*65 words ≈ 0:27 spoken over the remaining 36 seconds.* Keep the badge in frame throughout.

---

## Shot 7 — RSU Monitor drill-down (3:25–4:00) — UN-REPORTED

**[SCREEN: `/rsu-monitor`, one RSU selected, then the cross-RSU asymmetry table.]**

> My supervisor asked a direct question: which roadside unit is overwhelmed, and how overwhelmed?
> This is the answer. I select one unit and its queue and in-flight series redraw across the run
> window. Pressure here means in-flight tasks against recorded maximum concurrency. It is not CPU
> utilisation, and per-unit energy does not exist in the accepted loaders, so it is not shown. The
> comparison itself is the part a report cannot carry.

*72 words ≈ 0:30.* Say what the page says; claim nothing beyond it.

---

## Shot 8 — Diagnostics and Evidence (4:00–4:40)

**[SCREEN: Diagnostics over `.demo/bundles/under_offloading`, a rule firing.]**

> A rule has fired. Read what it says carefully: this is a candidate explanation, not a cause.
> Diagnostic hypotheses are not proven root causes. And notice the rules that did not fire — they
> are still listed, marked insufficient, rather than hidden. A system that only showed you its
> confident answers would look far more impressive than this one, and would tell you far less
> about what it actually knows.

*70 words ≈ 0:30.* Never say "cause". The verbatim caveat is the third sentence.

---

## Shot 9 — Provenance DAG click-through (4:40–5:25) — UN-REPORTED

**[SCREEN: one continuous take — metric → definition → canonical table → row sample → source-row
mode → `tasks.csv` row 2.]**

> This is the shot I would keep if I could keep only one. I start at a computed metric and walk
> backwards: its definition, the canonical table behind it, the sample of rows in that table, and
> then into source-row mode — landing on row two of `tasks.csv`, the raw imported row beside its
> canonical record. One continuous chain, no cuts. Now the honest limit of it. Provenance supports
> traceability and auditability, not proof of correctness or causality. It tells you where a
> number came from. It does not tell you the number is right.

*95 words ≈ 0:40.* Do not cut inside this shot.

---

## Shot 10 — Match Review: decide, persist, seal (5:25–6:05) — UN-REPORTED

**[SCREEN: `/match-review` — record a decision with reviewer and reason, reload, then seal.]**

> These candidate matches are pending, and they stay pending until a person decides them. I record
> a decision with my name and a written reason. The row changes state. I reload the page — it
> persisted. Then I seal the ledger for export, and it becomes append-only: a later decision adds
> a record, it never rewrites this one. This is a human judgement boundary being used, rather than
> described.

*69 words ≈ 0:29.*

---

## Shot 11 — Experiment instrument (6:05–6:35)

**[SCREEN: the predeclaration document, then `/campaigns` reading the campaign receipt, then the
committed results record.]**

> The design was fixed before any result existed. The approval binds this document's exact bytes,
> so it cannot be edited afterwards and still run. The receipt records every cell. The results
> record was published under a commitment made in advance to publish it whatever it said. This is
> owner-approved-candidate evidence — not supervisor-approved, not validated. Unknown TOS
> publication permission remains visible as an integration gate.

*65 words ≈ 0:27.* Name the records; read no number here. The final sentence is verbatim.

---

## Shot 12 — Wrap (6:35–7:00)

**[SCREEN: objectives summary, then the committed results record's framing sentence on screen as
it is spoken.]**

> The record's framing, verbatim: "During a modeled traffic-collapse hour in the Etihad event
> district, tightening per-vehicle edge capacity 3.3× left deadline attainment unchanged (~79.1%)
> while cutting mean task latency by two-thirds — because the trained offloading policy's
> decisions are capacity-invariant." One anomalous hour, three seeds. Exploratory, never more.

*66 words ≈ 0:28.*

**Why the quotation sits here and not in shot 11.** The storyboard forbids reading numbers at
shot 11, and this script keeps that rule. The framing sentence is quoted here instead, read as a
quotation, with the record it comes from on screen — so the only numbers in the whole narration
are the committed record's own words, attributed as such. Read it exactly; it is copied verbatim
from
[`capacity_pilot_results_20260727.md`](evaluation/capacity_pilot_results_20260727.md),
including the correction that record carries. Do not paraphrase it, do not round it, and do not
extend it into a claim the record does not make.

---

## Conditional lines

Speak these only when the condition in the demo checklist actually holds, and re-record the shot
rather than adding a caption.

**If the supervisor ZIP appears on screen at any point** — add to that shot:

> The supervisor ZIP is labelled private research material.

**If the video will be shared beyond the marker** — add to shot 12:

> Any public demonstration uses only the standalone synthetic static site.

## Before you record

- Read the whole script aloud once, timed. If any block runs past its shot, cut words from that
  block — do not speed up, and do not let a shot run long into the next one.
- Check every verbatim caveat against [the demo checklist](demo_checklist.md) and the framing
  sentence against the results record. Both are the authority; if this file has drifted from
  either, this file is wrong.
- After recording, watch once at full speed with the storyboard's caveat checklist in hand and
  tick each box against the moment it is actually spoken.

Related documents:

- [Dissertation video storyboard](video_storyboard.md)
- [Demo script](demo_script.md)
- [Demo checklist](demo_checklist.md)
- [Capacity pilot exploratory results](evaluation/capacity_pilot_results_20260727.md)

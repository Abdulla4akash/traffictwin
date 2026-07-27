# Dissertation video storyboard (6–8 minutes)

A planned shot list for the submitted video, built on the existing
[demo script](demo_script.md) and [demo checklist](demo_checklist.md) rather than beside them.
Every shot names the demo-script step it executes, so the rehearsal and the recording follow
one path.

**This document makes no scientific claim.** Where a shot needs a result, it points the camera
at the committed results record and the speaker names the record — it never reads a number
into the narration, and no number appears in this file.

## Why the shots are ordered this way

The recorded rubric note for this component splits the marks as **Use of Medium 40%** and
**Complementing the Report 40%**, with the remaining 20% not itemised in the note. This
storyboard optimises the two named components and does not guess at the rest:

- *Use of Medium* is served by planning: fixed timings, a written narration beat per shot, no
  improvised navigation, and a single continuous screen capture per section so cuts land on
  intent rather than on a mis-click.
- *Complementing the Report* is served by spending the middle four minutes on material the
  written report structurally cannot carry — motion, interaction, and click-through. Those
  shots are marked **UN-REPORTED** below.

The video is 15% of the grade in the recorded note, which is why it is storyboarded rather
than improvised, and why the total runs to 7:00 inside the 6–8 minute window with room to
breathe.

## Shot list

| # | Time | Length | Shot | Demo-script step | Un-reported? |
|---:|---|---:|---|---|---|
| 1 | 0:00–0:40 | 0:40 | Hook: talking head over the Manchester Operations map | — (opening) | partly |
| 2 | 0:40–1:10 | 0:30 | Home / Project Status, capability honesty | step 1 | no |
| 3 | 1:10–1:40 | 0:30 | Guided Demo track and the evidence boundary | step 2 | no |
| 4 | 1:40–2:15 | 0:35 | Bundle Import validating baseline, then variation | steps 5–6 | no |
| 5 | 2:15–2:45 | 0:30 | Run Overview: unavailable is not zero | step 7 | no |
| 6 | 2:45–3:25 | 0:40 | **Replay animation** with the `HISTORICAL REPLAY` badge | step 8 | **UN-REPORTED** |
| 7 | 3:25–4:00 | 0:35 | **RSU Monitor drill-down** into one RSU's window | additive `/rsu-monitor` | **UN-REPORTED** |
| 8 | 4:00–4:40 | 0:40 | Diagnostics & Evidence: a rule fires | step 12 | no |
| 9 | 4:40–5:25 | 0:45 | **Provenance DAG click-through** to the source row | step 16 | **UN-REPORTED** |
| 10 | 5:25–6:05 | 0:40 | **Match Review: decide → persist → seal** | additive `/match-review` | **UN-REPORTED** |
| 11 | 6:05–6:35 | 0:30 | Experiment instrument: predeclaration, campaign receipt, results record | — (new surfaces) | partly |
| 12 | 6:35–7:00 | 0:25 | Wrap: objectives, one honest limitation, future work | — (closing) | no |

Total **7:00**.

### Shot-by-shot notes

**1 — Hook (0:00–0:40).** Open on the Manchester Operations map with a talking-head overlay;
the rubric note explicitly encourages the talking head. State the problem in one sentence:
vehicular-edge offloading policies are trained on synthetic fleets, and the question is
whether their behaviour is trustworthy on evidence you can trace. Do not preview a result.

**2 — Home (0:40–1:10).** Demo-script step 1. Show that direct launch is unsupported and that
unknown capabilities stay unknown. This is the shot that establishes the honesty discipline
the rest of the video relies on; if the audience does not believe the unavailable states are
real, nothing later lands.

**3 — Guided Demo (1:10–1:40).** Demo-script step 2. Show the standalone synthetic track and
say the separation aloud: simulation artifacts, deterministic pipeline, researcher
interpretation. Do not click into the imported track unless the authorised package is
configured on the recording machine.

**4 — Bundle Import (1:40–2:15).** Demo-script steps 5 and 6. Validate `.demo/bundles/baseline`
and then `.demo/bundles/stressed_demand`. Keep the accepted status, declared files, and record
counts on screen long enough to read. This shot exists so the later provenance click-through
has something the viewer has already seen validated.

**5 — Run Overview (2:15–2:45).** Demo-script step 7. Point at an unavailable optional metric
and say "unavailable is not zero" — one of the few narration lines worth scripting verbatim.

**6 — Replay animation (2:45–3:25) — UN-REPORTED.** Demo-script step 8. This is motion, and a
report cannot carry motion. Play, then use one speed preset and one scrubber jump. Keep the
`HISTORICAL REPLAY` badge visible in frame for the whole shot and say there is no wall-clock
live source. Do not narrate over the first four seconds; let the animation read.

**7 — RSU Monitor drill-down (3:25–4:00) — UN-REPORTED.** The additive `/rsu-monitor` route.
Select one RSU and show its queue and in-flight series across the run window, then the
cross-RSU asymmetry table. Say what the page says: pressure is in-flight tasks over recorded
maximum concurrency, it is not CPU utilisation, and per-RSU energy does not exist in the
accepted loaders. The interaction — choosing an RSU and watching the window change — is the
un-reported part; a report can print one table, not the act of comparing.

**8 — Diagnostics (4:00–4:40).** Demo-script step 12. Use `.demo/bundles/under_offloading` so a
rule fires on camera. Say "candidate explanation", never "cause". Show that the insufficient
rules stay insufficient rather than being hidden.

**9 — Provenance DAG click-through (4:40–5:25) — UN-REPORTED.** Demo-script step 16, and the
single highest-value shot in the video. Start at a metric, click through the definition, the
canonical table, and the row sample, then switch to source-row mode and land on `tasks.csv`
row 2 — the raw row beside its canonical record. A report can print the endpoints of that
chain; only video can show a person walking it in one continuous take. Do not cut inside this
shot. Say that lineage depth is traceability, not correctness and not causality.

**10 — Match Review decide-persist-seal (5:25–6:05) — UN-REPORTED.** The additive
`/match-review` route. Record one decision with a named reviewer and a written reason, show
the row change state, reload to show it persisted, then seal for export. This is the shot that
demonstrates a *human* decision boundary rather than describing one: the rows were visibly
pending until a person decided them, and the ledger is append-only.

**11 — Experiment instrument (6:05–6:35).** Show the signed predeclaration document, then the
additive `/campaigns` route reading that campaign's receipt, then open the committed results
record. **Name the records; do not read their numbers.** The narration line is that the design
was fixed before any result was visible, the approval binds the document's bytes, and the
result — whatever it says — is published under a null-publication commitment recorded in
advance.

**12 — Wrap (6:35–7:00).** Objectives met, one honest limitation stated plainly, and the named
next step. End on the limitation rather than burying it; the rubric rewards the medium being
used well, and a clean, unhedged closing limitation is a better use of thirty seconds than a
montage.

## Spoken-caveats checklist

The checklist's *Required Spoken Caveats* apply to the video exactly as they apply to a live
demonstration. Tick each one against the shot that carries it, and re-record the shot rather
than adding a caption afterwards.

- [ ] Synthetic fixtures are not real Manchester data. *(shots 2–5)*
- [ ] Historical replay is not live data. *(shot 6 — the badge must also be visible)*
- [ ] Diagnostic hypotheses are not proven root causes. *(shot 8)*
- [ ] Provenance supports traceability and auditability, not proof of correctness or
  causality. *(shot 9)*
- [ ] Read-only TOS inspection and bounded SUMO import are available, but full Randy/VEC
  conversion and launch stay blocked. *(shot 2 or 3)*
- [ ] Direct launch is intentionally disabled. *(shot 2)*
- [ ] Unknown TOS publication permission remains visible as an integration gate. *(shot 2 or
  11)*
- [ ] The supervisor ZIP is labelled private research material. *(only if it appears on
  screen)*
- [ ] Any public demonstration uses only the standalone synthetic static site. *(shot 12, if
  the video will be shared beyond the marker)*

Two further caveats this video needs that a live demo does not, because a recording is
re-watched and paused:

- [ ] Anything shown from the experiment instrument is `owner_approved_candidate` evidence —
  not supervisor-approved, not validated. *(shot 11)*
- [ ] Buses, where they appear, are transit vehicles and never general road traffic. *(shot 1
  or 7, if a bus surface is on screen)*

## Recording and equipment notes

**Before recording.** Run the demo checklist's pre-demo section in full — `uv sync`,
`uv run pytest`, a clean `git status --short`, and `uv run traffictwin demo initialise .demo`.
A failed fixture mid-take costs more than the setup does.

**Capture.**

- Record at 1920×1080 and keep the browser at a fixed window size for every screen shot; a
  resized window between takes is the most visible avoidable defect.
- Use the light theme throughout unless the whole video is dark — mixing them reads as
  carelessness, and the theme is a `.streamlit/config.toml` setting, not something to toggle
  mid-recording.
- Increase the browser zoom one step before recording. Text that is comfortable on a 27-inch
  monitor is unreadable in a downscaled video.
- Hide bookmarks, notifications, and any window title carrying a real path or identifier.
- One continuous take per shot. Cut between shots, never inside shot 9.

**Audio.** Record narration separately from the screen capture against the written beat for
each shot, then lay it under the picture. Scripted narration is what the *Use of Medium*
component is measuring; live commentary over a live demo reliably runs long and hedges.

**Screen hygiene.** Nothing on screen may show a real vehicle reference, a session token, an
API key, or a private path. The surfaces used here publish aggregates only by construction,
but the terminal and the window title are not covered by that guarantee — check both frames
before recording.

**After recording.** Watch once at full speed with the caveat checklist in hand and tick each
box against the moment it is actually spoken. A caveat that is only in the storyboard is not a
caveat.

**Fallback.** If Streamlit will not start on the recording machine, the demo script's CLI
fallback covers the same evidence chain, but it cannot carry shots 6, 7, 9, or 10 — the
un-reported material is exactly the part that needs the UI. Fix the launch rather than
recording the fallback.

Related documents:

- [Demo script](demo_script.md)
- [Demo checklist](demo_checklist.md)
- [v0.7 navigation and additive routes](v07_navigation.md)
- [Screenshot checklist](assets/screenshots/README.md)

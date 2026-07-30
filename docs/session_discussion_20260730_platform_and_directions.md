# Session discussion archive — platform decisions and directions (30 July 2026)

**Status: owner-requested archive of six in-session assistant responses (30 July,
afternoon/evening). These are working discussion notes, NOT evidence, NOT records, and
nothing here is signed or supervisor-approved. Decisions referenced are recorded
authoritatively in `traffictwin-data-platform-v1-plan.md` and the phase claims; findings
referenced are authoritative only in their linked records. Kept because these responses
carry design reasoning (the two-tier what-if engine, the surrogate design, the
independent-study and Bangladesh directions) that later documents will draw on.**

---

## 1. The platform enters scope

*(response to the owner's directive: "no i want to do it the platform this is non negotiable")*

The platform is now officially in scope, planned, and pushed (`3363cc4`) —
`docs/traffictwin-data-platform-v1-plan.md`, Phase 136 claimed, indexed. The plan is built
to survive contact with the deadline:

**Three slices, in build order:**

1. **P-1: What-if scenario composer** — natural language in ("what if capacity drops 3.3×
   on the incident trace?"), a drafted campaign design + predeclaration out, human signs,
   the existing campaign instrument executes, and the composer writes an evidence-cited
   summary. The LLM only ever *drafts* — the approval and admission gates stay exactly as
   they are, so the platform inherits the project's rigor instead of undermining it.
2. **P-2: Prediction layer** — small honest hourly forecasts (bus concurrency/speeds, DfT
   profiles) with uncertainty and support counts shown.
3. **P-3: Platform dashboard** — data inventory, forecast, and composer pages in the
   existing UI.

**One deliberate non-build:** streaming ingestion — the measured 66–68 s feed cadence
proves polling already matches the source's information rate, and *proving* that in the
report beats building it.

**The timeline is the contract:** build to 13 Aug → freeze → user eval 11–22 Aug exercises
the platform pages (making it an *evaluated* artifact, which is exactly what disarms the
supervisor's "we don't care about programs" bar) → all feature work stops 22 Aug for the
report. That last line is what makes this compatible with "non-negotiable."

**Three decisions were the owner's, conservative defaults otherwise:** P-D1 an Anthropic
API key + small budget for the composer; P-D2 unattended BODS acquisition; P-D3 whether
the submitted ethics script covers platform pages.

## 2. The owner's three decisions, and the two-tier design

*(response to: coding-tool subscriptions already owned; tentative yes to unattended BODS;
ethics covers the platform; and "P-1 should use the actual data we have, feed it to some
model we build")*

The owner's P-1 instinct is the best idea in the thread, with one design move that makes
it both fast *and* honest. We already have the perfect training set: ~154 admitted cells
across 5 traces and capacities 0.1–2.5, plus a *closed-form backbone* (the ceiling law)
validated by pre-registered extrapolation 27/27 at 7.5× outside its fitted range. So the
what-if engine is **two-tier**:

1. **Predict instantly** — a small surrogate model fitted on our admitted cells (ceiling
   law as the mechanistic spine, per-trace/per-actor terms, uncertainty from seed spread).
   Ask "what if capacity drops 4× on the incident trace?" and it answers in milliseconds,
   *labelled as a prediction*, refusing or flagging anything outside the measured envelope.
2. **Verify on demand** — one click escalates to a real predeclared campaign run through
   the existing instrument, which produces *evidence*. The prediction and the eventual
   measurement sit side by side — and every verified prediction becomes new training data.

That predict-then-verify loop **is** the supervisor's platform in miniature: data in,
model predicts the future state, twin verifies.

**Correction on P-D1:** Claude Max / Codex Max are coding-tool subscriptions — they cover
building the thing, but they don't give the deployed app an API key to call at runtime.
So the composer ships with a structured form interface, and the natural-language layer
plugs in the moment a funded `ANTHROPIC_API_KEY` exists (small money, ~pennies/query).

**P-D2 (unattended BODS = tentative yes):** a scheduled session runner keeping every
existing rule (≥60 s, one-at-a-time, quarantine, session-scoped identity), feeding P-2
with more hours of data — currently its scarcest input.

**P-D3 resolved:** ethics covers platform pages — participants evaluate the platform.

All recorded in the amended plan (`6fe0936`).

## 3. What the surrogate model would be like

*(response to: "what would the surrogate model be like?")*

Small, mechanistic, and honest — closer to "the measured laws, packaged" than to a neural
net.

**Inputs (the scenario coordinates):** trace (`we`/`ev`/`wd_am`/`wd_pm`/`inc`), capacity
(0.1–2.5), actor (trained / baseline). That's the entire measured envelope; fleet preset
is fixed at `uk2030` because it's the only one with data.

**Outputs:** typed predictions with intervals for the metrics the campaigns actually
measure — deadline attainment, mean latency, median latency, the tail ceiling, offload
rate — each stamped `evidence: False`.

**The structure mirrors what the experiments found, in three regimes:**

1. **Off-saturation** (the four normal traces above their onset): the prediction is
   literally the measured cap-2.5 value for that trace and actor, with near-zero capacity
   uncertainty — because the paired differences were measured to be *exactly zero*. The
   model is an honest lookup there, and says so.
2. **Near onset** (the measured per-trace onset table: 0.25 / 0.25 / 0.1 / 0.1): the
   faint measured signature — completion up ~0.001–0.004 pp, latency down 0.02–0.2 ms —
   as tiny corrections.
3. **Saturated (`inc`)** — the mechanistic core: the ceiling law
   `p95-of-missed ≈ 39,959 ms × capacity`, mean latency linear in capacity per actor
   (~3,828 ms/unit trained, ~6,555 baseline — the 1.67–1.70× level factor from the
   crossover), p50 pinned at 44.3 ms, offload rates constant per actor (0.408 / 0.470),
   deadline attainment flat with the faint deep-squeeze rise. About two dozen fitted
   parameters in total.

**Uncertainty comes from seed spread**, which is the genuinely dominant noise (baseline
deadline rate spans 0.719–0.742 *across seeds* — far bigger than any capacity effect
off-saturation). Predictive intervals come from the 3–5 seeds behind each measured point,
widened at low capacity by the ceiling law's measured sag trend (+3.4% at cap-0.1 and
rising).

**Refusals are a first-class output.** Outside the envelope — an unstudied trace,
capacity beyond [0.1, 2.5], a different fleet mix, and notably **any fleet size in the
unmeasured (215, 2,488] density band, which is exactly where the real bus fleet (~1,200)
lives** — the predictor returns a typed refusal naming the gap, and the composer's answer
to a refusal is the tier-2 offer: "no data supports a prediction here; here's the drafted
campaign that would measure it." Every honest "I don't know" becomes a runnable
experiment, which is the platform's whole pitch.

**Fitting and provenance, house-style:** the fit routine reads only *committed* campaign
analyses (never raw cells), records their digests, and a self-test must reproduce the
published constants — K = 39,959, the two latency slopes, the crossover margin — before
the model is allowed to predict, exactly like the verdict scripts guard themselves.
Closed-form least squares in numpy; no sklearn, no training pipeline, fully deterministic.

**Why not a neural net** (worth one line in the report): 154 cells whose variation is
mostly structured zeros would be memorized, and a net would extrapolate confidently into
regions proven unmeasured. The small model is more accurate *and* more honest — and when
new verified runs land, refitting is instantaneous.

One growth axis: the predeclared-but-unlaunched fleet-composition campaign (3 cells)
would add a tier-share input — the first knob that predicts *attainment* changes rather
than latency.

## 4. What Codex is running on Colab

*(response to: "codex is running some colab stuff, can u tell me what that is?")*

It's the **B-BUS Sparse-64 clean rerun** — Codex re-running the bus-fleet training
campaign on a Colab G4 GPU, because the first one's result was spoiled at the last step:
the compute finished 5/5, but a `launchd` relaunch repeated the held-out peak evaluation
147 times and overwrote the archives, breaking the "evaluate peak once" rule — so the
result was non-admissible. The rerun (session `bbus-sparse64-clean-20260730`, attempt a5
at the time of writing) exists to produce a clean, admissible version.

The moving parts, from the processes and logs: the **supervisor**
(`supervise_colab_campaign.py`) — Codex's browser-independent orchestrator that uploads
the checkpointed pack, launches the training entrypoint, polls every 30 s, retries up to
5 attempts, and **mirrors every checkpoint locally** (which is why attempts a1–a4 dying
earlier that day cost nothing; a5 resumed from mirrored state); the **GPU execution**
itself (MAPPO training of the bus-native Sparse-64 scenario — the whole observed
Manchester bus fleet, dawn-trained, peak held out — five seeds {30–34}); a **keep-alive
daemon** pinned to the G4 machine (the fix for sessions silently dying while the kernel
showed idle); and a **proxy refresher** every 10 minutes.

Progress at the time of the question: all five seeds at update 900 of 1,562 (~58%, ~2.88M
of 5M environment steps), every checkpoint sha-recorded, completion projected that
evening — and even a died attempt resumes rather than restarts. It is entirely the
lead's lane (session, supervisor, and data directory untouched by this side), and it is
remote GPU, so it competes with nothing local.

## 5. Something independent of the producer

*(response to: "i want to make something independent of randy too idk what")*

Worth saying first: **a lot already exists with zero producer content** — the entire
Manchester twin chain (network build, DfT acquisition, map matching, demand
reconstruction and its diagnosis), the whole bus observation programme, and the evidence
platform itself. The producer's environment only touches the VEC/capacity track.

The recommendation for something *new* and fully owned, because it is 70% built and the
clock works in its favor: **a bus-dynamics study on our own collected data — with the
prediction model trained on it.**

- Already measured, and ours alone: Manchester buses move **44% slower at peak than at
  night**, a clean monotone hourly speed–density relation across a 36× fleet range, a
  stable 66–68 s feed cadence, and a genuine data-quality discovery (the cross-operator
  VehicleRef collision in the national feed). All from open BODS data, through our
  privacy design and quarantine pipeline.
- The just-approved unattended BODS runner (P-D2) turns four sessions into **weeks of
  sessions** — every day it runs adds a training day for free.
- P-2's prediction model then becomes the centerpiece instead of a demo: predict
  next-hour bus progression speed and fleet concurrency from time-of-day and current
  observations, **validated on held-out days** — a model we built, on data we collected,
  under the same predeclaration discipline. That answers the supervisor's "prediction
  models, we gotta train some" with something 100% independent.
- It slots straight into the platform story: ingestion → storage → analytics →
  prediction → dashboard. The independent science and the platform become one artifact.

Consequence for build order: **the scheduled BODS runner moves first**, because data
accumulates in real time and every day before it runs is a training day lost.

Ranked below it: a SUMO-side traffic what-if (blocked on the demand rebuild decision,
risky in five weeks), and writing up the MAN-05 data-quality finding as a standalone note
(nice, small, essentially free — could be done *in addition*).

## 6. The Bangladesh angle

*(response to: "i want to make the study palatable to bd govt... for funding, so how can I
add bangladesh here?")*

There is a genuinely honest version of this — because the project's own results translate
into exactly the message a resource-constrained government needs to hear.

**The narrative hook already owned:** the findings say, with pre-registered rigor, that
*adding capacity often does nothing* (four of five traffic regimes completely inert),
that where it *does* matter is narrow and measurable (only the saturated collapse hour),
and that the binding problem can be placement, not capacity (three of ten RSUs carrying
literally zero load). For a government with tight budgets: **"we build the evidence layer
that tells you which infrastructure spending is wasted before you spend it."** Dhaka is
one of the most congested cities on earth — congestion cost estimates run to billions of
dollars a year — and the national agenda is literally branded *Smart Bangladesh 2041*.

**What honestly transfers vs what doesn't:**

- *Transfers directly:* the entire methodology. The network builder runs on OSM —
  Geofabrik publishes Bangladesh extracts, so a Dhaka network build uses the exact
  committed pipeline. SUMO, the quarantine/receipt ingestion, the admission discipline,
  the what-if engine, the prediction layer — all data-source-agnostic by design.
- *Doesn't transfer — and this gap IS the funding ask:* the data. Bangladesh has no BODS
  equivalent and no DfT-style open count archive; Dhaka's buses are largely untracked
  private operators. So the pitch writes itself: **Manchester proves what the platform
  does when open data exists; Bangladesh needs the data layer built; fund a pilot
  corridor** — GPS units on BRTC buses on one corridor, ~12 months, feeding the same
  platform. The bus programme's privacy design (session-scoped identity, aggregate-only)
  is a ready-made answer to the surveillance objection a government pitch will face.

**How to add Bangladesh without endangering 4 September — three tiers:**

1. **Words, not weeks (do this):** a transferability section in the dissertation — the
   methodology-transfers/data-gap analysis, framed as designed future deployment. Costs a
   page; makes the dissertation itself the exhibit for the funding pitch.
2. **One cheap artifact (only after the 13 Aug platform freeze, if time):** build a Dhaka
   corridor network from the Geofabrik Bangladesh extract through the existing pipeline
   and validate it — a committed, receipted "the twin already runs on Dhaka roads" proof.
   Roughly a day, via normal governance for the scope-config addition.
3. **The actual funding document (separate from the dissertation):** a concept note for
   BD government channels — ICT Division innovation funding, a2i, DTCA, or the ADB/World
   Bank urban transport projects already operating in Dhaka. Problem (congestion cost,
   cited carefully), solution (the platform, with Manchester as evidence), pilot design
   (one corridor, BRTC partnership, cost sketch), and the "spend where it binds" evidence
   argument. This is where the Bangladesh energy should go — it doesn't belong inside the
   8k words.

Sequencing advice: keep building the platform now, put tier 1 in the report skeleton,
and draft the tier-3 concept note early, refining it after the results chapter exists.

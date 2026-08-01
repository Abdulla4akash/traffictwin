# Dissertation video narration — metric-to-mechanism cut

This script follows `video_storyboard.md`. Bracketed directions are not spoken. Record each block
separately and leave the planned visual pauses intact. The result records remain the numerical
authority; if a number changes there, this script must be re-audited before recording.

## Timing budget

| # | Shot | Picture time | Spoken words | Approximate speech at 140 wpm |
|---:|---|---:|---:|---:|
| 1 | Hook | 0:30 | 55 | 0:24 |
| 2 | Scope/source | 0:30 | 54 | 0:23 |
| 3 | Signed experiment | 0:40 | 73 | 0:31 |
| 4 | Paired result | 0:40 | 89 | 0:38 |
| 5 | Metric reversal | 0:40 | 79 | 0:34 |
| 6 | Actions/observations | 0:45 | 88 | 0:38 |
| 7 | Vehicle partition | 0:50 | 95 | 0:41 |
| 8 | RSU monitor | 0:35 | 65 | 0:28 |
| 9 | Provenance walk | 0:40 | 74 | 0:32 |
| 10 | Predictions | 0:30 | 62 | 0:27 |
| 11 | Buses | 0:20 | 45 | 0:19 |
| 12 | Conclusion | 0:20 | 44 | 0:19 |

**Total:** approximately 823 spoken words, leaving about one minute for visual silence, cuts and
breathing inside the seven-minute picture.

## Shot 1 — Hook

**[Capacity 2.5 shrinks to 0.75; mean latency falls; deadline line stays flat.]**

> I made the edge resource worse, and the usual performance number said the system got better.
> Reducing this RSU capacity control cut mean task latency by more than eight seconds, but it did
> not improve deadline attainment. That is not a recommendation to remove infrastructure. It is
> the problem: what exactly did the average reward?

## Shot 2 — Scope and source

**[Event-district extent and pinned source card.]**

> The central trace is one modelled collapse hour, from eight to nine in Manchester's Etihad and
> Co-op Live event district. It is not city-wide traffic. SUMO generated the mobility with seed
> forty-three. Randy Prasetia Putra produced the pinned environment, trace repository and trained
> checkpoint; TrafficTwin evaluates and audits those artifacts under permission with citation.

## Shot 3 — Signed experiment

**[Protocol digest flows to ten-cell campaign receipt, then result record.]**

> The pilot generated the hypothesis, so I did not call it confirmation. Before touching the
> reserved seeds, the owner approved this latency-primary protocol. Its exact bytes are hashed;
> edit the design and the runner refuses the approval. Five held-out seeds, two capacity arms,
> ten completed cells. The receipt and result are committed whatever the direction. This is
> confirmed within that signed project protocol—not supervisor approval, external validation or a
> claim about deployed Manchester.

## Shot 4 — Paired result

**[Highlight paired seeds 10–14, then show estimate and interval.]**

> Each line is one seed evaluated twice. All five point in the same direction. Mean latency falls
> from twelve thousand and twenty-seven point five milliseconds to three thousand seven hundred
> and sixteen point six. The paired estimate is minus eight thousand three hundred and ten point
> nine milliseconds; the bootstrap interval runs from minus nine thousand ninety-seven point five
> to minus seven thousand five hundred and twenty-four point three. With only five pairs, the
> exact two-sided sign-test floor is zero point zero six two five, and I report it.

## Shot 5 — Metric reversal

**[Deadline stays flat; p50, p99 and tail mass appear.]**

> Now watch the distribution instead of the mean. Deadline attainment stays at about seventy-nine
> percent. Median latency stays forty-four point three milliseconds at every pilot capacity. The
> ninety-ninth percentile falls by sixty-nine point nine percent, and between ninety-seven point
> nine and ninety-nine point four percent of all latency mass sits above one second. The resource
> squeeze is not helping the middle. It is compressing an already-late tail, so the average looks
> dramatically better while the deadline outcome stays flat.

## Shot 6 — Actions and observations

**[Action-invariance plot, then actor observation fields.]**

> Perhaps the policy adapts cleverly to scarcity. It does not. For each of nine pilot arm pairs I
> aligned eight million nine hundred and fifty-six thousand eight hundred vehicle-slot decisions,
> including their targets. There were zero mismatches. The RSU state changes, but the vehicle-side
> actor inputs are identical across these arms and contain no RSU-load term. Capacity changes the
> downstream queue while this fixed checkpoint chooses the same action. That explains why it does
> not adapt; it does not prove that adding a load field would improve it.

## Shot 7 — Vehicle partition

**[Split-screen never-offload and always-offload groups; animate cap 2.5 → 0.1.]**

> The post-hoc vehicle audit gives the mechanism. About three-fifths of vehicles never offload.
> Across a twenty-five-fold squeeze, their mean latency is bit-identical at thirty-nine point six
> milliseconds. The always-offloading group is exactly the weakest compute tier in every analysed
> cell. Its mean falls from roughly twenty-six seconds to roughly one point one seconds, yet this
> group still carries about ninety-two percent of missed tasks. Put the fleet mean between those
> groups and nobody experiences it: most vehicles receive exactly no change; the rest receive a
> huge reduction inside failure. The headline average describes neither population.

## Shot 8 — RSU monitor

**[Select saturated and idle RSUs; show 99.1% load concentration.]**

> Four roadside units run close to the recorded concurrency bound and carry ninety-nine point one
> percent of load; four are almost idle. Pressure here means in-flight work against that bound,
> not CPU utilisation. I initially blamed the association rule, then found that analysis used the
> wrong counting unit and contradicted busy-time evidence. I withdrew the causal explanation. The
> asymmetry is measured; its cause is undetermined.

## Shot 9 — Provenance walk

**[One continuous take: metric → definition → canonical row → source row.]**

> This is why TrafficTwin exists. I start at the reported metric, open its definition, follow the
> canonical table and land beside the bounded source row from which it was computed. The campaign
> record also pins the trace, checkpoint, environment and configuration. One chain, no hidden
> spreadsheet. But the limit matters: provenance supports traceability and auditability, not proof
> of correctness or causality. It shows where a number came from. It cannot make the source true.

## Shot 10 — Predictions and refutations

**[Three equal cards: held, refuted, refuted.]**

> A useful method must be able to say wrong. The inverse-capacity ceiling prediction held in all
> twenty-seven new checks. The prediction that two actors would have similar latency slopes was
> refuted by a fifty-two point five three percent contrast. Exact onset scaling was also refuted:
> four of six checks passed, and two failed by disclosed sub-microsecond differences. I keep all
> three outcomes.

## Shot 11 — Captured buses

**[Dawn/peak paths with full-shot `DESCRIPTIVE / NON-ADMITTED` banner.]**

> These dawn and peak paths are captured public-transport buses, not general traffic. The VEC
> tasks, equipment and sixty-four sites are synthetic and cover only about forty-five percent of
> occupied cells. A duplicate return broke the one-shot rule. The similar direction is
> descriptive and non-admitted—not confirmation.

## Shot 12 — Conclusion

**[Return to opening contrast; evidence labels collapse into conclusion.]**

> The contribution is not that less infrastructure is better. A QoS average can reward degradation
> when improvement sits entirely in tasks that fail either way. A signed test found the reversal;
> vehicle audit explained it; refutations and non-admitted transfer show where the claim stops.

## Pre-record audit

- Check every number against the committed result named in the storyboard.
- Keep the evidence-state label on screen for every results shot.
- Verify Putra environment/trace and SUMO credits on producer-derived frames.
- Rehearse decimal numbers slowly; never accelerate a shot to force the timing.
- If an authorised producer-derived UI is not available on the recording machine, use committed
  aggregate figures rather than showing a private path or repository.
- Watch the final export once with the narration muted and confirm that the central mechanism is
  still understandable.

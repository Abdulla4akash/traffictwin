# Sandra and Randy: TrafficTwin VEC progress email thread (12-18 August 2026)

## Source and transcription

- Source supplied by the repository owner: `p1.pdf`, 18 pages, an Outlook printout.
- PDF SHA-256: `037d1e0a517dd32c71a936a7ea6723511115de1e720c7f1468e584f9357be5ee`.
- Print timestamp displayed on the PDF: `06/09/2026, 21:36`. This is the print date, not the email date.
- Transcribed: 6 September 2026.
- Method: direct extraction of the embedded text with `pdftotext -layout`, checked against all 18 rendered pages. Raster OCR was unnecessary because the PDF contains selectable text.
- Scope: the complete visible five-message thread, in the newest-first order of the PDF. Message headers, wording, numerical values, and original spelling are retained. Dates and times are reproduced as displayed; no email timezone is inferred.
- Formatting: repeated print headers, private Outlook mailbox-URL footers, and the initial Outlook application label are omitted. Left margins and repeated blank lines are normalized. PDF line wrapping, including words and URLs split across lines, is retained. Bold, colour, bullet glyphs, and quote-box styling are not reproduced; indentation and numbered lists are retained.
- The headings, index, and transcription notes outside the fenced page text are editorial navigation, not email content.

This is a transcript of the owner-supplied PDF, not an original `.eml` export or a verification of email transport headers. It records the correspondents' statements; scientific results and implementation claims should still be checked against their underlying evidence.

## Message index

| Sender | Date and time displayed | PDF pages | Topic |
|---|---|---|---|
| Randy Putra | 18 August 2026, 4:34 PM | [1](#pdf-page-1)-[2](#pdf-page-2) | Radio-link sampling and one action / V2V helper per vehicle-second |
| Sandra Sampaio | 18 August 2026, 12:30 | [2](#pdf-page-2)-[4](#pdf-page-4) | Results, thesis framing, worked example, supporting metrics, and state-staleness suggestion |
| S M Abdulla Al Mamun | 17 August 2026, 17:40 | [5](#pdf-page-5)-[13](#pdf-page-13) | Thirteen-point architecture response, implementation questions, and proposed generalisation |
| Sandra Sampaio | 17 August 2026, 4:15 PM | [13](#pdf-page-13)-[17](#pdf-page-17) | Layered architecture, Questions 9-11, forwarding, state information, and V2V selection |
| S M Abdulla Al Mamun | 12 August 2026, 12:09 | [17](#pdf-page-17)-[18](#pdf-page-18) | Week 6 E0-E2d results and research-repository links |

Sandra's specific **100 ms, 500 ms, or 1 second** suggestion is on [PDF page 4](#pdf-page-4), in the paragraph beginning "Looking slightly further ahead". Her discussion of Question 11, state information and staleness, begins on [PDF page 14](#pdf-page-14) and continues on [PDF page 15](#pdf-page-15).

## Complete transcript

### PDF page 1

```text
Re: Week 6 TrafficTwin VEC progress: Deterministic RSU load management results
 From Randy Putra <randy.putra@postgrad.manchester.ac.uk>
 Date Tue 8/18/2026 4:34 PM
 To S M Abdulla Al Mamun <smabdullaal.mamun@postgrad.manchester.ac.uk>
 Cc Sandra Sampaio <S.Sampaio@manchester.ac.uk>
Dear Abdulla,

     Sandra Sampaio 18/08/2026 12:30
     Observation and execution link information My current reading is that the radio-link summaries used
     to construct MAPPO’s observation are generated separately from the operational link calculation
     used after MAPPO selects its action. This may mean that MAPPO observes one instantaneous
     channel sample, while the operational V2I or V2V target may use another channel sample. Was this
     intended, or would you expect the observation and execution stages to use the same link realisation
     within each vehicle-step?

Yes, it was an intended design for a realistic radio signal. Think of it as the model (MAPPO)
taking a photo of the road conditions to decide, and then the actual driving happening a
moment later when conditions have shifted slightly. The fixed part (how far away the RSU is)
is identical in both. Only the random wobble of the radio signal is re-rolled.

Is that OK? Yes:

The radio signal wobbles extremely fast, caused by it bouncing off surfaces and interfering
with itself hundreds of times per second, known as "fast fading" noise. So by the time you've
(MAPPO) measured/observed it, it's already different at execution time. Thus, re-rolling
(rolling the random signal wobbles) after MAPPO select its action is a realistic approach.
That noise wouldn't be much, but re-calculating it at execution is a good practice for planning
and realisation accounting.

Most important: training does exactly the same thing. So the MAPPO could learn to cope
with this realistic noise.

     One action and one V2V target per vehicle-step My reading is also that the evaluator calculates: one
     MAPPO mode choice for each active vehicle during the one-second step; one operational best-V2V
     target for that vehicle-step; and then uses them for the task substeps within that second. Was this
     the intended behaviour, or was the longer-term intention to select the mode and/or V2V target
     separately for each individual task arrival? These details were held the same across the E2c and
     E2d comparison arms, so they do not change the placement comparison. They would, however, be
     helpful to state clearly when documenting the architecture.

One action and one V2V target per vehicle-step, yes, both halves intended. The evaluator
computes one MAPPO mode choice and one best-V2V target per active vehicle per one-
second step, and all task arrivals within that second follow them.

For the V2V target, the intuition is like your phone network: a single radio associates with
one network at a time, and hopping between networks mid-burst costs real coordination
overhead rather than being free and instant. Our V2V offloading is a session in the same
sense (the helper receives the task, computes it, and returns the result), so the vehicle
keeps one helper per second rather than reselecting one on each arrival. We don't claim a
```

### PDF page 2

```text
literal 1-second association delay from any specific standard; the one-second cadence is a
modelling choice that reflects session and signalling overheads and matches the control-
plane rate of the rest of the platform. Re-selecting the target per task arrival would multiply
signalling and inference by up to K=5 while adding no actionable information, since the
decision-relevant state (geometry, neighbour set, shadowing) is effectively constant within a
second. The only thing that changes faster is the "fast fading" random noise, which
decorrelates before any decision could exploit it.

The same holds for the mode choice: one decision per vehicle-second, applied to that
second's arrivals. The known cost is that a burst cannot be split across destinations within a
second, a real limitation for now, but the per-task-type action for the next experiment/future
work is worth doing.

Thanks!
Best Regards,
Randy

From: Sandra Sampaio <S.Sampaio@manchester.ac.uk>
Sent: 18 August 2026 12:30
To: S M Abdulla Al Mamun <smabdullaal.mamun@postgrad.manchester.ac.uk>
Cc: Randy Putra <randy.putra@postgrad.manchester.ac.uk>
Subject: Re: Week 6 TrafficTwin VEC progress: Deterministic RSU load management results

Dear Abdulla and Randy,

Thank you for the update and, in particular, for waiting until you had completed the main
comparisons and validation checks before sharing the results. I appreciate how time-
consuming these campaigns have been, especially given the runtime constraints you
described.
I have now had a chance to read through the experiments carefully. My overall impression is
that the work has progressed well beyond simply comparing schedulers and has actually
clarified several of the questions that have been recurring throughout our recent email
exchanges.
What I find particularly encouraging is that the results seem to fit naturally into the
architectural discussions we have been having over the last few weeks.
One of the themes in our earlier exchanges was the distinction between the vehicle-side
policy and the infrastructure-side decision making. We discussed the idea that MAPPO
should continue to make the high-level offloading decision (Local, V2V, or V2I), while a
separate infrastructure layer would manage execution placement, admission, forwarding,
and ultimately load balancing across RSUs.
To me, your experiments now provide evidence that this infrastructure layer has an
identifiable role of its own.
Because MAPPO was kept frozen throughout the experiments, any changes in performance
cannot be attributed to changes in the learned policy. Instead, they must come from the
infrastructure-side scheduling decisions. That is quite an important observation because it
means we can isolate the impact of the scheduler itself.
In that sense, the results support the layered architecture we discussed earlier:

            MAPPO decides whether a task remains local, uses V2V, or enters the infrastructure
            through V2I.
            The infrastructure scheduler decides how V2I tasks are distributed across available
            RSUs.
```

### PDF page 3

```text
I think this separation of responsibilities is becoming increasingly clear in the results.
Another aspect that struck me is how neatly the findings connect with our earlier discussion
around Questions 9, 10, and 11. We previously talked about those questions as three
connected parts of a larger RSU coordination problem:

      the load-balancing architecture itself;
      task forwarding and execution placement;
      the information available to support those decisions.
Although your current experiments do not yet introduce a full forwarding model or explicit
state-staleness modelling, they do demonstrate that execution placement matters. In other
words, once the task has reached the infrastructure, the choice of execution destination can
have a measurable impact on deadline attainment.
That may seem obvious in hindsight, but the interesting part is that the result is highly
dependent on how the scheduler is implemented.
The transition from E2 to E2d illustrates this very clearly. The original common-target
implementation of the least-busy scheduler appears to have produced one conclusion. Once
the scheduler was changed to make placement decisions sequentially on a per-task basis,
the conclusion reversed.
To me, that is one of the most interesting outcomes of the entire study.
The experiments also reinforce another point we have discussed several times: queue
capacity and compute capacity are fundamentally different concepts.
E1 appears to confirm this rather strongly. Increasing the waiting-room size allowed more
tasks to enter the system and reduced rejection, but it did not translate into a clear
improvement in deadline attainment. In fact, larger queues increased waiting times and
latency.
This is broadly consistent with the argument we have been making that a larger waiting room
does not create a faster processor.
In practical terms, that suggests that future work should continue treating:

      admission capacity,
      compute capacity,
      placement policies,
      forwarding mechanisms,
      and scaling strategies
as separate experimental factors rather than combining them into a single notion of
"capacity".
I also found it interesting to think about these results in relation to our earlier discussion on
action masking.
The experiments do not directly address action masking because MAPPO was not retrained.
However, they do highlight another form of feasibility management that occurs after MAPPO
has already selected V2I.
In the action-masking discussion, we were concerned with questions such as:
Should MAPPO be allowed to choose an action that is physically infeasible?
The work you have done here instead addresses the next stage of the pipeline:
Once V2I has been selected, how should the infrastructure decide whether and where the
task should be executed?
So, in a sense, the scheduler experiments and a future action-masking study would address
two complementary levels of decision making.
Coming to the interpretation of the results, I would encourage you to be quite careful in how
the contribution is framed.
```

### PDF page 4

```text
My reading of the evidence is not simply:
"Least-busy scheduling is better than strongest-link scheduling."
I think the more interesting story is:
The implementation details of a scheduler can materially alter, and in this case reverse, the
observed result.
That is a much stronger scientific message because it highlights a methodological issue
rather than merely promoting one algorithm over another.
From what I can see, the evidence currently supports a claim along the lines of:
Within the tested Manchester incident scenario, a per-task sequential least-busy
scheduler produced a statistically positive improvement relative to strongest-link execution,
whereas a common-target least-busy implementation produced the opposite conclusion.
That is a much more nuanced result, but I think it is also much more publishable.
I would also continue to be cautious about generalising beyond the tested scenario. At this
stage I do not think the experiments justify statements such as "least-busy scheduling is
always better". Rather, they demonstrate that the per-task implementation performs better
under the conditions tested so far.
In terms of next steps, a few ideas immediately come to mind.

            First, I think the distinction between the common-target implementation and the per-
            task implementation deserves to be made explicit in the methodology. It is not simply a
            coding detail. It appears to be central to understanding the results.
            Second, it would be helpful to include a simple worked example showing how a
            common-target scheduler can unintentionally direct a surge of tasks towards a single
            RSU, whereas a per-task scheduler naturally redistributes work as the system state
            changes. I think such an example would make the results easier for readers to
            understand.
            Third, alongside the deadline-attainment results, I would continue recording and
            reporting supporting metrics such as queue lengths, RSU utilisation, workload
            distributions, rejection counts, and latency distributions. These provide the mechanism
            behind the outcome and make the conclusions much stronger.
            Looking slightly further ahead, the next question that occurs to me is whether the per-
            task scheduler remains effective when it no longer has perfectly current information.
            Earlier we discussed the issue of stale state information and delayed RSU status
            updates. The current implementation appears to make decisions using effectively fresh
            state. It would therefore be interesting to see how sensitive the results are to delays
            such as 100 ms, 500 ms, or 1 second.
            Finally, I agree with your decision to keep MAPPO frozen for this line of work. At the
            moment, I see that as a strength rather than a limitation because it allows the
            infrastructure-side contribution to be isolated cleanly. Any future work involving MAPPO
            retraining, expanded observations, or action masking can then be treated as a
            separate study rather than becoming mixed into the current experiments.

Overall, I think this is a strong piece of work. The progression from evaluator validation,
through admission-capacity experiments, to placement-policy investigation and finally
scheduler refinement shows exactly the kind of systematic reasoning that we have been
aiming for.

Thank you again for the detailed write-up. I found it both informative and thought-provoking,
and I think the results provide a good foundation for the next stage of the project.

Randy shall address the questions you directed to him.

Best regards,
Sandra
```

### PDF page 5

```text
From: S M Abdulla Al Mamun <smabdullaal.mamun@postgrad.manchester.ac.uk>
Date: Monday, 17 August 2026 at 17:40
To: Sandra Sampaio <S.Sampaio@manchester.ac.uk>
Subject: Re: Week 6 TrafficTwin VEC progress: Deterministic RSU load management results

Dear Dr. Sandra and Randy,

Thank you very much, Sandra, for your thoughtful response and for setting out the
architecture so clearly. Your layered interpretation is very helpful and is broadly aligned with
my current understanding of the implementation.

I have reviewed the frozen environment and evaluator code used for the E2c and E2d
studies so that I could respond carefully to each of the points you raised. I have summarised
my current understanding below, together with a few areas where I would be grateful for your
guidance before I prepare any further experimental work.

1. Did the architectural choice play a meaningful role?

Yes, I believe the architectural choice played a meaningful role within the Manchester
incident scenario that we tested.

Using the same frozen MAPPO actor and the same deadline-aware admission rule:

            the inherited common-target-per-substep least-busy approach was approximately
            2.12 percentage points lower than strongest-link execution;
            the per-task sequential least-busy approach was approximately 0.53 percentage
            points higher than strongest-link execution;
            the difference between the two least-busy implementations was approximately 2.65
            percentage points.

This suggests that the outcome depended not only on whether load balancing was used, but
also on how the infrastructure scheduler assigned the tasks.

The most balanced way I would currently describe the result is:

            Within the tested Manchester incident scenario, changing the dispatch approach
            from one common RSU per task substep to a separate least-busy choice for
            each task changed the direction of the observed deadline-performance result.

I would keep this conclusion within the tested setting. We have not compared the layered
architecture against a newly trained policy that jointly chooses both the offloading mode and
the execution node, so I would not yet make a wider claim that one overall architecture is
always better than the other.

2. What does MAPPO currently control?

Your understanding is correct that the frozen MAPPO actor selects one of three modes:

            Local;
            V2I;
            V2V.

MAPPO does not directly select:

            an RSU identity;
            a receiving vehicle identity;
            an admission outcome;
```

### PDF page 6

```text
a forwarding route;
            an infrastructure scaling level.

There is one timing detail that may be useful for the architecture description. In the real-
traffic evaluator, MAPPO produces one mode choice for each active vehicle during each
one-second simulation step. That mode is then used for the task arrivals associated with the
vehicle during the task substeps inside that second.

The closest description is therefore:

            MAPPO chooses the offloading mode for the active vehicle-step, while the
            environment and infrastructure logic manage target eligibility, placement,
            admission and execution.

I would also describe a V2I choice as an attempt to use the infrastructure, rather than a
guarantee that the task enters an RSU queue. A task may still be unavailable or not admitted
because of the radio link, the deadline rule or the queue-capacity rule.

MAPPO still has an important role because its choice determines how much offered work is
directed towards:

            the source vehicle’s local resources;
            neighbouring vehicles;
            the RSU infrastructure.

It also receives limited summaries of the communication and compute environment, but it
does not receive the detailed RSU workload state or directly choose the execution RSU.

3. Why the layered separation is useful

I agree with your point that the separation is attractive from both an architectural and
deployment perspective.

A vehicle-side policy would not normally be expected to maintain a detailed and perfectly
current view of:

            every RSU queue;
            worker utilisation;
            admission capacity;
            forwarding policies;
            infrastructure scaling state.

That information more naturally belongs to the infrastructure side.

Keeping MAPPO focused on the smaller Local/V2V/V2I action space may also make the
policy easier to manage than an action space containing every possible vehicle and RSU
target. The infrastructure layer can then manage the more detailed placement and resource
decisions using information that is available within the infrastructure.

4. How the V2I path currently works

The current V2I implementation contains two distinct RSU roles.

Ingress RSU

The environment evaluates the available V2I links and identifies the RSU with the strongest
current simulated link quality for the vehicle.

This is the radio-ingress RSU.
```

### PDF page 7

```text
Execution RSU

The execution RSU depends on the infrastructure mode.

For the baseline and strongest-link-with-admission conditions, the task executes at the
ingress RSU.

For the load-balancing conditions, the ingress RSU remains the same, but the infrastructure
scheduler may select a different RSU for execution.

In the final E2d approach, the scheduler considers each V2I task candidate in sequence. It
selects the RSU with the lowest remaining compute workload, checks the deadline and
capacity conditions, and updates the temporary workload before considering the next
candidate.

This is why the per-task approach used all ten RSUs much more evenly than the earlier
common-target approach.

Your proposed structure therefore reflects the logical architecture well:

Vehicle
   |
MAPPO selects Local / V2V / V2I
   |
Ingress RSU
   |
Infrastructure scheduler
   |
Execution RSU

5. What forwarding currently represents

The current evaluator represents forwarding at a logical, simulator-side level.

It records:

            the ingress RSU;
            the selected execution RSU;
            the actual execution RSU when the task is admitted;
            whether the ingress and execution RSUs differ;
            a configurable forwarding-delay value.

When the execution RSU differs from the ingress RSU, the task is counted as forwarded and
its compute work is placed in the selected execution RSU’s simulated queue.

At present, the evaluator does not include a detailed physical inter-RSU network model. For
example, it does not yet represent:

            a full RSU-to-RSU topology;
            individual backhaul-link capacities;
            multi-hop routing;
            backhaul congestion;
            packet-level transfer;
            reservation-message exchanges;
            controller communication delays.

For E2d, the forwarding delay was set to 0 ms. The result therefore focused on the effect of
placement and admission without adding a forwarding-delay effect.
```

### PDF page 8

```text
For the current work, I would describe this as:

            simulator-side infrastructure forwarding and remote-execution accounting,

rather than a complete physical forwarding deployment.

6. How Questions 9, 10 and 11 fit together

I agree that Questions 9, 10 and 11 form three connected parts of the future infrastructure-
control layer:

     1. who chooses the execution RSU;
     2. how work moves from ingress to execution;
     3. what RSU-state information is available to support that choice.

For the research design, it may still be useful to examine these parts separately.

For example, we can:

            change the placement rule while keeping forwarding delay fixed;
            change forwarding delay while keeping placement fixed;
            change state freshness while keeping placement and forwarding fixed.

This approach helped with E2c and E2d because the actor, traffic input, admission rule,
service level and forwarding delay remained controlled while the dispatch approach
changed.

A wording that may work well in the dissertation is:

            Questions 9, 10 and 11 form three connected parts of the infrastructure-control
            layer, while each part can still be examined separately so that the source of a
            performance change remains clear.

7. What state information the current scheduler uses

The final per-task scheduler currently uses:

            the remaining compute workload at each RSU, in milliseconds;
            the current admitted or in-flight task load at each RSU.

For each V2I candidate, it uses the current internal state, selects an RSU, and updates that
state immediately when the task is admitted.

The current E2d study therefore represents a setting where RSU information is available
centrally and without an information delay.

It does not yet include:

            delayed state updates;
            periodic polling;
            stale queue information;
            inconsistent views across RSUs;
            controller-to-RSU communication delay.

I agree that state freshness is an important future question. Before studying it, it would be
helpful to agree on the intended information-sharing model. Possible examples include:

            a central controller receiving regular RSU updates;
            ingress RSUs receiving periodic state messages;
            direct RSU-to-RSU state sharing;
```

### PDF page 9

```text
a Kubernetes-style control-plane view.

Each option would give a slightly different meaning to state delay and staleness.

8. The role of Kubernetes-inspired scaling

I agree that the following three-layer view is useful:

Layer 1:
MAPPO vehicle-level mode selection

Layer 2:
Infrastructure placement, admission and forwarding

Layer 3:
Infrastructure resource management and scaling

The evaluator contains optional simulator-side service-scaling modes, including static and
reactive service multipliers.

However, these were not used in the final E2d comparison. E2d kept the service setting fixed
at 1×.

There has also not been a real Kubernetes deployment. For the current dissertation and
experimental results, I would therefore use the terms:

            deterministic infrastructure-side RSU load management;
            Kubernetes-inspired scheduling or scaling.

The scaling layer remains a possible future extension rather than part of the completed E2d
result.

9. How the V2V target is currently selected

The V2V path also contains two decisions.

MAPPO selects the V2V mode, while the environment selects the receiving vehicle.

The current peer-selection process is:

     1. evaluate the simulated V2V link from the source vehicle to the other vehicles;
     2. exclude the source vehicle itself;
     3. exclude candidate vehicles whose queue is already full;
     4. choose the remaining vehicle with the highest current V2V link quality.

The target is therefore best described as:

            the available peer with the strongest instantaneous simulated V2V link.

Distance contributes to the link-quality value, but the approach is not simply “choose the
nearest vehicle,” because the simulated channel conditions and fading also influence the
value.

The current V2V target is not directly selected using:

            the shortest compute queue;
            the highest compute capability;
            the lowest expected end-to-end latency;
            the most stable future connection;
```

### PDF page 10

```text
the highest battery level;
            a learned neighbour-selection policy.

The receiving vehicle’s compute capability and queue workload affect the task’s latency after
selection. Apart from excluding a vehicle whose queue is already full, these factors do not
currently decide which peer is selected.

The selection rule itself is fixed once the calculated link-quality values are available.
However, the simulated link qualities include fading, so the selected peer may vary between
channel realisations.

This supports your wider point that V2V performance depends on both:

     1. MAPPO selecting V2V;
     2. the environment selecting and admitting the receiving vehicle.

10. Two implementation points where Randy’s guidance would be helpful

Randy, could you please confirm my reading of the following two details?

Observation and execution link information

My current reading is that the radio-link summaries used to construct MAPPO’s observation
are generated separately from the operational link calculation used after MAPPO selects its
action.

This may mean that MAPPO observes one instantaneous channel sample, while the
operational V2I or V2V target may use another channel sample.

Was this intended, or would you expect the observation and execution stages to use the
same link realisation within each vehicle-step?

One action and one V2V target per vehicle-step

My reading is also that the evaluator calculates:

            one MAPPO mode choice for each active vehicle during the one-second step;
            one operational best-V2V target for that vehicle-step;

and then uses them for the task substeps within that second.

Was this the intended behaviour, or was the longer-term intention to select the mode and/or
V2V target separately for each individual task arrival?

These details were held the same across the E2c and E2d comparison arms, so they do not
change the placement comparison. They would, however, be helpful to state clearly when
documenting the architecture.

11. V2V target selection as a future opportunity

I agree that V2V neighbour selection could become a useful future research topic.

Possible approaches could include:

            strongest-link selection;
            lowest-workload peer selection;
            compute-capability-aware selection;
            estimated end-to-end latency;
            mobility or contact-duration awareness;
            a learned target-selection policy.
```

### PDF page 11

```text
For the immediate work, my suggestion would be to document the current V2V behaviour
clearly and retain these alternatives as future directions, unless you would prefer V2V
selection to become a nearer-term priority.

12. Proposed architecture description and documentation

Based on your interpretation and the current implementation, I suggest documenting the
architecture as follows:

Layer 1 — Vehicle-level mode selection

Frozen MAPPO actor:
Local / V2V / V2I

Layer 2A — Environment-side communication target

V2I:
strongest current RSU radio link

V2V:
strongest current eligible peer link

Layer 2B — Infrastructure-side V2I control

execution-RSU placement
deadline-aware admission
capacity admission
logical forwarding
queue and service accounting

Layer 3 — Future infrastructure management

state-sharing model
state delay and freshness
physical forwarding constraints
Kubernetes-inspired resource scaling

I agree with your suggestion that we should document the responsibilities and information
boundaries explicitly.

I will add a concise architecture section or table covering:

     1. the responsibilities of MAPPO;
     2. the responsibilities of the infrastructure scheduler;
     3. the V2V target-selection mechanism;
     4. the V2I ingress and execution-selection mechanisms;
     5. the information available to each decision-making component.

This should make it easier to explain where any future performance improvement originates.

13. Generalisation to another use case or dataset

Thank you also for encouraging a generalisation step. I agree that this would strengthen the
work if the remaining time and compute resources allow it.
```

### PDF page 12

```text
To keep the result easy to interpret, my initial suggestion would be to retain:

            the same frozen MAPPO actor;
            the same task-accounting definitions;
            the same deadline-aware admission rule;
            the same service setting;
            the same forwarding-delay setting;
            the same current-state assumption;
            the same primary outcome definition.

We could then compare:

     1. strongest-link execution with deadline-aware admission;
     2. common-target-per-substep least-busy placement with the same admission rule;
     3. per-task sequential least-busy placement with the same admission rule.

This would allow us to see whether the same ordering appears in another use case without
changing several parts of the architecture at the same time.

I would be happy to take responsibility for preparing and administering this step. Before
scheduling the full runs, could I please ask for your guidance on the following points?

     1. When you mention another use case or traffic dataset, would you prefer:
              another traffic condition from the traces already available to us; or
              a fully separate external dataset or geographical setting?
     2. Would your main preference be:
              a quicker comparison under a different traffic condition; or
              broader generalisation using an independent dataset, even if it requires more
              preparation?
     3. Would you be comfortable with keeping forwarding delay, state freshness and scaling
        fixed for the first generalisation step, so that the dataset or use-case change remains
        the main new factor?
     4. Would you prefer:
              the full three-condition comparison; or
              a smaller comparison between strongest-link execution and per-task least-busy
              placement?
     5. Would you like forwarding delay and state freshness to follow later as separate studies,
        or would you prefer either of them to take priority over the dataset generalisation?
     6. Should V2V target selection remain a documented future direction for now, or would
        you like me to include a small V2V target-selection review before the next V2I study?

Once we have agreed on the scope, I will prepare a clear experiment plan before beginning
any full run. This will include:

            the exact dataset and scenario identity;
            the comparison conditions;
            the settings that remain fixed;
            the replication unit;
            the primary comparison;
            the accounting and conservation checks;
            the stopping conditions;
            the expected runtime and storage requirement.

Thank you again for the detailed guidance. I find the hierarchical view very helpful,
particularly for explaining where MAPPO’s responsibility ends and where the environment
and infrastructure responsibilities begin.

Best regards,
```

### PDF page 13

```text
S M Abdulla Al Mamun

From: Sandra Sampaio <S.Sampaio@manchester.ac.uk>
Sent: Monday, August 17, 2026 4:15 PM
To: S M Abdulla Al Mamun <smabdullaal.mamun@postgrad.manchester.ac.uk>
Cc: Randy Putra <randy.putra@postgrad.manchester.ac.uk>
Subject: Re: Week 6 TrafficTwin VEC progress: Deterministic RSU load management results

Dear Abdulla,

Thank you for the update and the material you generated! The results are indeed interesting.
I would also recommend/encourage a generalisation step towards another use case
(another traffic dataset), if time allows it.

Correct me if I am wrong to believe that the architectural choice seems to have played a
significant role.

I have been thinking further about the relationship between the proposed load-balancing
architecture, RSU forwarding, state-information management, and the role of the existing
MAPPO policy. I believe there are several important architectural and research questions
that are worth clarifying before too long (this may be more relevant to Randy, than to you, as
your focus seems to be more on the V2I)
One of the things that struck me is that the issues discussed in Abdulla’s Questions 9, 10,
and 11 (in a previous message from him to us) are not independent questions. They are
really three layers of the same infrastructure-level problem and, when viewed together, they
define the architecture of the future RSU coordination layer.
++++How I Currently Understand the Architecture:
The existing system appears to operate as follows:
Vehicle
|
+--> Local
|
+--> V2V
|
+--> V2I
|
v
Best RSU
|
v
Execute
In this architecture, MAPPO decides whether a task should be processed:

     locally;
     through V2V;
     through V2I.
Once V2I is chosen, the environment determines the target RSU using deterministic logic.
The proposed design seems to be moving towards the following structure:
Vehicle
|
| MAPPO
```

### PDF page 14

```text
v
Local / V2V / V2I
|
v
Ingress RSU
|
v
Infrastructure Scheduler
|
v
Execution RSU
Under this interpretation, MAPPO decides whether the task enters the infrastructure, while
the infrastructure decides where it should ultimately execute.
I find this separation of responsibilities intuitively appealing because it mirrors real edge-
computing deployments. Vehicles do not generally possess detailed knowledge of RSU
queues, worker utilisation, Kubernetes state, admission limits, or forwarding policies. By
contrast, the infrastructure naturally has that information available.

+++Relationship Between Abdulla’s Questions 9, 10, and 11
I now see these three questions as defining a hierarchy:
Question 9 - Load-Balancing Architecture
This determines who makes the execution-placement decision.
The proposed Option B effectively says:

      vehicles decide whether to use V2I;
      ingress RSUs receive the tasks;
      an infrastructure-side dispatcher chooses the execution RSU.
This establishes the overall control architecture.
Question 10 - Inter-RSU Forwarding
Once Option B is adopted, tasks may need to move between RSUs.
For example:
Vehicle
|
RSU A (Ingress)
|
+------> RSU B (Execution)
Question 10 therefore defines the forwarding mechanism itself:

      topology;
      latency assumptions;
      reservation model;
      rejection handling;
      forwarding restrictions;
      execution semantics.
In short, it defines how tasks physically move through the infrastructure.
Question 11 - State Information and Staleness
Once forwarding is introduced, a new question immediately arises:
How does the dispatcher know which RSU to choose?
The answer is that it requires knowledge of RSU state:
```

### PDF page 15

```text
queue lengths;
      worker availability;
      utilisation;
      backlog;
      admission capacity.
The difficulty is that this information may already be stale by the time it is used.
Consequently, Question 11 defines the information model used by the load balancer and
explores the impact of information delay.
I therefore see Questions 9, 10, and 11 as defining:

   1. the architecture;
   2. the forwarding mechanism;
   3. the information available to drive forwarding decisions.
From my perspective, these three questions collectively define the future infrastructure-side
control layer.
+++++A Question About the Role of MAPPO
Thinking about this architecture also raises an important question.
If every V2I task is sent first to the ingress RSU, what exactly is MAPPO still controlling?
My current interpretation is:
MAPPO:
Local / V2V / V2I

Infrastructure:
RSU selection
Task forwarding
Load balancing
Resource scaling
Under this interpretation, MAPPO is solving the problem:
Should this task remain local, be sent to another vehicle, or enter the infrastructure?
It is not solving:
Which RSU should execute the task?
This distinction is important because it suggests a layered control architecture:
Layer 1
Vehicle-level offloading policy
(MAPPO)
Layer 2
Infrastructure-level task placement policy
(Load Balancer / Dispatcher)
Layer 3
Infrastructure resource-management policy
(Kubernetes-inspired scaling)
Viewed in this way, the architecture becomes much clearer.
Another Question: How Does V2V Actually Work?
While thinking about the RSU architecture, another question occurred to me.
If MAPPO only decides:
Local
V2I
```

### PDF page 16

```text
V2V
how is the target vehicle selected in the V2V case?
For V2I, we know that the environment selects the RSU through deterministic logic.
Does something similar happen for V2V?
For example:
MAPPO
|
+--> V2V
|
+--> Environment chooses Vehicle A
If so:

      what criterion is used?
      strongest link?
      nearest neighbour?
      lowest latency?
      highest available compute capacity?
      some combination of these?
This is important because, just as with V2I, the final system performance may depend on
both:

    1. MAPPO deciding to use V2V;
    2. the environment choosing the receiving vehicle.
Consequently, understanding the neighbour-selection policy is necessary for correctly
interpreting the results.

++++Potential Research Opportunity
This line of thinking suggests another interesting research question.
At present, the architecture appears to separate:
Decision Type 1:
Which offloading mode?
from
Decision Type 2:
Which execution node?
This separation is attractive because it keeps the MAPPO action space small and
manageable.
However, it may also be worth asking whether neighbour selection itself could become an
optimisation problem.
Possible questions include:

      Is the current neighbour-selection policy deterministic?
      Is it load-aware?
      Does it consider neighbour compute capability?
      Does it consider mobility stability?
      Would a learned neighbour-selection policy outperform the current approach?
I am not suggesting that we pursue this immediately, but it may be worth documenting
clearly because the same questions we are now asking about RSU selection may eventually
apply to V2V selection as well.
+++++Suggestions
At this stage, I would suggest that we explicitly document:
```

### PDF page 17

```text
1. The exact responsibilities of MAPPO.
    2. The exact responsibilities of the infrastructure scheduler.
    3. The target-selection mechanism used for V2V.
    4. The target-selection mechanism used for V2I.
    5. The information available to each decision-making component.
I would also encourage us to think of the emerging system as a genuinely hierarchical
architecture rather than a single decision-making agent.
Such a description would make the design significantly clearer and would help us explain
where performance improvements originate, especially once forwarding, load balancing, and
Kubernetes-inspired scaling are introduced.
I would be interested to hear your thoughts and to understand more precisely how V2V
target selection is currently implemented in the codebase.
Best regards, Sandra
From: S M Abdulla Al Mamun <smabdullaal.mamun@postgrad.manchester.ac.uk>
Date: Wednesday, 12 August 2026 at 12:09
To: Sandra Sampaio <S.Sampaio@manchester.ac.uk>
Cc: Randy Putra <randy.putra@postgrad.manchester.ac.uk>
Subject: Week 6 TrafficTwin VEC progress: Deterministic RSU load management results

Dear Sandra,

Firstly, please accept my apologies for the delay in providing this update. The experimental
program took longer to complete than I initially expected. The validated runs had to execute
serially on the available Mac CPU, and individual experimental campaigns typically required
around 10–18 hours of runtime, with some approaching a full day. I therefore waited until the
main comparisons, and validation checks were complete before sending you the results.

Following your suggestion to investigate deterministic RSU load management while keeping
the trained MAPPO task-offloading policy unchanged, I kept the MAPPO actor frozen and
treated infrastructure scheduling as a separate layer after the vehicle selects Local/V2I/V2V.

Before attempting a full Kubernetes deployment, I first isolated and tested the scheduling
and admission behavior directly in the simulator.

The work developed through the following experiments:

            E0 — Evaluator validation: I corrected and validated task accounting, rejection
            handling, and task/service-work conservation.
            E1 — RSU queue capacity: I confirmed the distinction you highlighted earlier:
            the RSU queue limit is a waiting-room capacity, not compute power. Increasing it
            admitted more tasks and reduced rejection, but did not establish an improvement in
            offered-task deadline attainment. The primary result was inconclusive.
            E2 — Initial load balancing: Least-busy RSU placement produced better load
            balance, but lower deadline attainment than strongest-link execution.
            E2b — Placement and admission: I separated infrastructure placement from
            deadline-aware admission. Deadline-aware admission improved performance,
            while the inherited least-busy placement remained worse than strongest-link
            execution under the same admission rule.
            E2c — Multi-draw replication: Across four new matched fleet draws, the inherited
            least-busy implementation was approximately 2.12 percentage points lower than
            strongest-link execution. I then found that this implementation selected one common
            least-busy RSU for an entire task substep rather than selecting a new RSU for each
            task.
            E2d — Per-task load balancing: I implemented per-task sequential least-busy
            placement while keeping the MAPPO actor, task stream, admission rule, service rate,
```

### PDF page 18

```text
and other controls fixed. The result reversed: per-task least-busy placement was
            approximately 0.53 percentage points higher than strongest-link execution and
            approximately 2.65 percentage points higher than the inherited common-target
            implementation.

The main finding is therefore that deterministic RSU load management can improve
deadline performance, but the exact dispatch implementation can materially change,
and in this case reverse, the observed result.

At this stage, I would describe the implementation as deterministic infrastructure-side
RSU load management / Kubernetes-inspired scheduling, rather than a real Kubernetes
deployment. The current evidence is also limited to the tested Manchester incident scenario
and simulator configuration.

I have prepared a short experimental program summary with both an academic explanation
and a simplified technical-English version:

https://github.com/Abdulla4akash/traffictwin-vec-research/blob/agent/add-experimental-
programme-summary/TrafficTwin%20Experimental%20Programme%20Summary.md

I have also created a public research repository containing the complete E0→E2d
progression, methods, compact data, figures, evidence records, limitations, and
reproducibility information:

https://github.com/Abdulla4akash/traffictwin-vec-research

I apologize again for the slower update cycle. I am recovering well from my recent illness,
and now that the long experimental runs are complete, I expect to provide updates much
more frequently.

Best regards,

Aakash
MSc Artificial Intelligence
The University of Manchester
```

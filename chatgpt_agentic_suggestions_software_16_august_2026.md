# ChatGPT Agentic Suggestions — Software (16 August 2026)

> Provenance: ChatGPT analysis relayed by the owner on 2026-08-16, grounded in the two
> Sandra meeting records, Randy's meeting notes, Sandra's follow-up email, and the
> current TrafficTwin LLM/XAI architecture. Recorded verbatim as a suggestion
> document. Not a decision, not an implementation plan, not accepted scope.

Yes. I went back through the two Sandra meeting records, Randy's meeting notes, Sandra's follow-up email, and the current TrafficTwin LLM/XAI architecture. There is a pretty clear answer:

The best agentic addition is not a generic ChatGPT box. It is a bounded "TrafficTwin Analyst Agent" that uses TrafficTwin's deterministic analysis tools and evidence as tools, then explains, challenges, and recommends.

Sandra's direction was that the product should be a Manchester digital-twin-style app where a traffic analyst creates what-if scenarios, gets predictions/consequences, and can understand what decision to make; she also stressed that it should be small/simple but high impact and easy to use through an interface rather than forcing users into technical details. (meeting 2.docx) She also specifically floated combining/choosing among promising algorithms according to the scenario. (meeting 2.docx)

Randy then gave the most explicit agentic direction: the dashboard should identify overloaded RSUs and task failures, and the system could use generative/agentic AI to analyse whether the remedy is to improve/retrain the model or improve the infrastructure, then re-evaluate the result. He explicitly said agentic AI could replace some of the human data-analysis work.

So, ranked by how closely they fit those directions:

| Feature | What it would actually do | Fit |
|---|---|---|
| 1. TrafficTwin Analyst Agent | User asks: "Why are tasks failing here?" Agent calls Consequence Lenses, Infrastructure/RSU evidence, Decision Safety and Provenance; returns an evidence-linked explanation such as "RSU-3 is overloaded, rejection increased, but global compute is not saturated." | Build first |
| 2. Model-vs-Infrastructure Recommendation Agent | Given deterministic diagnostics, decides among investigate model/retraining, redistribute RSU load, increase infrastructure, change scenario, or insufficient evidence. LLM explains the recommendation; deterministic rules establish it. | Very strong PI/Randy alignment |
| 3. What-If Challenge Agent | User says "make this scenario challenging." Agent proposes 2–3 parameterised scenarios deliberately designed to reveal where different strategies win/lose, then user confirms one. This directly follows Sandra's "Morocco wins" idea: avoid obvious scenarios where the obvious algorithm always wins. (meeting 1 notes.docx) | Excellent dissertation feature |
| 4. Agentic What-If Loop | observe → diagnose → propose intervention → human approves → run allowed what-if → compare → explain result. For example: observe overloaded RSU → propose load balancing vs extra RSU → run synthetic/bounded simulation → compare deadline attainment → summarize. | Most visibly "agentic" |
| 5. Evidence/Literature RAG Agent | When the agent makes a technical interpretation, it can retrieve the project evidence plus curated peer-reviewed literature and show citations: "Why might stale RSU state matter?" → project evidence + relevant papers. | Good supporting feature |
| 6. Live Manchester Assistant | On your Live Bus/BODS demo, answer things like "What am I looking at?", "How fresh is this evidence?", "What changed since the last accepted snapshot?" while keeping BODS separate from road-traffic claims. | Great demo feature |

There is an especially nice architecture available because you already built most of the hard non-LLM pieces.

TrafficTwin already has a Decision-Safety Ruleset capable of deterministic rankings, winners, evidence-backed advisory recommendations and reviewable action drafts, while explicitly having no execution authority. That is almost tailor-made to become a tool for an LLM agent.

So instead of:

```
CSV
 ↓
LLM
 ↓
"Maybe add another RSU?"
```

I'd make it:

```
              TRAFFICTWIN ANALYST AGENT
                        │
        ┌───────────────┼────────────────┐
        ↓               ↓                ↓
 Consequence       Infrastructure     Provenance
   Lenses             / RSU              │
        │               │                │
        └───────────────┼────────────────┘
                        ↓
              Deterministic diagnosis
                        ↓
                Decision Safety
                        ↓
              bounded recommendation
                        ↓
                       LLM
                        ↓
             human-readable explanation
                        ↓
                  User approves
                        ↓
               What-If / comparison
```

## And this boundary matters a LOT

Sandra was actually quite explicit in Meeting 1 that academic arguments and ideas cannot simply come from generative AI: they need grounding in reputable published work; AI can help with wording, but the scientific basis needs cited sources. (meeting 1 notes.docx)

TrafficTwin already encoded exactly the right architecture for that. ADR-005 says diagnostics must be deterministic before LLM rendering; prompting an LLM with raw CSV/metrics and letting it invent findings was explicitly rejected.

So the agent should never calculate the scientific result.

It can say:

> "TrafficTwin's deterministic diagnostic identifies concentrated RSU load and increased rejection. Based on the admitted comparison, the infrastructure intervention is the stronger candidate to investigate. Here is the evidence and provenance."

It should not say:

> "I looked at the CSV and I think adding three RSUs will improve performance by 17%."

That distinction makes the LLM component academically defensible rather than gimmicky.

## One thing you already have

Interestingly, you've already implemented the beginning of this.

The current What-If Composer has a bounded DeepSeek natural-language agent/socket. A user can describe a scenario in ordinary language and DeepSeek translates it into the strict ComposerForm; the deterministic TrafficTwin code then performs the actual prediction/drafting. DeepSeek cannot supply predicted values, evidence, approval or execution.

So I wouldn't build another natural-language scenario chatbot. That's already there.

I'd extend that into:

```
User:
"Why did this scenario perform badly?"
              ↓
TrafficTwin Agent:
"I'll inspect the evidence."
[tool] consequence_lenses
[tool] infrastructure_evidence
[tool] decision_safety
[tool] provenance
              ↓
"Deadline attainment fell while RSU-2 became
saturated and RSU-7 remained lightly loaded.
TrafficTwin's deterministic assessment supports
testing infrastructure-side redistribution before
assuming the MAPPO actor needs retraining.
Would you like me to prepare:
[A] least-busy redistribution what-if
[B] additional-RSU what-if
[C] no change — inspect provenance"
```

Then:

```
User → A
Agent:
"Here are the parameters I propose changing."
[Review changes]
             USER APPROVES
                    ↓
          TrafficTwin executes
        allowed bounded what-if
                    ↓
               Compare
                    ↓
Agent:
"The intervention improved X but worsened Y.
Here is the evidence."
```

That is genuinely agentic. It observes, reasons over tools, proposes an action, waits for authority, obtains new evidence, and evaluates whether its recommendation worked.

And it is almost a literal software implementation of Randy's suggestion that the system analyse the results, decide whether the model or infrastructure needs improvement, make a suggestion, then re-evaluate. (randy meeting 1.docx)

One more important distinction: Sandra's later email also proposed "DRL task offloading + AI-based Kubernetes load balancing." (Pasted text(20260805-092802).txt) That's an AI scheduling/control research direction, not necessarily an LLM agent. I would keep that scientifically separate. The LLM agent should be the analyst/orchestrator/explanation layer, not secretly become the RSU scheduler.

Given where TrafficTwin is now, my pick would therefore be:

**TrafficTwin Analyst Agent → with three abilities: Explain, Recommend, and Challenge.**

That is small enough to build, visibly agentic, directly connected to the supervisor's what-if/decision-support vision, directly connected to Randy's agentic-AI suggestion, and it can sit on top of the deterministic/provenance machinery you already spent so much time building.

# TrafficTwin Multi-Agent Workflow — Latest

**Version:** 1

**Date:** 26 July 2026

**Intended host:** the verified TrafficTwin macOS development environment

## 1. Purpose

This guide defines a controlled planner–implementer–reviewer workflow for TrafficTwin:

- **Fable 5 High** plans and arbitrates.
- **Opus 4.8 Medium/High** implements.
- **GPT-5.6 Sol High/xHigh** performs adversarial review and QA.
- **The repository owner** retains final authority over scientific claims, external data,
  ethics, pushing, merging, and releases.

The workflow uses [Jinn](https://github.com/hristo2612/jinn) to run the first-party Claude Code
and Codex CLIs, route work between roles, retain activity evidence, and enforce approval and review
stages. Jinn is beta software; its orchestration records supplement rather than replace Git,
TrafficTwin evidence artifacts, tests, or human approval.

The durable asset is the separation of roles and gates, not a particular model label. Confirm that
the installed Claude Code and Codex CLIs expose the requested model names before relying on them.

## 2. Non-negotiable operating model

| Role | Preferred model | Filesystem authority | Responsibility | May sign off? |
|---|---|---|---|---|
| **Planner and arbitrator** | Fable 5, High | Read-only | Read the governing documents, define scope, produce the plan and acceptance criteria, and decide disputed P2 findings. | May accept or reject ordinary engineering work because it did not implement it; may not supply human/scientific authority. |
| **Implementer** | Opus 4.8, Medium or High | **Only writing agent** | Modify the agreed files, write tests, run checks, and produce a reviewable checkpoint commit. | No. It moves its work to review. |
| **Adversarial reviewer and QA** | GPT-5.6 Sol, High; xHigh only for unusually difficult review | Read-only | Read the complete diff, trace affected paths, run checks, reproduce material failures, and use browser QA when UI changed. | May verify engineering criteria; may not edit or approve its own fixes. |
| **Repository owner** | Human | Approval authority | Approve scientific/domain judgments, ethics, provider permissions, public actions, merge, release, and protected-ref changes. | Yes, within the owner's authority. |

Only the implementer may write to the task worktree. Planner and reviewer sessions must be
read-only. Never run two writing agents in the same worktree.

## 3. Governing repository context

Every new workflow run begins by fetching Git state and reading the following documents in full:

1. `origin/claude/complete-v0.7:AGENTS.md`
2. `origin/claude/complete-v0.7:CURRENT_STATUS_CONTEXT_PROMPT.md`
3. `origin/feature-suggestions:research_directions_codex_review.md`
4. `origin/feature-suggestions:codex_review_completed_possibility_rubric_v1.md`
5. The task-relevant design, status, integration, decision, and handoff documents

The original Claude research plan remains available as
`origin/feature-suggestions:research_directions_claude.md`, but it is planning input rather than
capability truth.

At minimum, each task records:

- the fetched base SHA;
- the working branch and worktree path;
- the exact governing document revisions;
- the initial worktree status;
- the allowed files and authority boundaries; and
- the required checks and evidence.

An orchestration summary is not a substitute for original evidence. The planner, implementer, and
reviewer must independently receive the task packet and applicable rules.

## 4. TrafficTwin safety boundaries

Repeat these rules in every agent brief:

- Never modify `main`, `v0.6.0`, or an existing v0.7 release/alpha tag.
- Never inspect, modify, stage, rename, delete, or clean the user-owned untracked
  `supervisor questions2 Gemini/` directory.
- Never reset, clean, stash, or overwrite unrelated user work.
- Never modify the audited external Randy/TOS repositories.
- Never invent metrics, findings, experimental results, calibration, participant evidence,
  analyst acceptance, provider semantics, permission, ethics approval, or supervisor approval.
- Never represent BODS buses as general traffic.
- Never represent TfGM signal locations as signal phase, timing, state, queue, or telemetry.
- Never convert missing or unavailable evidence to zero.
- Raw source, network, run, credential, private-path, and vehicle-identifier material remains
  outside Git unless its explicit evidence and permission contract allows otherwise.
- No push, merge, tag, release, deployment, public communication, or external write occurs without
  explicit owner authority for that action.

The workflow may verify that an acceptance gate passed. It may not replace a gate that explicitly
requires a human, provider, analyst, ethics body, or domain authority.

## 5. Workflow graph

```text
Manual trigger
    |
    v
Fable: read-only plan and acceptance criteria
    |
    v
Human plan approval
    |
    v
Opus: implement as the single writer
    |
    v
Deterministic checks and checkpoint commit
    |
    v
Sol: read-only adversarial review and scoped QA
    |
    +-- P0/P1 found --> Fable confirms scope --> Opus fixes --> Sol verifies
    |
    +-- disputed P2 --> Fable arbitrates
    |
    +-- no P0/P1 --> Fable reads the complete final diff
    |
    v
Human approval for any push, merge, release, scientific claim, or external action
    |
    v
End with retained evidence and an explicit terminal status
```

Use sequential workflow nodes for writing and review. Parallel work is allowed only for independent
read-only exploration or test/log analysis. Parallel agents must return bounded summaries rather
than raw transcripts.

## 6. Required task packet

Every planned task must instantiate this template before implementation:

```text
TASK_ID:
BASE_SHA:
WORKING_BRANCH:
WORKTREE:

GOAL:
WHY_IT_MATTERS:

IN_SCOPE:
OUT_OF_SCOPE:
FILES_ALLOWED_TO_CHANGE:
FILES_OR_PATHS_NEVER_TO_TOUCH:

MANDATORY_DOCUMENTS:
ASSUMPTIONS_ALREADY_ACCEPTED:
DECISIONS_REQUIRING_HUMAN_AUTHORITY:

ACCEPTANCE_CRITERIA:
REQUIRED_TESTS_AND_CHECKS:
REQUIRED_RUNTIME_OR_BROWSER_EVIDENCE:

REVIEW_THRESHOLD:
MAX_REPAIR_REVIEW_ROUNDS: 2
TIME_OR_COST_BUDGET:
STOP_CONDITION:
ESCALATION_CONDITION:

PUSH_AUTHORISED: false
MERGE_AUTHORISED: false
RELEASE_OR_TAG_AUTHORISED: false
```

If the allowed files, acceptance criteria, evidence route, or owner-only decision is unclear, the
planner must stop before sending the task to implementation.

## 7. Review severity and noise control

| Severity | Definition | Required action |
|---|---|---|
| **P0** | Data loss; credential or security exposure; protected-ref damage; fabricated or corrupted scientific evidence; destructive action outside authority. | Stop immediately, preserve evidence, and escalate to the owner. |
| **P1** | Incorrect behaviour; regression; violated acceptance criterion; material scientific-boundary error; missing critical test; unsafe failure mode. | Must be fixed or explicitly rejected by the owner with rationale. |
| **P2** | Concrete maintainability, usability, accessibility, or robustness concern inside the agreed scope. | Fable decides whether it belongs in this change. |
| **P3** | Style preference, speculative edge case, unrelated improvement, or non-consequential cleanup. | Do not report it in this workflow. |

The Sol reviewer receives these limits:

- report every evidenced P0/P1;
- report at most the three most consequential P2 findings;
- report no P3/style-only findings;
- cap the complete review at ten findings;
- cite files, symbols, evidence, reproduction steps, and affected acceptance criteria;
- distinguish observed failure from inference;
- do not edit files, commit, stage, push, merge, or alter workflow state outside review authority;
- stop when required checks pass and no P0/P1 remains; and
- after two repair/review rounds, stop and escalate rather than opening an infinite diligence loop.

Browser QA is required only when user-visible behaviour changed. Test the affected workflow first;
run broader route/viewport/theme matrices only when required by the task packet or final release
gate.

## 8. Phase briefs

### 8.1 Planner brief

```text
Act as TrafficTwin's read-only planner and arbitrator. Read every mandatory source in the task
packet before forming a plan. Verify the stated base SHA and worktree status. Decompose only the
smallest change that satisfies the goal. Define exact allowed files, acceptance criteria, required
tests, evidence, risk threshold, budget, stop condition, and human gates. Identify contradictions
or missing authority explicitly. Do not edit, stage, commit, push, merge, tag, or release.
```

### 8.2 Implementer brief

```text
Act as the sole TrafficTwin implementer for this task. Work only from the approved task packet and
plan. Verify the base SHA and working branch before editing. Modify only allowed files; preserve
unrelated and user-owned changes. Add or update proportionate tests. Run every required check.
Create a checkpoint commit only if the task packet authorises committing. Report changed files,
commands, results, limitations, and remaining gates. Do not approve your own work, broaden scope,
push, merge, tag, release, invent evidence, or resolve owner-only decisions.
```

### 8.3 Reviewer brief

```text
Act as an independent, read-only TrafficTwin reviewer. Read the original task packet, governing
rules, approved plan, complete diff from BASE_SHA, implementer evidence, and affected execution
paths. Re-run proportionate checks and use browser QA only for affected UI. Report findings using
the declared P0-P3 threshold and caps. Lead with concrete, reproducible correctness, scientific,
security, regression, and test risks. Do not edit, stage, commit, push, merge, tag, release, or
approve a human/scientific gate. Stop when no P0/P1 remains or the round cap is reached.
```

### 8.4 Arbitration brief

```text
Read the complete current diff and all reviewer findings. Confirm each finding against the task
packet and repository evidence. Accept P0/P1 repairs that are necessary for correctness. Admit a
P2 only when it is concrete, in scope, and proportionate to the deadline. Reject speculative or
style-only expansion. If agents disagree about scientific validity, permission, ethics, domain
acceptance, or owner intent, escalate to the owner rather than voting among models.
```

## 9. Mac installation and local configuration

Use Node.js 24 and install Jinn plus the first-party engine CLIs:

```bash
brew tap hristo2612/jinn https://github.com/hristo2612/jinn
brew install jinn

npm install -g @anthropic-ai/claude-code
npm install -g @openai/codex

claude  # sign in, then exit
codex   # sign in, then exit

jinn setup
jinn start
```

Keep the gateway on `127.0.0.1:7777`. Initially disable unnecessary connectors, schedules, public
webhooks, and external communications. Verify the installed CLIs independently before starting a
workflow. Jinn orchestrates available engines; it does not provide their authentication.

Before TrafficTwin work:

```bash
cd /Users/akashx/AntigravityTest/diss
git status --short --branch
git fetch origin --prune

export SUMO_HOME="/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO/share/sumo"
export PATH="$SUMO_HOME/bin:$PATH"

command -v sumo
sumo --version
python3 --version
uv --version
```

Use the literal repository and SUMO paths only if they match the actual Mac. Never let an agent
silently create an alternative clone or substitute a different simulator/runtime.

## 10. Branch and worktree policy

Start implementation work from the fetched v0.7 integration head, not `main` or
`feature-suggestions`:

```bash
git switch --create codex/research-evidence-chain-v1 origin/codex/traffictwin-v0.7
```

For later tasks, use a fresh task-specific branch name. Record the exact base SHA before work.
Prefer a dedicated task worktree when another process or agent may be active in the main clone.

Planner and reviewer phases are read-only and sequential relative to the implementer. The reviewer
reviews a checkpoint commit or an exact recorded diff so that the reviewed bytes cannot change
mid-review. Any subsequent repair invalidates the previous sign-off and requires a new bounded
verification pass.

## 11. Checks and definition of done

The task packet selects checks in proportion to the change. A task is not complete merely because
an agent returned successfully. Completion requires:

- the intended behaviour and every acceptance criterion are satisfied;
- only authorised files changed;
- focused tests pass;
- applicable integration/UI tests pass;
- applicable Ruff format/check and strict mypy gates pass;
- `git diff --check` passes;
- runtime or browser evidence exists where required;
- the reviewer reports no open P0/P1;
- Fable reads the complete final diff and resolves in-scope P2 findings;
- capability and evidence statuses remain honest; and
- every required human or external gate is either accepted by its real authority or remains
  explicitly pending/unavailable.

Historical test receipts in the status briefing establish the prior baseline; they do not prove a
new diff passes. Run the checks required for the new change.

## 12. First pilot workflow

Do not begin by automating mobile RSUs, multiple new scenes, broad UI polish, or the full Manchester
corridor. Pilot the orchestration on one bounded objective:

> Diagnose and close the smallest repository gap preventing one fresh VEC execution from entering
> the accepted scientific-metric workflow.

The pilot succeeds when:

1. Fable produces a bounded, evidence-backed plan from the verified v0.7 state.
2. The owner approves the plan and exact authority boundary.
3. Opus implements one coherent slice with tests as the sole writer.
4. Sol independently reviews the entire change and re-runs the agreed checks.
5. No P0/P1 remains after no more than two repair cycles.
6. The result either produces one honestly admissible end-to-end artifact or records the exact
   remaining external/human blocker without pretending completion.

Only after this loop works should it be reused for a tiny timed capacity pilot, the confirmatory
capacity study, user evaluation, a single follow-up experiment, or a time-boxed Manchester
corridor attempt.

## 13. Final operating principle

The planner decides what should be built, the implementer builds it, the reviewer tries to falsify
it, and the owner supplies authority that models do not possess. Durable task packets, Git SHAs,
tests, evidence artifacts, bounded review rounds, and explicit human gates—not model confidence—
determine whether TrafficTwin work is complete.

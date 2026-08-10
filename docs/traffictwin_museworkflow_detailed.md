# TrafficTwin Muse Workflow — Detailed Guide

A plain-language reference for the multi-agent development workflow used in this repository: what commits, HEADs, branches, PRs, freezing, and integration mean, and the exact order things happen in.

One important rule up front:

**You normally PUSH before the final reviewer says OK.**

Because the reviewer should review the **exact commit that exists on GitHub**, not some uncommitted code sitting only on your computer.

Think of your workflow like this:

## The basic workflow

```text
1. Muse changes code
        ↓
2. Muse runs tests
        ↓
3. Muse COMMITs the changes
        ↓
4. Muse PUSHes the commit to its GitHub branch
        ↓
5. Claude reviews that exact pushed commit
        ↓
6. Claude says:
      APPROVE
      or
      REQUEST CHANGES
        ↓
7a. If REQUEST CHANGES:
      Muse changes → tests → commit → push
      → Claude reviews NEW commit

7b. If APPROVE:
      STOP changing that branch
      = FROZEN
        ↓
8. Later Fable/integration worker combines
   the approved branches
        ↓
9. Final integration tests
        ↓
10. Merge into main
```

So **commit → push → review** is the normal order.

---

## What is a `commit`?

A commit is basically a **saved version of the repository**.

For example:

```text
ac6c65cfba92728e41db93617a35722cdb6d48c4
```

That long thing is the commit's **SHA**.

You can think:

> SHA = unique ID of this exact version of the code.

If you change even one line and commit again, you get a different SHA.

Example:

```text
Version A
ac6c65c
```

Then fix something:

```text
Version B
82f417a
```

Claude approving `ac6c65c` does **not automatically mean Claude approved `82f417a`**.

That's why we're obsessive about "exact-head review."

---

## What is `HEAD`?

This word sounds more complicated than it is.

**HEAD = the commit your branch currently points to.**

Suppose:

```text
A → B → C → D
            ↑
           HEAD
```

Your branch currently ends at `D`.

So:

```bash
git rev-parse HEAD
```

might return:

```text
ac6c65cfba92728e41db93617a35722cdb6d48c4
```

That means:

> My current version is commit `ac6c65c`.

---

## What is a branch head?

Same idea.

You have something like:

```text
main
   ↓
A → B

Muse 1 branch
   ↓
A → B → C → D
```

Muse 1's **branch head** is `D`.

If Muse makes another commit:

```text
A → B → C → D → E
                ↑
              HEAD
```

The head moved from `D` to `E`.

---

## What does "exact-head review" mean?

This is a really useful concept in this workflow.

Claude says:

> I reviewed exactly commit `D`.

Not:

> I vaguely reviewed this branch sometime today.

So we record:

```text
Claude APPROVE
exact head:
ac6c65cf...
```

Then we know precisely which code Claude approved.

If Muse creates:

```text
D → E
```

Claude's approval of `D` does not automatically cover `E`.

Therefore we send `E` back to Claude.

That's what we've been doing.

---

## What does `frozen` mean?

**Frozen is not a special Git command.**

It's just our workflow rule.

When we say:

> Muse 2 is frozen at `244f5b9`

we mean:

> Claude reviewed `244f5b9` and approved it.
> Nobody should change that branch anymore.

So:

```text
Muse 2
A → B → C → 244f5b9
              ↑
          APPROVED
          FROZEN
```

Don't do:

```text
A → B → C → 244f5b9 → X
```

because now the branch isn't pointing to the reviewed code anymore.

You'd need another review.

So **frozen = "hands off; this exact SHA is our approved artifact."**

It is a process concept, not some magical Git state.

---

## What is `local HEAD` vs `remote head` vs `PR head`?

This one is very important.

You can have three versions.

### Local HEAD

What's on your Mac:

```text
Muse computer
HEAD = E
```

### Remote branch head

What's actually pushed to GitHub:

```text
GitHub
branch = D
```

### PR head

What GitHub's Pull Request currently proposes:

```text
PR #26
head = D
```

If Muse has changed/committed something locally but hasn't pushed:

```text
LOCAL HEAD  = E
REMOTE HEAD = D
PR HEAD     = D
```

GitHub knows nothing about `E`.

After:

```bash
git push
```

you get:

```text
LOCAL HEAD  = E
REMOTE HEAD = E
PR HEAD     = E
```

Now Claude can say:

> I reviewed exact PR head `E`.

This is why we keep checking:

```text
local == remote == PR head
```

before freezing.

---

## What is the `working tree`?

That's the files currently sitting on the computer.

Suppose Claude edits:

```text
preregistration_studio.py
```

but hasn't committed.

Git says:

```text
modified: preregistration_studio.py
```

That's a **dirty working tree**.

Meaning:

> There are changes that haven't been saved in a commit yet.

If:

```bash
git status
```

shows nothing changed:

> **clean working tree**

So when a reviewer says:

> I've left it uncommitted

the situation is basically:

```text
GitHub PR head:
30214c43

Reviewer's computer:
30214c43 + some unsaved Git changes
```

The fix exists on disk, but there isn't a new commit SHA yet.

---

## Then why review uncommitted code at all?

That's okay during the **development/fixing stage**.

Claude can inspect a dirty local worktree and say:

> This looks good; tests pass.

But that's not the final artifact yet.

We still want:

```text
Claude's changes
      ↓
Muse adds regression test
      ↓
commit
      ↓
new SHA
      ↓
push
      ↓
Claude reviews NEW EXACT SHA
      ↓
APPROVE
      ↓
freeze
```

The second Claude review is what makes the final GitHub artifact trustworthy.

---

## What is `push`?

Commit saves locally.

Push sends those commits to GitHub.

So:

```text
CHANGE
↓
COMMIT
↓
PUSH
```

Think:

**change** = edit the Word document
**commit** = save a version
**push** = upload that saved version to GitHub

---

## What is a Pull Request / PR?

A PR basically says:

> Please take the work on this branch and eventually incorporate it into `main`.

Example:

```text
main
│
├──────── Muse 1 branch → PR #26
├──────── Muse 2 branch → PR #24
├──────── Muse 3 branch → PR #27
├──────── Muse 4 branch → PR #25
└──────── Muse 5 branch → PR #23
```

Each Muse is working independently.

Later Fable combines them.

---

## What is `main`?

`main` is your primary repository history.

Basically:

> This is the official current TrafficTwin codebase.

The Muse branches are candidate work.

Before merge:

```text
main
  |
  +-- Muse 1
  +-- Muse 2
  +-- Muse 3
  +-- Muse 4
  +-- Muse 5
```

After everything is integrated:

```text
main
A → B → V3 integrated product
```

---

## What is `merge`?

Merge means:

> Bring the changes from another branch into this branch.

For example:

```text
main:
A → B

Muse 2:
A → B → C
```

Merge Muse 2:

```text
main:
A → B → C
```

Conceptually.

With five workers there can be conflicts because multiple workers modified files such as:

```text
navigation.py
labels.py
page_runtime.py
```

That's why Fable's integration job matters.

---

## What's a merge conflict?

Imagine Muse 2 does:

```python
PAGES = [
    "Home",
    "Event Aligned",
]
```

Muse 5 separately does:

```python
PAGES = [
    "Home",
    "Preregistration",
]
```

When combining them Git says:

> Dude, which one?

Correct integration is:

```python
PAGES = [
    "Home",
    "Event Aligned",
    "Preregistration",
]
```

That's a merge conflict being **resolved**.

---

## What is `rebase`?

A rebase basically says:

> Pretend my branch started from the newest `main`.

Suppose:

```text
main:
A → B → C

Muse:
A → B → X → Y
```

Muse was created before `C`.

Rebase onto main:

```text
main:
A → B → C
          \
           X' → Y'
```

Notice:

```text
X ≠ X'
Y ≠ Y'
```

The commits get new SHAs.

That's why a rebase is a big deal in our review workflow.

If Claude approved:

```text
Y
```

and Muse rebases:

```text
Y → Y'
```

we should review `Y'`.

---

## What is force push?

A normal push adds commits.

A **force push** rewrites the branch's published history.

Often needed after a rebase because:

```text
GitHub:
X → Y

Local after rebase:
X' → Y'
```

Git says:

> These are different histories.

Then:

```bash
git push --force-with-lease
```

replaces the remote branch.

We use `--force-with-lease` because it's safer than raw `--force`.

But we avoid doing this casually, especially after reviews.

---

## What does `OPEN / DRAFT / MERGEABLE` mean?

### OPEN

The PR still exists and hasn't been closed/merged.

### DRAFT

The PR is intentionally not marked "ready for review/merge" in GitHub.

In this workflow we often leave these draft while doing exact-head review.

### MERGEABLE

GitHub thinks it can currently combine the branch with `main` without an immediate unresolved Git conflict.

It does **not** mean:

> Code is correct.

Just:

> Git can probably merge this.

Very different.

---

## What does "review closed" mean?

When we say:

> Claude review closed

we mean:

```text
implementation
↓
review
↓
fix
↓
review
↓
APPROVE
↓
no more findings
```

Then that lane is done.

We freeze it.

---

## What does "owner integration" mean?

This is the next phase.

The Muse workers shouldn't randomly merge their own PRs.

Instead:

```text
Muse 1 → frozen SHA
Muse 2 → frozen SHA
Muse 3 → frozen SHA
Muse 4 → frozen SHA
Muse 5 → frozen SHA
                 ↓
               Fable
                 ↓
      integrate all five together
                 ↓
       combined regression testing
                 ↓
              main
```

Fable is basically the **integration engineer**.

---

## The whole workflow in one picture

This is the cleanest representation:

```text
                 FEATURE DEVELOPMENT

GPT-5.6
  │
  │ gives task
  ▼
Muse
  │
  ├── edit
  ├── test
  ├── commit
  └── push
       │
       ▼
     Claude
       │
       ├── REQUEST CHANGES ─────────┐
       │                            │
       │                            ▼
       │                           Muse
       │                     edit/test/commit/push
       │                            │
       └────────── review again ◄───┘
       │
       ▼
    APPROVE
       │
       ▼
     FREEZE
   exact SHA
       │
       │
       │   Repeat independently
       │   for Muse 1–5
       ▼


                 INTEGRATION

Frozen Muse 1 SHA ─┐
Frozen Muse 2 SHA ─┤
Frozen Muse 3 SHA ─┤
Frozen Muse 4 SHA ─┤──► Fable
Frozen Muse 5 SHA ─┘       │
                           │ resolve integration
                           │ conflicts
                           │
                           ▼
                      combined tests
                           │
                           ▼
                     final integrated
                         version
                           │
                           ▼
                          MAIN
```

And the single most important rule in the whole system is:

> **Claude approves a SHA, not a vague branch.**

That's why `frozen head`, `exact head`, `PR head`, etc. keep coming up.

Once that clicks, almost all the Git terminology becomes much less mysterious.

# Claude session context prompt v8 — TrafficTwin, 1 August 2026

Supersedes V7. V3–V7 are historical; **this file carries the current state.**
Paste the block in §10 into a fresh session started from `~/AntigravityTest/diss-integration`.

---

## 1. READ THIS FIRST — state at handoff (1 Aug, afternoon)

**Nothing runs locally.** All overnight campaigns are COMPLETE and RECORDED. The active
mandate is a BUILD: the data platform v1 (owner: "non-negotiable"), with six committed
design docs in `docs/platform/` and a fixed build order. The owner is seeking a deadline
extension — scope is not cut for time, but dates hold until an extension is *granted*.

**Codex is MID-FLIGHT on Phase 138** (dissertation manuscript): at handoff,
`docs/dissertation_manuscript_20260801.md` + `docs/dissertation_literature_matrix_20260801.md`
were untracked and AGENTS.md + evaluation-plan + objectives-traceability were modified,
ALL UNCOMMITTED. **Never sweep these into a commit** — `git add` only your own named
files; check `git status` before every commit. My Phase claim for the platform design
docs is deferred until AGENTS.md is free (claim the next free number, currently 139).

## 2. The build queue (the actual work, in order)

Designs are committed — read each before building; they encode measured lessons:

1. **Scheduled BODS runner** — `docs/platform/bods_scheduled_runner_design.md`.
   FIRST because data accumulates in real time (bus prediction needs ~14 scheduled days
   for a held-out verdict). Detached supervisor, NOT launchd (two Sparse-64 deviations
   are the design input); completion marker written atomically BEFORE any fallible
   post-step; skip-late-never-run-late; acquisition boundary inherited verbatim.
2. **Outcome predictor** — `docs/platform/outcome_predictor_design.md`. Three-regime
   surrogate on the ~154 admitted cells; ceiling-law backbone; typed refusals
   (incl. `DENSITY_GAP` for (215, 2488]); fit accepts ONLY admitted campaign analyses
   (non-admitted/GPU-track refused by name); self-test gate must reproduce K=39,959,
   slopes 3,828.2/6,555.4, +6.09 pp margin, p50 44.3 before predicting.
3. **What-if composer** — `docs/platform/whatif_composer_design.md`. Draft-only
   (no execute import — tested); held-out {10–14} blocked twice; cite-only-committed;
   LLM socket dormant until a funded ANTHROPIC_API_KEY exists (owner's Max subs are
   coding tools, NOT runtime API).
4. **Bus prediction layer** — `docs/platform/bus_prediction_design.md`. The
   producer-independent study: climatology+persistence blend, chronological split,
   predeclared held-out-day validation with a publishable null, verdict code committed
   before held-out days exist.
5. **Dashboard pages** — `docs/platform/dashboard_design.md`. Inventory (incl.
   non-admitted diagnostic archives labelled verbatim) / Forecasts / Composer; additive;
   honest empty states; these are the pages the 11–22 Aug participants evaluate.
6. **Dhaka corridor (optional)** — `docs/platform/dhaka_corridor_design.md`. After the
   platform slices; owner decisions BD-D1 (corridor; proposed Airport road) and BD-D2
   (pinned dated Geofabrik BD extract) pending.

## 3. Decisions already taken (do not re-ask)

- **Ethics: SUBMITTED** (awaiting approval; user-eval window 11–22 Aug proposed).
- **Randy permission: CLOSED** (`5e507c3`) — written grant is held PRIVATELY by the
  owner, deliberately NOT filed in the repo. **Never ask for the text again.** Citation
  duties per `docs/producer_citation_requirements.md`.
- **P-D1** form-first composer; NL activates on a funded API key. **P-D2** tentative YES
  unattended BODS via the scheduled runner (rules unchanged). **P-D3** YES — ethics
  script covers platform pages.
- Platform freeze before the eval window; feature work stops for the report (dates may
  shift with the extension).

## 4. The science state (for anything that cites results)

- `docs/evaluation/experiment_catalogue_20260730.md` = detailed narrative of every
  experiment; the register (`docs/experiments_and_findings_20260728.md`) = the index.
- 30-Jul verdicts: **crossover — NO crossover** (trained wins all four capacities by
  ~+6.09 pp; prediction (3) REFUTED — slopes 3,828 vs 6,555 ms/unit, 52.5% contrast);
  **onset scaling — REFUTED 4/6** (sub-microsecond identity breaks; onsets
  0.25/0.25/0.1/0.1 not density-ordered).
- **Both Sparse-64 GPU returns are NON_ADMITTED** (first: 147 repeat evaluations;
  second: ONE repeat — terminal record written after fallible cleanup). Colab-study
  spot-verification (1 Aug): archive shas match records byte-for-byte (bmask cf18bedf…,
  bdomain 0d17154e…, bcap 77204c47…); chains of custody hold; deviations self-reported.
- Headline framing (owner-agreed): standard VEC QoS metrics can be improved by
  degrading the system; improvement lives entirely in already-failed tasks; the
  −8,310.9 ms describes no vehicle; capacity is the instrument, not the finding.

## 5. Owner queue (not agent-takeable)

CSF request + Sandra email sends; Sandra's questions email → answer to Sandra+Randy
(draft answers exist in the 30-Jul session; key correction: it is NOT SUMO — latency
exists only in the VEC evaluator); fleet-composition launch decision (3 cells,
recommended); demand-variant order; B1/G1–G5; stadium/R1; extension application;
match-review ledger (165 rows, human). Codex items: MAN-05 fix, GPU-track gate debt
(~51 mypy), codex FF.

## 6. Governance (unchanged, binding)

Worktree `~/AntigravityTest/diss-integration`, branch `claude/complete-v0.7`, push after
each slice. Phase claims in AGENTS.md before editing repo files; all-new disjoint files
for platform slices. `owner_approved_candidate` ceiling; no LLM output is ever evidence;
predictions/forecasts typed `evidence: False`. The owner's checkout `~/AntigravityTest/diss`
is NEVER touched; `cd` persists across Bash calls — return to the worktree explicitly.
Gates per slice: uv run pytest (focused + full), ruff + format, mypy --strict, uv lock
--check. If touching any shared campaign launcher: re-verify ALL pre-existing design
fingerprints byte-exactly afterwards.

## 7. Hard-won operational facts still live

Detached jobs (`start_new_session` + `caffeinate` + pid file) survive harness kills;
foreground wait loops do not — use Monitor. Writer-writes-marker for resumable stages.
BODS: quarantine manifest is `quarantine-manifest.json`; wire bytes are gzip (sha the
stored bytes BEFORE decompress); metric trap — `vehicles_linked_across_snapshots` is
session support, NOT concurrency (use per-snapshot `live_vehicle`); select sessions by
UTC stamp ranges, never hour prefixes; per-segment progression speed, never
displacement÷interval. Feed cadence 66–68 s stable across a 36× fleet range (why
streaming is deliberately not built — plan §4).

## 8. Where things live

Platform: plan `docs/traffictwin-data-platform-v1-plan.md` + `docs/platform/*`.
Session discussions: `docs/session_discussion_20260730_platform_and_directions.md`.
Campaign data: `data/vec-fresh/*`; verdicts `data/actor-crossover-verdict-20260729/`,
`data/onset-scaling-verdict-20260729/`. GPU archives: `data/gpu-track/` (private).
Workspace: `~/AntigravityTest/diss/data/workspace-v0.7`. Dissertation skeleton:
`~/Downloads/diss_mat/DISSERTATION_SKELETON.md` (8k words, COMP60060 rubric — no
Background chapter). Bangladesh direction: archive §6 + `docs/platform/dhaka_corridor_design.md`.

## 9. Boundaries (absolute)

Codex's lanes: MAN-05/bods.py, GPU track (`gpu/real_*`), the dissertation manuscript
(Phase 138), any live Colab session. Held-out seeds {10–14} spent. No supervisor
approval exists or is implied anywhere. Never claim provider mutation (N1 withdrawn).
Never promote `owner_approved_candidate` to anything stronger.

## 10. THE PROMPT TO PASTE INTO A FRESH SESSION

```
Read CLAUDE_SESSION_CONTEXT_PROMPT_V8.md at the repo root of
~/AntigravityTest/diss-integration first — it carries the current state (V3–V7 are
historical). Then check `git status` and `git log --oneline -5` for anything Codex
landed or left in flight since, and read the memory file's RESUME HERE.

The active mandate is the data platform v1 build (owner directive, design-first,
extension being sought — scope not cut for time). Build order and designs are in V8 §2;
start with the scheduled BODS runner unless the owner says otherwise, claim the next
free Phase number in AGENTS.md for it (deferred claims noted in V8 §1), implement to
the committed design, run the full gates, commit only your own files, push, and report.
```

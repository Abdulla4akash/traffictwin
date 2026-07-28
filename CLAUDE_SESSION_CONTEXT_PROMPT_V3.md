# Claude session context prompt v3 — TrafficTwin, morning of 28 July 2026

Supersedes V2 (which covered through the confirmatory result, ~01:15). Paste into a fresh
Claude session started from `~/AntigravityTest/diss-integration`:

```text
You are continuing as the owner-directed primary research/integration agent for
TrafficTwin. Multi-agent setup: you (primary; AGENTS.md phases 14–39, 80–93, next 95+),
parallel feature batches (40–71, complete), Codex as GPU-track lead (Colab campaigns; it
took Phase 82, 91, 94 — NOTE: Phase 91 is a NUMBERING COLLISION, used by both the primary
handoff claim and Codex's B-REWARD claim; harmless, file-scoped, flag it at
reconciliation). Standing delegation: "take reasonable choices and keep working" — ship
autonomously, record honest provenance, never fabricate approvals, owner decisions are
presented not taken. XAI framing is DROPPED (owner). Full research-directions-v2 scope by
4 September (owner).

FIRST ACTIONS — VERIFY
1. Read memory traffictwin-governance.md completely; then V2 (repo root) for the base
   state, then this file's deltas. Read docs/evaluation/capacity_grid_results_20260728.md,
   baseline_invariance_results_20260728.md, capacity_confirmatory_results_20260728.md,
   docs/evaluation/capacity_sweep_completion_predeclaration.md, AGENTS.md phases 88–94.
2. git status/pull --ff-only: branch claude/complete-v0.7, multiple agents push to it —
   re-verify HEAD before EVERY edit. Codex may have local-only commits; never rebase or
   force anything.

THE SCIENCE AS OF ~06:45, 28 JULY
- CONFIRMED (signed candidate (b), held-out {10–14}, now SPENT): capacity squeeze
  2.5→0.75 cuts mean latency −8,310.9 ms [−9,097.5, −7,524.3], all 5 seeds agree;
  deadline null replicated. docs/evaluation/capacity_confirmatory_results_20260728.md.
- MECHANISM (four independent legs): structural observation-space blindness — keyed
  actions bit-identical (0/8.9M × 9), vehicle-side observation inputs identical across
  arms while RSU-side differs ~41%, no RSU-load term in the observation; reproduced in a
  from-scratch GPU 17-D control; B0 CONFIRMED THE PREDICTION on the second actor
  (baseline_model_c_17 exactly invariant on ev; Phase 93 record).
- FIVE-REGIME SWEEP COMPLETE AND UNANIMOUS: capacity completely inert (all metrics
  exactly identical across arms) on we(139 slots), ev(175), wd_am(215), wd_pm(163) —
  only the 2,488-slot collapse hour shows outcome sensitivity. All five Gate-A traces
  admitted (ADR-062/065/066), each after its own measured probe. ev run cost measured
  265.9 s. Threshold bracketed (215, 2488].
- IN FLIGHT LOCALLY: ev-deep leg (arms 0.5/0.25/0.1, seeds {50–52}) measuring the
  binding ONSET — check data/vec-fresh/capacity-deep-ev/ (12 cells, done ~07:00);
  analyze via `uv run python scripts/capacity_grid_campaign.py ev-deep analyze`, then
  write the sweep-completion results record (wd-am + wd-pm zero-diffs + onset; Phase 95).
- CODEX GPU CAMPAIGNS (Colab G4, real producer code under recorded citation permission;
  artifacts preserved in data/gpu-track/ with SHAs): B-CAP full (10×5M steps, 17-D
  controls exactly invariant, 19-D capacity-obs responds; zip 77204c47…), B-REWARD full
  (α0.7 vs α1.0; pure-QoS ≈ +0.017pp completion, +0.04J energy, +10pp local, LESS
  capacity-switching 1.94% vs 3.51%; zip 316092d9…), B-MASK 2×2 masking (was 9/10 at
  06:07 — check /tmp/bmask* and preserve its archive to data/gpu-track/ when done),
  plus B-BUS-synthetic and IPPO smokes. All non-admitted diagnostics; homecoming to
  evidence requires pinned-actor review + local admission (not done).
- BUS SESSIONS (owner attended, live now): shallow early-morning session RUNNING —
  60 snapshots @65 s, started 06:12, done ~07:17, output
  workspace-v0.7/manchester/bus_shallow_am_session_20260728.json; then owner says
  "start peak" ~07:55 → run scripts/bus_cadence_probe_session.py with ~85 snapshots
  @65 s (attended, BODS_API_KEY in env, never echo). After each: process with
  `scripts/bus_session_report.py` (see --help) → B1 FILL-FROM-PROBE values; commit
  aggregates only (Phase 96). Third density point: night probe(41 active)/shallow/peak.
  ATTENDED RULE IS ABSOLUTE — never start a session without the owner present.

MORNING QUEUE (in order)
1. ~07:00 ev-deep completes → analyze → sweep-completion results record → push.
2. ~07:17 shallow session ends → bus_session_report → note aggregates.
3. 07:55 owner: "start peak" → launch peak session (85@65 s) → 09:30 report → update B1
   draft probe fields as PROPOSED.
4. Preserve B-MASK archive + record its provenance note (evidence JSON in
   docs/integration/evidence/, mirror bcap_engineering_smoke pattern).
5. Owner sends: ethics (CRITICAL), Sandra + Randy emails (action pack, updated),
   CSF request. Sandra meeting today — NEGOTIATION_CARD.md in ~/Downloads/diss_mat
   (platform framing, XAI dropped).
6. Codex integration handoff: CODEX_INTEGRATION_HANDOFF.md exists; after the morning's
   records land, owner tells Codex to review + fast-forward codex/traffictwin-v0.7
   (push sha:refs pattern; main untouched).
7. Later: week-4→5 progress update, cross-regime dissertation figure, crossover/stadium
   candidate signings (owner), demand/N1/R1 decisions (owner).

HARD BOUNDARIES (unchanged)
Never touch main/tags/external clones (NEVER fetch), byte-frozen
capacity_confirmatory_candidate_b_latency_primary.md, registries/data campaign dirs
except read-only, held-out {10–14} spent, label ceilings (owner_approved_candidate),
buses never general traffic, raw refs never leave quarantine, attended-only BODS.
Detached-launch pattern for >1 h jobs (start_new_session + caffeinate + pid file);
session-managed background tasks get killed. Fingerprint gotchas: approval text and arm
labels are inside design fingerprints — verify old fingerprints byte-exactly after ANY
edit to shared design code (bitten twice).

GOTCHAS: cd persists; pull --ff-only before edits; scripts/ escapes CI mypy; stale
receipts persist until overwritten (check launcher pid first); Colab CLI file-token
expires hourly (Codex knows); /tmp is volatile — preserve artifacts to data/gpu-track/.

Verify, give the owner a concise status, then continue the morning queue; hold bus
sessions on the owner's word.
```

Supersedes `CLAUDE_SESSION_CONTEXT_PROMPT_V2.md`. The memory capstone points here.

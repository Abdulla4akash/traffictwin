# Claude session context prompt — TrafficTwin v0.7 research programme

Paste into a fresh Claude Code session started from `~/AntigravityTest/diss-integration`:

```text
You are continuing as the owner-directed research/integration agent for TrafficTwin v0.7.

FIRST ACTIONS — VERIFY, DO NOT TRUST THIS PROMPT BLINDLY
1. Read your persistent memory file `traffictwin-governance.md` completely (your memory
   directory; MEMORY.md points to it). It carries the full session history including the
   RESUME HERE capstone.
2. Read, in order: AGENTS.md (§v0.7 Work Coordination, Phases 14–28 are yours),
   docs/evaluation/capacity_pilot_results_20260727.md,
   docs/evaluation/capacity_confirmatory_protocol_draft.md,
   docs/integration/manchester_workspace_continuity_20260727.md,
   docs/evaluation/bus_data_experiment_options.md,
   docs/evaluation/bus_fleet_experiment_predeclaration_draft.md,
   docs/evaluation/demand_rebuild_predeclaration.md,
   docs/evaluation/actor_crossover_study_draft.md, CHANGELOG.md (top block).
3. Run git status/fetch; expected: branch claude/complete-v0.7 at 3aee9d4 or later, in sync,
   clean but for gitignored data/. Tags v0.7.0-alpha.1..8 immutable; main = v0.6.0 line.

CURRENT VERIFIED STATE (27 July 2026)
- The predeclared capacity-squeeze pilot COMPLETED PERFECTLY: 12/12 cells admitted, 12.47 h,
  design fingerprint de474e03… matched. RESULT: the predeclared null holds — deadline success
  flat (~79.1%) across a 3.3× capacity squeeze; mean latency collapses monotonically 3.2×
  (9,799→3,084 ms); offloading decisions are bit-identical across capacities (the trained
  policy is capacity-invariant). Committed results:
  docs/evaluation/capacity_pilot_results_20260727.md; full analysis with STA-01 appendices at
  data/vec-fresh/capacity-pilot/campaign_analysis.md; registry
  .demo/registry-capacity-pilot.sqlite.
- The complete instrument exists and is proven: fresh-run scientific admission (ADR-061),
  reviewed inc-trace admission (ADR-062), approval-gated resumable campaigns (ADR-063),
  exploratory analysis harness, cross-actor slope comparison, STA-02 per-algorithm-checkpoint
  extension, analyst review ledger + Match Review page at /match-review (ADR-064), first-run
  guidance on the four entry pages, bus session-identity policy + measured cadence probe
  (median 68 s) + hourly progression + DfT shape comparison.
- Trace provenance (Randy's sidecar, upstream commit 6e56393): traces are the Manchester
  Etihad/Co-op Live EVENT DISTRICT (not city-wide); inc = documented VSL-collapse hour
  (Fri 2024-03-15 20:00–21:00, seed 43); ev = Champions League night (Sandra's stadium
  what-if, audited but not yet runner-admitted); we = zero-event Sunday.

OWNER DECISION QUEUE (present these when the owner engages; never decide alone)
- Confirmatory fork at signing: (a) confirm the null descriptively on held-out seeds {10–14}
  or (b) declare task.latency.mean_ms the confirmatory primary (defensible pre-held-out).
  Then: fill+sign the draft, bind its FINAL digest with held_out_authorised=True, build the
  campaign script, run (~2 arms × 5 seeds × ~63 min).
- R1: tos-data upstream moved by ONE docs-only commit (6e56393 adds traces/PROVENANCE.md;
  data identical). Re-pin = update TOS_DATA_AUDITED_COMMIT + re-audit note. NEVER fetch the
  pinned ../external clones before updating the origin/main==audited-commit checks — a fetch
  bricks fresh admissions.
- N1: Geofabrik mutated its dated GM extract (50.5 MB/38f18e98 vs recorded 996.9 MB/233af3fa);
  original network input not re-derivable; rebuild = new network identity. Gates the demand
  cascade (BETA-D-02→D-03→E-01→E-02), the 305-row match artifact, and B1 trace derivation.
- E1–E5 (demand rebuild), G1–G6 (bus fleet; G6 proposed: slope method), ev-trace admission
  (ADR-062 pattern; occupancy_ev.csv 88a2ff15…, trace 70d6d12f…), three sends (ethics is
  confirm-and-send in the draft; Randy baseline + Study Case 2; CSF).

SAFE NEXT WORK WITHOUT THE OWNER
- services.py split (3,127 lines; facade pattern; land as ONE commit with full UI suite).
- ev-trace measured admission probe (read-only) to prepare the stadium scenario decision.
- Nothing else: all other branches are decision-, human-, or daylight-gated.

HARD BOUNDARIES (unchanged, non-negotiable)
- Never touch main, v0.6.0, any alpha tag, ../external repo STATE, or the untracked
  `supervisor questions2 Gemini/`. Never force-push.
- Labels: owner_approved_candidate / analyst_reviewed_candidate ceilings; never
  scientifically_validated, ground_truth, causal, supervisor-approved. Never fabricate
  evidence, approvals, or provider semantics. Buses are never general traffic. Pilot numbers
  are exploratory forever; held-out seeds untouched without signed authorisation.
- Record ownership in AGENTS.md before editing; keep claims disjoint (lead-claimed Manchester
  source/Operations files and shared surfaces stay untouched). CPU-only JAX (numerical
  equivalence is pinned to it). Attended-only BODS sessions, ≥60 s apart.

GOTCHAS THAT COST TIME BEFORE
- `cd` persists across Bash calls. AppTest breaks on st.rerun() in forms. Strict frozen
  pydantic models refuse python-dict tuples (validate via model_validate_json). Quarantine
  members live under raw/ and are gzip wire bytes (verify sha BEFORE decompress). scripts/
  escapes CI mypy. The full reference-docs generator can exceed 5 min — regenerate single
  contracts surgically. Heavy local compute steals cores from timed campaign cells.

Verify everything above against the repository, give the owner a concise status, then
continue: prepare the ev-trace admission probe and the services split unless the owner
redirects, and surface the decision queue.
```

This file is the successor to the session that ran 26–27 July 2026 (alpha.8 checkpoint through
the completed pilot). It supersedes nothing owned by the lead; `CURRENT_STATUS_CONTEXT_PROMPT.md`
remains the Codex takeover document.

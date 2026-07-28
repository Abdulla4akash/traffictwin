# Claude session context prompt v4 — TrafficTwin, afternoon of 28 July 2026

Supersedes V3. Paste into a fresh Claude session started from
`~/AntigravityTest/diss-integration`:

```text
You are continuing as the owner-directed primary research/integration agent for
TrafficTwin. Read, in order: (1) your memory file traffictwin-governance.md COMPLETELY,
(2) CLAUDE_SESSION_CONTEXT_PROMPT_V3.md (base state through early morning), (3)
docs/experiments_and_findings_20260728.md — the consolidated register of ALL 18
experiments and findings with links, (4) AGENTS.md §v0.7 Work Coordination phases 88–97.
Then git status/pull --ff-only (multiple agents push this branch; verify HEAD before
EVERY edit; never force/rebase). Expected head `3ccb140`+.

DELTAS SINCE V3 (~06:50 → ~12:45)
- ev-deep DONE: binding onset located between cap-0.25 and cap-0.1 (inert at 10×; at 25×
  the collapse-hour signature appears in miniature). Sweep-completion results committed
  (Phase 96). The capacity programme is COMPLETE: blind policy (4 legs) + inert in all
  normal regimes + saturation-governed outcomes + onset located + CONFIRMED −8.3 s
  latency effect on held-out seeds.
- Bus sessions: shallow dawn (52 receipted snapshots, T05–06Z ids) and rush-hour peak
  (~52 snapshots, T07–08Z ids) BOTH captured but BOTH unprocessed — each session was cut
  before its in-session aggregation (task-kill; then a SECOND fail-closed PARSE_REJECTED
  ~09:00 — recurring rush-hour SIRI-VM shape gap in the lead-owned MAN-05 parser;
  rejected bytes preserved; a real data-quality finding). PITFALL: bus_session_report.py
  reads the STORED measurement (still the 27-Jul night probe) — it does NOT process new
  snapshots. TOP TASK: post-hoc measurement via the bods_session_identity library over
  each date-keyed snapshot set (new in-process salt per declared session) → measurement
  JSONs → per-session reports → night/dawn/peak density comparison → B1 FILL-FROM-PROBE
  proposed values → session-record commit (Phase 98) incl. both PARSE_REJECTED findings.
  NO bus experiment has run; B1 stays gated on owner G1–G5 signing.
- Codex: B-MASK completed 10/10 (2×2 masking; zero-infeasible invariant held; archive on
  its side/tmp — preserve to data/gpu-track/ + evidence note if not done). B-DOMAIN
  predeclared (`a08e73f`) and possibly running/complete — check /tmp + git log; preserve
  artifacts (they vanish on reboot). Phase 91 numbering collision (mine + Codex's) noted.
- Consolidated register committed: docs/experiments_and_findings_20260728.md (Phase 97).
  Primary phase numbering continues at 98.

QUEUE (owner-gated items marked *)
1. Process both bus sessions (above) — no attendance needed, data durable.
2. Preserve/record any new Codex artifacts (B-MASK, B-DOMAIN) from volatile /tmp.
3. *Owner sends: ethics (CRITICAL), Sandra+Randy emails (docs/owner_action_pack_20260727.md,
   XAI-free), CSF request. Sandra meeting outcome may set new scope — obey it.
4. Codex integration handoff: CODEX_INTEGRATION_HANDOFF.md ready; owner triggers review +
   fast-forward of codex/traffictwin-v0.7 (push sha:refs; main untouched).
5. *Signings: B1 G1–G5, crossover + stadium candidates, E1–E5 demand, N1/R1 re-pins.
6. Week-4→5 progress update; cross-regime dissertation figure; parser-gap diagnosis slice
   (lead-owned MAN-05 — coordinate with Codex).

STANDING RULES (unchanged, absolute): delegation = "take reasonable choices and keep
working" with honest recorded provenance; owner decisions presented never taken; XAI
framing dropped; label ceilings owner_approved_candidate; held-out {10–14} spent;
byte-frozen candidate (b); never fetch ../external clones; attended-only BODS (launch
acquisitions DETACHED so task-kills can't kill them); detached pattern for >1 h jobs;
fingerprint byte-exactness after ANY shared design-code edit (bitten twice); /tmp is
volatile — preserve artifacts; registries/data read-only; buses never general traffic.

Verify, give a concise status, then work the queue.
```

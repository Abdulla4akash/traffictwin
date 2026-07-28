# Claude session context prompt v5 — TrafficTwin, evening of 28 July 2026

Supersedes V4. Paste into a fresh Claude session started from
`~/AntigravityTest/diss-integration`:

```text
You are continuing as the owner-directed primary research/integration agent for
TrafficTwin. Read in order: (1) memory file traffictwin-governance.md COMPLETELY,
(2) docs/experiments_and_findings_20260728.md — the consolidated register of every
experiment with links, (3) AGENTS.md §v0.7 Work Coordination, scanning the highest phase
numbers first. V3/V4 are historical; this file carries the current state. Then
git status/pull --ff-only. Multiple agents push this branch: re-verify HEAD before EVERY
edit, never force or rebase. Expected head `372df2e` or later.

STANDING DELEGATION: "take reasonable choices and keep working" — ship autonomously with
honest recorded provenance; present owner decisions, never take them. XAI framing is
DROPPED. Full research-directions-v2 scope by 4 September. Label ceiling
owner_approved_candidate everywhere.

THE SCIENCE IS COMPLETE AND CLOSED FOR THE CAPACITY PROGRAMME
- CONFIRMED (signed protocol, held-out seeds {10-14}, now spent): squeezing per-vehicle
  RSU capacity 2.5->0.75 reduces mean task latency by 8,310.9 ms [-9,097.5, -7,524.3],
  all five seeds in the predeclared direction; deadline attainment flat.
- MECHANISM, now measured end to end and on five independent legs:
  (a) observation-space gap — no RSU-load term reaches the policy;
  (b) keyed actions bit-identical (0 mismatches / 8.9M cells x 9 pairs);
  (c) a from-scratch 17-D GPU control is equally invariant;
  (d) B0: the second audited actor is equally invariant;
  (e) LATENCY TAIL (Phase 110): p50 is 44.3 ms at EVERY capacity (-0.10% over the 3.3x
      squeeze), the >1 s population moves only -0.07 pp, but p99 falls 69.9% and
      97.9-99.4% of latency mass is tail. The squeeze moves latency ONLY within the
      already-deadline-failed population — which is exactly why the -8.3 s mean effect
      coexists with flat deadlines. NOTE FOR FUTURE PROTOCOLS: mean latency is ~99% tail
      mass; predeclare a percentile or tail-share endpoint beside it.
- FIVE-REGIME SWEEP unanimous: capacity inert in all four normal traces (139-215 slots),
  active only in the 2,488-slot collapse hour; deep-squeeze onset located between
  cap-0.25 and cap-0.1. All five Gate-A traces admitted (ADR-062/065/066).
- RSU ASYMMETRY (Phase 111): 3 of 10 RSUs carry EXACTLY zero load at every capacity, a
  fourth under 5%, busiest ~24%; Gini 0.486->0.467 so the squeeze does not redistribute.
  Placement, not capacity, is the binding infrastructure problem. Study Case 1 answered.

N1 IS WITHDRAWN — DO NOT REPEAT THE OLD CLAIM (Phase 105)
Geofabrik never mutated anything. The "lost" 996,913,352 B / 233af3fa identity was the
DECODED XML's identity written into an evidence record's SOURCE fields. The on-disk pbf is
50,502,348 B / md5 c73b16ec, matching the provider's published md5 and the FIRST
acquisition record exactly. **No dissertation output may claim a provider mutated a dated
file.** The real finding is ours: a derived artifact's identity was recorded as its
source's, and a checksum mismatch was rationalised instead of failing closed.

NETWORK IS REBUILT AND DURABLE (Phase 108)
`data/network-build/gm-baseline-20260728/` — canonical identity
`ce285f85d07fee24414cc3318cf85ea1ca0cb967e2eadb2ac7bcb3f96bde2577` REPRODUCES the 25-July
record exactly (raw bytes differ by 2 = netconvert's generation banner, by design).
Rebuild via `scripts/rebuild_baseline_network.py`. N1 no longer gates anything.
TWO DECODE DEFECTS in lead-owned network_decode.py, recorded not fixed: (1) it runs osmium
with cwd=staging so RELATIVE source paths cannot resolve — pass absolute; (2) after a
SUCCESSFUL decode its receipt handling raises "TypeError: Object of type date is not JSON
serializable" and reports DECODE_FAILED while leaving a byte-correct artifact — reuse the
artifact on a second pass. Guards preventing recurrence: Phase 106
`artifact_integrity.py` (source/derived collision + ephemeral-path refusals, 7 tests).

BUS TRACK — CODEX OWNS IT, DO NOT COLLIDE
Three attended sessions captured and processed (night 41 active / dawn 1,162 / peak 1,433;
cadence stable 66-68 s; displacement 418->231 m as density rises). Peak CONCURRENCY
measured at 1,216 max / 1,192 median, placing the observed fleet INSIDE the capacity
sweep's unresolved band (215, 2488]. Identity policy corrected to v1.1 (operator-scoped)
after cross-operator collisions manufactured 18.7 km/s vehicles. Two rush-hour
PARSE_REJECTED refusals diagnosed to the same cross-operator scope gap in lead-owned
MAN-05. Codex is building B-BUS in two arms (bounded corridor + whole fleet) on Colab.
FLAG: its prep produced traces WITHOUT map matching although the B1 draft predeclares
interpolation along matched road paths — a deviation worth recording explicitly.

QUEUE, IN ORDER (none of 1-2 needs an owner decision)
1. Complete the restored chain: clip the study subnetwork (~33 s), rebuild the edge index,
   regenerate the 305-row v1.1 match artifact. This restores the Match Review page's real
   data and unblocks the demand cascade. All unblocked by the rebuilt network.
2. Demand diagnosis (predeclaration §2: route-length, free-flow residence, counted-edge
   multiplicity, fringe share). The predeclaration says these publish regardless of
   outcome, so they run before E1-E5 signing. Library exists (Phase 41).
3. *Owner: ethics send (critical), Sandra/Randy/CSF emails
   (docs/owner_action_pack_20260727.md section A), B1 G1-G5, crossover + stadium
   candidates, E1-E5, R1 re-pin.
4. *Owner: trigger Codex review + fast-forward via CODEX_INTEGRATION_HANDOFF.md.
5. Crossover study — the last major predeclared experiment; needs signing and ~20 h.

BOUNDARIES (absolute): never fetch ../external clones; byte-frozen
capacity_confirmatory_candidate_b_latency_primary.md; held-out {10-14} spent; registries
and data/vec-fresh read-only; attended-only BODS launched DETACHED; detached pattern
(start_new_session + caffeinate + pid file) for anything over an hour; verify design
fingerprints byte-exactly after ANY shared-design edit (bitten twice); /tmp is volatile —
preserve artifacts to data/; buses never general traffic; never fabricate approvals.

Verify, give a concise status, then work the queue.
```

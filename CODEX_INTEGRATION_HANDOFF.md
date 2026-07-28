# Codex integration handoff — review and fast-forward (28 July 2026)

For Codex as lead/integrator: review the accumulated work and advance the official
branch. One instruction from the owner suffices: "read CODEX_INTEGRATION_HANDOFF.md,
review the range, fast-forward the official branch, touch nothing else."

## The range

- Official branch `codex/traffictwin-v0.7` last stood at `7a4a16c` (alpha.7 era; tag
  `v0.7.0-alpha.8` = `6b238e4` line is already on it if previously advanced — verify).
- Everything since lives on `claude/complete-v0.7` (HEAD at or beyond `14db4ac`), as
  additive commits only — no history rewrites at any point. The correct integration is a
  **fast-forward**, exactly like the alpha.6 checkpoint. If this branch is checked out in
  the owner's worktree, push from here instead of switching:
  `git push origin <reviewed-sha>:refs/heads/codex/traffictwin-v0.7`.
- **`main` stays untouched** (v0.6.0 release line until REL-01). All `v0.7.0-alpha.*`
  tags are immutable.

## What the range contains (review map)

AGENTS.md §"v0.7 Work Coordination" is the authoritative claim ledger:

- **Phases 14–39 + 80–90 (primary session):** the experiment instrument (ADR-061..065),
  the capacity programme end to end — pilot (12 cells), signed held-out confirmatory
  (10 cells; the −8,310.9 ms latency confirmation), three-trace grid (24 cells), keyed
  action and observability-gap probes, ev timing probe, the B0 baseline-invariance
  campaign (in flight), all results records under docs/evaluation/, the repeat-admission
  resume repair (`bb6992f`, with regression tests), the services.py package split, the
  bus session-identity/cadence/B2 track, and the documentation/handoff apparatus.
- **Phases 40–71 (parallel feature batches 1–6):** RSU Monitor, demand-diagnosis
  library, mechanism report + CLI + exhibit, stadium/crossover skeletons, appendix and
  figure/table generators, bus trajectory library + VEC-06 bridge, confirmatory-mode
  renderer, campaigns browser, CSF job-pack + CLI, gate battery, participant documents,
  diagrams, narration script, the tos-reader fork-segfault fix.
- **Phase 82 + gpu/ (Codex's own GPU track):** already familiar; the B-CAP
  predeclaration and G4 harness are in-range.

## Gate evidence at the tree

Most recent full verification (primary session, tree of 28 July): repository ruff clean,
strict mypy 797+ files, tests/unit 2,765+ and tests/ui 476+ green (counts grew with the
batches; `scripts/run_all_gates.py` reruns everything in one command). CI-equivalent
gates were run per slice throughout; receipts in the claim records.

## Hazards — absolute, regardless of review outcome

1. **Never `git fetch`/`pull` inside `../external/tos-data` or `../external/vec_env`** —
   fresh admission verifies origin/main == audited commit; a fetch bricks admissions.
   Probe upstreams with `ls-remote` only. (R1 re-pin is a queued owner decision.)
2. **Byte-frozen:** `docs/evaluation/capacity_confirmatory_candidate_b_latency_primary.md`
   (digest-bound into the completed held-out campaign's approval). Never reformat it.
3. `.demo/registry-*.sqlite` and `data/vec-fresh/**` are admitted evidence — read-only.
   A B0 campaign may still be executing (check
   `data/vec-fresh/baseline-invariance-ev/launcher.pid`); never kill or relaunch
   campaign processes.
4. Held-out seeds {10–14} are spent. Label ceilings and forbidden labels unchanged.
5. The attended-only BODS boundary is untouched; no acquisition runs from review.

## Open decision queue (owner's, unchanged by integration)

Confirmatory-signed programme extensions (crossover/stadium candidates await owner
signing), R1/N1 re-pins, E1–E5 demand signing, G1–G5 bus signing (peak session pending),
ethics/CSF/producer-email sends, and the producer's written code/data permissions.

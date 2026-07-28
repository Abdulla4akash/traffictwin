# Codex integration handoff — review and fast-forward (28 July 2026)

For Codex as lead/integrator: review the accumulated work and advance the official
branch. One instruction from the owner suffices: "read CODEX_INTEGRATION_HANDOFF.md,
review the range, fast-forward the official branch, touch nothing else."

## Current fast-forward range

- On 28 July at the Phase-102 claim, official branch `codex/traffictwin-v0.7` was
  `1dbc748fd7f08de8d8369d167d6025fd0d68e0ee` and candidate branch
  `claude/complete-v0.7` was `a87e082a0e6e28fc70134fe8d426421f28de548e` (131 additive
  commits). `git merge-base --is-ancestor` passed. Re-read both refs before review because
  this shared candidate branch may have advanced.
- The correct integration remains a **fast-forward**. If the official branch is checked out
  in the owner's worktree, push from this integration worktree instead of switching:
  `git push origin <reviewed-sha>:refs/heads/codex/traffictwin-v0.7`.
- **`main` stays untouched** (v0.6.0 release line until REL-01). All `v0.7.0-alpha.*`
  tags are immutable.

## What the range contains (review map)

AGENTS.md §"v0.7 Work Coordination" is the authoritative claim ledger:

- **Primary research arc:** the experiment instrument (ADR-061..066), capacity pilot,
  signed held-out confirmation (−8,310.9 ms), five-regime completion, deep-squeeze onset,
  B0 baseline prediction test, keyed-action and observation-gap probes, results records,
  tables, and the hash-bound cross-regime dissertation figure.
- **Phases 40–71 (parallel feature batches 1–6):** RSU Monitor, demand-diagnosis
  library, mechanism report + CLI + exhibit, stadium/crossover skeletons, appendix and
  figure/table generators, bus trajectory library + VEC-06 bridge, confirmatory-mode
  renderer, campaigns browser, CSF job-pack + CLI, gate battery, participant documents,
  diagrams, narration script, the tos-reader fork-segfault fix.
- **GPU track:** B-CAP, B-REWARD, B-MASK, B-BUS/IPPO engineering smokes, and B-DOMAIN
  harnesses plus full-campaign records. B-MASK and B-DOMAIN exact archives are preserved
  in gitignored `data/gpu-track/` with committed provenance records. They remain private,
  non-admitted diagnostics; B-DOMAIN is not literal trace B4.
- **Bus track:** night/dawn/peak post-hoc aggregates, operator-scoped session identity v1.1,
  the three-session B1 proposal record, and exact diagnosis of both preserved MAN-05
  rush-hour refusals. No bus experiment ran and the accepted MAN-05 parser is unchanged.
- **Governance/handoff:** consolidated 18-entry experiment register, owner action drafts,
  Week-4→5 checkpoint, session prompts, and claim records through Phase 102+.

## Gate evidence at the tree

Use the per-slice gates in AGENTS.md rather than the older clean-tree count. Most recently:
the bus slice has 49 focused tests with focused Ruff/mypy clean and 3/3 exact artifact-hash
checks; the cross-regime figure has six focused tests with focused Ruff/format/mypy clean,
valid SVG XML, visual inspection, and exact source-value checks. The latest broad unit run
after mechanically regenerating the ADR-066 appendix is green: **2,923 passed in 128.16 s**.
Repository-wide Ruff and mypy still expose recorded pre-existing findings outside these
slices. Review those honestly and do not restate the range as globally clean without fresh
lint/type gates.

## Hazards — absolute, regardless of review outcome

1. **Never `git fetch`/`pull` inside `../external/tos-data` or `../external/vec_env`** —
   fresh admission verifies origin/main == audited commit; a fetch bricks admissions.
   Probe upstreams with `ls-remote` only. (R1 re-pin is a queued owner decision.)
2. **Byte-frozen:** `docs/evaluation/capacity_confirmatory_candidate_b_latency_primary.md`
   (digest-bound into the completed held-out campaign's approval). Never reformat it.
3. `.demo/registry-*.sqlite` and `data/vec-fresh/**` are admitted evidence — read-only.
   The completed campaigns must not be resumed, relaunched, mutated, or re-analysed under
   changed design bytes.
4. Held-out seeds {10–14} are spent. Label ceilings and forbidden labels unchanged.
5. The attended-only BODS boundary is untouched; no acquisition runs from review.

## Open decision queue (owner's, unchanged by integration)

Ethics/Sandra/Randy/CSF sends; Sandra's two scope answers; B1 G1–G5 (including the
speed-outlier rule); completion and signing/declining of crossover and stadium candidates;
R1/N1 re-pins; E1–E5 demand signing; and producer code/data/publication permissions.
The peak session is complete and processed. These decisions remain owner/external actions;
review and fast-forward do not take any of them.

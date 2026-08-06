# Codex integration handoff — 6 August 2026

The complete current handoff is
[`CLAUDE_SESSION_CONTEXT_PROMPT_V9.md`](CLAUDE_SESSION_CONTEXT_PROMPT_V9.md). Read it and
`AGENTS.md` before integrating anything. This file records the narrower Git integration posture.

## Current topology at the recorded snapshot

- `main` / `origin/main`:
  `49be6a2db8a69409a1b92fb02e954db7cf1441f6` (`release TrafficTwin v0.7.0 on main`).
- `claude/complete-v0.7` / remote:
  `c3e2dc868bbe6cc3dff21f7433984bb28b74df80` (Phase 198).
- `housekeeping/v0.7-completion` / remote:
  `e3871c6c73106a5ca1178cb3ef58d504780ad027`, open draft PR #1 to `main`.
- Annotated `v0.7.0` target:
  `e840be6c09ac4579e3604665110db2e3209fc7dd`, on the housekeeping history rather than
  the current `main` tip. Never move it without explicit owner authority.
- `agent/current-status-5-6-pro-analysis`: open draft PR #2 to `main`. Its first commit is
  `9036b6ed36577aa44fe18dc03ef4c8bf4b6357a7`.

Verify all mutable refs rather than copying these values blindly. Do not revive the old instruction
to fast-forward `codex/traffictwin-v0.7`; the release topology has moved on.

## PR #2 scope

PR #2 is documentation-only: the 5.6 Pro capacity-interpretation analysis, its docs-index entry and
the current context handoff. Do not add evaluator, scheduler, training or experiment code to it.
Its GitHub Actions jobs currently fail before executing steps because of an account billing or
spending-limit block. Record that external blocker accurately; it is not a code-test verdict.

## Integration boundaries

- Review and stage explicit paths only. Preserve unrelated user or agent work.
- Do not force-push, move tags, reset worktrees or infer that PR #1 should merge.
- Never fetch or pull inside the two pinned external Randy repositories.
- Do not mutate `.demo/`, `data/vec-fresh/`, private GPU archives, quarantine data or approval
  artifacts during integration.
- Never edit the byte-bound confirmatory candidate.
- Keep the 5.6 report's external-analysis status and subjective-score caveat intact.
- Any implementation of task lifecycle accounting or load balancing starts on a separate claimed
  branch after owner direction and a reviewed semantic contract.

## Review handback

Report the reviewed commit range, exact files, local checks, CI status, branch/tag discrepancies,
scientific label impact (normally none for documentation), and every owner decision still needed.

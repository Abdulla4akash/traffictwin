# Codex integration handoff — 7 August 2026

The complete current handoff is
[`CLAUDE_SESSION_CONTEXT_PROMPT_V10.md`](CLAUDE_SESSION_CONTEXT_PROMPT_V10.md). Read it and
`AGENTS.md` before integrating anything. This file records the narrower Git integration posture.

## Verified topology before the V10 documentation commit

- Local `main`: `49be6a2db8a69409a1b92fb02e954db7cf1441f6`.
- `origin/main`: `a462c72b81f1668eef4ea0b7f8e806be4d208b47`.
- `claude/complete-v0.7` local/remote:
  `c3e2dc868bbe6cc3dff21f7433984bb28b74df80`.
- Annotated `v0.7.0^{}`: `e840be6c09ac4579e3604665110db2e3209fc7dd`.
- Draft PR #1: `housekeeping/v0.7-completion` at
  `e3871c6c73106a5ca1178cb3ef58d504780ad027` to `main`.
- Draft PR #2: `agent/current-status-5-6-pro-analysis` at pre-update tip
  `a7c3a34055f5777e95e8efb93d84e8242c2d5a95` to `main`.

Resolve the V10 commit and every remote ref live. Do not fast-forward local `main`, move a tag,
merge either PR or reconcile the release topology without explicit owner direction.

## Separate implementation chain

The pushed implementation line is five sequential commits ahead of `origin/main`:

1. `agent/vec-task-lifecycle-v1` — `b7bc0cca870f3eaa3fd9a0d49e04b8fd951ff114`;
2. `agent/vec-two-rsu-handcheck-v1` — `ec256baef7682bae9bf3e9eec1c62bcc5d07a8fd`;
3. `agent/vec-deterministic-dispatch-v1` — `3b13856134fc6afece5fa6fd1d7e7c5876ace096`;
4. `agent/vec-native-runner-sidecar-v1` — `9fa1c379035f183784b714fcefe80311c0b8d408`;
5. `agent/vec-matched-dispatch-study-v1` — `3813431f7366c833924fcc79d50268be2179e974`.

The final tip passed the recorded local unit, Ruff and strict-mypy checks in V10 §2. The line is
not merged and has no native evaluator result. Integrating it requires an explicit owner choice,
review of the full five-commit range, and preservation of each provisional/synthetic evidence
label.

## PR #2 scope and CI

PR #2 is documentation-only. Do not add evaluator, scheduler, training, campaign or integration
code to it. Before the V10 commit its GitHub Actions jobs had no runner or steps; the recorded
annotation identified failed account payments or a spending-limit issue. This is an external
CI-start blocker, not a code-test verdict. Inspect any new V10 checks live and do not repeatedly
rerun them while billing remains unresolved.

## Integration boundaries

- Review and stage explicit paths only. Preserve unrelated user or agent work.
- Do not force-push, move/create tags, reset worktrees or infer that PR #1 should merge.
- Never fetch, pull or modify either pinned external repository.
- Do not mutate `.demo/`, `data/vec-fresh/`, private GPU archives, quarantine data, approvals,
  registries or the digest-bound confirmatory candidate.
- Do not expose private data, source identities, raw traces, checkpoints, credentials or machine
  paths.
- The implementation chain is synthetic/provisional until a reviewed native producer emits the
  lifecycle/state contract. Do not translate passing software tests into scientific evidence.
- Keep the admission/in-flight-ceiling correction and the distinction between modelled deadline
  attainment and physical completion intact.

## Review handback

Report the reviewed commit range, exact files, local checks, live CI state, branch/tag
discrepancies, scientific-label impact and every semantic, integration or owner decision still
needed.

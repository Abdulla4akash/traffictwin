# PR #17 Phase-B Rebase Packet — Challenge Seeds → What-If Studio

**Durable branch:** `rehearsal/pr17-phase-b-v1` (local and `origin/rehearsal/pr17-phase-b-v1` after push, based on `rehearsal-pr17-final-on-2d7e85f` at `884618e`)
**Created:** 2026-08-09, on current PR #13 head `2d7e85f5641c1836a0e8892d2e256c55b1e3bc6a` (still OPEN DRAFT, base main)
**Official PR #17 head (frozen):** `bb30fd49640084c9a0878afc3191e6e368c5edd0` on `agent/product-challenge-whatif-bridge-v2` (base now `main` after retarget, previously `agent/product-portfolio-explorer-v2`)
**Purpose:** Exact replay after PR #13 merges to `main`; no PR #16/PR #14 merge required. PR #17 has already been retargeted to `main` while head remains `bb30fd4` to prevent auto-close on PR #13 branch deletion.

## 1. Verified live state at packet creation

- `git rev-parse agent/product-challenge-whatif-bridge-v2` = `bb30fd4` (local)
- `git rev-parse origin/agent/product-challenge-whatif-bridge-v2` = `bb30fd4`
- `gh pr view 17 --json headRefOid` = `bb30fd4`, `isDraft=true`, `state=OPEN`, `baseRefName=main` (retargeted from `agent/product-portfolio-explorer-v2` to prevent auto-close; head unchanged)
- `gh pr view 13 --json headRefOid` = `2d7e85f`, `baseRefName=main`, `isDraft=true`, `state=OPEN`, `mergeable=MERGEABLE`
- `git branch --contains a6cb1bb02e2608b359dc4da03d601fdb231e4ee0` = `rehearsal-ux-keep` only (original `a6cb1bb` object not reachable from `rehearsal/pr17-phase-b-v1` except via cherry-picks `9b59b6a` which is a **different commit object** with same patch but different parent; `git cat-file -t a6cb1bb` = `commit`, `git cherry-pick a6cb1bb` creates new object `9b59b6a`).
- E1 dynamic still active (`pgrep eval_sumo_stage1_mc.py` = PID 87396), so all tests run serially without `-n`.

## 2. Patch-ID equivalence (original → replay)

Original PR #17 commits (3) on `agent/product-challenge-whatif-bridge-v2`:

- `7aae39ba5a46ead8429fdf020a13ced55acf4eb6` → `191c83f9d09ee4151d50b9d22a647fc0c7fb212a`
- `f14880501cf7ac203a61fa7a82843f26548672d2` → `d66f099ddc0ad8243c695a76f1e87437e5ef88be`
- `bb30fd49640084c9a0878afc3191e6e368c5edd0` → `4407059e4ee7a75e6d23d37580bc36008f4fdd94`

Replay commits on `rehearsal-pr17-final-on-2d7e85f` / `rehearsal/pr17-phase-b-packet-v1` (identical patches, `git patch-id --stable` matches):

- `13d6ebd` product: bridge challenge seeds into what-if studio → `191c83f9d09ee4151d50b9d22a647fc0c7fb212a`
- `b213f14` fix(pr17): address review — keyed prefill, generation-bound receipt, range validation → `d66f099ddc0ad8243c695a76f1e87437e5ef88be`
- `f0db845` fix(pr17): full-control cross-draft reset, no value=, full mypy → `4407059e4ee7a75e6d23d37580bc36008f4fdd94`

UX / test hardening commits appended (not in original, patch IDs separate):

- `9b59b6a` rehearsal(ux): truthful wording for reset and unmapped defaults + CH-07 incident truth → `2d196ee3e45be1775b61d16c9403234dbec6a279` (cherry-pick of `a6cb1bb`; same patch, different object)
- `9a05fb6` rehearsal(harden): exact UX captions and binding CH-07 provenance assertions → `2bb0268517199d524feb828f6fb9a5060f8617ba` (cherry-pick of `f31a34e`)
- `459677f` fix(tests): harden ledger distinction and old-receipt provenance assertions → `6248a2f110ed2696673394bd7c3d14b8bead9ed4`
- `884618e` fix(tests): bind exact ledger info and harden old-receipt provenance → `new` (current fix: ledger `st.info` exact, old-receipt dead OR removed)

Do not rewrite already-proven replay commits; new commits only extend.

## 3. Exact file scope vs PR #13 head `2d7e85f`

```
git diff 2d7e85f..884618e --stat
 src/traffictwin/ui/challenge_whatif_bridge.py  | 626 +++++++++++++++++
 src/traffictwin/ui/pages/portfolio_explorer.py |  97 +++
 src/traffictwin/ui/pages/whatif_studio.py      | 396 +++++++++-
 src/traffictwin/ui/state.py                    |   4 +
 src/traffictwin/ui/whatif_controls.py          | 131 ++++
 tests/integration/test_challenge_whatif_e2e.py | 154 ++++
 tests/ui/test_challenge_whatif_bridge_ui.py    | 936 +++++++++++++++++++++++++
 tests/unit/test_challenge_whatif_bridge.py     | 413 +++++++++++
 8 files changed, 2726 insertions(+), 31 deletions(-)
```

`--numstat` (`2d7e85f..884618e`):

- `626 0 src/traffictwin/ui/challenge_whatif_bridge.py`
- `97 0 src/traffictwin/ui/pages/portfolio_explorer.py`
- `365 31 src/traffictwin/ui/pages/whatif_studio.py`
- `4 0 src/traffictwin/ui/state.py`
- `131 0 src/traffictwin/ui/whatif_controls.py`
- `154 0 tests/integration/test_challenge_whatif_e2e.py`
- `936 0 tests/ui/test_challenge_whatif_bridge_ui.py`
- `413 0 tests/unit/test_challenge_whatif_bridge.py`

Earlier `2d7e85f..459677f` was `2718 / 31` (928 UI); after `884618e` ledger fix adds 8 lines → `2726 / 31` (936 UI). No other files changed.

Zero-page proof (no new page / navigation edits):

- `ls src/traffictwin/ui/pages/*.py | wc -l` = `55` before and after
- `ls src/traffictwin/ui/app_pages/*.py | wc -l` = `53` before and after
- No diff in `src/traffictwin/ui/labels.py`, `navigation.py`, `navigation_v07.py`, `page_runtime.py` (`git diff 2d7e85f..884618e --name-only` shows only 8 files above).

## 4. Conflict expectations

- `src/traffictwin/ui/pages/portfolio_explorer.py`: expected 0 or trivial additive (bridge section after `default_synthetic_portfolio_rules` import and `What-If Bridge` container). Rehearsal rebase onto `2d7e85f` succeeded with `EXIT 0` on all three picks; no manual resolution.
- `src/traffictwin/ui/pages/whatif_studio.py`: no conflict (PR #13 does not touch What-If Studio).
- Overall `git cherry-pick 7aae39b f148805 bb30fd4` = 0 conflicts; UX picks `9b59b6a 9a05fb6 459677f 884618e` = 0 conflicts on rehearsal base.
- After PR #13 merges, cherry-picks remain clean because `2d7e85f` will be in `main`.

Avoid brittle line numbers: reset button is `st.button("Reset to stock defaults", key="whatif_clear_challenge_prefill")` in the challenge-source panel of `whatif_studio.py`; ledger distinction is `st.info("Challenge source fields above are separate from the actual What-If changed-parameter ledger below. Only the ledger determines what will be generated.")` shown when `challenge_draft is not None and can_generate`; disclosures are `st.caption("Unmapped controls keep ordinary What-If Studio defaults.")` and `st.caption("The actual generated ledger is authoritative.")`.

## 5. Exact official Phase-B rebase procedure after PR #13 merges (merge-style-agnostic, fail-closed, draft-guarded)

**Current reality (already retargeted):** PR #17 has already been retargeted to `main` while head remains `bb30fd4` (see §1). This prevents auto-close when `agent/product-portfolio-explorer-v2` is deleted. The temporary diff on GitHub is not the final Phase-B diff and must not be reviewed/merged. Future procedure begins with verification of this retargeted state. DRAFT status is the active safety guard — do not mark READY until Phase-B replay + final Claude 4 exact-head review (see Draft invariant below).

**Trigger — two gates, both required (see also CI and readiness sections):** PR #13 `mergedAt != null` (GitHub) AND live `origin/main` satisfies PR #13 product contract via `tools/check_pr17_phase_b_ready.py` → `READY_FOR_PHASE_B`. Do not use `git merge-base --is-ancestor 2d7e85f origin/main` as required gate (informational only — fails for squash/rebase).

Do NOT touch official PR #17 until both gates are READY, even though its base is already `main`.

**Draft invariant (formal):** At start and end, PR #17 must satisfy `state==OPEN && isDraft==true && baseRefName==main && headRefOid==bb30fd4` (or new SHA after Phase-B). If ever observed READY before final review, immediately convert back to DRAFT via `gh pr edit 17 --add-label`/`gh pr ready` inversion (`gh pr edit 17 --repo Abdulla4akash/traffictwin` → `gh api` to convert to draft) — do not interpret `MERGEABLE` as authorization. PR body top banner must say **DRAFT STATUS IS AN ACTIVE SAFETY GUARD — DO NOT MARK READY UNTIL PHASE-B REPLAY + FINAL CLAUDE 4 EXACT-HEAD REVIEW.**

Procedure (mechanical, 12 steps — starts with verification, then safety ref, then destructive ops):

```bash
# 1. git fetch origin --prune
git fetch origin --prune
# 2. Verify PR #17: OPEN, DRAFT, base main, head bb30fd4 (retarget already done)
gh pr view 17 --repo Abdulla4akash/traffictwin --json state,isDraft,baseRefName,headRefName,headRefOid,mergedAt
# must be: state=OPEN, isDraft=true, baseRefName=main, headRefOid=bb30fd49640084c9a0878afc3191e6e368c5edd0
git rev-parse agent/product-challenge-whatif-bridge-v2  # must be bb30fd4
git rev-parse origin/agent/product-challenge-whatif-bridge-v2  # must be bb30fd4
# If DRAFT is false, restore DRAFT via metadata only before continuing:
# gh pr edit 17 --repo Abdulla4akash/traffictwin --add-label  (or gh api -X PUT .../pulls/17 --field draft=true)
# 3. Verify safety tag exists locally/remotely BEFORE any destructive command
git rev-parse pr17-pre-phase-b-bb30fd4^{commit}  # must be bb30fd4
git ls-remote --tags origin refs/tags/pr17-pre-phase-b-bb30fd4  # must show 0d1f0fe... bb30fd4
# 4. Verify PR #13: mergedAt != null (Gate A)
gh pr view 13 --repo Abdulla4akash/traffictwin --json state,mergedAt,headRefOid,mergeCommit,baseRefName
# must be: mergedAt != null (ISO timestamp)
# 5. Run merge-style-agnostic PR13 content/readiness check against fetched origin/main (Gate B) — FAIL-CLOSED
# Both --main-path AND --expected-main-sha are REQUIRED (no cwd default); mismatch fails closed.
MERGED_AT="$(gh pr view 13 --repo Abdulla4akash/traffictwin --json mergedAt --jq .mergedAt)"
FETCHED_MAIN_SHA="$(git rev-parse origin/main)"
# Create throwaway worktree at exact fetched SHA (do not reuse rehearsal checkout)
rm -rf /tmp/pr17-main-check && mkdir -p /tmp/pr17-main-check
git worktree add --detach /tmp/pr17-main-check "$FETCHED_MAIN_SHA"
.venv/bin/python tools/check_pr17_phase_b_ready.py --main-path /tmp/pr17-main-check --expected-main-sha "$FETCHED_MAIN_SHA" --pr13-merged-at "$MERGED_AT"
# Require READY_FOR_PHASE_B (exit 0). Exit codes: 0 READY, 1 BLOCKED_PR13_OPEN, 2 BLOCKED_CONTENT_MISMATCH, 3 GITHUB_QUERY_ERROR, 4 MAIN_PATH_REVISION_MISMATCH → stop.
git worktree remove --force /tmp/pr17-main-check
# 6. Require READY_FOR_PHASE_B (both gates). If BLOCKED, stop and investigate.
# 7. Record hosted CI status: healthy OR CI_INFRASTRUCTURE_BLOCKED
gh run list --repo Abdulla4akash/traffictwin --limit 5
gh run view <RUN_ID> --repo Abdulla4akash/traffictwin  # check "The job was not started because recent account payments..."
# Classification: CI_INFRASTRUCTURE_BLOCKED is not product regression. Do not edit .github/workflows/**.
# 8. If owner authorizes Phase B: create temporary Phase-B branch from live origin/main, replay reviewed 7-commit packet
git checkout -b tmp-phase-b origin/main
# Verify patch range still 3 commits from pre-Phase-B head
git log --oneline 2d7e85f..bb30fd4 --reverse  # 7aae39b, f148805, bb30fd4
# Replay PR #17 core (identical patches — preserves reviewed product patch)
git cherry-pick 7aae39ba5a46ead8429fdf020a13ced55acf4eb6  # 7aae39b → 191c83f
git cherry-pick f14880501cf7ac203a61fa7a82843f26548672d2  # f148805 → d66f099
git cherry-pick bb30fd49640084c9a0878afc3191e6e368c5edd0  # bb30fd4 → 4407059
# Replay UX/test hardening from canonical packet branch
git cherry-pick 9b59b6a  # a6cb1bb equivalent → 2d196ee
git cherry-pick 9a05fb6  # f31a34e equivalent → 2bb02685
git cherry-pick 459677f  # → 6248a2f
git cherry-pick 884618e  # → 095d30b
# Verify patch IDs for the original reviewed bridge commits
git patch-id --stable < <(git show 7aae39b)  # must equal replay
git patch-id --stable < <(git show <replay>)  # see synthetic proof table
# 9. Verify, then run focused/full local validation + project gates
git diff origin/main..HEAD --stat  # 8 files, 2726/31
git diff origin/main..HEAD --name-only  # no navigation files
ls src/traffictwin/ui/pages/*.py | wc -l  # 55
ls src/traffictwin/ui/app_pages/*.py | wc -l  # 53
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync mypy
uv lock --check
git diff --check
uv run --no-sync python -m pytest tests/unit/test_challenge_whatif_bridge.py tests/ui/test_challenge_whatif_bridge_ui.py tests/integration/test_challenge_whatif_e2e.py tests/ui/test_whatif_studio.py tests/unit/test_whatif_pair.py -q  # 79
# 10. Force-with-lease official PR17 head against expected old SHA bb30fd4 (precondition)
REMOTE_BEFORE=$(git rev-parse origin/agent/product-challenge-whatif-bridge-v2)
# Require REMOTE_BEFORE == bb30fd49640084c9a0878afc3191e6e368c5edd0
# Then:
git checkout agent/product-challenge-whatif-bridge-v2
git reset --hard tmp-phase-b
git push --force-with-lease=refs/heads/agent/product-challenge-whatif-bridge-v2:bb30fd49640084c9a0878afc3191e6e368c5edd0 origin <NEW_PHASE_B_SHA>:refs/heads/agent/product-challenge-whatif-bridge-v2
# This prevents overwriting unexpected concurrent work.
# 11. Verify PR remains base main and DRAFT after force-push
gh pr view 17 --repo Abdulla4akash/traffictwin --json state,isDraft,baseRefName,headRefOid
# must be: OPEN, DRAFT true, base main, head = new Phase-B SHA
# If READY, convert back to DRAFT before requesting final review.
# 12. Request Claude 4 final exact-head review. Only after final review may owner consider mark-ready/merge.
# If hosted CI remains billing-blocked: retain CI_INFRASTRUCTURE_BLOCKED, do not edit workflows, rerun CI once owner restores billing.
git branch -D tmp-phase-b
```

If `git cherry-pick` reports 0 conflicts, proceed; if conflict, resolve by accepting both sides (additive bridge sections), then `git cherry-pick --continue`. Do not improvise outside this packet — any deviation is a packet defect.

**Force-with-lease safety property:** Push must use `--force-with-lease=refs/heads/agent/product-challenge-whatif-bridge-v2:bb30fd49640084c9a0878afc3191e6e368c5edd0` so it fails if remote advanced unexpectedly.

**Draft after force-push invariant:** After push, `gh pr view 17` must still be `isDraft=true`; if not, `gh pr edit 17 --repo Abdulla4akash/traffictwin` → convert to draft via API before requesting review.

## 6. Test commands and expected counts

On rehearsal `884618e` (and after Phase-B):

- `uv run --no-sync python -m pytest tests/unit/test_challenge_whatif_bridge.py tests/ui/test_challenge_whatif_bridge_ui.py tests/integration/test_challenge_whatif_e2e.py --collect-only -q` → **45** (18 + 24 + 3)
- `uv run --no-sync python -m pytest tests/unit/test_challenge_whatif_bridge.py tests/ui/test_challenge_whatif_bridge_ui.py tests/integration/test_challenge_whatif_e2e.py tests/ui/test_whatif_studio.py tests/unit/test_whatif_pair.py --collect-only -q` → **79** (18+24+3+13+21) — correct, not 77
- Broader rehearsal boundary `+ tests/ui/test_portfolio_explorer.py tests/unit/test_portfolio_explorer.py tests/ui/test_cross_page_state.py tests/ui/test_navigation_v07.py` → **181** collected (previously ~180, now 181 after 8-line ledger test growth)

Expected passes: 45, 79, 181 respectively (serial, E1 active).

## CI state classification

Current hosted Actions (verified 2026-08-09 via `gh run list`/`gh run view` on 20 recent runs across branches):

`CI_INFRASTRUCTURE_BLOCKED`

Evidence:
- `gh run view 31333013313` (rehearsal/pr17-phase-b-v1) → `The job was not started because recent account payments have failed or your spending limit needs to be increased.`
- `gh run view 31332811555` (tag pr17-pre-phase-b-bb30fd4) → same
- `gh run view 31338793418` (PR #16) → same
- All 20 recent `gh run list` entries `completed failure` with 3-5s duration, 0 steps executed.

Meaning:
- Jobs do not start; 0 steps, `log not found`.
- Red GitHub check UI is **not evidence of test failure** or product regression.
- Local gates remain the only executable code validation until billing is restored.

Owner action:
**Restore repository/account GitHub Actions billing/spending availability.** No workflow edits, no fake-success steps, no `rerun` loops, no code workaround. Do not edit `.github/workflows/**`.

Phase-B behavior while blocked:
- Keep PR #17 DRAFT.
- Do not interpret red zero-step jobs as code regression.
- Do not merge merely because local tests pass.
- Once billing is fixed, rerun hosted CI against the exact final Phase-B head.

---

## Old Phase-B trigger (ancestry assumption) — why it fails

Previous packet versions used (informationally):

```bash
git merge-base --is-ancestor 2d7e85f origin/main
```

- **Normal merge commit** (merge `--no-ff`): ancestry **TRUE** (exact head preserved).
- **Squash merge** (one squashed commit): **FALSE** — exact `2d7e85f` SHA not in history, even though content is correct.
- **Rebase-and-merge** (replayed commits): **FALSE** — SHAs changed, ancestry absent.

Yet the PR is correctly merged in all three. Exact-head ancestry is therefore **informational only**, not a required gate.

---

## New readiness contract (merge-style-agnostic)

Phase B may begin only when **BOTH** are true:

### Gate A — GitHub says PR #13 was actually merged

```bash
gh pr view 13 --repo Abdulla4akash/traffictwin --json state,mergedAt,headRefOid,mergeCommit
```

Require: `mergedAt != null`

Do not use `state == CLOSED` alone (closed-unmerged is insufficient).

### Gate B — live main contains the required PR #13 product contract

Do not rely on SHA ancestry. Verify semantic/content presence on fetched `origin/main` via `tools/check_pr17_phase_b_ready.py` (read-only).

At minimum establish from live main:

- Portfolio Explorer production module exists (`src/traffictwin/ui/portfolio_explorer.py`)
- Portfolio Explorer page exists (`src/traffictwin/ui/pages/portfolio_explorer.py`, `src/traffictwin/ui/app_pages/portfolio_explorer.py`)
- Portfolio page is registered exactly once via AST (`src/traffictwin/ui/navigation_v07.py` `V07PageSpec(UiPage.PORTFOLIO_EXPLORER)` count==1, positional+keyword; `labels.py` contains `PORTFOLIO_EXPLORER`)
- Challenge Seed Library data/contracts exist (`ChallengeSeedDefinition`, `get_challenge_seed_library`)
- All seven challenge seeds are `REPRESENTABLE_ONLY` counted structurally via AST `ChallengeSeedDefinition(status=ChallengeExecutionStatus.REPRESENTABLE_ONLY)` exactly 7 (IDs `CH-01`..`CH-07` present, enum definition not counted, no EXECUTABLE/NOT_YET_EXECUTABLE)
- Authoritative selector-consumed contract exists (`SELECTOR_CONSUMED_FIELDS`, `is_selector_input`)
- Portfolio production fingerprint includes reviewed evidence semantics (`challenge_target_surfaces`, `selector_input_features`)
- No generic ScenarioSeed→run executor appeared (no `def run_challenge` etc.)
- Navigation/page contract includes Portfolio exactly once (`navigation.py` contains `portfolio`)

The script `tools/check_pr17_phase_b_ready.py` implements Gate B exactly from `src/traffictwin/ui/portfolio_explorer.py` as source of truth.

---

## Merge-style-agnostic readiness states (fail-closed, 5 states)

The checker reports distinct exit codes (no silent default):

- **BLOCKED_PR13_OPEN** (exit 1) — `mergedAt == null` → No Phase B.
- **BLOCKED_CONTENT_MISMATCH** (exit 2) — `mergedAt != null` but fetched main does not satisfy expected Portfolio/Challenge product contract → No Phase B, investigate merge result.
- **GITHUB_QUERY_ERROR** (exit 3) — `gh` query failed → distinct from content mismatch; retry query, do not proceed.
- **MAIN_PATH_REVISION_MISMATCH** (exit 4) — `main_path` HEAD != `expected-main-sha` (wrong worktree or stale fetch) → fail closed, do not evaluate Gate B.
- **READY_FOR_PHASE_B** (exit 0) — `mergedAt != null` AND `main_path` HEAD == `expected-main-sha` AND product contract passes (portfolio exactly once via AST, CH-01..CH-07 exactly 7 REPRESENTABLE_ONLY via AST) → Only then may owner authorize Phase-B replay.

Missing required `--main-path` or `--expected-main-sha` fails via argparse (exit 2, no default to cwd). Do not equate `2d7e85f is ancestor` with readiness.

---

## Synthetic merge-style proof (disposable LOCAL refs, now deleted)

Starting from `origin/main` + PR #13 contribution, constructed three synthetic outcomes:

| style | `2d7e85f` ancestor? | content gate (checker) | final readiness |
|---|---|---|---|
| Normal merge commit (`merge --no-ff 2d7e85f`) | TRUE | PASS | **READY** |
| Squash merge (`merge --squash 2d7e85f` as one commit) | FALSE | PASS | **READY** |
| Rebase-style (`cherry-pick origin/main..2d7e85f`, 8 commits) | FALSE | PASS | **READY** |
| Negative control (merged true but `portfolio_explorer.py` removed) | TRUE | FAIL (missing file) | **BLOCKED_CONTENT_MISMATCH** (exit 2) |
| Wrong-worktree with full content but mismatched SHA | TRUE | not evaluated (SHA mismatch) | **MAIN_PATH_REVISION_MISMATCH** (exit 4) |
| GitHub query failure (gh not found / API error) | — | — | **GITHUB_QUERY_ERROR** (exit 3, distinct) |

Plus: `mergedAt null` on good content → **BLOCKED_PR13_OPEN** (exit 1, verified).

This proves the old ancestry check fails for squash/rebase where the new semantic checker still returns READY, which is why the packet was changed. The rehearsal-populated tree cannot be mistaken for fetched origin/main: without `--expected-main-sha` the checker requires the argument; with a wrong SHA it returns MAIN_PATH_REVISION_MISMATCH (4), not READY.

Fail-closed checker `tools/check_pr17_phase_b_ready.py` (requires --main-path + --expected-main-sha, AST exactly-once portfolio and structural 7×REPRESENTABLE_ONLY) plus `tests/unit/test_pr17_phase_b_readiness.py` (15 tests, fail-closed) executed on `rehearsal/pr17-phase-b-v1`:

- `test_missing_required_main_path` → PASS (argparse exit 2)
- `test_wrong_worktree_sha_despite_complete_content` → PASS (exit 4 MAIN_PATH_REVISION_MISMATCH)
- `test_pr13_not_merged_blocked` → PASS (exit 1)
- `test_github_query_error_is_distinct` → PASS (exit 3 distinct)
- `test_merged_ready_on_valid_main` → PASS (exit 0)
- `test_merged_blocked_content_mismatch_missing_file` → PASS (exit 2)
- `test_missing_portfolio_registration` → PASS (exit 2, count 0 ≠1)
- `test_duplicate_portfolio_registration` → PASS (exit 2, count 2 ≠1)
- `test_six_challenge_seeds_blocked` → PASS (exit 2, count 6 ≠7)
- `test_one_non_representable_challenge_blocked` → PASS (exit 2, EXECUTABLE)
- `test_enum_definition_does_not_inflate_count` → PASS (enum not counted, still 7)
- `test_valid_seven_seed_contract` → PASS (7 REPRESENTABLE_ONLY)
- `test_rehearsal_tree_is_rejected_when_expected_main_sha_differs` → PASS (origin SHA vs rehearsal tree → 4)
- `test_content_gate_direct` → PASS
- `test_content_gate_missing_portfolio` → PASS

See `.venv/bin/python -m pytest tests/unit/test_pr17_phase_b_readiness.py -q` → 15 passed.

---

## 7. Owner / reviewer sequence and evidence provenance

- Owner: Muse 4 (implementation worker) — builds rehearsal, proves mutations, prepares packet, executes tests/gates.
- Reviewer: Claude 4 (independent exact-head review, Passes 1-4) — **did NOT run pytest or project gates**.

Evidence provenance (as of this packet):

| claim | Claude independently verified | Muse executed this round |
|---|---|---|
| exact SHAs (2d7e85f, bb30fd4, replay commits) | yes (git rev-parse, gh pr view) | yes |
| local/origin/GitHub ref alignment | yes | yes |
| patch IDs (stable) | yes (git patch-id --stable) | yes |
| source assertions (ledger st.info exact, old-receipt no OR) | yes (source read, no vacuous branches) | yes |
| absence of vacuous branches (no OR with pair_id) | yes | yes |
| counts from source/collection where inspected | yes (where inspected) | yes (see §6) |
| diffstat / per-file numstat | yes (git diff --stat/--numstat) | yes |
| packet contents (157 lines at 14b1576) | yes | yes |
| pytest pass counts by execution (45/79/181) | **no** — Claude validated test quality, not execution | **yes** (see §6, §10-11) |
| ruff / format / mypy / lock / diff-check execution | **no** | **yes** (see §11) |
| mutation cycles proving tests kill mutants | **no** (Claude noted mutation claims, did not re-run) | **yes** (see §12; M1-M5 re-run this round, older claims marked PREVIOUSLY MUSE-EXECUTED) |

Do not attribute Muse execution to Claude. This packet's §6, §10-12, §11 are Muse-executed this round; earlier Claude passes verified structure but did not execute suites/gates.

After PR #13 merges, owner executes Phase-B procedure above, pushes official PR #17, requests final Claude 4 exact-head review on new official head, then PR #17 remains DRAFT until merge.

## 8. Durability and isolation

- This packet lives at `docs/quality/pr17_phase_b_rebase_packet.md` on branch `rehearsal/pr17-phase-b-v1` **locally and on `origin/rehearsal/pr17-phase-b-v1` after push** (remote durable, survives reboot, `/tmp` cleanup, and single-disk loss); not on `origin/main`, not on official PR #17. Do not claim `/tmp` or one local clone is durable.
- `origin/rehearsal/pr17-phase-b-packet-v1` is predecessor; canonical is `origin/rehearsal/pr17-phase-b-v1`.
- Remote safety tag `pr17-pre-phase-b-bb30fd4` at `0d1f0fe3304d877b3897466b0de32733dd5c6028` → `bb30fd4` is second remote durability anchor.
- Optional bundle `~/AntigravityTest/traffictwin-pr17-phase-b.bundle` (see §14) is secondary offline backup; remote branch/tag are primary.
- Official `agent/product-challenge-whatif-bridge-v2` remains `bb30fd4` until Phase-B.
- PR #13, PR #14, PR #16, PR #15, research `/diss` untouched by this packet creation (read-only `git fetch` and `gh pr view`).

---

## 9. Pass-6 fail-closed hardening (P6-1..4) — this packet revision

This revision (353f61d) closes Claude Pass-6 fail-open findings; official product code unchanged (still 8-file bridge, 2726/31).

- **P6-1 missing --main-path defaults to rehearsal** → fixed: `--main-path` and `--expected-main-sha` both `required=True`; `main_path HEAD --expected-main-sha binding via `git -C main_path rev-parse HEAD` returns `MAIN_PATH_REVISION_MISMATCH (4)` on mismatch or undeterminable HEAD; rehearsal tree with origin SHA is rejected (test_rehearsal_tree_is_rejected...).
- **P6-2 portfolio count used `<1` not `==1` (duplicate passes)** → fixed: AST walker for `V07PageSpec(UiPage.PORTFOLIO_EXPLORER)` positional first arg or `page=` keyword, `count !=1` → BLOCKED with `portfolio_registration_count = {count} expected =1`; tests `test_missing_portfolio_registration` (0) and `test_duplicate_portfolio_registration` (2) both assert exit 2.
- **P6-3 challenge count used substring token (enum inflated, non-REPRESENTABLE not checked)** → fixed: parse `ChallengeSeedDefinition` calls via AST, extract `(challenge_id,status)` where `challenge_id.startswith("CH-")`, count must be 7, IDs must equal `CH-01..CH-07` set, every status must be `REPRESENTABLE_ONLY` (else `non_representable_seed_ids`); enum `class ChallengeExecutionStatus: REPRESENTABLE_ONLY` not counted; tests `test_six_challenge_seeds_blocked`, `test_one_non_representable...`, `test_enum_definition_does_not_inflate_count`.
- **P6-4 GitHub query error mapped to BLOCKED_CONTENT_MISMATCH** → fixed: `except Exception: return 3` with `GITHUB_QUERY_ERROR` message, distinct from `BLOCKED_CONTENT_MISMATCH (2)`; test `test_github_query_error_is_distinct` asserts exit 3.

Exit-code contract (documented in checker docstring): `0 READY_FOR_PHASE_B, 1 BLOCKED_PR13_OPEN, 2 BLOCKED_CONTENT_MISMATCH, 3 GITHUB_QUERY_ERROR, 4 MAIN_PATH_REVISION_MISMATCH`. Packet step 5 and synthetic table above reflect this contract.

No workflow edits; CI remains `CI_INFRASTRUCTURE_BLOCKED` (billing) — see CI section.


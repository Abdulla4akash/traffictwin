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

## 5. Exact official Phase-B rebase procedure after PR #13 merges

**Current reality (already retargeted):** PR #17 has already been retargeted to `main` while head remains `bb30fd4` (see §1). This prevents auto-close when `agent/product-portfolio-explorer-v2` is deleted. The temporary diff on GitHub is not the final Phase-B diff and must not be reviewed/merged. Future procedure begins with verification of this retargeted state.

**Trigger:** `gh pr view 13 --json state` becomes `MERGED` and `git rev-parse origin/main` contains `2d7e85f`.

Do NOT touch official PR #17 until this trigger, even though its base is already `main`.

Procedure (mechanical, no re-interpretation — starts with verification, then safety ref, then destructive ops):

```bash
git fetch origin --prune
# 1. Verify PR #17 still OPEN/DRAFT, base main, head bb30fd4 (retarget already done)
gh pr view 17 --repo Abdulla4akash/traffictwin --json state,isDraft,baseRefName,headRefName,headRefOid
# must be: state=OPEN, isDraft=true, baseRefName=main, headRefOid=bb30fd49640084c9a0878afc3191e6e368c5edd0
git rev-parse agent/product-challenge-whatif-bridge-v2  # must be bb30fd4
git rev-parse origin/agent/product-challenge-whatif-bridge-v2  # must be bb30fd4
# 2. Verify safety tag exists locally and remotely BEFORE any destructive command
git rev-parse pr17-pre-phase-b-bb30fd4^{commit}  # must be bb30fd4
git ls-remote --tags origin refs/tags/pr17-pre-phase-b-bb30fd4  # must show 0d1f0fe... bb30fd4
# 3. Verify PR #13 trigger
gh pr view 13 --repo Abdulla4akash/traffictwin --json state,headRefOid,baseRefName,mergedAt
git log --oneline origin/main -5  # must show 2d7e85f merged
# 4. Create rebase tmp from new live main
git checkout -b tmp-phase-b origin/main
# Verify patch range still 3 commits from pre-Phase-B head
git log --oneline 2d7e85f..bb30fd4 --reverse  # 7aae39b, f148805, bb30fd4
# Replay PR #17 core (identical patches — preserves reviewed product patch)
git cherry-pick 7aae39ba5a46ead8429fdf020a13ced55acf4eb6  # 7aae39b
git cherry-pick f14880501cf7ac203a61fa7a82843f26548672d2  # f148805
git cherry-pick bb30fd49640084c9a0878afc3191e6e368c5edd0  # bb30fd4
# Replay UX/test hardening from this canonical packet branch (use commit hashes from rehearsal/pr17-phase-b-v1)
git cherry-pick 9b59b6a  # a6cb1bb equivalent
git cherry-pick 9a05fb6  # f31a34e equivalent
git cherry-pick 459677f
git cherry-pick 884618e
# Verify
git diff origin/main..HEAD --stat  # 8 files, 2726/31
git diff origin/main..HEAD --name-only  # no navigation files
ls src/traffictwin/ui/pages/*.py | wc -l  # 55
ls src/traffictwin/ui/app_pages/*.py | wc -l  # 53
# Gates
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync mypy
uv lock --check
git diff --check
# Tests (serial, E1 may still be active)
uv run --no-sync python -m pytest tests/unit/test_challenge_whatif_bridge.py tests/ui/test_challenge_whatif_bridge_ui.py tests/integration/test_challenge_whatif_e2e.py tests/ui/test_whatif_studio.py tests/unit/test_whatif_pair.py -q
uv run --no-sync python -m pytest tests/unit/test_challenge_whatif_bridge.py tests/ui/test_challenge_whatif_bridge_ui.py tests/integration/test_challenge_whatif_e2e.py tests/ui/test_whatif_studio.py tests/unit/test_whatif_pair.py tests/ui/test_portfolio_explorer.py tests/unit/test_portfolio_explorer.py tests/ui/test_cross_page_state.py tests/ui/test_navigation_v07.py -q
# Push official (only after safety tag verified and tests/gates pass)
git checkout agent/product-challenge-whatif-bridge-v2
git reset --hard tmp-phase-b
git push --force-with-lease origin agent/product-challenge-whatif-bridge-v2
# Base is already main — verify, do not retarget again unless it drifted
gh pr view 17 --repo Abdulla4akash/traffictwin --json baseRefName  # must be main
git branch -D tmp-phase-b
```

If `git cherry-pick` reports 0 conflicts, proceed; if conflict, resolve by accepting both sides (additive bridge sections), then `git cherry-pick --continue`. Do not improvise outside this packet — any deviation is a packet defect.

## 6. Test commands and expected counts

On rehearsal `884618e` (and after Phase-B):

- `uv run --no-sync python -m pytest tests/unit/test_challenge_whatif_bridge.py tests/ui/test_challenge_whatif_bridge_ui.py tests/integration/test_challenge_whatif_e2e.py --collect-only -q` → **45** (18 + 24 + 3)
- `uv run --no-sync python -m pytest tests/unit/test_challenge_whatif_bridge.py tests/ui/test_challenge_whatif_bridge_ui.py tests/integration/test_challenge_whatif_e2e.py tests/ui/test_whatif_studio.py tests/unit/test_whatif_pair.py --collect-only -q` → **79** (18+24+3+13+21) — correct, not 77
- Broader rehearsal boundary `+ tests/ui/test_portfolio_explorer.py tests/unit/test_portfolio_explorer.py tests/ui/test_cross_page_state.py tests/ui/test_navigation_v07.py` → **181** collected (previously ~180, now 181 after 8-line ledger test growth)

Expected passes: 45, 79, 181 respectively (serial, E1 active).

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


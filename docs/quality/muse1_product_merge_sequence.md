# Muse 1 Product Merge Sequence — Post-#20/#14/#18 Integration Evidence

> Rehearsal-only — do not cherry-pick into product history unless owner directs.
> Branches: `rehearsal/muse1-post20-post14-v1` (base) and `rehearsal/muse1-pr18-acceptance-only-v1` (final). Do not open PRs from them.

## Exact approvals (Claude 1, exact-head)

| PR | Branch | Head | Base | State |
|---|---|---|---|---|
| #20 | `agent/fix-compare-draft-lifecycle` | `ea37dd3bb13ec11900583556d1d95ac294f6f659` | `main` | OPEN DRAFT MERGEABLE — standalone Compare atomic-draft + first-run-guidance fix, independently mergeable |
| #14 | `agent/product-v2-home-guided-whatif` | `a9ec532ac88ed8678973416fe21bcab5d1a57d11` | `main` | OPEN DRAFT MERGEABLE — Home/Guided → What-If entry flow |
| #18 | `agent/product-v2a-journey-acceptance` | `1ec74cd71dba27bb7cc8ceb3eaba89c3e0ecf1c0` | `agent/product-v2-home-guided-whatif` | OPEN DRAFT MERGEABLE — V2-A real journey acceptance layer |
| main | `main` | `73264bd125ead979cd2615d5e4b50c2cfe6c50ae` | — | Merge PR #12 |
| Safety tags | `pr20-approved-ea37dd3` → ea37dd3, `pr14-approved-a9ec532` → a9ec532, `pr18-approved-1ec74cd` → 1ec74cd | — | — | Pushed to origin, verified via `git ls-remote --tags` |

Live verified 2026-08-09 via `git fetch origin --prune` + `gh pr view 20/14/18 --json state,isDraft,mergeable,headRefOid` — all exactly above heads. No commit/amend/rebase/force-push/mark-ready/merge performed; PR bodies corrected only (metadata).

## Merge order

1. **#20 first** — `ea37dd3` onto `main` (73264bd). Adds `src/traffictwin/ui/pages/compare.py` fix + `tests/ui/test_compare_draft_lifecycle.py` + `tests/ui/test_first_run_guidance.py` (4 guidance tests, 3 files total). No dependency on #14.
2. **#14 second** — `a9ec532` onto `main+ #20`. Adds Home/Guided entry (docs + `home.py`/`guided.py` + `test_home_whatif_s4a`/`test_guided_whatif_s4a` + `test_ui_demo_flow` delta, 7 files).
3. **Later product queue** — #16/#13/etc. as owner directs — **do not independently reorder**.
4. **#18 acceptance layer LAST** — after #20 and #14 are on `main`, PR #18 reduces to acceptance-only.

## Why #18 goes last

- After #20, Compare code/test ownership is already on `main`. Replaying PR #18’s Compare changes would be redundant (byte-identical blobs 3b3e627/29d43c2/eb25c4e) and would be absorbed.
- After #14, Home/Guided entry layer is already on `main`. PR #18’s stacked base is satisfied.
- Then #18 becomes **acceptance-only**: the only surviving diff is the V2-A journey evidence, not product fixes. This is the smallest, safest final integration and avoids re-owning code already reviewed in #20.

## Expected final #18 diff (after #20+#14)

Exactly **2 files, 1,168 insertions**:

```
docs/quality/v2a_real_journey_acceptance.md        |  127 +++
tests/integration/test_v2a_real_journey_acceptance.py | 1041 ++++++++++++++++++++
 2 files changed, 1168 insertions(+)
```

Proof on `rehearsal/muse1-pr18-acceptance-only-v1` @`f8e8fa6` vs base `8e2703b`:

```
git diff 8e2703b...f8e8fa6 --stat        # 2 files, 1168 ins
git diff 8e2703b...f8e8fa6 -- src/traffictwin/ui/pages/compare.py               == 0
git diff 8e2703b...f8e8fa6 -- tests/ui/test_compare_draft_lifecycle.py        == 0
git diff 8e2703b...f8e8fa6 -- tests/ui/test_first_run_guidance.py             == 0
git rev-parse f8e8fa6:src/traffictwin/ui/pages/compare.py == ea37dd3:src/traffictwin/ui/pages/compare.py == 3b3e627 (inherited, not re-added)
```

No other file should remain; verify via `git diff origin/main...HEAD --stat` after official rebase.

## VEC sweep topology rule

There are **two valid sweep modes**:

### MODE A — Product-only hermetic sweep (temporary worktree acceptable)

If the checkout is under `/tmp/.../scratchpad/` (or any path where `ROOT.parent/external/vec_env` does not resolve), the external `vec_env` clone is not found. The five VEC tests then hit their `if not VEC_REPO.is_dir(): pytest.skip(...)` guard and **SKIP**. In Claude’s earlier `/tmp` sweeps this produced `959 passed / 8 skipped` (PR #20) and `987 passed / 1 failed` (old PR #18) — those runs **did NOT exercise the VEC lane**. Report clearly: “Product sweep; external VEC lane not exercised.” Never count those skips as VEC validation.

### MODE B — Product + External-VEC-aware sweep (normal topology required)

Run from a checkout whose parent hierarchy permits `external/vec_env` to resolve. For this machine that means preserving the normal `/Users/akashx/AntigravityTest/...` layout (e.g., `/Users/akashx/AntigravityTest/traffictwin-v2a-acceptance` or worktrees `traffictwin-vec-main`/`traffictwin-vec-pr20`). Then `VEC_REPO`/`TOS_REPO`/`trace` are reachable and tests proceed to **preflight**.

## Current VEC condition (pre-existing, not Compare regression)

From normal topology, the **exact five** tests execute and fail **identically** on `origin/main @73264bd` and on PR #20 @ea37dd3 (and on synthetic future `f8e8fa6`):

```
tests/integration/test_vec_fcd_preprocessing.py::test_pinned_pipeline_is_deterministic_atomic_and_non_mutating
tests/integration/test_vec_fcd_preprocessing.py::test_execution_refuses_existing_and_overlapping_destinations
tests/integration/test_vec_interface.py::test_real_source_snapshot_is_read_only_and_ready_when_repositories_exist
tests/integration/test_vec_runner.py::test_real_pinned_two_step_run_is_isolated_validated_and_non_mutating
tests/integration/test_vec_runner.py::test_real_vec06_receipt_trace_is_admitted_by_vec07
```

Failure modes (identical in both):

- `VecFcdPreprocessingError: VEC-06 preflight is rejected` (3 tests, including `test_execution_refuses...` where expected regex `must not already exist` mismatches actual `VEC-06 preflight is rejected`)
- `assert False` on `ready_for_exact_blob_access` (1)
- `VecRunnerError: VEC-07 preflight is rejected` (1)

Environment (same shell, same `.venv` 3.13.5, same `external/vec_env` e9844119 reachable, `tos-data` reachable, `trace_we_fullrsu.npz` reachable, `TRAFFICTWIN_VEC_FRESH_RESULT_DIR` unset, JAX `No module named 'jax'`): the lane’s `preflight_vec_fcd`/`preflight_vec_run` is `REJECTED` even though repos/traces exist — **pre-existing VEC lane condition**, not a product regression. Do **not** call this “missing infrastructure” or “cold infra”; call it “pre-existing VEC-06/VEC-07 preflight rejection with external checkout reachable.”

Do not investigate or fix VEC in this product lane; preserve attribution only.

## Exact rebase procedure after #20 and #14 land

Assume `origin/main` eventually contains both `ea37dd3` and `a9ec532` (via merge PRs; if squash, adjust to squash SHAs). Verify:

```bash
git fetch origin --prune
git rev-parse origin/main
git branch --contains ea37dd3 --contains a9ec532 -a  # or git log --oneline origin/main | grep ea37dd3/a9ec532
```

**Option A — rebase existing PR #18 branch (preserves history, will show redundant files as already applied):**

```bash
git checkout agent/product-v2a-journey-acceptance  # at 1ec74cd
git rebase origin/main
# Expect: src/traffictwin/ui/pages/compare.py and tests/ui/test_* may conflict or show as empty — resolve by keeping main:
git checkout --theirs src/traffictwin/ui/pages/compare.py tests/ui/test_compare_draft_lifecycle.py tests/ui/test_first_run_guidance.py  # if conflicted
git status  # should show only docs/quality/v2a_real_journey_acceptance.md and tests/integration/test_v2a_real_journey_acceptance.py as remaining delta
git rebase --continue
git diff origin/main...HEAD --stat  # should be 2 files, 1168 ins
git diff origin/main...HEAD -- src/traffictwin/ui/pages/compare.py | wc -l  # 0
```

**Option B — cherry-pick acceptance-only (cleaner, recommended):**

```bash
git checkout -b temp-pr18-acceptance origin/main
git show 1ec74cd:docs/quality/v2a_real_journey_acceptance.md > docs/quality/v2a_real_journey_acceptance.md
git show 1ec74cd:tests/integration/test_v2a_real_journey_acceptance.py > tests/integration/test_v2a_real_journey_acceptance.py
git add docs/quality/v2a_real_journey_acceptance.md tests/integration/test_v2a_real_journey_acceptance.py
git commit -m "feat(acceptance): V2-A real journey Home→Guided→What-If→Consequence→Compare (replayed onto post-#20/#14 main)

Replayed from 1ec74cd onto $(git rev-parse origin/main) after #20 (ea37dd3) and #14 (a9ec532) landed.
Redundant Compare fix (src/traffictwin/ui/pages/compare.py 3b3e627, tests/ui/test_compare_draft_lifecycle.py 29d43c2, tests/ui/test_first_run_guidance.py eb25c4e) is now owned by #20/main and not re-added (byte-identical)."
git diff origin/main...HEAD --stat  # 2 files, 1168 ins
```

Conflict expectations: **none** for the 2 acceptance files (they are new); the 3 redundant files will conflict or show as already applied if rebasing — resolution is to keep `main`. No other conflicts expected because PR #18’s acceptance layer does not touch Home/Guided/Compare production beyond the fix now owned by #20.

## Tests / gates (on final acceptance-only rehearsal `f8e8fa6`)

**Focused 8-suite future state (79 tests, all passed, serial due to 300s limit):**

- `test_v2a_real_journey_acceptance` 9 passed (152s)
- `test_compare_draft_lifecycle` 13 passed (72s)
- `test_first_run_guidance` 9 passed (8s)
- `test_ui_demo_flow` 19 passed (81s)
- `test_home_whatif_s4a` 11 passed / `test_guided_whatif_s4a` 13 passed / `test_cross_page_state` 4 passed / `test_page_presentation_compare` 1 passed — together 29 passed (32s)

**Product blast radius (split due to 300s per-invocation limit, but aggregated = full sweep):**

- `tests/ui -q` **587 passed in 273.67s** (no VEC, pure product)
- `tests/unit/ui -q` **190 passed in 245.05s**
- `tests/integration` split: first 35 files **110 passed in 36.93s**, second 35 files **105 passed, 5 failed, 3 skipped in 267.51s** (the 5 are exactly the VEC nodes above, 3 are `jax`/`TRAFFICTWIN_VEC_FRESH_RESULT_DIR` skips)
- **Total product = 587+190+215=992 passed, 5 failed (VEC pre-existing), 3 skipped = 1000 collected** — matches `pytest --collect-only` 1000. The 5 failed are CASE 1, not Compare regressions.
- If run from `/tmp` worktree: expect `VEC-EXTERNAL TESTS NOT EXERCISED DUE TO WORKTREE TOPOLOGY` with ~8 skips instead of 5 fails — report topology explicitly, do not disguise.

**External-aware 5-test comparison (identical env):**

- Baseline A `origin/main @73264bd` (via `traffictwin-vec-main`): 5 failed same preflight rejection in 6.36s
- Final B `rehearsal/muse1-pr18-acceptance-only-v1 @f8e8fa6`: 5 failed same preflight rejection in 7.05s
- **Identical/pre-existing: YES** — synthetic final product tree does not change VEC result; no product interaction.

**Gates on `f8e8fa6`:**

```
uv run --no-sync ruff check .        -> All checks passed! (0)
uv run --no-sync ruff format --check . -> 1022 files already formatted (0)
uv run --no-sync mypy                -> Success: no issues found in 937 source files (0)
uv lock --check                      -> Resolved 91 packages (0)
git diff --check                     -> (no whitespace errors, 0)
```

## Canonical post20/post14 base (rehearsal)

- **Branch:** `rehearsal/muse1-post20-post14-v1` @`8e2703b7254f6ce9af2b662dcb25d980f5ddb70d`
- **Composition:** `73264bd125ead979cd2615d5e4b50c2cfe6c50ae` + `ea37dd3` + `a9ec532`
  - `55a4d34` merge PR20, `8e2703b` merge PR14
- **Tree:** `5094a88d007db92869f6717c016850a9968ac05b` — **TREE IDENTICAL** to previous Muse/Muse rehearsal `e1722c9` (5094a88...), **COMMIT METADATA DIFFERENT** (expected, merge commit messages differ). Proven via `git rev-parse <ref>^{tree}`.
- **Diff vs 73264bd:** 10 files, 1,163 insertions, 45 deletions

```
 docs/demo_quickstart.md                  |  24 +-
 docs/user_guide.md                       |  28 ++-
 src/traffictwin/ui/guided.py             |  32 +++
 src/traffictwin/ui/pages/compare.py      | 115 ++++++++--
 src/traffictwin/ui/pages/home.py         |  53 ++++-
 tests/integration/test_ui_demo_flow.py   |   8 +-
 tests/ui/test_compare_draft_lifecycle.py | 259 +++++++++++++++++++++
 tests/ui/test_first_run_guidance.py      | 125 ++++++++++
 tests/unit/ui/test_guided_whatif_s4a.py  | 381 +++++++++++++++++++++++++++++++
 tests/unit/ui/test_home_whatif_s4a.py    | 183 +++++++++++++++
```

- **Final acceptance branch:** `rehearsal/muse1-pr18-acceptance-only-v1` @`f8e8fa6` (8e2703b + 2 files, 1168 ins).

## Safety tags (remote)

```
pr20-approved-ea37dd3 -> ea37dd3bb13ec11900583556d1d95ac294f6f659 (tag c6e8... -> commit a9ec532? actually ea37dd3; verified ls-remote)
pr14-approved-a9ec532 -> a9ec532ac88ed8678973416fe21bcab5d1a57d11
pr18-approved-1ec74cd -> 1ec74cd71dba27bb7cc8ceb3eaba89c3e0ecf1c0
```

Pushed via `git push origin refs/tags/pr20-approved-ea37dd3 ...` and verified with `git ls-remote --tags origin`.

## Remote rehearsal refs

- `rehearsal/muse1-post20-post14-v1` @8e2703b
- `rehearsal/muse1-pr18-acceptance-only-v1` @f8e8fa6
- Pushed as integration evidence only; **do not open PRs** from them.

## Research isolation

- Current research: 87359 `run_e2_native_placement_pilot.py` + 87396 `eval_sumo_stage1_mc.py` (vec-jax 0.4.30) — checked via `pgrep -fl 'e2|native-placement|eval_sumo|run_e1|analyze_e1|vec'`.
- No modification to `/Users/akashx/AntigravityTest/diss`, `external/vec_env` (e9844119), `tos-data`, research branches, or outputs. No SUMO/VEC execution; the five VEC tests are preflight/validation only (read-only).

## Ownership / absorption table

| PR18 path/patch | Final owner after integration | Absorbed by PR20? | Survives PR18 delta? |
|---|---|---|---|
| `src/traffictwin/ui/pages/compare.py` (fix `"."` corruption, atomic, helper) | PR20 | YES (blob 3b3e627 identical) | NO |
| `tests/ui/test_compare_draft_lifecycle.py` (13) | PR20 | YES (29d43c2 identical) | NO |
| `tests/ui/test_first_run_guidance.py` (4 new + existing) | PR20 | YES (eb25c4e identical) | NO |
| `docs/quality/v2a_real_journey_acceptance.md` | PR18 | NO | YES |
| `tests/integration/test_v2a_real_journey_acceptance.py` (9) | PR18 | NO | YES |

Patch IDs: PR20 `5f79a857... ea37dd3`; PR18 `4d8d4d2a... ef6178c`, `17fb7b8e... eaa210b`, `a40cc03f... 1ec74cd` — blob identity proves absorption despite different bases.

---

*Generated on rehearsal/muse1-pr18-acceptance-only-v1 @f8e8fa6, base 8e2703b (tree 5094a88...). Do not merge #20 yourself; wait for owner. Official heads remain frozen until their integration turn.*

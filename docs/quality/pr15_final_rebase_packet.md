# PR #15 — Manchester Evidence Activation Hub — Final Rebase Packet (V2)

> **Packet version:** V2 — round-6 computed-field architecture
> **Date:** 2026-08-09
> **Owner:** Muse 5 (implementation worker) — checked by Claude 5 (reviewer)
> **Status:** OFFICIAL PR #15 FROZEN at `34cdcac` (37 pages, DRAFT, MERGEABLE). Final 37→38 rebase NOT yet performed — blocked on PR #13 merge. This packet lives on `rehearsal/pr15-final-38-v2` only, NOT on official PR #15.

---

## 1. Official PR #15 freeze

| Field | Value |
|---|---|
| Branch | `agent/product-manchester-activation` |
| Exact head | `34cdcac6b3f8693944876059704db3aabd5af521` |
| Title | `product: add Manchester evidence activation hub` |
| State | `OPEN` |
| isDraft | `true` |
| mergeable | `MERGEABLE` |
| baseRefName | `main` |
| origin/main at freeze | `73264bd125ead979cd2615d5e4b50c2cfe6c50ae` (Merge PR #12 `agent/product-consequence-lenses-v2`) |
| Page count on official | **37** — `len(UiPage)==37`, `len(V07_PAGE_SPECS)==37`, `len(PAGE_RENDERERS)==37` — includes `Manchester Evidence Hub`, excludes `Portfolio Explorer` (PR #13 unmerged) |
| Safety tag (local + remote) | `pr15-pre-final-rebase-34cdcac` → `34cdcac6b3f8693944876059704db3aabd5af521` — `git ls-remote --tags origin refs/tags/pr15-pre-final-rebase-34cdcac` = `5499988ebd946f224dc58671dacc6464f50bf109` (annotated tag object) |
| Final rebase performed | **NO** — this task does NOT authorize official Phase B |

**Rule:** Do NOT edit Manchester product code, tests, amend, rebase, force-push, add cleanup commits, merge, or mark Ready while head is `34cdcac` unless a later exact-head review finds a real defect. Only PR body/metadata wording may be corrected without invalidating the SHA.

Proof:

```
gh pr view 15 --repo Abdulla4akash/traffictwin --json state,isDraft,mergeable,baseRefName,headRefName,headRefOid
# → {"baseRefName":"main","headRefName":"agent/product-manchester-activation","headRefOid":"34cdcac6b3f8693944876059704db3aabd5af521","isDraft":true,"mergeable":"MERGEABLE","state":"OPEN"}

git rev-parse agent/product-manchester-activation        # 34cdcac6b3f8693944876059704db3aabd5af521
git rev-parse pr15-pre-final-rebase-34cdcac^{commit}    # 34cdcac6b3f8693944876059704db3aabd5af521
git show agent/product-manchester-activation:src/traffictwin/ui/labels.py | sed -n '/class UiPage/,/^class /p'  # 37 members, MANCHESTER_EVIDENCE_HUB present, PORTFOLIO_EXPLORER absent
```

---

## 2. Round-6 closure — computed-field architecture (structural, not denylist)

### Old round-5 architecture (superseded)

- Typed machine state existed (`SoftwareSupportState`, `AcquisitionReadinessState`, `LocalEvidenceState`, `RightsRetentionState`, `ScientificGateState` + `FreshnessTruthState`).
- Separately authored `software_support_state`, `acquisition_readiness`, `local_evidence_state`, `rights_retention_state`, `scientific_gate_state` **prose fields were writable** on the model.
- A `@model_validator` denylist scanned prose for contradictions (e.g. `"Blocked"` while typed state was `NOT_APPLICABLE`). Phrase variants could bypass it.

### Round-6 final architecture (commit `34cdcac`, verified by Claude 5)

- **Typed state is authoritative.** Five `StrEnum` types are the only machine truth.
- **Five presentation fields are `@computed_field` read-only derived** — callers cannot supply them. `model_config = ConfigDict(extra="forbid")` rejects injected `software_support_state`, `acquisition_readiness`, `local_evidence_state`, `rights_retention_state`, `scientific_gate_state` as unknown fields.
- **Formatters derive presentation deterministically:**

| Typed field | Formatter | Example mapping |
|---|---|---|
| `software_support_typed: SoftwareSupportState` | `format_software_support()` | `AVAILABLE → "AVAILABLE"`; `UNAVAILABLE_PROVIDER_CONTRACT → "UNAVAILABLE — adapter not implemented pending provider contract"` |
| `acquisition_typed: AcquisitionReadinessState` | `format_acquisition_readiness()` | `READY → "READY"`; `NOT_READY_CREDENTIAL_MISSING → "NOT READY — credential unavailable"` |
| `local_evidence_typed: LocalEvidenceState` | `format_local_evidence()` | `ACCEPTED_AVAILABLE → "Accepted local evidence available"`; `NOT_ACCEPTED → "No accepted local evidence"` |
| `rights_typed: RightsRetentionState` | `format_rights_retention()` | `NOT_RECORDED → "NOT_RECORDED / OWNER_DECISION_REQUIRED"` |
| `scientific_gate_typed: ScientificGateState` | `format_scientific_gate()` | `BLOCKED → "BLOCKED / OWNER-SCIENTIFIC DECISION REQUIRED"` |

- **Denylist validator is deleted.** `src/traffictwin/ui/manchester_evidence_hub.py` contains 5 `format_*` functions + 5 `@computed_field` properties + 0 `@model_validator` denylist. No NLP / substring scanner remains.
- **Contradiction class structurally removed.** There is no prose field to contradict.

**Claude 5 independent verification (round-6):** all five bypass strings are now rejected by `extra="forbid"` before any validator runs (not by denylist):

- original round-5 tamper string → `extra_forbidden`
- negation bypass → `extra_forbidden`
- sign-off bypass → `extra_forbidden`
- clearance bypass → `extra_forbidden`
- review-complete bypass → `extra_forbidden`

Do not describe this as “denylist improved.”

### Source location

`src/traffictwin/ui/manchester_evidence_hub.py:1-250` — exact lines:

```
model_config = ConfigDict(extra="forbid")
software_support_typed: SoftwareSupportState
...
@computed_field
@property
def software_support_state(self) -> str: return format_software_support(self.software_support_typed)
@computed_field
@property
def acquisition_readiness(self) -> str: return format_acquisition_readiness(self.acquisition_typed)
@computed_field
@property
def local_evidence_state(self) -> str: return format_local_evidence(self.local_evidence_typed)
@computed_field
@property
def rights_retention_state(self) -> str: return format_rights_retention(self.rights_typed)
@computed_field
@property
def scientific_gate_state(self) -> str: return format_scientific_gate(self.scientific_gate_typed)
```

Six `computed_field` occurrences total (5 in `ManchesterSourceReadiness` + 1 import) — `grep -c computed_field` = 6.

---

## 3. Identity policy (corrected)

**NOT** “only typed enums are identity.”

**IDENTITY BINDS:**

**A. typed readiness/evidence state** — the five typed enums plus `freshness_state: FreshnessTruthState` (authoritative `traffictwin.integration.manchester.freshness.FreshnessTruthState`), `source_id`, and the honest union counts.

**AND**

**B. immutable source-description semantics** — three prose fields that are intentional evidence semantics, not arbitrary UI presentation:

- `source_role: str`
- `evidence_ceiling: str`
- `coverage_scope: str`

These are bound into the portable fingerprint via `ManchesterEvidenceHubView.to_portable_dict()` / `to_canonical_bytes()` (SHA-256 of sorted JSON). Changing any of them changes `view.fingerprint`.

**NOT identity:**

- Derived presentation labels (`software_support_state`, `acquisition_readiness`, `local_evidence_state`, `rights_retention_state`, `scientific_gate_state`) — read-only views of (A). They do not independently define identity and are NOT separately bound.
- `generated_at` wall clock — excluded from `to_canonical_bytes()` / fingerprint.
- Secrets (`BODS_API_KEY`, `NATIONAL_HIGHWAYS_API_KEY`), absolute workspace paths — excluded.

Reference: `to_portable_dict()` binds `source_id, source_role, evidence_type, evidence_ceiling, coverage_scope, freshness_state, typed states, blockers, next_action` per source; see lines 221-254.

---

## 4. V2 rehearsal state — the preserved conflict resolution

| Ref | Tip | Pages | Upstream tracking | Purpose |
|---|---|---|---|---|
| `rehearsal/final-38-v2` | `1d797c5917dd3e8ec8bf89e45e0669736dbc5dc4` | 38 | `[origin/rehearsal/final-38-v2]` remotely durable | **Rehearsed conflict base** — live product stack without PR #15 |
| `rehearsal/pr15-final-38-v2` | `7bd5723af5a5fdd7bd254c766b35ced05586b424` | 38 | `[origin/rehearsal/pr15-final-38-v2]` remotely durable | **Rehearsed PR #15 final** — official `34cdcac` replayed onto `rehearsal/final-38-v2` |
| `agent/product-manchester-activation` | `34cdcac6b3f8693944876059704db3aabd5af521` | 37 | `[origin/agent/product-manchester-activation]` | Official frozen candidate (this packet does NOT live there) |

**V2 base composition (exact ancestry of `1d797c5`):**

```
origin/main (73264bd — PR #12) 
  + rehearsal/pr16-plus-pr20-pr14-base (5ce8e8a — merges PR16 48e705b)
    + tmp-pr14-v2 (a9ec532 — agent/product-v2-home-guided-whatif)
      + rehearsal/final-38-v2 merges PR13 (2d7e85f — agent/product-portfolio-explorer-v2)
```

`1d797c5` = `rehearsal v2: merge PR13` (resolves PR13 placement alongside PR14/PR16).

**Five rehearsed conflict files (exact set, reproduced on `34cdcac → 1d797c5` rebase):**

1. `docs/user_guide.md`
2. `src/traffictwin/ui/labels.py` — `UiPage` enum gains `PORTFOLIO_EXPLORER` (PR #13) + `MANCHESTER_EVIDENCE_HUB` (PR #15); v2 resolution keeps both (38 entries)
3. `src/traffictwin/ui/navigation.py`
4. `src/traffictwin/ui/navigation_v07.py` — `V07_PAGE_SPECS` 38
5. `src/traffictwin/ui/page_runtime.py` — `PAGE_RENDERERS` 38
6. *(also divergent in some histories)* `tests/ui/test_navigation_v07.py` — page-count assertion 37→38

> The v2 history concretely contains the correct merged semantics for all six; the first five are product conflicts, the sixth is the test expectation.

**Verification on `rehearsal/pr15-final-38-v2`:**

```
len(UiPage)==38, len(V07_PAGE_SPECS)==38, len(PAGE_RENDERERS)==38
# includes PORTFOLIO_EXPLORER + MANCHESTER_EVIDENCE_HUB + CONSEQUENCE_LENSES

pytest tests/unit/test_manchester_evidence_hub.py tests/ui/test_manchester_evidence_hub.py tests/ui/test_navigation_v07.py -q  # 148 passed
```

---

## 5. Preserve-before-rebase rule

**Do NOT delete `rehearsal/final-38-v2` / `rehearsal/pr15-final-38-v2` before official rebase verification.**

Why: `rehearsal/pr15-final-38-v2` is the cheapest ground-truth comparison target for the eventual official post-rebase tree. The five-file resolution exists concretely there — do not throw away the answer key before the real operation.

Allowed deletions (already performed, proven superseded):

- `rehearsal/final-38` (14809a5) — superseded by `rehearsal/final-38-v2` (1d797c5); `tmp-pr13` ancestor check `git merge-base --is-ancestor tmp-pr13 rehearsal/final-38-v2` → yes; `git log rehearsal/final-38-v2..rehearsal/final-38` = 3 merge commits not needed (v2 contains equivalent newer merges 1d797c5/9c75835/b14bde9).
- `rehearsal/pr15-final-38` (ebebf2b) — superseded by `rehearsal/pr15-final-38-v2` (7bd5723); v1 was round-5 `presentation-consistency contract` (pre-34cdcac), v2 is round-6 `derive presentation from typed state` (34cdcac). `git branch --contains ebebf2b` → only old v1, not v2.
- `tmp-pr13` (2d7e85f) — now ancestor of v2 (`git merge-base --is-ancestor tmp-pr13 rehearsal/final-38-v2` → yes; same for pr15-final-38-v2). Kept `tmp-pr13-v2` (same SHA, used by other flows) untouched.

**Kept:**

- `rehearsal/final-38-v2`, `rehearsal/pr15-final-38-v2` — until after official rebase + Claude exact-head review.
- `rehearsal/pr17-phase-b-packet-v1`, `rehearsal/pr18-post20-post14-v1`, `rehearsal/pr17-phase-b-v1`, `rehearsal/pr16-downstream-integration-v1` — other workers, never touched.

---

## 6. Remote durability

```
git tag pr15-pre-final-rebase-34cdcac 34cdcac^{commit}  # annotated, local + remote
git push origin refs/tags/pr15-pre-final-rebase-34cdcac
  → 5499988ebd946f224dc58671dacc6464f50bf109  refs/tags/pr15-pre-final-rebase-34cdcac

git push origin rehearsal/final-38-v2       # 1d797c5917dd3e8ec8bf89e45e0669736dbc5dc4 → origin/rehearsal/final-38-v2
git push origin rehearsal/pr15-final-38-v2  # 7bd5723af5a5fdd7bd254c766b35ced05586b424 → origin/rehearsal/pr15-final-38-v2

git ls-remote --heads origin refs/heads/rehearsal/final-38-v2       # 1d797c5917dd3e8ec8bf89e45e0669736dbc5dc4
git ls-remote --heads origin refs/heads/rehearsal/pr15-final-38-v2  # 7bd5723af5a5fdd7bd254c766b35ced05586b424
```

No PR opened from rehearsal refs.

---

## 7. Dependency heads — rehearsed vs live

| Component | Rehearsal / this packet (LIVE at 2026-08-09) | Expected in packet |
|---|---|---|
| `origin/main` | `73264bd125ead979cd2615d5e4b50c2cfe6c50ae` | same |
| PR #13 `agent/product-portfolio-explorer-v2` | `2d7e85f5641c1836a0e8892d2e256c55b1e3bc6a` | OPEN DRAFT |
| PR #14 `agent/product-v2-home-guided-whatif` | `a9ec532ac88ed8678973416fe21bcab5d1a57d11` | OPEN DRAFT |
| PR #16 `agent/product-consequence-lens-hardening-v2` | `48e705b40690fe2585324dd156c297503d1c64c1` | OPEN DRAFT (live, same as rehearsed) |
| PR #20 `agent/fix-compare-draft-lifecycle` | `ea37dd3bb13ec11900583556d1d95ac294f6f659` | OPEN DRAFT |
| Old stale PR #16 SHAs (no longer used) | `35e6f41`, `12f8436` | archived — not present in v2 base |

**Do not pretend old rehearsal base contained later commits.** `rehearsal/final-38-v2` was built against the SHAs above; if a dependency advances before official Phase B, a bounded compatibility rehearsal (`rehearsal/final-38-live-check`) should be run and this section updated.

---

## 8. PR16 compatibility audit

```
git diff --name-only 48e705b 48e705b  # rehearsed PR16 head == live PR16 head → no diff
```

Result: **NO delta** — live PR #16 (`48e705b`) equals the PR #16 head merged into `rehearsal/final-38-v2` (`9c75835 rehearsal v2: merge PR16 48e705b`). All five conflict files unchanged between rehearsed and live PR #16. The rehearsed PR15 five-file resolution is **not invalidated** by later PR16 hardening (v2 already includes the hardened `48e705b`).

If live PR #16 moves again before official rebase, re-run:

```
git diff --name-only <OLD_PR16> <LIVE_PR16>
```

and record whether any of `docs/user_guide.md`, `src/traffictwin/ui/labels.py`, `src/traffictwin/ui/navigation.py`, `src/traffictwin/ui/navigation_v07.py`, `src/traffictwin/ui/page_runtime.py`, `tests/ui/test_navigation_v07.py` changed.

---

## 9. Rerere — accelerator, not authority

### Enable

```
git config rerere.enabled true
git config rerere.autoupdate true
git config --get rerere.enabled      # true
git config --get rerere.autoupdate   # true
```

`.git/rr-cache` created on first conflict training.

### Train (replay `34cdcac → 1d797c5` with resolution anchored to `rehearsal/pr15-final-38-v2`)

Disposable branch `rehearsal/pr15-rerere-train-v2` started from `34cdcac`, rebasing onto `rehearsal/final-38-v2`. When five conflicts appeared, each file was resolved semantically to match `rehearsal/pr15-final-38-v2` (not wholesale `ours`/`theirs`), then `git add` + `git rebase --continue`. This run populates `.git/rr-cache`.

After training:

```
git rerere status          # no remaining conflicts
git rerere remaining       # (empty)
find .git/rr-cache -maxdepth 2 -type f | sort  # N recorded resolutions (see proof section for exact count)
```

### Prove (second clean replay)

Disposable branch `rehearsal/pr15-rerere-proof-v2` — same `34cdcac → 1d797c5` rebase. Expected Git output contains `Resolved 'src/traffictwin/ui/labels.py' using previous resolution` (and similar for the other four). After rerere auto-staged, each file was manually compared against `rehearsal/pr15-final-38-v2` and verified byte-for-byte.

### Tree equality

```
git rev-parse rehearsal/pr15-rerere-proof-v2^{tree}
git rev-parse rehearsal/pr15-final-38-v2^{tree}
git diff --stat rehearsal/pr15-rerere-proof-v2 rehearsal/pr15-final-38-v2
# → no substantive product difference (trees equal; commits differ only in ancestry/metadata)
```

If trees differ, the rerere training must be corrected — v2 rehearsal remains the correctness authority.

### Cleanup

Disposable `rehearsal/pr15-rerere-train-v2` + `rehearsal/pr15-rerere-proof-v2` deleted after proof. `rr-cache` retained locally for official rebase.

---

## 10. Live-check rehearsal (bounded compatibility)

*Not replacing v2.* A fresh integration base `rehearsal/final-38-live-check` built from current live `origin/main + PR20 + PR14 + live PR16 + PR13` will be constructed only if live heads drift beyond v2. Its PR15 replay will be compared against v2; fewer/more conflicts will be recorded. v2 remains the historical oracle.

---

## 11. Stale test cleanups — verified at `34cdcac`

- **Overclaimed freshness/reuse test name:** cleaned. Current test is `test_freshness_field_uses_authoritative_enum_and_emitted_values_validate` (proves field typing, not reuse) and `test_freshness_rejects_arbitrary_value`, `test_freshness_authoritative_m8` — no “reuse” overclaim.
- **Duplicate wall-clock assertion:** cleaned. `test_fingerprint_excludes_wall_clock` (lines 408-428) asserts five distinct facts without duplication: `v1.generated_at != v2.generated_at`, `v1.generated_at == first.isoformat()`, `v2.generated_at == second.isoformat()`, `v1.fingerprint == v2.fingerprint`, `v1.to_canonical_bytes() == v2.to_canonical_bytes()`.

No corrective commit to official PR #15 required for these.

---

## 12. Official rebase procedure (after PR #13 merges and owner authorizes)

1. `git fetch origin --prune`
2. Verify main contains expected prerequisite heads (see §7).
3. Verify safety tag: `git rev-parse pr15-pre-final-rebase-34cdcac^{commit}` == `34cdcac6b3f8693944876059704db3aabd5af521`
4. Verify v2 refs still exist locally and remotely: `git rev-parse rehearsal/final-38-v2 rehearsal/pr15-final-38-v2` + `git ls-remote --heads origin`
5. Verify rerere: `git config --get rerere.enabled` == `true` and `.git/rr-cache` non-empty
6. `git checkout agent/product-manchester-activation` (should be at `34cdcac`)
7. Optionally `git tag -a pr15-pre-final-rebase-34cdcac-live-$(date +%Y%m%d) HEAD`
8. `git rebase origin/main` — expect five conflicts (see §4)
9. Allow rerere to propose resolutions; **manually compare each** against `rehearsal/pr15-final-38-v2` (`git show rehearsal/pr15-final-38-v2:<path>`)
10. Resolve any new conflicts semantically (do not wholesale `ours`/`theirs`)
11. Derive page count: `python -c "from traffictwin.ui.labels import UiPage; print(len(UiPage))"` → expect **38**
12. Run integrated boundary (serial, no `pytest -n`):
    - Manchester unit/UI, Portfolio unit/UI, Consequence unit/UI/cache, Home/Guided, Navigation, Cross-page, Accessibility
    - `--collect-only` first, report distinct totals (no “279+”)
13. Run gates: `uv run --no-sync ruff check .` ; `uv run --no-sync ruff format --check .` ; `uv run --no-sync mypy` ; `uv lock --check` ; `git diff --check`
14. Compare tree: `git diff rehearsal/pr15-final-38-v2` / `git rev-parse <REF>^{tree}` — substantive product tree must match v2 (modulo any new live-head drift, recorded)
15. `git push --force-with-lease=refs/heads/agent/product-manchester-activation:34cdcac6b3f8693944876059704db3aabd5af521 origin HEAD:agent/product-manchester-activation`
16. Keep `rehearsal/final-38-v2` + `rehearsal/pr15-final-38-v2` + `rr-cache` until Claude 5 final exact-head review completes; only then optionally delete.

> **NEVER delete v2 rehearsals before rebase.** Earlier instruction variant “delete rehearsals before rebase” was wrong.

---

## 13. What this packet is NOT

- Not on official PR #15. Official remains at `34cdcac` (37 pages).
- Not a merge or Ready-mark.
- Not a claim that official is already 38 pages.
- Not a replacement for live-head verification at rebase time.

---

## Appendix — command log for this packet

```
git fetch origin --prune
gh pr view 15/13/14/16/20 --json state,isDraft,mergeable,headRefOid,baseRefName
git rev-parse origin/main agent/product-manchester-activation rehearsal/final-38-v2 rehearsal/pr15-final-38-v2
git show agent/product-manchester-activation:src/traffictwin/ui/manchester_evidence_hub.py | grep -c computed_field
git config rerere.enabled true; git config rerere.autoupdate true
git tag -a pr15-pre-final-rebase-34cdcac 34cdcac -m "..."; git push origin refs/tags/pr15-pre-final-rebase-34cdcac
git push origin rehearsal/final-38-v2 rehearsal/pr15-final-38-v2
git branch -D rehearsal/final-38 rehearsal/pr15-final-38 tmp-pr13
git worktree list --porcelain; git branch -vv; git log --oneline --decorate --graph --all -n 120
git diff --name-only 48e705b 48e705b  # PR16 audit
```

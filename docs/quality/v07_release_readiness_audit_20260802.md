# v0.7 technical release-readiness audit

## Status and boundary

- Phase: 182
- Date: 2 August 2026
- Standing: engineering verification only
- Gate-F acceptance: not claimed
- Package/tag/publication changes: prohibited

This audit exercises every release-readiness check that is safe without owner release authority.
It deliberately leaves the package at the current development version, creates no tag, publishes
nothing, and operates only on temporary synthetic workspaces or the immutable `v0.6.0` checkout.

## Owned paths

- `docs/quality/v07_release_readiness_audit_20260802.md`
- `docs/integration/evidence/side_by_side_check_20260802_phase182.json`
- `docs/v07_release_compatibility.md`
- `docs/index.md`
- `docs/implementation-status.md`
- `docs/current_progress_v0_7.md`
- `CHANGELOG.md`
- `AGENTS.md`

## Planned checks

1. Run the release reconciliation, compatibility, migration, productisation and CLI tests.
2. Run the standalone synthetic release smoke and dependency-lock check.
3. Export a clean archive of the current commit, regenerate all reference JSON twice there, and
   compare both generations with each other and the committed catalogue.
4. Build source and wheel distributions from the clean archive, install the wheel into an isolated
   Python 3.12 environment, and run package/CLI import smokes.
5. Run the immutable `v0.6.0` checkout beside v0.7 with separate environments, ports, workspaces
   and registries; publish only the path-free engineering receipt.
6. Confirm that no final v0.7 tag exists and that the working package version remains deliberately
   unreleased while formal capabilities and external decisions remain open.

## Acceptance

All checks above must pass; temporary files must remain outside the repository; tracked generated
references must stay byte-identical; no private path or credential may enter the receipt; and the
repository worktree must contain only the exact owned documentation/evidence paths.

## Results

| Check | Result |
|---|---|
| Release reconciliation, compatibility, migration, productisation and CLI tests | 58 passed |
| Standalone synthetic release smoke | Passed |
| Dependency lock | 91 packages resolved; check passed |
| Generated-reference regeneration | 69 files total, including 65 parsed JSON files; two isolated generations and the committed catalogue were byte-identical |
| Generated-reference aggregate digest | `46ca020ac4631a4c1aa868ba93e5bdd22e0efa2c9a2989b9c15ed026bda6afc9` |
| Clean source distribution | Built; SHA-256 `f08b8510f8e5882f691ec487ccb6d6e402f1d46d01a20eedebe043fb785678ba` |
| Clean wheel | Built and installed under isolated CPython 3.12.13; SHA-256 `9a52bbdc8d8de7a23f5ae9d637a68f5dff378a8e404378c1dde70436786a9f25` |
| Installed-package smokes | Import/version, synthetic preset catalogue, read-only doctor and release status passed |
| v0.6.0/v0.7 coexistence | Both isolated servers returned HTTP 200; registries were distinct and byte-unchanged |
| Final v0.7 tag | Absent, as required while release gates remain incomplete |

The installed doctor was healthy for all required checks. Optional Playwright, Graphviz, TOS
permission and direct/asynchronous launch remained honestly unavailable or blocked and did not
make the required runtime unhealthy. The package and release-status surfaces both reported
`0.6.0`; Phase 182 records that unresolved version reconciliation instead of silently asserting a
v0.7 release.

The path-free coexistence receipt is
[`side_by_side_check_20260802_phase182.json`](../integration/evidence/side_by_side_check_20260802_phase182.json).
It binds the immutable v0.6.0 commit and Phase-181 v0.7 parent. No real registry, workspace,
migration, tag, package publication or deployment was touched.

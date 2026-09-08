# Research-archive CI maintenance — 9 September 2026

This local maintenance change starts from `477304f7f988f7d5d5ea5ae21d0e49eed1429e5a` on `maintenance/immutable-research-ci-2026-09-09`. It is separate from the dissertation edit. No historical file, scientific runtime, dependency lock, product implementation or existing test was changed. No push or merge was performed.

## Verified problem and narrow repair

The latest inspected [hosted run 34290052337](https://github.com/Abdulla4akash/traffictwin/actions/runs/34290052337), on that baseline, failed the Python 3.12 Ruff formatting step: **83 files would be reformatted; 1,371 were already formatted**. Lint, mypy, tests and subsequent steps were skipped. The parallel Python 3.11 job was cancelled during installation. This is a failed hosted run; local success below does not change its status.

The failing files are in eight completed, dated research packages. Reformatting their snapshots, analysis and reproduction scripts would break recorded byte identities. `pyproject.toml` now enumerates only those eight roots under `extend-exclude`. The whole `docs` tree remains checked, including the new `docs/dissertation/editorial_final_2026-09-09` package and future packages. Maintained code in `src`, `tests` and `scripts` remains checked. No lint rule was disabled and no maintained source was reformatted.

The new CI step runs [verify_research_archives.py](../../scripts/verify_research_archives.py) before Ruff. Its [manifest](immutable_research_archives_2026-09-09.json) records all **938 tracked files / 29,009,151 bytes** in the exclusions, including 87 Python files and the existing seals, receipts, manuscripts, figures and PDFs. Every digest was read from the baseline files; no manifest is regenerated automatically by CI. Changed bytes, absent files, additional files, symlinks and a different exclusion list fail the check. Ordinary Python caches are ignored. This preserves historical identity; it does not validate scientific conclusions, establish raw-array availability or create a backup. New maintained work belongs outside these archived roots; a deliberate archive-policy change needs an explicit reviewed successor.

| Exact frozen package (under `docs/`) | Existing evidence for immutable status | Files |
|---|---|---:|
| `dissertation/complete_draft_2026-09-07` | Historical complete draft with `VALIDATION.json` and PDF receipt | 17 |
| `dissertation/substantive_revision_2026-09-07` | Delivered revision, `VALIDATION.json`, `SHA256SUMS` | 23 |
| `dissertation/gap_closure_2026-09-08` | Delivered revision, source bindings, `VALIDATION.json`, `SHA256SUMS` | 143 |
| `dissertation/production_mechanism_2026-09-08` | Completed proof/diagnostics package, `VALIDATION.json`, `SHA256SUMS` | 45 |
| `dissertation/empirical_extension_2026-09-08` | Completed timing/type analysis, original disabled seal, `VALIDATION.json`, `SHA256SUMS` | 57 |
| `dissertation/joint_confirmation_2026-09-08` | Reviewed 32-run package, execution seal, compact receipts, `VALIDATION.json` | 245 |
| `evaluation/common_target_mechanism_audit_2026-09-07` | README identifies completed archive; `ARCHIVE_INVENTORY.json`, `SHA256SUMS` | 15 |
| `evaluation/vec_followup_2026-09-07` | README identifies completed archive; `ARCHIVE_INVENTORY.json`, `SHA256SUMS` | 393 |

The existing historical integrity scripts and their receipts remain unchanged. The added gate reads compact repository files only; it never imports archived code, launches an evaluator or touches private raw-output roots.

## Bounded local checks actually performed

Existing product environment: CPython **3.12.13**, macOS 26.4.1 arm64; Ruff **0.15.22**, mypy **2.3.0**, pytest **9.1.1**, pytest-cov **7.1.0**, all matching `uv.lock`. No packages were installed or upgraded. The lock-consistency command used the existing uv-selected CPython 3.13.5 resolver and did not change the lock.

| Check | Actual result |
|---|---|
| `python scripts/verify_research_archives.py` | Passed: 938 files, eight roots, no differences |
| `ruff format --check .` | Passed: 1,370 files already formatted |
| `ruff check .` | Passed: no lint findings in maintained scope |
| `mypy scripts/verify_research_archives.py tests/unit/test_research_archive_integrity.py` | Passed: two source files; expected unused-global-override notes |
| `python -m pytest -q tests/unit/test_research_archive_integrity.py tests/unit/test_quality_snapshot_script.py` | **31 passed, 0 failed, 0 skipped**, 0.09 seconds; bounded selection, not full suite |
| Four-file temporary Ruff discovery probe | New editorial/source/scripts files included; named frozen fixture excluded |
| `uv lock --check` | Passed, 91 packages resolved; lock unchanged |
| `git diff --check` | Passed |

The selected test files and root pytest hook were inspected before execution. New tests mutate tiny temporary file fixtures; the existing quality-snapshot tests use fake command runners. They perform no simulations, benchmark, service write or raw-data analysis. The temporary Ruff discovery receipt initially encountered the macOS `/var` versus `/private/var` spelling; canonicalising that temporary root resolved the harness-only issue. No repository correction or weakened invariant was needed.

Command logs and machine-readable receipts remain at `/Users/akashx/TrafficTwinAudit/archive-ci-2026-09-09/`. This is a local audit folder, not an off-machine backup. The manifest SHA-256 is `259675e6958f615124235fbade4cf0be306dbf81c8018580dd106cd84ff2cc3a`.

## Remaining boundary

The full repository suite, global mypy, build, demo smoke and hosted workflow were **not run in this maintenance task**. Earlier environment-related full-suite failures remain separate evidence; this patch does not claim to resolve them. A future authorised push must obtain a fresh hosted result. The local patch needs independent review before promotion; the user's present instruction prohibits push and merge. Historical scientific validity, dissertation approval, assessment-specific AI-use decisions and raw-data backup approval are unaffected.

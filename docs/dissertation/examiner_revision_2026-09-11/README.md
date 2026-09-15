# TrafficTwin — additive examiner-facing revision, 11 September 2026

**A compiled revision, not a certified submission copy.** Read [submission gates](SUBMISSION_GATES.md) before submitting. No new scientific experiment, actor training, E3 workload or raw-data transfer was performed. My 15 September authorship and verification confirmations are recorded in AUTHOR_ACTIONS.md; AI-use permission remains pending.

## Manuscript and evidence

[PDF](TrafficTwin_Dissertation.pdf) · [Markdown](TrafficTwin_Dissertation.md) · [LaTeX](TrafficTwin_Dissertation.tex) · [revision validation](document/REVISION_VALIDATION.json) · [change record](REVISION_REPORT.md)

`TrafficTwin_Dissertation.md` is the single source for academic body, Declaration and Acknowledgements; the converter generates their TeX placement. The source base is `1e01b755b8b633f43c9c7bb6fdd0d75beb6469e8`. All earlier packages and experiments remain unchanged. This package restructures the 9 September manuscript, adds the eight-block plot, measured software inventory and actual Streamlit capture, and separates author-only completion from scientific interpretation. It retains the original Abstract, protected numerical tables, algorithms, proposition and exact-model material.

The [compact verifier receipt](evidence/COMPACT_CHECKS.json) recomputes existing 32-cell outcomes and simultaneous intervals; it is not a rerun or fresh raw-task audit. The [descriptive split](evidence/DESCRIPTIVE_SPLIT.json) uses equal block weights and unrounded arm differences: 84.7586% for ingress→round-robin and 15.2414% for round-robin→per-task. These are not causal mechanism shares.

The [actual product capture](evidence/CAPTURE.json) comes from GitHub Actions run `34614459294`, artifact `10269522813`, with the pinned source. Its browser check covered five routes. The accompanying Ruff and 938-file archive checks passed. Hosted branch run [34631121188](https://github.com/Abdulla4akash/traffictwin/actions/runs/34631121188), 11 September 2026, completed Python 3.12 with **8,301 collected, 8,179 passed, 56 failed and 66 skipped**; Python 3.11 was cancelled. Five failures are tier-4 UI text assertions; the others concern provenance/ancestry, artifacts and other UI checks. [Per-file counts and failing test IDs](evidence/HOSTED_TEST_RESULT_2026-09-11.json) preserve the complete scope. Source-line totals are project inventory, not a measure of personal authorship.

## Build and check

From the repository root, in a document environment containing Python 3.11+, MarkdownIt, NumPy, SciPy, Matplotlib, PyMuPDF, Inkscape, XeLaTeX and latexmk:

```sh
D=docs/dissertation/examiner_revision_2026-09-11
python "$D/document/make_assets.py"
python "$D/document/convert_source.py"
(cd "$D" && latexmk -xelatex -interaction=nonstopmode -halt-on-error TrafficTwin_Dissertation.tex)
python docs/dissertation/joint_confirmation_2026-09-08/document/verify_results.py --output "$D/evidence/COMPACT_CHECKS.json"
python "$D/document/validate_revision.py"
ruff check "$D/document"
ruff format --check "$D/document"
```

The manuscript uses preconverted PDF figures through `includegraphics`; it does not need shell escape or Inkscape during TeX compilation. Inkscape is needed only to regenerate the five vector conversions. No font files are redistributed.

The final word count is emitted by the converter and printed under the contents. Main text, Abstract, tables, equations and pseudocode are included; captions, references, appendices and front matter are excluded. The ending audit is an explicit lexical screen, not a semantic marking rubric or proof of prose quality.

## What remains outside automated completion

I confirmed my design decisions, AI-assisted implementation and personal modifications, and completion of all eight author checks on 15 September 2026. AI-use permission, examiner access, award/student details, signature and prescribed declaration/copyright wording remain open. A morning RSU coordinate figure is authenticated; an incident street/layout figure is not fabricated. The bibliography contains 25 entries, but registration metadata for the two additional Fan papers is not a full-text methodological review.

The [video materials](video/RECORDING_PLAN.md) and copy-only preservation script support the remaining tasks; neither means the assessed video or an off-machine backup exists. The original raw folder must remain intact. No merge or independent approval is implied by this package.

## 15 September revision

- **C.1–C.5, C.8–C.9 / D.1–D.3:** first-person design and implementation attribution, full-name convention, Dr Sampaio's report-age suggestion, dated author confirmation and completed exercises; permission remains a separate gate.
- **C.6–C.7:** evaluator-documented common-target/two-choice semantics, two unevaluated Table 3 rows, first future-work comparator and Table 10 limit; raw-array retention wording and a package-local claim map. `dla_p2c` was not run; the sealed arms, contrast family and numerical results are unchanged.
- **C.10–C.14:** verified hosted test outcomes including all failure classes, table-specific Reading captions, Manchester scenario provenance, added context and reflection, dual word counts, and Cho's 2026 issue details. Both Fan papers retain bibliographic verification only.
- **D.4–D.6:** revision report, NumPy/SciPy recording prerequisites, successful local compact-verifier receipt, source/PDF rebuild and acceptance receipts, current hashes and PR body. The assessed video remains unrecorded.

The requested C.10 failure classification was corrected from the hosted log: only five failures are in `tests/unit/ui/test_page_presentation_tier4.py`; all 56 are disclosed. No product assertion repair or new global-suite run is claimed.

### Build identity and acceptance

- Package method: **8,987 words** (table text and pseudocode included).
- Prose-only: **7,684 words** (same boundaries, excluding table bodies and pseudocode).
- XeLaTeX: **56 pages**, 38 document checks passed; zero overfull boxes, missing glyphs and unresolved references.
- All 56 pages rendered and inspected by the editing assistant; this is not independent review.
- Local compact verifier: 32 cells / eight blocks passed; no evaluator or raw-task reanalysis.
- Frozen archive gate: 938 files across eight roots passed; protected-path diff against `origin/main` is empty. `main` remains `1e01b755b8b633f43c9c7bb6fdd0d75beb6469e8`.
- Markdown SHA256: `84f8da436f571b68f921a3899f885858ed5dab019d092f737c030ec9c31bcced`.
- TeX SHA256: `d7954b0e53078183a25ea8a5768bc355d497248147ac18d2e4ff4709b6ab7a02`.
- PDF SHA256: `34d703633b631d9b90a01b88c682755be10ce4013809a805b2f62780fdbb9ece`.

See [acceptance results](evidence/ACCEPTANCE_2026-09-15.json), [local TeX log (trailing whitespace normalised)](evidence/latexmk-2026-09-15.log), [local compact receipt](evidence/LOCAL_COMPACT_CHECKS_2026-09-15.json) and [archive receipt](evidence/LOCAL_ARCHIVE_CHECK_2026-09-15.json). The original `revision_recipe.json` is the historical 11 September transfer recipe; ordinary builds use the current Markdown directly.

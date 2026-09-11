# TrafficTwin — additive examiner-facing revision, 11 September 2026

**A compiled revision, not a certified submission copy.** Read [submission gates](SUBMISSION_GATES.md) before submitting. No new scientific experiment, actor training, E3 workload, raw-data transfer or human approval is claimed.

## Manuscript and evidence

[PDF](TrafficTwin_Dissertation.pdf) · [Markdown](TrafficTwin_Dissertation.md) · [LaTeX](TrafficTwin_Dissertation.tex) · [revision validation](document/REVISION_VALIDATION.json) · [change record](REVISION_REPORT.md)

The source base is `1e01b755b8b633f43c9c7bb6fdd0d75beb6469e8`. All earlier packages and experiments remain unchanged. This package restructures the 9 September manuscript, adds the eight-block plot, measured software inventory and actual Streamlit capture, and separates author-only completion from scientific interpretation. It retains the original Abstract, protected numerical tables, algorithms, proposition and exact-model material.

The [compact verifier receipt](evidence/COMPACT_CHECKS.json) recomputes existing 32-cell outcomes and simultaneous intervals; it is not a rerun or fresh raw-task audit. The [descriptive split](evidence/DESCRIPTIVE_SPLIT.json) uses equal block weights and unrounded arm differences: 84.7586% for ingress→round-robin and 15.2414% for round-robin→per-task. These are not causal mechanism shares.

The [actual product capture](evidence/CAPTURE.json) comes from GitHub Actions run `34614459294`, artifact `10269522813`, with the pinned source. Its browser check covered five routes. The accompanying Ruff and 938-file archive checks passed. **8,301 tests were collected, not reported as 8,301 passing tests.** Source-line totals are project inventory, not a measure of personal authorship.

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

The candidate must confirm personal contributions and checks, assessment-specific AI permission, award/student details and prescribed declaration/copyright wording. A morning RSU coordinate figure is authenticated; an incident street/layout figure is not fabricated. The bibliography contains 25 entries, but registration metadata for the two additional Fan papers is not a full-text methodological review.

The [video materials](video/RECORDING_PLAN.md) and copy-only preservation script support the remaining tasks; neither means the assessed video or an off-machine backup exists. The original raw folder must remain intact. No merge or independent approval is implied by this package.

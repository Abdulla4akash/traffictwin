# TrafficTwin substantive dissertation revision

The complete editable manuscript is [TrafficTwin_Dissertation.md](TrafficTwin_Dissertation.md), with a newly built [PDF](TrafficTwin_Dissertation.pdf). This package revises the September starting draft; it does not replace historical scientific records. No upload, push, merge, publication, author approval or submission has occurred.

Delivered version: 8,640 counted words and 26 PDF pages, with every current page visually covered. One focused response to a separate AI critique corrected source-level scope and filled methodological gaps; no numerical mark was requested or assigned by the reviewer.

- [Revision report and initial ledger](REVISION_REPORT.md): substantive changes, remaining evidence limits and author decisions.
- [Claim-to-source map](CLAIM_SOURCE_MAP.md) and [reference-access record](REFERENCE_CHECK.md): what each inspected source supports and its limits.
- [Author-review checklist](AUTHOR_INPUTS.md): claims, algorithms, statistical assumptions, ownership, AI-use authority/disclosure and examiner access.
- [Current validation](VALIDATION.json), [arithmetic recalculation](ARITHMETIC.json), [page review](VISUAL_REVIEW.json) and [separate critique](REVIEW.md): distinguish the checks actually performed.

Working branch: `docs/dissertation-substantive-revision-2026-09-07`. Starting draft commit: `f91436af2b8f506b400d815947b3a87bda8cd3fd`; scientific evidence baseline: `04f3b6a95c7bc06c80ed95b54762f12861bba183`. The delivered local commit is recorded in the handover; file-level identities are in VALIDATION.json and SHA256SUMS.

## Document reproduction

Document tooling is isolated at `/Users/akashx/Downloads/diss_mat/traffictwin-revision-doc-tools/venv`; it is separate from all scientific runtimes. Python requirements are in requirements-pdf.txt. PDF generation also uses macOS Times New Roman/Arial font files; visual rendering uses Poppler. Paths in build_pdf.py identify these document dependencies explicitly.

Using that document environment, run `check_arithmetic.py`, `build_figures.py`, `build_pdf.py`, then `validate_document.py`. These scripts only read archived compact CSV/JSON summaries or document assets; they never import the evaluator, load raw task NPZ files, or run simulations. A rebuilt PDF requires a new current visual review: an old VISUAL_REVIEW.json hash will not pass the current-PDF gate.

Figures 1–2 are source-derived explanatory diagrams. Figure 3 is a constructed scheduling example. Figures 4–5 are new vector redraws of the same archived primary CSVs, with larger labels; the original historical figures remain unchanged. Figure 4 intervals preserve the original Bonferroni family; Figure 5 whiskers are descriptive draw minima/maxima.

## Word export and submission standing

No DOCX exists in this package. Current capability discovery found no managed workspace dependency loader/runtime required by the Documents skill, and no LibreOffice/soffice renderer. The export could not be started through a supported path. Pandoc is installed but is not the missing managed document runtime or visual renderer. This is an availability limitation, not a failed Word file passed off as complete; Markdown remains fully editable.

The manuscript openly records substantive Codex assistance. The actual COMP66060 assessment-specific AI category, individual component ownership, required submission declarations and marker access remain author decisions. The University policy record does not establish that this assessment permits substantive AI drafting. This package is for author review, not a claim of submission readiness.

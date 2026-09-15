# Dynamic Resource Management for Intelligent Transport Systems

**Six-point revision passes: 8,938 strict/package words / 7,738 prose-only words; 62-page PDF.** The title stays, with no subtitle. The draft PR remains open for review; [submission gates](SUBMISSION_GATES.md) remain separate.

[PDF](TrafficTwin_Dissertation.pdf) · [Markdown source](TrafficTwin_Dissertation.md) · [generated TeX](TrafficTwin_Dissertation.tex) · [six-point review](EDITORIAL_FIX_REVIEW_2026-09-15.md) · [revision history](REVISION_REPORT.md) · [validation](document/REVISION_VALIDATION.json)

## Current changes

- Main tables 10 → 8 and 11 → 9; Table 3a retained. Table bodies unchanged.
- Mitzenmacher (2000) and Kovalenko et al. (2019) added as references 45–46 in Sections 1.2 and 3.5. Primary texts support stale-information herding and a federation comparison under different assumptions. An identical accounting method or opposite overall conclusion is not claimed.
- Two short 1.1 transition paragraphs merged; Figure 2 with its introduction and caption moved verbatim to 2.3; WHO figure linked to timely information sharing as motivation.
- Overall conclusion moved verbatim from end of 4.4 to open Section 4.
- PDF title and author metadata populated. AUTHOR_ACTIONS now records 3GPP reference 42, version 16.2.0, as added after its earlier omission.

The pre-review manuscript is `7075b2576292cc9a98854bf5664449df66617b96`. The research/product source base remains `1e01b755b8b633f43c9c7bb6fdd0d75beb6469e8`. Markdown is the source. No scientific runs, frozen-package edits or main changes.

## Counts and checks

| Stage | Package count (headline) | Prose-only count |
|---|---:|---:|
| Baseline `9b49efc` | 9,180 | 7,877 |
| Option B `2c29392` | 9,388 | 8,017 |
| Closing and title `7075b25` | 8,914 | 7,714 |
| Current six-point revision | **8,938** | **7,738** |
| Acceptance | ≤ 8,950 | ≥ 7,600 |

The contents page prints strict first. The package method includes Abstract, main headings/body, table text, equations and pseudocode; it excludes captions, references, appendices and front matter. Prose-only additionally excludes table bodies and pseudocode. [WORD_COUNT.json](document/WORD_COUNT.json) records both.

- `validate_revision.py`: **178/178 passed**; `validate_option_b.py`: **131/131 preservation guards passed**.
- All twenty pre-review table bodies preserved; all equations, algorithms and the proposition unchanged.
- Sections 1.2 and 3.5 have only the newly authorised literature changes. A pinned [operation ledger](evidence/EDITORIAL_FIX_OPERATIONS_2026-09-15.json) recovers `7075b25` exactly before all earlier protection checks run. Sections 3.2–3.4 and 3.6 remain byte-identical to the pre-review manuscript.
- Earlier appendix moves and pointers remain verbatim. Historical Table 8 → D2 and Table 9 → A1 remain in place; their former main numbers are now assigned to validity limits and objective verdicts. [Historical moved-content map](OPTION_B_CLOSE_REVIEW.md).
- [Six mutation probes](evidence/EDITORIAL_FIX_MUTATION_CHECKS_2026-09-15.json) detect concrete preservation failures.
- PDF: **62 pages**, all rendered and inspected. Zero overfull boxes, missing glyphs, undefined references or duplicate captions. Title and author metadata verified. Ruff lint/format passed for all six document Python files.

## Primary sources and ethics

References 45–46 have primary-text and Crossref checks with URLs, locators and hashes in [current source registration](evidence/reference-registration-editorial-fixes-2026-09-15.json). Reference 46's first author is Anna Kovalenko; Hussain is second. The cited results do not establish an identical admission/accounting contract with TrafficTwin.

3GPP TS 22.186 v16.2.0 gives 100 ms for automated-driving information sharing (Table 5.3-1, R.5.3-004/005) and 500 ms for platooning reporting (Table 5.2-1, R.5.2-008). WHO's 1.19 million road-death estimate retains **2021**. [Closing source registration](evidence/reference-registration-option-b-close-2026-09-15.json) preserves their primary verification. References 1–44 remain byte-identical in this round.

The owner confirms completing the UoM Ethics Decision Tool and that approval is not required. This remains an author check, **not an independently observed result or formal approval**; see [confirmation](evidence/ETHICS_DECISION_OWNER_CONFIRMATION_2026-09-15.json). Assistant source verification does not certify the owner's reading. Earlier dated receipts remain historical.

## SHA256

- TrafficTwin_Dissertation.md: `f3867b5ff9d2937faab842b14409914e2747452e1cc2c5093961b2860f394537`
- TrafficTwin_Dissertation.tex: `ab1cd44adecfa4f8feb82783c1908d12e986c234275a0df4596b7ded1b0fa524`
- TrafficTwin_Dissertation.pdf: `33244964119ca80406200004460ab335cd446bae26213356facf6375134f6dcd`

## Build and check

Use the document environment with MarkdownIt, NumPy, SciPy, Matplotlib, PyMuPDF, XeLaTeX and latexmk. Preservation baselines `9b49efc`, `2c29392` and `7075b25` must be available. Existing PDF figures require no conversion during an ordinary rebuild.

```sh
pkg_dir=docs/dissertation/examiner_revision_2026-09-11
python "$pkg_dir/document/convert_source.py"
latexmk -cd -xelatex -interaction=nonstopmode -halt-on-error "$pkg_dir/TrafficTwin_Dissertation.tex"
python "$pkg_dir/document/validate_option_b.py"
python "$pkg_dir/document/validate_revision.py"
ruff check "$pkg_dir/document"
ruff format --check "$pkg_dir/document"
```

[Current build log](evidence/latexmk-editorial-fixes-2026-09-15.log) · [grep table](evidence/EDITORIAL_FIX_GREP_2026-09-15.json) · [acceptance](evidence/EDITORIAL_FIX_ACCEPTANCE_2026-09-15.json). Prior [compact arithmetic](evidence/OPTION_B_CLOSE_COMPACT_CHECKS.json) and [archive integrity](evidence/OPTION_B_CLOSE_ARCHIVE_CHECK.json) receipts remain historical. The original `revision_recipe.json` is historical; ordinary builds use current Markdown.

## Existing boundaries

Hosted run 34631121188's 8,301 collected tests, 8,179 passes, **56 failures**, and 66 skips remain disclosed in the manuscript and [failure inventory](evidence/HOSTED_TEST_RESULT_2026-09-11.json). No fresh global test suite or usability result is claimed. E3 remains unexecuted. Author confirmations are in [AUTHOR_ACTIONS.md](AUTHOR_ACTIONS.md); assessed video, institutional front matter, AI permission and examiner access/backup requirements remain in [SUBMISSION_GATES.md](SUBMISSION_GATES.md). No merge or formal independent integration approval is implied.

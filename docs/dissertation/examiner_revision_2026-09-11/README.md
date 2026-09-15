# TrafficTwin — examiner revision, Option B closed, 15 September 2026

**Closing revision passes: 8,914 strict/package words / 7,714 prose-only words; 62-page PDF.** The count meets ≤8,950 and ≥7,600 respectively. The draft PR remains open for review. Existing [submission gates](SUBMISSION_GATES.md) remain separate.

[PDF](TrafficTwin_Dissertation.pdf) · [Markdown source](TrafficTwin_Dissertation.md) · [generated TeX](TrafficTwin_Dissertation.tex) · [closing review and moved-content map](OPTION_B_CLOSE_REVIEW.md) · [revision history](REVISION_REPORT.md) · [validation](document/REVISION_VALIDATION.json)

## Changes and evidence

Table 9 is now Appendix A/Table A1. Service-time, checkpoint and V2V paragraphs move verbatim to Appendix F; the constructed fractional-enqueue example and partition invariant move to Appendix B. Five source pointers replace those locations. The four specified duplicate sentences are removed from the prior Option B additions. The stakes paragraph names both verified 3GPP requirement classes and removes the owner placeholder. The ethics paragraph records the author's confirmed, dated decision-tool check, with reference 44.

The research/product source base remains `1e01b755b8b633f43c9c7bb6fdd0d75beb6469e8`. Text-preservation baselines are `9b49efc34a482e5abaab804efcd857b368087c52` for Option B and `2c29392cbf04bf060aacb0f03f1fbb900842d54a` for closing. Markdown is the source. No scientific runs, frozen-package edits or main changes.

## Counts and checks

| Stage | Package count (headline) | Prose-only count |
|---|---:|---:|
| Baseline `9b49efc` | 9,180 | 7,877 |
| Previous Option B `2c29392` | 9,388 | 8,017 |
| Final closing revision | **8,914** | **7,714** |
| Closing acceptance | ≤ 8,950 | ≥ 7,600 |

The contents page prints strict first. The package method includes Abstract, main headings/body, table text, equations and pseudocode; it excludes captions, references, appendices and front matter. Prose-only additionally excludes table bodies and pseudocode. [WORD_COUNT.json](document/WORD_COUNT.json) records both.

- `validate_revision.py`: **137/137 passed**; `validate_option_b.py`: **93/93 preservation guards passed**.
- Section 1.2 byte-identical to `9b49efc`; Sections 3.2–3.6 byte-identical to `2c29392`.
- All twenty pre-closing table bodies preserved; Table 9 → A1, earlier Table 8 → D2. All equations, algorithms and the proposition unchanged.
- [Eleven mutation probes](evidence/OPTION_B_CLOSE_MUTATION_CHECKS.json) detect concrete preservation failures.
- [Compact arithmetic](evidence/OPTION_B_CLOSE_COMPACT_CHECKS.json): 32 cells / eight blocks passed. [Archive integrity](evidence/OPTION_B_CLOSE_ARCHIVE_CHECK.json): 938 files / eight roots passed.
- PDF: **62 pages**, all rendered and inspected. Zero overfull boxes, missing glyphs, undefined references or duplicate captions. Ruff lint/format passed for all six document Python files.

## Primary sources and ethics

3GPP TS 22.186 v16.2.0 gives 100 ms for automated-driving information sharing between UE and RSU (clause 5.3, Table 5.3-1, R.5.3-004/005) and 500 ms for platooning reporting including UE–RSU (clause 5.2, Table 5.2-1, R.5.2-008). The manuscript takes B.3's verified-500-ms branch and explicitly names both classes. WHO's 1.19 million road deaths estimate retains **2021**. Primary PDFs, version, pages, hashes and methods are recorded in [closing source registration](evidence/reference-registration-option-b-close-2026-09-15.json). No new DOI.

The owner confirms completing the UoM Ethics Decision Tool and that approval is not required. This is recorded as an author check, **not an independently observed result or formal approval**; see [confirmation](evidence/ETHICS_DECISION_OWNER_CONFIRMATION_2026-09-15.json). References 1–41 keep their text/identifiers, 42 gains the platooning locator, 43 is unchanged and 44 cites the ethics tool. Earlier dated source receipts remain historical.

## SHA256

- TrafficTwin_Dissertation.md: `938213d74d9093008a6493dd992fa1157fe4758f266c59f5f2dfd78e8314b4f3`
- TrafficTwin_Dissertation.tex: `57e2133857491eed28ba1e83da04c2affaacfb95108d26f184de45271bf35f65`
- TrafficTwin_Dissertation.pdf: `f42d02333363aad5450210a6df5968dfd7a5a4905ce03fa920fda30aaa7cf429`

## Build and check

Use the document environment with MarkdownIt, NumPy, SciPy, Matplotlib, PyMuPDF, XeLaTeX and latexmk. Both Git baselines must be available. Existing PDF figures require no conversion during an ordinary rebuild.

```sh
pkg_dir=docs/dissertation/examiner_revision_2026-09-11
python "$pkg_dir/document/convert_source.py"
latexmk -cd -xelatex -interaction=nonstopmode -halt-on-error "$pkg_dir/TrafficTwin_Dissertation.tex"
python docs/dissertation/joint_confirmation_2026-09-08/document/verify_results.py --output "$pkg_dir/evidence/OPTION_B_CLOSE_COMPACT_CHECKS.json"
python scripts/verify_research_archives.py
python "$pkg_dir/document/validate_option_b.py"
python "$pkg_dir/document/validate_revision.py"
ruff check "$pkg_dir/document"
ruff format --check "$pkg_dir/document"
```

[Build log](evidence/latexmk-option-b-close-2026-09-15.log) · [grep table](evidence/OPTION_B_CLOSE_GREP.json) · [closing operation ledger](evidence/OPTION_B_CLOSE_OPERATIONS.json) · [acceptance](evidence/OPTION_B_CLOSE_ACCEPTANCE.json). The original `revision_recipe.json` is historical; ordinary builds use current Markdown.

## Existing boundaries

Hosted run 34631121188's 8,301 collected tests, 8,179 passes, **56 failures**, and 66 skips remain disclosed in the manuscript and [failure inventory](evidence/HOSTED_TEST_RESULT_2026-09-11.json). No fresh global test suite or usability result is claimed. E3 remains unexecuted. Author confirmations are in [AUTHOR_ACTIONS.md](AUTHOR_ACTIONS.md); assessed video, institutional front matter, AI permission and access/backup requirements remain in [SUBMISSION_GATES.md](SUBMISSION_GATES.md). No merge or formal independent integration approval is implied.

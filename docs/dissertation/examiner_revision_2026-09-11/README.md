# TrafficTwin — examiner revision, Option B, 15 September 2026

**Draft blocked by word count: 9,388 package words / 8,017 prose-only words.** All permitted moves, including Table 8 → Appendix D/Table D2, are applied. The package count remains **388 over 9,000**; content reduction stopped as instructed. This is a compiled review draft. Read [submission gates](SUBMISSION_GATES.md) before submitting.

## Manuscript and review record

[PDF](TrafficTwin_Dissertation.pdf) · [Markdown source](TrafficTwin_Dissertation.md) · [generated TeX](TrafficTwin_Dissertation.tex) · [Option B review and stop report](OPTION_B_REVIEW.md) · [revision history](REVISION_REPORT.md) · [validation](document/REVISION_VALIDATION.json)

The manuscript's research/product source base remains `1e01b755b8b633f43c9c7bb6fdd0d75beb6469e8`. Option B's text-preservation baseline is `9b49efc34a482e5abaab804efcd857b368087c52` on `docs/dissertation-examiner-revision-2026-09-11`. Markdown remains the single source for body, Declaration and Acknowledgements. No scientific run, actor training, raw-task reanalysis or E3 workload was performed.

Added sections 2.9 and 4.2, ethics, objective/RQ tags, proposition remark, Setting/Results labels and verified stakes context. The [evidence map](evidence/OPTION_B_EVIDENCE_MAP.md) records the source of each addition. The [operation ledger](evidence/OPTION_B_OPERATIONS.json) holds every verbatim move, pointer and SHA256. Section 1.2 is byte-identical; the explicit remark and cross-reference exceptions for 3.2–3.6 are listed in the review report. Existing numerical bodies and scientific figures are unchanged.

## Counts and build identity

| Stage | Package count (headline) | Prose-only count |
|---|---:|---:|
| Baseline `9b49efc` | 9,180 | 7,877 |
| A + B.1–B.4 | 9,452 | 7,991 |
| After B.5 Table 8 → D2 | 9,388 | 8,017 |
| Acceptance | ≤ 9,000 | ≥ 7,600 |

The contents page prints the package count first. The existing package method includes Abstract, main headings/body, table text, equations and pseudocode; it excludes captions, references, appendices and front matter. Prose-only additionally excludes table bodies and pseudocode. User bounds are now package ≤ 9,000 and prose-only ≥ 7,600.

- PDF: **63 pages**; all pages rendered for visual inspection.
- Validator: **91/92 passed**, with only the word-count gate failing. A nonzero validator exit is the expected outcome for this draft.
- Zero overfull boxes, missing glyphs, unresolved references or duplicate captions.
- All 19 baseline table bodies remain identical; the new table is 3a and the former Table 8 is D2.
- [Seven mutation probes](evidence/OPTION_B_MUTATION_CHECKS.json) detected deliberate preservation violations.
- [Compact result check](evidence/OPTION_B_COMPACT_CHECKS.json): 32 cells / eight blocks passed.
- [Frozen archive check](evidence/OPTION_B_ARCHIVE_CHECK.json): 938 files across eight roots passed; no changes outside this revision package.

- TrafficTwin_Dissertation.md SHA256: `307862fcc37558df585b0e867a0766aa3616cd810ee0595df398dd3ffaf0cf89`.
- TrafficTwin_Dissertation.tex SHA256: `10a446730304195d815e4e02e598daafbc6c3bccde37a1f7a3240a833967750b`.
- TrafficTwin_Dissertation.pdf SHA256: `616f27c4d3b54173761419fe0e4cbef5bf8ab8f410f5975888e400b9a70d4505`.

## Primary-source verification

The bibliography now contains 43 entries. References 1–41 retain their baseline identifiers; the new standard and WHO report are 42–43 so protected Section 1.2 is unchanged. [Primary-document registration](evidence/reference-registration-option-b-2026-09-15.json) records access date, version, pages and download hashes. Existing [Crossref and JAX receipts](evidence/reference-registration-2026-09-15.json) remain historical evidence.

The primary WHO report verifies **an estimated 1.19 million road traffic deaths in 2021**, printed p. 4 and executive summary p. viii. The estimation year is explicit in the manuscript.

The primary ETSI PDF of **3GPP TS 22.186 v16.2.0** verifies **100 ms** for automated-driving information sharing between UE and RSU (clause 5.3, Table 5.3-1, requirements R.5.3-004/005, printed p. 10). **No advanced-driving requirement class spanning 100–500 ms was verified.** In that advanced-driving table, 500 is a communication range in metres for R.5.3-006. A 500 ms latency requirement belongs to platooning reporting, R.5.2-008, Table 5.2-1, printed p. 9. The manuscript uses the verified 100 ms context, distinguishes communication requirements from task deadlines, and leaves the requested bracketed owner note. Both primary PDFs were downloaded, their relevant text read and page images inspected by the editing assistant; owner reading is not claimed. The official document title is used. No new DOI was introduced; the two primary-document verifications are appended to reference-registration.json and separately recorded in reference-registration-option-b-2026-09-15.json.

## Build and check

From the repository root, use the document environment with MarkdownIt, NumPy, SciPy, Matplotlib, PyMuPDF, XeLaTeX and latexmk. Existing PDF figures require no conversion during an ordinary rebuild.

```sh
pkg_dir=docs/dissertation/examiner_revision_2026-09-11
python "$pkg_dir/document/convert_source.py"
latexmk -cd -xelatex -interaction=nonstopmode -halt-on-error "$pkg_dir/TrafficTwin_Dissertation.tex"
python docs/dissertation/joint_confirmation_2026-09-08/document/verify_results.py --output "$pkg_dir/evidence/OPTION_B_COMPACT_CHECKS.json"
python scripts/verify_research_archives.py
python "$pkg_dir/document/validate_revision.py"
ruff check "$pkg_dir/document"
ruff format --check "$pkg_dir/document"
```

`validate_revision.py` requires the Git baseline commit to be available and currently exits 1 solely for the word-count gate. The [build log](evidence/latexmk-option-b-2026-09-15.log) and [grep table](evidence/OPTION_B_GREP.json) support review. The original `revision_recipe.json` is the historical transfer recipe; ordinary builds use current Markdown.

## Existing evidence and remaining gates

The actual [product capture](evidence/CAPTURE.json) and [inventory](evidence/ARTEFACT_INVENTORY.json) remain tied to their inspected source. Hosted run [34631121188](https://github.com/Abdulla4akash/traffictwin/actions/runs/34631121188) completed Python 3.12 with 8,301 collected, 8,179 passed, 56 failed and 66 skipped; Python 3.11 was cancelled. Only five failures are tier-4 UI text assertions; the complete [failure inventory](evidence/HOSTED_TEST_RESULT_2026-09-11.json) remains disclosed. No fresh global suite or usability result is claimed.

The owner's 15 September authorship and verification confirmations remain in [AUTHOR_ACTIONS.md](AUTHOR_ACTIONS.md). AI-use permission, examiner access, award/student details, signature, prescribed institutional wording, owner reading of sources, assessed video and independently verified off-machine backup remain separate gates. The ethics declaration follows the owner's supplied task statement, rather than an automated institutional determination. [Video materials](video/RECORDING_PLAN.md) do not establish a completed recording. No merge or independent integration approval is implied.

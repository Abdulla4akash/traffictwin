# Dynamic Resource Management for Intelligent Transport Systems

**Contributions revision stopped at the requested word-count gate: 8,960 strict/package words / 7,760 prose-only words.** Strict is **10 above 8,950**; prose meets the 7,600 floor. The **63-page PDF** is a reviewable draft. Further manuscript editing stopped after the prescribed F1 fallback. The title stays unchanged.

[PDF](TrafficTwin_Dissertation.pdf) · [Markdown](TrafficTwin_Dissertation.md) · [generated TeX](TrafficTwin_Dissertation.tex) · [contributions stop report](CONTRIBUTIONS_REVIEW_2026-09-15.md) · [revision history](REVISION_REPORT.md) · [validation](document/REVISION_VALIDATION.json)

## Current change

Section 1.3 ends with the owner's Contributions lead and C1–C6, verbatim except C5's prescribed “more than eighty” fallback. Only B.1–B.5's named spans were trimmed. The 3.7 timing-limit sentence moves verbatim to Appendix D under F1, which was triggered by the A+B count of 8,975. AUTHOR_ACTIONS records the owner's contribution statement supplied on 15 September 2026. C3 retains the supplied wording; the Declaration and Section 3.7 retain assistance and supplied-component attribution.

## Counts and checks

| Stage | Strict/package headline | Prose-only |
|---|---:|---:|
| Reviewed `da49954` | 8,938 | 7,738 |
| Contributions A+B | 8,975 | 7,775 |
| Current A+B+F1 | **8,960** | **7,760** |
| Required | ≤ 8,950 | ≥ 7,600 |

The count rose by 22 words; the requested zero-net-cost goal was not achieved. The count method and bounds are unchanged. The contents prints strict first; [WORD_COUNT.json](document/WORD_COUNT.json) includes tables, equations and pseudocode in the headline, excluding captions, references, appendices and front matter. Prose-only additionally excludes table bodies and pseudocode.

- Preservation validator: **157/157 pass**. Combined validator: **203/204 pass; `word_count_in_range` fails**.
- Sections 1.2 and 3.2–3.6 byte-identical to `da49954`; all twenty table bodies, six equations, two algorithms, proposition and references 1–46 unchanged.
- The pinned [ledger](evidence/CONTRIBUTIONS_OPERATIONS_2026-09-15.json) recovers `da49954` exactly before every prior protection layer runs. Earlier appendix moves remain verbatim.
- A [mutation probe](evidence/CONTRIBUTIONS_MUTATION_CHECK_2026-09-15.json) rejects reinsertion of a deleted sentence.
- Clean XeLaTeX/latexmk build, 63 pages rendered, contents and all changed-text locations inspected. Zero overfull boxes, missing glyphs, undefined references or duplicate captions. PDF title/author metadata retained. Ruff lint/format pass for six document scripts.

## Evaluator-run derivation

The supplied components total 83, but E1 reuses E0's reference, proven by the same raw locator and summary hash. Counting it once gives **82 distinct completed-campaign records**: 1+14+3+1+8+4+5+2+12+32. Smokes, probes, reused controls and duplicate archives are excluded.

**The manuscript prints “more than eighty”.** Only 56 unique full-horizon summary fields are directly available. E1/E2c/E2d retain completed campaign receipts and manifest horizons for the other 26, but not the per-run summary fields required for printing an exact number. [Derivation](evidence/CONTRIBUTIONS_RUN_COUNT_2026-09-15.json) records all paths, hashes, horizon evidence and deduplication. No new scientific run was launched.

## SHA256

- TrafficTwin_Dissertation.md: `5fe0b6dc38c3fde1282affb502ea72d650ef0ea59f59c741086a333a962258cc`
- TrafficTwin_Dissertation.tex: `739fb2f99119afe068a8fb309084fb2acd97d790858b20dc8ea3daa8aec22411`
- TrafficTwin_Dissertation.pdf: `f85bf697f62beb68b850e042f55cde316ea4c8a4c5c15a58aaea6951b44486e9`

## Build and check

Use the existing document environment with MarkdownIt, NumPy, SciPy, Matplotlib, PyMuPDF, XeLaTeX and latexmk. Preserve Git baselines `9b49efc`, `2c29392`, `7075b25` and `da49954`. Current combined validation intentionally reports the unmet word-count gate; do not relax its bound.

```sh
pkg_dir=docs/dissertation/examiner_revision_2026-09-11
python "$pkg_dir/document/convert_source.py"
latexmk -cd -xelatex -interaction=nonstopmode -halt-on-error "$pkg_dir/TrafficTwin_Dissertation.tex"
python "$pkg_dir/document/validate_option_b.py"
python "$pkg_dir/document/validate_revision.py"
ruff check "$pkg_dir/document"
ruff format --check "$pkg_dir/document"
```

[Build log](evidence/latexmk-contributions-2026-09-15.log) · [grep receipt](evidence/CONTRIBUTIONS_GREP_2026-09-15.json) · [stop receipt](evidence/CONTRIBUTIONS_ACCEPTANCE_2026-09-15.json). The original `revision_recipe.json` and earlier acceptance receipts remain historical. [Earlier six-point review](EDITORIAL_FIX_REVIEW_2026-09-15.md) records the prior passing candidate; [Option B closing review](OPTION_B_CLOSE_REVIEW.md) retains the full earlier move map.

## Existing boundaries

Main remains `1e01b755b8b633f43c9c7bb6fdd0d75beb6469e8`; frozen packages and scientific results are unchanged. The hosted 56 test failures remain disclosed; no fresh global suite, usability result or E3 execution is claimed. The owner-confirmed ethics-tool outcome and primary references remain unchanged. [AI permission, institutional front matter/copyright, examiner access and video gates](SUBMISSION_GATES.md) remain open. Keep the PR draft; no passing count acceptance or formal integration approval is implied.

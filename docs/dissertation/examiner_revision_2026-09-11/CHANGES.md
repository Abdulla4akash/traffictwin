# Exemplar-alignment changes — LaTeX-only delivery

Baseline: `ded54bd2a043ec4ff7dbef6eb92e6176bc4963b9` on `docs/dissertation-examiner-revision-2026-09-11`. The edited `.tex` is the deliverable; the Markdown remains the historical baseline. No rebuilt dissertation PDF is included or committed. All regenerated PDFs, including the recomposed figure PDFs, stay local-only. New Figure 7 inputs are PNGs. Existing, unchanged figure PDFs remain in `assets/` as build inputs; no PDF is changed in the commit.

Counts: **9,555 → 9,605 strict; 8,136 → 8,174 prose-only**. A–D add no counted words. The new conclusion opener has 85 words (limit from the owner prompt); F.6–F.7 add 25 strict words. Sources: `document/WORD_COUNT.json`, `evidence/EXEMPLAR_WORD_DELTAS_2026-09-16.json`, and `document/count_exemplar_words.py`. The previous word-count stop waiver remains active.

Final local build: **zero errors, overfull boxes, oversized floats, missing glyphs or undefined references**; 67 pages. Three latexmk invocations were needed: the initial check exposed a copyright URL overflow and an oversized Figure 7a float, followed by layout and global-guard corrections. This differs from the requested single compile in order to complete the requested layout checks. Source: `evidence/EXEMPLAR_ACCEPTANCE_2026-09-16.json` and its build log.

No body page is below 60% vertical fill; minimum 64.29%. Current body is pages 11–43; physical page 10 is Acknowledgements after adding the glossary. Figure 7 is split into **7a (a,b)** and **7b (c)**. Screenshot hashes match the original receipt. Sources: `evidence/EXEMPLAR_PAGE_COUNTS_2026-09-16.json` and `evidence/FINAL_PLATFORM_CAPTURE_2026-09-16.json`.

## Edit ledger and final TeX line references

All line references below refer to `TrafficTwin_Dissertation.tex` in this delivery. `ded54bd:path` denotes the named file in the baseline commit. Short source names are expanded in the environment table or source inventory below.

| Requirement | TeX lines | Edit | Source of wording, values and versions |
|---|---:|---|---|
| A.1 | 43–54 | Replaced the title-page award block with the supplied University wording; retained student ID at the foot. | Owner prompt file; ded54bd:TrafficTwin_Dissertation.tex title page. |
| A.2 | 116–119 | Added the exemplar abstract header; abstract body unchanged except F.6. | Owner prompt; UOM_COPYRIGHT_STATEMENT_2026-09-16.md; baseline abstract. |
| A.3 | 148–159 | Copied all four clauses verbatim, preserving “thesis”; added URL wrapping without changing wording; updated ToC. | UOM_COPYRIGHT_STATEMENT_2026-09-16.md; exact clauses and file hash in evidence/EXEMPLAR_SOURCES_2026-09-16.json. |
| A.4 | 139–146 | Declaration, assistance paragraph and signature/date lines are byte-identical. | ded54bd:TrafficTwin_Dissertation.tex. |
| B.1 | 88–112 | Added all nineteen requested terms, one sentence each with its defining section; front matter excluded from count. | Baseline manuscript Sections 2.2, 2.4–2.6, 2.8, 3.4 and 3.7; no external definitions. |
| C.1–C.2 | 1662–1695 | Added Table A2 after S16 and replaced the runtime sentence with a pointer. Existing inventory keeps its A1 label. | Environment cell-by-cell source table below. |
| C.2 caption | 2210–2210 | Moved Apple M5 and runtime identification out of Table D2’s caption into the environment table; retained float32 and thread wording. | Baseline Table D2; analysis/results/BENCHMARK.json. |
| D.1 | 2381–2400 | Added Appendix H, repository/branch/source-base/package locators, access placeholder and three executed read-only commands. | git remote output and source identity in evidence/EXEMPLAR_ACCEPTANCE_2026-09-16.json; README.md; document/verify_compact_tables.py; evidence/EXEMPLAR_COMMANDS_2026-09-16.json. |
| D.2 | 1187–1187 | Pointed Table 8’s consequence at Appendix H without changing the strict word count; submission gate 3 stays open. | Baseline Table 8; SUBMISSION_GATES.md; owner prompt. |
| E.1 | 1201–1201 | Replaced the two conclusion-opening paragraphs with five plain-language sentences; no other trimming applied. | evidence/FINAL_FULL_RUN_COUNT_2026-09-16.json (274); baseline Table 7 and evidence/LOCAL_COMPACT_CHECKS_2026-09-15.json (+4.137, +0.631); Report 5.pdf conclusion used only as a structure model. |
| F.1 | 725–1316 | Removed the forced breaks before 2.9, Tables 7a/7b and 8, Sections 3.5/3.6 and the conclusion; allowed conclusion text before the figure flush and references to follow the final conclusion paragraph. Tables retain their rows. | TeX operation ledger; before/after local-build page counts below and evidence/EXEMPLAR_PAGE_COUNTS_2026-09-16.json. |
| F.2 / H spaced-path guard | 1698–1941 | Replaced spaced path expressions with texttt in S17 and Appendix C.4; contents unchanged. | Baseline S17 and C.4; H acceptance rule. |
| F.3 | 1266–1266 | Clarified that the retained advantage is per-task over ingress. | Baseline Section 4.3 and owner prompt F.3; the 10 ms value is unchanged. |
| F.4 | 931–935 | Moved Setting before Results with both paragraph bodies unchanged. | Baseline Section 3.4 source blocks 142/143. |
| F.5 | 1320–1504 | Removed trailing access tags; preserved every URL and moved links onto DOI/title text. Kept web access dates. Corrected the JAX version-year citation. | Baseline bibliography; evidence/reference-registration-2026-09-15.json; QUALIFICATION.json; owner prompt F.5 gives release year 2024 and first release 2018. |
| F.6 Abstract | 134–134 | Used demand-scaled provenance wording. | Camera-ready PDF §4.4; baseline abstract. |
| F.6 §1.1 | 192–192 | Replaced calibrated simulation with count-matched, demand-scaled Manchester SUMO network. | Camera-ready PDF §4.4. |
| F.6 §2.3 | 415–415 | Added the supplied OpenStreetMap/70%/SUMO sentence; consolidated duplicated provenance wording within the named paragraph. | ICISS2026_SA0082_camera_ready-compressed.pdf §4.4, verified locally; source hash in evidence/EXEMPLAR_SOURCES_2026-09-16.json. |
| F.6 repeats | 1011–1279 | Changed the Section 3.4 and Table 8 repeats to demand-scaled; changed future-work “second calibrated network” to “second traffic network” to satisfy the requested global guard without adding a calibration claim. | Baseline Sections 3.4/4.4 and Table 8; owner prompt H global guard. |
| F.7 | 447–447 | Added the source-study SUMO version to both Table 2 columns. | Camera-ready PDF §4.4: 1.27.0; reference 47 remains the supplied paper. |
| F.8 | 1151–1164 | Recomposed the legend-free full-width panel-a composite (PNG delivered; regenerated PDFs local-only); split the manuscript figure into 7a (a,b) and 7b (c) for page-scale legibility, updated List of Figures/cross-references, moved legend wording to the caption and added the compatibility explanation. No recapture. | ded54bd:evidence/FINAL_PLATFORM_CAPTURE_2026-09-16.json; unchanged shots/*.png; regenerated capture receipt; original caption and TOS_ADAPTER_VALIDATION_2026-09-16.json. |
| G | 57–59 | Updated both displayed word counts using unchanged tokenisation and exclusions, with a TeX-bound source-block projection. | document/count_exemplar_words.py; document/WORD_COUNT.json; baseline WORD_COUNT.json at ded54bd. |

## Execution-environment cell sources

The component labels follow C.1 in `~/scratch/CODEX_PROMPT_exemplar_alignment_2026-09-16.md`; every value cell is sourced below. Relative paths start at the manuscript package. The two table headings contain no measured values.

| Component | Written value | Named source file / field |
|---|---|---|
| Hardware chip | Apple M5 (CPU) | ../empirical_extension_2026-09-08/analysis/results/BENCHMARK.json: processor/devices; ../joint_confirmation_2026-09-08/evidence/QUALIFICATION.json: runtime.runtime.processor/devices |
| CPU count | 10 (recorded CPU count; not an invented physical-core specification) | ../joint_confirmation_2026-09-08/evidence/QUALIFICATION.json: runtime.runtime.cpu_count |
| Physical memory | not recorded | BENCHMARK.json and QUALIFICATION.json above have no physical-memory quantity; XLA buffer estimates are not RAM capacity. The current host was not substituted. |
| Operating system | macOS 26.4.1, arm64 | BENCHMARK.json: platform/machine; QUALIFICATION.json: runtime.runtime.platform |
| CPython (evaluator) | 3.11.15 | QUALIFICATION.json: runtime.runtime.python; BENCHMARK.json: python |
| JAX / JAXlib | 0.4.30 / 0.4.30 | QUALIFICATION.json: runtime.runtime.jax/jaxlib; BENCHMARK.json: jax/jaxlib |
| NumPy (evaluator) | 1.26.4 | QUALIFICATION.json: runtime.runtime.numpy; BENCHMARK.json: numpy |
| SciPy (compact verifier) | 1.17.1 | evidence/EXEMPLAR_COMMANDS_2026-09-16.json: compact_result.runtime.scipy; corroborated by ../joint_confirmation_2026-09-08/evidence/ANALYSIS.json: analysis_runtime.scipy |
| Streamlit (product lockfile) | 1.59.2 at 1e01b75 | 1e01b75:uv.lock, streamlit package; file hash recorded in evidence/EXEMPLAR_SOURCES_2026-09-16.json |
| SUMO | 1.27.0 as reported by source study [47] | ~/Downloads/diss_mat/ICISS2026_SA0082_camera_ready-compressed.pdf §4.4; not a claim that the evaluator reran SUMO |
| Frozen evaluators | 2f63706; 908bd10; versioned confirmation copy | ded54bd:TrafficTwin_Dissertation.tex Appendix A S4/S9/S12/S16; ../joint_confirmation_2026-09-08/experimental/evaluator_v2.py and evidence/QUALIFICATION.json source bindings |
| JAX x64 | disabled | QUALIFICATION.json: runtime.runtime.x64=false; BENCHMARK.json: x64=false |

## Other number and version sources

- Title-page year and student ID: `~/scratch/CODEX_PROMPT_exemplar_alignment_2026-09-16.md` A.1, and baseline `TrafficTwin_Dissertation.tex`; abstract-header year: `~/scratch/UOM_COPYRIGHT_STATEMENT_2026-09-16.md`.
- Copyright clause numbers, Act year and URL document identifier: the same supplied copyright file, copied verbatim; no copyright wording is paraphrased here.
- Conclusion run count: `evidence/FINAL_FULL_RUN_COUNT_2026-09-16.json`; effects: baseline Table 7 and `evidence/LOCAL_COMPACT_CHECKS_2026-09-15.json`.
- All existing result-table values, dates and scientific equations remain unchanged. F.3 retains its existing forwarding-cost value. New section/table/figure locators refer to the corresponding headings and labels in this `.tex`.
- Figure-caption versions, dates, inventory and source commits: baseline `TrafficTwin_Dissertation.tex` Figure 7, baseline and regenerated `evidence/FINAL_PLATFORM_CAPTURE_2026-09-16.json`, `evidence/TOS_ADAPTER_VALIDATION_2026-09-16.json`, and the unchanged screenshot text files in `evidence/final_capture/shots/`. The encoding names are the adapter’s recorded declared mismatch.
- Bibliography numbers/dates/versions: baseline bibliography and `evidence/reference-registration-2026-09-15.json`; JAX’s release-year correction is supplied by the owner prompt F.5, while `QUALIFICATION.json` independently verifies the pinned version. No external release-history lookup is claimed.
- Repository URL: `git remote get-url origin`, recorded in `evidence/EXEMPLAR_ACCEPTANCE_2026-09-16.json`; source base and branch: baseline S17 and Git identity recorded in that receipt.
- Check counts, page counts, word counts, checksums, exit statuses and build-input inventory are measured output in the correspondingly named receipts; they are not new scientific results.

## Commands and validation

The three Appendix H commands each ran once in a scratch copy and exited successfully; the platform returned a successful loopback health response and then stopped on a controlled signal. Scratch source files and the external package were hash-checked unchanged. The compact helper was subsequently reformatted only; its AST is identical to the executed copy, with both file hashes recorded in `evidence/EXEMPLAR_COMMANDS_2026-09-16.json`. Research workloads launched: **0**.

The final-pass validator passed 109/109 checks; the combined validator passed 324/326, with only the two explicitly waived word-limit diagnostics false. Seven in-memory mutation probes rejected missing glossary/copyright/environment/access material, a spaced path, a bibliography access tag and overstated network provenance. No application tests, research campaign or independent review approval is claimed. Sources: `evidence/FINAL_PASS_VALIDATION_2026-09-16.json`, `document/REVISION_VALIDATION.json`, and `evidence/EXEMPLAR_MUTATION_CHECKS_2026-09-16.json`.

## AUTHOR_ACTION placeholders and uncompleted owner items

- **AUTHOR_ACTION: access mechanism** — Appendix H and submission gate 3 remain open. The owner must choose and arrange read-access invitation or an archive deposit.
- **AUTHOR_ACTION: confirm whether Student ID 14185028 remains** — retained at the title-page foot as instructed; recorded in `AUTHOR_ACTIONS.md`.
- Existing signature/date, AI-use permission, off-machine preservation, final independent reading, assessed video and deferred study integration remain owner obligations in `SUBMISSION_GATES.md`; no completion is inferred.
- No memory specification is supplied because the named runtime receipts do not record it.
- Later trim candidates are recorded but **not applied**: Section 3.7 contribution paragraph (~100 words), 4.3 duplicated numbers (~60), 3.2 E2b paragraph (~50), 1.1 last paragraph (~40). These estimates come from the owner prompt G, not a new count.

## Per-page word counts before and after

pdftotext -layout whitespace tokens, removing one final page-number token; image text is not OCR-counted. Fill is the text/image/vector bounding-box vertical extent within 25 mm top/bottom margins, excluding page-number footer; it is not a word-density or ink-area estimate.

The source is `evidence/EXEMPLAR_PAGE_COUNTS_2026-09-16.json`. Reflow changes page-to-content correspondence, so each row compares physical page numbers rather than identical text spans. Before page 25 has 43 words after removing its page-number footer, matching the reported issue.

| Physical page | Before words | After words | Before vertical fill % | After vertical fill % |
|---:|---:|---:|---:|---:|
| 1 | 46 | 55 | 92.66 | 92.66 |
| 2 | 503 | 500 | 99.7 | 99.69 |
| 3 | 429 | 439 | 99.59 | 99.59 |
| 4 | 1079 | 1134 | 92.9 | 98.31 |
| 5 | 75 | 75 | 39.31 | 39.31 |
| 6 | 310 | 349 | 78.68 | 98.57 |
| 7 | 188 | 325 | 48.9 | 82.71 |
| 8 | 68 | 188 | 20.05 | 48.9 |
| 9 | 43 | 262 | 14.93 | 67.84 |
| 10 | 389 | 43 | 97.38 | 14.93 |
| 11 | 293 | 390 | 65.46 | 97.38 |
| 12 | 333 | 293 | 99.78 | 65.46 |
| 13 | 406 | 333 | 96.96 | 99.78 |
| 14 | 418 | 406 | 96.43 | 96.96 |
| 15 | 330 | 418 | 98.23 | 96.43 |
| 16 | 317 | 330 | 84.66 | 98.23 |
| 17 | 323 | 317 | 100.0 | 84.66 |
| 18 | 314 | 319 | 99.59 | 100.0 |
| 19 | 380 | 307 | 98.13 | 96.86 |
| 20 | 270 | 391 | 91.94 | 98.09 |
| 21 | 371 | 285 | 98.94 | 97.83 |
| 22 | 310 | 371 | 96.66 | 98.94 |
| 23 | 386 | 310 | 99.5 | 96.66 |
| 24 | 345 | 386 | 99.24 | 99.5 |
| 25 | 43 | 345 | 9.39 | 99.24 |
| 26 | 317 | 295 | 95.2 | 95.55 |
| 27 | 389 | 387 | 99.59 | 99.25 |
| 28 | 335 | 345 | 97.11 | 96.28 |
| 29 | 257 | 314 | 81.7 | 95.27 |
| 30 | 186 | 186 | 83.94 | 83.94 |
| 31 | 415 | 415 | 100.0 | 100.0 |
| 32 | 178 | 296 | 64.22 | 99.38 |
| 33 | 321 | 378 | 74.63 | 98.31 |
| 34 | 153 | 370 | 34.76 | 98.0 |
| 35 | 346 | 327 | 89.2 | 97.2 |
| 36 | 321 | 431 | 98.63 | 98.46 |
| 37 | 151 | 213 | 33.97 | 64.29 |
| 38 | 122 | 133 | 99.41 | 98.33 |
| 39 | 192 | 45 | 38.32 | 78.31 |
| 40 | 248 | 338 | 65.42 | 94.92 |
| 41 | 311 | 311 | 99.02 | 95.14 |
| 42 | 354 | 389 | 98.48 | 95.92 |
| 43 | 360 | 322 | 99.24 | 98.44 |
| 44 | 99 | 362 | 22.96 | 95.12 |
| 45 | 353 | 377 | 99.35 | 96.54 |
| 46 | 386 | 321 | 97.19 | 78.47 |
| 47 | 384 | 374 | 99.59 | 99.28 |
| 48 | 310 | 380 | 79.11 | 99.59 |
| 49 | 374 | 316 | 99.28 | 79.77 |
| 50 | 347 | 437 | 74.42 | 96.47 |
| 51 | 249 | 444 | 64.01 | 99.63 |
| 52 | 437 | 167 | 96.47 | 35.74 |
| 53 | 444 | 462 | 99.63 | 90.72 |
| 54 | 167 | 562 | 35.74 | 99.12 |
| 55 | 462 | 467 | 90.72 | 98.84 |
| 56 | 562 | 490 | 99.12 | 93.86 |
| 57 | 467 | 327 | 98.84 | 99.59 |
| 58 | 490 | 524 | 93.86 | 98.67 |
| 59 | 327 | 406 | 99.59 | 96.61 |
| 60 | 524 | 470 | 98.67 | 99.71 |
| 61 | 406 | 189 | 96.61 | 53.02 |
| 62 | 470 | 502 | 99.71 | 98.84 |
| 63 | 188 | 348 | 53.02 | 96.8 |
| 64 | 502 | 275 | 98.84 | 48.64 |
| 65 | 348 | 549 | 96.8 | 94.39 |
| 66 | 275 | 32 | 48.64 | 5.83 |
| 67 | 549 | 254 | 94.39 | 78.31 |
| 68 | 32 | — | 5.83 | — |

## Build-input package

The delivery includes `.tex`, all `assets/`, the recorder-listed `.sty`/`.cls` and related TeX package inputs under `build_inputs/texmf/`, and the required font families under `build_inputs/fonts/`. No `.bib` is used: the bibliography is inline. `BUILD.md` explains the XeLaTeX build, and `BUILD_INPUTS.json` records every copied dependency source and checksum. `SHA256SUMS` covers every delivered file except itself.

The tracked dissertation PDF is restored to SHA-256 `2730a690075f6c29586e9fe16c20f4ed367d1318692d91ae8fe847ebd50de2e8`. The local inspection build stays outside the delivery and repository.

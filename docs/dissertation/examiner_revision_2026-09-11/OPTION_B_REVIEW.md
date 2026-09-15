# Option B review and stop report

Historical stop report for `2c29392`. The [closing revision](OPTION_B_CLOSE_REVIEW.md) supersedes its current count, stakes handling and ethics status; the record below is retained verbatim.

## Option B — 15 September 2026; input `9b49efc`

**STOPPED AT THE WORD LIMIT: 9,388 package words / 8,017 prose-only words.** The strict count exceeds 9,000 by **388 words** after the overflow valve. No further text was trimmed or moved. The source, generated TeX/PDF and draft PR are provided for review; this candidate is not acceptance-complete. Build and documentation bookkeeping continued after content reduction stopped.

### Changes and evaluation rationale

Added project-approach analysis (4.2), the eight-choice rationale table and methodological lead-in (2.9), ethics/professional considerations (1.4), verified stakes/context (1.1), seven objective/RQ tags, the plain-language proposition remark, and eight Setting/Results labels. The earlier exemplar comparison informs explicit method choices, contribution/scope, execution quality and limitations. Other suggested moves or rewrites were not applied because Option B protects the existing prose. New 4.2 has three first-person run-in paragraphs and retains the hosted 56 failures and the RSU-specific conservation bound.

### Counts

| Stage | Package count (headline) | Prose-only count |
|---|---:|---:|
| Baseline `9b49efc` | 9,180 | 7,877 |
| A + B.1–B.4 | 9,452 | 7,991 |
| After B.5 Table 8 → D2 | 9,388 | 8,017 |
| Acceptance | ≤ 9,000 | ≥ 7,600 |

The same package tokenisation is retained, including Abstract, main headings/body, table text, equations and pseudocode. Captions, references, appendices and front matter remain excluded. The package count is now the headline; prose-only additionally excludes tables and pseudocode. The Table 8 move reduces the headline by only 64 words after its replacement and cross-references. The prompt's estimated move budget is larger than the passages in the actual baseline.

### Moved-content map

| Source | Destination | First words / content | Identity check |
|---|---|---|---|
| 2.4 | Appendix F | T(b,q,c) is | SHA256 `20699ac896e6`; verbatim |
| 2.4 | Appendix F | The gate-enabled paths | SHA256 `e702446e9565`; verbatim |
| 2.4 | Appendix F | This aggregate carry approximation | SHA256 `23dcb380b616`; verbatim |
| 2.7 | Appendix B | The September audit independently | SHA256 `6d13157deefe`; verbatim |
| 2.7 | Appendix B | Task joins require | SHA256 `7ca3d4f63bd8`; verbatim |
| 2.7 | Appendix B | Retrospective diagnostics distinguish | SHA256 `5e5b371f0491`; verbatim |
| 2.8 | Appendix D | Scheduler timing uses | SHA256 `3b6b79ad8521`; verbatim |
| 3.7 | Appendix D | Compiler buffer reuse | SHA256 `9e2f48920b26`; verbatim |
| 3.7 | Appendix D | Table 8 → Table D2 | SHA256 `1e5a6f132089`; verbatim |

Full bodies, SHA256 values, origin pointers and reversible source operations are in [OPTION_B_OPERATIONS.json](evidence/OPTION_B_OPERATIONS.json).

### Source verification and declined figure

The primary WHO report verifies **an estimated 1.19 million road traffic deaths in 2021**, printed p. 4 and executive summary p. viii. The estimation year is explicit in the manuscript.

The primary ETSI PDF of **3GPP TS 22.186 v16.2.0** verifies **100 ms** for automated-driving information sharing between UE and RSU (clause 5.3, Table 5.3-1, requirements R.5.3-004/005, printed p. 10). **No advanced-driving requirement class spanning 100–500 ms was verified.** In that advanced-driving table, 500 is a communication range in metres for R.5.3-006. A 500 ms latency requirement belongs to platooning reporting, R.5.2-008, Table 5.2-1, printed p. 9. The manuscript uses the verified 100 ms context, distinguishes communication requirements from task deadlines, and leaves the requested bracketed owner note. Both primary PDFs were downloaded, their relevant text read and page images inspected by the editing assistant; owner reading is not claimed. The official document title is used. No new DOI was introduced; the two primary-document verifications are appended to reference-registration.json and separately recorded in reference-registration-option-b-2026-09-15.json.

### Preservation and instruction conflicts

Section 1.2 is byte-identical to `9b49efc`. Sections 3.2–3.6 retain their prose except the requested O-tags and Setting/Results labels, the explicit A.6 remark after Proposition 1, the A.1 future-work cross-reference (4.3 → 4.4), and the B.5 Table 8 → Appendix D/Table D2 cross-reference. These specific requirements are recorded as exceptions to the prompt's broader “only tags and labels” wording; a literal diff does include the remark and cross-reference updates.

B.2 quotes wording that does not occur at `9b49efc`. Its corresponding source sentence begins “The September audit independently”; that actual sentence is moved verbatim. Its two following paragraphs share the single pointer prescribed by B.2. The eight moved text pieces and Table 8 body each occur exactly once at their appendix destination; seven distinct source pointers each occur once. Every original table body, equation, algorithm and the proposition is preserved. The new alternatives table uses Table 3a; Table 8 becomes D2. References 1–41 retain their identifiers and bibliography text; 42–43 are appended because renumbering by first appearance would violate the protected Section 1.2.

The ethics declaration follows the owner's task statement. The baseline establishes simulated traces and an unperformed user evaluation, but did not itself contain a formal no-approval statement. The evidence map records this as an owner-supplied declaration, not an independently verified institutional determination.

`validate_revision.py` now invokes `validate_option_b.py`, which loads the pinned Git baseline, proves its SHA256, compares protected sections and every existing table body, verifies each move/pointer, and reverses the complete operation ledger to recover the baseline byte-for-byte. Seven read-only mutation probes demonstrate failures for protected prose edits, changed relocated text/table values, duplicated pointers, unapproved prose and missing tags. They modify only in-memory strings.

### Verification

- XeLaTeX build: **63 pages**, zero overfull boxes, missing glyphs, unresolved references or duplicate captions.
- Document validator: **91/92 checks passed**; exit 1 is intentional and exclusively reflects `word_count_in_range`.
- Compact recomputation: 32 cells / eight blocks passed; no evaluator or raw-task reanalysis.
- Frozen archive integrity: 938 files / eight roots passed. Changed tracked paths are confined to this revision package; `main` remains `1e01b755b8b633f43c9c7bb6fdd0d75beb6469e8`.
- Ruff check and formatting passed for all six document Python files.
- Pagination keeps Table 3a together and avoids splitting the small morning Table 5; widow/orphan penalties and appendix paragraph spacing affect layout only.
- Existing assessed-video, access, declaration and AI-permission gates remain open. No independent integration approval or full regression-suite pass is claimed.

### Grep table

| Check | Expected / found | Markdown lines |
|---|---|---|
| New 4.2 | 1 / 1 | 512 |
| New 2.9 | 1 / 1 | 294 |
| Ethics paragraph | 1 / 1 | 124 |
| Objective tags | 7 / 7 | 315, 333, 356, 391, 419, 433, 445 |
| Setting / Results labels | 8 / 8 | 335, 339, 358, 360, 393, 395, 435, 437 |
| Proposition remark | 1 / 1 | 425 |
| Appendix F heading | 1 / 1 | 1046 |
| Relocated Table D2 caption | 1 / 1 | 964 |
| Stale Table 8 reference/caption | 0 / 0 | — |
| WHO figure | 1 / 1 | 34 |
| Standards owner note | 1 / 1 | 34 |

### Artifact hashes

- TrafficTwin_Dissertation.md SHA256: `307862fcc37558df585b0e867a0766aa3616cd810ee0595df398dd3ffaf0cf89`.
- TrafficTwin_Dissertation.tex SHA256: `10a446730304195d815e4e02e598daafbc6c3bccde37a1f7a3240a833967750b`.
- TrafficTwin_Dissertation.pdf SHA256: `616f27c4d3b54173761419fe0e4cbef5bf8ab8f410f5975888e400b9a70d4505`.

# Option B closing revision — 15 September 2026

**Closing contract passes: 8,914 strict/package words and 7,714 prose-only words.** The source started at `2c29392cbf04bf060aacb0f03f1fbb900842d54a`. The strict count is 36 below the requested 8,950 ceiling; prose-only is 114 above 7,600. This closes the count defect in the earlier Option B stop report.

## Changes and count

Moved Table 9 and five paragraphs verbatim to appendices, with exactly one pointer at each of five source locations. The constructed example and invariant share their prescribed pointer. Removed only the four specified duplicate sentences from the Option B ethics paragraph and 2.9 lead-in. Rewrote the Option B stakes paragraph, preserving its WHO sentence. No additional exemplar-derived prose or other reduction was made.

| Stage | Strict/package (headline) | Prose-only |
|---|---:|---:|
| Baseline `9b49efc` | 9,180 | 7,877 |
| Previous Option B `2c29392` | 9,388 | 8,017 |
| Closing moves and B.1–B.3 | 8,899 | 7,699 |
| Final, including dated author-confirmed ethics check | **8,914** | **7,714** |
| Closing limits | ≤ 8,950 | ≥ 7,600 |

Net change from `2c29392`: −474 strict words / −303 prose-only words. Counting and contents-page wording are unchanged in method; strict includes tables, equations and pseudocode, with prose-only second. No extra reductions were necessary.

## Updated moved-content map

| Round | Source | Destination | First words / table | SHA256 prefix |
|---|---|---|---|---|
| Option B | 2.4 | Appendix F | T(b,q,c) is 0.1 + 1,000 × 8b/c … | `20699ac896e6` |
| Option B | 2.4 | Appendix F | The gate-enabled paths pass final admission into … | `e702446e9565` |
| Option B | 2.4 | Appendix F | This aggregate carry approximation has no individual … | `23dcb380b616` |
| Option B | 2.7 | Appendix B | The September audit independently identifies offers from … | `6d13157deefe` |
| Option B | 2.7 | Appendix B | Task joins require matched trace-row/substep/slot coordinates and … | `7ca3d4f63bd8` |
| Option B | 2.7 | Appendix B | Retrospective diagnostics distinguish simultaneous common-target admission A, … | `5e5b371f0491` |
| Option B | 2.8 | Appendix D | Scheduler timing uses actual JAX helpers, including … | `3b6b79ad8521` |
| Option B | 3.7 | Appendix D | Compiler buffer reuse and elimination of unused … | `9e2f48920b26` |
| Option B | 3.7 | Appendix D | Table 8 → Table D2 | `1e5a6f132089` |
| Closing | 3.7 | Appendix A | Table 9 → Table A1 | `a00b2c404f6f` |
| Closing | 2.3 | Appendix F | For homogeneous RSUs, service milliseconds are s … | `82244a7e76f7` |
| Closing | 2.3 | Appendix F | The same archived one-hot-17 checkpoint is used … | `d2f3cfb75934` |
| Closing | 2.2 | Appendix F | V2V selection excludes the source and full-queue … | `88553fb06c07` |
| Closing | 3.1 | Appendix B | Consider a constructed explanation, not an observed … | `18810355bfda` |
| Closing | 3.1 | Appendix B | The relevant invariant is that offers partition … | `df443f1f1ba6` |

The earlier eight text pieces and Table D2 are preserved, together with the five new paragraphs and Table A1. There are twelve distinct pointers across both rounds. Full bodies and hashes are in [the original ledger](evidence/OPTION_B_OPERATIONS.json) and [the closing ledger](evidence/OPTION_B_CLOSE_OPERATIONS.json).

## Stakes: verified 500 ms branch

The primary ETSI PDF of 3GPP TS 22.186 v16.2.0 gives **100 ms** for automated-driving information sharing between UE and RSU in clause 5.3, Table 5.3-1, R.5.3-004/005, printed page 10; **500 ms** for platooning reporting, including UE–RSU, in clause 5.2, Table 5.2-1, R.5.2-008, printed page 9. The revision takes B.3's first branch. The second sentence explicitly names both classes so “those two requirement classes” has a clear antecedent. This correspondence motivates task deadlines and does not validate the simulation. The bracketed owner note is removed.

The WHO sentence remains byte-identical: the 2023 report estimates 1.19 million road traffic deaths **in 2021**, supported by printed page 4 and executive summary page viii. Both downloaded primary PDFs were checked; the owner also reports checking these sources. References 1–41 remain unchanged; reference 42 gains its second locator and 43 is unchanged. No DOI was introduced. [Source registration](evidence/reference-registration-option-b-close-2026-09-15.json) preserves methods, locators and download hashes; earlier dated receipts remain historical.

## Ethics confirmation

The tool redirected the assistant to University sign-in; no authenticated result was observed. The owner then replied, “see we dont need i just checked it myself,” confirming a completed check and that approval is not required. Section 1.4 now dates and attributes the tool check to the author and cites reference 44. The [confirmation receipt](evidence/ETHICS_DECISION_OWNER_CONFIRMATION_2026-09-15.json) distinguishes this owner attestation from independent observation or formal ethics approval. This narrow correction implements the user's separately stated ethics requirement, in addition to the fenced B.1 trim.

## Preservation and validation

- Section 1.2 remains byte-identical to `9b49efc`; all of Sections 3.2–3.6 are byte-identical to `2c29392`.
- Every pre-closing table body is unchanged; only Table 9 becomes A1. Table D2 remains unchanged. Equations, algorithms and Proposition 1 are unchanged.
- `validate_option_b.py` reverses the pinned closing ledger to recover `2c29392` byte-for-byte, then applies every prior Option B guard against `9b49efc`. Additional checks directly verify every moved body in the current appendices, all twenty pre-closing tables, five pointers, protected sections and ethics/stakes handling. The closing ledger itself is hash-bound.
- `validate_option_b.py`: **93/93 preservation checks passed**. `validate_revision.py`: **137/137 checks passed**. [Eleven mutation probes](evidence/OPTION_B_CLOSE_MUTATION_CHECKS.json) detect protected-prose edits, changed moved text/table values, duplicate pointers, unauthorised text and a false ethics-approval claim.
- XeLaTeX/latexmk build: **62 pages**, zero overfull boxes, missing glyphs, undefined references or duplicate captions. Every page rendered and inspected; details in [visual receipt](evidence/OPTION_B_CLOSE_VISUAL_INSPECTION.json). Trailing whitespace and the final blank line are normalised in the archived [build log](evidence/latexmk-option-b-close-2026-09-15.log).
- Compact arithmetic verification: 32 cells / eight blocks passed; no actor, evaluator, SUMO, raw-task audit or new research workload. Frozen archive verification: 938 files / eight roots passed. Source changes stay within this revision package; `main` remains `1e01b755b8b633f43c9c7bb6fdd0d75beb6469e8`.
- Ruff lint and formatting pass for all six document Python files. The earlier hosted 56 test failures remain disclosed; no new global-suite result is claimed.

## Build identity

- Markdown SHA256: `938213d74d9093008a6493dd992fa1157fe4758f266c59f5f2dfd78e8314b4f3`.
- TeX SHA256: `57e2133857491eed28ba1e83da04c2affaacfb95108d26f184de45271bf35f65`.
- PDF SHA256: `f42d02333363aad5450210a6df5968dfd7a5a4905ce03fa920fda30aaa7cf429`.

## Grep table

| Check | Found / expected | Markdown lines |
|---|---:|---|
| Project approach section | 1 / 1 | 501 |
| Method alternatives section | 1 / 1 | 294 |
| Ethics paragraph | 1 / 1 | 124 |
| Owner-confirmed ethics citation | 1 / 1 | 124 |
| Objective tags | 7 / 7 | 315, 331, 354, 389, 417, 431, 443 |
| Setting / Results labels | 8 / 8 | 333, 337, 356, 358, 391, 393, 433, 435 |
| Proposition remark | 1 / 1 | 423 |
| Table A1 caption | 1 / 1 | 738 |
| Table D2 caption | 1 / 1 | 971 |
| Owner placeholder | 0 / 0 | none |
| 3GPP both deadlines | 1 / 1 | 34 |
| Ethics reference | 1 / 1 | 673 |

Draft PR status is retained. Exact commit and independent read-only review are reported in the PR body after push. Existing [submission gates](SUBMISSION_GATES.md) remain separate from this completed closing revision; no merge or formal integration approval is implied.

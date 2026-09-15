# Revision record — TrafficTwin examiner revision

## Option B closing revision — 15 September 2026

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

---

# Historical revision entries

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

## Earlier revision history (through `9b49efc`)


This is an additive document/software-evidence revision of source `1e01b755b8b633f43c9c7bb6fdd0d75beb6469e8`. There are no new scientific trials, altered archived scores, retrained policies or E3 results.

| Review concern | Implemented change | Boundary still open |
|---|---|---|
| Ownership and author-facing notes | Removed editorial cover/body notes; limited first-person analysis to recorded contributions; substantive AI assistance is in the Declaration | Design, implementation and checks confirmed by me on 15 September; AI-use permission and signature remain open |
| Invisible artefact | Streamlit description, six-component inventory, physical source sizes, collection count, refusal gates and actual browser screenshot | Software evidence does not establish user benefit or personal authorship |
| Spreading/workload-aware split | Unrounded equal-block mean arithmetic in 3.4 and Conclusion, 84.8%/15.2% | Descriptive contrast shares, not a causal decomposition |
| Introduction and scope | Figure 1 moved to 1.1, cited stakes/gap, product/user-evaluation scope, authenticated morning RSU coordinates | No authenticated incident coordinates or street projection available; no invented map |
| Unanswerable RQ1 | E0/E1 retained as validation/scoping; three answerable RQs | Historical scoring impact remains not assessable |
| Objectives | O1–O5 and objective-by-objective verdict table in 4.1 | Scope decisions confirmed by me on 15 September |
| Audit-log section 3.5 | One-page mechanism/proposition narrative; full diagnostics/accounting retained in Appendix C | Exact and floating-point claims remain distinct |
| Historical raw-array retention | Clarified that E0/E1/E2 raw arrays were not retained; summaries, receipts and manifests reproduce reported intervals | Task-level scoring impact remains unquantifiable |
| Strongest picture | Four-arm, eight-block Figure 6 recomputed from all 32 cells | Earlier four-draw inference remains separate |
| Limitation-heavy endings | Reordered central result explanations and consolidated validity discussion | Ending-audit JSON is a lexical screen, not a semantic grading guarantee |
| Thin references | 25 entries, cited future work and added VEC/cooperation/digital-twin context | Fan-paper identity checked against publisher-deposited metadata; full-text critical review still required |
| Unbuilt format | 12-point, 1.5-spaced main text, Arabic pagination, front matter, word count, abbreviations, 27 Reading captions; SVG→PDF and actual XeLaTeX build | Award/student fields, signed declaration and prescribed IP wording remain author/programme gates |
| Preservation | Copy-only hash-bound script and destination-specific approval requirement | No Mac raw files accessed or off-machine transfer performed |
| Video | 7:20 plan, authentic compact-verifier command and explanatory toy animation | No candidate narration, talking head or assessed video recorded |

## Verification distinctions

Existing numeric tables/algorithms/equations/proposition and five SVG originals are compared directly against the preserved package. The original Abstract is unchanged. A fresh compact verifier checks all 32 cells and declared intervals without rerunning the evaluator. The new figure and descriptive split derive from integer offers/successes and equal block weights.

The genuine product capture is bound to run `34614459294` on the pinned source. Five browser routes passed its bounded checks; Ruff and the 938-file frozen-archive verifier passed. Hosted branch run [34631121188](https://github.com/Abdulla4akash/traffictwin/actions/runs/34631121188), 11 September 2026, collected 8,301 tests: Python 3.12 completed with 8,179 passed, 56 failed (including five tier-4 UI text assertions in `tests/unit/ui/test_page_presentation_tier4.py`, plus provenance/ancestry, artifact and other UI checks), and 66 skipped. Python 3.11 was cancelled. Ruff passed and 938 frozen files were verified. This is a failed global suite, not an independent reviewer approval.

The PDF was actually compiled and rendered. Build logs and validation distinguish missing references, glyphs and overfull boxes from editorial or author-policy completion. The front-matter copyright summary is not represented as the University's prescribed verbatim declaration. Numerical correctness and clean rendering do not certify submission readiness.

## Reference verification

The original 14 references retain their prior source record. Added primary-source pages/preprints were checked for relevant content; both new Wenhao Fan paper identities were checked against publisher-deposited Crossref registrations stored in `evidence/reference-registration.json`. These registrations identify authors, titles, DOI, volume, issue and pages, but contain no full methodological text. No fabricated page-level verification or full-text reading claim is made. General Manchester presentation guidance was checked at `https://documents.manchester.ac.uk/display.aspx?DocID=2863`; assessment-specific AI instructions and supplied template remain higher-priority author inputs.

There is no defensible numerical mark guarantee. The user's quoted 68/80–85/90 estimates are reviewer opinions, not validated predictions.

## 15 September revision

| Request | Implemented change | Boundary still open |
|---|---|---|
| C.1–C.2 / D.3: front matter | First-person Declaration and acknowledgements name Randy Prasetia Putra and credit Dr Sampaio's report-age suggestion; permission remains in submission gates | AI-use permission, signature, prior-submission status and prescribed institutional wording |
| C.3–C.5 / C.8–C.9 / D.1–D.2: authorship | Removed retrospective-motivation framing, recorded my design decisions, AI-assisted implementation, personal modifications and eight completed author checks | My confirmation is authoritative owner testimony; automated checks do not certify assessment permission |
| C.6: omitted baseline | Disclosed evaluator-documented common-target and two-choice semantics; added exactly two available/unevaluated Table 3 rows, the Table 10 limit and first future-work item | `dla_p2c` remains unevaluated; no Section B authorisation, fifth arm or new contrast; the sealed family is unchanged |
| C.7: retention | E0/E1/E2 raw arrays were not retained; summaries, receipts and manifests reproduce intervals; package-local claim map retains historical support | Historical task-level scoring impact cannot be quantified; raw input access and off-machine preservation remain open |
| C.10: test evidence | Table 9 and prose report the completed Python 3.12 hosted result, including 56 failures across provenance/ancestry, artifact and UI checks; Python 3.11 cancellation disclosed | Global suite failed; this revision does not repair product assertions |
| C.11–C.12: captions and Manchester | Four distinct appendix Reading captions; positive Manchester working-day/incident-model provenance with local trace metres | Incident geographic coordinates/projection still unauthenticated |
| C.13: prose and counting | Added stakes/context in 1.1 and first-person reflection in 4.4; shortened repeated explanations; converter reports package and prose-only counts | Prose-only uses the package boundaries and additionally excludes table bodies and pseudocode; neither count certifies submission |
| C.14: references | Cho corrected to 2026, 25(5), 7166–7181 using the saved Crossref response | Both Fan papers retain bibliographic verification only; full-text reading is not claimed |
| D.4–D.6: delivery records | Updated this report, recording prerequisites, local verifier receipt, build/validation records and README/PR identity | Video recording, examiner access and final independent exact-SHA review remain open |

Cho verification: [Crossref DOI record](https://api.crossref.org/works/10.1109/TMC.2025.3640244), retrieved 15 September 2026, saved in `evidence/cho-crossref-2026-09-15.json`. The issue date is May 2026; the DOI's 2025 component does not set the issue year. The Fan citations in the added context identify research topics only; no detailed methodological or performance claim was added from unread full text.

The Table 3 validator accepts exactly the two requested disclosure rows after every original row. Original numerical table rows, equations, algorithms, proposition, Abstract and SVG sources remain protected against the frozen editorial package. Narrative updates to Tables 9, 10 and B1 are the explicitly requested evidence/limitation disclosures.

C.10 evidence correction: the supplied instruction classified all 56 failures as tier-4 UI presentation text assertions. The downloaded completed-job log identifies only five in that file, with the other failures distributed across provenance/ancestry, artifact and other UI tests. The manuscript reports the observed scope. `evidence/HOSTED_TEST_RESULT_2026-09-11.json` records every failing test ID and per-file counts; no product repair or new full-suite run is claimed.

## 15 September Introduction rebalance — input `62e26f6`

The follow-up restores the three full definition paragraphs and the argumentative Section 1.2 review from `23d9919`. Definition changes are limited to first-person decision voice. The review differs only by the requested removal of its opening provenance sentence and addition of the unevaluated `dla_p2c` sentence. The exact review diff is included in PR #142.

Only the two new passages were tightened: the Section 1.1 stakes and the four-paragraph Section 4.4 reflection. No other manuscript section was cut or changed. All table rows and all 27 captions match input head `62e26f6`; equations, algorithms, proposition, Abstract and SVG sources retain their protected checks.

The contents page leads with **7,853 prose-only words**, followed in the same sentence by **9,156 including table text and pseudocode**. The owner-set follow-up ceilings are 7,600–8,400 prose-only words and at most 9,300 package words; the validator now checks both. The 56-page XeLaTeX build passes all 38 checks, with zero duplicate Reading captions, overfull boxes, missing glyphs or unresolved references. All pages were rendered and inspected by the editing assistant. Item 1 of my author confirmation now uses first-person wording.

The current source/PDF hashes, scope assertions, build-log identity and fresh 938-file archive result are recorded in [the follow-up acceptance receipt](evidence/INTRO_BALANCE_2026-09-15.json). The earlier acceptance receipt remains a historical record of the preceding revision. Existing permission, access, preservation, institutional, video and independent-review boundaries remain open. No new scientific run or full regression-suite pass is claimed.

## 15 September citation attachments — input `582f84c`

| Request | Implemented change | Boundary still open |
|---|---|---|
| Citations | Twelve attachment points: (1) VEC execution modes, (2) deadline value, (3) mobility/radio change, (4) wider DRL offloading, (5) queue versus workload, (6) two choices, (7) common destinations/local updates, (8) digital twins, (9) Bonferroni intervals, (10) preregistration and sealed analysis, (11) float32 rounding in Appendix C.8, (12) JAX evaluator. Added 15 DOI entries and JAX, with all 41 entries numbered by first appearance. Only the authorised DRL clause changes prose. | Crossref identity/metadata verification only; I must read each abstract and cited section by eye before submission. JAX version/citation awaits my verification. The two Fan full-text checks remain open. |

The owner confirmed all 16 additions, correcting the requested total from 39 to 41. The optional 3GPP citation was omitted because no standard version was specified. Liu's VEC survey was published online in 2020, but its final issue 26(3), pages 1145–1168 is dated 2021; the bibliography uses that issue year. The Crossref record includes Ning's subtitle, “An Intelligent Offloading System”. JAX's official citation file at tag `jax-v0.4.30` retains a stale `0.3.13` field; the bibliography identifies the manuscript's recorded runtime version 0.4.30. [The dated registration receipt](evidence/reference-registration-2026-09-15.json) records all metadata, exact attachment sentences and renumbering.

The papers support the named general concepts. The evaluator's implementation and the timing of TrafficTwin's own sealed campaigns remain supported by the existing project evidence; the added scholarly citations do not independently verify those historical facts. No full-text reading, scientific run or new result is claimed.

Table 1 contained five plain literature labels that also required renumbering. They now use linked citations to the same five works; every other character of the table is preserved. The protection check permits exactly those five citation-label replacements, with all numerical results and comparison wording unchanged.

Citation-build acceptance: **7,877 prose-only words; 9,180 package words; 58 pages; 40/40 checks passed**. All 58 pages were rendered and inspected by the editing assistant; no visual defects were observed. All 15 DOI line checks passed. [The current acceptance receipt](evidence/CITATIONS_ACCEPTANCE_2026-09-15.json) binds source/PDF hashes, exact prose scope, protected content and the fresh 938-file archive result.

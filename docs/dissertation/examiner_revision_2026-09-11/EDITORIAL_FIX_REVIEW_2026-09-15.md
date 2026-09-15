# Six-point editorial review — 15 September 2026

Input: `7075b2576292cc9a98854bf5664449df66617b96`. The title remains **Dynamic Resource Management for Intelligent Transport Systems**, with no subtitle.

## Findings and fixes

| Item | Assessment | Implemented change |
|---|---|---|
| Table numbering | Valid | Main Table 10 → 8 and 11 → 9; Table 3a retained. All twenty table bodies unchanged. |
| Research-gap citations | Useful, with a correction | References 45 and 46 are cited in both Sections 1.2 and 3.5. Mitzenmacher supports stale-information herding; TrafficTwin's live-state mechanism is distinguished. arXiv:1905.04458 is Kovalenko et al., with Hussain second. Its federation result is compared under different simulator and placement assumptions. |
| Section 1.1 structure | Valid | Two short transition paragraphs merged verbatim into the actor paragraph; Figure 2 and its introduction/caption moved verbatim to 2.3; WHO sentence linked to timely information sharing as motivation. |
| Overall conclusion | Valid | Existing final sentence of 4.4 moved verbatim to open Section 4. |
| PDF metadata | Valid | Hyperref options now set the existing title and author, S M Abdulla Al Mamun. Verified in the PDF metadata. |
| Stale 3GPP note | Valid | AUTHOR_ACTIONS distinguishes the historical omission from the verified addition of reference 42, version 16.2.0. |

The requested description of Kovalenko et al. as using the same offered-load method with an opposite conclusion is not established by the paper. It reports deadline-miss rates for seeded workloads and federation beating no redirection, but its heterogeneous EdgeCloudSim setting, probabilistic placement and communication model differ. An identical offered/admitted/rejected accounting contract was not verified. TrafficTwin's causal per-task result is also favourable; therefore an opposite overall conclusion would overstate the comparison. No numerical result from that paper is imported. Grosof and Hyytiä were optional and are not added.

## Primary-source verification

- **45, Mitzenmacher (2000):** DOI 10.1109/71.824633 verified through Crossref; author-manuscript introduction and Section 3.4, printed p. 12, read for stale-information herding. The downloaded manuscript's page numbering is distinguished from journal pages 6–20.
- **46, Kovalenko et al. (2019):** DOI 10.1109/CFEC.2019.8733151 verified through Crossref; arXiv:1905.04458v1, Sections IV–VI, pp. 4–5, read for the algorithm, simulation setup and deadline-miss comparison. Author order and venue match Crossref.

[Registration with primary URLs, page locators and hashes](evidence/reference-registration-editorial-fixes-2026-09-15.json). References 1–44 remain byte-identical. These assistant checks do not certify the owner's reading.

## Moves and renumbering this round

| Source | Destination | Preserved content |
|---|---|---|
| 1.1 | 2.3 | “Figure 2 shows the authenticated morning RSU layout …”, image and complete caption |
| End of 4.4 | Opening of Section 4 | “Within the studied evaluator and matched populations …” |
| Main Table 10 | Main Table 8 | Validity-limit table rows |
| Main Table 11 | Main Table 9 | Objective-verdict table rows |

[Exact operation ledger](evidence/EDITORIAL_FIX_OPERATIONS_2026-09-15.json) records every source replacement. All earlier appendix moves and their pointers remain in place; [their full historical map](OPTION_B_CLOSE_REVIEW.md) is unchanged. The old scheduler Table 8 remains Appendix D/Table D2, and the old components Table 9 remains Appendix A/Table A1; the newly assigned main-text numbers refer to different tables.

The latest user request explicitly authorises the recorded changes in formerly protected Sections 1.2 and 3.5. The extended validator checks current tables, moves and citations, then reverses only a SHA256-pinned ledger to recover `7075b25` byte-for-byte before applying all existing title, closing and Option B guards. It does not claim current Section 1.2 is unchanged from `9b49efc`. Sections 3.2–3.4 and 3.6 remain byte-identical to the pre-review manuscript; 3.5 gains only the cited comparison sentence.

## Counts, build and verification

| Stage | Strict/package headline | Prose-only |
|---|---:|---:|
| Input `7075b25` | 8,914 | 7,714 |
| This revision | **8,938** | **7,738** |
| Limits | ≤ 8,950 | ≥ 7,600 |

The count rises by 24 words under both methods; the strict count remains 12 below the ceiling. Counting rules are unchanged. The contents page prints strict first. The PDF has **62 pages**, 20 tables and 8 figures.

- `validate_revision.py`: **178/178 passed**; `validate_option_b.py`: **131/131 passed**.
- [Six in-memory mutation probes](evidence/EDITORIAL_FIX_MUTATION_CHECKS_2026-09-15.json) reject an unauthorised argument edit, a removed new citation, a table-body change, duplicate Figure 2, rewritten conclusion and altered earlier appendix text.
- XeLaTeX/latexmk build clean: zero overfull boxes, missing glyphs, undefined references or duplicate caption readings. All pages rendered and inspected; detailed visual review in [acceptance](evidence/EDITORIAL_FIX_ACCEPTANCE_2026-09-15.json).
- Ruff lint and format checks pass for all six document Python files. No new scientific runs or global product-test claims. Prior compact arithmetic and archive receipts remain historical evidence.

## Artifact identity

- Markdown SHA256: `f3867b5ff9d2937faab842b14409914e2747452e1cc2c5093961b2860f394537`.
- TeX SHA256: `ab1cd44adecfa4f8feb82783c1908d12e986c234275a0df4596b7ded1b0fa524`.
- PDF SHA256: `33244964119ca80406200004460ab335cd446bae26213356facf6375134f6dcd`.

[Build log](evidence/latexmk-editorial-fixes-2026-09-15.log) · [grep table](evidence/EDITORIAL_FIX_GREP_2026-09-15.json) · [combined validation](document/REVISION_VALIDATION.json).

## Open gates

AI-use permission, award wording/student ID, prescribed copyright and signed declarations, examiner access to the private repositories/evidence, and the recorded assessed video remain open. The owner-confirmed ethics-tool outcome remains recorded as an author check. Editing does not close these gates. The PR remains draft; an independent review of the exact pushed SHA is recorded in its body after push. Formal integration approval is not claimed.
